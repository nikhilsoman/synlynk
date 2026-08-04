# Local Agent Parity Config (A/B Test + Starter-Tier Guardrails) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the A/B test harness that will decide whether `Ornith-1.0-9B-4bit` or
`Qwen3.6-27B-4bit` gets pinned as the `local` agent's model, and ship Starter-tier
safety guardrails (no architect mode, no auto-lint/auto-test, capped repo-map) against
the currently-pinned model regardless of that outcome.

**Architecture:** A new standalone harness script (`scripts/local_agent_ab_test.py`,
following the existing `scripts/convert_roadmap_table.py` pattern) temporarily re-pins
`.agents/local.json` to a given model, runs one real dispatch through the existing
`synlynk dispatch local` CLI path, records wall-time/peak-RSS/git-diff-footprint, and
always restores the original config file. Separately, `synlynk/local_agent.py`'s
`_local_dispatch_model_flags()` gets three new hardcoded Starter-tier guardrail flags
appended unconditionally, since Starter is the only tier that exists today.

**Tech Stack:** Python 3 stdlib only (`argparse`, `json`, `subprocess`, `resource`,
`time`) — matches the rest of this project's no-dependency CLI philosophy.

**Scope boundary:** This plan covers Task Group A (the A/B harness) and Task Group B
(Starter-tier guardrails) only. Full-tier work (`--architect` mode, `auto-lint`/
`auto-test: true`, `editor_model_name`) is explicitly out of scope — per the spec, Full
ships later, gated on the N=10 track record. Do not add architect-mode flags anywhere
in this plan's tasks.

**Dependency note:** PR #690 (`fix/omlx-aider-edit-format`, pins `edit_format: "diff"`
for `Ornith-1.0-9B-4bit`) is open but not yet merged to `main` as of this plan's
creation. This plan's branch was cut from `main` before #690 merged, so
`.agents/local.json`'s pinned entry currently still shows `"edit_format": "whole"`.
Task Group B's Step 1 test is written against the *post-#690* expected state
(`"diff"`) since the resolved spec question says Starter ships now regardless of
sequencing — if #690 has not merged by the time Task Group B executes, rebase this
branch onto `main` after #690 merges, or merge #690 into this branch directly, before
starting Task Group B. Task Group A does not depend on #690 (it re-pins whatever model
it's testing to `"diff"` itself, overriding whatever the base config says).

---

## Task Group A: A/B Test Harness

### Task A1: Build the harness's pure config-transform logic

**Files:**
- Create: `scripts/local_agent_ab_test.py`
- Test: `tests/test_local_agent_ab_test.py`

- [ ] **Step 1: Write the failing test for `_build_temp_config`**

```python
import unittest

from scripts.local_agent_ab_test import _build_temp_config


class TestBuildTempConfig(unittest.TestCase):
    def setUp(self):
        self.base_config = {
            "name": "local",
            "endpoint": "http://127.0.0.1:8000",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
                {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
            ],
            "hardware_tier": "16gb-default",
        }

    def test_pins_requested_model_and_sets_diff_format(self):
        result = _build_temp_config(self.base_config, "qwen-coder")
        pinned = [m for m in result["models"] if m["pinned"]]
        self.assertEqual(len(pinned), 1)
        self.assertEqual(pinned[0]["id"], "qwen-coder")
        self.assertEqual(pinned[0]["edit_format"], "diff")

    def test_unpins_previously_pinned_model(self):
        result = _build_temp_config(self.base_config, "qwen-coder")
        ornith = next(m for m in result["models"] if m["id"] == "Ornith-1.0-9B-4bit")
        self.assertFalse(ornith["pinned"])

    def test_does_not_mutate_original_config(self):
        _build_temp_config(self.base_config, "qwen-coder")
        original_pinned = [m for m in self.base_config["models"] if m["pinned"]]
        self.assertEqual(original_pinned[0]["id"], "Ornith-1.0-9B-4bit")

    def test_raises_on_unknown_model_id(self):
        with self.assertRaises(ValueError):
            _build_temp_config(self.base_config, "does-not-exist")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.local_agent_ab_test'`

- [ ] **Step 3: Write the module with `_build_temp_config`**

Create `scripts/local_agent_ab_test.py` with this exact content (later steps append
more functions to this same file):

