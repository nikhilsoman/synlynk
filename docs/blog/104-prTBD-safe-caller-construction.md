---
title: "Safe Caller Construction: Documenting the Path That Already Existed"
date: 2026-08-08
series: "Building the OS for Multi-Agent Development"
post: 104
pr: "TBD"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

PR #778 closed the second of three sub-projects under issue #769 (itself born from issue #720's
six-item hardening checklist): scope enforcement, which turned `--scope-paths` from a request in
prose into a hard boundary a job either respects or gets quarantined for violating (`SCOPE_VIOLATION`).
That left one sub-project on the board — safe-caller-construction docs, the sixth and final #720
requirement: publish guidance on constructing `synlynk dispatch` task text safely, since
`--task "<text>"` is a shell command and any caller building it by string-interpolating dynamic
content is exposed to the same class of bug as SQL string concatenation.

## Strategic Shifts in This PR

One real one, surfaced by the user before design work started rather than during it. The obvious
reading of #720's requirement 6 was "publish an SDK/API example that accepts task text as
structured data" — which raises the question of whether that means *building* a new structured
interface (a `--task-file`/stdin JSON path for non-Python CLI callers) or *documenting* the
structured path that already exists (`dispatch_agent()` in `synlynk/dispatch.py`, which already
takes `task` as a plain `str` and never touches a shell). The user's framing settled it: no caller
needs a structured CLI interface today — synlynk's own internal callers are all Python or a human
typing the CLI — so building one now would be speculative. But Team/Enterprise editions
(targeted ~September 2026) are expected to introduce external, non-Python, non-human callers
(webhooks, an API gateway, other services), and *that's* when a structured interface stops being
speculative. The design commits to "Option 1 now, design toward Option 2, build Option 2 when
Team/Enterprise starts" — document today's real safe path, and file a tracked, unscheduled issue
for the future one instead of building it blind.

A second, smaller correction happened during design review, before it reached a plan: my first
draft assumed `docs/reference/commands.md` was hand-editable. Checking
`scripts/generate_command_docs.py` before finalizing the design showed `render_reference_doc()`
does a full `Path(...).write_text(...)` overwrite with no preserved-section markers — a direct
edit would be silently wiped on the next regeneration. The design moved the link into the
generator's own source instead, so it survives every future run.

## What This PR Shipped

One new hand-written file, `docs/reference/safe-caller-construction.md`, with four sections:

1. **Python callers (recommended).** Call `dispatch_agent()` directly — `task` is already a plain
   `str`, no shell involved, no escaping step needed regardless of where the text came from. Points
   to the real internal caller at `synlynk/capability_sweep.py:127`
   (`dispatch_agent(agent, task, **dispatch_kwargs)`) as a live, grep-able example rather than a
   duplicated snippet that can drift out of sync with the real signature.
2. **Shell/CLI/automation callers.** A do/don't pair: **don't**
   `os.system(f'synlynk dispatch codex --task "{task_text}"')` (breaks the moment `task_text`
   contains a `"`, backtick, `$(...)`, or newline); **do**
   `subprocess.run(["synlynk", "dispatch", "codex", "--task", task_text])` (argument list, default
   `shell=False`, no re-parsing, no quoting needed at all). One line for callers stuck building a
   literal shell string anyway (a Makefile, a `.sh` script): `shlex.quote()`, never hand-rolled
   escaping.
3. **Verify before you dispatch for real.** Points at the existing `--dry-run` flag (shipped in
   PR #759) and `jobs --summary`'s `task_sha256`/`task_preview` fields as the way to confirm what a
   dynamically constructed task string actually resolved to, both before and after a real dispatch.
4. **Known gap.** One paragraph, explicitly framed as deferred rather than a current limitation:
   no `--task-file`/stdin structured interface exists for non-Python CLI callers, linking
   [issue #782](https://github.com/nikhilsoman/synlynk/issues/782) — filed with the trigger
   condition (external, non-Python, non-human callers appearing) spelled out so it isn't
   rediscovered from scratch in September.

The new file is discoverable via a one-line addition inside `render_reference_doc()`'s header —
"See [safe-caller-construction.md](safe-caller-construction.md) for guidance on building dispatch
task text programmatically." — added to the *generator source*, not the generated output, then
`docs/reference/commands.md` regenerated so the link is live immediately.
`tests/test_docs_sync.py` continues to assert the generated file matches the generator, unchanged.

No production code changed — `dispatch_agent()`, `cli.py`'s `dispatch` subcommand, and the
receipt/classifier/scope enforcement from the prior two #769 sub-projects were all already correct;
this sub-project only had to write down the path that already worked.

One real dispatch hiccup, not in the design: the implementer job (job-7135dcb4) reported done with
exit 0 and genuinely correct, fully-committed work — but that work existed only in the job's own
local nested worktree/branch, never pushed or merged anywhere. Caught by the standing "never trust
`synlynk jobs` status alone" discipline (`#202`): diffing the target branch against origin came up
empty, which sent me into the job's own worktree to inspect its `git log`/`git diff --stat`
directly. Resolved with a manual fast-forward merge of the job's branch rather than an expensive
re-dispatch, since the work itself checked out clean. A leftover nested `worktrees/job-7135dcb4/`
directory then caused `pytest -q` to double-collect the test suite from both copies (92 collection
errors) until it was removed per Worktree Hygiene Protocol, after which the full suite ran clean:
1730 passed, 2 skipped.

## Brainstorm Visuals Used

None — this design was entirely text/API-shape (a scoping question about strings vs. structured
data), no visual companion was used.

## What This Achieved on the Path to Autonomy

This closes issue #720's full six-item hardening checklist and, with it, issue #769's three-part
decomposition: the permission-denied classifier corroboration fix (#770/#771), scope enforcement
(#778), and now safe caller construction. The fleet's dispatch surface is now documented end to end
for both of its real caller shapes — Python-native (already safe, now written down) and shell/CI
(safe *if* built as an argument list, now shown explicitly as a do/don't). Nothing here adds new
enforcement code; it closes the gap between "a safe path exists" and "callers know to use it,"
which is exactly what #720 asked for.

## Strategic Note: The Goal at the End of This PR

#720 and #769 are both fully shipped as of this PR. The one open thread this sub-project
deliberately did not resolve — a structured `--task-file`/stdin interface for non-Python CLI
callers — is now a named, findable placeholder (#782) rather than an implicit gap, with its trigger
condition already written down: Team/Enterprise work starting in September, introducing the first
non-Python, non-human dispatch callers synlynk will actually have. Until then, the two safe paths
documented here are the complete answer.
