Type: grilling
Status: resolved
Blocked by: 07, 09

## Question

What confidence threshold and evidence bar should a guess meet before it appears as a "guess" on the public page, and how is "confirmed" defined for reveals?

## Answer

Evidence bar for a public guess: tokenizer exact match (95/95 on the probe battery) plus at least one corroborating family (generation metadata match, infra probe, or context-cap consistency). If tokenizer is inconclusive (nearest-neighbor only, no all-match), no public guess.

Confidence display: a single 0-100 heuristic score computed from weighted signal agreement, shown on the page. Treated as a heuristic score, not a calibrated probability (no false precision claims; honesty rules apply).

Low-confidence display: when a guess doesn't meet the bar, show the top match labeled "low confidence, not published as guess" rather than suppressing.

Confirmed reveal: first-party sources only — OpenRouter's own pages/blog/X or the lab's own channel. Community speculation, benchmark runs, and fingerprinting analysis do not confirm. The reveals table stays strict.

Publishing gate: human-in-the-loop. The system auto-suggests a guess when the bar is met; a human approves before it appears on the page. Matches the existing `reveal` command flow.

Context pointer: docs/research-model-identification.md; issues 07 and 09.