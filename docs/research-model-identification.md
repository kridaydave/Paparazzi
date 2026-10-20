# Model identification: what signals are actually available

Research notes for extending paparazzi beyond style features. Sources are primary where possible.

## The short version

No single signal identifies a model. A reliable profile combines several independent families. Ranked by signal strength per dollar:

1. Tokenizer differential (strongest, cheapest, ~200 calls)
2. Infra and error probes (binary, very cheap)
3. Generation metadata and router region (direct evidence when available)
4. Single-token output distributions (cheap, statistical)
5. Knowledge boundary (KBF) (expensive, ~$22 enrollment)
6. Style/behavioral fingerprinting (weak alone, gameable)

Everything else corroborates.

## Signal families

### 1. Tokenizer differential (strongest, cheapest)

OpenRouter returns `usage.prompt_tokens` calculated with the model's native tokenizer (docs: "Token counts are calculated using the model's native tokenizer"). A served model adds a constant chat-template overhead per request. Send `BASE` and `BASE + probe`, subtract `prompt_tokens`, the overhead cancels, leaving the model's own token count for the probe string. Compare against candidate vocabularies from Hugging Face.

- Probe set: ~95 strings covering scripts, code, unicode edge cases, special-token literals (escaped), emoji, CJK, etc.
- Candidate tokenizers: load with `transformers.AutoTokenizer` or `tokenizers`, encode each probe with `add_special_tokens=False`, compare counts.
- Result: exact-match count + MAE. The vocabulary with all probes matching is the family.
- Note: vocabulary is family-level evidence, not proof of operator. A vocab can be licensed or forked.
- Special-token literals must be compared in escaped mode because the endpoint escapes them in user content.
- Cost: ~200 short calls, ~1 completion token each.

Reference: iSimplifyMe tokenizer-fingerprint repo and white paper "The Tokenizer Is a Fingerprint"; gist by davedean. This is the method that unmasked ox-alpha.

### 2. Chat-template overhead constant

The constant `prompt_tokens` overhead (base minus probe) identifies the serving template's size. Different labs use different templates. Useful as a second, independent signal.

### 3. Infrastructure and error probes

The serving stack leaks identity through error envelopes, not model personality. Probes:

- `temperature: 2.0` (or out of range) returns validation prose written by the lab's engineers.
- `max_tokens: 1e9` returns a refusal naming the real output limit.
- Invalid role value, malformed JSON, missing fields: numeric vs string vs typed error codes, serde/Java error text, accepted roles.
- GLM's `1301` code exposed ox-alpha. Error format matching Z.ai docs confirmed it.

Modelprint runs 9 such probes and normalizes them. These are binary/structural, not style.

Also inspect HTTP headers and response shape. Gateway noise (Cloudflare, AWS API Gateway, Nginx, Apigee) means headers can lie. Cross-check several.

### 4. Behavioral fingerprinting (style + structure)

The current paparazzi approach. Send a fixed battery of prompts, extract features (emoji/markdown/list/refusal/hedge rates, word counts, counting-quirk miss, maker claims), compare with cosine similarity over z-scaled vectors.

Stronger version: LLM-Fingerprinter (litemars) sends 31 prompts in 3 groups (discriminative, behavioral, stylistic), extracts sentence embeddings + linguistic + behavioral features, and runs an ensemble (Random Forest, SVM, MLP). More systematic than eyeballing style.

Weakness: gameable via system prompts and sampling. Treat as supporting evidence only.

### 5. Single-token output distributions

Bruckner 2026, "One Token Is Enough" (arxiv 2607.10252). Ask a trivial question repeatedly ("say a random number 1-100"), collect single-token answers, build the distribution. Compare distributions with Jensen-Shannon Divergence. Lower = more similar.

- Evaluated on 165 models. EER 7.3% for model verification on a 40-cell probe set.
- Implementation: vivgrid/llm-fingerprinting, matches against a library of 176+ models across 15 probe tasks in 4 languages.
- Cheap: many short calls, temperature > 0 to get variance.

Caveat: deployments, sampling, and provider changes alter distributions. Same model can look different across endpoints.

### 6. Knowledge boundary (KBF)

Fang et al. Fingerprints by stable numerical recall near the knowledge boundary. Common facts carry no signal; far-obscure facts are unstable. The useful regime: the reference commits to a concrete (sometimes wrong) numerical value stably, while substitutes differ.

