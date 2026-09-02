# synlynk Memory

## Strategic Research & Architecture Initiatives (opened 2026-09-02)
- **#1339 (Inter-Agent Event Relay & Messaging Bus):** Story `story-522f42cc`, linked to `goal-ef42902a`. Real-time SSE/JSON-RPC relay bus enabling cross-harness subagent messaging, mid-flight steering, and artifact exchange. [@agy]
- **#1340 (PM Autonomous Backlog Triaging & Story Formation):** Story `story-c70350f9`, linked to `goal-6733bbf1`. Operationalizes PM's durable loop to autonomously ingest GitHub issues, perform semantic goal-clustering, synthesize acceptance criteria, and promote ready stories. [@agy]
- **#1341 (Ephemeral Swarm Execution Infrastructure Drivers):** Story `story-611003e0`, linked to `goal-005ea87d`. Pluggable ephemeral cloud runner drivers (Fly.io micro-VMs, Kubernetes Job pods, Hetzner Cloud) for massive parallel swarm execution with hard budget ceilings. [@agy]
- **#1342 (Living Charter Evolution & Capability-Gated Adaptive Routing):** Story `story-3699e01b`, linked to `goal-adb60ccc`. Dynamically recalibrates dispatch routing weights from verified telemetry and automatically proposes living charter revisions when empirical competencies shift. [@agy]
- **#1343 (First-Class Model Registry & Complexity Dispatch):** Story `story-da31fea8`, linked to `goal-005ea87d`. Canonical Model & ModelFamily registry, local environment discovery, entitlement tiers, differential rate cards, and complexity-aware dispatch routing. [@agy]

## Sentinel Guard: Token Bloat & Cost Inflation Detection (decided/shipped 2026-09-02)
- **Shipped:** PR #1334 (closes #1073, story `story-a4b90a20`, relates to #1068). Adds Sentinel pattern and telemetry checks to detect anomalous token-per-file-touched ratios and cost inflation on completed and historical jobs. [@agy]
- **Root Cause Resolution (Incident `job-cf837848`):** Investigated $5.26 / 7.6M input token bloat on issue #1068. Root cause identified as `--context-mode full` monotonic context expansion across multi-turn headless stall with zero files touched.
- **Sentinel Anomaly Detection:** Implemented `check_token_bloat()` in `synlynk/sentinel.py` configured with default thresholds (`500k` tokens with 0 files touched, `500k` tokens/file ratio, `$3.00` WARN / `$5.00` CRITICAL cost inflation).
- **Integration & Scanning:** Wired into `_reconcile_jobs()` and `_reconcile_daemon_jobs()` in `synlynk/jobs.py` and `check_sentinel_patterns()` in `synlynk/sentinel.py` with telemetry fallback scanning across `.synlynk/telemetry.json`.
- **Verification:** Unit tests in `tests/test_sentinel.py`, regression test `test_investigate_rootcause_costtoken_bloat_on_jobcf837848_and_add_costratio_sentinel_guard_1073` in `tests/test_agent_cli.py`. All tests pass.
- **Blog Post:** `docs/blog/160-pr1334-token-bloat-sentinel-guard.md`.

## Fleet Parity: Add Grok to agent_slots in Default Config Templates (decided/shipped 2026-09-02)
- **Shipped:** PR #1327 (closes #863, story `story-1744cccb`). Adds `grok` to default `agent_slots` in `load_config()` and verifies clean dispatch slot resolution and diagnostic profile checks. [@agy]
- **Core 4 Fleet Parity:** `agent_slots` defaults in `synlynk/__init__.py` now explicitly include `{"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"}`, aligning runtime fallback behavior with `instructions.py` generated templates.
- **Diagnostics & Slot Resolution:** Ensures `.agents/` profile validation (`_hc_agent_profiles`) in `synlynk doctor` and CLI slot resolutions recognize Grok consistently across initialized and uninitialized environments.
- **Verification:** Unit test `test_config_add_grok_to_agent_slots_in_synlynk_and_default_config_templates` in `tests/test_agent_cli.py`, updated `test_load_config_has_new_defaults` in `tests/test_synlynk.py`. All tests pass.
- **Blog Post:** `docs/blog/156-pr1327-agent-slots-grok.md`.

## Research: Multi-Agent Swarms & Fleet Orchestration Engine (opened 2026-09-02)
- **Filed:** Issue #1326 (story `story-95238497`, linked to `goal-005ea87d`). Explores an accelerated multi-agent swarm/fleet engine across all 5 harnesses (Claude, Codex, Agy, Grok, and Local). [@agy]
- **Lifecycle & Deployment Matrix:** Evaluates initialization, tracking, messaging, and termination across home (interactive CLI/TUI) and away (headless) modes, abstracting harness-specific delegation models.
- **Ephemeral Scaling:** Explores dynamic provisioning of lightweight subagent workers on cheap VPS micro-instances (Fly.io, Hetzner) and Kubernetes Job pods with SSE telemetry streaming.
- **Local Harness Evolution:** Assesses Aider's limitations for swarm fan-out and evaluates `synlynk-local-runtime` (native async agent daemon) and Google Antigravity `LiteRTAgentConfig` on-device runners as alternatives.

## Fix YAML Frontmatter in Blog Post 103 (decided/shipped 2026-09-02)
- **Shipped:** PR #1322 (closes #941). Fixes invalid YAML frontmatter in `docs/blog/103-pr778-scope-violation-enforcement.md`. [@agy]
- **Root Cause Resolution:** Post 103 contained `merged: status open`, which violated YAML syntax and caused Eleventy website builds (`npm run build`) to crash with a `bad indentation of a mapping entry` parse error.
- **Merge Date Correction:** Updated `merged:` to `2026-08-08` matching the actual merge date of PR #778.
- **Verification:** `npm run build` in `website/` generates all static HTML pages cleanly. Full test suite (506 tests) passes.
- **Blog Post:** `docs/blog/154-pr1322-fix-blog-post-103-frontmatter.md`.

## Repair Stale & Missing SOP Sections during synlynk roles --fix (decided/shipped 2026-09-01)
- **Shipped:** PR #1321 (closes #1231, relates to #718, #1229). Ensures `synlynk roles --fix` repairs missing and stale SOP sections across all configured agent directive files. [@agy]
- **Root Cause Resolution:** `synlynk roles --fix` previously only checked whether a harness fence existed in each directive file, writing a minimal `## Your Role` fence if missing. It never called `_repair_sops_only()`, meaning newly-added SOP sections (e.g. `## Herdr Workspace Protocol`) and stale SOP sections (e.g. `## PR Review Discipline`) were not repaired or refreshed without explicitly discovering and running `synlynk sync --repair-sops --confirm`.
- **Automatic SOP Repair:** `cmd_roles(fix=True)` now invokes `_repair_sops_only(cfg=cfg, dry_run=False)`, and `_repair_config_agents(cfg)` now includes all directive-backed agents in `roles` alongside `workgroup_agents`.
- **Verification:** Unit tests added in `tests/test_roles.py`. All 18 roles tests, 4 quota/SOP tests, and 506 suite tests pass clean.
- **Blog Post:** `docs/blog/153-pr1321-roles-fix-repairs-sops.md`.

