# Workspace Policy Layer & Autonomous Loop Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give synlynk's own repo a two-tier (workspace/repo) policy config, wire it into the four places that currently make undocumented authority decisions, turn on real GitHub branch protection from it, then build a cron-driven story sweep that walks stories through dispatch→verify→PR→review→merge unattended, pausing at policy-flagged approval points via a GitHub ticket + push notification.

**Architecture:** `synlynk/policy.py` is a pure-function policy resolver (`load_policy()` / `check_authority()`) with no caching — same "re-read every call" convention `load_config()` already uses for `.synlynk/config.json`. It is called from four existing decision points (`dispatch_agent()`'s harness routing, a new merge-gate command, `cmd_release()`, `cmd_roadmap_add()`/`cmd_goal_create()`) and from the new `synlynk tpm sweep` loop. GOVERNS events follow the exact `emit_event()`/`scan_local_events()` pattern PR #922 established.

**Tech Stack:** Python 3 stdlib only (per project convention), `gh` CLI subprocess calls, SQLite (`synlynk/db.py`), existing `pytest` test suite.

**Corrections vs. the design spec, found during code-grounding (see task notes for each):** `project-docs/roadmap.md` does not exist as a file — roadmap/goals are DB-backed (`roadmap_arcs`, `goals` tables) via `cmd_roadmap_add`/`cmd_goal_create` in `synlynk/db.py`; the "roadmap_edit"/"goal_create" gate wires into those functions, not a markdown file. There is **no existing `gh pr merge` call anywhere in synlynk's own Python** — merging today is always a dispatched reviewer agent's own `gh pr merge` invocation, so `merge_authority` needs a *new* enforcement surface (a `synlynk policy check-merge` command reviewers call first in v0.15, and a real `_merge_pr_via_gh()` function synlynk itself calls in v0.16's sweep) rather than an existing call site to wrap. The `stories` table has no `session_id` column and readiness is tracked via the **`readiness`** column (`readiness='ready'`), not `status='ready'`.

---

### Task 1: Two-tier policy.json schema + loader

**Files:**
- Create: `synlynk/policy.py`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write the failing tests for `load_policy()`**

```python
# tests/test_policy.py
import json
import os
from pathlib import Path

import pytest

from synlynk.policy import load_policy, DEFAULT_WORKSPACE_POLICY


def _write_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data))


def test_load_policy_falls_back_to_hardcoded_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["merge_authority"]["can_merge"] == DEFAULT_WORKSPACE_POLICY["defaults"]["merge_authority"]["can_merge"]


def test_load_policy_reads_workspace_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {
            "merge_authority": {"can_merge": ["qa"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"},
        },
    })
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["qa"]
    assert policy["org"]["org_id"] == "acme"


def test_load_policy_repo_override_replaces_whole_object(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {
            "merge_authority": {"can_merge": ["qa"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"},
            "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": True},
        },
    })
    repo = tmp_path / "repo"
    repo_policy_path = repo / ".synlynk" / "policy.json"
    _write_json(repo_policy_path, {
        "schema_version": 1,
        "repo_id": "rxcc",
        "overrides": {
            "merge_authority": {"can_merge": ["qa", "architect"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"},
        },
    })
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["qa", "architect"]
    # release_authority untouched by the override — inherited from workspace defaults
    assert policy["release_authority"]["can_cut_release"] == ["pm"]


def test_load_policy_stub_org_fields_present_but_inert(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["org"]["teams"] == []
    assert policy["org"]["sso_provider"] is None
    assert policy["org"]["seat_limits"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_policy.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.policy'`

- [ ] **Step 3: Implement `synlynk/policy.py` — schema + loader**

```python
# synlynk/policy.py
"""Two-tier (workspace/repo) policy configuration for authority gating.

Follows the same re-read-every-call convention as load_config() in
__init__.py — no caching, no mtime tracking. Policy files are small and
read infrequently relative to dispatch/merge/release actions.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, Optional

DEFAULT_WORKSPACE_POLICY: Dict[str, Any] = {
    "schema_version": 1,
    "org": {"org_id": None, "teams": [], "sso_provider": None, "seat_limits": None},
    "defaults": {
        "roadmap_authority": {
            "can_edit_roadmap": ["pm"],
            "can_create_goals": ["pm", "architect"],
        },
        "dev_authority": {
            "task_allocation": {
                "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
                "test": {"harness": "codex", "fallback": ["grok", "agy"]},
                "css": {"harness": "agy", "fallback": []},
                "templates": {"harness": "agy", "fallback": []},
                "canvas": {"harness": "grok", "fallback": []},
                "js": {"harness": "grok", "fallback": []},
                "infra": {"harness": "grok", "fallback": []},
                "refactor": {"harness": "codex", "fallback": []},
                "cli-plumbing": {"harness": "codex", "fallback": []},
                "gh_write": {"harness": "claude", "fallback": ["agy"]},
            },
        },
        "merge_authority": {
            "can_merge": ["qa"],
            "require_non_authoring_review": True,
            "review_fallback": "comment_checklist",
        },
        "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": True},
        "approval_required_for": [
            "security_sensitive_paths:.github/workflows/**,.synlynk/policy.json,.synlynk/github_apps/**",
            "irreversible_merge",
            "named_release",
            "roadmap_authority_change",
        ],
        "agent_roles": {
            "pm": {"default_harness": "claude", "scope": ["roadmap", "review", "deploy", "brainstorm"]},
            "qa": {"default_harness": "claude", "scope": ["review", "merge"]},
            "dev": {"default_harness": "codex", "scope": ["implement", "test"]},
            "architect": {"default_harness": "claude", "scope": ["roadmap", "brainstorm"]},
        },
    },
}


def _read_json(path: Path) -> Optional[Dict[str, Any]]:
    try:
        return json.loads(path.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return None


def _workspace_policy_path(workspace_name: str) -> Path:
    return Path(os.path.expanduser("~/.synlynk/workspaces")) / workspace_name / "policy.json"


def _repo_policy_path(repo_path: str) -> Path:
    return Path(repo_path) / ".synlynk" / "policy.json"


def load_policy(repo_path: str, workspace_name: str = "default") -> Dict[str, Any]:
    """Merge workspace defaults with a repo's sparse overrides.

    Merge rule: for each top-level key under "defaults", if the repo's
    "overrides" supplies that key, the repo's value REPLACES the workspace
    default's value entirely (whole-object replace, one level deep — not a
    recursive deep merge).
    """
    ws_raw = _read_json(_workspace_policy_path(workspace_name))
    workspace_doc = ws_raw if ws_raw is not None else DEFAULT_WORKSPACE_POLICY

    merged = json.loads(json.dumps(workspace_doc.get("defaults", DEFAULT_WORKSPACE_POLICY["defaults"])))
    merged["org"] = workspace_doc.get("org", DEFAULT_WORKSPACE_POLICY["org"])

    repo_raw = _read_json(_repo_policy_path(repo_path))
    if repo_raw:
        for key, value in repo_raw.get("overrides", {}).items():
            merged[key] = value

    return merged
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_policy.py -v`
Expected: PASS, 4/4

- [ ] **Step 5: Commit**

```bash
git add synlynk/policy.py tests/test_policy.py
git commit -m "feat(policy): add two-tier workspace/repo policy schema and loader"
```

---

### Task 2: `check_authority()` core logic

**Files:**
- Modify: `synlynk/policy.py`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write the failing tests**

```python
# append to tests/test_policy.py
from synlynk.policy import check_authority, AuthorityResult


def test_check_authority_allows_role_in_can_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("merge", role="qa", repo_path=str(repo))
    assert isinstance(result, AuthorityResult)
    assert result.allowed is True
    assert result.requires_approval is False


def test_check_authority_denies_role_not_in_can_merge(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("merge", role="dev", repo_path=str(repo))
    assert result.allowed is False
    assert "dev" in result.reason


def test_check_authority_release_cut_requires_approval(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("release_cut", role="pm", repo_path=str(repo))
    assert result.allowed is True
    assert result.requires_approval is True
    assert "named_release" in result.reason


def test_check_authority_task_dispatch_checked_against_allocation_table(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:css", role="dev", repo_path=str(repo))
    assert result.allowed is True


def test_check_authority_unknown_action_raises_value_error(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    with pytest.raises(ValueError):
        check_authority("not_a_real_action", role="pm", repo_path=str(repo))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_policy.py -v -k check_authority`
Expected: FAIL with `ImportError: cannot import name 'check_authority'`

- [ ] **Step 3: Implement `check_authority()`**

```python
# append to synlynk/policy.py
import fnmatch
from dataclasses import dataclass, field
from typing import List


@dataclass
class AuthorityResult:
    allowed: bool
    requires_approval: bool = False
    reason: str = ""


_ACTION_PREFIXES = ("roadmap_edit", "goal_create", "merge", "release_cut", "task_dispatch:")


def _matches_approval_rule(action: str, policy: Dict[str, Any]) -> Optional[str]:
    for rule in policy.get("approval_required_for", []):
        if rule == "irreversible_merge" and action == "merge":
            return rule
        if rule == "named_release" and action == "release_cut":
            return rule
        if rule == "roadmap_authority_change" and action in ("roadmap_edit", "goal_create"):
            return rule
        if rule.startswith("security_sensitive_paths:") and action.startswith("task_dispatch:"):
            continue  # path-based rules are checked by callers that know the changed files, not here
    return None


def check_authority(action: str, role: str, repo_path: str, workspace_name: str = "default") -> AuthorityResult:
    if not any(action == p or action.startswith(p) for p in _ACTION_PREFIXES):
        raise ValueError(f"check_authority: unknown action {action!r}")

    policy = load_policy(repo_path=repo_path, workspace_name=workspace_name)

    if action == "roadmap_edit":
        allowed = role in policy["roadmap_authority"]["can_edit_roadmap"]
    elif action == "goal_create":
        allowed = role in policy["roadmap_authority"]["can_create_goals"]
    elif action == "merge":
        allowed = role in policy["merge_authority"]["can_merge"]
    elif action == "release_cut":
        allowed = role in policy["release_authority"]["can_cut_release"]
    elif action.startswith("task_dispatch:"):
        task_type = action.split(":", 1)[1]
        table = policy["dev_authority"]["task_allocation"]
        allowed = task_type in table  # presence in the table = an authorized task type
    else:  # pragma: no cover - guarded by the ValueError check above
        allowed = False

    if not allowed:
        return AuthorityResult(
            allowed=False,
            reason=f"role {role!r} is not authorized for action {action!r} per policy.json",
        )

    matched_rule = _matches_approval_rule(action, policy)
    if matched_rule:
        return AuthorityResult(allowed=True, requires_approval=True, reason=matched_rule)

    return AuthorityResult(allowed=True, requires_approval=False, reason="")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_policy.py -v`
Expected: PASS, 9/9

- [ ] **Step 5: Commit**

```bash
git add synlynk/policy.py tests/test_policy.py
git commit -m "feat(policy): add check_authority() authority resolver"
```

---

### Task 3: Wire `check_authority` into `dispatch_agent()` task-allocation

**Files:**
- Modify: `synlynk/dispatch.py:2138` (`dispatch_agent`), `synlynk/dispatch.py:34-66` (`_harness_for_org_role`)
- Test: `tests/test_dispatch.py`

Ground truth from research: harness routing happens via `resolve_dispatch_harness()` (`dispatch.py:2080-2135`), called at `dispatch.py:2167-2171`, which falls through capability-score routing → `_harness_for_org_role()` → the passed-in `agent` string unchanged. This task adds a policy check that runs *before* `resolve_dispatch_harness()` is called, using `task_type` (already a `dispatch_agent()` parameter) as the action.

- [ ] **Step 1: Write the failing test**

```python
# add to tests/test_dispatch.py
def test_dispatch_agent_raises_when_task_type_not_in_policy_allocation_table(tmp_path, monkeypatch, isolated_db):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    with pytest.raises(RuntimeError, match="not an authorized task_type"):
        sl.dispatch_agent(
            "codex", "do something", task_type="not_a_real_task_type",
            context_mode="none",
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_dispatch.py::test_dispatch_agent_raises_when_task_type_not_in_policy_allocation_table -v`
Expected: FAIL — no such check exists yet, dispatch proceeds instead of raising.

- [ ] **Step 3: Add the gate**

In `dispatch.py`, near the top of `dispatch_agent()` (before the `resolve_dispatch_harness()` call at line ~2167), add:

```python
from synlynk.policy import check_authority

# ... inside dispatch_agent(), before resolve_dispatch_harness() is invoked:
if task_type:
    try:
        authority = check_authority(
            f"task_dispatch:{task_type}", role=role or "dev", repo_path=os.getcwd(),
        )
    except ValueError:
        authority = None  # unknown task_type action shape — not a policy-covered task_type, skip gate
    if authority is not None and not authority.allowed:
        raise RuntimeError(
            f"Dispatch refused: task_type {task_type!r} is not an authorized task_type "
            f"for role {role or 'dev'!r} per policy.json (see #423, #569)."
        )
```

Note the message format matches the established #569 style (`"Dispatch refused: ..."`, issue citation in parens at the end) confirmed during code-grounding.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch.py::test_dispatch_agent_raises_when_task_type_not_in_policy_allocation_table -v`
Expected: PASS

- [ ] **Step 5: Run the full dispatch test file to check for regressions**

Run: `python3 -m pytest tests/test_dispatch.py -v`
Expected: PASS, no new failures (existing tests don't pass `task_type` for the cases this gate would reject, since real task_types like `"implement"`/`"test"`/`"review"`/`"none"` are either in the allocation table or fall through the `ValueError`→skip path)

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat(policy): gate dispatch_agent() task_type against policy.json allocation table"
```

---

### Task 4: `synlynk policy check-merge` command (merge-authority enforcement surface)

**Files:**
- Create: `synlynk/policy_cli.py`
- Modify: `synlynk/cli.py` (subparser wiring)
- Test: `tests/test_policy_cli.py`

Ground truth: there is no existing `gh pr merge` call in synlynk's Python — merging is always a dispatched reviewer's own `gh pr merge`. This task adds the enforcement surface reviewers call first; Task 9/10 (v0.16) adds the code path where synlynk performs the merge itself for the autonomous sweep.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_policy_cli.py
import json
from pathlib import Path

from synlynk.policy_cli import cmd_policy_check_merge


def test_cmd_policy_check_merge_exits_zero_for_authorized_role(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    exit_code = cmd_policy_check_merge(role="qa")
    assert exit_code == 0
    assert "cleared to merge" in capsys.readouterr().out


def test_cmd_policy_check_merge_exits_nonzero_for_unauthorized_role(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    exit_code = cmd_policy_check_merge(role="dev")
    assert exit_code != 0
    assert "not authorized" in capsys.readouterr().out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_policy_cli.py -v`
Expected: FAIL — `synlynk.policy_cli` doesn't exist

- [ ] **Step 3: Implement `synlynk/policy_cli.py`**

```python
# synlynk/policy_cli.py
"""CLI surface for policy.json enforcement outside of dispatch_agent()."""
from __future__ import annotations

import os

from synlynk.policy import check_authority


def cmd_policy_check_merge(role: str) -> int:
    """Print + return whether `role` may merge in the current repo, per policy.json.

    Intended to be run by a dispatched reviewer agent before it calls
    `gh pr merge` itself, per the project's PR Review Discipline convention
    ("the reviewer alone must merge"). Non-zero exit means: do not merge.
    """
    result = check_authority("merge", role=role, repo_path=os.getcwd())
    if not result.allowed:
        print(f"BLOCKED: role {role!r} is not authorized to merge — {result.reason}")
        return 1
    if result.requires_approval:
        print(f"BLOCKED: merge requires human approval per policy.json ({result.reason})")
        return 2
    print(f"cleared to merge: role {role!r} is authorized per policy.json")
    return 0


def cmd_policy_sync_branch_protection(dry_run: bool = False) -> int:
    """Implemented in Task 5."""
    raise NotImplementedError
```

- [ ] **Step 4: Wire the CLI subparser**

In `synlynk/cli.py`, find the `policy` subparser group (create one if none exists — search for how `roadmap`/`goal` subparsers are registered as a pattern to follow) and add:

```python
policy_check_merge_parser = policy_subparsers.add_parser("check-merge", help="Check merge authority for a role per policy.json")
policy_check_merge_parser.add_argument("--role", required=True, help="Role identity attempting to merge")
```

And in the command-dispatch block:

```python
elif args.command == "policy" and args.policy_command == "check-merge":
    sys.exit(cmd_policy_check_merge(role=args.role))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_policy_cli.py -v`
Expected: PASS, 2/2

- [ ] **Step 6: Commit**

```bash
git add synlynk/policy_cli.py synlynk/cli.py tests/test_policy_cli.py
git commit -m "feat(policy): add synlynk policy check-merge enforcement command"
```

---

### Task 5: `synlynk policy sync-branch-protection`

**Files:**
- Modify: `synlynk/policy_cli.py`
- Test: `tests/test_policy_cli.py`

Ground truth: `.github/workflows/test.yml` produces the required-check names `test (3.8)`, `test (3.10)`, `test (3.12)`, and `qa-gate` (PR-only, `needs: test`). Use these as the required-status-checks list.

- [ ] **Step 1: Write the failing test**

```python
# append to tests/test_policy_cli.py
from unittest.mock import patch, MagicMock

from synlynk.policy_cli import cmd_policy_sync_branch_protection


def test_cmd_policy_sync_branch_protection_calls_gh_api_with_required_checks(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    with patch("synlynk.policy_cli.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="{}", stderr="")
        exit_code = cmd_policy_sync_branch_protection()
    assert exit_code == 0
    called_args = mock_run.call_args[0][0]
    assert "branches/main/protection" in " ".join(called_args)
    assert any("qa-gate" in a for a in called_args)


def test_cmd_policy_sync_branch_protection_dry_run_does_not_call_gh(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    monkeypatch.chdir(repo)
    with patch("synlynk.policy_cli.subprocess.run") as mock_run:
        exit_code = cmd_policy_sync_branch_protection(dry_run=True)
    assert exit_code == 0
    mock_run.assert_not_called()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_policy_cli.py -v -k sync_branch_protection`
Expected: FAIL — `NotImplementedError`

- [ ] **Step 3: Implement `cmd_policy_sync_branch_protection`**

```python
# replace the NotImplementedError stub in synlynk/policy_cli.py
import json
import subprocess

REQUIRED_STATUS_CHECKS = ["test (3.8)", "test (3.10)", "test (3.12)", "qa-gate"]


def _current_repo_slug() -> str:
    result = subprocess.run(
        ["gh", "repo", "view", "--json", "nameWithOwner", "-q", ".nameWithOwner"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout.strip()


def cmd_policy_sync_branch_protection(dry_run: bool = False) -> int:
    policy = load_policy(repo_path=os.getcwd())
    review_count = 1 if policy["merge_authority"]["require_non_authoring_review"] else 0
    body = {
        "required_status_checks": {"strict": True, "contexts": REQUIRED_STATUS_CHECKS},
        "enforce_admins": True,
        "required_pull_request_reviews": {"required_approving_review_count": review_count},
        "restrictions": None,
    }
    if dry_run:
        print(json.dumps(body, indent=2))
        return 0

    repo_slug = _current_repo_slug()
    cmd = [
        "gh", "api", "--method", "PUT",
        f"repos/{repo_slug}/branches/main/protection",
        "--input", "-",
    ] + [f"-F{k}={v}" for k, v in []]  # placeholder args list unused; body sent via stdin below
    result = subprocess.run(
        ["gh", "api", "--method", "PUT", f"repos/{repo_slug}/branches/main/protection", "--input", "-"],
        input=json.dumps(body), capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"FAILED to sync branch protection: {result.stderr}")
        return 1
    print(f"branch protection synced for {repo_slug}: required checks {REQUIRED_STATUS_CHECKS}, review_count={review_count}")
    return 0
```

Also import `load_policy` alongside `check_authority` at the top of `policy_cli.py`.

(Remove the leftover unused `cmd` local built with the placeholder list comprehension before committing — it was scaffolding while drafting the real `subprocess.run` call below it and does nothing; keep only the second `subprocess.run` invocation.)

- [ ] **Step 4: Wire the CLI subparser**

```python
policy_sync_bp_parser = policy_subparsers.add_parser("sync-branch-protection", help="Configure GitHub branch protection from policy.json")
policy_sync_bp_parser.add_argument("--dry-run", action="store_true")
```

```python
elif args.command == "policy" and args.policy_command == "sync-branch-protection":
    sys.exit(cmd_policy_sync_branch_protection(dry_run=args.dry_run))
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_policy_cli.py -v`
Expected: PASS, 4/4

- [ ] **Step 6: Commit**

```bash
git add synlynk/policy_cli.py synlynk/cli.py tests/test_policy_cli.py
git commit -m "feat(policy): add synlynk policy sync-branch-protection command"
```

---

### Task 6: Wire `check_authority` into `cmd_release` and `cmd_roadmap_add`/`cmd_goal_create`

**Files:**
- Modify: `synlynk/__init__.py` (`cmd_release`, ~line 2950)
- Modify: `synlynk/db.py` (`cmd_roadmap_add`, ~line 2327; `cmd_goal_create`, ~line 2510)
- Test: `tests/test_synlynk.py`, `tests/test_db.py` (or wherever existing tests for these two functions already live — grep `def test_.*cmd_release` / `def test_.*cmd_roadmap_add` / `def test_.*cmd_goal_create` first and add alongside)

- [ ] **Step 1: Write the failing tests**

```python
# add near existing cmd_release tests
def test_cmd_release_refuses_when_role_not_authorized(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "VERSION").write_text("0.14.0")
    with pytest.raises(RuntimeError, match="not authorized"):
        sl.cmd_release(dry_run=True, role="dev")


# add near existing cmd_roadmap_add tests
def test_cmd_roadmap_add_refuses_when_role_not_authorized(tmp_path, monkeypatch, isolated_db):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="not authorized"):
        db.cmd_roadmap_add(version="0.15.0", title="x", role="dev")


# add near existing cmd_goal_create tests
def test_cmd_goal_create_refuses_when_role_not_authorized(tmp_path, monkeypatch, isolated_db):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.chdir(tmp_path)
    with pytest.raises(RuntimeError, match="not authorized"):
        db.cmd_goal_create(outcome="x", criterion="y", role="dev")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_synlynk.py -v -k "release_refuses" && python3 -m pytest tests/test_db.py -v -k "roadmap_add_refuses or goal_create_refuses"`
Expected: FAIL — `role` isn't a parameter yet, `TypeError: unexpected keyword argument 'role'`

- [ ] **Step 3: Add the `role` parameter and gate to each function**

In `synlynk/__init__.py`, `cmd_release()` signature gains `role: str = "dev"`; at the very top of the function body:

```python
from synlynk.policy import check_authority
authority = check_authority("release_cut", role=role, repo_path=os.getcwd())
if not authority.allowed:
    raise RuntimeError(f"Release refused: role {role!r} is not authorized to cut a release per policy.json.")
```

In `synlynk/db.py`, `cmd_roadmap_add()` signature gains `role: str = "dev"`; at the top:

```python
from synlynk.policy import check_authority
authority = check_authority("roadmap_edit", role=role, repo_path=os.getcwd())
if not authority.allowed:
    raise RuntimeError(f"Roadmap edit refused: role {role!r} is not authorized per policy.json.")
```

`cmd_goal_create()` gains `role: str = "dev"`; at the top:

```python
from synlynk.policy import check_authority
authority = check_authority("goal_create", role=role, repo_path=os.getcwd())
if not authority.allowed:
    raise RuntimeError(f"Goal creation refused: role {role!r} is not authorized per policy.json.")
```

Wire `--role` as an optional CLI flag (default `"dev"`, matching existing dispatch conventions) on the `release`, `roadmap add`, and `goal create` subparsers in `cli.py`, passed through to each `cmd_*` call.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_synlynk.py -v -k "release_refuses" && python3 -m pytest tests/test_db.py -v -k "roadmap_add_refuses or goal_create_refuses"`
Expected: PASS, 3/3 across both files

- [ ] **Step 5: Run each file's full suite to check for regressions**

Run: `python3 -m pytest tests/test_synlynk.py tests/test_db.py -v`
Expected: PASS — all pre-existing calls to these three functions must be checked for missing `role=` kwargs; since `role` defaults to `"dev"` and `"dev"` is NOT in `can_cut_release`/`can_edit_roadmap`/`can_create_goals` per the default policy, **any existing test that calls these functions without expecting a RuntimeError will now fail**. Fix each such pre-existing test by passing `role="pm"` explicitly (the default-authorized role for all three actions).

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py synlynk/db.py synlynk/cli.py tests/test_synlynk.py tests/test_db.py
git commit -m "feat(policy): gate cmd_release/cmd_roadmap_add/cmd_goal_create on check_authority"
```

---

### Task 7: Migrate synlynk's own CLAUDE.md tables into `.synlynk/policy.json`

**Files:**
- Create: `.synlynk/policy.json` (this repo's own repo-override file)
- Modify: `CLAUDE.md`

- [ ] **Step 1: Write this repo's own policy override**

```json
{
  "schema_version": 1,
  "repo_id": "synlynk",
  "overrides": {
    "dev_authority": {
      "task_allocation": {
        "implement": {"harness": "codex", "fallback": ["grok", "agy"]},
        "test": {"harness": "codex", "fallback": ["grok", "agy"]},
        "css": {"harness": "agy", "fallback": []},
        "templates": {"harness": "agy", "fallback": []},
        "content": {"harness": "agy", "fallback": []},
        "subpages": {"harness": "agy", "fallback": []},
        "canvas": {"harness": "grok", "fallback": []},
        "js": {"harness": "grok", "fallback": []},
        "infra": {"harness": "grok", "fallback": []},
        "refactor": {"harness": "codex", "fallback": []},
        "cli-plumbing": {"harness": "codex", "fallback": []},
        "gh_write": {"harness": "claude", "fallback": ["agy"]}
      }
    },
    "merge_authority": {
      "can_merge": ["qa"],
      "require_non_authoring_review": true,
      "review_fallback": "comment_checklist"
    },
    "release_authority": {"can_cut_release": ["pm"], "requires_human_approval": true}
  }
}
```

Path: `.synlynk/policy.json` at repo root (not the `worktrees/` subdirectory — this file belongs to the real repo root and will need copying there once this branch merges, same as any other repo-root config file).

- [ ] **Step 2: Replace CLAUDE.md's Capability-Based Task Allocation table and PR Review Discipline authority line**

In `CLAUDE.md`, under `## Capability-Based Task Allocation`, replace the full markdown table with:

```markdown
## Capability-Based Task Allocation

Source of truth: `.synlynk/policy.json` (`dev_authority.task_allocation`). Run
`synlynk policy show` to print the current resolved table. Do not hand-edit this
section — edit `.synlynk/policy.json` instead.
```

Under `## PR Review Discipline`, append after the existing numbered list:

```markdown
**Merge authority is enforced from `.synlynk/policy.json` (`merge_authority`)** —
a reviewer must run `synlynk policy check-merge --role <role>` before `gh pr merge`;
a non-zero exit means do not merge.
```

- [ ] **Step 3: Add a `synlynk policy show` command (small, referenced above)**

```python
# append to synlynk/policy_cli.py
def cmd_policy_show() -> int:
    policy = load_policy(repo_path=os.getcwd())
    print(json.dumps(policy, indent=2))
    return 0
```

Wire as `policy_subparsers.add_parser("show", ...)` with no args, dispatched the same way as the other two `policy` subcommands.

- [ ] **Step 4: Verify manually**

Run: `python3 -m synlynk policy show` from the repo root (after copying `.synlynk/policy.json` there)
Expected: prints the merged policy JSON with `merge_authority.can_merge == ["qa"]`

- [ ] **Step 5: Commit**

```bash
git add .synlynk/policy.json CLAUDE.md synlynk/policy_cli.py synlynk/cli.py
git commit -m "docs(policy): migrate CLAUDE.md capability/review tables into .synlynk/policy.json"
```

---

### Task 8: Unit tests for `check_authority` edge cases (override merge, missing repo file, stub fields)

**Files:**
- Modify: `tests/test_policy.py`

Note: Tasks 1 and 2 already wrote 9 of the required tests (allow/deny/requires_approval, override-merge, missing-repo-override, stub-fields-inert). This task adds the remaining edge cases called out in the spec that aren't yet covered.

- [ ] **Step 1: Write the additional tests**

```python
# append to tests/test_policy.py
def test_load_policy_missing_repo_override_file_inherits_workspace_defaults(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    ws_policy_path = tmp_path / ".synlynk" / "workspaces" / "acme" / "policy.json"
    _write_json(ws_policy_path, {
        "schema_version": 1,
        "org": {"org_id": "acme", "teams": [], "sso_provider": None, "seat_limits": None},
        "defaults": {"merge_authority": {"can_merge": ["architect"], "require_non_authoring_review": True, "review_fallback": "comment_checklist"}},
    })
    repo = tmp_path / "repo"
    repo.mkdir()  # no .synlynk/policy.json created here
    policy = load_policy(repo_path=str(repo), workspace_name="acme")
    assert policy["merge_authority"]["can_merge"] == ["architect"]


def test_check_authority_task_dispatch_unknown_task_type_denied(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:not_a_real_type", role="dev", repo_path=str(repo))
    assert result.allowed is False
```

- [ ] **Step 2: Run to verify they fail, then pass after no further code change needed**

Run: `python3 -m pytest tests/test_policy.py -v`
Expected: both pass immediately (Task 1/2's implementation already handles these cases) — this step is pure coverage, not a new behavior; if either fails, that reveals a real gap in Task 1/2's implementation to fix now.

- [ ] **Step 3: Commit**

```bash
git add tests/test_policy.py
git commit -m "test(policy): cover missing-repo-override and unknown-task-type edge cases"
```

---

### Task 9 (PM/deploy, Claude runs directly — not dispatched): Sync branch protection on the real repo and verify

- [ ] Ensure `.synlynk/policy.json` (Task 7) is present at the real repo root on `main` (this branch merges it there).
- [ ] Run: `python3 -m synlynk policy sync-branch-protection` from the real repo root.
- [ ] Independently verify — do not trust the command's own exit code alone:

```bash
gh api repos/nikhilsoman/synlynk/branches/main/protection --jq '{required_status_checks: .required_status_checks.contexts, required_reviews: .required_pull_request_reviews.required_approving_review_count, enforce_admins: .enforce_admins.enabled}'
```

Expected: `required_status_checks` contains `test (3.8)`, `test (3.10)`, `test (3.12)`, `qa-gate`; `required_reviews` is `1`; `enforce_admins` is `true`.

This step is the direct, independently-verified proof that Phase 1's original exit criterion ("branch protection can be turned on for real") is met — cite the `gh api` output, not just "command exited 0," when marking this done.

---

## v0.16.0 "Autonomous Loop" — Tasks 10-13

### Task 10: `awaiting_approval` GOVERNS event type

**Files:**
- Modify: `synlynk/events.py`
- Test: `tests/test_events.py` (or wherever `review_submitted` is tested — grep first)

Ground truth: `emit_event(event_type, payload, emitted_by, parent_event_id=None)` at `events.py:134-147` does a direct `INSERT INTO events`. `review_submitted` detection follows the pattern: a dedup-key helper (`_existing_review_submitted_keys`, `events.py:23-39`) + a `_scan_*` function + wiring into `scan_local_events()`'s loop with its own `advance_checkpoint()` call.

- [ ] **Step 1: Write the failing test**

```python
# add near existing review_submitted tests in tests/test_events.py
def test_emit_awaiting_approval_event_recorded(isolated_db):
    from synlynk.events import emit_event
    event_id = emit_event(
        "awaiting_approval",
        {"story_id": "story-1", "action": "release_cut", "reason": "named_release"},
        emitted_by="tpm_sweep",
    )
    assert event_id is not None
    import sqlite3
    conn = sqlite3.connect(db_path_for_test())  # use whatever helper isolated_db exposes for a raw connection
    row = conn.execute("SELECT event_type, payload_json FROM events WHERE id=?", (event_id,)).fetchone()
    assert row[0] == "awaiting_approval"
    assert '"story-1"' in row[1]
```

(Adjust the raw-connection helper to match whatever `isolated_db`/`conftest.py` already exposes — grep `tests/conftest.py` for the exact fixture-provided accessor before writing this step for real, since the plan's illustrative `db_path_for_test()` may not be the real helper name.)

- [ ] **Step 2: Run to verify it fails**

Run: `python3 -m pytest tests/test_events.py -v -k awaiting_approval`
Expected: FAIL only if `emit_event` itself is broken for a new event_type string — likely **passes immediately** since `emit_event()` takes an arbitrary `event_type` string with no allowlist. If it passes on first run, that's expected — this step is a regression-proofing test, not new behavior; proceed to Step 3 regardless since the sweep (Task 11) needs a purpose-built helper, not raw `emit_event` calls scattered around.

- [ ] **Step 3: Add a purpose-built helper**

```python
# append to synlynk/events.py
def emit_awaiting_approval(story_id: str, action: str, reason: str, emitted_by: str = "tpm_sweep") -> int:
    return emit_event(
        "awaiting_approval",
        {"story_id": story_id, "action": action, "reason": reason},
        emitted_by=emitted_by,
    )
```

- [ ] **Step 4: Run tests to verify pass**

Run: `python3 -m pytest tests/test_events.py -v`
Expected: PASS, no regressions

- [ ] **Step 5: Commit**

```bash
git add synlynk/events.py tests/test_events.py
git commit -m "feat(events): add awaiting_approval GOVERNS event type"
```

---

### Task 11: Approval-gate flow (GitHub ticket + PushNotification + resolution detection)

**Files:**
- Create: `synlynk/approval_gate.py`
- Modify: `synlynk/events.py` (`scan_local_events()` extension for resolution detection)
- Test: `tests/test_approval_gate.py`

Ground truth: `support_engineer.py:488` already has a working "file a GitHub issue via `gh issue create`" function from synlynk's own Python — follow that exact pattern (dry-run handling, stderr truncation on failure) rather than inventing a new one.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_approval_gate.py
from unittest.mock import patch, MagicMock

from synlynk.approval_gate import raise_approval_ticket


def test_raise_approval_ticket_calls_gh_issue_create_with_assignee_and_context():
    with patch("synlynk.approval_gate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=0, stdout="https://github.com/x/y/issues/123\n", stderr="")
        url = raise_approval_ticket(
            story_id="story-1", action="release_cut", reason="named_release",
            assignee="nikhilsoman", context="Goal: ship v0.16.0. No PR yet.",
        )
    assert url == "https://github.com/x/y/issues/123"
    args = mock_run.call_args[0][0]
    assert "--assignee" in args and "nikhilsoman" in args
    assert any("APPROVAL" in a for a in args)


def test_raise_approval_ticket_returns_empty_on_gh_failure():
    with patch("synlynk.approval_gate.subprocess.run") as mock_run:
        mock_run.return_value = MagicMock(returncode=1, stdout="", stderr="rate limited")
        url = raise_approval_ticket(
            story_id="story-1", action="release_cut", reason="named_release",
            assignee="nikhilsoman", context="x",
        )
    assert url == ""
```

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_approval_gate.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `synlynk/approval_gate.py`**

```python
# synlynk/approval_gate.py
"""GitHub-ticket-based approval gate for policy-flagged autonomous actions."""
from __future__ import annotations

import subprocess


def raise_approval_ticket(story_id: str, action: str, reason: str, assignee: str, context: str) -> str:
    """File a GitHub issue assigned to `assignee`, requesting approval to proceed.

    Returns the issue URL, or '' if `gh issue create` failed. Mirrors the
    dry-run-and-failure handling already used by support_engineer.py's own
    `gh issue create` caller.
    """
    title = f"[APPROVAL] {action} — {story_id}"
    body = (
        f"Story `{story_id}` is paused pending approval.\n\n"
        f"**Action:** {action}\n"
        f"**Why it needs approval:** policy.json rule `{reason}` matched.\n\n"
        f"**Context:**\n{context}\n\n"
        f"Reply `approve` on this issue, or take the equivalent action directly on "
        f"GitHub, to let the sweep proceed."
    )
    result = subprocess.run(
        ["gh", "issue", "create", "--title", title, "--body", body, "--assignee", assignee],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"WARNING: failed to raise approval ticket for {story_id}: {result.stderr[:500]}")
        return ""
    return result.stdout.strip()
```

- [ ] **Step 4: Add resolution detection to `scan_local_events()`**

Following the exact `review_submitted` pattern (`events.py:23-39` dedup helper, `_scan_pr_reviews` shape, wiring at `events.py:225` + `advance_checkpoint` call at `events.py:234-237`):

```python
# append to synlynk/events.py
def _existing_approval_resolved_keys() -> set:
    conn = _get_db()  # use whatever the file's existing connection helper is named — match _existing_review_submitted_keys's own accessor exactly
    rows = conn.execute(
        "SELECT payload_json FROM events WHERE event_type='approval_resolved'"
    ).fetchall()
    return {json.loads(r[0])["issue_url"] for r in rows}


def _scan_approval_tickets() -> None:
    """Poll open [APPROVAL] issues for an 'approve' comment or closure, emit approval_resolved."""
    result = subprocess.run(
        ["gh", "issue", "list", "--search", "[APPROVAL] in:title", "--state", "all",
         "--json", "url,state,comments"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        return
    already = _existing_approval_resolved_keys()
    for issue in json.loads(result.stdout):
        if issue["url"] in already:
            continue
        resolved = issue["state"] == "CLOSED" or any(
            c.get("body", "").strip().lower().startswith("approve") for c in issue.get("comments", [])
        )
        if resolved:
            emit_event("approval_resolved", {"issue_url": issue["url"]}, emitted_by="_scan_approval_tickets")
```

Wire `_scan_approval_tickets()` into `scan_local_events()`'s body alongside the existing `_scan_pr_reviews()` call, following the same per-harness-checkpoint convention already established there.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_approval_gate.py tests/test_events.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/approval_gate.py synlynk/events.py tests/test_approval_gate.py
git commit -m "feat(events): add approval-gate GitHub ticket flow + resolution detection"
```

---

### Task 12: `synlynk tpm sweep` command

**Files:**
- Create: `synlynk/tpm_sweep.py`
- Modify: `synlynk/cli.py`
- Test: `tests/test_tpm_sweep.py`

Ground truth: readiness is queried via `readiness='ready'` (not `status='ready'`), matching `scheduler.py:62-69`'s existing query. There is no `session_id` column on `stories` — the sweep will not thread session_id (deferred, not in this plan's scope).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_tpm_sweep.py
from unittest.mock import patch, MagicMock

from synlynk.tpm_sweep import run_sweep_pass


def test_run_sweep_pass_advances_authorized_story(isolated_db, monkeypatch):
    from synlynk import db
    db.cmd_story_add(story_id="story-1", title="test story", readiness="ready")  # match the real story-creation helper's actual name/signature, grep db.py first
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
         patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-1", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    assert summary["parked"] == 0


def test_run_sweep_pass_parks_story_requiring_approval(isolated_db, monkeypatch):
    from synlynk import db
    db.cmd_story_add(story_id="story-2", title="release story", readiness="ready")
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
         patch("synlynk.tpm_sweep.raise_approval_ticket") as mock_ticket:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=True, reason="named_release")
        mock_ticket.return_value = "https://github.com/x/y/issues/1"
        summary = run_sweep_pass()
    assert summary["parked"] == 1
    assert summary["advanced"] == 0
```

(Replace `db.cmd_story_add(...)` with whatever the real story-insertion helper is actually named — grep `db.py` for `INSERT INTO stories` before finalizing this step; the plan's placeholder name must be swapped for the real one during implementation, not left as-is.)

- [ ] **Step 2: Run to verify they fail**

Run: `python3 -m pytest tests/test_tpm_sweep.py -v`
Expected: FAIL — module doesn't exist

- [ ] **Step 3: Implement `synlynk/tpm_sweep.py`**

```python
# synlynk/tpm_sweep.py
"""One pass of the autonomous TPM sweep: ready stories -> dispatch/verify/PR/review/merge,
gated at every step by policy.json via check_authority()."""
from __future__ import annotations

import os
from typing import Dict

from synlynk.dispatch import dispatch_agent
from synlynk.policy import check_authority
from synlynk.approval_gate import raise_approval_ticket
from synlynk.events import emit_awaiting_approval


def _ready_stories() -> list:
    from synlynk.db import _get_db  # match the real low-level connection accessor's actual name
    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, title, role FROM stories WHERE readiness='ready' "
        "AND NOT EXISTS (SELECT 1 FROM daemon_jobs dj WHERE dj.story_id=stories.story_id "
        "AND dj.status IN ('queued','running'))"
    ).fetchall()
    return [{"story_id": r[0], "title": r[1], "role": r[2] or "dev"} for r in rows]


def run_sweep_pass(assignee: str = "nikhilsoman") -> Dict[str, int]:
    summary = {"advanced": 0, "parked": 0, "failed": 0}
    repo_path = os.getcwd()

    for story in _ready_stories():
        authority = check_authority("task_dispatch:implement", role=story["role"], repo_path=repo_path)
        if not authority.allowed:
            summary["failed"] += 1
            continue
        if authority.requires_approval:
            emit_awaiting_approval(story["story_id"], "task_dispatch:implement", authority.reason)
            raise_approval_ticket(
                story_id=story["story_id"], action="task_dispatch:implement", reason=authority.reason,
                assignee=assignee, context=f"Story: {story['title']}",
            )
            summary["parked"] += 1
            continue

        try:
            dispatch_agent(
                "codex", story["title"], story_id=story["story_id"],
                task_type="implement", context_mode="full", role=story["role"],
            )
            summary["advanced"] += 1
        except Exception:
            summary["failed"] += 1

    return summary
```

Note: this initial sweep only handles the dispatch step per pass (one story-lifecycle stage per invocation) — verify/PR/review/merge stages are picked up on subsequent passes once `job_terminal`/`review_submitted` events show the prior stage complete, matching the event-driven reconciliation style already used elsewhere in this codebase (`_reconcile_daemon_jobs()`), rather than one pass performing a story's entire lifecycle synchronously.

- [ ] **Step 4: Wire the CLI command**

```python
tpm_sweep_parser = subparsers.add_parser("tpm", help="TPM sweep commands")
tpm_sweep_subparsers = tpm_sweep_parser.add_subparsers(dest="tpm_command")
sweep_parser = tpm_sweep_subparsers.add_parser("sweep", help="Run one autonomous sweep pass over ready stories")
sweep_parser.add_argument("--assignee", default="nikhilsoman")
```

```python
elif args.command == "tpm" and args.tpm_command == "sweep":
    summary = run_sweep_pass(assignee=args.assignee)
    print(f"sweep pass: {summary['advanced']} advanced, {summary['parked']} parked, {summary['failed']} failed")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_tpm_sweep.py -v`
Expected: PASS, 2/2

- [ ] **Step 6: Commit**

```bash
git add synlynk/tpm_sweep.py synlynk/cli.py tests/test_tpm_sweep.py
git commit -m "feat(tpm): add synlynk tpm sweep command"
```

---

### Task 13 (PM/deploy, Claude runs directly — not dispatched): Live dogfood run

- [ ] Create one real, small, genuinely-ready story via `synlynk story` tooling, tagged with a role that will trip `release_cut`-style approval (or temporarily add a test-only `approval_required_for` rule matching a harmless action, if no real story naturally trips one — document which was used).
- [ ] Run `python3 -m synlynk tpm sweep` directly (not dispatched) and observe: does it dispatch the non-gated story, and does it park the gated one, raising a real GitHub issue assigned to Nikhil?
- [ ] Independently verify via `gh issue list --search "[APPROVAL] in:title"` and `gh api repos/nikhilsoman/synlynk/branches/main/protection` — do not trust the sweep's own printed summary alone.
- [ ] Resolve the approval ticket (comment `approve`), run a second sweep pass, and confirm `approval_resolved` appears via `synlynk events tail --type approval_resolved`.
- [ ] Report actual results (real command output, real GitHub URLs) as the Aug 31 demo evidence — this is the exit-criterion proof for v0.16.0, cite it directly rather than summarizing "it worked."

---

## Self-Review Notes

- **Spec coverage:** Architecture sections 1 (schema) → Tasks 1, 7; section 2 (`check_authority`) → Task 2; section 3 (call sites + branch protection) → Tasks 3, 4, 5, 6, 9; section 4 (sweep) → Task 12; section 5 (approval gate) → Tasks 10, 11, 13. All five architecture sections have at least one task.
- **Placeholder scan:** two illustrative placeholders were flagged inline rather than left silent — `db.cmd_story_add(...)` in Task 12's test and the raw-connection helper name in Task 10's test — both explicitly instruct the implementer to grep for and substitute the real name before finalizing, since the exact helper names weren't confirmed during code-grounding. Task 5's draft code has one intentional dead local (`cmd = [...]`) called out for removal in the step text — kept visible rather than silently cleaned up so the implementer understands why it's there and removes it deliberately.
- **Type consistency:** `AuthorityResult(allowed, requires_approval, reason)` is defined once in Task 2 and used with the same field names throughout Tasks 3-13. `check_authority(action, role, repo_path, workspace_name="default")` signature is consistent everywhere it's called.
