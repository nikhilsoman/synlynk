# synlynk Priority Listing & Brainstorm Schedule

**Date:** 2026-06-24  
**Covers:** v0.9.3 stabilization · v0.9.4 · v0.10.0 · v1.0.0 · 4 cross-cutting epics (DevX, CA, AB, OB)  
**Open GitHub issues reviewed:** 23 (16 Platform:Codex, 4 enhancement, 2 documentation, 0 live-issue)

---

## Approach Decision: (c) Release-Dependency-First, Then Brainstorm Per Release

The three options from the agenda:
- **(b)** Brainstorm all epics first, then decide which outputs go into which releases  
- **(c)** Identify what each release needs from the epics, then brainstorm to answer exactly those questions  

**Decision: (c).** Rationale: we have a concrete next release (v0.9.4 — Workgroup Relay) whose architecture cannot be finalised without specific answers. The epics are design debt that feeds INTO releases; open-ended brainstorming without a release target produces over-scoped specs. Each brainstorm session below has a stated output (decision or spec section) and a named blocker it unblocks.

---

## Tier 0 — Stabilize v0.9.3 (patch before v0.9.4 work begins)

**No labeled live issues on GitHub.** The v0.9.3 correctness bugs (zombie reaping, dep-failure deadlock, per-job commit) all shipped fixed. However two production issues have been observed:

| # | Issue | Source | Fix |
|---|-------|--------|-----|
| P0 | `synlynk dispatch` injects full project-docs context (119KB for a cross-repo PR review) — 300× overinflation | Observed 2026-06-24 | Q8 patch: write dispatch context to `.synlynk/jobs/<job_id>/context.md` instead of overwriting global file; Q9: enforce `context_tokens_max` in config |
| P1 | Concurrent dispatch races on `context.md` (global file overwritten mid-read) | Latent — exposed by above | Same Q8 fix |
| P2 | Todo.md version numbering drifted (v0.9.1 label = v0.9.2 shipped) | Fixed 2026-06-24 | Done ✅ |
| P3 | Platform:Codex issues #6–#20 (16 open, all from v0.5 era) | GitHub | Triage: group into a `chore/codex-platform` issue bundle, close stale/superseded, forward relevant ones to v0.9.4 scope |

**P0+P1 should be a `fix/dispatch-context-scoping` PR before any v0.9.4 branch work starts.**

---

## Tier 1 — Pre-v0.9.4 Gates (decisions required before implementation)

These items must be resolved (brainstorm → decision) before the v0.9.4 implementation plan is written. Nothing in Tier 2 can be spec'd without them.

| Priority | Item | Blocks | Brainstorm session |
|----------|------|--------|--------------------|
| 1 | **DevX-1** — context-layer brainstorm (Q1–Q10, spec already written) | Relay wire protocol, `generate_context()` hybrid read, dispatch scoping fix design | BS-1 |
| 2 | **DevX-2** — task tracking canon decision (todo.md vs state.db vs Projects V2) | DevX-1 brainstorm Q5 (migration path), CA-8 (autopilot trigger map), OB-5 (mode→agent availability) | BS-1 (as a sub-question) |
| 3 | **OB-4** — mode taxonomy rewrite decision (solo/solo+agents/team/team+agents) | Daemon behavior, `synlynk init` wizard, AB-0 access mode matrix | BS-2 |
| 4 | **AB-3** — compliance scoring framework (define compliance tag schema) | No blocker — can start immediately; adds data pipeline from v0.9.4 day 1 | No brainstorm needed — design + implement directly |

---

## Tier 2 — v0.9.4 Scope (Workgroup Relay + bundled improvements)

v0.9.4 release should ship more than the relay. Every item below is small enough to bundle without bloating the PR, and each has a dependency on the Tier 1 decisions. The brainstorm sessions (BS-1, BS-2) produce the specs that feed the implementation plan.

**Core relay work (relay team owns):**
- WSS/443 relay · 3 deployment modes (LAN/Cloudflare Tunnel/VPS) · revolving host protocol  
- Per-dispatch context file (Q8 fix from Tier 0 P0)  
- Structured relay events, not markdown blob (DevX-1 outcome)

