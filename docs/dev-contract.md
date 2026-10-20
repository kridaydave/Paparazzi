# Dev contract for the v0.1.1 fan-out

Read this before writing code, then read `paparazzi/db.py` and `paparazzi/types.py`. It exists so six workers can run at the same time in one repo without stepping on each other.

**Status note:** the fan-out is done and integrated, so the ownership table is
now history. The API shapes below are still the reference, plus these
integrations the contract did not anticipate: `probe.know` runs every family
and stores the signature, `probe.run_all` is what `paparazzi probe` calls, a
guess row carries `meta.used_mock`, and `db.connect()` honors `PAPARAZZI_DB`
when no path is given.

## Hard rules

- Do not run `git commit`, `git add`, or touch `.git`. Changes stay uncommitted, Kriday commits them.
- Only write the files in your ownership row. Shared files below are done and off limits. If you need a change in a file you do not own, put the need in your final report instead of editing it.
- No hardcoded results, no fake test output, no tautological asserts. A failing test exits non-zero. A missing dependency gets marked `[SKIP]` and never prints `PASSED`.
- Mock runs store `used_mock=1`. A failed API call is stored as a failed run and the command exits non-zero after the row is written.
- Every number the page shows must come from a real call or a fixture that says it is a fixture.

## Ownership

| Worker | Owns |
| --- | --- |
| core | `paparazzi/cli.py`, `paparazzi/__main__.py`, `paparazzi/config.py`, `data/battery.yaml`, `data/fixtures/canned.json`, `requirements.txt`, `.gitignore`, `tests/test_cli.py`, `tests/test_config.py` |
| client | `paparazzi/openrouter.py`, `paparazzi/probe.py`, `paparazzi/probes/__init__.py`, `paparazzi/probes/infra.py`, `tests/test_openrouter.py`, `tests/test_infra.py` |
| tokenizer | `paparazzi/probes/tokenizer.py`, `paparazzi/candidates.py`, `tests/test_tokenizer.py` |
| extras | `paparazzi/probes/generation.py`, `paparazzi/probes/context.py`, `tests/test_generation.py`, `tests/test_context.py` |
| match | `paparazzi/features.py`, `paparazzi/match.py`, `paparazzi/report.py`, `tests/test_match.py`, `tests/test_report.py` |
| research | `docs/research-open-questions.md` only |

Shared, already written, do not edit: `paparazzi/__init__.py`, `paparazzi/types.py`, `paparazzi/db.py`, `paparazzi/battery.py`, `docs/dev-contract.md`.

The static page lives in the `paparazzi-website-ui` worktree and belongs to another session. Do not create or edit `docs/index.html`. Under `docs/`, match owns nothing, the report writes `docs/data.json`, and research owns `docs/research-open-questions.md`.

## The import rule that keeps you unblocked

Another worker may not have written their file yet. So:

- Import shared modules (`types`, `db`, `battery`) at module top level. They exist.
- Import anyone else's module **lazily, inside the function that needs it**, or take it as a callable argument.
- Your tests must never import a file you do not own. Inject a fake instead. Pattern:

```python
def run_battery(model: str, prompts: list[BatteryPrompt], *, send=None, conn=None) -> int:
    if send is None:
        from paparazzi import openrouter  # lazy: client worker may still be writing it
        send = openrouter.complete
```

That way `python3 -m pytest tests/ -q` passes for your own tests right now, not "once everyone is done".

## Environment

System `python3` is 3.14.8 with `requests`, `pyyaml`, `tokenizers` (0.23.3) and `pytest` installed. There is no working `venv` on this box, `ensurepip` is broken, use the system interpreter. Run from the repo root:

```bash
cd /home/kriday/Code/paparazzi && python3 -m pytest tests/ -q
```

## Data model

`paparazzi/db.py` is authoritative: `models`, `state`, `probe_runs`, `responses`, `signatures`, `guesses`, `reveals`. Do not fork the schema into your own DDL. If you need SQL no helper covers, write the SQL in your own module against those tables.

Signatures store one JSON dict per known model under `signals`, with a key per family: `tokenizer`, `infra`, `generation`, `context`, `style`. Each family module also exposes `compare(a: dict, b: dict) -> float | None` returning agreement from 0.0 to 1.0, or `None` when the family has no signal for that pair. The matcher never invents agreement itself.

## Client contract (client worker, used by everyone else)

```python
def complete(model: str, prompt: str, *, temperature: float = 0.0,
             max_tokens: int | None = None, system: str | None = None,
             json_mode: bool = False, mock: bool | None = None,
             prompt_key: str | None = None) -> Completion: ...

def models() -> list[dict]: ...          # GET /models roster
def generation(model: str) -> dict: ...  # GET /generation, {} when unavailable
def infra_probe(model: str, payload: dict, *, mock: bool | None = None) -> Completion: ...
```

