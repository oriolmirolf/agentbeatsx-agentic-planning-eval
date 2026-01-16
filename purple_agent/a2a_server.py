from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Dict, Any

# A2A SDK imports
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
    InvalidRequestError
)
from a2a.utils import get_message_text, new_agent_text_message, new_task
from a2a.utils.errors import ServerError

@dataclass
class TurnState:
    stage: int = 0

class PurpleBaselinePolicy:
    def __init__(self) -> None:
        # Maps context_id to TurnState to support parallel evaluations
        self._states: Dict[str, TurnState] = {}

    def next_tool_call(self, context_id: str, _prompt: str) -> str:
        st = self._states.setdefault(context_id, TurnState(stage=0))
        
        if st.stage == 0:
            st.stage = 1
            return json.dumps({"tool_name": "get_task_overview", "tool_args": {}}, indent=2)
        if st.stage == 1:
            st.stage = 2
            return json.dumps({"tool_name": "list_actions", "tool_args": {}}, indent=2)
        if st.stage == 2:
            st.stage = 3
            return json.dumps({"tool_name": "get_state", "tool_args": {"max_facts": 200}}, indent=2)
        
        st.stage = 999
        return json.dumps({"tool_name": "submit", "tool_args": {"unsolvable": True}}, indent=2)

class PurpleAgentInstance:
    def __init__(self, policy: PurpleBaselinePolicy) -> None:
        self.policy = policy

    async def run(self, message: Any, updater: TaskUpdater, context_id: str) -> None:
        prompt = get_message_text(message)
        
        await updater.update_status(TaskState.working, new_agent_text_message("Purple Agent: Reasoning..."))

        # Generate the next step in the symbolic plan
        tool_call_json = self.policy.next_tool_call(context_id, prompt)
        
        # Send the tool call back to the Green Oracle
        await updater.complete(new_agent_text_message(tool_call_json))

# --- Executor ---
TERMINAL_STATES = {TaskState.completed, TaskState.canceled, TaskState.failed, TaskState.rejected}

class PurpleAgentExecutor(AgentExecutor):
    def __init__(self) -> None:
        self.policy = PurpleBaselinePolicy()

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

        agent = PurpleAgentInstance(self.policy)
        await agent.run(msg, updater, task.context_id)

    async def cancel(self, context: RequestContext, event_queue: EventQueue) -> None:
        pass

def build_agent_card(card_url: str | None = None) -> AgentCard:
    advertised_url = card_url or os.getenv("AGENT_URL", "http://localhost:8001")
    
    return AgentCard(
        name="Purple Baseline Tool Planner",
        description="A deterministic baseline policy that cycles through inspection tools.",
        url=advertised_url, 
        version="1.0.0",
        capabilities=AgentCapabilities(streaming=True),
        default_input_modes=["text"],
        default_output_modes=["text"],
        skills=[
            AgentSkill(
                id="tool-planner",
                name="Tool Planner",
                description="Returns next symbolic tool call as JSON.",
                tags=["baseline", "planner", "tools"],
            )
        ]
    )

def build_app(card_url: str | None = None):
    return A2AStarletteApplication(
        build_agent_card(card_url),
        DefaultRequestHandler(
            agent_executor=PurpleAgentExecutor(),
            task_store=InMemoryTaskStore()
        )
    ).build()

app = build_app()

if __name__ == "__main__":
    import uvicorn
    import argparse

    parser = argparse.ArgumentParser()
    parser.add_argument("--host", type=str, default="0.0.0.0")
    parser.add_argument("--port", type=int, default=8001)
    parser.add_argument("--card-url", type=str, help="URL for the agent card")
    args = parser.parse_args()

    app = build_app(card_url=args.card_url)
    uvicorn.run(app, host=args.host, port=args.port)