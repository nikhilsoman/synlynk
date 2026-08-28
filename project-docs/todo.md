# Task Execution Order and Dependencies

## Recently Landed (since last sync)
- [x] v0.15.0 — Workspace Policy Layer
- [x] v0.16.0 — Autonomous Loop
- [x] v0.17.0 — Ticket-Driven Approval Auto-Resume
- [x] v0.18.0 — Dispatch Reliability & QA Merge-Gate Authority
- [x] Charter authority design + injection mechanism spec (PR #1193) — content/structure follow-up spec also drafted, plan not yet dispatched
- [x] Harness capability baseline + recurring reassessment protocol (`docs/harness-capability-baseline.md`, PR #1178, 2026-08-25) — tracked ongoing via #1179
- [x] LIVE-9 (`jobs --all` datetime crash) + LIVE-10 (branch-protection `enforce_admins` regression) — RCAs written, fixes merged
- [x] #1209 — Codex dispatch `--ask-for-approval` flag mismatch (PR #1210, merged 2026-08-28, issue closed 2026-08-29)
- [x] #1211 — macOS launchd daemon `KeepAlive` missing `SuccessfulExit: false` (PR #1212, merged 2026-08-28, issue closed 2026-08-29)
- [x] #332/#338/#340/#348/#419/#461/#786/#936/#860 — all confirmed CLOSED on GitHub; stale in this file for weeks, removed from Next Task below

## Next Task
- [ ] Fleet-parity remainder (only #342 and #347 of the original cluster are still open; #332/#338/#340/#348/#419/#461 all closed — see Recently Landed)
- [ ] #573 — Agy+Stitch MCP integration
- [ ] #914 — Workspace-level (multi-repo) agent identities — still untriaged into a phase
- [ ] #937 — Review-dispatch job wrote to docs/ outside its read-only scope (job-0c924723, PR #933)
- [ ] #1179 — Harness capability reassessment recurring cycle (parent/tracking; first cycle due ~25 jobs from creation or 2026-09-25)
- [ ] #1213 — Automated live in-sandbox gh-write probe (re-scoped 2026-08-29 as concrete implementation under #1179, not a duplicate mechanism — see issue comment)
- [ ] #1201 — Wire charter content into dispatch/execution context (implements PR #1193's surfacing mechanism; charter content/structure design spec drafted, plan not yet written)
- [ ] #1198 — [Tracking] Autonomous Operations Activation
- [ ] #1202 — Standardize harness vs. agent terminology across codebase and docs
- [ ] #1203 — Design GOVERNS backlog automation (auto-associate discovered/open/planned work with issues) — needs brainstorm first
- [ ] #1188 — pipx-installed synlynk drifts silently from repo VERSION until schema-mismatch crash
- [ ] #1194 — `synlynk decide --record` writes decision docs to gitignored path once repo is 'migrated'

## Review Queue
- [ ] PR #1195, #1214, #1215 — open docs-only PRs, each needs a non-authoring reviewer dispatched + `synlynk pr check` before merge
