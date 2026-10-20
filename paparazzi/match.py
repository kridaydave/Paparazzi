"""Match an anonymous slug against stored signatures.

Combines several independent signal families with explicit weights. The score is
a heuristic, not a probability.

Weights:
    tokenizer   0.5
    infra       0.15
    generation  0.15
    context     0.1
    style       0.1

Missing families re-normalize over the families that did produce a signal.

Publish bar (``met_bar``): tokenizer agreed on every probe for the best
candidate AND at least one corroborator (generation, infra, context) at 0.5 or
better AND ``used_mock`` is false. Style never counts toward the bar.
"""

from __future__ import annotations

import importlib
import json
from typing import Any, Callable

from paparazzi import db

WEIGHTS: dict[str, float] = {
    "tokenizer": 0.5,
    "infra": 0.15,
    "generation": 0.15,
    "context": 0.1,
    "style": 0.1,
}

# Family -> (run kind, module path)
_FAMILY_RUN_KIND: dict[str, str] = {
    "style": "battery",
    "tokenizer": "tokenizer",
    "infra": "infra",
    "generation": "generation",
    "context": "context",
}

_CORROBORATORS = ("generation", "infra", "context")


def _import_family(family: str) -> Any:
    module_path = {
        "tokenizer": "paparazzi.probes.tokenizer",
        "infra": "paparazzi.probes.infra",
        "generation": "paparazzi.probes.generation",
        "context": "paparazzi.probes.context",
    }.get(family)
    if module_path is None:
        return None
    try:
        return importlib.import_module(module_path)
    except Exception:
        return None


def _load_features() -> Any:
    try:
        return importlib.import_module("paparazzi.features")
    except Exception:
        return None


def _signal_from_run(family: str, run: Any, conn: Any) -> Any:
    if family == "style":
        features = _load_features()
        if features is None:
            return None
        try:
            rows = db.responses_for(conn, int(run["id"]))
        except Exception:
            return None
        try:
            return features.from_responses(rows)
        except Exception:
            return None
    meta_raw = run["meta"] if "meta" in run.keys() else None
    if meta_raw is None:
        return None
    if isinstance(meta_raw, str):
        meta_raw = meta_raw.strip()
        if not meta_raw:
            return None
        try:
            meta = json.loads(meta_raw)
        except (json.JSONDecodeError, TypeError):
            return None
    else:
        meta = meta_raw
    if not isinstance(meta, dict):
        return None
    for key in ("result", "signal", family, "data", "counts"):
        if key in meta and isinstance(meta[key], dict):
            return meta[key]
    return meta if meta else None


def _is_mock_run(run: Any) -> bool:
    try:
        return bool(int(run["used_mock"]))
    except (TypeError, ValueError):
        return bool(run["used_mock"])


def _compare_family(module: Any, slug_signal: Any, candidate_signal: Any) -> float | None:
    if module is None:
        return None
    compare = getattr(module, "compare", None)
    if not callable(compare):
        return None
    try:
        result = compare(slug_signal, candidate_signal)
    except Exception:
        return None
    if result is None:
        return None
    try:
        return float(result)
    except (TypeError, ValueError):
        return None


