# Per-Repo Identity Slug Override — Design

**Date:** 2026-08-11
**Status:** Design, approved by Nikhil in chat 2026-08-11.

## Problem

`synlynk identity init --role <role>` derives the GitHub App name slug for a
repo's role identities from `os.path.basename(cwd)` via
`_resolve_project_slug()` (`synlynk/team.py:104-118`). There is no way to
provision under a different name when a repo's git directory name and its
product/brand name diverge — e.g. cc-videoreframing's product name is
"vdowrx," but its GitHub App identities would otherwise be named
`synlynk-ccvidreframe-<role>`.

This surfaced while provisioning cc-videoreframing's 8 role identities
(issue #901 / PR #903 fixed the underlying org-scoped-manifest bug that
blocked provisioning; this spec addresses the separate naming gap found
immediately after).

Two things this is explicitly **not**:

- **Not a multi-repo identity change.** Per
  `docs/superpowers/specs/2026-08-11-autonomous-ops-program-design.md` §1,
  identities are isolated per repo — not shared across repos, not shared
  across roles. That's an already-approved decision and stays unchanged
  here.
- **Not the `workspace` concept in `synlynk/scan.py`.** That's a named
  grouping of multiple repos for `synlynk scan --workspace <name>`, stored
  under `~/.synlynk/workspaces/<name>/`. It has different scope (can span
  many repos) than identity provisioning (strictly one repo). Naming the new
  field after "workspace" would misleadingly suggest shared scope, so this
  design uses a distinct name instead.

## Design

Add `identity_slug: str | None` to `.synlynk/config.json`'s schema
(`load_config()` defaults, `synlynk/__init__.py:1525-1541`), alongside the
existing `project_id`, `org`, `owner` fields. `project_id` is not reused —
it already means "GitHub Projects v2 node ID" (`PVT_...`, consumed by
`_build_templates()` in `synlynk/instructions.py`), a distinct concept.

Default is `None`. When `None`, behavior is unchanged: the slug still comes
from the cwd basename. When set, it overrides that basename for this repo's
identity provisioning only.

### `_resolve_project_slug()` change

`synlynk/team.py:104-118`, current:

```python
def _resolve_project_slug() -> str:
    repo_root = _find_repo_root()
    if repo_root:
        return _role_slug(os.path.basename(repo_root))
    return _role_slug(os.path.basename(os.getcwd()))
```

New:

```python
def _resolve_project_slug() -> str:
    identity_slug = load_config().get("identity_slug")
    if identity_slug:
        return _role_slug(identity_slug)
    repo_root = _find_repo_root()
    if repo_root:
        return _role_slug(os.path.basename(repo_root))
    return _role_slug(os.path.basename(os.getcwd()))
```

`load_config()` already exists in `synlynk/__init__.py` and is the
established way `team.py`-adjacent code reads `.synlynk/config.json` (see
its use for `org`, `owner`, `project_id` elsewhere in the file). No new
config-loading path is introduced.

### No other call sites change

`_build_app_manifest_url`, `_truncate_app_name`, and
`cmd_identity_init_role` all reach the slug exclusively through
`_resolve_project_slug()` when their `project` parameter is `None` (the only
call site today, `cli.py:1373`, always passes `project=None`). The override
is transparent to all of them — no CLI flag, no new parameter plumbing.

The existing `project` parameter on `cmd_identity_init_role` and
`_build_app_manifest_url` stays as-is (an unwired low-level override hook);
this design does not add a `--project` CLI flag, matching the earlier
decision to prefer a persistent config value over a per-invocation flag.

### Rollout for cc-videoreframing

Once shipped, set in cc-videoreframing's `.synlynk/config.json`:

```json
{
  "identity_slug": "vdowrx"
}
```

Then `synlynk identity init --role pm` (and the remaining 7 roles) will
provision GitHub Apps named `synlynk-vdowrx-<role>` instead of
`synlynk-ccvidreframe-<role>`.

## Testing

Extend `tests/test_identity_init_role.py` (already covers
`_resolve_project_slug` behavior from PR #903) with:

- `_resolve_project_slug()` returns `_role_slug(identity_slug)` when
  `.synlynk/config.json` has `identity_slug` set.
- `_resolve_project_slug()` falls back to cwd-basename behavior when
  `identity_slug` is absent or empty — regression guard for every repo that
  doesn't set it (synlynk itself included).

## Out of scope

- Renaming `project_id` or any existing config field.
- Any change to the `synlynk scan --workspace` multi-repo concept.
- A CLI `--project` flag.
- Retroactively renaming already-provisioned identities (e.g. synlynk's own
  8 roles, or any cc-videoreframing role provisioned before this ships).
