# Synlynk for Visual Studio Code

A lightweight, zero-dependency VS Code extension providing native IDE reach into Synlynk's multi-agent autonomous engineering OS.

## Features

- **Synlynk: Dispatch Task to Agent Fleet (`synlynk.dispatch`)**: Submit tasks directly from VS Code to Claude, Codex, Agy, or Grok with adaptive capability routing.
- **Synlynk: Show Dispatched Jobs (`synlynk.jobs`)**: Interactive quick-pick to inspect running and completed agent jobs, token usage, and costs.
- **Synlynk: View Job Logs (`synlynk.logs`)**: Stream and tail live job execution logs directly in the VS Code terminal.
- **Synlynk: Check Platform Health & Burn Rate (`synlynk.status`)**: Real-time observability over platform readiness, budget burn, and active worktrees.
- **Synlynk: Run Workspace Diagnostics (`synlynk.doctor`)**: Comprehensive compliance and configuration health check suite.

## Prerequisites

Synlynk CLI must be installed and available in your `PATH`:

```bash
pip install synlynk
# or via pipx
pipx install synlynk
```

## Quick Start

1. Open any workspace in VS Code.
2. Initialize Synlynk if not already configured:
   ```bash
   synlynk init
   ```
3. Open the Command Palette (`Ctrl+Shift+P` or `Cmd+Shift+P`) and type `Synlynk`.
4. Choose `Synlynk: Dispatch Task to Agent Fleet`.
