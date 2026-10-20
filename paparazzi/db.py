"""SQLite storage for paparazzi.

One file, one schema. Every other module goes through these helpers instead of
writing its own DDL, so the report page and the matcher always see the same
shape. Timestamps are UTC ISO 8601 with a Z suffix.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_DB = DATA_DIR / "paparazzi.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS models (
    slug        TEXT PRIMARY KEY,
    provider    TEXT,
    name        TEXT,
    anonymous   INTEGER NOT NULL DEFAULT 0,
    status      TEXT NOT NULL DEFAULT 'active',
    first_seen  TEXT NOT NULL,
    last_seen   TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS probe_runs (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL,
    kind        TEXT NOT NULL,
    used_mock   INTEGER NOT NULL DEFAULT 0,
    ok          INTEGER NOT NULL DEFAULT 1,
    error       TEXT,
    meta        TEXT NOT NULL DEFAULT '{}',
    started_at  TEXT NOT NULL,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS responses (
    id                INTEGER PRIMARY KEY,
    run_id            INTEGER NOT NULL REFERENCES probe_runs(id),
    prompt_key        TEXT NOT NULL,
    idx               INTEGER NOT NULL DEFAULT 0,
    text              TEXT,
    prompt_tokens     INTEGER,
    completion_tokens INTEGER,
    reasoning_tokens  INTEGER,
    latency_ms        INTEGER,
    ok                INTEGER NOT NULL DEFAULT 1,
    error             TEXT,
    meta              TEXT NOT NULL DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS signatures (
    slug       TEXT PRIMARY KEY,
    signals    TEXT NOT NULL,
    used_mock  INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS guesses (
    id          INTEGER PRIMARY KEY,
    slug        TEXT NOT NULL,
    candidate   TEXT NOT NULL,
    score       REAL NOT NULL,
    per_signal  TEXT NOT NULL,
    met_bar     INTEGER NOT NULL DEFAULT 0,
    published   INTEGER NOT NULL DEFAULT 0,
    approved_by TEXT,
    meta        TEXT NOT NULL DEFAULT '{}',
    created_at  TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS reveals (
    slug          TEXT PRIMARY KEY,
    true_name     TEXT NOT NULL,
    source_url    TEXT NOT NULL,
    revealed_at   TEXT NOT NULL,
    our_guess     TEXT,
    guessed_by_us INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_probe_runs_slug ON probe_runs(slug);
CREATE INDEX IF NOT EXISTS idx_responses_run ON responses(run_id);
CREATE INDEX IF NOT EXISTS idx_guesses_slug ON guesses(slug);
"""


def now_iso() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


