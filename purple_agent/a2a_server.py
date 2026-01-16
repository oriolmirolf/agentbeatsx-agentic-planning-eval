from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI

from a2a.server.agent_execution import AgentExecutor, RequestContext
from a2a.server.apps import A2AStarletteApplication
from a2a.server.events import EventQueue
from a2a.server.request_handlers import DefaultRequestHandler
from a2a.server.tasks import InMemoryTaskStore, TaskUpdater
from a2a.types import AgentCard, AgentCapabilities, AgentSkill, TaskState
from a2a.utils import get_message_text, new_agent_text_message, new_task


def _extract_tool_env_observation(user_text: str) -> Optional[str]:
    """
    Green sends a prompt that contains an OBSERVATION section. Keeping ONLY that section
    massively improves tool-call compliance vs sending the whole long instruction blob.
    """
    if not user_text:
        return None
    marker = "\nOBSERVATION:\n"
    if marker in user_text:
        return user_text.split(marker, 1)[1].strip()
    return None


class PurpleReActAgent:
    """
    Baseline Purple agent:
    - always returns a single JSON object {"tool":..., "args":...}
    - never wraps in markdown fences
    - keeps short memory per task to avoid ballooning prompts
    """

    def __init__(self) -> None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            # Fail fast with a clear message (otherwise you'll get confusing OpenAI errors)
            raise RuntimeError("OPENAI_API_KEY is not set")

        self.client = AsyncOpenAI(api_key=api_key)
        self.model = os.getenv("LLM_MODEL", "gpt-4o-mini")

        # Keep a small rolling history per task to improve reliability without huge context.
        self._history: Dict[str, List[Dict[str, str]]] = {}

        self.system_prompt = (
            "You are a PDDL Planning Agent interacting with an environment ONLY via tool calls.\n"
            "You MUST output exactly one JSON object and nothing else.\n"
            'Format: {"tool": "<tool_name>", "args": {...}}\n'
            "Do not include markdown fences, explanations, or extra keys.\n"
            "\n"
            "Available tools:\n"
            "- get_task_overview\n"
            "- list_actions\n"
            "- list_objects\n"
            "- describe_object\n"
            "- describe_action\n"
            "- get_state\n"
            "- act\n"
            "- get_history\n"
            "- submit\n"
            "\n"
            "Policy:\n"
            "- Start with get_task_overview.\n"
            "- Use list_actions/get_state as needed.\n"
            "- Use act for a single action string like \"(pick-up a)\".\n"
            "- Submit when solved; submit {\"unsolvable\": true} if impossible.\n"
        )

        # How many user/assistant turns to keep (excluding system)
        self.max_turns_kept = int(os.getenv("PURPLE_MAX_TURNS", "12"))

    def _ensure_json_object(self, s: str) -> str:
        """
        OpenAI can still occasionally emit non-JSON. This enforces a JSON object output.
        If parsing fails, fall back to a safe tool call.
        """
        try:
            obj = json.loads(s)
            if isinstance(obj, dict) and "tool" in obj:
                return json.dumps(obj)
        except Exception:
            pass
        # Safe fallback (recoverable) if model misbehaves:
        return json.dumps({"tool": "get_task_overview", "args": {}})

    def _trim_history(self, hist: List[Dict[str, str]]) -> List[Dict[str, str]]:
        # Keep system + last N user/assistant messages
        if not hist:
            return hist
        system = hist[:1]
        rest = hist[1:]
        # each turn = user+assistant; keep max_turns_kept messages (not pairs) for simplicity
        return system + rest[-self.max_turns_kept :]

    async def run(self, task_id: str, message: Any, updater: TaskUpdater) -> None:
        user_text = get_message_text(message)

        # Prefer only the observation block (much cleaner signal)
        obs = _extract_tool_env_observation(user_text)
        effective_user = obs if obs is not None else user_text

        hist = self._history.setdefault(task_id, [])
        if not hist:
            hist.append({"role": "system", "content": self.system_prompt})

        hist.append({"role": "user", "content": effective_user})
        hist[:] = self._trim_history(hist)

        await updater.update_status(TaskState.working, new_agent_text_message("ReAct: thinking..."))

        try:
            resp = await self.client.chat.completions.create(
                model=self.model,
                messages=hist,
                response_format={"type": "json_object"},
            )

            out = resp.choices[0].message.content or "{}"
            out = self._ensure_json_object(out)

            hist.append({"role": "assistant", "content": out})
            hist[:] = self._trim_history(hist)

            # IMPORTANT: complete with a normal A2A message (with parts)
            await updater.complete(new_agent_text_message(out))

        except Exception as e:
            await updater.failed(new_agent_text_message(f"LLM error: {type(e).__name__}: {e}"))


class SimpleExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.agent = PurpleReActAgent()

    async def execute(self, context: RequestContext, event_queue: EventQueue) -> None:
        msg = context.message
        task = context.current_task
        if not task:
            task = new_task(msg)
            await event_queue.enqueue_event(task)

        updater = TaskUpdater(event_queue, task.id, task.context_id)
        await updater.start_work()
        await self.agent.run(task.id, msg, updater)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        return


def build_app(card_url: str | None = None) -> Any:
    # IMPORTANT: card_url should match the externally-reachable URL passed in docker-compose:
    # e.g. http://planner:9009 (not localhost:8001)
    url = card_url or os.getenv("PURPLE_AGENT_URL", "http://localhost:8001")

    card = AgentCard(
        name="Purple ReAct",
        description="Baseline LLM ReAct planner that emits JSON tool calls.",
        url=url,
        version="2.0.3",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="react-planning",
                name="ReAct Planner",
                description="LLM reasoning for PDDL via tool calls.",
                tags=["llm", "react", "planner"],
            )
        ],
    )

    return A2AStarletteApplication(
        agent_card=card,
        http_handler=DefaultRequestHandler(
            agent_executor=SimpleExecutor(),
            task_store=InMemoryTaskStore(),
        ),
    ).build()


if __name__ == "__main__":
    import argparse
    import uvicorn

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument(
        "--card-url",
        type=str,
        help="URL for the agent card (provided by platform / compose, e.g. http://planner:9009)",
    )
    args = parser.parse_args()

    app = build_app(card_url=args.card_url)
    uvicorn.run(app, host=args.host, port=args.port)
