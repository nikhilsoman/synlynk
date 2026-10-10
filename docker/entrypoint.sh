#!/bin/bash
set -e

ENDPOINT="${OMLX_ENDPOINT:-http://host.docker.internal:8000}"

# Write the local harness configuration for the host oMLX endpoint.
mkdir -p .agents
cat > .agents/local.json <<JSON
{
  "name": "local",
  "endpoint": "${ENDPOINT}",
  "models": [
    "Ornith-1.0-9B-4bit",
    "Qwen3.6-27B-4bit",
    "Ternary-Bonsai-2-27B-mlx-2bit"
  ],
  "hardware_tier": "16gb-default",
  "pinned_model": "Ornith-1.0-9B-4bit",
  "max_concurrent": 1
}
JSON

# oMLX may not be running when the container starts, so health failure is
# informational and must not prevent the image from opening.
synlynk local doctor || echo "[sovereign] oMLX not reachable - start oMLX on host first"

if [ -n "${TASK}" ]; then
  exec synlynk dispatch local --task "${TASK}"
else
  exec bash
fi
