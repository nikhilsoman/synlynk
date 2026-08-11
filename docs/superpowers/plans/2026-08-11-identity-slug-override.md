# Identity Slug Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a repo's `.synlynk/config.json` declare an `identity_slug` that overrides the directory-basename-derived slug used when provisioning GitHub App role identities (`synlynk identity init --role <role>`).

**Architecture:** Add `identity_slug: None` to the config schema defaults in `load_config()` (`synlynk/__init__.py`). Change `_resolve_project_slug()` (`synlynk/team.py`) to check this config value first via the module's existing `_pkg()` cross-module accessor (avoids a circular import — `team.py` is imported *by* `synlynk/__init__.py`, so it can't `from synlynk import load_config` directly), and fall through to the existing git-root/cwd-basename logic when unset. No other function changes — every other call site (`_build_app_manifest_url`, `_truncate_app_name`, `cmd_identity_init_role`) already reaches the slug exclusively through `_resolve_project_slug()`.

**Tech Stack:** Python 3, pytest, `monkeypatch`/`tmp_path` fixtures (existing patterns in `tests/test_identity_init_role.py`).

**Spec:** `docs/superpowers/specs/2026-08-11-identity-slug-override-design.md`

---

## Context for the implementer

This is a synlynk repo (single-file-style CLI split across `synlynk/*.py` modules, no build step). `synlynk/team.py` avoids a circular import with `synlynk/__init__.py` by calling a helper `_pkg(name, default=None)` (defined at the top of `team.py`) instead of importing `synlynk` functions directly — e.g. `_pkg("_docs_dir")()` is used in `get_mode()`. You must follow this same pattern to call `load_config()` from inside `team.py`; a direct `from synlynk import load_config` at module level would fail because `synlynk/__init__.py` imports `team.py` before `team.py` would even exist to import back from.

Run the full test suite via `pytest tests/ -x -q` from the repo root. It currently passes (1867 passed, 2 skipped as of the last full run on this branch's base).

---

### Task 1: Add `identity_slug` to config schema defaults

**Files:**
- Modify: `synlynk/__init__.py:1525-1557` (the `defaults` dict inside `load_config()`)

- [ ] **Step 1: Add the new default field**

In `synlynk/__init__.py`, inside `load_config()`, the `defaults` dict currently has this block (around line 1538-1542):

```python
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "project_docs_dir": "project-docs",
```

Change it to:

```python
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "identity_slug": None,
        "project_docs_dir": "project-docs",
```

No other change is needed in `load_config()` — the existing merge loop (`for key, val in defaults.items(): if key not in config: config[key] = val`, a few lines below) already backfills any missing key from `defaults` into whatever is loaded from `.synlynk/config.json`, so `identity_slug` will default to `None` for every repo that doesn't set it.

- [ ] **Step 2: Verify by hand**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore-identity-slug-override
python3 -c "import synlynk; print(synlynk.load_config()['identity_slug'])"
```

Expected output: `None`

- [ ] **Step 3: Commit**

```bash
git add synlynk/__init__.py
git commit -m "feat: add identity_slug field to config schema defaults"
```

---

### Task 2: Make `_resolve_project_slug()` read `identity_slug` first (TDD)

**Files:**
- Modify: `synlynk/team.py:107-121` (`_resolve_project_slug()`)
- Test: `tests/test_identity_init_role.py`

- [ ] **Step 1: Write the failing tests**

Open `tests/test_identity_init_role.py`. Find `test_build_app_manifest_url_resolves_project_from_git_root_and_caps_name_length` (around line 131) — use it as your pattern reference for `tmp_path`/`monkeypatch.chdir`/`git init` setup. Add these two new test functions directly after it (before `test_cmd_identity_init_role_noops_if_already_provisioned`):

```python
def test_resolve_project_slug_uses_identity_slug_override(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config_dir = tmp_path / ".synlynk"
    config_dir.mkdir()
    (config_dir / "config.json").write_text(
        json.dumps({"identity_slug": "vdowrx"}) + "\n"
    )

    assert team_mod._resolve_project_slug() == "vdowrx"


def test_resolve_project_slug_falls_back_without_identity_slug(tmp_path, monkeypatch):
    repo_dir = tmp_path / "cc-videoreframing"
    repo_dir.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo_dir, check=True)
    monkeypatch.chdir(repo_dir)

    assert team_mod._resolve_project_slug() == "cc-videoreframing"
```

These use `team_mod` (already imported at the top of the file as `import synlynk.team as team_mod`) and `json`/`subprocess` (both already imported at the top of the file — verify with `head -10 tests/test_identity_init_role.py` before writing if unsure).

- [ ] **Step 2: Run the tests to verify they fail**

Run: `pytest tests/test_identity_init_role.py -k resolve_project_slug -v`

Expected: both FAIL. `test_resolve_project_slug_uses_identity_slug_override` fails because `_resolve_project_slug()` doesn't read `identity_slug` yet (it'll return `_role_slug(os.path.basename(tmp_path))` instead of `"vdowrx"`). `test_resolve_project_slug_falls_back_without_identity_slug` should currently PASS already (it's a regression guard for existing behavior) — if it fails, stop and investigate before proceeding; do not write Task 2's implementation to make a pre-existing regression test pass by accident.

- [ ] **Step 3: Implement the minimal change**

In `synlynk/team.py`, `_resolve_project_slug()` currently reads:

```python
def _resolve_project_slug() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            git_common_dir = os.path.abspath(result.stdout.strip())
            repo_root = os.path.dirname(git_common_dir)
            return _role_slug(os.path.basename(repo_root))
    except Exception:
        pass
    return _role_slug(os.path.basename(os.getcwd()))
```

Change it to:

```python
def _resolve_project_slug() -> str:
    load_config = _pkg("load_config")
    if load_config is not None:
        identity_slug = load_config().get("identity_slug")
        if identity_slug:
            return _role_slug(identity_slug)
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--git-common-dir"],
            capture_output=True,
            text=True,
            check=False,
        )
        if result.returncode == 0 and result.stdout.strip():
            git_common_dir = os.path.abspath(result.stdout.strip())
            repo_root = os.path.dirname(git_common_dir)
            return _role_slug(os.path.basename(repo_root))
    except Exception:
        pass
    return _role_slug(os.path.basename(os.getcwd()))
