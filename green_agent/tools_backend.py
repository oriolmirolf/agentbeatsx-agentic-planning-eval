from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from .metrics import compute_metrics
from .val_wrapper import run_val

import os

# ---------------------------------------------------------------------------
# Tool Signatures (Optimized for Agent Usage)
# ---------------------------------------------------------------------------

def _get_examples_root() -> Path:
    # Uses the Docker ENV var if present, otherwise defaults to local 'examples'
    return Path(os.getenv("EXAMPLES_DIR", "examples"))

@dataclass(frozen=True, slots=True)
class SigField:
    name: str
    type: str
    desc: str

@dataclass(frozen=True, slots=True)
class ToolSignature:
    name: str
    inputs: list[SigField]
    output: SigField
    doc: str

# REMOVED "reset_episode" from here so the Agent doesn't see it.
TOOL_SIGNATURES: dict[str, ToolSignature] = {
    "get_task_overview": ToolSignature(
        name="get_task_overview",
        inputs=[
            SigField("domain", "str", "Domain name."),
            SigField("index", "int", "Problem index."),
        ],
        output=SigField("overview", "str", "Task description, initial state, and goal."),
        doc="Get the mission briefing: what is the goal and how does the world start?",
    ),
    "list_objects": ToolSignature(
        name="list_objects",
        inputs=[
            SigField("domain", "str", "Domain name."),
            SigField("index", "int", "Problem index."),
            SigField("kind", "Optional[str]", "Type filter (e.g. 'block')."),
        ],
        output=SigField("objects", "str", "List of objects."),
        doc="List physical objects available in the environment.",
    ),
    "describe_object": ToolSignature(
        name="describe_object",
        inputs=[
            SigField("domain", "str", "Domain name."),
            SigField("index", "int", "Problem index."),
            SigField("name", "str", "Object name."),
        ],
        output=SigField("object", "str", "Object details."),
        doc="Inspect a specific object.",
    ),
    "list_actions": ToolSignature(
        name="list_actions",
        inputs=[SigField("domain", "str", "Domain name.")],
        output=SigField("actions", "str", "List of available action types."),
        doc="List the actions/moves you are allowed to perform.",
    ),
    "describe_action": ToolSignature(
        name="describe_action",
        inputs=[
            SigField("domain", "str", "Domain name."),
            SigField("action_name", "str", "Action name."),
        ],
        output=SigField("action", "str", "Action usage syntax."),
        doc="Explain how to use a specific action (parameters, preconditions).",
    ),
    "act": ToolSignature(
        name="act",
        inputs=[
            SigField("step_text", "str", "Action text (e.g. 'pick-up b')."),
        ],
        output=SigField("result", "str", "Execution result."),
        doc="Perform an action in the environment.",
    ),
    "get_history": ToolSignature(
        name="get_history",
        inputs=[],
        output=SigField("history", "str", "Action log."),
        doc="Review your previous actions.",
    ),
    "get_state": ToolSignature(
        name="get_state",
        inputs=[], 
        output=SigField("state", "str", "Current world facts."),
        doc="Inspect the world state. Use this to check preconditions (e.g. is a block clear?) to avoid fatal errors.",
    ),
    "submit": ToolSignature(
        name="submit",
        inputs=[],
        output=SigField("summary", "str", "Validation result."),
        doc="Submit your current plan to check if the goal is achieved.",
    ),
}

# ---------------------------------------------------------------------------
# Data Structures
# ---------------------------------------------------------------------------

@dataclass(slots=True)
class TaskOverview:
    description: str
    initial_state: str
    goal: str

@dataclass(slots=True)
class ObjectSpec:
    name: str
    kind: str
    summary: str
    attributes: dict[str, Any]

@dataclass(slots=True)
class ParameterSpec:
    name: str
    kind: str

@dataclass(slots=True)
class ActionSchema:
    name: str
    signature: str
    parameters: list[ParameterSpec]
    preconditions: list[str]
    effects: list[str]
    cost: float

@dataclass(slots=True)
class ProblemSpec:
    domain: str
    index: int
    overview: TaskOverview
    objects: list[ObjectSpec]
    actions: list[ActionSchema]

# ---------------------------------------------------------------------------
# File Loading Helpers
# ---------------------------------------------------------------------------

def _prompts_path(domain: str) -> Path:
    return _get_examples_root() / domain / "prompts.json"

