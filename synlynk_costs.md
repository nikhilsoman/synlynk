# synlynk — Claude Code Session Costs

## Running Estimate

| Tier | Count | Rate | Subtotal |
|---|---|---|---|
| Light (~$1) | 0 | $1 | $0 |
| Medium (~$2–3) | 0 | $2.50 | $0 |
| Heavy / brainstorm-driven (~$4–6) | 4 | $4.33 | $17.33 |
| **Total to date** | | | **~$17.33** |

No cloud infra running (pure Python CLI, no AWS/GCP).

---

## Session Log

| Date | Description | Input Tok | Output Tok | Cache Read Tok | Input Cost | Output Cost | Total |
|---|---|---|---|---|---|---|---|
| 2026-06-07 | Design marathon: state-db + agentic PM, agent identity + dispatch, workspace + multi-repo, arc gap analysis, schedule recast. 3 brainstorm sessions with visual companion. 4 specs written. PR #28 opened. | ~160K | ~80K | ~160K | ~$0.48 | ~$1.20 | ~$3.50 |
| 2026-07-04 | BS-13 Workspace HUD: brainstorm (5 sections + visual companion), spec + plan (10 tasks), Codex+Grok dispatch, PR #106 merged (357L hud.py, 30 tests). Upgrade audit: 6 bugs diagnosed + fixed across PR #107 + #108 (21 upgrade tests). 791 total tests passing. | ~250K | ~80K | ~500K | ~$0.90 | ~$1.20 | ~$5.00 |
| 2026-07-11 | Epic #137 close-out: fleet dispatch scheduler design + plan, Grok dispatch, review, PR #156 + #157 merged, deferred v2 goal created, blog post 52, devlog/memory/cost housekeeping. | ~110K | ~55K | ~100K | ~$0.33 | ~$0.83 | ~$4.50 |
| 2026-07-12 | Vizor Architect Map v2: brainstorm (task #10) + spec + plan (8 tasks) + Subagent-Driven Development execution — 8 sequential Codex dispatch rounds with two-stage review each, PR #167 opened and merged, blog post 53 (fixed a same-number collision with #156/#157's post 52), CI baseline flake investigated (linked to existing #134, not a new live issue), full worktree/branch cleanup, roadmap/devlog/memory housekeeping. | ~160K | ~80K | ~160K | ~$0.48 | ~$1.20 | ~$4.33 |
