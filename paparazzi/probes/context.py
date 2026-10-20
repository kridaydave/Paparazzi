"""Context ladder probe: does the endpoint actually accept the context it claims?"""

from __future__ import annotations

FILLER = "The quick brown fox jumps over the lazy dog. "
NEEDLE_TEMPLATE = "The access code is {code}."


def _code_for(index: int, size: int) -> int:
    return 847293 + (index * 1009) + (size % 97)


def build_prompt(size: int, index: int = 0) -> str:
    """Build a prompt of roughly ``size`` tokens with a needle at a fixed depth."""
    code = _code_for(index, size)
    needle = NEEDLE_TEMPLATE.format(code=code)
    question = "\n\nWhat is the access code? Reply with only the code."
    target = size * 4
    overhead = len(needle) + len(question) + 2
    filler_chars = max(0, target - overhead)
    half = filler_chars // 2

    def filler_block(n: int) -> str:
        if n <= 0:
            return ""
        repeats = (n // len(FILLER)) + 1
        return (FILLER * repeats)[:n]

    pre = filler_block(half)
    post = filler_block(filler_chars - half)
    return f"{pre} {needle} {post}{question}".strip() + " "


def ladder(send, model: str, sizes=(8_000, 32_000, 128_000)) -> dict:
    """Run a context ladder.

    ``send(text)`` is an injected callable returning a ``Completion``. ``model``
    is accepted for signature compatibility but ``send`` is already bound to it.
    """
    sizes_list = [int(s) for s in sizes]
    ok_at: dict[int, bool] = {}
    failed_at: dict[int, str | None] = {}
    estimated_tokens: dict[int, int] = {}
    limit_observed: int | None = None

    for index, size in enumerate(sizes_list):
        prompt = build_prompt(size, index)
        estimated_tokens[size] = len(prompt) // 4
        code = _code_for(index, size)

        try:
            completion = send(prompt)
        except Exception as exc:  # never swallow: record and move on
            ok_at[size] = False
            failed_at[size] = str(exc)
            continue

        if not getattr(completion, "ok", True):
            ok_at[size] = False
            failed_at[size] = getattr(completion, "error", None) or "request failed"
            continue

        text = getattr(completion, "text", "") or ""
        ok = str(code) in text
        ok_at[size] = bool(ok)
        failed_at[size] = None

    # limit_observed = largest size that succeeded
    succeeded = [s for s in sizes_list if ok_at.get(s) is True]
    limit_observed = max(succeeded) if succeeded else None

    return {
        "sizes": sizes_list,
        "ok_at": ok_at,
        "failed_at": failed_at,
        "estimated_tokens": estimated_tokens,
        "limit_observed": limit_observed,
    }


def compare(a: dict, b: dict) -> float | None:
    """Compare two context ladders.

    Returns ``None`` if either has no sizes. Otherwise agreement over the sizes
    both sides probed: both ok or both failed counts as agreement.
    """
    if not (isinstance(a, dict) and isinstance(b, dict)):
        return None
    sa = a.get("sizes") or []
    sb = b.get("sizes") or []
    if not sa or not sb:
        return None

    ok_a = a.get("ok_at") or {}
    ok_b = b.get("ok_at") or {}

    common = set(sa) & set(sb)
    if not common:
        return None

    agrees = 0
    for size in common:
        a_ok = bool(ok_a.get(size, False))
        b_ok = bool(ok_b.get(size, False))
        if a_ok == b_ok:
            agrees += 1
    return agrees / len(common)

# Convenience aliases for prompt construction.
make_prompt = build_prompt
construct_prompt = build_prompt
prompt_for = build_prompt