**Bundled improvements (can run in parallel as separate PRs):**

| Item | Epic | Rationale for bundling |
|------|------|------------------------|
| Per-dispatch context file + size budget enforcement | DevX-1 / Q8+Q9 | Fixes P0 production issue; simple change to `exec_command()` |
| `generate_context(scope="task")` hybrid read | DevX-1 outcome | Required for relay to carry typed events |
| OTel tracer — stdlib `SynlynkTracer` class | CA-4 | Foundation for all telemetry; no new dependencies; 200 lines |
| OTel spans on exec + dispatch | CA-5 | Mechanical once CA-4 exists |
| `synlynk doctor` health check command | OB-9 | High user impact, low risk; no architecture dependency |
| Agent availability state machine (5 states) | OB-7 | Pre-flight for dispatch; replaces silent failures |
| `synlynk jobs` CLI + completion notification | DevX-3 | Closes the "status check" loop; ~30 lines on daemon HTTP endpoint |
| AB-3 compliance tags in instruction templates | AB-3 | Zero risk change to `synlynk init`; starts data pipeline immediately |
| Sentinel: VERIFY_SKIP + BRANCH_VIOLATION patterns | AB-4 | Incremental; runs on existing infrastructure |

---

## Tier 3 — v0.10.0 Scope (Multi-Repo Workspace)

Before the implementation plan is written, two brainstorm sessions gate this release:

| Item | Epic | Status |
|------|------|--------|
| OB-0 onboarding journey map brainstorm | OB | BS-3 output |
| OB-8 progressive onboarding model | OB | BS-3 output |
| OB-3 multi-repo join stopgap | OB | Decision only; no brainstorm needed — document current answer |
| AB-0 access mode taxonomy | AB | BS-4 output |
| CA-1 command audit matrix | CA | BS-4 sub-item |
| synlynk workspace init/join | v0.10.0 roadmap | Depends on BS-3 + BS-4 |

---

## Tier 4 — v1.0.0 Scope

These items need specs before implementation but have no v0.9.4 dependencies. All feed into the v1.0 "stable API + community layer" milestone.

| Item | Epic |
|------|------|
| Full onboarding rewrite (OB-1, OB-2, OB-5, OB-8, OB-10) | OB |
| Instruction durability + Ed25519 signing (AB-5) | AB |
| Cross-mode adherence dataset / Synlynk IDE justification (AB-9) | AB |
| Per-agent instruction variance tracking (AB-6) | AB |
| Command lifecycle labels + discoverability pass (CA-3, CA-9) | CA |
| Hook wiring contract (CA-7) | CA |
| Autopilot trigger map (CA-8) | CA |
| Instruction effectiveness → capability ratings (AB-8) | AB |

---

## GitHub Issues Triage

