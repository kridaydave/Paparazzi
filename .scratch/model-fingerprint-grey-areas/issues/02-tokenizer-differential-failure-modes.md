Type: research
Status: resolved

## Question

How many candidate tokenizers does the differential need, and when does it fail? Cases: forked vocab, licensed vocab, byte-identical families (MiMo/Qwen2.5), template changes. What is the false-positive rate of "all probes match" across candidate sets?

## Answer

Candidate count (iSimplifyMe tokenizer-fingerprint; paper "The Tokenizer Is a Fingerprint", 2026-08-22/31):
- Fetch list has 15 entries but 14 distinct hypotheses: `XiaomiMiMo/MiMo-7B-RL`'s `tokenizer.json` is byte-identical (same MD5) to `Qwen/Qwen2.5-72B-Instruct`, so MiMo collapses into the Qwen family. Kimi K2 is the only tiktoken-format candidate, reconstructed with its published pre-tokenization pattern.
- Need at least the suspected family plus one plausible alternative/outgroup; a useful attribution set covers every lab the speculation names plus outgroups (paper used 14 distinct). Duplicates add no discriminating power.

When the differential fails:
- Forked vocab: only detects the fork if merges changed. GLM-4.5 vs GLM-5 shows this: the 11 GLM-4.5 "misses" were GLM-5's shipped improvements, so a fork that only reuses the merge core scores 95/95 and is indistinguishable at vocab level. Template/infra signals are then needed to separate generations.
- Licensed vocab: tokenizer identity is lineage, not operator. A licensee or third party can serve the same vocabulary, so an all-match is a false positive for "who serves it" unless corroborated by runtime/infra probes.
- Byte-identical families: MiMo, Qwen2.5, and Qwen3 all score identically in `results/rank_full.json` (26/95 exact, MAE 5.14). The differential cannot split them; collapse to one hypothesis and rely on non-tokenizer signals.
- Template changes: `prompt_tokens(BASE+probe) - prompt_tokens(BASE)` cancels overhead only if the template is constant. Ox Alpha's `pt_base` was 92 and re-verified before the expanded run; the harness aborts on drift. Escaping also masks membership: special-token literals measure plain-BPE segmentation and only match 23/25 for the true GLM-5.2 vocab, so requiring all 25 on specials would false-negative the real family.

False-positive rate of "all probes match":
- Across the tested 15-candidate set, only `glm52` (Zhipu GLM-5.2, added post-publication) hits 95/95 (MAE 0.00). No other candidate matches all 95: best original candidate GLM-4.5 reached 84/95, next Llama-3.1 46/95. Empirical FP rate = 0/14 distinct candidates (0%) for a full 95-probe all-match.
- If the true vocabulary is absent from the candidate set, the method returns the nearest (e.g. 84/95) rather than a false all-match, so the all-match gate fails safe (no match) but can still misattribute by nearest-neighbor.
- Do not require all 25 special probes: escaping makes the true vocab score 23/25. Use all-match on the 95 text probes; treat specials as a separate, escaping-aware check.

Context pointer: docs/research-model-identification.md sections 1, 2, 3, 4, 5, 8; iSimplifyMe/tokenizer-fingerprint (`expand.py`, `results/rank_full.json`, `results/glm5_followup.json`, `results/battery2.json`).