```python
#!/usr/bin/env python3
"""A/B comparison harness for local-agent models.

Temporarily re-pins .agents/local.json to the model under test, runs one dispatch
through the real `synlynk dispatch local` CLI path, records wall-clock time, peak
child RSS, and git diff footprint, then always restores the original config. This
script does not decide a winner — it only produces data rows for a human/PM to read,
per docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md.
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import resource
import subprocess
import sys
import time

_CONFIG_PATH = os.path.join(".agents", "local.json")
_RESULTS_PATH = os.path.join(
    "project-docs", "decisions", "2026-08-03-local-agent-ab-test-results.jsonl"
)


def _build_temp_config(base_config: dict, model_id: str) -> dict:
    """Returns a deep copy of base_config with only model_id pinned, edit_format=diff."""
    config = copy.deepcopy(base_config)
    found = False
    for model in config["models"]:
        if model["id"] == model_id:
            model["pinned"] = True
            model["edit_format"] = "diff"
            found = True
        else:
            model["pinned"] = False
    if not found:
        raise ValueError(f"model_id {model_id!r} not present in roster")
    return config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add scripts/local_agent_ab_test.py tests/test_local_agent_ab_test.py
git commit -m "feat(local-agent): A/B harness config-transform logic"
```

### Task A2: Add config read/write helpers and result-row builder

**Files:**
- Modify: `scripts/local_agent_ab_test.py`
- Test: `tests/test_local_agent_ab_test.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_local_agent_ab_test.py`:

```python
import tempfile

from scripts.local_agent_ab_test import _write_config, _load_config, _build_result_row


class TestConfigReadWrite(unittest.TestCase):
    def test_write_then_load_roundtrips(self):
        config = {"name": "local", "models": [{"id": "x", "pinned": True}]}
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            _write_config(config, path)
            loaded = _load_config(path)
            self.assertEqual(loaded, config)


class TestBuildResultRow(unittest.TestCase):
    def test_builds_expected_schema(self):
        row = _build_result_row(
            model_id="qwen-coder",
            label="quality-docstring",
            prompt="add a docstring to foo()",
            wall_time_s=12.345,
            peak_rss_kb=204800,
            exit_code=0,
            diff_stat=" 1 file changed, 3 insertions(+)",
            stdout="...long output..." + "x" * 1000,
        )
        self.assertEqual(row["model_id"], "qwen-coder")
        self.assertEqual(row["label"], "quality-docstring")
        self.assertEqual(row["wall_time_s"], 12.35)
        self.assertEqual(row["peak_rss_kb"], 204800)
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["git_diff_stat"], " 1 file changed, 3 insertions(+)")
        self.assertEqual(len(row["stdout_tail"]), 500)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: FAIL with `ImportError: cannot import name '_write_config'`

- [ ] **Step 3: Add the helpers**

Append to `scripts/local_agent_ab_test.py` (after `_build_temp_config`):

```python
def _load_config(path: str = _CONFIG_PATH) -> dict:
    with open(path) as f:
        return json.load(f)


def _write_config(config: dict, path: str = _CONFIG_PATH) -> None:
    with open(path, "w") as f:
        json.dump(config, f, indent=2)
        f.write("\n")


def _git_diff_stat() -> str:
    result = subprocess.run(
        ["git", "diff", "--stat"], capture_output=True, text=True, check=False
    )
    return result.stdout.strip()


