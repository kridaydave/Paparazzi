"""Shared value types.

Every module speaks these, so nobody has to import another worker's file just
to describe a result. Nothing here does I/O.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


def _as_int(value: Any, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _as_float(value: Any) -> float | None:
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


@dataclass(frozen=True)
class Usage:
    """Token accounting from one API response.

    `prompt_tokens` is the number the model's own tokenizer produced, which is
    what the tokenizer differential probe measures.
    """

    prompt_tokens: int = 0
    completion_tokens: int = 0
    reasoning_tokens: int = 0
    cost: float | None = None

    @classmethod
    def from_response(cls, data: dict[str, Any] | None) -> "Usage":
        """Parse the `usage` object of an OpenRouter response. Absent fields stay 0."""
        if not isinstance(data, dict):
            return cls()
        details = data.get("completion_tokens_details")
        reasoning = details.get("reasoning_tokens") if isinstance(details, dict) else None
        return cls(
            prompt_tokens=_as_int(data.get("prompt_tokens")),
            completion_tokens=_as_int(data.get("completion_tokens")),
            reasoning_tokens=_as_int(reasoning),
            cost=_as_float(data.get("cost")),
        )


@dataclass(frozen=True)
class Completion:
    """One API call, success or failure. Never a raised exception."""

    text: str = ""
    usage: Usage = field(default_factory=Usage)
    latency_ms: int = 0
    status: int = 0  # HTTP status, 0 when the request never completed
    headers: dict[str, str] = field(default_factory=dict)
    raw: dict[str, Any] = field(default_factory=dict)
    ok: bool = True
    error: str | None = None

    @property
    def used_mock(self) -> bool:
        return bool(self.raw.get("paparazzi_mock"))


@dataclass(frozen=True)
class BatteryPrompt:
    """One prompt from data/battery.yaml."""

    key: str
    text: str
    category: str = "general"
