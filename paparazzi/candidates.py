"""Candidate model vocabularies for tokenizer-family attribution.

Closed models (Claude, GPT, and other API-only families) have no public
vocabulary, so they are deliberately absent here: pretending otherwise would
fabricate an attribution. Only open-weight repos whose tokenizer we can fetch
from the Hugging Face Hub are listed.
"""

from __future__ import annotations

from typing import Any

import tokenizers


DEFAULT_CANDIDATES: list[str] = [
    # Qwen family
    "Qwen/Qwen2-7B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen3-8B",
    # Llama family (gated on the Hub; needs HF_TOKEN)
    "meta-llama/Llama-3.1-8B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    # Gemma family (gated on the Hub; needs HF_TOKEN)
    "google/gemma-2-2b-it",
    "google/gemma-2-9b-it",
    # DeepSeek family
    "deepseek-ai/DeepSeek-V2.5",
    "deepseek-ai/DeepSeek-V3",
    "deepseek-ai/DeepSeek-R1",
    # Mistral family
    "mistralai/Mistral-7B-Instruct-v0.3",
    "mistralai/Mistral-Nemo-Instruct-2407",
    "mistralai/Mixtral-8x7B-Instruct-v0.1",
    # Phi family
    "microsoft/Phi-3-mini-4k-instruct",
    "microsoft/Phi-3.5-mini-instruct",
    "microsoft/Phi-4-mini-instruct",
    # GLM family
    "THUDM/GLM-4-9B-0414",
    "zai-org/GLM-4-9B-0414",
    "zai-org/GLM-4.5",
    "zai-org/GLM-4.5-Air",
    "zai-org/GLM-5",
    # Yi family
    "01-ai/Yi-1.5-9B-Chat",
    "01-ai/Yi-1.5-34B-Chat",
    # Cohere family (gated on the Hub; needs HF_TOKEN)
    "CohereForAI/c4ai-command-r-v01",
    "CohereForAI/c4ai-command-r-plus",
    # Other open families
    "XiaomiMiMo/MiMo-7B-RL",
    "tiiuae/Falcon3-7B-Instruct",
]


def load(name: str) -> tokenizers.Tokenizer:
    """Load a candidate tokenizer from the Hugging Face Hub (standard cache).

    Download failures are re-raised as a RuntimeError that names the repo id.
    """
    try:
        return tokenizers.Tokenizer.from_pretrained(name)
    except Exception as exc:  # network, auth, missing repo, ...
        raise RuntimeError(
            f"could not load tokenizer for candidate repo id {name!r}: {exc}"
        ) from exc


def local_counts(names, probe_texts) -> dict[str, dict[str, int]]:
    """Offline reference counts: encode every probe for each candidate.

    ``probe_texts`` may be a list of (id, text) tuples (as returned by
    ``probe_strings()``) or a list of plain strings (used as both id and text).
    Encoding uses ``add_special_tokens=False``.
    """
    probes: list[tuple[str, str]] = []
    for item in probe_texts:
        if isinstance(item, str):
            probes.append((item, item))
        else:
            pid, text = item[0], item[1]
            probes.append((str(pid), str(text)))

    result: dict[str, dict[str, int]] = {}
    for name in names:
        tokenizer = load(name)
        counts: dict[str, int] = {}
        for pid, text in probes:
            encoding = tokenizer.encode(text, add_special_tokens=False)
            ids = getattr(encoding, "ids", encoding)
            counts[pid] = len(ids)
        result[name] = counts
    return result
