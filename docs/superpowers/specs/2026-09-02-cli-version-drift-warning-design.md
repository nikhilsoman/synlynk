# Design Spec: Warn on Stale pipx-Installed CLI (#1188)

- **Issue:** [#1188](https://github.com/nikhilsoman/synlynk/issues/1188)
- **Date:** 2026-09-02
- **Status:** APPROVED

## Context

When a user runs a pipx-installed `synlynk` binary from a synlynk checkout, the
binary can lag behind the checkout's `VERSION` file. That mismatch is confusing
because the command is executing older code while the working tree advertises a
newer package version.

## Decision

After argument parsing and before command dispatch, inspect the current directory
and its ancestors for a `pyproject.toml` whose project name is `synlynk` and a
`VERSION` file. Compare the running package's `VERSION` constant with that file
using numeric dotted-version tuples. If the installed version is older, emit a
single actionable warning to stderr recommending a forced pipx reinstall.

The check is best-effort: missing files, malformed versions, non-synlynk
projects, and equal or newer installed versions produce no warning and never
change the command's result. The warning does not require network access and
does not attempt to mutate the environment.

## Test Contract

Tests cover the stale warning text and pipx remediation command, plus the
no-warning current-version path. The targeted verification is:

```text
pytest tests/test_agent_cli.py -k 'cli_detect_and_warn_on_stale_pipxinstall' -v
```
