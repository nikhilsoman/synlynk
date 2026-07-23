# Dispatch Stacking & Ground-Truth Merge Gate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific adaptation (per this repo's locked `CLAUDE.md` role split):** the "implementer subagent" role is a `synlynk dispatch codex` job, not a native Claude Agent-tool subagent. For each task below, run `python3 -m synlynk dispatch codex --task "<task text + file context>" --force-agent --context-mode task` from this worktree, wait for completion, then merge/cherry-pick its commit into this branch (`chore/dispatch-stacking-ground-truth-gate-design`). Claude performs both review stages itself by reading the diff (code review is within Claude's allowed role) — do not spawn a second subagent for review.

**Goal:** Stop dispatch jobs from branching fresh off mainline when a feature branch is already accumulating task commits, and stop treating job self-report as ground truth for merge-eligibility — implement Phase 1 of `docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-truth-gate-design.md` only (stacked dispatch branches + ground-truth test-suite gate). Phase 2 (footprint locking, wave scheduling) is explicitly out of scope.

**Architecture:** `synlynk/dispatch.py` gains base-ref auto-detection (current non-mainline branch by default, config/flag-overridable) and anchors new job worktrees to that base's exact tip SHA instead of a hardcoded `origin/main`. `synlynk/jobs.py`'s existing job-completion polling loop gains a harness-run test-suite gate and a base-freshness check, both stored as first-class job-record fields rather than inferred from job self-report.

**Tech Stack:** Python 3 stdlib only (`subprocess`, `json`, `re`), pytest for tests. No new dependencies.

---

## Task 1: `dispatch` config block

**Files:**
- Modify: `synlynk/__init__.py:1383-1423` (`load_config()`)
- Test: `tests/test_config.py` (check first; if it doesn't exist, add `tests/test_dispatch_config.py`)

- [ ] **Step 1: Check for an existing config test file**

Run: `ls tests/ | grep -i config`

If `tests/test_config.py` exists, add the new test there. Otherwise create `tests/test_dispatch_config.py`.

- [ ] **Step 2: Write the failing test**

```python
import json
import os


def test_load_config_fills_dispatch_defaults_when_missing(project_dir):
    import synlynk as sl

    config_path = os.path.join(".synlynk", "config.json")
    with open(config_path, "w") as f:
        json.dump({"schema_version": 1}, f)

    config = sl.load_config()

    assert config["dispatch"] == {"stacking": "auto", "gate_suite_cmd": ""}


def test_load_config_preserves_partial_dispatch_block(project_dir):
    import synlynk as sl

    config_path = os.path.join(".synlynk", "config.json")
    with open(config_path, "w") as f:
        json.dump({"schema_version": 1, "dispatch": {"stacking": "never"}}, f)

    config = sl.load_config()

    assert config["dispatch"]["stacking"] == "never"
    assert config["dispatch"]["gate_suite_cmd"] == ""
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_dispatch_config.py -v`
Expected: FAIL — `KeyError: 'dispatch'` (or assertion on missing key)

- [ ] **Step 4: Add the `dispatch` default block and nested merge**

In `synlynk/__init__.py`, inside `load_config()`'s `defaults` dict (around line 1387, next to `"budget"`), add:

```python
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "dispatch": {"stacking": "auto", "gate_suite_cmd": ""},
```

Immediately after the existing `budget` nested-merge block (around line 1419-1421):

```python
        for key, val in defaults["budget"].items():
            if key not in config.get("budget", {}):
                config.setdefault("budget", {})[key] = val
        for key, val in defaults["dispatch"].items():
            if key not in config.get("dispatch", {}):
                config.setdefault("dispatch", {})[key] = val
        return config
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dispatch_config.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_dispatch_config.py
git commit -m "feat(dispatch): add dispatch.stacking/gate_suite_cmd config block"
```

---

## Task 2: Base-ref resolution — auto-detect current branch, config-driven stacking mode, explicit override

**Files:**
- Modify: `synlynk/dispatch.py:539-572` (`_resolve_dispatch_worktree_base_ref`)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`:

```python
def test_resolve_dispatch_base_ref_stacks_on_current_feature_branch(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto"
    )

    assert base_ref == "feat/example"


def test_resolve_dispatch_base_ref_falls_back_to_mainline_on_main_branch(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)
    monkeypatch.setattr(
        dispatch_mod.subprocess, "run",
        lambda cmd, **kw: subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[:2] == ["git", "fetch"] else subprocess.run.__wrapped__(cmd, **kw)
        if False else __import__("subprocess").run(cmd, **kw)
    )

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto"
    )

    assert base_ref == "main"


def test_resolve_dispatch_base_ref_stacking_never_always_uses_mainline(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="never"
    )

    assert base_ref == "main"


def test_resolve_dispatch_base_ref_stacking_always_errors_on_mainline(git_worktree_repo):
    import synlynk.dispatch as dispatch_mod
    import subprocess
    import pytest

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)

    with pytest.raises(RuntimeError, match="stacking is 'always'"):
        dispatch_mod._resolve_dispatch_worktree_base_ref(
            str(git_worktree_repo), stacking_mode="always"
        )


def test_resolve_dispatch_base_ref_explicit_base_wins(git_worktree_repo):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto", explicit_base="main"
    )

    assert base_ref == "main"
