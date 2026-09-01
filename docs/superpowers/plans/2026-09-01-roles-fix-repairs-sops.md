# Implementation Plan: Repair Stale & Missing SOP Sections during `synlynk roles --fix` (#1231)

- **Issue:** [#1231](https://github.com/nikhilsoman/synlynk/issues/1231)
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-09-01

---

## 1. Code Changes

### 1.1 `synlynk/__init__.py`
- In `cmd_roles(fix: bool = False)`:
  - If `fix=True`, invoke `_repair_sops_only(cfg=cfg, dry_run=False)`.
  - Update user-facing prompt: `Run synlynk roles --fix to write missing role fences and repair SOP sections`.

### 1.2 `synlynk/probe.py`
- In `_repair_config_agents(cfg: dict) -> list`:
  - Combine `cfg.get("workgroup_agents")` and `cfg.get("roles", {}).keys()` to ensure all directive-backed agents (`claude`, `agy`, `codex`, `grok`) present in `roles` are processed during SOP repair.

### 1.3 `synlynk/cli.py`
- In `roles_parser`:
  - Update `--fix` argument help string: `Write missing role fences and repair stale/missing SOP sections in directive files`.

### 1.4 `tests/test_roles.py`
- Add `test_cmd_roles_fix_repairs_missing_sops_in_fenced_file()`:
  - Create a fenced `CLAUDE.md` lacking `## Herdr Workspace Protocol`.
  - Call `synlynk.cmd_roles(fix=True)`.
  - Assert that `CLAUDE.md` now contains `## Herdr Workspace Protocol` and `## PR Review Discipline`.
- Add `test_cmd_roles_fix_refreshes_stale_sops()`:
  - Create a fenced `CLAUDE.md` with stale `synlynk pr check <pr#>` text.
  - Call `synlynk.cmd_roles(fix=True)`.
  - Assert that `CLAUDE.md` is refreshed with canonical content.

### 1.5 Documentation & Devlogs
- Blog post 153: `docs/blog/153-pr1321-roles-fix-repairs-sops.md`.
- Update `docs/blog/README.md`.
- Record decision in `project-docs/memory.md`.
- Update `project-docs/devlogs/nikhilsoman.md`.

---

## 2. Verification Plan
- `pytest tests/test_roles.py -v`
- `pytest tests/test_agent_quota_tracking.py -k test_repair_sops_only -v`
- `pytest tests/test_synlynk.py -q`
- `python -m synlynk pr check`
- Open PR, dispatch review to Codex, and merge.
