<!-- generated - source of truth is state.db -->
---
decision_id: dec-11a45658
topic: "Native-session cost capture: per-(session,model,UTC-day) transcript-derived ledger rows, derived session-to-PR view, and a general Claude session-hook dispatcher (spec docs/superpowers/specs/2026-11-24-native-session-cost-capture-design.md, LIVE-35 gh:#5457, goal-62f693b8, arc v0.39.3)"
date: 2026-11-24
panel: [claude, codex, agy]
status: approved
---

## Topic
Native-session cost capture: per-(session,model,UTC-day) transcript-derived ledger rows, derived session-to-PR view, and a general Claude session-hook dispatcher (spec docs/superpowers/specs/2026-11-24-native-session-cost-capture-design.md, LIVE-35 gh:#5457, goal-62f693b8, arc v0.39.3)

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Position: approve, with five changes before the plan is written.**

The core design is sound. Rows per (session, model, UTC day) fit the existing ledger. The derived session-to-PR view keeps guesses about PR attribution out of the ledger. A cursor that advances in the same transaction as the upsert, plus a unique key, makes capture idempotent. First-seen-wins de-duplication is backed by your measurements (a 1.9–2.3x overcount from naive summing).

**Strengths**
- One code path serves the hook, the CLI and the backfill.
- The consent-gated hook install and the never-alter-or-delete rule for manual rows are conservative in the right places.
- The privacy and format-drift tests address real risks.

**Concerns and fixes**
1. **The `pr-link` records are incomplete.** This session listed 3 PRs and touched about 8. If `pr check` treats "has a linked session" as provenance, it will report false negatives. v1 should make clear that missing links mean unknown, not none. It should also add a cheap second source, such as scanning for `gh pr` calls in tool-use records (counts and numbers only).
2. **Reporting the whole session's cost on every linked PR overstates spend** when a session spans many PRs. The "shared across N PRs" label is honest. Even so, no consumer should ever sum per-PR costs. State that as an invariant and test it.
3. **The job-transcript exclusion rule relies on path substrings** (`/worktrees/job-`). It misses jobs run outside that layout, and the `session_id`-on-a-`job_id`-row check races with dispatch writes. Make the exclusion re-evaluated at sweep time, not only at capture time. Add a reconcile step that flags overlap (a session_id with both `transcript_derived` and `job_id` rows) so double counting is detected rather than assumed away.
4. **`superseded_by_transcript` is a sum-exclusion flag that every consumer has to remember.** A missed consumer silently double counts. The audit task covers this, but a structural fix is better: a view such as `cost_entries_effective` that all readers use, with a test that greps for raw `FROM cost_entries` reads. This fits your invariants-over-discipline stance.
5. **Dispatcher scope.** A general dispatcher with one handler is slightly speculative. It is cheap, since it is only a thin fan-out, and it unblocks the compaction work. Keep it, but don't let the extension points grow any code in this PR.

**Smaller points**
- A per-turn `Stop` hook adds latency to every turn. Set an explicit budget (for example under 200ms) and measure it, rather than just stating one.
- `payment_mode` comes from `billing.json` until gh:#5500 lands. Rows captured in that gap should carry a provisional marker so they can be corrected.
- The acceptance test uses totals measured at one point in time. A live session keeps growing, so pin the fixture instead.

**Recommendation:** Approve the design with changes 1–4 folded into the spec. Order the backfill before any report that sums native cost, as §12 already says. Treat change 4, the single effective-cost view, as a gating requirement for the consumer audit.

### codex
[model=default; version=codex-cli 0.172.0]

The design addresses the real failure mode: native Claude sessions are invisible to both dispatch telemetry and quota scraping, while naïve transcript summation demonstrably overcounts. The proposed `(session_id, model, UTC day)` ledger grain is a strong choice: it is stable, supports multi-day sessions and model changes, and avoids inventing false PR-level precision. Keeping PR attribution in `session_pr_links` is particularly sound; session work is often shared, so a derived, explicitly “shared” PR view is more honest than allocating costs by guesswork.

The architecture is appropriately centralized. A single capture function shared by hooks, CLI capture, and backfill limits divergence, while cursor-plus-transaction semantics and a unique derived-row key provide a credible idempotency story. The explicit job-worktree exclusions, consent-gated settings merge, exit-zero hook behavior, and privacy boundary are all necessary operational safeguards. The fixture, format-drift, privacy, partial-read, and consumer-audit tests form a well-targeted verification set.

I would require two clarifications before implementation. First, the pricing interface must state whether cache-creation tokens contribute to `total_cost_usd`; storing them only in `turn_usage_json` risks understated costs unless the pricing calculation still consumes them. Second, define the durable de-duplication boundary precisely: the cursor’s 16 recent IDs is evidence-based for observed repeats, but recovery after transcript rewrites, cursor loss, or repeats farther apart should be explicitly handled or rejected loudly. Backfill must also precede any reporting rollup, as noted, to avoid a temporary but material double-counting window.

My position: approve the design in principle, contingent on resolving those two accounting/idempotency details and recording the required DECIDE linkage for goal-62f693b8 before build planning.

### agy
[model=default; version=1.5.16]

**Last completed task:** Drafted native-session cost capture and session-hook dispatcher design specification ([2026-11-24-native-session-cost-capture-design.md](file:///Users/nikhilsoman/dev/synlynk/.worktrees/chore+native-session-capture-spec/docs/superpowers/specs/2026-11-24-native-session-cost-capture-design.md), gh:#5457).  
**Next task:** Decision panel review and sign-off on native-session cost capture architecture (gh:#5457, goal-62f693b8).

---

### Analysis & Recommendation

The proposed design for native-session cost capture resolves the Sev1 telemetry gap identified in RCA LIVE-35 (gh:#5457) with sound architectural boundaries and strong operational safeguards.

First, the **granularity choice of per-(session, model, UTC-day)** ledger rows is technically superior to per-turn or whole-session alternatives. Because Claude Code streams assistant records repeatedly—causing naive parsers to overcount token volumes by ~2x—first-seen `message.id` deduplication against an incremental byte cursor guarantees mathematical fidelity. Daily bucketing cleanly accommodates multi-day conductor sessions and mid-session model switches without inflating ledger cardinality.

Second, the **derived session-to-PR view (`session_pr_links`)** maintains strict domain separation. Interactive conductor sessions routinely span brainstorms, multiple PR reviews, and triage. Forcing arbitrary PR allocations into raw `cost_entries` would pollute the ground-truth ledger. Storing ledger rows with `pr_number=NULL` while presenting a linked, non-split attribution view in `pr check` preserves ledger immutability and transparent cost accounting.

Third, the **general session-hook dispatcher (`session_hooks.py`)** establishes a clean, decoupled boundary. Triggering incrementally on `Stop` and finalizing on `SessionEnd` ensures near real-time synchronization, while the catch-up sweep (`capture-session --pending`) in `doctor` guards against abrupt kills. Hook safety controls—zero-exit enforcement, hard execution time budgets, strict privacy filters (persisting token counts and IDs only, never prompt or message payloads), and explicit exclusions for dispatched worktrees (`/worktrees/job-*`)—prevent session degradation and double-counting. Furthermore, marking legacy manual entries as `superseded_by_transcript` preserves full auditability without mutating historical rows.

### Position

**I recommend unconditional approval of the specification.** The architecture is mathematically sound, privacy-conscious, and provides a durable foundation for future hook handlers (compaction triggers and intent capture) without introducing bloat. Proceed directly to implementation planning under milestone v0.39.3.

## Synthesis
**Synthesis:** All three panelists approve the core design. Claude and Codex attach conditions, and Agy approves without any. Because two of the three found concrete gaps, I'm treating the approval as conditional.

**What's settled:**
- Ledger rows per (session, model, UTC day), with first-seen `message.id` de-duplication.
- A cursor that advances in the same transaction as the upsert.
- A derived `session_pr_links` view, so PR attribution never goes into the ledger.
- One shared capture path for the hook, the CLI and the backfill.
- Consent-gated hook install, exit-zero hooks, and a token-counts-and-IDs-only privacy boundary.

**Changes to fold into the spec before the plan:**
1. **Link completeness.** Say explicitly that a missing PR link means unknown, not none, so `pr check` doesn't report false negatives. Add a second link source: scan `gh pr` tool-use records and keep only the PR numbers.
2. **No summing across PRs.** Make it an invariant, with a test, that no consumer sums per-PR session costs. The "shared across N PRs" label stays.
3. **Exclusion and overlap.** Re-evaluate the job-transcript exclusion at sweep time, not just at capture time. Add a reconcile step that flags any `session_id` with both `transcript_derived` and `job_id` rows.
4. **Effective-cost view.** Add a `cost_entries_effective` view that every reader uses, in place of a flag each consumer has to remember. Add a test that fails on raw `FROM cost_entries` reads. This is a gating requirement for the consumer audit.
5. **Cache-creation cost.** State that cache-creation tokens contribute to `total_cost_usd`, not just to `turn_usage_json`, and cover it with a test.
6. **De-duplication boundary.** The cursor holds 16 recent IDs. Define what happens after cursor loss, a transcript rewrite, or repeats further apart than that. Either rebuild from a full re-scan or fail loudly. Don't let it silently drift.
7. **Hook latency.** Set an explicit budget for the `Stop` hook (under about 200 ms) and measure it.
8. **Provisional `payment_mode`.** Mark rows captured before gh:#5500 lands as provisional so they can be corrected.
9. **Pinned acceptance fixture.** Use a fixed transcript, since a live session keeps growing.
10. **Dispatcher scope.** Ship one handler and no extension-point code in this PR.
11. **Backfill order.** Run the backfill before any report that sums native cost.

**Process:** run `synlynk decide --record` against goal-62f693b8. Check that the file actually lands in the worktree's `project-docs/decisions/`, because of the known worktree path bug (gh:#1226).

Decision: Approve the native-session cost capture design (LIVE-35, gh:#5457, goal-62f693b8, v0.39.3) conditionally. Amend the spec with the eleven changes above, treating the `cost_entries_effective` view and the explicit de-duplication-recovery behavior as gating. Re-commit the spec and record the DECIDE linkage. Only then write the implementation plan and generate the GOVERNS-linked stories.

## Decision
Decision: Approve the native-session cost capture design (LIVE-35, gh:#5457, goal-62f693b8, v0.39.3) conditionally. Amend the spec with the eleven changes above, treating the `cost_entries_effective` view and the explicit de-duplication-recovery behavior as gating. Re-commit the spec and record the DECIDE linkage. Only then write the implementation plan and generate the GOVERNS-linked stories.

> Signatures: see 2026-11-24-native-session-cost-capture-per-session.json
