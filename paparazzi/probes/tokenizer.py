"""Tokenizer differential probe.

The strongest signal in paparazzi: OpenRouter reports ``usage.prompt_tokens``
using the model's own tokenizer, so base-vs-base+probe subtraction isolates how
the model tokenizes a probe string, and comparing those counts against candidate
vocabularies names the model family.
"""

from __future__ import annotations

from typing import Any, Callable

BASE_PROMPT = "The quick brown fox jumps over the lazy dog."


def _as_completion(value: Any) -> Any:
    return value


def _ok(value: Any) -> bool:
    if hasattr(value, "ok"):
        return bool(value.ok)
    if isinstance(value, dict):
        return bool(value.get("ok", True))
    return True


def _used_mock(value: Any) -> bool:
    if hasattr(value, "used_mock"):
        return bool(value.used_mock)
    if isinstance(value, dict):
        raw = value.get("raw")
        if isinstance(raw, dict):
            return bool(raw.get("paparazzi_mock"))
        return bool(value.get("used_mock"))
    return False


def _prompt_tokens(value: Any) -> int:
    usage = None
    if hasattr(value, "usage"):
        usage = value.usage
    elif isinstance(value, dict):
        usage = value.get("usage")
    if usage is None:
        return 0
    if hasattr(usage, "prompt_tokens"):
        return int(usage.prompt_tokens or 0)
    if isinstance(usage, dict):
        return int(usage.get("prompt_tokens") or 0)
    return 0


