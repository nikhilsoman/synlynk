# Way of Working (WoW) Deep-Dive: Claude & Gemini Collaboration
## Case Study: Prisma Transparent Decryption Refactor (rxcc, 2026-05-31)

---

## 1. Situation and the Ask

**The trigger:** SEC-1 shipped on 2026-05-31 — full AES-256-GCM per-user envelope encryption across 35 fields and 10 Prisma models. Write path was solid. The read path was left as 73 per-call-site `decryptField()` calls spread across 5 route files.

**LIVE-11:** Within the same session, 10 routes were found shipping raw `enc:v1:...` ciphertext to clients. Encrypted strings are valid TypeScript strings — they pass every shape check, every type assertion, every integration test that doesn't specifically assert plaintext. Silent regression. The enforcement model was unenforceable.

**The ask:** Fix the class of bug, not the individual sites. Move decryption into the Prisma layer via a `$extends` hook reading `AsyncLocalStorage` context — so routes get plaintext by default, without touching crypto at all.

**Why two agents:** The work split cleanly into two domains — a complex infrastructure foundation (extension architecture, ALS wiring, no-circular-dependency constraint) and a high-volume mechanical sweep (73 call site removals, cross-user route rewiring, integration tests). Claude had the most context on the SEC-1 architecture. Gemini had already been allocated to the `feat/gemini/live-11-decrypt-tests` branch.

---

## 2. Process Efficiency and Output Quality

**Efficiency:**