```

Note: the second test's monkeypatch is deliberately simple — replace it with the cleaner version below if the inline lambda proves awkward in practice (it's here to force the `git fetch origin main/master` calls to fail so the test exercises the local-verify fallback path deterministically without depending on network access). Simplify to:

```python
def test_resolve_dispatch_base_ref_falls_back_to_mainline_on_main_branch(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "branch", "-M", "main"], cwd=git_worktree_repo, capture_output=True, check=True)

    real_run = subprocess.run

    def fake_run(cmd, **kw):
        if cmd[:2] == ["git", "fetch"]:
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="no remote")
        return real_run(cmd, **kw)

    monkeypatch.setattr(dispatch_mod.subprocess, "run", fake_run)

    base_ref = dispatch_mod._resolve_dispatch_worktree_base_ref(
        str(git_worktree_repo), stacking_mode="auto"
    )

    assert base_ref == "main"
```

Use this simplified version in the actual file — drop the first awkward draft.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -v -k resolve_dispatch_base_ref`
Expected: FAIL — `TypeError: _resolve_dispatch_worktree_base_ref() got an unexpected keyword argument 'stacking_mode'`

- [ ] **Step 3: Implement the new resolution logic**

Replace `_resolve_dispatch_worktree_base_ref` in `synlynk/dispatch.py:539-572` with:

```python
def _resolve_dispatch_worktree_base_ref(
    repo_path: Optional[str],
    stacking_mode: str = "auto",
    explicit_base: Optional[str] = None,
) -> str:
    """Resolve the base ref a new dispatch worktree should be anchored to.

    stacking_mode: "auto" (stack on current non-mainline branch, else mainline),
    "always" (stack on current branch, error on mainline/detached HEAD),
    "never" (always mainline — legacy behavior).
    """
    if explicit_base:
        return explicit_base

    if not repo_path or not os.path.isdir(repo_path):
        return "HEAD"

    if stacking_mode != "never":
        try:
            branch_result = subprocess.run(
                ["git", "-C", repo_path, "branch", "--show-current"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
            )
        except Exception:
            branch_result = None
        current_branch = (
            (branch_result.stdout or "").strip()
            if branch_result and branch_result.returncode == 0
            else ""
        )
        if current_branch and current_branch not in ("main", "master"):
            return current_branch
        if stacking_mode == "always":
            raise RuntimeError(
                f"dispatch.stacking is 'always' but current branch is "
                f"'{current_branch or '(detached HEAD)'}' — refusing to stack on mainline."
            )

    for candidate in ("main", "master"):
        try:
            fetch_result = subprocess.run(
                ["git", "fetch", "origin", candidate],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=repo_path,
            )
        except Exception:
            fetch_result = None
        if fetch_result and fetch_result.returncode == 0:
            return f"origin/{candidate}"

    for candidate in ("origin/main", "origin/master", "main", "master"):
        try:
            verify_result = subprocess.run(
                ["git", "rev-parse", "--verify", f"{candidate}^{{commit}}"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                cwd=repo_path,
            )
        except Exception:
            continue
        if verify_result.returncode == 0 and (verify_result.stdout or "").strip():
            return candidate

    return "HEAD"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v -k resolve_dispatch_base_ref`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat(dispatch): auto-detect current branch as dispatch worktree base"
```

---

## Task 3: `_create_job_worktree` anchors to resolved base's tip SHA, returns structured result

**Files:**
- Modify: `synlynk/dispatch.py:617-642` (`_create_job_worktree`)
- Modify: `tests/conftest.py:28-40` (`stub_dispatch_worktree`)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatch.py`:

```python
def test_create_job_worktree_anchors_to_base_tip_sha_and_returns_details(git_worktree_repo, monkeypatch):
    import synlynk.dispatch as dispatch_mod
    import subprocess
    import os as _os

    monkeypatch.chdir(git_worktree_repo)
    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)
    tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    result = dispatch_mod._create_job_worktree("job-test1", "codex")

    assert result["path"] == _os.path.join("worktrees", "job-test1")
    assert result["base_branch"] == "feat/example"
    assert result["base_sha"] == tip
    assert _os.path.isdir(result["path"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -v -k create_job_worktree_anchors`
Expected: FAIL — `TypeError: string indices must be integers` (current function returns a plain string)

- [ ] **Step 3: Implement the new `_create_job_worktree`**

Replace `synlynk/dispatch.py:617-642` with:

```python
def _create_job_worktree(job_id: str, agent: str, base: Optional[str] = None) -> dict:
    """Create the isolated git worktree for a dispatched job.

    Returns {"path": str, "branch": str, "base_branch": str, "base_sha": str}.
    """
    worktree_path, worktree_branch = _job_worktree_details(job_id, agent)
    os.makedirs(os.path.dirname(worktree_path), exist_ok=True)

    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    stacking_mode = (config.get("dispatch") or {}).get("stacking", "auto")

    base_ref = _resolve_dispatch_worktree_base_ref(
        os.getcwd(), stacking_mode=stacking_mode, explicit_base=base
    )

    base_sha = None
    if base_ref and base_ref != "HEAD":
        sha_result = subprocess.run(
            ["git", "-C", os.getcwd(), "rev-parse", base_ref],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        if sha_result.returncode == 0:
            base_sha = (sha_result.stdout or "").strip()

    worktree_cmd = ["git", "worktree", "add", worktree_path, "-b", worktree_branch]
    worktree_cmd.append(base_sha or base_ref)
    if not base_sha and base_ref == "HEAD":
        worktree_cmd = ["git", "worktree", "add", worktree_path, "-b", worktree_branch]

    result = subprocess.run(
        worktree_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        cwd=os.getcwd(),
    )
    if result.returncode != 0:
        details = "\n".join(
            part for part in [result.stdout.strip(), result.stderr.strip()] if part
        )
        raise RuntimeError(
            f"Failed to create worktree for job {job_id} at {worktree_path} "
            f"on branch {worktree_branch}."
            + (f"\n{details}" if details else "")
        )
    _assert_dispatch_worktree_base_is_fresh(worktree_path, base_ref)
    return {
        "path": worktree_path,
        "branch": worktree_branch,
        "base_branch": base_ref,
        "base_sha": base_sha,
    }
```