def probe_strings() -> list[tuple[str, str]]:
    """Return ~95 (probe id, probe text) pairs used for differential counting."""
    probes: list[tuple[str, str]] = []

    # Latin prose
    probes.append(("latin-short", "The quick brown fox jumps over the lazy dog."))
    probes.append(("latin-pangram", "Pack my box with five dozen liquor jugs."))
    probes.append(("latin-question", "How many tokens does this sentence use?"))
    probes.append(("latin-numbers", "There are 42 apples and 7 oranges in the basket."))
    probes.append(("latin-contraction", "Don't you think it's impossible?"))
    probes.append(("latin-hyphen", "state-of-the-art tokenization is well-known."))
    probes.append(("latin-apostrophe", "O'Reilly's book isn't O'Reilly's favourite."))

    # Cyrillic
    probes.append(("cyrillic-basic", "Привет, как дела?"))
    probes.append(("cyrillic-long", "Быстрая бурая лиса прыгает через ленивую собаку."))
    probes.append(("cyrillic-mixed", "Hello мир and привет world."))

    # CJK
    probes.append(("cjk-han", "快速的棕色狐狸跳过懒狗。"))
    probes.append(("cjk-han-long", "天地玄黄宇宙洪荒日月盈昃辰宿列张。"))
    probes.append(("cjk-hiragana", "すばやい茶色の狐が怠け者の犬を飛び越える。"))
    probes.append(("cjk-katakana", "クイックブラウンフォックス。"))
    probes.append(("cjk-hangul", "빠른 갈색 여우가 게으른 개를 뛰어넘는다."))
    probes.append(("cjk-mixed", "Hello 世界 and こんにちは and 안녕하세요."))

    # Arabic
    probes.append(("arabic-basic", "مرحبا كيف حالك"))
    probes.append(("arabic-long", "الثعلب البني السريع يقفز فوق الكلب الكسول."))
    probes.append(("arabic-digits", "لدي ٤٢ تفاحة و ٧ برتقال."))

    # Devanagari
    probes.append(("devanagari-basic", "नमस्ते आप कैसे हैं"))
    probes.append(("devanagari-long", "तेज भूरी लोमड़ी आलसी कुत्ते के ऊपर कूदती है।"))

    # Emoji
    probes.append(("emoji-single", "😀😁😂🤣😃😄😅😆😉😊"))
    probes.append(("emoji-zwj", "👨‍👩‍👧‍👦👩‍💻👨‍🚀"))
    probes.append(("emoji-flag", "🇺🇸🇬🇧🇯🇵🇫🇷🇩🇪"))
    probes.append(("emoji-skin", "👍🏽👋🏻🤝🏿"))
    probes.append(("emoji-sequence", "❤️‍🔥👩‍❤️‍👨"))
    probes.append(("emoji-mixed", "I love pizza 🍕 and coffee ☕!"))

    # Markdown
    probes.append(("markdown-heading", "# Title\n## Subtitle\n### Third"))
    probes.append(("markdown-list", "- item one\n- item two\n- item three"))
    probes.append(("markdown-code", "```python\nprint('hi')\n```"))
    probes.append(("markdown-bold", "**bold** and *italic* and `code`"))
    probes.append(("markdown-link", "[link](https://example.com/path?q=1)"))
    probes.append(("markdown-table", "| a | b |\n|---|---|\n| 1 | 2 |"))

    # Code snippets
    probes.append(("code-python", "def f(x):\n    return x * 2 + 1\nprint(f(5))"))
    probes.append(("code-js", "const f = (x) => x * 2 + 1; console.log(f(5));"))
    probes.append(("code-go", "func f(x int) int { return x*2 + 1 }\nfmt.Println(f(5))"))
    probes.append(("code-rust", "fn f(x: i32) -> i32 { x * 2 + 1 }"))
    probes.append(("code-sql", "SELECT id, name FROM users WHERE age > 18 ORDER BY name;"))
    probes.append(("code-html", "<div class=\"box\"><p>Hello</p></div>"))
    probes.append(("code-shell", "echo 'hello' | grep -c hello"))

    # JSON
    probes.append(("json-simple", '{"name": "Alice", "age": 30}'))
    probes.append(("json-nested", '{"a": {"b": [1, 2, 3]}, "c": true}'))
    probes.append(("json-array", '[{"id": 1}, {"id": 2}, {"id": 3}]'))

    # Base64
    probes.append(("base64-short", "SGVsbG8gV29ybGQ="))
    probes.append(("base64-long", "VGhlIHF1aWNrIGJyb3duIGZveCBqdW1wcyBvdmVyIHRoZSBsYXp5IGRvZy4="))

    # URLs
    probes.append(("url-simple", "https://example.com/"))
    probes.append(("url-path", "https://api.example.com/v1/users/123?limit=10&offset=0"))
    probes.append(("url-percent", "https://example.com/search?q=hello%20world&lang=en"))

    # Very long words
    probes.append(("longword-english", "antidisestablishmentarianism"))
    probes.append(("longword-german", "Donaudampfschifffahrtsgesellschaftskapitän"))
    probes.append(("longword-repeated", "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"))

    # Rare unicode
    probes.append(("rare-unicode", "℘ℑℜ∀∃∄∅∆∇∈∉∋∌∍∎"))
    probes.append(("rare-math", "∑∏∐∫∮∯∰∱∲∳"))
    probes.append(("rare-symbols", "★☆✦✧✩✪✫✬✭✮✯"))
    probes.append(("rare-cjk-ext", "𠮷  𠮷  𠮷"))

    # Repeated punctuation
    probes.append(("punct-repeated", "!!!!????....,,,,;;;;"))
    probes.append(("punct-mixed", "Hello!!! How are you??? I'm fine..."))
    probes.append(("punct-ellipsis", "Wait for it…"))

    # Digits and separators
    probes.append(("digits-plain", "1234567890"))
    probes.append(("digits-grouped", "1,234,567.89"))
    probes.append(("digits-spaced", "1 234 567.89"))
    probes.append(("digits-hex", "0xDEADBEEF"))
    probes.append(("digits-binary", "0b10101010"))
    probes.append(("digits-scientific", "1.23e-45"))

    # Special-token literals (escaped form, not real special tokens)
    probes.append(("special-s", "<s>"))
    probes.append(("special-slash-s", "</s>"))
    probes.append(("special-bos", "<|begin_of_text|>"))
    probes.append(("special-eos", "<|end_of_text|>"))
    probes.append(("special-im-start", "<|im_start|>"))
    probes.append(("special-im-end", "<|im_end|>"))
    probes.append(("special-inst", "[INST]"))
    probes.append(("special-inst-close", "[/INST]"))
    probes.append(("special-sys", "<<SYS>>"))
    probes.append(("special-glm", "[gMASK]<sop>"))
    probes.append(("special-qwen", "<|assistant|>"))
    probes.append(("special-cl100k", "<|endoftext|>"))

    # Whitespace and control
    probes.append(("ws-tabs", "a\tb\tc\td"))
    probes.append(("ws-newlines", "line1\nline2\nline3"))
    probes.append(("ws-leading", "   leading spaces"))
    probes.append(("ws-trailing", "trailing spaces   "))

    # Mixed scripts
    probes.append(("mixed-scripts", "Hello 世界 мир مرحبا नमस्ते 🌍"))
    probes.append(("mixed-code-prose", "The function returns 42 when x > 0."))

    # Short tokens
    probes.append(("short-a", "a"))
    probes.append(("short-i", "I"))
    probes.append(("short-the", "the"))

    # Repeated words
    probes.append(("repeat-word", "hello hello hello hello hello"))
    probes.append(("repeat-char", "!!!!"))

    # Unicode normalization
    probes.append(("unicode-nfc", "café"))
    probes.append(("unicode-combining", "cafe\u0301"))

    # Quotes
    probes.append(("quotes-curly", "\u201cHello\u201d and \u2018world\u2019"))
    probes.append(("quotes-straight", "\"Hello\" and 'world'"))

    # Extra edge cases
    probes.append(("edge-space", " "))
    probes.append(("edge-single-char", "x"))
    probes.append(("edge-emoji-text", "Hello 👋 world 🌍!"))
    probes.append(("edge-long-sentence", "This is a slightly longer sentence that should tokenize into several pieces."))
    probes.append(("edge-parentheses", "(a + b) * (c - d) / e"))

    return probes


