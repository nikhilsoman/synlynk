# Tasks (generated - source of truth is state.db)
# Edit via: synlynk story create/update | Do NOT hand-edit this file

- [x] feat: synlynk v0.2.0 — watch daemon, checkpoint, status command, context compaction [cli] <!-- id:story-pr1 -->
- [x] fix: synlynk v0.2.1 — correctness patch [cli] <!-- id:story-pr3 -->
- [x] fix: resolve GitHub username and upgrade check via gh CLI [cli] <!-- id:story-pr23 -->
- [x] chore: bump version to 0.2.2 [docs] <!-- id:story-pr24 -->
- [x] feat: synlynk v0.3.0 — multi-agent foundation [cli] <!-- id:story-pr26 -->
- [x] chore: 2026-06-07 design session docs — state-db, identity, workspace, arc gap analysis [docs] <!-- id:story-pr28 -->
- [x] feat: synlynk v0.3.1 — sentinel + observability hardening [cli] <!-- id:story-pr29 -->
- [x] test: synlynk E2E test suite — black-box CLI coverage [test] <!-- id:story-pr30 -->
- [x] docs: Hybrid Workgroup design spec, brainstorm visuals, and blog post 10 [docs] <!-- id:story-pr35 -->
- [x] docs: v0.4.0 Hybrid Workgroup Bootstrap — implementation plan [docs] <!-- id:story-pr36 -->
- [x] docs: fix Tokq memory unit schema — file-grain → state.db view-grain [docs] <!-- id:story-pr37 -->
- [x] feat: v0.4.0 — Hybrid Workgroup Bootstrap [cli] <!-- id:story-pr39 -->
- [x] feat: v0.5.0 capability engine — model-aware routing, quality signals, score/story CLI [cli] <!-- id:story-pr41 -->
- [x] fix: normalize quality_auto by present-signal weights (closes #43) [cli] <!-- id:story-pr44 -->
- [x] docs: synlynk quick start guides [docs] <!-- id:story-pr40 -->
- [x] feat: v0.6.0 capability engine — tier 2 probe, verifier parsing, pr check, org_domain_tags [cli] <!-- id:story-pr42 -->
- [x] feat: v0.4.1 — Instruction Reach (Cursor, Copilot, Windsurf + drift detection) [cli] <!-- id:story-pr45 -->
- [x] feat: v0.4.2 task status model — 5-state todo.md [cli] <!-- id:story-pr46 -->
- [x] fix: sync VERSION to 0.6.1 — stop perpetual upgrade prompt [cli] <!-- id:story-pr47 -->
- [x] feat: v0.7.0 Static Scan Quality — source architecture in every exec context [cli] <!-- id:story-pr49 -->
- [x] AGY dispatch: autopilot gap analysis — unanswered questions and decision blockers [docs] <!-- id:story-4adc797d -->
- [x] Codex dispatch: add Capability Ledger section to synlynk status output [cli] <!-- id:story-99f6a867 -->
- [x] Code review PR #50: capability dogfood — backfill, dispatch fixes, ledger in status [cli] <!-- id:story-0bdc4c83 -->
- [x] Code review PR #50 by Codex: capability dogfood backfill, dispatch fixes, ledger in status [cli] <!-- id:story-d032d3af -->
- [x] Code review PR #51: codex exec headless dispatch fix [cli] <!-- id:story-b2550ce9 -->
- [x] AGY review of PR #51: codex exec headless dispatch [cli] <!-- id:story-617491f1 -->
- [x] Codex review of PR #51: codex exec headless dispatch [cli] <!-- id:story-d9b15457 -->
- [x] T1: SQLite Canon — stories.status + _generate_todo_md + _import_todo_to_stories [backend] <!-- id:story-80b66ba9 -->
- [x] T2: Per-agent context profiles — .agents/<agent>.json + dispatch merge + agent configure cmd [backend] <!-- id:story-c8887db1 -->
- [x] T3: synlynk jobs SQLite read + --watch + _preflight_dispatch + --context-mode CLI flag [backend] <!-- id:story-683da947 -->
- [x] T4: Relay wire protocol — SynlynkRelay SSE broker + relay start/broadcast CLI [infra] <!-- id:story-e5cc49f0 -->
- [x] T5: Sentinel VERIFY_SKIP pattern + _extract_compliance_tags [backend] <!-- id:story-7264a1d0 -->
- [x] dispatch: write job context to .synlynk/contexts/<job_id>.md not global context.md [dispatch] <!-- id:story-5b86c353 -->
- [x] BS-5: brainstorm — standalone synlynk website (design-first, beyond functional) [web] <!-- id:story-048f5fe5 -->
- [ ] BS-6: brainstorm — repo/workspace visualization: product view · logical view · infra view [visualization] <!-- id:story-f5513a93 -->
- [ ] BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform] <!-- id:story-bs7-interop -->
- [ ] BS-8: synlynk probe — ambient harness capability drift detection + publish pipeline [tooling] <!-- id:story-bs8-probe -->
- [ ] BS-8: dispatch_loop() — composite termination + /goal objective injection + job chain tracking [dispatch] <!-- id:story-bs8-loop -->
- [ ] BS-8: stuck detection + one-shot consult from capability matrix + Expert Consult injection [dispatch] <!-- id:story-bs8-consult -->
- [ ] BS-8: goal hierarchy (meta + milestone + story) + synlynk goals CLI + three-layer context injection [dispatch] <!-- id:story-bs8-meta-goals -->
- [ ] BS-8: synlynk story split — observatory-driven auto-decomposition for context-window-crossing stories [dispatch] <!-- id:story-bs8-split -->
- [ ] BS-14: brainstorm — Harness Compatibility: headless execution contracts, per-agent dispatch flag maps, compliance test suite, STALL_NO_OUTPUT sentinel spec [platform] <!-- id:story-bs14-harness-compat --> <!-- gh:#81 --> <!-- priority:next -->
- [ ] BS-12: brainstorm — Agent Autonomy Bridge: permission grants, harness config, handoff protocol, + synlynk TUI/chatbot at init/doctor time [platform] <!-- id:story-6f97c5a0 -->
<<<<<<< HEAD
- [ ] BS-9: brainstorm — Trio Orchestration Demo: State Continuity + Flatline + Parallel Dispatch showcase (scripted, narrative-first) <!-- id:story-ab6a0586 -->
- [ ] BS-10: brainstorm — PulseScape: end-to-end glassmorphic agent dashboard (SSE relay + Ed25519 consensus panel, 6-session build) <!-- id:story-e3a3170a -->
- [ ] BS-11: brainstorm — MCP Registry contribution: Project Context + Todo MCP Server for modelcontextprotocol/servers <!-- id:story-fda756fd -->
- [ ] flatline: standalone Python CLI circuit-breaker — hash stdout, kill after 3 identical failures, pip-installable public utility <!-- id:story-b4a90209 -->
- [ ] git-drift: standalone pip package — instruction drift auditor, pre-commit hook, manifest schema, git-drift install <!-- id:story-cb2c1d93 -->
- [ ] git-connectome: standalone language-agnostic codebase mapper → self-contained interactive HTML (synlynk viz public face) <!-- id:story-3652dafe -->
=======
- [ ] BS-12a (v0.10.0): Agent Role Formalization — roles block in .synlynk/config.json + synlynk init/doctor generates per-agent directive files (CLAUDE.md ##Your Role, GEMINI.md ##Your Role, AGENTS.md shared summary); synlynk roles subcommand prints current role table [platform] <!-- id:story-bs12a-roles --> <!-- gh:#79 -->
>>>>>>> 7af617f (chore: BS-12a — agent role formalization across directive files + todo)
