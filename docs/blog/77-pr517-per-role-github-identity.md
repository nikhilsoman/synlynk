---
title: "PR #517 — Per-Role GitHub App Identity for Dispatched Agents"
date: 2026-07-25
series: "Building the OS for Multi-Agent Development"
post: 77
pr: "#517"
merged: 2026-07-25
---

## The Broader Goal at the End of the Previous PR

By PR #476 (closing the brace-expansion CVE) and the surrounding work in that window, synlynk's dispatch and review pipeline was functionally solid but had a known integrity gap tracked as issue #423: every dispatched agent — Claude, Agy, Grok, Codex — writes to GitHub under the *same* `gh` identity, the repo owner's personal account. The PR Review Discipline rule ("a non-authoring agent must review before merge") was pure process discipline with no mechanism behind it. GitHub itself cannot tell dispatched agents apart, so it can't enforce anything, and every dispatch-authored PR hit "Can not approve your own pull request" the moment a reviewer tried to actually approve.

## Strategic Shifts in This PR

None on the design side — #423 was scoped and speced in earlier sessions (`docs/superpowers/specs/2026-07-23-agent-github-identity-design.md`, plan at `docs/superpowers/plans/2026-07-24-agent-github-identity-design.md`). The shift in *this* PR was operational: what started as "land the feature" turned into a multi-round validation-and-fix cycle once real GitHub App installation-permission propagation delays showed up in practice (see below), and once independent review surfaced a genuine security gap in the implementation that hadn't been caught by the earlier live validation.

## What This PR Shipped

**Per-role GitHub App identity.** Each dispatch role (`dev`, `qa`, `review`, etc.) can have its own GitHub App, installed on the repo, with its own scoped `default_permissions`. `synlynk identity init <role>` walks through the manifest flow (`_build_app_manifest_url` generates a local HTML form that POSTs to `github.com/settings/apps/new`), stores the resulting App ID/installation ID/private key under `.synlynk/github_apps/<role>.json` + `<role>.pem` (permissions tightened via `os.chmod(..., 0o600)`), and `get_installation_token(role, app_config)` mints short-lived installation tokens on demand by signing a JWT and exchanging it for an installation access token.

**Wiring into dispatch.** `synlynk dispatch <agent> --requires-gh-write` now resolves a role-scoped token via `_resolve_dispatch_gh_token(_role_for_story(story_id) or "dev")` and injects it as `GH_TOKEN` into the dispatched subprocess's environment — so a job's `gh pr create`/`gh pr review`/etc. calls authenticate as `app/synlynk-<project>-<role>` instead of the human operator.

**Task 10 live validation.** This is where the propagation-delay problem showed up: even after correctly setting `contents: write` on the App's manifest, GitHub does not retroactively apply a permission upgrade to an *existing* installation — the installation owner has to separately accept a pending permission-update prompt in the GitHub UI. Two validation retries (job-1e212ed9, throwaway PRs #512/#513, both still authored under the personal account) failed against this exact wall before the fix was identified and manually applied. Retry 3 (job-778e4be7 → PR #514) succeeded cleanly: `author.login: "app/synlynk-synlynk-dev"`, `is_bot: true`, confirmed independently via `gh pr view --json author` rather than trusting the dispatched job's own summary — a discipline this PR reinforced after retry 2's self-report turned out to be flatly wrong about whether it had used a personal token.

**Independent review caught what live validation missed.** PR #517 was opened with a Security Review section flagging two known, documented limitations (cross-process token redaction being a practical no-op; a TOCTOU window on private-key file permissions). A non-authoring review dispatched to Codex (job-c051d151) verified those and surfaced something more serious: `synlynk/dispatch.py`'s `requires_gh_write` block only *set* `GH_TOKEN` when a role token was successfully minted — it never *cleared* any `GH_TOKEN`/`GITHUB_TOKEN` already present in the parent shell's environment when minting failed or no role App was provisioned. A dispatch explicitly flagged as needing role-scoped GitHub write access could silently fall through to the operator's personal credential, which is exactly the failure mode this whole feature exists to prevent. Task 10's live validation never caught it because the role App *was* provisioned in that test, so the fallback path never triggered.

The fix, dispatched to Codex and integrated after independent diff review: when no role-scoped token resolves, explicitly `proc_env.pop("GH_TOKEN", None)` / `proc_env.pop("GITHUB_TOKEN", None)` and print a clear stderr warning, rather than leaving whatever was inherited. A regression test proves it — it pre-seeds fake personal-token values via `monkeypatch.setenv`, dispatches with a token resolver that returns `None`, and asserts neither key survives into the captured subprocess env.

**One more real bug, caught by CI, not local tests.** After merging and pushing, GitHub Actions failed `test (3.8)` with `TypeError: 'type' object is not subscriptable` — `synlynk/team.py` used `tuple[Path, Path, Path]` (PEP 585 subscript syntax), which only works on Python 3.9+. Local test runs never caught it because the local interpreter was newer. Fixed with `from __future__ import annotations`, matching the pattern already used in `observatory.py`, `hud.py`, `db.py`, `rollback.py`, and `selftest.py` — applied directly rather than dispatched, since it was a one-line, unambiguous, already-precedented fix to unblock CI on code that had already been reviewed.

**Review posted the sanctioned way.** As expected, `gh pr review 517 --approve` failed with "Can not approve your own pull request" — every dispatched agent and Claude's own interactive session share the same personal `gh` identity, so GitHub correctly refuses self-approval. Per the #423 caveat in `CLAUDE.md`'s PR Review Discipline section, the fallback is a formal COMMENT review with an explicit approve checklist, which is what got posted before merge.

## Brainstorm Visuals Used

None — this PR proceeded directly from the already-approved spec and plan; no new brainstorm was run this cycle.

## What This Achieved on the Path to Autonomy

This closes the biggest remaining gap in dispatch-based multi-agent autonomy: GitHub write actions taken by dispatched agents are now attributable to a specific role identity instead of blurring into the operator's own account, and the fallback path that would have silently defeated that guarantee has been closed and covered by a regression test. The PR Review Discipline's non-authoring-reviewer rule still isn't GitHub-enforced — it can't be, given the shared-identity constraint on approvals — but the review itself is now backed by a role-attributable audit trail on the GitHub side for anything the role actually *writes*.

## Strategic Note: The Goal at the End of This PR

Two follow-ups filed and deliberately not bundled into this PR: **#524** (token redaction across `synlynk logs` invocations is currently a no-op in real multi-process usage) and **#525** (`synlynk doctor`'s CLI entrypoint never actually reaches any of its 10 registered `HEALTH_CHECKS`, including the two new identity checks added here). Neither blocks the core per-role identity feature, but both are real gaps worth closing. Also explicitly deferred, per the original plan's own scoping: provisioning a `qa` role and generalizing GH_TOKEN injection to dispatch flows beyond `--requires-gh-write`.
