#!/bin/bash

# synlynk Global Installer
#
# Recommended (pipx — isolated, auto-updates):
#   pipx install git+https://github.com/nikhilsoman/synlynk
#
# Script install (no pipx required):
#   curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash

set -e

echo "⚠️  DEPRECATION NOTICE: The install.sh script installer is deprecated"
echo "   Migrate to pipx for automatic updates:"
echo "   pipx install git+https://github.com/nikhilsoman/synlynk"
echo "   (Continuing install for backward compatibility)"
echo ""

VERSION=$(python3 -c "import re, pathlib; m = re.search(r'VERSION = \"([^\"]+)\"', pathlib.Path('synlynk/__init__.py').read_text()); print(m.group(1) if m else '0.0.0')" 2>/dev/null || echo "0.21.0")
INSTALL_DIR="$HOME/.synlynk/bin"
LIB_DIR="$HOME/.synlynk/lib"
BINARY_PATH="$INSTALL_DIR/synlynk"
PACKAGE_DIR="$LIB_DIR/synlynk"

echo "🔗 Installing synlynk $VERSION..."

# 1. Dependency Check
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: python3 is required to run synlynk."
    exit 1
fi

# 2. Create Directory Structure
mkdir -p "$INSTALL_DIR" "$LIB_DIR"

# 3. Install package + shim (or download if running via curl)
if [ -f "synlynk/__init__.py" ]; then
    # Local install from repo checkout
    cp -r synlynk "$LIB_DIR/"
    if [ -f "bin/synlynk.py" ]; then
        cp "bin/synlynk.py" "$BINARY_PATH"
    fi
else
    # Remote install via curl
    echo "  Downloading synlynk package..."
    mkdir -p "$PACKAGE_DIR"
    for f in __init__.py __main__.py cli.py db.py hud.py viz.py; do
        curl -sSL "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/synlynk/$f" \
             -o "$PACKAGE_DIR/$f"
    done
    curl -sSL "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/synlynk/capability_baseline.json" \
         -o "$PACKAGE_DIR/capability_baseline.json" 2>/dev/null || true
    # Write shim directly (bin/synlynk.py references package via sys.path)
    cat > "$BINARY_PATH" <<'SHIM'
#!/usr/bin/env python3
import sys, os
sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".synlynk", "lib"))
from synlynk import main
if __name__ == "__main__":
    main()
SHIM
fi

# Patch sys.path in the installed shim to always point at ~/.synlynk/lib
if [ -f "$BINARY_PATH" ]; then
    python3 - "$BINARY_PATH" <<'PYEOF' 2>/dev/null || true
import sys
path = sys.argv[1]
with open(path) as f:
    content = f.read()
patched = content.replace(
    'sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))',
    'sys.path.insert(0, os.path.join(os.path.expanduser("~"), ".synlynk", "lib"))'
)
with open(path, 'w') as f:
    f.write(patched)
PYEOF
    chmod +x "$BINARY_PATH"
fi

# 4. PATH Configuration
echo "🚀 Configuring PATH automatically..."

add_to_path_file() {
    local file=$1
    local line=$2
    if [ -f "$file" ]; then
        if ! grep -q "$INSTALL_DIR" "$file"; then
            echo "" >> "$file"
            echo "# synlynk path" >> "$file"
            echo "$line" >> "$file"
            echo "  ✓ Added to $file"
        else
            echo "  ✓ Already present in $file"
        fi
    fi
}

add_to_path_file "$HOME/.zshrc" "export PATH=\"\$PATH:$INSTALL_DIR\""

if [[ "$OSTYPE" == "darwin"* ]]; then
    add_to_path_file "$HOME/.bash_profile" "export PATH=\"\$PATH:$INSTALL_DIR\""
else
    add_to_path_file "$HOME/.bashrc" "export PATH=\"\$PATH:$INSTALL_DIR\""
fi
add_to_path_file "$HOME/.profile" "export PATH=\"\$PATH:$INSTALL_DIR\""

if command -v fish &> /dev/null; then
    mkdir -p "$HOME/.config/fish"
    if [ ! -f "$HOME/.config/fish/config.fish" ]; then touch "$HOME/.config/fish/config.fish"; fi
    add_to_path_file "$HOME/.config/fish/config.fish" "set -gx PATH \$PATH $INSTALL_DIR"
fi

echo "------------------------------------------------"
echo "✅ synlynk installed successfully to $BINARY_PATH"
echo ""
echo "🚀 PATH has been updated for your shell."
echo "------------------------------------------------"
