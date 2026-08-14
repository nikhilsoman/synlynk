#!/usr/bin/env python3
import argparse
import sys
import os
import subprocess
import shutil
import time
import json
import re
import threading
import tempfile
import urllib.request
from pathlib import Path
from typing import Optional, Tuple
import sqlite3 as _sqlite3

from synlynk._constants import (
    AGENT_CAPABILITY_BASELINES,
    HARNESS_TIMEOUT_PATTERNS,
    QUOTA_PATTERNS,
    VERSION,
    _INSTALL_SCRIPT_URL,
)
from synlynk.upgrade import (
    _detect_install_type,
    _get_pipx_source,
    _run_upgrade,
    _ver_tuple,
    _warn_stale_script_install,
    upgrade,
)
from synlynk.sentinel import (
    _check_costs_freshness,
    _extract_auto_signals,
    _extract_compliance_tags,
    _read_sentinel_alerts,
    _summarize_sentinel_alerts,
    _write_sentinel_alert,
    check_model_rates_freshness,
    check_sentinel_patterns,
    log_telemetry_event,
    sentinel_clear,
    sentinel_list,
)
from synlynk.probe import (
    _compute_capability_hash,
    _scan_command_palette,
    _scan_repo_requirements,
    _build_fence_content,
    _upsert_harness_fence,
    _write_scan_fences,
    _build_fence_body_from_record,
    _probe_agent,
    _run_tc0,
    _run_tc1,
    _run_tc2,
    _run_tc3,
    _run_tc4,
    _run_tc5,
    _run_tc6,
    _repair_capability_allocation_sop,
    _repair_sops_only,
    cmd_probe,
    _fence_exists,
    _probe_model_version,
)
from synlynk.fencing import FenceData, render_task_fence
from synlynk.dispatch import (
    _spawn_with_pty_fallback,
    _is_interactive,
    _inject_grok_rules,
    _tee_process,
    _check_pre_exec_gate,
    _check_job_stall,
    _resolve_worktree_base_commit,
    _worktree_files_touched,
    _job_summary_path,
    _format_job_summary,
    _write_job_summary,
    _format_prompt_for_agent,
    _warn_context_size,
    _preflight_dispatch,
    dispatch_agent,
    exec_command,
)
from synlynk.quota import (
    _estimate_story_cost_usd,
    _force_exhaust_quota,
    _open_reservation,
    _open_reservations_sum,
    _project_request_quota_from_config,
    _quota_headroom,
    _quota_status_for_agent,
    _read_agent_quota_rows,
    _refresh_agent_quotas_from_telemetry,
    _release_reservation,
    _upsert_agent_quota,
    cmd_quota,
    cmd_quota_tpm_view,
    refresh_agent_quotas_from_telemetry,
)
from synlynk.costs import (
    _TokenCounts,
    _compute_burn_rate,
    _model_rate_for_version,
    check_budgets,
    extract_model_version,
    extract_tokens,
    extract_verifier_meta,
    _log_has_permission_denied_signature,
    parse_costs_md,
    update_costs,
)
from synlynk.capability_roles import _load_capability_roles
from synlynk.taxonomy import entries_for_tier
from synlynk.doctor import (
    HEALTH_CHECKS,
    HealthCheck,
    _doctor_fix_menu,
    _doctor_maybe_escalate,
    _hc_agent_profiles,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_instruction_files,
    _hc_model_rates,
    _hc_project_init,
    _hc_python_version,
    _hc_version_current,
    cmd_doctor,
)
from synlynk.team import (
    _build_team_digest,
    _build_app_manifest_url,
    _run_manifest_callback_server,
    _ensure_identity_key,
    _exchange_manifest_code,
    _confirm_installation,
    _run_agent_sync,
    _sign_capability_rating,
    _write_role_app_config,
    _write_decision_record,
    cmd_decide,
    cmd_identity_init,
    cmd_identity_init_role,
    cmd_identity_list,
    cmd_join,
    cmd_team_status,
    get_mode,
    get_username,
)
from synlynk.support_engineer import (
    _attempt_fix,
    _collect_capability_drop,
    _collect_github_issues,
    _collect_sentinel_alerts,
    _collect_telemetry_anomaly,
    _collect_test_suite,
    _dedup_findings,
    _extract_diff,
    _file_gh_issue,
    _install_cron_entry,
    _recommend_handoff_agent,
    _run_investigation,
    _stalled_job_ids_from_sentinel,
    cmd_agent_list,
    cmd_agent_run,
)
from synlynk.context import (
    _append_vizor_notes,
    _generate_context_from_db,
    _generate_task_context,
    _get_last_devlog_date,
    _relevant_files_for_story,
    _verify_contract_for_story,
    _write_last_devlog_section,
    _write_recent_devlog_entries,
    generate_context,
)
from synlynk.jobs import (
    _best_agent_for_story,
    _capability_candidates_for_story,
    _count_dispatch_rework,
    _count_tool_calls,
    _dispatch_ready_jobs,
    _extract_micro_rework,
    _inspect_worktree_git_state,
    _load_jobs,
    _reconcile_daemon_jobs,
    _reconcile_jobs,
    _save_jobs,
    _write_capability_rating,
    cmd_jobs,
    cmd_jobs_handoff,
    cmd_jobs_reap,
)
from synlynk.story_provisioning import (
    _classify_heuristic,
    _detect_issue_number,
    classify_story,
    cmd_backfill_capability_ratings,
    resolve_or_create_story_id,
)
from synlynk.daemon import (
    SynlynkDaemon,
    SynlynkRelay,
    WatchDaemon,
    _daemon_install_service,
    _daemon_uninstall_service,
    _make_daemon_handler,
    _make_relay_handler,
    check_daemon_health,
    check_stall,
    cmd_relay_broadcast,
    cmd_relay_start,
)

from synlynk.instructions import (
    _build_copilot_instructions,
    _build_cursor_mdc,
    _build_templates,
    _build_windsurf_rules,
    _check_instruction_drift,
    _compute_section_sha,
    _extract_gh_ids,
    _extract_synlynk_section,
    _find_existing_doc,
    _generate_ai_context_files,
    _is_evolved_repo,
    _is_section_covered,
    _llm_enrich,
    _load_instruction_manifest,
    _strip_synlynk_section,
    _write_informed_skeleton,
    _write_instruction_file,
    _write_instruction_manifest,
    install_pre_commit_hook,
    cmd_instructions_ack,
    cmd_instructions_diff,
    cmd_instructions_status,
    cmd_instructions_update,
)

from synlynk.scan import (
    _check_scan_cache,
    _extract_symbols,
    _format_source_architecture,
    _git_head_sha,
    _infer_industry,
    _load_scan_meta,
    _query_repo_file_tree,
    _save_scan_meta,
    _scan_full_repo,
    _scan_repo_for_docs,
    _detect_harnesses_on_path,
    _scan_source_skeleton,
    _scan_stage_arch,
    _scan_stage_complexity,
    _scan_stage_git,
    _scan_stage_source,
    _scan_stage_stack,
    _scan_stage_tests,
    _score_source_files,
    _static_scan,
    _workspace_config_dir,
    cmd_scan,
    detect_home_harness,
    find_git_roots,
    fingerprint_stack,
    generate_structured_context,
    parse_context_sections,
    run_workspace_scan,
    scan_skills,
    write_workspace_config,
)

# Fallback roadmap text still includes "## Business Goals".
from synlynk.hud import CYCLES

from synlynk.wizard import (
    _card_summary,
    _kbhit,
    _launch_screen_cycles,
    _launch_screen_preview,
    _launch_screen_tasks,
    _render_expanded_card,
    _render_one_card,
    _render_scan_cards,
    _run_scan_tui,
    _wiz_clear,
    _wiz_header,
    _wiz_prompt,
    _wiz_read_key,
    _wiz_screen_agents,
    _wiz_screen_harness,
    _wiz_screen_landing,
    _wiz_screen_launch,
    _wiz_screen_roles,
    _wiz_screen_skills,
    _wiz_screen_topology,
    _wiz_screen_workspace_confirm,
    _wiz_screen_workspace_name_pick,
    cmd_launch_ftue,
    wizard_init,
)

CYCLE_COLORS = {
    "dream":   "#a78bfa",
    "design":  "#60a5fa",
    "plan":    "#34d399",
    "build":   "#fbbf24",
    "ship":    "#f87171",
    "sustain": "#94a3b8",
}

CYCLE_DESCRIPTIONS = {
    "dream":   "What's worth building\nIdeate, assess, identify opportunities\n",
    "design":  "Brainstorm -> spec -> UX\nTurn ideas into a concrete brief\n",
    "plan":    "Implementation plan, story breakdown, agent wave schedule\n",
    "build":   "Dispatch agents, run jobs, iterate on diffs\n",
    "ship":    "Cut release, changelog, publish\n",
    "sustain": "Monitor, patch, community, docs, support\n",
}

CYCLE_DEFAULT_AGENTS = {
    "dream":   ["claude"],
    "design":  ["claude"],
    "plan":    ["claude"],
    "build":   ["agy", "codex", "grok"],
    "ship":    ["claude"],
    "sustain": ["claude", "agy", "codex", "grok"],
}

CORE_TEMPLATE_IDS = {"arch-review", "product-assessment", "lifecycle-setup"}

# Capability scores within this gap are considered ties → break on cost (#140).
_CAPABILITY_COST_TIE_GAP = 0.15

def _launch_visible_template_ids() -> set:
    tier1_primary_ids = {
        entry["command"]
        for entry in entries_for_tier(1)
        if entry["prominence"] == "primary"
    }
    return CORE_TEMPLATE_IDS | tier1_primary_ids


def _launch_visible_templates() -> list:
    visible_ids = _launch_visible_template_ids()
    return [template for template in LAUNCH_TASK_TEMPLATES if template["id"] in visible_ids]


LAUNCH_TASK_TEMPLATES = [
    # ── Core templates (always shown) ───────────────────────────────────────
    {
        "id": "arch-review",
        "title": "Workspace architecture review",
        "description": "Analyse structure, patterns, tech debt. Claude writes findings to memory.md.",
        "cycle": "visualize",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Review the architecture of {workspace} ({stack}, {topology} repo). "
            "Identify: structural patterns in use, top 5 tech debt hotspots (name files "
            "and functions), component coupling risks, and 3 concrete improvement "
            "opportunities with effort estimates. Write your findings as a new section "
            'in .synlynk/project-docs/memory.md under "## Architecture Review {date}". '
            "Be specific — no generic advice."
        ),
        "est_hours": 2,
        "r_tokens": 80000,
        "w_tokens": 8000,
        "tool_calls": 12,
        "trigger_condition": None,
    },
    {
        "id": "product-assessment",
        "title": "Product + opportunity assessment",
        "description": "Scope, features, market fit, growth levers. 1-page brief to memory.md.",
        "cycle": "goal",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Assess the product potential of {workspace}. Cover: what problem it solves, "
            "current feature set vs. gaps, market positioning, top 3 growth levers, and "
            "1 concrete opportunity to pursue in the next sprint. Write a 1-page brief to "
            '.synlynk/project-docs/memory.md under "## Product Assessment {date}".'
        ),
        "est_hours": 1,
        "r_tokens": 40000,
        "w_tokens": 6000,
        "tool_calls": 8,
        "trigger_condition": None,
    },
    {
        "id": "lifecycle-setup",
        "title": "Set up 7-stage GOVERNS workflow for this repo",
        "description": "Initialise GOVERNS lifecycle tracking in state.db. Label open stories by stage.",
        "cycle": "open",
        "agent": "claude",
        "context_mode": "task",
        "prompt_template": (
            "Set up the 7-stage GOVERNS workflow for {workspace}. "
            "Run `synlynk story list` to see existing stories. "
            "For each story, assign a cycle phase (goal/open/visualize/execute/release/notify/sustain) "
            "based on its title and update it with `synlynk story update`. "
            "Then write a short SDLC setup note in "
            '.synlynk/project-docs/memory.md under "## Lifecycle Setup {date}" '
            "explaining which stories belong to which cycle and why."
        ),
        "est_hours": 0.5,
        "r_tokens": 15000,
        "w_tokens": 3000,
        "tool_calls": 6,
        "trigger_condition": None,
    },
    # ── Scan-triggered templates ─────────────────────────────────────────────
    {
        "id": "add-tests",
        "title": "Add test coverage",
        "description": "Bootstrap a test suite for the most critical untested modules.",
        "cycle": "execute",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "Add pytest tests for {workspace}. "
            "Target the following untested public functions in {repo_name}: "
            "{gap_functions}. "
            "For each function: write a test file if one doesn't exist, add at minimum "
            "one happy-path test and one edge-case test. Use the existing test patterns "
            "in tests/. Do not mock internal functions or the filesystem unless unavoidable. "
            "Commit each test file with 'test: add coverage for <function>'."
        ),
        "est_hours": 3,
        "r_tokens": 60000,
        "w_tokens": 20000,
        "tool_calls": 30,
        "trigger_condition": lambda scan: (
            (scan.get("tests") or {}).get("gap_count", 0) > 5
            or scan.get("test_ratio", 1.0) < 0.1
        ),
    },
    {
        "id": "setup-ci",
        "title": "Set up CI/CD pipeline",
        "description": "Create a GitHub Actions workflow for tests and linting.",
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "task",
        "prompt_template": (
            "Set up CI/CD for {workspace} ({stack}). "
            "Create .github/workflows/ci.yml that: runs tests on every push to main "
            "and on PRs, runs a linter if one is configured, and fails fast on error. "
            "Use the appropriate test runner for the stack ({stack}). "
            "Commit the workflow file with a message: 'ci: add GitHub Actions workflow'."
        ),
        "est_hours": 1,
        "r_tokens": 20000,
        "w_tokens": 5000,
        "tool_calls": 10,
        "trigger_condition": lambda scan: not scan.get("has_ci", False),
    },
    {
        "id": "docs-audit",
        "title": "Documentation audit + gap fill",
        "description": "Audit docs coverage and write missing sections.",
        "cycle": "notify",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "Audit the documentation for {workspace}. "
            "Check: README completeness, API/function docstrings, architecture docs, "
            "contributing guide, and changelog. "
            "For each gap: write the missing content inline (do not use placeholders). "
            "Commit each doc file separately with a message like 'docs: add <section>'."
        ),
        "est_hours": 2,
        "r_tokens": 50000,
        "w_tokens": 15000,
        "tool_calls": 20,
        "trigger_condition": lambda scan: (
            not scan.get("has_docs", False) or scan.get("readme_word_count", 999) < 200
        ),
    },
    {
        "id": "security-scan",
        "title": "Dependency security scan",
        "description": "Check for known CVEs and outdated dependencies.",
        "cycle": "sustain",
        "agent": "claude",
        "context_mode": "task",
        "prompt_template": (
            "Run a dependency security audit for {workspace} ({stack}). "
            "Use `pip-audit` (Python), `npm audit` (Node), or `bundle audit` (Ruby) "
            "depending on the stack. List all HIGH and CRITICAL vulnerabilities found. "
            "For each: state the package, CVE, severity, and recommended fix. "
            'Write findings to .synlynk/project-docs/memory.md under "## Security Audit {date}". '
            "If no vulnerabilities: confirm that explicitly."
        ),
        "est_hours": 1,
        "r_tokens": 25000,
        "w_tokens": 4000,
        "tool_calls": 8,
        "trigger_condition": lambda scan: any(
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["python", "node", "ruby"]
        ),
    },
    {
        "id": "perf-baseline",
        "title": "Performance baseline + profiling plan",
        "description": "Identify hot paths and draft a performance improvement plan.",
        "cycle": "sustain",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Profile the performance of {workspace} ({stack}). "
            "Identify: the 3 slowest request paths or CLI operations, any N+1 query patterns, "
            "memory allocation hot spots, and opportunities for caching. "
            "Write a performance improvement plan to "
            '.synlynk/project-docs/memory.md under "## Performance Baseline {date}" '
            "with specific file + line references."
        ),
        "est_hours": 2,
        "r_tokens": 70000,
        "w_tokens": 8000,
        "tool_calls": 15,
        "trigger_condition": lambda scan: any(
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["next", "fastapi", "django", "express", "flask"]
        ),
    },
    {
        "id": "cross-repo-map",
        "title": "Cross-repo dependency map",
        "description": "Map inter-repo dependencies for the multi-repo workspace.",
        "cycle": "visualize",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Map the inter-repo dependencies of {workspace} ({topology} workspace). "
            "For each repo pair: identify shared interfaces, shared types/schemas, "
            "shared infra, and any circular dependencies. "
            "Write a dependency map to "
            '.synlynk/project-docs/memory.md under "## Cross-Repo Map {date}" '
            "using a table: Repo A → Repo B → Dependency type → Notes."
        ),
        "est_hours": 1,
        "r_tokens": 40000,
        "w_tokens": 6000,
        "tool_calls": 10,
        "trigger_condition": lambda scan: scan.get("topology") in ("mono", "multi", "monorepo"),
    },
    {
        "id": "type-safety",
        "title": "Add type annotations to public API",
        "description": "Annotate public functions and classes to improve tooling and safety.",
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "Add type annotations to the public API of {workspace} ({stack}). "
            "The codebase is currently {typed_pct}% typed. "
            "Target all functions and methods exported or called from tests. "
            "Use Python type hints (PEP 484). Do not annotate private (_-prefixed) helpers "
            "unless they are called by public functions. "
            "Commit each annotated file separately with 'refactor: add type hints to <module>'."
        ),
        "est_hours": 3,
        "r_tokens": 120000,
        "w_tokens": 30000,
        "tool_calls": 45,
        "trigger_condition": lambda scan: (
            any(lbl == "python" for lbl in scan.get("repos", [{}])[0].get("stack_labels", []))
            and (
                (
                    scan.get("source") is not None
                    and sum(f.get("typed_pct", 0) for f in scan["source"]) / max(len(scan["source"]), 1) < 40
                )
                or not scan.get("has_type_hints", True)
            )
        ),
    },
    {
        "id": "a11y-audit",
        "title": "Accessibility audit",
        "description": "Audit the frontend for WCAG 2.1 AA compliance gaps.",
        "cycle": "release",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "Audit {workspace} ({stack}) for accessibility issues (WCAG 2.1 AA). "
            "Check: missing alt text, keyboard navigation, ARIA roles, colour contrast, "
            "and form labels. List each issue with: component file, line number, "
            "WCAG criterion, and fix. "
            'Write findings to .synlynk/project-docs/memory.md under "## A11y Audit {date}". '
            "Fix the top 5 most critical issues and commit each fix separately."
        ),
        "est_hours": 2,
        "r_tokens": 60000,
        "w_tokens": 15000,
        "tool_calls": 25,
        "trigger_condition": lambda scan: any(
            lbl in scan.get("repos", [{}])[0].get("stack_labels", [])
            for lbl in ["react", "next", "vue", "svelte", "angular"]
        ),
    },
    {
        "id": "db-schema-review",
        "title": "Database schema review",
        "description": "Review schema design for correctness, indexes, and N+1 risks.",
        "cycle": "visualize",
        "agent": "claude",
        "context_mode": "full",
        "prompt_template": (
            "Review the database schema for {workspace} ({stack}). "
            "Identify: missing indexes, nullable columns that should be NOT NULL, "
            "foreign keys without cascades, N+1 query risks, and migration gaps. "
            "Write a schema review to "
            '.synlynk/project-docs/memory.md under "## Schema Review {date}" '
            "with a table: Issue → Table/Column → Severity → Fix."
        ),
        "est_hours": 1,
        "r_tokens": 40000,
        "w_tokens": 6000,
        "tool_calls": 10,
        "trigger_condition": lambda scan: scan.get("has_orm", False),
    },
    {
        "id": "refactor-module",
        "title": "Refactor large module",
        "description": "Split monolithic source file into focused modules.",
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "The file {largest_file} in {workspace} has grown to {largest_file_lines} lines "
            "with {largest_file_fns} functions. Refactor it: "
            "identify 3-5 logical groupings of functions, extract each group into a new "
            "module under the same package directory, update all imports, and ensure the "
            "test suite still passes. The largest function is {largest_fn} at {largest_fn_lines} lines - "
            "break it down if it has multiple responsibilities. "
            "Commit each extracted module separately."
        ),
        "est_hours": 4,
        "r_tokens": 200000,
        "w_tokens": 50000,
        "tool_calls": 60,
        "trigger_condition": lambda scan: (
            bool(scan.get("source"))
            and any(f.get("lines", 0) > 5000 for f in (scan.get("source") or []))
        ),
    },
    {
        "id": "reduce-complexity",
        "title": "Reduce complexity hotspots",
        "description": "Break down functions >50 lines into focused helpers.",
        "cycle": "execute",
        "agent": "codex",
        "context_mode": "full",
        "prompt_template": (
            "Reduce complexity in {workspace}. The top hotspot is {top_hotspot} "
            "({top_hotspot_lines} lines). For each of the top 3 complexity hotspots: "
            "extract sub-responsibilities into named helper functions, add a docstring "
            "explaining what each piece does, and ensure tests still pass. "
            "Do not change observable behaviour. "
            "Commit each refactored function separately."
        ),
        "est_hours": 3,
        "r_tokens": 120000,
        "w_tokens": 40000,
        "tool_calls": 40,
        "trigger_condition": lambda scan: (
            len((scan.get("complexity") or {}).get("hotspots", [])) > 2
        ),
    },
    {
        "id": "fix-churn-debt",
        "title": "Address hot file tech debt",
        "description": "Stabilise the most-changed file with tests + docstrings.",
        "cycle": "sustain",
        "agent": "agy",
        "context_mode": "full",
        "prompt_template": (
            "The file {hot_file} in {workspace} has been modified {commit_count} times "
            "in the last 30 commits - it is the highest-churn file in the repo. "
            "Stabilise it by: adding docstrings to all public functions that lack them, "
            "writing tests for any public function with no test (check test_ratio first), "
            "and adding a module-level docstring explaining the file's responsibility. "
            "Commit each category of change separately."
        ),
        "est_hours": 2,
        "r_tokens": 80000,
        "w_tokens": 20000,
        "tool_calls": 25,
        "trigger_condition": lambda scan: (
            bool((scan.get("git") or {}).get("churn"))
            and (scan.get("git") or {}).get("churn", [{}])[0].get("commits", 0) > 30
        ),
    },
]


