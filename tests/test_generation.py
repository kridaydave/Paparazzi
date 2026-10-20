import pytest

from paparazzi.probes import generation as gen


def test_collect_parses_flat_payload():
    payload = {
        "provider_name": "Acme",
        "data_region": "us",
        "tokens_prompt": 10,
        "tokens_completion": 20,
    }
    out = gen.collect(lambda model: payload, "m")
    assert out["available"] is True
    assert out["provider"] == "Acme"
    assert out["region"] == "us"
    assert out["fields"] == sorted(payload.keys())


def test_collect_parses_nested_payload():
    payload = {"data": {"provider_name": "Acme", "data_region": "europe"}}
    out = gen.collect(lambda model: payload, "m")
    assert out["available"] is True
    assert out["provider"] == "Acme"
    assert out["region"] == "europe"
    assert out["fields"] == ["data"]


def test_collect_unavailable_empty():
    out = gen.collect(lambda model: {}, "m")
    assert out == {"available": False, "provider": None, "region": None, "fields": []}


def test_collect_unavailable_none():
    out = gen.collect(lambda model: None, "m")
    assert out["available"] is False


def test_compare_matrix():
    a = {"available": True, "provider": "Acme", "region": "us"}
    b = {"available": True, "provider": "Acme", "region": "us"}
    assert gen.compare(a, b) == 1.0

    # one field missing
    c = {"available": True, "provider": "Acme", "region": None}
    assert gen.compare(a, c) == 0.5

    # direct disagreement
    d = {"available": True, "provider": "Other", "region": "us"}
    assert gen.compare(a, d) == 0.0

    # unavailable either side
    assert gen.compare({"available": False, "provider": None, "region": None}, a) is None
    assert gen.compare(a, {"available": False, "provider": None, "region": None}) is None


def test_absent_not_disagreement():
    # provider missing on both sides, region agrees -> not 0.0
    a = {"available": True, "provider": None, "region": "us"}
    b = {"available": True, "provider": None, "region": "us"}
    assert gen.compare(a, b) != 0.0


def test_compare_one_field_agrees():
    a = {"available": True, "provider": "X", "region": None}
    b = {"available": True, "provider": "X", "region": None}
    assert gen.compare(a, b) == 0.5