def _load_prompts(domain: str) -> dict[str, Any]:
    path = _prompts_path(domain)
    if not path.exists():
        raise FileNotFoundError(f"prompts.json not found for domain '{domain}' at {path}")
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    return data

def _find_problem_entry(data: dict[str, Any], index: int) -> dict[str, Any]:
    problems = data.get("problems") or []
    pid = f"p{int(index):02d}"
    for entry in problems:
        raw_id = str(entry.get("id", "")).strip()
        if raw_id == pid or raw_id == str(index):
            return entry
    raise KeyError(f"No problem with id '{pid}' (index {index}) in prompts.json.")

def _make_overview(domain: str, data: dict[str, Any], entry: dict[str, Any]) -> TaskOverview:
    domain_prompt = (data.get("domain_prompt") or "").strip()
    overview = entry.get("overview") or {}
    desc = (overview.get("description") or "\n\n".join(p for p in (domain_prompt, (entry.get("prompt") or "").strip()) if p).strip())
    init = (overview.get("initial_state") or entry.get("initial_state") or "").strip()
    goal = (overview.get("goal") or entry.get("goal") or "").strip()
    return TaskOverview(description=desc, initial_state=init, goal=goal)

def _make_actions(data: dict[str, Any]) -> list[ActionSchema]:
    raw_actions = data.get("actions") or []
    actions: list[ActionSchema] = []
    for a in raw_actions:
        name = str(a.get("name") or "").strip()
        if not name: continue
        signature = str(a.get("signature") or name)
        params_raw = a.get("parameters") or []
        params = [
            ParameterSpec(name=str(p.get("name") or "").strip(), kind=str(p.get("kind") or "object").strip())
            for p in params_raw if p.get("name") is not None
        ]
        pre = [str(x).strip() for x in (a.get("preconditions") or []) if str(x).strip()]
        eff = [str(x).strip() for x in (a.get("effects") or []) if str(x).strip()]
        cost = float(a.get("cost", 1))
        actions.append(ActionSchema(name=name, signature=signature, parameters=params, preconditions=pre, effects=eff, cost=cost))
    return actions

def _make_objects(entry: dict[str, Any]) -> list[ObjectSpec]:
    objs_raw = entry.get("objects") or []
    objs: list[ObjectSpec] = []
    for o in objs_raw:
        name = str(o.get("name") or "").strip()
        if not name: continue
        kind = str(o.get("kind") or "object").strip()
        summary = str(o.get("summary") or "").strip()
        attrs = o.get("attributes") or {}
        if not isinstance(attrs, dict): attrs = {"raw": attrs}
        objs.append(ObjectSpec(name=name, kind=kind, summary=summary, attributes=attrs))
    return objs

def _resolve_pddl_paths(domain: str, index: int) -> tuple[str, str]:
    base = _get_examples_root() / domain
    domain_pddl = base / "domain.pddl"
    problems_dir = base / "problems_pddl"
    problem_pddl = problems_dir / f"problem{int(index)}.pddl"
    if not domain_pddl.exists(): raise FileNotFoundError(f"domain.pddl not found at {domain_pddl}")
    if not problem_pddl.exists(): raise FileNotFoundError(f"problem{index}.pddl not found at {problem_pddl}")
    return str(domain_pddl), str(problem_pddl)

def load_problem_spec(domain: str, index: int) -> ProblemSpec:
    data = _load_prompts(domain)
    entry = _find_problem_entry(data, index)
    overview = _make_overview(domain, data, entry)
    actions = _make_actions(data)
    objects = _make_objects(entry)
    return ProblemSpec(domain=domain, index=index, overview=overview, objects=objects, actions=actions)

def _get_action_map(domain: str) -> dict[str, ActionSchema]:
    data = _load_prompts(domain)
    actions = _make_actions(data)
    return {a.name.lower(): a for a in actions}

# =============================================================================
# JSON Accessors (Internal)
# =============================================================================

def get_task_overview_json(domain: str, index: int) -> dict[str, str]:
    spec = load_problem_spec(domain, index)
    return {"description": spec.overview.description, "initial_state": spec.overview.initial_state, "goal": spec.overview.goal}

