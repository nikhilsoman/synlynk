---
title: "identity init: resume at install-confirmation instead of restarting App creation"
date: 2026-08-12
status: approved
issue: "#910"
---

# Design: Resume `identity init` at Install Confirmation

## Problem

`cmd_identity_init_role()` (`synlynk/team.py`) only skips re-provisioning when `installation_id` is already set:

```python
if existing.get("installation_id") and existing.get("private_key_path") and os.path.exists(existing["private_key_path"]):
    print(f"  role '{role}' already provisioned at {json_path}")
    return
```

There is no intermediate state. If the GitHub App manifest exchange already succeeded (`app_id`/`client_id`/`app_slug`/`private_key_path` present on disk) but `_confirm_installation()` never completed — process killed, `input()` hit EOF in a non-interactive shell, terminal closed before Enter — re-running the command restarts the *entire* flow: a new manifest callback server, a new browser tab, a new App creation form. Confirmed live 2026-08-11 provisioning cc-videoreframing's `pm` role.

## Design

Add one branch to the existing early-return check in `cmd_identity_init_role`: if the JSON file exists with `app_id`, `client_id`, `app_slug`, and a private key file on disk, but no `installation_id`, skip straight to `_confirm_installation(existing["app_slug"], json_path)` and the trailing `roles.yaml` registration — do not re-enter the manifest creation loop.

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

    # ... existing manifest-creation flow unchanged below this point
```

No other function changes. `_confirm_installation` itself is untouched — it already does the right thing (prompt, sign JWT, GET `/app/installations`, match by `app_slug`, write `installation_id` back into the JSON) once it's actually called.

## Testing

Extend `tests/test_identity_init_role.py` with one new test: given a `.synlynk/github_apps/<role>.json` with `app_id`/`client_id`/`app_slug`/`private_key_path` set but `installation_id` missing (and a stub `.pem` file present), `cmd_identity_init_role` calls `_confirm_installation` exactly once and does **not** call `_build_app_manifest_url` or open a browser. Existing tests (`test_cmd_identity_init_role_retries_taken_app_name`, `test_cmd_identity_init_role_noops_if_already_provisioned`) must keep passing unchanged — the new branch sits strictly between the existing no-op check and the existing manifest-creation loop.

## Out of scope

- No change to `_confirm_installation`'s own logic or its interactive `input()` prompt.
- No change to duplicate-app handling (`_truncate_app_name` retry-on-conflict) — this fix prevents the *primary* cause of accidental duplicate creation but doesn't touch that mechanism.
- No CLI flag or config change — this is a resume-logic bug fix, not a new feature.
