Type: research
Status: resolved

## Question

Can a stealth provider defeat these signals? What would it take (change template, add noise, mix backends, swap tokenizer) and how detectable is each countermeasure? Find literature on attacks against fingerprinting.

## Answer

Short answer: yes for the soft signals, no for the hard ones, if paparazzi combines them. A provider can cheaply break style/behavioral and single-token-distribution fingerprints with output rephrasing or temperature, and can spoof behavioral fingerprints by fine-tuning a weak model to mimic a strong one (GhostPrint). But tokenizer differential, infra/error probes, KBF, context limits, and router metadata are structural/identity-bearing: defeating them requires changing the actual serving stack or model, which is expensive and leaves traces. The literature mostly attacks backdoor/intrinsic fingerprints, not these black-box identity signals, and its main lesson (filtering + suppression is cheap; defeating structural signals is not) transfers.

Per-countermeasure detectability:

- Change chat template. Breaks the chat-template overhead constant (signal 2) and can shift token counts only if the tokenizer changes too. Detectable: overhead drift across repeated probes; template size is itself a signal; stealthprint/infra probes catch envelope changes. TemplateFuzz/BadTemplate show templates are a real attack surface, but a provider changing template for evasion changes a measurable constant. Cost: low, but creates a temporal inconsistency paparazzi can flag.

- Add output noise / rephrase. Defeats behavioral style (signal 4) and single-token distributions (signal 5) via temperature, paraphrase filters, or output rephrasing. Kurian et al. (ACSAC CSET 2025): a random filter model rephrasing outputs dropped LLMmap accuracy from 90-100% to 5-45%, at the cost of latency and semantic drift. Detectable: latency increase, semantic fidelity loss, perplexity shifts, and inconsistent answers on deterministic prompts. Does not touch tokenizer/infra/KBF.

- Mix backends. Defeats single-token distributions and vision/backend signals by routing; creates variance in answers and infra probes. Detectable: repeated identical probes expose backend mix rate (signal 8); error envelopes and headers differ across backends; context-limit ladder reveals caps. Cost: operational complexity; leaves a measurable mix signature.

- Swap tokenizer. Defeats tokenizer differential (signal 1) only if the new vocab is not in the candidate set; a forked/licensed vocab can cause false family matches. Detectable: all-probes-match count drops or candidate ranking changes; special-token literals and escaped-mode comparison catch partial swaps; temporal drift in measured counts. Cost: high and risky, since a mismatched tokenizer degrades model quality (TokSuite). Also does not change infra envelopes or KBF.

- Filter fingerprint queries (perplexity/input detection). Works against intrinsic/GCG fingerprints (Nasery et al., arxiv 2509.26598: perplexity filtering of unnatural queries with minimal utility loss). Does not apply to paparazzi's probes, which are natural-language, low-perplexity strings. Detectable: not needed; our probes pass the filter.

- Spoof via fine-tuning (GhostPrint, arxiv 2606.16100). A weak model fine-tuned to mimic a strong one evades behavioral fingerprinting under finite query budgets and weak classifiers. Defeated by: tokenizer differential (vocab differs), infra probes (error envelopes differ), KBF (knowledge boundary differs), context limits. So structural signals remain the discriminator.

- Suppress/overconfidence attacks (Nasery et al.). Target memorization-based fingerprints (backdoors), not paparazzi's identity signals. Transferable lesson: output suppression and overconfidence detection are cheap for a host with white-box access, which is exactly why behavioral fingerprints should be supporting evidence only, never proof.

Literature anchors: Nasery et al. "Are Robust LLM Fingerprints Adversarially Robust?" (arxiv 2509.26598) four attack themes (suppress output, detect output, detect input, learn stats) with ~100% ASR on 10 schemes; GhostPrint (arxiv 2606.16100) fingerprint spoofing; inhibitory attacks TFA/SVA (arxiv 2601.04261) ensemble suppression; Kurian et al. ACSAC CSET 2025 rephrasing defense; LLMmap (USENIX Sec 25) mitigations note countermeasures may be challenging/unrealizable for resourceful adversaries; SRAF (arxiv 2505.06304) perplexity hiding in markdown tables shows stealthiness arms race; Perplexity-based filtering and token-level defenses.

Bottom line for paparazzi: keep tokenizer differential + infra + KBF + context as the load-bearing identity signals; treat behavioral/single-token as corroborating and re-run probes over time to catch template/backend/tokenizer drift; never publish on a single family.

Context pointer: docs/research-model-identification.md signal families 1-15 and .scratch/model-fingerprint-grey-areas/map.md.