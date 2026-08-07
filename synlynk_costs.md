# synlynk — Claude Code Session Costs

## Running Estimate

| Tier | Count | Rate | Subtotal |
|---|---|---|---|
| Light (~$1) | 0 | $1 | $0 |
| Medium (~$2–3) | 0 | $2.50 | $0 |
| Heavy / brainstorm-driven (~$4–6) | 6 | $4.70 | $28.18 |
| **Total to date** | | | **~$28.18** |

No cloud infra running (pure Python CLI, no AWS/GCP).

---

## Session Log

| Date | Description | Input Tok | Output Tok | Cache Read Tok | Input Cost | Output Cost | Total |
|---|---|---|---|---|---|---|---|
| 2026-06-07 | Design marathon: state-db + agentic PM, agent identity + dispatch, workspace + multi-repo, arc gap analysis, schedule recast. 3 brainstorm sessions with visual companion. 4 specs written. PR #28 opened. | ~160K | ~80K | ~160K | ~$0.48 | ~$1.20 | ~$3.50 |
| 2026-07-04 | BS-13 Workspace HUD: brainstorm (5 sections + visual companion), spec + plan (10 tasks), Codex+Grok dispatch, PR #106 merged (357L hud.py, 30 tests). Upgrade audit: 6 bugs diagnosed + fixed across PR #107 + #108 (21 upgrade tests). 791 total tests passing. | ~250K | ~80K | ~500K | ~$0.90 | ~$1.20 | ~$5.00 |
| 2026-07-11 | Epic #137 close-out: fleet dispatch scheduler design + plan, Grok dispatch, review, PR #156 + #157 merged, deferred v2 goal created, blog post 52, devlog/memory/cost housekeeping. | ~110K | ~55K | ~100K | ~$0.33 | ~$0.83 | ~$4.50 |
| 2026-07-12 | Vizor Architect Map v2: brainstorm (task #10) + spec + plan (8 tasks) + Subagent-Driven Development execution — 8 sequential Codex dispatch rounds with two-stage review each, PR #167 opened and merged, blog post 53 (fixed a same-number collision with #156/#157's post 52), CI baseline flake investigated (linked to existing #134, not a new live issue), full worktree/branch cleanup, roadmap/devlog/memory housekeeping. | ~160K | ~80K | ~160K | ~$0.48 | ~$1.20 | ~$4.33 |
| 2026-07-26 | Cost/capability report direct from `state.db` (PR #541). Open-PR backlog triage: 38 open, 24 closed (superseded plan-task PRs, resolved review-report wrappers, malformed artifacts, git-ancestry-confirmed absorptions). #521/#529 architectural review (PR #560) — found #521 fully absorbed into #529 via git ancestry, then caught 4 failing tests on #529's own HEAD (incl. the exact rollback scenario it claims to fix) by running the suite directly rather than trusting the PR description. Discovered and reconciled with an autonomous LIVE-3 incident (PR #542 merge deleted 13 untracked-regen files; already RCA'd and recovered by the dispatch pipeline before this session caught up). | ~160K | ~80K | ~160K | ~$0.48 | ~$1.20 | ~$1.73 |
| 2026-08-05/06 | Synlynk UX 1.0 (PR #731): full 12-task plan executed via `synlynk dispatch` (Codex/Grok/Agy), each task independently verified (not trusted from job status alone) against a recurring stale-worktree-base failure mode (fixed via rebase-before-verify, now a standing pattern). Final regression pass caught 3 cross-cutting gaps per-task tests missed: missing `tui` taxonomy entry, an obsolete pre-rewire test, stale generated `docs/reference/commands.md` — fixed in one scoped Codex job, full suite verified clean (1660 passed). PR #731 reviewed/merged by Agy as non-authoring reviewer. Blog post #99 dispatched to Agy → PR #746; review dispatch chain hit two failures caught by direct verification rather than trusting job output — Codex flagged a false "not docs-only" diff (stale local `main`, no real conflict) and has no GitHub network access (should have routed to Grok per #426 from the start); Grok's session then expired mid-review (`cancelled`) after surfacing one real, minor inaccuracy (post overclaimed `notify` was added to `taxonomy.py`). Escalated to Claude per the reviewer-unavailable fallback: fixed the inaccuracy directly, ran `pr check`, reviewed, merged. | ~700K | ~180K | ~4.6M | ~$3.34 | ~$2.70 | ~$9.12 |
