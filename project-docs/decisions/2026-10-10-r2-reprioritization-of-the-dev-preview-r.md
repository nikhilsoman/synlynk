<!-- generated - source of truth is state.db -->
---
decision_id: dec-cb633547
topic: "R2 reprioritization of the dev-preview roadmap (docs/strategy/2026-10-10-dev-preview-revised-roadmap.md Section 7): Nikhil now ranks local-model (pillar 4) as a non-blocking, cost-offset nice-to-have, and elevates swarms + effective public-model-quota utilization (pillar 7) and multi-interface operation beyond CLI-only -- IDEs (Cursor/VS Code/JetBrains), agentic frameworks (Warp/Pi), OAuth public-provider accounts, and BYOK/model-provider support via OpenRouter+LiteLLM (tracked in #2126, #2103, #1708, #1711, #2076) -- to release-critical status for pillar 1. A personal-use hosted relay is pulled forward into active design-now scope as the direct architectural predecessor to a Teams edition epic that follows immediately after dev preview. Three questions for the panel: (a) does demoting pillar 4 and elevating pillars 1 and 7 change the Week 1-2 foundation-first sequencing already approved in R1, (b) is designing the personal-use hosted relay now, without necessarily shipping it inside the 4-week window, achievable without slipping the 2026-10-31 date or compromising the R1 Week-1/Week-2 gates, and (c) how should the new multi-interface work sequence relative to the swarm/quota work under pillar 7?"
date: 2026-10-10
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
R2 reprioritization of the dev-preview roadmap (docs/strategy/2026-10-10-dev-preview-revised-roadmap.md Section 7): Nikhil now ranks local-model (pillar 4) as a non-blocking, cost-offset nice-to-have, and elevates swarms + effective public-model-quota utilization (pillar 7) and multi-interface operation beyond CLI-only -- IDEs (Cursor/VS Code/JetBrains), agentic frameworks (Warp/Pi), OAuth public-provider accounts, and BYOK/model-provider support via OpenRouter+LiteLLM (tracked in #2126, #2103, #1708, #1711, #2076) -- to release-critical status for pillar 1. A personal-use hosted relay is pulled forward into active design-now scope as the direct architectural predecessor to a Teams edition epic that follows immediately after dev preview. Three questions for the panel: (a) does demoting pillar 4 and elevating pillars 1 and 7 change the Week 1-2 foundation-first sequencing already approved in R1, (b) is designing the personal-use hosted relay now, without necessarily shipping it inside the 4-week window, achievable without slipping the 2026-10-31 date or compromising the R1 Week-1/Week-2 gates, and (c) how should the new multi-interface work sequence relative to the swarm/quota work under pillar 7?

## Panel Inputs

### claude
[model=default; version=2.1.292 (Claude Code)]

**(a) Does this change Week 1-2 sequencing?** Mostly no, with one adjustment. R1's foundation-first gates (whatever core plumbing pillar 1 depends on) were almost certainly already load-bearing for pillar 7 work too — swarms and multi-interface operation both sit on top of the same dispatch/identity/policy substrate pillar 1 was hardening. Demoting local-model work removes a Week 1-2 item without removing a dependency anything else needed; it was parallel-track, not prerequisite. The one real sequencing change: if multi-interface (IDE plugins, OAuth provider accounts, BYOK via OpenRouter/LiteLLM) is now release-critical, any Week 1-2 gate that assumed a single CLI-harness identity/auth model needs to be re-checked for whether it accommodates provider-pluggable auth from the start, rather than bolting it on in Week 3-4. That's a scope-of-gate question, not a reordering of gates.

**(b) Can the relay be designed now without slipping 10/31 or the gates?** Yes, if "design" stays strictly design — spec + plan docs, no implementation branch, no dependency the Week 1/2 gate-pass is conditioned on. The risk isn't the design effort itself (that's cheap, parallelizable with an Architect-role dispatch) — it's scope creep where "design now" quietly becomes "scaffold now," pulling dev cycles off the critical path. Guard this explicitly: relay design work gets its own goal/story outside the dev-preview GOVERNS tree, reviewed on its own PR, with an explicit note that zero of its code ships before 10/31.

