from __future__ import annotations

import os

# --- CRITICAL NETWORK FIX ---
# Ensures internal Docker/container communication isn't blocked by proxy settings
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    if k in os.environ:
        del os.environ[k]
# ----------------------------

import asyncio
import json
import math
import socket
import statistics
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, ValidationError, field_validator


# A2A SDK
from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import (
    AgentCard,
    AgentSkill,
    AgentCapabilities,
    TaskState,
    Part,
    DataPart,
    InvalidRequestError,
)
from a2a.utils import get_message_text, new_agent_text_message, new_task
from a2a.utils.errors import ServerError

from green_agent import tools_backend as tb
from green_agent.interactive_runner import evaluate_interactive
from green_agent.val_utils import auto_detect_val_path


# Prefer these domains when running the full suite, but fall back to whatever exists under EXAMPLES_DIR.
DEFAULT_DOMAINS = ["blocks", "gripper", "logistics", "loadbalancing", "hospital"]


def _examples_root() -> Path:
    return Path(os.getenv("EXAMPLES_DIR", "examples"))


def _list_available_domains() -> list[str]:
    root = _examples_root()
    if not root.exists():
        return []
    return sorted([p.name for p in root.iterdir() if p.is_dir()])


_PROMPTS_CACHE: dict[str, dict[str, Any]] = {}
_DOMAIN_MEDIAN_CACHE: dict[str, Optional[float]] = {}


def _load_prompts(domain: str) -> dict[str, Any]:
    domain = str(domain).strip()
    if domain in _PROMPTS_CACHE:
        return _PROMPTS_CACHE[domain]

    prompts_path = _examples_root() / domain / "prompts.json"
    if not prompts_path.exists():
        raise FileNotFoundError(f"prompts.json not found for domain '{domain}' at {prompts_path}")

    data = json.loads(prompts_path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"Invalid prompts.json format for domain '{domain}' (expected object).")

    _PROMPTS_CACHE[domain] = data
    return data


def _get_optimal_cost(domain: str, index: int) -> Optional[float]:
    """
    Returns:
      - float optimal_cost if present
      - None if missing/invalid
    Convention:
      - optimal_cost < 0 means "unsolvable"
    """
    data = _load_prompts(domain)
    problems = data.get("problems") or []
    pid = f"p{int(index):02d}"

    entry = None
    for p in problems:
        if str(p.get("id", "")).strip() in {pid, str(index)}:
            entry = p
            break

    if not entry:
        return None

    oc = entry.get("optimal_cost", None)
    if oc is None:
        return None

    try:
        return float(oc)
    except Exception:
        return None


def _domain_median_optimal_cost(domain: str) -> Optional[float]:
    """
    Median of optimal_cost over solvable instances in prompts.json for a domain.
    Used to derive a non-global budget for unsolvable/unknown instances.
    """
    domain = str(domain).strip()
    if domain in _DOMAIN_MEDIAN_CACHE:
        return _DOMAIN_MEDIAN_CACHE[domain]

    try:
        data = _load_prompts(domain)
        vals: list[float] = []
        for p in (data.get("problems") or []):
            oc = p.get("optimal_cost", None)
            if oc is None:
                continue
            try:
                f = float(oc)
            except Exception:
                continue
            if f >= 0:  # solvable only
                vals.append(f)

        if not vals:
            _DOMAIN_MEDIAN_CACHE[domain] = None
            return None

        med = float(statistics.median(vals))
        _DOMAIN_MEDIAN_CACHE[domain] = med
        return med
    except Exception:
        _DOMAIN_MEDIAN_CACHE[domain] = None
        return None


def _parse_eval_request(input_text: str) -> "EvalRequest":
    """
    Be tolerant to wrappers: {"assessment_request": {...}} or direct {"participants":..., "config":...}
    """
    try:
        raw = json.loads(input_text)
    except json.JSONDecodeError as e:
        raise ValidationError.from_exception_data("EvalRequest", [{"loc": ("json",), "msg": str(e), "type": "value_error"}])

    if isinstance(raw, dict) and isinstance(raw.get("assessment_request"), dict):
        raw = raw["assessment_request"]

    return EvalRequest.model_validate(raw)


