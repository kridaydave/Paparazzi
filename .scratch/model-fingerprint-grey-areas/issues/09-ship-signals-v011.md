Type: grilling
Status: resolved
Blocked by: 01, 02, 03, 04, 05, 06, 07

## Question

Given the research, which signal families ship in paparazzi v0.1.1, and which defer? Decide per family with reasons.

## Answer

Ship in v0.1.1:
- Tokenizer differential (primary identity signal; strongest, cheapest; 0/14 all-match FP).
- Infra/error probes (corroborating binary signal; unwrap metadata.raw; cross-check headers/status/code shape).
- Generation metadata + router region (direct evidence when available; never count absence as negative).
- Context ladder + needle (rules-out filter for context caps; not a published score).
- Reasoning-token capture (free; leaks structure/identity strings).
- Latency/throughput (capture when already measured; do not probe for it).
- Style/behavioral cosine (keep computing, supporting only; never published alone).

Defer:
- Single-token output distributions (v0.2; ~1200 calls/model, EER 7.3-10.6%, 29% provider divergence; vulnerable to rephrasing).
- KBF (v0.2; relay-audit only; gated on suspected within-family downgrade; ~$0.31 min reference).
- Rate-limit probing (skip; ban risk; not identity).
- Targeted/honeypot, model equality testing, rank-based uniformity, CoT fingerprinting, side-channel (defer; verification/research extras).
- Vision/backend, video acceptance (defer; text-only lab for now).

Rationale: load-bearing identity = structural signals (tokenizer, infra, metadata). Corroboration = context, reasoning tokens, latency. Everything behavioral or statistical waits until v0.2.

Context pointer: docs/research-model-identification.md; .scratch/model-fingerprint-grey-areas/issues/01-08.md.