- Three stages: probe generation (adaptive frontier search across 15 domains), self-calibration (Clopper-Pearson upper bound on reference self-noise), suspect audit (binomial test on discrepancy count).
- Detects all 155 economically relevant substitutions in their eval, no false positives on same-model controls.
- Cost ~$0.39 per audit after ~$22 enrollment.
- Robust to system prompts, temperature, RAG wrappers. Benign queries.
- Non-goal: generic model identification. Tests endpoint consistency against a claimed reference, not "which model in a DB".

### 7. Context limit and needle retrieval

Send increasingly large contexts (100K, 200K, 450K, 1M) with a needle. 200 OK vs error reveals the real context window. Needle retrieval accuracy reveals whether long context actually works. Rules out generation caps (e.g. m2.5 caps at 204800).

### 8. Vision reality and backend mix

For vision-capable claims: color ground truth probes and token-overhead slope across image sizes. Constant overhead across resolutions means a placeholder encoder, not real vision. Repeated identical probes detect mixed backends (backend mix rate).

### 9. Video acceptance

Does the endpoint accept `video_url` natively vs treating mp4 as image? Binary capability signal.

### 10. Latency and throughput

Tokens/sec and time-to-first-token differ by serving stack (Rust gateway vs Python). Noisy but useful corroborating signal. Not identity alone.

### 11. Reasoning tokens

`completion_tokens_details.reasoning_tokens` presence and format. Thinking models leak structure. Some "no model identity provided" strings appear in thinking traces.

### 12. Generation metadata

OpenRouter `/generation` endpoint returns provider name, data region, native token counts. Direct evidence when available. Modelprint uses it.

### 13. Router region metadata

OpenRouter's router opt-in metadata (region, provider, strategy) names who answered. A "Stealth" lane served by Z.AI ends arguments.

### 14. Rate limits

Threshold, time window, response on exceed, headers, scope (IP/user/session/key), recovery. Reveals gateway and provider tier. OWASP LLM10 (unbounded consumption) territory.

### 15. White-box signals (only if weights or logits are available)

Not applicable to pure black-box API probing, but worth knowing they exist:

- TOKENPRINT (arxiv 2608.08139): top-k vocabulary projections of late hidden states over 250 fixed knowledge probes. Requires hidden-state/logit access.
- Gradient-based model fingerprinting (arxiv 2506.01631): pairwise similarity via gradients.
- LLMmap (USENIX Security 25): active fingerprinting with crafted queries + response analysis.
- Chain & Hash (Microsoft): verifiable proof of ownership via Chain-and-Hash.
- Instructional fingerprinting: lightweight instruction tuning to embed a confidential signature.
- SeedPrints (NeurIPS 2025): fingerprints at seed level.
- Weight fingerprinting (Hanlin Tan): detects (near-)identical weights for copy detection.
- UTF (under-trained tokens): uses under-trained tokens as fingerprints.

Paparazzi is black-box only. Keep these as reference for when someone hands us weights.

### Side-channel signals (only if you control the network path)

- Inter-token timing and network traffic analysis (OJCOMS 2025): the rhythm of token delivery differs by serving stack. Needs packet-level access to the connection.
- Memory usage patterns on edge devices (LLM-FIN). Not relevant to remote API probing.

These are reconnaissance extras, not identity proof.

### Targeted and honeypot probes

For verification rather than discovery. Inject an optimized suffix/prefix or a trigger prompt, then check whether the model emits a predetermined response. Tools: TRAP, ProFLingo, RoFL, RAP-SM. Useful once you have a candidate and want to confirm lineage, not for "which model is this".

### Model equality testing

"Model Equality Testing" (ICLR 2025): given two black-box APIs, decide whether they serve the same model. Uses a Hamming Distance Kernel plus Maximum Mean Discrepancy over crafted prompts. Useful for "is stealth-X the same as known-Y" questions, cheaper than full fingerprinting.

### Rank-based and log-rank tests

"Auditing Black-Box LLM APIs with a Rank-Based Uniformity Test" (2025): looks at the log-rank of response tokens and runs a Cramér-von Mises test. Detects substitution or tampering in a served API rather than naming the model.

### Chain-of-thought fingerprinting

CoTSRF (2025): uses the reasoning trace itself as the fingerprint. KL divergence between CoT distributions. Only applies to thinking models that expose reasoning tokens.

### Benchmark

