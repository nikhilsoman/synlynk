# `synlynk/__init__.py` Re-modularization (Pass 2) — Design

**Date:** 2026-07-12
**Related:** roadmap.md "`__init__.py` Modularisation" cross-cutting epic (⚠️ Regressed) · issue #109 (audit of the 2026-07-01 first pass, commit `222f7da`) · GOVERNS SDLC taxonomy (`docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md`)

## Problem

The first modularization pass (2026-07-01) extracted `probe.py`, `dispatch.py`, `sentinel.py`, and `upgrade.py`, briefly bringing `synlynk/__init__.py` from 11,268L down to ~1,500L. Since then, new feature work (BS-16 status, Capability Matrix Hardening, Job Lifecycle epic, FTUE wizard, etc.) landed directly back into `__init__.py` instead of into new or existing modules. As of 2026-07-12 it is **10,818L** — 7x the original target, effectively back to monolith size. No guardrail existed to prevent this regrowth.

Also found during investigation: `_generate_context_from_db` is defined **twice** in `__init__.py` (line 7909 and line 7989) — the second definition silently shadows the first. This is a latent bug independent of the modularization and should be fixed in the same pass since both definitions are being moved anyway.

## Goal

Extract the ~10 subsystems currently tangled in `__init__.py` into their own modules, following the same pattern already established by `probe.py`/`dispatch.py`/`sentinel.py`/`upgrade.py`/`db.py`/`cli.py`/`viz.py`/`hud.py`/`status.py`/`scheduler.py`/`observatory.py`. Add a CI guardrail so this doesn't regress a third time.

## Architecture

`cli.py` already owns all argparse wiring and imports command implementations from `synlynk` (confirmed: `cli.py:1-320` has zero business logic beyond `cmd_watch` and `main()`). This means the re-modularization is a **pure move-and-re-export refactor** — no CLI-facing behavior changes, no argparse changes. `__init__.py` keeps re-exporting every moved symbol so `from synlynk import X` call sites (used throughout the test suite and `cli.py`) keep working unchanged.

Module boundaries are chosen by **code cohesion** (shared data structures, functions that are tested and called together) — not by GOVERNS SDLC stage. Where a module's contents happen to concentrate in one GOVERNS stage, that's documented as metadata in the module docstring for discoverability, but it does not drive the split. (Full reasoning captured in conversation: several natural modules — `costs.py`, `context.py`, `instructions.py` — are cross-cutting and would be needlessly shattered if forced into single-stage buckets.)

## Module Split

