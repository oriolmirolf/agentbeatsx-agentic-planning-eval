from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class EvalConfig:
    domain_path: str
    problem_path: str
    out_dir: str = "out"

    # Optional override for where to write this run's artifacts.
    run_dir: str | None = None

    val_path: str | None = None
    # DEFAULT: "-v" only (no "-e").
    val_flags: tuple[str, ...] = ("-v",)
    tolerance: float = 0.001

    # Purple agent selection
    purple_kind: str = "openai"
    purple_url: str | None = None  # a2a endpoint (if purple_kind='a2a')

    # Prompt sources
    prompt_path: str | None = None
    prompt_text: str | None = None

    # Model + provider config (for OpenAI-compatible providers)
    openai_model: str | None = None
    llm_base_url: str | None = None  # e.g., http://localhost:8000/v1
    llm_api_key: str | None = None  # API key for that endpoint (if needed)

    check_redundancy: bool = False

    # Scoring
    optimal_cost: float | None = None

    # Printing control
    print_card: bool = True

    # Strategy-based purple orchestration
    strategy_name: str | None = None
    strategy_params: dict[str, Any] | None = None