def _build_result_row(model_id, label, prompt, wall_time_s, peak_rss_kb,
                       exit_code, diff_stat, stdout):
    return {
        "model_id": model_id,
        "label": label,
        "prompt": prompt,
        "wall_time_s": round(wall_time_s, 2),
        "peak_rss_kb": peak_rss_kb,
        "exit_code": exit_code,
        "git_diff_stat": diff_stat,
        "stdout_tail": stdout[-500:],
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: PASS (7 tests total)

- [ ] **Step 5: Commit**

```bash
git add scripts/local_agent_ab_test.py tests/test_local_agent_ab_test.py
git commit -m "feat(local-agent): A/B harness config I/O and result-row schema"
```

### Task A3: Add `run_ab_case` orchestration with injectable dispatch runner

**Files:**
- Modify: `scripts/local_agent_ab_test.py`
- Test: `tests/test_local_agent_ab_test.py`

**Why an injectable runner:** the real dispatch runner shells out to
`python3 -m synlynk dispatch local`, which requires a live oMLX server reachable at
`127.0.0.1:8000` (`AGENT_CAPABILITY_BASELINES["local"]["network_deps"]`). That is not
available in a CI sandbox or a Codex `workspace-write` sandbox. `run_ab_case` accepts a
`dispatch_runner` callable so its orchestration logic (backup, re-pin, restore,
timing, result assembly) is fully unit-testable without a real model or network call.

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_local_agent_ab_test.py`:

```python
from unittest.mock import patch

from scripts.local_agent_ab_test import run_ab_case


class _FakeCompletedProcess:
    def __init__(self, returncode=0, stdout="ok"):
        self.returncode = returncode
        self.stdout = stdout


class TestRunAbCase(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmpdir.cleanup)
        self.config_path = os.path.join(self.tmpdir.name, "local.json")
        self.original_config = {
            "name": "local",
            "endpoint": "http://127.0.0.1:8000",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
            ],
            "hardware_tier": "16gb-default",
        }
        with open(self.config_path, "w") as f:
            json.dump(self.original_config, f)

    def test_restores_original_config_after_success(self):
        fake_runner = lambda prompt: _FakeCompletedProcess()
        with patch("scripts.local_agent_ab_test._CONFIG_PATH", self.config_path):
            with patch("scripts.local_agent_ab_test._git_diff_stat", return_value=""):
                run_ab_case("qwen-coder", "quality-docstring", "add a docstring",
                            dispatch_runner=fake_runner)
        with open(self.config_path) as f:
            restored = json.load(f)
        self.assertEqual(restored, self.original_config)

    def test_restores_original_config_after_dispatch_raises(self):
        def failing_runner(prompt):
            raise RuntimeError("simulated dispatch failure")

        with patch("scripts.local_agent_ab_test._CONFIG_PATH", self.config_path):
            with self.assertRaises(RuntimeError):
                run_ab_case("qwen-coder", "quality-docstring", "add a docstring",
                            dispatch_runner=failing_runner)
        with open(self.config_path) as f:
            restored = json.load(f)
        self.assertEqual(restored, self.original_config)

    def test_returns_result_row_with_requested_model(self):
        fake_runner = lambda prompt: _FakeCompletedProcess(returncode=0, stdout="done")
        with patch("scripts.local_agent_ab_test._CONFIG_PATH", self.config_path):
            with patch("scripts.local_agent_ab_test._git_diff_stat", return_value="clean"):
                row = run_ab_case("qwen-coder", "quality-docstring", "add a docstring",
                                   dispatch_runner=fake_runner)
        self.assertEqual(row["model_id"], "qwen-coder")
        self.assertEqual(row["label"], "quality-docstring")
        self.assertEqual(row["exit_code"], 0)
        self.assertEqual(row["git_diff_stat"], "clean")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'run_ab_case'`

- [ ] **Step 3: Add `run_ab_case`**

Append to `scripts/local_agent_ab_test.py`:

```python
def _default_dispatch_runner(prompt: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["python3", "-m", "synlynk", "dispatch", "local",
         "--task", prompt, "--force-agent"],
        capture_output=True, text=True, check=False,
    )


def run_ab_case(model_id: str, label: str, prompt: str, dispatch_runner=None) -> dict:
    """Re-pins model_id, runs one dispatch, restores config, returns a result row.

    Always restores .agents/local.json, even if the dispatch raises.
    """
    dispatch_runner = dispatch_runner or _default_dispatch_runner
    with open(_CONFIG_PATH) as f:
        original_text = f.read()
    original_config = json.loads(original_text)
    try:
        temp_config = _build_temp_config(original_config, model_id)
        _write_config(temp_config, _CONFIG_PATH)
        rss_before = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        start = time.monotonic()
        completed = dispatch_runner(prompt)
        wall_time_s = time.monotonic() - start
        rss_after = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        peak_rss_kb = max(rss_after - rss_before, 0)
        diff_stat = _git_diff_stat()
        return _build_result_row(
            model_id, label, prompt, wall_time_s, peak_rss_kb,
            completed.returncode, diff_stat, completed.stdout,
        )
    finally:
        with open(_CONFIG_PATH, "w") as f:
            f.write(original_text)
