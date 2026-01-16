# green_agent/evaluation.py
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from .metrics import PlanMetrics, compute_metrics
from .plan_parser import extract_plan
from .tools_backend import compile_plan

from .val_utils import auto_detect_val_path

@dataclass(frozen=True)
class ParseResult:
    plan_text: str
    parsed_ok: bool
    parse_method: str  # "pddl_extract" | "nl_compile" | "empty"
    parse_errors: list[str]


@dataclass(frozen=True)
class EvalArtifacts:
    raw_response_path: Path
    plan_path: Path
    val_stdout_path: Path
    val_stderr_path: Path
    val_trace_path: Path


@dataclass(frozen=True)
class EvalResult:
    success: int  # 1 if output parsed, else 0 (your existing requirement)
    llm_duration_seconds: float
    eval_duration_seconds: float
    total_duration_seconds: float

    parse: ParseResult
    metrics: PlanMetrics | None
    failure: str | None
    artifacts: EvalArtifacts | None

    def to_mlflow_metrics(self) -> dict[str, float]:
        out: dict[str, float] = {
            "success": float(self.success),
            "duration_seconds": float(self.llm_duration_seconds),
            "eval_duration_seconds": float(self.eval_duration_seconds),
            "total_duration_seconds": float(self.total_duration_seconds),
        }
        if self.metrics is not None:
            out["valid"] = float(1.0 if self.metrics.valid else 0.0)
            out["plan_length"] = float(self.metrics.length)
            out["unsat_preconds"] = float(self.metrics.unsat_count)
            if self.metrics.cost_value is not None:
                out["plan_cost_value"] = float(self.metrics.cost_value)
        return out


def parse_plan(domain_name: str, raw_model_text: str) -> ParseResult:
    extracted = extract_plan(raw_model_text or "")
    plan_txt = extracted.to_val_plan_text()

    if plan_txt.strip():
        return ParseResult(
            plan_text=plan_txt,
            parsed_ok=True,
            parse_method="pddl_extract",
            parse_errors=[],
        )

    plan_txt2, errors = compile_plan(domain_name, raw_model_text or "")
    if plan_txt2.strip() and not errors:
        return ParseResult(
            plan_text=plan_txt2,
            parsed_ok=True,
            parse_method="nl_compile",
            parse_errors=[],
        )

    if plan_txt2.strip() and errors:
        return ParseResult(
            plan_text=plan_txt2,
            parsed_ok=False,
            parse_method="nl_compile",
            parse_errors=errors,
        )

    return ParseResult(
        plan_text="",
        parsed_ok=False,
        parse_method="empty",
        parse_errors=errors if isinstance(errors, list) else [],
    )


def evaluate_with_val(
    *,
    domain_pddl: Path,
    problem_pddl: Path,
    plan_text: str,
    val_path: str | None,
    val_flags: tuple[str, ...],
    tolerance: float,
    check_redundancy: bool = False,
    is_ground_truth_solvable: bool = True,
) -> PlanMetrics:
    flags = (*val_flags, "-t", str(float(tolerance)))
    
    if not val_path:
        val_path = auto_detect_val_path()
    
    return compute_metrics(
        domain=str(domain_pddl),
        problem=str(problem_pddl),
        plan_text=plan_text,
        val_path=val_path,
        flags=flags,
        check_redundancy=check_redundancy,
        is_ground_truth_solvable=is_ground_truth_solvable,
    )


def write_artifacts(
    *,
    out_dir: Path,
    raw_text: str,
    plan_text: str,
    metrics: PlanMetrics | None,
) -> EvalArtifacts:
    out_dir.mkdir(parents=True, exist_ok=True)

    raw_path = out_dir / "raw_response.txt"
    raw_path.write_text(raw_text or "", encoding="utf-8")

    plan_path = out_dir / "plan.plan"
    plan_path.write_text(plan_text or "", encoding="utf-8")

    val_stdout_path = out_dir / "val_stdout.txt"
    val_stderr_path = out_dir / "val_stderr.txt"
    val_trace_path = out_dir / "val_trace.json"

    if metrics is not None:
        val_stdout_path.write_text(metrics.val_stdout or "", encoding="utf-8", errors="replace")
        val_stderr_path.write_text(metrics.val_stderr or "", encoding="utf-8", errors="replace")
        with val_trace_path.open("w", encoding="utf-8") as f:
            json.dump(
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
                f,
                ensure_ascii=False,
                indent=2,
            )
    else:
        val_stdout_path.write_text("", encoding="utf-8")
        val_stderr_path.write_text("", encoding="utf-8")
        val_trace_path.write_text("[]\n", encoding="utf-8")

    return EvalArtifacts(
        raw_response_path=raw_path,
        plan_path=plan_path,
        val_stdout_path=val_stdout_path,
        val_stderr_path=val_stderr_path,
        val_trace_path=val_trace_path,
    )


__all__ = [
    "ParseResult",
    "EvalArtifacts",
    "EvalResult",
    "parse_plan",
    "evaluate_with_val",
    "write_artifacts",
]
