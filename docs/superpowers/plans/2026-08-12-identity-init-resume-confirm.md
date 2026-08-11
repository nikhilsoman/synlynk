# Identity Init Resume-At-Confirmation Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix `cmd_identity_init_role()` (`synlynk/team.py`) so that a role whose GitHub App was already created (manifest exchange succeeded) but never had its installation confirmed resumes at `_confirm_installation()` instead of restarting the entire App-creation flow.

**Architecture:** Insert one new branch into the existing early-return check at the top of `cmd_identity_init_role`, between the current "already fully provisioned, no-op" check and the manifest-creation loop. No other function is touched.

**Tech Stack:** Python 3, pytest, `monkeypatch`/`tmp_path` fixtures (existing patterns in `tests/test_identity_init_role.py`).

**Spec:** `docs/superpowers/specs/2026-08-12-identity-init-resume-confirm-design.md`

---

## Context for the implementer

This is a synlynk repo (single-file-style CLI split across `synlynk/*.py` modules, no build step). `cmd_identity_init_role` lives in `synlynk/team.py` starting at line 837. Run the full test suite via `pytest tests/ -q` from the repo root; it currently passes (1869 passed, 2 skipped as of this branch's base).

Background: this bug was discovered live while provisioning cc-videoreframing's `pm` role. The App (`synlynk-vdowrx-pm`, real `app_id`) was created and the user completed GitHub's install flow in their browser, but the local process had already died (hit `EOFError` on `input()` in a non-interactive shell) before writing `installation_id`. Re-running `synlynk identity init --role pm` reopened a brand-new manifest form instead of resuming — because the existing no-op check only fires when `installation_id` is already set, with nothing in between that and "start over."

---

### Task 1: Add resume-at-confirmation branch (TDD)

**Files:**
- Modify: `synlynk/team.py:837-846` (`cmd_identity_init_role`)
- Test: `tests/test_identity_init_role.py`

- [ ] **Step 1: Write the failing test**

Open `tests/test_identity_init_role.py`. Find `test_cmd_identity_init_role_noops_if_already_provisioned` (near the end of the file) — use it as your pattern reference for how a `.synlynk/github_apps/<role>.json` + `.pem` fixture is set up. Add this new test function directly after it:

```python
def test_cmd_identity_init_role_resumes_at_confirmation_when_app_created_but_not_installed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    app_dir = tmp_path / ".synlynk" / "github_apps"
    app_dir.mkdir(parents=True)
    pem_path = app_dir / "review.pem"
    pem_path.write_text("PRIVATE KEY")

    json_path = app_dir / "review.json"
    json_path.write_text(
        json.dumps(
            {
                "role": "review",
                "app_id": 42,
                "client_id": "client-1",
                "app_slug": "synlynk-review",
                "installation_id": None,
                "private_key_path": str(pem_path),
            },
            indent=2,
        )
        + "\n"
    )

    confirm_calls = []

    def fake_confirm(app_slug, path):
        confirm_calls.append((app_slug, path))
        data = json.loads(path.read_text())
        data["installation_id"] = 99
        path.write_text(json.dumps(data, indent=2) + "\n")
        return data

    monkeypatch.setattr(team_mod, "_confirm_installation", fake_confirm)
    monkeypatch.setattr(team_mod, "_build_app_manifest_url", lambda *a, **k: (_ for _ in ()).throw(AssertionError("should not rebuild manifest")))
    monkeypatch.setattr(team_mod.webbrowser, "open", lambda url: (_ for _ in ()).throw(AssertionError("should not reopen browser")))
    monkeypatch.setattr("synlynk.identity_roles.load_declared_roles", lambda: [])
    monkeypatch.setattr("synlynk.identity_roles.write_declared_roles", lambda roles: None)

    team_mod.cmd_identity_init_role("review")

    assert confirm_calls == [("synlynk-review", json_path)]
    assert json.loads(json_path.read_text())["installation_id"] == 99
```

This uses `team_mod`, `json` (already imported at the top of the file per prior sessions' work on this file — verify with `head -10 tests/test_identity_init_role.py` if unsure).

- [ ] **Step 2: Run the test to verify it fails**

Run: `pytest tests/test_identity_init_role.py -k resumes_at_confirmation -v`

Expected: FAIL — `_build_app_manifest_url` gets called (assertion error fires) because the current code has no intermediate branch and falls straight into the manifest-creation loop.

- [ ] **Step 3: Implement the fix**

In `synlynk/team.py`, `cmd_identity_init_role` currently reads (lines 837-846):

```python
def cmd_identity_init_role(role: str, project=None) -> None:
    app_dir, json_path, pem_path = _role_app_paths(role)
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
        if existing.get("installation_id") and existing.get("private_key_path") and os.path.exists(existing["private_key_path"]):
            print(f"  role '{role}' already provisioned at {json_path}")
            return

    owner_type, owner_login = _resolve_repo_owner()
```

Change it to:

```python
def cmd_identity_init_role(role: str, project=None) -> None:
    app_dir, json_path, pem_path = _role_app_paths(role)
    if json_path.exists():
        try:
            existing = json.loads(json_path.read_text())
        except (json.JSONDecodeError, OSError):
            existing = {}
        if existing.get("installation_id") and existing.get("private_key_path") and os.path.exists(existing["private_key_path"]):
            print(f"  role '{role}' already provisioned at {json_path}")
            return
        if (
            existing.get("app_id")
            and existing.get("client_id")
            and existing.get("app_slug")
            and existing.get("private_key_path")
            and os.path.exists(existing["private_key_path"])
        ):
            print(f"  role '{role}' has an App already created ({existing['app_slug']}) — resuming at install confirmation")
            _confirm_installation(existing["app_slug"], json_path)
            print(f"  role '{role}' provisioned at {json_path}")
            from synlynk.identity_roles import load_declared_roles, write_declared_roles
            declared = load_declared_roles()
            if role not in declared:
                write_declared_roles(declared + [role])
                print(f"  ✓ added '{role}' to .synlynk/roles.yaml")
            return

    owner_type, owner_login = _resolve_repo_owner()
```

Do not touch anything below `owner_type, owner_login = _resolve_repo_owner()` — the rest of the function (manifest creation loop, `_confirm_installation` call, `roles.yaml` registration at the bottom) is unchanged; the new branch duplicates the final two steps (confirm + register) for the resume path since it returns before reaching them at the bottom.

- [ ] **Step 4: Run the test to verify it passes**

Run: `pytest tests/test_identity_init_role.py -k resumes_at_confirmation -v`

Expected: PASS.

- [ ] **Step 5: Run the full file to check for regressions**

Run: `pytest tests/test_identity_init_role.py -v`

Expected: all tests PASS, including `test_cmd_identity_init_role_noops_if_already_provisioned` (installation_id already set — must still hit the first branch, not the new one) and `test_cmd_identity_init_role_retries_taken_app_name` (no JSON file exists yet — must still go through the full manifest-creation loop, not the new branch).

- [ ] **Step 6: Commit**

```bash
git add synlynk/team.py tests/test_identity_init_role.py
git commit -m "fix: resume identity init at install confirmation instead of restarting (#910)"
```

---

### Task 2: Full suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest tests/ -q`

Expected: all tests pass — same count as this branch's baseline plus the 1 new test (1870 passed, 2 skipped, no failures). If the run takes over 2 minutes, run it in the background and check the output file rather than letting it time out.

- [ ] **Step 2: Report status**

If all tests pass, report DONE. If anything fails that isn't the new test, report BLOCKED with the failure output — do not attempt to fix unrelated failing tests as part of this task.
