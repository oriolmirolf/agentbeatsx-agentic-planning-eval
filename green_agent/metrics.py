# green_agent/metrics.py
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .val_wrapper import TraceStep, run_val

# Header lines in "Plan Repair Advice":
# "(move-small ...) has an unsatisfied precondition at time 2"
_ADVICE_HDR_RE = re.compile(
    r"\(([^)]+)\)\s+has an unsatisfied precondition at time\s+(\d+)", re.IGNORECASE
)

# Advice lines:
# "Set (isoccupied loc3_6) to false"  OR  "Set (adjacent …) to true"
#  -> capture atom + desired truth value
_ADVICE_SET_RE = re.compile(r"Set\s*\(([^)]+)\)\s*to\s*(true|false)", re.IGNORECASE)

def is_plan_unsolvable(text: str) -> bool:
    """
    Detects if the model claimed the instance is unsolvable.
    Handles:
      UNSOLVABLE
      ```UNSOLVABLE```
      ```text\nUNSOLVABLE\n```
    """
    if not text:
        return False

    # Normalize: remove markdown fences and whitespace
    clean = text.replace("```", "").strip().upper()

    # Check for exact keyword or single line
    if clean == "UNSOLVABLE":
        return True

    # Check if it appears as a distinct line in a larger block
    lines = [L.strip().upper() for L in text.splitlines()]
    return "UNSOLVABLE" in lines

@dataclass(slots=True)
class PlanMetrics:
    valid: bool
    length: int
    cost_value: float | None
    first_failure_at: int | None
    unsat_count: int
    redundant_indices: list[int] | None
    failure_reason: str | None

    first_failed_action: str | None
    first_failure_reason: str | None
    first_failure_detail: str | None

    # Advice-derived signal
    advice_count: int
    advice_top_predicates: list[tuple[str, int]]

    # raw logs
    val_stdout: str
    val_stderr: str
    # optional trace
    steps: list[TraceStep]

    # VAL retry diagnostics
    val_attempts: int
    val_warning: str | None

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "length": self.length,
            "cost_value": self.cost_value,
            "first_failure_at": self.first_failure_at,
            "unsat_count": self.unsat_count,
            "redundant_indices": self.redundant_indices,
            "failure_reason": self.failure_reason,
            "first_failed_action": self.first_failed_action,
            "first_failure_reason": self.first_failure_reason,
            "first_failure_detail": self.first_failure_detail,
            "advice_count": self.advice_count,
            "advice_top_predicates": self.advice_top_predicates,
            "val_attempts": self.val_attempts,
            "val_warning": self.val_warning,
        }


def _parse_advice_by_time(stdout: str) -> dict[int, list[tuple[str, bool]]]:
    """
    Parse VAL's 'Plan Repair Advice' into: time -> list of (atom, desired_value)
    desired_value is True if advice says 'to true', else False.
    """
    lines = (stdout or "").splitlines()
    advice: dict[int, list[tuple[str, bool]]] = {}

    i = 0
    n = len(lines)
    while i < n:
        hdr = _ADVICE_HDR_RE.search(lines[i])
        if not hdr:
            i += 1
            continue

        try:
            t = int(hdr.group(2))
        except ValueError:
            t = None

        j = i + 1
        pairs: list[tuple[str, bool]] = []
        while j < n and not _ADVICE_HDR_RE.search(lines[j]):
            mset = _ADVICE_SET_RE.search(lines[j])
            if mset:
                atom = mset.group(1).strip()
                desired_raw = mset.group(2).strip().lower()
                desired = desired_raw == "true"
                pairs.append((atom, desired))
            j += 1

        if t is not None and pairs:
            advice.setdefault(t, []).extend(pairs)

        i = j

    return advice


