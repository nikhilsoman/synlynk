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
scheduled: see [issue #782](https://github.com/nikhilsoman/synlynk/issues/782).
