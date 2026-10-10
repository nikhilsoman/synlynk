# Muse Harness Config Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix synlynk's Muse (Meta) harness dispatch config so a dispatch to Muse actually invokes the real, installed `muse` CLI (v1.4.4) correctly, instead of failing immediately on flag/contract mismatches that predate the real CLI's release.

**Architecture:** Three small, tightly-coupled config edits (`synlynk/_constants.py`'s `HARNESS_CAPABILITY_BASELINES["muse"]` entry, two `agent == "muse"` special-case blocks in `synlynk/dispatch.py`, and a missing `"muse"` model-catalog entry in `synlynk/models.py` + the live `.synlynk/models.json`), plus one necessary correctness fix in `synlynk/fleet.py` discovered while reading the real code (its two live-smoke-test helpers silently mis-route the prompt to stdin instead of a positional CLI arg once `prompt_flag` is removed). No new abstractions, no `HarnessAdapter` protocol changes, no fleet-tier promotion.

**Tech Stack:** Python 3, pytest, synlynk CLI (`bin/synlynk.py`), real `muse` CLI v1.4.4 for the one live smoke-test step.

---

## Pre-requisite: create an isolated worktree

This is a separate, independent fix from the TPM-daemon-autonomy work on `docs/claude/tpm-daemon-autonomy-fix-design`. Before starting Task 1, invoke **superpowers:using-git-worktrees** to create a new worktree for branch `fix/claude/muse-harness-config`, branched off `main` (not off the docs branch this plan was written on). Follow that skill's directory-selection and baseline-test steps, then run all tasks below from inside that new worktree.

---

### Task 1: Fix `HARNESS_CAPABILITY_BASELINES["muse"]` in `synlynk/_constants.py`

**Files:**
- Modify: `synlynk/_constants.py:269-307`
- Test: `tests/test_muse_harness.py:14-34` (existing test, must be updated — it currently asserts the *old, wrong* contract)

The current entry (lines 269-307) is:

```python
    "muse": {
        "cli": "muse",
        "can_gh_write": True,
        "non_interactive_flags": ["run", "--non-interactive"],
        "prompt_flag": "--prompt",
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": [
                "--prompt",
                "--model",
                "--non-interactive",
                "-C",
                "--output-format",
            ],
            "invalid_flags": ["--dangerously-skip-permissions", "--always-approve"],
            "required_flags": ["--non-interactive"],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "--non-interactive",
        },
        "network_deps": {
            "required_endpoints": ["api.muse.meta.com:443"],
            "optional_endpoints": [],
        },
        "auth_check": {
            "probe": ["muse", "--version"],
            "unauthenticated_markers": [
                "not logged in",
                "login required",
                "missing api key",
            ],
        },
        "roles": ["builder", "verifier", "architect"],
        "env_passthrough": ["MUSE_API_KEY", "META_API_KEY"],
        "strengths": ["surgical refactoring", "algorithmic synthesis", "automated unit testing", "high throughput"],
    },
```

- [ ] **Step 1: Read the existing test to confirm what currently passes**

Run: `pytest tests/test_muse_harness.py::test_muse_baseline_schema_tc0 -v`
Expected: PASS (asserts the old contract, which is still live in the code at this point)

- [ ] **Step 2: Update `test_muse_baseline_schema_tc0` to assert the new, real contract**

Replace the body of `test_muse_baseline_schema_tc0` in `tests/test_muse_harness.py` (lines 14-34) with:

```python
def test_muse_baseline_schema_tc0():
    """Verify Meta Muse baseline passes TC-0 schema validation with zero issues."""
    assert "muse" in HARNESS_CAPABILITY_BASELINES
    baseline = HARNESS_CAPABILITY_BASELINES["muse"]

    assert baseline["cli"] == "muse"
    assert baseline["can_gh_write"] is True
    assert "builder" in baseline["roles"]
    assert "verifier" in baseline["roles"]
    assert "architect" in baseline["roles"]
    assert baseline["non_interactive_flags"] == ["exec"]
    assert "prompt_flag" not in baseline
    assert baseline["prompt_via_arg"] is True
    assert baseline["env_passthrough"] == []
    assert baseline["dispatch_flags"]["valid_flags"] == [
        "--json",
        "--provider",
        "--model",
        "--approval-mode",
        "--workspace",
    ]
    assert baseline["dispatch_flags"]["required_flags"] == ["--json", "--approval-mode"]
    assert baseline["headless_contract"]["non_interactive_flag"] == "exec"

    # TC-0 schema check
    res = _run_tc0("muse", baseline)
    assert res["schema_issues"] == [], f"TC-0 schema issues: {res['schema_issues']}"

    assert "muse" in NEXT_GEN_FLEET
    assert "muse" in EXTENDED_FLEET
```

- [ ] **Step 3: Run test to verify it fails against the current (old) baseline**

Run: `pytest tests/test_muse_harness.py::test_muse_baseline_schema_tc0 -v`
Expected: FAIL — `assert baseline["non_interactive_flags"] == ["exec"]` fails because the live value is still `["run", "--non-interactive"]`.

- [ ] **Step 4: Rewrite the `"muse"` entry in `synlynk/_constants.py`**

Replace lines 269-307 with:

```python
    "muse": {
        "cli": "muse",
        "can_gh_write": True,
        "non_interactive_flags": ["exec"],
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": [
                "--json",
                "--provider",
                "--model",
                "--approval-mode",
                "--workspace",
            ],
            "invalid_flags": ["--dangerously-skip-permissions", "--always-approve"],
            "required_flags": ["--json", "--approval-mode"],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "exec",
        },
        "network_deps": {
            "required_endpoints": ["api.muse.meta.com:443"],
            "optional_endpoints": [],
        },
        "auth_check": {
            "probe": ["muse", "--version"],
            "unauthenticated_markers": [
                "not logged in",
                "login required",
                "missing api key",
            ],
        },
        "roles": ["builder", "verifier", "architect"],
        "env_passthrough": [],
        "strengths": ["surgical refactoring", "algorithmic synthesis", "automated unit testing", "high throughput"],
    },
```

Do not touch `CORE_FLEET`, `EXPERIMENTAL_FLEET`, `NEXT_GEN_FLEET`, or `EXTENDED_FLEET` (lines 312-315) — fleet-tier membership is explicitly out of scope.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_muse_harness.py::test_muse_baseline_schema_tc0 -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/_constants.py tests/test_muse_harness.py
git commit -m "fix(muse): correct HARNESS_CAPABILITY_BASELINES to match real muse exec CLI contract"
```

---

### Task 2: Fix the two `agent == "muse"` special-case blocks in `synlynk/dispatch.py`

**Files:**
- Modify: `synlynk/dispatch.py:3941-3943` (output-format flag injection)
- Modify: `synlynk/dispatch.py:3982-3983` (worktree cwd flag injection)
- Test: `tests/test_muse_harness.py:37-89` (existing test, must be updated)

Current code (confirmed via direct read this session):

```python
# line 3941-3943
    if agent == "muse":
        if "--output-format" not in flags:
            flags = flags + ["--output-format", "json"]
```

```python
# line 3978-3983
    if agent == "grok" and worktree_path and "--cwd" not in flags:
        flags = flags + ["--cwd", worktree_path]
    if agent == "codex" and worktree_path and "-C" not in flags and "--cd" not in flags:
        flags = flags + ["-C", worktree_path]
    if agent == "muse" and worktree_path and "-C" not in flags:
        flags = flags + ["-C", worktree_path]
```

The prompt-construction block at line 2139-2150 (`if agent == "muse": ... working_dir = cwd_hint or os.getcwd() ...`) does **not** hardcode any wrong flag — confirmed by direct read this session, it only builds prose text for the prompt body, not CLI flags. No change needed there, per the spec.

- [ ] **Step 1: Update `test_muse_dispatch_flags_and_command_construction` to assert the new flag shape**

Replace the assertions in `tests/test_muse_harness.py` (lines 81-89) from:

```python
    # Inspect shell command string
    shell_cmd = cmd_run[2] if isinstance(cmd_run, (list, tuple)) and len(cmd_run) > 2 else str(cmd_run)
    assert "muse" in shell_cmd
    assert "run" in shell_cmd
    assert "--non-interactive" in shell_cmd
    assert "-C" in shell_cmd
    assert worktree_dir in shell_cmd
    assert "--output-format json" in shell_cmd
    assert "--prompt" in shell_cmd
```

to:

```python
    # Inspect shell command string
    shell_cmd = cmd_run[2] if isinstance(cmd_run, (list, tuple)) and len(cmd_run) > 2 else str(cmd_run)
    assert "muse" in shell_cmd
    assert "exec" in shell_cmd
    assert "--workspace" in shell_cmd
    assert worktree_dir in shell_cmd
    assert "--json" in shell_cmd
    assert "--approval-mode" in shell_cmd
    assert "never" in shell_cmd
    assert "--non-interactive" not in shell_cmd
    assert "--output-format" not in shell_cmd
    assert "-C " not in shell_cmd
    assert "--prompt" not in shell_cmd
```

- [ ] **Step 2: Run test to verify it fails against the current dispatch.py code**

Run: `pytest tests/test_muse_harness.py::test_muse_dispatch_flags_and_command_construction -v`
Expected: FAIL — `assert "exec" in shell_cmd` or similar fails because `non_interactive_flags` is already `["exec"]` from Task 1, but `dispatch.py` still injects `--output-format json` and `-C`, and nothing yet injects `--approval-mode never`.

- [ ] **Step 3: Fix the output-format injection block**

In `synlynk/dispatch.py`, replace (around line 3941-3943):

```python
    if agent == "muse":
        if "--output-format" not in flags:
            flags = flags + ["--output-format", "json"]
```

with:

```python
    if agent == "muse":
        if "--json" not in flags:
            flags = flags + ["--json"]
        if "--approval-mode" not in flags:
            flags = flags + ["--approval-mode", "never"]
```

- [ ] **Step 4: Fix the worktree cwd flag injection block**

In `synlynk/dispatch.py`, replace (around line 3982-3983):

```python
    if agent == "muse" and worktree_path and "-C" not in flags:
        flags = flags + ["-C", worktree_path]
```

with:

```python
    if agent == "muse" and worktree_path and "--workspace" not in flags:
        flags = flags + ["--workspace", worktree_path]
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_muse_harness.py::test_muse_dispatch_flags_and_command_construction -v`
Expected: PASS

- [ ] **Step 6: Run the full muse test file to confirm nothing else regressed**

Run: `pytest tests/test_muse_harness.py -v`
Expected: all tests PASS (including `test_muse_prompt_formatting`, `test_muse_structured_token_extraction`, `test_muse_probe_agent`, which are untouched by this task and should still pass unchanged)

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_muse_harness.py
git commit -m "fix(muse): inject --json/--approval-mode/--workspace instead of old --output-format/-C flags"
```

---

### Task 3: Fix `fleet.py`'s live-smoke-test prompt construction for agents with `prompt_via_arg` but no `prompt_flag`

**Why this task exists (not in the original spec, found during implementation):** `synlynk/fleet.py` has two functions, `live_agent_smoke` (line 356) and `live_agent_receipt_check` (line 450), each of which builds the real CLI invocation for a harness's live compliance-matrix smoke test. Both contain:

```python
        elif prompt_via_arg and prompt_flag:
            cmd = [cli] + ni + [prompt_flag, prompt]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        else:
            cmd = [cli] + ni
            proc = subprocess.run(cmd, input=prompt, capture_output=True, text=True, timeout=timeout_s)
```

Once Task 1 removes `prompt_flag` from the muse baseline, `prompt_via_arg and prompt_flag` becomes `True and None` → falsy, so muse falls into the `else` branch and the prompt gets piped over **stdin** instead of passed as the positional argument `muse exec` actually requires. That would silently break muse's live compliance-matrix smoke tests (`live_agent_smoke`/`live_agent_receipt_check`) the same way the original bug broke real dispatch — same class of bug, same root cause (code assumed `prompt_flag` is always present whenever `prompt_via_arg` is true), just a second call site. `synlynk/dispatch.py`, `synlynk/support_engineer.py`, and `synlynk/team.py` already handle `prompt_via_arg=True, prompt_flag=None` correctly (confirmed by direct read this session — each has an explicit `if prompt_flag: ... else: <no-flag positional form>` branch); `fleet.py` is the one place that does not.

**Files:**
- Modify: `synlynk/fleet.py:395-408` (`live_agent_smoke`)
- Modify: `synlynk/fleet.py:486-...` (`live_agent_receipt_check`, mirrors the same pattern)
- Test: `tests/test_fleet_operability.py` (new tests)

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_fleet_operability.py`:

```python
def test_live_agent_smoke_positional_prompt_when_no_prompt_flag(monkeypatch):
    import synlynk.fleet as fleet_mod

    captured = {}

    class FakeProc:
        returncode = 0
        stdout = "pong\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(fleet_mod.shutil, "which", lambda cli: "/usr/bin/muse")
    monkeypatch.setattr(fleet_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        fleet_mod,
        "HARNESS_CAPABILITY_BASELINES",
        {
            "muse": {
                "cli": "muse",
                "non_interactive_flags": ["exec"],
                "prompt_via_arg": True,
            }
        },
    )

    result = fleet_mod.live_agent_smoke("muse")

    assert result.status == "green"
    assert captured["cmd"][-1] == fleet_mod._LIVE_SMOKE_PROMPT
    assert "input" not in captured["kwargs"]


def test_live_agent_receipt_check_positional_prompt_when_no_prompt_flag(monkeypatch):
    import synlynk.fleet as fleet_mod

    captured = {}

    class FakeProc:
        returncode = 0
        stdout = "SYNLYNK_TASK_RECEIVED: abc123\nok done\n"
        stderr = ""

    def fake_run(cmd, **kwargs):
        captured["cmd"] = cmd
        captured["kwargs"] = kwargs
        return FakeProc()

    monkeypatch.setattr(fleet_mod.shutil, "which", lambda cli: "/usr/bin/muse")
    monkeypatch.setattr(fleet_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        fleet_mod,
        "HARNESS_CAPABILITY_BASELINES",
        {
            "muse": {
                "cli": "muse",
                "non_interactive_flags": ["exec"],
                "prompt_via_arg": True,
            }
        },
    )

    result = fleet_mod.live_agent_receipt_check("muse", task_sha256="abc123")

    assert result.status == "green"
    assert captured["cmd"][-1].endswith(fleet_mod._LIVE_SMOKE_PROMPT)
    assert "input" not in captured["kwargs"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fleet_operability.py::test_live_agent_smoke_positional_prompt_when_no_prompt_flag tests/test_fleet_operability.py::test_live_agent_receipt_check_positional_prompt_when_no_prompt_flag -v`
Expected: FAIL — `captured["cmd"]` is never set (the code takes the `else` branch with `input=prompt`, not `fake_run`'s `cmd` capture for the positional path), or `"input" not in captured["kwargs"]` fails because `input=prompt` was passed.

- [ ] **Step 3: Fix `live_agent_smoke`**

In `synlynk/fleet.py`, replace (around line 395-408):

```python
        elif prompt_via_arg and prompt_flag:
            cmd = [cli] + ni + [prompt_flag, prompt]
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s
            )
        else:
            cmd = [cli] + ni
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
```

with:

```python
        elif prompt_via_arg:
            cmd = [cli] + ni + ([prompt_flag, prompt] if prompt_flag else [prompt])
            proc = subprocess.run(
                cmd, capture_output=True, text=True, timeout=timeout_s
            )
        else:
            cmd = [cli] + ni
            proc = subprocess.run(
                cmd,
                input=prompt,
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
```

- [ ] **Step 4: Fix `live_agent_receipt_check`**

Read the full `else` branch of `live_agent_receipt_check` first (it mirrors `live_agent_smoke`'s structure starting at line 486 — read `synlynk/fleet.py:486-510` to get its exact `else` branch text, since it was only partially read this session). Apply the identical transformation: change

```python
        elif prompt_via_arg and prompt_flag:
            cmd = [cli] + ni + [prompt_flag, prompt]
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        else:
```

to

```python
        elif prompt_via_arg:
            cmd = [cli] + ni + ([prompt_flag, prompt] if prompt_flag else [prompt])
            proc = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout_s)
        else:
```

leaving the rest of that `else` branch (the stdin-based fallback for agents with no `prompt_via_arg`) untouched.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_fleet_operability.py -v`
Expected: all tests PASS, including the two new ones and every pre-existing test in the file (confirm no regression to the `claude`/stdin-fallback path, which has no `prompt_via_arg` set and must still take the `else` branch unchanged).

- [ ] **Step 6: Commit**

```bash
git add synlynk/fleet.py tests/test_fleet_operability.py
git commit -m "fix(fleet): pass prompt positionally for prompt_via_arg agents with no prompt_flag"
```

---

### Task 4: Add a real `muse` model-catalog entry in `synlynk/models.py` and `.synlynk/models.json`

**Files:**
- Modify: `synlynk/models.py:134-159` (builtin fallback `tiers` dict inside `load_model_catalog()`)
- Modify: `.synlynk/models.json` (live, file-backed catalog that overrides the builtin fallback whenever it's present — confirmed present in this repo)
- Test: `tests/test_muse_harness.py` (new test)

Confirmed via direct read this session: `resolve_tier_model(tier, harness)` (`synlynk/models.py:164-186`) first checks `tiers[tier][harness]`, then falls back through `("pro", "fast", "reasoning")` in that order, then (for `codex` only) a config-file read, else returns the literal placeholder string `f"{harness}-default"`. Since no `"muse"` key exists in any tier today, `resolve_tier_model(<any tier>, "muse")` currently returns `"muse-default"` — not a real model id.

The live `.synlynk/models.json` in this repo (read in full this session) currently has:

```json
  "tiers": {
    "fast": {
      "claude": "claude-haiku-4-5-20251001",
      "agy": "gemini-3.7-flash-medium",
      "codex": "gpt-5.6-luna",
      "grok": "grok-4.6",
      "local": "qwen2.5"
    },
    "pro": {
      "claude": "claude-sonnet-5",
      "agy": "gemini-3.1-pro-low",
      "codex": "gpt-5.6-luna",
      "grok": "grok-4.7",
      "local": "qwen2.5"
    },
    "reasoning": {
      "claude": "claude-opus-5",
      "agy": "gemini-3.1-pro-high",
      "codex": "gpt-5.6-luna",
      "grok": "grok-4.7",
      "local": "deepseek-r1"
    },
    "hermes": {
      "local": "Hermes-3-Llama-3.1-8B"
    }
  },
```

Every other harness has a `"muse"`-shaped sibling entry in `"pro"` and `"fast"` (and most in `"reasoning"`). `resolve_tier_model` checks the requested tier first, then falls back to `"pro"`, `"fast"`, `"reasoning"` in that order — so adding `muse` to `"pro"` alone is enough to make resolution succeed for any tier via the fallback chain, but add it to both `"pro"` and `"fast"` to match the density of every other harness and avoid surprising tier-specific behavior later.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_muse_harness.py`:

```python
def test_muse_model_resolves_to_real_catalog_id():
    """resolve_tier_model must not fall through to the 'muse-default' placeholder."""
    from synlynk.models import resolve_tier_model

    assert resolve_tier_model("pro", "muse") == "muse-spark-1.3"
    assert resolve_tier_model("fast", "muse") == "muse-spark-1.3"
    assert resolve_tier_model("unknown-tier", "muse") == "muse-spark-1.3"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_muse_harness.py::test_muse_model_resolves_to_real_catalog_id -v`
Expected: FAIL — `resolve_tier_model("pro", "muse")` returns `"muse-default"`, not `"muse-spark-1.3"`.

- [ ] **Step 3: Add `muse` to the builtin fallback catalog in `synlynk/models.py`**

In `synlynk/models.py`, inside `load_model_catalog()` (lines 134-159), update the `"fast"` and `"pro"` tier dicts:

```python
        "tiers": {
            "fast": {
                "claude": "claude-haiku-4-5-20251001",
                "agy": "gemini-3.7-flash-medium",
                "codex": "gpt-5.6-luna",
                "grok": "grok-4.6",
                "local": "qwen2.5",
                "muse": "muse-spark-1.3",
            },
            "pro": {
                "claude": "claude-sonnet-5",
                "agy": "gemini-3.1-pro-low",
                "codex": "gpt-5.6-luna",
                "grok": "grok-4.7",
                "local": "qwen2.5",
                "muse": "muse-spark-1.3",
            },
            "reasoning": {
                "claude": "claude-opus-5-5",
                "agy": "gemini-3.1-pro-high",
                "codex": "gpt-5.6-luna",
                "grok": "grok-4.7",
                "local": "deepseek-r1",
            },
            "hermes": {
                "local": "Hermes-3-Llama-3.1-8B",
            },
        },
```

(Leave `"reasoning"` and `"hermes"` untouched — `muse` is already reachable through the `"pro"`/`"fast"` fallback chain for any tier, matching the spec's "at least one tier" requirement while being consistent with how densely every other remote harness is mapped.)

- [ ] **Step 4: Add `muse` to the live `.synlynk/models.json` the same way**

Edit `.synlynk/models.json`'s `"tiers"` object so `"fast"` and `"pro"` each gain a `"muse": "muse-spark-1.3"` entry, identical in placement to Step 3. This file overrides the builtin fallback whenever it exists on disk (confirmed by `load_model_catalog`'s `catalog_path.is_file()` check) — without this edit, the builtin-fallback fix from Step 3 would never actually run in this repo's own checkout.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_muse_harness.py::test_muse_model_resolves_to_real_catalog_id -v`
Expected: PASS

- [ ] **Step 6: Run the full muse test file and the models test file to confirm no regressions**

Run: `pytest tests/test_muse_harness.py tests/test_fleet_operability.py -v`
Expected: all PASS

Run: `pytest -k models -v`
Expected: all PASS (no existing model-catalog test asserts an exact `tiers` dict shape that would break from an added key — if one does, read it and extend its expected-keys assertion rather than removing the new `muse` key)

- [ ] **Step 7: Commit**

```bash
git add synlynk/models.py .synlynk/models.json tests/test_muse_harness.py
git commit -m "fix(muse): add real muse-spark-1.3 model catalog entry, remove muse-default fallback"
```

---

### Task 5: Full regression run

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -x`
Expected: all tests pass, 0 failures. If anything outside the files touched in Tasks 1-4 fails, stop and investigate before proceeding — per this project's root-cause-first debugging norm, do not patch around an unrelated failure without understanding it.

- [ ] **Step 2: Commit the plan file itself (if not already committed) and confirm clean working tree**

```bash
git status --short
```
Expected: empty (everything from Tasks 1-4 already committed).

---

### Task 6: Live smoke-test dispatch (manual, real cost — not a pytest task)

**Files:** none (this task invokes the real `synlynk` CLI and the real `muse` binary)

This step cannot be verified by unit tests alone — they mock `subprocess.Popen`/`subprocess.run`, so they can confirm the *flags* are correct but not that the real `muse` binary accepts them and completes a real job. Run this only after Tasks 1-5 are committed and the full suite is green.

- [ ] **Step 1: Confirm `muse` is on PATH and authenticated**

Run: `muse --version`
Expected: prints a version string (e.g. `1.4.4` / `1.4.4-R5419.1`), exit code 0. If this fails, stop — the smoke test cannot proceed without a working `muse` CLI, and that failure is unrelated to this plan's config fix.

- [ ] **Step 2: Dispatch a cheap, read-only, no-op task to muse**

Run:
```bash
python3 bin/synlynk.py dispatch --harness muse --task "Read the file README.md in this repo and summarize it in exactly one sentence. Do not modify any file." --force-agent
```

(Use whatever flag this repo's `synlynk dispatch` CLI actually exposes for "force this harness regardless of routing policy" — confirm the exact flag name via `python3 bin/synlynk.py dispatch --help` before running, since the plan was written without re-verifying every CLI flag name against `bin/synlynk.py`'s argparse definitions.)

- [ ] **Step 3: Verify the job's real effect directly, not its reported status string**

Per this project's long-documented job-status false-negative history (see memory: job-status false-negative RCA, #1377, #1429), do not trust whatever status `synlynk jobs` reports for this dispatch. Instead:

```bash
python3 bin/synlynk.py jobs --all | grep muse
```

to find the job's worktree/log path, then read that job's actual log output directly (`cat` or `Read` tool on the job's log file under `.synlynk/logs/<job_id>.log`) to confirm:
- The invoked command line contains `exec`, `--json`, `--approval-mode never`, and `--workspace <path>` (not `run`, `--non-interactive`, `--output-format`, or `-C`).
- The real `muse` binary produced actual JSON output (not an immediate CLI-usage error).
- No file in the repo was modified (`git status --short` in the job's worktree should be empty, since the task was read-only).

- [ ] **Step 4: Log the real cost**

This live dispatch has real token cost. Confirm it was captured via the normal `synlynk cost log` path (per this project's Cost Capture Protocol) — dispatched jobs are auto-captured via `dispatch_agent()`, so no manual `synlynk cost log` call should be needed; just confirm the row exists:

```bash
grep -i muse project-docs/costs.md
```

Expected: a new row for this job, with a real (non-zero) token count.

---

## Execution Handoff

This plan's actual implementation (Tasks 1-6) should be dispatched via `synlynk dispatch` to Agy, Grok, or Codex rather than carried out directly by Claude, per this project's Default Agent Role policy (CLAUDE.md's "Default Agent Role" section, interim default under the 2026-10-04 Empirical Capability Assessment Policy — Claude's role is PM/review/deploy/brainstorm, implementation routes to the other harnesses by default). Claude's role here is limited to: writing this plan (done), dispatching it, and reviewing the resulting PR as a non-authoring reviewer per the Hardened PR Review Policy (cross-harness+model review required).

Two options for who drives dispatch of the individual tasks:

**1. Subagent-Driven via `synlynk dispatch` (recommended)** — dispatch Task 1+2 together as one job (same file-adjacent, tightly coupled, matches the spec's own task grouping), Task 3 as a second job (distinct file, independently testable), Task 4 as a third job, then Task 5 (regression run) and Task 6 (live smoke test) as PM-tier verification steps Claude performs directly after the dispatched jobs land, consistent with Claude's review/deploy role.

**2. Single combined dispatch** — dispatch all of Tasks 1-4 as one job to a single implementer (Codex or Grok, given the task's CLI-plumbing/refactor nature per the Capability-Based Task Allocation table), then Claude runs Task 5 and Task 6 directly.

Which approach?
