# green_agent/runner.py
from __future__ import annotations

import csv
import json
import os
import random
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Iterable

from rich.console import Console
from rich.progress import (
    BarColumn,
    MofNCompleteColumn,
    Progress,
    TextColumn,
    TimeElapsedColumn,
    TimeRemainingColumn,
)
from rich.table import Table

from purple_agent.react_dspy.react_agent import ReActDSPyPurpleAgent

from .config import EvalConfig
from .metrics import compute_metrics
from .plan_parser import extract_plan
from .tools_backend import compile_plan

console = Console()


# ---------------------------
# Small IO helpers
# ---------------------------


def load_text(path: str | None) -> str:
    if not path:
        return ""
    with open(path, encoding="utf-8") as f:
        return f.read().strip()


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text or "", encoding="utf-8")


def _write_text_lossy(path: Path, text: str) -> None:
    # For subprocess stdout/stderr dumps
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", errors="replace") as f:
        f.write(text or "")


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


# ---------------------------
# Purple builder
# ---------------------------


def build_purple(
    kind: str,
    *,
    model: str | None,
    a2a_url: str | None,
    base_url: str | None = None,
    api_key: str | None = None,
    strategy_name: str | None = None,
    strategy_params: dict | None = None,
):
    if kind == "openai":
        from purple_agent.openai_agent import OpenAIPurpleAgent

        return OpenAIPurpleAgent(model=model, base_url=base_url, api_key=api_key)

    if kind == "a2a":
        if not a2a_url:
            raise SystemExit("Missing purple_url for 'a2a' purple.")
        from purple_agent.a2a_agent import A2APurpleAgent

        return A2APurpleAgent(url=a2a_url)

    if kind in ("strategy", "composite"):
        from purple_agent.strategy_agent import StrategyPurpleAgent

        params = strategy_params or {}
        roles = params.get("roles", {})
        settings = params.get("settings", {})
        if not (strategy_name and roles):
            raise SystemExit("strategy kind requires strategy_name and strategy_params.roles")
        return StrategyPurpleAgent(strategy_name=strategy_name, roles=roles, settings=settings)

    if kind == "react_dspy":
        return ReActDSPyPurpleAgent(
            model=model,
            base_url=base_url,
            api_key=api_key,
            temperature=0.2,
        )

    raise SystemExit(f"Unknown purple kind: {kind!r}")


# ---------------------------
# Run directory + scoring
# ---------------------------


def _make_run_dir(base_out: str, domain_path: str) -> str:
    example = Path(domain_path).parent.name or "run"
    stamp = time.strftime("%Y%m%d-%H%M%S")
    run_dir = Path(base_out) / f"{example}-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=True)
    return str(run_dir)


def _score_from(metrics, optimal_cost: float | None) -> float | None:
    # Keep old behavior:
    # - invalid => 0.0
    # - valid but no optimal_cost => None (excluded from total_score)
    if not metrics.valid:
        return 0.0
    oc = optimal_cost
    cost = metrics.cost_value
    if oc is not None and cost is not None and cost > 0:
        return float(oc) / float(cost)
    return None


# ---------------------------
# Plan normalization + VAL dump
# ---------------------------


def _normalize_plan(domain_path: str, plan_raw: str) -> tuple[str, list[str]]:
    """
    Try:
      1) PDDL plan extraction (preferred)
      2) fallback: NL action-id compilation
    Returns: (plan_txt, errors)
    """
    extracted = extract_plan(plan_raw)
    plan_txt = extracted.to_val_plan_text()

    if plan_txt.strip():
        return plan_txt, []

    domain_name = Path(domain_path).parent.name
    plan_txt, errors = compile_plan(domain_name, plan_raw)

    # If compiler produced errors, treat plan as unusable (preserves old behavior)
    if errors:
        return "", errors

    return plan_txt, []


