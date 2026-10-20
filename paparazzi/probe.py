"""The only module that writes probe_runs rows."""

from __future__ import annotations

import inspect
import sys
from typing import Any, Callable

from paparazzi import battery, db


def _conn(conn: Any) -> Any:
    if conn is not None:
        return conn
    try:
        from paparazzi import config

        path = config.db_path()
    except Exception:
        path = db.DEFAULT_DB
    return db.connect(path)


def _is_anonymous(slug: str) -> bool:
    try:
        from paparazzi import cli

        return bool(cli.is_anonymous(slug))
    except Exception:
        return "stealth/" in slug or "anon" in slug


def _mock_flag(mock: bool | None) -> bool:
    if mock is not None:
        return bool(mock)
    try:
        from paparazzi import config

        return bool(config.mock())
    except Exception:
        import os

        return os.environ.get("PAPARAZZI_MOCK", "").strip().lower() in {"1", "true", "yes", "on"}


def _arity(fn: Callable) -> int:
    try:
        sig = inspect.signature(fn)
    except (TypeError, ValueError):
        return 0
    count = 0
    for param in sig.parameters.values():
        if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
            count += 1
    return count


def _model_sender(send: Callable | None, model: str, mock: bool | None) -> Callable[[str, str], Any]:
    if send is None:
        from paparazzi import openrouter

        _mock = mock

        def _default(m: str, p: str) -> Any:
            return openrouter.complete(m, p, mock=_mock)

        return _default
    if _arity(send) >= 2:
        _mock = mock

        def _wrapped(m: str, p: str) -> Any:
            try:
                return send(m, p, mock=_mock)
            except TypeError:
                return send(m, p)

        return _wrapped
    # single-arg sender is text-based; ignore model for compatibility
    def _text_based(m: str, p: str) -> Any:
        return send(p)

    return _text_based


def _text_sender(send: Callable | None, model: str, mock: bool | None) -> Callable[[str], Any]:
    if send is None:
        from paparazzi import openrouter

        _mock = mock

        def _default(text: str) -> Any:
            return openrouter.complete(model, text, mock=_mock)

        return _default
    if _arity(send) >= 2:
        _mock = mock

        def _wrapped(text: str) -> Any:
            try:
                return send(model, text, mock=_mock)
            except TypeError:
                return send(model, text)

        return _wrapped
    return send


def run_battery(
    model: str,
    prompts: Any = None,
    *,
    send: Callable | None = None,
    conn: Any = None,
    mock: bool | None = None,
) -> int:
    if prompts is None:
        prompts = battery.prompts()

    conn = _conn(conn)
    db.upsert_model(conn, model, anonymous=_is_anonymous(model))
    used_mock = _mock_flag(mock)
    run_id = db.start_run(conn, model, "battery", used_mock=used_mock)
    sender = _model_sender(send, model, mock)

    try:
        for idx, item in enumerate(prompts):
            if hasattr(item, "key") and hasattr(item, "text"):
                key = str(item.key)
                text = str(item.text)
            else:
                key = str(item[0])
                text = str(item[1])

            try:
                completion = sender(model, text)
            except Exception as exc:
                db.add_response(
                    conn,
                    run_id,
                    prompt_key=key,
                    idx=idx,
                    ok=False,
                    error=str(exc),
                )
                raise RuntimeError(str(exc)) from exc

            usage = getattr(completion, "usage", None)
            prompt_tokens = getattr(usage, "prompt_tokens", None) if usage is not None else None
            completion_tokens = getattr(usage, "completion_tokens", None) if usage is not None else None
            reasoning_tokens = getattr(usage, "reasoning_tokens", None) if usage is not None else None
            if prompt_tokens is None and isinstance(usage, dict):
                prompt_tokens = usage.get("prompt_tokens")
                completion_tokens = usage.get("completion_tokens")
                reasoning_tokens = usage.get("reasoning_tokens")

            ok = bool(getattr(completion, "ok", True))
            db.add_response(
                conn,
                run_id,
                prompt_key=key,
                idx=idx,
                text=getattr(completion, "text", None),
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                reasoning_tokens=reasoning_tokens,
                latency_ms=getattr(completion, "latency_ms", None),
                ok=ok,
                error=getattr(completion, "error", None),
            )
            if not ok:
                raise RuntimeError(getattr(completion, "error", None) or "completion failed")
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=str(exc))
        raise SystemExit(1)

    db.finish_run(conn, run_id, ok=True)
    return run_id


