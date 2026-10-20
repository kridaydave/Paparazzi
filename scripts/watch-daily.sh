#!/usr/bin/env bash
# Daily roster refresh: what is new on OpenRouter, what rotated off.
# Exits non-zero when the call fails, because a failed watch is not a quiet watch.
set -euo pipefail

cd "$(dirname "$0")/.."

# .env holds PAPARAZZI_OPENROUTER_KEY and is gitignored, so the key stays off
# the unit file, the command line, and the shell history.
if [[ -f .env ]]; then
  set -a
  # shellcheck disable=SC1091
  source .env
  set +a
fi

exec python3 -m paparazzi watch
