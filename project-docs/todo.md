# Task Execution Order and Dependencies

## Active Task
- [x] Two-imperatives roadmap cluster (job-truth/gh-write, workspace-context-governance, worktree/job cleanup (#559), `agent`→`harness` CLI rename (PR #993), Agent-roles-charters Phase 1 (PR #1003)) — landed 2026-08-15/16, cut as v0.14.0 (PR #1012)
- [x] PR #1003 follow-up cleanup: `capability_grants` merge-not-replace, `daemon_jobs.agent_id` persistence (PR #1022) — landed 2026-08-16/17
- [x] Agent-roles-charters Phase 2: memory-gated capability routing via synthetic per-org-role story (PR #1030) — landed 2026-08-17
- [x] Dependabot: 2 high-severity vulnerabilities on main — re-checked 2026-08-17, zero open/historical alerts via `gh api dependabot/alerts`; stale entry, already resolved (dependency bump in an intervening PR, or Dependabot auto-closed)

## Next Task
- [ ] Fleet-parity audit (#332/#338/#340/#342/#347/#348/#419/#461)
- [ ] #573 — Agy+Stitch MCP integration
- [ ] #786 — Rename internal 'agent' nomenclature to 'harness' (CLI, DB columns, docs) — broader than PR #993's CLI-verb-only rename; re-scope against the now-shipped agent-roles-charters `agent` (workspace identity) vs `harness` (execution backend) split before starting, may be partially/fully superseded
- [ ] PR #1030 deferred scope: "jobs by agent" view / cost attribution on `daemon_jobs.agent_id` (persisted since PR #1022, still unconsumed); `capability_grants` enforcement during harness selection (Phase 2 added learned *scoring*, not grant *enforcement*)
- [ ] #914 — Workspace-level (multi-repo) agent identities — flagged as possibly adjacent during Phase 2 brainstorm, not yet triaged into a phase
- [ ] #937 — Review-dispatch job wrote to docs/ outside its read-only scope (job-0c924723, PR #933)
- [ ] #936 — Workspace context divergence: state.db silently disagrees with project-docs/* markdown
- [ ] #860 — Job self-report status still unreliable, recurs after #461 closed COMPLETED
