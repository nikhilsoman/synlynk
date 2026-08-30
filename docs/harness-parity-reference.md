# Fleet Harness Parity Reference Manual

**Authoritative Reference for Multi-Harness Capabilities, Permissions, and Execution Parity**  
*Scope: Managed and checked periodically by `synlynk doctor` during harness capability reassessment cycles.*  
*Maintained under: `docs/harness-parity-reference.md`*  
*Last Updated: 2026-08-30 (Post-PR #1275, #1279)*

---

## 1. Executive Fleet Overview

synlynk orchestrates a polyglot fleet of 4 primary AI coding harnesses:
- **Codex** (OpenAI Codex CLI, `codex exec`)
- **Grok** (xAI Grok CLI, `grok --single`)
- **Agy** (Google Antigravity / Gemini CLI, `agy -p`)
- **Claude** (Anthropic Claude Code CLI, `claude --print`)

Each harness exhibits distinct architectural characteristics across three core operating dimensions:
1. **Interactive Shell vs. Headless Execution:** Interactive TTY operation with human-in-the-loop confirmation vs. headless background subprocess execution in isolated Git worktrees.
2. **Permission Model & Safety Enforcement:** Host sandboxing (macOS Seatbelt), fine-grained tool whitelists, CLI flag overrides, and model-level risk classifiers.
3. **Telemetry & Attribution:** Token usage parsing (input, output, reasoning/thinking, and prompt-cache reads), exit status detection, and role-scoped GitHub App identity attribution.

This document records the exact capability matrix, known failure modes, flag requirements, and automated validation rules enforced by `synlynk doctor`.

---

## 2. Comprehensive Harness Parity Matrix

| Dimension | OpenAI Codex | xAI Grok | Google Agy | Anthropic Claude |
|:---|:---|:---|:---|:---|
| **CLI Binary** | `codex` | `grok` | `agy` | `claude` |
| **Invocation Pattern** | `codex exec - -s workspace-write` (stdin piped) | `grok --always-approve --single "$PROMPT"` (cli arg) | `agy -p "$PROMPT"` (cli arg) | `claude --print` (stdin piped) |
| **Headless Auto-Approve** | Native (`approval:never` default in `exec`) | `--always-approve` (required) or `--permission-mode bypassPermissions` | `--dangerously-skip-permissions` | `--dangerously-skip-permissions` |
| **Fine-Grained Permissions** | File write vs read-only via `-c approval_policy=untrusted` | Handled via `--always-approve` in isolated worktree | `--mode plan` / `--sandbox` (prev. broken by `PermissionEnforcementError`) | `--allowedTools <tools>` |
| **Headless Timeout Contract** | Host stall killer (`stall_timeout_minutes: 30`) | Host stall killer (`stall_timeout_minutes: 30`) | `--print-timeout 30m0s` (prev. broken by 5m CLI default) | Host stall killer (`stall_timeout_minutes: 30`) |
| **File / Terminal Isolation** | Native Seatbelt sandbox (`-s workspace-write`) | Denied `bash` unless explicit shell grant | Host filesystem (isolated via worktree + `--sandbox`) | Host filesystem (isolated via worktree) |
| **Network Egress** | Gated by `-c sandbox_workspace_write.network_access=true` | Blocked in dispatch sandbox unless host shell granted | Open to Google endpoints & web | Open to Anthropic endpoints & web |
| **GitHub Write (`can_gh_write`)** | **Reliable** (PR #1271, #1275) | **Unreliable** (shell write blocked in sandbox) | **Reliable** (requires TC-7 `settings.json` allow-rules) | **Reliable** (direct CLI / PM role) |
| **Prompt Caching Telemetry** | Extracted (`cache_read_input_tokens`) | Extracted (`cache_read_input_tokens`) | Extracted (`cache_read_tokens`) | Extracted (`cache_read_input_tokens`) |
| **Structured Output Format** | `--json` (NDJSON stream) | `--output-format json` (single object) | `--output-format json` (single object) | `--output-format stream-json --verbose` |
| **SOP Fleet Role** | `["builder", "verifier"]` (primary implement/test/review) | `["builder", "verifier"]` (canvas/JS/infra scaffold) | `["builder", "verifier"]` (CSS/templates/content) | `["architect", "pm"]` (PM/deploy/brainstorm) |

---

## 3. Deep-Dive Harness Audit & Failure Analysis

### 3.1 OpenAI Codex
- **Status:** **Full Harness Parity Achieved (PR #1271, #1275)**
- **Historical Blocker Disproved:**
  For months, Codex was deemed structurally incapable of performing GitHub writes under the assumption that `workspace-write` Seatbelt sandboxing unalterably blocked DNS/network egress to `api.github.com`. A live empirical probe proved that passing `-c sandbox_workspace_write.network_access=true` cleanly enables outbound HTTPS without disabling file write sandboxing.
- **Dispatch Implementation:**
  In `synlynk/dispatch.py`, when `requires_gh_write` is active, synlynk appends `_CODEX_NETWORK_PERMISSION` (`"run:install"`) to `effective_grants`. This emits `["-c", "sandbox_workspace_write.network_access=true"]` and binds the ephemeral role-scoped GitHub App token (`GH_TOKEN`).
- **Telemetry:**
  Codex outputs JSON event streams where `usage.input_tokens`, `usage.output_tokens`, and `usage.cache_read_input_tokens` are parsed accurately.

### 3.2 xAI Grok
- **Status:** **Headless Stability Achieved (PR #1277, #1279)**
- **Historical Failure Mode Resolved:**
  Headless Grok jobs repeatedly terminated with `stopReason: "cancelled"` / `cancellationCategory: "PermissionCancelled"`. Forensic analysis of `~/.grok/sessions/.../events.jsonl` proved this was caused by Grok's internal shell AST splitter (`bash_command_splitting.rs`) and risk classifier (`exec_risk.rs`) triggering an interactive prompt for compound commands (e.g. `pytest ... ; echo "FILTER_EXIT=\$?"`). In `--permission-mode dontAsk`, Grok cannot prompt the user and immediately cancels the execution (`decision: "cancelled"`), aborting the entire turn.
- **Dispatch Implementation:**
  In `synlynk/dispatch.py:_grok_permission_flags()`, whenever `run:shell` or `run:tests` is granted, dispatch emits `["--always-approve"]`. In `synlynk/_constants.py`, `--always-approve` is declared as a required dispatch flag.

### 3.3 Google Agy (Antigravity CLI)
- **Status:** **Actionable Gaps Identified**
- **Identified Gaps:**
  1. **5-Minute Execution Timeout (`HARNESS_INTERNAL_TIMEOUT` / #750, #162):**
     In `--print` mode (`-p`), the Antigravity CLI enforces a built-in default timeout: `--print-timeout 5m0s`. Long-running tasks, multi-suite test runs, or deep refactors abort at ~300-500s with `Error: timeout waiting for response`. Fix: Pass `--print-timeout 30m0s` on all headless Agy dispatches.
  2. **Read-Only Lockout (`PermissionEnforcementError`):**
     In `synlynk/dispatch.py`, passing `permissions <= {"read:*"}` causes dispatch to raise `PermissionEnforcementError`, falsely claiming Agy cannot enforce read-only operation. Agy natively supports `--mode plan` and `--sandbox` to restrict tool execution.
  3. **Prompt Caching Telemetry Undercounting:**
     In `synlynk/costs.py:_extract_agy_structured()`, `cache_read_tokens` is hardcoded to `0` based on the obsolete assumption that Gemini does not report prompt caching. Live inspection of `agy --output-format json` proves `usage.cache_read_tokens` is actively emitted by the CLI.
  4. **TC-7 Allow-Rules Schema Preflight:**
     Headless Agy executions require preconfigured allow-rules in `~/.gemini/antigravity-cli/settings.json` under `permissions.allow` (e.g. `command(gh *)`) to prevent jetski auto-denials.

### 3.4 Anthropic Claude (Claude Code CLI)
- **Status:** **Role Alignment & Auto-Mode Gap Identified**
- **Identified Gaps:**
  1. **Baseline Role Contradiction:**
     `synlynk/_constants.py` classifies Claude as `["architect", "builder"]`, whereas `CLAUDE.md` and project SOP strictly enforce a PM-only split, forbidding Claude from implementing code. Roles in `_constants.py` must align with `["architect", "pm"]`.
  2. **Auto-Mode Classifier Denials (LIVE-6 / #1140):**
     When running under Claude Code auto-mode, Anthropic's local risk classifier blocks commands referencing `.pem` files or privileged GitHub App credentials (`Blocked by classifier`), requiring careful credential path isolation outside the workspace tree.
  3. **Flag Pairing:**
     Claude dispatches combine `--dangerously-skip-permissions` with `--allowedTools <list>`. Any tool omitted from `--allowedTools` is disabled regardless of skip permissions.

---

## 4. Interactive Shell vs. Headless Execution Parity

| Dimension | Interactive Shell Mode | Headless Dispatch Mode (`synlynk dispatch`) | Parity Risk / Mitigation |
|:---|:---|:---|:---|
| **Terminal Context** | Attached TTY / PTY | Detached session (`start_new_session=True`), output redirected to log | Requires unbuffered stdout (`PYTHONUNBUFFERED=1`) and JSON output formats. |
| **Tool Prompts** | Prompts developer visually (`[y/n/always]`) | No operator present; prompts cause auto-cancel or hang | Must pass full approval flags (`--always-approve`, `--dangerously-skip-permissions`, `approval:never`). |
| **Execution Timers** | Unbounded; runs until user interrupts | Subject to host stall killer (30m) + CLI-internal timers | Harnesses must not enforce tighter client timers than the host (e.g. `--print-timeout 30m0s`). |
| **GitHub Identity** | Ambient host credentials (`nikhilsoman`) | Ephemeral role-scoped GitHub App tokens (`synlynk-synlynk-qa`) | Prevents PR self-approval deadlocks; requires worktree-aware token path resolution (#1264). |
| **Context Ingestion** | Reads root instruction files (`CLAUDE.md`, `GEMINI.md`, etc.) | Receives formatted prompt envelope with context snapshot, story ID, and receipt hash | Enforces task delivery receipt protocol (`SYNLYNK_TASK_RECEIVED`). |

---

## 5. Scope & Rules for `synlynk doctor` Verification

As part of the periodic capability reassessment cycle (#1179), `synlynk doctor` inspects the health of this parity contract:

1. **Baseline Flag Parity:** Verify that flags declared in `HARNESS_CAPABILITY_BASELINES` correspond to valid options in each installed CLI (`agy --help`, `claude --help`, `grok --help`, `codex --help`).
2. **Timeout Safeguards:** Ensure `--print-timeout` is configured for Agy so headless runs do not fail at the default 5-minute boundary.
3. **TC-7 Allow-Rule Verification:** Confirm that `~/.gemini/antigravity-cli/settings.json` contains required allow-rules before dispatching Agy for shell/gh-write tasks.
4. **Role Integrity Check:** Verify that role allocations in `.synlynk/policy.json`, `synlynk/_constants.py`, and instruction files (`CLAUDE.md`, `AGENTS.md`, `GEMINI.md`, `GROK.md`) remain mutually consistent.
