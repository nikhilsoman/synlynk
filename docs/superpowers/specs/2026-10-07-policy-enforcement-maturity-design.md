# Policy Enforcement Maturity — Design

**Status:** Approved by Nikhil, 2026-10-07
**Author:** Claude (home conductor session)
**Related issues:** gh:#1990 (GOVERNS hard-fail, not yet built), gh:#1991 (cross-harness hard-fail, built but buggy), gh:#1992 (host-auth audit log, not yet built), gh:#2095 (cross-harness provenance misattribution bug), gh:#2118 (review-dispatch sandbox CLI deadlock), gh:#2119 (Codex home-conductor friction investigation)

## 1. Problem Statement

The 2026-10-04 Hardened PR Review Policy (CLAUDE.md) added hard-fail merge gates to `synlynk pr check` / `policy check-merge`. Two of them are causing disproportionate friction relative to the enforcement code actually backing them:

- **`governs_authority.require_linked_goal`** — `pr check`/`policy check-merge`'s hard-fail enforcement code does not exist yet (gh:#1990). As of 2026-10-06, dispatch *preflight* (a separate code path, at dispatch time rather than merge time) does emit a non-blocking warning to stdout/`sentinel.md` when no GOVERNS link is resolvable — but the job still proceeds, and `pr check` itself still has no enforcement at all. This design's `require_linked_goal_mode` governs the future `pr check`/merge-time gate once gh:#1990 lands; it does not change the existing dispatch-preflight warning, which is already non-blocking.
- **`merge_authority.cross_harness_review_required`** — *is* implemented (`synlynk/db.py:233-296`, `_cross_harness_review_verdict`), and has a confirmed bug: `_implementation_identity_from_native_cost_entry()` (`db.py:144-157`) cannot distinguish a native implementer's cost-provenance row from a reviewer's own self-logged stub — both look identical (`job_id IS NULL`, newest wins). A reviewer's self-logged `$0.0000` stub got mistaken for the implementer's identity, falsely blocking a second, genuinely-different-harness reviewer (gh:#2095).

Session evidence: merging a single PR (#2094) required three dispatched review jobs ($9.33 + $1.06 + $0.26) because the first two attempts hit gate bugs, not real defects. A separate, previously undocumented gap (gh:#2118) means `review`-type dispatches cannot run *any* `synlynk` CLI command at all — including the `pr check` the policy itself mandates reviewers run — because `_reconcile_jobs()` writes a lock file unconditionally at CLI startup, which crashes under Codex's read-only review sandbox. Reviewers have been silently falling back to reviewing diffs directly via `git`/`gh`, meaning the policy's own gates have barely been exercised by recent review dispatches at all.

**Goal of this design:** stop blocking merges on gates whose enforcement code is unfinished or buggy, without losing visibility into what those gates would have said — and define an objective, evidence-based path back to hard enforcement once each gate proves reliable.

## 2. Approaches Considered

**A. Just disable the two gates entirely (flip booleans to `false`) until bugs are fixed.**
Simplest possible change. Rejected: loses all signal — no record of what the gate would have said, no way to tell when it's safe to re-enable, and reintroduces risk silently (a bad merge could slip through with zero trace).

**B. Observe/record mode with a per-gate durable event log and consecutive-clean-streak counter (recommended).**
Each gate keeps running and producing its real verdict every `pr check`; in `"observe"` mode a WARN no longer blocks `qa`'s merge, but every verdict (pass/warn/insufficient_data) is written to a new `policy_gate_events` table. A per-gate streak of consecutive `"pass"` verdicts (reset by any `"warn"` or `"insufficient_data"`) is the re-hardening signal — once a gate crosses 100 consecutive clean passes, `pr check` surfaces a recommendation to flip that gate back to `"enforce"` as a manual, reviewed `policy.json` edit.

**C. Keep hard-fail but add a manual override flag per merge (e.g. `--override-gate <name> --reason "..."`).**
Keeps the gate "on" by default but lets `qa` bypass it case-by-case with a logged reason. Rejected as the primary mechanism: still requires active human intervention on every single PR hit by a buggy gate (same friction, just shifted from "blocked" to "requires an escape hatch each time"), and doesn't produce the aggregate evidence needed to know when the underlying bug is actually fixed.

**Recommendation: B.** It's the smallest change that satisfies all four of the user's stated asks (stop being too stringent; observe+record; fix the documented gaps; re-harden after a clean streak), and reuses the same evidence-based philosophy already established by the Empirical Capability Assessment Policy's ≥5-sample-size rule — scaled up to 100 because merge-gate false positives are costlier than routing misassignments.

## 3. Design

### 3.1 `policy.json` schema change

Each gated flag gains a sibling `*_mode` field (default `"enforce"` for backward compatibility if absent):

```json
"governs_authority": {
  "require_linked_goal": true,
  "require_linked_goal_mode": "observe"
},
"merge_authority": {
  "cross_harness_review_required": true,
  "cross_harness_review_required_mode": "observe",
  "can_merge": ["qa"],
  "require_non_authoring_review": true,
  "review_fallback": "same_identity_comment_checklist"
}
```

`mode` ∈ `"enforce"` (current behavior — a WARN blocks merge) | `"observe"` (WARN is printed with identical diagnostic text, but does not block `qa`'s merge). Nothing about *what* is checked changes — only whether a WARN becomes a hard stop. This repo's initial values: `require_linked_goal_mode = "observe"`, `cross_harness_review_required_mode = "observe"`.

### 3.2 `policy_gate_events` table (state.db)

```sql
CREATE TABLE policy_gate_events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pr_number INTEGER NOT NULL,
    gate TEXT NOT NULL,              -- 'governs_authority' | 'cross_harness_review'
    mode TEXT NOT NULL,              -- 'enforce' | 'observe', at time of check
    verdict TEXT NOT NULL,           -- 'pass' | 'warn' | 'insufficient_data'
    detail TEXT NOT NULL,            -- the existing human-readable verdict string
    recorded_at TEXT NOT NULL        -- ISO8601 UTC
);
CREATE INDEX idx_policy_gate_events_gate ON policy_gate_events(gate, id);
```

Added via the migrations framework (`synlynk/migrations/`, per gh:#1926) rather than the legacy monolithic `_migrate_db`. One row is written per gate, per `pr check` invocation, **regardless of mode** — observe mode's entire value proposition is that it still produces a queryable record, not just louder console output.

### 3.3 `pr check` / `policy check-merge` behavior change

In `db.py`, each gate's verdict function (`_cross_harness_review_verdict`, and the future GOVERNS-linkage check once gh:#1990 lands) is wrapped by a small `_evaluate_gate(gate_name, verdict_fn)` helper that:
1. Calls the existing verdict function unchanged (same logic, same diagnostic text).
2. Reads that gate's `mode` from `policy.json`.
3. Writes the `policy_gate_events` row.
4. If `mode == "enforce"` and verdict is `warn`/`insufficient_data` → returns the block as today.
5. If `mode == "observe"` → prints the same WARN/insufficient-data text prefixed with `[OBSERVE MODE — not blocking]`, returns a pass-through (does not block `qa`'s merge).

No change to `can_merge`, `require_non_authoring_review`, or any gate not explicitly moved to observe mode (e.g. the personal-GitHub-token-off-limits structural restriction, which isn't a `policy.json` flag at all and is out of scope here).

### 3.4 Re-hardening signal

A gate's streak = count of consecutive `policy_gate_events` rows with `verdict = 'pass'` for that gate, walking back from the most recent row, stopping at the first `'warn'` or `'insufficient_data'` (either resets to 0 — "couldn't tell" is not evidence of trustworthiness). Exposed via a new `synlynk policy gate-status` command (small, scoped command — not the full `synlynk capability report`, which doesn't exist yet per gh:#1993) that prints each observe-mode gate's current streak and the 100-pass threshold, and recommends (but does not perform) flipping `mode` back to `"enforce"` once crossed. The flip itself is always a manual, reviewed `policy.json` edit — same discipline as the Empirical Capability Assessment Policy's own `task_allocation` regeneration (generated signal, human-approved change).

### 3.5 Known gaps tracked, not fixed here

This design's scope is the observe-mode mechanism only. The following are separate, already-filed issues that should close before any gate is manually re-hardened, but do not block shipping this mechanism:

- gh:#2095 — `_implementation_identity_from_native_cost_entry` cannot distinguish implementer provenance from reviewer provenance (root cause confirmed and documented in the issue).
- gh:#2118 — `review`-type dispatches crash on any `synlynk` CLI invocation (including `pr check` itself) due to `_reconcile_jobs()`'s unconditional lock-file write under a read-only sandbox.
- gh:#2119 — Codex home-conductor friction (unreproduced from this session; needs investigation from within Codex's own session).

### 3.6 Error handling

- Missing `*_mode` key → defaults to `"enforce"` (fail safe, preserves current behavior for any gate this design doesn't explicitly touch).
- Malformed `policy_gate_events` write (e.g. DB locked) → logged as a warning, does not block the `pr check` result itself; the gate's own verdict still governs enforce-mode blocking even if the event row fails to persist.
- `gate-status` command run with zero recorded events for a gate → reports "no data yet," not a streak of 0 conflated with "0 consecutive failures."

### 3.7 Testing

Unit tests in `synlynk/db.py`'s test module:
- `mode` defaults to `"enforce"` when absent from `policy.json`.
- `observe` mode: a WARN verdict does not raise/block, but is still recorded.
- Every `pr check` call writes exactly one `policy_gate_events` row per evaluated gate, in both modes.
- Streak calculation: resets correctly on `warn`, resets correctly on `insufficient_data`, counts correctly on consecutive `pass`.
- Streak is scoped per-gate (a `warn` on `cross_harness_review` does not reset `governs_authority`'s streak).
No integration/dispatch-level test is needed — this is pure `db.py` + `policy.json` schema logic.

## 4. Non-goals

- Does not fix the #2095, #2118, or #2119 bugs (separate issues).
- Does not implement the GOVERNS hard-fail enforcement code itself (gh:#1990) — only changes what happens once it exists.
- Does not touch the personal-GitHub-token-off-limits restriction or its audit logging (gh:#1992) — that's a structural dispatch-env restriction, not a `policy.json` flag, and isn't part of the friction this design addresses.
- Does not automate the re-enforce flip — crossing the streak threshold produces a recommendation, not an automatic `policy.json` edit.
