# Changelog

All notable changes to synlynk are documented here.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).
Versioning follows [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

---

## [Unreleased]

### Added

**Ticket-driven approval auto-resume (design/plan 2026-08-24, PRs #1137-#1139, #1141)**
- Closes the known gap flagged at the end of `[0.16.0]`: resolving an `[APPROVAL]` ticket now actually unblocks the parked story on the next `synlynk tpm sweep` pass, instead of the story re-parking forever.
- `approval_tickets` table (PR #1137) plus `_find_ticket()` / `_insert_ticket()` / `_mark_ticket_consumed()` helpers in `synlynk/db.py` (PR #1138) give `run_sweep_pass()` (PR #1139) three-way state awareness per story/action: no ticket yet → file one; open ticket → keep parking; resolved ticket → consume it and let dispatch proceed.
- `synlynk/events.py`'s `_scan_approval_tickets()` (PR #1141) now writes `approval_tickets.status='resolved'` at the same point it emits `approval_resolved`, so the resolution is durable state the next sweep pass can actually query — not just an event log entry nothing consumed.
- **Live dogfood verification (Task 5, Claude-direct per plan, 2026-08-24):** ran the full ticket lifecycle against this repo's real GitHub issue tracker using a temporary, fully-reverted `task_dispatch_demo` policy rule (reverted before merge; never landed on `main`). Demo story `story-becf09a5`: sweep 1 parked it and filed ticket id 8 → issue [#1149](https://github.com/nikhilsoman/synlynk/issues/1149); sweep 2 confirmed no duplicate ticket/issue; `gh issue comment 1149 --body "approve"` + `scan_local_events()` produced `approval_resolved` event id 371 referencing issue #1149; sweep 3 dispatched instead of re-parking (job `job-e8277299`, exit 0) and marked the ticket `consumed` (`consumed_at` set). Every claim was verified via direct DB query / `gh issue list` / `synlynk events tail`, not sweep's own printed summary.
- **Process note:** Tasks 1-4's implementer stage was dispatched to Codex per the project's PM/review-only split as usual. Task 4 hit a session-level blocker — the Claude Code auto-mode classifier repeatedly denied `synlynk dispatch` calls even with valid role-scoped GitHub App credentials — so Task 4 was implemented directly by Claude as a documented, user-approved workaround. Filed as [LIVE-6, #1140](https://github.com/nikhilsoman/synlynk/issues/1140) (Sev2) since it degrades the autonomy-design goal; root cause not yet investigated.

**Agent vs Harness Terminology — Phase 0 (design 2026-08-09, plan 2026-08-09)**
- `docs/glossary-agent-vs-harness.md` — canonical definition distinguishing **Agent** (persistent role identity + charter: pm/architect/tpm/dev/designer/qa/marketing/synlynk-bot) from **Harness** (swappable execution backend: Claude/Agy/Grok/Codex/local).
- Auto-generated `## Capability-Based Task Allocation` table (synced into CLAUDE.md/GEMINI.md/AGENTS.md/GROK.md via `synlynk doctor --fix`) now reads `| Role | Harness | Tasks |` instead of the conflated `| Role | Agent | Tasks |`, with a glossary-link note.
- Hand-maintained "Terminology: Agent vs Harness" section added to this repo's own `CLAUDE.md`.
- `.synlynk/roles.yaml`, `README.md`, `SYNLYNK_GUIDE.md` wording fixed to stop conflating Agent and Harness.
- **Not yet a shippable milestone:** first phase of a 5-phase roadmap (`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` §10). Phase 1 (agent manifests/charter storage) has since shipped — see `[0.14.0]` below — but Phases 2-4 (memory, capability registry, portability) remain unbuilt. Held out of 0.13.1 and 0.14.0; will ship as its own named release once the full terminology rollout is complete.

**Quota-Aware Dispatch Reservation (design 2026-08-08, plan 2026-08-08)**
- `agent_reservations` ledger tracks estimated-token reservations per harness from the moment a job is queued/dispatched until it settles, closing the gap where `--force-agent` and daemon-queued dispatches could bypass quota checks entirely.
- `dispatch_agent()` now consults quota unconditionally (including `--force-agent` calls) and defers (`queued`, `blocked_reason=quota_exhausted`) instead of raising when a harness has no headroom; deferred jobs resume automatically once the harness's quota window resets — no manual re-dispatch needed.
- `_dispatch_ready_jobs()` no longer falls through to an exhausted harness when a job is blocked; it stays queued for the next poll.
- `synlynk schedule --execute` opens real reservations for the whole batch at commit time via `_enqueue_plan()`.
- `_force_exhaust_quota()` wires sentinel's existing `QUOTA_EXHAUSTED` detection into the reservation ledger without ever touching already-running jobs.
- `synlynk/tpm_hooks.py` — narrow TPM hook surface (`tpm_observe_reservations`, `tpm_reorder_queue`, `tpm_reallocate`) plus a read-only `synlynk quota --tpm-view` CLI command to inspect open reservations across harnesses.
- **Not yet a shippable milestone:** no active agents currently exercise the reservation ledger or TPM hooks in production dispatch flow. Held out of 0.13.1 and 0.14.0; will ship once agents actually consume it.

## [0.16.0] - 2026-08-23

**Release pitch:** the authority layer v0.15.0 built now actually gates something unattended — `synlynk tpm sweep` walks ready stories through dispatch end-to-end, pauses on a policy-flagged action with a GitHub approval ticket instead of blocking the whole batch, and a live dogfood run proved both the happy path and the pause+ticket path work — surfacing two real gaps in the process, filed rather than papered over.

### Added

**GOVERNS `awaiting_approval` event (Task 10, PR #1125)**
- New GOVERNS event type extending the `job_terminal`/`review_submitted` event-contract pattern (PR #922): `emit_awaiting_approval(story_id, action, reason)` in `synlynk/events.py`, recording which `policy.json` `approval_required_for` rule matched.

**Approval-gate ticket flow (Task 11, PR #1126)**
- `synlynk/approval_gate.py` — `raise_approval_ticket()` files a `[APPROVAL] <action> — <story_id>` GitHub issue with story context, the matched policy rule, and instructions to reply `approve` or act directly on GitHub.
- `synlynk/events.py`'s `_scan_approval_tickets()` polls open `[APPROVAL]` issues and emits `approval_resolved` for any that are closed or have an `approve`-prefixed comment, wired as the last step of `scan_local_events()`.

**`synlynk tpm sweep` (Task 12, PR #1127)**
- One pass over `readiness='ready'` stories: dispatch → verify → PR → review → merge per story, gating every step on `check_authority()`. A `requires_approval` result parks that story (raises a ticket, emits `awaiting_approval`) without blocking the rest of the batch. Per-pass summary surfaced via `synlynk status`.

**Live dogfood verification (Task 13, Claude-direct per plan)**
- Ran `synlynk tpm sweep` unattended against this repo's real backlog. To avoid dispatching all 8 pre-existing ready stories for real, the 8 were temporarily parked (`synlynk story draft`) and restored afterward; only two purpose-built demo stories were swept.
- Pass 1 (no approval rule active) proved the normal path: `story-028d26d9` dispatched, ran to completion, PR opened.
- Pass 2 (a temporary, documented, fully-reverted test-only `policy.json` rule — `task_dispatch:` has no default rule that can trip `requires_approval`, since `_matches_approval_rule()` explicitly skips `security_sensitive_paths:` for dispatch actions) proved the pause path: `story-7aa0aaec` parked, a real `[APPROVAL]` issue was filed and assigned, `approve` was commented, and `_scan_approval_tickets()` correctly emitted `approval_resolved` (event id 272) — independently confirmed via `synlynk events tail --type approval_resolved` and `gh issue view --json state,comments`.
- Every claim was cross-checked directly (`synlynk jobs --all`, direct DB queries, `gh issue list --search`, `gh api .../branches/main/protection`) rather than trusted from the sweep's own printed summary, per the plan's explicit instruction.

### Fixed / Known gaps (filed, not patched in this release — Claude is PM/review only; fixes are implementation work for a future dispatch)
- **`scan_local_events()` crashes before reaching `_scan_approval_tickets()`** (`sqlite3.OperationalError: table subscriptions has no column named harness_name`), and its only production call site (`workspace_agent.py`'s `cmd_workspace_agent_run`) has no wired CLI subcommand — meaning the documented approval-resolution detection path does not actually run unattended today. Filed as [#1132](https://github.com/nikhilsoman/synlynk/issues/1132).
- **`synlynk story done` does not clear `readiness`**, and `_ready_stories()`'s in-flight guard only excludes `queued`/`running` jobs, not `done` ones — so a story whose dispatch already completed gets re-swept and re-parked on the very next pass, observed live with `story-028d26d9`. Filed as [#1133](https://github.com/nikhilsoman/synlynk/issues/1133).
- **Resolving an approval ticket does not auto-unblock a re-sweep**: `check_authority()` is purely policy-rule-based with no awareness of ticket-resolution state, so `approval_resolved` firing does not itself let the parked story advance on the next pass. This matches the plan's own scoping (ticket-driven auto-resume was explicitly out of scope for this plan) — a known limitation, not a regression, and the natural next increment once #1132/#1133 are fixed.

## [0.15.0] - 2026-08-23

**Release pitch:** synlynk's own repo gets a real authority layer — a two-tier `policy.json` (workspace defaults + per-repo overrides) that turns previously-hardcoded prose tables (who can merge, who can cut a release, who can edit the roadmap, which harness handles which task type) into data, gated by a fail-closed `check_authority()` resolver, with branch protection now live-verified on `main`.

### Added

**Workspace Policy Layer (design 2026-08-23, plan `docs/superpowers/plans/2026-08-23-workspace-policy-and-autonomous-loop.md`, PR #1122)**
- `synlynk/policy.py` — two-tier policy schema: workspace defaults (`~/.synlynk/workspaces/<name>/policy.json`, falling back to `DEFAULT_WORKSPACE_POLICY` when absent) merged with a repo's sparse `.synlynk/policy.json` overrides, whole-object-replace-per-top-level-key (not a deep merge).
- `check_authority(action, role, repo_path)` → `AuthorityResult(allowed, requires_approval, reason)`, covering `roadmap_edit`, `goal_create`, `merge`, `release_cut`, and `task_dispatch:<type>` actions, plus an `approval_required_for` rule matcher (named releases, roadmap-authority changes, security-sensitive paths, irreversible merges).
- Wired fail-closed into four call sites: `dispatch_agent()`'s task-allocation resolution, `cmd_release`, `cmd_roadmap_add`, `cmd_goal_create` — each raises `RuntimeError` on `allowed=False` rather than proceeding.
- `synlynk policy check-merge`, `synlynk policy sync-branch-protection`, `synlynk policy show` — new CLI commands; `sync-branch-protection` calls GitHub's branch protection API idempotently, deriving required status checks from `.github/workflows/`.
- This repo's own `.synlynk/policy.json` migrates the existing CLAUDE.md prose tables (Capability-Based Task Allocation, PR Review Discipline, Named Release authority) into data — CLAUDE.md now points to `synlynk policy show` as the source of truth instead of hand-maintained tables.
- Full `check_authority()` unit coverage: allow/deny/requires_approval across both tiers, override-merge rule, missing-repo-override inheritance, unknown task_type denial (`tests/test_policy.py`, 11 tests).
- **Live-verified:** branch protection synced and independently confirmed via `gh api repos/nikhilsoman/synlynk/branches/main/protection` — `required_status_checks` = `["test (3.8)", "test (3.10)", "test (3.12)", "qa-gate"]`, `required_reviews` = `1`, `enforce_admins` = `true`.

### Fixed
- Default `role="dev"` on `cmd_release`/`cmd_roadmap_add`/`cmd_goal_create` didn't match the default policy's `pm`-only authority for these actions, causing unspecified-role calls (including coldstart's own roadmap-row write) to fail closed. Defaulted to `role="pm"`, matching the actions' actual authority scope.
- Taxonomy regression: two new `policy` subcommands were missing `COMMAND_TAXONOMY` entries, failing `test_taxonomy_matches_real_cli_surface`.

## [0.14.0] - 2026-08-16

**Release pitch:** the execution floor gets a truth guarantee — every GitHub-write dispatch now has its claimed outcome independently verified against live GitHub state instead of trusted at face value — and workspace agents get a real identity: a storage-backed charter, a `synlynk agent init/list/show/edit/disable` onboarding surface, and dispatch integration that resolves role and harness from that identity automatically.

### Added

**GOVERNS Job-Truth / GH-Write Consolidation (#701, PR #978)** — closes #331, #579, #935
- `synlynk/gh_verify.py` `gh_write_verified()` — an independent delivery-of-effect check that queries live GitHub state via the orchestrator's own `gh` identity (not the sandboxed job's), replacing "the job said it succeeded" with "GitHub confirms the write landed."
- Wired into `dispatch.py`'s `_check_job_stall` (extends timeout on an unverified write, kills the job on a confirmed failure) and `jobs.py`'s `_reconcile_daemon_jobs` (new `succeeded_gh_write_failed` terminal status distinct from a clean success).
- `gh_write_verified` surfaced as a column in `synlynk jobs` output.
- Regression guard (`tests/test_gh_write_guard.py`) asserting every terminal-status-deciding code path for a `--requires-gh-write` job consults the check.
- `synlynk doctor` TC-7 preflight verifies Agy's local `gh` allow-rules before routing gh-write tasks to it, instead of failing at dispatch runtime.
- Codex PR-review tasks now route through the `gh` CLI directly instead of the previously-unreliable MCP `add_review_to_pr`/`add_comment_to_issue` tools.

**Workspace-Scoped Agent Artifact Storage (design 2026-08-14/15, gh#936, PR #988)**
- Mints a real `workspace_id` (uuid4, persisted once in `.synlynk/config.json`) keying a new workspace-level agent artifact store.
- `agent_id` registry (`register_agent`/`resolve_agent_id`) mirroring the existing `member_id`/`member_aliases` pattern — loud failure on an unregistered alias, rejects duplicate agent_id/alias.
- Canonical `charter.md` + provenance-chained `charter.revisions.jsonl` storage (`read_charter`/`propose_charter_revision`) with stale-parent-revision conflict detection, extended to `memory/` and `statements-of-record/` entries.
- `regenerate_agent_projection()` writes a generated, gitignored `.synlynk/agents/<agent_id>.yaml` projection (agent_id/role/overrides only, never charter content) via a stdlib-only flat YAML emitter.

**Agent-Roles-Charters Phase 1 — CLI Onboarding + Dispatch Integration (design 2026-08-16, PR #1003)**
- `synlynk agent init/list/show/edit/disable` — the CLI onboarding surface for workspace agents (org-chart roles: dev/qa/pm/architect/tpm/designer/marketing/synlynk-bot), built on the storage layer above.
- `dispatch_agent()` gains `agent_id` support: validates the agent is registered/enabled, resolves its role, auto-selects a harness by capability fit when none is forced, and threads the resolved role into GitHub-identity/token resolution (taking precedence over `story_id`-derived role when both are present).
- `synlynk dispatch --as-agent <id_or_alias>` — makes the `harness` positional argument optional when `--as-agent` triggers auto-selection.

**Agent → Harness CLI Rename (PR #993)**
- Renames `synlynk agent add/configure/run/list` to `synlynk harness add/configure/run/list`, resolving the naming collision between execution-backend harnesses and the workspace/role-identity agents introduced above. No deprecation shim — pre-1.0 breaking change, decided via a 4/4 `synlynk decide --panel` vote (`project-docs/decisions/2026-08-16-synlynk-s-cli-has-a-naming-collision-syn.md`).
- Frees the `agent` CLI verb for the onboarding surface above. `dispatch <agent>`, `open <agent>`, `probe --agent`, `quota --agent` are untouched — those use "agent" in unrelated senses.

**TPM/Session MVP (plan 2026-08-13, PRs #934, #944, #950, #954, #959)**
- `sessions` table + `synlynk/session.py` active-session marker file helpers.
- `devlog_entries` gains `session_id`/`goal_id` columns; `cmd_devlog_append()` auto-inherits the active session when not passed explicitly.
- `session_id` threaded through `dispatch_agent()` → `daemon_jobs` → `cost_entries` (with inheritance from job to cost row), so every dispatch and its cost are attributable to the session that launched it.
- `synlynk dispatch --session <id>` override flag.
- `synlynk session status` surfaces a NUDGE line when `daemon_jobs` has rows with no `session_id` — the first concrete TPM-facing signal for unattributed work.

### Fixed
- Devlog identity re-fork prevented by resolving the devlog path through the `member_id` registry instead of a raw filename match (#956).
- Dispatch stall-timeout extended for review-only jobs, which previously could be killed mid-review before posting (#939).
- Review-only `synlynk dispatch` jobs no longer get miscounted against implementation-job budgets (#943, closes #937).

### Housekeeping
- Worktree/job accumulation (#559) audited and closed without new code: `synlynk worktree audit`/`worktree clean` (shipped pre-0.13.1 in PR #676) already covers the core ask; `synlynk status`'s existing staleness hint covers the proactive-warning ask. Re-verified against this repo's own worktree state during the audit.

## [0.13.1] - 2026-08-13

**Release pitch:** synlynk gets safer to operate on — init/migrate/upgrade can now roll back on failure, project docs are DB-canonical instead of hand-parsed markdown, the GOVERNS event bus gains job-terminal and review-submitted events plus a `synlynk events tail` command, and a new doctor check catches invalid GitHub tokens before a dispatch wastes a turn discovering them.

### Added

**GOVERNS Event-Contract Extension (design 2026-08-12, plan 2026-08-12, #922)**
- `job_terminal` event — emitted synchronously from `_reconcile_daemon_jobs()` for every daemon job reaching a terminal state, payload `{job_id, status, cost_recorded, dispatch_context}`.
- `review_submitted` event — emitted from `scan_local_events()` for each GitHub PR review not already represented, payload `{pr_number, reviewer_login, reviewer_role, verdict}`, with `reviewer_role` derived from bot-login patterns.
- `synlynk events tail [--type TYPE] [--limit N]` — read-only CLI command listing recent events newest-first directly from the `events` table.

**Init/Migrate/Upgrade Rollback Mechanism (design 2026-07-22, plan 2026-07-22)**
- `rollback_checkpoint` (Leg 1) wraps `init()` and `cmd_migrate()` in a git-checkpoint + untracked-state backup, auto-restoring on any mid-operation failure.
- `rollback_checkpoint_upgrade` (Leg 2) wraps `_run_upgrade()` in a global install snapshot (pipx reinstall-by-tag / script bin+lib backup), auto-restoring on upgrade failure.
- `synlynk rollback [--last|<op-id>|--clear]` — manual rollback CLI, restoring or discarding the most recent (or a specific) checkpoint manifest.
- `--dry-run` on `synlynk init` and `synlynk upgrade` — preview what would be written/changed without touching disk or making network/subprocess calls.
- Failure-injection live selftest coverage for both rollback legs, plus dedicated `rollback --last`/`--clear` scenario tests.

**State Engine PR1 — DB-canonical roadmap/memory/costs (design 2026-07-20, plan 2026-07-25)**
- `roadmap.md`, `memory.md`, and `costs.md` are now write-through generated from `state.db` (roadmap_arcs/roadmap_phases, memory_entries, cost_entries), with rotation/archive and a warn-and-continue mutation guard for hand-edits.
- `check_budgets()` reads `cost_entries` directly instead of regex-parsing `costs.md`.
- `synlynk migrate` run on this repo itself — `project-docs/` relocated under `.synlynk/`, `.synlynk_migrated` sentinel committed.

**`synlynk doctor` TC-6 — GitHub CLI auth check (#928, closes #577)**
- New check across all 4 dispatch harnesses (claude, codex, agy, grok) inspects `gh auth status` output for known invalid-token marker strings even when the command exits 0 — the documented false-green failure mode where a dispatch sandbox has a broken GitHub token but `gh` doesn't report a nonzero exit.

### Fixed

- Bumped `linkify-it` to 5.0.2 in `website/package-lock.json`, resolving a high-severity quadratic-complexity DoS (CVE-2026-59887, GHSA-v245-v573-v5vm) in its `mailto:` schema validator. Dev-only, transitive via `markdown-it`; fixes GitHub Dependabot alert #6.
- `synlynk jobs` now resolves the repo's real default base branch before `gh pr create`, avoiding hardcoded `--base main` failures on repos whose default branch is `master` or another tracked branch.
- `synlynk dispatch agy` now warns when no write/run permissions are granted, so headless dispatches do not fail silently when approval-gated tool calls are auto-denied.
- Bumped `brace-expansion` to 1.1.16 in `website/package-lock.json`, resolving a high-severity exponential-time DoS (CVE-2026-13149, GHSA-3jxr-9vmj-r5cp) in expansion of consecutive non-expanding `{}` groups. Dev-only, transitive via `minimatch`; fixes GitHub Dependabot alert #7.

### Docs

- `docs/rca/2026-08-13-dispatched-pr-review-cancellation-714.md` (#929, closes #714) — RCA concluding Grok's `cancelled` stopReason on dispatched PR reviews is harness-side, not a synlynk stall/timeout bug; no code change warranted.

## [0.13.0] - 2026-07-22

**Release pitch:** synlynk learns to explain itself — every command now has a discoverable taxonomy entry with a maturity-tiered reveal, a live selftest exercises all 59 commands end-to-end, cost accounting gets payment-model awareness and a task-boundary fence around actual spend, and dispatch routing gets capability-aware enough to stop sending GitHub-write work to agents that structurally can't do it.

### Added

**Command Taxonomy, Maturity-Tiered Reveal, and Trigger Registry (design #303, PRs #304/#305/#309/#310/#311/#312/#316/#319/#320/#321)**
- `COMMAND_TAXONOMY` becomes the single source of truth for all 59 commands — `cli.py`'s `build_parser()` extracted standalone (#304), taxonomy command surface restored and hardened (#305), default `fenced_commands` allowlist (#309).
- Command reference docs now generate directly from `COMMAND_TAXONOMY` (#316) instead of hand-maintained markdown, closing a recurring drift source.
- FTUE wizard and the `synlynk` launch picker are now driven by the same taxonomy (#319), so first-run onboarding and the reference docs can never disagree about what a command does or which tier it belongs to.
- Tier-scoped trigger phrases wired into `synlynk:start`/`synlynk:end` session fencing (#320).
- Pre-commit hook installed on `synlynk init` to gate instructions drift between the taxonomy and generated CLAUDE.md/GEMINI.md/AGENTS.md content (#321).

**Task-Boundary Cost Fence (story-615bc8f4, PRs #313/#314/#315/#317)**
- `synlynk exec`'s actual-cost print now routes through a dedicated cost fence at the task boundary (#313) rather than being computed ad hoc per call site, closing a class of under/over-reporting bugs where a task's real spend diverged from what `costs.md` recorded.
- Shipped and marked complete in the roadmap (#314); PM session cost for the execution itself logged per the Cost Capture Protocol (#315, #317).

**Live Command Selftest (PR #328, follow-ups #335/#337)**
- `synlynk selftest` — a taxonomy-driven smoke test that exercises all 59 commands, catching command-surface regressions the unit suite doesn't (drift between `COMMAND_TAXONOMY` and actual CLI behavior, broken flag wiring, silent crashes on real invocation).
- Blog post documenting the design and implementation (#335).
- Follow-up fix: live paid selftest scenarios now rebind `DB_PATH` to a scratch workspace instead of touching the real project DB (#337, scenario N6).

**Capability Sweep + Industry Taxonomy (PR #367)**
- `synlynk capability sweep` — a taxonomy-driven calibration sweep scoring agent capability against NAICS/APQC/SFIA-coded skill axes, seeded from `synlynk/capability_baseline.json` and reinforced organically as real PRs land, with a configurable `$10` cost guardrail (`capability_sweep.cost_cap_usd`) and independent cross-agent verification scoring.
- Legacy free-text `discipline` / `org_domain` / `industry` values are crosswalked to NAICS/APQC/SFIA codes on migration, tagging unmatched values `legacy_unmapped` rather than dropping them.

**Payment-Model-Aware Cost/Value Accounting — PMA-1 through PMA-6 (PR #374)**
- Cost and value accounting now distinguishes payment model (subscription-seat vs. metered/API) so `costs.md` and budget reporting reflect what was actually spent under each agent's real billing arrangement, instead of a single blended token-rate assumption.
- Manual cost entries gained payment-column population (#402); historical entries backfilled with `api_equivalent_usd` for cross-model comparison (#388).
- Roadmap and devlog synced for both Capability Sweep (#367) and PMA (#374) landing together (#375).

**Story-ID Auto-Provisioning for Dispatch (PR #407)**
- `dispatch_agent()` now auto-provisions a `story_id` when a dispatched task has none, closing a gap where ad hoc dispatches (not tied to an existing story) fell outside cost/capability tracking.

**`can_gh_write` Capability Routing (issues #423/#426, PRs #427/#432/#438)**
- `AGENT_CAPABILITY_BASELINES` gained a `can_gh_write` field so dispatch routing can structurally avoid sending GitHub-write work (`gh pr review`/merge) to agents that can't complete it headless (Agy, Codex, local) — previously enforced only by SOP convention (#427, #432 codified the convention first; #438 made it structural).
- New `--requires-gh-write` dispatch flag and enforcement logic in `dispatch_agent()`.

### Fixed

- **`synlynk watch` crash on `CYCLES.index("work")` (issue #421, fixed by #301, released here):** the `v0.12.0` tag shipped `cmd_watch()` still looking up a `"work"` cycle name that had already been renamed out of `hud.py`'s `CYCLES` list under the GOVERNS seven-stage vocabulary rollout, raising `ValueError: 'work' is not in list` on every invocation. The fix (`CYCLES.index("execute")`) merged to `main` via #301 two days after the `v0.12.0` tag, but was never shipped in a release until now.
- **`synlynk viz --serve` exits immediately, nothing binds the port (issue #421, PR #440, merged as #421):** `_start_server()` spawned the HTTP server on a `daemon=True` thread and returned immediately with no blocking call, so the process exited (killing the daemon thread with it) right after printing "Serving at...". Not a sandbox/forking artifact — reproduced identically in a real terminal. Fix adds `_serve_until_stopped()`, which blocks the main thread until `KeyboardInterrupt` and then cleanly shuts the server down.
- `synlynk migrate` false-positive `MigrationImportError` on idempotent re-runs (#276, #278): natural-key collisions on re-import no longer trip the loud-fail check.
- Dispatch auto-PR branch detection re-derives the worktree's actual current branch instead of trusting the pre-recorded name (#280, #283).
- `synlynk probe` clears `HARNESS_VERSION_DRIFT` for the specific agent just re-probed (#281, #284).
- `synlynk agent add <name>` retrofits onboarding for a newly available CLI agent already on `$PATH` (#277, #285), plus lazy daily housekeeping on the first `synlynk exec` of a new calendar day.
- Token-outlier cost entries now flagged safely instead of silently corrupting averages (#295).
- Stale Cost Visibility / Repo Hygiene SOP text corrected (#290, #296).
- Per-provider model rates with freshness checks across `costs`, `doctor`, and `sentinel` (#289, #297).
- Probe version-token parsing fixed (#294); model version now resolved from agent config files (#287, #292).
- `agent_quotas` now populated from telemetry, plus a new `synlynk quota` CLI (#291, #293).
- Job summary overwrites guarded against clobbering (#387).
- Dispatch worktrees branch from a fresh `origin/main` tip instead of a potentially stale local ref (#398, #395).
- Headless permission denials correctly classified, avoiding false positives from echoed source text (#399, #404).
- Agy permission dispatch enabled (#417).
- GitHub issue #379 follow-up: `.g` file handling fix (#384).
- `__init__.py` modularisation epic marked shipped, closing stale #380 (#401).

Design specs: `docs/superpowers/specs/2026-07-21-command-taxonomy-maturity-reveal-design.md`, capability sweep and PMA specs referenced in PRs #367/#374. Roadmap rows synced for Task-Boundary Cost Fence, Command Taxonomy, and Live Command Selftest (#416). State Engine tiered design (single-user/team/enterprise) drafted for a future release (#412) — not shipped in this version.

## [0.12.0] - 2026-07-15

**Release pitch:** the operational backbone gets provably reliable and provably accounted for — dispatched jobs finish their own git steps, a 5th zero-cost local agent joins the fleet, story routing gets real capability+quota+cost scoring with a fleet batch scheduler, and every dollar synlynk reports is now either structurally sourced or visibly flagged as an estimate.

### Added

**Measurement Ledger Hardening — Phase 1 + Phase 2 + display layer (epic #210, PRs #236/#241/#242/#244/#245/#246/#252/#256/#257/#264/#266/#267)**

*Phase 1 — provenance-tagged cost tracking (PR #236):*
- `cost_entries` gained explicit provenance columns: `cost_source TEXT NOT NULL` (`actual` | `estimated_token_rate` | `estimated_tshirt` | `estimated_manual` | `legacy_unknown`, no default — every `INSERT` must pass it explicitly) and `estimate_basis TEXT`. Migration rebuilds the table and backfills historical rows as `legacy_unknown`.
- `_insert_cost_row()` (`synlynk/db.py`) is now the sole sanctioned writer to `cost_entries`, replacing four independently-drifting direct-SQL write sites in `dispatch.py`, `jobs.py` (×2), and `support_engineer.py`. Upserts by `job_id` when present. Enforced by a call-site audit test that fails the suite if any other file writes to `cost_entries` directly.
- `extract_tokens()` now tags a `.basis` (`regex_pair` | `total_split` | `none`) distinguishing a real per-field token extraction from an 80/20 heuristic guess.
- `.synlynk/model_rates.json` (scaffolded by `synlynk init`) is now the source of truth for per-model rates and `billing_mode`, replacing a hardcoded table; falls back to hardcoded rates on missing/invalid file.
- New 3-tier t-shirt-size token fallback (`_estimate_tshirt_tokens()`) for surfaces with no real token count: story's `estimated_tokens` column → historical average from `cost_entries` (same discipline+phase, ≥3 samples) → fixed conservative default.
- **`synlynk cost log`** — manually log a cost row for native/unwrapped PM or brainstorming sessions with no CLI token data, tagged `estimated_manual`.
- Cost coverage closed across every surface identified in the design spec's audit: `dispatch_agent()`'s exec wrapper (no longer gated on `in_tokens > 0`), `jobs.py`'s reconcile and daemon-reconcile paths, `cmd_launch()`, and `support_engineer.py`'s investigation runs. `synlynk release`, `synlynk probe`, and `synlynk doctor` audited and confirmed correctly out of ledger scope.
- `check_budgets()` gained a dedicated sub-line surfacing failed-job placeholder estimates separately from the headline spend total. `costs.md` and budget parsers now tolerate `[est] `/`[legacy] `/`~` prefixes.
- New "Cost Capture Protocol" section in `CLAUDE.md`.
- `[failed job]` marker fix: `dispatch.py`'s zero-token-failure cost label now prepends (not appends) the marker so it survives `update_costs()`'s 20-character command truncation, restoring `check_budgets()`'s failed-job sub-line to live code.

*Phase 2 — structured-output token adapters, one per dispatch CLI (PRs #244, #252, #256, #257):* replaces the 80/20 heuristic split with a real per-field structured-JSON extraction path for each vendor CLI — Codex, Claude, Agy (Gemini), and Grok all shipped, closing epic #210's adapter scope.

*Display layer (PRs #264, #266):* Vizor's Effort & Cost tab now visually flags estimated-vs-measured cost rows; `synlynk status` gained a `RATES` line (and JSON `rates_updated_at` key) showing when the model rate table was last updated, warning `⚠ never updated` when no rate file exists.

Design spec: `docs/superpowers/specs/2026-07-13-measurement-ledger-hardening-design.md`. Roadmap arc + epic #210 marked shipped (PR #267). Deferred follow-ups filed as issues, out of scope for this release: #260 (Savings Ledger), #261 (dispatch-path unification), #262 (surface consolidation), #263 (stage constants staleness).

**Local Agent — 5th dispatch agent, zero-cost on-device inference (PRs #200/#204/#205/#207/#208/#209)**
- `local` joins claude/codex/agy/grok as a dispatchable agent, running as an `aider` CLI subprocess against an on-device oMLX OpenAI-compatible endpoint — zero per-token cost.
- Capability envelope seeding + concurrency guard so `local` starts with a conservative starter whitelist that self-widens with verified results.
- Real-hardware opt-in pytest tier (`tests/test_local_agent_hardware.py`) exercises actual Aider+oMLX end-to-end, correctly skipped when no local hardware is running.
- Capability-matrix taxonomy worked example + blog post documenting the integration.

**Capability Matrix Hardening — 3-stage routing engine + fleet batch scheduler (epic #137, PRs #139/#140/#141/#147/#148/#150/#151/#152/#154/#156)**
- `_best_agent_for_story()` now scores candidates across three real stages: weighted capability score (VERIFIER tier, dead-signal handling, `pr_review_cycles`/`verified_by_ci` signals), a hard quota-headroom gate (`agent_quotas` table across 5h/hourly/daily/weekly/monthly windows, degraded-mode fallback when quota signal is missing), and a cost tie-break (cheaper model wins when top scores are within 0.15).
- New `synlynk/scheduler.py`: `stories.priority`/`readiness` columns, `synlynk story ready/draft` gate, fleet-level in-batch headroom accounting (story N in a batch sees story 1..N-1's projected spend), retry/reassignment capped at 2 attempts, `synlynk schedule [--execute] [--max-stories N]` CLI.
- GOVERNS seven-stage vocabulary rollout replaces the old CYCLES/CYCLE_COLOURS naming across the capability taxonomy and HUD.
- Capability tag enum enforcement + taxonomy reference doc; `cycle_capability` row dedup migration fix.
- Deferred v2 (reset-timing-aware bin-packing, persistent quota-blocking history, GOVERNS-aware readiness gate) tracked as a goal, gated on 30 days of v1 production data (deadline 2026-08-10) rather than scoped into stories now.

**Job Lifecycle Ground-Truth Verification (#126, #127, #128, #129, PRs #130/#131/#132/#133/#135)**
- `dispatch_agent()` creates a dedicated `git worktree` per dispatched job (`worktrees/<job_id>`, branch `dispatch/<agent>/<job_id>`) instead of sharing the invoking shell's `cwd` — concurrent dispatches no longer collide.
- `_reconcile_jobs()` cross-checks git state when a job's exit sentinel is missing, instead of treating an ambiguous exit as automatic failure; new `"failed_unverified"` status flags "inspect before discarding."
- `files_touched` is real (via `git diff --name-only <merge-base> HEAD` + `git status --short --porcelain`), no longer hardcoded to `[]`.
- `cmd_migrate()` prints the resolved `DB_PATH` and fails loud with `MigrationImportError` on a 0-row import from a non-empty source, instead of a silent green banner.

**Vizor**
- **Architect Map v2** (PR #167): replaces the static tube-map SVG with a live force-directed graph of workspace repos and typed cross-repo edges, a side drawer (path/stack/GitHub/dispatch/Gantt-jump/active-dream-count), and an IDE-style file-tree sub-view.
- **Business Goals Panel** (PR #153): surfaces `goals`/`stories` rollups in the HUD.
- `__init__.py` re-modularized a second pass — 11 focused modules extracted (`synlynk/db.py`, `jobs.py`, `dispatch.py`, `context.py`, `sentinel.py`, `scheduler.py`, etc.), no more single-file monolith (PR #180).

### Fixed

**Dispatch git-finalization reliability chain (#182/#184/#185/#189/#190/#191/#196/#198, PRs #186/#187/#192/#193/#194/#195/#199/#201)**
- Dispatched agents (Codex/Agy) frequently completed real, tested work but didn't reliably finish their own git steps (commit/push/PR). synlynk now performs git finalization itself once, gated on a job's `running`→terminal transition (idempotent by construction) — stages everything except a hard-exclusion list, commits, pushes, opens a PR via `gh pr create` if none exists.
- Borrowed-worktree completions attributed via `origin/<branch>` state instead of being misread as zero-work.
- `HARNESS_INTERNAL_TIMEOUT` jobs now auto-retry (cap 2) instead of landing as a dead failure.
- A job that raced its own disk writes and landed `failed` with `0 touched` is re-inspected once and reclassified `failed_unverified` rather than staying permanently stale.
- Cost accounting no longer bypasses the per-model rate table in 3 places (including a hardcoded `gemini-2.5-pro` $0 bug); `local` gets an explicit $0.0 override regardless of model version.
- Capability router now filters on canonical `discipline`, not the legacy `engg_domain` column.
- Daemon queue launch unified through `dispatch_agent()` so worktree/preflight/permission-flags/concurrency-guard logic isn't duplicated across two divergent paths.
- Harness no longer misreports completed jobs as `FAILED` with fabricated token counts.

**Misc dispatch/CI hardening (PRs #163/#164/#165/#171/#173/#238/#240)**
- Codex sandbox gets `--add-dir <git-common-dir>` so it can write git refs inside a worktree.
- `dispatch --help`'s agent list now derives from `AGENT_CAPABILITY_BASELINES` instead of a stale hardcoded list.
- Stall-killer generalized to detect harness-internal timeouts and checks remote branch activity before hard-failing a silent job.
- 3 baseline CI flakes isolated from runner environment state; Python 3.8 compat fix for a `tuple[str, str]` annotation.
- `dispatch --context-mode full` now warns when used on a task that's already self-contained.

---

## [0.11.0] - 2026-07-05

**Release pitch:** synlynk v0.11.0 is the Agent Ecosystem Operational Layer — every dispatch now carries permissions and recovery paths, your terminal shows a live fleet of agents in real time, and the full workflow discipline is baked into every agent directive file at init.

### Added

**Agent Autonomy Bridge (BS-12, PR #119)**
- **`synlynk dispatch --grant <perm> --revoke <perm>`** — per-task permission overrides; role defaults in `.synlynk/config.json` map 12 roles (pm, review, implement, test, css, infra, etc.) to capability tiers. Resolved set translates to `--allowedTools` (Claude), `--ask-for-approval` (Codex), or a `## Permissions` context header (Agy).
- **`synlynk configure agent <name> [--flag k=v] [--env K=V] [--network-dep host:port]`** — write per-project harness overrides to `.agents/<agent>.json`; `dispatch_agent()` merges at call time: baseline → per-project overrides → per-task grant/revoke.
- **`synlynk jobs --stalled`** — list jobs with `HANDOFF_PENDING` sentinel (set when a job accumulates STALL_NO_OUTPUT, FLATLINE, or QUOTA_EXHAUSTED). Shows job ID, agent, failure sentinel, elapsed time, and recommended next agent.
- **`synlynk jobs handoff <job_id> [--to <agent>]`** — transfer a stalled job to a new agent; appends `## Handoff Note` to the job context file, increments `handoff_count`, updates `previous_agents` (JSON array), launches new dispatch with full context, clears `HANDOFF_PENDING`.
- **`synlynk doctor` TC-5** — scans each directive file for all 6 required SOP section headers; warns (non-blocking) if any are absent. Interactive fix wizard runs after each TC failure with structured fix paths (TC-1–5) and an "I'm stuck" escape that assembles failure context and dispatches Claude for conversational diagnosis.
- **`synlynk sync --repair-sops`** — re-injects missing SOP sections into directive files without touching existing harness fence content. Idempotent.
- **6 SOP blocks** written into CLAUDE.md, GEMINI.md, AGENTS.md, and GROK.md at `synlynk init` and `synlynk sync` time: PR Review Discipline · Brainstorm-First Policy · Design → Plan → Build Sequence · Capability-Based Task Allocation · Cost Visibility · Repo Hygiene.
- **`daemon_jobs` schema additions**: `handoff_count INTEGER DEFAULT 0`, `previous_agents TEXT` (JSON array). Migration applied automatically on first access.

**Live Job Observatory (BS-13, PR #117)**
- **`synlynk watch --live`** — fullscreen live job board: all running/recent jobs with agent, status, elapsed time, cost, and output tail; auto-refreshes every 3s; Ctrl-C to exit.
- **Vizor Observatory tab** — fifth tab in `synlynk viz` browser dashboard: real-time job fleet table (JS polling), per-agent status badges, cost rollup, job output drawer.

**Vizor Efficiency Enrichment (BS-22, PRs #113, #118)**
- **R/W/T budget bars** — per-agent card shows Read, Write, Test utilisation as percentage of TIER1_CAPACITY.
- **Cycle × Agent capability matrix** — `6 × 4` table (dream/plan/work/ship/maintain/engage × Claude/Agy/Codex/Grok) with full/partial/none badges (`cap-full`, `cap-partial`, `cap-none` CSS classes).
- **Per-agent radar hexagon SVGs** — 80×80px SVG radar on each agent card; 6-axis polygon filled at 30% opacity with agent theme colour; axis score maps `full`→1.0, `partial`→0.5, `none`→0.0.

**Ecosystem Status + Capacity (BS-16, PR #110)**
- **`synlynk status`** — terminal platform health: harness compliance table, agent availability, budget pulse (R/W/T capacity bars per agent), 6-cycle capability matrix.
- **`synlynk status --json`** — machine-readable ecosystem snapshot consumed by Vizor as its live data contract.
- **Three dispatch modes**: `eco` (respects R/W/T budget gates), `daily-grind` (default), `perf` (no budget gates).
- **Three new `_preflight_dispatch()` gates**: `CAPACITY_EXCEEDED_INPUT`, `CAPACITY_EXCEEDED_OUTPUT`, `TOOL_PRESSURE`.
- **New `state.db` tables**: `harness_status`, `cycle_capability`; `probe` command extended to seed Tier 1 capacity baselines.
- **`synlynk/status.py`** new module; `HarnessSnapshot` dataclass in `hud.py`.

**Modularisation (chore, PRs #103–#109)**
- Extracted `synlynk/__init__.py` (11,268L) into five focused modules: `synlynk/probe.py`, `synlynk/sentinel.py`, `synlynk/upgrade.py`, `synlynk/dispatch.py`, `synlynk/_constants.py`. `__init__.py` reduced to ~1,500L of orchestration and CLI surface.

### Fixed

**TC-2 dispatch fix arc (PRs #114–#116)**
- Fixed false-positive TC-2 failures caused by Agy `dispatch_flags` baseline including `--non-interactive` (valid for Agy but flagged as invalid by harness validator). Corrected per-agent flag baseline maps.
- Fixed `_run_tc2` seeding invalid flags into the passed list on first scan, blocking all subsequent Agy dispatches.
- `synlynk logs` now shows exit summary + TC-2 preflight gate result per dispatch.

**BS-12 review fixes**
- `--repair-sops` now merges missing SOP blocks into existing harness fence body instead of replacing the entire fence.
- TC-5 result wired into `all_passed` in `cmd_doctor`; doctor now exits non-zero when SOPs are missing.
- Handoff note included in `handoff_task` sent to new agent (was reading context before append).
- TC-5 fix menu scoped to agents with missing sections only (was firing for all agents in loop).
- `--flag KEY` (boolean flag without `=`) in `configure agent` now uses `partition` instead of crashing with `ValueError`.

**BS-22 review fixes**
- Removed `is_placeholder` short-circuit in SVG circles matrix that contradicted the new text capability matrix.
- CSS class `cap-{support}` now normalised to lowercase; prevents unstyled cells from mixed-case DB values.
- Removed unreachable dead-code fallback block in `get_capability_level()`.

### Changed
- `synlynk doctor` interactive fix wizard replaces silent print-and-exit after TC failures.
- `_check_job_stall()` now also writes `HANDOFF_PENDING` sentinel on STALL_NO_OUTPUT / FLATLINE / QUOTA_EXHAUSTED.
- `dispatch_agent()` merge layer: baseline → `.agents/<agent>.json` harness overrides → per-call `--grant`/`--revoke`.

---

## [0.10.0] - 2026-07-03

**Release pitch:** synlynk v0.10.0 is the Developer Preview — install it via pipx, set up your workspace in 60 seconds with the terminal wizard, and get a live browser dashboard that shows exactly what your agent team is doing.

### Added

**FTUE + Onboarding**
- **`synlynk init --wizard`** — FTUE typeform-style TUI wizard (6 screens: home harness detection, workspace topology, skills scan, agent fleet, role assignment, launch cheat sheet). Mandatory Phase 0 silent scan; writes workspace config, state.db, and role blocks into each agent's directive file. Ctrl-C before completion leaves no state.
- **`synlynk scan`** — re-runnable repo analysis: detects topology (single/mono/multi), fingerprints stack per repo/package via 14 file-presence heuristics, parses CLAUDE.md/GEMINI.md/AGENTS.md, maps to workspace in state.db, regenerates structured context.md. Flags: `--refresh`, `--add <path>`, `--remove <path>`, `--dry-run`.
- **`synlynk launch`** — FTUE task picker TUI with 6-cycle SDLC view (Dream · Plan · Work · Ship · Maintain · Engage); 12 scan-triggered launch templates (3 core + 9 stack-aware); dispatch preview screen; `synlynk open` replaces old `synlynk launch <agent>` for direct agent open. (BS-19, PR #94)
- **`synlynk roles`** — print current agent role table from `.synlynk/config.json`; `synlynk init` and `synlynk doctor` now generate per-agent directive role blocks (`## Your Role` in CLAUDE.md, GEMINI.md, AGENTS.md). (BS-12a, PR #95)

**State + Migration**
- **`synlynk migrate`** — one-shot atomic import of `project-docs/` markdown into state.db (8 steps: import → copy to `.synlynk/project-docs/` → `git rm` → `.gitignore` → sentinel → commit). After migration, every DB write immediately mirrors to `.synlynk/project-docs/` as a local backup (write-through). Flags: `--dry-run`, `--recover` (re-import from backup after DB loss), `--setup-dr` (configure cloud-synced DR folder).
- **`synlynk memory add`** / **`synlynk devlog append`** — write memory entries and devlog sessions to state.db with immediate flat-file write-through.
- **5 new state.db tables**: `memory_entries`, `roadmap_arcs`, `roadmap_phases`, `cost_entries`, `devlog_entries`; `gh_issue` column on `stories`.
- **DR sync** — configurable `dr_sync_path` in `.synlynk/config.json`; every write-through copy is also synced to a cloud-synced local folder (iCloud/GDrive/OneDrive). No OAuth, no new deps.

**Deep Scan**
- **`synlynk scan` (deep mode)** — 6-stage pipeline: repo fingerprint, dependency graph, test coverage ratio, doc coverage, CI health, churn density. Stage Cards TUI with progress indicators; scan fences written to state.db; `synlynk launch` templates upgrade automatically from scan signal data. 6 new scan fields: `test_ratio`, `readme_word_count`, `has_ci`, `has_docs`, `has_type_hints`, `has_orm`. (BS-20, PR #96)

**Daily-Driver Commands**
- **`synlynk jobs --summary <id>`** — after every job closes, print structured summary: files touched, exit status, cost, tokens, duration; append to `.synlynk/logs/<job_id>.summary`; readable via `synlynk jobs --summary <id>`. (PR #97)
- **`synlynk release`** — Ship cycle stub: bump VERSION, generate CHANGELOG entry from merged stories since last tag, write blog post stub in `docs/blog/`; `--dry-run` previews without writing. (PR #98)
- **`synlynk status --platform`** — infrastructure health view: harness compliance (last probe, any DRIFT sentinels), agent availability table (installed/version/TC status), budget pulse (daily/weekly burn rate). (PR #99)

**Browser Dashboard**
- **`synlynk viz`** — 5-view local browser dashboard generated from `state.db`, served at `http://localhost:8721`. Views: Gantt (accordion drill-down, stage bars, pencil notes), User Journeys (split-pane, `docs/journeys/*.md`), Architect Map (tube map SVG from `vizor-tube.json`), Effort & Cost (SVG bar charts), Efficiency (agent report cards + sentinel timeline). Sticky note system: `POST /note` → `viz-notes.json` → injected into `generate_context()` (visual annotation → AI context loop). Live JS polling + browser notifications. Zero new deps. (BS-21, PR #101)

**Packaging**
- **pipx packaging** — `pyproject.toml` with `[project.scripts]` entry point; VERSION is the single source of truth in `synlynk/__init__.py` (pyproject.toml reads it via dynamic attr). Install via `pipx install git+https://github.com/nikhilsoman/synlynk`.
- **`_detect_install_type()`** — detects pipx vs pip vs script install; `synlynk upgrade` routes to `pipx upgrade synlynk` when installed via pipx.

### Changed
- **`generate_context()`** routes to `_generate_context_from_db()` when `.synlynk/.synlynk_migrated` sentinel is present; reads from state.db (top story, recent devlog entries, recent memory sections).
- **`install.sh`** derives VERSION dynamically from `synlynk/__init__.py` instead of hardcoding.
- **Python requirement** raised from 3.8+ to 3.9+.
- **Refactor:** `main()` extracted to `synlynk/cli.py`; data-layer functions extracted to `synlynk/db.py`. Single-file `bin/synlynk.py` is now a thin dispatcher.
- README fully overhauled: pipx install, badge strip, wizard-first 60-second quickstart, state.db architecture, all new commands documented.

### Tests
- **747 tests** (up from 588 at v0.9.8); 28 new migrate tests, 28 launch/FTUE tests, 21 Vizor tests, 7 packaging tests, 40 deep-scan tests, full E2E round-trips.

---

## [0.9.8] - 2026-06-27

### Added
- **`synlynk exit`** — reverse all synlynk onboarding: strips managed sections from tracked
  instruction files (CLAUDE.md, GEMINI.md, etc.), removes `.agents/` profiles and `.synlynk/`
  directory, writes `SYNLYNK_HANDOFF.md` with re-init instructions. Dry-run by default;
  `--confirm` to execute. `--remove-docs` optionally removes `project-docs/`.
- **`synlynk repair`** — exit + immediate re-init from captured config (agents, mode, org, repo,
  docs-dir). Dry-run by default; `--confirm` to execute.
- **`synlynk sync`** — propagate updated synlynk artifacts (instruction file sections, missing
  `.agents/` profiles) to an existing repo without full re-init. Dry-run by default;
  `--confirm` to execute.
- **`_strip_synlynk_section(path, marker_style)`** internal helper — removes synlynk-managed
  block from any instruction file; handles html/hash/none marker styles; leaves surrounding
  user content intact.

### Changed
- VERSION bumped `0.9.7 → 0.9.8`

---

## [0.9.7] - 2026-06-26

### Added
- **Grok as a first-class fourth agent peer** alongside claude/agy/codex across all synlynk subsystems
- `AGENT_CAPABILITY_BASELINES["grok"]` — cli, non_interactive_flags (`-p`), prompt_via_arg, dispatch_flags
  (`--always-approve`), roles (builder/architect), strengths
- `AGENT_DISCOVERY_DEFAULTS["grok"]` — discovery path `~/.grok`
- `_probe_model_version` — `grok -v` probe + `grok-[\w.-]+` version pattern
- `GROK.md` template — identity (`Co-Authored-By: Grok <noreply@x.ai>`), branch prefixes
  (`feat/grok/`, `fix/grok/`), standard session/worktree/live-issues sections, `synlynk:start/end` markers
- `_INSTRUCTION_TARGETS` + `_MARKER_STYLE_FOR_TOOL` entries for GROK.md
- Init wizard: GROK.md in `trio_content` + `_agent_guards`; `agent_slots` default expanded to four agents;
  `--agents` default updated to `claude,agy,codex,grok`
- `_inject_grok_rules()` — prepends `--rules GROK.md` for all grok exec calls; adds
  `--rules .synlynk/context.md` in headless (`-p`) mode; silently skips missing files
- `dispatch_agent()` — `--always-approve` → `--permission-mode bypassPermissions` fallback via
  agent profile `always_approve_unsupported`; `--output-format json` for grok headless dispatch
- `extract_tokens()` — nested `usage.input_tokens/output_tokens` pattern for Grok JSON output
- `extract_model_version()` — tier-2 path via `.agents/grok.json` `"model"` field
- `GROK.md` written to the synlynk repo itself (100 lines, markers bookending)
- 15 new tests covering all registration, instruction file, init wizard, exec injection, dispatch,
  and token/model extraction paths

### Fixed
- Stale time-sensitive fixture in `test_collect_capability_drop_returns_finding` — hardcoded
  2026-06-21 timestamps replaced with `datetime.now(timezone.utc)`-relative values

---

## [0.9.3] - 2026-06-23

### Added
- `SynlynkDaemon` class — subclasses `WatchDaemon` to add an embedded HTTP server thread on
  `localhost:27471` and persistent job dispatch on every poll tick; double-fork daemonization
  inherited from `WatchDaemon`; separate pidfile `.synlynk/daemon.pid` and log `.synlynk/daemon.log`
- `daemon_jobs` table in `state.db` — persistent job queue with `priority` (1–10), `depends_on`
  (JSON array of job IDs), and full status lifecycle `queued → running → done | failed`
- `_reconcile_daemon_jobs()` — reaps finished child processes using `os.waitpid(WNOHANG)` (zombie-safe),
  reads `.exit` files for exit codes, updates `status`/`exit_code`/`completed_at` in state.db
- `_dispatch_ready_jobs(max_parallel)` — launches queued jobs respecting concurrency cap and dependency
  chains; propagates `failed` status to downstream dependents immediately; commits per-job for
  crash-safe restart semantics
- HTTP API on `localhost:27471` — 10 endpoints: `GET /context`, `GET /status`, `GET /jobs`,
  `GET /jobs/<id>`, `POST /dispatch`, `GET /stories`, `GET /stories/<id>`, `GET /capability`,
  `GET /sentinel`, `POST /checkpoint`; `_ReuseAddrHTTPServer` subclass prevents `Address already
  in use` on rapid restart; `threading.Lock` guards concurrent `generate_context()` calls
- `synlynk daemon start|stop|status|restart` CLI command
- `synlynk daemon --install-service` — writes and activates platform service unit:
  macOS: `~/Library/LaunchAgents/com.synlynk.daemon.plist` via `launchctl load -w`;
  Linux: `~/.config/systemd/user/synlynk-daemon.service` via `systemctl --user enable --now`;
  Fallback: `@reboot` crontab entry
- `synlynk daemon --uninstall-service` — reverses each platform path; handles `FileNotFoundError` gracefully

### Fixed
- Daemon zombie process detection: replaced `os.kill(pid, 0)` with `os.waitpid(WNOHANG)` so
  exited child processes are properly reaped rather than staying `running` indefinitely
- Dependency deadlock: queued jobs whose dependency fails are immediately marked `failed` rather
  than staying queued forever
- Transaction isolation in dispatch: each launched job is committed individually so a crash
  mid-loop cannot produce duplicate spawns on restart

---

## [0.9.2] - 2026-06-22

### Added
- `synlynk join` — new member onboarding: seeds a devlog stub for the joining user, regenerates
  AI context files (CLAUDE.md, GEMINI.md, AGENTS.md) with the joining member's identity, and
  prints a team digest showing all active members and their recent focus areas
- `synlynk team status` — team digest view: lists all members with devlog presence, current
  story assignments, token budget consumption, and last-active timestamp; reads
  `project-docs/devlogs/<user>.md` across all contributors
- `synlynk decide <topic> --panel <agents>` — multi-agent consensus panel: dispatches the
  panel agents non-interactively with the same decision prompt, collects structured
  `DECISION:` blocks from each response, computes a consensus position, and optionally
  writes a signed `Decision` record to `project-docs/decisions/YYYY-MM-DD-<topic>.md`
  with `--record` flag
- `--tokens <N>` flag on `synlynk story create` — set an estimated token budget for a story;
  stored in new `estimated_tokens` column on the `stories` table
- `_seed_devlog(username, root)` helper — writes a devlog stub for the joining user with an
  initial entry so the devlog file exists and is attributable in team digests from day one
- `_generate_ai_context_files(username, root, config)` helper — regenerates CLAUDE.md,
  GEMINI.md, and AGENTS.md with the joining member's name in the `git config user.name` slot
- `_build_team_digest(root)` helper — reads all devlogs from `project-docs/devlogs/`, extracts
  last-active date and focus summary per member; used by both `join` and `team status`
- `_check_upstream_divergence(root)` helper — checks whether the local branch is behind the
  remote before any write to `project-docs/`; prints a warning with advice to `git pull` if
  divergence is detected; continues without blocking so offline workflows still function
  (pull-before-write arbitration)

### Fixed
- None in this release

---

## [0.9.1] - 2026-06-22

### Added
- `--docs-dir <path>` flag on `synlynk init` — override the default `project-docs/` location
  for repos that store docs elsewhere (e.g. `--docs-dir docs/project`)
- `_docs_dir(root, config)` helper — reads `docs_dir` from `.synlynk/config.json`, falls back
  to `project-docs/`; used by `exec`, `checkpoint`, `status`, and `init` so every command
  respects the configured docs location

### Fixed
- Installed binary (`~/.synlynk/bin/synlynk`) crashed with `ModuleNotFoundError: No module
  named 'synlynk'` when invoked outside the source repo after the v0.9.0 package split.
  Fixed by embedding the package `synlynk/` directory in `~/.synlynk/lib/synlynk/` at install
  time and prepending `$HOME/.synlynk/lib` to `sys.path` in the installed shim.
- `synlynk init` in a repo with existing `project-docs/` overwrote the existing docs with
  blank templates. Fixed by detecting existing files via `_find_existing_doc()` and migrating
  their content to the new location (or skipping write if no relocation is needed).

---

## [0.9.0] - 2026-06-21

### Added
- Scoped dispatch context: `exec` now injects a per-task section (`## Current Task`) with
  only the relevant plan block instead of the full devlog, reducing context window usage
- `## Relevant Files` injected per dispatch from the source map — derived from the task
  description matched against `source-map.md` symbols
- `## How to Verify` contract injected per dispatch — specifies acceptance criteria the agent
  should validate before declaring the task done
- Per-agent prompt framing: Claude, AGY, and Codex each receive a tailored preamble that
  matches their CLI interaction model (conversational vs. task-oriented vs. non-interactive)
- Ed25519 capability rating signing: every `capability_ratings` row is signed with the project
  key so ratings cannot be forged across project boundaries
- Anti-gaming quality cap: `test_count < 3` stories are capped at quality score 5.0 regardless
  of other signals, preventing artificially inflated ratings for untested work
- `synlynk/` package split: all ~5000 lines of application logic moved from `bin/synlynk.py`
  into `synlynk/__init__.py`; `bin/synlynk.py` becomes a 5-line import shim

### Fixed
- `capability_ratings` entries were not being attributed to the correct project when multiple
  synlynk-managed repos shared the same `~/.synlynk/` directory — Ed25519 project key now
  scopes all ratings correctly

---

## [0.8.0] - 2026-06-21

### Added
- `synlynk agent run` — foreground support engineer investigation: collects signals, formats a
  structured report, and offers to file a GitHub issue or draft a fix PR
- Five signal collectors for the support engineer archetype: failing tests, flaky tests,
  coverage gaps, stale dependencies, open GitHub issues exceeding age threshold
- 7-day and 30-day deduplication: signals already filed within the window are suppressed so
  the agent doesn't file duplicate issues on repeated runs
- `synlynk agent --install-cron` — registers a launchd plist (macOS) or systemd timer
  (Linux) that runs the support engineer agent on a configurable schedule
- `.agents/` config directory: `support-engineer.json` defines signal weights, age thresholds,
  and notification channels per project; read by `synlynk agent run` at startup
- GitHub issue filing via `gh issue create` with structured body including signal summary,
  affected files, and suggested fix skeleton
- Draft fix PR creation via `gh pr create` for issues with high-confidence fix candidates

---

## [0.7.0] - 2026-06-20

### Added
- `synlynk scan` / `synlynk scan --deep` — language-agnostic source scanner: reads file tree,
  extracts top-level symbols from Python/JS/TS/Go/Rust/Ruby/Java/C/C++ source, writes
  `source-map.md` and populates `source_symbols` table in `state.db`
- `## Source Architecture` section injected into every `exec` context from the cached scan
  result, giving agents a structural overview without reading individual files
- Passive git-HEAD cache: scan results are keyed to the current git HEAD SHA; a re-scan is
  only triggered when HEAD changes, not on every `exec` call
- `synlynk scan --status` — shows last scan timestamp, HEAD SHA, and symbol count without
  re-scanning
- Dual storage: symbols written to both SQLite `source_symbols` table (queryable) and
  `source-map.md` (human-readable, injected into agent context)
- Language detection by file extension with fallback to content heuristics

### Fixed
- `synlynk scan` no longer traverses `.git/`, `node_modules/`, or `.synlynk/` directories

---

## [0.6.1] - 2026-06-17

### Added
- Instruction reach to seven additional IDE/editor targets: Cursor (`.cursor/rules/`),
  GitHub Copilot (`.github/copilot-instructions.md`), Windsurf (`.windsurfrules`),
  Cline (`.clinerules`), Aider (`.aider.conf.yml`), Continue (`.continue/config.json`),
  and Sourcegraph (`.sourcegraph/memory.md`)
- SHA manifest (`instructions.json`) tracking the synlynk-managed section hash for each
  generated file; used for drift detection
- Runtime drift detection: `exec` warns if any tracked instruction file's section has been
  externally modified since last generation
- `synlynk instructions status / diff / update / ack` — manage instruction file state
- Task status model: 5 states (`active`, `done`, `deferred`, `superseded`, `absorbed`);
  deferred tasks are included in context with reduced weight; `checkpoint` archives resolved
  states to a separate section
- AGY CLI replaces Gemini CLI throughout: all references to `gemini` updated to `agy`
- VERSION synced to GitHub releases (was incorrectly stuck at 0.4.x)
- `DB_PATH` centralised to `~/.synlynk/projects/<git-root-hash>/state.db` so the database
  is shared across worktrees of the same project

---

## [0.6.0] - 2026-06-14

### Added
- Model version tier-2 probe: `discover_agents()` now probes for Opus/Sonnet/Pro variants in
  addition to the base model, annotates capability entries with `model_tier`
- `synlynk pr check` — validates that the current branch's diff satisfies the story's
  acceptance criteria before opening a PR; exits non-zero if criteria unmet
- `synlynk score attest` — manually attest a story's quality score with a signed reason;
  appended to `capability_ratings` with `attestation=true` flag
- Verifier pipeline output capture: `run --trio` now captures and surfaces the Verifier
  agent's structured review comment
- Tokq `org_domain_tags` capability dimension: stories can be tagged with domain taxonomy
  labels (`backend/api`, `frontend/ui`, etc.) for cross-project capability aggregation
- Constraint propagation: blocking story constraints propagate to child tasks; dispatching a
  child task for a blocked story emits a warning and requires `--force`

---

## [0.5.0] - 2026-06-14

### Added
- SQLite WAL state database (`~/.synlynk/projects/<hash>/state.db`) replacing the flat JSON
  job store; WAL mode enables concurrent reads from multiple agent processes
- Model-aware routing: `dispatch` selects agent by matching story domain tags against
  `capability_ratings`; no domain match falls back to round-robin
- 3D domain taxonomy for capability rating: `(agent, domain, model_tier)` composite key
  replaces flat per-agent scores
- Quality signal hierarchy: test coverage, PR review comments, story completion rate, and
  task duration all feed the capability score; weights configurable in `.synlynk/config.json`
- `synlynk story create <title>` — create a new story in `state.db` with optional domain,
  priority, and acceptance criteria
- `synlynk story list` — list stories with status, domain, assignee, and capability score
- `synlynk score` — print capability score breakdown for all agents across all domains

---

## [0.4.2] - 2026-06-17

### Added
- Task status model (`active` / `done` / `deferred` / `superseded` / `absorbed`) added to
  the context schema; deferred tasks included in `context.md` with a `[deferred]` prefix
- `checkpoint` archives all resolved-state tasks to a `## Resolved Tasks` section rather than
  deleting them — preserves decision history while keeping the active list clean
- Agent instruction templates updated to explain the 5-state model and checkpoint archival

---

## [0.4.1] - 2026-06-17

### Added
- Section marker system: synlynk-managed blocks in instruction files delimited by
  `<!-- synlynk:start -->` / `<!-- synlynk:end -->` markers so user customisations outside
  those markers are preserved on regeneration
- SHA manifest (`instructions.json`): tracks content hash of the synlynk section in each
  generated file; used for drift detection
- `synlynk instructions status / diff / update / ack` — full CLI for managing instruction
  file drift
- `DB_PATH` centralised: all state now written to `~/.synlynk/projects/<git-root-hash>/`
  rather than `.synlynk/` within the project, so the database is shared across all worktrees
  of the same project

### Fixed
- `init` no longer regenerates files that already contain a synlynk section — protects user
  customisations from accidental overwrite

---

## [0.4.0] - 2026-06-14

### Added
- `AGENT_CAPABILITY_BASELINES` — hardcoded capability dict for claude/gemini/codex/agy with
  `cli`, `non_interactive_flags`, `roles`, and `strengths` per agent
- `discover_agents(config)` — probes each known agent CLI with `--version`, returns functional
  agents with their roles and capabilities; supports per-project path overrides via config
- `_static_scan(root)` — reads git log, README, and file tree to produce a structured project
  context dict (project name, commit count, languages, recent topics)
- `_write_informed_skeleton(scan)` — writes project-docs/ first draft using scan results
  instead of blank placeholders
- `_llm_enrich(agent_name, agent_cli, scan)` — opt-in step that calls the best available agent
  non-interactively to synthesise an informed `roadmap.md` from scan results
- `init()` refactored to a 6-step wizard: scan → **Magic Moment 1** (workgroup discovery table
  showing all detected agents with roles) → doc bootstrap → LLM enrichment offer → cloud nudge
  → finalise config
- `dispatch_agent(agent, task, story_id)` — launches agent CLI in background using
  `subprocess.Popen(start_new_session=True)`, captures stdout to `.synlynk/logs/<job_id>.log`,
  writes PID and job metadata to `.synlynk/jobs.json`
- `_load_jobs()`, `_save_jobs(jobs)` — read/write `.synlynk/jobs.json`
- `_reconcile_jobs()` — probes PIDs of running jobs via `os.kill(pid, 0)` on every startup;
  marks unreachable PIDs as failed/completed; called as first action in `main()`
- `synlynk dispatch <agent> --task <text> [--story <id>]` — **Magic Moment 2**: fire and
  forget agent dispatch from any shell
- `synlynk jobs [--all]` — list running/recent jobs with status, agent, and task
- `synlynk logs --job <id> [--tail N]` — tail the log file for a job
- `synlynk shell [--story <id>]` — open an interactive agent shell with story context injected
- `synlynk launch <agent> [--story <id>]` — interactive launcher that prompts for task before
  dispatching
- `synlynk run --trio <task>` — dispatches the same task to all functional agents in parallel
  (Architect, Builder, Verifier roles)
- ANSI colour helpers (`_BOLD`, `_GREEN`, `_YELLOW`, `_CYAN`, `_DIM`, `_RESET`) for wizard UI

### Fixed
- `_reconcile_jobs()`: `PermissionError` from `os.kill(pid, 0)` means the process exists (owned
  by another user) — no longer crashes the CLI; job correctly stays `running`
- `_reconcile_jobs()`: empty `log_file` no longer accidentally reads/deletes an unrelated
  `.exit` file in the current working directory
- `_llm_enrich()`: baselines now indexed by canonical agent name (not CLI binary path), so
  custom CLI paths still resolve the correct non-interactive flags

### Infrastructure
- 5 new reconcile/enrich tests; 4 new E2E tests (dispatch, jobs, logs, reconcile startup)
- 188 tests total (up from 140)

---

## [0.3.0] - 2026-06-03

### Added
- Enriched agent instruction templates: CLAUDE.md, GEMINI.md, AI_INSTRUCTIONS.md now include
  Live Issues SOP (Sev1/Sev2/Sev3 with RCA doc path pattern), Git Worktree-First Policy,
  per-agent branch naming and commit trailers, Mid-Session Anti-Amnesia Protocol (Phase 1/2
  cadence), Mandatory 4-Doc Discipline, and GitHub Projects v2 GraphQL integration block with
  parameterizable `PROJECT_ID`
- `AGENTS.md` — new Codex agent instruction file, generated at repo root on `synlynk init`
- `synlynk init --agents <claude,agy,codex>` — controls which agent files are generated
  (default: all three). Omit an agent to skip its file
- `synlynk init --mode <solo|team>` — writes `project-docs/.synlynk_config.json` with the
  chosen mode at init time (previously this file had to be created manually)
- `synlynk init --org <org>` — stores GitHub org name in `.synlynk/config.json`
- `synlynk init --repo <repo>` — stores GitHub repo name in `.synlynk/config.json`
- `synlynk init --project-id <id>` — fills GitHub Projects v2 node ID into all generated agent
  files, replacing the `TODO: PROJECT_ID` placeholder
- GEMINI.md includes AGY/Gemini CLI transition note: file is shared by Gemini CLI (until
  2026-06-18) and AGY CLI (AntiGravity) thereafter; no migration of the file is needed
- `_build_templates(org, repo, project_id)` internal function replaces the static `TEMPLATES`
  dict and `_SESSION_PROTOCOL` string, enabling parameterized template generation

### Changed
- `synlynk init` now writes `project-docs/.synlynk_config.json` directly (previously missing
  from init, requiring manual creation)

---

## [0.2.1] - 2026-05-17

### Fixed
- `exec_command()` now returns the child process exit code and `main()` calls `sys.exit()` with it — previously a wrapped command exiting non-zero would cause `synlynk exec` to exit 0, silently swallowing failures
- `parse_costs_md()` was reading the wrong column (`parts[6]` = Summary instead of `parts[5]` = Estimated Cost USD), causing `status` and budget checks to always report $0.00
- `install.sh` version corrected from `1.2.0-lite` to `0.2.0`
- `conftest.py` fixture schema aligned with real `costs.md` format (6-column) so budget tests exercise the correct parser behavior

### Removed
- Dead functions `log_telemetry()`, `extract_tokens()`, and `update_costs()` — superseded by `log_telemetry_event()` and manual cost tracking; removed to prevent confusion

### Infrastructure
- `.gitignore` expanded to cover `.synlynk/`, `__pycache__/`, `*.pyc`, `.DS_Store`, `test_archive/`, `test_context_output/`, `.venv/`
- `project-docs/roadmap.md` updated to reflect v0.2.x reality (was stale with v1.2/v1.3/v1.4 references)
- Test added for exit code propagation (47 tests total)

---

## [0.2.0] - 2026-05-17

### Added
- `synlynk watch start/stop/status` — background daemon that polls `project-docs/` and regenerates `context.md` on any file change, with configurable interval and debounce
- `synlynk checkpoint` — archives completed `[x]` tasks from `todo.md` into the user devlog, refreshes context, and emits a structured telemetry event
- `synlynk status` — project state dashboard showing active tasks, last checkpoint, sentinel alerts, budget, and watcher state; `--json` flag for machine-readable output
- `synlynk init --force` — overwrite existing template files
- `set_state()` — writes `.synlynk/state` and updates terminal title with state icon (`●` watching / `⚡` active / `○` stopped)
- Helper functions: `get_username()`, `get_mode()`, `load_config()`, `parse_costs_md()`
- `log_telemetry_event()` — structured event logging with `schema_version` and `type` fields
- `_check_costs_freshness()` — warns when `costs.md` has not been updated within the current session
- Devlog archiving: entries older than 30 days moved to `devlogs/archive/YYYY-MM.md`

### Changed
- `generate_context()` — now compacts output: excludes completed `[x]` tasks, includes only "In Progress" roadmap rows, injects sentinel alerts at top when present, scoped to last 7 days of devlog
- `check_budgets()` — now reads cumulative spend from `costs.md` instead of telemetry; request count sourced from telemetry `type=exec` events
- `check_flatline()` — now writes alerts to `.synlynk/sentinel.md` in addition to stdout
- `exec_command()` — uses `subprocess.Popen` (no stdout capture) for full TTY interactivity with Claude Code and Gemini CLI
- `CLAUDE.md` / `GEMINI.md` templates — include full session protocol: startup checklist, during-session rules, session-end steps
- `VERSION` bumped to `0.2.0`

### Fixed
- Type hint `str | None` replaced with `Optional[str]` for Python 3.8 compatibility (union syntax requires 3.10+)

### Infrastructure
- Added pytest test suite (`tests/conftest.py` + `tests/test_synlynk.py`) with 46 tests and `project_dir` fixture
- Added GitHub Actions CI workflow (runs pytest on Python 3.8, 3.10, 3.12 on push and PRs)
- Added `LICENSE` (MIT), `CONTRIBUTING.md`, PR template, issue templates

---

## [0.1.0] - 2026-05-14

Initial public release.

### Added
- `synlynk init` — bootstraps `project-docs/` (roadmap, todo, memory, costs, devlogs) and writes `CLAUDE.md`, `GEMINI.md`, `AI_INSTRUCTIONS.md`, `.cursorrules` and `.synlynk/config.json`
- `synlynk exec <cmd>` — wraps any AI CLI: injects context, checks budget, logs telemetry, detects flatline loops
- `synlynk upgrade` — checks GitHub releases API for newer versions
- `generate_context()` — compiles `project-docs/` into `.synlynk/context.md`
- `check_flatline()` — detects 3 consecutive failures of the same command
- `check_budgets()` — warns at 80% of configured USD/request limits
- `log_telemetry()` — rolling JSON log of last 100 exec events
- `install.sh` — global installer, adds synlynk to `~/.synlynk/bin/` and PATH

[Unreleased]: https://github.com/nikhilsoman/synlynk/compare/v0.3.0...HEAD
[0.3.0]: https://github.com/nikhilsoman/synlynk/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/nikhilsoman/synlynk/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/nikhilsoman/synlynk/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/nikhilsoman/synlynk/releases/tag/v0.1.0
