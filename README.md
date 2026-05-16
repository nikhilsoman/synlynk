# synlynk 🔗

**The Universal Context Switchboard for AI-Native Development.**

synlynk is a lightweight, cross-platform orchestration layer designed to turn stateless AI agents into persistent, project-aware engineers. It bridges the gap between your local development environment and the fragmented world of AI CLIs (Claude, Gemini, Codex) and IDEs (Cursor, VS Code, Windsurf).

## 🚀 The "Quota-Hopping" Superpower

Stop being locked into a single AI subscription. synlynk allows you to move seamlessly between tools and accounts without losing context. Start a task in **Claude Code**, run out of your message quota, and finish it in **Gemini** or **Cursor**. synlynk ensures every tool has the exact same project state, roadmap, and history.

## ✨ Key Features (v1.2.0-lite)

- **Unified Context Snapshots:** Automatically compiles your project docs into a single `.synlynk/context.md` for instant AI ingestion.
- **Multi-Tool Interoperability:** Standardized instruction templates for Claude, Gemini, Cursor, and a universal `AI_INSTRUCTIONS.md` for everything else.
- **The "Flatline" Sentinel:** Real-time hallucination detection that flags repetitive command failures and loops.
- **Budget & Cost Pulse:** Passive telemetry that tracks token usage, request counts, and estimated USD spend across all tools.
- **Frictionless Telemetry:** Seamlessly wraps your favorite CLIs via shell aliases to capture data without changing your workflow.

## 🛠️ Installation

Install synlynk globally on your machine with a single command:

```bash
curl -sSL https://raw.githubusercontent.com/nikhilsoman/synlynk/main/install.sh | bash
```

### Post-Install Setup

1. **Add to PATH:** The installer will provide a command to add synlynk to your `.zshrc` or `.bashrc`.
2. **Set up Aliases:** To enable frictionless telemetry, add these to your shell profile:
   ```bash
   alias claude='synlynk exec claude'
   alias gemini='synlynk exec gemini'
   ```

## 📖 Usage

### 1. Initialize a Project
Go to any repository and run:
```bash
synlynk init
```
This creates the `project-docs/` structure and your AI instruction files.

### 2. Execute with Context
Run your favorite AI CLI through the synlynk switchboard:
```bash
synlynk exec claude code
```
*Note: If you set up the aliases above, you can just run `claude code`!*

### 3. Monitor Your Pulse
After every execution, synlynk provides a **Budget Pulse**:
```text
📊 Budget Pulse: $0.0105 this session | Total Requests: 42
🪙 Tokens: 1200 in / 800 out
```

---
Built for the next generation of AI-native developers.
**Stay in the vibe. Stay in sync. Use synlynk.**