| New module | Contents (top-level `def`/`class` names from `__init__.py`) | Approx. lines | GOVERNS stage(s) (docstring only) |
|---|---|---|---|
| `synlynk/wizard.py` | `_wiz_clear`, `_wiz_read_key`, `_kbhit`, `_card_summary`, `_render_one_card`, `_render_expanded_card`, `_render_scan_cards`, `_run_scan_tui`, `_wiz_header`, `_wiz_prompt`, `_wiz_screen_landing`, `_wiz_screen_harness`, `_wiz_screen_topology`, `_wiz_screen_workspace_name_pick`, `_wiz_screen_workspace_confirm`, `_wiz_screen_skills`, `_wiz_screen_agents`, `_wiz_screen_roles`, `_wiz_screen_launch`, `_launch_screen_cycles`, `_launch_screen_preview`, `_launch_screen_tasks`, `wizard_init`, `cmd_launch_ftue` | ~950L | `open` |
| `synlynk/scan.py` | `_static_scan`, `_infer_industry`, `find_git_roots`, `fingerprint_stack`, `scan_skills`, `detect_home_harness`, `parse_context_sections`, `_scan_stage_source`, `_scan_stage_complexity`, `_scan_stage_tests`, `_scan_stage_git`, `_scan_stage_arch`, `_scan_stage_stack`, `run_workspace_scan`, `_workspace_config_dir`, `write_workspace_config`, `generate_structured_context`, `_score_source_files`, `_scan_source_skeleton`, `_query_repo_file_tree`, `_scan_full_repo`, `_check_scan_cache`, `_format_source_architecture`, `_scan_repo_for_docs`, `_load_scan_meta`, `_save_scan_meta`, `_extract_symbols`, `_git_head_sha`, `cmd_scan` | ~1,700L | `open`, `visualize` |
| `synlynk/instructions.py` | `_build_templates`, `_build_cursor_mdc`, `_build_copilot_instructions`, `_build_windsurf_rules`, `_write_instruction_file`, `_find_existing_doc`, `_write_informed_skeleton`, `_llm_enrich`, `_generate_ai_context_files`, `_extract_synlynk_section`, `_compute_section_sha`, `_strip_synlynk_section`, `_is_evolved_repo`, `_is_section_covered`, `_extract_gh_ids`, `_load_instruction_manifest`, `_write_instruction_manifest`, `_check_instruction_drift`, `cmd_instructions_status`, `cmd_instructions_diff`, `cmd_instructions_update`, `cmd_instructions_ack` | ~750L | `open`, `sustain` |
| `synlynk/daemon.py` | `WatchDaemon`, `SynlynkDaemon`, `SynlynkRelay`, `_make_daemon_handler`, `_daemon_install_service`, `_daemon_uninstall_service`, `_make_relay_handler`, `cmd_relay_start`, `cmd_relay_broadcast`, `check_daemon_health`, `check_stall` | ~900L | `notify` |
| `synlynk/jobs.py` | `_load_jobs`, `_save_jobs`, `_inspect_worktree_git_state`, `_count_dispatch_rework`, `_extract_micro_rework`, `_count_tool_calls`, `_write_capability_rating`, `_reconcile_jobs`, `_reconcile_daemon_jobs`, `_dispatch_ready_jobs`, `_best_agent_for_story`, `_capability_candidates_for_story`, `cmd_jobs`, `cmd_jobs_handoff` | ~950L | `execute` |
| `synlynk/quota.py` | `_quota_headroom`, `_upsert_agent_quota`, `_project_request_quota_from_config`, `_read_agent_quota_rows`, `_quota_status_for_agent`, `_estimate_story_cost_usd` | ~320L | `execute` |
| `synlynk/context.py` | `generate_context`, `_generate_context_from_db` (**fix the duplicate — see below**), `_append_vizor_notes`, `_write_last_devlog_section`, `_write_recent_devlog_entries`, `_get_last_devlog_date`, `_generate_task_context`, `_relevant_files_for_story`, `_verify_contract_for_story` | ~550L | (cross-cutting — no single stage) |
| `synlynk/costs.py` | `update_costs`, `extract_tokens`, `extract_model_version`, `extract_verifier_meta`, `_model_rate_for_version`, `check_budgets`, `_compute_burn_rate`, `parse_costs_md` | ~280L | (cross-cutting — no single stage) |
| `synlynk/support_engineer.py` | `_collect_test_suite`, `_collect_sentinel_alerts`, `_collect_telemetry_anomaly`, `_collect_capability_drop`, `_collect_github_issues`, `_dedup_findings`, `_run_investigation`, `_file_gh_issue`, `_recommend_handoff_agent`, `_stalled_job_ids_from_sentinel`, `_extract_diff`, `_attempt_fix`, `cmd_agent_run`, `_install_cron_entry`, `cmd_agent_list` | ~650L | `sustain` |
| `synlynk/team.py` | `cmd_join`, `_build_team_digest`, `cmd_team_status`, `cmd_decide`, `_write_decision_record`, `_run_agent_sync`, `_sign_capability_rating`, `_ensure_identity_key`, `cmd_identity_init`, `get_username`, `get_mode` | ~480L | `open`, `notify` |
| `synlynk/doctor.py` | `HealthCheck`, `_hc_python_version`, `_hc_project_init`, `_hc_docs_dir`, `_hc_identity_key`, `_hc_agent_profiles`, `_hc_instruction_files`, `_hc_version_current`, `cmd_doctor`, `_doctor_fix_menu`, `_doctor_maybe_escalate` | ~350L | `sustain` |

