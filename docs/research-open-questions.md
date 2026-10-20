# Open questions for paparazzi fingerprinting

Research notes for the four items the grey-areas map left unspecified. Each section states the question, the evidence, and one recommendation. Sources are linked where a number is attached. Claims I could not verify are labeled as such.

## 1. Vision-claim verification for a text-only probe lab

Question: a stealth slug may advertise vision support. What is the cheapest honest check that the claim is real, and should v0.1.1 build it?

Recommendation: do not build it in v0.1.1. Keep vision deferred, as the map and issue 09 already decided. The lab is text-only and the publish gate does not need vision to clear. Add it only if a stealth slug's identity stays unresolved after tokenizer, infra, and context probes, and even then as a v0.1.2 add-on rather than a v0.1.1 ship item.

If we do build it, the honest check is two parts, both cheap.

Color ground truth. Ask the model to name the color of a solid-color image. Use 64x64 or larger. A 1x1 pixel still hallucinates, so judge only on images of at least 64px. The stealthprint case studies report red 5/6 and blue 3/4 or 4/4 correct for real encoders, and wrong colors or refusals for placeholder pipelines.

Token-overhead slope across image sizes. Send the same prompt with images of several sizes and record prompt_tokens. A real vision encoder scales with resolution: stealthprint reverse-engineered union-alpha as prompt_tokens = max(22, ceil(H/28)^2 + 6), fitting 11 of 11 size points with zero error, which is the Qwen2-VL family's 28px-per-token dynamic resolution shape. A placeholder encoder bills a flat overhead regardless of size, for example space-bunny's +34 tokens whether the image is 1x1 or 64x64. Constant overhead means the image is not actually being encoded.

Cost is a few calls per size, well under a cent per model. Repeats of one identical 64x64 probe can surface a mixed backend pool, but stealthprint is explicit that repeats record outcomes, not a model mixing rate, so do not overstate what repeats prove.

What to skip: a dedicated vision module in v0.1.1, video acceptance probing, and any claim that color accuracy alone proves a real encoder. Color plus slope together are the check.