def _dump_val_artifacts(run_dir: Path, metrics) -> dict[str, str]:
    """
    Writes:
      - val_stdout.txt
      - val_stderr.txt
      - val_trace.json
    Returns the paths as strings.
    """
    val_stdout_path = run_dir / "val_stdout.txt"
    val_stderr_path = run_dir / "val_stderr.txt"
    trace_path = run_dir / "val_trace.json"

    _write_text_lossy(val_stdout_path, metrics.val_stdout or "")
    _write_text_lossy(val_stderr_path, metrics.val_stderr or "")

    _write_json(
        trace_path,
        [
            {
                "time": st.time,
                "action": st.action,
                "adds": st.adds,
                "deletes": st.deletes,
                "failed": st.failed,
                "failure_detail": st.failure_detail,
            }
            for st in metrics.steps
        ],
    )

    return {
        "val_stdout_path": str(val_stdout_path),
        "val_stderr_path": str(val_stderr_path),
        "val_trace_path": str(trace_path),
    }


def _print_card(metrics, *, llm_latency_s: float, title: str = "Green Agent — Plan Evaluation") -> None:
    table = Table(title=title)
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Valid", str(metrics.valid))
    if not metrics.valid:
        table.add_row("Reason", metrics.failure_reason or "unknown")
    table.add_row("Length", str(metrics.length))
    table.add_row("Cost/Value", str(metrics.cost_value))
    table.add_row("First failure at", str(metrics.first_failure_at))
    table.add_row("First failed action", metrics.first_failed_action or "—")
    table.add_row("First failure reason", metrics.first_failure_reason or "—")
    table.add_row("First failure details", metrics.first_failure_detail or "—")
    table.add_row("Unsat preconds", str(metrics.unsat_count))
    if metrics.redundant_indices:
        table.add_row("Redundant steps", ", ".join(map(str, metrics.redundant_indices)) or "—")
    table.add_row("Advice fixes", str(metrics.advice_count))
    table.add_row(
        "Advice top preds",
        ", ".join(f"{p}:{c}" for p, c in metrics.advice_top_predicates) or "—",
    )
    table.add_row("LLM Latency (s)", f"{llm_latency_s:.2f}")
    table.add_row("VAL attempts", str(getattr(metrics, "val_attempts", 1)))
    if getattr(metrics, "val_warning", None):
        table.add_row("Warning", metrics.val_warning)
    console.print(table)


# ---------------------------
# Single evaluation
# ---------------------------


def evaluate_once(cfg: EvalConfig) -> dict[str, Any]:
    run_dir = Path(cfg.run_dir or _make_run_dir(cfg.out_dir, cfg.domain_path))
    run_dir.mkdir(parents=True, exist_ok=True)

    problem_nl = (cfg.prompt_text or load_text(cfg.prompt_path) or "").strip()

    purple = build_purple(
        cfg.purple_kind,
        model=cfg.openai_model,
        a2a_url=cfg.purple_url,
        base_url=cfg.llm_base_url,
        api_key=cfg.llm_api_key,
        strategy_name=cfg.strategy_name,
        strategy_params=cfg.strategy_params,
    )

    t0 = time.time()
    plan_raw = purple.generate_plan(problem_nl=problem_nl)
    t1 = time.time()

    raw_path = run_dir / "purple_raw.txt"
    _write_text(raw_path, plan_raw)

    plan_txt, _errors = _normalize_plan(cfg.domain_path, plan_raw)

    plan_path = run_dir / "purple.plan"
    _write_text(plan_path, plan_txt)

    flags = (*cfg.val_flags, "-t", str(cfg.tolerance))
    metrics = compute_metrics(
        domain=cfg.domain_path,
        problem=cfg.problem_path,
        plan_text=plan_txt,
        val_path=cfg.val_path,
        flags=flags,
        check_redundancy=cfg.check_redundancy,
    )

    dumped = _dump_val_artifacts(run_dir, metrics)

    if cfg.print_card:
        _print_card(metrics, llm_latency_s=(t1 - t0))

    score = _score_from(metrics, cfg.optimal_cost)

    return {
        "domain": cfg.domain_path,
        "problem": cfg.problem_path,
        "valid": metrics.valid,
        "length": metrics.length,
        "cost_value": metrics.cost_value,
        "optimal_cost": cfg.optimal_cost,
        "score": score,
        "first_failure_at": metrics.first_failure_at,
        "first_failed_action": metrics.first_failed_action,
        "first_failure_reason": metrics.first_failure_reason,
        "first_failure_detail": metrics.first_failure_detail,
        "unsat_count": metrics.unsat_count,
        "redundant_indices": metrics.redundant_indices,
        "advice_count": metrics.advice_count,
        "advice_top_predicates": metrics.advice_top_predicates,
        "raw_plan_path": str(raw_path),
        "norm_plan_path": str(plan_path),
        "failure_reason": metrics.failure_reason,
        "run_dir": str(run_dir),
        "val_attempts": getattr(metrics, "val_attempts", 1),
        "val_warning": getattr(metrics, "val_warning", None),
        **dumped,
    }


