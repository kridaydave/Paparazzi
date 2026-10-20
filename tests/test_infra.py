import json

import pytest

from paparazzi import db, probe
from paparazzi.probes import infra
from paparazzi.types import Completion


def test_collect_injected():
    def send_payload(payload):
        return Completion(
            status=400,
            raw={"error": {"code": "INVALID", "type": "invalid_request_error", "message": "bad"}, "paparazzi_mock": False},
            ok=False,
            error="bad",
        )

    out = infra.collect(send_payload, "m")
    assert "out_of_range_temperature" in out
    assert out["out_of_range_temperature"]["status"] == 400
    assert out["out_of_range_temperature"]["error_code"] == "INVALID"
    assert out["out_of_range_temperature"]["error_type"] == "invalid_request_error"
    assert out["mock"] is False
    assert out["used_mock"] is False
    assert isinstance(out.get("probes"), list)


def test_collect_handles_exception():
    def send_payload(payload):
        raise RuntimeError("boom")

    out = infra.collect(send_payload, "m")
    assert out["out_of_range_temperature"]["error_message"] == "boom"


def test_compare_none_empty():
    assert infra.compare({}, {"a": {"status": 400, "error_code": "x", "error_type": "t"}}) is None
    assert infra.compare({"a": {"status": 400, "error_code": "x", "error_type": "t"}}, {}) is None


def test_compare_none_mock():
    a = {"mock": True, "p1": {"status": 400, "error_code": "x", "error_type": "t"}}
    b = {"p1": {"status": 400, "error_code": "x", "error_type": "t"}}
    assert infra.compare(a, b) is None
    # raw mock flag
    a2 = {"p1": {"status": 400, "error_code": "x", "error_type": "t", "paparazzi_mock": True}}
    assert infra.compare(a2, b) is None


def test_compare_agreement_math():
    a = {
        "p1": {"status": 400, "error_code": "X", "error_type": "T"},
        "p2": {"status": 400, "error_code": "Y", "error_type": "T"},
    }
    b = {
        "p1": {"status": 400, "error_code": "X", "error_type": "T"},
        "p2": {"status": 400, "error_code": "Z", "error_type": "T"},
    }
    assert infra.compare(a, b) == pytest.approx(0.5)

    # full agreement
    assert infra.compare(a, a) == pytest.approx(1.0)

    # no common probes
    c = {"q": {"status": 400, "error_code": "X", "error_type": "T"}}
    assert infra.compare(a, c) is None


def test_run_infra_roundtrip(tmp_path, monkeypatch):
    db_path = tmp_path / "t.db"
    monkeypatch.setenv("PAPARAZZI_DB", str(db_path))
    conn = db.connect(db_path)

    def send_payload(payload):
        return Completion(
            status=400,
            raw={"error": {"code": "INVALID", "type": "invalid_request_error", "message": "bad"}},
            ok=False,
            error="bad",
        )

    run_id = probe.run_infra("m", send_payload=send_payload, conn=conn)
    assert isinstance(run_id, int)

    run = db.latest_run(conn, "m", "infra")
    assert run is not None
    assert run["ok"] == 1
    meta = json.loads(run["meta"])
    assert "out_of_range_temperature" in meta
    assert meta.get("mock") is False
    conn.close()
