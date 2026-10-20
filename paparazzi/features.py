"""Style/behavioral feature vector.

Style is supporting evidence only. It is never enough on its own to publish
a guess: see ``paparazzi.match`` for the bar.
"""

from __future__ import annotations

import json
import math
import re
import sqlite3
from collections.abc import Iterable
from typing import Any


# A response counts as a refusal when it contains one of these phrases.
_REFUSAL_PHRASES = (
    "i can't",
    "i cannot",
    "i'm not able",
    "i am not able",
    "i won't",
    "i will not",
    "i'm unable",
    "i am unable",
    "sorry, but",
    "sorry, i",
    "as an ai",
    "i don't have",
    "i do not have",
    "not able to help",
    "can't help",
    "cannot help",
    "i'm not going to",
    "i am not going to",
)

_HEDGE_MARKERS = (
    "maybe",
    "perhaps",
    "possibly",
    "might",
    "could be",
    "i think",
    "i believe",
    "probably",
    "likely",
    "not sure",
    "it seems",
    "arguably",
)

_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F1E6-\U0001F1FF]+",
    re.UNICODE,
)

_HEADING_RE = re.compile(r"(?m)^\s{0,3}#{1,6}\s+\S")
_LIST_RE = re.compile(r"(?m)^\s*([-*+]|\d+\.)\s+\S")
_BOLD_RE = re.compile(r"\*\*[^*\n]+\*\*|__[^_\n]+__")

_MAKER_PATTERNS = (
    re.compile(r"(?:made|created|built|developed|trained|designed|produced)\s+by\s+([^.!?\n]{2,80})", re.IGNORECASE),
    re.compile(r"(?:i am|i'm)\s+(?:a\s+)?(?:model|assistant|ai|llm|chatbot)\s+(?:from|by|of)\s+([^.!?\n]{2,80})", re.IGNORECASE),
    re.compile(r"(?:from|by)\s+(openai|anthropic|google|meta|mistral|cohere|deepseek|alibaba|qwen|z\.?ai|zhipu|xai|perplexity|amazon|nvidia|microsoft)", re.IGNORECASE),
)


def _row_value(row: Any, key: str, default: Any = None) -> Any:
    if isinstance(row, dict):
        return row.get(key, default)
    try:
        return row[key]
    except (KeyError, IndexError, TypeError):
        try:
            return getattr(row, key, default)
        except Exception:
            return default


def _is_ok(row: Any) -> bool:
    value = _row_value(row, "ok", 1)
    if value is None:
        return True
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return bool(value)


def _text_of(row: Any) -> str:
    value = _row_value(row, "text", None)
    if value is None:
        return ""
    return str(value)


def _meta_of(row: Any) -> dict[str, Any]:
    raw = _row_value(row, "meta", None)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        raw = raw.strip()
        if not raw:
            return {}
        try:
            parsed = json.loads(raw)
            return parsed if isinstance(parsed, dict) else {}
        except (json.JSONDecodeError, TypeError):
            return {}
    return {}


def _word_count(text: str) -> int:
    return len(text.split())


def _contains_emoji(text: str) -> bool:
    return bool(_EMOJI_RE.search(text))


def _contains_markdown(text: str) -> bool:
    return bool(_HEADING_RE.search(text) or _LIST_RE.search(text) or _BOLD_RE.search(text))


def _is_refusal(text: str) -> bool:
    lowered = text.lower()
    return any(phrase in lowered for phrase in _REFUSAL_PHRASES)


def _contains_hedge(text: str) -> bool:
    lowered = text.lower()
    return any(marker in lowered for marker in _HEDGE_MARKERS)


def _extract_maker_claims(text: str) -> list[str]:
    claims: list[str] = []
    for pattern in _MAKER_PATTERNS:
        for match in pattern.finditer(text):
            claim = match.group(0).strip()
            if match.lastindex:
                captured = match.group(match.lastindex).strip().rstrip(".,;:!?")
                if captured:
                    claim = captured
            if claim and claim not in claims:
                claims.append(claim)
    # Fall back to sentence-level claims mentioning makers.
    if not claims:
        for sentence in re.split(r"(?<=[.!?])\s+", text):
            lowered = sentence.lower()
            if any(word in lowered for word in ("made by", "created by", "built by", "developed by", "trained by")):
                cleaned = sentence.strip()
                if cleaned and cleaned not in claims:
                    claims.append(cleaned)
    return claims