def evaluate(slug: str, *, conn: Any = None) -> dict[str, Any] | None:
    if conn is None:
        conn = db.connect()

    # Load latest run per family.
    runs: dict[str, Any] = {}
    for family, kind in _FAMILY_RUN_KIND.items():
        try:
            run = db.latest_run(conn, slug, kind)
        except Exception:
            run = None
        if run is not None:
            runs[family] = run

    # Build slug signals per family.
    slug_signals: dict[str, Any] = {}
    family_mock: dict[str, bool] = {}
    for family, run in runs.items():
        try:
            ok = bool(int(run["ok"]))
        except (TypeError, ValueError):
            ok = bool(run["ok"])
        if not ok:
            continue
        if family in ("tokenizer", "infra", "generation", "context"):
            module = _import_family(family)
            if module is None:
                continue
        signal = _signal_from_run(family, run, conn)
        if not signal:
            continue
        slug_signals[family] = signal
        family_mock[family] = _is_mock_run(run)

    if not slug_signals:
        return None

    used_mock = any(family_mock.values())

    # Candidates: every other signature.
    try:
        signatures = db.list_signatures(conn)
    except Exception:
        signatures = []
    candidates_sigs = [s for s in signatures if str(s.get("slug")) != str(slug)]

    if not candidates_sigs:
        # No candidates to compare against; cannot make a guess.
        return None

    # Precompute module handles.
    modules: dict[str, Any] = {}
    for family in slug_signals:
        if family == "style":
            modules[family] = _load_features()
        else:
            modules[family] = _import_family(family)

    # Per candidate evaluation.
    candidate_results: list[dict[str, Any]] = []
    for cand in candidates_sigs:
        cand_slug = str(cand.get("slug"))
        cand_signals = cand.get("signals") or {}
        if not isinstance(cand_signals, dict):
            cand_signals = {}
        per_family_agreement: dict[str, float | None] = {}
        for family, slug_signal in slug_signals.items():
            module = modules.get(family)
            cand_signal = cand_signals.get(family)
            agreement = _compare_family(module, slug_signal, cand_signal)
            per_family_agreement[family] = agreement

        # Combined score over the families that actually produced a signal.
        # A family with no signal is absent evidence, not disagreement, so it
        # leaves both the top and the bottom of the fraction.
        families_with_signal = [
            f
            for f in slug_signals
            if per_family_agreement.get(f) is not None and WEIGHTS.get(f, 0.0) > 0
        ]
        denom = sum(WEIGHTS.get(f, 0.0) for f in families_with_signal)
        if denom <= 0:
            combined = 0.0
        else:
            combined = sum(
                WEIGHTS.get(f, 0.0) * float(per_family_agreement.get(f) or 0.0)
                for f in families_with_signal
            ) / denom
        candidate_results.append(
            {
                "slug": cand_slug,
                "score": float(combined),
                # Every family stays visible here, including the ones with no
                # signal, so a reader can see what the score was built from.
                "per_signal": {f: per_family_agreement.get(f) for f in slug_signals},
            }
        )

    candidate_results.sort(key=lambda c: c["score"], reverse=True)
    best_candidate = candidate_results[0]["slug"] if candidate_results else None

    # Build per_signal report with agreement/score/evidence.
    best_result = candidate_results[0] if candidate_results else None
    best_agreements = best_result["per_signal"] if best_result else {}

    per_signal: dict[str, dict[str, Any]] = {}
    for family, slug_signal in slug_signals.items():
        module = modules.get(family)
        # candidate signal for best
        best_cand_sig = None
        if best_candidate is not None:
            for cand in candidates_sigs:
                if str(cand.get("slug")) == best_candidate:
                    cs = cand.get("signals") or {}
                    if isinstance(cs, dict):
                        best_cand_sig = cs.get(family)
                    break
        agreement = best_agreements.get(family)
        # evidence: include slug signal and best candidate signal
        per_signal[family] = {
            "agreement": (None if agreement is None else float(agreement)),
            "score": (0.0 if agreement is None else round(float(agreement) * 100.0, 1)),
            "evidence": {
                "slug_signal": slug_signal,
                "candidate_signal": best_cand_sig,
            },
        }

    top_candidates = []
    for c in candidate_results[:5]:
        # attach per-family agreement map under per_signal key
        top_candidates.append(
            {
                "slug": c["slug"],
                "score": round(c["score"] * 100.0, 1),
                "per_signal": {f: c["per_signal"].get(f) for f in c["per_signal"]},
            }
        )

    report: dict[str, Any] = {
        "slug": slug,
        "best": best_candidate,
        "score": 0.0,  # filled after score() import below
        "met_bar": False,
        "used_mock": bool(used_mock),
        "candidates": top_candidates,
        "per_signal": per_signal,
    }
    # Compute score and met_bar using module-level helpers (defined below).
    report["score"] = score(report)
    report["met_bar"] = met_bar(report)

    # Store guess row.
    if best_candidate is not None:
        try:
            db.add_guess(
                conn,
                slug,
                best_candidate,
                score=report["score"],
                per_signal=per_signal,
                met_bar=report["met_bar"],
                published=False,
                meta={"used_mock": bool(used_mock)},
            )
        except Exception:
            pass

    return report


def met_bar(report: dict[str, Any]) -> bool:
    if not isinstance(report, dict):
        return False
    if report.get("used_mock"):
        return False
    per_signal = report.get("per_signal") or {}
    tok = per_signal.get("tokenizer", {})
    tok_agree = tok.get("agreement") if isinstance(tok, dict) else None
    if tok_agree is None or float(tok_agree) < 0.999999:
        return False
    for fam in _CORROBORATORS:
        entry = per_signal.get(fam, {})
        ag = entry.get("agreement") if isinstance(entry, dict) else None
        if ag is not None and float(ag) >= 0.5:
            return True
    return False


def score(report: dict[str, Any]) -> float:
    if not isinstance(report, dict):
        return 0.0
    per_signal = report.get("per_signal") or {}
    # Only families that produced a signal take part. Missing evidence shrinks
    # the fraction instead of counting as a zero.
    present: list[str] = []
    for family, entry in per_signal.items():
        if family not in WEIGHTS:
            continue
        agreement = entry.get("agreement") if isinstance(entry, dict) else entry
        if agreement is None:
            continue
        present.append(family)
    if not present:
        return 0.0
    denom = sum(WEIGHTS.get(f, 0.0) for f in present)
    if denom <= 0:
        return 0.0
    numerator = 0.0
    for family in present:
        entry = per_signal.get(family, {})
        agreement = entry.get("agreement") if isinstance(entry, dict) else entry
        value = 0.0 if agreement is None else float(agreement)
        numerator += WEIGHTS.get(family, 0.0) * value
    return round((numerator / denom) * 100.0, 1)