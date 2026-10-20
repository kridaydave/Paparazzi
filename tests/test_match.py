# Synthetic fixtures only: these numbers are test fixtures, not real results.

import json

from paparazzi import db


class FakeModule:
    def __init__(self, agreement):
        self.agreement = agreement

    def compare(self, a, b):
        return self.agreement


def _make_conn(tmp_path):
    return db.connect(tmp_path / "test.db")


def _add_run(conn, slug, kind, meta, used_mock=False, ok=True):
    run_id = db.start_run(conn, slug, kind, used_mock=used_mock, meta=meta)
    db.finish_run(conn, run_id, ok=ok, meta=meta)
    return run_id


def test_weights_renormalize_when_family_missing():
    from paparazzi import match

    report = {
        "per_signal": {
            "tokenizer": {"agreement": 1.0},
        },
        "used_mock": False,
    }
    assert match.score(report) == 100.0


def test_full_tokenizer_match_plus_corroborator_sets_bar(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    _add_run(conn, slug, "tokenizer", {"counts": {"a": 1}})
    _add_run(conn, slug, "generation", {"provider": "Acme", "region": "us", "available": True})
    db.upsert_signature(
        conn,
        "known/model",
        {"tokenizer": {"counts": {"a": 1}}, "generation": {"provider": "Acme", "region": "us", "available": True}},
        used_mock=False,
    )

    def fake_import(family):
        if family == "tokenizer":
            return FakeModule(1.0)
        if family == "generation":
            return FakeModule(0.5)
        return None

    monkeypatch.setattr(match, "_import_family", fake_import)
    monkeypatch.setattr(match, "_load_features", lambda: None)

    report = match.evaluate(slug, conn=conn)
    assert report is not None
    assert report["best"] == "known/model"
    assert report["met_bar"] is True
    assert match.met_bar(report) is True
    assert 0 <= match.score(report) <= 100


def test_near_match_does_not_meet_bar(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    _add_run(conn, slug, "tokenizer", {"counts": {"a": 1}})
    _add_run(conn, slug, "generation", {"provider": "Acme", "region": "us", "available": True})
    db.upsert_signature(
        conn,
        "known/model",
        {"tokenizer": {"counts": {"a": 1}}, "generation": {"provider": "Acme", "region": "us", "available": True}},
        used_mock=False,
    )

    def fake_import(family):
        if family == "tokenizer":
            return FakeModule(0.9)
        if family == "generation":
            return FakeModule(0.5)
        return None

    monkeypatch.setattr(match, "_import_family", fake_import)
    monkeypatch.setattr(match, "_load_features", lambda: None)

    report = match.evaluate(slug, conn=conn)
    assert report is not None
    assert report["met_bar"] is False
    assert match.met_bar(report) is False


def test_mock_run_never_meets_bar(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    _add_run(conn, slug, "tokenizer", {"counts": {"a": 1}}, used_mock=True)
    _add_run(conn, slug, "generation", {"provider": "Acme", "region": "us", "available": True}, used_mock=True)
    db.upsert_signature(
        conn,
        "known/model",
        {"tokenizer": {"counts": {"a": 1}}, "generation": {"provider": "Acme", "region": "us", "available": True}},
        used_mock=False,
    )

    def fake_import(family):
        if family == "tokenizer":
            return FakeModule(1.0)
        if family == "generation":
            return FakeModule(1.0)
        return None

    monkeypatch.setattr(match, "_import_family", fake_import)
    monkeypatch.setattr(match, "_load_features", lambda: None)

    report = match.evaluate(slug, conn=conn)
    assert report is not None
    assert report["used_mock"] is True
    assert report["met_bar"] is False
    assert match.met_bar(report) is False


def test_no_signal_families_returns_none_and_no_row(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    db.upsert_signature(conn, "known/model", {"tokenizer": {"a": 1}}, used_mock=False)

    monkeypatch.setattr(match, "_import_family", lambda f: None)
    monkeypatch.setattr(match, "_load_features", lambda: None)

    before = len(db.list_guesses(conn))
    report = match.evaluate(slug, conn=conn)
    assert report is None
    assert len(db.list_guesses(conn)) == before


def test_style_alone_never_meets_bar(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    _add_run(conn, slug, "battery", {"emoji_rate": 0.5})

    class StyleFake:
        def from_responses(self, rows):
            return {"emoji_rate": 0.5}

        def compare(self, a, b):
            return 1.0

    monkeypatch.setattr(match, "_load_features", lambda: StyleFake())
    monkeypatch.setattr(match, "_import_family", lambda f: None)

    db.upsert_signature(conn, "known/model", {"style": {"emoji_rate": 0.5}}, used_mock=False)

    report = match.evaluate(slug, conn=conn)
    assert report is not None
    assert report["met_bar"] is False
    assert match.met_bar(report) is False


def test_score_lands_in_range(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    _add_run(conn, slug, "tokenizer", {"counts": {"a": 1}})
    db.upsert_signature(conn, "known/model", {"tokenizer": {"counts": {"a": 1}}}, used_mock=False)

    monkeypatch.setattr(match, "_import_family", lambda f: FakeModule(0.42) if f == "tokenizer" else None)
    monkeypatch.setattr(match, "_load_features", lambda: None)

    report = match.evaluate(slug, conn=conn)
    assert report is not None
    s = match.score(report)
    assert 0.0 <= s <= 100.0


def test_guess_row_lands_in_db(tmp_path, monkeypatch):
    from paparazzi import match

    conn = _make_conn(tmp_path)
    slug = "anon"
    _add_run(conn, slug, "tokenizer", {"counts": {"a": 1}})
    db.upsert_signature(conn, "known/model", {"tokenizer": {"counts": {"a": 1}}}, used_mock=False)

    monkeypatch.setattr(match, "_import_family", lambda f: FakeModule(1.0) if f == "tokenizer" else None)
    monkeypatch.setattr(match, "_load_features", lambda: None)

    report = match.evaluate(slug, conn=conn)
    assert report is not None

    rows = db.list_guesses(conn)
    assert len(rows) == 1
    row = rows[0]
    assert str(row["slug"]) == slug
    assert str(row["candidate"]) == "known/model"
    assert float(row["score"]) == float(report["score"])
    stored = json.loads(row["per_signal"])
    assert stored == report["per_signal"]