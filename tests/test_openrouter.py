import json
import os
from unittest.mock import patch

import pytest
import requests

from paparazzi import openrouter
from paparazzi.types import Completion


class _Resp:
    def __init__(self, status=200, body=None, headers=None, text=""):
        self.status_code = status
        self._body = body if body is not None else {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._body


def test_success_parsing(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")

    body = {
        "choices": [{"message": {"content": "hello world"}}],
        "usage": {"prompt_tokens": 7, "completion_tokens": 3, "completion_tokens_details": {"reasoning_tokens": 1}},
    }
    fake = _Resp(200, body, {"X-Foo": "Bar"})

    with patch("paparazzi.openrouter.requests.post", return_value=fake):
        c = openrouter.complete("m", "prompt", temperature=0.2, max_tokens=5, system="sys", json_mode=True)

    assert c.ok is True
    assert c.status == 200
    assert c.text == "hello world"
    assert c.usage.prompt_tokens == 7
    assert c.usage.completion_tokens == 3
    assert c.usage.reasoning_tokens == 1
    assert c.headers.get("x-foo") == "Bar"
    assert c.latency_ms >= 0
    assert c.raw == body


def test_reasoning_fallback(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")
    body = {"choices": [{"message": {"content": None, "reasoning": "thought"}}], "usage": {}}
    fake = _Resp(200, body)
    with patch("paparazzi.openrouter.requests.post", return_value=fake):
        c = openrouter.complete("m", "p")
    assert c.text == "thought"


def test_empty_choice(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")
    body = {"choices": [], "usage": {}}
    fake = _Resp(200, body)
    with patch("paparazzi.openrouter.requests.post", return_value=fake):
        c = openrouter.complete("m", "p")
    assert c.text == ""
    assert c.ok is True


def test_non_2xx_error_path(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")
    body = {"error": {"message": "bad request"}, "choices": []}
    fake = _Resp(400, body)
    with patch("paparazzi.openrouter.requests.post", return_value=fake):
        c = openrouter.complete("m", "p")
    assert c.ok is False
    assert c.status == 400
    assert c.error == "bad request"
    assert c.raw == body


def test_missing_key_path(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.delenv("PAPARAZZI_OPENROUTER_KEY", raising=False)
    c = openrouter.complete("m", "p")
    assert c.ok is False
    assert c.status == 0
    assert "PAPARAZZI_OPENROUTER_KEY" in (c.error or "")


def test_network_exception_path(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")

    with patch("paparazzi.openrouter.requests.post", side_effect=requests.ConnectionError("boom")):
        c = openrouter.complete("m", "p")
    assert c.ok is False
    assert c.status == 0
    assert "boom" in (c.error or "")


def test_json_decode_error_path(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")

    class BadResp:
        status_code = 500
        headers = {}
        text = "not json"

        def json(self):
            raise ValueError("no json")

    with patch("paparazzi.openrouter.requests.post", return_value=BadResp()):
        c = openrouter.complete("m", "p")
    assert c.ok is False
    assert c.status == 500


def test_mock_replay_used_mock_and_zero_usage(monkeypatch):
    monkeypatch.delenv("PAPARAZZI_OPENROUTER_KEY", raising=False)
    monkeypatch.setenv("PAPARAZZI_MOCK", "1")
    c = openrouter.complete("m", "totally unknown prompt", mock=True)
    assert c.used_mock is True
    assert c.usage.prompt_tokens == 0
    assert c.usage.completion_tokens == 0
    assert c.usage.reasoning_tokens == 0
    assert c.ok is True
    assert "SYNTHETIC FIXTURE" in c.text

    # mock=False override should require key
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    c2 = openrouter.complete("m", "p", mock=False)
    assert c2.ok is False
    assert "PAPARAZZI_OPENROUTER_KEY" in (c2.error or "")


def test_models_and_generation(monkeypatch):
    monkeypatch.setenv("PAPARAZZI_OPENROUTER_KEY", "sk-test")
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)

    def fake_get(url, headers=None, timeout=None):
        if url.endswith("/models"):
            return _Resp(200, {"data": [{"id": "a"}, {"id": "b"}]})
        if "/generation/" in url:
            return _Resp(200, {"provider_name": "Acme"})
        return _Resp(404, {})

    with patch("paparazzi.openrouter.requests.get", side_effect=fake_get):
        assert openrouter.models() == [{"id": "a"}, {"id": "b"}]
        assert openrouter.generation("m") == {"provider_name": "Acme"}

    # failure paths
    with patch("paparazzi.openrouter.requests.get", side_effect=requests.ConnectionError("nope")):
        assert openrouter.models() == []
        assert openrouter.generation("m") == {}


def test_infra_probe_mock(monkeypatch):
    monkeypatch.setenv("PAPARAZZI_MOCK", "1")
    c = openrouter.infra_probe("m", {"temperature": 2.0}, mock=True)
    assert c.used_mock is True
    assert c.status == 400
    assert c.raw.get("paparazzi_mock") is True
    assert "fake" in (c.error or "").lower() or "synthetic" in (c.error or "").lower()
    # non-mock missing key
    monkeypatch.delenv("PAPARAZZI_MOCK", raising=False)
    monkeypatch.delenv("PAPARAZZI_OPENROUTER_KEY", raising=False)
    c2 = openrouter.infra_probe("m", {}, mock=False)
    assert c2.ok is False
    assert "PAPARAZZI_OPENROUTER_KEY" in (c2.error or "")
