Type: research
Status: resolved

## Question

Is KBF-style enrollment (~$22) worth it for a weekend lab? What does it add beyond tokenizer+infra, and what is the minimum viable enrollment cost?

## Answer

No for v0.1. KBF is a relay-audit tool, not a discovery tool: it tests whether a suspect endpoint matches an already-enrolled reference. Paparazzi's job is unmasking unknown stealth slugs, so KBF only helps once tokenizer+infra have narrowed to a within-family candidate. It does not replace them.

What KBF adds beyond tokenizer+infra (Fang et al., arxiv 2605.29524):
- Within-family substitutions: catches all 12/12 within-family downgrades where tokenizer differential is blind (same vocab).
- Mixed/partial routing: 95% TPR at 15-34% substitution (budget substitutes) via two-round paired batch test.
- Wrapper robustness: 0/30 FPR across six deployment variants (system prompts, temp 0-0.7, RAG) where style fingerprints false-alarm.
- Benign numerical queries, renewable probes; 0/16 and 0/28 FPR on same-reference controls.

Costs: full 16-model enrollment ~$22 one-time (May 2026 run: 6 T1 refs, 3,696 probes, $7.07; ~$22 total). Audit after enrollment is cheap: $0.24 (Claude Opus 4.6) to $0.67 (GPT-6 Astra) per audit.

Minimum viable enrollment: ~100 retained probes on a single reference (ablation's stated minimum; specialist generation hits this in 60 rounds). Cheapest single ref in the data is Qwen3.5-397B-A17B at $0.31 (448 probes, May run) and Qwen3.5-9B-class budget refs at $0.10/$0.15 per M tokens. Skip contrastive screening for budget refs (paper does). Reuse fingerprints across audits of the same version. So a weekend-lab MVP is cents to ~$0.31 for one ambiguous within-family candidate, not $22.

Recommendation: ship tokenizer + infra first (per research doc open questions); defer KBF to v0.2, gated on a suspected within-family downgrade case. Revisit if a stealth slug's tokenizer matches a known family but infra/identity disagree.

Context pointer: docs/research-model-identification.md §6 (KBF) and map.md out-of-scope notes; Fang et al. arxiv.org/abs/2605.29524.
