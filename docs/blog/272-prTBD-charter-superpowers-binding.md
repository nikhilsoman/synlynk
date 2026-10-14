---
title: "PR #TBD — Charters Learn to Bind Skills, Not Just Roles"
date: 2026-10-14
series: "Building the OS for Multi-Agent Development"
post: 272
pr: 2306
status: open
author: "synlynk team"
version: "0.25.1"
tags: [posts]
---

## The Broader Goal at the End of the Previous PR

PR #2303 closed out gh:#2294 — a pytest verbosity shim that keeps dispatched jobs from paying for 1200-line
test-suite transcripts. That work, plus the empirical spot-check that followed it, left the session with a
confirmed, filed follow-up (gh:#2304: the shim gets bypassed by login-shell PATH re-prepending) and a broader
question still open from the day's master-plan recap: items 5 through 8 — charter skill-binding, auto-upgrade,
Vizor's revival, and multi-interface support — were all logged as one-line stubs with no scope, no issue, and no
design.

## Strategic Shifts in This PR (if any)

None — this PR is the first of those stubs getting turned into real scope. The recap item read simply
"GOVERNS-for-everything — missing `superpowers` key in `synlynk/charters.py`." Investigating it surfaced something
more specific and more interesting than the one-line description suggested: synlynk actually has *two* separate,
disconnected "charter" systems (a dead JSON dataclass path and a live markdown path that dispatch.py actually
injects), and the live one already has a `skills:` frontmatter key — it's just never populated with anything
except two hardcoded external-tool names, and even when populated it renders as inert YAML text with no
instruction telling a harness those skills are binding. The shift here is from "add a missing field" to "wire an
existing field all the way through, with enforcement language."

## What This PR Shipped

Filed gh:#2305 as the tracking issue once the real shape of the gap was confirmed by direct code inspection
(`grep` showing `AgentCharter`/`load_charter` are never read by `dispatch.py`, and that `skills:` has exactly one
producer today: `adapt_charters_for_installed_tools()`'s `TOOL_ROLE_SKILLS` map).

The design (`docs/superpowers/specs/2026-10-14-charter-superpowers-binding-design.md`) and plan
(`docs/superpowers/plans/2026-10-14-charter-superpowers-binding.md`) commit together, following the precedent PR
#2301 set for gh:#2294. The approach:

- A new `ROLE_SUPERPOWERS_SKILLS` static mapping in `charters.py`, feeding the *same* merge loop
  `adapt_charters_for_installed_tools` already uses for tool-derived skills — no new CLI surface, `synlynk
  charters adapt` picks it up automatically.
- `render_charter_section` (the function dispatch.py actually calls to build a dispatched job's context) gains a
  step that parses the charter's `skills:` frontmatter and, if non-empty, appends a `## Bound Skills (required)`
  section with explicit forcing language — modeled directly on the `using-superpowers` SessionStart hook's own
  "if 1% chance, you must invoke it" phrasing, rewritten harness-agnostically since not every dispatched harness
  has a `Skill` tool.
- A deliberate non-goal, stated plainly in both docs: the dead JSON `AgentCharter` path is documented, not fixed,
  here. Reconciling two charter systems in one PR would have blurred a focused fix into a larger refactor no one
  asked for yet.

The plan's three tasks build the mapping+merge, the rendering change, and — directly motivated by the session's
own experience a few hours earlier on gh:#2294/#2304, where unit tests passed while the real dispatched behavior
diverged — an end-to-end regression test that exercises the actual `dispatch.py:2417` call site, not just the
rendering function in isolation.

## Brainstorm Visuals Used

None. This PR went straight from a master-plan recap line item to code-level investigation to spec — no separate
brainstorm session was run, since the gap was narrow enough to scope directly by reading `charters.py`,
`charter_schema.py`, and `charter_injection.py`.

## What This Achieved on the Path to Autonomy

A dispatched headless job now has a charter-level signal for *how* to approach its work, not just *who* it is and
what it's allowed to touch. That's a small but real step toward GOVERNS actually governing behavior, not just
identity and authority — the gap that gh:#2305's title names directly.

## Strategic Note: The Goal at the End of This PR

Items 6 (auto-upgrade/bundled deps) and 7 (Vizor revival) remain unscoped. Item 7 in particular was clarified this
session as substantially larger than its one-line stub suggested: Vizor, the project's entire visual interface
layer, is reportedly not working at all right now and needs a full audit before any specific fix can be scoped —
that's the next piece of work, not a quick follow-on to this PR.
