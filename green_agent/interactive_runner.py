# green_agent/interactive_runner.py
from __future__ import annotations

import asyncio
import json
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional, Tuple

import httpx

from green_agent import tools_backend as tb


# -----------------------------------------------------------------------------
# A single global lock to protect tools_backend's global episode state (_EP).
# If you later refactor tools_backend to be per-episode objects, you can remove
# this lock.
# -----------------------------------------------------------------------------
_EP_LOCK = asyncio.Lock()


# -----------------------------------------------------------------------------
# Helpers (parsing + error categorization)
# -----------------------------------------------------------------------------
_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)


def _count_history_steps(history_text: str) -> int:
    if not history_text or "No actions executed yet" in history_text:
        return 0
    return len([ln for ln in history_text.splitlines() if ln.strip()])


def _parse_submit_text(text: str) -> dict[str, Any]:
    out: dict[str, Any] = {"accepted": None, "raw": text}
    if isinstance(text, str):
        m = re.search(r"Accepted:\s*(YES|NO)", text)
        if m:
            out["accepted"] = (m.group(1) == "YES")
        m = re.search(r"Plan length:\s*(\d+)", text)
        if m:
            out["plan_length"] = int(m.group(1))
        m = re.search(r"Total cost:\s*(\d+)", text)
        if m:
            out["total_cost"] = int(m.group(1))
        m = re.search(r"Score:\s*([0-9]*\.?[0-9]+)", text)
        if m:
            out["score"] = float(m.group(1))
    return out


