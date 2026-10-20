import sys

import pytest

from paparazzi import cli, db


def test_help_exits_zero():
    assert cli.main(["--help"]) == 0


def test_unknown_command_exits_nonzero():
    assert cli.main(["definitely-not-a-command"]) != 0


def test_help_subcommand_exits_zero():
    assert cli.main(["reveal", "--help"]) == 0


def test_is_anonymous():
    assert cli.is_anonymous("stealth/foo") is True
    assert cli.is_anonymous("openai/gpt-4o-anon") is True
    assert cli.is_anonymous("foo/ANON-bar") is False
    assert cli.is_anonymous("openai/gpt-4o") is False
    assert cli.is_anonymous("anthropic/claude") is False


def test_reveal_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "reveal.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))

    conn = db.connect(db_path)
    db.add_guess(
        conn,
        "stealth/alpha",
        "anthropic/claude-haiku",
        score=91.0,
        per_signal={},
        met_bar=True,
    )
    conn.close()

    rc = cli.main(["reveal", "stealth/alpha", "Claude Haiku", "https://example.com/source"])
    assert rc == 0

    conn = db.connect(db_path)
    rows = db.list_reveals(conn)
    assert len(rows) == 1
    assert rows[0]["slug"] == "stealth/alpha"
    assert rows[0]["true_name"] == "Claude Haiku"
    assert rows[0]["guessed_by_us"] == 1
    conn.close()


def test_reveal_miss_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "reveal2.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))

    rc = cli.main(["reveal", "stealth/beta", "Gemini Flash", "https://example.com/src"])
    assert rc == 0

    conn = db.connect(db_path)
    rows = db.list_reveals(conn)
    assert len(rows) == 1
    assert rows[0]["guessed_by_us"] == 0
    conn.close()


def test_report_missing_module_exits_one(monkeypatch, capsys):
    import paparazzi

    monkeypatch.setitem(sys.modules, "paparazzi.report", None)
    monkeypatch.delattr(paparazzi, "report", raising=False)
    rc = cli.main(["report"])
    assert rc == 1
    out = capsys.readouterr()
    assert "not wired up" in (out.out + out.err)


def test_know_missing_module_exits_one(monkeypatch, capsys):
    import paparazzi

    monkeypatch.setitem(sys.modules, "paparazzi.probe", None)
    monkeypatch.delattr(paparazzi, "probe", raising=False)
    rc = cli.main(["know", "some/slug", "--mock"])
    assert rc == 1
    out = capsys.readouterr()
    assert "not wired up" in (out.out + out.err)


def test_match_missing_module_exits_one(monkeypatch, capsys):
    import paparazzi

    monkeypatch.setitem(sys.modules, "paparazzi.match", None)
    monkeypatch.delattr(paparazzi, "match", raising=False)
    rc = cli.main(["match", "some/slug"])
    assert rc == 1
    out = capsys.readouterr()
    assert "not wired up" in (out.out + out.err)


def test_watch_empty_mock_roster_changes_nothing(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "watch.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))

    conn = db.connect(db_path)
    db.upsert_model(conn, "anthropic/claude-haiku-5.5")
    conn.close()

    rc = cli.main(["watch", "--mock"])
    assert rc == 0
    assert "nothing to diff" in capsys.readouterr().out

    conn = db.connect(db_path)
    row = conn.execute("SELECT status FROM models").fetchone()
    conn.close()
    assert row["status"] == "active", "an empty mock roster must not rotate anything off"


def test_watch_failed_roster_fetch_marks_nothing_gone(tmp_path, monkeypatch, capsys):
    """No key means the fetch failed. A failed fetch must not say models left."""
    db_path = tmp_path / "watch-fail.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))
    monkeypatch.setenv("PAPARAZZI_MOCK", "0")
    monkeypatch.delenv("PAPARAZZI_OPENROUTER_KEY", raising=False)

    conn = db.connect(db_path)
    db.upsert_model(conn, "anthropic/claude-haiku-5.5")
    conn.close()

    rc = cli.main(["watch"])
    assert rc == 1
    assert "nothing was marked gone" in capsys.readouterr().out

    conn = db.connect(db_path)
    row = conn.execute("SELECT status FROM models").fetchone()
    conn.close()
    assert row["status"] == "active"