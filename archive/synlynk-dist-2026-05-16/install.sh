#!/bin/bash

# synlynk: Standardized Documentation Bootstrap
# Usage: curl -sSL <link-to-raw-script> | bash

set -e

PROJECT_DOCS_DIR="project-docs"

echo "🚀 Pulsing your project..."

# 1. Interactive Mode Choice
echo "------------------------------------------------"
echo "Select Pulse Mode:"
echo "1) Single User (Personal repo, simple docs)"
echo "2) Team Mode (Collaborative, attributed decisions, multi-user devlogs)"
echo "------------------------------------------------"
read -p "Enter choice (1 or 2): " SYNLYNK_CHOICE

if [ "$SYNLYNK_CHOICE" == "2" ]; then
    SYNLYNK_MODE="team"
    echo "👥 Team Mode enabled."
else
    SYNLYNK_MODE="single"
    echo "👤 Single User mode enabled."
fi

# 2. Create directory structure
mkdir -p "$PROJECT_DOCS_DIR"

if [ "$SYNLYNK_MODE" == "team" ]; then
    mkdir -p "$PROJECT_DOCS_DIR/devlogs"
fi

# 3. Initialize files based on mode
cat <<EOF > "$PROJECT_DOCS_DIR/roadmap.md"
# Project Roadmap
| Priority | Feature | Description | Status | Target Release | $([ "$SYNLYNK_MODE" == "team" ] && echo "Owner |")
| :--- | :--- | :--- | :--- | :--- | $([ "$SYNLYNK_MODE" == "team" ] && echo ":--- |")
| P0 | Pulse Setup | Initialize project documentation. | Done | v0.1.0 | $([ "$SYNLYNK_MODE" == "team" ] && echo "Pulse-Bot |")
EOF

cat <<EOF > "$PROJECT_DOCS_DIR/todo.md"
# Project Todo List
## Active Tasks
- [ ] Implement core logic <!-- id: 0 --> $([ "$SYNLYNK_MODE" == "team" ] && echo "[Unassigned]")
EOF

cat <<EOF > "$PROJECT_DOCS_DIR/memory.md"
# Project Memory
## Decisions
- **Framework:** (e.g., React/Django) $([ "$SYNLYNK_MODE" == "team" ] && echo "[@InitialSetup]")

## Conventions
- **Docs:** Standardized in /project-docs
EOF

cat <<EOF > "$PROJECT_DOCS_DIR/costs.md"
# Project Costs Tracking
## Session Summary
| Date | User | Requests | Tokens (In/Out) | Estimated Cost (USD) | Summary |
| :--- | :--- | :--- | :--- | :--- | :--- |
EOF

# Initialize Devlogs
if [ "$SYNLYNK_MODE" == "single" ]; then
    cat <<EOF > "$PROJECT_DOCS_DIR/devlog.md"
# Developer Log
| Date | Task | Outcome |
| :--- | :--- | :--- |
| $(date +%Y-%m-%d) | Pulse Initialization | project-docs structure created. |
EOF
else
    # Create a placeholder/sample for teams
    cat <<EOF > "$PROJECT_DOCS_DIR/devlogs/README.md"
# Team Devlogs
This directory contains individual developer logs (e.g., \`nikhil.md\`). 
The AI will automatically create and maintain your specific log based on your git username.
EOF
fi

# 4. Save Pulse Config
cat <<EOF > "$PROJECT_DOCS_DIR/.synlynk_config.json"
{
  "mode": "$SYNLYNK_MODE",
  "version": "1.1.0",
  "initialized_at": "$(date)"
}
EOF

# 5. Handle GEMINI.md
if [ ! -f "GEMINI.md" ]; then
    cat <<EOF > "GEMINI.md"
# Project Guidelines
- Documentation lives in /project-docs.
- Follow synlynk standards.
EOF
fi

echo "✅ synlynk initialized in $SYNLYNK_MODE mode!"
echo "👉 Next step: Add the contents of SYNLYNK_GUIDE.md to your AI's global or project instructions."
