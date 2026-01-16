from __future__ import annotations

import os
# --- CRITICAL NETWORK FIX ---
# Ensures internal Docker container communication isn't blocked by proxy settings
os.environ["NO_PROXY"] = "*"
os.environ["no_proxy"] = "*"
for k in ["HTTP_PROXY", "HTTPS_PROXY", "http_proxy", "https_proxy"]:
    if k in os.environ: del os.environ[k]
# ----------------------------

import asyncio
import json
import socket
import httpx
from urllib.parse import urlparse
from typing import Any, Dict
from uuid import uuid4

from pydantic import BaseModel, Field, ValidationError

# A2A SDK
from a2a.client import A2ACardResolver, ClientConfig, ClientFactory
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
    TextPart,
    InvalidRequestError,
    Message,
    Role
)
from a2a.utils import get_message_text, new_agent_text_message, new_task
from a2a.utils.errors import ServerError

from green_agent import tools_backend as tb
from green_agent.interactive_runner import evaluate_interactive
from green_agent.val_utils import auto_detect_val_path

# --- Helper Utilities ---

def _part_text(parts: list[Part]) -> str:
    chunks: list[str] = []
    for part in parts:
        if isinstance(part.root, TextPart):
            chunks.append(part.root.text)
        elif isinstance(part.root, DataPart):
            chunks.append(json.dumps(part.root.data, indent=2))
    return "\n".join(chunks)

# --- Benchmark Logic ---

class EvalRequest(BaseModel):
    participants: Dict[str, str] = Field(default_factory=dict)
    config: Dict[str, Any] = Field(default_factory=dict)

class GreenBenchmarkAgent:
    def __init__(self) -> None:
        self._lock = asyncio.Lock()

    async def run(self, message: Any, updater: TaskUpdater) -> None:
        input_text = get_message_text(message)
        
        # 1. Parse Request
        try:
            req = EvalRequest.model_validate_json(input_text)
        except ValidationError as e:
            await updater.reject(new_agent_text_message(f"Invalid request schema: {e}"))
            return

        cfg = req.config or {}
        participants = req.participants or {}
        purple_url = participants.get("planner") or participants.get("purple")
        
        if not purple_url:
            await updater.reject(new_agent_text_message("Missing purple URL in participants dict"))
            return

        # 2. Resolve IP manually to bypass potential Docker DNS/proxy issues
        real_url = purple_url
        try:
            p = urlparse(purple_url)
            if p.hostname:
                ip = socket.gethostbyname(p.hostname)
                real_url = purple_url.replace(p.hostname, ip)
        except Exception:
            pass

        domain = str(cfg.get("domain", "blocks"))
        index = int(cfg.get("index", 1))

        await updater.update_status(
            TaskState.working, 
            new_agent_text_message(f"Oracle: Loading {domain} problem {index}...")
        )

        # 3. Setup Problem Configuration via Symbolic Backend
        try:
            async with self._lock:
                spec = tb.load_problem_spec(domain, index)
            
            prompt_text = spec.overview.description
            if spec.overview.initial_state:
                prompt_text += f"\n\nInitial State:\n{spec.overview.initial_state}"
            if spec.overview.goal:
                prompt_text += f"\n\nGoal:\n{spec.overview.goal}"
        except Exception as e:
            await updater.failed(new_agent_text_message(f"Pydantic/PDDL Load Error: {e}"))
            return

        val_path = auto_detect_val_path()
        if not val_path:
            await updater.failed(new_agent_text_message("VAL binary not found in environment."))
            return

        # 4. Run the Interactive Loop (The Verification Process)
        await updater.update_status(TaskState.working, new_agent_text_message("Engaging Purple Agent..."))
        
        try:
            async with self._lock:
                # evaluate_interactive uses _talk_to_agent internally.
                # Ensure it handles the Task-based response.
                result = await evaluate_interactive(
                    domain_name=domain,
                    problem_index=index,
                    prompt_text=prompt_text,
                    optimal_cost=float(cfg.get("optimal_cost", -1.0)),
                    val_path=val_path,
                    val_flags=["-v"],
                    purple_url=real_url,
                    max_iters=int(cfg.get("max_steps", 40)),
                )

            # 5. Report Formal Artifact
            output_data = {
                "ok": True,
                "domain": domain,
                "problem": index,
                "is_success": result.is_success,
                "score": result.score,
                "steps_taken": result.steps_taken,
                "optimal_steps": result.optimal_steps,
                "finish_reason": result.finish_reason,
                "history": result.history,
                "transcript": result.transcript,
                # Explicitly naming tokens as per user instructions
                "input_tokens": getattr(result, "input_tokens", 0),
                "output_tokens": getattr(result, "output_tokens", 0)
            }

            await updater.add_artifact(
                parts=[Part(root=DataPart(kind="data", data=output_data))],
                name="Symbolic Verification Result"
            )
            
            # Final completion message
            final_msg = f"Evaluation Complete. Success: {result.is_success} | Score: {result.score}"
            await updater.complete(new_agent_text_message(final_msg))

        except Exception as e:
            await updater.failed(new_agent_text_message(f"Runtime Oracle Error: {str(e)}"))

# --- Executor ---

TERMINAL_STATES = {TaskState.completed, TaskState.canceled, TaskState.failed, TaskState.rejected}

class GreenAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.agent = GreenBenchmarkAgent()

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
        pass

# --- Server Boilerplate ---

def build_agent_card(card_url: str | None = None) -> AgentCard:
    url = card_url or os.getenv("GREEN_AGENT_URL", "http://localhost:8000")
    return AgentCard(
        name="Symbolic Planning Oracle",
        description="Formal validator for Grounded Natural Language agents.",
        url=url,
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="constraint-verification", 
                name="Constraint Verification", 
                description="Verifies if NL actions respect hidden symbolic world rules.",
                tags=["planning", "formal-verification", "safety"]
            )
        ]
    )

def build_app(card_url: str | None = None):
    return A2AStarletteApplication(
        agent_card=build_agent_card(card_url), 
        http_handler=DefaultRequestHandler(
            agent_executor=GreenAgentExecutor(), 
            task_store=InMemoryTaskStore()
        )
    ).build()

app = build_app()

if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--card-url", type=str, help="URL for the agent card")
    args = parser.parse_args()

    # If the platform provides a card-url, it overrides defaults
    app = build_app(card_url=args.card_url)
    uvicorn.run(app, host=args.host, port=args.port)