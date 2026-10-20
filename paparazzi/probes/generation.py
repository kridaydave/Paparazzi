"""Generation metadata probe: cheapest direct evidence from OpenRouter's /generation."""

from __future__ import annotations


def collect(generate, model: str) -> dict:
    """Collect generation metadata for ``model`` via the injected ``generate``.

    ``generate(model)`` returns the payload from OpenRouter's ``/generation``
    endpoint, or an empty dict when it is unavailable. The client is never
    imported here; the caller injects it.
    """
    payload = generate(model)
    if not isinstance(payload, dict) or not payload:
        return {"available": False, "provider": None, "region": None, "fields": []}

    nested = payload.get("data") if isinstance(payload.get("data"), dict) else None

    def _pick(*keys):
        for key in keys:
            value = payload.get(key)
            if value is not None:
                return value
        if nested is not None:
            for key in keys:
                value = nested.get(key)
                if value is not None:
                    return value
        return None

    provider = _pick("provider_name", "provider")
    region = _pick("data_region", "region", "region_name", "dataRegion")

    if not isinstance(provider, str):
        provider = None
    if not isinstance(region, str):
        region = None

    return {
        "available": True,
        "provider": provider,
        "region": region,
        "fields": sorted(payload.keys()),
    }


def compare(a: dict, b: dict) -> float | None:
    """Compare two generation metadata dicts.

    Returns ``None`` when either side is unavailable. Otherwise:

    - ``1.0`` when provider and region both agree.
    - ``0.5`` when one field agrees and the other is missing on at least one side.
    - ``0.0`` when a field present on both sides disagrees.

    Absent fields never count as disagreement.
    """
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return None
    if not (a.get("available") and b.get("available")):
        return None

    pa, pb = a.get("provider"), b.get("provider")
    ra, rb = a.get("region"), b.get("region")

    if pa is not None and pb is not None and pa != pb:
        return 0.0
    if ra is not None and rb is not None and ra != rb:
        return 0.0

    agreed = 0
    if pa is not None and pb is not None and pa == pb:
        agreed += 1
    if ra is not None and rb is not None and ra == rb:
        agreed += 1

    if agreed >= 2:
        return 1.0
    if agreed == 1:
        return 0.5
    return 0.5