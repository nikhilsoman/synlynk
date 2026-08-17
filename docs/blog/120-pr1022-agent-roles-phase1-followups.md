# PR #1022 — Agent-Roles-Charters Phase 1 Follow-Ups: Closing the Footguns

## The Goal at the End of the Previous PR

PR #1003 (post #117) shipped Phase 1 of agent-roles-charters: a CLI (`synlynk agent
init/list/show/edit/disable`) and `agent_id`-driven dispatch integration, giving synlynk a
persistent workspace-agent identity distinct from the swappable execution harness. Its
non-authoring review (Grok, via `synlynk pr check`) approved and merged the PR but flagged five
non-blocking follow-up items — real footguns for the capability-grants work planned in Phase 2, not
blockers for Phase 1 itself. PR #1003's own retrospective named them explicitly: `capability_grants`
still gets wiped on every `agent edit`, and a dispatched job's originating agent identity is lost
the moment dispatch returns because `daemon_jobs` has no `agent_id` column.

## Strategic Shift in This PR

None. This PR is exactly the scope `docs/superpowers/specs/2026-08-16-agent-roles-phase1-followups-design.md`
laid out: five small, same-file-neighborhood fixes, explicitly scoped apart from the larger Phase 2
(memory + gated learning) work so that cleanup didn't get tangled with new design risk. One
deliberate, flagged deviation from the spec's literal text: §3 said to add `agent_id` to the
quota-deferred `INSERT INTO daemon_jobs` branch "mirroring `session_id` exactly" — but that branch
doesn't actually carry `session_id` today. The plan documented this up front and every dispatch
prompt for that task explicitly said to leave the branch untouched rather than force a mirror that
would introduce an inconsistency the spec didn't intend.

## What This PR Shipped

Executed as eight TDD tasks via Subagent-Driven Development, each dispatched individually to Codex
(`synlynk dispatch codex --task "..." --force-agent --context-mode full`), independently re-verified
by re-running the affected test files myself after every merge rather than trusting each job's
self-reported pass/fail — one job's self-report (3 failures) turned out to be a sandbox-only
`PermissionError` writing to `~/.synlynk/workspaces`, confirmed harmless only once re-run outside
that job's sandbox:

- **`daemon_jobs.agent_id` persistence** — new schema migration (`db.py`, guarded `ALTER TABLE`)
  and a new `_ensure_daemon_job_agent_id_column()` helper, threaded through both live write paths in
  `dispatch_agent()` (the `UPDATE ... SET agent_id=COALESCE(agent_id, ?)` branch and the
  `INSERT OR REPLACE` branch). The value written is the `agent_id` UUID parameter, not the resolved
  role string — it identifies *which* workspace agent dispatched the job.
- **`capability_grants` merge-not-replace** — `regenerate_agent_projection()` now reads the existing
  `.synlynk/agents/<id>.yaml` projection's `overrides` block before writing, merging new
  `repo_overrides` on top instead of replacing the dict wholesale. `cmd_agent_edit` drops its
  hardcoded `repo_overrides={"capability_grants": {}}` entirely — existing grants now survive a
  charter edit. New-agent init is unaffected: with no existing file, the merge still starts from
  `{}`.
- **`resolve_dispatch_harness()` extraction** — the inline role→harness resolution logic that lived
  only inside `dispatch_agent()` is now a standalone, side-effect-free function (no subprocess spawn,
  no DB write), called from both `dispatch_agent()` and `cli.py`'s `--dry-run` preview branch. Before
  this, `synlynk dispatch --as-agent dev --dry-run` (no explicit harness) printed `agent: None`
  because the preview never ran the same auto-selection the live path did.
- **`_harness_for_org_role` restricted to `CORE_FLEET`** — the function iterated
  `sorted(AGENT_CAPABILITY_BASELINES)`, the full baseline key set including experimental/non-fleet
  entries, sorted alphabetically. A future baseline (e.g. `"local"`) could win a role's harness pick
  purely by sorting before `agy`/`claude`. Iteration now filters to `synlynk._constants.CORE_FLEET`
  first.
- **Regression coverage** — a new test proves `story_id`-based routing still wins over `agent_id`
  role-based fallback when both are present (confirming Task 5's extraction preserved the original
  precedence order), plus a test locking in the `CORE_FLEET` filter using a fake non-fleet baseline
  that would otherwise win by alphabetical sort.

Full suite: 2026 passed, 2 skipped, 0 failed (`python3 -m pytest -q`, run independently after every
merge, not just at the end).

## Brainstorm Visuals Used

None — this was pattern-following cleanup work in an already-mapped file neighborhood
(`dispatch.py`, `agent_cli.py`, `agent_store.py`, `db.py`, `cli.py`); no new visual brainstorming was
needed.

## What This Achieved on the Path to Autonomy

The two persistence gaps this closes are exactly the ones the next phase depends on. Phase 2 wants
`capability_grants` to become load-bearing — actually read and enforced during dispatch/harness
selection — which only makes sense if grants survive a charter edit instead of being silently reset
every time. And any future "jobs by agent" view, cost attribution, or trust-scoring mechanism needs
`daemon_jobs.agent_id` to actually exist in the table; before this PR, the identity was resolved in
memory and then thrown away the moment `dispatch_agent()` returned.

## The Goal at the End of This PR

All five PR #1003 follow-up items are closed. Phase 1 of agent-roles-charters, plus its own
follow-up debt, is now fully settled — nothing deferred, nothing silently dropped. The next goalpost
is Phase 2: making `capability_grants` mean something (read and enforced, not just stored) and
building the gated-learning/memory layer on top of the now-solid identity and persistence
foundation this PR finished laying.
