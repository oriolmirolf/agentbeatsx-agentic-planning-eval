from __future__ import annotations

import json
import os
from pathlib import Path

import typer

from .config import EvalConfig
from .runner import (  # validate_existing_plan removed earlier
    evaluate_domain,
    evaluate_once,
)

app = typer.Typer(help="Green Agent: PDDL plan benchmark runner")


def _resolve_paths(domain: str | None, index: int | None) -> dict[str, str | None]:
    """
    Layout:
      examples/<domain>/
        - domain.pddl
        - problems_pddl/problem{index}.pddl
        - prompts.json (with 'domain_prompt' and 'problems':
            [{id:'pNN', prompt:'...', optimal_cost:...}, ...])
    """
    if not domain:
        return {
            "domain": None,
            "problem": None,
            "prompt_text": None,
            "prompts_json": None,
            "optimal_cost": None,
        }

    base = Path("examples") / domain
    domain_pddl = base / "domain.pddl"
    problems_dir = base / "problems_pddl"
    prompts_json = base / "prompts.json"

    def ok(p: Path) -> str | None:
        return str(p) if p.exists() else None

    prompt_text: str | None = None
    optimal_cost: float | None = None
    problem_path: str | None = None

    # Compose NL prompt from prompts.json (domain_prompt + specific problem prompt)
    if prompts_json.exists() and index is not None:
        with open(prompts_json, encoding="utf-8") as f:
            data = json.load(f)
        domain_prompt = (data.get("domain_prompt") or "").strip()
        pid = f"p{int(index):02d}"
        entry = next(
            (p for p in data.get("problems", []) if str(p.get("id")) == pid), None
        )
        if entry:
            prompt_text = (
                domain_prompt + "\n\n" + str(entry.get("prompt", "")).strip()
            ).strip()
            try:
                oc = entry.get("optimal_cost", None)
                optimal_cost = float(oc) if oc is not None else None
            except Exception:
                optimal_cost = None

    if index is not None:
        pp = problems_dir / f"problem{index}.pddl"
        problem_path = ok(pp)

    return {
        "domain": ok(domain_pddl),
        "problem": problem_path,
        "prompt_text": prompt_text,
        "prompts_json": ok(prompts_json),
        "optimal_cost": optimal_cost,
    }


def _val_flags(advice: bool) -> tuple[str, ...]:
    # Default: "-v" only (no "-e"). If advice is requested, add "-e".
    return ("-v", "-e") if advice else ("-v",)


@app.command()
def evaluate(
    # problem selection
    domain: str | None = typer.Option(
        None, help="Domain folder under ./examples (e.g., 'blocks')"
    ),
    index: int | None = typer.Option(None, help="Problem index"),
    # purple agent selection
    purple: str = typer.Option("openai", help="openai | a2a | react | langchain-react"),
    purple_url: str | None = typer.Option(
        None, help="A2A endpoint of the purple agent (required if --purple a2a)"
    ),
    out: str = typer.Option("out", help="Output directory"),
    val_path: str | None = typer.Option(None, help="Path to VAL (Validate) binary"),
    # LLM / model config
    model: str | None = typer.Option(
        None, help="Model name (e.g., gpt-4o-mini or local model id)"
    ),
    llm_base_url: str | None = typer.Option(
        None, help="OpenAI-compatible base URL (e.g., http://localhost:8000/v1)"
    ),
    llm_api_key: str | None = typer.Option(
        None, help="API key for base URL (overrides env if set)"
    ),
    check_redundancy: bool = typer.Option(False, help="Check redundant actions (slow)"),
    advice: bool = typer.Option(
        False, help="Enable VAL plan repair advice (-e). Avoid for stability."
    ),
):
    auto = _resolve_paths(domain, index)
    domain_path = auto["domain"]
    problem = auto["problem"]
    prompt_text = auto["prompt_text"]
    optimal_cost = auto["optimal_cost"]

    if not domain_path or not problem:
        raise typer.BadParameter(
            "Could not resolve domain/problem paths. Use --domain (and --index)."
        )

    cfg = EvalConfig(
        domain_path=domain_path,
        problem_path=problem,
        out_dir=out,
        val_path=val_path,
        purple_kind=purple,
        purple_url=purple_url,
        prompt_text=prompt_text,
        openai_model=model,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        check_redundancy=check_redundancy,
        optimal_cost=optimal_cost,
        val_flags=_val_flags(advice),
        print_card=True,
    )

    record = evaluate_once(cfg)

    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "record.json"), "a", encoding="utf-8") as f:
        f.write(json.dumps(record) + "\n")


