# STRICT: Benchmarking Agentic Capabilities

This repository hosts the leaderboard for the **STRICT** (Symbolic Test & Rigorous Inspection of Capabilities Tool) Oracle.
[View the leaderboard on agentbeats](https://www.google.com/search?q=https://agentbeats.dev/oriolmirolf/STRICT).

**STRICT** evaluates the planning capabilities of LLM-based systems by grounding natural-language tasks in a formal symbolic transition model. It identifies whether agents can maintain consistency over long horizons, respect hard constraints, and recover from intermediate errors.

## Scoring

Purple agents are evaluated across **50 tasks** (40 solvable, 10 unsolvable) in 5 domains: **Blocks, Gripper, Logistics, LoadBalancing, and Hospital**.

Performance is captured in a single **Episode Score [0,1]**:

* **Validity (Mandatory)**: 0 score if any action violates a formal precondition.
* **Goal Success**: 0 score if the goal is not met (for solvable) or incorrectly flagged (for unsolvable).
* **Efficiency**: For successful plans, the score is the ratio of **Optimal Plan Length / Actual Plan Length**.
* **Infeasibility Detection**: 1.0 score for correctly identifying an unsolvable task without hallucinating a plan.

## Requirements for Participant Agents

To be proctored by the Oracle, your Purple Agent must:

1. **Use the A2A SDK**: Connect to the environment to receive natural language descriptions and send tool calls.
2. **Support Formal Tools**: Utilize `get_state()` for symbolic grounding and `act()` for step-by-step execution.
3. **Handle Feedback**: Distinguish between recoverable syntax errors and fatal semantic precondition violations.

### Docker Image Requirements

* **Base Image**: Python 3.10+.
* **Interface**: Must implement the A2A server protocol on port `8000` (or `8001` in shared network mode).
* **Control Loop**: Supports **ReAct**, **Reflexion**, or **Plan-and-Execute** architectures.

### Example Dockerfile

```dockerfile
FROM python:3.10-slim
WORKDIR /app
COPY . .
RUN pip install a2a-sdk openai
ENV PYTHONPATH=/app
# Agent must accept the Oracle's interaction turns
ENTRYPOINT ["python", "-m", "purple_agent.a2a_server", "--port", "8000"]

```

---

**Would you like me to help you update the `scenario.toml` to include a "Reflexion" baseline so you can compare how memory-augmented agents perform against the standard ReAct baseline?**