def list_objects_json(domain: str, index: int, kind: str | None = None) -> dict[str, Any]:
    spec = load_problem_spec(domain, index)
    objs = spec.objects
    if kind:
        kind = str(kind).strip()
        objs = [o for o in objs if o.kind == kind]
    return {"kind": kind or "all", "objects": [{"name": o.name, "kind": o.kind, "summary": o.summary, "attributes": o.attributes} for o in objs]}

def describe_object_json(domain: str, index: int, name: str) -> dict[str, Any]:
    spec = load_problem_spec(domain, index)
    name = str(name).strip()
    for o in spec.objects:
        if o.name == name:
            return {"name": o.name, "kind": o.kind, "summary": o.summary, "attributes": o.attributes}
    raise KeyError(f"Unknown object '{name}'")

# =============================================================================
# Agent Tools (Human Readable)
# =============================================================================

_ACTION_NAME_RE = re.compile(r"^\s*([a-zA-Z][a-zA-Z0-9_\-]*)", re.IGNORECASE)

def _norm_key(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", (s or "").strip().lower())

def _strip_code_fences(raw: str) -> str:
    if "```" not in (raw or ""): return raw or ""
    parts = (raw or "").split("```")
    best = ""
    for i, p in enumerate(parts):
        if i % 2 == 1:
            lines = p.splitlines()
            body = "\n".join(lines[1:]) if lines and re.match(r"^[a-zA-Z0-9_-]+$", lines[0].strip()) else p
            if len(body) > len(best): best = body
    return best if best else (raw or "")

def get_task_overview(domain: str, index: int) -> str:
    ov = get_task_overview_json(domain, index)
    lines: list[str] = []
    if ov.get("description"): lines.extend(["Task description:", ov["description"].strip()])
    if ov.get("initial_state"): lines.extend(["", "Initial situation:", ov["initial_state"].strip()])
    if ov.get("goal"): lines.extend(["", "Goal:", ov["goal"].strip()])
    return "\n".join(lines).strip() or "No overview available."

def list_objects(domain: str, index: int, kind: str | None = None) -> str:
    res = list_objects_json(domain, index, kind=kind)
    objs = res.get("objects") or []
    if not objs: return "No objects."
    lines: list[str] = []
    for o in objs:
        k = str(o.get("kind") or "").strip()
        summary = str(o.get("summary") or "").strip()
        lines.append(f"- {o['name']} (type: {k})" + (f" — {summary}" if summary else ""))
    return "\n".join(lines)

def describe_object(domain: str, index: int, name: str) -> str:
    o = describe_object_json(domain, index, name)
    lines = [f"Name: {o.get('name', '')}", f"Type: {o.get('kind', '')}"]
    if o.get("summary"): lines.append(f"Summary: {o['summary']}")
    attrs = o.get("attributes") or {}
    if isinstance(attrs, dict) and attrs:
        lines.append("Attributes:")
        for k, v in attrs.items(): lines.append(f"- {k}: {v}")
    return "\n".join(lines).strip()

def list_action_types(domain: str) -> str:
    action_map = _get_action_map(domain)
    if not action_map: return "No action types defined."
    lines: list[str] = []
    for name in sorted(action_map.keys()):
        a = action_map[name]
        lines.append(f"Action: {a.name}")
        lines.append("Parameters (in order): " + (", ".join(p.name for p in a.parameters) if a.parameters else "none"))
        if a.preconditions:
            lines.append("Allowed when:")
            for p in a.preconditions: lines.append(f"- {p}")
        if a.effects:
            lines.append("Effects:")
            for e in a.effects: lines.append(f"- {e}")
        lines.append("")
    return "\n".join(lines).strip()

def list_actions(domain: str, index: int | None = None) -> str:
    return list_action_types(domain)

def describe_action(domain: str, action_name: str) -> str:
    action_map = _get_action_map(domain)
    aname = (action_name or "").strip().lower()
    if aname not in action_map: return f"Unknown action '{action_name}'."
    a = action_map[aname]
    lines = [f"Action: {a.name}"]
    lines.append("Parameters (in order): " + (", ".join(p.name for p in a.parameters) if a.parameters else "none"))
    if a.preconditions:
        lines.append("Allowed when:")
        for p in a.preconditions: lines.append(f"- {p}")
    if a.effects:
        lines.append("Effects:")
        for e in a.effects: lines.append(f"- {e}")
    return "\n".join(lines)

def _parse_step(line: str) -> tuple[str, dict[str, str] | list[str]]:
    ln = re.sub(r"^\s*\d+\s*[\)\.:\-]\s*", "", (line or "").strip()).strip()
    if not ln: raise ValueError("empty step")
    m = _ACTION_NAME_RE.search(ln)
    if not m: raise ValueError(f"Could not parse action name from: '{ln}'")
    act_name = m.group(1).lower()
    after = ln[m.end() :].strip()
    if after.startswith("(") and after.endswith(")"): after = after[1:-1].strip()
    
    payload = ""
    if "with:" in after.lower(): payload = re.split(r"with:", after, flags=re.IGNORECASE, maxsplit=1)[1].strip()
    elif after.startswith(":"): payload = after[1:].strip()
    else: payload = after.strip()
    
    if not payload: return act_name, []
    if "=" in payload or re.search(r"\w+\s*:\s*\S+", payload):
        parts = [p.strip() for p in payload.split(",") if p.strip()]
        out: dict[str, str] = {}
        for p in parts:
            if "=" in p: k, v = p.split("=", 1)
            elif ":" in p: k, v = p.split(":", 1)
            else: continue
            out[k.strip()] = v.strip()
        return act_name, out
    
    clean_args = payload.replace(",", " ")
    return act_name, [t for t in clean_args.split() if t.strip()]

def compile_plan(domain: str, raw: str) -> tuple[str, list[str]]:
    action_map = _get_action_map(domain)
    lines = [ln.strip() for ln in (_strip_code_fences(raw) or "").splitlines() if ln.strip()]
    errors: list[str] = []
    pddl_lines: list[str] = []

    for ln in lines:
        try:
            act_name, args = _parse_step(ln)
            if act_name not in action_map: raise ValueError(f"Unknown action '{act_name}'")
            schema = action_map[act_name]
            param_names = [p.name for p in schema.parameters]
            
            ordered: list[str] = []
            if isinstance(args, dict):
                keymap = {_norm_key(k): v for k, v in args.items()}
                for pn in param_names:
                    k = _norm_key(pn)
                    if k not in keymap: raise ValueError(f"missing parameter '{pn}' for action '{schema.name}'")
                    ordered.append(str(keymap[k]).strip())
            else:
                if len(args) != len(param_names):
                    raise ValueError(f"Action '{schema.name}' expects {len(param_names)} args, got {len(args)}.")
                ordered = [str(x).strip() for x in args]
            
            arg_str = " ".join(ordered)
            pddl_lines.append(f"({schema.name} {arg_str})" if arg_str else f"({schema.name})")
        except Exception as e:
            errors.append(f"{ln} -> {e}")
            
    return ("\n".join(pddl_lines) + ("\n" if pddl_lines else "")), errors

# -------------------------------
# Stateful execution (episode)
# -------------------------------

@dataclass(slots=True)
class _Episode:
    domain: str | None = None
    index: int | None = None
    domain_path: str | None = None
    problem_path: str | None = None
    val_path: str | None = None
    tolerance: float = 0.001
    pddl_steps: list[str] | None = None

    def __post_init__(self) -> None:
        self.pddl_steps = []

_EP = _Episode()

# WE KEEP THE PYTHON FUNCTION FOR THE ORCHESTRATOR, BUT IT IS REMOVED FROM TOOL_SIGNATURES
def reset_episode(domain: str, index: int, *, val_path: str | None = None, tolerance: float = 0.001) -> str:
    _EP.domain = domain
    _EP.index = int(index)
    _EP.domain_path, _EP.problem_path = _resolve_pddl_paths(domain, index)
    _EP.val_path = val_path
    _EP.tolerance = float(tolerance)
    _EP.pddl_steps = []
    return f"State reset for domain '{domain}', problem {index}. Step counter = 0."

def get_history() -> str:
    if not _EP.pddl_steps: return "No actions executed yet."
    out: list[str] = []
    for i, ln in enumerate(_EP.pddl_steps, start=1):
        inner = ln.strip()
        inner = inner[1:-1].strip() if inner.startswith("(") and inner.endswith(")") else inner
        toks = inner.split()
        out.append(f"{i}) {toks[0] if toks else 'unknown'} {' '.join(toks[1:])}".strip())
    return "\n".join(out).strip()

def undo(to_step: int) -> str:
    k = max(0, int(to_step))
    if not _EP.pddl_steps: return "Reverted to step 0."
    if k > len(_EP.pddl_steps): k = len(_EP.pddl_steps)
    _EP.pddl_steps = _EP.pddl_steps[:k]
    return f"Reverted to step {k}."

def _translate_fact(fact: str) -> str:
    inner = fact.strip()
    if inner.startswith("(") and inner.endswith(")"): inner = inner[1:-1].strip()
    parts = inner.split()
    if not parts: return fact
    pred = parts[0].lower().replace("-", " ").replace("_", " ")
    args = parts[1:]
    if len(args) == 0: return f"{pred} is true"
    if len(args) == 1: return f"{args[0]} is {pred}"
    if len(args) == 2: return f"{args[0]} is {pred} {args[1]}"
    return fact

def _translate_error(detail_raw: str) -> str:
    txt = detail_raw.strip()
    m_set = re.search(r"Set\s+(\(.+\))\s+to\s+true", txt, re.IGNORECASE)
    if m_set: txt = m_set.group(1)
    if txt.startswith("(") and txt.endswith(")"): txt = txt[1:-1]
    parts = txt.split()
    if not parts: return detail_raw
    pred = parts[0].lower().replace("-", " ").replace("_", " ")
    args = parts[1:]
    if len(args) == 0: return f"The condition '{pred}' should be met."
    if len(args) == 1: return f"{args[0]} should be {pred}."
    if len(args) == 2: return f"{args[0]} should be {pred} {args[1]}."
    return f"Relationship '{pred}' should hold for ({', '.join(args)})."

def act(step_text: str) -> str:
    if not (_EP.domain and _EP.domain_path and _EP.problem_path):
        return "No episode loaded. Call reset_episode() first."

    plan_text, errors = compile_plan(_EP.domain, step_text)
    if errors: return "Executed: NO\nReason: " + errors[0]

    step_line = plan_text.strip().splitlines()
    if not step_line: return "Executed: NO\nReason: could not compile step."

    candidate = (_EP.pddl_steps or []) + [step_line[0]]
    cand_text = "\n".join(candidate) + "\n"
    flags = ("-v", "-t", str(_EP.tolerance))
    
    res = run_val(_EP.domain_path, _EP.problem_path, cand_text, val_path=_EP.val_path, flags=flags)

    if res.unsatisfied:
        u = res.unsatisfied[-1]
        at = u.at_action_index if u.at_action_index is not None else "?"
        return f"Executed: NO\nAt step: {at}\nDetail: {_translate_error(u.detail or '')}"

    if res.failure_reason == "no_output": return "Executed: NO\nReason: VAL produced no usable output."
    if (not res.ok) and (res.failure_reason not in (None, "goal_not_satisfied")):
        return f"Executed: NO\nReason: VAL failure ({res.failure_reason})"

    _EP.pddl_steps = candidate
    return f"Executed: YES\nStep counter now: {len(_EP.pddl_steps)}"

# -------------------------------
# State reconstruction (debug)
# -------------------------------

_INIT_ASSIGN_RE = re.compile(r"^\(\s*=\s*\(\s*([^)]+)\s*\)\s*([+-]?\d+(?:\.\d+)?)\s*\)\s*$")

def _read_text(path: str) -> str:
    with open(path, encoding="utf-8") as f: return f.read()

def _extract_balanced_block(text: str, start_idx: int) -> str:
    depth = 0
    i = start_idx
    n = len(text)
    while i < n and text[i] != "(": i += 1
    start = i
    while i < n:
        if text[i] == "(": depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0: return text[start : i + 1]
        i += 1
    return text[start:]

def _split_top_level_sexps(block: str) -> list[str]:
    out: list[str] = []
    depth = 0
    buf: list[str] = []
    for c in block:
        if c == "(":
            if depth == 0: buf = []
            depth += 1
        if depth > 0: buf.append(c)
        if c == ")":
            depth -= 1
            if depth == 0 and buf:
                out.append("".join(buf).strip())
                buf = []
    return out

def _parse_problem_init(problem_path: str) -> tuple[set[str], dict[str, float]]:
    txt = _read_text(problem_path)
    pos = txt.lower().find("(:init")
    if pos < 0: return set(), {}
    
    init_block = _extract_balanced_block(txt, pos)
    inner = init_block.strip()[1:-1].strip()
    if inner.lower().startswith(":init"): inner = inner[5:].strip()

    sexps = _split_top_level_sexps(inner)
    facts: set[str] = set()
    funcs: dict[str, float] = {}

    for e in sexps:
        e = re.sub(r"\s+", " ", e.strip())
        if not e.startswith("(") or not e.endswith(")"): continue
        if e.lower().startswith("(not "): continue
        m = _INIT_ASSIGN_RE.match(e)
        if m:
            func_inner = m.group(1).strip()
            func_name = func_inner.split()[0].lower()
            try: funcs[func_name] = float(m.group(2))
            except Exception: pass
            continue
        facts.add(e.lower())
    return facts, funcs

def _apply_trace(facts: set[str], adds: list[str], deletes: list[str]) -> None:
    for d in deletes or []:
        dd = re.sub(r"\s+", " ", (d or "").strip()).lower()
        if dd: facts.discard(dd)
    for a in adds or []:
        aa = re.sub(r"\s+", " ", (a or "").strip()).lower()
        if aa: facts.add(aa)

def get_state(max_facts: int = 200) -> str:
    if not (_EP.domain and _EP.domain_path and _EP.problem_path):
        return "No episode loaded. Call reset_episode() first."

    plan_text = "\n".join(_EP.pddl_steps or []) + ("\n" if (_EP.pddl_steps or []) else "")
    flags = ("-v", "-t", str(_EP.tolerance))
    res = run_val(_EP.domain_path, _EP.problem_path, plan_text, val_path=_EP.val_path, flags=flags)

    facts, funcs = _parse_problem_init(_EP.problem_path)
    for st in res.steps: _apply_trace(facts, st.adds, st.deletes)
    if res.value is not None: funcs["total-cost"] = float(res.value)

    facts_sorted = sorted(facts)
    if max_facts and len(facts_sorted) > max_facts:
        facts_sorted = facts_sorted[:max_facts] + [f"... ({len(facts) - max_facts} more facts)"]

    lines: list[str] = [f"Episode: domain={_EP.domain}, problem={_EP.index}, steps={len(_EP.pddl_steps or [])}"]
    if funcs:
        lines.append("Functions:")
        for k in sorted(funcs.keys()): lines.append(f"- {k} = {funcs[k]}")
    lines.append("Facts:")
    for fct in facts_sorted: lines.append(f"- {_translate_fact(fct)}")
    return "\n".join(lines)

def submit(*, unsolvable: bool = False) -> str:
    if unsolvable:
        return "Episode Terminated: DECLARED_UNSOLVABLE"
    if not (_EP.domain and _EP.domain_path and _EP.problem_path):
        return "No episode loaded. Call reset_episode() first."

    plan_text = "\n".join(_EP.pddl_steps or []) + ("\n" if (_EP.pddl_steps or []) else "")
    if not plan_text.strip(): return "Episode plan is empty."

    flags = ("-v", "-t", str(_EP.tolerance))
    
    # We use explicit keyword args as in the fixed example
    metrics = compute_metrics(
        domain=_EP.domain_path,
        problem=_EP.problem_path,
        plan_text=plan_text,
        val_path=_EP.val_path,
        flags=flags,
        check_redundancy=False
    )

    lines = [f"Accepted: {'YES' if metrics.valid else 'NO'}", f"Plan length: {metrics.length}"]
    if metrics.cost_value is not None: lines.append(f"Plan cost/value: {metrics.cost_value}")
    if not metrics.valid:
        lines.append(f"Failure category: {metrics.failure_reason or 'unknown_failure'}")
        if metrics.first_failure_at is not None: lines.append(f"First failing step: {metrics.first_failure_at}")
        if metrics.first_failed_action: lines.append(f"First failed action: {metrics.first_failed_action}")
        if metrics.first_failure_detail: lines.append(f"Details: {metrics.first_failure_detail}")
        lines.append(f"Unsatisfied conditions count: {metrics.unsat_count}")
    return "\n".join(lines)

compile_nl_plan = compile_plan

__all__ = [
    "ToolSignature", "SigField", "TOOL_SIGNATURES", "load_problem_spec", "get_task_overview",
    "list_objects", "describe_object", "list_action_types", "list_actions", "describe_action",
    "compile_plan", "reset_episode", "act", "undo", "get_history", "get_state", "submit"
]