- [ ] **Step 4: Update the `stub_dispatch_worktree` fixture to match the new return shape**

In `tests/conftest.py`, replace:

```python
    monkeypatch.setattr(
        dispatch_mod,
        "_create_job_worktree",
        lambda job_id, agent: os.path.join("worktrees", job_id),
    )
```

with:

```python
    monkeypatch.setattr(
        dispatch_mod,
        "_create_job_worktree",
        lambda job_id, agent, base=None: {
            "path": os.path.join("worktrees", job_id),
            "branch": f"dispatch/{agent}/{job_id}",
            "base_branch": None,
            "base_sha": None,
        },
    )
```

- [ ] **Step 5: Update the call site in `dispatch_agent`**

In `synlynk/dispatch.py`, replace (around line 954-956):

```python
    worktree_path, worktree_branch = _job_worktree_details(job_id, agent)
    worktree_path = _create_job_worktree(job_id, agent)
```

with:

```python
    _unused_path, worktree_branch = _job_worktree_details(job_id, agent)
    worktree_info = _create_job_worktree(job_id, agent, base=base)
    worktree_path = worktree_info["path"]
    base_branch = worktree_info["base_branch"]
    base_sha = worktree_info["base_sha"]
```

(The `base` parameter referenced here is added to `dispatch_agent`'s signature in Task 4 — this step will not run standalone until Task 4 lands; keep both edits in the same commit if easier, or land Task 4 immediately after without a passing intermediate state.)

- [ ] **Step 6: Run the full existing dispatch/jobs test suite to check nothing else broke**

Run: `pytest tests/test_dispatch.py tests/test_jobs.py -v`
Expected: new test passes; watch for any other test asserting the old string-return shape of `_create_job_worktree` — fix any found by applying the same dict-unpacking pattern.

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/conftest.py tests/test_dispatch.py
git commit -m "feat(dispatch): anchor job worktrees to resolved base's tip SHA"
```

---

## Task 4: Job record fields (`base_branch`, `base_sha`, `suite_result`) + `dispatch_agent(base=...)` + `--base` CLI flag

**Files:**
- Modify: `synlynk/dispatch.py:810-820` (`dispatch_agent` signature)
- Modify: `synlynk/dispatch.py:1128-1150` (job dict construction)
- Modify: `synlynk/cli.py:426-452` (dispatch arg parser)
- Modify: `synlynk/cli.py:836-845` (dispatch command handler)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
def test_dispatch_agent_records_base_branch_and_sha_on_job(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod

    class FakeProc:
        pid = 4242

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda *a, **kw: {"passed": True, "reasons": []})
    monkeypatch.setattr(
        dispatch_mod, "_create_job_worktree",
        lambda job_id, agent, base=None: {
            "path": "worktrees/job-fake",
            "branch": f"dispatch/{agent}/job-fake",
            "base_branch": base or "feat/example",
            "base_sha": "deadbeef",
        },
    )

    job = dispatch_mod.dispatch_agent("codex", "do the thing", force_agent=True, base="feat/example")

    assert job["base_branch"] == "feat/example"
    assert job["base_sha"] == "deadbeef"
    assert job["suite_result"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -v -k records_base_branch_and_sha`
Expected: FAIL — `TypeError: dispatch_agent() got an unexpected keyword argument 'base'`

- [ ] **Step 3: Add `base` parameter to `dispatch_agent`**

In `synlynk/dispatch.py:810-820`, change the signature to:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None) -> dict:
```

- [ ] **Step 4: Apply Task 3 Step 5's call-site edit (if not already applied) and add job dict fields**

Confirm the call site reads:

```python
    _unused_path, worktree_branch = _job_worktree_details(job_id, agent)
    worktree_info = _create_job_worktree(job_id, agent, base=base)
    worktree_path = worktree_info["path"]
    base_branch = worktree_info["base_branch"]
    base_sha = worktree_info["base_sha"]
```

In the job dict literal (`synlynk/dispatch.py:1128-1150`), add three fields after `"worktree_branch": worktree_branch,`:

```python
        "worktree_branch": worktree_branch,
        "base_branch": base_branch,
        "base_sha": base_sha,
        "suite_result": None,
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py -v -k records_base_branch_and_sha`
Expected: PASS

- [ ] **Step 6: Add `--base` CLI flag**

In `synlynk/cli.py`, inside the `dispatch_parser` block (after the `--skip-preflight` argument, ~line 448-451):

```python
    dispatch_parser.add_argument(
        "--base", default=None,
        help="Explicit base branch/ref to anchor the job worktree to (overrides auto-stacking)"
    )
```

In the `elif args.command == "dispatch":` handler (`synlynk/cli.py:836-845`), add `base=getattr(args, "base", None)` to the `dispatch_agent(...)` call:

```python
            job = dispatch_agent(args.agent, args.task, story_id=args.story_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 requires_gh_write=getattr(args, "requires_gh_write", False),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 base=getattr(args, "base", None))
