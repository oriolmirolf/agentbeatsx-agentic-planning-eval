from __future__ import annotations

import os
import shutil
from pathlib import Path


def _repo_root_from_here() -> Path:
    # green_agent/val_utils.py -> green_agent/ -> repo root
    return Path(__file__).resolve().parents[1]


def auto_detect_val_path(repo_root: Path | None = None) -> str | None:
    """
    Find a VAL Validate binary.
    Priority:
      1) env VAL_PATH
      2) bundled binary in repo
      3) PATH lookup ("Validate")
    """
    env = os.getenv("VAL_PATH")
    if env:
        p = Path(env)
        if p.exists() and p.is_file():
            return str(p.resolve())

    rr = repo_root or _repo_root_from_here()

    candidates = [
        rr / "green_agent" / "Val-20211204.1-Linux" / "bin" / "Validate",
        rr / "green_agent" / "VAL" / "bin" / "Validate",
        rr / "Val-20211204.1-Linux" / "bin" / "Validate",
    ]
    for p in candidates:
        if p.exists() and p.is_file():
            return str(p.resolve())

    which = shutil.which("Validate")
    return which
