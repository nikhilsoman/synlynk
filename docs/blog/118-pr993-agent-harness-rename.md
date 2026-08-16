# 118: PR #993 — freeing `agent` from `harness`

## Where we left off

PR #880 (post #113) shipped Phase 0 of the Agent-vs-Harness terminology rollout:
`docs/glossary-agent-vs-harness.md`, a renamed `Role | Harness | Tasks` table, and
wording fixes across `CLAUDE.md`/`README.md`/`SYNLYNK_GUIDE.md`. But Phase 0 was
docs-only by design — it named the distinction without touching any code. The CLI
itself still had `synlynk agent add/configure/run/list` bound to execution-backend
selection, which is exactly the concept Phase 0's glossary calls **Harness**, not
**Agent**. Task #97 (Agent-roles-charters Phase 1) needed the real `agent` verb
for role-identity onboarding (`agent init/list/show/edit/disable`) and couldn't
claim it while the old harness-execution group still held it.

## What moved the goalpost

Nothing strategic shifted — this is the mechanical unblock Phase 0 always implied
but didn't do. The only real decision was whether a rename this central needed a
deprecation shim. Pre-1.0, with a small and mostly-internal user base, the answer
came out of a `synlynk decide --panel claude,agy,codex,grok --record` vote:
unanimous 4/4 for a clean break, no shim
(`project-docs/decisions/2026-08-16-synlynk-s-cli-has-a-naming-collision-syn.md`).

## What this PR shipped

- `synlynk agent add/configure/run/list` → `synlynk harness add/configure/run/list`
  — the CLI verb group, its `dest`, and its `help_parsers` key all moved; the
  underlying `cmd_agent_add/configure/run/list` Python function names were left
  alone, since only the CLI-facing surface needed to change.
- No deprecation shim. Running the old `synlynk agent add ...` now fails with
  argparse's standard "invalid choice" error rather than silently routing to the
  new behavior — deliberate, per the spec's §4 breaking-change stance.
- Explicitly left untouched: `dispatch <agent>`, `open <agent>`, `probe --agent`,
  `quota --agent`, `configure agent` — all of these use "agent" in senses that
  don't collide (dispatch target, not the harness-execution verb group), so
  renaming them would have been scope creep against the actual naming collision.
- Freed the `agent` top-level verb for PR #1003 (Agent-roles-charters Phase 1),
  which landed immediately after and claimed it for `synlynk agent
  init/list/show/edit/disable`.

## What this achieved

Closes the last blocker on Task #97's CLI surface. The terminology rollout is now
consistent end-to-end: the glossary defines the split, the docs use the right
words, and the CLI's own verb namespace no longer contradicts either.

## The goal at the end of this PR

`agent` is free. Phase 1 of Agent-roles-charters (storage + CLI onboarding +
dispatch integration) ships next, in the same session, using the verb this PR
unblocked.
