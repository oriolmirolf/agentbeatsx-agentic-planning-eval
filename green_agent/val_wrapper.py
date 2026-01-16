# green_agent/val_wrapper.py
from __future__ import annotations

import os
import re
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, field


def guess_val_binary(explicit: str | None) -> str | None:
    if explicit and os.path.exists(explicit):
        return explicit
    for name in ("Validate", "validate", "Validate.exe", "validate.exe"):
        path = shutil.which(name)
        if path and os.path.exists(path):
            return path
    envp = os.getenv("VAL_PATH")
    if envp and os.path.exists(envp):
        return envp
    return None


# --- Patterns seen across VAL variants ---
_UNSAT_RE = re.compile(r"Unsatisfied precondition", re.IGNORECASE)
_UNSAT_LINE_RE = re.compile(
    r"Plan failed because of unsatisfied precondition", re.IGNORECASE
)
_FAILED_AT_STEP_RE = re.compile(r"\baction\s+(\d+)\b", re.IGNORECASE)
_TIME_RE = re.compile(r"Checking next happening\s*\(time\s*(\d+)\)", re.IGNORECASE)

_VALUE_RE = re.compile(r"Value\s*[:=]\s*([0-9]+(?:\.[0-9]+)?)", re.IGNORECASE)
_SUCCESS_RE = re.compile(r"Successful plans|Plan valid", re.IGNORECASE)
_FAILED_RE = re.compile(
    r"Failed plans|Plan failed|Invalid plan|Goal not satisfied", re.IGNORECASE
)
_GOAL_NOT_SAT_RE = re.compile(r"Goal not satisfied", re.IGNORECASE)

_ACTION_LINE_RE = re.compile(r"^\s*\(([^()]+)\)\s*$")  # "(move-small ...)"

# Matches "1:" OR "1: (action ...)"
_PLAN_STEP_RE = re.compile(r"^\s*(\d+)\s*:\s*(.*)$")
_ACTION_INNER_RE = re.compile(r"\(([^()]+)\)")

_ADDING_RE = re.compile(r"^\s*Adding\s*\((.+)\)\s*$", re.IGNORECASE)
_DELETING_RE = re.compile(r"^\s*Deleting\s*\((.+)\)\s*$", re.IGNORECASE)


@dataclass(slots=True)
class Unsat:
    at_action_index: int | None
    detail: str


@dataclass(slots=True)
class TraceStep:
    time: int
    action: str | None = None
    adds: list[str] = field(default_factory=list)
    deletes: list[str] = field(default_factory=list)
    failed: bool = False
    failure_detail: str | None = None


@dataclass(slots=True)
class ValResult:
    ok: bool
    stdout: str
    stderr: str
    value: float | None = None
    unsatisfied: list[Unsat] = field(default_factory=list)
    failure_reason: str | None = None
    plan_size: int | None = None
    plan_actions: dict[int, str] = field(default_factory=dict)  # index->"(action ...)"
    steps: list[TraceStep] = field(default_factory=list)  # per happening
    last_executed_step: int | None = None
    attempts: int = 1
    warning: str | None = None


def _parse_plan_listing(lines: list[str]) -> dict[int, str]:
    """
    Parse the 'Plan to validate' listing into {index: action}.
    """
    plan: dict[int, str] = {}
    i = 0
    while i < len(lines):
        line = lines[i].strip()
        m = _PLAN_STEP_RE.match(line)
        if m:
            idx = int(m.group(1))
            remainder = m.group(2).strip()

            action_found = None

            # Case 1: Action is on the same line -> "1: (move a b)"
            if remainder and "(" in remainder:
                m_act = _ACTION_INNER_RE.search(remainder)
                if m_act:
                    action_found = f"({m_act.group(1).strip()})"

            # Case 2: Action is on the next line(s)
            if not action_found:
                j = i + 1
                while j < len(lines):
                    next_ln = lines[j].strip()
                    if not next_ln:
                        j += 1
                        continue

                    # If we hit the next index "2:", stop lookahead
                    if _PLAN_STEP_RE.match(next_ln):
                        break

                    m_act = _ACTION_INNER_RE.search(next_ln)
                    if m_act:
                        action_found = f"({m_act.group(1).strip()})"
                        i = j
                        break

                    j += 1

            if action_found:
                plan[idx] = action_found

        i += 1
    return plan


def _has_verdict(out: str) -> bool:
    if not (out or "").strip():
        return False
    return bool(
        _SUCCESS_RE.search(out)
        or _FAILED_RE.search(out)
        or _GOAL_NOT_SAT_RE.search(out)
        or _UNSAT_RE.search(out)
        or _UNSAT_LINE_RE.search(out)
        or _TIME_RE.search(out)
    )


