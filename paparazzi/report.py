"""Write the static report JSON consumed by the page."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from paparazzi import db


def _default_path() -> Path:
    return Path(__file__).resolve().parent.parent / "docs" / "data.json"


def write(conn: Any = None, out_path: Any = None) -> dict[str, Any]:
    if conn is None:
        conn = db.connect()
    target = Path(out_path) if out_path is not None else _default_path()
    target.parent.mkdir(parents=True, exist_ok=True)

    counts = db.counts(conn)

    models = []
    for row in db.list_models(conn):
        models.append(
            {
                "slug": str(row["slug"]),
                "status": str(row["status"]),
                "anonymous": bool(row["anonymous"]),
                "first_seen": str(row["first_seen"]),
                "last_seen": str(row["last_seen"]),
            }
        )

    guesses = []
    for row in db.list_guesses(conn):
        try:
            per_signal = json.loads(row["per_signal"]) if row["per_signal"] else {}
        except (json.JSONDecodeError, TypeError):
            per_signal = {}
        guesses.append(
            {
                "slug": str(row["slug"]),
                "candidate": str(row["candidate"]),
                "score": float(row["score"]),
                "met_bar": bool(row["met_bar"]),
                "published": bool(row["published"]),
                "used_mock": bool(db.guess_meta(row).get("used_mock")),
                "per_signal": per_signal,
                "created_at": str(row["created_at"]),
            }
        )

    reveals = []
    for row in db.list_reveals(conn):
        reveals.append(
            {
                "slug": str(row["slug"]),
                "true_name": str(row["true_name"]),
                "source_url": str(row["source_url"]),
                "revealed_at": str(row["revealed_at"]),
                "our_guess": (None if row["our_guess"] is None else str(row["our_guess"])),
                "guessed_by_us": bool(row["guessed_by_us"]),
            }
        )

    runs = []
    for row in db.list_runs(conn):
        runs.append(
            {
                "id": int(row["id"]),
                "slug": str(row["slug"]),
                "kind": str(row["kind"]),
                "ok": bool(row["ok"]),
                "used_mock": bool(row["used_mock"]),
                "error": (None if row["error"] is None else str(row["error"])),
                "started_at": str(row["started_at"]),
            }
        )

    document = {
        "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "counts": counts,
        "models": models,
        "guesses": guesses,
        "reveals": reveals,
        "runs": runs,
    }

    with target.open("w", encoding="utf-8") as handle:
        json.dump(document, handle, indent=2, sort_keys=True)
    return document