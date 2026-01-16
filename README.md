# STRICT: Planning (Green Agent)

**STRICT** (Symbolic Test & Rigorous Inspection of Capabilities Tool) is a formal planning proctor built for the **AgentBeats** competition. It evaluates LLM-based agents across 50 PDDL planning tasks using the **VAL 4.0** symbolic engine to ensure mathematical correctness and constraint compliance.

## 🚀 Quick Start (Local Run)

To run the Oracle locally for testing, ensure you have Docker installed and execute:

```bash
docker build -t formaplan-oracle .
docker run -p 8000:8000 formaplan-oracle --host 0.0.0.0 --port 8000

```

## 🛠️ Configuration & Environment

The Oracle runs end-to-end without manual intervention. It automatically manages:

* **PDDL Validation**: Integrated `Validate` binary for formal state checks.
* **Resource Extraction**: Automatically renames and reports `input_tokens` and `output_tokens` in the final evaluation artifact.
* **Domain Suite**: Pre-loaded with `blocks`, `gripper`, `logistics`, `hospital`, and `balancer` domains.

### Deployment Parameters

When registered on the platform, the agent accepts the following standard A2A arguments:

* `--host`: Binds the server to a specific IP (default `0.0.0.0`).
* `--port`: Listens on a specific port (standard `8000`).
* `--card-url`: Advertises the agent's capability card.

## 📊 Evaluation Logic

STRICT uses a multi-turn interactive protocol. It provides the Purple Agent with a natural language task description and validates every `act()` tool call against the formal transition model.

* **Fatal Error**: Any precondition violation terminates the task immediately.
* **Scoring**: Calculated as the ratio of the optimal reference plan length over the agent's actual plan length.

## 🤝 Contributing

This agent is part of a Master's Thesis on agentic planning evaluation. For technical details on the symbolic grounding logic, please refer to the `green_agent/` source code.


http://googleusercontent.com/youtube_content/29

```