## Tighten _task_requires_gh_write() Auto-Detection Heuristic (decided/shipped 2026-09-01)
- **Shipped:** PR #1320 (closes #1246, relates to #659, #1110, #1200). Eliminates false-positive GitHub write auto-detection on incidental prompt prose and plan filenames. [@agy]
- **Root Cause Resolution:** `_task_requires_gh_write()` previously ran unanchored `_GH_WRITE_ACTION_RE` and `_GH_TARGET_RE` substring searches across prompts. File paths containing `review` (e.g. `2026-08-20-doctor-pr-review-cycles-check.md`), tracking references (e.g. `gh#1202`), and flags (`--requires-gh-write`) triggered false positives on pure code authorship tasks, failing dispatches with role-resolution errors.
- **Grammatical Co-Occurrence:** Replaced independent regexes with `_GH_CLI_WRITE_RE` and `_GH_ACTION_TARGET_RE`, requiring explicit CLI write commands (`gh (pr|issue|release) (create|review|comment|close|merge|edit|reopen|delete)`) or direct action-target grammatical pairing (`review PR #...`, `close issues #...`, `merge PR ... via`, `comment on issue #...`, `create a pull request`).
- **Verification:** Unit tests added in `tests/test_dispatch.py` covering positive and negative prompt variations. All 140 dispatch tests, 7 task inference tests, and 506 suite tests pass clean.
- **Blog Post:** `docs/blog/152-pr1320-dispatch-gh-write-false-positives.md`.

## Decouple README Sync Validator Unit Tests from Live Repo Root (decided/shipped 2026-09-01)
- **Shipped:** PR #1319 (closes #1270, relates to #1242, PR #1269). Decouples README consistency unit tests from live filesystem mutations. [@agy]
- **Root Cause Resolution:** `test_docs_keep_readme_synchronized_during_named_releases_real_readme_patterns` in `tests/test_agent_cli.py` previously executed `validate_readme_for_release()` against the live repository root `repo_root` and asserted hardcoded test counts (e.g. `2346`). This caused spurious test failures whenever `README.md` was updated.
- **Synthetic Fixture Isolation:** Refactored the test to construct a synthetic README fixture via pytest's `tmp_path` fixture and `_docs_keep_readme_synchronized_readme()`, validating version checks, test discrepancy detection, prose tolerance, and relative GitHub route handling in complete isolation.
- **Verification:** Unit test passes cleanly in isolation and with full suite (506 tests).
- **Blog Post:** `docs/blog/151-pr1319-readme-sync-test-synthetic-fixture.md`.

## Grant Administration:Write Permission to Merge Roles in GitHub App Manifests (decided/shipped 2026-09-01)
- **Shipped:** PR #1303 (closes #1295, relates to #423, #1124). Dynamically requests `administration: write` in GitHub App manifests for roles holding merge authority. [@agy]
- **Branch Protection & Merge Authority:** Branch protection on `main` requires 1 approving review. Dispatched reviewers share one repo-owner identity and cannot self-approve, relying on the sanctioned COMMENT-review checklist fallback. Merging via `gh pr merge --admin` previously failed because the `qa` GitHub App manifest lacked `administration: write`.
- **Dynamic Manifest Scoping:** In `synlynk/team.py::_build_app_manifest_url()`, synlynk now inspects `merge_authority.can_merge` in `.synlynk/policy.json` (defaulting to `["qa"]`). If the role being initialized holds merge authority, `administration: write` is automatically requested in `default_permissions`.
- **Verification:** Covered by `test_build_app_manifest_url_adds_administration_only_for_merge_roles` in `tests/test_team.py`. All 13 team/identity tests and 506 tests in `tests/test_synlynk.py` pass.
- **Blog Post:** `docs/blog/150-pr1303-qa-app-administration-permission.md`.

## Hardening: Prohibit Direct todo.md Hand-Edits Across Harness Instruction Templates (decided/shipped 2026-09-01)
- **Shipped:** PR #1318 (closes #1317, relates to #1220, PR #1314). Hardens harness instruction templates against direct `todo.md` edits. [@agy]
- **Root Cause Resolution:** Legacy instruction templates in `synlynk/instructions.py` and repository directive files (`GEMINI.md`, `CLAUDE.md`, `GROK.md`) previously told models to edit `[ ] → [x]` in `todo.md`. This contradicted the authoritative role of `state.db` and triggered doctor drift warnings (`_hc_todo_drift`).
- **Template Hardening:** Updated `_session_protocol`, `_build_cursor_mdc()`, `_build_copilot_instructions()`, and `_build_windsurf_rules()` in `synlynk/instructions.py` to prohibit direct `todo.md` edits and direct agents to use `synlynk story done <id>` (or `synlynk story create/update`) and `synlynk checkpoint`.
- **Verification:** Unit test `test_instruction_templates_prohibit_direct_todo_edits()` in `tests/test_instructions.py` asserts that all templates prohibit hand-edits and reference `state.db` / `synlynk story done` / `synlynk checkpoint`. All 506 tests in `tests/test_synlynk.py` pass.
- **Blog Post:** `docs/blog/144-pr1318-harden-harness-instructions-todo-state-db.md`.
- **Shipped:** PR #1310 (closes #573, relates to #426, #332). Resolves Stitch MCP configuration and invocation gaps on Agy. [@agy]
- **Configuration vs. Extension Mismatch:** Agy (Google Antigravity CLI) does not read Gemini CLI extensions (`~/.gemini/extensions/Stitch/`). Agy requires MCP servers configured in `~/.gemini/config/mcp_config.json`.
- **Tool Calling Convention:** Agy invokes MCP tools through `call_mcp_tool(server="stitch", tool="<tool_name>", arguments={...})` rather than Claude Code's `mcp__stitch__*` naming convention.
- **Diagnostics & Auto-Remediation:** Added `_run_tc8()` (TC-8 Stitch MCP preflight) and `_build_agy_stitch_fix_plan()` in `synlynk/doctor.py` enabling one-command remediation via `synlynk doctor --fix agy`.
- **Preflight & Prompt Adaptation:** In `synlynk/dispatch.py`, added `--requires stitch` / `--requires mcp` preflight gate, and injected `## Stitch MCP Tool Usage Note` prompting Agy to invoke `call_mcp_tool`.
- **Blog Post:** `docs/blog/143-pr1310-agy-stitch-mcp-integration.md`.

## Fleet Parity: Instruction File Preflight and Closed-Loop Receipt Verification (decided/shipped 2026-08-30)
- **Shipped:** PR #1309 (closes #347, relates to #343, #344, #345, #720). Enforces preflight instruction file presence and closed-loop execution receipt verification. [@agy]
- **Instruction Version Extraction:** In `synlynk/instructions.py`, added `extract_instruction_version()` and `get_instruction_file_for_agent()` supporting both `synlynk:start` and `synlynk:harness` markers.
- **Preflight Gate:** In `synlynk/dispatch.py:_preflight_dispatch()`, asserts that the target core instruction file exists in initialized workspaces before dispatching (fails closed with `INSTRUCTION_FILE_MISSING` unless forced).
- **Closed-Loop Receipt Protocol:** In `synlynk/dispatch.py:_format_prompt_for_agent()`, injects `SYNLYNK_INSTRUCTION_VERSION` directive without disclosing the expected token.
- **Telemetry & Verification:** In `synlynk/jobs.py`, added `_check_instruction_receipt()` to verify `ok`, `mismatch`, `none`, or `absent`, recording `job["instruction_receipt"]` and emitting advisory sentinel warnings on convention drift.
- **Blog Post:** `docs/blog/142-pr1309-instruction-file-preflight-and-receipt-verification.md`.