# ---------------------------
# Batch/domain evaluation
# ---------------------------


def _parse_problem_index(pid: str) -> int | None:
    pid = (pid or "").strip()
    if not pid:
        return None
    try:
        return int(pid[1:]) if pid.lower().startswith("p") else int(pid)
    except Exception:
        return None


def _iter_jobs(problems: Iterable[dict], *, start: int | None, end: int | None) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for item in problems:
        pid = str(item.get("id", "")).strip()
        idx = _parse_problem_index(pid)
        if idx is None:
            continue
        if start is not None and idx < start:
            continue
        if end is not None and idx > end:
            continue
        items.append({"pid": pid, "idx": idx, "entry": item})
    # Stable ordering helps reproducibility and easier diffs
    items.sort(key=lambda x: x["idx"])
    return items


def evaluate_domain(
    cfg_base: EvalConfig,
    *,
    start: int | None = None,
    end: int | None = None,
    print_cards: bool = False,
    llm_workers: int = 4,
    val_workers: int = 1,
) -> dict[str, Any]:
    domain_dir = Path(cfg_base.domain_path).parent
    problems_dir = domain_dir / "problems_pddl"
    prompts_path = domain_dir / "prompts.json"

    if not prompts_path.exists():
        raise FileNotFoundError(f"Missing prompts.json at: {prompts_path}")
    if not problems_dir.exists():
        raise FileNotFoundError(f"Missing problems_pddl directory at: {problems_dir}")

    with open(prompts_path, encoding="utf-8") as f:
        data = json.load(f)

    domain_prompt = (data.get("domain_prompt") or "").strip()
    problems = data.get("problems", [])
    jobs = _iter_jobs(problems, start=start, end=end)

    stamp = time.strftime("%Y%m%d-%H%M%S")
    batch_root = Path(cfg_base.out_dir) / f"{domain_dir.name}-{stamp}"
    batch_root.mkdir(parents=True, exist_ok=True)

    # ---------- LLM generation stage ----------

    def _gen_job(job: dict[str, Any]) -> dict[str, Any]:
        pid = job["pid"]
        idx = job["idx"]
        entry = job["entry"]

        prob_dir = batch_root / pid
        prob_dir.mkdir(parents=True, exist_ok=True)

        problem_pddl = problems_dir / f"problem{idx}.pddl"
        prompt_text = (domain_prompt + "\n\n" + str(entry.get("prompt", "")).strip()).strip()
        oc = entry.get("optimal_cost")

        cfg = EvalConfig(
            domain_path=cfg_base.domain_path,
            problem_path=str(problem_pddl),
            out_dir=str(batch_root),
            run_dir=str(prob_dir),
            val_path=cfg_base.val_path,
            val_flags=cfg_base.val_flags,
            tolerance=cfg_base.tolerance,
            purple_kind=cfg_base.purple_kind,
            purple_url=cfg_base.purple_url,
            prompt_text=prompt_text,
            openai_model=cfg_base.openai_model,
            check_redundancy=cfg_base.check_redundancy,
            llm_base_url=cfg_base.llm_base_url,
            llm_api_key=cfg_base.llm_api_key,
            optimal_cost=oc,
            print_card=False,
            strategy_name=cfg_base.strategy_name,
            strategy_params=cfg_base.strategy_params,
        )

        purple = build_purple(
            cfg.purple_kind,
            model=cfg.openai_model,
            a2a_url=cfg.purple_url,
            base_url=cfg.llm_base_url,
            api_key=cfg.llm_api_key,
            strategy_name=cfg.strategy_name,
            strategy_params=cfg.strategy_params,
        )

        t0 = time.time()
        plan_raw = purple.generate_plan(problem_nl=cfg.prompt_text or "")
        # optional jitter to reduce bursty rate-limit behavior; keep it small
        time.sleep(random.uniform(0.05, 0.15))
        t1 = time.time()

        run_dir = Path(cfg.run_dir)
        raw_path = run_dir / "purple_raw.txt"
        _write_text(raw_path, plan_raw)

        plan_txt, _errors = _normalize_plan(cfg.domain_path, plan_raw)
        plan_path = run_dir / "purple.plan"
        _write_text(plan_path, plan_txt)

        return {
            "pid": pid,
            "idx": idx,
            "problem_path": str(problem_pddl),
            "optimal_cost": oc,
            "run_dir": str(run_dir),
            "norm_plan_path": str(plan_path),
            "raw_plan_path": str(raw_path),
            "plan_text": plan_txt,  # avoid re-reading file during VAL stage
            "llm_latency": t1 - t0,
        }

    # ---------- VAL stage ----------

    def _val_job(r: dict[str, Any]) -> dict[str, Any]:
        run_dir = Path(r["run_dir"])
        plan_txt = r.get("plan_text") or ""

        flags = (*cfg_base.val_flags, "-t", str(cfg_base.tolerance))
        metrics = compute_metrics(
            domain=cfg_base.domain_path,
            problem=r["problem_path"],
            plan_text=plan_txt,
            val_path=cfg_base.val_path,
            flags=flags,
            check_redundancy=cfg_base.check_redundancy,
        )

        dumped = _dump_val_artifacts(run_dir, metrics)

        if print_cards:
            _print_card(metrics, llm_latency_s=float(r.get("llm_latency", 0.0)), title=f"Problem {r['pid']}")

        score = _score_from(metrics, r.get("optimal_cost"))
        return {
            **{k: v for k, v in r.items() if k != "plan_text"},
            "valid": metrics.valid,
            "length": metrics.length,
            "cost_value": metrics.cost_value,
            "score": score,
            "first_failure_at": metrics.first_failure_at,
            "first_failed_action": metrics.first_failed_action,
            "first_failure_reason": metrics.first_failure_reason,
            "first_failure_detail": metrics.first_failure_detail,
            "unsat_count": metrics.unsat_count,
            "redundant_indices": metrics.redundant_indices,
            "advice_count": metrics.advice_count,
            "advice_top_predicates": metrics.advice_top_predicates,
            "failure_reason": metrics.failure_reason,
            "val_attempts": getattr(metrics, "val_attempts", 1),
            "val_warning": getattr(metrics, "val_warning", None),
            **dumped,
        }

    # ---------- Progress + execution ----------

    progress_columns = [
        TextColumn("[bold blue]{task.description}"),
        BarColumn(),
        MofNCompleteColumn(),
        TextColumn("•"),
        TimeElapsedColumn(),
        TextColumn("• ETA "),
        TimeRemainingColumn(),
    ]

    llm_workers = max(1, int(llm_workers))
    val_workers = max(1, int(val_workers))

    llm_results: list[dict[str, Any]] = []
    final_results: list[dict[str, Any]] = []

    with Progress(*progress_columns, console=console) as progress:
        t_llm = progress.add_task("Generating plans (LLM)", total=len(jobs))
        with ThreadPoolExecutor(max_workers=llm_workers) as pool:
            futures = [pool.submit(_gen_job, job) for job in jobs]
            for fut in as_completed(futures):
                llm_results.append(fut.result())
                progress.update(t_llm, advance=1)

        # Sort again to keep output stable even though as_completed is unordered
        llm_results.sort(key=lambda x: x["idx"])

        t_val = progress.add_task("Validating plans (VAL)", total=len(llm_results))
        if val_workers == 1:
            for r in llm_results:
                final_results.append(_val_job(r))
                progress.update(t_val, advance=1)
        else:
            with ThreadPoolExecutor(max_workers=val_workers) as pool:
                futures = [pool.submit(_val_job, r) for r in llm_results]
                for fut in as_completed(futures):
                    final_results.append(fut.result())
                    progress.update(t_val, advance=1)
            final_results.sort(key=lambda x: x["idx"])

    # ---------- Relative paths + save artifacts ----------

    results: list[dict[str, Any]] = []
    for rec in final_results:
        # Convert selected paths to paths relative to batch_root (nicer output)
        for k in (
            "raw_plan_path",
            "norm_plan_path",
            "val_stdout_path",
            "val_stderr_path",
            "val_trace_path",
            "run_dir",
        ):
            if rec.get(k):
                try:
                    rec[k] = str(Path(rec[k]).relative_to(batch_root))
                except Exception:
                    pass
        rec["problem_id"] = rec["pid"]
        results.append(rec)

    jsonl_path = batch_root / "results.jsonl"
    with open(jsonl_path, "w", encoding="utf-8") as f:
        for r in results:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    n = len(results)
    counts_by_reason: defaultdict[str, int] = defaultdict(int)
    for r in results:
        if r.get("valid"):
            counts_by_reason["valid"] += 1
        else:
            reason = r.get("failure_reason") or "unknown_failure"
            counts_by_reason[reason] += 1
    counts_by_reason = dict(sorted(counts_by_reason.items(), key=lambda kv: kv[0]))

    scores = [r.get("score") for r in results if isinstance(r.get("score"), (int, float))]
    total_score = sum(scores) if scores else 0.0

    summary = {
        "domain": str(domain_dir),
        "root_dir": str(batch_root),
        "results_path": str(jsonl_path),
        "count": n,
        "total_score": total_score,
        "scores": {r["problem_id"]: r.get("score") for r in results},
        "counts_by_reason": counts_by_reason,
    }

    _write_json(batch_root / "domain_summary.json", summary)

    csv_path = batch_root / "scores.csv"
    with open(csv_path, "w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(
            [
                "problem_id",
                "valid",
                "optimal_cost",
                "cost_value",
                "score",
                "failure_reason",
                "val_attempts",
                "val_warning",
                "llm_latency_s",
            ]
        )
        for r in results:
            w.writerow(
                [
                    r.get("problem_id"),
                    r.get("valid"),
                    r.get("optimal_cost"),
                    r.get("cost_value"),
                    r.get("score"),
                    r.get("failure_reason"),
                    r.get("val_attempts"),
                    r.get("val_warning"),
                    f"{r.get('llm_latency', 0.0):.2f}",
                ]
            )

    table = Table(title=f"Domain Summary — {domain_dir.name}")
    table.add_column("Metric")
    table.add_column("Value")
    table.add_row("Problems", str(n))
    table.add_row("Total Score", f"{total_score:.4f}")
    console.print(table)

    if counts_by_reason:
        console.print("Outcome breakdown (reason -> count):")
        for reason, count in counts_by_reason.items():
            console.print(f"  - {reason}: {count}")

    console.print(f"[results.jsonl]  {jsonl_path}")
    console.print(f"[summary.json]   {batch_root / 'domain_summary.json'}")
    console.print(f"[scores.csv]     {csv_path}")

    return summary
