#!/usr/bin/env bash
set -euo pipefail

echo "▶ Installing Synlynk..."
if command -v pipx >/dev/null 2>&1; then
    pipx install synlynk --force
elif command -v brew >/dev/null 2>&1; then
    brew install synlynk/tap/synlynk || pip install --user synlynk
else
    pip install --user synlynk
fi
echo "✓ Synlynk installed successfully. Run 'synlynk --version' to verify."
