#!/bin/bash
# gh:#2649 — a fresh runner ledger sometimes fails its first write reservation.
# Retry that disk I/O error once against a new explicit ledger. Any other
# failure, including a second disk I/O error, fails the job.
set -euo pipefail

if [ -z "${SYNLYNK_STATE_DB_PATH:-}" ]; then
  echo "SYNLYNK_STATE_DB_PATH is required" >&2
  exit 1
fi
if [ "${SYNLYNK_ALLOW_STATE_DB_FALLBACK:-}" = "1" ]; then
  echo "refusing SYNLYNK_ALLOW_STATE_DB_FALLBACK" >&2
  exit 1
fi

mkdir -p "$(dirname "$SYNLYNK_STATE_DB_PATH")"
log="${RUNNER_TEMP:-/tmp}/synlynk-nudge.log"

for attempt in 1 2; do
  if python3 bin/synlynk.py harness run workspace-lifecycle-nudge >"$log" 2>&1; then
    cat "$log"
    exit 0
  fi
  cat "$log" >&2
  if [ "$attempt" -eq 2 ] || ! grep -q "disk I/O error" "$log"; then
    exit 1
  fi
  rm -f \
    "$SYNLYNK_STATE_DB_PATH" \
    "${SYNLYNK_STATE_DB_PATH}-wal" \
    "${SYNLYNK_STATE_DB_PATH}-shm" \
    "${SYNLYNK_STATE_DB_PATH}-journal"
done
