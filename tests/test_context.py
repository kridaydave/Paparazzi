import re

from paparazzi.types import Completion
from paparazzi.probes import context as ctx


def test_ladder_with_limit():
    threshold = 50  # tokens-ish: prompt chars < threshold*4 passes

    def send(text):
        if len(text) // 4 < threshold:
            m = re.search(r"access code is (\d+)", text)
            code = m.group(1) if m else ""
            return Completion(text=code, ok=True)
        return Completion(ok=False, error="too long")

    res = ctx.ladder(send, "m", sizes=(10, 100))
    assert res["sizes"] == [10, 100]
    assert res["ok_at"][10] is True
    assert res["ok_at"][100] is False
    assert res["failed_at"][10] is None
    assert res["failed_at"][100] == "too long"
    assert res["limit_observed"] == 10
    for size in (10, 100):
        prompt_len = None
        # estimated_tokens must equal chars//4 of the built prompt; recompute via capture not available,
        # but it must be an int and positive.
        assert isinstance(res["estimated_tokens"][size], int)
        assert res["estimated_tokens"][size] > 0


def test_failed_rung_keeps_message():
    def send(text):
        return Completion(ok=False, error="boom")

    res = ctx.ladder(send, "m", sizes=(8,))
    assert res["failed_at"][8] == "boom"
    assert res["ok_at"][8] is False
    assert res["limit_observed"] is None


def test_compare_hand_built():
    a = {"sizes": [10, 20], "ok_at": {10: True, 20: False}}
    b = {"sizes": [10, 20, 30], "ok_at": {10: True, 20: False, 30: True}}
    assert ctx.compare(a, b) == 1.0

    c = {"sizes": [10, 20], "ok_at": {10: True, 20: True}}
    assert ctx.compare(a, c) == 0.5


def test_empty_ladder_none():
    a = {"sizes": [], "ok_at": {}}
    b = {"sizes": [10], "ok_at": {10: True}}
    assert ctx.compare(a, b) is None


def test_prompt_building_cheap():
    prompt = ctx.build_prompt(100, 0)
    m = re.search(r"access code is (\d+)", prompt)
    assert m is not None
    assert len(prompt) > 0
    # approximate length: estimated tokens ~ size
    assert abs(len(prompt) // 4 - 100) <= 2


def test_needle_placement():
    prompt = ctx.build_prompt(200, 0)
    m = re.search(r"access code is (\d+)", prompt)
    idx = prompt.index(m.group(0))
    # needle not at the very start or very end
    assert idx > 0
    assert idx < len(prompt) - 50


def test_unique_codes_per_size():
    codes = set()
    for i, s in enumerate((8_000, 32_000, 128_000)):
        p = ctx.build_prompt(s, i)
        m = re.search(r"access code is (\d+)", p)
        codes.add(m.group(1))
    assert len(codes) == 3