```

- [ ] **Step 7: Write a CLI-level test**

```python
def test_cli_dispatch_passes_base_flag(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.cli as cli_mod
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_dispatch(agent, task, **kwargs):
        captured.update(kwargs)
        return {"id": "job-x", "pid": 1, "fence": None}

    monkeypatch.setattr(cli_mod, "dispatch_agent", fake_dispatch)

    cli_mod.main(["dispatch", "codex", "--task", "do it", "--base", "feat/example", "--force-agent"])

    assert captured["base"] == "feat/example"
```

Check `synlynk/cli.py` for the actual entry-point function name (`main`) before writing this — if it differs, use the correct name; the existing `test_cli_dispatch_passes_requires_gh_write_flag` test at `tests/test_dispatch.py:168` shows the established calling convention to copy exactly.

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py -v -k cli_dispatch_passes_base_flag`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_dispatch.py
git commit -m "feat(dispatch): add base_branch/base_sha/suite_result job fields and --base flag"
```

---

## Task 5: Mandatory ground-truth test-suite gate

**Files:**
- Create: `_run_dispatch_gate` in `synlynk/dispatch.py` (near `_worktree_files_touched`, ~line 376)
- Modify: `synlynk/jobs.py:1062-1063` and `synlynk/jobs.py:1243` (both job-completion call sites, after `_finalize_completed_worktree_job`)
- Test: `tests/test_dispatch.py`, `tests/test_jobs.py`

- [ ] **Step 1: Write the failing test for the gate runner**

Add to `tests/test_dispatch.py`:

```python
def test_run_dispatch_gate_parses_pytest_summary_and_flags_failures(tmp_path, monkeypatch):
    import synlynk.dispatch as dispatch_mod

    class FakeResult:
        returncode = 1
        stdout = "2 passed, 1 failed, 1 skipped in 0.05s"
        stderr = ""

    monkeypatch.setattr(dispatch_mod.subprocess, "run", lambda *a, **kw: FakeResult())

    job = {"worktree_path": str(tmp_path)}
    result = dispatch_mod._run_dispatch_gate(job, "pytest tests/ -q")

    assert result == {"passed": 2, "failed": 1, "skipped": 1}


def test_run_dispatch_gate_returns_none_when_no_gate_cmd_configured(tmp_path):
    import synlynk.dispatch as dispatch_mod

    job = {"worktree_path": str(tmp_path)}
    result = dispatch_mod._run_dispatch_gate(job, "")

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -v -k run_dispatch_gate`
Expected: FAIL — `AttributeError: module 'synlynk.dispatch' has no attribute '_run_dispatch_gate'`

- [ ] **Step 3: Implement `_run_dispatch_gate`**

Add to `synlynk/dispatch.py`, after `_worktree_files_touched` (~line 376):

```python
def _run_dispatch_gate(job: dict, gate_suite_cmd: str) -> Optional[dict]:
    """Runs the configured test-suite command inside a job's worktree.

    Returns {"passed": int, "failed": int, "skipped": int} parsed from the
    command's combined output, or None if no gate command is configured or
    the worktree is unavailable.
    """
    if not gate_suite_cmd:
        return None
    worktree_path = job.get("worktree_path")
    if not worktree_path or not os.path.isdir(worktree_path):
        return None

    try:
        result = subprocess.run(
            gate_suite_cmd,
            shell=True,
            cwd=worktree_path,
            capture_output=True,
            text=True,
            check=False,
        )
    except Exception:
        return None

    combined = (result.stdout or "") + "\n" + (result.stderr or "")

    def _count(pattern: str) -> int:
        match = re.search(pattern, combined)
        return int(match.group(1)) if match else 0

    return {
        "passed": _count(r"(\d+)\s+passed"),
        "failed": _count(r"(\d+)\s+failed"),
        "skipped": _count(r"(\d+)\s+skipped"),
    }
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v -k run_dispatch_gate`
Expected: PASS (2 passed)

- [ ] **Step 5: Wire the gate into the job-completion polling loop**

In `synlynk/jobs.py`, both call sites that call `_finalize_completed_worktree_job(job, git_state)` (line 1063 and line 1243) need a gate run added immediately after, but only when `job.get("status") == "completed"`. Add a shared helper near `_finalize_completed_worktree_job` (`synlynk/jobs.py`, right after its definition ends ~line 420-ish — find the exact end via `grep -n "^def " synlynk/jobs.py` around that area and insert after it):

```python
def _apply_dispatch_gate(job: dict) -> None:
    """Runs the configured gate suite in job's worktree; downgrades status on failure."""
    if job.get("status") != "completed":
        return
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    gate_suite_cmd = (config.get("dispatch") or {}).get("gate_suite_cmd", "")
    if not gate_suite_cmd:
        return
    run_gate = _pkg("_run_dispatch_gate")
    if not run_gate:
        return
    suite_result = run_gate(job, gate_suite_cmd)
    if suite_result is None:
        return
    suite_result["ran_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    job["suite_result"] = suite_result
    if suite_result.get("failed", 0) > 0:
        job["status"] = "needs_fix"
        print(
            f"  ⚠ gate suite failed for job {job.get('id', '')}: "
            f"{suite_result['failed']} failed, {suite_result['passed']} passed "
            f"— status downgraded to needs_fix"
        )
```

Then at both call sites, change:

```python
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
```

to:

```python
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
```

- [ ] **Step 6: Write the harness-level gate test**

Add to `tests/test_jobs.py`:

```python
def test_apply_dispatch_gate_downgrades_status_on_suite_failure(project_dir, monkeypatch):
    import synlynk.jobs as jobs_mod
    import synlynk as sl

    config_path = ".synlynk/config.json"
    import json
    with open(config_path, "w") as f:
        json.dump({"dispatch": {"gate_suite_cmd": "pytest tests/ -q"}}, f)

    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: {
            "load_config": sl.load_config,
            "_run_dispatch_gate": lambda job, cmd: {"passed": 3, "failed": 2, "skipped": 0},
        }.get(name, default),
    )

    job = {"id": "job-gate1", "status": "completed", "worktree_path": "worktrees/job-gate1"}
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "needs_fix"
    assert job["suite_result"]["failed"] == 2


def test_apply_dispatch_gate_leaves_status_completed_when_no_gate_configured(project_dir, monkeypatch):
    import synlynk.jobs as jobs_mod
    import synlynk as sl

    monkeypatch.setattr(jobs_mod, "_pkg", lambda name, default=None: {"load_config": sl.load_config}.get(name, default))

    job = {"id": "job-gate2", "status": "completed", "worktree_path": "worktrees/job-gate2"}
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "completed"
    assert job.get("suite_result") is None
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -v -k apply_dispatch_gate`
Expected: PASS (2 passed)

- [ ] **Step 8: Run the full test suite**

Run: `pytest tests/ -q`
Expected: all tests pass, no regressions

- [ ] **Step 9: Commit**

```bash
git add synlynk/dispatch.py synlynk/jobs.py tests/test_dispatch.py tests/test_jobs.py
git commit -m "feat(dispatch): mandatory ground-truth test-suite gate on job completion"
```

---

## Task 6: STALE_BASE detection

**Files:**
- Create: `_check_dispatch_base_still_fresh` in `synlynk/dispatch.py` (near `_run_dispatch_gate`)
- Modify: `synlynk/jobs.py` — call it from `_apply_dispatch_gate` (added in Task 5)
- Test: `tests/test_dispatch.py`, `tests/test_jobs.py`

- [ ] **Step 1: Write the failing test for the freshness check**

Add to `tests/test_dispatch.py`:

```python
def test_check_dispatch_base_still_fresh_true_when_sha_matches_current_tip(git_worktree_repo):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    job = {"base_branch": "main", "base_sha": tip}
    assert dispatch_mod._check_dispatch_base_still_fresh(job, repo_path=str(git_worktree_repo)) is True


def test_check_dispatch_base_still_fresh_false_when_branch_advanced(git_worktree_repo):
    import synlynk.dispatch as dispatch_mod
    import subprocess

    old_tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "HEAD"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()

    (git_worktree_repo / "new_file.txt").write_text("more work\n")
    subprocess.run(["git", "add", "."], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "advance branch"], cwd=git_worktree_repo, capture_output=True, check=True)

    job = {"base_branch": "main", "base_sha": old_tip}
    assert dispatch_mod._check_dispatch_base_still_fresh(job, repo_path=str(git_worktree_repo)) is False


