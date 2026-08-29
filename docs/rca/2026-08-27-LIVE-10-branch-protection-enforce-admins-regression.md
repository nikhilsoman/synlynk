# [LIVE-10] `cmd_policy_sync_branch_protection()` hardcoded `enforce_admins: True`, would silently reintroduce the #1124 merge deadlock

**Date:** 2026-08-27
**Severity:** Sev2 — no active production impact at time of filing (live `main` already had `enforce_admins: false`), but the code path was armed to reintroduce a confirmed merge-blocking deadlock (#1124) the moment anyone re-ran `synlynk policy sync-branch-protection`. A workaround existed (don't run that command), which is what keeps this out of Sev1.
**Source:** Discovered by Claude (PM/review session) during #1124 investigation, cross-verified by a synlynk decide panel (claude/codex/grok) plus direct `gh api repos/nikhilsoman/synlynk/branches/main/protection` inspection.
**Status:** Resolved. Fixed same-day in PR #1186, merged into `main`, shipped in v0.18.0.

## Impact

`synlynk/policy_cli.py`'s `cmd_policy_sync_branch_protection()` unconditionally hardcoded `"enforce_admins": True` in the branch-protection payload it `PUT`s to GitHub. Live `main` at the time had `enforce_admins: false` — the setting that allows single-identity (shared-account) merges to succeed today. Nothing was actively broken, because nobody had re-run `sync-branch-protection` since `enforce_admins` was last set to `false`. But the command existed, was documented, and would be reached for by anyone doing routine policy maintenance — at which point it would silently write `enforce_admins: True` back onto live `main` and reintroduce the exact deadlock from #1124: admins/shared-identity actors blocked from merging their own approved PRs.

This is filed as a Live Issue retroactively (see Status note below) because the failure mode it guards against is a real, previously-experienced production deadlock (#1124), and the bug was a landmine in an operational tool rather than a cosmetic defect — even though it happened not to have detonated yet.

## Root cause

`cmd_policy_sync_branch_protection()` (`synlynk/policy_cli.py`, line ~50) built its branch-protection request body with `enforce_admins` as a hardcoded literal:

```python
body = {
    "required_status_checks": {"strict": True, "contexts": REQUIRED_STATUS_CHECKS},
    "enforce_admins": True,
    "required_pull_request_reviews": {"required_approving_review_count": review_count},
    "restrictions": None,
}
```

This literal predated the #1124 resolution. #1124's actual fix was workspace-agent identity separation (registering distinct `qa`/`architect` GitHub App identities and reviewing via `synlynk dispatch claude --as-agent <qa-agent-id>`, producing genuine non-authoring `gh pr review --approve` calls) — not a branch-protection config change. Nobody went back and updated `cmd_policy_sync_branch_protection()`'s hardcoded value to match the new live state, so the tool's own source of truth (a Python literal) drifted out of sync with the actual policy decision (`enforce_admins: false`, verified operationally).

A secondary consideration surfaced during the panel review: `check_authority()` in `synlynk/policy.py` does not implement non-authoring-review verification itself — it only checks `role in can_merge`. This means `required_approving_review_count` is the only functioning review gate today; the panel explicitly flagged that lowering it without a real replacement would be a genuine regression, not a false alarm. The fix therefore only touched `enforce_admins`, deliberately leaving `required_approving_review_count` alone.

## Fix

PR #1186 (merged 2026-08-26, shipped v0.18.0):

```python
-        "enforce_admins": True,
+        "enforce_admins": False,
```

One-line change in `cmd_policy_sync_branch_protection()`, bringing the tool's hardcoded payload back in sync with live `main`'s actual, correct state.

## Prevention

The underlying pattern — a policy value duplicated as a Python literal instead of being derived from `.synlynk/policy.json` — is what let this drift happen silently in the first place; `enforce_admins` could be wrong again the next time the real policy intent changes without someone remembering to update this specific hardcoded line. Issue #1185's own fix-direction note suggested deriving `enforce_admins` from an explicit `policy.json` field instead of a literal, as the more durable fix; that was not done as part of PR #1186 and remains open as a hardening opportunity, not re-filed here since it's an enhancement rather than an active defect.

## Timeline

- **2026-08-26, during #1124 investigation:** Drift discovered via decide-panel review and direct `gh api` verification; filed as issue #1185.
- **2026-08-26:** One-line fix implemented and merged (PR #1186).
- **2026-08-27:** Shipped in v0.18.0.
- **2026-08-28:** Retroactively declared as a Live Issue (LIVE-10) as part of a post-release SOP audit — the issue's own body already assessed it as "not urgent... no live impact today," which is accurate and is reflected in the Sev2 (not Sev1) classification here. It was closed as a plain `bug` without going through the Live Issues declare/label/RCA process at the time, despite guarding against a real previously-experienced production deadlock.
