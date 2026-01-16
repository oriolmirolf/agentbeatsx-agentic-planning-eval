from __future__ import annotations

import re
from dataclasses import dataclass

CODE_BLOCK_RE = re.compile(r"```[a-zA-Z0-9_-]*\n(.*?)\n```", re.DOTALL)
# ACTION_LINE_RE = re.compile(
#     r"""^\s*(?:\d+\s*[:.]\s*)?(?:\d+\.\d+\s*:\s*)?\(\s*([a-zA-Z0-9_-]+)(?:\s+[^)]*)?\)\s*(?:;.*)?$""",  # noqa: E501
#     re.VERBOSE | re.IGNORECASE,
# )
ACTION_LINE_RE = re.compile(
    r"^\s*(?:\d+[:.]\s*)?(?:\d+\.\d+\s*:\s*)?(\([a-zA-Z0-9_\-\s]+\))",
    re.VERBOSE | re.IGNORECASE,
)


@dataclass(slots=True)
class PlanStep:
    text: str


@dataclass(slots=True)
class ExtractedPlan:
    steps: list[PlanStep]

    def to_val_plan_text(self) -> str:
        return "\n".join(s.text for s in self.steps) + ("\n" if self.steps else "")


def extract_plan(raw: str) -> ExtractedPlan:
    m = CODE_BLOCK_RE.search(raw)
    body = m.group(1) if m else raw
    lines = [ln.strip() for ln in body.splitlines()]

    steps: list[PlanStep] = []
    for ln in lines:
        if not ln:
            continue

        if ";" in ln:
            ln = ln.split(";", 1)[0].strip()
            if not ln:
                continue

        if "(" in ln and ")" in ln:
            start = ln.find("(")
            end = ln.rfind(")")
            candidate = ln[start : end + 1]

            if re.match(r"\(\s*[\w-]+", candidate):
                clean = re.sub(r"\s+", " ", candidate)
                steps.append(PlanStep(text=clean))

    return ExtractedPlan(steps=steps)
