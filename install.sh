#!/bin/bash

# synlynk Global Installer
# Usage: curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash

set -e

VERSION="0.9.4"
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
    cp "bin/synlynk.py" "$BINARY_PATH"
else
    # Remote install via curl
    echo "  Downloading synlynk package..."
    mkdir -p "$PACKAGE_DIR"
    curl -sSL "https://raw.githubusercontent.com/nikhilsoman/synlynk/main/synlynk/__init__.py" -o "$PACKAGE_DIR/__init__.py"
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
# (bin/synlynk.py uses a relative path that works in the dev repo but not when
# installed to ~/.synlynk/bin/ — rewrite that line for the installed copy)
python3 - "$BINARY_PATH" <<'PYEOF'
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
    else
        # If the file doesn't exist but is a primary config, we might want to create it
        # but for safety we only update existing ones here except for fish
        :
    fi
}

# Zsh (Default on macOS)
add_to_path_file "$HOME/.zshrc" "export PATH=\"\$PATH:$INSTALL_DIR\""

# Bash
if [[ "$OSTYPE" == "darwin"* ]]; then
    add_to_path_file "$HOME/.bash_profile" "export PATH=\"\$PATH:$INSTALL_DIR\""
else
    add_to_path_file "$HOME/.bashrc" "export PATH=\"\$PATH:$INSTALL_DIR\""
fi
add_to_path_file "$HOME/.profile" "export PATH=\"\$PATH:$INSTALL_DIR\""

# Fish
if command -v fish &> /dev/null; then
    mkdir -p "$HOME/.config/fish"
    if [ ! -f "$HOME/.config/fish/config.fish" ]; then touch "$HOME/.config/fish/config.fish"; fi
    add_to_path_file "$HOME/.config/fish/config.fish" "set -gx PATH \$PATH $INSTALL_DIR"
fi

echo "------------------------------------------------"
echo "✅ synlynk installed successfully to $BINARY_PATH"
echo ""
echo "🚀 PATH has been updated for your shell."
echo "👉 Please run 'source ~/.zshrc' (or your shell's config) or open a new terminal."
echo ""
echo "👉 Next steps:"
echo "   1. Run 'synlynk init' in your repository."
echo "   2. Run 'synlynk exec <command>' to wrap your AI CLIs."
echo "------------------------------------------------"
