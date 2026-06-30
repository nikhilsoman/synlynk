# BS-14: Harness Compatibility System

**Date:** 2026-06-30
**Session:** BS-14 (Nikhil + Claude)
**Status:** Drafted for review
**Target:** v0.10.1 (LIVE-1 fixes) + v0.11.0 (full system)
**Incident context:** LIVE-1 (#81) — Agy 6h silent hang (stdout, no PTY); Grok flag contamination + network error

---

## Problem Statement

synlynk dispatches tasks to agent harnesses (Claude Code CLI, Agy, Grok, Codex) by spawning vendor CLIs as subprocesses. LIVE-1 exposed two classes of failure that a user can do nothing about:

1. **Agy silent hang** — stdout never flushed without PTY, job ran for 6h with zero log output, no sentinel fired.
2. **Grok flag contamination** — `--always-approve` (a Claude Code flag) was in the dispatch config, causing Grok to fail at startup. Compounded by a required network endpoint (`cli-chat-proxy.grok.com`) being unreachable. Job stuck open 6h.

The root cause is structural: synlynk has no systematic record of what each harness supports, what it requires to run headlessly, or when those requirements change as vendors ship new CLI versions.

The goal of BS-14 is to make synlynk the normalization layer. The user has one workflow and one vocabulary. synlynk maps it to whatever harness is running, detects when a harness changes, and surfaces failures before they become 6h silent hangs.

---

## Goals

1. Eliminate the LIVE-1 class of failure: no job should hang silently for hours due to a known, detectable harness issue.
2. Maintain a live record of every installed harness's execution contract, valid flags, and network dependencies.
3. Expose a Command Interoperability Matrix: every synlynk verb mapped to harness equivalents, parity gaps explicit and queryable.
4. Discover the full command palette of each harness proactively — detect harness changes before users report them.
5. Keep agent instruction files (CLAUDE.md, GEMINI.md, etc.) current with harness-specific execution instructions, via a synlynk-managed fence section.
6. Track harness capability changes over time by CLI version.

---

## Non-Goals

- Runtime verb translation engine — the `harness_verb_map` is populated in v0.11.0, but the layer that automatically rewrites user invocations into agent-specific commands at dispatch time is a follow-on arc.
- Native harness implementation (this spec addresses CLI wrapper mode; native harness is a separate arc).
- Agent/model performance ratings (the existing Agent Capability Matrix — separate concern, separate tables).

---

## Architecture

### Agent vs Harness

These are distinct concepts that happen to be 1:1 today:

| Concept | Definition | Examples |
|---|---|---|
| **Agent** | User-facing identity — what the user names and dispatches to | agy, grok, codex, claude |
| **Harness** | CLI runtime used to invoke the agent | agy CLI, grok CLI, codex CLI, claude CLI, native (future) |

User-facing surfaces stay agent-centric (`.agents/agy.json`, `synlynk dispatch --agent agy`). Internal data models and table names use harness-centric keys. `.agents/<agent>.json` gains two fields: `harness` (CLI runtime identifier) and `model` (underlying model ID).

When synlynk goes native, the harness changes (`agy` → `native`) while the agent identity (`agy`) stays the same. The normalization layer handles this transparently.

### Three Layers

```
User Layer        synlynk dispatch / probe / doctor / jobs / story / ...
                         │
Normalization     Capability Records · Command Interop Matrix · Dispatch Preflight
Layer             Verb Map · Palette Scan · Version Fingerprints
                         │
Harness Layer     claude-cli · agy · grok · codex · native (future)
```

---

## Data Model

All harness state lives in `state.db`. Five new tables.

### `harness_baselines`

Curated baselines shipped with synlynk. One row per `(harness_name, cli_version)`. The fast path for known agents.

| Column | Type | Notes |
|---|---|---|
| `harness_name` | TEXT | claude-cli · agy · grok · codex · native |
| `cli_version` | TEXT | semver from `--version` |
| `headless_contract` | JSON | `requires_pty`, `stdout_flush_method`, `env_vars_required`, `non_interactive_flag` |
| `dispatch_flags` | JSON | `valid_flags[]`, `invalid_flags[]`, `required_flags[]` |
| `network_deps` | JSON | `required_endpoints[]`, `optional_endpoints[]` |
| `baseline_source` | TEXT | curated · discovered · community |

### `harness_records`

Live state for each installed agent. Written by probe/doctor. Read by dispatch preflight on every dispatch call.

| Column | Type | Notes |
|---|---|---|
| `agent_name` | TEXT PK | user-facing agent name |
| `harness_name` | TEXT | CLI runtime identifier |
| `installed_version` | TEXT | last seen from `--version` |
| `compliance_status` | TEXT | ok · degraded · unknown · failed |
| `active_contract` | JSON | live headless_contract (may differ from baseline if drift detected) |
| `active_flags` | JSON | verified valid dispatch flags for installed version |
| `last_probe_at` | TIMESTAMP | |
| `capability_hash` | TEXT | SHA256 of `active_contract + active_flags` — drift detection key |

### `harness_verb_map`

Full synlynk verb surface mapped to per-harness invocation templates. Covers all verb categories (dispatch, observability, harness, PM, workspace). PM and workspace verbs have no harness equivalent — `supported = false` there means not applicable, not broken.

| Column | Type | Notes |
|---|---|---|
| `synlynk_verb` | TEXT | e.g. `dispatch.task`, `dispatch.headless`, `jobs`, `story` |
| `verb_category` | TEXT | dispatch · observability · harness · pm · workspace |
| `agent_name` | TEXT | |
| `agent_command` | TEXT | invocation template, NULL if not supported |
| `supported` | TEXT | full · partial · none |
| `partial_notes` | TEXT | what's missing when partial |
| `min_cli_version` | TEXT | when support was added |

### `harness_command_palette`

Full discovered command set per harness version. Every flag, subcommand, and positional argument found in `--help` output. The product intelligence layer.

| Column | Type | Notes |
|---|---|---|
| `harness_name` | TEXT | |
| `cli_version` | TEXT | |
| `command` | TEXT | e.g. `--non-interactive`, `mcp`, `config set` |
| `command_type` | TEXT | flag · subcommand · positional |
| `synlynk_verb` | TEXT NULL | mapped synlynk verb; NULL = unmapped = extension opportunity |
| `help_text` | TEXT | raw description from `--help` |
| `first_seen_version` | TEXT | when this command first appeared |
| `last_seen_version` | TEXT NULL | NULL if still present; populated when removed |

### `harness_version_history`

Append-only drift log. Every version change and capability hash diff.

| Column | Type | Notes |
|---|---|---|
| `agent_name` | TEXT | |
| `cli_version` | TEXT | version at time of event |
| `event_type` | TEXT | version_change · drift_detected · doctor_run · baseline_missing |
| `prev_hash` | TEXT | capability_hash before event |
| `new_hash` | TEXT | capability_hash after event |
| `recorded_at` | TIMESTAMP | |

---

## Trigger Chain

Three independent triggers, one shared outcome (updated harness_records + rewritten instruction fences):

### Trigger A — Full Probe
**When:** install · init · repair · `synlynk probe` manual invocation

**Flow per agent:**
1. Version fingerprint — run `<cli> --version`, compare to `harness_records.installed_version`. If version unchanged and `capability_hash` matches baseline → skip deep probe (fast path).
2. Baseline lookup — query `harness_baselines` for `(harness, cli_version)`. If found: load curated contract + flags.
3. Dynamic discovery (baseline missing or version gap) — parse `--help` tree for flag signatures; attempt minimal headless smoke test (echo task, 5s timeout, verify stdout flushes). Mark `baseline_source: discovered`. Status stays `unknown` until doctor runs TC-1–TC-4.
4. Network preflight — TCP connection check per `network_deps.required_endpoints[]`.
5. Write `harness_records` — upsert `active_contract`, `active_flags`, `compliance_status`, `capability_hash`. Append to `harness_version_history` if hash changed.
6. Rewrite instruction fence — update managed section in `CLAUDE.md`, `GEMINI.md`, etc. with current contract and flags.
7. Full palette scan — parse full `--help` tree, populate `harness_command_palette`, diff against previous version to detect additions/removals.

### Trigger B — Dispatch Preflight
**When:** every `synlynk dispatch` call. Reads `harness_records` only — no CLI spawn. Target: ~2s.

| Check | Failure sentinel |
|---|---|
| Version match — run `--version`, compare to `installed_version` | `HARNESS_VERSION_DRIFT` |
| Flag validation — verify job dispatch flags against `active_flags[]` | `HARNESS_PREFLIGHT_FAIL` |
| Network reachability — TCP ping `required_endpoints` | `HARNESS_PREFLIGHT_FAIL` |

On any failure: dispatch blocked with clear error message. Sentinel fired. Background `synlynk doctor` queued for affected agent.

### Trigger C — Stall Detection
**When:** job running + zero log bytes after `stall_timeout_minutes` (configurable per agent in `.synlynk/config.json`, default 30).

**Flow:** Kill job. Fire `STALL_NO_OUTPUT` sentinel with agent name + job ID. Queue background `synlynk doctor` for affected agent.

---

## synlynk doctor — Compliance Suite

Triggered by sentinel (background) or manual `synlynk doctor`. Spawns the actual CLI. Updates `harness_records` and rewrites instruction fence on completion.

### TC-1 — Headless Stdout Contract
Spawn a minimal task in pipe mode (no PTY). Verify stdout flushes within 5s. If hang detected: retry with PTY, update `headless_contract.requires_pty = true`, update `stdout_flush_method`. Record which mode actually works. This directly addresses the Agy LIVE-1 failure.

### TC-2 — Flag Compliance
For each flag in `dispatch_flags`: attempt invocation with `--help` or a dry-run equivalent. Record pass/fail per flag. Identifies flags in config that are rejected by the installed binary (Grok `--always-approve` case).

### TC-3 — Network Dependency
Full connectivity check: DNS resolution + TCP handshake per `required_endpoint`. Mark each as reachable · unreachable · latency-degraded. Update `harness_records.active_contract`.

### TC-4 — Verb Map Validation
For each synlynk verb mapped to this harness in `harness_verb_map`: verify the `agent_command` template produces a valid invocation against the installed version. Update `supported` status. Flag new parity gaps. Fire `HARNESS_VERSION_DRIFT` if any verb's support status changes.

---

## New Sentinel Patterns

| Pattern | Trigger | Action |
|---|---|---|
| `STALL_NO_OUTPUT` | Job running + zero log bytes after `stall_timeout_minutes` | Kill job · alert operator · queue doctor |
| `HARNESS_PREFLIGHT_FAIL` | Dispatch preflight check fails | Block dispatch · clear error with agent + failed check · queue doctor |
| `HARNESS_VERSION_DRIFT` | CLI version changed OR capability_hash diff OR verb support status change | Alert operator · queue doctor · append to `harness_version_history` |

`stall_timeout_minutes` is configured per agent in `.synlynk/config.json`:
```json
{
  "agents": {
    "agy": { "stall_timeout_minutes": 45 },
    "grok": { "stall_timeout_minutes": 20 }
  }
}
```

---

## Agent Instruction Fence

synlynk owns one delimited section in each agent instruction file. Everything outside is human-authored and untouched.

### Format

```
<!-- synlynk:harness v{harness_version} verified:{ISO_timestamp} -->
# Harness Instructions (synlynk-managed — do not edit)

## Headless Execution Contract
- Execution mode: pipe | pty
- Non-interactive flag: --non-interactive
- Stdout flush: unbuffered (set PYTHONUNBUFFERED=1) | native
- Stall timeout: 45min (configured in .synlynk/config.json)

## Active Dispatch Flags (verified {harness_version})
- Valid: --non-interactive --model --prompt --output-format
- Invalid (do not use): --always-approve

## Network Dependencies
- Required: generativelanguage.googleapis.com:443 ✓ reachable

## Parity Gaps
- dispatch.approve not supported in this harness version
<!-- /synlynk:harness -->
```

### Upsert Rules

| State | Behaviour |
|---|---|
| Fence exists | Regex match on open/close tags; replace entire block in-place. Surrounding content byte-preserved. |
| Fence missing | Append at end of file with blank line separator. Never inserts mid-file on first write. |
| File missing | Log warning: `"GEMINI.md not found — fence skipped. Run synlynk init to create."` Do not create file. |

---

## Command Interoperability Matrix

### Full Verb Coverage

The matrix covers all synlynk verb categories:

| Category | Verbs |
|---|---|
| dispatch | dispatch.task · dispatch.headless · dispatch.resume · dispatch.approve · dispatch.model · dispatch.tools · dispatch.context |
| observability | jobs · status · telemetry · costs |
| harness | probe · doctor |
| pm | story · epic · decide |
| workspace | workspace · upgrade |

PM and workspace verbs (`story`, `epic`, `decide`, `workspace`) have no harness equivalent — `supported: none` there means not applicable. synlynk owns these exclusively; they are not mapped to any harness command.

### Parity Gap Handling

| Status | Behaviour |
|---|---|
| `partial` | Dispatch proceeds with degraded-mode flag. Warning logged: `"dispatch.tools partially supported on agy — proceeding without tool restriction."` Outcome noted in telemetry. |
| `none` | Dispatch blocked. Error with alternative: `"dispatch.approve not supported on grok. Use --agent claude or --agent codex for approval-gated tasks."` |

### Extension Opportunity Surface

`harness_command_palette` rows where `synlynk_verb IS NULL` across 2+ harnesses are surfaced in `synlynk doctor --report` as "unmapped capabilities." These are candidate new synlynk verbs. Removal of a command between versions fires `HARNESS_VERSION_DRIFT` proactively — synlynk detects the breaking change before any user hits it.

---

## Implementation Stories

### v0.10.1 (LIVE-1 fixes — immediate)

| Story | Scope |
|---|---|
| story-bs14-sentinel-stall | Add `STALL_NO_OUTPUT` sentinel pattern + `stall_timeout_minutes` config |
| story-bs14-preflight | Dispatch preflight: version match + flag validation + network check → `HARNESS_PREFLIGHT_FAIL` |
| story-bs14-grok-flags | Fix Grok `dispatch_flags`: remove `--always-approve`, add network preflight for `cli-chat-proxy.grok.com` |
| story-bs14-agy-contract | Fix Agy headless contract: pipe mode + `PYTHONUNBUFFERED=1` + PTY fallback |

### v0.11.0 (full system)

| Story | Scope |
|---|---|
| story-bs14-schema | Add five tables to state.db: `harness_baselines`, `harness_records`, `harness_verb_map`, `harness_command_palette`, `harness_version_history` |
| story-bs14-probe | Extend `synlynk probe` with full flow: version fingerprint → baseline lookup → dynamic discovery → palette scan → fence rewrite |
| story-bs14-doctor | Implement `synlynk doctor` compliance suite (TC-1 through TC-4) + background queue via sentinel |
| story-bs14-verb-map | Populate `harness_verb_map` for all four harnesses + full verb category coverage |
| story-bs14-palette | Implement `harness_command_palette` scan + diff + extension opportunity report |
| story-bs14-fence | Implement instruction fence upsert across CLAUDE.md, GEMINI.md, AGENTS.md, Grok.md |
| story-bs14-agent-json | Add `harness` + `model` fields to `.agents/<agent>.json`; update agent/harness separation throughout |
| story-bs14-drift | Implement `HARNESS_VERSION_DRIFT` sentinel + `harness_version_history` append-only log |

---

## Path to Native Harness (C)

Under this design, the native synlynk harness is just another entry in `harness_baselines` and `harness_records` — with `baseline_source: native` and no subprocess overhead. The normalization layer the user gets today becomes the routing layer that dispatches to native tomorrow. Zero user-visible workflow change on the transition.

`harness_verb_map` rows for native will initially carry `supported: none` (flagged as 🔜). As native capabilities are implemented, rows are updated to `full`. The Command Interoperability Matrix tracks the native harness's growing parity with CLI wrapper mode.