def run_val(
    domain: str,
    problem: str,
    plan_text: str,
    *,
    val_path: str | None = None,
    flags: tuple[str, ...] = ("-v",),
    retries: int = 5,
    retry_backoff: float = 0.4,
) -> ValResult:
    """
    Invoke VAL. If it appears to produce no output or no recognizable verdict,
    retry up to `retries` times with a short backoff.
    """
    bin_path = guess_val_binary(val_path)
    if not bin_path:
        raise RuntimeError("VAL binary not found. Install or set VAL_PATH.")

    with tempfile.NamedTemporaryFile("w", suffix=".plan", delete=False) as tf:
        tf.write(plan_text)
        tf.flush()
        plan_path = tf.name

    out = ""
    err = ""
    attempts = 0
    warning: str | None = None

    try:
        while True:
            attempts += 1
            cmd = [bin_path, *flags, domain, problem, plan_path]
            proc = subprocess.run(cmd, capture_output=True, text=True)
            out, err = proc.stdout, proc.stderr

            if _has_verdict(out) or attempts >= max(1, retries):
                if not _has_verdict(out):
                    warning = "VAL produced no recognizable output after "
                    f"{attempts} attempt(s)."
                    if err.strip():
                        warning += f" STDERR: {err.strip()}"
                break

            time.sleep(retry_backoff * attempts)

        ok = bool(_SUCCESS_RE.search(out)) and not _FAILED_RE.search(out)

        value = None
        mval = _VALUE_RE.search(out)
        if mval:
            try:
                value = float(mval.group(1))
            except ValueError:
                value = None

        lines = out.splitlines()
        plan_actions = _parse_plan_listing(lines)
        plan_size = max(plan_actions.keys(), default=0) or None

        steps: list[TraceStep] = []
        current: TraceStep | None = None
        current_step_idx: int | None = None

        unsatisfied: list[Unsat] = []
        last_executed_step: int | None = None

        i = 0
        while i < len(lines):
            line = lines[i]

            mtime = _TIME_RE.search(line)
            if mtime:
                if current:
                    steps.append(current)
                current_step_idx = int(mtime.group(1))
                current = TraceStep(
                    time=current_step_idx, action=plan_actions.get(current_step_idx)
                )
                last_executed_step = current_step_idx

            elif _UNSAT_RE.search(line) or _UNSAT_LINE_RE.search(line):
                # -------------------------------------------------------------
                #  IMPROVED ERROR PARSING LOGIC START
                # -------------------------------------------------------------
                idx = None
                mact = _FAILED_AT_STEP_RE.search(line)
                if mact:
                    try:
                        idx = int(mact.group(1))
                    except ValueError:
                        idx = None
                if idx is None:
                    idx = current_step_idx

                # Lookahead for details. VAL often prints:
                # (pick-up a)
                # (Follow each of:
                #   (handempty)
                # )
                detail_parts = []
                j = i + 1
                max_peek = 8  # read up to 8 lines to find the atom
                scan_count = 0

                while j < len(lines) and scan_count < max_peek:
                    ln = lines[j].strip()
                    if not ln:
                        j += 1
                        continue

                    # Stop if we hit a new section
                    if (
                        _TIME_RE.search(ln)
                        or _UNSAT_RE.search(ln)
                        or _UNSAT_LINE_RE.search(ln)
                    ):
                        break

                    # We look for sexpr-like lines e.g. "(handempty)"
                    # We skip the "Follow each of" wrapper text
                    lower_ln = ln.lower()
                    if lower_ln.startswith("(") and "follow each of" not in lower_ln:
                        if lower_ln != ")":  # skip closing paren
                            detail_parts.append(ln)

                    j += 1
                    scan_count += 1

                if detail_parts:
                    detail_action = "; ".join(detail_parts)
                else:
                    # Fallback to just grabbing the immediate next line if nothing parsd
                    j = i + 1
                    while j < len(lines) and not lines[j].strip():
                        j += 1
                    if j < len(lines):
                        detail_action = lines[j].strip()
                    else:
                        detail_action = "Unknown unsatisfied condition"

                unsatisfied.append(Unsat(at_action_index=idx, detail=detail_action))

                if current:
                    current.failed = True
                    current.failure_detail = "unsatisfied_precondition"
                    # Try to backfill the action name if we caught it in details
                    if (
                        not current.action
                        and detail_action
                        and detail_action.startswith("(")
                    ):
                        # Use the first part as the action name guess
                        current.action = detail_action.split(";")[0]

                # -------------------------------------------------------------
                #  IMPROVED ERROR PARSING LOGIC END
                # -------------------------------------------------------------

            else:
                madd = _ADDING_RE.match(line)
                if madd and current:
                    current.adds.append("(" + madd.group(1).strip() + ")")
                mdel = _DELETING_RE.match(line)
                if mdel and current:
                    current.deletes.append("(" + mdel.group(1).strip() + ")")

            i += 1

        if current:
            steps.append(current)

        failure_reason: str | None = None
        if not ok:
            if not _has_verdict(out):
                failure_reason = "no_output"
            elif unsatisfied:
                failure_reason = "precondition_unsatisfied"
            elif _GOAL_NOT_SAT_RE.search(out):
                failure_reason = "goal_not_satisfied"
            else:
                failure_reason = "unknown_failure"

        return ValResult(
            ok=ok,
            stdout=out,
            stderr=err,
            value=value,
            unsatisfied=unsatisfied,
            failure_reason=failure_reason,
            plan_size=plan_size,
            plan_actions=plan_actions,
            steps=steps,
            last_executed_step=last_executed_step,
            attempts=attempts,
            warning=warning,
        )

    finally:
        try:
            os.unlink(plan_path)
        except Exception:
            pass
