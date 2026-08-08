# Safe Caller Construction Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish documentation showing callers of `synlynk dispatch` how to construct task text safely — as structured Python data via `dispatch_agent()`, or via argument-list `subprocess` calls for shell/CI callers — and defer the still-hypothetical structured `--task-file` CLI interface to a tracked follow-up issue.

**Architecture:** Docs-only. One new hand-written reference file (`docs/reference/safe-caller-construction.md`), one line added to the auto-generated `docs/reference/commands.md`'s generator (`scripts/generate_command_docs.py`) so the new file is discoverable and the link survives regeneration, and one new GitHub issue tracking the deferred `--task-file` interface. No production code in `synlynk/` changes.

**Tech Stack:** Python 3 stdlib (`subprocess`, `shlex`), Markdown, `gh` CLI for issue filing.

---

### Task 1: Write `docs/reference/safe-caller-construction.md`

**Files:**
- Create: `docs/reference/safe-caller-construction.md`

- [ ] **Step 1: Confirm the reference example is accurate against current code**

Run:
```bash
sed -n '1635,1651p' synlynk/dispatch.py
```
Expected: shows `def dispatch_agent(agent: str, task: str, story_id: str = None, ...)` — confirms `task` is the second positional parameter and a plain `str`. Also confirm the real internal caller reference:
```bash
sed -n '120,128p' synlynk/capability_sweep.py
```
Expected: shows a call of the form `return dispatch_agent(agent, task, **dispatch_kwargs)` around line 127.

- [ ] **Step 2: Write the file**

```markdown
# Safe Caller Construction

`synlynk dispatch` sends free-text task instructions to an AI agent. How you build that task
text matters: constructing it as structured data avoids an entire class of bugs that string
interpolation into a shell command is exposed to.

## Python callers (recommended)

If your automation runs in Python, call `dispatch_agent()` directly instead of shelling out to
the `synlynk` CLI:

```python
from synlynk.dispatch import dispatch_agent

result = dispatch_agent(
    agent="codex",
    task=task_text,          # plain str — no shell involved
    story_id=None,
    context_mode="full",
)
```

`task_text` can come from anywhere — a template, user input, another API response — with no
escaping step, because it never passes through a shell. This is the same pattern synlynk's own
internal callers use; see `synlynk/capability_sweep.py`'s
`dispatch_agent(agent, task, **dispatch_kwargs)` call site for a live example that will stay in
sync with the real signature (rather than a duplicated snippet here that can drift).

## Shell / CLI / automation callers

If you can't call Python directly — a CI step, a shell script, another language's automation —
you still shell out to the `synlynk` CLI. Build the command as an argument list, not a string.

**Don't** interpolate task text into a shell command string:

```python
# BROKEN: task_text containing a `"`, `` ` ``, `$(...)`, or a newline breaks out of the
# intended argument boundary.
os.system(f'synlynk dispatch codex --task "{task_text}"')
```

**Do** pass an argument list to `subprocess.run` (the default `shell=False` means the OS never
re-parses the string, so no quoting/escaping is needed at all):

```python
subprocess.run(["synlynk", "dispatch", "codex", "--task", task_text])
```

If you're stuck building a literal shell string anyway (e.g. inside a Makefile or a `.sh`
script where a Python list isn't available), quote the value properly — never hand-roll
escaping:

```python
import shlex
quoted = shlex.quote(task_text)  # or the shell's own `printf %q` equivalent in bash
```

## Verify before you dispatch for real

Any automation call site should run a `--dry-run` pass first (see `synlynk dispatch --help`) to
confirm the task text resolved the way you expect, before it creates a real job:

```bash
synlynk dispatch codex --task "$TASK_TEXT" --dry-run
```

This prints the task digest and preview without creating a job, worktree, or cost entry. The
same `task_sha256`/`task_preview` fields are also visible later via `synlynk jobs --summary
<job-id>`, so you can confirm after the fact exactly what text a given job actually received.

## Known gap: no structured CLI interface yet

Today's safe paths above cover Python callers (direct function call) and shell callers
(argument-list `subprocess`). There is no `--task-file <path>.json` or stdin-JSON interface for
non-Python CLI callers — if you need one, none exists yet. This is expected to become necessary
once Team/Enterprise editions introduce external, non-Python callers (webhooks, API gateway,
other services) invoking dispatch programmatically. It's tracked as a deferred follow-up, not
scheduled: see the "Structured task-file/stdin interface for `synlynk dispatch` (Team/Enterprise
prerequisite)" issue.
```

- [ ] **Step 3: Commit**

```bash
git add docs/reference/safe-caller-construction.md
git commit -m "docs: safe caller construction guide (#769 sub-project 3/3)"
```

---

### Task 2: Link the new doc from the generated command reference

**Files:**
- Modify: `scripts/generate_command_docs.py:26-29` (the `render_reference_doc()` header lines)

- [ ] **Step 1: Confirm current header text**

Run:
```bash
sed -n '26,30p' scripts/generate_command_docs.py
```
Expected output:
```python
    lines = ["# Command Reference", "",
             "Generated from `synlynk/taxonomy.py`. Do not edit by hand — run "
             "`python3 scripts/generate_command_docs.py`.", ""]
```

