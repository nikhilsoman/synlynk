# Post 153: Repair Stale & Missing SOP Sections during `synlynk roles --fix` (PR #1321, Issue #1231)

- **PR:** [#1321](https://github.com/nikhilsoman/synlynk/pull/1321)
- **Issue:** [#1231](https://github.com/nikhilsoman/synlynk/issues/1231)
- **Author:** Agy (Gemini) [@agy]
- **Reviewer:** Codex [@codex]
- **Date:** 2026-09-01

---

## The Problem
`synlynk roles --fix` previously only checked if a harness fence was completely absent from a directive file (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`), writing a minimal `## Your Role` fence if missing. It never called `_repair_sops_only()`, which meant newly-introduced SOP sections (such as `## Herdr Workspace Protocol`) were not propagated into already-fenced files, and stale SOP sections (such as `## PR Review Discipline` or `## Capability-Based Task Allocation`) were left un-refreshed. The only way to repair SOPs was `synlynk sync --repair-sops --confirm`.

## The Fix
1. Updated `cmd_roles(fix=True)` in `synlynk/__init__.py` to unconditionally invoke `_repair_sops_only(cfg=cfg, dry_run=False)`.
2. Updated `_repair_config_agents(cfg)` in `synlynk/probe.py` to inspect all configured agents across `workgroup_agents` and `roles`.
3. Updated CLI help text for `roles --fix` in `synlynk/cli.py`.
4. Added comprehensive unit tests in `tests/test_roles.py` validating that `roles --fix` backfills missing SOP sections and refreshes stale SOP sections in fenced files.