_WORD_NUMBERS = {
    "zero": 0, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
    "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}


def _to_int(token: str) -> int | None:
    token = token.strip().lower()
    if token.isdigit():
        return int(token)
    return _WORD_NUMBERS.get(token)


def _counting_prompt_text(row: Any) -> str | None:
    meta = _meta_of(row)
    for key in ("prompt", "text", "prompt_text", "prompt_body", "question"):
        value = meta.get(key)
        if isinstance(value, str) and value.strip():
            return value
    prompt_key = _row_value(row, "prompt_key", None)
    if not isinstance(prompt_key, str):
        return None
    # Try to resolve a known battery prompt from the battery file.
    try:
        from paparazzi import battery as _battery

        for prompt in _battery.load():
            if getattr(prompt, "key", None) == prompt_key:
                return str(prompt.text)
    except Exception:
        pass
    lowered = prompt_key.lower()
    if "count" in lowered or "repeat" in lowered or "exact" in lowered or "quirk" in lowered:
        return prompt_key
    return None


def _parse_counting_expectation(prompt_text: str) -> tuple[int | None, str | None, str | None]:
    """Return (expected_count, target_word, mode) where mode is 'repeat' or 'count_letter'."""
    lowered = prompt_text.lower()
    # repeat exactly N times
    match = re.search(r"repeat\s+(?:the\s+word\s+)?['\"]?(\w+)['\"]?\s+exactly\s+(\w+)", lowered)
    if match:
        target = match.group(1)
        expected = _to_int(match.group(2))
        if expected is not None:
            return expected, target, "repeat"
    match = re.search(r"exactly\s+(\w+)\s+times", lowered)
    if match:
        # try to find a quoted word
        word_match = re.search(r"['\"](\w+)['\"]", prompt_text)
        target = word_match.group(1) if word_match else None
        expected = _to_int(match.group(1))
        if expected is not None:
            return expected, target, "repeat"
    # count letter X in word Y
    match = re.search(r"count\s+the\s+letter\s+['\"]?(\w)['\"]?\s+in\s+(?:the\s+word\s+)?['\"]?(\w+)['\"]?", lowered)
    if match:
        letter = match.group(1)
        word = match.group(2)
        expected = word.count(letter)
        return expected, letter, "count_letter"
    return None, None, None


def _counting_miss(row: Any, text: str) -> bool | None:
    prompt_text = _counting_prompt_text(row)
    if not prompt_text:
        return None
    expected, target, mode = _parse_counting_expectation(prompt_text)
    if expected is None:
        # If prompt_key itself hints at counting but no parse, fall back to a
        # simple "exactly N" scan of the prompt_key.
        if mode is None and ("count" in prompt_text.lower() or "repeat" in prompt_text.lower() or "exact" in prompt_text.lower()):
            num_match = re.search(r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten)", prompt_text.lower())
            if num_match:
                expected = _to_int(num_match.group(1))
        if expected is None:
            return None
    if mode == "repeat" and target:
        actual = len(re.findall(r"\b" + re.escape(target) + r"\b", text, flags=re.IGNORECASE))
        return actual != expected
    if mode == "count_letter" and target:
        # Check whether the response states the expected count.
        nums = re.findall(r"\d+", text)
        if nums:
            return int(nums[0]) != expected
        # word numbers
        for word, value in _WORD_NUMBERS.items():
            if re.search(r"\b" + word + r"\b", text.lower()):
                return value != expected
        return True
    return None


def from_responses(rows: Iterable[Any]) -> dict[str, Any]:
    """Build a style feature vector from one battery run's responses.

    ``rows`` are ``responses`` table rows. Failed rows (``ok=0``) are skipped
    rather than counted as zero-rate answers.
    """
    rows = list(rows or [])
    ok_rows = [r for r in rows if _is_ok(r)]

    emoji_hits = 0
    markdown_hits = 0
    heading_hits = 0
    list_hits = 0
    bold_hits = 0
    word_counts: list[int] = []
    refusal_hits = 0
    hedge_hits = 0
    counting_misses: list[bool] = []
    maker_claims: list[str] = []

    for row in ok_rows:
        text = _text_of(row)
        if _contains_emoji(text):
            emoji_hits += 1
        if _contains_markdown(text):
            markdown_hits += 1
        if _HEADING_RE.search(text):
            heading_hits += 1
        if _LIST_RE.search(text):
            list_hits += 1
        if _BOLD_RE.search(text):
            bold_hits += 1
        word_counts.append(_word_count(text))
        if _is_refusal(text):
            refusal_hits += 1
        if _contains_hedge(text):
            hedge_hits += 1
        miss = _counting_miss(row, text)
        if miss is not None:
            counting_misses.append(bool(miss))
        for claim in _extract_maker_claims(text):
            if claim not in maker_claims:
                maker_claims.append(claim)

    n = len(ok_rows)
    if n == 0:
        emoji_rate = 0.0
        markdown_rate = 0.0
        heading_rate = 0.0
        list_rate = 0.0
        bold_rate = 0.0
        avg_word_count = 0.0
        refusal_rate = 0.0
        hedge_rate = 0.0
    else:
        emoji_rate = emoji_hits / n
        markdown_rate = markdown_hits / n
        heading_rate = heading_hits / n
        list_rate = list_hits / n
        bold_rate = bold_hits / n
        avg_word_count = sum(word_counts) / n
        refusal_rate = refusal_hits / n
        hedge_rate = hedge_hits / n

    counting_quirk_miss: bool | None
    if not counting_misses:
        counting_quirk_miss = None
    else:
        counting_quirk_miss = any(counting_misses)

    return {
        "emoji_rate": float(emoji_rate),
        "markdown_rate": float(markdown_rate),
        "heading_rate": float(heading_rate),
        "list_rate": float(list_rate),
        "bold_rate": float(bold_rate),
        "avg_word_count": float(avg_word_count),
        "refusal_rate": float(refusal_rate),
        "hedge_rate": float(hedge_rate),
        "counting_quirk_miss": counting_quirk_miss,
        "maker_claims": maker_claims,
    }


def _is_flagged_mock(sig: Any) -> bool:
    if not isinstance(sig, dict):
        return False
    if sig.get("mock") or sig.get("used_mock") or sig.get("_mock"):
        return True
    # A features dict with no real answers is treated as mock/empty.
    if not sig:
        return True
    return False


def _numeric_items(sig: Any) -> dict[str, float]:
    if not isinstance(sig, dict):
        return {}
    out: dict[str, float] = {}
    for key, value in sig.items():
        if isinstance(value, bool):
            out[key] = 1.0 if value else 0.0
        elif isinstance(value, (int, float)):
            # guard nan/inf
            if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
                continue
            out[key] = float(value)
        # lists/strings/dicts are not part of the cosine vector
    return out


def _normalize_sig(sig: Any, population: list[Any] | None) -> Any:
    # Unwrap signature containers.
    if isinstance(sig, dict):
        if "style" in sig and isinstance(sig["style"], dict):
            return sig["style"]
        if "signals" in sig and isinstance(sig["signals"], dict):
            inner = sig["signals"]
            if "style" in inner and isinstance(inner["style"], dict):
                return inner["style"]
            return inner
    return sig


def compare(a: Any, b: Any, population: Any = None) -> float | None:
    """Cosine similarity between two style signatures.

    ``population`` is an optional list of other signatures used to compute
    per-key mean/std for z-scaling. With fewer than 3 usable signatures we
    fall back to plain cosine over the bounded rates.
    """
    a = _normalize_sig(a, population)
    b = _normalize_sig(b, population)

    if _is_flagged_mock(a) or _is_flagged_mock(b):
        return None
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    if not a or not b:
        return None

    va = _numeric_items(a)
    vb = _numeric_items(b)
    shared = [k for k in va if k in vb]
    if not shared:
        return None

    # Population usable count.
    pop_list: list[Any] = []
    if isinstance(population, (list, tuple)):
        pop_list = list(population)
    usable_pop = []
    for item in pop_list:
        ns = _normalize_sig(item, None)
        if isinstance(ns, dict) and ns and not _is_flagged_mock(ns):
            usable_pop.append(ns)

    use_z = len(usable_pop) >= 3

    if use_z:
        # mean/std per shared key over population
        means: dict[str, float] = {}
        stds: dict[str, float] = {}
        for key in shared:
            values = []
            for ns in usable_pop:
                if key in ns and isinstance(ns[key], (int, float, bool)):
                    values.append(float(ns[key]))
            if not values:
                means[key] = 0.0
                stds[key] = 0.0
                continue
            m = sum(values) / len(values)
            var = sum((v - m) ** 2 for v in values) / len(values)
            s = math.sqrt(var)
            means[key] = m
            stds[key] = s

        def z(sig_items: dict[str, float], key: str) -> float:
            std = stds[key]
            if std == 0:
                return 0.0
            return (sig_items[key] - means[key]) / std

        a_vec = [z(va, k) for k in shared]
        b_vec = [z(vb, k) for k in shared]
    else:
        a_vec = [va[k] for k in shared]
        b_vec = [vb[k] for k in shared]

    dot = sum(x * y for x, y in zip(a_vec, b_vec))
    na = math.sqrt(sum(x * x for x in a_vec))
    nb = math.sqrt(sum(y * y for y in b_vec))
    if na == 0 or nb == 0:
        return None
    result = dot / (na * nb)
    # clamp tiny numerical drift
    if result > 1.0:
        result = 1.0
    if result < -1.0:
        result = -1.0
    return float(result)