```

The `load_config is not None` guard mirrors the existing `_pkg()` usage pattern elsewhere in this file (e.g. `_pkg("_docs_dir")()` in `get_mode()`) — `_pkg()` returns `None` if the `synlynk` package module isn't registered in `sys.modules` yet (e.g. some import-order edge case or standalone testing of `team.py`), and this must not crash in that case.

- [ ] **Step 4: Run the tests to verify they pass**

Run: `pytest tests/test_identity_init_role.py -k resolve_project_slug -v`

Expected: both PASS.

- [ ] **Step 5: Run the full test file to check for regressions**

Run: `pytest tests/test_identity_init_role.py -v`

Expected: all tests PASS, including `test_build_app_manifest_url_resolves_project_from_git_root_and_caps_name_length` and `test_cmd_identity_init_role_retries_taken_app_name` (both exercise `_resolve_project_slug()` indirectly through `_build_app_manifest_url` and must still pass unchanged, since none of their fixtures set `identity_slug`).

- [ ] **Step 6: Commit**

```bash
git add synlynk/team.py tests/test_identity_init_role.py
git commit -m "feat: let identity_slug config override the provisioning slug"
```

---

### Task 3: Full suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q`

Expected: all tests pass (same count as the pre-existing baseline on this branch, plus the 2 new tests from Task 2 — i.e. 1869 passed, 2 skipped, no failures). If the run takes over 2 minutes, run it in the background and check the output file rather than letting it time out.

- [ ] **Step 2: Report status**

If all tests pass, report DONE. If anything fails that isn't one of the two new tests, report BLOCKED with the failure output — do not attempt to fix unrelated failing tests as part of this task.

---

## Rollout note (not part of this implementation — separate manual step after merge)

Once this ships, cc-videoreframing's `.synlynk/config.json` needs `"identity_slug": "vdowrx"` added by hand (or via `synlynk config set identity_slug vdowrx` if that CLI command exists and accepts arbitrary keys — check `cmd_config_set` in `synlynk/__init__.py:1583-1588` before assuming). This plan does not include that step; it belongs to whoever retries `synlynk identity init --role pm` in cc-videoreframing afterward.
