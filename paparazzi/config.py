"""Runtime configuration resolved from environment variables.

Nothing is read at import time, so tests can monkeypatch the environment and
see the new value on the next call.
"""

from __future__ import annotations

import os
from pathlib import Path

from paparazzi import db


def openrouter_key() -> str | None:
    """Return the OpenRouter API key from the environment, or None if unset."""
    value = os.environ.get("PAPARAZZI_OPENROUTER_KEY")
    return value if value else None


def db_path() -> Path:
    """Resolve the sqlite database path, honoring PAPARAZZI_DB."""
    value = os.environ.get("PAPARAZZI_DB")
    if value:
        return Path(value)
    return db.DEFAULT_DB


def mock() -> bool:
    """Whether mock mode is requested via the environment."""
    value = os.environ.get("PAPARAZZI_MOCK", "")
    return value.strip().lower() in {"1", "true", "yes", "on"}