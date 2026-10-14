# Continuous Momentum: Self-Claim Backlog + Decide-as-Tiebreaker

> Status: design proposal; no implementation included
>
> Date: 2026-10-10
>
> Scope: eliminate idle-after-finish, allocation-authority gaps, and
> decision-blocking as sources of lost autonomous momentum, using only
> existing surfaces (`stories` table, `synlynk decide`, `state.db`-sourced
> dashboard) — no new infra.

## 1. Problem

synlynk's stated goal is continuous autonomous implementation: so long as a
goal is planned and designed, work should keep moving without a human
re-starting it. In practice, momentum is lost in three ways:

1. **Idle-after-finish** — a harness (home or dispatched) completes a task
   and stops, instead of pulling the next ready unit of work.
2. **Allocation-authority gap** — no mechanism decides *what* an idle
   harness should do next; today a human (or Claude-as-PM) has to assign it.
3. **Decision-blocking** — when a scope/mandate fork comes up mid-epic
   (not an implementation detail, a real fork in direction), work stalls
   waiting for a human to notice and weigh in, with no structured path to
   surface the question and resume once answered.

Constraint (user-stated): solve this in the current architecture, with no
new surface/infra to maintain, if at all possible.

## 2. Approach selected

Three mechanical approaches were considered: (A) small CLI extensions to
`synlynk story`/`synlynk decide`, (B) a pure documented protocol with zero
new code, (C) a new `--autonomous` dispatch-level daemon loop.

**Decision: A.** (User-approved.) B under-delivers — a documented
convention with no enforcement will decay the same way the heuristic
capability tables did. C introduces a new long-running surface (a daemon)
that becomes one more thing to maintain and debug, which conflicts with
the no-new-infra constraint. A reuses `stories` (already the backlog of
record) and `synlynk decide` (already the escalation mechanism) and adds
only thin CLI surface on top of both.

## 3. Design

### Component 1 — Shared backlog, self-claim

**Mechanism:** `synlynk story claim-next --role <role> --harness <harness>`,
a new subcommand. Atomically claims the next `status='ready'` row in
`stories` that the calling harness is eligible for, via an optimistic
`UPDATE stories SET status='claimed', claimed_by=? WHERE story_id = (
SELECT story_id FROM stories WHERE status='ready' AND <eligibility filter>
ORDER BY priority ASC LIMIT 1) AND status='ready'` pattern — SQLite's WAL
mode already makes this safe across concurrent callers with no new lock
infra.

**Eligibility filter:** role/task_type compatibility, read from
`.synlynk/policy.json`'s `task_allocation` (and, once it ships,
`role_task_type_compat` from `story-issue-2069`/gh:#2068 — `claim-next`
should consume that matrix, not reimplement it) plus goal/roadmap
membership (only claim stories under an active, non-superseded goal).

**Loop:** each harness's home/interactive session runs: finish task →
`synlynk story done <id>` → `synlynk story claim-next` → work, or report
idle (nothing eligible/ready) back to whoever is acting as PM for the
session.

**Reclaim safety:** a harness that dies or stalls mid-claim is covered by
the existing `synlynk story reclaim` command — no new mechanism needed.

