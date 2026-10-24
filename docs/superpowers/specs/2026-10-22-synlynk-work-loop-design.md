# `synlynk work` — Autonomous Story Pickup Loop: Design Spec

**Date:** 2026-10-22
**Status:** Approved
**Roadmap entry:** New collaborator onboarding — "how does the new user pick up work" follow-on to `synlynk join` (v0.9.2) and Story Home Claims (gh:#2511, PR #2524)

---

## Context

This spec grew out of a brainstorm about new-collaborator onboarding. The original proposal was a GitHub ticket containing an Agy CLI prompt that installs synlynk and wires `GEMINI.md` to poll GitHub for assigned issues and execute whatever instructions the issue body contains.

That proposal was rejected during brainstorming for three reasons:

1. **Prompt-injection / supply-chain surface.** A standing instruction to "process any assigned ticket per its instructions" gives anyone who can open or edit a GitHub issue — including a compromised account or a mis-scoped label automation — an arbitrary-instruction channel into an agent running with `--dangerously-skip-permissions`.
2. **Duplicates existing onboarding infrastructure.** `synlynk join` (v0.9.2, `synlynk/team.py:998`) already onboards a new team member: it regenerates `CLAUDE.md`/`GEMINI.md`/`AGENTS.md`, seeds their devlog, and prints a one-time "RECOMMENDED FIRST TASK". A bespoke GitHub-ticket mechanism would route around this rather than extend it.
3. **Reads a mirror, not the source of truth.** This repo already runs `synlynk backlog sync` to push synlynk stories *to* GitHub issues. Having Agy read raw issue bodies as instructions means reading a downstream copy instead of the reviewed, GOVERNS-linked story record.

The agreed direction: `synlynk join` already solves first-contact onboarding. What's missing is **ongoing, unattended work pickup** — after day one, a collaborator (human or their harness) should be able to keep finding and claiming the next piece of synlynk-tracked work without a human re-driving each pickup, and without reopening the injection surface that killed the original proposal.

This also needs to work in a **swarm**: multiple collaborators, each potentially running multiple harnesses (Claude, Agy, Grok, Codex), all polling the same shared backlog concurrently, without double-claiming a story.

---

## Existing primitives this design reuses

Three pieces of existing, already-shipped machinery make this a thin orchestration layer rather than new infrastructure:

- **`task_leases` table + claim functions** (`synlynk/jobs.py:3836-4170`, gh:#2511, PR #2524): `acquire_task_lease()` does an atomic SELECT-then-INSERT against the shared `state.db`, keyed by `story_id`. `leased_by` encodes `{harness}:{hostname}:{pid}`. `heartbeat_claims_by_story_ids()` renews a held lease by exact `lease_id` (not just `story_id`, so a stale marker from an overridden claim can't silently renew someone else's lease — a fix already made during #2511's cross-harness review). `release_task_lease()` and `reclaim_stranded_stories()` round out the lifecycle. **This is already the swarm concurrency primitive** — no new locking is needed.
- **`story_governs_linkage()`** (`synlynk/governs_gate.py:16`): the same check `synlynk pr check` and dispatch preflight already use to enforce 100% GOVERNS adherence. Reused here, not reimplemented, so this loop cannot become a backdoor around that policy.
- **`synlynk dispatch`** and its per-harness no-prompt contracts (`HARNESS_CAPABILITY_BASELINES` in `synlynk/_constants.py`): the existing Away Worker execution path. This design adds a selection+claim loop in front of it; it does not change how dispatch itself runs.

---

## Scope

One new module, `synlynk/work_loop.py`, exposing two CLI actions under a new `synlynk work` subcommand group:

1. `synlynk work claim-next` — one-shot: find the next claimable story and claim it. A scripting primitive; does no execution itself.
2. `synlynk work run` — the actual pickup loop: select → claim → execute → heartbeat → release, bounded by explicit stop conditions.

Out of scope for this spec: the GitHub-issue-polling mechanism from the original proposal (rejected, see Context); any change to `synlynk join`, `synlynk dispatch`, or the `task_leases` schema itself.

---

## `synlynk work claim-next`

```
synlynk work claim-next [--role ROLE] [--harness HARNESS] [--duration SECONDS=2700]
```

Runs the candidate selection query (below), attempts `acquire_task_lease` on the top candidate, and on success prints the claimed `story_id` and exits 0. On failure (lost the race, or nothing claimable), exits 1 with a one-line reason. Thin wrapper — no retry loop, no execution. Exists so a human or a shell script can claim a single story without invoking the full `work run` loop.

## `synlynk work run`

```
synlynk work run [--role ROLE] [--max-iters N=1] [--dispatch-harness auto|home|<name>] [--parallel N=1] [--interval SECONDS=0]
```

### Candidate selection

```sql
SELECT s.story_id, s.title, s.role, s.priority
FROM stories s
LEFT JOIN task_leases tl
  ON tl.story_id = s.story_id AND tl.status = 'active'
WHERE s.readiness = 'ready'
  AND tl.lease_id IS NULL
  AND (:role IS NULL OR s.role = :role)
ORDER BY s.priority DESC, s.rowid ASC
```

Each candidate is then passed through `story_governs_linkage(conn, story_id)`; any result that isn't `linked` is dropped before the next step. This mirrors the dispatch-preflight gate exactly — a story that couldn't be dispatched today cannot be claimed by this loop either.

### Per-iteration flow

1. Pull the next governs-linked candidate from the query above.
2. Call `acquire_task_lease(story_id, leased_by=f"{harness}:{hostname}:{pid}", harness=harness)`.
   - `acquired: False` (lost the race to a concurrent claimant) → drop this candidate, try the next one. Cap at 5 consecutive race losses per iteration before giving up on this iteration entirely (treated as "nothing claimable right now", not an error) — this bounds the loop against spinning when the backlog is small and contested.
3. On successful claim, start a background heartbeat: call `heartbeat_claims_by_story_ids({story_id: lease_id})` every `min(300, duration_seconds / 3)` seconds for as long as the story is in-flight. This is a plain timer, not a separate process — it runs between the synchronous steps below, not concurrently with them.
4. **Execute:**
   - If `--dispatch-harness home` (default when the invoking session is an interactive Home Conductor): do the work directly in this session, same as a human would — write code, open the PR, etc.
   - Otherwise (`auto` or an explicit harness name): call `synlynk dispatch` targeting that harness (or, for `auto`, whatever harness the existing Capability-Based Task Allocation / empirical routing would pick for the story's `role`). This dispatched job is a normal Away Worker — it goes through the same PR review, cross-harness-review, and merge-authority gates as any other dispatched task. `work run` does not bypass those; it only decides *which* story to feed in.
5. **Release:** only after the resulting PR is verified merged (reuse whatever `synlynk story done` already checks — do not reimplement merge verification here). Call `release_task_lease(story_id, leased_by, new_status='done')`.
6. If execution fails or is blocked (dispatch reports `BLOCKED`, or the Home-Conductor path hits an unresolvable error): **do not** auto-reclaim and move to the next story. Leave the lease as-is (it will either get a further heartbeat if the human is actively investigating, or expire and be swept by `reclaim_stranded_stories` on its normal TTL), print a clear escalation message, and stop the loop. This mirrors the existing "2-cycle then escalate" pattern used for `BEHIND`/`DIRTY` PRs elsewhere in this project — failures are surfaced, not papered over by continuing.

### Stop conditions

The loop exits cleanly (not an error) when any of these hit:

- `--max-iters` reached (default **1** — `work run` is a bounded batch operation by default, not a daemon; a human or a supervising process is expected to re-invoke it, e.g. from a shell `while` loop or a scheduled job, if continuous operation is wanted)
- No claimable candidate found (after the race-loss cap above)
- `check_budgets()` reports the cost/request budget exceeded
- A `FLATLINE` sentinel from `check_sentinel_patterns()` (3 consecutive failures) — reused, not reimplemented

A failed/blocked execution (step 6 above) also stops the loop, but is reported as an escalation rather than a silent "done."

### `--parallel`

When `--parallel N > 1` and `--dispatch-harness` is not `home`, `work run` may have up to `N` dispatched jobs in flight at once, each independently claimed via step 2. This is safe for the same reason the swarm case in general is safe: claim acquisition is the shared gate, not something `work run` tracks itself. `--parallel` has no effect combined with `--dispatch-harness home` (a single interactive session can only work on one story at a time) and is rejected with an error if both are passed.

---

## Swarm behavior

No new design is needed here — it falls out of reusing `task_leases`. Multiple humans, each running their own `synlynk work run` (on whatever harness is their Home Conductor), and/or dispatched Away Worker jobs themselves invoking `work run`, can all poll the same `stories` table and race for claims concurrently. The atomic claim check in `acquire_task_lease` (a single SQLite transaction doing SELECT-then-INSERT, already hardened against the "same holder" and "override" edge cases during #2511's review) is the only coordination mechanism required. A new collaborator who runs `synlynk join` followed by `synlynk work run` joins this swarm with no additional setup.

---

## Error handling summary

| Condition | Behavior |
|---|---|
| Lost claim race | Skip candidate, try next (capped at 5/iteration) |
| No claimable stories | Exit 0, "nothing to claim" |
| GOVERNS-unlinked candidate | Excluded from query results entirely |
| Dispatched job BLOCKED/failed | Stop loop, escalate; lease left for TTL sweep |
| Budget/sentinel trip | Stop loop, report which limit tripped |
| `--parallel` + `--dispatch-harness home` | Reject at argument parsing, not at runtime |

---

## Testing

- **Unit — candidate query:** role filter includes/excludes correctly; a story with an active lease is excluded; a GOVERNS-unlinked story is excluded even if otherwise `ready`.
- **Unit — race:** two concurrent `acquire_task_lease` calls for the same `story_id` (reuse/extend existing #2511 coverage if present) — exactly one succeeds.
- **Integration — single iteration:** tmp `state.db` with one ready, linked story; `work run --max-iters 1 --dispatch-harness home` with a stubbed execution step; assert claim → execute → release sequence and final story status.
- **Integration — swarm:** tmp `state.db` with 3 ready linked stories; spawn 2 `work run` processes concurrently; assert no story is claimed by both, and all 3 end up claimed exactly once between them.
- **Integration — failure path:** stub a dispatch failure; assert the loop stops, the lease is left intact (not force-released), and the exit output names the failure rather than silently continuing to the next story.