**Remains in `__init__.py`** (no clean subsystem home, or genuinely cross-cutting glue): `init()`, `_resolve_db_path`, `_get_db`, `_is_migrated`, `_synlynk_project_docs_dir`, `_dr_sync`, `_docs_dir`, `load_config`, `cmd_config_set`, `_update_config`, `_seed_verb_map`, `_check_verb_support`, `_load_agent_config`, `_load_agent_profile`, `_dispatch_flags_for_agent`, `cmd_roles`, `_template_matches`, `_select_launch_tasks`, `_render_prompt`, `_infer_engg_domain`, `_build_relay_event`, `_check_upstream_divergence`, `_seed_devlog`, `cmd_status`, `_print_platform_health`, `_print_platform_table`, `_load_platform_harness_rows`, `_load_platform_drift_agents`, `_load_platform_budget_pulse`, `_load_telemetry_events`, `_parse_status_timestamp`, `_humanize_ago`, `cmd_release`, `checkpoint`, `_archive_old_devlog_entries`, `cmd_shell`, `cmd_logs`, `cmd_launch`, `cmd_run_trio`, `cmd_agent_configure`, `cmd_configure_agent`, `_is_interactive`, `_inject_grok_rules`, `_tee_process`, `detect_remote_owner_repo`, `set_state`, `discover_agents`, `_check_agent_functional`, plus re-export imports for every symbol moved to the new modules above.

Expected final size: **~1,900–2,200L** (close to the original ~1,500L target, slightly higher because more commands now exist than in the first pass).

## The duplicate `_generate_context_from_db` fix

Two definitions exist (line 7909, line 7989). Implementation must:
1. Diff the two function bodies.
2. If identical (or the second is a superset/bugfix of the first, which is the common case for accidental duplication via merge/copy-paste) — keep the second (later-defined, i.e., the one actually in effect at runtime) and delete the first.
3. If they differ in a way that suggests the first was doing something the second lost — flag it in the PR description rather than silently picking one; do not guess.

## CI Guardrail

Add a step to the existing test workflow (`.github/workflows/*.yml` — implementer to identify the right job) that runs after checkout:

```bash
LINES=$(wc -l < synlynk/__init__.py)
if [ "$LINES" -gt 2500 ]; then
  echo "::error::synlynk/__init__.py is ${LINES} lines (limit 2500). New code belongs in a module, not __init__.py. See docs/superpowers/specs/2026-07-12-init-remodularization-design.md."
  exit 1
fi
```

Threshold: **2,500L** (buffer above the ~2,000-2,200L expected post-extraction size, tight enough to catch regrowth early rather than let it reach 10K again before anyone notices).

## Testing

- No new tests required for the moves themselves — the existing suite (973+ tests) exercises these functions via `from synlynk import X`, which keeps working through `__init__.py` re-exports.
- One new/updated test for the `_generate_context_from_db` duplicate fix, scoped based on what the diff-and-decide step above finds.
- Full suite must pass unchanged after the move — this is the acceptance bar (same as the first extraction, which shipped 740 passing tests with zero regressions).
- New guardrail CI step gets no test of its own (it's a build-time check, not application code) — verified manually by confirming it fails locally against current `__init__.py` size before the extraction, and passes after.

## Delivery

Single design (this doc) → single implementation plan → one Codex dispatch job (mirrors the original `job-421b7f01` from the first pass) → one PR, diff-reviewed the same way the Job Lifecycle epic PRs (#130-133) were — each extraction step independently verified against the full test suite before merge.

## Out of scope

- No CLI-facing behavior changes.
- No changes to `cli.py`'s argparse wiring.
- No renaming of existing already-extracted modules (`probe.py`, `dispatch.py`, etc.).
- No changes to the GOVERNS stage taxonomy itself — docstring stage annotations are informational only, not enforced or validated by tooling.
