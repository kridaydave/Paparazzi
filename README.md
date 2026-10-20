# paparazzi

Anonymous models on OpenRouter ("stealth" slugs) get probed, fingerprinted and
unmasked against known-model signatures. Zero infra, one sqlite file, one static
page. Every claim on the page comes from a real api call or a clearly labeled
fixture replay; failures are recorded as failures.

## Status

**v0.1.1, wired up and offline-tested, never run against a live model yet.**
The command surface works end to end in fixture replay mode (`--mock`), with
every run marked `used_mock=1` and no guess meeting the publish bar. What has
never happened is a real key pointed at a real stealth slug, so the matcher is
still wrong until proven otherwise in public.

Signals in this version: tokenizer differential as the primary identity
signal, infra/error envelopes, generation metadata, a context ladder, style
cosine as support only. Decisions and the publish bar are written up in
`docs/research-model-identification.md` and `.scratch/model-fingerprint-grey-areas/`.
Module contracts and how the pieces fit are in `docs/dev-contract.md`.

## Use

```bash
pip install -r requirements.txt

# fingerprint known models once (needs a key, costs cents per model)
export PAPARAZZI_OPENROUTER_KEY=sk-or-...
python3 -m paparazzi know anthropic/claude-haiku-5.5
python3 -m paparazzi know deepseek/deepseek-v4.1-flash

# daily: refresh roster, probe anything new + anonymous
python3 -m paparazzi watch          # flags new stealth/anon slugs, notes rotated-off ones
python3 -m paparazzi probe stealth/whatever-alpha
python3 -m paparazzi match stealth/whatever-alpha   # ranked guesses -> db -> page
python3 -m paparazzi reveal stealth/whatever-alpha <true-name> <source-url>   # after the lab confirms

# offline dev / self-test (no key, no network)
python3 -m paparazzi know fixture/timidy --mock
python3 -m pytest tests/ -q

# the page
python3 -m paparazzi report && open docs/index.html   # or any static server
```

After a `reveal`, the reveals table shows whether our earlier guess hit. That
table is the only thing that matters. Everything else is scaffolding for it.

## How it works (plain english)

1. `data/battery.yaml` holds a fixed set of prompts (identity, style, quirks,
   refusals). One cheap completion per prompt, temperature 0.
2. Responses become a small feature vector: emoji/markdown/list/refusal/hedge
   rates, word counts, a counting-quirk miss check, explicit maker claims.
   Style is support only, never enough to publish.
3. `know` also measures how the model tokenizes ~95 probe strings (this is the
   load-bearing signal), captures error envelopes, generation metadata and a
   context ladder. `match` compares a stealth slug against every stored
   signature using fixed weights: tokenizer 0.5, infra 0.15, generation 0.15,
   context 0.1, style 0.1, renormalized over families that produced a signal.
4. A public guess needs a full tokenizer match plus one corroborator, and a
   human approves it. Fixture replays can never meet that bar.
5. `watch` diffs OpenRouter's public model list against the db: new stealth
   slugs in, rotated-off slugs marked gone. An empty roster marks nothing, so
   a failed fetch cannot write a lie.

## Honesty rules

- Fixture mode replays `data/fixtures/canned.json`, which is synthetic text,
  and marks every such run `used_mock=1` (visible in the page's error counts).
- A failed api call is recorded as a failed run and exits nonzero. Nothing
  pretends.
- Scores are heuristic similarity, not proof. Only confirmed `reveal` entries
  count as track record, and `guessed_by_us` is only set when a logged guess
  actually named the revealed model.

## Open items

- live key wiring + first real probe run: put `PAPARAZZI_OPENROUTER_KEY` in
  `.env`, then `python3 -m paparazzi know <slug>` for real
- `bash ops/install-timer.sh` to turn on the daily watch (it refuses to
  install without a key, so it cannot fire failures at you beforehand)
- CI file is in `.github/workflows/ci.yml`; it starts running once this repo
  has a remote to push to
- candidate vocabularies: some Hugging Face repos are gated and want `HF_TOKEN`,
  so a real tokenizer run needs one or needs those candidates dropped