def compute_metrics(
    *,
    domain: str,
    problem: str,
    plan_text: str,
    val_path: str | None = None,
    flags: tuple[str, ...] = ("-v",),
    check_redundancy: bool = False,
    is_ground_truth_solvable: bool = True,
) -> PlanMetrics:
    # 1. Check for Unsolvable Claim
    if is_plan_unsolvable(plan_text):
        # If the problem is actually unsolvable, this "plan" is valid (correct refusal).
        # If the problem IS solvable, this is a False Negative (invalid plan).
        is_correct_refusal = (not is_ground_truth_solvable)
        
        return PlanMetrics(
            valid=is_correct_refusal,
            length=0,
            cost_value=None,
            first_failure_at=None,
            unsat_count=0,
            redundant_indices=None,
            failure_reason="DECLARED_UNSOLVABLE" if is_correct_refusal else "FALSE_NEGATIVE_UNSOLVABLE",
            first_failed_action=None,
            first_failure_reason=None,
            first_failure_detail=None,
            advice_count=0,
            advice_top_predicates=[],
            val_stdout="",
            val_stderr="",
            steps=[],
            val_attempts=0,
            val_warning=None,
        )

    # 2. Standard VAL Logic
    base = run_val(domain, problem, plan_text, val_path=val_path, flags=flags)

    length = len([ln for ln in plan_text.splitlines() if ln.strip().startswith("(")])

    # first failure
    first_fail = None
    first_failed_action = None
    for st in base.steps:
        if st.failed:
            first_fail = st.time
            first_failed_action = st.action
            break

    # quick redundancy check (remove-one validation)
    redundant = None
    if check_redundancy and length > 0:
        redundant = []
        lines = [ln for ln in plan_text.splitlines() if ln.strip()]
        # consider only action lines; map from action index -> original line index
        action_line_idxs = [
            idx for idx, ln in enumerate(lines) if ln.strip().startswith("(")
        ]
        for k, remove_idx in enumerate(action_line_idxs):
            variant = (
                "\n".join(lines[j] for j in range(len(lines)) if j != remove_idx) + "\n"
            )
            res = run_val(domain, problem, variant, val_path=val_path, flags=flags)
            if res.ok:
                redundant.append(k + 1)  # 1-based among ACTIONS

    # Advice parsing
    advice_by_time = _parse_advice_by_time(base.stdout or "")

    # Flatten for counts/top predicates (use just the atom names)
    all_advice_atoms = [
        atom for pairs in advice_by_time.values() for (atom, _desired) in pairs
    ]
    advice_count = len(all_advice_atoms)
    pred_counts = Counter(
        (
            a.strip()[1:-1]
            if a.strip().startswith("(") and a.strip().endswith(")")
            else a
        )
        .split()[0]
        .lower()
        for a in all_advice_atoms
        if isinstance(a, str) and a.strip()
    )
    advice_top_predicates = pred_counts.most_common(8)

    # First failure reason (short + detailed)
    first_failure_reason = None
    first_failure_detail = None
    if first_fail is not None and advice_by_time.get(first_fail):
        first_atom, _ = advice_by_time[first_fail][0]
        first_failure_reason = first_atom

        def _fmt_pair(pair: tuple[str, bool]) -> str:
            atom, desired = pair
            desired_str = "true" if desired else "false"
            assumed_was = "false" if desired else "true"
            return f"{atom} = {desired_str} (but was {assumed_was})"

        action_txt = first_failed_action or "unknown-action"
        detail_bits = "; ".join(_fmt_pair(p) for p in advice_by_time[first_fail][:5])
        if len(advice_by_time[first_fail]) > 5:
            detail_bits += f"; ... (+{len(advice_by_time[first_fail]) - 5} more)"
        first_failure_detail = (
            f"Unsatisfied preconditions at step {first_fail} for {action_txt}: "
            f"{detail_bits}."
        )

    # 3. Handle False Positive (Valid plan for unsolvable problem)
    # If VAL says valid (base.ok) but the problem is actually unsolvable, 
    # then the model hallucinated a solution (likely due to a bug in PDDL or loose validation).
    # We mark validity as False for the final metric.
    final_validity = base.ok
    final_failure_reason = base.failure_reason

    if base.ok and not is_ground_truth_solvable:
        final_validity = False
        final_failure_reason = "FALSE_POSITIVE_SOLVABLE"

    return PlanMetrics(
        valid=final_validity,
        length=length,
        cost_value=base.value,
        first_failure_at=first_fail,
        unsat_count=len(base.unsatisfied),
        redundant_indices=redundant,
        failure_reason=final_failure_reason,
        first_failed_action=first_failed_action,
        first_failure_reason=first_failure_reason,
        first_failure_detail=first_failure_detail,
        advice_count=advice_count,
        advice_top_predicates=advice_top_predicates,
        val_stdout=base.stdout,
        val_stderr=base.stderr,
        steps=base.steps,
        val_attempts=base.attempts,
        val_warning=base.warning,
    )


