# green_agent/interactive_runner.py
from __future__ import annotations

import asyncio
import json
import math
import os
import re
import uuid
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, Optional

import httpx

from green_agent import tools_backend as tb

# -----------------------------------------------------------------------------
# CRITICAL NETWORK FIX (proxy-proof inside Docker & CI)
# -----------------------------------------------------------------------------
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    os.environ.pop(k, None)

# -----------------------------------------------------------------------------
# A single global lock to protect tools_backend's global episode state (_EP).
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

    # 1) Markdown fenced block
    m = _JSON_FENCE_RE.search(text)
    if m:
        try:
            obj = json.loads(m.group(1))
            if not isinstance(obj, dict):
                raise ValueError("JSON must be an object")
            return obj
        except Exception:
            pass  # fall through

    # 2) Heuristic: first '{' and last '}'
    s = text.strip()
    start = s.find("{")
    end = s.rfind("}")

    if start == -1 or end == -1 or end <= start:
        # Fallback: try parsing the whole string
        try:
            obj = json.loads(s)
        except Exception:
            raise ValueError(f"No JSON object found in response: {s[:200]}")
        if not isinstance(obj, dict):
            raise ValueError(f"Expected JSON object, got {type(obj)}")
        return obj

    try:
        obj = json.loads(s[start : end + 1])
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON found between braces: {e}")

    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object, got {type(obj)}")
    return obj


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
    if t.lower() in {"finish", "submit_episode"}:
        t = "submit"
    return t, args


def _is_hallucinated_action_err(out: str) -> bool:
    lower = out.lower()
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
    Like EpisodeTools._call: tolerate minor signature differences.
    """
    try:
        return fn(*args, **kwargs)
    except TypeError:
        if kwargs and not args:
            return fn(**kwargs)
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
    timeout_s: float = 300.0,
) -> dict[str, Any]:
    """
    Sends JSON-RPC method "message/send" to an A2A server.
    """
    if "://" not in base_url:
        base_url = "http://" + base_url

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
            "configuration": {"blocking": True},
        },
    }

    resp = await http.post(url, json=payload, timeout=timeout_s)
    resp.raise_for_status()
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"A2A error: {data['error']}")
    if "result" not in data:
        raise RuntimeError(f"A2A missing result: {data}")
    res = data["result"]
    if not isinstance(res, dict):
        raise RuntimeError(f"A2A result not an object: {type(res)}")
    return res


def _extract_text_from_parts(parts: Any) -> str:
    if not isinstance(parts, list):
        return ""
    texts: list[str] = []
    for p in parts:
        if isinstance(p, dict):
            if (p.get("kind") == "text" or p.get("type") == "text" or "text" in p) and isinstance(p.get("text"), str):
                texts.append(p["text"])
    return "\n".join(texts).strip()


def _extract_purple_text(result: dict[str, Any]) -> str:
    """
    Extracts text from A2A responses. Purple may return:
      1) Message-like: {"kind":"message","parts":[...]} or {"message": {"parts":[...]}}
      2) Task-like: {"kind":"task","status":{"message":{"parts":[...]}}}
      3) Messages in history: {"history":[{"role":"agent","parts":[...]}], ...}
    """
    if not isinstance(result, dict):
        raise RuntimeError(f"Purple returned non-object result: {type(result)}")

    # (1) direct message
    txt = _extract_text_from_parts(result.get("parts"))
    if txt:
        return txt

    msg = result.get("message")
    if isinstance(msg, dict):
        txt = _extract_text_from_parts(msg.get("parts"))
        if txt:
            return txt

    # (2) task.status.message
    status = result.get("status")
    if isinstance(status, dict):
        st_msg = status.get("message")
        if isinstance(st_msg, dict):
            txt = _extract_text_from_parts(st_msg.get("parts"))
            if txt:
                return txt

    # (3) search history for latest agent message
    history = result.get("history")
    if isinstance(history, list) and history:
        for item in reversed(history):
            if isinstance(item, dict) and item.get("role") == "agent":
                txt = _extract_text_from_parts(item.get("parts"))
                if txt:
                    return txt
        for item in reversed(history):
            if isinstance(item, dict):
                txt = _extract_text_from_parts(item.get("parts"))
                if txt:
                    return txt

    raise RuntimeError(f"Purple returned no parsable text parts: {result}")


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

    # Ground truth solvability convention:
    # optimal_cost < 0 => unsolvable
    is_gt_solvable = True
    optimal_steps = float(optimal_cost or 0.0)
    if optimal_cost is not None and optimal_cost < 0:
        is_gt_solvable = False
        optimal_steps = 0.0

    # Step limit logic:
    if is_gt_solvable and optimal_steps > 0:
        ep_limit = max(20, int(math.floor(optimal_steps * limit_multiplier)))
    else:
        ep_limit = int(max_iters)

    counters = ToolPolicyCounters()
    transcript: list[dict[str, Any]] = []
    submit_text = ""
    finish_reason = "unknown"
    is_valid = True
    declared_unsolvable = False

    async with _EP_LOCK:
        tb.reset_episode(domain_name, problem_index, val_path=val_path, tolerance=0.001)

        observation = (
            f"{prompt_text.strip()}\n\n"
            "Episode started. Use get_task_overview() and list_actions() to begin."
        )

        context_id = uuid.uuid4().hex

        # Make httpx proxy-proof even if env has proxies
        timeout = httpx.Timeout(connect=10.0, read=300.0, write=30.0, pool=30.0)
        limits = httpx.Limits(max_connections=50, max_keepalive_connections=20)

        async with httpx.AsyncClient(timeout=timeout, limits=limits, trust_env=False) as http:
            for t in range(ep_limit):
                turn_prompt = _build_turn_prompt(observation)

                # Ask purple for next tool call
                try:
                    result = await _a2a_jsonrpc_send(
                        http=http,
                        base_url=purple_url,
                        user_text=turn_prompt,
                        context_id=context_id,
                        timeout_s=300.0,
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
                        {"turn": t, "purple_raw": purple_text, "tool_call": None, "observation": observation}
                    )
                    continue

                tool_name_norm = tool_name.strip()
                counters.track(tool_name_norm)

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
                            "Valid tools are: get_task_overview, list_actions, list_objects, "
                            "describe_object, describe_action, get_state, act, get_history, submit."
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

        # Decide success/failure reasons
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

        # Score
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