def _template_matches(template: dict, scan: dict) -> bool:
    """Returns True if the template's trigger condition is met by scan."""
    condition = template.get("trigger_condition")
    if condition is None:
        return True
    try:
        return bool(condition(scan))
    except Exception:
        return False


def _select_launch_tasks(scan: dict) -> list:
    """Returns ordered list of 3-5 matching templates (core first, bonus sorted by specificity)."""
    eligible = [t for t in _launch_visible_templates() if _template_matches(t, scan)]
    core = [t for t in eligible if t["id"] in CORE_TEMPLATE_IDS]
    bonus = [t for t in eligible if t["id"] not in CORE_TEMPLATE_IDS]
    return (core + bonus)[:5]


def _render_prompt(template: dict, scan: dict) -> str:
    """Substitutes {variables} in prompt_template from scan data. Missing vars become ''."""
    import datetime as _datetime
    import re as _re

    repos = scan.get("repos", [])
    primary = repos[0] if repos else {}
    tests = scan.get("tests") or {}
    source = scan.get("source") or []
    complexity = scan.get("complexity") or {}
    git = scan.get("git") or {}
    gap_functions = tests.get("gap_functions", [])
    if gap_functions:
        gap_functions_text = ", ".join(
            g.get("name", str(g)) if isinstance(g, dict) else str(g)
            for g in gap_functions
        )
    else:
        gap_functions_text = "none"
    typed_pct = (
        int(sum(f.get("typed_pct", 0) for f in source) / max(len(source), 1))
        if source
        else int(scan.get("typed_pct", 0) or 0)
    )
    largest_file = max(source, key=lambda f: f.get("lines", 0), default={})
    largest_fn = {}
    for file_info in source:
        for fn in file_info.get("largest_fns", []):
            if fn.get("lines", 0) > largest_fn.get("lines", 0):
                largest_fn = {
                    "name": fn.get("name", ""),
                    "lines": fn.get("lines", 0),
                    "file": file_info.get("path", ""),
                }
    hotspots = complexity.get("hotspots", [])
    top_hotspot = max(hotspots, key=lambda h: h.get("lines", 0), default={})
    churn = git.get("churn", [])
    hot_file = churn[0].get("path", "") if churn else ""
    commit_count = churn[0].get("commits", 0) if churn else 0
    variables = {
        "workspace": scan.get("workspace_name", ""),
        "stack": ", ".join(primary.get("stack_labels", [])) or "unknown",
        "repo_name": primary.get("name", ""),
        "topology": scan.get("topology", "single"),
        "test_count": str(scan.get("test_ratio", 0)),
        "gap_functions": gap_functions_text,
        "typed_pct": str(typed_pct),
        "largest_file": largest_file.get("path", ""),
        "largest_file_lines": str(largest_file.get("lines", 0)),
        "largest_file_fns": str(largest_file.get("functions", 0)),
        "largest_fn": largest_fn.get("name", ""),
        "largest_fn_lines": str(largest_fn.get("lines", 0)),
        "top_hotspot": top_hotspot.get("fn") or os.path.basename(top_hotspot.get("path", "")),
        "top_hotspot_lines": str(top_hotspot.get("lines", 0)),
        "hot_file": hot_file,
        "commit_count": str(commit_count),
        "date": _datetime.date.today().isoformat(),
        "agent": template.get("agent", "claude"),
    }
    text = template.get("prompt_template", "")

    def _replace(match):
        key = match.group(1)
        return variables.get(key, "")

    return _re.sub(r"\{(\w+)\}", _replace, text)


TASK_STATUSES = {
    "[ ]": "active",
    "[x]": "done",
    "[-]": "deferred",
    "[~]": "superseded",
    "[>]": "absorbed",
}


def _project_root() -> str:
    """Return the shared repo root for the current git worktree, or CWD fallback."""
    try:
        common = subprocess.check_output(
            ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"],
            stderr=subprocess.DEVNULL,
        ).decode().strip()
        if common:
            return os.path.abspath(os.path.join(common, ".."))
    except Exception:
        pass
    return os.getcwd()


def _get_project_root() -> str:
    """Backwards-compatible alias for callers that expect a root helper."""
    return _project_root()


def _resolve_db_path() -> str:
    """Centralise DB at ~/.synlynk/projects/<key>/state.db so all worktrees share one DB.

    Key is an 8-char MD5 of the shared repo root, falling back to CWD outside git.
    This avoids the .synlynk/state flat-file collision and the per-worktree isolation bug.
    """
    import hashlib as _h

    root = _project_root()
    key = _h.md5(root.encode()).hexdigest()[:8]
    return os.path.expanduser(f"~/.synlynk/projects/{key}/state.db")