- [ ] **Step 2: Add the link line**

Change:
```python
    lines = ["# Command Reference", "",
             "Generated from `synlynk/taxonomy.py`. Do not edit by hand — run "
             "`python3 scripts/generate_command_docs.py`.", ""]
```
to:
```python
    lines = ["# Command Reference", "",
             "Generated from `synlynk/taxonomy.py`. Do not edit by hand — run "
             "`python3 scripts/generate_command_docs.py`.", "",
             "See [safe-caller-construction.md](safe-caller-construction.md) for guidance on "
             "building dispatch task text programmatically.", ""]
```

This is an edit to the generator's Python source (a legitimate code change), not a hand-edit of
the generated Markdown output — the link survives every future regeneration.

- [ ] **Step 3: Regenerate the committed docs**

Run:
```bash
python3 scripts/generate_command_docs.py
```
Expected output: `Regenerated docs/reference/commands.md and README.md command section.`

- [ ] **Step 4: Verify the diff is exactly the new link line, nothing else**

Run:
```bash
git diff docs/reference/commands.md
```
Expected: only the two new lines (the link paragraph) appear in the diff, inserted after the
"Generated from..." line and before "## Orientation gateway". `README.md` should show no diff at
all — `render_readme_section()` was not touched.

- [ ] **Step 5: Run the docs-sync tests**

Run:
```bash
python3 -m pytest tests/test_docs_sync.py -v
```
Expected: `2 passed` — `test_generated_reference_doc_matches_taxonomy` and
`test_generated_readme_section_matches_taxonomy` both pass, confirming the regenerated file
matches what the generator now produces.

- [ ] **Step 6: Commit**

```bash
git add scripts/generate_command_docs.py docs/reference/commands.md
git commit -m "docs: link safe-caller-construction.md from command reference"
```

---

### Task 3: File the deferred `--task-file` interface issue

**Files:** none (GitHub issue only, no repo files touched)

- [ ] **Step 1: File the issue**

Run:
```bash
gh issue create --repo nikhilsoman/synlynk \
  --title "Structured task-file/stdin interface for synlynk dispatch (Team/Enterprise prerequisite)" \
  --body "$(cat <<'EOF'
## Context

Issue #720's requirement 6 ("document safe caller construction") shipped as
docs/reference/safe-caller-construction.md (see #769). That doc covers today's real callers:
Python automation (dispatch_agent() called directly, already structured data) and shell/CI
callers (argument-list subprocess calls, no string interpolation).

## The gap

There is no structured `--task-file <path>.json` or stdin-JSON interface for non-Python CLI
callers. `synlynk dispatch --task "<text>"` remains a shell-string argument for any caller that
isn't Python.

## Why this isn't built yet

No caller needs it today — synlynk's own internal callers are all Python
(dispatch_agent() direct calls) or a human typing the CLI. Building a new wire format
speculatively would violate YAGNI.

## When this becomes real

Team/Enterprise editions (targeted ~September 2026) are expected to introduce external,
non-Python, non-human callers — webhooks, an API gateway, other services — invoking dispatch
programmatically. That's the trigger condition for revisiting this.

## Scope (not yet designed)

Not scoped to a specific implementation. When picked up, should go through the normal
brainstorm → spec → plan cycle, informed by whatever the actual Team/Enterprise caller shape
turns out to be (an issue filed speculatively now would likely guess wrong).

Not scheduled. Filed to keep this discoverable via issue search/roadmap rather than relying on
someone re-reading docs/reference/safe-caller-construction.md in September.
EOF
)"
```
Expected: prints the new issue URL, e.g.
`https://github.com/nikhilsoman/synlynk/issues/<N>`.

- [ ] **Step 2: Backfill the issue link into the safe-caller-construction.md "Known gap" section**

Edit `docs/reference/safe-caller-construction.md`'s final paragraph (written with a placeholder
description, no link, in Task 1) to add the real issue link. Replace:

```markdown
It's tracked as a deferred follow-up, not
scheduled: see the "Structured task-file/stdin interface for `synlynk dispatch` (Team/Enterprise
prerequisite)" issue.
```

with (substituting the real issue number `<N>` from Step 1's output):

```markdown
It's tracked as a deferred follow-up, not
scheduled: see [issue #<N>](https://github.com/nikhilsoman/synlynk/issues/<N>).
```

- [ ] **Step 3: Commit**

```bash
git add docs/reference/safe-caller-construction.md
git commit -m "docs: link deferred task-file interface issue in safe-caller-construction.md"
```

---

### Task 4: Full regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run:
```bash
python3 -m pytest -q
```
Expected: same pass/skip count as this worktree's clean baseline (1730 passed, 2 skipped, as
measured when the worktree was created for this plan) — no new failures, since no production
code changed.

- [ ] **Step 2: Confirm no unintended files changed**

Run:
```bash
git status --short
git diff --stat main
```
Expected `git status --short`: empty (everything committed across Tasks 1-3). Expected
`git diff --stat main`: only these four files touched —
`docs/reference/safe-caller-construction.md` (new),
`scripts/generate_command_docs.py`,
`docs/reference/commands.md`,
`docs/superpowers/specs/2026-08-08-safe-caller-construction-design.md` (from the brainstorming
step, already committed before this plan).
