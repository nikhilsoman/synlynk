# Standardizing Harness vs. Workspace Agent Separation — Design

**Date:** 2026-08-30  
**Status:** Approved  
**Author:** Agy (implementer), brainstormed with Nikhil Soman  
**Issue:** Resolves #1255 (Parent: #1198, follow-up to #1202)  
**Tracking Story:** `story-a646edf9`  
**Linked Goals:** `goal-a222b393` (primary), `goal-85656c82` (secondary)  

---

## 1. Motivation & Problem Statement

In early versions of Synlynk, the term "agent" was used colloquially to describe two fundamentally different concepts:
1. **The execution backend tool / CLI:** `claude`, `codex`, `grok`, `agy`, `local`.
2. **The functional role and accountability identity:** `pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot`.

This conflation caused severe operational ambiguity:
* A command like `synlynk dispatch codex --as-agent dev` used "agent" in two conflicting senses in the very same invocation: the positional argument was called `agent` in the parser (but accepted a harness like `codex`), while `--as-agent` accepted an org-chart role (`dev`).
* The CLI verb was renamed to `synlynk harness` (PR #993), but its underlying implementation functions remained `cmd_agent_add`, `cmd_agent_configure`, `cmd_agent_list`, reading from a directory called `.agents/<harness>.json`.
* In `state.db`, the `daemon_jobs` table has column `agent` (storing the harness name `"claude"`) alongside `agent_id` (storing the workspace agent UUID `109dc5d1-...`).
* In living strategy documents and instruction files, harnesses were repeatedly referred to as "workspace agents," obscuring that the 8 Workspace Agents are durable roles that *use* harnesses as swappable compute resources.

PR #1254 (closing issue #1202) performed a non-breaking sweep of docstrings and comments in `synlynk/*.py`. Issue #1255 was filed to make the architectural decision on the remaining load-bearing surfaces (CLI flags, directory names, configuration files, and database schemas) and define a clean deprecation and migration path.

---

## 2. Core Definitions & Ontological Boundary

Per `docs/glossary-agent-vs-harness.md` and `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md`:

### 2.1 Workspace Agent (Identity, Role, Charter, Accountability)
* **What it is:** A persistent identity representing an org-chart role in a workspace.
* **The Roster (8 Agents):** `pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot` (plus user-defined workspace extensions such as `devops`).
* **Attributes:**
  * **Charter:** Stored in `~/.synlynk/workspaces/<id>/agents/<agent_id>/charter.md` (validated via `synlynk/charter_schema.py`).
  * **Durability:** `durable` (e.g. `pm`, `tpm`, `qa`/Support Engineer), `session-only` (`architect`), or `dispatch-only` (`dev`, `designer`, `marketing`).
  * **GitHub App Identity:** Unique bot credentials provisioned per role (`synlynk-<repo>-<role>[bot]`).
  * **Workflow Accountability:** Owns specific stages of the development lifecycle (Brainstorming, Spec, Plan, Implement, Test, Review, Merge, Release, Comms).
* **Rule:** Agents are the **actors who own the work**.

### 2.2 Harness (Execution Backend, CLI Tool, Model Provider)
* **What it is:** A swappable execution backend that runs dispatched tasks.
* **The Fleet:** `claude`, `codex`, `grok`, `agy`, `local`.
* **Attributes:**
  * **Tool Execution:** Vendor CLI binaries (`claude-cli`, `codex exec`, `grok`, `agy`).
  * **Sandboxing & Flags:** Non-interactive execution contracts (`-s workspace-write`, `--always-approve`, `--print-timeout 30m0s`, `--print`).
  * **Telemetry & Accounting:** Token counting, prompt cache extraction, context window limits, and dollar cost ledgering.
* **Rule:** Harnesses are **compute and model resources** used by Workspace Agents and the human admin.

### 2.3 The Relationship Matrix
A Workspace Agent is mapped to a Harness dynamically based on capability fit, token quota, and policy overrides defined in `.synlynk/policy.json`:
* `dev` agent → dispatched via `codex` (CLI/refactor), `grok` (canvas/JS/infra), or `agy` (general implementation).
* `designer` agent → dispatched via `agy` (templates/CSS).
* `qa` agent → dispatched via `codex` (test writing/review), `grok` (CI/CD), or Support Engineer (durable watchdog).
* `pm` & `architect` agents → dispatched via `claude` (decisions, specs, plans, merge review).

All writes to GitHub attribute to the **Workspace Agent's** App identity, regardless of which Harness executed the turn.

---

## 3. Four-Phase Separation Roadmap

To ensure 100% operational continuity and zero breaking changes across scripts or muscle memory, the separation executes in four phased vertical slices:

```mermaid
flowchart TD
    subgraph Phase 1: Docs & Strategy Cleansing
        D1[docs/strategy/2026-08-15-two-imperatives-roadmap.md]
        D2[Instruction preambles in GEMINI.md, CLAUDE.md, GROK.md]
        D3[synlynk/probe.py task allocation table headers]
    end

    subgraph Phase 2: CLI Aliases & Deprecation Layer
        C1[synlynk dispatch: --harness canonical, --role / --as-agent]
        C2[--force-harness canonical, --force-agent deprecated alias]
        C3[synlynk quota & jobs handoff: --harness and --to-harness canonical]
    end

    subgraph Phase 3: Configuration & Internal Renaming
        F1[.harnesses/ canonical directory, .agents/ fallback]
        F2[.synlynk/harness-allocations.json replaces capability-roles.json]
        F3[Rename cmd_agent_* -> cmd_harness_* with aliases]
    end

    subgraph Phase 4: Database Schema Clarification
        S1[daemon_jobs: add harness column mirroring agent]
        S2[cost_entries: add harness and role columns for dual reporting]
        S3[agent_quotas -> harness_quotas alias/view]
    end

    Phase 1 --> Phase 2 --> Phase 3 --> Phase 4
```

---

## 4. Phase Specifications

### Phase 1: Documentation & Instruction Cleansing (Immediate, Non-Breaking)
1. **Strategy Docs:**
   * Fix line 7 in `docs/strategy/2026-08-15-two-imperatives-roadmap.md` to remove "workspace agents (Agy/Grok/Codex)" and replace with:
     > *"1. **Execution autonomy** — workspace agents (`dev`, `qa`, `designer`, `marketing`) execute implementation and verification tasks through autonomous harnesses (`codex`, `grok`, `agy`); Claude stays `pm`/review/deploy only."*
2. **Instruction File Preambles:**
   * Update preamble sections in `GEMINI.md`, `CLAUDE.md`, `GROK.md`:
     * Replace `- **Agent name:** Agy` with `- **Harness:** Agy`.
     * Clarify: *"You are executing as a Harness backend. When dispatched, your role identity is passed via `--as-agent <role>` (e.g. dev, qa, pm)."*
3. **Capability Allocation SOP (`synlynk/probe.py`):**
   * Change table headers from `| Role | Harness | Tasks |` to:
     `| Task Domain | Preferred Harness | Fallback Harnesses | Assigned Agent Role |`
   * Clearly separate the skill domain from the Workspace Agent who owns that stage.

### Phase 2: CLI Surface Flag Standardization & Aliases
1. **`synlynk dispatch`:**
   * Support: `synlynk dispatch --harness <name> --role <role> --task "..."`
   * Positional argument handling:
     * If the first positional argument matches a known harness (`claude`, `codex`, `grok`, `agy`, `local`), treat it as `harness`.
     * If the positional argument is omitted, and `--as-agent <role>` (or `--role <role>`) is provided, resolve the default harness via `.synlynk/policy.json`.
   * Add `--force-harness`: Bypasses capability routing to pin the exact harness.
   * Deprecate `--force-agent`: Alias to `--force-harness` with a soft stderr warning:
     `warning: --force-agent is deprecated, use --force-harness instead`
2. **`synlynk quota` and `synlynk jobs handoff`:**
   * Make `--harness` canonical in `synlynk quota` (mirroring `synlynk credit grant`).
   * In `synlynk jobs handoff`, add `--to-harness` as canonical, deprecating `--to-agent`.
3. **Extend `_warn_deprecated_harness_flag`:**
   * Expand CLI warning handler to catch `--force-agent` and `--to-agent`.

### Phase 3: Configuration & Code Internals Alignment
1. **Harness Profile Directory (`.harnesses/` vs `.agents/`):**
   * The canonical location for harness execution profiles (`claude.json`, `codex.json`, etc.) becomes `.harnesses/` (or `harnesses/` in repo root).
   * Synlynk will check for `.harnesses/` first. If absent, it transparently falls back to `.agents/` or `agents/`.
2. **Harness Capability Config:**
   * Support `.synlynk/harness-allocations.json` alongside `.synlynk/capability-roles.json`.
   * Reserve `.synlynk/roles.yaml` strictly for the 8 Workspace Agent roster.
3. **Internal Function Renames (`synlynk/support_engineer.py` & `synlynk/cli.py`):**
   * Rename:
     * `cmd_agent_add` → `cmd_harness_add`
     * `cmd_agent_configure` → `cmd_harness_configure`
     * `cmd_agent_list` → `cmd_harness_list`
     * `cmd_agent_run` → `cmd_harness_run`
   * Export backwards-compatible aliases for all renamed functions so third-party calls or older tests do not fail.

### Phase 4: Database Schema Dual-Read / Dual-Write
1. **`daemon_jobs`:**
   * Add `harness TEXT` column.
   * On write: `harness` is populated with the harness name (e.g. `"codex"`). `agent` is written identically for backwards compatibility.
   * On read: `job.get("harness") or job.get("agent")`.
   * Ensure `agent_id` consistently stores the Workspace Agent UUID, and `role` stores the Agent role slug (`dev`, `qa`, etc.).
2. **`cost_entries`:**
   * Add `harness TEXT` and `agent_role TEXT`.
   * Populated on every dispatch completion.
   * Enables dual-dimension reporting:
     * **By Harness:** Total spending across OpenAI Codex, Anthropic Claude, Google Gemini, xAI Grok.
     * **By Workspace Agent:** Total spending across `dev`, `qa`, `architect`, `pm`.

---

## 5. Verification & Test Plan (TDD)

1. **CLI Flag Aliasing Tests:**
   * Verify `synlynk dispatch --force-harness` sets `force_agent = True`.
   * Verify `synlynk dispatch --force-agent` emits deprecation warning to stderr and behaves identically.
   * Verify `synlynk jobs handoff --to-harness` is accepted.
2. **Configuration Fallback Tests:**
   * Verify `cmd_harness_list()` and `cmd_harness_configure()` work when `.harnesses/` is present.
   * Verify they fall back to `.agents/` when `.harnesses/` is absent.
3. **Instruction Rendering Tests:**
   * Verify generated fences and preambles use "Harness" for execution engines and "Agent" for roles.
4. **Full Regression Suite:**
   * Ensure all 472+ core tests pass cleanly with zero regressions.
