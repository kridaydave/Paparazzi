import pytest

from paparazzi.probes import tokenizer
from paparazzi.types import Completion, Usage


def _send_with(counts_by_text):
    """Build a send callable returning controlled prompt_tokens.

    counts_by_text maps the full prompt text (BASE or BASE+probe) to a token count.
    """
    def send(text):
        if text not in counts_by_text:
            return Completion(ok=False, error="unknown prompt")
        return Completion(ok=True, usage=Usage(prompt_tokens=counts_by_text[text]))
    return send


def test_differential_arithmetic():
    base = tokenizer.BASE_PROMPT
    probe_text = "hello world"
    # BASE=10, BASE+probe=13 => delta 3
    send = _send_with({base: 10, base + "\n" + probe_text: 13})
    probes = [("p1", probe_text)]
    result = tokenizer.count_differential(send, probes)
    assert result == {"p1": 3}


def test_differential_none_on_failure():
    base = tokenizer.BASE_PROMPT
    send = _send_with({base: 10})  # probe call missing => fail
    probes = [("p1", "boom")]
    result = tokenizer.count_differential(send, probes)
    assert result == {"p1": None}


def test_differential_negative_delta_none():
    base = tokenizer.BASE_PROMPT
    # probe returns fewer tokens than base (nonsensical)
    send = _send_with({base: 10, base + "\n" + "x": 8})
    result = tokenizer.count_differential(send, [("p1", "x")])
    assert result == {"p1": None}


def test_differential_base_failure_empty():
    send = lambda text: Completion(ok=False, error="nope")
    result = tokenizer.count_differential(send, [("p1", "x")])
    assert result == {}


def test_mock_guard_differential():
    base = tokenizer.BASE_PROMPT
    # mock completion: used_mock True
    def send(text):
        return Completion(ok=True, usage=Usage(prompt_tokens=0), raw={"paparazzi_mock": True})
    result = tokenizer.count_differential(send, [("p1", "x")])
    assert result == {}


def test_compare_all_match():
    counts = {"p1": 2, "p2": 5}
    local = {"cand-a": {"p1": 2, "p2": 5}, "cand-b": {"p1": 2, "p2": 6}}
    report = tokenizer.compare(counts, ["cand-a", "cand-b"], local=local)
    assert report["exact_match"] == "cand-a"
    assert report["mock"] is False
    assert report["matched"] == 2
    assert report["total"] == 2
    assert report["per_candidate"]["cand-a"]["matched"] == 2
    assert report["per_candidate"]["cand-b"]["matched"] == 1


def test_compare_near_match_no_exact():
    counts = {"p1": 2, "p2": 5, "p3": 7}
    local = {"cand-a": {"p1": 2, "p2": 5, "p3": 8}}  # one off
    report = tokenizer.compare(counts, ["cand-a"], local=local)
    assert report["exact_match"] is None
    assert report["matched"] == 2
    assert report["total"] == 3
    assert report["matched"] < report["total"]


def test_compare_mock_guard():
    # empty counts -> mock
    report = tokenizer.compare({}, ["cand-a"], local={"cand-a": {"p1": 1}})
    assert report["mock"] is True
    assert report["exact_match"] is None

    # all-zero counts -> mock
    report2 = tokenizer.compare({"p1": 0}, ["cand-a"], local={"cand-a": {"p1": 0}})
    assert report2["mock"] is True
    assert report2["exact_match"] is None


def test_compare_stored_dicts():
    a = {"p1": 2, "p2": 5, "p3": None}
    b = {"p1": 2, "p2": 9, "p3": 7}
    # both measured on p1,p2 (p3 skipped in a? a p3 None -> skip; p1,p2 both measured)
    # agree on p1 only => 1/2
    val = tokenizer.compare(a, b)
    assert val == pytest.approx(0.5)

    assert tokenizer.compare({}, b) is None
    assert tokenizer.compare(a, {}) is None
    assert tokenizer.compare({"mock": True}, b) is None


def test_probe_strings_unique_and_nonempty():
    ps = tokenizer.probe_strings()
    ids = [p[0] for p in ps]
    assert len(ids) == len(set(ids))
    assert all(isinstance(p[1], str) and p[1] != "" for p in ps)
    assert len(ps) >= 90


def test_compare_stored_none_on_no_common():
    a = {"p1": None}
    b = {"p1": 2}
    assert tokenizer.compare(a, b) is None
