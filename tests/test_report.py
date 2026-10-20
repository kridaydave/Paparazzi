# Synthetic fixtures only.

import json
from pathlib import Path

from paparazzi import db


def test_write_produces_valid_json_at_temp_path(tmp_path):
    from paparazzi import report

    conn = db.connect(tmp_path / "t.db")
    out = tmp_path / "out.json"
    result = report.write(conn=conn, out_path=out)
    assert out.exists()
    loaded = json.loads(out.read_text())
    assert loaded == result
    # sorted keys
    raw = out.read_text()
    assert raw == json.dumps(result, indent=2, sort_keys=True)


def test_counts_match_db(tmp_path):
    from paparazzi import report

    conn = db.connect(tmp_path / "t.db")
    # add some synthetic rows
    db.upsert_model(conn, "m1", status="active", anonymous=False)
    db.start_run(conn, "m1", "battery", used_mock=True)
    db.set_reveal(conn, "m1", "Real Name", "https://example.com")
    out = tmp_path / "out.json"
    doc = report.write(conn=conn, out_path=out)
    actual = db.counts(conn)
    assert doc["counts"] == actual
    # query independently
    import sqlite3
    c = conn
    assert c.execute("SELECT COUNT(*) FROM models WHERE status='active'").fetchone()[0] == doc["counts"]["models"]
    assert c.execute("SELECT COUNT(*) FROM probe_runs").fetchone()[0] == doc["counts"]["runs"]


def test_sorted_keys_stable_across_runs(tmp_path):
    from paparazzi import report

    conn = db.connect(tmp_path / "t.db")
    out1 = tmp_path / "a.json"
    out2 = tmp_path / "b.json"
    report.write(conn=conn, out_path=out1)
    report.write(conn=conn, out_path=out2)
    assert out1.read_text() == out2.read_text()