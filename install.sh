#!/bin/sh

# Script installation into ~/.synlynk/bin is retired; pipx is the only supported method.

CANONICAL_INSTALL="pipx install git+https://github.com/nikhilsoman/synlynk"

if ! command -v python3 >/dev/null 2>&1; then
    echo "Error: python3 is required to install synlynk." >&2
    exit 1
fi

if ! command -v pipx >/dev/null 2>&1; then
    echo "pipx is required to install synlynk." >&2
    echo "Install pipx: https://pipx.pypa.io/stable/" >&2
    echo "Then run: $CANONICAL_INSTALL" >&2
    exit 1
fi

PIPX_HOME_DIR=${PIPX_HOME:-"$HOME/.local/pipx"}
if [ -d "$PIPX_HOME_DIR/venvs/synlynk" ]; then
    pipx install git+https://github.com/nikhilsoman/synlynk --force
    synlynk viz --install || true
else
    pipx install git+https://github.com/nikhilsoman/synlynk
    synlynk viz --install || true
fi
