# Tasks (generated - source of truth is state.db)
# Edit via: synlynk story create/update | Do NOT hand-edit this file

- [ ] BS-6: brainstorm — repo/workspace visualization: product view · logical view · infra view [visualization] <!-- id:story-f5513a93 -->
- [ ] BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform] <!-- id:story-bs7-interop -->
- [ ] BS-8: synlynk probe — ambient harness capability drift detection + publish pipeline [tooling] <!-- id:story-bs8-probe -->
- [ ] BS-8: dispatch_loop() — composite termination + /goal objective injection + job chain tracking [dispatch] <!-- id:story-bs8-loop -->
- [ ] BS-8: stuck detection + one-shot consult from capability matrix + Expert Consult injection [dispatch] <!-- id:story-bs8-consult -->
- [ ] BS-8: goal hierarchy (meta + milestone + story) + synlynk goals CLI + three-layer context injection [dispatch] <!-- id:story-bs8-meta-goals -->
- [ ] BS-8: synlynk story split — observatory-driven auto-decomposition for context-window-crossing stories [dispatch] <!-- id:story-bs8-split -->
- [ ] BS-12: brainstorm — Agent Autonomy Bridge: permission grants, harness config, handoff protocol, + synlynk TUI/chatbot at init/doctor time [platform] <!-- id:story-6f97c5a0 -->
- [ ] BS-9: brainstorm — Trio Orchestration Demo: State Continuity + Flatline + Parallel Dispatch showcase (scripted, narrative-first) <!-- id:story-ab6a0586 -->
- [ ] BS-10: brainstorm — PulseScape: end-to-end glassmorphic agent dashboard (SSE relay + Ed25519 consensus panel, 6-session build) <!-- id:story-e3a3170a -->
- [ ] BS-11: brainstorm — MCP Registry contribution: Project Context + Todo MCP Server for modelcontextprotocol/servers <!-- id:story-fda756fd -->
- [ ] flatline: standalone Python CLI circuit-breaker — hash stdout, kill after 3 identical failures, pip-installable public utility <!-- id:story-b4a90209 -->
- [ ] git-drift: standalone pip package — instruction drift auditor, pre-commit hook, manifest schema, git-drift install <!-- id:story-cb2c1d93 -->
- [ ] git-connectome: standalone language-agnostic codebase mapper → self-contained interactive HTML (synlynk viz public face) <!-- id:story-3652dafe -->
- [ ] BS-15: brainstorm — synlynk as a standalone harness [platform] <!-- id:story-2ebedf92 -->
- [ ] BS-12e: Agent SOP Codification — missing workflow discipline SOPs in directive files: brainstorm-first, PR-by-non-author, design-spec-plan sequence, capability-allocation, cost-gate, repo-hygiene [platform] <!-- id:story-d59e1b3b -->
- [ ] Release announcement docs pass: README, website, quickstart PDFs, blog series — agenda in docs/superpowers/specs/2026-07-12-release-announcement-agenda.md [docs] <!-- id:story-b4b1167e -->
- [ ] Cut v0.12.0 Named Release: VERSION bump, CHANGELOG consolidation (Job Lifecycle epic + Capability Matrix Hardening/Fleet Scheduler + Dispatch Reliability trio + Vizor Architect Map v2), gh release create [DEPL] <!-- id:story-54d83487 -->
- [ ] BUG: Codex dispatch harness dies silently after clean completion — observed job-e7102d86 (#134 fix) and job-4ca68424 (viz.py py3.8 fix): Codex log shows full clean response + explicit verification confirmation, no error text anywhere, but the dispatch wrapper reports status FAILED (exit -1), tokens 0/0, files 0 touched — synlynk's own post-response processing (token extraction, git diff/files-touched, commit) never runs. NOT caught by #162/PR #165's HARNESS_TIMEOUT_PATTERNS, which only matches the literal string "timeout waiting for response" (agy's internal-timeout text) — neither Codex log contains that phrase since Codex itself completed successfully. Root cause is in synlynk's dispatch wrapper exit/post-processing path for Codex, not the underlying agent CLI. [PROG] <!-- id:story-codex-silent-exit -->
- [ ] synlynk init/wizard config option: file bugs/stories to GitHub Issues, state.db-only, or both. Auto-detect GH remote as default signal. Persisted as issue_tracking: "github" | "state_db_only" | "both" in .synlynk/config.json. Decouples public-facing tracker layer (GitHub Issues) from the internal agentic execution substrate (state.db) — complementary, not competing. [PROG] <!-- id:story-issue-tracking-config -->
- [ ] test-check-story-id-format [PROG] <!-- id:story-7b743876 -->
- [ ] fix(dispatch): warn when --context-mode full is used on a self-contained task (PR #238) [DEPL] <!-- id:story-2c254dac -->
- [ ] fix(jobs): stall-killer checks remote branch activity before hard-failing (PR #240) [DEPL] <!-- id:story-1e05e3cf -->
- [ ] Extract build_parser() from cli.py main() for testability [PROG] <!-- id:story-e528c886 -->
- [ ] COMMAND_TAXONOMY module: schema, coverage test, full 58-command classification [PROG] <!-- id:story-43346243 -->
- [ ] Generate docs/reference/commands.md and README command section from COMMAND_TAXONOMY [PROG] <!-- id:story-126d706f -->
- [ ] Drive FTUE wizard and launch picker from COMMAND_TAXONOMY (retires #262) [PROG] <!-- id:story-0097a566 -->
- [ ] Trigger registry: tier-scoped agent-context phrases in synlynk:start/end fencing [PROG] <!-- id:story-d5341d65 -->
- [ ] Trigger registry: pre-commit hook for instructions ack on synlynk init [PROG] <!-- id:story-e5896237 -->
- [ ] Enhance dispatch/job comms: est. + actual token/$ cost, watch/viz reminder, fence or HUD presentation [PROG] <!-- id:story-615bc8f4 -->
- [ ] Update the README docs for #42 [docs] <!-- id:story-issue-42 -->
- [ ] do something freeform [backend] <!-- id:story-adhoc-99 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-07-21-gh-write-capability-routing.md exactly as specified below. This is a fresh dispatch job -- your worktree will branch from current origin/main, whi [testing] <!-- id:story-issue-500 -->
- [ ] docs: codify Grok-only gh write routing + PR review identity caveat (#423, #426) [backend] <!-- id:story-issue-432 -->
- [ ] feat: can_gh_write capability routing for dispatch_agent() [testing] <!-- id:story-issue-438 -->
- [ ] release: v0.13.0 — Discoverability & Accounting [testing] <!-- id:story-issue-442 -->
- [ ] synlynk selftest --live clobbers real repo's project-docs/todo.md and GEMINI.md [backend] <!-- id:story-issue-448 -->
- [ ] fix: Fix two bugs in synlynk selftest --live scratch-work (job-2d10274d) [backend] <!-- id:story-issue-450 -->
- [ ] Live selftest scenario coverage gap: init (against existing files), migrate, upgrade never live-tested [backend] <!-- id:story-issue-451 -->
- [ ] fix: Implement issue #451 in nikhilsoman/synlynk: add rea (job-b87c2d19) [testing] <!-- id:story-issue-452 -->
- [ ] Implement Task 1 from docs/superpowers/plans/2026-07-22-rollback-mechanism.md on branch chore/rollback-mechanism-design (issue: rollback mechanism for init/migrate/upgrade, see docs/superpowers/specs/ [testing] <!-- id:story-adhoc-1784730043 -->
- [ ] Fix a spec-compliance bug in the commit you just made on this branch (dispatch/codex/job-7175d83e), file synlynk/rollback.py.

The plan (docs/superpowers/plans/2026-07-22-rollback-mechanism.md) and sp [testing] <!-- id:story-adhoc-1784730495 -->
- [ ] Fix a spec-compliance bug in the commit you just made on this branch (dispatch/codex/job-7175d83e), file synlynk/rollback.py.

The plan (docs/superpowers/plans/2026-07-22-rollback-mechanism.md) and sp [testing] <!-- id:story-adhoc-1784730578 -->
- [ ] Your worktree is based on origin/main, which does not yet contain synlynk/rollback.py or tests/test_rollback.py — that's expected, create both files fresh with the exact content below (this is a corre [testing] <!-- id:story-adhoc-1784731005 -->
- [ ] Your worktree is a fresh checkout based on origin/main, which does NOT yet contain synlynk/rollback.py or tests/test_rollback.py from prior work on this feature. You must first CREATE both files with  [testing] <!-- id:story-adhoc-1784731827 -->
- [ ] Your worktree is based on origin/main, which does not yet contain synlynk/rollback.py or tests/test_rollback.py. These files already exist on branch chore/rollback-mechanism-design (Tasks 1-2 of docs/ [testing] <!-- id:story-adhoc-1784734841 -->
- [ ] Your worktree is based on origin/main, which does not yet contain synlynk/rollback.py or tests/test_rollback.py. These already exist on branch chore/rollback-mechanism-design (Tasks 1-3 of docs/superp [testing] <!-- id:story-adhoc-1784738780 -->
- [ ] Your worktree is based on origin/main, which does not yet contain synlynk/rollback.py — that's expected. This task fixes two real bugs discovered during code review of an already-merged rollback mecha [testing] <!-- id:story-adhoc-1784742472 -->
- [ ] Implement Task 1 of the plan below EXACTLY as specified. This is one task from a 9-task implementation plan for synlynk's dispatch tooling (docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-t [testing] <!-- id:story-adhoc-1784775794 -->
- [ ] Implement Task 2 of the plan below EXACTLY as specified. This is one task from a 9-task implementation plan for synlynk's dispatch tooling (docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-t [testing] <!-- id:story-adhoc-1784776643 -->
- [ ] Implement Tasks 3 AND 4 of the plan below EXACTLY as specified, together in one pass — they are explicitly coupled (Task 3's call-site edit references a `base` parameter that Task 4 adds to `dispatch_ [testing] <!-- id:story-adhoc-1784801848 -->
- [ ] Implement Tasks 5 AND 6 of the plan below EXACTLY as specified, together in one pass — they are explicitly coupled (Task 6 replaces/extends the `_apply_dispatch_gate` function Task 5 creates, same fun [testing] <!-- id:story-adhoc-1784804173 -->
- [ ] Implement Task 7 of docs/superpowers/plans/2026-07-23-dispatch-stacking-ground-truth-gate.md: surface base_branch/base_sha/suite_result in job summaries (synlynk jobs/synlynk logs output).

Context: T [backend] <!-- id:story-adhoc-1784810104 -->
- [ ] Implement Tasks 8 and 9 of docs/superpowers/plans/2026-07-23-dispatch-stacking-ground-truth-gate.md. These are the final two tasks of the plan. Tasks 1-7 are already merged on this branch: dispatch st [testing] <!-- id:story-adhoc-1784812732 -->
- [ ] Implement Task 5 of docs/superpowers/plans/2026-07-22-rollback-mechanism.md: wire Leg 1 (rollback_checkpoint) into init().

Read the full Task 5 section of that plan file first (search for '### Task 5 [testing] <!-- id:story-adhoc-1784862079 -->
- [ ] Implement Task 6 of docs/superpowers/plans/2026-07-22-rollback-mechanism.md: wire Leg 2 (rollback_checkpoint_upgrade) into synlynk/upgrade.py's _run_upgrade().

IMPORTANT — your dispatch worktree bran [testing] <!-- id:story-adhoc-1784863275 -->
- [ ] Implement Task 7 of docs/superpowers/plans/2026-07-22-rollback-mechanism.md: add the `synlynk rollback [--last|--op-id|--clear]` CLI command.

IMPORTANT — your dispatch worktree branched off origin/ma [testing] <!-- id:story-adhoc-1784864331 -->
- [ ] Implement Task 8 of docs/superpowers/plans/2026-07-22-rollback-mechanism.md: add `--dry-run` to `synlynk init` and `synlynk upgrade` (Approach C).

Your dispatch worktree branches off origin/main. The [testing] <!-- id:story-adhoc-1784865655 -->
- [ ] Run 'synlynk pr check 471' against https://github.com/nikhilsoman/synlynk/pull/471 (branch chore/rollback-mechanism-design, the init/migrate/upgrade rollback mechanism PR). Report the full output of t [backend] <!-- id:story-adhoc-1784885158 -->
- [ ] feat(rollback): init/migrate/upgrade rollback mechanism [testing] <!-- id:story-issue-471 -->
- [ ] [Platform:Codex] Add synlynk init --codex [security] <!-- id:story-issue-6 -->
- [ ] fix(website): bump linkify-it to 5.0.2 (CVE-2026-59887) [testing] <!-- id:story-issue-473 -->
- [ ] Fix two confirmed bugs in synlynk's dispatch/jobs pipeline. This is Python-only work in this repo (single-file-per-module CLI under synlynk/). Do NOT run pytest test-name-guessing or search for unrela [testing] <!-- id:story-adhoc-1784900675 -->
- [ ] [Platform:Codex] Document Codex CLI and Desktop baseline usage [ml] <!-- id:story-issue-7 -->
- [ ] Run the command 'synlynk pr check' (no arguments, no PR number) in this worktree. Do NOT run pytest. Do NOT search for or guess a test name. Do NOT run any other command.

First, checkout this exact c [testing] <!-- id:story-adhoc-1784901918 -->
- [ ] Create a file called REPRO_TEST.txt at the repo root containing the single line: agy-repro-ok [testing] <!-- id:story-adhoc-1784905931 -->
- [ ] Create a file called REPRO_TEST2.txt at the repo root containing the single line: agy-repro-attempt-2 [testing] <!-- id:story-adhoc-1784906083 -->
- [ ] Create a file called REPRO_TEST3.txt at the repo root containing the single line: agy-repro-attempt-3 [testing] <!-- id:story-adhoc-1784907733 -->
- [ ] Run the shell command 'git log -1 --oneline' and write its exact output to a new file called REPRO_TEST4.txt at the repo root. Do not use any file-writing tool other than by first running the command  [testing] <!-- id:story-adhoc-1784907915 -->
- [ ] Run the shell command 'git log -1 --oneline' and write its exact output to a new file called REPRO_TEST4.txt at the repo root. Do not use any file-writing tool other than by first running the command  [testing] <!-- id:story-adhoc-1784911174 -->
- [ ] Run 'synlynk pr check 479' in this worktree and report the full output verbatim. Do not modify any files. This PR is docs-only (adds docs/rca/2026-07-24-agy-jetski-headless-permission-investigation.md [docs] <!-- id:story-adhoc-1784917001 -->
- [ ] docs: RCA for agy jetski headless permission investigation [testing] <!-- id:story-issue-479 -->
- [ ] fix(website): bump brace-expansion to 1.1.16 (CVE-2026-13149) [testing] <!-- id:story-issue-476 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: '.synlynk/roles.yaml data model + gitignore fix'. Follow the plan's Task 1 section exactly (TDD, step-by-step, ex [ml] <!-- id:story-adhoc-1784952590 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'synlynk/github_app_auth.py — JWT signing + installation token minting'. Follow the plan's Task 2 section exactly [testing] <!-- id:story-adhoc-1784954833 -->
- [ ] Implement Task 3 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'synlynk identity init --role <name> provisioning flow'. Follow the plan's Task 3 section exactly, step by step ( [testing] <!-- id:story-adhoc-1784955832 -->
- [ ] docs: capture uncommitted cost entries drifting on main [testing] <!-- id:story-issue-485 -->
- [ ] Implement Task 3 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'synlynk identity init --role <name> provisioning flow'.

CRITICAL CONTEXT: your dispatch worktree was forked fro [backend] <!-- id:story-adhoc-1784957240 -->
- [ ] Add a COMMAND_TAXONOMY entry for the new 'identity list' CLI command in synlynk/taxonomy.py. Context: synlynk/cli.py already defines an 'identity list' subcommand (identity_sub.add_parser('list', ...) [testing] <!-- id:story-adhoc-1784961720 -->
- [ ] docs: approve State Engine spec, scope PR1 landing decisions [testing] <!-- id:story-issue-489 -->
- [ ] Implement Task 4 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'synlynk identity list' command. Follow the plan's Task 4 section exactly (lines 716-795), step by step, using th [ml] <!-- id:story-adhoc-1784969458 -->
- [ ] Implement Task 5 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'Inject role-scoped GH_TOKEN at dispatch time'.

CRITICAL CONTEXT: your dispatch worktree forks from origin/main, [testing] <!-- id:story-adhoc-1784971031 -->
- [ ] Implement Task 5 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'Inject role-scoped GH_TOKEN at dispatch time'.

CRITICAL CONTEXT: your dispatch worktree forks from origin/main, [testing] <!-- id:story-adhoc-1784972647 -->
- [ ] GOVERNS lifecycle checkpoint directives [testing] <!-- id:story-issue-464 -->
- [ ] docs: record GOVERNS goal-90e73dfd on lifecycle handoff [security] <!-- id:story-issue-494 -->
- [ ] File a GitHub issue for a bug in synlynk's own capability router. Repro: 'python3 -m synlynk dispatch agy --story story-issue-464 --task "..." --context-mode task' (no --force-agent) crashes with:

sq [backend] <!-- id:story-adhoc-1784973959 -->
- [ ] Fix a broken mock in tests/test_dispatch_github_identity.py on branch chore/agent-github-identity-design (this file was just added in a prior commit). The helper _dispatch_with_fake_popen mocks dispat [testing] <!-- id:story-adhoc-1784973988 -->
- [ ] Fix a broken mock in tests/test_dispatch_github_identity.py on branch chore/agent-github-identity-design.

CRITICAL CONTEXT: this file does NOT exist in your dispatch worktree because it forks from or [testing] <!-- id:story-adhoc-1784974942 -->
- [ ] Fix ONE line in tests/test_dispatch_github_identity.py on branch chore/agent-github-identity-design.

CRITICAL CONTEXT: this file does NOT exist in your dispatch worktree (forks from origin/main; file [testing] <!-- id:story-adhoc-1784975878 -->
- [ ] Implement Task 6 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'Doctor health check for un-provisioned declared roles'.

CRITICAL CONTEXT: your dispatch worktree forks from ori [testing] <!-- id:story-adhoc-1784978674 -->
- [ ] dispatch: capability router crashes with sqlite3.OperationalError: no such column: discipline [backend] <!-- id:story-issue-496 -->
- [ ] Implement Task 7 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'Hygiene hardening — permission enforcement + gitignore verification'.

CRITICAL CONTEXT: your dispatch worktree  [testing] <!-- id:story-issue-2 -->
- [ ] Implement Task 8 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'Auto-register newly provisioned roles into .synlynk/roles.yaml'.

CRITICAL CONTEXT: your dispatch worktree forks [testing] <!-- id:story-adhoc-1784980588 -->
- [ ] Implement Task 9 of docs/superpowers/plans/2026-07-24-agent-github-identity-design.md: 'Redact minted GH_TOKEN values from synlynk logs display'.

CRITICAL CONTEXT: your dispatch worktree forks from o [testing] <!-- id:story-adhoc-1784981198 -->
- [ ] Fix stale capability_scores view missing discipline column (#496) [backend] <!-- id:story-0ba62064 -->
- [ ] PR Review Discipline's non-authoring-reviewer rule is unenforceable by GitHub — all dispatched agents share the same gh identity [frontend] <!-- id:story-issue-423 -->
- [ ] chore: validate per-role GitHub identity dispatch (issue #423 Task 10 step 4) [backend] <!-- id:story-10604467 -->
- [ ] Task 10 Step 4 retry 3: dev-role identity validation [backend] <!-- id:story-cee3a4a6 -->
- [ ] docs: devlog + costs.md updates for #496 fix session [testing] <!-- id:story-issue-515 -->
- [ ] Review PR #517 (per-role GitHub App identity, #423) [backend] <!-- id:story-013958f1 -->
- [ ] chore: synlynk jobs --all shows stale FAILED/0-touched status for a job that actually completed successfully [testing] <!-- id:story-issue-202 -->
- [ ] Fix GH_TOKEN inheritance leak in requires_gh_write dispatch (PR #517 review) [backend] <!-- id:story-c8d4607e -->
- [ ] fix: stop job reconcilers from clobbering correct terminal summary with stale FAILED/-1 data (#202) [testing] <!-- id:story-issue-519 -->
- [ ] v0.11.0 (retention): synlynk launch D1+ daily brief mode — when state.db has prior job history, replace template picker opening with "welcome back" card: last job status + scan delta (coverage %, typed % vs last scan) + next recommended template; warm handoff for returning users; scan delta data sourced from .synlynk/scan-result.json diffs <!-- id:story-ca84004b -->
- [ ] v0.11.0 (retention): BS-20 scope add — scan delta surfacing in synlynk launch + synlynk jobs --summary: "coverage +8% since last scan", typed%, git churn trend; signals already captured in .synlynk/scan-result.json, needs UX layer to surface them; ties into D1 daily brief and D7 week-in-review narrative <!-- id:story-4b288e24 -->
- [ ] v1.0.0 (multi-project): synlynk workspace add <path> FTUE — 3-screen guided TUI (repo detected → scan summary → added to workspace); synlynk launch in multi-repo mode gains repo selector Screen 0; cross-repo task prioritization by scan signal urgency (gap_count + churn density) not repo order; design decision: how launch surfaces tasks across repos <!-- id:story-9e2296f3 -->
- [ ] BUG: Codex dispatch harness dies silently after clean completion — observed job-e7102d86 (#134 fix) and job-4ca68424 (viz.py py3.8 fix): Codex log shows full clean response + explicit verification confirmation, no error text anywhere, but the dispatch wrapper reports status FAILED (exit -1), tokens 0/0, files 0 touched — synlynk's own post-response processing (token extraction, git diff/files-touched, commit) never runs; NOT caught by #162/PR #165's HARNESS_TIMEOUT_PATTERNS, which only matches "timeout waiting for response" (agy's internal-timeout text) — root cause is in synlynk's dispatch wrapper exit/post-processing path for Codex, not the underlying agent CLI <!-- id:story-42373d94 -->
- [ ] synlynk init/wizard config option: file bugs/stories to GitHub Issues, state.db-only, or both — auto-detect GH remote as default signal; persisted as `issue_tracking: "github" | "state_db_only" | "both"` in `.synlynk/config.json`; decouples public-facing tracker layer (GitHub Issues) from internal agentic execution substrate (state.db) <!-- id:story-74193239 -->
- [ ] docs: devlog + costs.md backfill for PR #515 review flow and #202 fix session [testing] <!-- id:story-issue-520 -->
- [ ] fix: synlynk jobs --all permanently shows unknown for jobs that lost the race to consume the shared .exit marker file [testing] <!-- id:story-issue-526 -->
- [ ] fix: Fix #526: synlynk jobs --all permanently shows 'unkn (job-faf6428c) [testing] <!-- id:story-issue-528 -->
- [ ] fix: .gitignore excludes .worktrees/ but the repo's actual worktree dir is worktrees/ (no dot) [security] <!-- id:story-issue-530 -->
- [ ] Fix cross-process token redaction no-op in synlynk logs (#524) [backend] <!-- id:story-8fe00292 -->
- [ ] Wire HEALTH_CHECKS into real synlynk doctor CLI, run before TC1-5 wizard (#525) [backend] <!-- id:story-abbccee7 -->
- [ ] docs: devlog + costs.md backfill for PR #528 verification and #530 fix session [backend] <!-- id:story-issue-538 -->
- [ ] Story one <!-- id:story-2c9de0a0 -->
- [ ] Story two <!-- id:story-33a23622 -->
- [ ] State Engine PR1: DB-canonicalize roadmap/memory/costs + migrate self [testing] <!-- id:story-issue-542 -->
- [ ] fix: restore project-docs content lost in PR #542 merge (LIVE-3) [testing] <!-- id:story-issue-548 -->
- [ ] docs: blog posts for PR #542 and PR #549 (LIVE-3) [testing] <!-- id:story-issue-552 -->
- [ ] fix: Your worktree is based on origin/main, which does no (job-76234e3d) [testing] <!-- id:story-issue-457 -->
- [ ] fix: Fix a real safety bug in the migrate rollback mechan (job-c332a4fb) [backend] <!-- id:story-issue-529 -->
- [ ] fix: Fix a real bug found during manual end-to-end valida (job-ba87125c) [frontend] <!-- id:story-issue-509 -->
- [ ] fix: Implement Task 7 of docs/superpowers/plans/2026-07-2 (job-7d157983) [testing] <!-- id:story-issue-502 -->
- [ ] docs: reapply PR #528/#530 devlog + backfill PR #533 cost rows [testing] <!-- id:story-issue-564 -->
- [ ] docs: PR #521/#529 review (superseded pair, failing rollback test) [backend] <!-- id:story-issue-560 -->
- [ ] _repair_sops_only() injects synlynk's own hardcoded dev-repo conventions into other repos' CLAUDE.md, contradicting their real setup [backend] <!-- id:story-issue-553 -->
- [ ] fix: Fix GitHub issue #553 (https://github.com/nikhilsoma (job-ce5189bb) [testing] <!-- id:story-issue-567 -->
- [ ] Agent capability routing: Agy and Codex cannot perform GitHub write actions (PR review/merge) in headless dispatch [backend] <!-- id:story-issue-426 -->
- [ ] regression of #554: --repair-sops silently reverts Capability-Based Task Allocation to generic defaults when .synlynk/config.json has no 'roles' key [frontend] <!-- id:story-issue-571 -->
- [ ] synlynk doctor: TC-1/TC-2/TC-3/TC-5 silently no-op for most agents due to AGENT_CAPABILITY_BASELINES schema inconsistency [testing] <!-- id:story-issue-339 -->
- [ ] sync --repair-sops only fills missing SOP headers, never refreshes stale existing ones [testing] <!-- id:story-issue-583 -->
- [ ] echo test [testing] <!-- id:story-adhoc-1785374144 -->
- [ ] fix(probe): preserve blank-line spacing when refreshing stale SOP sections [testing] <!-- id:story-issue-591 -->
- [ ] docs: regenerate harness SOP capability-allocation blocks [frontend] <!-- id:story-issue-592 -->
- [ ] docs: blog posts for PRs #584, #588, #589, #591, #592 [testing] <!-- id:story-issue-594 -->
- [ ] Harden preflight dispatch check: agent auth/login and headless permission-allow gaps go undetected [backend] <!-- id:story-issue-332 -->
- [ ] fix(dispatch): harden reporting and preflight gates (#332, #419, #461) [testing] <!-- id:story-issue-604 -->
- [ ] Implement Task 1 from the plan at docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md (read that file's "### Task 1" section for full context if useful, but the com [backend] <!-- id:story-adhoc-1785497931 -->
- [ ] Implement Task 2 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below (no need to read the plan file, everything needed is here). Task  [testing] <!-- id:story-adhoc-1785499080 -->
- [ ] Implement Task 3 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below (no need to read the plan file). Task 1 (state.db schema) is alre [backend] <!-- id:story-adhoc-1785499103 -->
- [ ] Implement Task 7 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below. Task 1 (state.db schema including capability_incidents table) is [backend] <!-- id:story-adhoc-1785499119 -->
- [ ] Bug fix in your own recent commit b094dfd ("feat: generalize selftest dispatch/exec scenarios to loop over all discovered harnesses") on this branch.

In synlynk/selftest.py's `_exec_scenario` functio [testing] <!-- id:story-adhoc-1785501907 -->
- [ ] fix: Fix issue #616: _maybe_open_worktree_pr (synlynk/job (job-3b69ce6b) [backend] <!-- id:story-issue-617 -->
- [ ] Implement Task 5 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below. Tasks 1, 3, and 4 are already merged into your base branch — rea [backend] <!-- id:story-adhoc-1785502539 -->
- [ ] Implement Task 6 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below. Tasks 1, 3, 4, 5 are already merged into your base branch — read [testing] <!-- id:story-adhoc-1785503578 -->
- [ ] Fix a real regression your own last commit (54b64a6, "test: reduce mocking depth in join/decide selftest scenarios to catch real regressions") introduced in this branch.

CONTEXT: You just changed `_s [testing] <!-- id:story-adhoc-1785505415 -->
- [ ] Implement Task 8 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below. Tasks 1, 2, and 7 are already merged into your base branch — rea [testing] <!-- id:story-adhoc-1785512783 -->
- [ ] Implement Task 9 from docs/superpowers/plans/2026-07-31-harness-capability-drift-regression-classification.md. Full instructions below. Tasks 1, 2, and 7 are already merged into your base branch — rea [backend] <!-- id:story-adhoc-1785512964 -->
- [ ] Fix two verified bugs found during final code review of the just-merged harness-capability-drift-regression-classification stack. Both are small, targeted fixes in already-implemented code.

BUG 1 — c [testing] <!-- id:story-adhoc-1785519808 -->
- [ ] fix: Run the 'Harness compatibility & capability' GOVERNS (job-a7eb31f5) [backend] <!-- id:story-issue-587 -->
- [ ] Agent parity gap: role-based permission/grants system is a no-op for Agy, Grok, and Local dispatches [testing] <!-- id:story-issue-338 -->
- [ ] Dispatched agent subprocess inherits full parent environment — no secret redaction anywhere [backend] <!-- id:story-issue-348 -->
- [ ] fix: fleet-parity security cluster — fail-closed permissions + env allowlist (#348, #338) [backend] <!-- id:story-issue-641 -->
- [ ] Execute Task Group 6 exactly as written in docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md (the section titled 'Task Group 6: Doctor — Aider-presence check (post-ship gap fix, added 2026-0 [testing] <!-- id:story-adhoc-1785657397 -->
- [ ] fix: TASK: Fix a real cost-capture gap in synlynk's dispa (job-658ee066) [backend] <!-- id:story-issue-646 -->
- [ ] cmd_status crashes with 'unable to open database file' in dispatched-agent sandboxes; config falls back to null org/repo [backend] <!-- id:story-issue-648 -->
- [ ] fix(local-agent): doctor now checks for aider on PATH [testing] <!-- id:story-issue-657 -->
- [ ] feat: fleet operability truth gate (Core 4 + matrix + fail-closed doctor) [backend] <!-- id:story-issue-661 -->
- [ ] Fix a port default mismatch for the 'local' (oMLX/aider) agent. The user's actual oMLX install runs on port 8000, but two source-code literals still hardcode the old wrong default of 8080. .agents/loc [testing] <!-- id:story-adhoc-1785670162 -->
- [ ] Fix a port default mismatch for the 'local' (oMLX/aider) agent. The user's actual oMLX install runs on port 8000, but two source-code literals still hardcode the old wrong default of 8080. .agents/loc [testing] <!-- id:story-adhoc-1785670178 -->
- [ ] fix(local-agent): correct oMLX port from 8080 to 8000 [testing] <!-- id:story-issue-665 -->
- [ ] Implement Task Group 7 from docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md (in this worktree, branch fix/omlx-api-key). Read that section in full before starting — it has complete code fo [backend] <!-- id:story-adhoc-1785689272 -->
- [ ] fix(local-agent): oMLX API-key auth + roster model-ID drift [backend] <!-- id:story-issue-672 -->
- [ ] local-seed-00 [docs] <!-- id:local-seed-00 -->
- [ ] local-seed-01 [testing] <!-- id:local-seed-01 -->
- [ ] Scan this repo and give me a summary [backend] <!-- id:story-adhoc-1785696073 -->
- [ ] Scan this repo and give me a summary [backend] <!-- id:story-adhoc-1785696084 -->
- [ ] Implement Task Group 8 from docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md (in this worktree, branch fix/omlx-litellm-provider-prefix). Read that section in full before starting — it has  [backend] <!-- id:story-adhoc-1785696514 -->
- [ ] Continuing your prior work on branch fix/omlx-litellm-provider-prefix (commit fb2de26, "fix(local-agent): prefix aider --model with openai/ for litellm routing"). Full project test suite run afterward [backend] <!-- id:story-adhoc-1785696930 -->
- [ ] fix(local-agent): litellm needs openai/ provider prefix for real dispatch [backend] <!-- id:story-issue-678 -->
- [ ] Scan this repo and give me a summary [backend] <!-- id:story-adhoc-1785723730 -->
- [ ] State database outside workspace fails under sandboxed harness execution [backend] <!-- id:story-issue-681 -->
- [ ] Execute Task Group 9 in docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md exactly as written (branch fix/omlx-aider-edit-format, already checked out). It is a config-only fix: change .agents [testing] <!-- id:story-adhoc-1785773391 -->
- [ ] fix(local-agent): diff edit-format for pinned Ornith model [testing] <!-- id:story-issue-690 -->
- [ ] Implement Task A1 from docs/superpowers/plans/2026-08-03-local-agent-parity-config.md exactly: create scripts/local_agent_ab_test.py with _build_temp_config and tests/test_local_agent_ab_test.py with  [testing] <!-- id:story-adhoc-1785795618 -->
- [ ] Implement Task A2 from docs/superpowers/plans/2026-08-03-local-agent-parity-config.md exactly: append _load_config, _write_config, _git_diff_stat, _build_result_row to scripts/local_agent_ab_test.py,  [testing] <!-- id:story-adhoc-1785796754 -->
- [ ] Implement Task A3 from docs/superpowers/plans/2026-08-03-local-agent-parity-config.md exactly: append _default_dispatch_runner and run_ab_case to scripts/local_agent_ab_test.py, and append TestRunAbCa [testing] <!-- id:story-adhoc-1785796961 -->
- [ ] Implement Task A4 from docs/superpowers/plans/2026-08-03-local-agent-parity-config.md exactly: append append_result and main() to scripts/local_agent_ab_test.py, and append TestAppendResult to tests/t [testing] <!-- id:story-adhoc-1785802113 -->
- [ ] Implement Task B1 from docs/superpowers/plans/2026-08-03-local-agent-parity-config.md exactly: modify _local_dispatch_model_flags() in synlynk/local_agent.py to append Starter-tier guardrail flags (-- [testing] <!-- id:story-adhoc-1785803912 -->
- [ ] chore: local-agent parity config — A/B harness + Starter-tier guardrails [testing] <!-- id:story-issue-697 -->
- [ ] Add a docstring to the add() function in project-docs/decisions/ab_test_fixtures/sample_module.py. [testing] <!-- id:story-adhoc-1785808481 -->
- [ ] Add a docstring to the add() function in project-docs/decisions/ab_test_fixtures/sample_module.py. [testing] <!-- id:story-adhoc-1785808510 -->
- [ ] Add a docstring to the add() function in project-docs/decisions/ab_test_fixtures/sample_module.py. [testing] <!-- id:story-adhoc-1785808536 -->
- [ ] Add a docstring to the add() function in project-docs/decisions/ab_test_fixtures/sample_module.py. [testing] <!-- id:story-adhoc-1785811043 -->
- [ ] In project-docs/decisions/ab_test_fixtures/sample_module.py, rename the function old_name_needs_rename to double_value, updating any references in that file. [testing] <!-- id:story-adhoc-1785811214 -->
- [ ] In project-docs/decisions/ab_test_fixtures/sample_module.py, extract the total/count/average accumulation loop inside compute_stats into a small helper function called _accumulate_stats, and call it f [testing] <!-- id:story-adhoc-1785822423 -->
- [ ] Scan this repo and summarize it. [backend] <!-- id:story-adhoc-1785822688 -->
- [ ] Add a docstring to the add() function in project-docs/decisions/ab_test_fixtures/sample_module.py. [testing] <!-- id:story-adhoc-1785822757 -->
- [ ] In project-docs/decisions/ab_test_fixtures/sample_module.py, rename the function old_name_needs_rename to double_value, updating any references in that file. [testing] <!-- id:story-adhoc-1785822800 -->
- [ ] In project-docs/decisions/ab_test_fixtures/sample_module.py, extract the total/count/average accumulation loop inside compute_stats into a small helper function called _accumulate_stats, and call it f [testing] <!-- id:story-adhoc-1785822823 -->
- [ ] Scan this repo and summarize it. [backend] <!-- id:story-adhoc-1785822845 -->
- [ ] [LIVE-4] _reconcile_jobs() unhandled FK IntegrityError crashes every stateful command [backend] <!-- id:story-issue-710 -->
- [ ] fix: Fix Sev1 LIVE-4 (gh#710, RCA: docs/rca/2026-08-04-LI (job-2be4aa71) [backend] <!-- id:story-issue-711 -->
- [ ] PR Review Discipline instructions say 'synlynk pr check <pr#>' — command takes no argument [testing] <!-- id:story-issue-712 -->
- [ ] chore: fix local-agent roster ID + record A/B test results [testing] <!-- id:story-issue-715 -->
- [ ] Implement Task 1 ('uxcore.py skeleton — dataclasses, Actor, Role, Event') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written: read that task's full text from the plan file fir [testing] <!-- id:ux1.0-task1 -->
- [ ] Implement Task 2 ('get_costs() and get_gantt_data() — extract from generate_viz_data()') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written: read that task's full text from th [testing] <!-- id:ux1.0-task2 -->
- [ ] Implement Task 3 ('get_jobs() and get_fleet_state() — extract telemetry/sentinel/agent reads') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written: read that task's full text f [testing] <!-- id:ux1.0-task3 -->
- [ ] Implement Task 4 ('Rewire generate_viz_data() to call uxcore + regression test') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written. This is the highest-risk task in Phase 1:  [frontend] <!-- id:ux1.0-task4 -->
- [ ] Implement Task 5 ('FeatureFlags, list_capabilities(), _execute_write(), .synlynk/events.jsonl') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written. synlynk/uxcore.py already h [testing] <!-- id:ux1.0-task5 -->
- [ ] Implement Task 6 ('uxcore.dispatch(), uxcore.approve_pr(), uxcore.kill_job()') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written. synlynk/uxcore.py already has Role/Actor/Fea [testing] <!-- id:ux1.0-task6 -->
- [ ] docs: add Worktree Hygiene Protocol to CLAUDE.md [testing] <!-- id:story-issue-575 -->
- [ ] fix: PR #599 (feat/grok-flag-mapping, Phase 2 of docs/sup (job-afb43752) [ml] <!-- id:story-issue-602 -->
- [ ] fix: Implement Task 3 from docs/superpowers/plans/2026-07 (job-3e696d1a) [docs] <!-- id:story-issue-624 -->
- [ ] fix: Fix two verified bugs found during final code review (job-59e25b71) [backend] <!-- id:story-issue-632 -->
- [ ] Implement Task 7 ('uxcore.subscribe() — tail .synlynk/events.jsonl') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written. synlynk/uxcore.py already has EVENTS_PATH, Event, _exe [testing] <!-- id:ux1.0-task7 -->
- [ ] Implement Task 8 ('Panel render functions — Fleet, Jobs, Costs, Review') from docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written. synlynk/uxcore.py already has AgentBucket, JobRun, [testing] <!-- id:ux1.0-task8 -->
- [ ] Implement Task 9 of docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written, no deviation from scope. Task text:

### Task 9: Register `synlynk tui` CLI subcommand

**Files:**
- Modify: [frontend] <!-- id:ux1.0-task9 -->
- [ ] Implement Task 10 of docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written, no deviation from scope. Task text:

### Task 10: Rewire /dispatch through uxcore, add /approve and /kill

 [testing] <!-- id:ux1.0-task10 -->
- [ ] Implement Task 11 of docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written, no deviation from scope. Task text:

### Task 11: docs/api/uxcore.md — public library README

Files:
- Crea [frontend] <!-- id:ux1.0-task11 -->
- [ ] Implement Task 12 of docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md exactly as written, no deviation from scope. Task text:

### Task 12: Minimal Slack notifier

Files:
- Create: synlynk/notifier [testing] <!-- id:ux1.0-task12 -->
- [ ] Fix two regressions surfaced by the final full-suite pytest run on branch chore/synlynk-ux-1.0-spec, after Tasks 1-12 of docs/superpowers/plans/2026-08-05-synlynk-ux-1.0.md were merged. These are gaps [frontend] <!-- id:ux1.0-regression-fix -->
- [ ] feat: Synlynk UX 1.0 — TUI + Vizor on shared uxcore [frontend] <!-- id:story-issue-731 -->
- [ ] bug: _SECRET_PATTERNS regex doesn't redact GitHub's new ghs_ installation token format [testing] <!-- id:story-issue-742 -->
- [ ] roles --fix and sync --repair-sops write uncoordinated, non-fenced harness content [testing] <!-- id:story-issue-718 -->
- [ ] docs(blog): add post 99 for PR #731 (Synlynk UX 1.0) [frontend] <!-- id:story-issue-746 -->
- [ ] flaky: test_tui_panels.py curses tests fail intermittently in CI with 'must call initscr() first' [frontend] <!-- id:story-issue-745 -->
- [ ] UX 1.0 Field Trial Readiness — design spec (test plan, journey simulator, nudges, release gate) [testing] <!-- id:story-6c5ff44e -->
- [ ] Fail closed on empty dispatch tasks and enforce task/scope integrity [backend] <!-- id:story-issue-720 -->
- [ ] Scope enforcement, permission-denied classifier fix, and safe-caller docs (#720 remainder) [backend] <!-- id:story-issue-769 -->
- [ ] Implement Task 1 only from docs/superpowers/plans/2026-08-07-scope-violation-enforcement.md (the SCOPE_VIOLATION enforcement plan, #769). Read that file's Task 1 section in full and follow it exactly  [testing] <!-- id:scope-violation-task-1 -->
- [ ] Implement Task 2 only from docs/superpowers/plans/2026-08-07-scope-violation-enforcement.md (the SCOPE_VIOLATION enforcement plan, #769). Read that file's Task 2 section in full and follow it exactly  [testing] <!-- id:scope-violation-task-2 -->
- [ ] Implement Task 3 only from docs/superpowers/plans/2026-08-07-scope-violation-enforcement.md (the SCOPE_VIOLATION enforcement plan, #769). Read that file's Task 3 section in full and follow it exactly  [testing] <!-- id:scope-violation-task-3 -->
- [ ] Implement Task 4 only from docs/superpowers/plans/2026-08-07-scope-violation-enforcement.md (the SCOPE_VIOLATION enforcement plan, #769). Read that file's Task 4 section in full and follow it exactly  [testing] <!-- id:scope-violation-task-4 -->
- [ ] Implement Task 5 only from docs/superpowers/plans/2026-08-07-scope-violation-enforcement.md (the SCOPE_VIOLATION enforcement plan, #769). Read that file's Task 5 section in full and follow it exactly  [testing] <!-- id:scope-violation-task-5 -->
- [ ] Implement Task 6 only from docs/superpowers/plans/2026-08-07-scope-violation-enforcement.md (the SCOPE_VIOLATION enforcement plan, #769). Read that file's Task 6 section in full and follow it exactly: [docs] <!-- id:scope-violation-task-6 -->
- [ ] In this worktree's README.md, the last commit (9e03a7a, 'docs: document --scope-paths flag and SCOPE_VIOLATION status') inserted two new subsections ('### Dispatch flags' and '### `jobs --summary <id> [testing] <!-- id:scope-violation-task-6-fix -->
- [ ] Review and merge PR #778 (nikhilsoman/synlynk) — 'SCOPE_VIOLATION: enforce declared --scope-paths at reconciliation (#769)'. Steps: (1) Read the PR diff and the design/plan docs it links (docs/superpo [testing] <!-- id:scope-violation-pr-review -->
- [ ] Review and merge PR #778 (nikhilsoman/synlynk) — 'SCOPE_VIOLATION: enforce declared --scope-paths at reconciliation (#769)'. Steps: (1) 'gh pr view 778 --repo nikhilsoman/synlynk' and 'gh pr diff 778  [testing] <!-- id:scope-violation-pr-review-2 -->
- [ ] Implement Tasks 1, 2, and 4 of the plan at docs/superpowers/plans/2026-08-08-safe-caller-construction.md exactly as written, on branch chore/safe-caller-construction. Task 1: create docs/reference/saf [testing] <!-- id:story-adhoc-1786167832 -->
- [ ] docs: safe caller construction guide (#769 sub-project 3/3) [testing] <!-- id:story-issue-783 -->
- [ ] GOVERNS plan Task 1: events/subscriptions schema + event bus module [backend] <!-- id:story-d797dabc -->
- [ ] GOVERNS plan Task 6: nudge fence + config [backend] <!-- id:story-0888a8d4 -->
- [ ] GOVERNS plan Task 2: goal_contributions link_status/skip_reason migration [backend] <!-- id:story-f70fb7aa -->
- [ ] GOVERNS plan Task 3: synlynk story done command [backend] <!-- id:story-8c2318c5 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md on branch chore/quota-aware-dispatch-reservation-design: the agent_reservations table and daemon_jobs.blocked_ [testing] <!-- id:quota-reservation-task-1 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md on branch chore/quota-aware-dispatch-reservation-design. Task 1 (agent_reservations table, daemon_jobs.blocked [testing] <!-- id:quota-reservation-task-2 -->
- [ ] GOVERNS plan Task 4: goal-link hook in cmd_story_ready [backend] <!-- id:story-f4035f1a -->
- [ ] GOVERNS plan Task 7: local event scanning (scan_local_events) [backend] <!-- id:story-3bab37ee -->
- [ ] Implement Task 3 of docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md on branch chore/quota-aware-dispatch-reservation-design. Tasks 1 and 2 (agent_reservations table, and _open_re [testing] <!-- id:quota-reservation-task-3 -->
- [ ] Implement Task 4 of docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md on branch chore/quota-aware-dispatch-reservation-design. Tasks 1-3 (agent_reservations table, reservation life [testing] <!-- id:quota-reservation-task-4 -->
- [ ] GOVERNS plan Task 5: pr check soft-warn for unlinked goals [backend] <!-- id:story-67fc4858 -->
- [ ] Implement Task 5 from docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md: dispatch_agent() unconditional quota gate + reservation open + defer-not-raise.

Context: Tasks 1-4 are alr [testing] <!-- id:quota-reservation-task-5 -->
- [ ] Implement Task 6 from docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md: fix _dispatch_ready_jobs() all-exhausted fall-through in synlynk/jobs.py.

Context: Task 5 (already merged  [backend] <!-- id:quota-reservation-task-6 -->
- [ ] Implement Task 7 from docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md: release reservation on job settlement in _reconcile_daemon_jobs() (synlynk/jobs.py).

Context: Tasks 1-6 ar [testing] <!-- id:quota-reservation-task-7 -->
- [ ] Fix stale test_goals/test_taxonomy assertions after GOVERNS Tasks 2/3/6 [backend] <!-- id:story-f4171bdd -->
- [ ] Implement Task 8 from docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md: scheduler.py's _enqueue_plan() opens real reservations at batch-commit time.

Context: Tasks 1-7 are alread [testing] <!-- id:quota-reservation-task-8 -->
- [ ] Task 8: Pilot workspace-lifecycle-nudge agent [backend] <!-- id:story-b950515c -->
- [ ] Implement Task 9 from docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md: create the new file synlynk/tpm_hooks.py with three TPM hook stub functions, plus tests/test_tpm_hooks.py.
 [backend] <!-- id:quota-reservation-task-9 -->
- [ ] Implement Task 10 from docs/superpowers/plans/2026-08-08-quota-aware-dispatch-reservation.md: add a `synlynk quota --tpm-view` CLI subcommand.

Context: Tasks 1-9 are already merged into this branch.  [testing] <!-- id:quota-reservation-task-10 -->
- [ ] Task 9: Surface pending nudges from exec_command [backend] <!-- id:story-e0f0b014 -->
- [ ] Task 10: GH Actions cron trigger for workspace-lifecycle-nudge agent [backend] <!-- id:story-8faedf0a -->
- [ ] Task 11: Integration tests — full reserve → dispatch → settle → release cycle, and exhaustion/resume

Files:
- Create: tests/test_quota_reservation_integration.py

Step 1: Write the integration tests
 [testing] <!-- id:quota-reservation-task-11 -->
- [ ] Task 12: Full regression suite + README documentation

Files:
- Modify: README.md (or wherever `synlynk quota` / `synlynk schedule` are currently documented — grep for `synlynk quota` in README.md fir [testing] <!-- id:quota-reservation-task-12 -->
- [ ] Fix regression in dispatch_agent()'s quota gate: closing a shared db connection breaks test_preflight_receives_real_db_conn

Context: this repo's quota-aware-dispatch-reservation feature added an unco [backend] <!-- id:quota-reservation-task12-fix-conn-close -->
- [ ] Review PR #816 (quota-aware dispatch reservation, branch chore/quota-aware-dispatch-reservation-design) on the nikhilsoman/synlynk repo. Steps: 1) Run 'synlynk pr check 816'. 2) Review the PR diff for [testing] <!-- id:pr816-review -->
- [ ] Review PR #816 (quota-aware dispatch reservation) on nikhilsoman/synlynk, branch chore/quota-aware-dispatch-reservation-design. IMPORTANT syntax note: 'synlynk pr check' takes NO arguments (not 'synly [testing] <!-- id:pr816-review-v2 -->
- [ ] Review PR #816 (quota-aware dispatch reservation) on nikhilsoman/synlynk, branch chore/quota-aware-dispatch-reservation-design. Two prior Grok dispatch attempts got cut off mid-review before completin [testing] <!-- id:pr816-review-agy -->
- [ ] Fix two bugs found in code review of PR #816 (quota-aware dispatch reservation), both in the dispatch_agent() quota gate in synlynk/dispatch.py (~lines 1680-1715), affecting the case where dispatch_ag [backend] <!-- id:pr816-fix-double-reservation -->
- [ ] Re-review PR #816 (nikhilsoman/synlynk) after a fix commit was pushed. Your prior review (posted as a PR comment on this PR) requested changes for two bugs in dispatch_agent()'s quota gate in synlynk/ [backend] <!-- id:pr816-rereview-and-merge -->
- [ ] Fix synlynk viz --serve EOFError on non-interactive invocation [backend] <!-- id:story-c822fd03 -->
- [ ] UX 1.0 Phase 2: journey map simulator [backend] <!-- id:story-e8c5d15f -->
- [ ] UX 1.0 Phase 3a: terminal tip producer [backend] <!-- id:story-0989ce14 -->
- [ ] UX 1.0 Phase 3b: Vizor first-visit banner [backend] <!-- id:story-d4b40958 -->
- [ ] UX 1.0 Phase 3c: Slack cross-links [backend] <!-- id:story-8e8c952c -->
- [ ] Implement Task 1 of the cold-start Phase 1 plan: detection heuristics for `synlynk start`.

Context: synlynk is a single-package Python CLI that wraps AI harnesses. We are adding a new `synlynk start` [testing] <!-- id:cold-start-phase1-task1 -->
- [ ] Implement Task 2 of the cold-start Phase 1 plan: the one-line ambiguous-case confirm for `synlynk start`.

Context: This builds on Task 1, which already added `synlynk/coldstart.py` with `_detect_cold [testing] <!-- id:cold-start-phase1-task2 -->
- [ ] Implement Task 3 of the cold-start Phase 1 plan: the new-project 4-question flow for `synlynk start`.

Context: This builds on Tasks 1-2, which already added `synlynk/coldstart.py` with `_detect_cold_ [testing] <!-- id:cold-start-phase1-task3 -->
- [ ] Spec-compliance fix for `_run_new_project_flow` in `synlynk/coldstart.py` (the function you just added in commit 3f2a170, "feat: add new-project 4-question cold-start flow").

Issue: the implementatio [testing] <!-- id:cold-start-phase1-task3-fix -->
- [ ] Fix a test in `tests/test_coldstart.py`: `test_run_new_project_flow_writes_config_and_roadmap_row`.

Context: this test calls `_run_new_project_flow(answers)`, which internally calls `init(mode=mode)` [testing] <!-- id:cold-start-phase1-task3-fix2 -->
- [ ] Fix one incorrect assertion in `tests/test_coldstart.py`, in `test_run_new_project_flow_writes_config_and_roadmap_row`.

Context: an earlier version of `_run_new_project_flow` in `synlynk/coldstart.py [testing] <!-- id:cold-start-phase1-task3-fix3 -->
- [ ] Implement Task 4 of the cold-start Phase 1 plan: the existing-project baseline flow for `synlynk start`.

Context: This builds on Tasks 1-3, which already added to `synlynk/coldstart.py`: `_detect_col [testing] <!-- id:cold-start-phase1-task4 -->
- [ ] Implement Task 5 of the cold-start Phase 1 plan: the `cmd_start()` orchestrator with re-run refresh prompt.

Context: This builds on Tasks 1-4, which already added to `synlynk/coldstart.py`: `_detect_ [testing] <!-- id:cold-start-phase1-task5 -->
- [ ] Fix a code-quality issue in `synlynk/coldstart.py`'s `cmd_start()` (added in commit "feat: add synlynk start orchestrator with re-run refresh prompt").

Issue: the current implementation imports `unit [testing] <!-- id:cold-start-phase1-task5-fix -->
- [ ] TUI: approve/kill keybindings missing from synlynk tui [frontend] <!-- id:story-issue-846 -->
- [ ] Slack notifier: event-name and Vizor deep-link port mismatches [testing] <!-- id:story-issue-847 -->
- [ ] Implement Task 6 of the cold-start Phase 1 plan: wire `synlynk start` into the CLI.

Context: `synlynk/coldstart.py` now has a complete `cmd_start()` orchestrator (from Tasks 1-5), fully tested (18 pa [testing] <!-- id:cold-start-phase1-task6 -->
- [ ] Fix a full-suite test failure surfaced by running `pytest -q` after the `synlynk start` cold-start command was wired into the CLI (Task 6 of the cold-start Phase 1 plan): `tests/test_taxonomy.py::test [testing] <!-- id:cold-start-phase1 -->
- [ ] Write GitHub issue #848: "Watching Synlynk @Work" guide — the 4th document on the synlynk.com/docs page, alongside the existing Quick Start Guide, Command Reference, and The Manual. This is a docs-onl [frontend] <!-- id:story-issue-848 -->
- [ ] Review PR #855 (nikhilsoman/synlynk) titled 'Cold-start Phase 1: synlynk start command'. This PR was implemented by Codex (dispatched by Claude/PM) — you did not author any of this code, so you're the [testing] <!-- id:pr-855-review -->
- [ ] Review PR #855 (nikhilsoman/synlynk) titled 'Cold-start Phase 1: synlynk start command'. This PR was implemented by Codex (dispatched by Claude/PM) — you did not author any of this code, so you're the [testing] <!-- id:pr-855-review-retry -->
- [ ] Cold-start Phase 1: synlynk start command [testing] <!-- id:story-issue-855 -->
- [ ] Review PR #855 (nikhilsoman/synlynk) titled 'Cold-start Phase 1: synlynk start command'. This PR was implemented by Codex (dispatched by Claude/PM) — you did not author any of this code, so you're the [testing] <!-- id:pr-855-review-agy -->
- [ ] Implement Task 1 of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is already committe [testing] <!-- id:cold-start-phase2-task1 -->
- [ ] Implement Task 2 of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is already committe [testing] <!-- id:cold-start-phase2-task2 -->
- [ ] Implement Task 3 of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is already committe [testing] <!-- id:cold-start-phase2-task3 -->
- [ ] Implement Task 4 of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is already committe [testing] <!-- id:cold-start-phase2-task4 -->
- [ ] Implement Task 5 of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is already committe [testing] <!-- id:cold-start-phase2-task5 -->
- [ ] Implement Task 6 of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is already committe [testing] <!-- id:cold-start-phase2-task6 -->
- [ ] Implement Task 7 (final task) of the cold-start Phase 2 implementation plan.

Read the plan file at `docs/superpowers/plans/2026-08-09-cold-start-phase2-canon-baseline.md`
in this worktree — it is alr [testing] <!-- id:cold-start-phase2-task7 -->
- [ ] Fix a bug found in final review of the cold-start Phase 2 branch (all 7 plan tasks are already
implemented and merged; this is a follow-up fix, not part of the original plan file).

Bug: `_build_claim [testing] <!-- id:cold-start-phase2-task8-fix -->
- [ ] Review and merge PR #874 in the synlynk repo (nikhilsoman/synlynk).

This PR implements "cold-start Phase 2": generating a `workspace-canon.md` baseline (a
Documentation Index + a 3-claim provenance r [testing] <!-- id:cold-start-phase2-pr874-review -->
- [ ] Review and merge PR #874 in the synlynk repo (nikhilsoman/synlynk).

This PR implements "cold-start Phase 2": generating a `workspace-canon.md` baseline (a
Documentation Index + a 3-claim provenance r [testing] <!-- id:cold-start-phase2-pr874-review-agy -->
- [ ] This is Task 3 of docs/superpowers/plans/2026-08-09-agent-vs-harness-phase0-terminology.md (Phase 0 terminology fix). Task 2 already fixed the generator function (_repair_capability_allocation_sop in  [docs] <!-- id:story-adhoc-1786298470 -->
- [ ] This is Task 4 of docs/superpowers/plans/2026-08-09-agent-vs-harness-phase0-terminology.md (Phase 0 terminology fix).

Modify CLAUDE.md only: insert a new hand-maintained section (this is outside the  [backend] <!-- id:story-adhoc-1786299496 -->
- [ ] This is Task 5 (final task) of docs/superpowers/plans/2026-08-09-agent-vs-harness-phase0-terminology.md (Phase 0 terminology fix).

Step 1: Add a header comment to .synlynk/roles.yaml. Current content [ml] <!-- id:story-adhoc-1786299617 -->
- [ ] docs: Agent vs Harness terminology — Phase 0 (spec §10) [backend] <!-- id:story-issue-880 -->
- [ ] docs(blog): PR #880 Agent vs Harness terminology post [testing] <!-- id:story-issue-885 -->
- [ ] docs: add missing session-cost row for PR #880/#885 housekeeping [testing] <!-- id:story-issue-887 -->
- [ ] [Platform:Codex] Add stdin prompt support for synlynk codex [ml] <!-- id:story-issue-12 -->
- [ ] docs: add tpm-charter review addendum to roadmap governance strategy [testing] <!-- id:story-issue-889 -->
- [ ] synlynk viz FTUE crashes with FileNotFoundError when .synlynk/ doesn't exist [testing] <!-- id:story-issue-891 -->
- [ ] cmd_probe(write_fence=True) clobbers SOP harness fence with capability-contract template [testing] <!-- id:story-issue-893 -->
- [ ] P0: serialize git ref operations in dispatch/worktree cleanup to prevent EPERM races [testing] <!-- id:story-issue-895 -->
- [ ] fix: serialize git ref operations in dispatch/worktree cleanup (#895) [testing] <!-- id:story-issue-897 -->
- [ ] GitHub App manifest callback 404s — code must be hand-copied from URL bar [frontend] <!-- id:story-issue-864 -->
- [ ] identity init: GitHub App manifest always targets personal account, not the repo's owning org [frontend] <!-- id:story-issue-901 -->
- [ ] fix: support org-scoped GitHub App manifests (#901) [backend] <!-- id:story-issue-903 -->
- [ ] Implement Tasks 1 and 2 from docs/superpowers/plans/2026-08-11-identity-slug-override.md in this worktree (branch chore/identity-slug-override). Read that plan file in full first — it has exact code s [testing] <!-- id:story-adhoc-1786466562 -->
- [ ] chore: identity_slug config override for App identity provisioning [testing] <!-- id:story-issue-908 -->
- [ ] identity init resumes incorrectly when App created but installation not confirmed [backend] <!-- id:story-issue-910 -->
- [ ] fix: resume identity init at install confirmation instead of restarting (#910) [testing] <!-- id:story-issue-912 -->
- [ ] docs: land Road to Autonomous Operations strategy + program spec [testing] <!-- id:story-issue-915 -->
- [ ] Rebase this branch (dispatch/codex/job-0d11e5c1) onto current origin/main and resolve merge conflicts to land its intent as a mergeable PR. The branch has 2 commits — 'fix(dispatch): harden reporting  [testing] <!-- id:story-adhoc-1786512284 -->
- [ ] chore: archive 3 unmerged docs from stale worktree cleanup [testing] <!-- id:story-issue-917 -->
- [ ] fix(dispatch): report only committed files in _worktree_files_touched [testing] <!-- id:story-issue-919 -->
- [ ] Implement Task 1 (job_terminal event emission) from docs/superpowers/plans/2026-08-12-governs-event-contract-extension.md in this repo. Read that plan file's 'Task 1' section for exact file paths, lin [testing] <!-- id:story-adhoc-1786558766 -->
- [ ] Implement Task 2 (review_submitted event emission) from docs/superpowers/plans/2026-08-12-governs-event-contract-extension.md in this repo. Read that plan file's 'Task 2' section for exact code (3 new [testing] <!-- id:story-adhoc-1786558957 -->
- [ ] Implement Task 3 (synlynk events tail CLI command) from docs/superpowers/plans/2026-08-12-governs-event-contract-extension.md in this repo. Read that plan file's 'Task 3' section for exact code: cmd_e [testing] <!-- id:story-adhoc-1786561143 -->
- [ ] GOVERNS event-contract extension: job_terminal, review_submitted, events tail [testing] <!-- id:story-issue-922 -->
- [ ] docs: lift stale Blog Post Protocol hold [testing] <!-- id:story-issue-923 -->
- [ ] Add dispatch_context (home|headless) column to daemon_jobs+cost_entries, filled at enqueue/dispatch (#740) [backend] <!-- id:story-53789473 -->
- [ ] fix: A3: implement real home|headless detection for dispa (job-08ce0867) [testing] <!-- id:story-issue-926 -->
- [ ] fix: B3: root-cause + mitigate the GitHub MCP review-subm (job-d15e18c3) [testing] <!-- id:story-issue-925 -->
- [ ] Root-cause investigation only, NO code changes and NO GitHub write attempts: issue #577 says the Codex dispatch sandbox's gh CLI reports 'invalid/expired token' (gh auth status fails) when trying to p [backend] <!-- id:issue-577 -->
- [ ] Root-cause investigation only, NO code changes and NO GitHub write attempts: issue #659 documents 4/4 occurrences of dispatched review jobs (in cc-videoreframing PRs #80/#83) whose GitHub MCP tool cal [backend] <!-- id:issue-659 -->
- [ ] Execute docs/superpowers/plans/2026-08-09-cold-start-phase3-release-tag-signal.md task-by-task using superpowers:subagent-driven-development (or superpowers:executing-plans). Follow the plan's byte-ex [testing] <!-- id:cold-start-phase3 -->
- [ ] story-issue-931: Audit harness/PM conventions across synlynk, rxcc, cc-videoreframing (1.0 standardization) [backend] <!-- id:story-a302384c -->
- [ ] chore: release v0.13.1 — operational reliability patch [testing] <!-- id:story-issue-932 -->
- [ ] docs: TPM/session MVP implementation plan (Week 2) [testing] <!-- id:story-issue-933 -->
- [ ] fix: ## Permissions (job-5b4cff27) [testing] <!-- id:story-issue-930 -->
- [ ] [Workspace Context Sync Audit] devlog/memory/state.db drift across project-docs working copy, .synlynk/ git-tracked mirror, and SQLite state — requires deep review + broad sweep of ALL workspace context constituents, not just devlogs.

Investigation (cc-videoreframing repo, 2026-08-14, during a routine "check devlog/memory are up to date" task):

1. project-docs/ at repo root is fully gitignored (.gitignore:75 `/project-docs/`) — it's a local, ungitted working copy. The actual git-tracked "source of truth" mirror lives under .synlynk/project-docs/ (devlogs/, memory.md, roadmap.md, todo.md, costs.md, archive/). These two copies can silently diverge with no warning surfaced to the operator.

2. Confirmed divergence: .synlynk/project-docs/devlogs/nikhilsoman.md is a stale one-time migration snapshot — different header/format than the working copy, last modified 2026-08-13, missing entries that already existed in the working copy at that time (e.g. the 2026-08-12 admin-panel session). Meanwhile .synlynk/project-docs/memory.md (same directory, same last-modified date) IS actively current — correctly reflects a running log of real `### <Title> [@author] YYYY-MM-DD` entries appended across many sessions. Same sync mechanism, two different files, two very different staleness outcomes — no obvious reason why.

3. state.db's devlog_entries table (schema: id, author, entry_date, session_title, body, recorded_at) is even more stale than the .synlynk mirror — newest row dated 2026-07-31, predating even the already-existing 2026-08-12 devlog entry that was on disk well before this investigation.

4. `synlynk checkpoint` runs clean ("0 tasks archived, context refreshed") and gives no indication it failed to sync anything — but does not appear to actually ingest devlog content into state.db or refresh the .synlynk/project-docs/devlogs/ mirror from the working copy.

5. `synlynk migrate --dry-run` reports "Already migrated. Use --recover to re-import from backup" — confirmed this is a one-time bootstrap operation, not a routine resync path; --recover is documented for backup-restore, not day-to-day content sync.

6. CLAUDE.md's documented workflow ("append directly to this file... then run synlynk checkpoint to sync derived state") does not match observed behavior — checkpoint exits clean without actually performing the sync it's described as doing.

ASK — two deliverables, both required:

A) Deep review of the actual sync pipeline: trace what synlynk checkpoint, synlynk migrate, and any other sync-adjacent command actually read/write for each project-docs/* artifact type (devlogs/*.md, memory.md, roadmap.md, todo.md, costs.md) and the corresponding state.db tables. Determine definitively why memory.md stays current while devlogs/*.md does not — is this an intentional design difference (e.g. memory.md is DB-backed and rendered, while devlogs are meant to be pure append-only markdown never re-synced from the DB), a partially-implemented feature, or a genuine bug. Document the real contract, since CLAUDE.md's description does not match observed behavior.

B) Broad sweep across ALL workspace context constituents (not just devlogs): systematically audit every file/table pair implicated in project-docs sync — devlogs/*.md vs any devlog_entries-like table, memory.md vs its backing table (if any), roadmap.md, todo.md, costs.md — for the same class of drift, across every repo currently using synlynk (not just cc-videoreframing), and report findings per-artifact. If any other artifact shows the same silent-divergence pattern, it needs the same fix or documented-as-expected treatment as whatever is decided for devlogs in (A).

Impact: any Claude session (or human) relying on `.synlynk/project-docs/devlogs/` as "the" project history, or on state.db devlog_entries for cross-session continuity, is working from stale/incomplete data with no signal that this is happening — checkpoint's clean exit gives false confidence. [devops] <!-- id:story-e4cd6595 -->
- [ ] fix: Implement Task 1 of the approved plan docs/superpowe (job-027c510e) [backend] <!-- id:story-issue-934 -->
- [ ] Addendum to story-e4cd6595: fold project-docs/decisions/ into the workspace context sync sweep

story-e4cd6595 (Workspace Context Sync Audit) scoped its broad sweep across devlogs/*.md,
memory.md, roadmap.md, todo.md, and costs.md — but missed project-docs/decisions/, which
is the same class of gitignored working-copy constituent (confirmed via
`git check-ignore -v`, matched by the same `.gitignore:75 /project-docs/` rule).

Concrete instance found 2026-08-14 (cc-videoreframing): a `synlynk decide --record` call
wrote project-docs/decisions/2026-08-14-composition-classifier-architecture-wher.md — a
real decision record with no git-tracked mirror anywhere under .synlynk/project-docs/ and
no corresponding state.db table identified yet. Same open questions as story-e4cd6595
apply here: is this file meant to be ephemeral/local-only by design, or should it sync to
a git-tracked mirror and/or a state.db table the way memory.md does; if the latter, why
hasn't it.

Fold this into story-e4cd6595's Part B broad sweep: audit every project-docs/* subdirectory
(not just the file types already listed) for the same working-copy-vs-mirror-vs-db pattern,
using decisions/ as the concrete example that prompted this addendum. No separate fix
should ship for decisions/ alone — resolve it as part of e4cd6595's unified sync-pipeline
review so the fix (or documented-as-expected decision) is consistent across all
constituent types. [devops] <!-- id:story-9583deba -->
- [ ] Update the synlynk.com website to reflect the v0.13.1 release. Files: website/src/features.njk (features page), website/src/docs.njk and website/src/assets/docs/ (docs content) — check docs.njk for ho [security] <!-- id:story-adhoc-1786699116 -->
- [ ] Reviewer-dispatch reliability gap: 3 of 4 PR-review dispatches failed to complete this session [backend] <!-- id:story-issue-935 -->
- [ ] fix: Fix: review-only synlynk dispatch jobs get killed as (job-5dcb8434) [testing] <!-- id:story-issue-939 -->
- [ ] fix: Implement Task 2 of docs/superpowers/plans/2026-08-1 (job-b5aab040) [testing] <!-- id:story-issue-940 -->
- [ ] fix: Fix issue #937: review-only synlynk dispatch jobs ge (job-c62bbfd3) [testing] <!-- id:story-issue-943 -->
- [ ] fix: Fix a blocking bug found in PR #940 (story-issue-934 (job-cddd3080) [testing] <!-- id:story-issue-944 -->
- [ ] Implement Task 3 of the approved plan docs/superpowers/plans/2026-08-13-tpm-session-mvp.md — link devlog_entries to session + goal. IMPORTANT CONTEXT DIVERGENCE FROM THE PLAN TEXT: Task 2's merged PR  [backend] <!-- id:story-adhoc-1786718972 -->
- [ ] Implement Task 3 of the approved plan docs/superpowers/plans/2026-08-13-tpm-session-mvp.md — link devlog_entries to session + goal. IMPORTANT CONTEXT DIVERGENCE FROM THE PLAN TEXT: Task 2's merged PR  [backend] <!-- id:story-adhoc-1786719704 -->
- [ ] Implement Task 3 of the approved plan docs/superpowers/plans/2026-08-13-tpm-session-mvp.md — link devlog_entries to session + goal. IMPORTANT CONTEXT DIVERGENCE FROM THE PLAN TEXT: Task 2's merged PR  [backend] <!-- id:story-adhoc-1786720086 -->
- [ ] docs: devlog identity registry + synlynk audit-docs implementation plan [backend] <!-- id:story-issue-949 -->
- [ ] Implement Task 3 of the approved plan docs/superpowers/plans/2026-08-13-tpm-session-mvp.md — link devlog_entries to session + goal. IMPORTANT CONTEXT DIVERGENCE FROM THE PLAN TEXT: Task 2's merged PR  [backend] <!-- id:story-adhoc-1786720427 -->
- [ ] fix: Implement Task 3 of the approved plan docs/superpowe (job-be2d54a0) [backend] <!-- id:story-issue-950 -->
- [ ] Implement Tasks 1, 2, and 3 from docs/superpowers/plans/2026-08-14-devlog-identity-registry.md (on main as of this dispatch — read the whole plan file first). These three tasks are tightly coupled (Ta [security] <!-- id:story-adhoc-1786721223 -->
- [ ] fix: Implement Tasks 1, 2, and 3 from docs/superpowers/pl (job-15d2c93d) [testing] <!-- id:story-issue-953 -->
- [ ] Implement Task 4 of the approved plan docs/superpowers/plans/2026-08-13-tpm-session-mvp.md — thread session_id through dispatch_agent() -> daemon_jobs -> cost_entries. Task 3 (devlog_entries session/g [backend] <!-- id:story-adhoc-1786721532 -->
- [ ] fix: Implement Task 4 of the approved plan docs/superpowe (job-fd0a7927) [backend] <!-- id:story-issue-954 -->
- [ ] fix: Implement Task 5 of the approved plan docs/superpowe (job-f9573e0b) [testing] <!-- id:story-issue-955 -->
- [ ] Implement Task 4 from docs/superpowers/plans/2026-08-14-devlog-identity-registry.md (on main as of this dispatch, which now includes Tasks 1-3 already merged — read the whole plan file first, and re-c [security] <!-- id:story-adhoc-1786723121 -->
- [ ] Implement Task 6 (final task) of the approved plan docs/superpowers/plans/2026-08-13-tpm-session-mvp.md — add the first durable TPM nudge: surface unattributed daemon_jobs (session_id IS NULL) as a NU [backend] <!-- id:story-adhoc-1786723786 -->
- [ ] fix(checkpoint): resolve devlog path through member_id registry (Task 4) [testing] <!-- id:story-issue-956 -->
- [ ] feat: surface unattributed-job nudge in session status (Task 6) [testing] <!-- id:story-issue-959 -->
- [ ] fix: Implement Tasks 5 and 6 from docs/superpowers/plans/ (job-78b20084) [testing] <!-- id:story-issue-958 -->
- [ ] Implement Task 7 (final task) from docs/superpowers/plans/2026-08-14-devlog-identity-registry.md (on main as of this dispatch — Tasks 1-6 are now fully merged: member registry schema, cmd_audit_docs r [testing] <!-- id:story-adhoc-1786725205 -->
- [ ] Run 'synlynk audit-docs' (report mode first) against this repo's real project-docs/devlogs/ state to see the current nikhil.md/nikhilsoman.md fork it detects, then run 'synlynk audit-docs --fix' to ac [testing] <!-- id:story-adhoc-1786780602 -->
- [ ] docs(strategy): two-imperatives roadmap [testing] <!-- id:story-issue-963 -->
- [ ] Consolidate + permanently fix: daemon_jobs status untruthfulness and sandboxed gh-write unreliability (#331/#579, #426/#569/#577/#659) [backend] <!-- id:story-issue-701 -->
- [ ] Execute Task 0 from docs/superpowers/plans/2026-08-15-job-truth-gh-write-consolidation.md (branch chore/job-truth-gh-write-consolidation-design). Read that file's 'Task 0: Persist requires_gh_write an [testing] <!-- id:story-adhoc-1786808036 -->
- [ ] Execute Task 1 from docs/superpowers/plans/2026-08-15-job-truth-gh-write-consolidation.md (branch chore/job-truth-gh-write-consolidation-design, current HEAD already has Task 0 merged — requires_gh_wr [testing] <!-- id:story-adhoc-1786808705 -->
- [ ] Execute Task 4 from docs/superpowers/plans/2026-08-15-job-truth-gh-write-consolidation.md (branch chore/job-truth-gh-write-consolidation-design) — the 'TC-7 preflight: Agy allow-rules check before rou [testing] <!-- id:story-adhoc-1786808715 -->
- [ ] Execute Task 2 from docs/superpowers/plans/2026-08-15-job-truth-gh-write-consolidation.md (read the full plan file first for context; Task 2 section starts at "### Task 2: Surface `gh_write_verified`  [testing] <!-- id:story-adhoc-1786809285 -->
- [ ] daemon_jobs status reconciliation never got Ground-Truth Verification — jobs falsely report UNKNOWN/0-files-touched [testing] <!-- id:story-issue-331 -->
- [ ] Review the job-truth/gh-write consolidation implementation on branch chore/job-truth-gh-write-consolidation-design (this is the current branch tip, containing Tasks 0-6 already merged locally via --no [testing] <!-- id:story-adhoc-1786809960 -->
- [ ] Fix a real test regression caused by earlier work in this branch (Task 4 of the job-truth/gh-write consolidation, which added a TC-7 Agy allow-rules preflight check to synlynk/doctor.py, called as doc [testing] <!-- id:story-adhoc-1786810792 -->
- [ ] GOVERNS: job-truth/gh-write consolidation (#701) [testing] <!-- id:story-issue-978 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md exactly as written: get_workspace_id() — mint-once workspace identity.

Read the plan file's Task 1 section fo [testing] <!-- id:story-adhoc-1786815729 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md exactly as written: agent store paths + agent_id registry.

Context: Task 1 (get_workspace_id() in synlynk/age [testing] <!-- id:story-adhoc-1786815890 -->
- [ ] Implement Task 3 of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md exactly as written: charter revision storage.

Context: Tasks 1-2 already landed on this branch (get_workspace [testing] <!-- id:story-adhoc-1786816023 -->
- [ ] Implement Task 4 of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md exactly as written: memory + statements-of-record entry storage.

Context: Tasks 1-3 already landed on this br [testing] <!-- id:story-adhoc-1786816158 -->
- [ ] Implement Task 5 of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md exactly as written: regenerate_agent_projection() repo-local generated projection.

Context: Tasks 1-4 already [ml] <!-- id:story-adhoc-1786819949 -->
- [ ] Implement Task 6 (final task) of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md exactly as written: integration test for the full agent artifact storage flow.

Context: Tasks 1- [testing] <!-- id:story-adhoc-1786820124 -->
- [ ] Fix a path bug from the already-merged Task 5 commit, then implement Task 6 (final task) of docs/superpowers/plans/2026-08-15-workspace-agent-artifact-storage.md.

BUG TO FIX FIRST: synlynk/agent_stor [ml] <!-- id:story-adhoc-1786820507 -->
- [ ] feat: workspace-scoped agent artifact storage (charter, memory, SoR) [ml] <!-- id:story-issue-988 -->
- [ ] Implement Task 1 from docs/superpowers/plans/2026-08-16-rename-agent-cli-to-harness.md in this worktree (branch chore/rename-agent-cli-to-harness).

Task 1: Update the CLI-route test to the new `harne [testing] <!-- id:story-adhoc-1786828866 -->
- [ ] feat(v0.10): job completion summaries — _write_job_summary + cmd_jobs --summary [testing] <!-- id:story-issue-97 -->
- [ ] chore: rename synlynk agent CLI group to harness [backend] <!-- id:story-issue-993 -->
- [ ] Implement Task 1 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 1: Storage layer additions — set_agent_disabled and list_agents"). Read that exact section of the plan file [testing] <!-- id:story-adhoc-1786853807 -->
- [ ] Implement Task 2 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 2: synlynk/agent_cli.py — init, list, show"). Read that exact section of the plan file first for full conte [testing] <!-- id:story-adhoc-1786854088 -->
- [ ] Implement Task 3 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 3: synlynk/agent_cli.py — edit, disable"). Read that exact section of the plan file first for full context  [testing] <!-- id:story-adhoc-1786854355 -->
- [ ] Implement Task 4 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 4: Wire agent subparser into synlynk/cli.py"). Read that exact section of the plan file first (lines ~515-6 [testing] <!-- id:story-adhoc-1786854772 -->
- [ ] Implement Task 5 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 5: dispatch_agent() gains agent_id — role resolution and error handling"). Read that exact section of the p [testing] <!-- id:story-adhoc-1786855298 -->
- [ ] Implement Task 6 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 6: Harness auto-selection and GitHub identity resolution from agent_id"). Read that exact section of the pl [testing] <!-- id:story-adhoc-1786856405 -->
- [ ] Implement Task 7 from docs/superpowers/plans/2026-08-16-agent-dispatch-integration.md ("Task 7: --as-agent flag on synlynk dispatch CLI"). Read that exact section of the plan file first (lines ~955-10 [testing] <!-- id:story-adhoc-1786856549 -->
- [ ] feat: agent-roles-charters Phase 1 — CLI onboarding + dispatch integration [testing] <!-- id:story-issue-1003 -->
- [ ] docs(blog): add PR #1003 agent-roles-charters Phase 1 post [security] <!-- id:story-issue-1006 -->
- [ ] docs: sync two-imperatives roadmap + todo.md, revise release cadence [testing] <!-- id:story-issue-1010 -->
- [ ] chore: cut v0.14.0 named release [testing] <!-- id:story-issue-1012 -->
- [ ] Implement Task 1 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as written (read that file's "Task 1: daemon_jobs.agent_id schema migration" section for full details).  [backend] <!-- id:story-adhoc-1786967176 -->
- [ ] Implement Task 2 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as written (read that file's "Task 2: regenerate_agent_projection() merge-not-replace semantics" section [testing] <!-- id:story-adhoc-1786967289 -->
- [ ] Implement Task 3 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as written (read that file's "Task 3: cmd_agent_edit stops clobbering capability_grants" section for ful [testing] <!-- id:story-adhoc-1786967413 -->
- [ ] Implement Task 4 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as written (read that file's "Task 4: Thread agent_id through daemon_jobs write paths" section for full  [testing] <!-- id:story-adhoc-1786967549 -->
- [ ] Implement Task 5 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as written (read that file's "Task 5: Extract resolve_dispatch_harness(), fix --dry-run + --as-agent pre [testing] <!-- id:story-adhoc-1786967687 -->
- [ ] Implement Task 6 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as specified.

### Task 6: _harness_for_org_role restricted to CORE_FLEET

Files:
- Modify: synlynk/disp [testing] <!-- id:story-adhoc-1786968103 -->
- [ ] Implement Task 7 from docs/superpowers/plans/2026-08-16-agent-roles-phase1-followups.md exactly as specified. This is a test-only task — no production code changes.

### Task 7: story_id vs agent_id p [testing] <!-- id:story-adhoc-1786968228 -->
- [ ] fix: close 5 non-blocking follow-ups from PR #1003 review [testing] <!-- id:story-issue-1022 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-17-agent-roles-phase2-memory-gated-learning.md ("Synthetic Story ID Helper + Seeding Function"). Read that plan file's Task 1 section in full first — [testing] <!-- id:story-adhoc-1786973533 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-08-17-agent-roles-phase2-memory-gated-learning.md ("Read Path — resolve_dispatch_harness() Synthetic-Story Lookup + static_baseline Flag"). Read that pl [testing] <!-- id:story-adhoc-1786973679 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-08-17-agent-roles-phase2-memory-gated-learning.md on branch chore/agent-roles-phase2-spec. Follow TDD: write the failing tests first, run them, implemen [backend] <!-- id:story-adhoc-1786984239 -->
- [ ] Workspace-level (multi-repo) agent identities — cross-repo App scope, shared board, and operational implications [frontend] <!-- id:story-issue-914 -->
- [ ] feat: Agent-roles Phase 2 — memory-gated capability routing [testing] <!-- id:story-issue-1030 -->
- [ ] Implement Task 1 from docs/superpowers/plans/2026-08-18-workspace-context-write-through-936.md: add a new 'decisions' table to the executescript block in _migrate_db() in synlynk/db.py (right after th [testing] <!-- id:story-adhoc-1787004759 -->
- [ ] Implement Task 2 from docs/superpowers/plans/2026-08-18-workspace-context-write-through-936.md: add cmd_decision_record() and _write_decision_record_md() to synlynk/db.py, inserted immediately after c [testing] <!-- id:story-adhoc-1787004859 -->
- [ ] Workspace context divergence: state.db silently disagrees with project-docs/* markdown (devlogs, decisions, more TBD) [backend] <!-- id:story-issue-936 -->
- [ ] fix: workspace context write-through for decisions + devlogs (#936) [testing] <!-- id:story-issue-1038 -->
- [ ] Dispatched agent GitHub MCP review submissions silently cancelled 4/4 times (add_review_to_pr / add_comment_to_issue) [backend] <!-- id:story-issue-659 -->
- [ ] GH-Write Delivery Verification, Round 2 (#659, #860) [backend] <!-- id:story-issue-1048 -->
- [ ] Rename internal 'agent' nomenclature to 'harness' (CLI, DB columns, docs) [testing] <!-- id:story-issue-786 -->
- [ ] Daemon auto-opens phantom PRs for review/gh-write-only dispatch jobs with incidental worktree diffs [testing] <!-- id:story-issue-1058 -->
- [ ] Final sign-off review of PR #1053 (docs/harness-capability-registry-v2-786 branch, #786 harness rename + capability registry v2 plans). You are the non-authoring reviewer required before merge (Claude [backend] <!-- id:PR-1053-final-signoff -->
- [ ] Final sign-off review of PR #1053 (docs/harness-capability-registry-v2-786 branch, #786 harness rename + capability registry v2 plans). You are the non-authoring reviewer required before merge (Claude [backend] <!-- id:PR-1053-final-signoff-v2 -->
- [ ] fix: skip phantom PR auto-creation for review/gh-write-only dispatch jobs (#1058) [testing] <!-- id:story-issue-1061 -->
- [ ] Implement docs/superpowers/plans/2026-08-18-harness-rename-plan-a-786.md task-by-task, in order, exactly as written (8 tasks: DB schema rename, AGENT_CAPABILITY_BASELINES->HARNESS_CAPABILITY_BASELINES [testing] <!-- id:harness-rename-plan-a-786 -->
- [ ] Implement docs/superpowers/plans/2026-08-18-harness-capability-registry-v2-plan-b-786.md task-by-task, in order, exactly as written. This plan already went through two rounds of independent review (Gr [backend] <!-- id:harness-capability-registry-v2-plan-b-786 -->
- [ ] Resume implementing docs/superpowers/plans/2026-08-18-harness-capability-registry-v2-plan-b-786.md. You are on branch dispatch/agy/job-f1858da0, which already has Task 1 committed (harness_models/harn [ml] <!-- id:harness-capability-registry-v2-plan-b-786-resume -->
- [ ] Non-authoring review of PR #1065 (github.com/nikhilsoman/synlynk/pull/1065), branch dispatch/codex/job-7bb79549, authored by Codex. This PR implements docs/superpowers/plans/2026-08-18-harness-rename- [testing] <!-- id:PR-1065-review -->
- [ ] fix: Implement docs/superpowers/plans/2026-08-18-harness- (job-7bb79549) [backend] <!-- id:story-issue-1065 -->
- [ ] feat: harness capability registry v2 — Plan B (#786) [backend] <!-- id:story-issue-1066 -->
- [ ] Prevent global state DB corruption from unisolated migration tests (root cause of #1065 incident) [backend] <!-- id:story-issue-1068 -->
- [ ] CI: synlynk/__init__.py exceeds 4000-line guard on main (4054 lines), blocks every PR's merge-check CI [testing] <!-- id:story-issue-1076 -->
- [ ] fix: Fix issue #1076: synlynk/__init__.py is 4054 lines, (job-027f37b6) [testing] <!-- id:story-issue-1077 -->
- [ ] Implement Task 1 and Task 1b from docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md (read that file for full context/rationale). Branch: feat/qa-gate-verdict-module, based on main.

## Task [testing] <!-- id:qa-gate-task1 -->
- [ ] Implement Task 2 from docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md (read that file for full context/rationale — this task is 'Task 2: Wire the verdict into synlynk pr check'). Branch:  [backend] <!-- id:qa-gate-task2 -->
- [ ] Implement Task 3 from docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md (read that file for full context/rationale — this task is 'Task 3: synlynk pr gate-status CLI subcommand + CI workflo [ml] <!-- id:qa-gate-task3 -->
- [ ] Fix a real CI race bug in PR #1084 (https://github.com/nikhilsoman/synlynk/pull/1084, branch feat/qa-gate-ci-workflow) on the synlynk repo.

Context: this branch added .github/workflows/qa-gate.yml as [ml] <!-- id:qa-gate-task3-fix -->
- [ ] Fix a second real bug in PR #1084 (https://github.com/nikhilsoman/synlynk/pull/1084, branch feat/qa-gate-ci-workflow) on the synlynk repo, found by actually running the new qa-gate CI job for the firs [testing] <!-- id:qa-gate-task3-ci-branch-fix -->
- [ ] feat: qa-gate CI workflow job (branch-protection backstop, half 2 of 2) [backend] <!-- id:story-issue-1084 -->
- [ ] [LIVE-5] _migrate_db() copies the entire state DB on every connection — backup storm + lock contention [backend] <!-- id:story-issue-1087 -->
- [ ] Implement Task 4 of docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md ("Branch-protection required-check wiring"). PRs A, B, C (qa_gate module, synlynk pr check integration, qa-gate.yml CI  [backend] <!-- id:story-adhoc-1787345762 -->
- [ ] Implement Task 4 of docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md ("Branch-protection required-check wiring"). PRs A, B, C (qa_gate module, synlynk pr check integration, and the qa-gate [backend] <!-- id:story-adhoc-1787345859 -->
- [ ] Implement Task 4 of docs/superpowers/plans/2026-08-20-qa-merge-gate-authority.md ("Branch-protection required-check wiring"). PRs A, B, C (qa_gate module, synlynk pr check integration, and the qa-gate [backend] <!-- id:story-adhoc-1787345989 -->
- [ ] Fix a bug in scripts/apply_qa_gate_branch_protection.sh, which you already wrote on this branch (commit 737b200). The script has a genuine bug: `gh api "$endpoint" --jq 'contexts'` uses `contexts` as  [backend] <!-- id:story-adhoc-1787346540 -->
- [ ] Fix a bug in scripts/apply_qa_gate_branch_protection.sh, which you already wrote on this branch (commit 737b200). The script has a genuine bug: `gh api "$endpoint" --jq 'contexts'` uses `contexts` as  [backend] <!-- id:story-adhoc-1787346606 -->
- [ ] Fix a bug in scripts/apply_qa_gate_branch_protection.sh, which you already wrote on this branch (commit 737b200). The script has a genuine bug: `gh api "$endpoint" --jq 'contexts'` uses `contexts` as  [backend] <!-- id:story-adhoc-1787346675 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-22-qa-completion-tracker.md: Spec/plan/issue reference parser.

Files:
- Create: synlynk/completion_tracker.py
- Test: tests/test_completion_tracker. [testing] <!-- id:qa-completion-tracker-task-1 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-22-qa-merge-restricted-classes.md: Docs-only file-pattern matcher.

Files:
- Create: synlynk/merge_class.py
- Test: tests/test_merge_class.py

Follow [testing] <!-- id:qa-merge-restricted-classes-task-1 -->
- [ ] In the worktree for job-3495905c (branch dispatch/codex/job-3495905c), fix a spec-compliance deviation in synlynk/completion_tracker.py. The implementation plan (docs/superpowers/plans/2026-08-22-qa-c [testing] <!-- id:story-adhoc-1787388305 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-08-22-qa-merge-restricted-classes.md: 'qa_gate_mode config plumbing + changed-files helper'. This branch is stacked on Task 1 (already merged into this  [testing] <!-- id:story-adhoc-1787388439 -->
- [ ] In the worktree for job-2e461875 (branch dispatch/codex/job-2e461875), add back two docstrings to synlynk/completion_tracker.py that the implementation plan (docs/superpowers/plans/2026-08-22-qa-compl [testing] <!-- id:story-adhoc-1787388576 -->
- [ ] CRITICAL BUG FIX in the worktree for job-116fdd40 (branch dispatch/codex/job-116fdd40). synlynk/qa_gate.py's _qa_gate_mode() (added in the last commit) opens the WRONG PATH: it has 'synlynk/config.jso [testing] <!-- id:story-adhoc-1787388610 -->
- [ ] CRITICAL BUG FIX in the worktree for job-116fdd40 (branch dispatch/codex/job-116fdd40). synlynk/qa_gate.py's _qa_gate_mode() (added in the last commit) opens the WRONG PATH: it has 'synlynk/config.jso [testing] <!-- id:story-adhoc-1787388631 -->
- [ ] In the current worktree (this job's own worktree, stacked on dispatch/codex/job-2e461875), add back two docstrings to synlynk/completion_tracker.py that the implementation plan (docs/superpowers/plans [testing] <!-- id:story-adhoc-1787388691 -->
- [ ] In your own worktree for this job (stacked on dispatch/codex/job-a57d989f), fix one remaining test bug in tests/test_qa_gate.py. The function test_qa_gate_mode_defaults_to_block_only_when_key_absent ( [testing] <!-- id:story-adhoc-1787388722 -->
- [ ] Implement Task 3 of docs/superpowers/plans/2026-08-22-qa-completion-tracker.md exactly as written below. This branch is stacked on the already-reviewed and approved Task 2 branch (dispatch/codex/job-6 [backend] <!-- id:story-adhoc-1787388988 -->
- [ ] Implement Task 3 of docs/superpowers/plans/2026-08-22-qa-merge-restricted-classes.md exactly as written below. This branch is stacked on the already-reviewed and approved Task 2 branch (dispatch/codex [testing] <!-- id:story-adhoc-1787388993 -->
- [ ] Implement Task 4 ("Vizor panel for verified PRs") of the plan at docs/superpowers/plans/2026-08-22-qa-completion-tracker.md, exactly as specified below. This is the final task of this plan, stacked on [frontend] <!-- id:story-adhoc-1787390270 -->
- [ ] feat: qa gate verdict module (block-only mode) [backend] <!-- id:story-issue-1082 -->
- [ ] docs: record PR #1091/#1092/#1104 merges + autonomy roadmap [testing] <!-- id:story-issue-1105 -->
- [ ] TC-7 Agy preflight checks wrong JSON path in antigravity-cli settings.json [testing] <!-- id:story-issue-1106 -->
- [ ] fix: Fix #1106: TC-7 Agy preflight in synlynk/doctor.py c (job-d7489801) [testing] <!-- id:story-issue-1107 -->
- [ ] feat: synlynk v0.2.0 — watch daemon, checkpoint, status command, context compaction [backend] <!-- id:story-issue-1 -->
- [ ] fix(doctor): TC-4 false-positives on flag-only verb command templates [testing] <!-- id:story-issue-123 -->
- [ ] fix(dispatch): gh-write identity hardening — Phase 1 closeout (#423) [testing] <!-- id:story-issue-1110 -->
- [ ] docs: note shared durable-agent runtime as future extraction (#1080) [testing] <!-- id:story-issue-1081 -->
- [ ] Implement Task 1 from docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md exactly as specified below. Work in the current repo/branch (docs/workspace-policy-autonomous-loop-desig [frontend] <!-- id:story-adhoc-1787467571 -->
- [ ] Implement exactly Task 1 (only Task 1, stop after its Step 5 commit) from the plan file docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md in this repo/branch. Read that section [testing] <!-- id:story-adhoc-1787467705 -->
- [ ] Implement exactly Task 2 (only Task 2, stop after its Step 5 commit) from the plan file docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md in this repo/branch. Task 1's synlynk/ [testing] <!-- id:story-adhoc-1787468683 -->
- [ ] Implement exactly Task 3 (only Task 3, stop after its Step 6 commit) from the plan file docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md in this repo/branch. Tasks 1 and 2 alr [testing] <!-- id:story-adhoc-1787470122 -->
- [ ] On branch dispatch/codex/job-9aaadf59 in this worktree (which already has commit 123daa9 'feat(policy): gate dispatch_agent() task_type against policy.json allocation table'), fix a regression: runnin [testing] <!-- id:story-adhoc-1787471907 -->
- [ ] On this branch (docs/workspace-policy-autonomous-loop-design), which now includes commit 123daa9 'feat(policy): gate dispatch_agent() task_type against policy.json allocation table', fix a regression: [testing] <!-- id:story-adhoc-1787471955 -->
- [ ] Implement exactly Task 4 (only Task 4, stop after its Step 6 commit) from the plan file docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md in this repo/branch. Tasks 1-3 already [testing] <!-- id:story-adhoc-1787472921 -->
- [ ] Implement exactly Task 5 (only Task 5, stop after its Step 6 commit) from the plan file docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md in this repo/branch. Tasks 1-4 already [backend] <!-- id:story-adhoc-1787474211 -->
- [ ] On this branch (docs/workspace-policy-autonomous-loop-design), commit cb61761 'feat(policy): add synlynk policy sync-branch-protection command' added cmd_policy_sync_branch_protection() in synlynk/pol [backend] <!-- id:story-adhoc-1787475473 -->
- [ ] Implement Task 6 from the plan file docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md in this repo/branch, with one correction to the plan's ground truth: the plan references t [testing] <!-- id:story-adhoc-1787476462 -->
- [ ] Implement Task 7 from docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md exactly as specified. Read that section of the plan directly (search for "### Task 7:") rather than rein [backend] <!-- id:story-adhoc-1787479634 -->
- [ ] Implement Task 8 from docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md exactly as specified. Read that section of the plan directly (search for "### Task 8:") for the exact te [backend] <!-- id:story-adhoc-1787497257 -->
- [ ] Add a purpose-built helper `emit_awaiting_approval()` to synlynk/events.py, following this repo's existing GOVERNS event pattern.

CONTEXT: synlynk/events.py already has `emit_event(event_type: str, p [backend] <!-- id:story-adhoc-1787501242 -->
- [ ] Add an approval-gate flow to this repo: a new module synlynk/approval_gate.py that files a GitHub issue requesting human approval for a policy-gated autonomous action, plus resolution-detection wired  [backend] <!-- id:story-adhoc-1787502818 -->
- [ ] Add an approval-gate flow to this repo: a new module synlynk/approval_gate.py that files a GitHub issue requesting human approval for a policy-gated autonomous action, plus resolution-detection wired  [backend] <!-- id:story-adhoc-1787502913 -->
- [ ] Implement Task 12 of docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md: the `synlynk tpm sweep` CLI command. This is TDD — write the failing test first, then the implementation [backend] <!-- id:story-adhoc-1787504299 -->
- [ ] chore: append a one-line dogfood-verification note to project-docs/devlogs/nikhilsoman.md recording the v0.16.0 Task 13 live tpm-sweep demo timestamp [backend] <!-- id:story-028d26d9 -->
- [ ] tpm-sweep dogfood demo: gated story (should park pending approval) [backend] <!-- id:story-7aa0aaec -->
- [ ] fix(events): subscriptions table missing harness_name migration crashes scan_local_events (#1132) [backend] <!-- id:story-55bcacc8 -->
- [ ] fix(stories,tpm_sweep): story done doesn't clear readiness, causing re-sweep of completed stories (#1133) [backend] <!-- id:story-1e28248e -->
- [ ] Implement Task 1 of the ticket-driven-approval-auto-resume plan: add an `approval_tickets` table to synlynk's SQLite schema. Follow strict TDD — write the failing test first, confirm it fails, impleme [backend] <!-- id:approval-tickets-task1 -->
- [ ] # Task 2: DB helper functions in `synlynk/db.py`

This is Task 2 of a 5-task plan implementing ticket-driven approval auto-resume for synlynk's `tpm sweep` command. Task 1 (the `approval_tickets` tabl [backend] <!-- id:approval-tickets-task2 -->
- [ ] # Task 3: Wire ticket-check logic into `run_sweep_pass()`

This is Task 3 of a 5-task plan implementing ticket-driven approval auto-resume for synlynk's `tpm sweep` command. Task 1 (the `approval_tick [testing] <!-- id:approval-tickets-task3 -->
- [ ] ticket-auto-resume dogfood demo [backend] <!-- id:story-becf09a5 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-24-pm-competitive-intelligence-sweep.md: 'pm_agent.py — config loading and prompt composition'.

Files: Create synlynk/pm_agent.py, Test tests/test_p [ml] <!-- id:story-adhoc-1787554839 -->
- [ ] Implement Task 2 of the PM competitive-intelligence sweep plan (docs/superpowers/plans/2026-08-24-pm-competitive-intelligence-sweep.md): add `_invoke_headless_claude` and `cmd_pm_sweep` to the existin [ml] <!-- id:story-adhoc-1787555292 -->
- [ ] Implement Task 3 of the PM competitive-intelligence sweep plan (docs/superpowers/plans/2026-08-24-pm-competitive-intelligence-sweep.md): wire `synlynk pm sweep` into `synlynk/cli.py`. `synlynk/pm_agen [ml] <!-- id:story-adhoc-1787555486 -->
- [ ] Implement Task 4 of the PM competitive-intelligence sweep plan (docs/superpowers/plans/2026-08-24-pm-competitive-intelligence-sweep.md): seed the competitive-intelligence config and living comparison  [frontend] <!-- id:story-adhoc-1787555732 -->
- [ ] PM competitive-intel sweep Task 6: PM charter revision.

Files:
- Modify: synlynk/agent_cli.py:14
- Test: tests/test_agent_cli.py

Step 1: Run: grep -n 'SEED_CHARTERS\[.pm.\]|SEED_CHARTERS\["pm"\]' te [testing] <!-- id:story-adhoc-1787556076 -->
- [ ] Fix test_taxonomy.py::test_taxonomy_matches_real_cli_surface failure.

The full test suite currently fails with:
AssertionError: cli.py commands with no taxonomy entry: {'pm sweep'}

This is because s [backend] <!-- id:story-adhoc-1787556735 -->
- [ ] feat: PM competitive-intelligence sweep (weekly cron, living comparison doc, decide-round pipeline) [backend] <!-- id:story-issue-1159 -->
- [ ] Fix pre-existing stale version assertion in tests/test_synlynk.py. The test test_version_is_0120 (around line 2692) asserts 'assert synlynk.VERSION == "0.16.0"' but synlynk/_constants.py now defines V [testing] <!-- id:story-adhoc-1787586610 -->
- [ ] Do exactly this, in order, with minimal investigation — you already reviewed this PR twice before and found real issues that are now fixed, so do NOT re-investigate from scratch:

1. Run: git diff mai [ml] <!-- id:story-adhoc-1787589654 -->
- [ ] [LIVE-7] Worktrees don't inherit .synlynk/github_apps/ — headless gh-write dispatch silently unusable per-worktree [ml] <!-- id:story-issue-1160 -->
- [ ] fix: worktree gh-write dispatch falls back to main repo's github_apps [backend] <!-- id:story-issue-1164 -->
- [ ] Implement Task 1 of the LIVE-6 (#1140) fix plan: split `get_installation_token()` in `synlynk/github_app_auth.py` into two functions, `refresh_installation_token()` and `read_cached_installation_token [backend] <!-- id:1140-task1-github-app-auth-split -->
- [ ] This is a fix-up on top of your own prior commit `9b464cd` ("refactor(github-app-auth): split get_installation_token into refresh/read-cache pair") and `eb27d26`, which are already the tip of your cur [backend] <!-- id:1140-task1-fixup-naming-logs-import -->
- [ ] Implement Task 2 of the LIVE-6 (#1140) plan: make `synlynk/daemon.py`'s `WatchDaemon` refresh every provisioned role's GitHub App installation token on a timer, reading/writing via the already-existin [backend] <!-- id:1140-task2-daemon-token-refresh -->
- [ ] Implement Task 3 of the LIVE-6 (#1140) plan: repoint `synlynk/dispatch.py` to read GitHub App installation tokens from the daemon-maintained on-disk cache instead of minting them inline (which was the [backend] <!-- id:1140-task3-dispatch-cache-read -->
- [ ] Implement Task 4 of the LIVE-6 (#1140) plan: make `synlynk identity init --role <role>` seed the GitHub App token cache immediately after provisioning a role, so the role has an immediately-usable cac [backend] <!-- id:1140-task4-identity-init-token-seed -->
- [ ] [LIVE-6] Claude Code auto-mode classifier blocks dispatch with real GitHub App credentials, forcing manual implementation fallback [backend] <!-- id:story-issue-1140 -->
- [ ] [LIVE-8] Grok non-authoring PR reviews repeatedly stall/get cancelled right before the terminal gh pr review write [testing] <!-- id:story-issue-1166 -->
- [ ] fix: ticket-auto-resume dogfood demo (job-e8277299) [security] <!-- id:story-issue-1150 -->
- [ ] Fix a macOS Objective-C fork-safety crash in `synlynk/daemon.py` that makes `synlynk daemon start` (and `synlynk watch`) die silently within seconds on macOS.

## Root cause (already confirmed via liv [backend] <!-- id:story-adhoc-1787635875 -->
- [ ] fix(policy): add missing 'review' task_allocation entry (#1166) [backend] <!-- id:story-issue-1175 -->
- [ ] docs: log PR backlog triage + LIVE-8 verification fix [testing] <!-- id:story-issue-1176 -->
- [ ] Codex dispatch: workspace-write sandbox blocks package installs/.venv setup (network + writable-root scope), no parity check catches it [backend] <!-- id:story-issue-340 -->
- [ ] fix(#340): gate Codex sandbox network access behind explicit permission [testing] <!-- id:story-issue-1180 -->
- [ ] Auto-PR-creation skips real implementation jobs when requires_gh_write=True (found during #340 fix, job-7289479d) [testing] <!-- id:story-issue-1181 -->
- [ ] Fix a bug in synlynk/jobs.py: the function _maybe_open_worktree_pr() (around line 334-344) currently skips automatically opening a branch-publish request whenever job.requires_gh_write is True and job [testing] <!-- id:story-adhoc-1787697077 -->
- [ ] fix(#1181): base auto-PR-creation skip on actual worktree diff, not requires_gh_write flag [backend] <!-- id:story-issue-1182 -->
- [ ] fix(#860): resolve gh-write verification targets from task text [backend] <!-- id:story-issue-1183 -->
- [ ] fix(#1124): stop branch-protection sync from re-enabling enforce_admins [testing] <!-- id:story-issue-1186 -->
- [ ] jobs --all crashes: TypeError comparing offset-naive and offset-aware datetimes in gh_write_verified [backend] <!-- id:story-issue-1184 -->
- [ ] No backfill path to register an existing project into the instructions-drift manifest [testing] <!-- id:story-issue-1191 -->
- [ ] Implement Task 1 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("charter_schema.py — constants, frontmatter split/parse, CharterValidationError").

Read that file's Tas [ml] <!-- id:story-adhoc-1787854705 -->
- [ ] Implement Task 2 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("charter_schema.py — dispatch_routing rendering and frontmatter-block editing").

Task 1 is already merg [testing] <!-- id:story-adhoc-1787854883 -->
- [ ] Implement Task 3 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("Wire validate_charter into agent_store.propose_charter_revision").

Tasks 1 and 2 are already merged: s [testing] <!-- id:story-adhoc-1787854994 -->
- [ ] Implement Task 4 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("Retire the .synlynk/agents/<id>.yaml projection mechanism").

Tasks 1-3 are already merged: synlynk/cha [ml] <!-- id:story-adhoc-1787855319 -->
- [ ] Implement Task 5 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("agent_store.sync_dispatch_routing()").

Tasks 1-4 are already merged: synlynk/charter_schema.py has ful [backend] <!-- id:story-adhoc-1787855486 -->
- [ ] Implement Task 6 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("Rewrite SEED_CHARTERS + agent_cli.py handlers").

Tasks 1-5 are already merged: synlynk/charter_schema. [ml] <!-- id:story-adhoc-1787855615 -->
- [ ] Implement Task 7 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("Wire agent sync-routing into cli.py").

Tasks 1-6 are already merged. synlynk/agent_cli.py now has cmd_ [testing] <!-- id:story-adhoc-1787856083 -->
- [ ] Implement Task 8 of the plan at docs/superpowers/plans/2026-08-27-charter-content-structure.md ("CHANGELOG.md entry").

Tasks 1-7 are already merged: full charter schema validation, dead projection me [docs] <!-- id:story-adhoc-1787856372 -->
- [ ] test_agy_dispatch_fix.py org_domain remap test fails on main (regression from #1189) [backend] <!-- id:story-issue-1197 -->
- [ ] fix: skip harness fence rewrite when content is unchanged [backend] <!-- id:story-issue-1204 -->
- [ ] fix: #1197 restore org_domain remap on already-migrated connections [testing] <!-- id:story-issue-1205 -->
- [ ] chore: incorporate agent-workers content into capability routing design (v0.5.0) [ml] <!-- id:story-issue-33 -->
- [ ] fix: dispatch writes per-job context to .synlynk/contexts/<job_id>.md (story-5b86c353) [ml] <!-- id:story-issue-67 -->
- [ ] docs: retroactive RCAs for LIVE-9 (#1184) and LIVE-10 (#1185) [testing] <!-- id:story-issue-1206 -->
- [ ] fix: Fix a CI trigger gap in .github/workflows/site.yml t (job-af3b9bea) [ml] <!-- id:story-issue-1207 -->
- [ ] fix: Fix malformed YAML frontmatter in 11 blog post files (job-69fa441b) [ml] <!-- id:story-issue-1208 -->
- [ ] codex dispatch fails: --ask-for-approval rejected by installed Codex CLI (codex exec) [testing] <!-- id:story-issue-1209 -->
- [ ] macOS launchd daemon service has KeepAlive=false — daemon doesn't auto-restart after crash, GH App tokens go stale [backend] <!-- id:story-issue-1211 -->
- [ ] docs: recover 2 decision records lost to gitignored write path [testing] <!-- id:story-issue-1195 -->
- [ ] docs: session topic discipline & cross-harness context transfer design spec [testing] <!-- id:story-issue-1214 -->
- [ ] docs: ticket-driven approval auto-resume design spec + implementation plan [testing] <!-- id:story-issue-1215 -->
- [ ] docs: resync todo.md with current project state [testing] <!-- id:story-issue-1216 -->
- [ ] Fix checkpoint() todo.md handling: it bypasses the stories table and the migration-aware _generate_todo_md() generator (synlynk/db.py:1766), and hardcodes a non-migration-aware todo_path literal at sy [backend] <!-- id:1218 -->
- [ ] Fix 3 test regressions in the checkpoint() todo.md rewrite (branch dispatch/codex/job-1390603b, worktree already has the archived_at/stories-table change). Full pytest run against this branch shows 3  [backend] <!-- id:story-adhoc-1787972450 -->
- [ ] fix: checkpoint() todo.md handling bypasses stories table + hardcodes migration-unaware path (#1218) [backend] <!-- id:story-issue-1224 -->
- [ ] Add a new SOP section, "Herdr Workspace Protocol", to synlynk's Harness Instructions fence generator in synlynk/probe.py.

CONTEXT: synlynk/probe.py contains SOP_SECTION_HEADERS (list of "## ..." head [testing] <!-- id:story-adhoc-1787986723 -->
- [ ] synlynk daemon (GitHub App token refresher) does not persist/stay running between sessions [testing] <!-- id:story-issue-1228 -->
- [ ] Wire charter content into dispatch/execution context (implement PR #1193's surfacing mechanism) [testing] <!-- id:story-issue-1201 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is the first chapter
of Part I ("What This Actually Is") of a repositioned [frontend] <!-- id:story-adhoc-1787990308 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is the second
chapter of Part I ("What This Actually Is") of a repositione [frontend] <!-- id:story-adhoc-1787990318 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is the third
chapter of Part I ("What This Actually Is") of a repositioned [frontend] <!-- id:story-adhoc-1787990328 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is Part 0 of a
repositioned nonfiction book ("The Supervised Machine") abo [frontend] <!-- id:story-adhoc-1787990432 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is Part 0 of a
repositioned nonfiction book ("The Supervised Machine") abo [frontend] <!-- id:story-adhoc-1787990707 -->
- [ ] docs(book): Part 0 + Part I multi-author chapters, v0.3-DRAFT [frontend] <!-- id:story-issue-1239 -->
- [ ] docs(blog): PR #1239 post — The Book Gets Co-Authors [testing] <!-- id:story-issue-1241 -->
- [ ] docs: keep README synchronized during named releases [testing] <!-- id:story-issue-1242 -->
- [ ] Implement the single implementation task in the plan file already committed on this branch under docs/superpowers/plans/ (filename starts 2026-08-29-doctor-pr) — read that file directly, do not re-der [testing] <!-- id:issue-1200 -->
- [ ] Execute the plan at docs/superpowers/plans/2026-08-29-harness-agent-terminology-sweep.md, Tasks 1 and 2 only (the prose sweep). Task 3 is a separate follow-up and not part of this dispatch. Follow the [backend] <!-- id:story-adhoc-1788007770 -->
- [ ] fix: Fix #1140 (reopened): synlynk daemon start still doe (job-352c9929) [backend] <!-- id:story-issue-1249 -->
- [ ] dispatch job summaries report 'files: 0 touched' despite real committed work landing [backend] <!-- id:story-issue-1250 -->
- [ ] Follow-up to synlynk tracking item 1202 terminology sweep: fix 8 remaining help= string wording misses in synlynk/cli.py that a spec-compliance check flagged. Change ONLY the help= string text on thes [backend] <!-- id:story-adhoc-1788010223 -->
- [ ] fix: #1250 dispatch job summaries silently report 'files: 0 touched' [testing] <!-- id:story-issue-1251 -->
- [ ] Standardize harness vs. agent terminology across the codebase and docs [backend] <!-- id:story-issue-1202 -->
- [ ] docs: standardize Harness vs Agent terminology in synlynk/*.py (#1202) [backend] <!-- id:story-issue-1256 -->
- [ ] Implement Task 1 of docs/superpowers/plans/2026-08-29-charter-corpus-references.md exactly as written: read the corpus (devlog, memory, git log per the plan's greps), create docs/charters/corpus-refer [testing] <!-- id:story-adhoc-1788016260 -->
- [ ] Implement Task 2 of docs/superpowers/plans/2026-08-29-charter-corpus-references.md exactly as written: read the corpus (devlog, memory, git log per the plan's greps) for tpm/designer/marketing, append [testing] <!-- id:story-adhoc-1788016438 -->
- [ ] fix: Fix #1228 (synlynk daemon does not persist between s (job-78d04989) [testing] <!-- id:story-issue-1258 -->
- [ ] fix: Fix gh:#1228 — synlynk daemon state paths are CWD-re (job-24507a4d) [testing] <!-- id:story-issue-1232 -->
- [ ] docs: ground 6 charter roles in project corpus (#1199) [backend] <!-- id:story-issue-1262 -->
- [ ] fix: Implement Task 2 of docs/superpowers/plans/2026-08-2 (job-f4c16542) [testing] <!-- id:story-issue-1260 -->
- [ ] Execute the plan at docs/superpowers/plans/2026-08-29-codex-direct-gh-write-network-access.md to implement direct Codex GitHub-write network access via config override. Follow Task 1 and Task 2 step-b [testing] <!-- id:story-adhoc-1788027017 -->
- [ ] feat: direct Codex GitHub-write network access via config override (#1268) [testing] <!-- id:story-issue-1271 -->
- [ ] fix: Review PR #1271: Inspect diff against main. Run test (job-b3492d49) [testing] <!-- id:story-issue-1272 -->
- [ ] Execute the implementation plan at docs/superpowers/plans/2026-08-30-codex-full-harness-parity.md step-by-step: 1. Update tests in tests/test_synlynk.py, tests/test_dispatch.py, and tests/test_agent_c [testing] <!-- id:story-adhoc-1788029337 -->
- [ ] Execute the implementation plan at docs/superpowers/plans/2026-08-30-grok-headless-permission-mode.md step-by-step: 1. Add unit tests in tests/test_dispatch.py asserting _grok_permission_flags emits - [testing] <!-- id:story-adhoc-1788056522 -->
- [ ] synlynk daemon crashes immediately on macOS (objc NSNumber initialize + fork) [backend] <!-- id:story-issue-1263 -->
- [ ] fix: daemon re-exec fork-safety + worktree-aware token cache path (#1263, #1264) [backend] <!-- id:story-issue-1282 -->
- [ ] Design GOVERNS backlog automation: auto-associate discovered/open/planned work with issues [testing] <!-- id:story-issue-1203 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.3-DRAFT.html. This is Part II ("The
Onboarding") of a repositioned nonfiction book ("The Supe [frontend] <!-- id:story-adhoc-1788072792 -->
- [ ] Write one short, self-contained, credited subsection (NOT a full chapter)
as an HTML fragment, for insertion inside Part II ("The Onboarding") of the
manuscript at docs/book/the-supervised-machine-v0. [frontend] <!-- id:story-adhoc-1788072806 -->
- [ ] Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.3-DRAFT.html. This is Part II ("The
Onboarding") of a repositioned nonfiction book ("The Supe [frontend] <!-- id:story-adhoc-1788072929 -->
- [ ] Write one short, self-contained, credited subsection (NOT a full chapter)
as an HTML fragment, for insertion inside Part II ("The Onboarding") of the
manuscript at docs/book/the-supervised-machine-v0. [frontend] <!-- id:story-adhoc-1788072940 -->
- [ ] docs(book): Part II Onboarding chapter, v0.4-DRAFT [frontend] <!-- id:story-issue-1292 -->
- [ ] Instrument real readership analytics for book/blog (time-spent + downloads/reads) — prerequisite for goal-0c4e96ff [devops] <!-- id:story-33ab504a -->
- [ ] Execute Task 1 and Task 2 from docs/superpowers/plans/2026-08-30-marketing-goal-ownership-plan.md, in order, exactly as written. Read that plan file first.

Task 1: Add a "marketing" entry to the agen [testing] <!-- id:story-adhoc-1788081076 -->
- [ ] Execute Task 3 and Task 4 from docs/superpowers/plans/2026-08-30-marketing-goal-ownership-plan.md, in order, exactly as written. Read that plan file first.

Task 3: Edit the SEED_CHARTERS["marketing"] [testing] <!-- id:story-adhoc-1788081084 -->
- [ ] Fix a real gap found during review of the marketing-goal-ownership feature (docs/superpowers/plans/2026-08-30-marketing-goal-ownership-plan.md, now merged into this branch).

synlynk/db.py:88 defines: [testing] <!-- id:story-adhoc-1788081237 -->
- [ ] codex dispatch fails: hardcoded approval_policy=untrusted rejected by codex-cli 0.150.1 [testing] <!-- id:story-issue-1293 -->
- [ ] Implement docs/superpowers/plans/2026-08-29-governs-backlog-automation.md task-by-task in order (Task 1 through Task 4), exactly as written: TDD (failing test, verify fail, implement, verify pass, com [testing] <!-- id:governs-backlog-automation -->
- [ ] fix: replace hardcoded codex approval_policy=untrusted with -s read-only [testing] <!-- id:story-issue-1302 -->
- [ ] fix: grant qa App administration:write for merge roles (gh:#1295) [testing] <!-- id:story-issue-1303 -->
- [ ] Standardize Harness vs Workspace Agent separation across CLI flags, configs, and documentation (#1255) [backend] <!-- id:story-a646edf9 -->
- [ ] Write a 3-bullet status update summarizing a completed feature. [backend] <!-- id:story-adhoc-1788105905 -->
- [ ] Standardize Harness vs Workspace Agent separation across CLI flags, configs, and docs (#1255) [backend] <!-- id:story-issue-1306 -->
- [ ] Fleet Parity: Grok --cwd and Codex -C working directory protection (#342) [backend] <!-- id:story-e66de65c -->
- [ ] Fleet Parity: Enforce --cwd for Grok and -C for Codex with working-directory prompt header (#342) [testing] <!-- id:story-issue-1308 -->
- [ ] Preflight verification that dispatched agent loaded instruction file (#347) [backend] <!-- id:story-e5383d22 -->
- [ ] Fleet Parity: Instruction file preflight presence check and closed-loop receipt verification (#347) [testing] <!-- id:story-issue-1309 -->
- [ ] Run unit tests [testing] <!-- id:story-adhoc-1788196986 -->
- [ ] explo: accelerated multi-agent swarm & fleet orchestration engine (#1326) [backend] <!-- id:story-95238497 -->
- [ ] Agy cannot call Stitch MCP tools (mcp__stitch__*) in headless dispatch [backend] <!-- id:story-issue-573 -->
- [ ] fix: Resolve the remaining correction for ticket 1242 on (job-6e5d67d4) [frontend] <!-- id:story-issue-1247 -->
- [ ] docs: complete archive of PR 1304 [testing] <!-- id:story-issue-1352 -->
- [ ] Read all five Part III ("Field Notebook") chapters of the book manuscript
and add a running fact-check/rigor annotation layer across them, per your
own role in the design doc at
docs/superpowers/specs [frontend] <!-- id:story-adhoc-1788371277 -->
- [ ] docs: integrate Strategic Review content into the book manuscript [frontend] <!-- id:story-issue-1374 -->
- [ ] config(fleet): grant Codex full harness parity across review and gh-write tasks [backend] <!-- id:story-issue-1274 -->
- [ ] fix: restore Codex review network access [backend] <!-- id:story-issue-1375 -->
- [ ] docs: devlog entry for PR #1374 merge verification + #1274 fix chain [testing] <!-- id:story-issue-1376 -->
- [ ] Job self-report status unreliable — 3rd recurrence, 5 new false-negative instances in one session (2026-09-04) [testing] <!-- id:story-issue-1377 -->
- [ ] docs: record decision-panel outcome for Model/ModelFamily as first-class citizens [testing] <!-- id:story-issue-1378 -->
- [ ] Job status: PR-open gh-write jobs hardcode gh_write_expect='closed', causing deterministic false succeeded_gh_write_failed [testing] <!-- id:story-issue-1379 -->
- [ ] fix: verify PR-open GitHub writes [testing] <!-- id:story-issue-1384 -->
- [ ] Job status: killed_zombie hard-codes failure from PID/worktree shape, bypasses gh-write verifier entirely [testing] <!-- id:story-issue-1382 -->
- [ ] fix: verify gh writes before killed zombie status [testing] <!-- id:story-issue-1385 -->
- [ ] Job status: timed_out is finalized before exit-marker/GTV check, causing premature failure labels [testing] <!-- id:story-issue-1381 -->
- [ ] fix: retry and capture gh review verification evidence [backend] <!-- id:story-issue-1386 -->
- [ ] Job status: daemon_jobs (SQLite) and jobs.json split-brain leaves stuck-running jobs with no repair path [backend] <!-- id:story-issue-1383 -->
- [ ] fix: verify gh writes before timeout finalization [testing] <!-- id:story-issue-1387 -->
- [ ] fix: reconcile terminal jobs across sqlite and jobs.json [backend] <!-- id:story-issue-1388 -->
- [ ] Research virtualized VCS workspace backends (EdenFS, Sapling, sparse checkouts) for multi-agent dispatch [backend] <!-- id:story-ebdc2894 -->
- [ ] Research OS-level sandboxing (Bubblewrap, rootless Docker, sandbox-exec) and credential isolation for agent execution [security] <!-- id:story-f6e126fd -->
- [ ] Research SCIP indexers, Tree-sitter symbol graphs, and Glean-compatible code intelligence for context assembly [backend] <!-- id:story-4949989b -->
- [ ] Research 3-way AST semantic merge algorithms and speculative rebase trees for concurrent agent branches [backend] <!-- id:story-1b212bfd -->
- [ ] Research distributed state.db synchronization protocols (LiteFS, CRDTs, gRPC relay) and enterprise cost aggregation [backend] <!-- id:story-d58e5033 -->
- [ ] Brainstorm virtualized workspace lifecycle and sparse worktree architecture in synlynk [architecture] <!-- id:story-031c1bef -->
- [ ] Brainstorm unified sandbox provider architecture and secret boundary enforcement for multi-agent fleets [security] <!-- id:story-b1f1a8bf -->
- [ ] Brainstorm SCIP-backed code knowledge graph indexing and dynamic symbol context injection in synlynk [architecture] <!-- id:story-575700b8 -->
- [ ] Brainstorm speculative rebase queue and automated merge conflict resolution engine in synlynk [architecture] <!-- id:story-4d00cbae -->
- [ ] Brainstorm enterprise team workspace sync architecture and centralized multi-tenant governance [architecture] <!-- id:story-2c19bbad -->
- [ ] docs: BS-5 website redesign design phase complete [frontend] <!-- id:story-issue-71 -->
- [ ] chore: gitignore node_modules and stray state.db [testing] <!-- id:story-issue-1410 -->
- [ ] docs(book): sync PDF-export pipeline to synlynk doc style system [frontend] <!-- id:story-issue-1411 -->
- [ ] Job status: add real-gh-write end-to-end regression test (job-status truth pipeline) [backend] <!-- id:story-issue-1414 -->
- [ ] Stall-kill signals a raw stored PID with no identity check — risk of killing an unrelated recycled process [testing] <!-- id:story-issue-352 -->
- [ ] Job Lifecycle epic fix didn't cover the daemon_jobs reconciliation path [backend] <!-- id:story-issue-136 -->
- [ ] Orphaned dispatched child process survives daemon crash; no lock against concurrent daemon instances [backend] <!-- id:story-issue-349 -->
- [ ] Vizor and daemon HTTP servers have zero authentication — POST /dispatch is CSRF-exploitable from any browser tab [frontend] <!-- id:story-issue-355 -->
- [ ] test: add end-to-end job status truth regression [testing] <!-- id:story-issue-1415 -->
- [ ] Review PR # (, off docs/distinguished-engineer-review): run synlynk pr check from the PR's own worktree, confirm the research/spec doc content is legitimate and well-formed. DO NOT MERGE — approve onl [docs] <!-- id:story-adhoc-1788546595 -->
- [ ] fix: ## Permissions (job-d6b97dea) [docs] <!-- id:story-issue-1404 -->
- [ ] fix: ## Permissions (job-a7ba87c1) [docs] <!-- id:story-issue-1405 -->
- [ ] fix: ## Permissions (job-317f2a93) [docs] <!-- id:story-issue-1406 -->
- [ ] fix: ## Permissions (job-4010ba49) [docs] <!-- id:story-issue-1407 -->
- [ ] fix: ## Permissions (job-7c8c84f5) [docs] <!-- id:story-issue-1408 -->
- [ ] fix: Execute the implementation plan at docs/superpowers/ (job-4ba2fb42) [backend] <!-- id:story-issue-1278 -->
- [ ] fix: Execute the implementation plan at docs/superpowers/ (job-56f6ecec) [backend] <!-- id:story-issue-1287 -->
- [ ] fix: Write one short, self-contained, credited subsection (job-cee83fda) [backend] <!-- id:story-issue-1290 -->
- [ ] fix: ## Permissions (job-e298e474) [backend] <!-- id:story-issue-1291 -->
- [ ] fix: Execute Task 3 and Task 4 from docs/superpowers/plan (job-56aa11ba) [backend] <!-- id:story-issue-1296 -->
- [ ] fix: Execute Task 1 and Task 2 from docs/superpowers/plan (job-5462edb4) [backend] <!-- id:story-issue-1297 -->
- [ ] fix: Fix a real gap found during review of the marketing- (job-49d70a0b) [backend] <!-- id:story-issue-1298 -->
- [ ] fix: Fix a duplicate-flag regression in synlynk/dispatch. (job-5c780ac4) [backend] <!-- id:story-issue-1305 -->
- [ ] fix: Implement issue #1188: Detect and warn on stale pipx (job-cd49c562) [backend] <!-- id:story-issue-1323 -->
- [ ] fix: Implement issue #937: Review-dispatch permissions ha (job-455385e6) [backend] <!-- id:story-issue-1328 -->
- [ ] fix: ## Permissions (job-e73d175d) [backend] <!-- id:story-issue-1329 -->
- [ ] fix: Implement issue #1327: Deduplicate boolean CLI flags (job-a24af5b3) [backend] <!-- id:story-issue-1333 -->
- [ ] fix: ## Permissions (job-9c597160) [backend] <!-- id:story-issue-1334 -->
- [ ] fix: Implement Phase 1 and Phase 2 of Issue #1343 per doc (job-d6812ef1) [backend] <!-- id:story-issue-1344 -->
- [ ] fix: ## Permissions (job-8575a177) [backend] <!-- id:story-issue-1354 -->
- [ ] fix: Implement Cross-Harness Inter-Agent Event Relay per (job-38bb3618) [backend] <!-- id:story-issue-1357 -->
- [ ] fix: Implement Living Charter Evolution & Capability-Gate (job-4bf9c7e6) [backend] <!-- id:story-issue-1359 -->
- [ ] fix: ## Permissions (job-e2061c9a) [backend] <!-- id:story-issue-1361 -->
- [ ] chore: archive unmerged blog-index backfill diff [backend] <!-- id:story-issue-1364 -->
- [ ] fix: Implement Ephemeral Swarm Cloud Runner Drivers per d (job-006f075f) [backend] <!-- id:story-issue-1365 -->
- [ ] docs(book): Part III Field Notebook restructuring, v0.5-DRAFT [frontend] <!-- id:story-issue-1368 -->
- [ ] fix: ## Permissions (job-723928d6) [backend] <!-- id:story-issue-1370 -->
- [ ] fix: Implement Autonomous Remediation Loop (synlynk heal) (job-89bd001e) [backend] <!-- id:story-issue-1371 -->
- [ ] Non-authoring review of PR # ("") on branch . From within this PR's own checked-out worktree/branch, run 'synlynk pr check' to auto-detect the PR via git/gh context. Independently verify the PR's actu [backend] <!-- id:story-adhoc-1788582350 -->
- [ ] Non-authoring review of PR # ("") on branch . From within this PR's own checked-out worktree/branch, run 'synlynk pr check' to auto-detect the PR via git/gh context. Independently verify the PR's actu [backend] <!-- id:story-adhoc-1788599513 -->
- [ ] chore: add EPUB build as default book output alongside PDF [frontend] <!-- id:story-issue-1430 -->
- [ ] [Platform:Codex] Generate Codex-native AGENTS.md during init [frontend] <!-- id:story-issue-5 -->
- [ ] chore: add synlynk glyph to book cover [frontend] <!-- id:story-issue-1434 -->
- [ ] chore: regenerate book PDF/EPUB with glyph cover [frontend] <!-- id:story-issue-1437 -->
- [ ] docs: blog post for PR #1434 (book glyph cover) [frontend] <!-- id:story-issue-1438 -->
- [ ] docs: update blog post — PR #1437 merged [frontend] <!-- id:story-issue-1439 -->
- [ ] fix: do not mark daemon jobs permission_denied after corroborated success [backend] <!-- id:story-issue-1441 -->
- [ ] fix: gh-write verifier leftovers from LIVE-1429 [testing] <!-- id:story-issue-1444 -->
- [ ] docs: blog post for PR #1415 (job status end-to-end regression test) [testing] <!-- id:story-issue-1431 -->
- [ ] fix: skip injected ## Permissions when auto-finalizing PR titles [testing] <!-- id:story-issue-1447 -->
- [ ] Non-authoring review of PR #1449 (https://github.com/nikhilsoman/synlynk/pull/1449). You are QA. You did not author this PR (Grok did). Do not push code changes. Do not merge. Review only. Do not open [testing] <!-- id:story-issue-1449 -->
- [ ] Non-authoring review of PR #1450 (https://github.com/nikhilsoman/synlynk/pull/1450). You are QA. You did not author this PR (Grok did). Do not push code changes. Do not merge. Review only. Do not open [testing] <!-- id:story-issue-1450 -->
- [ ] Non-authoring review of PR #1451 (https://github.com/nikhilsoman/synlynk/pull/1451). You are QA. You did not author this PR (Grok did). Do not push. Do not merge. Review only. Do not open a new PR.

E [security] <!-- id:story-issue-1451 -->
- [ ] Non-authoring review of PR #1452 (https://github.com/nikhilsoman/synlynk/pull/1452). You are QA. You did not author this PR (Grok did). Do not push. Do not merge. Review only. Do not open a new PR.

B [testing] <!-- id:story-issue-1452 -->
- [ ] Non-authoring review of PR #1453 (https://github.com/nikhilsoman/synlynk/pull/1453). You are QA. You did not author this PR (Grok did). Do not push. Do not merge. Review only. Do not open a new PR.

B [testing] <!-- id:story-issue-1453 -->
- [ ] Non-authoring review of PR #1454 (https://github.com/nikhilsoman/synlynk/pull/1454). You are QA. You did not author this PR (Grok did). Do not push. Do not merge. Review only. Do not open a new PR.

B [testing] <!-- id:story-issue-1454 -->
- [ ] Implement #1436 leftover: charter patch so architect does not hold merge authority.

Issue: https://github.com/nikhilsoman/synlynk/issues/1436
Approved spec: docs/superpowers/specs/2026-09-06-workspac [testing] <!-- id:story-issue-1436 -->
- [ ] Non-authoring review of PR #1455 (https://github.com/nikhilsoman/synlynk/pull/1455). You are QA. Codex authored this as synlynk-synlynk-dev[bot]. This is the #1436 live cell: qa MUST `gh pr review --a [security] <!-- id:story-issue-1455 -->
- [ ] Non-authoring review of PR #1456 (https://github.com/nikhilsoman/synlynk/pull/1456). You are QA. Agy authored (job-6db3944d). Do not push. Do not merge. Do not open a new PR. Expected HEAD: 3d9060ad90 [security] <!-- id:story-issue-1456 -->
- [ ] Non-authoring review of PR #1457 (https://github.com/nikhilsoman/synlynk/pull/1457). You are QA. Agy authored (job-f0ef526b). Do not push. Do not merge. Do not open a new PR. Expected HEAD: 575eb8a293 [security] <!-- id:story-issue-1457 -->
- [ ] Non-authoring review of PR #1458 (https://github.com/nikhilsoman/synlynk/pull/1458). You are QA. Codex authored (job-697d53cd). Do not push. Do not merge. Do not open a new PR. Expected HEAD: 9d41a0e7 [testing] <!-- id:story-issue-1458 -->
- [ ] feat(book): make EPUB output Apple Books-ready [frontend] <!-- id:story-issue-1463 -->
- [ ] Non-authoring QA of PR #1467 (https://github.com/nikhilsoman/synlynk/pull/1467). Codex authored as synlynk-synlynk-dev[bot]. Do not push. Do not merge. Do not open a new PR. Expected HEAD: 7273b64dbb7 [testing] <!-- id:story-issue-1467 -->
- [ ] Non-authoring QA of PR #1464 (https://github.com/nikhilsoman/synlynk/pull/1464). Codex authored as synlynk-synlynk-dev[bot]. Do not push. Do not merge. Do not open a new PR. Expected HEAD: 32837007a75 [testing] <!-- id:story-issue-1464 -->
- [ ] Non-authoring QA of PR #1465 (https://github.com/nikhilsoman/synlynk/pull/1465). Agy authored as synlynk-synlynk-architect[bot]. Do not push. Do not merge. Do not open a new PR. Expected HEAD: d24e4c4 [security] <!-- id:story-issue-1465 -->
- [ ] Non-authoring QA of PR #1466 (https://github.com/nikhilsoman/synlynk/pull/1466). Agy authored as synlynk-synlynk-marketing[bot]. Do not push. Do not merge. Do not open a new PR. Expected HEAD: aae19fc [security] <!-- id:story-issue-1466 -->
- [ ] Non-authoring QA of PR #1472 (https://github.com/nikhilsoman/synlynk/pull/1472). Codex authored as synlynk-synlynk-dev[bot]. Do not push. Do not merge. Do not open a new PR. Expected HEAD: 6b0dd707296 [testing] <!-- id:story-issue-1472 -->
- [ ] Non-authoring QA of PR #1471 (https://github.com/nikhilsoman/synlynk/pull/1471). Agy authored as synlynk-synlynk-marketing[bot]. Do not push. Do not merge. Do not open a new PR. Expected HEAD: a531201 [testing] <!-- id:story-issue-1471 -->
- [ ] test: isolate archived pytest modules [testing] <!-- id:story-issue-1474 -->
- [ ] Allow distinct QA App identities to submit approving PR reviews [backend] <!-- id:story-issue-1475 -->
- [ ] fix(review): allow distinct QA App identities to submit approving PR reviews (#1475) [backend] <!-- id:story-issue-1476 -->
- [ ] Write a 3-bullet status update summarizing a completed feature. [backend] <!-- id:story-adhoc-1788745962 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745963 -->
- [ ] Triage this bug report into a GitHub issue with severity and repro steps: a general scenario at intermediate difficulty [backend] <!-- id:story-adhoc-1788745965 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745966 -->
- [ ] Draft a roadmap section reconciling two conflicting stakeholder priorities: a general scenario at advanced difficulty [backend] <!-- id:story-adhoc-1788745967 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745969 -->
- [ ] List the trade-offs between two database indexing strategies for a general scenario at basic difficulty. [backend] <!-- id:story-adhoc-1788745970 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745972 -->
- [ ] Design a data model for a general scenario at intermediate difficulty with at least 2 tables and their relationships. [backend] <!-- id:story-adhoc-1788745973 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745975 -->
- [ ] Review this system design for a race condition and propose a fix: a general scenario at advanced difficulty [backend] <!-- id:story-adhoc-1788745976 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745978 -->
- [ ] Break a 3-step feature into a dependency-ordered task list. [backend] <!-- id:story-adhoc-1788745979 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745980 -->
- [ ] Identify the critical path across 4 parallel workstreams: a general scenario at intermediate difficulty [backend] <!-- id:story-adhoc-1788745982 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745983 -->
- [ ] Reconcile a slipping deadline against two blocked dependencies: a general scenario at advanced difficulty [backend] <!-- id:story-adhoc-1788745985 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745986 -->
- [ ] Write a minimal Python function demonstrating a general scenario at basic difficulty. [backend] <!-- id:story-adhoc-1788745988 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745989 -->
- [ ] Fix a failing test given this stack trace: a general scenario at intermediate difficulty [testing] <!-- id:story-adhoc-1788745991 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745993 -->
- [ ] Refactor this function to remove duplication while preserving behavior: a general scenario at advanced difficulty [architecture] <!-- id:story-adhoc-1788745994 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745996 -->
- [ ] Describe a simple 3-field form layout for a general scenario at basic difficulty. [backend] <!-- id:story-adhoc-1788745998 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788745999 -->
- [ ] Propose a navigation structure for a 5-page app: a general scenario at intermediate difficulty [backend] <!-- id:story-adhoc-1788746001 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746002 -->
- [ ] Resolve a usability conflict between mobile and desktop layouts: a general scenario at advanced difficulty [backend] <!-- id:story-adhoc-1788746004 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746006 -->
- [ ] Write 3 test cases for a general scenario at basic difficulty. [testing] <!-- id:story-adhoc-1788746007 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746009 -->
- [ ] Identify an edge case this test suite misses: a general scenario at intermediate difficulty [testing] <!-- id:story-adhoc-1788746011 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746013 -->
- [ ] Design a regression test strategy for a flaky integration test: a general scenario at advanced difficulty [testing] <!-- id:story-adhoc-1788746015 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746016 -->
- [ ] Write a 1-sentence pitch for a general scenario at basic difficulty. [backend] <!-- id:story-adhoc-1788746018 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746020 -->
- [ ] Draft a changelog entry for a breaking change: a general scenario at intermediate difficulty [backend] <!-- id:story-adhoc-1788746021 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746023 -->
- [ ] Reconcile messaging across two conflicting positioning statements: a general scenario at advanced difficulty [backend] <!-- id:story-adhoc-1788746025 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746027 -->
- [ ] Summarize a devlog entry in 2 sentences. [backend] <!-- id:story-adhoc-1788746029 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746031 -->
- [ ] Detect drift between two versions of a roadmap doc: a general scenario at intermediate difficulty [backend] <!-- id:story-adhoc-1788746033 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746035 -->
- [ ] Reconcile a merge conflict in a union-merged markdown file: a general scenario at advanced difficulty [backend] <!-- id:story-adhoc-1788746037 -->
- [ ] Review this general calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [backend] <!-- id:story-adhoc-1788746039 -->
- [ ] Make live selftest provision probe metadata in scratch repos [testing] <!-- id:story-issue-1484 -->
- [ ] fix(selftest): provision probe metadata in live scratch DB [backend] <!-- id:story-issue-1485 -->
- [ ] Follow up: live selftest still lacks probe metadata in scratch DB [backend] <!-- id:story-issue-1486 -->
- [ ] Audit orphaned dispatch branches and recover useful unique commits [docs] <!-- id:story-issue-1487 -->
- [ ] Sentinel lifecycle hygiene: deduplicate alerts and enforce actionable health gates [testing] <!-- id:story-issue-1488 -->
- [ ] Triage 40 unmerged or dirty worktrees [docs] <!-- id:story-issue-1479 -->
- [ ] fix(selftest): probe cold source ledger before live dispatch [testing] <!-- id:story-issue-1490 -->
- [ ] Perf: Remediate 12-minute test suite runtime (drop EOL Python 3.8, add pytest-xdist, mock selftest probe cascade, lazy-load CLI) [testing] <!-- id:story-057d4312 -->
- [ ] fix(sentinel): unify alert persistence and expiry (#1488) [testing] <!-- id:story-issue-1493 -->
- [ ] test: minimal Python function for capability calibration (job-b60fc2e1) [testing] <!-- id:story-issue-1477 -->
- [ ] test: QA advanced flaky-integration regression strategy [testing] <!-- id:story-issue-1478 -->
- [ ] fix: Draft a roadmap section reconciling two conflicting (job-df2aee7c) [testing] <!-- id:story-issue-1480 -->
- [ ] fix: Reconcile a slipping deadline against two blocked de (job-aca06f51) [testing] <!-- id:story-issue-1481 -->
- [ ] fix: Write 3 test cases for a general scenario at basic d (job-89b5c9a1) [testing] <!-- id:story-issue-1482 -->
- [ ] fix: Detect drift between two versions of a roadmap doc: (job-8aa012b0) [testing] <!-- id:story-issue-1483 -->
- [ ] fix(dispatch): diagnose and prevent zombie worker termination (#1498) [backend] <!-- id:story-issue-1504 -->
- [ ] fix(ci): align test matrix with supported Python versions [ml] <!-- id:story-issue-1505 -->
- [ ] perf(selftest): isolate probe metadata from unit-test runs [testing] <!-- id:story-issue-1506 -->
- [ ] Plan continuous harness compatibility expansion and Meta Muse + DeepSeek onboarding [devops] <!-- id:story-9791a697 -->
- [ ] Define tactical versus durable goals and enforce goal association checks in GOVERNS [devops] <!-- id:story-620ca244 -->
- [ ] Implement sentinel-to-shipped Platform Health & Performance maintenance loop [devops] <!-- id:story-2e48a8c5 -->
- [ ] Define autonomous PM/TPM grooming and four-boundary human notification contract [devops] <!-- id:story-5dfe6b3f -->
- [ ] perf: evaluate pytest-xdist for safe test parallelism [testing] <!-- id:story-issue-1496 -->
- [ ] perf: profile CLI startup before lazy-loading imports [testing] <!-- id:story-issue-1497 -->
- [ ] Publish The Supervised Machine next draft with EPUB, cover, excerpt, and core-tenets updates [docs] <!-- id:story-c8e2b987 -->
- [ ] Synlynk 1.0.0 Developer Preview Launch Readiness: install, Vizor onboarding, project intelligence, and HN/Product Hunt [devops] <!-- id:story-1aab8f81 -->
- [ ] fix(selftest): isolate live probe provisioning [backend] <!-- id:story-issue-1517 -->
- [ ] fix: Task Group 2: capability envelope seeding + concurre (job-ecba9b0b) [testing] <!-- id:story-issue-1518 -->
- [ ] fix: Task Group 4: docs (job-424d106a) [devops] <!-- id:story-issue-1519 -->
- [ ] fix(daemon): recover stale lifecycle locks (#1523) [backend] <!-- id:story-issue-1524 -->
- [ ] platform: isolate state-DB path fallback and reconciliation write failures [backend] <!-- id:story-issue-1525 -->
- [ ] fix(state): harden sandbox DB fallback and reconciliation [backend] <!-- id:story-issue-1526 -->
- [ ] Investigate dispatch context/log inflation and anomalous worker token burn [testing] <!-- id:story-issue-1531 -->
- [ ] docs: investigate dispatch token inflation in #1531 [testing] <!-- id:story-issue-1532 -->
- [ ] BS-6 brainstorm: design the product, logical, and infrastructure views for Synlynk repository/workspace visualization. Produce an approved-scope design/spec artifact only; inspect current visualizatio [devops] <!-- id:story-adhoc-1788972982 -->
- [ ] fix(worktree): guard empty branch in _gh_pr_for_branch and recognize squash-merged branches via git cherry (#1536) [backend] <!-- id:story-7e09d930 -->
- [ ] feat(viz): implement BS-6 Repo & Workspace Views visualizer from approved design spec (#1539) [backend] <!-- id:story-f8380ea0 -->
- [ ] Epic: Layered Release Protocol, Control-Plane Resilience & Autonomous Execution (Sprints 1-4, #1543) [architecture] <!-- id:story-c5205e03 -->
- [ ] Read-only diagnostic smoke task. Do not modify any files, run tests, or make network requests. Report your harness version, current working directory, and whether this isolated dispatch starts and exi [testing] <!-- id:story-adhoc-1789064247 -->
- [ ] Sprint 2: Adaptive Scope-Bounded Sparse Worktrees & Rebase Concurrency (#1389, #1551) [backend] <!-- id:story-afa066ee -->
- [ ] Sprint 3: Fleet Diagnostic Truth & Concurrency Resilience (#1521, #1503, #1551) [backend] <!-- id:story-52a6dcd1 -->
- [ ] Sprint 4: Meta Muse Commercial CLI Adapter & Discovery Probe (#1508, #1551) [backend] <!-- id:story-5f7d655f -->
- [ ] feat(marketing): Marketing Release Ceremony Automation [frontend] <!-- id:story-issue-1557 -->
- [ ] feat(worktree): Milestone v0.20.0 Cluster B — Worktree Lifecycle & Rebase Concurrency [backend] <!-- id:story-issue-1558 -->
- [ ] Milestone v0.21.0: Sprint 1 Plan & Implementation (Cluster A: Ephemeral Swarm Execution Infrastructure) [backend] <!-- id:story-3aeb1c7a -->
- [ ] fix(daemon): eliminate false 'already running' deadlock and port collision zombie (#1572) [backend] <!-- id:story-issue-1573 -->
- [ ] [Research & Spec] DSH Cordis Plugin Architecture & @synlynk/dsh-plugin Integration [backend] <!-- id:story-b75cb3e7 -->
- [ ] [Architecture] DSH Agent Control Protocol (ACP) JSON-RPC Headless Transport [backend] <!-- id:story-541995f4 -->
- [ ] [Architecture] Active Herdr Terminal Multi-Pane Cockpit Orchestration [backend] <!-- id:story-2348ac34 -->
- [ ] Synlynk Cockpit: Active Herdr 4-pane terminal orchestration (synlynk herdr init) [backend] <!-- id:story-0127066f -->
- [ ] feat: FTUE onboarding journey with universal surface support (v0.21.0) [testing] <!-- id:story-issue-1574 -->
- [ ] install.sh curl path is broken: ships 6 of 103 modules, crashes on import of synlynk._constants [frontend] <!-- id:story-issue-1575 -->
- [ ] fix: tolerate ANSI output in QA sentinel gate [testing] <!-- id:story-issue-1578 -->
- [ ] feat(graphify): Graphify Knowledge Graph Substrate, Multi-Repo Mesh, and Reusable Spike Evaluation Harness (v0.22.0) [testing] <!-- id:story-issue-1579 -->
- [ ] fix(ci): unblock marketing PR sync git add and mark v0.22.0 shipped [testing] <!-- id:story-issue-1580 -->
- [ ] [T9] Daemon liveness: start/status match a live PID; token refresh runs [testing] <!-- id:story-issue-1588 -->
- [ ] [C9] Worktree and branch reap on merge [testing] <!-- id:story-issue-1607 -->
- [ ] test: prove daemon recovery from dead PID [testing] <!-- id:story-issue-1610 -->
- [ ] fix: reap merged worktrees after qa merge [testing] <!-- id:story-issue-1611 -->
- [ ] docs(housekeeping): sync memory, cost log, and recorded decision records [testing] <!-- id:story-issue-1612 -->
- [ ] [T2] Fail-closed --requires-gh-write and worktree-aware token cache [testing] <!-- id:story-issue-1584 -->
- [ ] [T8] Live selftest / smoke actually running [testing] <!-- id:story-issue-1591 -->
- [ ] [C8] policy check-merge in the merge path [testing] <!-- id:story-issue-1598 -->
- [ ] [C10] Board/story state follows merge in state.db [testing] <!-- id:story-issue-1608 -->
- [ ] [T3] Fail loud on capability: never OK/exit 0 on a silent no-op [testing] <!-- id:story-issue-1589 -->
- [ ] [T4] Cost row or explicit missing on every finished job [testing] <!-- id:story-issue-1582 -->
- [ ] [T6] Scope enforcement: review/read-only jobs cannot write outside declared paths [testing] <!-- id:story-issue-1583 -->
- [ ] [S1] Home vs headless split in telemetry [testing] <!-- id:story-issue-1600 -->
- [ ] [C1] GOVERNS spine at spec and plan approval [testing] <!-- id:story-issue-1605 -->
- [ ] [C2] Backlog to goal auto-association (live proof) [testing] <!-- id:story-issue-1590 -->
- [ ] [C4] Reserved approval gates halt only the blocked branch [testing] <!-- id:story-issue-1596 -->
- [ ] [S3] Unattended milestone command is the default driver [testing] <!-- id:story-issue-1599 -->
- [ ] [C6] Non-author merge identity (qa App ≠ author App) [testing] <!-- id:story-issue-1597 -->
- [ ] [C5] CI + qa-gate are the merge oracle [testing] <!-- id:story-issue-1592 -->
- [ ] [T5] Instruction receipt closed loop is evidence, not hope [testing] <!-- id:story-issue-1601 -->
- [ ] [C3] Charters in the execution prompt — live proof [testing] <!-- id:story-issue-1593 -->
- [ ] [C7] Rebase/stack without a human [testing] <!-- id:story-issue-1604 -->
- [ ] [C11] TPM and Release runners (spec gate) [testing] <!-- id:story-issue-1606 -->
- [ ] Harness capability reassessment — recurring cycle [testing] <!-- id:story-issue-1179 -->
- [ ] test: enforce scope violation without gh write (#1583) [testing] <!-- id:story-issue-1614 -->
- [ ] test: prove reserved gates isolate DAG branches [testing] <!-- id:story-issue-1617 -->
- [ ] feat(backlog): add explicit goal association [backend] <!-- id:story-issue-1618 -->
- [ ] feat: split ops telemetry by home vs headless [testing] <!-- id:story-issue-1629 -->
- [ ] feat: add GOVERNS goal suggestion telemetry and warnings [testing] <!-- id:story-issue-1619 -->
- [ ] fix(doctor): guard durable role App material [testing] <!-- id:story-issue-1630 -->
- [ ] feat: enforce CI and qa-gate merge oracle [testing] <!-- id:story-issue-1631 -->
- [ ] fix: inject live charters into dispatch prompts [testing] <!-- id:story-issue-1621 -->
- [ ] fix: run live smoke checks from daemon cadence [testing] <!-- id:story-issue-1623 -->
- [ ] fix: # #1606 [C11] TPM and Release runners — smallest sli (job-1ff7c140) [testing] <!-- id:story-issue-1632 -->
- [ ] fix: fail-closed GitHub writes from worktrees [testing] <!-- id:story-issue-1616 -->
- [ ] fix: fail loud on capability failures [testing] <!-- id:story-issue-1626 -->
- [ ] feat: make unattended milestone execution the default [testing] <!-- id:story-issue-1620 -->
- [ ] fix: mark terminal jobs with missing costs [testing] <!-- id:story-issue-1622 -->
- [ ] fix(review): select non-author merge identity [testing] <!-- id:story-issue-1625 -->
- [ ] feat(capability): add recurring reassessment cadence [testing] <!-- id:story-issue-1627 -->
- [ ] fix: gate unattended merge on instruction receipts [testing] <!-- id:story-issue-1624 -->
- [ ] fix: gate merge helpers with policy check [testing] <!-- id:story-issue-1613 -->
- [ ] feat(qa): rebase behind PRs before merge [testing] <!-- id:story-issue-1628 -->
- [ ] fix: mark stories done after merged PR [testing] <!-- id:story-issue-1615 -->
- [ ] docs: workspace identity W0 vocabulary (#914) [testing] <!-- id:story-issue-1647 -->
- [ ] feat: Wave 1 product-scoped identity store (#914) [testing] <!-- id:story-issue-1648 -->
- [ ] feat: #914 Wave 2 work graph and policy [testing] <!-- id:story-issue-1649 -->
- [ ] feat: add workspace identity industry packs [testing] <!-- id:story-issue-1650 -->
- [ ] feat(workspace): add product repo registration [backend] <!-- id:story-issue-1651 -->
- [ ] [LIVE-1] Headless harness preflight masks Claude authentication failure and blocks decision panels [backend] <!-- id:story-issue-1654 -->
- [ ] [LIVE-1] Recover and harden canonical state.db with offline DR [backend] <!-- id:story-issue-1655 -->
- [ ] [LIVE-2] Post-merge marketing sync cannot update protected main [ml] <!-- id:story-issue-1666 -->
- [ ] Hardening: one canonical state DB with explicit idempotent migration and quarantine [backend] <!-- id:story-4fe0a8bf -->
- [ ] fix: add explicit canonical registry recovery [backend] <!-- id:story-issue-1685 -->
- [ ] Exploration: Vizor World View Inside-Out Projection & Opportunity Radar Architecture [architecture] <!-- id:story-2161a277 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806534 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806536 -->
- [ ] Capability baseline seed (synthetic, not a real story) <!-- id:__baseline_seed__ -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806538 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806539 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806541 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806543 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806545 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806546 -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806548 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806550 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806552 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806554 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806556 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806558 -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806560 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806563 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806564 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806567 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806569 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806571 -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806573 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806575 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806577 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806580 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806582 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806584 -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806586 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806588 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806590 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806592 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806594 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806596 -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806598 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806600 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806603 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806605 -->
- [ ] Write a minimal example demonstrating Programming/Software Development for a small Python function. [backend] <!-- id:story-adhoc-1789806608 -->
- [ ] Review this Programming/Software Development calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<tr [backend] <!-- id:story-adhoc-1789806610 -->
- [ ] Write a minimal example demonstrating Testing for a small Python function. [testing] <!-- id:story-adhoc-1789806613 -->
- [ ] Review this Testing calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'correct=<true|false>'.

Executor har [testing] <!-- id:story-adhoc-1789806615 -->
- [ ] Write a minimal example demonstrating Requirements Definition and Management for a small Python function. [backend] <!-- id:story-adhoc-1789806618 -->
- [ ] Review this Requirements Definition and Management calibration task output from another harness and score it 0-10 for quality.
Respond with a line '# synlynk-meta' followed by 'quality=<N>' and 'corre [backend] <!-- id:story-adhoc-1789806621 -->
- [ ] [Wave 1 - 01 Oct] Synlynk Personal Dev Preview v1.0.0 (Local-Only, 9-Pillar Stabilization) [architecture] <!-- id:story-ffb0f3e6 -->
- [ ] [Wave 2 - 08 Oct] Synlynk Teams Relay (Peer-to-Peer Mesh, Distributed Leases & Conflict Preemption) [architecture] <!-- id:story-f6782d57 -->
- [ ] [Wave 3 - 15 Oct] Synlynk Teams Server (Hosted Collaboration Hub, Multi-Tenant RBAC & W9 Hosted Vizor) [architecture] <!-- id:story-f4dbf2ce -->
- [ ] [Wave 4 - 22 Oct] Synlynk Model Hub (Meta Muse GA, Local oMLX Harness & Universal Provider Aggregators) [architecture] <!-- id:story-c7064c40 -->
- [ ] Exploration: Decisioning Models (TypeSafe.ai/Jev) for Sub-20ms Fleet Routing & Policy Gating [architecture] <!-- id:story-0f7043d7 -->
- [ ] docs: W10 - Grok Bot remote MCP surface spec (blocked on W9) [backend] <!-- id:story-issue-1726 -->
- [ ] Fix 5 failing CI tests on PR #1753 caused by the new _require_dispatch_gh_token fail-at-launch precondition check in synlynk/dispatch.py (added around line 3037, called from dispatch_agent before work [testing] <!-- id:story-39ada885 -->
- [ ] Fix stale model catalog entries in synlynk/models.py [backend] <!-- id:story-5e2d2db2 -->
- [ ] Review PR #1764: stale model catalog fix [backend] <!-- id:story-226eb31c -->
- [ ] Fix issue 1766 in the nikhilsoman/synlynk repo: two related bugs in synlynk dispatch's model override plumbing, both confirmed live during PR 1764 review dispatch attempts to agy.

Bug 1 -- missing ef [testing] <!-- id:story-adhoc-1790223013 -->
- [ ] dispatch.py: no --effort passthrough + wrong Agy/Gemini model-ID format causes 3/3 review-dispatch launch failures [testing] <!-- id:story-issue-1766 -->
- [ ] Vizor In-Browser Settings & Credentials Manager: Provider OAuth & State DB Snapshot Management [backend] <!-- id:story-631a6a86 -->
- [ ] Vizor Real-Time SSE/WebSocket Live Telemetry Stream & Agent Action Feed [backend] <!-- id:story-18983f9f -->
- [ ] Vizor Remote Access Tunnel & Mobile HUD Companion [backend] <!-- id:story-565bf96f -->
- [ ] [LIVE-15 fix] run_brownfield_init() calls cwd-relative init() without chdir guard [testing] <!-- id:story-issue-1774 -->
- [ ] Graphify automated refresh lifecycle: post-merge hooks, daemon watcher, and 1-click Vizor UI refresh [backend] <!-- id:story-3d52ea96 -->
- [ ] Graph-backed context packager for sub-3k token agent task dispatch and impact analysis [backend] <!-- id:story-5ce5a997 -->
- [ ] feat(viz): Graphify auto-extraction pipeline & Vizor unified clustered canvas [frontend] <!-- id:story-issue-1777 -->
- [ ] feat(viz): canonical community labels, topbar multi-select dropdown, and monorepo tab streamlining [frontend] <!-- id:story-issue-1782 -->
- [ ] docs: restore roadmap.md from triaged state.db arcs [testing] <!-- id:story-issue-1784 -->
- [ ] fix: lock generated 4-docs after migrate and dual-write from state.db [testing] <!-- id:story-issue-1786 -->
- [ ] feat(viz): Knowledge Graph usability — file deep-link, inspect traversal, kind-based L0 (#1790) [frontend] <!-- id:story-503a76f2 -->
