# GitHub-Write Capability Routing — Design

## Context

Issue [#426](https://github.com/nikhilsoman/synlynk/issues/426) found that `synlynk dispatch` sends GitHub-write tasks (`gh pr review`, `gh pr merge`) to agents that structurally cannot complete them headless:

- **Agy** — headless mode auto-denies the "command" permission class for external-mutating GitHub writes, even with `--dangerously-skip-permissions`.
- **Codex** — dispatched via `codex exec -s workspace-write`, whose sandbox blocks network egress to `api.github.com` by design (intentionally never upgraded to `--dangerously-bypass-approvals-and-sandbox`, which would grant full host/network access).
- **Grok** — the only agent confirmed to succeed at `gh pr review`/`gh pr merge` headless (PR #416, #417, #428).

A docs-only fix already shipped separately, codifying "route GitHub-write tasks to Grok" as documented policy in the routing SOP. This spec is the structural follow-up: make routing *enforce* this automatically instead of relying on whoever is dispatching to remember the rule.

This is scoped to #426 only. Issue #423 (all dispatched agents share one `nikhilsoman` GitHub identity, so even Grok's `gh pr review --approve` fails as self-approval) is a separate, independent problem — it needs real GitHub identity/auth infrastructure (a GitHub App or per-agent PATs) and is deferred to its own future spec.

## What This Builds

1. A `can_gh_write: bool` field added to each agent's entry in `AGENT_CAPABILITY_BASELINES` (`synlynk/_constants.py:44`), reflecting the evidence already gathered in #426:
   - `claude: true`
   - `grok: true`
   - `codex: false`
   - `agy: false`
   - `local: false`
2. A new `--requires-gh-write` flag on `synlynk dispatch` (added alongside `--force-agent` in `synlynk/cli.py`, in the `dispatch_parser.add_argument(...)` block starting at `cli.py:416`), threaded through to a new `requires_gh_write: bool = False` parameter on `dispatch_agent()` (`synlynk/dispatch.py:705`).
3. Enforcement logic inside `dispatch_agent()`, placed immediately after the existing story-based agent resolution block (`dispatch.py:714-723`):
   - If `requires_gh_write` is `False` (default) → no behavior change at all.
   - If `requires_gh_write` is `True` and the resolved `agent`'s baseline has `can_gh_write: True` → proceed unchanged.
   - If `requires_gh_write` is `True`, the resolved agent has `can_gh_write: False`, and `force_agent` is `False` → **auto-reroute**: pick the first agent in `baselines_map` (dict iteration order) whose baseline has `can_gh_write: True`, substitute it for `agent`, and print an info line to stdout stating the reroute happened and why (citing #426).
   - If `requires_gh_write` is `True`, the resolved agent has `can_gh_write: False`, and `force_agent` is `True` → **respect the override**: keep `agent` as explicitly chosen, but print a loud stderr warning that this combination is known to fail headless (citing #426), then proceed with dispatch as requested.
   - If `requires_gh_write` is `True` and no agent in `baselines_map` has `can_gh_write: True` (defensive; not expected given today's baselines) → raise `ValueError("No agent in AGENT_CAPABILITY_BASELINES has can_gh_write: True")`.

## Non-Goals

- No change to `_best_agent_for_story()`'s scoring heuristic (`synlynk/jobs.py:784`) — this is a post-hoc override layer applied after existing resolution, not a rewrite of story-based routing.
- No retroactive detection or correction of already-running/already-dispatched jobs.
- No solution to #423 (shared GitHub identity blocking formal `--approve` reviews) — separate future spec.
- No automatic detection of "this task needs GitHub writes" from task text or story metadata — the caller states it explicitly via `--requires-gh-write`, matching how `--force-agent` already works today.

## Data Flow

```
synlynk dispatch <agent> --task "..." [--requires-gh-write] [--force-agent] [--story <id>]
  → cli.py parses args, passes requires_gh_write=getattr(args, "requires_gh_write", False)
      into dispatch_agent(...)
  → dispatch_agent():
      1. existing story-based resolution (unchanged, dispatch.py:714-723)
      2. if requires_gh_write:
           baseline = baselines_map.get(agent, {})
           if baseline.get("can_gh_write", False):
               proceed                                   # capable, no-op
           elif not force_agent:
               capable = next agent in baselines_map with can_gh_write True
               agent = capable                            # auto-reroute
               print(f"  ↪ rerouted to '{agent}' (requires-gh-write; see #426)")
           else:
               print(f"  ⚠ '{agent}' cannot reliably complete GitHub-write "
                     f"actions headless (see #426) — proceeding because "
                     f"--force-agent was set", file=sys.stderr)
      3. rest of dispatch_agent() proceeds unchanged with final `agent`
```

## Error Handling

- Unknown `agent` string still raises `ValueError` exactly as today (`dispatch.py:722-723`) — this check happens before the new `can_gh_write` logic, so behavior for invalid agent names is unchanged.
- The defensive "no capable agent exists" case raises `ValueError` with a message naming the missing capability, rather than silently dispatching to an agent known to fail.
- No new exception types — reuses `ValueError`, matching the existing pattern in `dispatch_agent()`.

## Testing

TDD, added to wherever `dispatch_agent()` is currently tested (locate via existing test file for `synlynk/dispatch.py`):

1. `requires_gh_write=False` (default) with any agent → assert final agent and all other dispatch behavior is byte-for-byte identical to calling without the parameter at all (regression guard — this must be a strict no-op for every existing caller).
2. `requires_gh_write=True`, agent="grok" (can_gh_write: True) → assert no reroute, agent stays "grok".
3. `requires_gh_write=True`, agent="agy", force_agent=False → assert agent is rerouted to the first `can_gh_write: True` agent in `baselines_map` (i.e. "claude", given current dict order), and that the reroute message is printed.
4. `requires_gh_write=True`, agent="codex", force_agent=True → assert agent stays "codex" (override respected) and the stderr warning is printed.
5. Defensive case: monkeypatch `baselines_map` to have no `can_gh_write: True` entries, `requires_gh_write=True` → assert `ValueError` is raised.

## synlynk Orchestration Plan

Single Codex dispatch (Python/CLI/tests is Codex's lane):

1. **Task 1 — everything:** add `can_gh_write` to `AGENT_CAPABILITY_BASELINES`, add the `--requires-gh-write` CLI flag, add the enforcement logic to `dispatch_agent()`, write all 5 tests above, update the routing SOP doc note (already covers this at a policy level, but cross-reference the new flag once it exists). Small enough to be one task — no need to split further.

Existing `dispatch_agent()`/telemetry/cost-capture machinery requires no changes to support this — the new parameter is purely additive with a safe default.

## Open Questions / Risks

- **Reroute target selection when multiple agents qualify:** today only `claude` and `grok` have `can_gh_write: True`, and `claude` happens to sort first in `AGENT_CAPABILITY_BASELINES`' dict order. If a future agent's baseline is added before `grok`, the "first capable agent in dict order" rule could reroute to an agent other than the empirically-proven Grok. This is accepted as a known limitation — dict order is stable and explicit, and if it ever picks wrong, the fix is a one-line reorder or an explicit preference list, not a design change.
