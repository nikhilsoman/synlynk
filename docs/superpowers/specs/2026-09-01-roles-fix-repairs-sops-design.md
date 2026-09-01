# Design Spec: Repair Stale & Missing SOP Sections during `synlynk roles --fix` (#1231)

- **Issue:** [#1231](https://github.com/nikhilsoman/synlynk/issues/1231)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01
- **Status:** APPROVED

---

## 1. Context & Problem Statement

`synlynk roles --fix` (`cmd_roles` in `synlynk/__init__.py`) previously only checked whether a harness fence was present in each agent directive file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`). If missing, it wrote a minimal `## Your Role` fence.

However:
1. `cmd_roles` never invoked `_repair_sops_only()`, meaning it could not backfill newly-added SOP sections (e.g. `## Herdr Workspace Protocol`) into files that already possessed a fence.
2. It could not refresh stale SOP sections whose canonical text had evolved (e.g. `## PR Review Discipline`, `## Capability-Based Task Allocation`).
3. `_repair_sops_only()` was only reachable via `synlynk sync --repair-sops --confirm`, creating a tooling dead-end for developers expecting `roles --fix` to be the primary command to update directive files.

---

## 2. Proposed Architecture

### 2.1 Invoke `_repair_sops_only()` in `cmd_roles(fix=True)`
When `synlynk roles --fix` is invoked:
1. Continue generating missing fences for directive files where none exist.
2. Unconditionally invoke `_repair_sops_only(cfg=cfg, dry_run=False)` across all configured agents (`_repair_config_agents(cfg)`).
3. Ensure `_repair_config_agents(cfg)` considers all agents configured in `cfg["roles"]` in addition to `cfg["workgroup_agents"]`.

### 2.2 CLI Help Text & Guidance
Update `roles_parser` help text and `cmd_roles` messaging to clearly state that `roles --fix` writes missing fences and repairs stale or missing SOP sections.

---

## 3. Testing & Verification Plan

- Unit tests in `tests/test_roles.py`:
  - Assert that `synlynk.cmd_roles(fix=True)` backfills missing SOP sections (e.g. `## PR Review Discipline`, `## Herdr Workspace Protocol`) into an existing fenced directive file.
  - Assert that `synlynk.cmd_roles(fix=True)` refreshes stale SOP sections in fenced directive files.
  - Assert that `synlynk.cmd_roles(fix=True)` writes both the fence and complete SOP sections for an unfenced directive file.
- Full suite verification: `pytest tests/test_synlynk.py -q`.
- PR check: `python -m synlynk pr check`.