## Fleet Parity: Grok --cwd and Codex -C Working Directory Protection (decided/shipped 2026-08-30)
- **Shipped:** PR #1308 (closes #342, relates to commit `8c1e124`). Enforces working directory root isolation across Grok and Codex dispatches. [@agy]
- **Grok Structural & Defense-in-Depth:** In `synlynk/dispatch.py:dispatch_agent()`, dynamically appends `["--cwd", worktree_path]` to Grok CLI flags upon worktree creation, and injects a `## Working Directory` reminder header in `_format_prompt_for_agent()`.
- **Codex Working Directory Root:** In `synlynk/dispatch.py:dispatch_agent()`, dynamically appends `["-C", worktree_path]` to Codex CLI flags upon worktree creation.
- **Verification:** Covered by unit tests `test_format_prompt_for_grok_includes_working_directory`, `test_grok_dispatch_includes_cwd_flag`, and `test_codex_dispatch_includes_c_flag` in `tests/test_synlynk.py`. All 499 tests in `tests/test_synlynk.py` pass cleanly.
- **Blog Post:** `docs/blog/141-pr1308-grok-codex-cwd-protection.md`.

## Claude Baseline Roles Aligned with PM/Deploy SOP (decided/shipped 2026-08-30)
- **Shipped:** PR #1288 (closes #1284, relates to #1140, #423). Aligns Anthropic Claude's baseline programmatic roles with governance SOP. [@agy]
- **Role Alignment:** In `synlynk/_constants.py`, updated `HARNESS_CAPABILITY_BASELINES["claude"]["roles"]` from `["architect", "builder"]` to `["architect", "pm"]`, eliminating capability routing drift while preserving `can_gh_write: True` for PM, deploy, and PR review tasks.
- **Verification:** Implemented by Claude (`job-56f6ecec`, commit `cada628`), covered by `test_claude_harness_alignment_update_baseline`, verified across all matrix runners (Python 3.8, 3.10, 3.12, `qa-gate`), and merged to `main`.
- **Blog Post:** `docs/blog/138-pr1288-claude-harness-alignment.md`.