def _compute_episode_limit(
    *,
    domain: str,
    optimal_cost: Optional[float],
    cfg: Dict[str, Any],
) -> int:
    """
    Paper policy:
      if solvable: ep_limit = max(min_turns, floor(lambda * L*))
      if unsolvable: (user does not want a fixed global cap)
        -> derive a domain-adaptive cap: max(min_turns, floor(lambda_uns * median_L*_domain))
        -> optional override via config.unsolvable_turns
    """
    lam = float(cfg.get("limit_multiplier", 3.0) or 3.0)
    min_turns = int(cfg.get("min_turns", 20) or 20)

    # If caller explicitly overrides every episode, respect it.
    override = cfg.get("episode_turn_limit", None)
    if override is not None:
        try:
            return max(1, int(override))
        except Exception:
            pass

    # Solvable case
    if optimal_cost is not None and optimal_cost >= 0:
        return max(min_turns, int(math.floor(lam * optimal_cost)))

    # Unsolvable / unknown optimal_cost
    # Optional explicit setting (still not "hardcoded global"; it's chosen by you in config)
    unsolvable_turns = cfg.get("unsolvable_turns", None)
    if unsolvable_turns is not None:
        try:
            return max(min_turns, int(unsolvable_turns))
        except Exception:
            pass

    # Domain-adaptive: scale median solvable L* for the domain
    lam_uns = float(cfg.get("unsolvable_multiplier", lam) or lam)
    med = _domain_median_optimal_cost(domain)

    if med is not None and med > 0:
        return max(min_turns, int(math.floor(lam_uns * med)))

    # Last resort: no domain stats available -> give at least min_turns
    # (Still prevents infinite loops without introducing a fixed 40.)
    return max(1, min_turns)


class EvalRequest(BaseModel):
    participants: Dict[str, str] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("participants", mode="before")
    @classmethod
    def _norm_participants(cls, v):
        if v is None:
            return {}
        if isinstance(v, dict):
            return {str(k): str(val) for k, val in v.items()}
        if isinstance(v, list):
            out = {}
            for item in v:
                if not isinstance(item, dict):
                    continue
                role = item.get("role") or item.get("name")
                endpoint = item.get("endpoint") or item.get("url")
                if role and endpoint:
                    out[str(role)] = str(endpoint)
            return out
        return {}