@app.command("evaluate-domain")
def evaluate_domain_cmd(
    domain: str = typer.Option(
        ..., help="Domain folder name under ./examples (e.g., 'blocks')"
    ),
    start: int | None = typer.Option(None, help="First index to include"),
    end: int | None = typer.Option(None, help="Last index to include"),
    purple: str = typer.Option("openai", help="openai | a2a | react | langchain-react"),
    purple_url: str | None = typer.Option(None, help="A2A endpoint (if --purple a2a)"),
    out: str = typer.Option("out", help="Output directory"),
    val_path: str | None = typer.Option(None, help="Path to VAL (Validate) binary"),
    # LLM / model config
    model: str | None = typer.Option(None, help="Model name"),
    llm_base_url: str | None = typer.Option(
        None, help="OpenAI-compatible base URL (e.g., http://localhost:8000/v1)"
    ),
    llm_api_key: str | None = typer.Option(None, help="API key for base URL"),
    check_redundancy: bool = typer.Option(False, help="Check redundant actions (slow)"),
    advice: bool = typer.Option(
        False, help="Enable VAL plan repair advice (-e). Avoid for stability."
    ),
    strategy_name: str | None = typer.Option(
        None,
        help="Run composite strategy via purple 'strategy' kind",
    ),
    strategy_file: str | None = typer.Option(
        None, help="YAML/JSON with 'roles' and 'settings' for the chosen strategy"
    ),
    show_cards: bool = typer.Option(False, help="Print per-problem cards during batch"),
    llm_workers: int = typer.Option(4, help="Parallel threads for LLM calls"),
    val_workers: int = typer.Option(
        1, help="Parallel threads for VAL (1 = sequential)"
    ),
):
    auto = _resolve_paths(domain, 1)
    if not auto["domain"]:
        raise typer.BadParameter("Could not resolve domain.pddl. Check --domain.")

    # load strategy params if provided
    sparams = None
    if strategy_file:
        import pathlib

        import yaml

        p = pathlib.Path(strategy_file)
        sparams = (
            json.loads(p.read_text())
            if p.suffix.lower() in (".json",)
            else yaml.safe_load(p.read_text())
        )

    cfg_base = EvalConfig(
        domain_path=auto["domain"],
        problem_path="",
        out_dir=out,
        val_path=val_path,
        purple_kind=("strategy" if strategy_name else purple),
        purple_url=purple_url,
        prompt_text=None,
        openai_model=model,
        llm_base_url=llm_base_url,
        llm_api_key=llm_api_key,
        check_redundancy=check_redundancy,
        val_flags=_val_flags(advice),
        print_card=False,
        strategy_name=strategy_name,
        strategy_params=sparams,
    )

    agg = evaluate_domain(
        cfg_base,
        start=start,
        end=end,
        print_cards=show_cards,
        llm_workers=llm_workers,
        val_workers=val_workers,
    )

    # pointers + concise JSON
    from pathlib import Path as _P

    typer.echo(f"[domain-run root] {agg['root_dir']}")
    typer.echo(f"[results.jsonl]  {agg['results_path']}")
    typer.echo(f"[summary.json]   {_P(agg['root_dir']) / 'domain_summary.json'}")
    typer.echo(f"[scores.csv]     {_P(agg['root_dir']) / 'scores.csv'}")
    typer.echo(
        json.dumps(
            {
                "count": agg["count"],
                "total_score": agg["total_score"],
                "counts_by_reason": agg.get("counts_by_reason", {}),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    app()