Sources: stealthprint README and case studies (https://github.com/majiayu000/stealthprint), union-alpha case (https://github.com/majiayu000/stealthprint/blob/main/docs/case-union-alpha.md), space-bunny case (https://github.com/majiayu000/stealthprint/blob/main/docs/case-space-bunny.md).

## 2. Temporal drift

Question: a provider swaps tokenizer or chat template mid-preview and every stored signature goes stale. What detects that cheaply, and what count delta counts as drift worth acting on?

Recommendation: detect drift with a scheduled re-run of the structural probes, not with a count-delta threshold on behavioral data. Re-run the tokenizer differential battery, the infra probes, the wrapper offset, and the context ladder against stored baselines on a schedule. Any change in a comparable probe value is a drift flag. This is the cheapest signal that actually names the failure, because tokenizer exact match is the strongest identity signal and its probes cost about 200 short calls.

OpenRouter's /generation endpoint and model-card metadata are useful as an early warning but are not sufficient on their own. There is no official change feed for a model's tokenizer or template. The /models and /generation endpoints expose architecture and provider fields, and the router metadata header exposes region and provider, but those fields can lag or stay identical while the serving stack changes. Treat metadata changes as a trigger to re-run the probe battery, not as proof of drift.

On the alert threshold question, the honest answer splits by signal family.

Structural probes: zero tolerance. Tokenizer exact match is 95 of 95 on the probe battery per the publish gate, so any drop is drift. The wrapper offset is a constant, so any change is drift. The context cap is a hard number, so any change is drift. These are binary and cheap to re-run, so flag on any change.

Behavioral probes: no defensible threshold exists yet. Bruckner 2026 reports that same-model cross-provider deployments have a median JSD of 0.227, different models sit at 0.463, and about 29% of same-model provider pairs diverge more than impostor pairs do, which is 10 of 34 pairs in the paper. That provider-side variance is larger than the drift we would be trying to catch, so a threshold set on behavioral data would either cry wolf on every provider change or miss a real swap. I cannot give a number that survives that variance. Anyone who does is guessing.

Build: a weekly scheduled re-run of tokenizer, infra, wrapper, and context probes against stored fingerprints, with a drift flag on any changed probe value. Store one baseline fingerprint per slug. Skip: daily re-runs, behavioral drift alerts, and automatic republishing of guesses after a drift flag.

Sources: Bruckner, One Token Is Enough (arxiv 2607.10252, https://arxiv.org/abs/2607.10252); alphaXiv overview of the same paper (https://www.alphaxiv.org/overview/2607.10252); ToseaAI implementation notes (https://github.com/ToseaAI/llm-fingerprint-detector); OpenRouter /generation and router metadata docs (https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation, https://openrouter.ai/docs/projects/docs/guides/features/router-metadata); lm-fingerprint drift command (https://gitlab.com/WattoCyber/lm-fingerprint).

## 3. Rate-limit probing policy

Question: how light is light enough to learn something about the gateway without getting banned?

Recommendation: do not probe rate limits at all in v0.1.1. Rate-limit probing is already deferred in issue 09, and nothing in the v0.1.1 identity story needs it. If a future version wants gateway tier information, collect it passively from limits that occur during normal probing rather than by deliberately exceeding them.

The reason is that learning the limit requires triggering a 429. OpenRouter's limits doc states that successful inference responses do not include X-RateLimit-* headers. Those headers appear only on 429 error responses, along with X-RateLimit-Limit, X-RateLimit-Remaining, and X-RateLimit-Reset. A Retry-After header appears when every attempted provider returned a retry hint. So the only way to read the limit is to hit it, which spends quota and risks a block.

The numbers that exist are community-documented, not published on OpenRouter's own limits page. Secondary sources report free-model caps of 20 requests per minute, 50 requests per day for accounts with 10 credits or fewer, and 1000 per day for accounts with 10 or more credits, with limits governed globally per account rather than per key. I could not verify these exact figures against OpenRouter's own documentation, so treat them as unverified.

OWASP's LLM10, unbounded consumption, frames excessive probing as a model-extraction and denial-of-service risk, which is the same shape of behavior we would be doing. The guidance there is rate limiting, quotas, and throttling on the server side, which implies the client side should not be the one stress-testing the limit.

If we ever do collect this passively, the rules are the vendor's own. Honor Retry-After when present. Otherwise use exponential backoff with jitter, for example 2^n seconds plus a random fraction, and do not retry in a tight loop. Do not create extra accounts to multiply limits, since OpenRouter governs capacity globally. Read the limit from the 429 response headers and from GET /api/v1/key for credit and budget state, and stop probing that slug for the day.

Build: nothing in v0.1.1. Skip: dedicated rate-limit probing, out-of-range request floods, account multiplication, and any number presented as an OpenRouter-published limit without verification.

Sources: OpenRouter limits doc (https://openrouter.ai/docs/api/reference/limits); OWASP LLM10 unbounded consumption (https://owasp.org/www-project-top-10-for-large-language-model-applications/2_0_vulns/LLM10_UnboundedConsumption); community figures from https://fast.io/resources/openrouter-rate-limit/ and https://github.com/serjs/openrouter-proxy-injector, both unverified against OpenRouter's own page.

## 4. Single-token behavioral fingerprinting in v0.1.1

Issue 09 deferred single-token distributions to v0.2 on grounds of call volume, error rate, and provider divergence. Re-checking against the current evidence confirms the deferral. Bruckner's paper reports an equal error rate of 7.3% with the full 40-cell battery and 10.6% with 8 cells, which is roughly 100 to 400 single-token calls per audit. That is more calls than the tokenizer differential needs, and the tokenizer gives an exact match rather than a statistical verdict. The same paper reports that same-model cross-provider deployments have a median JSD of 0.227 while different models sit at 0.463, and that 10 of 34 same-model provider pairs diverge beyond the impostor range. Paparazzi's publish gate requires a tokenizer exact match plus one corroborator before a public guess, and a signal that disagrees with itself across providers 29% of the time cannot be that corroborator. The method is also sensitive to quantization and to silent updates, which is exactly the kind of change a stealth preview is likely to undergo. Cost is a few cents per audit, so price is not the blocker. The blocker is that a 7 to 11% error rate on a signal that drifts with the serving stack would put guesses on the public page that the tokenizer cannot back up.

The second reason is sequencing. Paparazzi has not run a single live stealth probe yet. Adding a statistical method with a known error rate before the structural baseline has a reveal track record means we would be calibrating two new things at once. The cheaper and more honest order is tokenizer, infra, and context first, then add single-token distributions in v0.2 as a corroborator with its own track record in the reveals table. The implementation already exists to reuse later: Bruckner's code and dataset on Zenodo, vivgrid/llm-fingerprinting, and ToseaAI/llm-fingerprint-detector. Reversing the deferral would require a measured error rate below the publish gate's tolerance on our own endpoints, and we do not have that measurement yet.

Build: nothing in v0.1.1. Skip: single-token distributions, and any plan to publish a guess backed by behavioral data alone.

Sources: Bruckner, One Token Is Enough (arxiv 2607.10252, https://arxiv.org/abs/2607.10252); ToseaAI/llm-fingerprint-detector (https://github.com/ToseaAI/llm-fingerprint-detector); vivgrid/llm-fingerprinting (cited in docs/research-model-identification.md).

## Also worth deciding

Three items the map does not list but that fall out of the above.

Candidate tokenizer set management. The research doc notes 15 candidates in iSimplifyMe's fetch list and that MiMo is byte-identical to Qwen2.5. Someone needs to own fetching, pinning, and versioning those tokenizer files, and to decide what an exact match means when two candidates are byte-identical. This is a prerequisite for the tokenizer signal to be reproducible, not an open research question.

Whether to store a full fingerprint per slug. Drift detection needs a baseline to diff against. Decide the schema now: one row per slug per probe run, with probe values and a run timestamp, so a future drift job has something to compare to. Without this, the weekly re-run in section 2 has no baseline.

Whether the page shows drift at all. The reveals table is the only thing that matters per the README. A drift flag on a published guess is a strong signal that the guess may be stale, and it should probably appear next to the guess. That is a UI decision worth making before the drift job ships, not after.