**Relationship to `story-bs8-loop`:** BS-8's `dispatch_loop()`
(`goal-d38e3c83`) does the equivalent job for *headless, away-mode*
dispatch — composite termination, `/goal` objective injection, job-chain
tracking. Component 1 is the home/interactive-mode counterpart to BS-8,
reading from the same `stories` table — not a duplicate. The two should
converge on the same eligibility-filter logic (§3's role/task_type check)
rather than each growing its own.

### Component 2 — `decide` as institutionalized tiebreaker

**Mechanism:** extend the existing `cmd_decide` function (`synlynk/team.py`)
with `synlynk decide --issue <N> --wait-approval`.

**Trigger:** a harness self-invokes this **only** for scope/mandate forks —
a genuine fork in direction or authority, not an implementation-detail
choice. Implementation details stay the harness's own judgment call, per
the user's explicit threshold decision earlier in this design's brainstorm.

**Flow:** post the panel's recommendation as a GitHub issue comment via
the existing role-scoped `gh` plumbing (`synlynk gh --role pm`), opening an
issue first if none exists for this fork. Then poll that issue's comments
for the user's reply, **blocking until it lands — no timeout, no
auto-proceed.** This matches the user's explicit approval-UX decision
(GitHub issue comment, not a Herdr-pane relay).

**This closes `story-5dfe6b3f`** ("Define autonomous PM/TPM grooming and
four-boundary human notification contract", `goal-90e73dfd`) — that story
is a draft placeholder for exactly this mechanism, with no prior body or
gh_issue to conflict with. This spec should be linked from that story (and
the story's goal) rather than tracked as a separate, parallel concept.

**Reclaim safety:** a harness that dies while waiting on a `decide`
response is covered the same way as any other in-flight claim — on
restart/reclaim, the waiting state is re-derived from the GitHub issue's
own comment history (did the human reply yet?), not from in-memory state
that could be lost.

### Component 3 — Dashboard: no change

The dashboard stays sourced from `state.db`/GOVERNS stories (already
confirmed working via `roadmap_dashboard.py`), not rebuilt from GitHub
state. Per the user's explicit sign-off: "Yes, keep state.db as the one
source (recommended)." Nothing in Components 1 or 2 changes this —
`claim-next` and `decide --wait-approval` both operate on data the
dashboard already reads.

## 4. Error handling / edge cases

- **No eligible story for a harness:** `claim-next` exits cleanly reporting
  idle; the calling session surfaces this rather than busy-looping.
- **Claim race:** the optimistic `UPDATE ... WHERE status='ready'` guard
  means a losing racer gets zero rows affected and simply retries the
  query (another `ready` row, or idle) — no distributed lock needed.
- **`decide` panel produces no clear resolution:** falls back to the
  existing escalation path (whoever is acting as home/PM for the session),
  same as any other ambiguous decide outcome today.
- **Human never replies:** by design, no timeout/auto-proceed — this is a
  genuine scope/mandate fork, and proceeding without an answer is exactly
  the loss-of-authority this component exists to prevent. This is a
  deliberate tradeoff: it trades some momentum (a blocked story) for
  correctness on authority-level decisions, while Component 1 keeps every
  *other* eligible story moving in parallel (claim-next does not block fleet-wide
  progress, since it operates on a different story than the one blocked
  on `decide`).

## 5. Testing

- Unit: `claim-next`'s atomic UPDATE actually prevents double-claim under
  concurrent callers (simulate with two connections racing on the same
  `ready` row).
- Unit: eligibility filter correctly excludes a harness lacking the
  story's required role/task_type, and excludes stories under an inactive
  or superseded goal.
- Unit: `decide --wait-approval` polling correctly detects a new comment
  on the target issue and exits the wait loop; does not false-positive on
  an unrelated comment or a comment predating the dispatch.
- Integration: `story done` → `claim-next` → `story done` chain across two
  consecutive stories with no manual intervention.

## 6. Related work (consolidation audit, 2026-10-10)

Audited against all open goals/stories in `state.db` tagged toward
autonomous operation (`goal-eacab0dc`, `goal-f424fc4c`, `goal-d38e3c83`,
`goal-90e73dfd`, `goal-bc0011cd`, `goal-079e2f37`, `goal-adb60ccc`, and
others). No duplicate or conflicting prior design was found; a `decide`
panel was judged unnecessary for this audit (no competing decision exists
to arbitrate). Findings:

- **`docs/superpowers/specs/2026-10-06-governs-velocity-unblock-design.md`**
  (`story-issue-2060`/`2067`) — already-committed, solves a different
  layer (completion-oracle cross-branch evidence, reviewer-logged cost
  provenance, role×task_type enforcement at dispatch, GOVERNS hard-fail
  ambiguity). Complementary: that design makes dispatch *results*
  trustworthy faster; this design makes the *next dispatch* happen without
  a human re-starting it. Cross-link, do not merge.
- **`story-5dfe6b3f`** — satisfied by Component 2 (see §3).
- **`story-bs8-loop`** — home-mode counterpart relationship with Component
  1 (see §3); should share eligibility-filter logic, not duplicate it.
- **`story-issue-2069`** (role×task_type compat matrix, gh:#2068) —
  Component 1's eligibility filter is a consumer of this once it ships.
- **`story-issue-2094`** / `docs/strategy/2026-10-10-dev-preview-revised-roadmap.md`
  — no mention of self-claim/idle/decide-escalation; no collision. This
  design should be filed under Pillar 2 (`goal-eacab0dc`, "Autonomously
  operate the GOVERNS SDLC") in that roadmap.

## 7. Out of scope

- Any new daemon, service, or long-running process (ruled out as Approach
  C, per the no-new-infra constraint).
- Loosening `cross_harness_review_required`, self-approval guards, or any
  other Hardened PR Review Policy gate — Components 1/2 produce more work
  for those gates to review, not an exception path around them.
- BS-8's own headless `dispatch_loop()` implementation — tracked
  separately under `goal-d38e3c83`; this spec only defines the
  home-session analog and the shared eligibility-filter contract between
  them.