DB_PATH = _resolve_db_path()

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS stories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL UNIQUE,
    title         TEXT,
    estimated_tokens INTEGER,
    actual_tokens INTEGER,
    engg_domain   TEXT NOT NULL DEFAULT 'backend',
    discipline    TEXT NOT NULL DEFAULT 'backend',
    org_domain    TEXT NOT NULL DEFAULT 'platform',
    role          TEXT NOT NULL DEFAULT 'dev',
    stage         TEXT NOT NULL DEFAULT 'open',
    org_domain_tags TEXT DEFAULT '[]',
    stack_tags    TEXT DEFAULT '[]',
    industry      TEXT DEFAULT 'unknown',
    phase         TEXT DEFAULT 'build',
    legacy_unmapped INTEGER NOT NULL DEFAULT 0,
    priority      INTEGER NOT NULL DEFAULT 5,
    readiness     TEXT NOT NULL DEFAULT 'draft',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS capability_ratings (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id              TEXT NOT NULL REFERENCES stories(story_id),
    agent                 TEXT NOT NULL,
    model_version         TEXT NOT NULL DEFAULT 'unknown',
    model_at_dispatch     TEXT,
    model_at_completion   TEXT,
    split_model           INTEGER DEFAULT 0,
    engg_domain           TEXT NOT NULL DEFAULT 'backend',
    discipline            TEXT NOT NULL DEFAULT 'backend',
    org_domain            TEXT NOT NULL DEFAULT 'platform',
    role                  TEXT NOT NULL DEFAULT 'dev',
    stage                 TEXT NOT NULL DEFAULT 'open',
    org_domain_tags       TEXT DEFAULT '[]',
    stack_tags            TEXT DEFAULT '[]',
    industry              TEXT NOT NULL DEFAULT 'unknown',
    phase                 TEXT NOT NULL DEFAULT 'build',
    legacy_unmapped       INTEGER NOT NULL DEFAULT 0,
    signal_source         TEXT NOT NULL DEFAULT 'auto',
    quality               REAL NOT NULL DEFAULT 0.0,
    quality_auto          REAL,
    verifier_agent        TEXT,
    verifier_model        TEXT,
    test_pass_rate        REAL,
    build_success         INTEGER,
    dispatch_rework       INTEGER DEFAULT 0,
    micro_rework          INTEGER DEFAULT 0,
    pr_review_cycles      INTEGER DEFAULT 0,
    duration_vs_estimate  REAL,
    verified_by_ci        INTEGER,
    correct               INTEGER DEFAULT 1,
    note                  TEXT,
    pr_number             INTEGER,
    ed25519_sig           TEXT,
    ts                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS pr_multiplier_applied (
    pr_number  INTEGER PRIMARY KEY,
    applied_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS source_symbols (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    head_sha    TEXT NOT NULL,
    file        TEXT NOT NULL,
    language    TEXT NOT NULL,
    symbol      TEXT NOT NULL,
    symbol_type TEXT NOT NULL,
    line        INTEGER,
    scanned_at  TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_source_symbols_head ON source_symbols(head_sha);
CREATE INDEX IF NOT EXISTS idx_source_symbols_file ON source_symbols(file);

CREATE TABLE IF NOT EXISTS autopilot_runs (
    id            TEXT PRIMARY KEY,
    agent_name    TEXT NOT NULL,
    signal_type   TEXT NOT NULL,
    signal_hash   TEXT NOT NULL,
    severity      TEXT NOT NULL,
    summary       TEXT NOT NULL,
    status        TEXT NOT NULL,
    gh_issue_url  TEXT,
    pr_url        TEXT,
    story_id      TEXT,
    ts            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_hash ON autopilot_runs(signal_hash, ts);

CREATE TABLE IF NOT EXISTS daemon_jobs (
    job_id       TEXT PRIMARY KEY,
    agent        TEXT NOT NULL,
    task         TEXT NOT NULL,
    story_id     TEXT,
    status       TEXT NOT NULL DEFAULT 'queued',
    priority     INTEGER NOT NULL DEFAULT 5,
    depends_on   TEXT NOT NULL DEFAULT '[]',
    pid          INTEGER,
    enqueued_at  TEXT NOT NULL,
    started_at   TEXT,
    completed_at TEXT,
    exit_code    INTEGER,
    log_path     TEXT,
    handoff_count INTEGER NOT NULL DEFAULT 0,
    previous_agents TEXT,
    dispatch_context TEXT,
    blocked_reason TEXT,
    context_mode TEXT,
    context_bytes INTEGER,
    session_id TEXT REFERENCES sessions(session_id)
);
CREATE INDEX IF NOT EXISTS idx_daemon_jobs_status ON daemon_jobs(status);

CREATE TABLE IF NOT EXISTS goals (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id     TEXT NOT NULL UNIQUE,
    outcome     TEXT NOT NULL,
    criterion   TEXT NOT NULL,
    deadline    TEXT,
    status      TEXT NOT NULL DEFAULT 'active',
    created_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS goal_contributions (
    id       INTEGER PRIMARY KEY AUTOINCREMENT,
    goal_id  TEXT NOT NULL REFERENCES goals(goal_id),
    story_id TEXT NOT NULL REFERENCES stories(story_id),
    UNIQUE(goal_id, story_id)
);

CREATE TABLE IF NOT EXISTS sessions (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id       TEXT NOT NULL UNIQUE,
    title            TEXT NOT NULL,
    goal_id          TEXT REFERENCES goals(goal_id),
    status           TEXT NOT NULL DEFAULT 'open',
    disposition      TEXT,
    opened_at        TEXT NOT NULL,
    closed_at        TEXT,
    last_checkpoint_at TEXT,
    closing_summary  TEXT
);
CREATE INDEX IF NOT EXISTS idx_sessions_status ON sessions(status);

CREATE TABLE IF NOT EXISTS events (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type      TEXT NOT NULL,
    payload_json    TEXT NOT NULL,
    created_at      TEXT NOT NULL,
    emitted_by      TEXT NOT NULL,
    parent_event_id INTEGER,
    authority_scope TEXT
);
CREATE INDEX IF NOT EXISTS idx_events_type ON events(event_type, id);

CREATE TABLE IF NOT EXISTS subscriptions (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    agent_name         TEXT NOT NULL,
    event_type         TEXT NOT NULL,
    last_seen_event_id INTEGER NOT NULL DEFAULT 0,
    UNIQUE(agent_name, event_type)
);

-- Per-agent plan quotas (tokens or requests). quota_type is plan-driven:
-- different harnesses reset on different windows (5h Claude plan, hourly,
-- daily, weekly, monthly). headroom is computed as limit_tokens - used_tokens
-- (columns named *_tokens historically; unit column disambiguates).
CREATE TABLE IF NOT EXISTS agent_quotas (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    agent        TEXT NOT NULL,
    model        TEXT NOT NULL DEFAULT 'unknown',
    quota_type   TEXT NOT NULL,
    unit         TEXT NOT NULL DEFAULT 'tokens',
    limit_tokens INTEGER NOT NULL,
    used_tokens  INTEGER NOT NULL DEFAULT 0,
    reset_at     TIMESTAMP,
    updated_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(agent, model, quota_type, unit)
);
CREATE INDEX IF NOT EXISTS idx_agent_quotas_agent ON agent_quotas(agent);

-- Reservation ledger: an open row represents tokens committed against a
-- harness before real usage lands in agent_quotas via telemetry (#XXX
-- quota-aware dispatch reservation). Released once the matching daemon_jobs
-- row settles (done/failed/timed_out) and real usage has been recorded.
-- Reservations older than 24h are treated as expired at READ time (lazy
-- expiry, see _open_reservations_sum) rather than physically deleted.
CREATE TABLE IF NOT EXISTS agent_reservations (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    harness        TEXT NOT NULL,
    tokens         INTEGER NOT NULL,
    scope          TEXT NOT NULL,
    scope_id       TEXT,
    job_id         TEXT,
    status         TEXT NOT NULL DEFAULT 'open',
    created_at     TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    released_at    TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_agent_reservations_harness ON agent_reservations(harness, status);

CREATE TABLE IF NOT EXISTS credit_grants (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    agent           TEXT NOT NULL,
    face_value_usd  REAL NOT NULL,
    remaining_usd   REAL NOT NULL,
    granted_at      TEXT NOT NULL,
    expires_at      TEXT,
    note            TEXT
);

CREATE TABLE IF NOT EXISTS remediation_actions (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT NOT NULL,
    agent       TEXT NOT NULL,
    target_file TEXT NOT NULL,
    exact_diff  TEXT NOT NULL,
    operator    TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_remediation_actions_timestamp
    ON remediation_actions(timestamp);

CREATE TABLE IF NOT EXISTS fleet_matrix_runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    run_id TEXT NOT NULL,
    tier INTEGER NOT NULL,
    home TEXT NOT NULL,
    cell TEXT NOT NULL,
    status TEXT NOT NULL,
    detail TEXT,
    cost_usd REAL NOT NULL DEFAULT 0,
    ts TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_fleet_matrix_runs_lookup
    ON fleet_matrix_runs(home, cell, tier, ts);
"""

_DB_SCORES_VIEW = """
CREATE VIEW IF NOT EXISTS capability_scores AS
SELECT
    agent,
    model_version,
    discipline,
    engg_domain,
    org_domain,
    role,
    stage,
    industry,
    phase,
    SUM(quality * pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER))) /
      SUM(pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER)))
      AS weighted_score,
    COUNT(*) AS sample_count,
    MAX(ts) AS last_seen
FROM capability_ratings
WHERE split_model = 0
GROUP BY agent, model_version, discipline, engg_domain, org_domain, role, stage, industry, phase;
"""

def _get_db() -> _sqlite3.Connection:
    """Returns a WAL-mode SQLite connection to state.db, running migrations.

    SYNLYNK_STATE_DB_PATH, if set, is used verbatim and takes precedence over
    everything below: no nested-worktree guard, no fallback chain. A caller
    setting this env var has made a deliberate choice about ledger location
    (e.g. a sandbox restricted to the repo workspace root, where neither the
    home path nor the tmpdir fallback is reachable). If that path is itself
    unwritable, the resulting exception propagates uncaught — an explicit
    override that fails should surface loudly, not be silently re-routed.
    See #681.

    Falls back to ./.synlynk/state.db when the centralised path under
    ~/.synlynk/projects/<key>/ is unwritable. Dispatched-agent sandboxes
    commonly mount $HOME read-only; that surfaces as OSError(EROFS) from
    os.makedirs (not PermissionError) or as sqlite3.OperationalError from
    connect when the directory already exists. See #648.

    Primary product ledger must not live under job/feature worktrees when the
    home path is the intended path (#330 / fleet S2a). Sandbox fallback after
    OSError/OperationalError uses a path that never lands under worktrees
    (tmpdir when cwd is a job/feature worktree) so nested_state matrix stays clean.
    """
    override = os.environ.get("SYNLYNK_STATE_DB_PATH")
    if override:
        os.makedirs(os.path.dirname(override), exist_ok=True)
        conn = _sqlite3.connect(override)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _migrate_db(conn)
        return conn

    from synlynk.fleet import assert_not_nested_product_ledger, sandbox_fallback_db_path

    db_path = DB_PATH
    fallback_path = sandbox_fallback_db_path()
    tried_fallback = False
    while True:
        try:
            # Refuse nested worktree product ledger on the primary attempt only.
            if not tried_fallback:
                assert_not_nested_product_ledger(db_path, home_writable=True)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            conn = _sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _migrate_db(conn)
            return conn
        # OSError covers PermissionError, EROFS (read-only mounts), ENOSPC, etc.
        # OperationalError covers "unable to open database file" when the dir
        # exists but the file/FS is still unwritable (sandbox case in #648).
        # RuntimeError from nested-ledger refusal must not trigger fallback.
        except (OSError, _sqlite3.OperationalError) as exc:
            if tried_fallback:
                raise
            print(
                f"warning: cannot open project state DB at {db_path} ({exc}); "
                f"no project state found on this machine — falling back to "
                f"local {fallback_path}",
                file=sys.stderr,
            )
            db_path = fallback_path
            tried_fallback = True



def _is_migrated() -> bool:
    return os.path.exists(os.path.join(_project_root(), ".synlynk", ".synlynk_migrated"))


def _synlynk_project_docs_dir() -> str:
    return os.path.join(_project_root(), ".synlynk", "project-docs")


def _dr_sync(relative_path: str) -> None:
    try:
        cfg_path = os.path.join('.synlynk', 'config.json')
        if not os.path.exists(cfg_path):
            return
        with open(cfg_path) as f:
            cfg = json.load(f)
        dr_path = cfg.get('dr_sync_path')
        if not dr_path:
            return
        dr_path = os.path.expanduser(str(dr_path))
        if not os.path.isdir(dr_path):
            return
        src = os.path.join('.synlynk', 'project-docs', relative_path)
        if not os.path.exists(src):
            return
        dst = os.path.join(dr_path, 'project-docs', relative_path)
        os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
        import shutil as _shutil
        _shutil.copy2(src, dst)
    except Exception:
        pass


def _seed_verb_map(db_conn):
    db_conn.executemany("""
        INSERT OR IGNORE INTO harness_verb_map
            (synlynk_verb, verb_category, agent_name, agent_command, supported, partial_notes)
        VALUES (?,?,?,?,?,?)
    """, _VERB_MAP_SEED)
    db_conn.commit()


def _check_verb_support(verb: str, agent_name: str, db_conn) -> dict:
    row = db_conn.execute(
        "SELECT supported, partial_notes, agent_command FROM harness_verb_map WHERE synlynk_verb=? AND agent_name=?",
        (verb, agent_name)
    ).fetchone()
    if not row:
        return {"supported": "unknown", "block": False, "warn": False, "notes": None, "command": None}
    supported, notes, cmd = row
    return {
        "supported": supported,
        "block": supported == "none",
        "warn": supported == "partial",
        "notes": notes,
        "command": cmd,
    }


def _load_agent_config(name: str) -> dict:
    """Load .agents/<name>.json. Raises FileNotFoundError with clear message."""
    import json as _json
    candidates = [os.path.join(".agents", f"{name}.json"), os.path.join("agents", f"{name}.json")]
    path = next((candidate for candidate in candidates if os.path.exists(candidate)), candidates[0])
    if not os.path.exists(path):
        raise FileNotFoundError(f"No agent config found at {path}")
    with open(path) as f:
        return _json.load(f)


def _load_agent_profile(agent_name: str, agents_dir: str = ".agents") -> dict:
    """Load an agent profile and normalize harness/model defaults."""
    import json as _json

    candidates = [
        os.path.join(agents_dir, f"{agent_name}.json"),
        os.path.join(".agents", f"{agent_name}.json"),
        os.path.join("agents", f"{agent_name}.json"),
    ]
    path = next((candidate for candidate in candidates if os.path.exists(candidate)), candidates[0])
    if not os.path.exists(path):
        return {"agent": agent_name, "harness": agent_name, "model": "unknown"}
    try:
        with open(path) as f:
            profile = _json.load(f)
    except (OSError, ValueError, TypeError):
        return {"agent": agent_name, "harness": agent_name, "model": "unknown"}
    profile.setdefault("harness", agent_name)
    profile.setdefault("model", "unknown")
    return profile


def _dispatch_flags_for_agent(agent: str) -> list:
    """Return the executable dispatch flags for an agent baseline.

    Supports both the legacy list form and the structured mapping form.
    """
    baselines = AGENT_CAPABILITY_BASELINES.get(agent, {})
    dispatch_flags = baselines.get("dispatch_flags", [])
    if isinstance(dispatch_flags, dict):
        ordered = []
        for flag in dispatch_flags.get("required_flags", []) or []:
            if flag not in ordered:
                ordered.append(flag)
        return ordered
    return list(dispatch_flags or [])


def cmd_roles(fix: bool = False) -> None:
    """Print current agent role table from config.

    With --fix, regenerate role fences.
    """
    cfg = load_config()
    roles = cfg.get("roles", {})
    if isinstance(roles, dict):
        visible_agents = [agent for agent in roles if agent]
    elif isinstance(roles, (list, tuple)):
        visible_agents = [agent for agent in roles if agent]
    else:
        visible_agents = []

    print(f"\n  {_BOLD}synlynk roles{_RESET}\n")
    print(f"  {'agent':<10}  {'roles':<40}  {'directive file':<12}  fence")
    print(f"  {'─' * 10}  {'─' * 40}  {'─' * 12}  {'─' * 10}")

    for agent in visible_agents:
        role_list = roles.get(agent, []) if isinstance(roles, dict) else []
        fname = _directive_file_for_agent(agent)
        roles_str = ", ".join(role_list) if isinstance(role_list, list) else str(role_list)
        file_exists = os.path.exists(fname)
        fence_present = False
        if file_exists:
            try:
                with open(fname) as f:
                    fence_present = "<!-- synlynk:harness" in f.read()
            except IOError:
                pass
        file_status = fname if file_exists else f"{fname} (missing)"
        fence_status = f"{_GREEN}✓{_RESET}" if fence_present else f"{_YELLOW}missing{_RESET}"
        print(f"  {agent:<10}  {roles_str:<40}  {file_status:<12}  {fence_status}")

        if fix and file_exists and not fence_present:
            roles_line = ", ".join(role_list) if isinstance(role_list, list) else str(role_list)
            try:
                _upsert_harness_fence(
                    fname,
                    harness_version="roles",
                    body=f"## Your Role\n{roles_line}\n",
                )
                print(f"    {_GREEN}✓{_RESET} wrote role fence to {fname}")
            except Exception as exc:
                print(f"    {_YELLOW}⚠{_RESET} could not write {fname}: {exc}")

    print()
    if not fix:
        missing = [
            _directive_file_for_agent(a)
            for a in visible_agents
            if os.path.exists(_directive_file_for_agent(a))
            and not _fence_exists(_directive_file_for_agent(a))
        ]
        if missing:
            print(f"  {_DIM}Run `synlynk roles --fix` to write missing role fences{_RESET}\n")
    if not visible_agents:
        print(f"  {_DIM}No agents in roles to display{_RESET}\n")




_ENGG_DOMAIN_PATTERNS = [
    ("data",         [r"etl", r"pipeline/", r"schema\.sql", r"migrations/", r"dbt/"]),
    ("ml",           [r"ml/", r"models/", r"train\.", r"inference/", r"embeddings/"]),
    ("security",     [r"auth/", r"oauth", r"jwt", r"crypto", r"certs/"]),
    ("devops",       [r"\.github/", r"dockerfile", r"terraform", r"pulumi", r"k8s/", r"helm/"]),
    ("frontend",     [r"components/", r"pages/", r"\.tsx?", r"\.vue", r"\.svelte", r"styles/"]),
    ("backend",      [r"api/", r"routes/", r"handlers/", r"controllers/", r"services/"]),
    ("testing",      [r"tests/", r"test_", r"spec/", r"\.spec\.", r"fixtures/"]),
    ("docs",         [r"docs/", r"readme", r"\.md$", r"changelogs?"]),
    ("architecture", [r"design/", r"specs/", r"adr/", r"diagrams/"]),
]

def _infer_engg_domain(log_text: str) -> str:
    """Infers engineering domain from file path patterns in job log output."""
    lower = log_text.lower()
    for domain, patterns in _ENGG_DOMAIN_PATTERNS:
        if any(re.search(p, lower) for p in patterns):
            return domain
    return "unknown"


JOBS_FILE = ".synlynk/jobs.json"
LOGS_DIR = ".synlynk/logs"
PROMPTS_DIR = ".synlynk/prompts"

_VERB_MAP_SEED = [
    # (synlynk_verb, category, agent, agent_command, supported, partial_notes)
    ("dispatch.task",     "dispatch",      "claude", "claude --print {task} --dangerously-skip-permissions", "full", None),
    ("dispatch.task",     "dispatch",      "agy",    "agy -p {task}", "full", None),
    ("dispatch.task",     "dispatch",      "grok",   "grok --single {task}", "full", None),
    ("dispatch.task",     "dispatch",      "codex",  "codex exec - -s workspace-write", "full", None),
    ("dispatch.headless", "dispatch",      "claude", "claude --print {task}", "full", None),
    ("dispatch.headless", "dispatch",      "agy",    "agy -p {task}", "partial", "May hang without PTY on some agy versions"),
    ("dispatch.headless", "dispatch",      "grok",   "grok --single {task}", "partial", "Network dep required"),
    ("dispatch.headless", "dispatch",      "codex",  "codex exec - -s workspace-write", "full", None),
    ("dispatch.resume",   "dispatch",      "claude", "claude --resume {session_id}", "full", None),
    ("dispatch.resume",   "dispatch",      "agy",    None, "none", None),
    ("dispatch.resume",   "dispatch",      "grok",   None, "none", None),
    ("dispatch.resume",   "dispatch",      "codex",  None, "none", None),
    ("dispatch.approve",  "dispatch",      "claude", "claude --allowedTools {tools}", "full", None),
    ("dispatch.approve",  "dispatch",      "agy",    None, "none", None),
    ("dispatch.approve",  "dispatch",      "grok",   None, "none", None),
    ("dispatch.approve",  "dispatch",      "codex",  None, "partial", "ask-for-approval=untrusted only"),
    ("dispatch.model",    "dispatch",      "claude", "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "agy",    "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "grok",   "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "codex",  "--model {model}", "full", None),
    ("dispatch.tools",    "dispatch",      "claude", "--allowedTools {tools}", "full", None),
    ("dispatch.tools",    "dispatch",      "agy",    None, "partial", "No tool_list flag"),
    ("dispatch.tools",    "dispatch",      "grok",   None, "none", None),
    ("dispatch.tools",    "dispatch",      "codex",  None, "partial", "ask-for-approval only"),
    ("dispatch.context",  "dispatch",      "claude", "claude --print {task}", "full", None),
    ("dispatch.context",  "dispatch",      "agy",    "agy -p {task}", "full", None),
    ("dispatch.context",  "dispatch",      "grok",   "grok --prompt {task}", "partial", "No explicit context file flag"),
    ("dispatch.context",  "dispatch",      "codex",  "codex exec - -s workspace-write", "full", None),
    ("jobs",              "observability", "claude", None, "partial", "No native jobs subcommand"),
    ("jobs",              "observability", "agy",    None, "none", None),
    ("jobs",              "observability", "grok",   None, "none", None),
    ("jobs",              "observability", "codex",  None, "none", None),
    ("status",            "observability", "claude", None, "partial", None),
    ("status",            "observability", "agy",    None, "none", None),
    ("status",            "observability", "grok",   None, "none", None),
    ("status",            "observability", "codex",  None, "none", None),
    ("telemetry",         "observability", "claude", None, "none", None),
    ("telemetry",         "observability", "agy",    None, "none", None),
    ("telemetry",         "observability", "grok",   None, "none", None),
    ("telemetry",         "observability", "codex",  None, "none", None),
    ("costs",             "observability", "claude", None, "partial", "Token count via /cost"),
    ("costs",             "observability", "agy",    None, "none", None),
    ("costs",             "observability", "grok",   None, "none", None),
    ("costs",             "observability", "codex",  None, "none", None),
    ("probe",             "harness",       "claude", "claude --version", "full", None),
    ("probe",             "harness",       "agy",    "agy --version", "full", None),
    ("probe",             "harness",       "grok",   "grok --version", "full", None),
    ("probe",             "harness",       "codex",  "codex --version", "full", None),
    ("doctor",            "harness",       "claude", None, "full", None),
    ("doctor",            "harness",       "agy",    None, "full", None),
    ("doctor",            "harness",       "grok",   None, "full", None),
    ("doctor",            "harness",       "codex",  None, "full", None),
    ("story",             "pm",            "claude", None, "none", None),
    ("story",             "pm",            "agy",    None, "none", None),
    ("story",             "pm",            "grok",   None, "none", None),
    ("story",             "pm",            "codex",  None, "none", None),
    ("epic",              "pm",            "claude", None, "none", None),
    ("epic",              "pm",            "agy",    None, "none", None),
    ("epic",              "pm",            "grok",   None, "none", None),
    ("epic",              "pm",            "codex",  None, "none", None),
    ("decide",            "pm",            "claude", None, "none", None),
    ("decide",            "pm",            "agy",    None, "none", None),
    ("decide",            "pm",            "grok",   None, "none", None),
    ("decide",            "pm",            "codex",  None, "none", None),
    ("workspace",         "workspace",     "claude", None, "none", None),
    ("workspace",         "workspace",     "agy",    None, "none", None),
    ("workspace",         "workspace",     "grok",   None, "none", None),
    ("workspace",         "workspace",     "codex",  None, "none", None),
    ("upgrade",           "workspace",     "claude", None, "partial", "Via /upgrade slash command"),
    ("upgrade",           "workspace",     "agy",    None, "partial", "Via agy update"),
    ("upgrade",           "workspace",     "grok",   None, "partial", None),
    ("upgrade",           "workspace",     "codex",  None, "partial", None),
]

RELAY_EVENT_TYPES = frozenset({
    "story_updated",
    "job_dispatched",
    "job_completed",
    "alert_raised",
    "context_checkpoint",
    "table_changed",
    "broadcast",
})


def _build_relay_event(event_type: str, payload: dict) -> dict:
    """Constructs a relay event dict with required base fields."""
    if event_type not in RELAY_EVENT_TYPES:
        raise ValueError(
            f"unknown event type '{event_type}'. Valid: {sorted(RELAY_EVENT_TYPES)}"
        )
    import socket as _socket

    event = {
        "type": event_type,
        "ts": int(time.time()),
        "origin_node": _socket.gethostname(),
    }
    event.update(payload)
    return event

# Default paths scanned for agent CLI config directories.
# Overridable in .synlynk/config.json under "agent_discovery_paths".
AGENT_DISCOVERY_DEFAULTS = {
    "claude": os.path.expanduser("~/.claude"),
    "codex": os.path.expanduser("~/.codex"),
    "agy": os.path.expanduser("~/.agy"),
    "grok": os.path.expanduser("~/.grok"),
}

_AGENT_DIRECTIVE_FILES = {
    "claude": "CLAUDE.md",
    "agy": "GEMINI.md",
    "grok": "GROK.md",
    "codex": "AGENTS.md",
}


def _default_roles_for_agent(agent: str) -> list:
    """Return the default onboarded role list for an agent."""
    return {
        "claude": ["pm", "review", "deploy"],
        "agy": ["implement", "test", "css", "templates", "content"],
        "grok": ["implement", "test", "canvas", "js", "infra"],
        "codex": ["implement", "test", "refactor"],
    }.get(agent, [])


def _default_roles_map() -> dict:
    """Return the default role mapping for supported agents."""
    return {name: _default_roles_for_agent(name) for name in _AGENT_DIRECTIVE_FILES}


def _directive_file_for_agent(agent: str) -> str:
    return _AGENT_DIRECTIVE_FILES.get(agent, f"{agent}.md")


def _write_json_atomic(path: str, payload: dict) -> None:
    """Write a JSON file atomically within the current workspace."""
    directory = os.path.dirname(path) or "."
    os.makedirs(directory, exist_ok=True)
    fd, tmp_path = tempfile.mkstemp(dir=directory, prefix=".tmp.", suffix=".json")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(payload, f, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)
    finally:
        if os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except OSError:
                pass

# ANSI helpers used by the wizard.
_BOLD = "\033[1m"
_GREEN = "\033[32m"
_YELLOW = "\033[33m"
_CYAN = "\033[36m"
_DIM = "\033[2m"
_RESET = "\033[0m"
_RED = "\033[31m"
_MAGENTA = "\033[35m"


def _docs_dir() -> str:
    """Returns the configured project docs directory (defaults to 'project-docs').

    Reads project_docs_dir from .synlynk/config.json. Pass --docs-dir to
    synlynk init to set a custom location (e.g. '.' for repos that keep docs
    at the root).
    """
    config_file = ".synlynk/config.json"
    if os.path.exists(config_file):
        try:
            with open(config_file) as f:
                return json.load(f).get("project_docs_dir", "project-docs")
        except (json.JSONDecodeError, IOError):
            pass
    return "project-docs"


def load_config() -> dict:
    """Loads .synlynk/config.json with schema-v1 defaults."""
    capability_roles = _load_capability_roles()
    defaults = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "dispatch": {"stacking": "auto", "gate_suite_cmd": ""},
        "watch_interval_seconds": 30,
        "auto_smoke_test": False,
        "auto_launch_after_wizard": True,
        "dispatch_mode": "daily-grind",
        "fenced_commands": ["dispatch", "jobs", "exec", "schedule"],
        "nudges": {"enabled": True, "dismissed_ids": [], "last_shown": {}},
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "identity_slug": None,
        "project_docs_dir": "project-docs",
        "agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex"},  # AGY CLI binary is named 'agy' — update when binary is renamed
        "workgroup_agents": [],
        "last_housekeeping_date": None,
        "team": None,
        "sync_endpoint": None,
        "exec_timeout_minutes": 30,
        "stall_timeout_minutes": 30,
        "review_stall_timeout_minutes": 90,
        "agents": {},
        "payment_models": {},
        "capability_sweep": {"cost_cap_usd": 10.0},
        "roles": capability_roles if capability_roles is not None else _default_roles_map(),
        "story_classification": {"method": "heuristic"},
    }
    config_file = ".synlynk/config.json"
    if not os.path.exists(config_file):
        return defaults
    try:
        with open(config_file) as f:
            config = json.load(f)
        for key, val in defaults.items():
            if key not in config:
                config[key] = val
        if capability_roles is not None:
            config["roles"] = capability_roles
        elif "roles" not in config:
            config["roles"] = _default_roles_map()
        for key, val in defaults["budget"].items():
            if key not in config.get("budget", {}):
                config.setdefault("budget", {})[key] = val
        for key, val in defaults["dispatch"].items():
            if key not in config.get("dispatch", {}):
                config.setdefault("dispatch", {})[key] = val
        for key, val in defaults["nudges"].items():
            if key not in config.get("nudges", {}):
                config.setdefault("nudges", {})[key] = val
        return config
    except (json.JSONDecodeError, IOError):
        return defaults


def cmd_config_set(key: str, value: str) -> None:
    """Set a top-level config key in .synlynk/config.json."""
    config_path = ".synlynk/config.json"
    config = load_config()
    config[key] = value
    _write_json_atomic(config_path, config)
    print(f"  ✓ {key} = {value!r} saved to .synlynk/config.json")
















def _check_upstream_divergence() -> None:
    """Warn if remote has commits the local branch hasn't pulled. Silent no-op otherwise."""
    try:
        local = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL
        ).decode().strip()
        upstream = subprocess.check_output(
            ["git", "rev-parse", "@{u}"], stderr=subprocess.DEVNULL
        ).decode().strip()
    except (subprocess.CalledProcessError, AttributeError):
        return  # no upstream configured, detached HEAD, or not in git repo
    if local != upstream:
        try:
            behind = subprocess.check_output(
                ["git", "rev-list", "--count", "HEAD..@{u}"],
                stderr=subprocess.DEVNULL
            ).decode().strip()
        except (subprocess.CalledProcessError, AttributeError):
            behind = "?"
        print(f"⚠  Remote has {behind} commit(s) you haven't pulled. "
              f"Consider `git pull` before writing.\n   Continuing anyway...")


def _seed_devlog(username: str) -> None:
    """Creates project-docs/devlogs/<username>.md if absent. Idempotent."""
    devlog_dir = os.path.join(_docs_dir(), "devlogs")
    os.makedirs(devlog_dir, exist_ok=True)
    devlog_path = os.path.join(devlog_dir, f"{username}.md")
    if os.path.exists(devlog_path):
        return
    today = time.strftime("%Y-%m-%d")
    with open(devlog_path, "w") as f:
        f.write(f"# Devlog — @{username}\n\n")
        f.write(f"## {today} — Joined project\n")
        f.write("Joined via `synlynk join`.\n")






def cmd_exit(dry_run: bool = True, remove_docs: bool = False) -> int:
    """Reverse synlynk onboarding: strip instruction sections, remove .synlynk/ and .agents/.

    Writes SYNLYNK_HANDOFF.md summarising what was configured before removal.
    Dry-run by default — pass --confirm to execute.
    """
    manifest_data = _load_instruction_manifest()
    docs = None
    try:
        docs = _docs_dir()
    except Exception:
        pass

    cfg = {}
    if os.path.exists(".synlynk/config.json"):
        try:
            cfg = json.load(open(".synlynk/config.json"))
        except Exception:
            pass

    # Build action list
    strip_targets = []
    for fpath, info in manifest_data.items():
        style = _MARKER_STYLE_FOR_TOOL.get(info.get("tool", ""), "html")
        strip_targets.append((fpath, style, info.get("tool", "?")))

    agent_profiles = []
    if os.path.isdir(".agents"):
        agent_profiles = [os.path.join(".agents", f) for f in os.listdir(".agents") if f.endswith(".json")]

    synlynk_dir = ".synlynk"
    docs_dir_path = docs if (remove_docs and docs and os.path.isdir(docs)) else None

    print(f"\n{_BOLD}synlynk exit{_RESET} {'(dry run — pass --confirm to execute)' if dry_run else '(executing)'}\n")

    # Instruction files
    print("  Instruction files:")
    if strip_targets:
        for fpath, style, tool in strip_targets:
            exists = os.path.exists(fpath)
            tag = "remove" if style == "none" else "strip synlynk section"
            label = f"{_DIM}(not found){_RESET}" if not exists else ""
            print(f"    {'→' if dry_run else '✓'} {fpath} [{tool}] — {tag} {label}")
            if not dry_run and exists:
                _strip_synlynk_section(fpath, style)
    else:
        print(f"    {_DIM}no tracked instruction files{_RESET}")

    # Agent profiles
    print("  Agent profiles:")
    if agent_profiles:
        for p in agent_profiles:
            print(f"    {'→' if dry_run else '✓'} remove {p}")
            if not dry_run:
                os.remove(p)
        if not dry_run and os.path.isdir(".agents"):
            try:
                os.rmdir(".agents")
            except OSError:
                pass
    else:
        print(f"    {_DIM}no .agents/ profiles found{_RESET}")

    # .synlynk/ directory
    print(f"  Config & state:")
    print(f"    {'→' if dry_run else '✓'} remove {synlynk_dir}/")
    if not dry_run and os.path.isdir(synlynk_dir):
        import shutil as _shutil
        _shutil.rmtree(synlynk_dir)

    # project-docs (optional)
    if docs_dir_path:
        print(f"  Project docs:")
        print(f"    {'→' if dry_run else '✓'} remove {docs_dir_path}/")
        if not dry_run:
            import shutil as _shutil
            _shutil.rmtree(docs_dir_path)
    elif remove_docs:
        print(f"  Project docs: {_DIM}not found or already absent{_RESET}")

    # Handoff doc
    handoff_path = "SYNLYNK_HANDOFF.md"
    handoff_lines = [
        f"# synlynk handoff — {time.strftime('%Y-%m-%d')}",
        "",
        "synlynk was removed from this repository. This file records what was configured.",
        "",
        "## Configuration",
        f"- Version: {cfg.get('synlynk_version', VERSION)}",
        f"- Mode: {cfg.get('mode', 'unknown')}",
        f"- Agents: {', '.join(cfg.get('agent_slots', {}).keys()) or 'unknown'}",
        f"- Org: {cfg.get('org', 'unknown')} / {cfg.get('repo', 'unknown')}",
        f"- Docs dir: {docs or 'unknown'}",
        "",
        "## Removed",
    ]
    for fpath, style, tool in strip_targets:
        handoff_lines.append(f"- `{fpath}` ({tool}) — synlynk section stripped")
    for p in agent_profiles:
        handoff_lines.append(f"- `{p}` — removed")
    handoff_lines += [
        f"- `.synlynk/` — removed",
        "",
        "## To re-initialize",
        "```",
        f"synlynk init --agents {','.join(cfg.get('agent_slots', {}).keys()) or 'claude,agy,codex,grok'}",
        "```",
        "",
    ]
    print(f"  Handoff doc:")
    print(f"    {'→' if dry_run else '✓'} write {handoff_path}")
    if not dry_run:
        with open(handoff_path, "w") as f:
            f.write("\n".join(handoff_lines))

    print()
    if dry_run:
        print(f"  Dry run complete. Run with {_CYAN}--confirm{_RESET} to apply changes.")
    else:
        print(f"  {_GREEN}synlynk removed.{_RESET} See {handoff_path} for re-init instructions.")
    print()
    return 0


def cmd_repair(dry_run: bool = True) -> int:
    """Exit synlynk and immediately re-initialize from the current configuration.

    Reads config before exit so re-init uses the same agents/mode/org/repo/docs-dir.
    Dry-run by default — pass --confirm to execute.
    """
    cfg = {}
    if os.path.exists(".synlynk/config.json"):
        try:
            cfg = json.load(open(".synlynk/config.json"))
        except Exception:
            pass

    agents_str = ",".join(cfg.get("agent_slots", {}).keys()) or "claude,agy,codex,grok"
    mode = cfg.get("mode", "solo")
    org = cfg.get("org") or None
    repo = cfg.get("repo") or None
    project_id = cfg.get("project_id") or None
    docs_dir_arg = cfg.get("docs_dir") or None

    print(f"\n{_BOLD}synlynk repair{_RESET} {'(dry run — pass --confirm to execute)' if dry_run else '(executing)'}\n")
    print(f"  Captured config: agents={agents_str}  mode={mode}  org={org or '—'}  docs-dir={docs_dir_arg or 'project-docs'}")
    print()

    print("  Step 1: exit")
    cmd_exit(dry_run=dry_run)

    print("  Step 2: re-init")
    if dry_run:
        print(f"    → synlynk init --agents {agents_str} --mode {mode}"
              + (f" --org {org}" if org else "")
              + (f" --repo {repo}" if repo else "")
              + (f" --project-id {project_id}" if project_id else "")
              + (f" --docs-dir {docs_dir_arg}" if docs_dir_arg else ""))
        print()
        print(f"  Dry run complete. Run with {_CYAN}--confirm{_RESET} to apply.")
    else:
        init(
            agents=[a.strip() for a in agents_str.split(",") if a.strip()],
            mode=mode,
            org=org,
            repo=repo,
            project_id=project_id,
            docs_dir=docs_dir_arg,
        )
        try:
            from synlynk.doctor import cleanup_selftest_workspaces

            removed = cleanup_selftest_workspaces()
            if removed:
                print(f"  ✓ Cleaned up {removed} orphaned synlynk-selftest workspace(s)")
        except Exception:
            pass
        print(f"\n  {_GREEN}Repair complete.{_RESET}")
    print()
    return 0


def cmd_sync(dry_run: bool = True, repair_sops: bool = False) -> int:
    """Propagate updated synlynk artifacts to an existing repo without full re-init.

    Updates: instruction file sections (CLAUDE.md, GEMINI.md, etc.), .agents/ profile
    defaults for any slots missing from .agents/. Does NOT touch project-docs/.
    Dry-run by default — pass --confirm to execute.
    """
    print(f"\n{_BOLD}synlynk sync{_RESET} {'(dry run — pass --confirm to execute)' if dry_run else '(executing)'}\n")

    # --- instruction files ---
    manifest_data = _load_instruction_manifest()
    print("  Instruction files:")
    if not manifest_data:
        print(f"    {_DIM}no tracked instruction files — run synlynk init first{_RESET}")
    else:
        _tool_content_builders = {
            "cursor":    (_build_cursor_mdc,            "none"),
            "copilot":   (_build_copilot_instructions,  "html"),
            "windsurf":  (_build_windsurf_rules,        "hash"),
            "universal": (lambda: _build_templates().get("AI_INSTRUCTIONS.md", ""), "html"),
        }
        updated_manifest = {}
        for fpath, info in manifest_data.items():
            tool = info.get("tool", "unknown")
            marker_style = _MARKER_STYLE_FOR_TOOL.get(tool, "html")
            if dry_run:
                print(f"    → {fpath} [{tool}]")
                continue
            if tool in _tool_content_builders:
                builder, _ = _tool_content_builders[tool]
                content = builder()
            else:
                templates = _build_templates()
                content = templates.get(os.path.basename(fpath), "")
            _write_instruction_file(fpath, tool, content, marker_style)
            if os.path.exists(fpath):
                section = _extract_synlynk_section(open(fpath).read(), marker_style)
                if section:
                    updated_manifest[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}
            print(f"    {_GREEN}✓{_RESET} {fpath} [{tool}]")
        if not dry_run and updated_manifest:
            _write_instruction_manifest(updated_manifest)

    # --- agent profiles ---
    print("  Agent profiles (.agents/):")
    try:
        cfg = load_config()
    except Exception:
        cfg = {}
    slots = cfg.get("agent_slots", {})
    if not slots:
        print(f"    {_DIM}no agent slots in config{_RESET}")
    else:
        os.makedirs(".agents", exist_ok=True) if not dry_run else None
        for name in slots:
            profile_path = os.path.join(".agents", f"{name}.json")
            if os.path.exists(profile_path):
                print(f"    {_DIM}· {profile_path} already present — skipped{_RESET}")
                continue
            print(f"    {'→' if dry_run else _GREEN + '✓' + _RESET} {profile_path} — create default profile")
            if not dry_run:
                profile = _load_agent_profile(name)
                os.makedirs(".agents", exist_ok=True)
                with open(profile_path, "w") as f:
                    json.dump(profile, f, indent=2)
                    f.write("\n")

    print()
    if dry_run:
        print(f"  Dry run complete. Run with {_CYAN}--confirm{_RESET} to apply.")
    else:
        print(f"  {_GREEN}Sync complete.{_RESET}")
    print()

    if repair_sops:
        _repair_sops_only(load_config(), dry_run=dry_run)

    return 0











def _check_agent_functional(cli: str) -> Optional[str]:
    """Runs `<cli> --version` to confirm CLI is installed and executable.

    Returns version string (stdout stripped) on success, None otherwise.
    """
    try:
        result = subprocess.run(
            [cli, "--version"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip().splitlines()[0]
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None


def discover_agents(config: dict = None) -> list:
    """Scans for installed agent CLIs and checks each is functional.

    Returns list of dicts: {name, cli, version, functional, capabilities,
    roles, discovery_path}.
    Agents not found on disk are omitted. Agents found but failing --version
    are included with functional=False.
    """
    if config is None:
        config = load_config()

    # Allow per-project overrides of discovery paths.
    discovery_paths = {**AGENT_DISCOVERY_DEFAULTS}
    discovery_paths.update(config.get("agent_discovery_paths", {}))

    found = []
    for name, defaults in AGENT_CAPABILITY_BASELINES.items():
        path = discovery_paths.get(name)
        if path and not os.path.exists(path):
            continue  # config dir not present — skip entirely
        cli = defaults["cli"]
        version = _check_agent_functional(cli)
        found.append({
            "name": name,
            "cli": cli,
            "version": version,
            "functional": version is not None,
            "roles": defaults["roles"],
            "capabilities": defaults["strengths"],
            "non_interactive_flags": defaults["non_interactive_flags"],
            "discovery_path": path or "",
        })
    return found




_INDUSTRY_KEYWORDS = {
    "ott": ["ott", "over-the-top", "streaming service", "video platform"],
    "streaming": ["streaming", "live stream", "media delivery"],
    "fintech": ["fintech", "financial", "payment", "trading", "investment"],
    "banking": ["banking", "bank", "loan", "mortgage", "deposit"],
    "securities": ["securities", "stock", "equity", "portfolio", "brokerage"],
    "healthcare": ["healthcare", "medical", "patient", "clinical", "health"],
    "ecommerce": ["ecommerce", "e-commerce", "shop", "cart", "marketplace"],
    "edtech": ["edtech", "education", "learning", "course", "student"],
    "gaming": ["gaming", "game", "player", "leaderboard", "matchmaking"],
}



_STACK_FINGERPRINTS = [
    ("pyproject.toml", "Python"),
    ("setup.py", "Python"),
    ("Cargo.toml", "Rust"),
    ("go.mod", "Go"),
    ("next.config.js", "Next.js"),
    ("next.config.ts", "Next.js"),
    ("next.config.mjs", "Next.js"),
    ("Pulumi.yaml", "Pulumi"),
    ("Pulumi.yml", "Pulumi"),
    ("Dockerfile", "Docker"),
    ("docker-compose.yml", "Docker"),
    ("docker-compose.yaml", "Docker"),
]

_STACK_EXT_MAP = {
    ".go": "Go",
    ".rs": "Rust",
}






_KNOWN_SKILL_PATTERNS = [
    "~/.claude/plugins/cache/superpowers-marketplace/superpowers/*/",
    "~/.config/gstack/plugins/*/",
]
_SKILL_MANIFEST_NAMES = ("manifest.json", "package.json", "skill.json")








_MONOREPO_MARKERS = ("packages", "apps", "services", "modules", "libs")














STAGE_KEYS = ["stack", "source", "complexity", "tests", "git", "arch"]


























def cmd_agent_configure(agent_name: str) -> None:
    """Interactively write .agents/<agent_name>.json context-profile settings."""
    import json as _json

    if agent_name not in AGENT_CAPABILITY_BASELINES:
        print(f"  Unknown agent '{agent_name}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")
        return

    os.makedirs(".agents", exist_ok=True)
    path = os.path.join(".agents", f"{agent_name}.json")

    existing = {}
    if os.path.exists(path):
        try:
            with open(path) as f:
                existing = _json.load(f)
            print(f"  Existing profile at {path}:")
            for key, value in existing.items():
                print(f"    {key}: {value}")
        except Exception:
            existing = {}

    print(f"\n  Configuring context profile for '{agent_name}' (press Enter to keep current)\n")

    def _ask(default, desc):
        shown = "" if default is None else str(default)
        value = input(f"  {desc} [{shown}]: ").strip()
        return value if value else default

    context_mode = _ask(existing.get("context_mode", "task"),
                        "context_mode (none / task / full)")
    max_bytes_raw = _ask(existing.get("context_max_bytes", None),
                         "context_max_bytes (int, leave blank for no limit)")

    profile = {
        "agent": agent_name,
        "harness": existing.get("harness", agent_name),
        "model": existing.get("model", "unknown"),
        "context_mode": context_mode,
    }
    if max_bytes_raw not in ("", None):
        try:
            profile["context_max_bytes"] = int(max_bytes_raw)
        except (TypeError, ValueError):
            pass

    with open(path, "w") as f:
        _json.dump(profile, f, indent=2)
        f.write("\n")
    print(f"\n  {_GREEN}✓{_RESET} Written {path}")


def cmd_agent_add(agent_name: str) -> None:
    """Retrofit an on-PATH agent into the current project."""
    if agent_name not in AGENT_CAPABILITY_BASELINES:
        print(f"  Error: unknown agent '{agent_name}'. Known: {', '.join(sorted(AGENT_CAPABILITY_BASELINES))}")
        return

    cli_path = shutil.which(agent_name)
    if not cli_path:
        print(f"  Error: agent binary '{agent_name}' is not on PATH.")
        return

    config_path = ".synlynk/config.json"
    config = load_config()
    workgroup_agents = list(config.get("workgroup_agents") or [])
    directive_path = _directive_file_for_agent(agent_name)
    fence_present = _fence_exists(directive_path)

    if agent_name in workgroup_agents and fence_present:
        print(f"  {agent_name} is already fully onboarded — no changes made.")
        return

    created_directive = False
    if not os.path.exists(directive_path):
        templates = _build_templates()
        template_body = templates.get(os.path.basename(directive_path), "")
        if not template_body:
            template_body = f"# synlynk {agent_name} instructions\n"
        with open(directive_path, "w") as f:
            f.write(template_body.rstrip("\n") + "\n")
        created_directive = True

    probe_results = cmd_probe(agent_name, write_fence=False) or []
    probe_result = probe_results[0] if probe_results else {}

    role_list = _default_roles_for_agent(agent_name)
    _upsert_harness_fence(
        directive_path,
        harness_version="roles",
        body=f"## Your Role\n{', '.join(role_list) if role_list else 'general'}\n",
    )

    if agent_name not in workgroup_agents:
        workgroup_agents.append(agent_name)

    agent_slots = dict(config.get("agent_slots") or {})
    agent_slots[agent_name] = agent_name

    roles = dict(config.get("roles") or {})
    if not roles.get(agent_name):
        roles[agent_name] = role_list

    config["workgroup_agents"] = workgroup_agents
    config["agent_slots"] = agent_slots
    config["roles"] = roles
    _write_json_atomic(config_path, config)

    print(f"  {_GREEN}✓{_RESET} added {agent_name} to workgroup_agents")
    print(f"  {_GREEN}✓{_RESET} added {agent_name} to agent_slots")
    if created_directive:
        print(f"  {_GREEN}✓{_RESET} created {directive_path} from template")
    else:
        print(f"  {_GREEN}✓{_RESET} updated {directive_path}")
    print(f"  {_GREEN}✓{_RESET} wrote role fence to {directive_path}")
    if probe_result:
        status = "skipped (up to date)" if probe_result.get("skipped") else probe_result.get("status", "unknown")
        print(f"  {_GREEN}✓{_RESET} probe [{agent_name}] {probe_result.get('version', 'unknown')} → {status}")
    print(f"  {_GREEN}✓{_RESET} onboarded {agent_name} from {cli_path}")


def _run_daily_housekeeping() -> None:
    """Run the once-per-day drift check triggered by exec flow."""
    config_path = ".synlynk/config.json"
    if not os.path.exists(config_path):
        return

    config = load_config()
    today = time.strftime("%Y-%m-%d")
    if config.get("last_housekeeping_date") == today:
        return

    workgroup_agents = [a for a in (config.get("workgroup_agents") or []) if a in AGENT_CAPABILITY_BASELINES]
    known_on_path = {
        harness["name"]
        for harness in _detect_harnesses_on_path()
        if harness.get("name") in AGENT_CAPABILITY_BASELINES
    }
    onboarded = set(workgroup_agents)
    new_agents = sorted(known_on_path - onboarded)

    printed = False
    for agent_name in new_agents:
        print(f"  New agent detected on PATH: {agent_name} — run `synlynk agent add {agent_name}` to onboard it")
        printed = True

    db_conn = None
    try:
        if workgroup_agents:
            db_conn = _get_db()
        for agent_name in workgroup_agents:
            try:
                before = db_conn.execute(
                    "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
                    (agent_name,),
                ).fetchone()
                result = _probe_agent(agent_name, db_conn, write_fence=False)
                after = db_conn.execute(
                    "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
                    (agent_name,),
                ).fetchone()
            except Exception as exc:
                print(f"  Housekeeping probe failed for {agent_name}: {exc}")
                printed = True
                continue
            if before != after:
                before_version = before[0] if before else "none"
                after_version = after[0] if after else result.get("version", "unknown")
                status = result.get("status", "unknown")
                print(f"  Probe drift for {agent_name}: {before_version} → {after_version} ({status})")
                baseline = AGENT_CAPABILITY_BASELINES.get(agent_name)
                if baseline is not None:
                    baseline["last_probe_snapshot"] = {
                        "installed_version": after_version,
                        "capability_hash": after[1] if after else "",
                        "status": status,
                    }
                printed = True
            try:
                _repair_sops_only(agent_name=agent_name, dry_run=False)
            except Exception as exc:
                print(f"  Housekeeping repair failed for {agent_name}: {exc}")
                printed = True
    finally:
        if db_conn is not None:
            db_conn.close()

    config["last_housekeeping_date"] = today
    _write_json_atomic(config_path, config)

    if not printed:
        return


def cmd_configure_agent(
    name: str,
    flags: dict = None,
    envs: dict = None,
    network_deps: list = None,
) -> None:
    """Write per-project harness overrides to .agents/<name>.json."""
    flags = flags or {}
    envs = envs or {}
    network_deps = network_deps or []

    os.makedirs(".agents", exist_ok=True)
    profile_path = os.path.join(".agents", f"{name}.json")
    profile: dict = {}
    if os.path.exists(profile_path):
        try:
            with open(profile_path) as f:
                profile = json.load(f)
        except (json.JSONDecodeError, OSError):
            profile = {}

    overrides = profile.setdefault(
        "harness_overrides",
        {"dispatch_flags": {}, "env": {}, "network_deps": []},
    )
    overrides.setdefault("dispatch_flags", {})
    overrides.setdefault("env", {})
    overrides.setdefault("network_deps", [])

    overrides["dispatch_flags"].update(flags)
    overrides["env"].update(envs)
    for dep in network_deps:
        if dep not in overrides["network_deps"]:
            overrides["network_deps"].append(dep)

    with open(profile_path, "w") as f:
        json.dump(profile, f, indent=2)
        f.write("\n")

    print(f"  ✓ {name}: harness overrides written to {profile_path}")
    if flags:
        print(f"    flags: {flags}")
    if envs:
        print(f"    env:   {envs}")
    if network_deps:
        print(f"    deps:  {network_deps}")


























def _render_codex_log_line(line: str):
    """Renders one line of a Codex --json log into human-readable text."""
    stripped = line.strip()
    if not stripped:
        return line
    try:
        event = json.loads(stripped)
    except (ValueError, TypeError):
        return line
    if not isinstance(event, dict):
        return line
    event_type = event.get("type")
    if event_type in {"thread.started", "turn.started", "item.started", "turn.completed"}:
        return None
    if event_type == "item.completed":
        item = event.get("item", {})
        if not isinstance(item, dict):
            return line
        item_type = item.get("type")
        if item_type == "agent_message":
            return f"{item.get('text', '')}\n\n"
        if item_type == "command_execution":
            output = (item.get("aggregated_output") or "").rstrip("\n")
            return f"$ {item.get('command', '')}\n{output}\n\n"
    return line


def _render_claude_log_line(line: str):
    """Renders one line of a Claude --output-format stream-json log into
    human-readable text."""
    stripped = line.strip()
    if not stripped:
        return line
    try:
        event = json.loads(stripped)
    except (ValueError, TypeError):
        return line
    if not isinstance(event, dict):
        return line
    event_type = event.get("type")
    if event_type in {"system", "rate_limit_event", "result", "user"}:
        return None
    if event_type == "assistant":
        message = event.get("message", {})
        content = message.get("content", []) if isinstance(message, dict) else []
        if not isinstance(content, list):
            return None
        rendered_parts = []
        for block in content:
            if not isinstance(block, dict):
                continue
            block_type = block.get("type")
            if block_type == "text":
                text = block.get("text", "")
                if text:
                    rendered_parts.append(f"{text}\n\n")
            elif block_type == "tool_use":
                tool_name = block.get("name", "")
                tool_input = block.get("input", {})
                try:
                    args = json.dumps(tool_input, separators=(",", ":"))
                except (TypeError, ValueError):
                    args = str(tool_input)
                rendered_parts.append(f"$ {tool_name}({args})\n\n")
        return "".join(rendered_parts) if rendered_parts else None
    return line


def _redact_active_tokens(text: str) -> str:
    """Strip any currently-cached GitHub App installation token values from
    display text. Checks both the in-process cache (same-process dispatch)
    and the on-disk redaction cache (tokens minted by an earlier, separate
    `synlynk dispatch` process), since installation tokens live ~1hr and
    `dispatch`/`logs` are normally different CLI invocations."""
    from synlynk.github_app_auth import _load_redaction_tokens, _token_cache

    for entry in _token_cache.values():
        token = entry.get("token")
        if token:
            text = text.replace(token, "***REDACTED***")
    for token in _load_redaction_tokens():
        text = text.replace(token, "***REDACTED***")
    return text


_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{36}"),
    re.compile(r"ghs_[A-Za-z0-9._-]{20,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"sk-[A-Za-z0-9]{20,}"),
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),
]


def _redact_secret_patterns(text: str) -> str:
    """Redact common, recognizable secret-shaped substrings from captured output.

    Pattern-based and necessarily incomplete (can't catch arbitrary
    high-entropy secrets with no recognizable prefix) -- defense-in-depth
    alongside the dispatched-subprocess env allowlist, for the case where a
    secret still ends up in captured output some other way.
    """
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text


def cmd_logs(job_id: str, tail: int = 50) -> None:
    """Prints the captured stdout of a dispatched job."""
    jobs = _load_jobs()
    job = next((j for j in jobs if j["id"] == job_id), None)
    if job is None:
        print(f"No job found with id '{job_id}'. Run `synlynk jobs` to list jobs.")
        return
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        print(f"Log file not found for job {job_id}.")
        return
    print(f"{_BOLD}── logs: {job_id} ({job['agent']}) ─────────────────────────{_RESET}")
    with open(log_file) as f:
        lines = f.readlines()
    display_lines = lines[-tail:]
    if job.get("agent") == "codex":
        renderer = _render_codex_log_line
    elif job.get("agent") == "claude":
        renderer = _render_claude_log_line
    else:
        renderer = None
    if renderer is not None:
        for line in display_lines:
            rendered = renderer(line)
            if rendered is not None:
                print(_redact_secret_patterns(_redact_active_tokens(rendered)), end="")
    else:
        for line in display_lines:
            print(_redact_secret_patterns(_redact_active_tokens(line)), end="")
    if len(lines) > tail:
        print(f"\n{_DIM}(showing last {tail} of {len(lines)} lines){_RESET}")
    summary_path = _job_summary_path(job_id)
    if os.path.exists(summary_path):
        print()
        with open(summary_path) as f:
            print(f.read(), end="")


def cmd_shell(story_id: str = None) -> None:
    """Spawns an interactive subshell with synlynk context env vars injected.

    The shell runs in the current directory (worktree-per-story lands in v0.5.0).
    On exit the calling process resumes normally.
    """
    shell = os.environ.get("SHELL", "/bin/bash")
    env = {**os.environ,
           "SYNLYNK_PROJECT_DIR": os.path.abspath("."),
           "SYNLYNK_STORY_ID": story_id or "",
           "SYNLYNK_CONTEXT": os.path.abspath(".synlynk/context.md")}
    label = f"story #{story_id}" if story_id else "synlynk"
    print(f"{_BOLD}Entering synlynk shell ({label}).{_RESET} "
          f"Type {_CYAN}exit{_RESET} to return.")
    subprocess.run([shell], env=env)
    print(f"{_DIM}Returned from synlynk shell.{_RESET}")


def cmd_launch(agent: str, story_id: str = None) -> None:
    """Launches an agent CLI interactively in the current directory.

    Pre-generates .synlynk/context-<agent>.md and starts the CLI so the
    agent reads it as initial context. Stdout/stderr are not captured —
    this is an interactive session. Telemetry is logged on exit.
    """
    if agent not in AGENT_CAPABILITY_BASELINES:
        print(f"Unknown agent '{agent}'. Known: {list(AGENT_CAPABILITY_BASELINES)}")
        return

    cli = AGENT_CAPABILITY_BASELINES[agent]["cli"]

    try:
        generate_context(scope="full")
    except Exception:
        pass
    src = ".synlynk/context.md"
    dest = f".synlynk/context-{agent}.md"
    if os.path.exists(src):
        import shutil as _shutil
        _shutil.copy(src, dest)

    label = f"story #{story_id}" if story_id else "interactive session"
    print(f"{_BOLD}Launching {agent} — {label}.{_RESET}")
    print(f"  Context: {_CYAN}{dest}{_RESET}")
    print(f"  Exit the agent to return to synlynk.\n")

    start = time.time()
    result = subprocess.run([cli])
    duration = time.time() - start

    log_telemetry_event({"type": "launch", "agent": agent,
                         "story_id": story_id, "exit_code": result.returncode,
                         "duration_s": round(duration, 1)})
    model_version = extract_model_version("", agent=agent)
    update_costs(
        cli,
        0,
        0,
        duration,
        cache_read_tokens=0,
        model_version=model_version,
        story_id=story_id,
        agent=agent,
        basis="none",
    )
    print(f"\n{_DIM}Returned from {agent}. Duration: {duration:.0f}s{_RESET}")




def cmd_run_trio(task: str, story_id: str = None) -> None:
    """Dispatches all functional agents in parallel — one job per agent.

    This is a parallel convenience wrapper, NOT the sequential Trio pipeline.
    Each agent gets the same task description and full context. For the
    sequential Architect→Build→Verify pipeline, see the Trio Protocol spec.
    """
    agents = [a for a in discover_agents() if a["functional"]]
    if not agents:
        print("No functional agents found. Run `synlynk init` to set up your Hybrid Workgroup.")
        return
    if len(agents) < 3:
        print(f"  {_YELLOW}Only {len(agents)} agent(s) available "
              f"(trio needs 3). Dispatching what's configured.{_RESET}")

    print(f"{_BOLD}✨ Dispatching {len(agents)} agents in parallel{_RESET}")
    print(f"  Task: {task}\n")

    jobs = []
    for ag in agents:
        job = dispatch_agent(ag["name"], task, story_id=story_id)
        jobs.append(job)
        role = ag["roles"][0] if ag["roles"] else "worker"
        print(f"  {_GREEN}▶{_RESET} [{job['id']}] {ag['name']:10} → {role}  PID {job['pid']}")

    print(f"\n  {_DIM}All agents running in background.{_RESET}")
    print(f"  Monitor with: {_CYAN}synlynk jobs{_RESET}")
    print(f"  View output:  {_CYAN}synlynk logs <job-id>{_RESET}")


def set_state(state: str) -> None:
    """Writes synlynk state to .synlynk/state and updates terminal title."""
    icons = {"watching": "●", "active": "⚡", "stopped": "○"}
    state_file = ".synlynk/state"
    if not os.path.exists(".synlynk"):
        return
    with open(state_file, "w") as f:
        f.write(state)
    if sys.stdout.isatty():
        project = os.path.basename(os.getcwd())
        title = f"{icons.get(state, '○')} synlynk: {state}  ·  {project}"
        sys.stdout.write(f"\033]0;{title}\007")
        sys.stdout.flush()

def detect_remote_owner_repo() -> tuple:
    """Returns (owner, repo) from git remote origin URL, or (None, None)."""
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            capture_output=True, text=True
        )
        if result.returncode != 0:
            return None, None
        url = result.stdout.strip().rstrip("/")
        if url.endswith(".git"):
            url = url[:-4]
        if "github.com/" in url:
            path = url.split("github.com/")[-1]
        elif "github.com:" in url:
            path = url.split("github.com:")[-1]
        else:
            return None, None
        parts = path.split("/")
        return (parts[0], parts[1]) if len(parts) >= 2 else (None, None)
    except Exception:
        return None, None


def _update_config(updates: dict) -> None:
    """Merges updates into .synlynk/config.json in-place."""
    config_file = ".synlynk/config.json"
    if not os.path.exists(".synlynk"):
        return
    config = load_config()
    config.update(updates)
    _write_json_atomic(config_file, config)


# Task 3-5: Repo scanning, maturity detection, section signals, semantic matching, GH ID extraction
_PROJECT_DOC_NAMES = {"roadmap.md", "todo.md", "memory.md", "costs.md", "devlog.md"}
_AGENT_FILE_NAMES = {"CLAUDE.md", "GEMINI.md", "AGENTS.md", "AI_INSTRUCTIONS.md"}
_SCAN_SKIP_DIRS = {
    ".git", "node_modules", ".synlynk", "project-docs",
    "__pycache__", ".venv", "venv", "env", ".next", "dist", "build",
    "vendor", ".worktrees", "coverage", ".nyc_output", "target", "out", "tmp",
}

_SOURCE_EXTENSIONS = {
    ".py": "python",
    ".js": "javascript", ".mjs": "javascript", ".cjs": "javascript",
    ".ts": "typescript", ".tsx": "typescript",
    ".go": "go",
    ".rs": "rust",
    ".rb": "ruby",
    ".java": "java",
    ".kt": "kotlin",
    ".sh": "shell",
}

_SOURCE_ENTRY_POINTS = {
    "main.py", "app.py", "server.py", "index.js", "index.ts", "main.go",
    "lib.rs", "main.rs", "app.rb", "manage.py", "wsgi.py", "asgi.py", "__init__.py",
}

_SYMBOL_PATTERNS = {
    "python": [
        (re.compile(r"^async def (\w+)"), "async_function"),
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^([A-Z_]{2,})\s*="), "constant"),
    ],
    "javascript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "typescript": [
        (re.compile(r"^export (?:default )?(?:async )?function (\w+)"), "function"),
        (re.compile(r"^export (?:default )?class (\w+)"), "class"),
        (re.compile(r"^export interface (\w+)"), "interface"),
        (re.compile(r"^export type (\w+)"), "type"),
        (re.compile(r"^export enum (\w+)"), "enum"),
        (re.compile(r"^export const (\w+)"), "constant"),
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
    ],
    "go": [
        (re.compile(r"^func (?:\(\w+ \*?\w+\) )?(\w+)"), "function"),
        (re.compile(r"^type (\w+) struct"), "struct"),
        (re.compile(r"^type (\w+) interface"), "interface"),
    ],
    "rust": [
        (re.compile(r"^pub fn (\w+)"), "function"),
        (re.compile(r"^pub struct (\w+)"), "struct"),
        (re.compile(r"^pub trait (\w+)"), "trait"),
        (re.compile(r"^pub enum (\w+)"), "enum"),
        (re.compile(r"^pub type (\w+)"), "type"),
    ],
    "ruby": [
        (re.compile(r"^def (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^module (\w+)"), "module"),
    ],
    "java": [
        (re.compile(r"(?:public|protected) (?:class|interface|enum) (\w+)"), "class"),
        (re.compile(r"(?:public|protected) \w+ (\w+)\s*\("), "function"),
    ],
    "kotlin": [
        (re.compile(r"^fun (\w+)"), "function"),
        (re.compile(r"^class (\w+)"), "class"),
        (re.compile(r"^object (\w+)"), "class"),
        (re.compile(r"^interface (\w+)"), "interface"),
    ],
    "shell": [
        (re.compile(r"^function (\w+)"), "function"),
        (re.compile(r"^(\w+)\(\)"), "function"),
    ],
}

SECTION_SIGNALS: dict = {
    "## Live Issues SOP": [
        "live issue", "live-issue", "sev1", "sev2", "sev3", "rca", "[live-",
    ],
    "## Mid-Session Anti-Amnesia Protocol": [
        "25,000 tokens", "25k tokens", "compaction", "compaction imminent",
        "mid-session", "checkpoint every",
    ],
    "## Mandatory 4-Doc Discipline": [
        "roadmap.md", "devlog", "costs.md", "memory.md",
        "mandatory document", "four doc", "4-doc",
    ],
    "## GitHub Projects v2 Integration": [
        "updateProjectV2", "projectId", "PVT_", "PVTSSF_",
        "github projects", "programme board",
    ],
    "## Git Worktree-First Policy": [
        "git worktree", "worktree add", "never commit to main",
        "never commit to master",
    ],
}




































_INSTRUCTIONS_MANIFEST = ".synlynk/instructions.json"

_INSTRUCTION_TARGETS = [
    # (path, tool, marker_style, detection_fn)
    # detection_fn: called in init() to decide whether to write the file.
    ("CLAUDE.md",                          "claude",    "html", lambda: True),
    ("GEMINI.md",                          "agy",       "html", lambda: True),
    ("AGENTS.md",                          "codex",     "html", lambda: True),
    ("GROK.md",                            "grok",      "html", lambda: True),
    (".cursor/rules/synlynk.mdc",          "cursor",    "none", lambda: os.path.isdir(".cursor")),
    (".github/copilot-instructions.md",    "copilot",   "html", lambda: os.path.isdir(".github")),
    (".windsurfrules",                     "windsurf",  "hash", lambda: True),
    ("AI_INSTRUCTIONS.md",                 "universal", "html", lambda: True),
]





_MARKER_STYLE_FOR_TOOL = {
    "claude":    "html",
    "agy":       "html",
    "codex":     "html",
    "grok":      "html",
    "cursor":    "none",
    "copilot":   "html",
    "windsurf":  "hash",
    "universal": "html",
}












def _is_interactive(cmd_args: list) -> bool:
    """Returns True if the command needs a real TTY (no stdout capture)."""
    NON_INTERACTIVE = ["--no-tty", "--output-format json", "--print",
                       "--non-interactive", "-p "]
    cmd_str = " ".join(cmd_args)
    return not any(flag in cmd_str for flag in NON_INTERACTIVE)


def _inject_grok_rules(cmd_args: list) -> list:
    """Adds Grok rules flags when invoking grok and the rule files exist."""
    if not cmd_args or cmd_args[0] != "grok":
        return list(cmd_args)

    injected = [cmd_args[0]]
    if os.path.exists("GROK.md"):
        injected.extend(["--rules", "GROK.md"])
    if "-p" in cmd_args and os.path.exists(os.path.join(".synlynk", "context.md")):
        injected.extend(["--rules", os.path.join(".synlynk", "context.md")])
    injected.extend(cmd_args[1:])
    return injected


def _tee_process(process, buffer: list) -> None:
    """Reads process stdout line-by-line, writes to terminal and appends to buffer."""
    for line in iter(process.stdout.readline, b''):
        sys.stdout.buffer.write(line)
        sys.stdout.buffer.flush()
        buffer.append(line.decode('utf-8', errors='replace'))
    process.stdout.close()





















def _archive_old_devlog_entries(devlog_path: str) -> None:
    """Moves devlog entries older than 30 days to devlogs/archive/YYYY-MM.md."""
    import calendar
    if not os.path.exists(devlog_path):
        return
    cutoff = time.time() - (30 * 24 * 3600)
    pattern = re.compile(r'^## (\d{4}-\d{2}-\d{2})')
    sections = []
    current_lines, current_date = [], None
    with open(devlog_path) as f:
        for line in f:
            m = pattern.match(line)
            if m:
                if current_lines:
                    sections.append((current_date, current_lines))
                current_date = m.group(1)
                current_lines = [line]
            else:
                current_lines.append(line)
    if current_lines:
        sections.append((current_date, current_lines))

    keep, archive_by_month = [], {}
    for date_str, lines in sections:
        if date_str is None:
            keep.append((date_str, lines))
            continue
        try:
            ts = calendar.timegm(time.strptime(date_str, "%Y-%m-%d"))
            if ts < cutoff:
                month_key = date_str[:7]
                archive_by_month.setdefault(month_key, []).extend(lines)
            else:
                keep.append((date_str, lines))
        except ValueError:
            keep.append((date_str, lines))

    if not archive_by_month:
        return

    archive_dir = os.path.join(os.path.dirname(devlog_path), "archive")
    os.makedirs(archive_dir, exist_ok=True)
    for month_key, lines in archive_by_month.items():
        with open(os.path.join(archive_dir, f"{month_key}.md"), "a") as f:
            f.writelines(lines)

    with open(devlog_path, "w") as f:
        for _, lines in keep:
            f.writelines(lines)

def _resolve_member_id(username: str) -> str:
    """Looks up username in the member_aliases registry; falls back to username
    itself when unregistered (matches audit-docs' "unregistered" finding — an
    unregistered identity is reported, never silently reassigned)."""
    try:
        conn = _get_db()
        row = conn.execute(
            "SELECT member_id FROM member_aliases WHERE alias = ?", (username,)
        ).fetchone()
        conn.close()
        return row[0] if row else username
    except Exception:
        return username


def checkpoint() -> None:
    """Archives done tasks, refreshes context, and emits a telemetry event."""
    set_state("active")
    _check_upstream_divergence()
    username = get_username()
    canonical_id = _resolve_member_id(username)
    todo_path = "project-docs/todo.md"
    devlog_path = f"project-docs/devlogs/{canonical_id}.md"

    # Collect resolved tasks (done/superseded/absorbed) and keep the rest
    completed, active_lines = [], []
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if re.match(r'\s*-\s*\[(x|~|>)\]', line, re.IGNORECASE):
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[(x|~|>)\]\s*', '', line, flags=re.IGNORECASE).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    completed.append({"id": id_m.group(1) if id_m else None, "text": text})
                else:
                    active_lines.append(line)

    # Append resolved tasks to devlog
    if completed:
        os.makedirs(os.path.dirname(devlog_path), exist_ok=True)
        with open(devlog_path, "a") as f:
            f.write(f"\n## {time.strftime('%Y-%m-%d')}\n### Resolved (checkpoint)\n")
            for task in completed:
                f.write(f"- {task['text']}\n")
        with open(todo_path, "w") as f:
            f.writelines(active_lines)

    _archive_old_devlog_entries(devlog_path)
    generate_context()

    completed_ids = [t["id"] for t in completed if t["id"]]
    log_telemetry_event({
        "type": "checkpoint",
        "schema_version": 1,
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S'),
        "user": username,
        "completed_task_count": len(completed),
        "completed_task_ids": completed_ids,
        "devlog_entry_appended": bool(completed),
    })

    total_usd, total_requests = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    pct = (total_usd / limit_usd * 100) if limit_usd else 0

    daemon = WatchDaemon()
    set_state("watching" if daemon._is_running() else "stopped")

    print(f"\n✓ checkpoint [@{username}] — {len(completed)} tasks archived, context refreshed")
    if completed:
        names = "  ·  ".join(f'"{t["text"][:40]}"' for t in completed[:3])
        print(f"  Archived: {names}")
    print(f"  Budget: ${total_usd:.2f} / ${limit_usd:.2f} ({pct:.0f}%)  ·  {total_requests} requests")

def cmd_release(dry_run: bool = False, version: Optional[str] = None, bump: bool = False, minor: bool = False) -> None:
    """Cut a named release: bump version, prepend CHANGELOG.md, write blog stub, print checklist."""
    import datetime
    import re

    # Resolve project root:
    # First priority: check if a VERSION file exists in CWD. If so, root is CWD.
    if os.path.exists(os.path.join(os.getcwd(), "VERSION")):
        root = os.getcwd()
    else:
        root = _get_project_root()

    version_path = os.path.join(root, "VERSION")
    changelog_path = os.path.join(root, "CHANGELOG.md")
    blog_dir = os.path.join(root, "docs", "blog")

    # Step a: Determine next version
    if version:
        next_version = version
    else:
        # read current VERSION file
        if os.path.exists(version_path):
            with open(version_path, "r") as f:
                current_version = f.read().strip()
        else:
            current_version = "0.10.0"
        
        # parse current_version
        parts = current_version.split(".")
        if len(parts) >= 3:
            try:
                major = int(parts[0])
                minor_ver = int(parts[1])
                patch = int(parts[2].split("-")[0].split("+")[0]) # strip any prerelease suffix
            except ValueError:
                major, minor_ver, patch = 0, 10, 0
        else:
            major, minor_ver, patch = 0, 10, 0

        if minor:
            next_version = f"{major}.{minor_ver + 1}.0"
        else:
            next_version = f"{major}.{minor_ver}.{patch + 1}"

    print(f"Proposed version: v{next_version}")

    # Step b: Read merged stories since last git tag
    try:
        tag_cmd = "git describe --tags --abbrev=0 2>/dev/null || echo ''"
        last_tag = subprocess.check_output(tag_cmd, shell=True).decode("utf-8").strip()
    except Exception:
        last_tag = ""

    if last_tag:
        git_cmd = f"git log {last_tag}..HEAD --oneline"
    else:
        git_cmd = "git log -n 20 --oneline"

    try:
        log_output = subprocess.check_output(git_cmd, shell=True).decode("utf-8").strip()
    except Exception:
        log_output = ""

    lines = log_output.splitlines() if log_output else []
    added = []
    fixed = []
    changed = []

    for line in lines:
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        if len(parts) < 2:
            continue
        msg = parts[1].strip()
        
        match = re.match(r"^([a-zA-Z0-9_\-]+)(?:\(.*?\))?\s*:\s*(.*)", msg)
        if match:
            prefix = match.group(1).lower()
        else:
            prefix = ""

        if prefix == "feat":
            added.append(msg)
        elif prefix == "fix":
            fixed.append(msg)
        else:
            changed.append(msg)

    # Step c: Build CHANGELOG entry
    today = datetime.date.today().isoformat()
    changelog_parts = [f"## [v{next_version}] - {today}"]
    if added:
        changelog_parts.append("### Added")
        changelog_parts.extend(f"- {item}" for item in added)
    if fixed:
        changelog_parts.append("### Fixed")
        changelog_parts.extend(f"- {item}" for item in fixed)
    if changed:
        changelog_parts.append("### Changed")
        changelog_parts.extend(f"- {item}" for item in changed)
    
    changelog_entry = "\n".join(changelog_parts) + "\n\n"

    # Step d: Build blog post stub
    # Determine NN
    next_nn = 0
    if os.path.exists(blog_dir):
        existing_numbers = []
        for name in os.listdir(blog_dir):
            if name.endswith(".md"):
                match = re.match(r"^(\d+)-", name)
                if match:
                    existing_numbers.append(int(match.group(1)))
        if existing_numbers:
            next_nn = max(existing_numbers) + 1

    nn_str = f"{next_nn:02d}"
    blog_filename = f"{nn_str}-prTBD-v{next_version}.md"
    blog_path = os.path.join(blog_dir, blog_filename)

    # Read template from docs/blog/README.md if it exists
    readme_path = os.path.join(blog_dir, "README.md")
    template_content = None
    if os.path.exists(readme_path):
        try:
            with open(readme_path, "r") as f:
                readme_text = f.read()
            h_idx = readme_text.find("## Per-PR Post Template")
            if h_idx != -1:
                sub = readme_text[h_idx:]
                m_idx = sub.find("```markdown")
                if m_idx != -1:
                    start_idx = m_idx + len("```markdown")
                    end_idx = sub.find("```", start_idx)
                    if end_idx != -1:
                        template_content = sub[start_idx:end_idx].strip()
        except Exception:
            pass

    if not template_content:
        template_content = """---
title: "PR #N — <theme>"
date: YYYY-MM-DD
series: "Building the OS for Multi-Agent Development"
post: N
pr: "#N"
merged: YYYY-MM-DD (or status: open)
---

## The Broader Goal at the End of the Previous PR
[What was the stated/understood goal before this work started?]

## Strategic Shifts in This PR (if any)
[What changed in the broader strategy? What moved the goalpost and why?]

## What This PR Shipped
[Deep technical description: commands, key implementation decisions, data structures, test approach]

## Brainstorm Visuals Used
[Links to any HTML brainstorm files in docs/brainstorm/ that informed decisions in this PR]

## What This Achieved on the Path to Autonomy
[Specific ways this PR advances the eventual goal of autonomous multi-agent dispatch]

## Strategic Note: The Goal at the End of This PR
[The new goalpost, as understood after this PR's decisions]"""

    stub_content = template_content
    stub_content = stub_content.replace('title: "PR #N — <theme>"', f'title: "PR #TBD — v{next_version} Release"')
    stub_content = stub_content.replace('date: YYYY-MM-DD', f'date: {today}')
    stub_content = stub_content.replace('post: N', f'post: {next_nn}')
    stub_content = stub_content.replace('pr: "#N"', 'pr: "#TBD"')
    stub_content = stub_content.replace('merged: YYYY-MM-DD (or status: open)', 'status: open')
    stub_content = stub_content.replace('merged: status: open', 'status: open')

    if dry_run:
        # Step f: In dry-run mode, print everything but write nothing
        print("\n--- Proposed CHANGELOG Entry ---")
        print(changelog_entry.strip())
        print("\n--- Proposed Blog Post Stub ---")
        print(f"Path: docs/blog/{blog_filename}")
        print(stub_content.strip())
        print("\n--------------------------------")
    else:
        # Write VERSION file
        with open(version_path, "w") as f:
            f.write(next_version + "\n")
            
        # Write to synlynk/__init__.py VERSION if it exists
        init_py_path = os.path.join(root, "synlynk", "__init__.py")
        if os.path.exists(init_py_path):
            with open(init_py_path, "r") as f:
                init_content = f.read()
            new_init_content = re.sub(
                r'^VERSION\s*=\s*".*"',
                f'VERSION = "{next_version}"',
                init_content,
                flags=re.MULTILINE
            )
            with open(init_py_path, "w") as f:
                f.write(new_init_content)

        # Prepend to CHANGELOG.md (create if missing)
        if os.path.exists(changelog_path):
            with open(changelog_path, "r") as f:
                old_content = f.read()
            match = re.search(r"##\s*\[v?\d+\.\d+\.\d+\]", old_content)
            if match:
                idx = match.start()
                new_changelog = old_content[:idx] + changelog_entry + "---\n\n" + old_content[idx:]
            else:
                idx = old_content.find("## ")
                if idx != -1:
                    new_changelog = old_content[:idx] + changelog_entry + "---\n\n" + old_content[idx:]
                else:
                    new_changelog = old_content + "\n\n" + changelog_entry
        else:
            new_changelog = "# Changelog\n\nAll notable changes to synlynk are documented here.\n\n" + changelog_entry
            
        with open(changelog_path, "w") as f:
            f.write(new_changelog)

        # Write blog post stub
        os.makedirs(os.path.dirname(blog_path), exist_ok=True)
        with open(blog_path, "w") as f:
            f.write(stub_content + "\n")

    # Step e: Print named release checklist
    print(f"synlynk release checklist for v{next_version}")
    print("[x] VERSION bumped")
    print("[x] CHANGELOG entry written")
    print(f"[x] Blog post stub: docs/blog/{blog_filename}")
    print(f"[ ] git tag v{next_version} && git push --tags")
    print(f"[ ] gh release create v{next_version}")
    print("[ ] Roadmap row marked shipped")

def _load_telemetry_events() -> list:
    """Returns telemetry events from .synlynk/telemetry.json, or [] on failure."""
    telemetry_file = ".synlynk/telemetry.json"
    if not os.path.exists(telemetry_file):
        return []
    try:
        with open(telemetry_file) as f:
            events = json.load(f)
        return events if isinstance(events, list) else []
    except (json.JSONDecodeError, IOError):
        return []


def _parse_status_timestamp(value):
    import datetime as _dt

    if value is None:
        return None
    if isinstance(value, (int, float)):
        return _dt.datetime.fromtimestamp(float(value), tz=_dt.timezone.utc)
    if not isinstance(value, str):
        return None
    try:
        dt = _dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=_dt.timezone.utc)
    return dt.astimezone(_dt.timezone.utc)


def _humanize_ago(value) -> str:
    import datetime as _dt

    dt = _parse_status_timestamp(value)
    if dt is None:
        return "not probed"
    now = _dt.datetime.now(_dt.timezone.utc)
    age_s = max(0, int((now - dt).total_seconds()))
    if age_s < 60:
        return f"{age_s}s ago"
    if age_s < 3600:
        return f"{age_s // 60}m ago"
    if age_s < 86400:
        return f"{age_s // 3600}h ago"
    return f"{age_s // 86400}d ago"


def _load_platform_harness_rows() -> tuple:
    """Returns (rows, source) for platform health tables."""
    known_agents = ["claude", "agy", "codex", "grok", "gemini"]
    try:
        conn = _get_db()
    except Exception:
        conn = None
    db_rows = []
    if conn is not None:
        try:
            db_rows = conn.execute(
                "SELECT agent_name, installed_version, last_probe_at, "
                "compliance_status AS probe_status, capability_hash "
                "FROM harness_records ORDER BY agent_name"
            ).fetchall()
        except Exception:
            db_rows = []
        finally:
            conn.close()

    if db_rows:
        rows = []
        for agent_name, installed_version, last_probe_at, probe_status, capability_hash in db_rows:
            rows.append({
                "agent_name": agent_name,
                "installed_version": installed_version or "—",
                "last_probe_at": last_probe_at,
                "probe_status": probe_status or "unknown",
                "capability_hash": capability_hash or "",
                "installed": True,
            })
        return rows, "db"

    rows = []
    for agent_name in known_agents:
        path = shutil.which(agent_name)
        version = "—"
        if path:
            try:
                result = subprocess.run(
                    [agent_name, "--version"], capture_output=True, text=True, timeout=5
                )
                raw = (result.stdout or result.stderr or "").strip()
                if raw:
                    version = raw.split()[-1]
            except Exception:
                version = os.path.basename(path)
        rows.append({
            "agent_name": agent_name,
            "installed_version": version,
            "last_probe_at": None,
            "probe_status": "unknown",
            "capability_hash": "",
            "installed": bool(path),
        })
    return rows, "which"


def _load_platform_drift_agents() -> tuple:
    """Returns drifted agent names and raw DRIFT sentinel lines."""
    sentinel_file = ".synlynk/sentinel.md"
    if not os.path.exists(sentinel_file):
        return set(), []
    try:
        with open(sentinel_file) as f:
            drift_lines = [line.strip() for line in f if "DRIFT" in line]
    except IOError:
        return set(), []
    drift_agents = set()
    for line in drift_lines:
        lower = line.lower()
        for agent_name in ("claude", "agy", "codex", "grok", "gemini"):
            if agent_name in lower:
                drift_agents.add(agent_name)
    return drift_agents, drift_lines


def _load_platform_budget_pulse(events: list, limit_usd: float) -> tuple:
    import datetime as _dt

    now = _dt.datetime.now(_dt.timezone.utc)
    daily_cutoff = now - _dt.timedelta(days=1)
    weekly_cutoff = now - _dt.timedelta(days=7)
    daily = 0.0
    weekly = 0.0
    for event in events:
        cost = event.get("cost_usd")
        if cost is None:
            continue
        ts = _parse_status_timestamp(
            event.get("timestamp") or event.get("ts") or event.get("created_at")
        )
        if ts is None:
            continue
        try:
            cost_val = float(cost)
        except (TypeError, ValueError):
            continue
        if ts >= weekly_cutoff:
            weekly += cost_val
        if ts >= daily_cutoff:
            daily += cost_val
    remaining = max(0.0, limit_usd - weekly) if limit_usd else 0.0
    pct_used = (weekly / limit_usd * 100.0) if limit_usd else 0.0
    return daily, weekly, remaining, pct_used


def _print_platform_table(title: str, headers: list, rows: list) -> None:
    print()
    print(f" {title}")
    if not rows:
        print("   (none active)")
        return
    widths = [len(h) for h in headers]
    rendered_rows = []
    for row in rows:
        rendered = [str(value) for value in row]
        rendered_rows.append(rendered)
        for idx, value in enumerate(rendered):
            widths[idx] = max(widths[idx], len(value))
    print("  " + "  ".join(h.ljust(widths[idx]) for idx, h in enumerate(headers)))
    for rendered in rendered_rows:
        print("  " + "  ".join(rendered[idx].ljust(widths[idx]) for idx in range(len(headers))))


def _print_platform_health() -> bool:
    import datetime as _dt

    events = _load_telemetry_events()
    config = load_config()
    limit_usd = float(config.get("budget", {}).get("limit_usd", 0.0) or 0.0)
    daily_burn, weekly_burn, remaining_budget, pct_used = _load_platform_budget_pulse(events, limit_usd)
    drift_agents, drift_lines = _load_platform_drift_agents()
    rows, source = _load_platform_harness_rows()
    now = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

    print(f"◆ synlynk platform health  {now}")

    compliance_rows = []
    availability_rows = []
    for row in rows:
        agent_name = row["agent_name"]
        probe_status = "DRIFT" if agent_name in drift_agents else "OK"
        status_icon = "⚠" if probe_status == "DRIFT" else "✓"
        age = _humanize_ago(row.get("last_probe_at"))
        compliance_rows.append([
            agent_name,
            row.get("installed_version") or "—",
            f"probed {age}" if age != "not probed" else "not probed",
            f"{status_icon} {probe_status}",
        ])
        if row.get("installed", False):
            tc_status = "known" if row.get("capability_hash") else "unknown"
            availability_rows.append([
                agent_name,
                row.get("installed_version") or "—",
                f"✓ {tc_status}" if tc_status == "known" else "⚠ unknown",
            ])

    _print_platform_table(
        "HARNESSES",
        ["agent", "version", "probe", "compliance"],
        compliance_rows,
    )

    _print_platform_table(
        "AGENT AVAILABILITY",
        ["agent", "version", "TC"],
        availability_rows,
    )

    print()
    print(" BUDGET")
    print(
        f"   today: ${daily_burn:.2f}  ·  week: ${weekly_burn:.2f}  ·  "
        f"remaining: ${remaining_budget:.2f} / ${limit_usd:.2f}  ·  {pct_used:.0f}% used"
    )

    print()
    print(" SENTINELS")
    if drift_lines:
        for line in drift_lines:
            print(f"   {line}")
    else:
        print("   (none active)")

    return bool(drift_lines) or (limit_usd > 0 and weekly_burn >= limit_usd)


def cmd_status(json_output: bool = False, platform: bool = False) -> None:
    """Displays project state dashboard. Exits 1 if sentinel active or budget exceeded."""
    if platform:
        has_alert = _print_platform_health()
        sys.exit(1 if has_alert else 0)

    username = get_username()
    mode = get_mode()

    # Active tasks
    active_tasks = []
    todo_path = "project-docs/todo.md"
    if os.path.exists(todo_path):
        with open(todo_path) as f:
            for line in f:
                if "- [ ]" in line:
                    id_m = re.search(r'<!--\s*id:\s*(\d+)\s*-->', line)
                    text = re.sub(r'-\s*\[ \]\s*', '', line).strip()
                    text = re.sub(r'<!--.*?-->', '', text).strip()
                    active_tasks.append({"id": id_m.group(1) if id_m else None, "text": text})

    telemetry_events = _load_telemetry_events()

    # Last checkpoint from telemetry
    last_checkpoint = None
    for e in reversed(telemetry_events):
        if e.get("type") == "checkpoint":
            last_checkpoint = e
            break

    # Sentinel alerts
    sentinel_alerts = []
    sentinel_file = ".synlynk/sentinel.md"
    if os.path.exists(sentinel_file):
        with open(sentinel_file) as f:
            for line in f:
                if line.startswith("- ["):
                    sentinel_alerts.append(line.strip())

    # Budget
    total_usd, total_requests = parse_costs_md()
    config = load_config()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]

    # Watcher
    daemon = WatchDaemon()
    watcher_running = daemon._is_running()
    last_trigger_file = None
    for e in reversed(telemetry_events):
        if e.get("type") == "watch_trigger":
            last_trigger_file = e.get("changed_file")
            break

    # Teammates (team mode)
    teammates = []
    if mode == "team":
        devlogs_dir = "project-docs/devlogs"
        if os.path.exists(devlogs_dir):
            for fname in sorted(os.listdir(devlogs_dir)):
                if fname.endswith(".md") and fname not in (f"{username}.md", "README.md"):
                    fpath = os.path.join(devlogs_dir, fname)
                    teammates.append({
                        "user": fname[:-3],
                        "last_active": _get_last_devlog_date(fpath),
                    })

    has_alert = bool(sentinel_alerts) or total_usd >= limit_usd or total_requests >= limit_reqs

    if json_output:
        data = {
            "schema_version": 1,
            "timestamp": time.strftime('%Y-%m-%dT%H:%M:%S'),
            "user": username,
            "mode": mode,
            "active_tasks": active_tasks,
            "last_checkpoint": last_checkpoint,
            "sentinel": {"alerts": sentinel_alerts},
            "budget": {
                "used_usd": round(total_usd, 4),
                "limit_usd": limit_usd,
                "requests": total_requests,
                "limit_requests": limit_reqs,
            },
            "watcher": {"running": watcher_running, "last_trigger_file": last_trigger_file},
            "teammates": teammates,
        }
        print(json.dumps(data, indent=2))
        sys.exit(1 if has_alert else 0)

    # Human output
    sep = "─" * 45
    print(sep)
    print(f" synlynk status · @{username} · {mode} mode")
    print(sep)
    print(f" ACTIVE TASKS ({len(active_tasks)})")
    for t in active_tasks:
        tid = f"#{t['id']}" if t['id'] else ""
        print(f"   [ ] {t['text']:<40} {tid}")
    print()
    print(" LAST CHECKPOINT")
    if last_checkpoint:
        print(f"   @{last_checkpoint.get('user')} · {last_checkpoint.get('timestamp')} · "
              f"{last_checkpoint.get('completed_task_count', 0)} tasks archived")
    else:
        print("   No checkpoints yet")
    print()
    print(" SENTINEL")
    if sentinel_alerts:
        for alert in sentinel_alerts:
            print(f"   ⚠ {alert}")
    else:
        print("   ✓ No alerts")
    print()
    pct = (total_usd / limit_usd * 100) if limit_usd else 0
    print(" BUDGET")
    print(f"   ${total_usd:.2f} / ${limit_usd:.2f} ({pct:.0f}%)  ·  {total_requests} / {limit_reqs} requests")
    avg_cost, remaining_execs = _compute_burn_rate()
    if avg_cost > 0:
        runway = f"~{remaining_execs:,} execs remaining" if remaining_execs is not None else "N/A"
        print(f"   Burn:   ${avg_cost:.4f}/exec avg  |  {runway} at current pace")
    print()
    icon = "●" if watcher_running else "○"
    state = "Running" if watcher_running else "Stopped"
    trigger = f"  ·  last trigger {last_trigger_file}" if last_trigger_file else ""
    print(f" WATCHER\n   {icon} {state}{trigger}")
    check_daemon_health()
    check_stall()
    if mode == "team" and teammates:
        print()
        print(" TEAMMATES")
        for tm in teammates:
            print(f"   @{tm['user']:<12} · last active {tm['last_active']}")
    print()
    print(f" {_CYAN}CAPABILITY LEDGER{_RESET}")
    try:
        _cl_conn = _get_db()
        _cl_rows = _cl_conn.execute(
            "SELECT agent, model_version, engg_domain, phase, weighted_score, sample_count "
            "FROM capability_scores ORDER BY weighted_score DESC LIMIT 3"
        ).fetchall()
        _cl_conn.close()
    except Exception:
        _cl_rows = []
    if _cl_rows:
        print(f"   {'Agent':<10} {'Model':<22} {'Domain':<8} {'Phase':<10} {'Score':>6}  N")
        for _ag, _mv, _dom, _ph, _sc, _n in _cl_rows:
            _sc_str = f"{_sc:.2f}" if _sc is not None else "  —  "
            print(f"   {_GREEN}{_ag:<10}{_RESET} {_mv:<22} {_dom:<8} {_ph:<10} {_sc_str:>6}  {_n}")
    else:
        print("   No capability data yet.")
    print(sep)
    sys.exit(1 if has_alert else 0)