**(c) Sequencing multi-interface vs. swarm/quota under pillar 7:** multi-interface should lead. Swarm orchestration and quota-aware routing both need to know *which* interfaces and provider accounts exist before they can allocate work across them sensibly — building the swarm/quota layer first risks hardcoding CLI-only assumptions that get reworked once OAuth/BYOK lands. Sequence: (1) provider-plural auth/BYOK plumbing (#2103/#1708/#1711/#2076), (2) IDE/framework surface bindings (#2126), (3) swarm+quota logic on top, since it's the piece most naturally re-tested against the now-wider interface/account surface.

**Recommendation:** Approve the reprioritization. It doesn't invalidate R1's sequencing, just narrows what Week 1-2's gates need to validate against (provider-plural auth, not just CLI). Approve relay design-now as a strictly docs/spec-only parallel track with its own goal outside the dev-preview GOVERNS tree, so it can't slip 10/31 by construction. Sequence pillar 7 as auth/BYOK → multi-interface bindings → swarm/quota, since the later layers depend on the former's surface, not vice versa.

### agy
[model=default; version=1.3.3]

**Last Completed Task:** `docs(strategy): R2 reprioritization — demote local model, elevate swarms/multi-interface, pull relay forward`  
**Next Task from `todo.md`:** `BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform]`

---

### Panel Analysis & Recommendation

Regarding the R2 reprioritization of the dev-preview roadmap in [docs/strategy/2026-10-10-dev-preview-revised-roadmap.md](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/live24-job-status-reconciliation-investigation/docs/strategy/2026-10-10-dev-preview-revised-roadmap.md#L95-L112):

**(a) Impact on Week 1–2 Foundation Sequencing:**  
Demoting Pillar 4 and elevating Pillars 1 and 7 **does not change** the Week 1–2 foundation-first sequencing. Consolidated state tracking (`#1926`), job status reconciliation (`#2136`), stale goal cleanup, and P0 correctness fixes remain strictly blocking prerequisites. Swarm orchestration under Pillar 7 and multi-interface provider proxying under Pillar 1 directly depend on a stable, single-source-of-truth telemetry layer. Bypassing Week 1 foundation work would corrupt quota accounting and generate false-negative statuses across multi-agent swarm dispatches.

**(b) Personal-Use Hosted Relay Design Feasibility:**  
**Yes, this is fully achievable** without slipping the 2026-10-31 target date or compromising the Week 1/2 gates. Treating the personal-use hosted relay strictly as a *design-now* architectural spec (defining single-tenant RPC patterns with forward compatibility for Teams multi-tenancy) isolates the task to design artifacts during Week 2. Because production deployment and cloud infra ops are out of scope for the 4-week preview, core engineering bandwidth remains focused on release-critical paths.

**(c) Sequencing Multi-Interface vs. Swarm/Quota Work:**  
The implementation should follow a two-tier sequence:
1. **Week 2 (Provider Abstraction Layer):** Prioritize BYOK and provider aggregators (`#1708`, `#1711`, `#2076`) alongside OpenRouter/LiteLLM routing. This establishes the unified API adapter and rate-limit tracking layer needed by both swarms and external clients.
2. **Weeks 3–4 (Swarms & Client Interfaces):** Build public-model quota-aware swarm dispatch (Pillar 7) on top of the provider layer, while concurrently delivering IDE and agentic framework connectors (`#2103`, `#2126` sub-items).

### Position Statement
**I vote to APPROVE the R2 reprioritization scheme.** The shift aligns development focus with immediate end-user utility while preserving structural rigor. Approval is strictly contingent on holding the Week 1 hard gate (`#1926` state consolidation and `#2136` job reconciliation) before advancing to swarm and multi-interface execution in Weeks 3 and 4.

### codex
[model=default; version=codex-cli 0.160.0]

R2 changes the **priority of outcomes**, but it does not remove the dependencies that made the R1 foundation-first sequence necessary. Keep Week 1 intact: reconcile stale goals, make #1926 queryable, close the job-status issue, and resolve the three-lens P0s. These protect the reliability of later measurements and release claims regardless of whether local models remain in scope. In Week 2, remove pillar 4 from the go/no-go gate as R2 directs. Keep the checkpoint: if #1926 or #2136 misses the Week 1 gate, re-park affected work rather than silently compressing the schedule.

Designing the personal-use relay now appears achievable within the 2026-10-31 target **if design is the commitment, not delivery**. Timebox a focused architecture decision and record interfaces, trust boundaries, and a migration path to Teams multi-tenancy. Do not let relay implementation displace the foundation gates or the minimum evidence needed for the release-critical claims. If design exposes a blocker, report it and make an explicit scope decision; don’t imply the relay ships in the preview.

For pillar 1 versus pillar 7, sequence shared prerequisites first, then advance both tracks after the Week 1 gate. Establish provider and credential handling (including BYOK/OpenRouter/LiteLLM) before building multiple clients on top of it. Start with the thinnest end-to-end interface proof—likely VS Code via #2103—then prioritize other interfaces against demonstrated demand; #2126 and the named Cursor, JetBrains, Warp, and Pi targets need scoped acceptance criteria. In parallel, build quota-aware swarm dispatch and validate it with a bounded field trial. Release evidence should show users can reach dispatch through supported interfaces and that concurrent workers use public quotas effectively. If the window cannot support every named target, narrow the supported list transparently rather than treating “multi-interface” as satisfied by CLI parity.

**My position:** preserve the R1 Week 1–2 foundation and its gates; demote local-model measurement; make multi-interface access and swarm/quota utilization release-critical; and bring relay architecture into a timeboxed design track now, with shipping deferred unless it fits without weakening those commitments.

### grok
[model=default; version=grok 1.0.44 (5b807183dd79) [stable]]

I'll read the revised roadmap and the R1 sequencing it depends on, then answer the three panel questions against those gates.R2 changes what the 10/31 pitch may claim. It does not change the dependency order R1 already approved.

**(a)** Week 1 stays first and unchanged. `#1926` (queryable `state.db`) and `#2136` (honest job status), plus the three-lens P0s, become more load-bearing once swarms and quota use are release-critical. A swarm trial on false-negative job status, or a quota scheduler over unconsolidated shards, cannot support the date. Demoting pillar 4 only removes Hermes measurement (`#2102`, `#2104`) from the Week 2 go/no-go. It does not free Week 1, and IDE or relay work must not jump that gate. Week 2's contents should be reweighted — keep `#1993` and the cost investigation, shrink Muse-only calibration — but the order remains foundation, then measurement, then claims.

**(b)** A personal-use hosted relay can be designed in this window without slipping 10/31 only as a spec. File the personal-use issue this week. The design must keep auth, tenancy, and state-sync extensible to Teams, and must not fork `#1926` or reopen enterprise sync (`#1402`). No implementation and no dispatch slot before the Week 1 checkpoint is green. Review the spec in Week 3–4, once the swarm and quota shape is known. Code on the preview branch competes with `#1926`'s zero float and should be refused.

**(c)** Build the shared substrate before either surface. Quota utilization and BYOK are one mechanism: `#2076` plus the minimum of `#1711`/`#1708` for a single OpenRouter-compatible provider, then a quota-aware scheduler under `goal-abecd18c`. That is Week 2–3 work, after the Week 1 gate, and it is what the Week 4 swarm trial should run. IDE breadth sits on a stable dispatch, jobs, and logs API. Ship one thin client, `#2103` (VS Code), in Week 3. File Cursor, JetBrains, Warp, and Pi under `#2126` and leave them unbuilt. Four clients, a full Model Hub epic, and a swarm proof will not fit in the remaining three weeks.

**Position:** Approve R2 as a reweighting, not a re-sequence. Hold both Week 1 and Week 2 gates. Treat release-critical pillars 1 and 7 as one provider path, one quota-aware swarm trial, and one IDE client. Design the personal relay now under a hard no-ship rule. Leave pillar 4 off the pitch.

## Synthesis
Decision: Approve R2's reprioritization as a reweighting of release-critical claims, not a reordering of execution. Week 1's foundation gates (#1926 state consolidation, #2136 job-status reconciliation, the three-lens P0s) remain first and unmoved — all four panelists converge here, and it's correct: swarms and quota-aware dispatch under pillar 7 would produce false signals on an unconsolidated/unreliable telemetry layer, so demoting pillar 4 frees no slot at the front of the queue, it only drops Hermes-local measurement from the Week 2 go/no-go. Within pillar 7, sequence provider/BYOK plumbing (OpenRouter/LiteLLM, #2076, minimum viable slice of #1708/#1711) ahead of both multi-interface clients and swarm/quota logic, since both later layers consume that auth/provider surface rather than the reverse — then ship one thin interface proof (VS Code, #2103) before fanning out to Cursor/JetBrains/Warp/Pi under #2126, and build the swarm/quota trial on top once the provider layer and at least one client exist to validate it against. The personal-use hosted relay is approved for design-now, strictly as a spec/architecture track (trust boundaries, tenancy model, forward-compatible migration path to Teams) — filed under its own goal outside the dev-preview GOVERNS tree, zero implementation or dispatch slots against it before the Week 1 gate is green, and no code from it ships inside the 10/31 window by construction. If Week 1's gate slips, pillar 7 and multi-interface work re-park behind it rather than compressing the schedule to protect the date.

## Decision
Decision: Approve R2's reprioritization as a reweighting of release-critical claims, not a reordering of execution. Week 1's foundation gates (#1926 state consolidation, #2136 job-status reconciliation, the three-lens P0s) remain first and unmoved — all four panelists converge here, and it's correct: swarms and quota-aware dispatch under pillar 7 would produce false signals on an unconsolidated/unreliable telemetry layer, so demoting pillar 4 frees no slot at the front of the queue, it only drops Hermes-local measurement from the Week 2 go/no-go. Within pillar 7, sequence provider/BYOK plumbing (OpenRouter/LiteLLM, #2076, minimum viable slice of #1708/#1711) ahead of both multi-interface clients and swarm/quota logic, since both later layers consume that auth/provider surface rather than the reverse — then ship one thin interface proof (VS Code, #2103) before fanning out to Cursor/JetBrains/Warp/Pi under #2126, and build the swarm/quota trial on top once the provider layer and at least one client exist to validate it against. The personal-use hosted relay is approved for design-now, strictly as a spec/architecture track (trust boundaries, tenancy model, forward-compatible migration path to Teams) — filed under its own goal outside the dev-preview GOVERNS tree, zero implementation or dispatch slots against it before the Week 1 gate is green, and no code from it ships inside the 10/31 window by construction. If Week 1's gate slips, pillar 7 and multi-interface work re-park behind it rather than compressing the schedule to protect the date.

> Signatures: see 2026-10-10-r2-reprioritization-of-the-dev-preview-r.json
