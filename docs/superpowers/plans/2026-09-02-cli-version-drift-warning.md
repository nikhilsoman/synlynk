# Implementation Plan: Warn on Stale pipx-Installed CLI (#1188)

1. Add a repository-root detector in `synlynk/cli.py` that recognizes the
   synlynk project from `pyproject.toml` and `VERSION`.
2. Add a best-effort version-drift warning helper and invoke it after parsing,
   before command dispatch, without changing exit codes or command behavior.
3. Add TDD coverage in `tests/test_agent_cli.py` for stale and current versions.
4. Record the change in the blog index, project memory, and Codex devlog.
5. Verify the issue-specific pytest selection and the touched CLI test module.