def _dump(value: Any) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"))


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open the database, create it if needed, and make sure the schema exists.

    When the caller does not name a path, PAPARAZZI_DB decides, so every
    module ends up in the same database.
    """
    db_path = Path(path) if path is not None else _configured_path()
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    init_schema(conn)
    return conn


def _configured_path() -> Path:
    # Imported inside the function because config imports this module.
    try:
        from paparazzi import config

        return config.db_path()
    except Exception:
        return DEFAULT_DB


def init_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(SCHEMA)
    _migrate(conn)
    conn.commit()


def _migrate(conn: sqlite3.Connection) -> None:
    """Bring an existing database up to the current schema.

    Additive only. Databases written before guesses carried metadata get the
    column backfilled to {}, so a guess never loses its fixture flag.
    """
    guess_columns = {str(row["name"]) for row in conn.execute("PRAGMA table_info(guesses)")}
    if "meta" not in guess_columns:
        conn.execute("ALTER TABLE guesses ADD COLUMN meta TEXT NOT NULL DEFAULT '{}'")


def set_state(conn: sqlite3.Connection, key: str, value: Any) -> None:
    conn.execute(
        "INSERT INTO state(key, value) VALUES(?, ?) "
        "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
        (key, str(value)),
    )
    conn.commit()


def get_state(conn: sqlite3.Connection, key: str) -> str | None:
    row = conn.execute("SELECT value FROM state WHERE key = ?", (key,)).fetchone()
    return None if row is None else str(row["value"])


def upsert_model(
    conn: sqlite3.Connection,
    slug: str,
    *,
    provider: str | None = None,
    name: str | None = None,
    anonymous: bool | None = None,
    status: str = "active",
    at: str | None = None,
) -> None:
    """Insert or refresh a slug. Existing rows keep their first_seen date."""
    stamp = at or now_iso()
    conn.execute(
        """
        INSERT INTO models(slug, provider, name, anonymous, status, first_seen, last_seen)
        VALUES(?, ?, ?, COALESCE(?, 0), ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            provider   = COALESCE(excluded.provider, models.provider),
            name       = COALESCE(excluded.name, models.name),
            anonymous  = COALESCE(excluded.anonymous, models.anonymous),
            status     = excluded.status,
            last_seen  = excluded.last_seen
        """,
        (
            slug,
            provider,
            name,
            None if anonymous is None else int(anonymous),
            status,
            stamp,
            stamp,
        ),
    )
    conn.commit()


def mark_model_gone(conn: sqlite3.Connection, slug: str, at: str | None = None) -> None:
    conn.execute(
        "UPDATE models SET status = 'gone', last_seen = ? WHERE slug = ?",
        (at or now_iso(), slug),
    )
    conn.commit()


def list_models(conn: sqlite3.Connection, *, status: str | None = "active") -> list[sqlite3.Row]:
    if status is None:
        return list(conn.execute("SELECT * FROM models ORDER BY slug"))
    return list(conn.execute("SELECT * FROM models WHERE status = ? ORDER BY slug", (status,)))


def start_run(
    conn: sqlite3.Connection,
    slug: str,
    kind: str,
    *,
    used_mock: bool = False,
    meta: dict[str, Any] | None = None,
) -> int:
    cur = conn.execute(
        "INSERT INTO probe_runs(slug, kind, used_mock, meta, started_at) VALUES(?, ?, ?, ?, ?)",
        (slug, kind, int(used_mock), _dump(meta or {}), now_iso()),
    )
    conn.commit()
    return int(cur.lastrowid)


def finish_run(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    ok: bool,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> None:
    if meta is None:
        conn.execute(
            "UPDATE probe_runs SET ok = ?, error = ?, finished_at = ? WHERE id = ?",
            (int(ok), error, now_iso(), run_id),
        )
    else:
        conn.execute(
            "UPDATE probe_runs SET ok = ?, error = ?, meta = ?, finished_at = ? WHERE id = ?",
            (int(ok), error, _dump(meta), now_iso(), run_id),
        )
    conn.commit()


def add_response(
    conn: sqlite3.Connection,
    run_id: int,
    *,
    prompt_key: str,
    idx: int = 0,
    text: str | None = None,
    prompt_tokens: int | None = None,
    completion_tokens: int | None = None,
    reasoning_tokens: int | None = None,
    latency_ms: int | None = None,
    ok: bool = True,
    error: str | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO responses(
            run_id, prompt_key, idx, text, prompt_tokens, completion_tokens,
            reasoning_tokens, latency_ms, ok, error, meta
        ) VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id,
            prompt_key,
            idx,
            text,
            prompt_tokens,
            completion_tokens,
            reasoning_tokens,
            latency_ms,
            int(ok),
            error,
            _dump(meta or {}),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def responses_for(conn: sqlite3.Connection, run_id: int) -> list[sqlite3.Row]:
    return list(
        conn.execute(
            "SELECT * FROM responses WHERE run_id = ? ORDER BY idx, id", (run_id,)
        )
    )


def runs_for(conn: sqlite3.Connection, slug: str, kind: str | None = None) -> list[sqlite3.Row]:
    if kind is None:
        return list(
            conn.execute(
                "SELECT * FROM probe_runs WHERE slug = ? ORDER BY id", (slug,)
            )
        )
    return list(
        conn.execute(
            "SELECT * FROM probe_runs WHERE slug = ? AND kind = ? ORDER BY id",
            (slug, kind),
        )
    )


def latest_run(conn: sqlite3.Connection, slug: str, kind: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM probe_runs WHERE slug = ? AND kind = ? ORDER BY id DESC LIMIT 1",
        (slug, kind),
    ).fetchone()


def upsert_signature(
    conn: sqlite3.Connection,
    slug: str,
    signals: dict[str, Any],
    *,
    used_mock: bool = False,
) -> None:
    conn.execute(
        """
        INSERT INTO signatures(slug, signals, used_mock, created_at)
        VALUES(?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            signals = excluded.signals,
            used_mock = excluded.used_mock,
            created_at = excluded.created_at
        """,
        (slug, _dump(signals), int(used_mock), now_iso()),
    )
    conn.commit()


def get_signature(conn: sqlite3.Connection, slug: str) -> dict[str, Any] | None:
    row = conn.execute("SELECT * FROM signatures WHERE slug = ?", (slug,)).fetchone()
    if row is None:
        return None
    return {
        "slug": str(row["slug"]),
        "signals": json.loads(row["signals"]),
        "used_mock": bool(row["used_mock"]),
        "created_at": str(row["created_at"]),
    }


def list_signatures(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [
        {
            "slug": str(row["slug"]),
            "signals": json.loads(row["signals"]),
            "used_mock": bool(row["used_mock"]),
            "created_at": str(row["created_at"]),
        }
        for row in conn.execute("SELECT * FROM signatures ORDER BY slug")
    ]


def add_guess(
    conn: sqlite3.Connection,
    slug: str,
    candidate: str,
    *,
    score: float,
    per_signal: dict[str, Any],
    met_bar: bool = False,
    published: bool = False,
    approved_by: str | None = None,
    meta: dict[str, Any] | None = None,
) -> int:
    cur = conn.execute(
        """
        INSERT INTO guesses(slug, candidate, score, per_signal, met_bar, published, approved_by, meta, created_at)
        VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            slug,
            candidate,
            float(score),
            _dump(per_signal),
            int(met_bar),
            int(published),
            approved_by,
            _dump(meta or {}),
            now_iso(),
        ),
    )
    conn.commit()
    return int(cur.lastrowid)