class FormaPlanOracleAgent:
    """
    Green Agent: orchestrates an interactive tool loop against the Purple agent and emits
    a machine-readable artifact for AgentBeats.
    """

    def __init__(self) -> None:
        # Protects tools_backend's global episode state and any shared resources.
        self._lock = asyncio.Lock()

    async def run(self, message: Any, updater: TaskUpdater) -> None:
        input_text = get_message_text(message)

        # ---- Parse request payload (tolerant) ----
        try:
            req = _parse_eval_request(input_text)
        except Exception:
            await updater.reject(
                new_agent_text_message(
                    "Invalid request schema. Expected JSON like: "
                    '{"participants":{"planner":"http://..."},"config":{...}} '
                    'or {"assessment_request":{...}}'
                )
            )
            return

        cfg = req.config or {}
        participants = req.participants or {}
        purple_url = participants.get("planner") or participants.get("purple")

        if not purple_url:
            await updater.reject(new_agent_text_message("Missing purple URL in participants (expected key 'planner' or 'purple')."))
            return

        # ---- Resolve hostname to IP (helps with some Docker DNS/proxy edge cases) ----
        real_url = purple_url
        try:
            p = urlparse(purple_url)
            if p.hostname:
                host_no_dots = p.hostname.replace(".", "")
                if not host_no_dots.isdigit():
                    ip = socket.gethostbyname(p.hostname)
                    real_url = purple_url.replace(p.hostname, ip)
        except Exception:
            real_url = purple_url

        # ---- Ensure VAL exists ----
        val_path = auto_detect_val_path()
        if not val_path:
            await updater.failed(new_agent_text_message("VAL binary not found in environment (set VAL_PATH or bundle Validate)."))
            return

        # ---- Decide what to run ----
        target_domain = cfg.get("domain")
        target_index = cfg.get("index")

        if target_domain:
            domains_to_run = [str(target_domain).strip()]
            if target_index is not None:
                indices = [int(target_index)]
            else:
                indices = range(1, 11)
            suite_label = "Fast Test"
        else:
            available = _list_available_domains()
            preferred = [d for d in DEFAULT_DOMAINS if d in available]
            domains_to_run = preferred if preferred else available
            indices = range(1, 11)
            suite_label = "Autonomous Suite"

        if not domains_to_run:
            await updater.failed(
                new_agent_text_message(
                    "No domains found under EXAMPLES_DIR. "
                    "Ensure examples are present and EXAMPLES_DIR is set correctly."
                )
            )
            return

        await updater.update_status(
            TaskState.working,
            new_agent_text_message(f"Oracle: Starting {suite_label} ({len(domains_to_run)} domain(s))..."),
        )

        all_task_results: list[dict[str, Any]] = []
        total_in_tokens = 0
        total_out_tokens = 0

        # ---- Main evaluation loop ----
        try:
            for domain in domains_to_run:
                for i in indices:
                    await updater.update_status(
                        TaskState.working,
                        new_agent_text_message(f"Status: Formalizing {domain.upper()} Task {i}..."),
                    )

                    try:
                        async with self._lock:
                            # Load prompt/spec for problem
                            spec = tb.load_problem_spec(domain, int(i))

                            prompt_parts = [spec.overview.description.strip()]
                            if spec.overview.initial_state:
                                prompt_parts.append(f"Initial State:\n{spec.overview.initial_state.strip()}")
                            if spec.overview.goal:
                                prompt_parts.append(f"Goal:\n{spec.overview.goal.strip()}")
                            prompt = "\n\n".join([p for p in prompt_parts if p]).strip()

                            optimal_cost = _get_optimal_cost(domain, int(i))
                            ep_limit = _compute_episode_limit(
                                domain=domain,
                                optimal_cost=optimal_cost,
                                cfg=cfg,
                            )

                            result = await evaluate_interactive(
                                domain_name=domain,
                                problem_index=int(i),
                                prompt_text=prompt,
                                optimal_cost=optimal_cost,
                                val_path=val_path,
                                val_flags=["-v"],
                                purple_url=real_url,
                                max_iters=int(ep_limit),
                            )

                        # Token accounting:
                        in_toks = int(getattr(result, "input_tokens", 0) or (len(prompt) // 4))
                        out_toks = int(getattr(result, "output_tokens", 0) or (len(str(result.history)) // 4))

                        total_in_tokens += in_toks
                        total_out_tokens += out_toks

                        all_task_results.append({
                            "domain": domain,
                            "problem": i,
                            "is_executable": bool(result.is_valid),
                            "is_success": bool(result.is_success),
                            "finish_reason": str(result.finish_reason),
                            "score": float(result.score or 0.0),
                            "steps_taken": int(result.steps_taken or 0),
                        })

                    except Exception as e:
                        all_task_results.append({
                            "domain": domain,
                            "problem": int(i),
                            "is_executable": False,
                            "is_success": False,
                            "finish_reason": f"system_error: {e}",
                            "score": 0.0,
                            "steps_taken": 0,
                        })

            success_count = sum(1 for r in all_task_results if r.get("is_success") is True)
            normalized_score = (
                sum(float(r.get("score", 0.0) or 0.0) for r in all_task_results) / float(len(all_task_results) or 1)
            )

            output_data = {
                "ok": True,
                "benchmark_id": "FormaPlan-Autonomous-50",
                "summary": {
                    "success_count": sum(1 for r in all_task_results if r["is_success"]),
                    "normalized_score": sum(r["score"] for r in all_task_results) / (len(all_task_results) or 1),
                    "total_tasks": len(all_task_results),
                },
                "results": all_task_results,
            }


            await updater.add_artifact(
                parts=[Part(root=DataPart(kind="data", data=output_data))],
                name="FormaPlan Oracle: Final Formal Result",
            )

            await updater.complete(
                new_agent_text_message(
                    f"Benchmark Complete. Success: {success_count}/{len(all_task_results)} | Avg score: {normalized_score:.3f}"
                )
            )

        except Exception as e:
            await updater.failed(new_agent_text_message(f"Critical loop error: {e}"))


# --- SDK Infrastructure ---
TERMINAL_STATES = {TaskState.completed, TaskState.canceled, TaskState.failed, TaskState.rejected}


class GreenAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.agent = FormaPlanOracleAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        if not msg:
            raise ServerError(error=InvalidRequestError(message="Missing message"))

        task = context.current_task
        if task and task.status.state in TERMINAL_STATES:
            return

        if not task:
            task = new_task(msg)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()
        await self.agent.run(msg, updater)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return


def build_agent_card(card_url: str | None = None) -> AgentCard:
    url = card_url or os.getenv("GREEN_AGENT_URL", "http://localhost:8000")
    return AgentCard(
        name="FormaPlan Oracle",
        description="Autonomous formal benchmark for agentic planning via interactive symbolic verification.",
        url=url,
        version="2.1.8",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="autonomous-eval",
                name="Autonomous Evaluation",
                description="Automated PDDL proctoring via tool-mediated interaction.",
                tags=["formal", "pddl", "proctor"],
            )
        ],
    )


def build_app(card_url: str | None = None):
    return A2AStarletteApplication(
        agent_card=build_agent_card(card_url),
        http_handler=DefaultRequestHandler(
            agent_executor=GreenAgentExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()


app = build_app()


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--card-url", type=str, help="URL for the agent card (provided by platform)")
    args = parser.parse_args()

    app = build_app(card_url=args.card_url)
    uvicorn.run(app, host=args.host, port=args.port)