def run_tokenizer(
    model: str,
    *,
    send: Callable | None = None,
    conn: Any = None,
    mock: bool | None = None,
) -> int:
    conn = _conn(conn)
    db.upsert_model(conn, model, anonymous=_is_anonymous(model))
    used_mock = _mock_flag(mock)
    run_id = db.start_run(conn, model, "tokenizer", used_mock=used_mock)

    try:
        from paparazzi.probes import tokenizer as tz
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"tokenizer probe unavailable: {exc}")
        raise SystemExit(1)

    text_sender = _text_sender(send, model, mock)

    try:
        probes = tz.probe_strings()
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"tokenizer probe_strings failed: {exc}")
        raise SystemExit(1)

    try:
        counts = tz.count_differential(text_sender, probes)
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"count_differential failed: {exc}")
        raise SystemExit(1)

    if not isinstance(counts, dict):
        counts = {}

    # candidate comparison (best effort, never required for storage)
    report: Any = None
    try:
        from paparazzi import candidates

        cands = getattr(candidates, "DEFAULT_CANDIDATES", [])
        report = tz.compare(counts, cands)
    except Exception as exc:
        try:
            report = tz.compare(counts, [])
        except Exception:
            report = {"error": str(exc)}

    # per-probe response rows
    for idx, (pid, _text) in enumerate(probes):
        value = counts.get(pid) if isinstance(counts, dict) else None
        db.add_response(
            conn,
            run_id,
            prompt_key=str(pid),
            idx=idx,
            prompt_tokens=value,
            ok=(value is not None),
            error=None if value is not None else "probe failed",
        )

    ok = True
    error: str | None = None
    if not counts and not used_mock:
        ok = False
        error = "tokenizer base probe failed"

    meta = {"counts": counts, "report": report}
    db.finish_run(conn, run_id, ok=ok, error=error, meta=meta)
    if not ok:
        raise SystemExit(1)
    return run_id


def run_infra(
    model: str,
    *,
    send_payload: Callable | None = None,
    conn: Any = None,
    mock: bool | None = None,
) -> int:
    conn = _conn(conn)
    db.upsert_model(conn, model, anonymous=_is_anonymous(model))
    used_mock = _mock_flag(mock)
    run_id = db.start_run(conn, model, "infra", used_mock=used_mock)

    if send_payload is None:
        from paparazzi import openrouter

        _mock = mock

        def send_payload(payload: Any) -> Any:
            return openrouter.infra_probe(model, payload, mock=_mock)

    try:
        from paparazzi.probes import infra as inframod
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"infra probe unavailable: {exc}")
        raise SystemExit(1)

    try:
        result = inframod.collect(send_payload, model)
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"infra collect failed: {exc}")
        raise SystemExit(1)

    meta = result if isinstance(result, dict) else {"result": result}
    db.finish_run(conn, run_id, ok=True, meta=meta)
    return run_id


def run_context(
    model: str,
    *,
    send: Callable | None = None,
    conn: Any = None,
    mock: bool | None = None,
) -> int:
    conn = _conn(conn)
    db.upsert_model(conn, model, anonymous=_is_anonymous(model))
    used_mock = _mock_flag(mock)
    run_id = db.start_run(conn, model, "context", used_mock=used_mock)

    try:
        from paparazzi.probes import context as ctxmod
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"context probe unavailable: {exc}")
        raise SystemExit(1)

    text_sender = _text_sender(send, model, mock)

    try:
        sizes = (8_000, 32_000, 128_000)
        result = ctxmod.ladder(text_sender, model, sizes=sizes)
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"context ladder failed: {exc}")
        raise SystemExit(1)

    # per-size response rows (context sizes are not prompts; store as sizes)
    # The contract asks for responses per probe; context has no per-prompt rows required.
    # Store the ladder result in meta.
    meta = result if isinstance(result, dict) else {"result": result}
    db.finish_run(conn, run_id, ok=True, meta=meta)
    return run_id


def probe(model: str, kind: str = "battery", *, mock: bool | None = None, conn: Any = None, **kwargs: Any) -> int:
    kind = (kind or "battery").lower()
    if kind in {"battery", "know", "probe", "run"}:
        return run_battery(model, conn=conn, mock=mock, **{k: v for k, v in kwargs.items() if k in {"prompts", "send"}})
    if kind in {"tokenizer"}:
        return run_tokenizer(model, conn=conn, mock=mock, **{k: v for k, v in kwargs.items() if k in {"send"}})
    if kind in {"infra"}:
        return run_infra(model, conn=conn, mock=mock, **{k: v for k, v in kwargs.items() if k in {"send_payload"}})
    if kind in {"context"}:
        return run_context(model, conn=conn, mock=mock, **{k: v for k, v in kwargs.items() if k in {"send"}})
    # default
    return run_battery(model, conn=conn, mock=mock)