# ── Wizard TUI primitives (BS-17 Plan B Tasks B-1 / B-2) ────────────────────
# Inserted before init() per plan. Pure stdlib TUI for FTUE.

_WIZ_SYNAPTIC_BLURB = (
    "In the brain, a synaptic link is the tiny gap where one neuron passes\n"
    "  its signal to the next. Alone, neurons are just cells. Connected, they\n"
    "  produce thought. Your AI tools are the same — powerful in isolation,\n"
    "  transformative when they share a signal. synlynk is the gap that makes\n"
    "  them think together."
)

_WIZ_PRODUCT_BLURB = (
    "You already have great AI tools. The problem is they don't know about\n"
    "  each other — or your project. synlynk fixes that: it injects shared\n"
    "  context before every dispatch, routes tasks to the right agent, and\n"
    "  keeps score on what's working. Your fleet, finally coordinated."
)








_STAGE_LABELS = ["STACK", "SOURCE", "COMPLEXITY", "TESTS", "GIT CHURN", "ARCHITECTURE"]
_STAGE_COLORS = [_GREEN, _CYAN, _YELLOW, _GREEN, _RED, _MAGENTA]




























_ROBOT_ASCII = "[~]"  # ASCII robot stand-in for terminal (no emoji)










        # any other key — redraw


        # invalid key — redraw




