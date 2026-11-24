<p align="center">
  <img src="docs/img/logo/lockup.svg" alt="synlynk — neutral control plane for coding tasks" height="80">
</p>

<p align="center"><strong>Route coding tasks across AI vendors and local models, then prove the result.</strong></p>

<p align="center">
  <a href="https://github.com/nikhilsoman/synlynk/actions/workflows/test.yml"><img src="https://github.com/nikhilsoman/synlynk/actions/workflows/test.yml/badge.svg" alt="Tests passing"></a>
  <a href="https://github.com/nikhilsoman/synlynk/releases"><img src="https://img.shields.io/badge/version-0.38.3-blue" alt="Version"></a>
  <a href="LICENSE"><img src="https://img.shields.io/badge/license-Apache--2.0-green" alt="License"></a>
  <a href="https://www.python.org/downloads/"><img src="https://img.shields.io/badge/python-3.10%2B-blue" alt="Python 3.10+"></a>
</p>

Synlynk is a neutral control plane for multi-agent development. It keeps project context, dispatches scoped work to Claude, Codex, Agy, Grok, or local models, tracks cost and lifecycle state, and verifies what actually changed.

**v0.38.3:** Harness Parity Phase 3 brings live routing, manifest validation, CLI-version preflight checks, fail-closed local harness gates, and dual-ledger attribution to the dispatch workflow.

## Install

The fastest install is one command:

```bash
pipx install synlynk
```

Prefer a virtual environment? Use `python -m pip install synlynk`. Synlynk requires Python 3.10+ and has no required runtime dependencies.

## 60-second quickstart

From the repository you want to coordinate:

```bash
# 1. Initialize the project and discover available harnesses
synlynk init --wizard

# 2. Build or refresh the repository source map
synlynk scan

# 3. Preview a dispatch (safe: no job or worktree is created)
synlynk dispatch auto --as-agent dev \
  --task "Add a health-check command and tests" --dry-run

# 4. Run it, then inspect the result
synlynk dispatch auto --as-agent dev \
  --task "Add a health-check command and tests"
synlynk jobs
synlynk status
```

The dispatch creates an isolated worktree, injects the relevant project context, records cost and lifecycle events, and leaves the final verification trail in the job log. Run `synlynk logs --job <job-id>` to follow a job in detail.

## Command reference

These are the commands most users need day to day. The complete generated catalog is in the [command reference](docs/reference/commands.md).

| Command | What it does |
|:---|:---|
| `synlynk init --wizard` | Initialize a project and configure the local workspace |
| `synlynk quickstart` | Open the guided first-run workflow |
| `synlynk scan` | Build or refresh the repository source map |
| `synlynk dispatch` | Send a scoped task to an AI or local harness |
| `synlynk jobs` | List, inspect, or stream dispatched jobs |
| `synlynk status` | Show workspace health, goals, and burn rate |
| `synlynk doctor` | Diagnose configuration and environment issues |
| `synlynk story` | Create and track implementation work |
| `synlynk goal` | Manage project goals and roadmap alignment |
| `synlynk pr check` | Verify a pull request against project gates |
| `synlynk upgrade` | Upgrade the installed Synlynk version |

For command-specific flags, run `synlynk <command> --help`.

<!-- commands:start -->

**Start here:**

- `synlynk home`
- `synlynk init`
- `synlynk start`
- `synlynk new`
- `synlynk quickstart`
- `synlynk brainstorm`
- `synlynk brief`
- `synlynk scan`
- `synlynk join`
- `synlynk governs`
- `synlynk report`
- `synlynk preflight`
- `synlynk status`
- `synlynk watch`
- `synlynk viz`

Full command reference: [docs/reference/commands.md](docs/reference/commands.md)

<!-- commands:end -->

## Dispatch tasks

Use `--as-agent` to attribute the work to a project role. Start with `--dry-run` when you are composing task text or checking routing.

```bash
# Let capability routing choose the best available harness
synlynk dispatch auto --as-agent dev \
  --task "Review the cache invalidation path and add regression tests"

# Target a specific harness
synlynk dispatch codex --as-agent dev \
  --task "Refactor synlynk/dispatch.py without changing its public CLI"

# Run a documentation-only task with a narrow scope
synlynk dispatch agy --as-agent dev \
  --task "Refresh the onboarding guide for the current CLI" \
  --scope-paths "docs/**" --scope-paths "README.md"
```

Dispatch task text must be non-empty. Every job is associated with an isolated worktree and emits a receipt marker so delivery can be audited. See the [safe caller construction guide](docs/reference/safe-caller-construction.md) before building task text programmatically.

## Documentation

- [Documentation hub](docs/README.md)
- [10-minute quickstart](docs/quickstart.md)
- [Task-oriented how-tos](docs/how-to/README.md)
- [Full command reference](docs/reference/commands.md)
- [Agent vs. harness glossary](docs/glossary-agent-vs-harness.md)

## Development

```bash
git clone https://github.com/nikhilsoman/synlynk.git
cd synlynk
python3 bin/synlynk.py --help
pytest -q
```

Synlynk is licensed under the [Apache License 2.0](LICENSE).
