---
title: "Fixing #1862 — The Wizard's Clear Screen Was Spawning a Pipe-Inheriting Child"
date: 2026-09-30
series: "Building the OS for Multi-Agent Development"
post: 234
pr: "1875"
issue: "1862"
status: published
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, bugfix, wizard]
type: story
---

## The Broader Goal at the End of the Previous PR

R12 (post 233, PR #1868) had just closed out the `__init__.py` god-module decomposition and,
with it, a review-remediation wave that surfaced a cluster of independent defects across the
wizard and CLI paths — #1862, #1864, and #1865. An earlier combined investigation (dispatched
before this PR) had already refuted a suspected shared root cause across the three and
confirmed #1862 and #1865 as real, separate bugs, posting findings as comments on each issue.
#1864 remained genuinely unconfirmed. The goalpost at that point was simply: dispatch real
fixes for the two confirmed issues, and dig deeper into the one that wasn't.

## Strategic Shifts in This PR

None — this PR stayed exactly inside #1862's confirmed scope: `_wiz_clear()`.

## What #1862 Was

`synlynk/wizard.py::_wiz_clear()` cleared the terminal screen with:

```python
def _wiz_clear() -> None:
    """Clear the terminal screen."""
    os.system("clear" if os.name != "nt" else "cls")
```

`os.system()` spawns a child process through the shell, and that child inherits the parent's
file descriptors — including stdin, stdout, and stderr. When the wizard runs under a captured,
non-TTY subprocess (exactly the shape of `test_synlynk_init_wizard_dry_run_subprocess`, which
drives `synlynk init --wizard` via `subprocess.run(..., capture_output=True)`), that inherited
pipe can hang: `clear`/`cls` becomes a second process sharing the same pipe-backed stdin/stdout
as the wizard itself, and the parent's `capture_output` read can stall waiting on a descriptor
the child hasn't released yet.

## What This PR Shipped

The fix replaces the shell-spawning call with a direct ANSI escape sequence, gated on an
actual TTY:

```python
def _wiz_clear() -> None:
    """Clear the terminal screen without spawning a pipe-inheriting child."""
    if os.name == "nt":
        os.system("cls")
    elif sys.stdout.isatty():
        print("\033[H\033[2J", end="", flush=True)
```

On POSIX, `\033[H\033[2J` (cursor-home + erase-screen) is the same effect `clear` produces,
written directly to `stdout` — no subprocess, no inherited descriptors, nothing to hang on.
The `isatty()` guard means a captured/piped run does nothing at all instead of writing control
codes into captured output. Windows keeps `os.system("cls")`, since `cls` is a shell builtin
there with no POSIX-style escape-sequence equivalent worth chasing for this fix's scope.

The regression test (`test_synlynk_init_wizard_dry_run_subprocess`) was tightened from an
`or 'Traceback' not in result.stderr` fallback to a strict `returncode == 0` assertion — the
looser assertion had been masking exactly this class of hang/failure.

## Review Cycle

First review came back `CHANGES_REQUESTED`: the updated subprocess test wasn't CI-runnable,
because `python -m synlynk` from a bare `tmp_path` working directory can't find the `synlynk`
package unless the repo root is explicitly on `PYTHONPATH` — something the local dev checkout
had implicitly, masking the gap. Follow-up fix propagated the repo root into the child's
`PYTHONPATH` explicitly. Second review: `APPROVED`. Squash-merged.

## What's Next

The new goalpost: apply the same discipline to #1865 (a related but independently-confirmed
subprocess-state bug in the same test), and push the #1864 investigation further with an
actual reproduction attempt rather than another static audit — both covered in the next two
posts in this wave.

Refs #1862.