def init(force: bool = False, agents: list = None,
         org: str = None, repo: str = None, project_id: str = None,
         mode: str = "solo", dry_run: bool = False, quiet: bool = False) -> None:
    """Progressive wizard: semantic scan → agent discovery → doc bootstrap → nudge."""

    def _print_step(n: int, label: str) -> None:
        print(f"\n{_BOLD}{_CYAN}Step {n}/{_TOTAL_STEPS} — {label}{_RESET}")

    _TOTAL_STEPS = 6

    # ── Step 1: Detect existing state ──────────────────────────────────────
    _print_step(1, "Scanning repository")
    synlynk_exists = os.path.exists(".synlynk")
    if synlynk_exists and not force:
        print(f"  {_YELLOW}⚠ .synlynk/ already exists.{_RESET} "
              "Use --force to reinitialise.\n  Updating agent files only.")

    if dry_run:
        print("  DRY RUN — no files will be written\n")
        dd_preview = _docs_dir()
        for d in [dd_preview, os.path.join(dd_preview, "devlogs"), ".synlynk", LOGS_DIR, PROMPTS_DIR]:
            if not os.path.exists(d):
                print(f"  would create: {d}/")
        print("  would always overwrite (marker_style='none', regardless of --force):")
        for fpath in (".cursor/rules/synlynk.mdc", ".github/copilot-instructions.md",
                      ".windsurfrules", "AI_INSTRUCTIONS.md"):
            if os.path.exists(fpath):
                print(f"    ⚠ {fpath}  (already exists — would be overwritten unconditionally)")
            else:
                print(f"    {fpath}  (would be created)")
        return

    scan = _static_scan(".")
    print(f"  Project : {_BOLD}{scan['project_name']}{_RESET}")
    print(f"  Commits : {scan['commit_count']}")
    print(f"  Languages: {', '.join(scan['languages']) or 'unknown'}")
    if scan["recent_topics"]:
        print(f"  Recent  : {scan['recent_topics'][0]}")
    if not scan["has_structured_commits"] and scan["commit_count"] > 0:
        print(f"  {_DIM}⚠ Commit messages don't follow a structured convention — "
              "skeleton quality may be lower. Review generated docs before proceeding.{_RESET}")

    # ── Step 2: Agent discovery ─────────────────────────────────────────────
    _print_step(2, "Discovering agents")
    discovered = discover_agents()
    functional = [a for a in discovered if a["functional"]]
    non_functional = [a for a in discovered if not a["functional"]]

    if functional:
        print(f"\n  {_BOLD}{_GREEN}✨ Your Hybrid Workgroup is ready:{_RESET}")
        for ag in functional:
            roles = ", ".join(ag["roles"])
            print(f"    {_GREEN}✓ {ag['name']:10}{_RESET} {ag['version']}  "
                  f"roles: {roles}")
    else:
        print(f"  {_YELLOW}No agents detected. Install Claude, Gemini, or Codex to form your Hybrid Workgroup.{_RESET}")

    if non_functional:
        print(f"\n  {_DIM}Found but not configured (run --version failed):{_RESET}")
        for ag in non_functional:
            print(f"    {_DIM}✗ {ag['name']} — check API key / install{_RESET}")

    from synlynk.rollback import rollback_checkpoint

    config_path = os.path.join(".synlynk", "config.json")
    rates_path = os.path.join(".synlynk", "model_rates.json")
    with rollback_checkpoint("init", untracked_paths=[
        os.path.join(".git", "hooks", "pre-commit"),
        config_path,
        os.path.join(".synlynk", "instructions.json"),
        rates_path,
        "project-docs",
        "roadmap.md",
        "memory.md",
        "todo.md",
        "CLAUDE.md",
        "GEMINI.md",
        "AGENTS.md",
        "GROK.md",
        ".cursor/rules/synlynk.mdc",
        ".github/copilot-instructions.md",
        ".windsurfrules",
        "AI_INSTRUCTIONS.md",
    ]):
        # ── Step 3: Create directories + write skeleton ─────────────────────
        dd = _docs_dir()
        _print_step(3, f"Bootstrapping {dd}/")
        for d in [dd, os.path.join(dd, "devlogs"), ".synlynk",
                  LOGS_DIR, PROMPTS_DIR]:
            if not os.path.exists(d):
                os.makedirs(d)

        written = _write_informed_skeleton(scan, skip_existing=not force)
        if written:
            for p, label in written:
                print(f"  {_GREEN}✓{_RESET} {p}  {_DIM}({label}){_RESET}")
        else:
            print(f"  {_DIM}All docs already exist — skipped (use --force to overwrite){_RESET}")

        # Write agent instruction files using _write_instruction_file().
        agent_set = set(agents) if agents is not None else {a["name"] for a in functional} or {"claude", "agy", "codex", "grok"}
        templates = _build_templates(org=org, repo=repo, project_id=project_id)

        # Core trio: only write if agent was discovered as functional.
        trio_content = {
            "CLAUDE.md":   (templates.get("CLAUDE.md", ""), "html"),
            "GEMINI.md":   (templates.get("GEMINI.md", ""), "html"),
            "AGENTS.md":   (templates.get("AGENTS.md", ""), "html"),
            "GROK.md":     (templates.get("GROK.md", ""), "html"),
        }
        _agent_guards = {"CLAUDE.md": "claude", "GEMINI.md": "agy", "AGENTS.md": "codex", "GROK.md": "grok"}
        for fname, (content, mstyle) in trio_content.items():
            required = _agent_guards[fname]
            if required not in agent_set:
                continue
            _write_instruction_file(fname, required, content, mstyle)

        # Extended targets: written based on environment detection.
        # Guards are sourced from _INSTRUCTION_TARGETS[i][3] (detection_fn).
        _target_detection = {fpath: fn for fpath, _, _, fn in _INSTRUCTION_TARGETS}
        extended = [
            (".cursor/rules/synlynk.mdc",       "cursor",    "none", _build_cursor_mdc()),
            (".github/copilot-instructions.md",  "copilot",   "html", _build_copilot_instructions()),
            (".windsurfrules",                   "windsurf",  "hash", _build_windsurf_rules()),
            ("AI_INSTRUCTIONS.md",              "universal",  "html", templates.get("AI_INSTRUCTIONS.md", "")),
        ]
        for fpath, tool, mstyle, content in extended:
            if _target_detection[fpath]():
                # marker_style='none' means synlynk owns the whole file — always overwrites
                _write_instruction_file(fpath, tool, content, mstyle)

        # Write manifest of all tracked files with their SHAs.
        manifest_entries = {}
        for fpath, tool, mstyle, _ in _INSTRUCTION_TARGETS:
            if not os.path.exists(fpath):
                continue
            file_content = open(fpath).read()
            section = _extract_synlynk_section(file_content, mstyle)
            if section is not None:
                manifest_entries[fpath] = {"tool": tool, "sha": _compute_section_sha(section)}
        if manifest_entries:
            _write_instruction_manifest(manifest_entries)

        install_pre_commit_hook(repo_root=Path.cwd())

        # Write config.json if needed.
        config_json_content = templates.get("config.json", "")
        if config_json_content:
            if not os.path.exists(config_path) or force:
                with open(config_path, "w") as f:
                    f.write(config_json_content)

        if not os.path.exists(rates_path):
            from synlynk.costs import _HARDCODED_FALLBACK_RATES
            rates_seed = dict(_HARDCODED_FALLBACK_RATES)
            rates_seed["rates_updated_at"] = time.strftime("%Y-%m-%d")
            with open(rates_path, "w") as f:
                json.dump(rates_seed, f, indent=2)
            print(f"  ✓ Created {rates_path}")

    # ── Step 4: LLM enrichment offer ────────────────────────────────────────
    if not quiet:
        _print_step(4, "LLM enrichment (optional)")
        if functional:
            enricher = functional[0]
            print(f"  I found {scan['commit_count']} commits and {len(scan['recent_topics'])} "
                  f"recent topics.\n  Want me to ask {enricher['name']} to synthesise a roadmap "
                  f"from this? (costs tokens)")
            try:
                answer = input("  [y/N] ").strip().lower()
            except EOFError:
                answer = ""
            if answer == "y":
                print(f"  {_DIM}Calling {enricher['cli']} --print...{_RESET}", end=" ", flush=True)
                ok = _llm_enrich(enricher["name"], enricher["cli"], scan)
                print(f"{_GREEN}done{_RESET}" if ok else f"{_YELLOW}failed — keeping skeleton{_RESET}")
        else:
            print(f"  {_DIM}No functional agent available — skipping enrichment{_RESET}")

    # ── Step 5: Cloud directory nudge ────────────────────────────────────────
    inferred = _infer_industry()
    if quiet:
        email = ""
        industry = inferred
    else:
        _print_step(5, "Team & cloud setup (optional)")
        print("  Add a collaborator or share this workspace with your team.")
        print("  Leave blank to skip.")
        try:
            email = input("  Email or synlynk ID: ").strip()
        except EOFError:
            email = ""
        try:
            industry = input(f"  Industry vertical [{inferred}]: ").strip() or inferred
        except EOFError:
            industry = inferred
        if industry not in list(_INDUSTRY_KEYWORDS.keys()) + ["unknown"]:
            industry = "unknown"

    # ── Step 6: Finalise config ──────────────────────────────────────────────
    _print_step(6, "Finalising")
    synlynk_config_path = os.path.join("project-docs", ".synlynk_config.json")
    if not os.path.exists(synlynk_config_path) or force:
        config_data = {"mode": mode, "version": VERSION,
                       "init_timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")}
        with open(synlynk_config_path, "w") as f:
            json.dump(config_data, f, indent=2)

    _update_config({
        "workgroup_agents": [a["name"] for a in functional],
        "workgroup_invite_email": email or None,
        "industry": industry,
    })

    set_state("stopped")
    from synlynk.capability_sweep import _seed_capability_ledger_from_baseline

    _seed_capability_ledger_from_baseline(_get_db())

    print(f"\n{_BOLD}{_GREEN}✓ synlynk initialised — your Hybrid Workgroup is ready.{_RESET}")
    if functional:
        agent_names = " + ".join(a["name"] for a in functional)
        print(f"\n  {_BOLD}✨ Magic Moment 2 — dispatch agents now:{_RESET}")
        print(f"    {_CYAN}synlynk dispatch {functional[0]['name']} --task \"your task\"{_RESET}")
        if len(functional) >= 3:
            print(f"    {_CYAN}synlynk run --trio --task \"your task\"{_RESET}  "
                  f"← runs {agent_names} in parallel")
    print(f"\n  Next: {_DIM}synlynk status  ·  synlynk jobs  ·  synlynk dispatch --help{_RESET}\n")

# --- module extractions (backwards compat) ---
from synlynk.cli import main, cmd_watch  # noqa: E402
from synlynk.db import (  # noqa: E402
    _detect_hand_edit,
    _generate_costs_md,
    _generate_todo_md,
    _import_todo_to_stories,
    _migrate_db,
    _migrate_import,
    _insert_cost_row,
    _parse_costs_md,
    _parse_devlog_file,
    _parse_memory_md,
    _parse_roadmap_md,
    _parse_todo_metadata,
    cmd_devlog_append,
    cmd_cost_log,
    cmd_audit_docs,
    cmd_remediation_log,
    cmd_roadmap_add,
    cmd_memory_add,
    cmd_migrate,
    cmd_pr_check,
    cmd_score_add,
    cmd_score_attest,
    cmd_score_list,
    cmd_story_create,
    cmd_story_draft,
    cmd_story_list,
    cmd_story_ready,
)
