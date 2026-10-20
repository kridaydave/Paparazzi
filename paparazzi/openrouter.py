"""The only module that talks to the network.

Every function returns a :class:`Completion` instead of raising. Missing keys,
network errors and malformed bodies all become ``ok=False`` results with a plain
error string.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from typing import Any

import requests

from paparazzi.types import Completion, Usage

BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_TIMEOUT = 60

FIXTURE_PATH = Path(__file__).resolve().parents[1] / "data" / "fixtures" / "canned.json"


def _key() -> str | None:
    value = os.environ.get("PAPARAZZI_OPENROUTER_KEY")
    return value if value else None


def _mock_requested(mock: bool | None) -> bool:
    if mock is not None:
        return bool(mock)
    try:
        from paparazzi import config

        return bool(config.mock())
    except Exception:
        return os.environ.get("PAPARAZZI_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def _load_fixture() -> dict[str, Any]:
    try:
        return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _pick_canned(data: Any, prompt: str, prompt_key: str | None) -> str:
    if not isinstance(data, dict):
        data = {}
    value: Any = None
    if prompt in data:
        value = data[prompt]
    elif prompt_key is not None and prompt_key in data:
        value = data[prompt_key]
    else:
        value = data.get("__default__")

    if isinstance(value, list):
        if not value:
            value = data.get("__default__")
        if isinstance(value, list):
            if not value:
                return ""
            key = prompt_key if prompt_key is not None else prompt
            idx = int(hashlib.sha256(str(key).encode("utf-8")).hexdigest(), 16) % len(value)
            value = value[idx]
        elif value is None:
            return ""

    if isinstance(value, dict):
        for field in ("text", "content", "completion", "response", "message"):
            if isinstance(value.get(field), str):
                value = value[field]
                break
        else:
            value = str(value)

    if value is None:
        return ""
    if not isinstance(value, str):
        return str(value)
    return value


def _messages(prompt: str, system: str | None) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})
    return messages


def complete(
    model: str,
    prompt: str,
    *,
    temperature: float = 0.0,
    max_tokens: int | None = None,
    system: str | None = None,
    json_mode: bool = False,
    mock: bool | None = None,
    prompt_key: str | None = None,
) -> Completion:
    """One chat completion. Never raises."""
    mock_flag = _mock_requested(mock)

    if mock_flag:
        text = _pick_canned(_load_fixture(), prompt, prompt_key)
        return Completion(
            text=text,
            usage=Usage(),
            latency_ms=0,
            status=200,
            headers={},
            raw={"paparazzi_mock": True},
            ok=True,
            error=None,
        )

    key = _key()
    if not key:
        return Completion(
            ok=False,
            status=0,
            error="PAPARAZZI_OPENROUTER_KEY is not set",
        )

    body: dict[str, Any] = {
        "model": model,
        "messages": _messages(prompt, system),
        "temperature": temperature,
    }
    if max_tokens is not None:
        body["max_tokens"] = max_tokens
    if json_mode:
        body["response_format"] = {"type": "json_object"}

    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
    }

    start = time.perf_counter()
    try:
        response = requests.post(
            f"{BASE_URL}/chat/completions",
            headers=headers,
            json=body,
            timeout=DEFAULT_TIMEOUT,
        )
    except requests.RequestException as exc:
        elapsed = int(round((time.perf_counter() - start) * 1000))
        return Completion(
            ok=False,
            status=0,
            latency_ms=elapsed,
            error=f"request failed: {exc}",
        )
    except Exception as exc:  # pragma: no cover - defensive
        elapsed = int(round((time.perf_counter() - start) * 1000))
        return Completion(
            ok=False,
            status=0,
            latency_ms=elapsed,
            error=f"request failed: {exc}",
        )

    elapsed = int(round((time.perf_counter() - start) * 1000))
    try:
        parsed = response.json()
    except (ValueError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    resp_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}

    text = ""
    choices = parsed.get("choices")
    if isinstance(choices, list) and choices:
        first = choices[0]
        if isinstance(first, dict):
            message = first.get("message")
            if isinstance(message, dict):
                content = message.get("content")
                if not content:
                    content = message.get("reasoning")
                if isinstance(content, str):
                    text = content
                elif content is not None:
                    text = str(content)

    usage = Usage.from_response(parsed.get("usage"))

    if response.status_code < 200 or response.status_code >= 300:
        error_msg = None
        err = parsed.get("error")
        if isinstance(err, dict):
            error_msg = err.get("message")
        if not isinstance(error_msg, str) or not error_msg:
            error_msg = response.text.strip() or f"HTTP {response.status_code}"
        return Completion(
            text=text,
            usage=usage,
            latency_ms=elapsed,
            status=response.status_code,
            headers=resp_headers,
            raw=parsed,
            ok=False,
            error=error_msg,
        )

    return Completion(
        text=text,
        usage=usage,
        latency_ms=elapsed,
        status=response.status_code,
        headers=resp_headers,
        raw=parsed,
        ok=True,
        error=None,
    )


def models(mock: bool | None = None) -> list[dict]:
    """Roster from GET /models. Returns [] on failure."""
    if _mock_requested(mock):
        return []

    key = _key()
    if not key:
        return []

    try:
        response = requests.get(
            f"{BASE_URL}/models",
            headers={"Authorization": f"Bearer {key}"},
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code < 200 or response.status_code >= 300:
            return []
        parsed = response.json()
    except Exception:
        return []

    if isinstance(parsed, dict):
        data = parsed.get("data")
        if isinstance(data, list):
            return [x for x in data if isinstance(x, dict)]
    if isinstance(parsed, list):
        return [x for x in parsed if isinstance(x, dict)]
    return []


def generation(model: str, mock: bool | None = None) -> dict:
    """GET /generation/{model}. Returns {} when unavailable."""
    if _mock_requested(mock):
        return {}

    key = _key()
    if not key:
        return {}

    try:
        response = requests.get(
            f"{BASE_URL}/generation/{model}",
            headers={"Authorization": f"Bearer {key}"},
            timeout=DEFAULT_TIMEOUT,
        )
        if response.status_code < 200 or response.status_code >= 300:
            return {}
        parsed = response.json()
    except Exception:
        return {}

    return parsed if isinstance(parsed, dict) else {}


def infra_probe(model: str, payload: Any, *, mock: bool | None = None) -> Completion:
    """POST a deliberately malformed chat completion. Never raises."""
    mock_flag = _mock_requested(mock)
    if mock_flag:
        msg = "synthetic infra probe failure (mock)"
        return Completion(
            text="",
            usage=Usage(),
            latency_ms=0,
            status=400,
            headers={},
            raw={"paparazzi_mock": True, "error": {"message": msg, "type": "invalid_request_error", "code": 400}},
            ok=False,
            error=msg,
        )

    key = _key()
    if not key:
        return Completion(ok=False, status=0, error="PAPARAZZI_OPENROUTER_KEY is not set")

    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}
    if isinstance(payload, dict):
        body: Any = dict(payload)
        if isinstance(body, dict) and "model" not in body:
            body["model"] = model
    else:
        body = payload

    start = time.perf_counter()
    try:
        if isinstance(body, (str, bytes)):
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                data=body if isinstance(body, (str, bytes)) else str(body),
                timeout=DEFAULT_TIMEOUT,
            )
        else:
            response = requests.post(
                f"{BASE_URL}/chat/completions",
                headers=headers,
                json=body,
                timeout=DEFAULT_TIMEOUT,
            )
    except requests.RequestException as exc:
        elapsed = int(round((time.perf_counter() - start) * 1000))
        return Completion(ok=False, status=0, latency_ms=elapsed, error=f"request failed: {exc}")
    except Exception as exc:  # pragma: no cover - defensive
        elapsed = int(round((time.perf_counter() - start) * 1000))
        return Completion(ok=False, status=0, latency_ms=elapsed, error=f"request failed: {exc}")

    elapsed = int(round((time.perf_counter() - start) * 1000))
    try:
        parsed = response.json()
    except (ValueError, json.JSONDecodeError):
        parsed = {}
    if not isinstance(parsed, dict):
        parsed = {}

    resp_headers = {str(k).lower(): str(v) for k, v in response.headers.items()}

    error_msg = None
    err = parsed.get("error")
    if isinstance(err, dict):
        error_msg = err.get("message")
    if not isinstance(error_msg, str) or not error_msg:
        error_msg = response.text.strip() or f"HTTP {response.status_code}"

    ok = 200 <= response.status_code < 300
    return Completion(
        text="",
        usage=Usage.from_response(parsed.get("usage")),
        latency_ms=elapsed,
        status=response.status_code,
        headers=resp_headers,
        raw=parsed,
        ok=ok,
        error=None if ok else error_msg,
    )