def test_check_dispatch_base_still_fresh_true_when_no_base_recorded():
    import synlynk.dispatch as dispatch_mod

    job = {"base_branch": None, "base_sha": None}
    assert dispatch_mod._check_dispatch_base_still_fresh(job) is True
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -v -k check_dispatch_base_still_fresh`
Expected: FAIL — `AttributeError: module 'synlynk.dispatch' has no attribute '_check_dispatch_base_still_fresh'`

- [ ] **Step 3: Implement `_check_dispatch_base_still_fresh`**

Add to `synlynk/dispatch.py`, after `_run_dispatch_gate`:

```python
def _check_dispatch_base_still_fresh(job: dict, repo_path: Optional[str] = None) -> bool:
    """Returns False if job.base_branch has moved past job.base_sha since dispatch.

    True (fresh) when no base was recorded (legacy jobs, or stacking: never).
    """
    base_branch = job.get("base_branch")
    base_sha = job.get("base_sha")
    if not base_branch or not base_sha:
        return True

    repo_path = repo_path or os.getcwd()
    try:
        tip_result = subprocess.run(
            ["git", "-C", repo_path, "rev-parse", base_branch],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
    except Exception:
        return True

    current_tip = (tip_result.stdout or "").strip()
    if tip_result.returncode != 0 or not current_tip:
        return True

    return current_tip == base_sha
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -v -k check_dispatch_base_still_fresh`
Expected: PASS (3 passed)

- [ ] **Step 5: Wire it into `_apply_dispatch_gate`**

In `synlynk/jobs.py`, extend `_apply_dispatch_gate` (added in Task 5) to also run the freshness check, after the gate-suite block:

```python
def _apply_dispatch_gate(job: dict) -> None:
    """Runs the configured gate suite in job's worktree; downgrades status on failure.
    Also flags STALE_BASE when the job's stacked base branch has advanced since dispatch.
    """
    if job.get("status") != "completed":
        return
    load_config_fn = _pkg("load_config")
    config = load_config_fn() if load_config_fn else {}
    gate_suite_cmd = (config.get("dispatch") or {}).get("gate_suite_cmd", "")
    if gate_suite_cmd:
        run_gate = _pkg("_run_dispatch_gate")
        if run_gate:
            suite_result = run_gate(job, gate_suite_cmd)
            if suite_result is not None:
                suite_result["ran_at"] = time.strftime("%Y-%m-%dT%H:%M:%S")
                job["suite_result"] = suite_result
                if suite_result.get("failed", 0) > 0:
                    job["status"] = "needs_fix"
                    print(
                        f"  ⚠ gate suite failed for job {job.get('id', '')}: "
                        f"{suite_result['failed']} failed, {suite_result['passed']} passed "
                        f"— status downgraded to needs_fix"
                    )

    if job.get("status") == "completed":
        check_fresh = _pkg("_check_dispatch_base_still_fresh")
        if check_fresh and not check_fresh(job):
            job["status"] = "stale_base"
            print(
                f"  ⚠ job {job.get('id', '')}'s base branch '{job.get('base_branch')}' "
                f"has advanced since dispatch — status set to stale_base "
                f"(re-dispatch fresh rather than force-merging)"
            )
```

(This replaces the version added in Task 5 Step 5 — same function name, extended body.)

- [ ] **Step 6: Write the harness-level stale-base test**

Add to `tests/test_jobs.py`:

```python
def test_apply_dispatch_gate_flags_stale_base(project_dir, monkeypatch):
    import synlynk.jobs as jobs_mod
    import synlynk as sl

    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: {
            "load_config": sl.load_config,
            "_check_dispatch_base_still_fresh": lambda job: False,
        }.get(name, default),
    )

    job = {
        "id": "job-stale1", "status": "completed",
        "worktree_path": "worktrees/job-stale1",
        "base_branch": "feat/example", "base_sha": "abc123",
    }
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "stale_base"
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_jobs.py -v -k apply_dispatch_gate`
Expected: PASS (3 passed — the two from Task 5 plus this one)

- [ ] **Step 8: Run the full test suite**

Run: `pytest tests/ -q`
Expected: all tests pass, no regressions

- [ ] **Step 9: Commit**

```bash
git add synlynk/dispatch.py synlynk/jobs.py tests/test_dispatch.py tests/test_jobs.py
git commit -m "feat(dispatch): detect STALE_BASE when a job's stacked branch advances before merge"
```

---

## Task 7: Surface `base_branch`/`base_sha`/`suite_result` in job summaries (`synlynk jobs`/`synlynk logs`)

**Files:**
- Modify: `synlynk/dispatch.py:379-451` (`_format_job_summary`, `_write_job_summary`)
- Modify: `synlynk/jobs.py:1046-1060` and the equivalent call around line 1220-1240 (both `_write_job_summary` call sites)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_dispatch.py`:

