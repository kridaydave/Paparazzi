# Map: Model fingerprinting grey areas

## Destination

Decide which signals paparazzi ships in v0.1.1, with calibrated confidence thresholds and explicit deferrals, so the matcher stops being "dumb and honest" only by accident.

## Notes

- Domain: LLM black-box fingerprinting for paparazzi (Python, sqlite, static page).
- Skills every session should consult: research (for AFK research tickets), grilling + domain-modeling (for HITL decision tickets).
- Standing preference: keep honesty rules (mock marked, failures recorded, no hardcoded numbers). Prefer cheap signals first.

## Decisions so far

- [Ship signals in v0.1.1](.scratch/model-fingerprint-grey-areas/issues/09-ship-signals-v011.md): ship tokenizer differential, infra probes, generation metadata+router region, context ladder, reasoning tokens, latency capture; keep style as supporting-only; defer single-token, KBF, rate-limit probing, and verification extras.
- [Publish threshold](.scratch/model-fingerprint-grey-areas/issues/10-publish-threshold.md): public guess needs tokenizer exact match + one corroborator; display a 0-100 heuristic score; low-confidence guesses shown but labeled; reveals confirmed by first-party sources only; human gate before publishing.

## Not yet specified

- Vision-claim verification for a text-only probe lab: do we need it, and how cheaply?
- Temporal drift: how to detect a provider changed tokenizer/template mid-preview.
- Rate-limit probing policy: how light is light enough to avoid bans.
- Whether to ship single-token behavioral fingerprinting in v0.1.1 or defer.

## Out of scope

- Weight-level fingerprinting (TOKENPRINT, HuRef, etc.): no weights available.
- Legal advice on unmasking stealth models: record facts only, no counsel.