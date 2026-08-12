---
title: "Fixing #910 — Resume Identity Init at Install Confirmation, Not App Creation"
date: 2026-08-12
series: "Building the OS for Multi-Agent Development"
post: 115
issue: "#910"
---

# Resume at Confirmation, Not from Scratch

## Broader goal (previous)

PR #908 shipped `identity_slug`, letting a repo's GitHub App identity slug diverge from its directory basename — the immediate need being cc-videoreframing's App identities named after its product "vdowrx" rather than the repo folder. The next step was purely operational: set `identity_slug: "vdowrx"` in cc-videoreframing's config and run `synlynk identity init --role pm` to provision the first role under the new naming.

## Why this PR

That rollout surfaced a real bug live. The `pm` App got created successfully — manifest exchanged, `app_id`/`client_id`/`app_slug`/private key all written to disk — and the user completed GitHub's install flow in their browser, selecting the specific repo for App access. But the local CLI process had already died on `input()` hitting `EOFError` in a non-interactive shell, before it could write `installation_id` back to the JSON file. Re-running `synlynk identity init --role pm` didn't resume — it reopened a brand-new manifest form and a new browser tab, asking the user to create the App and pick repo access all over again. `cmd_identity_init_role()`'s only early-return check was "is `installation_id` already set" — there was no state for "App created, install not yet confirmed," so anything short of full completion fell all the way back to square one.

The immediate situation was resolved manually — a standalone script reusing `_confirm_installation`'s own JWT-signing and `/app/installations` lookup logic to fetch and write the correct `installation_id` without touching the broken code path — but the underlying bug needed a real fix before the remaining seven roles (architect, tpm, dev, designer, qa, marketing, synlynk-bot) hit the same stall.

## What shipped

One new branch in `cmd_identity_init_role()` (`synlynk/team.py`), inserted between the existing "fully provisioned, no-op" check and the manifest-creation loop: if the role's JSON file has `app_id`, `client_id`, `app_slug`, and a private key on disk, but no `installation_id`, skip straight to `_confirm_installation(existing["app_slug"], json_path)` and the trailing `roles.yaml` registration — no new manifest, no new browser tab, no re-prompt for repo access.

```python
if (
    existing.get("app_id")
    and existing.get("client_id")
    and existing.get("app_slug")
    and existing.get("private_key_path")
    and os.path.exists(existing["private_key_path"])
):
    print(f"  role '{role}' has an App already created ({existing['app_slug']}) — resuming at install confirmation")
    _confirm_installation(existing["app_slug"], json_path)
    ...
    return
```

`_confirm_installation` itself was untouched — it already did the right thing once actually called. This was a routing bug, not a logic bug.

Process: a fast-path design spec (issue #910 already had problem, impact, and suggested fix fully written out, so no multi-round brainstorming dialogue was needed), a TDD implementation plan, dispatched whole to Codex per the established subagent-driven pattern. Codex's diff came back exactly on spec — one new branch, one new test (`test_cmd_identity_init_role_resumes_at_confirmation_when_app_created_but_not_installed`) asserting `_confirm_installation` is called exactly once and neither `_build_app_manifest_url` nor `webbrowser.open` fire. Verification caught a wrinkle worth noting: Codex's own sandboxed worktree reported 5 failures (2 pre-existing localhost-socket-bind tests, 3 unrelated `.synlynk/project-docs/todo.md` permission errors) — none touching this change. Cherry-picking the same commit into the unsandboxed parent worktree and re-running confirmed all 12 identity-init tests and the full 1870-test suite pass clean, isolating those failures as sandbox artifacts rather than regressions.

## On the long arc

This closes the loop the `identity_slug` rollout opened: the feature that let cc-videoreframing get a correctly-branded App identity also exposed that the provisioning flow had no resume semantics at all, just "done" or "start over." Fixing it here — rather than working around it again for each of the remaining seven roles — turns a one-off manual recovery into a permanent property of the tool.

## New goalpost

`identity init` can now recover cleanly from a mid-flow interruption at any point after App creation. Next: resume provisioning the remaining seven cc-videoreframing roles, now able to rely on this fix if any of them stall the same way.
