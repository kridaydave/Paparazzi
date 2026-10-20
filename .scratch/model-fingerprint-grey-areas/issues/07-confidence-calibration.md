Type: research
Status: resolved

## Question

What false-positive rates do these signals have in practice, and how should paparazzi calibrate a "confident enough to publish" threshold? Look for reported EERs, base rates, and calibration methods.

## Answer

Reported error rates (primary sources):

- Single-token distributions (Bruckner 2026, arxiv 2607.10252): EER 7.3% full 40-cell battery, 10.6% at 8 cells (~120 queries), 23.3% single cell; AUC 0.971 same-provider, 0.880 cross-provider; cross-provider median distance 0.227 vs impostor 0.463; genuine split-half JSD median 0.075 vs impostor 0.489. 10/34 same-model provider pairs (29%) diverge beyond impostor 5th percentile, so deployment noise alone can mimic an impostor.
- KBF (Fang et al., arxiv 2605.29524): 0 false positives on same-model controls across 16 endpoints; 0/30 under 6 benign config variations; flags all 155 substitutions at p<0.05 including 12 within-family downgrades; mixed routing detected at 5-10% substitution. Self-calibration: Clopper-Pearson one-sided upper bound (gamma=0.99) on reference self-noise p0, then binomial test on suspect discrepancy count.
- Model Equality Testing (Gao et al., ICLR 2025): MMD string-kernel test, median 77.4% power, 11/31 commercial endpoints deviated from reference weights. Type-I controlled by permutation p-values.
- Rank-based uniformity test (Zhu et al., arxiv 2506.06975): type-I error controlled at alpha=0.05 by construction (Cramér-von Mises); power AUCs 0.05-0.99 by substitution type; 8-bit quantization largely undetected.
- LLMmap (Pasquini et al., USENIX 2025): >95% on 42 models with 8 queries, but exact rate drops 61.54% to 17.95% under restrictive system prompts. Not a calibrated FPR; robustness degrades sharply.

Base rates matter: anomalies are common (29% provider-pair divergence, 7/27 shadow cells inconsistent, one flagship indistinguishable from Qwen), so an uncalibrated "publish" over-claims. Paparazzi must not treat any single deviation as proof.

Calibration methods to adopt:

- Measure reference self-noise first, then set the null tolerance from it (KBF pattern): self-test discrepancy count k_self over n enrolled probes, p0 = CP_gamma(k_self, n), audit rejects only when suspect count exceeds the binomial tail at p0. Precision-first: FPR is the safety metric.
- Use biometric-style ROC/EER only as a summary, not the operating point (Bruckner): report the threshold and both rates; pick an operating point that favors low FAR for public claims, following NIST-style "FNMR at fixed FMR" reporting. EER 7.3% is too loose to publish on alone.
- For small samples report Wilson/CP intervals, not point estimates.
- Require independent-family convergence before publishing: a strong binary signal (tokenizer exact match or infra probe) plus at least one corroborating family (single-token JSD below impostor 5th percentile with >=8-16 cells, or KBF-style binomial rejection), backed by a calibrated test (p<0.05 or CP-bound rejection).
- Style/cosine similarity alone never publishes; it has no reported FPR and is gameable.
- Refresh enrollment on drift; stale thresholds are worse than none.

Context: paparazzi matcher is heuristic cosine over style features; see docs/research-model-identification.md and issues 01-06.