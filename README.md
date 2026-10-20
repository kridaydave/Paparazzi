# paparazzi

Anonymous models on OpenRouter ("stealth" slugs) get probed, fingerprinted and
unmasked against known-model signatures. Zero infra, one sqlite file, one static
page. Every claim on the page comes from a real api call or a clearly labeled
fixture replay; failures are recorded as failures.

## Status

**Weekend-lab v0.1.** The matcher is deliberately dumb and honest: stylistic
feature rates z-scaled cosine similarity over a fixed probe battery. It has
never run against a live stealth model yet. Expect it to be wrong until proven
otherwise in public.

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

# offline dev / self-test
python3 -m paparazzi know fixture/timidy --mock

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
3. The stealth vector is compared (cosine, z-scaled) to signatures of known
   models. Best match + confidence gap = the guess, logged to sqlite.
4. `watch` diffs OpenRouter's public model list against the db: new stealth
   slugs in, rotated-off slugs marked gone.

## Honesty rules

- Fixture mode replays `data/fixtures/canned.json`, which is synthetic text,
  and marks every such run `used_mock=1` (visible in the page's error counts).
- A failed api call is recorded as a failed run and exits nonzero. Nothing
  pretends.
- Scores are heuristic similarity, not proof. Only confirmed `reveal` entries
  count as track record, and `guessed_by_us` is only set when a logged guess
  actually named the revealed model.

## Open items

- live key wiring + first real probe run
- a cron/systemd timer for `watch`
-.gitignore + CI later
