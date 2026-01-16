# AgentBeats Submission: Interactive PDDL Evaluator

## Abstract
This submission implements a **Green Agent** that evaluates planning capabilities using a strict **Interactive Tool-Use Protocol**. Unlike traditional PDDL solvers that output a full plan at once, this Green Agent forces the Purple Agent (the planner) to act as an autonomous agent: it must explore the environment using tools (`get_task_overview`, `list_objects`, `get_state`) and execute actions step-by-step (`act`). The Green Agent utilizes the VAL PDDL validator to enforce domain constraints in real-time, providing immediate feedback on precondition violations or state changes.

## Repository Structure
- `green_agent/`: The evaluator logic, A2A server, and VAL integration.
- `purple_agent/`: A baseline agent that connects via A2A.
- `examples/`: PDDL domains and problems.

## How to Run (Reproducibility)
1. **Prerequisites**: Docker and Docker Compose.
2. **Build and Run**:
   ```bash
   chmod +x run_submission.sh
   ./run_submission.sh