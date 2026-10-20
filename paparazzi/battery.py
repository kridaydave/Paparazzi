"""Load the fixed probe battery from data/battery.yaml.

The battery is fixed on purpose. Changing it mid-experiment invalidates
comparison against stored signatures, so treat the file as append-only.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from paparazzi.types import BatteryPrompt

DEFAULT_BATTERY = Path(__file__).resolve().parent.parent / "data" / "battery.yaml"

_REQUIRED = ("key", "text")


def load(path: Path | str | None = None) -> list[BatteryPrompt]:
    """Return every prompt in the battery, in file order.

    Raises ValueError on a malformed file so a broken battery fails loudly
    instead of silently probing nothing.
    """
    battery_path = Path(path) if path is not None else DEFAULT_BATTERY
    if not battery_path.exists():
        raise ValueError(f"battery file not found: {battery_path}")

    document = yaml.safe_load(battery_path.read_text(encoding="utf-8"))
    if not isinstance(document, dict) or not isinstance(document.get("prompts"), list):
        raise ValueError(f"{battery_path} must be a mapping with a 'prompts' list")

    prompts: list[BatteryPrompt] = []
    seen: set[str] = set()
    for position, entry in enumerate(document["prompts"]):
        if not isinstance(entry, dict):
            raise ValueError(f"prompt #{position} in {battery_path} is not a mapping")
        missing = [name for name in _REQUIRED if not entry.get(name)]
        if missing:
            raise ValueError(f"prompt #{position} in {battery_path} is missing {missing}")

        key = str(entry["key"]).strip()
        if key in seen:
            raise ValueError(f"duplicate prompt key in {battery_path}: {key}")
        seen.add(key)

        prompts.append(
            BatteryPrompt(
                key=key,
                text=str(entry["text"]),
                category=str(entry.get("category") or "general"),
            )
        )

    if not prompts:
        raise ValueError(f"battery file has no prompts: {battery_path}")
    return prompts


def prompts(path: Path | str | None = None) -> list[BatteryPrompt]:
    """Alias for load()."""
    return load(path)
