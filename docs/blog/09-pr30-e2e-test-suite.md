---
title: "PR #30 — The E2E Safety Net"
date: 2026-06-10
series: "Building the OS for Multi-Agent Development"
post: 9
pr: "#30"
merged: open
tags: posts
excerpt: "17 black-box CLI tests, zero subprocess mocks. The E2E suite treats synlynk as a user would: real subprocess invocations, real tmp dirs, real exit codes. A safety net that grows with every feature."
---

# PR #30 — The E2E Safety Net

**PR:** test: add E2E test suite (17 scenarios, black-box CLI testing)  
**Branch:** `feat/e2e-test-suite`  
**Depends on:** PR #29 (v0.3.1 — sentinel + observability hardening)  
**Status:** open

---

## The Broader Goal at the End of PR #29

v0.3.1 added nine observability features — token scraping, zombie detection, stall detection, quota-exhausted patterns, burn rate, pre-exec gate, and the `synlynk sentinel` CLI. All tested at the unit level: 123 function-level tests that run against a monkeypatched `project_dir` fixture.

The gap: not a single test invoked `python3 bin/synlynk.py` as a subprocess. A broken argparse flag, a wrong exit code, a `finally` block that swallows the wrapped command's return code — none of these would fail the unit suite.

---

## What This PR Shipped

### `tests/test_e2e.py` — 17 Black-Box Scenarios

Every test in this file uses `subprocess.run`. No imports from `synlynk`. No monkeypatching. The CLI is treated exactly as a user would invoke it from a terminal.

**The `Cli` helper class** is the extensibility primitive:

```python
class Cli:
    def run(self, *args, timeout=30) -> subprocess.CompletedProcess
    def write_file(self, rel_path, content)
    def read_file(self, rel_path) -> str
    sentinel_file: Path  # .synlynk/sentinel.md
```

The `cli` fixture returns a `Cli` instance in a fresh initialized project. The `uninit_cli` fixture returns one in a bare directory. New tests drop into the right fixture and call `cli.run(...)`. Adding a new scenario is ~5 lines.

**Scenarios by feature:**

| Feature | Tests | What's verified |
|---|---|---|
| CLI basics | 4 | `--version`, `--help`, `init`, `init --force` |
| exec | 4 | exit 0, exit code propagation, exit 127, telemetry written |
| sentinel | 5 | list empty, list after write, clear all, clear by severity, clear by code |
| pre-exec gate | 2 | CRITICAL blocks exec, `--force` bypasses |
| status | 2 | exits 0, shows expected sections |

**One real bug found:** `test_status_output_contains_expected_sections` revealed that `cmd_status()` uses uppercase section headers (`BUDGET`, `SENTINEL`, `WATCHER`, `ACTIVE TASKS`) — not title-case as documented in comments. The test was written against the actual output, not the assumption.

**`pytest.ini`** registers the `e2e` mark so the suite can be run in isolation:
```bash
pytest tests/test_e2e.py -v          # run E2E only
pytest tests/test_e2e.py -m e2e -v   # same, using mark
pytest tests/                         # run everything (unit + E2E)
```

### What's Deliberately Not Tested

```python
# ---------------------------------------------------------------------------
# TODO: watch lifecycle tests
#
# synlynk watch start / stop are not covered here because daemon forking
# is unreliable in subprocess-based test environments (PID files, signal
# handling, timing). Add these as a dedicated test module that is opt-in
# and marked @pytest.mark.slow when the daemon API stabilises.
# ---------------------------------------------------------------------------
```

The watch daemon forks a background process and writes a PID file. In a test environment with many parallel tmp dirs and process groups, timing-based daemon assertions are flaky by design. Marked as a known gap with a clear extension point.

### How to Extend It

Every new feature gets a section:

```python
# --- Feature: my_new_command ---

def test_my_new_command_happy_path(cli):
    result = cli.run("my-command", "--flag", "value")
    assert result.returncode == 0
    assert "expected output" in result.stdout

def test_my_new_command_error_case(cli):
    result = cli.run("my-command", "--bad-flag")
    assert result.returncode != 0
```

The fixture handles `init`, tmp dir creation, and cleanup. The test writer provides the scenario.

---

## What This Achieved on the Path to Autonomy

Unit tests verify logic. E2E tests verify behavior. An OS that an autonomous agent runs on behalf of a user must be verifiable at both levels — the unit suite guards function contracts; the E2E suite guards the user-facing contract.

With both suites in place, the release checklist for v0.3.2 and beyond is:

```bash
pytest tests/test_synlynk.py   # unit: function contracts
pytest tests/test_e2e.py       # E2E: CLI behavior
```

The E2E suite will grow with every PR. By v0.4.0, it will cover `synlynk run`, `synlynk start`, and the Trio pipeline. By v0.5.0, it will cover state.db operations. The `Cli` helper is the single stable interface that all future tests build on.

---

## The New Goalpost

> v0.4.0 — Conventions + Trio Bootstrap — is the next release. All design decisions locked. The E2E suite now has the scaffold to cover `synlynk run`, shared `.rules/` conventions, and the Architect → Build → Verify pipeline as soon as they ship.