def guess_meta(row: sqlite3.Row) -> dict[str, Any]:
    """Read a guess row's metadata. An unreadable blob stays empty, never guessed at."""
    raw = row["meta"] if "meta" in row.keys() else "{}"
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return {}
    return parsed if isinstance(parsed, dict) else {}


def publish_guess(conn: sqlite3.Connection, guess_id: int, *, approved_by: str) -> None:
    conn.execute(
        "UPDATE guesses SET published = 1, approved_by = ? WHERE id = ?",
        (approved_by, guess_id),
    )
    conn.commit()


def latest_guess(conn: sqlite3.Connection, slug: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM guesses WHERE slug = ? ORDER BY id DESC LIMIT 1", (slug,)
    ).fetchone()


def list_guesses(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM guesses ORDER BY id"))


def set_reveal(
    conn: sqlite3.Connection,
    slug: str,
    true_name: str,
    source_url: str,
    *,
    at: str | None = None,
) -> bool:
    """Store a reveal. Returns True when our own guess had named the model."""
    guess = latest_guess(conn, slug)
    our_guess = None if guess is None else str(guess["candidate"])
    hit = bool(our_guess and _same_name(our_guess, true_name))
    conn.execute(
        """
        INSERT INTO reveals(slug, true_name, source_url, revealed_at, our_guess, guessed_by_us)
        VALUES(?, ?, ?, ?, ?, ?)
        ON CONFLICT(slug) DO UPDATE SET
            true_name = excluded.true_name,
            source_url = excluded.source_url,
            revealed_at = excluded.revealed_at,
            our_guess = excluded.our_guess,
            guessed_by_us = excluded.guessed_by_us
        """,
        (slug, true_name, source_url, at or now_iso(), our_guess, int(hit)),
    )
    conn.commit()
    return hit


def _same_name(a: str, b: str) -> bool:
    """Compare 'anthropic/claude-haiku' to 'Claude Haiku' without case or vendor noise."""
    def norm(value: str) -> set[str]:
        cleaned = value.lower().replace("_", "-")
        parts = [p for p in cleaned.split("/") if p]
        pieces: set[str] = set()
        for part in parts:
            pieces.update(t for t in part.replace("-", " ").split() if t)
        return pieces

    guess_tokens, true_tokens = norm(a), norm(b)
    # The guess usually carries a vendor prefix the true name does not, so the
    # true name has to sit inside the guess rather than match it exactly.
    return bool(true_tokens) and true_tokens <= guess_tokens


def list_reveals(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return list(conn.execute("SELECT * FROM reveals ORDER BY revealed_at"))


def list_runs(conn: sqlite3.Connection, *, limit: int | None = None) -> list[sqlite3.Row]:
    if limit is None:
        return list(conn.execute("SELECT * FROM probe_runs ORDER BY id"))
    return list(conn.execute("SELECT * FROM probe_runs ORDER BY id DESC LIMIT ?", (limit,)))


def counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Row counts for the report page. Every field is a real count."""
    def one(sql: str) -> int:
        return int(conn.execute(sql).fetchone()[0])

    return {
        "models": one("SELECT COUNT(*) FROM models WHERE status = 'active'"),
        "runs": one("SELECT COUNT(*) FROM probe_runs"),
        "failed_runs": one("SELECT COUNT(*) FROM probe_runs WHERE ok = 0"),
        "mock_runs": one("SELECT COUNT(*) FROM probe_runs WHERE used_mock = 1"),
        "guesses": one("SELECT COUNT(*) FROM guesses"),
        "published": one("SELECT COUNT(*) FROM guesses WHERE published = 1"),
        "reveals": one("SELECT COUNT(*) FROM reveals"),
        "hits": one("SELECT COUNT(*) FROM reveals WHERE guessed_by_us = 1"),
    }