**16 Platform:Codex issues (#6–#20, opened 2026-05-18):**  
These predate the capability engine and package split. Most are about a `synlynk codex` subcommand that was designed before the generalized dispatch model existed. Recommended disposition:
- **Close as superseded:** `synlynk codex` subcommand items (#6, #11, #12, #13) — `synlynk exec codex` + `synlynk dispatch` cover this
- **Forward to AB-7** (native behaviour matrix): #7, #16, #17, #18, #19, #20 — Codex IDE and telemetry questions belong there
- **Forward to OB-9** (doctor command): #8 (`synlynk doctor --codex`) — fold into general doctor
- **Close as wont-fix (covered by CA-4):** #9 (validators), #10 (fake-Codex tests), #14 (tolerant JSONL parser), #15 (costs.md recording)
- **Retain for research:** #4 (AI dev metrics prompt) — useful input for AB-8

**4 enhancement issues:**
- #32 (GitHub Projects V2 integration) → DevX-2 scope
- #31 (synlynk migrate) → DevX-1 Q5 (migration path decision)
- #48 (synlynk consensus) → v0.9.2 shipped this as `synlynk decide` — close as done
- #38 (model-aware capability scoring design review) → capability engine shipped in v0.6; close as done

**2 documentation issues:**
- #34 (synlynk-vision.md) → site rewrite partially covered this; carry forward to v1.0 public presence initiative
- #33 (agent-workers content into capability routing) → done in v0.6; close

---

## Consolidation Opportunities Across Epics

Three clusters where items from different epics address the same underlying design question. Brainstorming them together produces better specs than doing them independently:

**Cluster A — "Something went wrong with an agent, what does the user see?"**  
OB-7 (agent state machine) + CA-2 (error UX sweep) + DevX-3 (dispatch observability) + AB-4 (sentinel non-adherence)  
→ Brainstorm BS-1 should produce a unified "agent failure surface" design: pre-flight state check, job-start banner, sentinel alert, completion notification. One coherent UX, not four separate patches.

**Cluster B — "Is SQLite canon or is the file canon?"**  
DevX-2 (task tracking canon) + OB-5 (mode→agent availability) + CA-8 (autopilot trigger map) + AB-9 (injection audit log)  
→ All four block on the same architectural decision. BS-1 must resolve this first — it unlocks all four independently.

**Cluster C — "OTel instrumentation sweep"**  
CA-4 (tracer) + CA-5 (command spans) + AB-10 (instruction adherence spans) + OB-11 (first-run milestones)  
→ One implementation pass. CA-4 defines the `SynlynkTracer` class; CA-5, AB-10, OB-11 are callers. Write them together as one PR.

---

## Brainstorm Sessions Schedule

**Approach: each session has a stated output (spec section or decision record) that directly unblocks a named release item. Use past visuals from `docs/brainstorm/` to anchor decisions. No open-ended horizon sessions.**

---

### BS-1 — Context Layer + Dispatch Architecture (v0.9.4 gate)
**Output:** Updated context-layer spec (Q1–Q10 answered) + "agent failure surface" UX design  
**Unblocks:** Relay wire protocol · `generate_context()` hybrid read · P0 dispatch context fix · task tracking canon (Cluster B)  
**Relevant past visuals:**
- `docs/brainstorm/v0.9.3-async-daemon/daemon-architecture.html` — HTTP API endpoints, two-thread model
- `docs/brainstorm/state-db-agentic-pm/design-storage.html` — SQLite as local JetStream
- `docs/brainstorm/invisible-state/design-architecture.html` — context flow design
- `docs/brainstorm/relay-vps-deep-dive/relay-architecture.html` — relay transport options  
**Key questions:**
- Q6: task-scoped context — what are the mandatory vs optional fields?
- Q7: cross-repo dispatch — suppress project-docs entirely?
- Q8: per-dispatch context file design
- Q10: per-agent context profiles schema
- Cluster B: is SQLite canon at v0.9.4 or deferred to v1.0?
- Cluster A: unified agent failure surface design

---

### BS-2 — Onboarding Model + Mode Taxonomy (v0.9.4 gate)
**Output:** OB-4 mode taxonomy decision record + OB-0 onboarding journey map  
**Unblocks:** `synlynk init` wizard rewrite · daemon mode behavior · `synlynk agents status` design · AB-0 access mode matrix  
**Relevant past visuals:**
- `docs/brainstorm/invisible-state/design-commands.html` — init flow design
- `docs/brainstorm/roadmap-realignment/os-framing.html` — what "OS layer" means for users
- `docs/brainstorm/v1-architecture/hud-concepts-v1.html` — user-facing status concepts  
**Key questions:**
- What are the 4 mode labels and their concrete trigger criteria?
- What is the single most important "next step" printed at the end of `synlynk init`?
- What does `synlynk doctor` output look like?
- Where does "agent available" end and "agent active for tasking" begin?

---

### BS-3 — Agent Behaviour & Instruction Adherence (v1.0 prep)
**Output:** AB-0 access mode matrix + AB-3 compliance tag schema + AB-7 native behaviour matrix  
**Unblocks:** Instruction template updates (add compliance line) · sentinel extension · v1.0 Synlynk IDE justification dataset design  
**Relevant past visuals:**
- `docs/brainstorm/agent-identity-dispatch/design-schema-dispatch.html` — dispatch framing schema
- `docs/brainstorm/model-aware-capability-scoring/competency-model.html` — domain × quality model
- `docs/brainstorm/v1-architecture/agent-comms.html` — agent communication model  
**Key questions:**
- What is the minimal compliance tag schema that works across Claude/Codex/Agy?
- Which native capabilities does each access mode have — full matrix
- How do we detect INSTRUCTION_IGNORE vs INSTRUCTION_DRIFT in sentinel?
- What is the cross-mode compliance measurement methodology?

---

### BS-4 — Command Audit + Autopilot Trigger Map (v1.0 prep)
**Output:** CA-1 command audit matrix + CA-7 hook wiring contract + CA-8 autopilot trigger map  
**Unblocks:** OTel instrumentation scope · agent archetype trigger contracts (TPM Agent, PM Agent) · v0.8.x agent ecosystem  
**Relevant past visuals:**
- `docs/brainstorm/tpm-agent/tpm-board.html` — TPM agent lifecycle and triggers
- `docs/brainstorm/tpm-agent/tpm-lifecycle.html` — wave dispatch lifecycle
- `docs/brainstorm/agent-allocation/agent-allocation.html` — allocation model
- `docs/brainstorm/state-db-agentic-pm/design-token-budget.html` — token budget per story  
**Key questions:**
- What is the full command inventory as of v0.9.3?
- For each command: hook trigger, pre-reqs, input/output contract
- Which commands should trigger agent/autopilot actions and under what conditions?
- What is the `synlynk telemetry stats` output schema?

---

## Recommended Execution Order

```
TODAY:
  → P0 patch: fix/dispatch-context-scoping (Q8 + Q9)
  → Close/triage Platform:Codex GitHub issues (16 items → ~4 kept)
  → AB-3: compliance tag schema (design + add to instruction templates in init)

THIS WEEK (pre-v0.9.4 gates):
  → BS-1: context layer + dispatch architecture brainstorm
  → BS-2: onboarding + mode taxonomy brainstorm
  → Write v0.9.4 implementation plan from BS-1 + BS-2 outputs

v0.9.4 SPRINT:
  → Relay core (WSS/443, 3 modes, revolving host)
  → Bundled improvements (see Tier 2 table above)
  → CA-4 + CA-5 + AB-10 + OB-11 as one OTel instrumentation PR

POST-v0.9.4:
  → BS-3: agent behaviour brainstorm
  → BS-4: command audit brainstorm
  → v0.10.0 workspace design + OB full onboarding rewrite
```

---

## Brainstorm Visual Archive Index

All sessions committed to `docs/brainstorm/` as of 2026-06-24:

| Folder | Topic | Used in |
|--------|-------|---------|
| `agent-allocation/` | Agent task allocation model | BS-4 |
| `agent-identity-dispatch/` | Ed25519 identity + dispatch schema | BS-3 |
| `features-page/` | Site features page positioning | Site work |
| `github-projects-v2/` | GH Projects V2 integration design | DevX-2 |
| `hybrid-workgroup-imperatives/` | v0.4.0 four imperatives | Historical |
| `invisible-state/` | Context flow + init commands | BS-1, BS-2 |
| `migration-analysis/` | project-docs → state.db migration | BS-1 (Q5) |
| `model-aware-capability-scoring/` | Domain taxonomy + quality signals | BS-3, BS-4 |
| `relay-vps-deep-dive/` | Relay architecture + VPS options | BS-1 |
| `roadmap-realignment/` | OS framing + unified roadmap | BS-2 |
| `state-db-agentic-pm/` | SQLite as local JetStream | BS-1 |
| `synlynk-unified-roadmap/` | Full roadmap visual | Reference |
| `synlynk-website-wireframes/` | Site wireframes | Site work |
| `tokq-data-metamorphosis/` | Tokq convergence design | v1.3 |
| `tpm-agent/` | TPM agent lifecycle + board | BS-4 |
| `v041-architecture/` | v0.4.1 architecture | Historical |
| `v1-architecture/` | v1.0 architecture + HUD | BS-2, BS-3 |
| `v0.9.2-decide-command/` | `synlynk decide` output design | Reference |
| `v0.9.3-async-daemon/` | Daemon approaches + architecture | BS-1 |
| `workspace-multi-repo/` | Workspace init/join + sync | v0.10.0 |
