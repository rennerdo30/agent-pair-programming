"""Where the data folder lives."""

from __future__ import annotations

import os
from pathlib import Path

DATA_ENV = "PAIR_DESK_DATA"


def default_data_dir() -> Path:
    """The data folder: $PAIR_DESK_DATA, else %LOCALAPPDATA%\\AgentPairProgramming on Windows,
    else ~/.agent-pair-programming."""
    override = os.environ.get(DATA_ENV)
    if override:
        return Path(override).expanduser()
    if os.name == "nt":
        base = os.environ.get("LOCALAPPDATA")
        if base:
            return Path(base) / "AgentPairProgramming"
        return Path.home() / "AppData" / "Local" / "AgentPairProgramming"
    return Path.home() / ".agent-pair-programming"


def resolve_data_dir(value: str | os.PathLike | None) -> Path:
    return Path(value).expanduser() if value else default_data_dir()
