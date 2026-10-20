Type: research
Status: resolved

## Question

What are the ethics and ToS implications of unmasking stealth models on OpenRouter? Does OpenRouter prohibit it? Are there documented takedowns or community norms? Record facts only.

## Answer

Facts from OpenRouter's published terms (ToS last updated 2026-08-31; Stealth EULA last updated 2026-09-14):

- No clause names "unmasking" or identity disclosure. OpenRouter itself later reveals providers on model pages/blog (e.g., Ox Alpha -> GLM-5.3-Flash; Space Bunny Alpha -> MiniMax M3.1 Flash).
- Stealth EULA AUP (Exhibit A) does prohibit: (v) reverse engineering/decompiling/disassembling/seeking source code; (vi) extracting data except as expressly permitted; (viii) publicly disseminating confidential technical information regarding performance of Stealth Models; (ix) circumventing filtering/safety; (iv) bypassing rate limits/excessive usage; (vii) removing notices.
- Base ToS 7.10 prohibits reverse engineering source code of the Service; 7.11 prohibits Red Teaming (prompt injection/jailbreaking/adversarial actions designed to compromise models or violate Model Terms) without prior written approval; 7.5 prohibits scraping/crawling; 5.7 prohibits circumventing Restricted Model safeguards; 9 allows suspension/termination at sole discretion.
- Tokenizer-count fingerprinting (sending probes and comparing reported token counts) is not source-code reverse engineering and uses normal API outputs; publishing identity theories is common community practice and is not, on the face of the terms, "confidential technical information regarding performance." Publishing benchmark/performance numbers could fall under AUP (viii).
- Data/ethics facts: stealth models usually train on prompts with no selective opt-out; prompts/completions retained; hashed user identifiers; OpenRouter contractually bars providers from re-identifying users; Ox Alpha was the sole no-training carve-out (retention still occurred). OpenRouter disclaims liability for Model Provider data practices.
- Community norms: widespread public fingerprinting (tokenizer, infra, behavioral) and public speculation; official reveals only via first-party channels (OpenRouter blog/X or lab's own channel); fingerprinting has never been the mechanism of an official reveal; style-based fingerprinting considered unreliable; community benchmark runs are n=1/unverified.
- Takedowns: no documented account takedowns or enforcement actions specifically for unmasking/fingerprinting were found in sources. OpenRouter retains contractual right to suspend/terminate for AUP breaches or at sole discretion; red-teaming without approval can lead to provider/model bans and account bans.

Context pointer: map.md (legal advice on unmasking is out of scope; facts only); OpenRouter ToS https://openrouter.ai/terms and Stealth EULA https://openrouter.ai/terms/stealth; digitalapplied.com stealth model census.