```python
def test_format_job_summary_includes_base_and_suite_result_when_present():
    from synlynk.dispatch import _format_job_summary

    summary = _format_job_summary(
        "job-abc", "codex", "story-1", 0, 12.5, 100, 200, 0.01,
        files_touched=["a.py"],
        base_branch="feat/example",
        base_sha="deadbeefcafe",
        suite_result={"passed": 5, "failed": 0, "skipped": 1, "ran_at": "2026-07-23T00:00:00"},
    )

    assert "base:     feat/example @ deadbeef" in summary
    assert "suite:    5 passed, 0 failed, 1 skipped" in summary
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch.py -v -k includes_base_and_suite_result`
Expected: FAIL — `TypeError: _format_job_summary() got an unexpected keyword argument 'base_branch'`

- [ ] **Step 3: Extend `_format_job_summary` and `_write_job_summary` signatures**

In `synlynk/dispatch.py`, update `_format_job_summary`'s signature (line ~385-392) to add three trailing optional params:

```python
def _format_job_summary(job_id: str, agent: str, story_id: Optional[str],
                        exit_code: Optional[int], duration_s: Optional[float],
                        in_tokens: int, out_tokens: int, cost_usd: float,
                        files_touched: Optional[list] = None,
                        worktree_path: Optional[str] = None,
                        worktree_branch: Optional[str] = None,
                        status_label: Optional[str] = None,
                        note: Optional[str] = None,
                        base_branch: Optional[str] = None,
                        base_sha: Optional[str] = None,
                        suite_result: Optional[dict] = None) -> str:
```

Inside the function body, after `note_line` is computed, add:

```python
    base_line = ""
    if base_branch:
        sha_label = f" @ {base_sha[:8]}" if base_sha else ""
        base_line = f"base:     {base_branch}{sha_label}\n"
    suite_line = ""
    if suite_result:
        suite_line = (
            f"suite:    {suite_result.get('passed', 0)} passed, "
            f"{suite_result.get('failed', 0)} failed, "
            f"{suite_result.get('skipped', 0)} skipped\n"
        )
```

Insert `{base_line}{suite_line}` into both return blocks (fenced and unfenced), immediately after the `{note_line}` line in each:

```python
            f"status:   {status_label}\n"
            f"{note_line}"
            f"{base_line}"
            f"{suite_line}"
            f"duration: {duration_label}\n"
```

Apply the same insertion to both `return` statements in the function (fenced-command branch and plain branch).

Update `_write_job_summary`'s signature the same way (add the three trailing optional params) and pass them through to `_format_job_summary`:

```python
def _write_job_summary(job_id: str, agent: str, story_id: Optional[str],
                       exit_code: Optional[int], duration_s: Optional[float],
                       in_tokens: int, out_tokens: int, cost_usd: float,
                       files_touched: Optional[list],
                       worktree_path: Optional[str] = None,
                       worktree_branch: Optional[str] = None,
                       status_label: Optional[str] = None,
                       note: Optional[str] = None,
                       base_branch: Optional[str] = None,
                       base_sha: Optional[str] = None,
                       suite_result: Optional[dict] = None) -> str:
    """Writes a structured completion summary for a job and returns the text."""
    os.makedirs(".synlynk/logs", exist_ok=True)
    summary = _format_job_summary(
        job_id, agent, story_id, exit_code, duration_s, in_tokens, out_tokens,
        cost_usd, files_touched, worktree_path=worktree_path, worktree_branch=worktree_branch,
        status_label=status_label, note=note, base_branch=base_branch, base_sha=base_sha,
        suite_result=suite_result,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch.py -v -k includes_base_and_suite_result`
Expected: PASS

- [ ] **Step 5: Pass the new fields from both `_write_job_summary` call sites in `jobs.py`**

Both call sites (around line 1046-1060, and the equivalent one near line 1220-1240) currently call `_pkg("_write_job_summary")(...)` positionally then with keyword args `status_label=`/`note=`. Since the gate now runs via `_apply_dispatch_gate` *after* the summary is written (Task 5/6 wired it in after `_finalize_completed_worktree_job`, which itself runs after the summary print), the summary at print-time won't yet have `suite_result`. Reorder so the gate runs *before* the summary write in both places:

At the first call site (~line 1046-1063), change the order from:

```python
            summary = _pkg("_write_job_summary")(
                job.get("id", ""), job.get("agent", ""), job.get("story_id"),
                job.get("exit_code"), duration_s, in_tokens, out_tokens, cost_usd,
                _pkg("_worktree_files_touched")(job.get("worktree_path")),
                job.get("worktree_path"), job.get("worktree_branch"),
                status_label=summary_status, note=summary_note,
            )
            print(summary, end="")
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
```

to:

```python
            if job.get("status") == "completed":
                _finalize_completed_worktree_job(job, git_state)
                _apply_dispatch_gate(job)
            summary = _pkg("_write_job_summary")(
                job.get("id", ""), job.get("agent", ""), job.get("story_id"),
                job.get("exit_code"), duration_s, in_tokens, out_tokens, cost_usd,
                _pkg("_worktree_files_touched")(job.get("worktree_path")),
                job.get("worktree_path"), job.get("worktree_branch"),
                status_label=summary_status, note=summary_note,
                base_branch=job.get("base_branch"), base_sha=job.get("base_sha"),
                suite_result=job.get("suite_result"),
            )
            print(summary, end="")
```

Apply the equivalent reordering at the second call site (~line 1220-1243) — find it via `grep -n "_write_job_summary" synlynk/jobs.py` and apply the same pattern: move the `_finalize_completed_worktree_job` + `_apply_dispatch_gate` calls before the `_write_job_summary` call, and pass `base_branch=job.get("base_branch")`, `base_sha=job.get("base_sha")`, `suite_result=job.get("suite_result")` into it.

- [ ] **Step 6: Run the full test suite**