def count_differential(send: Callable[[str], Any], probes) -> dict[str, int | None]:
    """Measure per-probe token counts via base vs base+probe subtraction.

    ``send(text)`` returns a ``Completion``. The BASE prompt is sent once and
    its ``usage.prompt_tokens`` is reused. Returns ``{}`` when BASE fails or any
    completion is a mock replay (zeros are not measurements). A probe whose call
    fails or whose delta is negative/nonsensical becomes ``None``.
    """
    base_completion = send(BASE_PROMPT)
    if not _ok(base_completion):
        return {}
    if _used_mock(base_completion):
        return {}
    base_tokens = _prompt_tokens(base_completion)

    items: list[tuple[str, str]] = []
    for probe in probes:
        if isinstance(probe, str):
            items.append((probe, probe))
        else:
            items.append((str(probe[0]), str(probe[1])))

    result: dict[str, int | None] = {}
    for pid, text in items:
        try:
            completion = send(BASE_PROMPT + "\n" + text)
        except Exception:
            result[pid] = None
            continue
        if not _ok(completion):
            result[pid] = None
            continue
        if _used_mock(completion):
            return {}
        delta = _prompt_tokens(completion) - base_tokens
        if delta < 0:
            result[pid] = None
            continue
        # A wildly large delta is not a real token count for a short probe.
        if delta > 100000:
            result[pid] = None
            continue
        result[pid] = delta
    return result


def compare(counts, candidates, *, local=None):
    """Compare measured counts against candidate vocabularies.

    Two calling shapes:
      - ``compare(counts, candidates, *, local=None)`` -> dict report
      - ``compare(a, b)`` -> float | None agreement between two stored dicts
    """
    # Agreement-between-two-stored-dicts form.
    if isinstance(candidates, dict):
        return _compare_stored(counts, candidates)

    # Mock / empty guard for candidate comparison.
    mock = False
    if not isinstance(counts, dict) or not counts:
        mock = True
    if isinstance(counts, dict) and counts.get("mock"):
        mock = True
    if isinstance(counts, dict) and counts and all(
        (v is None or v == 0) for v in counts.values()
    ):
        mock = True

    if mock:
        return {
            "exact_match": None,
            "matched": 0,
            "total": 0,
            "mae": 0.0,
            "skipped": 0,
            "per_candidate": {},
            "mock": True,
        }

    measured_ids = [pid for pid, v in counts.items() if v is not None]
    skipped = sum(1 for v in counts.values() if v is None)
    total = len(measured_ids)

    if local is None:
        # Lazy import to avoid pulling network at module import time.
        from paparazzi import candidates as _candidates

        local = _candidates.local_counts(list(candidates), probe_strings())

    per_candidate: dict[str, dict[str, int | float]] = {}
    best_name: str | None = None
    best_matched = -1
    best_mae = 0.0
    for name in candidates:
        lc = (local or {}).get(name, {}) if isinstance(local, dict) else {}
        matched = 0
        abs_sum = 0
        n = 0
        for pid in measured_ids:
            if pid not in lc:
                continue
            n += 1
            cand_val = lc[pid]
            meas_val = counts[pid]
            if cand_val == meas_val:
                matched += 1
            abs_sum += abs(int(cand_val) - int(meas_val))
        mae = (abs_sum / n) if n else 0.0
        per_candidate[name] = {"matched": matched, "mae": mae}
        if best_name is None or matched > best_matched or (matched == best_matched and mae < best_mae):
            best_name = name
            best_matched = matched
            best_mae = mae

    exact_match = None
    for name in candidates:
        if total > 0 and per_candidate[name]["matched"] == total:
            exact_match = name
            break

    return {
        "exact_match": exact_match,
        "matched": best_matched if best_matched >= 0 else 0,
        "total": total,
        "mae": float(best_mae),
        "skipped": skipped,
        "per_candidate": per_candidate,
        "mock": False,
    }


def _compare_stored(a: dict, b: dict) -> float | None:
    if not isinstance(a, dict) or not isinstance(b, dict):
        return None
    if not a or not b:
        return None
    if a.get("mock") or b.get("mock"):
        return None
    if a.get("used_mock") or b.get("used_mock"):
        return None

    measured = 0
    agree = 0
    for key in a:
        if key not in b:
            continue
        va = a[key]
        vb = b[key]
        if va is None or vb is None:
            continue
        measured += 1
        if va == vb:
            agree += 1
    if measured == 0:
        return None
    return agree / measured