LeaFBench (shaoshuo-ss) is the comprehensive benchmark for evaluating LLM fingerprinting methods. Use it to pick which method to implement rather than guessing.

## What to avoid

- Self-identification probes ("who are you") are frequently bait for stealth models. Do not weight them.
- Style/emoji density alone is gameable.
- Do not fake or hardcode counts. Record failures as failures.
- A single signal is never proof. Combine and report per-signal agreement.

## Proposed changes to paparazzi

1. Add `usage` capture to `openrouter.complete` (return prompt_tokens, completion_tokens, reasoning_tokens, cost). Currently discarded.
2. Add a `tokenizer` probe module: differential counting + candidate comparison. Store measured counts.
3. Add an `infra` probe module: error envelopes, temperature/max_tokens validation prose, headers.
4. Add a `behavioral` probe module: single-token distributions with JSD comparison.
5. Add `context` probe module: context ladder + needle.
6. Extend features/match to combine multiple signal families with explicit weights and report per-signal agreement, not one opaque score.
7. Keep honesty rules: mock runs marked, failures recorded, no hardcoded numbers.

## v0.1.1 scope decisions (from grey-areas map)

Ship:
- Tokenizer differential (primary identity signal).
- Infra/error probes (corroborating).
- Generation metadata + router region (direct evidence when available).
- Context ladder + needle (rules-out filter).
- Reasoning-token capture (free).
- Latency capture when already measured (note only).
- Style/behavioral cosine (supporting only, never published alone).

Defer to v0.2:
- Single-token distributions, KBF, rate-limit probing, targeted/honeypot, equality testing, rank-based, CoT, side-channel, vision/backend, video.

Publish gate (human-in-the-loop): public guess needs tokenizer exact match + one corroborator; display a 0-100 heuristic score; low-confidence guesses shown but labeled; reveals confirmed by first-party sources only.

## Open questions

- Candidate tokenizer set management (fetch from HF, version pinning). 15 candidates in iSimplifyMe's fetch list; MiMo is byte-identical to Qwen2.5.
- Cost budget for KBF-style enrollment (~$22) vs current cents-per-model. Probably skip KBF for v0.1.
- Whether to implement behavioral (single-token) or just tokenizer + infra first. Recommend tokenizer + infra first; behavioral is cheap to add later.
- Rate-limit probing needs care to avoid getting banned. Keep it light.

## Sources

- OpenRouter API reference (usage, native tokenizer): openrouter.ai/docs
- iSimplifyMe tokenizer-fingerprint: github.com/iSimplifyMe/tokenizer-fingerprint
- iSimplifyMe white paper "The Tokenizer Is a Fingerprint"
- davedean probe gist
- majiayu000/stealthprint
- unclecode/modelprint
- Fang et al., KBF: arxiv.org/abs/2605.29524
- "Invisible Traces" arxiv 2501.18712
- Digital Today coverage of ox-alpha unmasking
- PeakCyber, "Know Your Target: LLM Reconnaissance and Model Fingerprinting"
- litemars/LLM-Fingerprinter
- Bruckner, "One Token Is Enough" (arxiv 2607.10252); vivgrid/llm-fingerprinting
- arxiv 2506.01631 (gradient-based fingerprinting)
- LLMmap, USENIX Security 25
- Microsoft Chain & Hash (openreview)
- TOKENPRINT, arxiv 2608.08139
- SeedPrints, NeurIPS 2025
- UTF (under-trained tokens), ACL 2025 LLMSEC
- S1M0N38/llm-fingerprint
- SoK: Large Language Model Copyright Auditing via Fingerprinting (arxiv 2508.19843); shaoshuo-ss/Awesome-LLM-Fingerprinting
- LeaFBench benchmark (shaoshuo-ss)
- Model Equality Testing (ICLR 2025): github.com/i-gao/model-equality-testing
- LLMmap (USENIX Security 25): github.com/pasquini-dario/LLMmap
- TRAP (ACL Findings 2024): github.com/parameterlab/trap
- RoFL: github.com/yunyuntsai/robust_llm_fingerprint
- Invisible Traces (arxiv 2501.18712)
- CoTSRF (arxiv 2505.16785)
- "Your LLMs are Leaving Fingerprints" (COLING 2025 workshop)
- Auditing Black-Box LLM APIs with a Rank-Based Uniformity Test (arxiv 2506.06975)
- "LLMs Have Rhythm" inter-token timing (OJCOMS 2025)