```

**Note on `patch("scripts.local_agent_ab_test._CONFIG_PATH", ...)`:** `run_ab_case`
must read `_CONFIG_PATH` as a module attribute at call time (not capture it in a
default argument) for this patch to take effect — the code above already does this
correctly by referencing the bare name inside the function body.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: PASS (10 tests total)

- [ ] **Step 5: Commit**

```bash
git add scripts/local_agent_ab_test.py tests/test_local_agent_ab_test.py
git commit -m "feat(local-agent): A/B harness run_ab_case orchestration"
```

### Task A4: Add `append_result` and CLI entrypoint

**Files:**
- Modify: `scripts/local_agent_ab_test.py`
- Test: `tests/test_local_agent_ab_test.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_local_agent_ab_test.py`:

```python
from scripts.local_agent_ab_test import append_result


class TestAppendResult(unittest.TestCase):
    def test_appends_jsonl_line_and_creates_parent_dir(self):
        with tempfile.TemporaryDirectory() as d:
            results_path = os.path.join(d, "nested", "results.jsonl")
            append_result({"model_id": "qwen-coder", "exit_code": 0}, results_path)
            append_result({"model_id": "Ornith-1.0-9B-4bit", "exit_code": 0}, results_path)
            with open(results_path) as f:
                lines = [json.loads(line) for line in f]
            self.assertEqual(len(lines), 2)
            self.assertEqual(lines[0]["model_id"], "qwen-coder")
            self.assertEqual(lines[1]["model_id"], "Ornith-1.0-9B-4bit")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: FAIL with `ImportError: cannot import name 'append_result'`

- [ ] **Step 3: Add `append_result` and `main`**

Append to `scripts/local_agent_ab_test.py`:

```python
def append_result(row: dict, results_path: str = _RESULTS_PATH) -> None:
    parent = os.path.dirname(results_path)
    if parent:
        os.makedirs(parent, exist_ok=True)
    with open(results_path, "a") as f:
        f.write(json.dumps(row) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="Run one A/B comparison dispatch for a local-agent model."
    )
    parser.add_argument("--model-id", required=True,
                         help="Roster id from .agents/local.json, e.g. qwen-coder")
    parser.add_argument("--label", required=True,
                         help="quality-<name>, safety-<name>, or cost-<name>")
    parser.add_argument("--prompt", required=True)
    args = parser.parse_args(argv)
    row = run_ab_case(args.model_id, args.label, args.prompt)
    append_result(row)
    print(json.dumps(row, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_local_agent_ab_test.py -v`
Expected: PASS (11 tests total)

- [ ] **Step 5: Commit**

```bash
git add scripts/local_agent_ab_test.py tests/test_local_agent_ab_test.py
git commit -m "feat(local-agent): A/B harness CLI entrypoint"
```

---

## Task Group B: Starter-Tier Guardrails

### Task B1: Add guardrail flags to `_local_dispatch_model_flags()`

**Files:**
- Modify: `synlynk/local_agent.py:64-80` (the `_local_dispatch_model_flags` function)
- Test: `tests/test_local_agent.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_local_agent.py` (inside the file, as a new `TestCase` class —
match the existing style already in that file):

```python
class TestLocalDispatchStarterTierGuardrails(unittest.TestCase):
    def test_includes_no_auto_lint(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertIn("--no-auto-lint", flags)

    def test_includes_no_auto_test(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertIn("--no-auto-test", flags)

    def test_caps_map_tokens_to_zero(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        map_tokens_index = flags.index("--map-tokens")
        self.assertEqual(flags[map_tokens_index + 1], "0")

    def test_never_includes_architect_flag(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "endpoint": "http://127.0.0.1:8000",
                    "models": [
                        {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
                    ],
                    "hardware_tier": "16gb-default",
                }, f)
            flags = local_agent._local_dispatch_model_flags(path)
        self.assertNotIn("--architect", flags)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_local_agent.py -k StarterTierGuardrails -v`
Expected: FAIL — `test_includes_no_auto_lint` and `test_includes_no_auto_test` and
`test_caps_map_tokens_to_zero` fail (flags absent); `test_never_includes_architect_flag`
already passes (no code path adds `--architect` yet) but keep it as a regression guard.

- [ ] **Step 3: Add the guardrail flags**