def _extract_json_obj(text: str) -> dict[str, Any]:
    """
    Accepts either:
      - raw JSON: {"tool":"act","args":{"step_text":"..."}}
      - fenced JSON: ```json {...} ```
      - text with JSON somewhere inside (best effort).
    """
    if not text:
        raise ValueError("Empty response")

    # 1. Try Regex for Markdown blocks
    m = _JSON_FENCE_RE.search(text)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass # Fall through to heuristic

    # 2. Heuristic: Find first '{' and last '}'
    s = text.strip()
    start = s.find("{")
    end = s.rfind("}")
    
    if start == -1 or end == -1 or end <= start:
        # Fallback: try loading the whole string (e.g. if it's just a number or string)
        try:
            return json.loads(s)
        except:
            raise ValueError(f"No JSON object found in response: {s[:200]}")
            
    try:
        return json.loads(s[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON found between braces: {e}")


def _normalize_tool_call(obj: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    """
    Supports multiple schemas:
      - {"tool": "...", "args": {...}}
      - {"tool_name": "...", "tool_args": {...}}
      - DSPy-like {"next_tool_name": "...", "next_tool_args": {...}}
    """
    tool = obj.get("tool") or obj.get("tool_name") or obj.get("next_tool_name")
    if not tool or not isinstance(tool, str):
        raise ValueError(f"Missing tool name in: {obj}")

    args = obj.get("args")
    if args is None:
        args = obj.get("tool_args")
    if args is None:
        args = obj.get("next_tool_args")
    if args is None:
        args = {}
    if not isinstance(args, dict):
        raise ValueError(f"Tool args must be an object/dict. Got: {type(args)}")

    t = tool.strip()
    # common normalizations
    if t.lower() in {"finish", "submit_episode"}:
        t = "submit"
    return t, args


def _is_hallucinated_action_err(out: str) -> bool:
    lower = out.lower()
    # Mirrors your EpisodeTools heuristic; adjust phrases to match your backend.
    return any(
        x in lower
        for x in [
            "unknown action",
            "could not parse",
            "not defined",
            "not an action",
            "unrecognized action",
        ]
    )


def _is_syntax_action_err(out: str) -> bool:
    lower = out.lower()
    return any(
        x in lower
        for x in [
            "arg",
            "expect",
            "expected",
            "found",
            "got",
            "parameter",
            "signature",
            "missing",
        ]
    )


def _safe_call(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """
    Like your EpisodeTools._call: tolerate minor signature differences.
    """
    try:
        return fn(*args, **kwargs)
    except TypeError:
        # try kwargs-only (some wrappers)
        if kwargs and not args:
            return fn(**kwargs)
        # try args-only (some wrappers)
        if args and not kwargs:
            return fn(*args)
        raise


# -----------------------------------------------------------------------------
# A2A JSON-RPC sender (works with A2AStarletteApplication JSON-RPC servers)
# -----------------------------------------------------------------------------
async def _a2a_jsonrpc_send(
    *,
    http: httpx.AsyncClient,
    base_url: str,
    user_text: str,
    context_id: str,
    timeout_s: float = 120.0,
) -> dict[str, Any]:
    """
    Sends JSON-RPC method "message/send" to the purple A2A server.

    Expected response shape (best-effort):
      {"jsonrpc":"2.0","id":"...","result":{...}}
    """
    url = base_url.rstrip("/") + "/"
    req_id = uuid.uuid4().hex

    payload = {
        "jsonrpc": "2.0",
        "id": req_id,
        "method": "message/send",
        "params": {
            "message": {
                "messageId": uuid.uuid4().hex,
                "role": "user",
                "contextId": context_id,
                "parts": [{"kind": "text", "text": user_text}],
            },
            # Try to encourage “single-turn” completion on purple side
            "configuration": {
                "blocking": True,
            },
        },
    }

    resp = await http.post(url, json=payload, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"Purple A2A error: {data['error']}")
    if "result" not in data:
        raise RuntimeError(f"Purple A2A missing result: {data}")
    return data["result"]


def _extract_purple_text(result: dict[str, Any]) -> str:
    """
    Extracts combined text from A2A message-like results.
    """
    # most common: {"type":"message","parts":[...]}
    parts = None
    if isinstance(result, dict):
        if "parts" in result:
            parts = result["parts"]
        elif "message" in result and isinstance(result["message"], dict):
            parts = result["message"].get("parts")

    if not parts:
        # Could be a task; for this benchmark, require message responses.
        raise RuntimeError(f"Purple returned non-message result (no parts): {result}")

    texts: list[str] = []
    for p in parts:
        if not isinstance(p, dict):
            continue
        # accept both server styles: {"type":"text","text":...} or {"kind":"text","text":...}
        if p.get("type") == "text" or p.get("kind") == "text" or ("text" in p and isinstance(p["text"], str)):
            texts.append(p["text"])
    return "\n".join(texts).strip()


# -----------------------------------------------------------------------------
# Interactive evaluation loop
# -----------------------------------------------------------------------------
@dataclass
class ToolPolicyCounters:
    syntax_error_count: int = 0
    hallucinated_action_count: int = 0
    precondition_error_count: int = 0
    hallucinated_tool_count: int = 0
    tool_usage: dict[str, int] = field(default_factory=dict)

    def track(self, name: str) -> None:
        self.tool_usage[name] = self.tool_usage.get(name, 0) + 1


@dataclass
class InteractiveResult:
    is_valid: bool
    is_success: bool
    finish_reason: str
    steps_taken: int
    optimal_steps: float
    score: float
    tool_policy: ToolPolicyCounters
    submit_text: str
    history: str
    transcript: list[dict[str, Any]]


def _tool_help_text() -> str:
    # Keep this short; you can generate from tb.TOOL_SIGNATURES if you want.
    return (
        "TOOLS (respond with JSON only):\n"
        '- {"tool":"get_task_overview","args":{}}\n'
        '- {"tool":"list_actions","args":{}}\n'
        '- {"tool":"list_objects","args":{"kind":null}}   # kind optional\n'
        '- {"tool":"describe_object","args":{"name":"..."}}\n'
        '- {"tool":"describe_action","args":{"action_name":"..."}}\n'
        '- {"tool":"get_state","args":{"max_facts":200}}  # optional\n'
        '- {"tool":"act","args":{"step_text":"(action arg1 arg2)"}}\n'
            '- {"tool":"get_history","args":{}}\n'
        '- {"tool":"submit","args":{"unsolvable":false}}  # set true to declare unsolvable\n'
    )


def _build_turn_prompt(observation: str) -> str:
    return (
        "You are solving an interactive planning episode.\n"
        "Rules:\n"
        "1) You MUST reply with a single JSON object specifying the next tool call.\n"
        "2) Do NOT include any extra keys beyond what you need.\n"
        "3) Precondition/domain violations in act() are FATAL (episode ends).\n"
        "4) Syntax mistakes / unknown actions in act() are recoverable.\n"
        "5) To declare unsolvable: submit with {\"unsolvable\": true}.\n\n"
        + _tool_help_text()
        + "\nOBSERVATION:\n"
        + observation
    )


async def evaluate_interactive(
    *,
    domain_name: str,
    problem_index: int,
    prompt_text: str,
    optimal_cost: Optional[float],
    val_path: str,
    val_flags: list[str],
    purple_url: str,
    max_iters: int = 40,
    limit_multiplier: float = 3.0,
    strict_invalid_action: bool = True,
) -> InteractiveResult:
    """
    Runs the interactive tool loop against the purple agent at `purple_url`.
    """
    # Ground truth solvability convention from your prompts.json:
    # optimal_cost == -1 => unsolvable
    is_gt_solvable = True
    optimal_steps = float(optimal_cost or 0.0)
    if optimal_cost is not None and optimal_cost < 0:
        is_gt_solvable = False
        optimal_steps = 0.0

    # Step limit logic (mirrors your script)
    if is_gt_solvable and optimal_steps > 0:
        ep_limit = max(20, int(optimal_steps * limit_multiplier))
    else:
        ep_limit = max_iters

    counters = ToolPolicyCounters()
    transcript: list[dict[str, Any]] = []
    submit_text = ""
    finish_reason = "unknown"
    is_valid = True
    declared_unsolvable = False

    async with _EP_LOCK:
        # Reset env episode
        tb.reset_episode(domain_name, problem_index, val_path=val_path, tolerance=0.001)

        # Optional: you can start by giving the purple agent the human prompt_text
        # but NOT the raw PDDL. prompt_text should be natural language overview.
        observation = (
            f"{prompt_text.strip()}\n\n"
            "Episode started. Use get_task_overview() and list_actions() to begin."
        )

        context_id = uuid.uuid4().hex

        async with httpx.AsyncClient() as http:
            for t in range(ep_limit):
                turn_prompt = _build_turn_prompt(observation)

                # Ask purple for next tool call
                try:
                    result = await _a2a_jsonrpc_send(
                        http=http,
                        base_url=purple_url,
                        user_text=turn_prompt,
                        context_id=context_id,
                    )
                    purple_text = _extract_purple_text(result)
                except Exception as e:
                    is_valid = False
                    finish_reason = f"purple_comm_error: {e}"
                    break

                # Parse tool call JSON
                try:
                    obj = _extract_json_obj(purple_text)
                    tool_name, tool_args = _normalize_tool_call(obj)
                except Exception as e:
                    counters.syntax_error_count += 1
                    observation = f"Error: Invalid tool call format ({e}). Reply with JSON only."
                    transcript.append(
                        {
                            "turn": t,
                            "purple_raw": purple_text,
                            "tool_call": None,
                            "observation": observation,
                        }
                    )
                    continue

                tool_name_norm = tool_name.strip()
                counters.track(tool_name_norm)

                # Execute tool
                tool_obs = ""
                terminal = False

                try:
                    if tool_name_norm == "submit" and bool(tool_args.get("unsolvable", False)):
                        declared_unsolvable = True
                        tool_obs = "Episode Terminated: DECLARED_UNSOLVABLE"
                        terminal = True

                    elif tool_name_norm == "get_task_overview":
                        tool_obs = _safe_call(tb.get_task_overview, domain_name, problem_index)

                    elif tool_name_norm == "list_actions":
                        # list_actions signature varies in some versions; be tolerant.
                        try:
                            tool_obs = _safe_call(tb.list_actions, domain_name)
                        except TypeError:
                            tool_obs = _safe_call(tb.list_actions, domain_name, problem_index)

                    elif tool_name_norm == "list_objects":
                        tool_obs = _safe_call(
                            tb.list_objects,
                            domain_name,
                            problem_index,
                            kind=tool_args.get("kind", None),
                        )

                    elif tool_name_norm == "describe_object":
                        tool_obs = _safe_call(tb.describe_object, domain_name, problem_index, tool_args["name"])

                    elif tool_name_norm == "describe_action":
                        tool_obs = _safe_call(tb.describe_action, domain_name, tool_args["action_name"])

                    elif tool_name_norm == "get_state":
                        tool_obs = _safe_call(tb.get_state, max_facts=int(tool_args.get("max_facts", 200)))

                    elif tool_name_norm == "get_history":
                        tool_obs = _safe_call(tb.get_history)

                    elif tool_name_norm == "act":
                        tool_obs = _safe_call(tb.act, tool_args["step_text"])

                        # Enforce your “allowed vs fatal” policy
                        if isinstance(tool_obs, str) and "Executed: NO" in tool_obs:
                            if _is_hallucinated_action_err(tool_obs):
                                counters.hallucinated_action_count += 1
                            elif _is_syntax_action_err(tool_obs):
                                counters.syntax_error_count += 1
                            else:
                                counters.precondition_error_count += 1
                                if strict_invalid_action:
                                    tool_obs = f"FATAL DOMAIN ERROR: {tool_obs}"
                                    terminal = True
                                    finish_reason = "precondition_violation"

                    elif tool_name_norm == "submit":
                        submit_text = _safe_call(tb.submit)
                        tool_obs = submit_text
                        parsed = _parse_submit_text(submit_text)
                        if parsed.get("accepted") is True:
                            terminal = True

                    else:
                        counters.hallucinated_tool_count += 1
                        tool_obs = (
                            f"Error: Tool '{tool_name_norm}' not found.\n"
                            f"Valid tools are: get_task_overview, list_actions, list_objects, "
                            f"describe_object, describe_action, get_state, act, get_history, submit."
                        )

                except Exception as e:
                    is_valid = False
                    finish_reason = f"tool_exec_error:{tool_name_norm}:{e}"
                    terminal = True
                    tool_obs = f"Execution error in {tool_name_norm}: {e}"

                transcript.append(
                    {
                        "turn": t,
                        "tool_call": {"tool": tool_name_norm, "args": tool_args},
                        "purple_raw": purple_text,
                        "observation": tool_obs,
                    }
                )

                observation = tool_obs

                if terminal:
                    break

        # End-of-episode bookkeeping (history + score)
        history = tb.get_history()
        steps_taken = _count_history_steps(history)

        # If purple never submitted and didn't crash, submit once for scoring
        if not declared_unsolvable and is_valid and not submit_text:
            try:
                submit_text = tb.submit()
            except Exception as e:
                is_valid = False
                finish_reason = f"submit_crash:{e}"
                submit_text = f"Submit Failed: {e}"

        # Decide success/failure reasons (mirrors your script)
        if finish_reason == "precondition_violation":
            is_success = False
        elif declared_unsolvable:
            if not is_gt_solvable:
                is_success = True
                finish_reason = "correctly_identified_unsolvable"
            else:
                is_success = False
                finish_reason = "false_negative_unsolvable"
        else:
            parsed = _parse_submit_text(submit_text or "")
            accepted = parsed.get("accepted") is True
            if accepted and not is_gt_solvable:
                is_success = False
                finish_reason = "false_positive_solvable"
            elif accepted and is_gt_solvable:
                is_success = True
                finish_reason = finish_reason if finish_reason != "unknown" else "success"
            else:
                is_success = False
                finish_reason = finish_reason if finish_reason != "unknown" else "goal_not_reached"

        # Score: same as your harness
        score = 0.0
        if is_success:
            if not is_gt_solvable:
                score = 1.0
            elif steps_taken > 0 and optimal_steps > 0:
                score = min(1.0, float(optimal_steps) / float(steps_taken))

        return InteractiveResult(
            is_valid=is_valid,
            is_success=is_success,
            finish_reason=finish_reason,
            steps_taken=steps_taken,
            optimal_steps=optimal_steps,
            score=score,
            tool_policy=counters,
            submit_text=submit_text,
            history=history,
            transcript=transcript,
        )
