"""End-to-end glue test: the six workers' pieces have to fit together.

Everything here runs in fixture replay (`--mock`), so no network and no API
key. The point is the wiring: know stores a signature, match reads it back,
report writes counts that match the database.
"""

import json
from pathlib import Path

from paparazzi import cli, db


def _run(args, monkeypatch, db_path):
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))
    return cli.main(args)


def test_know_match_report_roundtrip(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "glue.db"
    data_path = tmp_path / "data.json"

    rc = _run(["know", "fixture/known-model", "--mock"], monkeypatch, db_path)
    assert rc == 0
    assert "signature stored" in capsys.readouterr().out

    conn = db.connect(db_path)
    signature = db.get_signature(conn, "fixture/known-model")
    assert signature is not None, "know must store a signature"
    assert signature["used_mock"] is True, "a fixture-built signature must say so"
    assert "style" in signature["signals"], "the battery has to produce a style vector"
    conn.close()

    rc = _run(["probe", "stealth/unknown-thing", "--mock"], monkeypatch, db_path)
    assert rc == 0

    rc = _run(["match", "stealth/unknown-thing", "--mock"], monkeypatch, db_path)
    assert rc == 0
    printed = capsys.readouterr().out
    assert "guess:" in printed
    assert "low confidence, not published as guess" in printed

    conn = db.connect(db_path)
    guesses = db.list_guesses(conn)
    assert len(guesses) == 1, "match must store exactly one guess row"
    guess = guesses[0]
    assert guess["slug"] == "stealth/unknown-thing"
    assert guess["met_bar"] == 0, "a fixture replay can never meet the publish bar"
    assert guess["published"] == 0
    assert db.guess_meta(guess)["used_mock"] is True
    conn.close()

    rc = _run(["report"], monkeypatch, db_path)
    assert rc == 0
    repo_data = Path(__file__).resolve().parent.parent / "docs" / "data.json"
    document = json.loads(repo_data.read_text(encoding="utf-8"))
    assert document["counts"]["guesses"] == 1
    assert document["counts"]["mock_runs"] >= 4, "every mock run must be counted as mock"
    assert document["guesses"][0]["used_mock"] is True
    assert document["guesses"][0]["met_bar"] is False
    assert not data_path.exists(), "report must only write docs/data.json"


def test_failed_probe_reports_the_recorded_error(tmp_path, monkeypatch, capsys):
    """A failure has to print something, not just exit 1 into silence."""
    db_path = tmp_path / "fail.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))
    monkeypatch.setenv("PAPARAZZI_MOCK", "0")
    monkeypatch.delenv("PAPARAZZI_OPENROUTER_KEY", raising=False)

    rc = cli.main(["know", "fixture/no-key"])
    assert rc == 1
    out = capsys.readouterr()
    printed = out.out + out.err
    assert "failed" in printed
    assert "PAPARAZZI_OPENROUTER_KEY" in printed

    conn = db.connect(db_path)
    rows = list(conn.execute("SELECT * FROM probe_runs WHERE ok = 0"))
    assert rows, "a failed call must be stored as a failed run"
    conn.close()


def test_reveal_after_guess_marks_the_hit(tmp_path, monkeypatch, capsys):
    db_path = tmp_path / "reveal-glue.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))

    assert cli.main(["know", "fixture/known-model", "--mock"]) == 0
    capsys.readouterr()
    assert cli.main(["probe", "stealth/thing", "--mock"]) == 0
    assert cli.main(["match", "stealth/thing", "--mock"]) == 0
    capsys.readouterr()

    conn = db.connect(db_path)
    guess = db.latest_guess(conn, "stealth/thing")
    candidate = str(guess["candidate"])
    conn.close()

    rc = cli.main(["reveal", "stealth/thing", candidate, "https://example.com/first-party"])
    assert rc == 0

    conn = db.connect(db_path)
    reveals = db.list_reveals(conn)
    assert len(reveals) == 1
    assert reveals[0]["guessed_by_us"] == 1
    conn.close()