Run: `pytest tests/ -q`
Expected: all tests pass, no regressions

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py synlynk/jobs.py tests/test_dispatch.py
git commit -m "feat(dispatch): surface base_branch/base_sha/suite_result in job summaries"
```

---

## Task 8: Integration test — two sequential dispatched jobs stack with zero conflicts

**Files:**
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the integration test**

```python
def test_sequential_dispatch_jobs_stack_with_zero_conflicts(git_worktree_repo, monkeypatch, tmp_path):
    """Simulates Task N and Task N+1 of a plan: job2 should be anchored to
    the tip left behind after job1's commit is merged, so merging job2
    produces no conflicts even though both jobs touch the same file."""
    import synlynk.dispatch as dispatch_mod
    import subprocess

    subprocess.run(["git", "checkout", "-b", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)

    class FakeProc:
        pid = 1111

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.chdir(git_worktree_repo)

    # --- Job 1 ---
    worktree1 = dispatch_mod._create_job_worktree("job-seq1", "codex")
    shared_file = os_path_join(worktree1["path"], "shared.py")
    with open(shared_file, "w") as f:
        f.write("value = 1\n")
    subprocess.run(["git", "add", "."], cwd=worktree1["path"], capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "job1: set value=1"], cwd=worktree1["path"], capture_output=True, check=True)

    # Simulate the reviewer merging job1's commit back onto the feature branch.
    subprocess.run(["git", "checkout", "feat/example"], cwd=git_worktree_repo, capture_output=True, check=True)
    merge1 = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge job1", worktree1["branch"]],
        cwd=git_worktree_repo, capture_output=True, text=True,
    )
    assert merge1.returncode == 0, merge1.stderr

    # --- Job 2, dispatched after job1 merged ---
    worktree2 = dispatch_mod._create_job_worktree("job-seq2", "codex")

    assert worktree2["base_branch"] == "feat/example"
    new_tip = subprocess.run(
        ["git", "-C", str(git_worktree_repo), "rev-parse", "feat/example"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    assert worktree2["base_sha"] == new_tip

    with open(os_path_join(worktree2["path"], "shared.py"), "w") as f:
        f.write("value = 1\nextra = 2\n")
    subprocess.run(["git", "add", "."], cwd=worktree2["path"], capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "job2: add extra=2"], cwd=worktree2["path"], capture_output=True, check=True)

    merge2 = subprocess.run(
        ["git", "merge", "--no-ff", "-m", "merge job2", worktree2["branch"]],
        cwd=git_worktree_repo, capture_output=True, text=True,
    )
    assert merge2.returncode == 0, merge2.stderr
    assert "CONFLICT" not in (merge2.stdout + merge2.stderr)


def os_path_join(*parts):
    import os
    return os.path.join(*parts)
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_dispatch.py -v -k sequential_dispatch_jobs_stack`
Expected: PASS — both merges succeed with no `CONFLICT` in output, and `worktree2["base_sha"]` equals the feature branch's tip after job1's merge

- [ ] **Step 3: Commit**

```bash
git add tests/test_dispatch.py
git commit -m "test(dispatch): integration test for zero-conflict sequential stacking"
```

---

## Task 9: Gate test — deliberately-failing worktree yields `needs_fix`, never `completed`

**Files:**
- Test: `tests/test_jobs.py`

- [ ] **Step 1: Write the test**

This exercises the full `_apply_dispatch_gate` path against a real worktree with a real failing pytest run (no mocking of `_run_dispatch_gate` itself, unlike Task 5's unit tests) to prove the parsing + status-downgrade wiring works end-to-end.

```python
def test_apply_dispatch_gate_end_to_end_with_real_failing_suite(git_worktree_repo, monkeypatch):
    import synlynk.jobs as jobs_mod
    import synlynk.dispatch as dispatch_mod
    import synlynk as sl
    import json
    import os
    import subprocess

    tests_dir = os.path.join(str(git_worktree_repo), "tests")
    os.makedirs(tests_dir, exist_ok=True)
    with open(os.path.join(tests_dir, "test_deliberate_failure.py"), "w") as f:
        f.write("def test_deliberately_fails():\n    assert 1 == 2\n")
    subprocess.run(["git", "add", "."], cwd=git_worktree_repo, capture_output=True, check=True)
    subprocess.run(["git", "commit", "-m", "seed failing test"], cwd=git_worktree_repo, capture_output=True, check=True)

    config_path = os.path.join(str(git_worktree_repo), ".synlynk", "config.json")
    os.makedirs(os.path.dirname(config_path), exist_ok=True)
    with open(config_path, "w") as f:
        json.dump({"dispatch": {"gate_suite_cmd": "python3 -m pytest tests/ -q"}}, f)

    monkeypatch.chdir(git_worktree_repo)
    monkeypatch.setattr(
        jobs_mod, "_pkg",
        lambda name, default=None: {
            "load_config": sl.load_config,
            "_run_dispatch_gate": dispatch_mod._run_dispatch_gate,
        }.get(name, default),
    )

    job = {"id": "job-realgate", "status": "completed", "worktree_path": str(git_worktree_repo)}
    jobs_mod._apply_dispatch_gate(job)

    assert job["status"] == "needs_fix"
    assert job["suite_result"]["failed"] >= 1
```

- [ ] **Step 2: Run the test**

Run: `pytest tests/test_jobs.py -v -k end_to_end_with_real_failing_suite`
Expected: PASS — `job["status"] == "needs_fix"` and `suite_result["failed"] >= 1`

- [ ] **Step 3: Run the full test suite one final time**

Run: `pytest tests/ -q`
Expected: all tests pass

- [ ] **Step 4: Commit**

```bash
git add tests/test_jobs.py
git commit -m "test(dispatch): end-to-end gate test proving a failing suite yields needs_fix"
```

---

## Final Step: Push and open PR

Once all 9 tasks are committed and `pytest tests/ -q` is green:

```bash
git push -u origin chore/dispatch-stacking-ground-truth-gate-design
gh pr create --title "feat(dispatch): stacked dispatch branches + ground-truth merge gate (Phase 1)" --body "$(cat <<'EOF'
## Summary
- Dispatch jobs now stack on the current feature branch's tip by default instead of always branching off stale mainline (config: `dispatch.stacking`, override: `--base`)
- Job worktrees anchor to the resolved base's exact tip SHA at creation time, recorded on the job record as `base_branch`/`base_sha`
- A harness-run test-suite gate (`dispatch.gate_suite_cmd`) now judges merge-eligibility from ground truth — a job with `suite_result.failed > 0` is `needs_fix`, never silently `completed`
- STALE_BASE detection flags jobs whose stacked base branch advanced before merge, recommending re-dispatch over a forced merge

Implements Phase 1 of docs/superpowers/specs/2026-07-22-dispatch-stacking-ground-truth-gate-design.md. Phase 2 (footprint locking, wave scheduling) is explicitly out of scope.

## Test Plan
- [x] All 9 plan tasks landed with passing unit/integration tests
- [x] `pytest tests/ -q` green
- [ ] First real usage: dispatch the remaining rollback-mechanism plan tasks against this mechanism and confirm zero add/add conflicts
EOF
)"
```

---

## Self-Review Notes

- **Spec coverage:** Data model (`base_branch`/`base_sha`/`suite_result` — Task 4), stacked branches (Tasks 2-3), ground-truth gate (Task 5), STALE_BASE (Task 6), config schema (Task 1), CLI surface (Task 4/7) — all covered. Phase 2 items (footprint locking, wave scheduling) intentionally absent per spec's Rollout section.
- **Placeholder scan:** No TBD/TODO markers; every step has complete code.
- **Type consistency:** `_create_job_worktree` returns `dict` from Task 3 onward everywhere it's referenced (dispatch_agent, conftest stub, both new tests) — no lingering assumption of the old string return type. `_apply_dispatch_gate(job: dict) -> None` signature is identical across Task 5's initial version and Task 6's extension (Task 6 replaces the whole function body, not a second competing definition).