| Metric | Value |
|--------|-------|
| Total PRs produced | 3 (#381, #382, #355) |
| Call sites eliminated | 73 |
| Route files touched | 5 |
| Unit tests written | 9 (db package) |
| Integration tests written | 4+ |
| LOINC bugs caught in code review | 3 |
| Session boundary crossings requiring re-context | 2 (S-038 → S-039, Gemini session restart) |
| Turns spent on re-discovery at each handoff | ~3–5 (estimated from Gemini's devlog note) |
| Unplanned branch conflicts | 0 |
| Merge conflicts requiring resolution | 0 |

**Quality:**

The extension architecture is genuinely good — no circular dependency between `packages/db` and `packages/crypto` (decrypt fn injected via ALS, not imported), graceful degradation on KMS failure, explicit cross-user context wrapping for the 3 share/family routes, clean separation of worker (raw Prisma, intentionally explicit) from API (extended client, transparent). Gemini's consultation on recursive nested `include` traversal prevented a real architectural gap.

Output quality was higher than a single-agent session would likely have produced because: Claude had the architecture context and wrote the design spec; Gemini had a clean spec to execute against rather than inferring intent; the code review loop on PR #355 (LOINC) caught 3 bugs before merge.

---

## 3. Net Positive or Negative?

**Net positive. The hard metrics:**

**In favor:**
- **73 call sites → 0** in one session. A single-agent session would likely have caught the same bugs but without the architectural shift — it would have added 3 more `decryptField` calls, leaving the enforcement model still unenforceable.
- **3 PRs in parallel** — #381 (Gemini, integration tests + route fixes), #382 (Gemini, extension + sweep), #355 (Gemini, LOINC) — were all in flight while Claude was running S-039 unit tests. A solo session is serial.
- **Code review caught 3 LOINC bugs** (searchByName sliced at 1,000 — 98% of 51K codes invisible; dead panelCodeToSlug map; 5 phantom TARGET_CLASSES). These were genuine defects in production-bound code.
- **Zero merge conflicts** despite both agents working on overlapping files — because the branch boundary was respected.

**Against:**
- **3–5 re-discovery turns per handoff.** Gemini had to grep commit logs and read the filesystem to determine Claude had finished the foundation. Pure waste — probably ~$0.30–0.50 in tokens per handoff, zero output.
- **Single-branch coordination friction.** Both agents were on `feat/gemini/live-11-decrypt-tests`. The branch name implied Gemini ownership. When Claude picked up Task 3 (unit tests), the first act was verifying branch state and reconciling what Gemini had and hadn't committed.
- **No explicit capability signals.** Task allocation (Claude = foundation, Gemini = sweep) was correct but decided by a human with prior knowledge of agent strengths, not by any systematic assessment.
- **Context asymmetry.** Claude authored the design spec with full SEC-1 architecture in session context. Gemini was handed the spec as a cold read. Any ambiguity in the spec produced implementation drift that a human had to catch.

**Verdict:** ~2.5–3x the throughput of a single-agent serial session, with quality equal or higher due to the review loop. The lost efficiency (re-discovery, single-branch friction) was real but small relative to the gain.

---

## 4. Design Stage vs. Implementation Stage — Independently

**Design stage (Claude-led):**

The spec was written in a single Claude session. Gemini contributed one consultation pass: suggesting recursive traversal for nested `include` blocks and graceful degradation on KMS failure. Both were incorporated. This was the highest-leverage collab moment — Gemini's consultation added architectural correctness (the nested include gap is real; a flat traversal would have silently skipped relationships) at very low cost (one prompt, one response, no branch work).

What worked: the spec became the contract. Both agents executed against it without divergence. The architecture section was precise enough (component names, file paths, data flow diagram, interface signatures) that Gemini's implementation matched exactly what Claude had designed.

What was absent: no explicit "Gemini review of the spec before implementation." Gemini's consultation was structured as "here's a suggestion" not "here's what I'd change and why." A formal review pass from Gemini — specifically checking for gaps in the ALS propagation model or Prisma extension edge cases — would have caught anything Claude missed before a line of code was written.

**Implementation stage (Gemini-led):**

Gemini executed Tasks 5–11 (route sweep) well. The 73-call-site removal was mechanical but required understanding the cross-user context pattern for the 3 family/share routes — and Gemini got that right without ambiguity. The integration tests covered the graceful degradation case. The transaction `any` casts were an honest admission of a known Prisma limitation.

What worked: Gemini's high-volume editing throughput. Five route files, 73 sites, 4 integration tests, one PR body — this is the kind of sweep where Gemini consistently outperforms because it produces less overhead per edit and is willing to grind the repetition.

What was absent: Gemini had no visibility into what Claude was doing in parallel (unit tests for `decryptTree`). The unit test work and the integration test work could have been coordinated — instead they were independent and slightly duplicative in setup code. Also: Gemini opened PR #382 before Claude had finished the unit tests — technically the PR was incomplete when opened.

---

## 5. Collaboration Mechanics

**Communication channel:** Asynchronous, artifact-driven. No real-time signaling. The channel was:
1. **Spec document** — Claude writes, Gemini reads cold
2. **Implementation plan file** — `docs/superpowers/plans/2026-05-31-prisma-decrypt-extension.md` — task list with explicit owner assignments
3. **Git commits** — Gemini discovers Claude's foundation by reading commit log and checking file existence
4. **PR body** — completion signal
5. **Devlog** — post-hoc record, not used as a live channel

**Latency:** Hours. A handoff from Claude → Gemini required: (1) Claude commits, (2) Claude's session ends, (3) human opens Gemini session, (4) Gemini reads spec + plan + commit log = 3–5 re-discovery turns. This is not agent-to-agent; it's agent → human → agent. The human is the message bus.

**Context transfer:** The spec was the primary mechanism. It worked because it was precise (file paths, interface signatures, data flow). It broke down at the edges — Gemini had to infer Claude's completion state from git, not from an explicit signal.

**Output structure:** Gemini produced patch commits + PR. Claude produced unit tests + PR verification. Neither produced a structured "I am done, here is what I did, here is what remains" handover artifact. The WoW doc was written after the fact, as reflection — not as a live handover.

**Analysis of each other's syntax / style:** There was implicit alignment from the shared spec. Gemini's route code preserved Claude's `runWithCryptoContext` pattern exactly — same function call shape, same bind pattern (`app.crypto.decrypt.bind(app.crypto)`). This wasn't accidental; the spec had the exact interface. Where the spec was vague (unit test structure), Claude had to invent — and the test conventions differ slightly from Gemini's integration test style. Not a defect, but visible.

---

## 6. How to Make This More Effective and Autonomous

### Capability Grading

Based on observed performance across the rxcc project:

| Capability | Claude | Gemini |
|-----------|--------|--------|
| Architecture design | 9/10 | 6/10 |
| Complex type system / inference | 9/10 | 6/10 |
| High-volume mechanical edits | 6/10 | 9/10 |
| Integration test generation | 7/10 | 8/10 |
| Unit test design | 8/10 | 6/10 |
| Code review (finding defects) | 9/10 | 6/10 |
| Spec cold-read → correct impl | 7/10 | 7/10 |
| Context reacquisition speed | 7/10 | 5/10 (3–5 extra turns) |
| Cross-file consistency checks | 9/10 | 6/10 |

**Task allocation rule:** Claude owns architecture, type-system-heavy code, code review, unit tests, any work requiring cross-file reasoning. Gemini owns sweeps, batch refactors, integration test generation on well-defined schemas, frontend implementation.

### Communication Channel: Replace the Human Bus

The bottleneck is human-as-message-bus. The fix is a structured handover file at a known path, written as the last act of any partial-work session:

```
.agent/handover.json   (git-tracked)
```

```json
{
  "from": "claude-sonnet-4-6",
  "to": "gemini-2.5-pro",
  "sessionId": "S-039",
  "branchName": "feat/gemini/live-11-decrypt-tests",
  "headCommit": "a9cf253",
  "completedTasks": ["Task-1", "Task-2", "Task-3", "Task-4"],
  "pendingTasks": ["Task-5", "Task-6", "Task-7", "Task-8", "Task-9", "Task-10", "Task-11"],
  "blockers": [],
  "contextFiles": [
    "docs/superpowers/specs/2026-05-31-prisma-decrypt-extension-design.md",
    "packages/db/src/extensions/decrypt.ts",
    "packages/db/src/crypto-context.ts"
  ],
  "knownGotchas": [
    "Transaction types require 'any' cast — Prisma extension limitation, not a bug",
    "Worker must use raw prisma, not app.db — intentional, do not extend"
  ],
  "openQuestions": [],
  "nextAction": "Execute Tasks 5–11 per spec. Start with records.ts sweep, verify zero decryptField callsites after."
}
```

The receiving agent reads this file as its first act. Zero re-discovery turns.

### Resource Usage Monitoring

Every agent session costs money. Per-session token logging in `.agent/sessions.jsonl`:

```json
{"sessionId":"S-039","agent":"claude","date":"2026-05-31","inputTokens":120000,"outputTokens":15000,"cacheRead":80000,"estimatedCost":0.68,"tasksCompleted":["Task-3"],"linesChanged":340}
{"sessionId":"S-039b","agent":"gemini","date":"2026-05-31","inputTokens":200000,"outputTokens":35000,"estimatedCost":0.00,"tasksCompleted":["Task-5","Task-6","Task-7","Task-8","Task-9","Task-10","Task-11"],"linesChanged":1100}
```

From this you can derive: cost-per-task, cost-per-line-changed, and over time which agent is cheaper for which task type. Gemini's API is currently at $0 for this project (free tier CLI), which is a strong signal to route high-volume mechanical work there.

### Speed: Parallel Multi-Branch

```
master
  └── feat/infra-foundation    (Claude: Tasks 1–4, extension + ALS + Fastify plugin)
  └── feat/route-sweep         (Gemini: Tasks 5–11, starts after foundation merges)
```

Merge trigger: CI passes on `feat/infra-foundation` → auto-rebase `feat/route-sweep` onto it. Gemini can start from a clean checkpoint commit tagged `foundation-complete`, not from reading git logs.

For fully independent tasks (e.g. LOINC seeding + decrypt extension), both branches open simultaneously from master. No dependency, no wait.

---

## 7. The Solo-Dev Multi-Agent Harness

A minimal harness that makes the collab above systematic, repeatable, and autonomous.

```
.agent/
  harness.md              # Operating contract for all agents
  handover.json           # Active: last writer's state, next agent's cold-boot
  sessions.jsonl          # Append-only: every session's cost + output metrics
  capability-grades.json  # Graded capability matrix, updated after each task type
  task-map.json           # Current plan's task list with assignee + status
```

### harness.md

```markdown
# Multi-Agent Harness

## Cold-Boot Protocol (every agent, every session)
1. Read `.agent/handover.json` — this is your mission brief
2. Read only the contextFiles listed in handover.json — nothing else
3. Read `.agent/task-map.json` — find your assigned tasks
4. Begin with the first pending task assigned to you

## Completion Protocol (every agent, before session end)
1. Update `.agent/task-map.json` — mark your tasks complete
2. Write `.agent/handover.json` — populate: completedTasks, pendingTasks,
   headCommit, knownGotchas, openQuestions, nextAction, contextFiles
3. Append to `.agent/sessions.jsonl` — session cost + metrics estimate
4. Commit: `chore: agent handover [agent-name] tasks [N-M] complete`

## Task Assignment Rules
- Architecture, type-system, code review, unit tests → Claude
- Sweeps, batch refactors, integration tests, frontend → Gemini
- If a task is ambiguous: default to Claude; Claude can reassign in handover.json

## Branch Rules
- Independent task groups → separate branches from master
- Sequential task groups → single branch, one commits foundation then tags it
- Never work on master directly
```

### task-map.json

```json
{
  "planId": "prisma-decrypt-extension",
  "specFile": "docs/superpowers/specs/2026-05-31-prisma-decrypt-extension-design.md",
  "tasks": [
    { "id": "T1", "title": "crypto-context.ts", "type": "architecture", "assignee": "claude", "status": "complete", "commit": "a1b2c3d" },
    { "id": "T2", "title": "encrypted-fields.ts registry", "type": "architecture", "assignee": "claude", "status": "complete", "commit": "e4f5g6h" },
    { "id": "T3", "title": "decrypt.ts extension", "type": "type-system", "assignee": "claude", "status": "complete", "commit": "i7j8k9l" },
    { "id": "T4", "title": "Fastify plugin + app.ts wiring", "type": "architecture", "assignee": "claude", "status": "complete", "commit": "m0n1o2p" },
    { "id": "T5", "title": "records.ts sweep", "type": "batch-sweep", "assignee": "gemini", "status": "pending", "dependsOn": ["T1","T2","T3","T4"] },
    { "id": "T6", "title": "family.ts sweep", "type": "batch-sweep", "assignee": "gemini", "status": "pending", "dependsOn": ["T4"] }
  ]
}
```

### capability-grades.json

```json
{
  "lastUpdated": "2026-05-31",
  "grades": {
    "claude": {
      "architecture": 9, "type-system": 9, "code-review": 9,
      "unit-tests": 8, "cross-file-reasoning": 9,
      "batch-sweep": 6, "integration-tests": 7, "frontend": 4
    },
    "gemini": {
      "architecture": 6, "type-system": 6, "code-review": 6,
      "unit-tests": 6, "cross-file-reasoning": 6,
      "batch-sweep": 9, "integration-tests": 8, "frontend": 8
    }
  },
  "costPerToken": {
    "claude-sonnet-4-6": { "input": 0.000003, "output": 0.000015, "cacheRead": 0.0000003 },
    "gemini-2.5-pro": { "input": 0.0, "output": 0.0, "cacheRead": 0.0 }
  },
  "allocationPolicy": "maximize(grade / cost) per task type"
}
```

### How a session starts under this harness

1. **You (the dev):** Write the spec. Populate `task-map.json` with task types annotated. Run `python .agent/allocate.py` — reads task types + grades + costs, auto-assigns `assignee` fields. Review and override if wrong. Commit.

2. **Claude (Session 1):** Reads `handover.json` (empty → reads task-map.json directly). Finds tasks assigned to `claude` with no `dependsOn`. Executes. On session end: writes `handover.json` with foundation-complete state. Tags commit `foundation-complete`.

3. **Gemini (Session 2):** Reads `handover.json`. Gets: branch name, head commit, contextFiles, pendingTasks, knownGotchas, nextAction. Begins Task 5 immediately — zero re-discovery turns. On session end: writes `handover.json` with remaining state.

4. **Claude (Session 3):** Reads `handover.json`. Sees remaining Claude tasks. Takes them. Completes. Appends sessions.jsonl with cost estimate.

5. **You:** `git log --oneline` shows clean attribution. `.agent/sessions.jsonl` shows cost per task type. Over 5–6 projects, `capability-grades.json` becomes evidence-backed, not intuition-backed.

---

## Core Insight

The architecture that made this collab work was the **spec-as-contract**. The architecture that would make it *systematic* is **handover.json as the live nerve fiber between agents** — replacing the human as the message bus, making agent capability legible and quantifiable, and making task allocation a data decision rather than a judgment call.

The harness above is ~4 JSON files and ~30 lines of allocation script. Everything else is discipline.
