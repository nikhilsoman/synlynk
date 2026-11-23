# Design Specification: Synlynk Modular Ecosystem (The Standalone Developer Tooling Suite)

**Document ID:** `SPEC-MODULAR-01`  
**Date:** 2026-11-23  
**Status:** RATIFIED & READY FOR FINAL OPERATOR APPROVAL  
**Governing Decisions:** [dec-f39b1a08](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-11-23-standalone-tokentrail-and-tokenprice-architecture.md) & [dec-e89c42fa](file:///Users/nikhilsoman/dev/synlynk/project-docs/decisions/2026-11-23-comprehensive-modular-ecosystem-panel-assessment.md)  
**Target Milestone:** Sequence B Foundation (`packages/*`)  

---

## 1. Executive Summary & Ecosystem Topology

This specification defines the architecture, isolation invariants, configuration tooling, and publishing contracts for **five standalone, independently maintained Python packages and CLI utilities** located in `packages/`:

```
+----------------------------------------------------------------------------------------------------+
|                                  THE SYNLYNK ECOSYSTEM SUITE                                       |
+----------------------------------------------------------------------------------------------------+

  [ Model Pricing ]   [ Session Extraction ]  [ Worktree Leases ]  [ Agent Probing ]   [ Token Budget ]
   tokenprice           tokentrail              worktree-lease       harness-spec        token-breaker
  (Zero deps)          (Universal I/O)         (Atomic Git)         (CLI Sandboxing)    (Active Kill)
        │                    │                       │                    │                   │
        ▼                    ▼                       ▼                    ▼                   ▼
  tokenprice CLI       tokentrail CLI          wtlease CLI          harness-spec CLI    tbreak CLI
  config init/edit     config init/hook        config init/prune    config probe/test   config rules/set
        │                    │                       │                    │                   │
        └────────────────────┴───────────────────────┼────────────────────┴───────────────────┘
                                                     ▼
                                      +─────────────────────────────+
                                      |   synlynk/ecosystem/ Bridge |  <-- Isolation Facade
                                      |       (Adapter Layer)       |
                                      +─────────────────────────────+
                                                     ▼
                                      +─────────────────────────────+
                                      |     synlynk Core Control    |
                                      |    (state.db & Governance)  |
                                      +─────────────────────────────+
```

---

## 2. Modularity & Zero-Leakage Architecture

### A. Mechanical Isolation Invariant
None of the 5 packages may import anything from `synlynk.*`. Each package maintains:
1. An independent `pyproject.toml` (PEP 621 / `hatchling`).
2. An isolated test directory (`tests/`).
3. An automated AST import-scanner in CI asserting zero `synlynk` references across all source files.

### B. Core Integration via Bridge Facade (`synlynk/ecosystem/`)
Synlynk core interacts with the standalone suite exclusively through an internal bridge facade:
- `synlynk/ecosystem/pricing.py` $\rightarrow$ wraps `tokenprice`.
- `synlynk/ecosystem/transcripts.py` $\rightarrow$ wraps `tokentrail`.
- `synlynk/ecosystem/worktrees.py` $\rightarrow$ wraps `worktree_lease`.
- `synlynk/ecosystem/probing.py` $\rightarrow$ wraps `harness_spec`.
- `synlynk/ecosystem/circuit_breakers.py` $\rightarrow$ wraps `token_breaker`.

This guarantees that external package API changes never destabilize internal `state.db` schema logic.

---

## 3. Standardized 4-Tier Configuration Resolution Ladder

Every package and CLI tool implements an identical, predictable configuration hierarchy:

```
Tier 1: Explicit CLI flags (e.g. --config, --provider, --max-cost)
   ▼
Tier 2: Environment variables (e.g. TOKENTRAIL_CONFIG, TOKENPRICE_PROVIDER)
   ▼
Tier 3: Project-local config file (e.g. ./.tokentrail.json, ./.wtlease.json)
   ▼
Tier 4: Global user config file (e.g. ~/.config/tokentrail/config.json)
```

Each package includes a published `config.schema.json` enabling IDE auto-completion and validation in Cursor, VSCode, and PyCharm.

---

## 4. Package Deep Dives & Technical Hardening

### Package 1: `tokenprice` (Model Pricing & Valuation Engine)
- **Scope:** Zero-dependency, sub-millisecond pricing lookup, prompt cache accounting, and nominal vs. effective cost calculation.
- **Hardening:** Memory catalog implemented with `__slots__` for zero-allocation execution inside 10,000 req/sec proxy routers.
- **CLI Commands:**
  - `tokenprice init`: Generates config and default pricing file.
  - `tokenprice update --online`: Fetches upstream pricing updates.
  - `tokenprice set-rate <model> --input <in> --output <out>`: Adds custom or local LLM pricing.
  - `tokenprice mode set [api|subscription|custom]`: Sets nominal vs. effective rate modes.

### Package 2: `tokentrail` (Universal Agent Session & Gateway Transcript Extractor)
- **Scope:** Multi-harness session transcript extraction, streaming turn chunk deduplication by `message.id`, and HTTP gateway middleware.
- **Hardening:**
  - Streaming chunk collapse invariant: ensures progress chunks for a single turn collapse to exact terminal usage (eliminating the 2× overcounting bug).
  - Strict privacy invariant: extracts token counts, model names, and timestamps only; zero user prompts or code are parsed into memory.
  - Shared test fixture kit (`tokentrail.testing`): ships anonymized real streaming transcript fixtures from Claude Code, Agy, and Codex CLI.
- **CLI Commands:**
  - `tokentrail init`: Detects installed agent CLIs and configures transcript paths.
  - `tokentrail hooks install [claude|agy]`: Idempotently installs `SessionEnd` cost-capture hooks.
  - `tokentrail summary [--last | --session <id>]`: Prints a Rich terminal audit of tokens, cache hit rate, and cost.
  - `tokentrail watch`: Real-time terminal HUD monitoring active local agent sessions.
  - `tokentrail export [--format json|csv|otlp]`: Emits standardized OpenTelemetry / Prometheus metrics.

### Package 3: `worktree-lease` (Atomic Git Worktree Manager)
- **Scope:** Lease-locked, collision-free git worktrees with automatic stale-lock recovery for multi-agent concurrency.
- **Hardening:**
  - Atomic file-descriptor locking (`fcntl.flock` on Unix, `msvcrt` on Windows).
  - Pre-delete validation checking open process handles before deleting directories.
  - Support for detached HEAD checkouts so agents can test speculative patches without polluting local branches.
- **CLI Commands:**
  - `wtlease init`: Configures worktree base path and lease TTL.
  - `wtlease list`: Displays active leases, PIDs, and branches.
  - `wtlease prune [--stale 2h] [--dry-run]`: Clears expired worktrees with safety dry-run output.
  - `wtlease acquire <branch> --holder <agent>`: Reserves a guarded worktree.

### Package 4: `harness-spec` (Universal Agent CLI Discovery & Sandboxing Protocol)
- **Scope:** Probes installed agent CLIs (`claude`, `codex`, `agy`, `grok`, `cursor`), verifies flag availability (`--version`, headless flags), and normalizes execution contracts.
- **Hardening:** Strict separation between harmless capability probing (`--version`) and active execution sandbox validation.
- **CLI Commands:**
  - `harness-spec probe`: Scans system PATH and outputs structured capability matrix.
  - `harness-spec test <harness>`: Executes sandbox isolation validation.
  - `harness-spec register <custom>`: Registers custom agent CLIs or proxy wrappers.

### Package 5: `token-breaker` (In-Flight Token & Spend Circuit Breaker)
- **Scope:** Active in-flight spending watchdog, stall-turn detector, and rogue loop terminator.
- **Hardening:** Dual supervisor modes:
  1. Process Supervisor: Monitors child process trees via OS signals (SIGTERM/SIGKILL).
  2. Streaming Generator Iterator: Wraps Python iterators (`for chunk in stream: breaker.feed(chunk)`), immediately raising `CircuitBreakerError` without requiring OS permissions.
- **CLI Commands:**
  - `tbreak init`: Configures per-job spending ceilings and turn limits.
  - `tbreak run --max-cost 2.50 -- <command>`: Wraps any agent CLI execution with budget enforcement.
  - `tbreak status`: Shows active monitored sessions and trip history.

---

## 5. Publishing Strategy & Open-Source Suite Distribution

1. **License:** Apache-2.0 across all 5 packages.
2. **PyPI Publishing:** Dual-registered clean names (`tokenprice`, `tokentrail`, `worktree-lease`, `harness-spec`, `token-breaker`) and namespaced aliases (`synlynk-tokenprice`, etc.).
3. **Interactive Web Portal:**
   - Hosted at `synlynk.com/ecosystem` (or `ecosystem.synlynk.dev`).
   - Browser-executable WebAssembly (Pyodide) tools allowing developers to drag and drop Claude Code or Agy transcripts to get an instant cost audit.
   - Provides organic top-of-funnel conversion to Synlynk's full autonomous platform.