def run_generation(
    model: str,
    *,
    generate: Callable | None = None,
    conn: Any = None,
    mock: bool | None = None,
) -> int:
    """Ask OpenRouter who is behind the slug. Records an unavailable answer as unavailable."""
    conn = _conn(conn)
    db.upsert_model(conn, model, anonymous=_is_anonymous(model))
    used_mock = _mock_flag(mock)
    run_id = db.start_run(conn, model, "generation", used_mock=used_mock)

    if generate is None:
        from paparazzi import openrouter

        _mock = mock

        def generate(target: str) -> dict:
            return openrouter.generation(target, mock=_mock)

    try:
        from paparazzi.probes import generation as genmod
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"generation probe unavailable: {exc}")
        raise SystemExit(1)

    try:
        result = genmod.collect(generate, model)
    except Exception as exc:
        db.finish_run(conn, run_id, ok=False, error=f"generation collect failed: {exc}")
        raise SystemExit(1)

    meta = result if isinstance(result, dict) else {"result": result}
    db.finish_run(conn, run_id, ok=True, meta=meta)
    return run_id


def run_all(
    model: str,
    *,
    conn: Any = None,
    mock: bool | None = None,
    send: Callable | None = None,
) -> dict[str, int]:
    """Run every signal family for one slug, in cost order.

    Stops at the first failure. The failure is already stored on its run row,
    and SystemExit(1) carries the exit code out to the caller.
    """
    conn = _conn(conn)
    run_ids: dict[str, int] = {
        "battery": run_battery(model, send=send, conn=conn, mock=mock),
        "tokenizer": run_tokenizer(model, conn=conn, mock=mock),
        "infra": run_infra(model, conn=conn, mock=mock),
        "generation": run_generation(model, conn=conn, mock=mock),
        "context": run_context(model, conn=conn, mock=mock),
    }
    return run_ids


def _meta_signal(run: Any, family: str) -> Any:
    """Pull a family's signal out of a run's stored meta.

    The key order matches paparazzi.match._signal_from_run on purpose: what
    `know` stores has to be what `match` reads back, or signatures silently
    stop round-tripping.
    """
    raw = run["meta"] if "meta" in run.keys() else None
    if raw is None:
        return None
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return None
        try:
            import json

            meta = json.loads(raw)
        except Exception:
            return None
    else:
        meta = raw
    if not isinstance(meta, dict) or not meta:
        return None
    for key in ("result", "signal", family, "data", "counts"):
        value = meta.get(key)
        if isinstance(value, dict):
            return value
    return meta


def build_signals(conn: Any, run_ids: dict[str, int]) -> dict[str, Any]:
    """Turn fresh run rows into the signals dict a signature stores."""
    signals: dict[str, Any] = {}
    for run_kind, run_id in run_ids.items():
        run = conn.execute("SELECT * FROM probe_runs WHERE id = ?", (int(run_id),)).fetchone()
        if run is None:
            continue
        try:
            ok = bool(int(run["ok"]))
        except (TypeError, ValueError):
            ok = bool(run["ok"])
        if not ok:
            continue

        if run_kind == "battery":
            try:
                from paparazzi import features
            except Exception:
                continue
            vector = features.from_responses(db.responses_for(conn, int(run_id)))
            if vector:
                signals["style"] = vector
            continue

        signal = _meta_signal(run, run_kind)
        if signal:
            signals[run_kind] = signal
    return signals


def know(
    model: str,
    *,
    conn: Any = None,
    mock: bool | None = None,
    send: Callable | None = None,
) -> dict[str, Any]:
    """Enroll a known model: run every family, store the signature.

    The signature is marked used_mock when the run was a fixture replay, so a
    fixture-built signature can never read as a measured one later.
    """
    conn = _conn(conn)
    run_ids = run_all(model, conn=conn, mock=mock, send=send)
    signals = build_signals(conn, run_ids)
    if not signals:
        print(f"no signals measured for {model}, signature not stored", file=sys.stderr)
        raise SystemExit(1)

    db.upsert_signature(conn, model, signals, used_mock=_mock_flag(mock))
    return {"run_ids": run_ids, "families": sorted(signals)}


# single name for callers that just want the dispatcher
run = probe
