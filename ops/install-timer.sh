#!/usr/bin/env bash
# Install the daily watch timer for the current user.
#
# Run this once PAPARAZZI_OPENROUTER_KEY exists in .env. Until then the timer
# would only log a failure every day, which is why it is not enabled by default.
set -euo pipefail

here="$(cd "$(dirname "$0")" && pwd)"
unit_dir="${HOME}/.config/systemd/user"

if [[ ! -f "${here}/../.env" ]]; then
  echo "no .env yet: put PAPARAZZI_OPENROUTER_KEY in ${here}/../.env first" >&2
  exit 1
fi

mkdir -p "${unit_dir}"
ln -sf "${here}/watch.service" "${unit_dir}/paparazzi-watch.service"
ln -sf "${here}/watch.timer" "${unit_dir}/paparazzi-watch.timer"

systemctl --user daemon-reload
systemctl --user enable --now paparazzi-watch.timer
systemctl --user list-timers paparazzi-watch.timer --no-pager