## Agy Headless Parity: Timeout, Plan Mode, & Prompt Cache Telemetry (decided/shipped 2026-08-30)
- **Shipped:** PR #1286 (closes #1283, relates to #750, #162, #437, #1106). Establishes headless execution parity for Google Antigravity (`agy`). [@agy]
- **Eliminate 5-Minute Headless Timeout:** Added `--print-timeout` to `HARNESS_CAPABILITY_BASELINES["agy"]["dispatch_flags"]["valid_flags"]` in `synlynk/_constants.py` and dynamically injects `["--print-timeout", "30m0s"]` on all headless Agy dispatches in `synlynk/dispatch.py:dispatch_agent()`, eliminating the 5-minute timeout boundary (#750 / #162).
- **Read-Only Plan Mode:** Replaced `PermissionEnforcementError` on `read:*` in `synlynk/dispatch.py:_permissions_to_flags()` with native `["--mode", "plan"]`, allowing Agy to safely execute read-only audits and code reviews.
- **Capture Gemini Prompt Cache Telemetry:** In `synlynk/costs.py:_extract_agy_structured()`, parse `cache_read_tokens = int(usage.get("cache_read_tokens", 0))` instead of hardcoding `0`, capturing millions of cached tokens and eliminating billing distortion.
- **Verification:** Unit tests added in `tests/test_dispatch.py`, `tests/test_agent_cli.py`, `tests/test_constants.py`, `tests/test_cost_ledger.py`, and `tests/test_costs.py`. All 731 tests passed across all matrix runners (Python 3.8, 3.10, 3.12, `qa-gate`), and merged to `main`.
- **Blog Post:** `docs/blog/137-pr1286-agy-headless-parity.md`.

## Grok Headless Cancellation Resolved via --always-approve (decided/shipped 2026-08-30)
- **Shipped:** PR #1279 (closes #1277, relates to #714, #880, #1038, #1166). Permanently resolves Grok's recurring headless execution cancellation (`stopReason: "cancelled"`, `PermissionCancelled`). [@agy]
- **Root Cause:** In headless execution, passing `--permission-mode dontAsk` triggered Grok's internal shell AST parser (`bash_command_splitting.rs`) and safety risk classifier (`exec_risk.rs`) on compound commands (e.g. `pytest ...; echo "FILTER_EXIT=$?"`). Because `dontAsk` suppresses interactive prompting, the resolver immediately returned `decision: "cancelled"`, aborting the turn.
- **Fix:** In `synlynk/dispatch.py:_grok_permission_flags()`, whenever `run:shell` or `run:tests` is granted, dispatch emits `["--always-approve"]`. In `synlynk/_constants.py`, added `--permission-mode` to valid flags and made `--always-approve` required on Grok dispatch.
- **Verification:** Implemented by Grok via `synlynk dispatch` (`job-4ba2fb42`, commit `41c8070`), verified across all matrix runners (Python 3.8, 3.10, 3.12, `qa-gate`), and merged to `main`.
- **Blog Post:** `docs/blog/136-pr1279-grok-headless-permission-mode.md`.

## Codex Full Harness Parity Across Review and GH-Write Tasks (decided/shipped 2026-08-30)
- **Shipped:** PR #1275 (closes #1274, relates to #1271, #865, #426, #569). Permanently eliminates the legacy 4-layer lockout that auto-rerouted Codex GitHub writes to Claude, establishing OpenAI Codex as a first-class peer for reviews, code inspection, and GitHub-write tasks. [@agy]
- **Empirical Proof:** In job `job-836e13a4`, Codex executed inside its Seatbelt sandbox with `-c sandbox_workspace_write.network_access=true` to query PR #1272, post an audit comment, and close the PR via `gh pr close` under its role GitHub App identity (`synlynk-synlynk-qa`), verifying zero egress blocks or token failures.
- **Core Baselines & Policy:** Set `HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"] = True` and added `"verifier"` to baseline roles in `synlynk/_constants.py`. Updated `.synlynk/policy.json` and `synlynk/policy.py` so `review` and `gh_write` route to Codex with Claude and Agy as fallbacks.
- **Templates & Directives:** Updated `synlynk/probe.py` so initialized instruction tables dynamically route GitHub writes to Codex by default, and updated `docs/harness-capability-baseline.md` to classify Codex as **Reliable**.
- **Blog Post:** `docs/blog/135-pr1275-codex-full-harness-parity.md`.

## Direct Codex GitHub-Write Network Access via Config Override (decided/shipped 2026-08-29)
- **Shipped:** PR #1271 (closes #1268, relates to #865). Replaces the proposed brokered file relay with a native configuration override (`-c sandbox_workspace_write.network_access=true`) injected into Codex dispatch when `requires_gh_write` is active. [@agy]
- **Attribution Finding:** PR #1258 was created by synlynk's host wrapper (`_maybe_open_worktree_pr`), not by Codex inside the sandbox. Codex never attempted network calls.
- **Empirical Sandbox Probe:** Live test confirmed that `codex exec -s workspace-write` blocks DNS egress by default (`Could not resolve host: api.github.com`), but `-c sandbox_workspace_write.network_access=true` cleanly enables outbound HTTPS (`HTTP/2 200`).
- **Implementation:** `synlynk/dispatch.py:dispatch_agent()` now appends `_CODEX_NETWORK_PERMISSION` (`"run:install"`) to `effective_grants` for Codex when `requires_gh_write=True`, causing `_permissions_to_flags()` to emit the network access override flag.
- **Security & Isolation:** Default non-gh-write dispatches remain strictly isolated without network access. Environment variables continue to be scrubbed via `_ENV_ALLOWLIST_BASE`, and only temporary, role-scoped GitHub App tokens are injected into isolated directories.
- **Spec & Plan:** `docs/superpowers/specs/2026-08-29-codex-direct-gh-write-network-access-design.md`, `docs/superpowers/plans/2026-08-29-codex-direct-gh-write-network-access.md`.
- **Blog Post:** `docs/blog/134-pr1271-codex-direct-gh-write-network-access.md`.

## QA Completion Tracker + Merge-Restricted-Classes Gate Mode (decided/shipped 2026-08-22)
- **Shipped:** PR #1100 (completion tracker — `spec_verified` GOVERNS event, Vizor panel distinguishing merged vs verified PRs) and PR #1101 (`qa_gate_mode=merge-restricted-classes` — qa merges docs-only PRs directly, first concrete answer to #1079 §5's deferred "what PR class is safe to merge unattended"). [@nikhilsoman via Claude]
- **Both plans** executed via subagent-driven-development, dispatched to Codex; reviewed directly by Claude (spec-compliance + code quality, no sub-delegated review) against plan text; merged via #423 COMMENT-review-with-checklist fallback.
- **Process gap found:** stacked `synlynk dispatch --base` opened a separate PR per task against `main` instead of the parent branch — 2 four-task plans produced 8+ PRs and 16 worktrees needing manual cleanup. Recorded in global memory as `feedback_dispatch_stacking_pr_proliferation`; worth a synlynk issue to make `--base` target the parent branch as PR base.
- **Still deferred (unchanged from #123):** applying branch protection for real, extending `merge-restricted-classes` to harder PR classes (dependency bumps, CI config).
- **Blog post:** `docs/blog/124-pr1100-1101-qa-completion-tracker-and-merge-restricted-classes.md` (PR #1102, docs-only follow-up since both PRs merged before the post was drafted).
- **Design-doc PRs landed 2026-08-22:** #1091 (qa-completion-tracker design spec + implementation plan) and #1092 (qa-merge-restricted-classes design spec + implementation plan) merged — both were spec/plan docs written before their implementations shipped in #1100/#1101; committed after the fact for the historical Design → Plan → Build record. Also landed this session: PR #1104, committing the previously-untracked `docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md` (the original block-only qa-gate plan) — noted in its body that the plan's literal text describes a standalone `qa-gate.yml` workflow that was later superseded by a `needs:test` job in `test.yml` (see commit `7177913`).
- **Full autonomy roadmap (2026-08-22):** presented a phased plan (Phase 0: close synlynk's own remaining gaps — dispatch-stacking fix, merge-restricted-classes extension; Phase 1: resolve #423 GitHub identity limitation as the critical-path blocker, apply branch protection for real; Phase 2: port qa-gate pattern to rxcc, more conservative safe-merge class given DPDP/ABDM; Phase 3: port to Vdowrx/cc-videoreframing, gated on fixing open issue #99 (fabricated PTS correctness bug) and rebuilding its corrupted `project-docs/roadmap.md`; Phase 4: unified cross-repo Vizor + adopt rxcc's "three decisions only humans make" framing as the north star). Not yet written to a spec doc — informal for now, pending user decision on whether to formalize via brainstorming.
- **#423 identity mechanism CONFIRMED LIVE end-to-end (2026-08-22):** dispatched Agy with `--requires-gh-write --grant run:shell` against PR #1105 in synlynk itself; the resulting review comment posted under `synlynk-synlynk-dev`, a distinct GitHub App bot login, not `nikhilsoman`. This is the first real (non-simulated) proof that role-scoped identity separation works, on both synlynk and Vdowrx (8/8 role Apps provisioned + token-minting verified on both repos beforehand). Two blockers found and one fixed along the way:
  - **Fixed:** #1106/PR #1107 — `_run_tc7()` in `synlynk/doctor.py` was checking `settings.get("allowRules", [])`, a top-level key that doesn't exist in the real `~/.gemini/antigravity-cli/settings.json` schema; the real allow-rules live at `settings["permissions"]["allow"]` (same path `_build_agy_fix_plan()` already used correctly). TC-7 was silently rejecting correctly-configured operator settings. Confirmed shipped and re-tested live against the actual local settings.json.
  - **Still open, not yet filed as an issue:** dispatching `--requires-gh-write --task-type review` to Agy without an explicit `--grant run:shell` fails closed with `PermissionEnforcementError` — the `review` task-type's default permission profile (`_ROLE_PERMISSION_DEFAULTS["review"] = ["read:*"]`) has no shell/gh capability, so a gh-write review dispatch needs the grant spelled out by the caller every time. Worth deciding whether `--requires-gh-write` should auto-imply `run:shell` in the permission resolution rather than requiring both flags in tandem.
  - **Still confirmed broken, not yet filed:** Grok's dispatch sandbox denies `bash` entirely for this harness/config, contradicting CLAUDE.md's "route gh-write to Grok by default" (#426) rule as the actual current default. Agy (once TC-7 fixed + `run:shell` granted) is the only harness that has actually completed a live gh-write in this environment; Codex remains blocked by network egress sandboxing to `api.github.com`.

## Per-Agent Instruction Fixes (post-BS-14 backlog — 2026-06-29)

Changes to agent directive files pending outcome of BS-14 brainstorm. Do not apply until BS-14 spec is locked.

| Agent | File | Fix needed | Incident |
|---|---|---|---|
| Agy | `GEMINI.md` | Scope Discipline section — session-end ceremony must not fire on single-prompt tasks; "note in project-docs" ≠ story create; tests only before code commits | TC-2: 30+ tool calls, 472 tests, raw SQLite for a 2-file doc task (2026-06-29) |
| Agy | `GEMINI.md` | Headless dispatch contract — stdout must flush without PTY; verify `agy` supports unbuffered/pipe mode | TC-1: LIVE-1 6h silent hang, zero log output (2026-06-28) |
| Grok | `.agents/grok.json` | Remove `--always-approve` from dispatch_flags — Claude Code flag, not a Grok flag; causes startup failure | TC-1: LIVE-1 network + flag error, job stuck open 6h (2026-06-28) |
| Grok | `.agents/grok.json` | Grok CLI network dependency — `cli-chat-proxy.grok.com` must be reachable; add preflight connectivity check | TC-1: LIVE-1 `reqwest error stream` on API endpoint (2026-06-28) |
| All | `synlynk doctor` | Add flag validation check: for each agent, verify dispatch_flags are accepted by the installed binary version | FIX-4 from #81 |
| All | sentinel | Add `STALL_NO_OUTPUT` pattern: running job + zero log bytes after 30min → alert | FIX-3 from #81 |

**Scope discipline fix already shipped:** `GEMINI.md` updated 2026-06-29 with Scope Discipline section. All other items blocked on BS-14.

## synlynk as a Native Harness (decided 2026-06-29 — workgroup consensus: Claude + AGY + Codex + Nikhil)
- **Shift to native execution:** synlynk will transition from wrapping vendor CLIs (like `claude`, `codex`, `grok`) to hosting its own agent runtime/harness. [@agy]
- **API integration:** The new harness will directly integrate with LLM provider APIs (Vertex/Gemini, Anthropic Messages API, OpenAI-compatible APIs) to control System Instructions and tool-call loops directly.
- **Granular sandboxing:** Replaces loose guest CLI safety flags with native path-specific read/write locks (configured in `config.json`) and interactive shell/PTY command approval gates.
- **MCP Host support:** Rather than bloat core, an MCP (Model Context Protocol) Host will be built into the harness to connect to external search, browser, or database servers.
- **Dual-mode transition:** Standard CLI wrapper modes are retained as a fallback. Native execution will roll out under `synlynk-agent` in v0.10.x/v1.0 as an opt-in, eventually replacing CLI wrappers as the primary execution model.
- **Spec:** [synlynk-as-a-harness.md](file:///Users/nikhilsoman/dev/synlynk/docs/strategy/synlynk-as-a-harness.md)

## Live Job Observatory Brainstorm (decided 2026-06-28)
- **Need:** a read-only, htop/mtop-style live board for every running job across all repos, with near real-time refresh (~10s), repo/stage grouping, and cost/token/request visibility. [@nikhilsoman]
- **Surface split:** ship both terminal and web versions, but keep one shared monitoring model underneath so the board state stays consistent across surfaces.
- **Foundational fields:** originating agent, executing agent, and input context size are now first-class observability signals, not optional metadata.
- **Interaction limit:** no inline action CTAs beyond opening the relevant terminal or web link from the top-level board. This is monitoring only, not control.
- **Spec:** `docs/superpowers/specs/2026-06-28-bs13-live-job-observatory-design.md`
- **Next:** terminal-first implementation plan; use the observability view as the seed for `synlynk viz` later.

## Roadmap Realignment (decided 2026-06-21 — workgroup consensus: Claude + AGY + Codex + Nikhil)
- **Tiers are permanently off.** "Team edition" = networked collaboration features, not billing tiers. [@nikhilsoman]
- **Agent archetypes:** Four types — Maintainers (schedule-triggered, self-healing) · Communicators (release-triggered, outward publishing) · Orchestrators (story/signal-triggered, work management) · SMEs (domain-tag/file-path-triggered, reactive expertise). Same archetype deployed at different levels (workgroup → team → enterprise → domain) behaves differently by scope.
- **Context portability principle:** The `.agents/<name>.json` config + deployment level define what an agent monitors and who it communicates with. Archetype is the pattern; context gives it purpose.
- **Kernel fix is highest priority [Codex/AGY]:** `generate_context(scope=task)` silently falls back to full context (bin/synlynk.py ~line 2955, deferred to v1.3.0 — PULLED to v0.9.0). Every agent dispatch is degraded without scoped context.
- **Package split before agent series [Codex]:** bin/synlynk.py at ~4000 lines is a merge conflict timebomb. Split into `synlynk/` package in v0.9.0 before more agents land.
- **Capability ledger integrity [AGY]:** Ed25519 sig column exists but signing not wired into `_write_capability_rating`. Wire in v0.9.0. `quality_auto` formula is gameable — anti-gaming baseline in v0.9.0, hardened in v1.0.0.
- **Real moat [AGY]:** Not "shared capability ledger" (anyone can clone a SQLite table). The moat is the accumulated routing graph — which agent/model/version succeeded on which (engg × org × industry × phase) cell, decayed over time. Only defensible if signed, game-resistant, and large.
- **Relay design:** Stateless WSS relay on port 443. Three modes: LAN (mDNS auto-discovery) → Cloudflare Tunnel (no open ports, firewall-transparent) → VPS (always-on). Revolving host: any active member can be host, relay bootstraps from any online member. Loud handover protocol (signed broadcast, 10-min grace, degraded-mode warning). Daemon on localhost:27471 only.
- **Relay ownership model (decided 2026-06-21):** Community-first hybrid. Community relay (relay.synlynk.com, Fly.io hosted by synlynk) is the DEFAULT for all users — `synlynk relay join`. Self-provisioned VPS is gated behind `--enterprise` flag or exception token (for regulated industries / air-gapped). LAN/CF Tunnel stays as fallback/prototype. `synlynk relay join` points at relay.synlynk.com even in v0.9.3 (graceful "launching with v1.0" message until server is live). Fly.io is the recommended VPS for enterprise self-host path. Northflank for v1.1+ community server.
- **Consensus decision framework:** `synlynk decide "<topic>" --panel <agents>` — first-class command. Produces signed Decision record in `project-docs/decisions/`. A Decision is a peer to Epic in the PM hierarchy.
- **VPS deep-dive (resolved 2026-06-21):** Fly.io ($3–5/mo) for community relay + enterprise self-host. Hetzner (€4.51/mo) as budget enterprise option for teams with ops expertise. E2B/Modal ruled out (ephemeral sandboxes, not relay). Koyeb ruled out (acquired by Mistral). Bedrock AgentCore / Azure Foundry Hosted Agents are AI-native but designed for agent session management, not relay hosting — overkill. No purpose-built agentic relay platform exists yet.
- **Spec:** `docs/superpowers/specs/2026-06-21-synlynk-roadmap-realignment-design.md`

## Positioning (decided 2026-06-06)
- **Name:** synlynk — "The OS for multi-agent development." [@nikhilsoman]
- **Framing:** Not a context injector, skill package, or SaaS dashboard. An OS layer beneath every
  AI tool, giving agents persistent memory, structured coordination, and a stable shared substrate.
- **Tier model retired:** Solo/Team/Enterprise tiers replaced by the OS layer model — one product,
  increasing capability as you move up the stack.

## Workspace & Multi-Repo (decided 2026-06-07)
- **Workspace = unit of organization above a repo.** One product = one workspace, N repos. Solo dev = one workspace, one repo — structurally identical, invisible to user. [@nikhilsoman]
- **Storage:** `~/.synlynk/workspaces/<name>/state.db` — one DB per workspace. Repos are a dimension (`repos` table + `repo_id` FK on stories/events/costs), not separate DBs.
- **Identity: machine-level.** `~/.synlynk/identity.key` — one Ed25519 keypair per person per machine. Shared across all workspaces. Replaces per-project keypair. Closes Gap 10 entirely.
- **Init: repo-first, auto-promoted.** `synlynk init` creates workspace transparently. `synlynk workspace join <name>` adds a second repo. Auto-detects via GitHub org match.
- **Cross-repo Epics: first-class.** One Epic spans N repos. Stories have `repo_id` FK. Architect context = full epic cross-repo view. Builder/Verifier = workspace shared + repo slice.
- **Team sync: event-log via shared git repo (not export/import).** Daemon pushes new events to per-member branch every 5 min. Others pull and apply. Max drift ≈ 5 min. Conflict-free (events are append-only). Becomes NATS at Tokq Alpha — same event format, different transport.
- **Simulated team:** switch `git config user.name` — events record different git_user, all signed by same machine key. Full cost/activity attribution per simulated member. No extra infra.
- **Spec:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md`

## Agent Identity, Dispatch & Entitlements (decided 2026-06-07)
- **Identity is two-layered:** Local Identity (Ed25519 keypair, agent_uuid — cryptographic anchor, machine-scoped) + Role (primary entitlement unit) + Agent Profile (fitness function: CLI × model × environment × competency_scores). [@nikhilsoman]
- **Roles:** Architect (docs only, no src writes), Builder (implements, can branch/PR), Verifier (tests/audits). Custom roles via `synlynk role add`.
- **Dispatch modes:** A=daemon (persistent, primary), B=self-chain (agent completion re-evaluates), C=one-shot `synlynk dispatch` (universal fallback — no daemon needed), D=agent-native scheduling (`use_native_scheduling` flag).
- **Dispatch address:** `inbox` table in state.db (v0.5–v0.7), NATS subject (v1.0+). Logical address: `synlynk://<project_id>/roles/<role>/inbox`.
- **Human-agent bridge:** Email (send-only SMTP, v0.7.0). Approval via `synlynk story approve <id>` CLI. Gmail reply parsing deferred to v0.8.0.
- **Entitlements are two layers:** Authorization (gate before dispatch) + Sandboxing (constraints while running). Merge to main is always approval-required — no threshold can override.
- **Ed25519 identity pulled forward:** From v0.9.0 to v0.5.0. Every dispatch_log row and completed event is signed. Audit trail is non-repudiable.
- **Cron design:** One `synlynk dispatch` cron, not per-agent. Per-role frequency via multiple `schedules` entries with different `filter` values.
- **Spec:** `docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md`

## Dispatch Reliability Fixes (decided 2026-07-11/12) [@nikhilsoman]
- **#161 fixed (PR #163):** Codex worktree git-ref writes were blocked — `dispatch_agent()` now resolves `git rev-parse --path-format=absolute --git-common-dir` and appends `--add-dir <path>` to Codex's sandbox flags.
- **#160 fixed (PR #164):** `synlynk dispatch --help`'s agent list was a hand-maintained string that drifted (missing `grok`). Now derived from `sorted(AGENT_CAPABILITY_BASELINES)` with `choices=` added to the argparse arg, so it can't drift again and rejects unknown agents at the CLI layer.
- **#162 fixed (PR #165):** Added `HARNESS_TIMEOUT_PATTERNS` (mirrors `QUOTA_PATTERNS`) — dead jobs whose log matches `"timeout waiting for response"` get a `HARNESS_INTERNAL_TIMEOUT` sentinel alert instead of looking like a generic task failure. Also generalized `_check_job_stall()` from "log is empty" (`os.path.getsize(log_file) > 0` early-exit, unreachable for almost every real job) to "log stopped advancing" (mtime staleness vs. `stall_timeout_minutes`, no new config knob).
- **Live confirmation of the bug #162 fixes:** while dispatching #162's own fix to Codex, the job died at exit -1 after ~500s — right after finishing implementation but before committing — the exact harness-internal-timeout pattern the fix targets. Work survived in the worktree; verified diff against plan and committed manually rather than losing it. First-hand evidence the failure mode isn't agy-specific.
- **Established verification pattern** for dispatch → PR: `git diff main <dispatch-branch> --stat` + targeted diffs to confirm the diff matches the plan exactly; cross-check CI failures against `main`'s own CI history before merging (5 known baseline failures: `test_detect_install_type_pip/script/unknown`, `test_run_tc4_skips_flag_only_command_templates`, `test_upgrade_auto_installs_new_version` — env-specific, not regressions).
- Specs: `docs/superpowers/specs/2026-07-11-codex-worktree-git-refs-design.md`, `docs/superpowers/specs/2026-07-11-dispatch-help-agent-list-design.md`, `docs/superpowers/specs/2026-07-11-harness-timeout-detection-design.md`.

## Brainstorm Session Map (updated 2026-06-27)
- **BS-1** ✅ Done — Initial architecture / OS framing
- **BS-2** ✅ Done — Onboarding + Mode Taxonomy
- **BS-3** ~~queued~~ → **retired** (2026-06-27): AB-11/12/13 (conflict taxonomy + instruction coexistence) folded into BS-7. No standalone BS-3 session.
- **BS-4** — Command Audit + Autopilot Trigger Map. Queued pre-GA, not this weekend.
- **BS-5** — Website redesign (story-048f5fe5). Saturday PM this weekend.
- **BS-6** — OKF alignment + `synlynk viz` three-view visualization (story-f5513a93). Sunday AM.
- **BS-7** — Skill Pack Interop + Benchmarks + **AB-11 conflict taxonomy** (story-bs7-interop). Sunday AM/PM. Benchmark execution week of 2026-06-30.
- **BS-8** ✅ Spec done (2026-06-27) — Harness Capability Awareness + Loop-Native Dispatch. `synlynk probe` + `dispatch_loop()` + stuck consult. Three stories: story-bs8-probe, story-bs8-loop, story-bs8-consult. Target v0.10.1. Spec: `docs/superpowers/specs/2026-06-27-bs8-harness-capability-awareness-loop-dispatch-design.md`
- **BS-13** — Live Job Observatory / watch overlay for cross-repo running jobs. Near-real-time refresh, repo/stage grouping, cost/token/request telemetry, terminal + web surfaces, read-only board with open-link affordances only.
- **BYOA** — Parked post-dev-preview (Ollama, OpenCode/OpenRouter, DeepSeek).

## State DB & Agentic PM (decided 2026-06-07)
- **Core invariant:** State never branches. All worktrees share one `~/.synlynk/projects/<key>/state.db` where `<key>` = 8-char MD5 of `git rev-parse --git-common-dir/..` (repo root). [@nikhilsoman] Implemented v0.4.1.
- **project-docs/ retired:** Markdown files become gitignored. state.db is primary. Context bridge unchanged — agents still see `.synlynk/context.md`.
- **Agentic PM hierarchy:** Project → Arc → Phase → Epic → Story → Event. Replaces time/capacity anchoring with dependency/verification anchoring.
  - **Arc** — strategic direction (pivot/archive/merge). The layer missing from every PM tool.
  - **Phase** — structural backbone (capability gate, rarely changes; was: roadmap row).
  - **Epic** — one implementation plan (`writing-plans` output = one Epic + N Stories).
  - **Story** — one agent task unit with `done_criteria` and `depends_on` graph.
  - **Event** — append-only universal log (replaces devlogs; devlog is a filtered view).
- **Token budget replaces story points:** `estimated_tokens` on stories. Routing: capability → quota headroom → cost. `agent_quotas` table tracks per-agent limits.
- **Costs fully attributed:** `costs` table gains `story_id / epic_id / phase_id` FKs — can now answer "what did Phase v0.5.0 cost?"
- **Platform sync:** `external_refs` table maps Arc/Phase/Epic/Story → GitHub/Jira/Linear. state.db is canonical; platforms are views.
- **GitHub Projects V2 — agentic-first decision (2026-06-27):** [@nikhilsoman] The board is a human-readable projection of state.db, not the source of truth. Agents never write to the board directly. synlynk owns the push via `synlynk sync --board github` (post-v0.10.0). The current `--project-id` flag on `synlynk init` stamps a placeholder into agent instruction files for agents to manually invoke GraphQL if needed — that is the *only* live artifact; no bidirectional sync exists yet. Do not expand GitHub Projects V2 surface area before `external_refs` is implemented.
- **Migration:** `synlynk migrate` (ships v0.5.0) — parses project-docs/, populates state.db, untracks with `git rm --cached`.
- **Next:** Agent identity, addressability, scheduling, entitlements — separate brainstorm.
- **Spec:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`

## Architecture — OS Layer Model (decided 2026-06-06)
Bottom to top: Kernel → Filesystem → IPC → Scheduler → Shell → Ecosystem Interface → Applications.
- **Kernel + Filesystem:** SHIPPED (v0.3.0) — exec, telemetry, flatline, budget, project-docs/
- **IPC:** v0.4.0 — conventions.md, Trio pipeline, constraint propagation
- **Scheduler:** v0.5.0 — capability engine, SQLite-backed routing, state.db for all project state
- **Shell:** v0.7.0 — daemon, dispatch, async pipeline
- **Ecosystem Interface:** v0.8.0 — Open Context Protocol, MCP server
- **Applications:** GStack, SuperPowers, HermesAgent, OpenClaw, NmoClaw run ON synlynk, not beside it

## Architecture — Infrastructure Arc (decided 2026-06-06)
Flat files (v0.3) → SQLite WAL (v0.5–v0.6) → HTTP Context Server on localhost (v0.7) →
NATS leaf node schema defined (v1.0) → NATS leaf→hub live (Tokq Alpha). [@nikhilsoman]
- SQLite via stdlib `sqlite3`. HTTP via stdlib `socketserver`. NATS via inlined pure-Python client.
- Single-file constraint (`bin/synlynk.py`, zero pip deps) holds through v1.0.
- Exception: Tokq Alpha introduces `cryptography` package as `pip install synlynk[tokq]`. Local-only
  use remains zero-dependency forever.

## Tokq Convergence (decided 2026-06-06)
- **Tokq** (Jan 2026) = distributed agent memory marketplace (same author). Cloud/network layer.
- **synlynk** (May 2026) = local OS client. Built as the stepping stone toward Tokq.
- **Relationship:** synlynk is the local OS. Tokq is the cloud layer above it. Both survive
  independently. Cloud is additive, never required.
- **Bridge sequence:** v0.9 generates Ed25519 identity → v1.0 freezes memory unit schema + NATS leaf
  schema → Tokq Alpha connects, adds ZK encryption + sync + marketplace.
- **Distribution insight:** Tokq's original distribution problem (no client, no install base) is
  solved by synlynk. Every `synlynk init` = a Tokq onboarding event.

## Tokq Bridge Decisions (decided 2026-06-06)

**Agent Identity (FR-1):**
- `synlynk identity init` — generates UUID + Ed25519 keypair via `ssh-keygen` subprocess.
- Writes `.synlynk/identity.json` (UUID + public key fingerprint) + `.synlynk/identity.key` (chmod 600).
- Ships in v0.9.0. Auto-called from `synlynk init`.

**Memory Unit Schema (FR-2/3):**
- One Tokq memory unit per `project-docs/` file (not per paragraph).
- `session_id` = git remote URL (or SHA of repo path if no remote).
- `client_id` = `project_id` from `.synlynk/config.json`.
- `memory_id` = `sha256(session_id + filename + version_counter)` — deterministic, idempotent sync.
- Schema frozen at v1.0, published as `docs/tokq-memory-unit-schema.md`.

**Zero-Knowledge Encryption (FR-4):**
- Client-side AES-256-GCM. Key derived from Ed25519 private key via HKDF-SHA256.
- Tokq stores only ciphertext. Cannot decrypt. Ships in Tokq Alpha.

**Ledger Boundary (FR-6):**
- `costs.md` = local ops ledger (exec, Trio pipeline). Permanent. Never replaced.
- Gas tank = Tokq cloud ops ledger (memory CRUD, marketplace). Separate. Additive.
- `synlynk tokq balance` shows gas tank. `costs.md` shows local ops. Both coexist forever.

**Conventions → Marketplace (FR-5/7):**
- `synlynk publish conventions` — packages `conventions.md` as a Tokq collection with pricing.
- `synlynk subscribe <id>` — subscribes, gas tank auto-deducts. 70/30 revenue split.
- Ships in Tokq Alpha.

## Open Context Protocol (decided 2026-06-06)
Two commands are the entire integration surface:
- `synlynk context --for <tool>` — generate tool-scoped context, write to `.synlynk/context-<tool>.md`
- `synlynk checkpoint --from <tool>` — tool writes back what it learned to project state
Any tool integrates in < 10 lines. No SDK. No fee. Published spec at v0.8.
HTTP Context Server (v0.7, `localhost:27471`) is the underlying transport.
[@nikhilsoman]

## Instruction Reach (shipped v0.4.1, 2026-06-17)
- **7 tracked instruction targets:** CLAUDE.md (html), GEMINI.md (html/agy), AGENTS.md (html/codex), `.cursor/rules/synlynk.mdc` (none — synlynk owns whole file), `.github/copilot-instructions.md` (html), `.windsurfrules` (hash), `AI_INSTRUCTIONS.md` (html/universal).
- **`_INSTRUCTION_TARGETS`** is the single source of truth: `(path, tool, marker_style, detection_fn)`. Guards for conditional targets (`cursor`, `copilot`) are derived from `detection_fn` — no duplicate dict anywhere.
- **Three marker styles:** `html` = `<!-- synlynk:start version="..." tool="..." -->` / `<!-- synlynk:end -->`; `hash` = `# synlynk:start` / `# synlynk:end`; `none` = synlynk owns whole file.
- **SHA manifest** at `.synlynk/instructions.json` — tracks section SHA (not whole-file SHA) per target. User edits outside markers never trigger false drift events.
- **Drift detection:** `_check_instruction_drift()` hooked into `exec_command()`. Fires `INSTRUCTION_DRIFT` sentinel once per change (deduplicates by updating manifest SHA immediately after firing). Reset via `synlynk instructions update` or `synlynk instructions ack`.
- **AGY replaces Gemini CLI:** `"gemini"` removed from baselines, discovery, probe patterns. Trio is now claude/agy/codex. GEMINI.md template is AGY-only.

## Trio Protocol Core Decisions (decided 2026-06-01, ships v0.4.0)
- Phase artifacts: `task-packet.md` (Architect) → `build-notes.md` (Build) → `verify-report.md` (Verify)
- Roles emergent from usage: empirical scoring, no hardcoded vendor mapping
- Cold-start: round-robin until 3 samples per (agent, phase, domain)
- Score decay: recency-weighted, half-life = 10 tasks (configurable)
- Phase failure: auto-retry once with next-best agent, then halt
- Full spec: `docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md`

## Load-Bearing Schema Contracts
- **costs.md:** 6 columns — `| Date | User | Requests | Tokens (In/Out) | Estimated Cost (USD) | Summary |`
  Cost at `parts[5]`. Parser in `parse_costs_md()`. Do not add columns without updating the parser.
- **exec exit code:** `exec_command()` returns child exit code as int. `main()` calls `sys.exit()`
  with it. Never swallow non-zero. Flatline triggers after 3 consecutive non-zero same-command exits.
- **Attribution:** All `memory.md` and `devlogs/` entries in team mode MUST have `[@username]`.
- **conftest.py:** Fixtures must mirror the real costs.md 6-column schema at all times. `isolated_db` autouse fixture redirects `synlynk.DB_PATH` to a per-test temp path — every test gets its own `state.db`, no cross-test DB pollution.

## Harness vs. Workspace Agent Separation (decided 2026-08-30, ships PR #1306)
- Strict ontological boundary: Workspace Agents (`pm`, `architect`, `tpm`, `dev`, `designer`, `qa`, `marketing`, `synlynk-bot`) are durable role identities, charter holders, and lifecycle owners; Harnesses (`claude`, `codex`, `grok`, `agy`, `local`) are execution backends and compute resources.
- `synlynk dispatch --force-harness`: Added as canonical flag to pin a harness backend; `--force-agent` is preserved as a deprecated alias emitting a non-breaking warning.
- `synlynk jobs handoff --to-harness`: Added alongside `--to` and `--to-agent`.
- Config discovery: `.harnesses/` is checked first with transparent fallback to `.agents/`.
- Database lock safety: `synlynk/db.py` guards `_normalize_org_domain_drift` updates with row-existence checks, eliminating same-thread SQLite deadlocks during nested dispatches.
- Full design spec: `docs/superpowers/specs/2026-08-30-harness-agent-separation-design.md`.
[@agy]

## Superseded Decisions
- ~~Tier model (Solo/Team/Enterprise)~~ → retired 2026-06-06. Replaced by OS layer model.
- ~~"Context Switchboard" framing~~ → retired 2026-06-06. Replaced by "OS for multi-agent development."
- ~~Lite → Full progression~~ → retired. Replaced by v0.4→v1.0 staircase + Tokq cloud layer.
- ~~Blog Post Protocol paused (2026-07-12)~~ → resolved, hold lifted (2026-08-13). Originally: no new `docs/blog/` posts or `website/src/blog/posts/` syncs until an IP assessment was done on the flagged Four-POV IP candidates (sentinel detection, permission translation, handoff protocol). In practice, `docs/blog/` posts continued every session since with no formal decision doc ever lifting the hold (through post #114 on 2026-08-12, #115 on 2026-08-13) — treating that informal continuation as the operative decision rather than leaving a stale blocking note future sessions keep silently ignoring. `website/src/blog/posts/` site-sync scope (capped at post #33 per the original note) and item 3 of `docs/superpowers/specs/2026-07-12-release-announcement-agenda.md` (website messaging refresh) were not re-examined here — verify current site-deploy scope before assuming either is still capped if they become relevant again.

## Active Holds
(none currently — see Superseded Decisions for the lifted Blog Post Protocol hold)

## CLI Version Drift Warning (2026-09-02)

When invoked inside a synlynk checkout, the CLI compares its running package
version with the enclosing repository's `VERSION` file. If the installed version
is older, it emits a non-blocking stderr warning with a forced pipx reinstall
command. The check is local and best-effort, so malformed metadata and unrelated
repositories remain silent. See `docs/superpowers/specs/2026-09-02-cli-version-drift-warning-design.md`.
[@codex]

## Review Dispatch Read-Only Scope (#937, 2026-09-02)

Review task permission resolution now strips all `write:*` grants after
combining role defaults, explicit grants, and revokes, so caller overrides
cannot make a review job writable. Codex review jobs retain GitHub network
access when required but use the read-only workspace sandbox. Regression tests
cover explicit write grants and review command flags; see spec
`docs/superpowers/specs/2026-09-02-review-dispatch-readonly-scope-design.md`.
[@codex]

## Manifest Callback Server Concurrency Fix (2026-09-02, gh:#906)

`synlynk/team.py::_run_manifest_callback_server` (the loopback server used
during GitHub App Manifest role provisioning) captured its OAuth code via a
`threading.Event` + list, which silently dropped a second concurrent
`/callback` request's code (duplicated tab, retried redirect) since the
check-then-set guard only ever kept the first code. Fixed by switching to
`queue.Queue()` (unconditional `put`, never drops) and
`http.server.ThreadingHTTPServer` (concurrent requests get independent
handler threads instead of serializing behind one accept loop). External
contract (`port, wait_for_code, shutdown`) unchanged. See
`docs/superpowers/specs/2026-09-02-manifest-callback-concurrency-design.md`.
[@claude]

## First-Class Model Registry (#1339, 2026-09-02)

Phase 1/2 adds a canonical model-family/model registry backed by SQLite, with
explicit context geometry, rate cards, and entitlement tiers. `synlynk models
list|show|discover` expose built-ins and safe environment discovery for Claude,
Codex, Agy, Grok, Ollama, and oMLX. Doctor verifies catalog availability.
[@codex]

## Boolean Dispatch Flag Deduplication (#1327, 2026-09-02)

Dispatch now removes repeated occurrences of known boolean CLI flags after
baseline, override, permission, and harness-specific flags are combined. This
prevents Grok's required and permission-derived `--always-approve` from being
passed twice while preserving repeatable option/value pairs. See
`docs/superpowers/specs/2026-09-02-grok-always-approve-dedup-design.md`.
[@codex]

## Subscription Cost Ledger (#787, 2026-09-02)

`harness_billing` is the preferred configuration for payment mode, monthly
subscription fee, projected tokens, extra usage, and overage caps. The cost
ledger preserves API-equivalent value separately from realized cash outlay;
`synlynk cost true-up --month YYYY-MM` records the end-of-cycle variance as a
`true_up_reconciliation` entry. Local `zero_cost` harnesses always record
`actual_usd=0.0`.
[@codex]

## Cadence-Breaker Resilience Engine (#1346, 2026-09-02)

Added bounded recovery for autonomous dispatch: `synlynk/rebase.py` resolves
supported markdown append conflicts, sentinel can terminate jobs at 500k
zero-file tokens or $5, dispatch can fail over after an immediate harness
startup failure, and daemon reconciliation marks dead-PID jobs
`killed_zombie` while removing leaked worktrees. Unsupported conflicts and
uncertain process ownership remain fail-closed.
[@codex]

## Conventions
- Attribution: `[@username]` on all team-mode entries.
- Session protocol: read last 3 devlog entries at session start. Surface any open threads.
- AI maintains these docs without user prompting at natural pause points.
- PR Reviews: When reviewing a pull request, only comment with observations and suggestions. Do not make code fixes on the branch or commit changes directly; the original author must implement corrections to learn and retain ownership.
