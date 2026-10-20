"""Infra family probe: how does the endpoint reject malformed requests?"""

from __future__ import annotations

from typing import Any, Callable

_META_KEYS = {"model", "mock", "used_mock", "paparazzi_mock", "available", "probes"}


def _probe_result(completion: Any) -> dict[str, Any]:
    status = 0
    raw: Any = {}
    error: str | None = None
    if completion is not None:
        status = getattr(completion, "status", 0) or 0
        raw = getattr(completion, "raw", {})
        error = getattr(completion, "error", None)
    if not isinstance(raw, dict):
        raw = {}

    err_obj = raw.get("error")
    if not isinstance(err_obj, dict):
        err_obj = {}

    code = err_obj.get("code")
    if code is None and isinstance(err_obj.get("param"), str):
        code = None
    etype = err_obj.get("type")
    message = err_obj.get("message")
    if not isinstance(message, str):
        message = error if isinstance(error, str) else None

    envelope_keys = sorted(raw.keys())

    result = {
        "status": int(status) if status is not None else 0,
        "error_code": code,
        "error_type": etype,
        "error_message": message,
        "envelope_keys": envelope_keys,
        # aliases for callers that expect shorter keys
        "code": code,
        "type": etype,
        "message": message,
        "keys": envelope_keys,
    }
    if isinstance(raw.get("paparazzi_mock"), bool) and raw.get("paparazzi_mock"):
        result["paparazzi_mock"] = True
    return result


def collect(send_payload: Callable[[Any], Any], model: str) -> dict[str, Any]:
    """Run a handful of malformed requests and return a JSON-able dict."""
    probes: list[tuple[str, Any]] = [
        (
            "out_of_range_temperature",
            {"messages": [{"role": "user", "content": "hi"}], "temperature": 2.0, "max_tokens": 8},
        ),
        (
            "absurd_max_tokens",
            {"messages": [{"role": "user", "content": "hi"}], "max_tokens": 10_000_000},
        ),
        (
            "invalid_role",
            {"messages": [{"role": "banana", "content": "hi"}], "max_tokens": 8},
        ),
        ("malformed_json_body", "{not valid json"),
        (
            "missing_required_field",
            {"temperature": 0.0},
        ),
    ]

    results: dict[str, Any] = {}
    probe_list: list[dict[str, Any]] = []
    any_mock = False

    for name, payload in probes:
        try:
            completion = send_payload(payload)
        except Exception as exc:
            completion = None
            err_text = str(exc)
        else:
            err_text = None

        result = _probe_result(completion)
        if err_text is not None and result["error_message"] is None:
            result["error_message"] = err_text
            result["message"] = err_text
        if completion is not None and getattr(completion, "raw", None) and isinstance(completion.raw, dict):
            if completion.raw.get("paparazzi_mock"):
                any_mock = True
                result["paparazzi_mock"] = True
        results[name] = result
        probe_list.append({"probe": name, **result})

    results["model"] = model
    results["mock"] = any_mock
    results["used_mock"] = any_mock
    results["paparazzi_mock"] = any_mock
    results["probes"] = probe_list
    # also expose as dict under "probes" for convenience
    results["probes_dict"] = {p["probe"]: {k: v for k, v in p.items() if k != "probe"} for p in probe_list}
    return results


def _probe_map(data: Any) -> dict[str, Any]:
    if not isinstance(data, dict) or not data:
        return {}
    if isinstance(data.get("probes"), dict):
        base = data["probes"]
    elif isinstance(data.get("probes"), list):
        base = {}
        for item in data["probes"]:
            if isinstance(item, dict):
                name = item.get("probe") or item.get("name") or item.get("id")
                if name is not None:
                    base[name] = {k: v for k, v in item.items() if k not in ("probe", "name", "id")}
    elif isinstance(data.get("probes_dict"), dict):
        base = data["probes_dict"]
    else:
        base = data

    result: dict[str, Any] = {}
    for key, value in base.items():
        if key in _META_KEYS or key in {"probes_dict"}:
            continue
        if isinstance(value, dict) and (
            "status" in value
            or "code" in value
            or "error_code" in value
            or "message" in value
            or "error_message" in value
            or "envelope_keys" in value
            or "keys" in value
        ):
            result[key] = value
    return result


def _is_mock(data: Any) -> bool:
    if not isinstance(data, dict) or not data:
        return True
    for key in ("mock", "used_mock", "paparazzi_mock"):
        if data.get(key):
            return True
    pm = _probe_map(data)
    for value in pm.values():
        if isinstance(value, dict) and value.get("paparazzi_mock"):
            return True
    return False


def _norm_probe(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict):
        value = {}
    code = value.get("error_code")
    if code is None:
        code = value.get("code")
    etype = value.get("error_type")
    if etype is None:
        etype = value.get("type")
    status = value.get("status")
    return {"status": status, "code": code, "type": etype}


def compare(a: Any, b: Any) -> float | None:
    """Agreement over probes both sides have."""
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return None
    if not a or not b:
        return None
    if _is_mock(a) or _is_mock(b):
        return None

    map_a = _probe_map(a)
    map_b = _probe_map(b)
    if not map_a or not map_b:
        return None

    common = sorted(set(map_a) & set(map_b))
    if not common:
        return None

    agree = 0
    for name in common:
        na = _norm_probe(map_a[name])
        nb = _norm_probe(map_b[name])
        if na["status"] == nb["status"] and na["code"] == nb["code"] and na["type"] == nb["type"]:
            agree += 1
    return agree / len(common)
