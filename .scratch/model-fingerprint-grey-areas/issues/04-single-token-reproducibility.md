Type: research
Status: resolved

## Question

How reproducible are single-token output distributions (Bruckner 2026) across endpoints, temperatures, and days? What sample size and JSD threshold give stable verification, and how do deployments differ?
## Answer

Reproducibility (Bruckner 2026, arXiv:2607.10252; 165 models, 40-cell battery, OpenRouter census):

- Within one deployment: median cell-level JSD between two time-interleaved halves of the same model's samples is 0.075, vs 0.489 between different models (6,564 genuine vs 1.07M impostor cell trials). Aggregated full battery: AUC 0.971, EER 7.3%.
- Across endpoints/deployments: 31 models served by two or more providers (34 pairs, >=15 shared cells each). Median cross-provider JSD 0.227: above the single-deployment split-half noise floor (0.140) but below the impostor median (0.463); 70.6% of pairs stay below the 5th percentile of impostor distances. Cross-provider verification AUC 0.880 vs 0.971 same-provider mix. The fingerprint largely survives serving-stack changes, but provider matters.
- Temperature: standard collection is T=1.0 (30 reps/cell; 15 for models priced >=$5/1M input). At T=0, 90.4% of cells are deterministic within a provider and 84.5% pooled across providers; the gap is serving-stack variance. T=0 fingerprints are analyzed the same way. No separate T=0 EER is reported.
- Days/time: only short-horizon stability is quantified via repetition-parity, time-interleaved split halves. No multi-day or multi-week drift experiment is reported; the paper states fingerprints drift with model updates and reference enrollment must be refreshed. Collection window is not stated in days beyond the catalog snapshot 2026-07-06.

Sample size and JSD threshold for stable verification:

- Battery is 10 tasks x 4 languages = 40 cells; n=30 per cell (n=15 for frontier-priced models); at least 10 valid samples per cell; 165 models. A full fingerprint costs ~1200 single-token calls per model (~600 for frontier models).
- Verification score is mean JSD over k sampled cells; accept if score <= tau. Full 40 cells: EER 7.3% (AUC 0.971). 8 cells: EER 10.6%. 16 cells: 9.5%. The curve flattens around k=16-24. At k=16 with 15 reps/cell cost is 240 single-token queries.
- The paper reports ROC/EER rather than a single tau. A conservative operational default in the reference implementation is tau=0.10 for verify (raise it with fewer samples). For distinctness/collision screening the reference implementation uses 0.35 mean JSD.
- Practical stable operating point: k>=8 (prefer 16), n>=15-30 per cell, yielding EER roughly 9.5-10.6%.

How deployments differ:

- Serving provider shifts fingerprints by a median 0.227, less than half the impostor median 0.463, but 10 of 34 same-model provider pairs (29%) exceed the impostor 5th percentile. Extreme cases: 0.716 for meta-llama/llama-3.2-3b-instruct (Cloudflare vs Parasail) and 0.392 for openai/gpt-4 (Azure vs first-party).
- Opacity/caching: the response-caching screen found no cache signature in the census; 13.4% of requests had prompt-cache hits, which does not change the decoding distribution; 0.76% of responses carried a reasoning trace despite the disable flag across 14 model-provider combos; some flagship endpoints burned ~40-60 tokens per one-word visible answer.
- Identity anomalies: writer/palmyra-x5 sits at distance 0.141 from qwen/qwen3-235b-a22b-2507 (at the median genuine distance 0.140); several vendor models land in the Qwen neighborhood. Heavy post-training can erase lineage (nvidia/llama-3.3-nemotron-super-49b-v1.5 is closer to Qwen at 0.303 than to any Llama checkpoint).

Context pointer: docs/research-model-identification.md section 5; arXiv:2607.10252; vivgrid/llm-fingerprinting.