In `synlynk/local_agent.py`, modify `_local_dispatch_model_flags` (replace the
existing function body from the summary's line 64-80):

```python
_STARTER_TIER_GUARDRAIL_FLAGS = [
    "--no-auto-lint",
    "--no-auto-test",
    "--map-tokens", "0",
]


def _local_dispatch_model_flags(config_path: str = None) -> list:
    """Builds aider model flags from .agents/local.json.

    Always appends Starter-tier safety guardrails (no autonomous lint/test
    execution, no repo-map context) — see
    docs/superpowers/specs/2026-08-03-local-agent-parity-config-design.md.
    Full-tier flags (--architect, auto-lint/auto-test: true) are a future,
    separately-gated change and must not be added here.
    """
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError:
        return []
    endpoint = config["endpoint"]
    model_id = _pinned_model(config)
    model_entry = next((model for model in config["models"] if model["id"] == model_id), {})
    edit_format = model_entry.get("edit_format", "whole")
    return [
        "--openai-api-base", f"{endpoint}/v1",
        "--model", f"openai/{model_id}",
        "--edit-format", edit_format,
    ] + _STARTER_TIER_GUARDRAIL_FLAGS
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_local_agent.py -v`
Expected: PASS (all tests in the file, including the pre-existing ones — confirm no
regressions in flag order/content assertions elsewhere in this file)

- [ ] **Step 5: Commit**

```bash
git add synlynk/local_agent.py tests/test_local_agent.py
git commit -m "fix(local-agent): Starter-tier guardrail flags (no auto-lint/test, capped map-tokens)"
```

---

## Task Group C: Regression Verification

### Task C1: Full local-agent suite and full project suite

**Files:** none modified — verification only.

- [ ] **Step 1: Run the local-agent test suite**

Run: `python3 -m pytest tests/test_local_agent.py tests/test_local_agent_ab_test.py tests/test_dispatch_local_agent.py -v`
Expected: all PASS, 0 failures. (`tests/test_dispatch_local_agent.py` exercises
`_dispatch_flags_for_agent("local")` end to end — confirm it still passes with the
three new guardrail flags appended; if it asserts an exact flags list, that assertion
needs updating to include `_STARTER_TIER_GUARDRAIL_FLAGS` — do that update as part of
this step, not as a separate task, since it's the same regression class caught during
PR #678's litellm-prefix fix.)

- [ ] **Step 2: Run the full project suite**

Run: `python3 -m pytest`
Expected: all PASS, 0 failures (baseline was 1575 passed, 2 skipped before this plan;
expect 1575 + ~15 new tests from this plan, 2 skipped, 0 failed — verify directly by
reading the pytest summary line, not by trusting any job/dispatch status).

- [ ] **Step 3: Commit if Step 1 required a fix**

```bash
git add tests/test_dispatch_local_agent.py
git commit -m "test(local-agent): update flags assertion for Starter-tier guardrails"
```

(Skip this step if Step 1 required no changes.)

---

## Explicitly out of scope for this plan

- Running the live A/B test against real oMLX (both models loaded, actual dispatches,
  actual timing/memory/quality data collected) — that's a manual/operational step using
  the harness this plan builds, not a coding task. Do it after this plan merges, per
  the spec's three dimensions (quality/correctness, safety/reliability, resource
  cost/latency), and write the comparison note to
  `project-docs/decisions/2026-08-03-local-agent-ab-test-comparison.md` — a short
  narrative summary of the `.jsonl` results, not a full RCA.
- Re-pinning `.agents/local.json` to `Qwen3.6-27B-4bit` if it wins — that's a one-line
  follow-up once the live A/B test (above) has a result, not part of this plan.
- Any Full-tier work (`--architect`, `editor_model_name`, `auto-lint`/`auto-test: true`)
  — gated on the N=10 Starter-tier track record per the spec.
- The N=10 graduation track record itself — that accumulates from real production
  dispatches over time; it is not something this plan can produce synthetically.

## Self-Review Notes

**Spec coverage:** A/B test prerequisite → Task Group A. Starter-tier guardrail table
(chat mode code-only / no `--architect`, `auto-lint: false`, `auto-test: false`,
`map-tokens` capped) → Task Group B, all four rows covered (chat-mode restriction is a
regression test since no code path adds `--architect` currently — see Task B1 Step 1
note). Graduation criteria, Full tier, non-goals → explicitly excluded per the
"Explicitly out of scope" section above, matching the spec's own tier boundary.

**Placeholder scan:** no TBD/TODO; every step has complete code or an exact command.

**Type consistency:** `run_ab_case(model_id, label, prompt, dispatch_runner=None)`
signature is identical across Task A3's tests, Task A3's implementation, and Task A4's
`main()` call site. `_build_result_row` positional argument order matches between Task
A2's test and Task A3's call site in `run_ab_case`.