`complete` never raises. It returns `ok=False` with `error` set in plain words. The key comes from `PAPARAZZI_OPENROUTER_KEY`; a missing key on a non-mock run is a failure, not a silent skip. Mock mode comes from `mock=` or `PAPARAZZI_MOCK=1` and replays `data/fixtures/canned.json`, which is a flat JSON object mapping an exact prompt text to a canned completion string, with `"__default__"` allowed as the fallback key. Mock completions set `raw["paparazzi_mock"] = True` so `Completion.used_mock` is true.

## Family module contracts

Family modules do pure work. They take callables, return plain dicts, never touch sqlite.

```python
# probes/tokenizer.py
def probe_strings() -> list[tuple[str, str]]: ...   # (probe id, probe text), ~95 of them
def count_differential(send, probes) -> dict[str, int | None]: ...  # probe id -> measured count, None when the probe failed
def compare(counts: dict[str, int], candidates: list[str]) -> dict: ...
def compare(a: dict, b: dict) -> float | None: ...
# compare() result: {"exact_match": str|None, "matched": int, "total": int,
#                    "mae": float, "per_candidate": {name: {"matched": int, "mae": float}}}

# probes/infra.py
def collect(send_payload, model: str) -> dict: ...   # send_payload(payload) -> Completion
def compare(a: dict, b: dict) -> float | None: ...

# probes/generation.py
def collect(generate, model: str) -> dict: ...       # generate(model) -> dict from /generation
def compare(a: dict, b: dict) -> float | None: ...

# probes/context.py
def ladder(send, model: str, sizes=(8_000, 32_000, 128_000)) -> dict: ...
def compare(a: dict, b: dict) -> float | None: ...

# features.py (match worker)
def from_responses(rows: list[sqlite3.Row]) -> dict: ...   # style feature vector
def compare(a: dict, b: dict) -> float | None: ...         # cosine over z-scaled rates
```

`paparazzi/probe.py` (client worker) is the only thing that writes `probe_runs` rows. It opens the db, starts a run, calls the family module with real senders, stores responses plus the family result in the run's `meta`, and finishes the run. Family modules stay importable without a database.

## CLI surface (core worker)

```
python3 -m paparazzi know <slug> [--mock]
python3 -m paparazzi watch [--mock]
python3 -m paparazzi probe <slug> [--mock]
python3 -m paparazzi match <slug> [--mock]
python3 -m paparazzi reveal <slug> <true-name> <source-url>
python3 -m paparazzi report
```

`--mock` maps to `mock=True` down the stack. `report` delegates to `paparazzi.report.write()`. Commands that need another worker's module import it lazily inside the command handler, so `--help` and argument errors never crash on a missing module.

## Matcher contract (match worker)

```python
def evaluate(slug: str, *, conn=None) -> dict | None: ...
def met_bar(report: dict) -> bool: ...
def score(report: dict) -> float: ...   # 0-100 heuristic
```

Weights for `score`, so the number is reproducible instead of vibes: tokenizer 0.5, infra 0.15, generation 0.15, context 0.1, style 0.1. Missing families re-normalize over the families that did produce a signal. Document the weights in the module docstring.

`met_bar` is true only when the tokenizer matched every probe **and** at least one corroborator (generation, infra, or context) agreed at 0.5 or better. Style never counts toward the bar. `met_bar` is always false when the evaluated run was mock (`used_mock=1`), because a fixture replay measures nothing. A `guesses` row is always stored, with `met_bar=0` when the bar is unmet and shown labeled "low confidence, not published as guess". Nothing publishes without a human running `publish_guess`.

## Report JSON (match worker)

`paparazzi/report.py` writes `docs/data.json`:

```json
{
  "generated_at": "2026-10-20T00:00:00Z",
  "counts": {"models": 0, "runs": 0, "failed_runs": 0, "mock_runs": 0, "guesses": 0, "published": 0, "reveals": 0, "hits": 0},
  "models": [{"slug": "", "status": "active", "anonymous": false, "first_seen": "", "last_seen": ""}],
  "guesses": [{"slug": "", "candidate": "", "score": 0, "met_bar": false, "published": false, "per_signal": {}, "created_at": ""}],
  "reveals": [{"slug": "", "true_name": "", "source_url": "", "revealed_at": "", "our_guess": "", "guessed_by_us": false}],
  "runs": [{"id": 0, "slug": "", "kind": "", "ok": true, "used_mock": false, "error": null, "started_at": ""}]
}
```

Write it with `json.dump(..., indent=2, sort_keys=True)` so diffs stay quiet.

## What is deliberately not built here

Single-token distributions, KBF, rate-limit probing, equality testing, rank tests, CoT fingerprinting, vision and video probes, latency probing for its own sake. Those are v0.2. Do not start them.
