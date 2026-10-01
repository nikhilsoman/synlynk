#!/bin/sh
set -e

CANONICAL_SPEC=${SYNLYNK_INSTALL_SPEC:-"git+https://github.com/nikhilsoman/synlynk.git"}
INSTALL_DIR=${SYNLYNK_HOME:-"$HOME/.synlynk"}
BIN_DIR="$HOME/.local/bin"

# Percent formatting: interpreters older than 3.6 still print a version
# instead of dying on an f-string SyntaxError before the floor check.
python_version() {
    python3 -c 'import sys; print("%d.%d" % (sys.version_info[0], sys.version_info[1]))'
}

if [ "${1:-}" = "--check-prereqs" ]; then
    if ! command -v python3 >/dev/null 2>&1; then
        echo "Error: python3 >= 3.10 is required." >&2
        exit 1
    fi
    if ! PY_VER=$(python_version); then
        echo "Error: python3 >= 3.10 is required." >&2
        exit 1
    fi
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ne 3 ] || [ "$PY_MINOR" -lt 10 ]; then
        echo "Error: python3 >= 3.10 is required (found Python $PY_VER)." >&2
        exit 1
    fi
    exit 0
fi

echo "  ✦ Synlynk Zero-Risk Installer"
echo "  → Verifying prerequisites..."

if ! command -v python3 >/dev/null 2>&1; then
    echo "❌ Error: python3 is required. Please install Python >= 3.10." >&2
    exit 1
fi

PY_VER=$(python_version)
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [ "$PY_MAJOR" -ne 3 ] || [ "$PY_MINOR" -lt 10 ]; then
    echo "❌ Error: Python >= 3.10 is required (found Python $PY_VER)." >&2
    exit 1
fi

METHOD="unknown"

# Tier 1: uv
if command -v uv >/dev/null 2>&1; then
    echo "  ✓ Found uv — installing in high-speed isolated tool environment..."
    uv tool install "$CANONICAL_SPEC" --force
    METHOD="uv"
# Tier 2: pipx
elif command -v pipx >/dev/null 2>&1; then
    echo "  ✓ Found pipx — installing in isolated application environment..."
    pipx install "$CANONICAL_SPEC" --force
    METHOD="pipx"
# Tier 3: Consent-gated pipx bootstrap (interactive only)
elif [ -t 0 ] && [ "$ALLOW_BOOTSTRAP" = "1" ] && command -v brew >/dev/null 2>&1; then
    echo "  → pipx is recommended. Attempting Homebrew installation..."
    brew install pipx && pipx ensurepath
    pipx install "$CANONICAL_SPEC" --force
    METHOD="pipx"
# Tier 4: Guaranteed Standalone Stdlib venv
else
    echo "  → Using guaranteed zero-pollution standalone venv fallback..."
    mkdir -p "$INSTALL_DIR/releases/current" "$BIN_DIR"
    python3 -m venv "$INSTALL_DIR/releases/current"
    "$INSTALL_DIR/releases/current/bin/pip" install --upgrade pip
    "$INSTALL_DIR/releases/current/bin/pip" install "$CANONICAL_SPEC"
    ln -sfn "$INSTALL_DIR/releases/current/bin/synlynk" "$BIN_DIR/synlynk"
    METHOD="standalone_venv"
fi

echo "  ✓ Installed synlynk via tier: $METHOD"

# Health check & PATH check. Print a hint only; do not edit shell rc files.
case ":$PATH:" in
    *:"$BIN_DIR":*) ;;
    *)
        echo ""
        echo "  ⚠ Action needed: $BIN_DIR is not on your PATH."
        echo "    Add it by adding this line to your ~/.zshrc or ~/.bashrc:"
        echo "    export PATH=\"\$HOME/.local/bin:\$PATH\""
        echo ""
        ;;
esac

echo "  ✦ Run 'synlynk doctor' to verify complete environment health."
