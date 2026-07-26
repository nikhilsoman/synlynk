---
title: "PR #535 — Cross-Process Token Redaction for GitHub App Installation Tokens"
date: 2026-07-25
series: "Building the OS for Multi-Agent Development"
post: 78
pr: "#535"
merged: 2026-07-25
---

## The Broader Goal at the End of the Previous PR

PR #517 shipped per-role GitHub App identity (#423): dispatched agents now write to GitHub under a role-scoped App installation token instead of the operator's personal account. That PR's own Security Review flagged a known, documented limitation rather than silently shipping it: `_redact_active_tokens` in `synlynk/__init__.py` only ever checked the *in-process* `_token_cache` in `github_app_auth.py`. In practice, `synlynk dispatch` (which mints the token) and a later `synlynk logs` invocation (which displays output that might contain it) are almost always separate CLI processes — so the redaction was a no-op for the exact case it exists to cover. Filed as #524 and deliberately not bundled into #517.

## Strategic Shifts in This PR

None — this was a scoped, well-understood bug fix from the moment #524 was filed. The only real decision was *how* to bridge the cross-process gap without a running daemon or shared memory: an on-disk cache file, written when a token is minted and read by any later process wanting to redact.

## What This PR Shipped

**On-disk redaction cache.** `get_installation_token()` in `synlynk/github_app_auth.py` now calls `_persist_token_for_redaction(role, token, expires_at)` immediately after caching a freshly-minted token in-process. That function appends the token to `.synlynk/token_redaction_cache.json`, pruning any already-expired entries first, and sets `0o600` permissions on the file (it holds live credentials, however short-lived). `_load_redaction_tokens()` is the read side: it loads the cache, filters out anything past its `expires_at`, and returns the still-valid token strings.

**Wiring into redaction.** `_redact_active_tokens` in `synlynk/__init__.py` now checks both sources — the in-process `_token_cache` (same-process dispatch) and `_load_redaction_tokens()` (a token minted by an earlier, separate `dispatch` invocation) — before replacing any match with `***REDACTED***`. Installation tokens live about an hour, and `dispatch`/`logs` are normally different invocations entirely, so the on-disk path is the one that actually matters in real usage.

**A real bug caught before merge, not after.** The dispatched fix (job-67052f14, story-8fe00292) hardcoded `_redaction_cache_path()` as `os.path.join("synlynk", "token_redaction_cache.json")` — one directory name short of the spec, which called for `.synlynk/` (the hidden config directory every other piece of local state lives under), not `synlynk/` (the actual Python package source directory). The job's own new tests in `tests/test_github_app_auth.py` had baked in the identical wrong path via `tmp_path / "synlynk" / "token_redaction_cache.json"`, so `pytest` reported all green despite the defect. It only surfaced because running the full suite directly in the real integration worktree — not inside a `tmp_path` fixture — left behind an untracked `synlynk/token_redaction_cache.json` file, visible in `git status --short`. That's not a file that should ever appear at the top level of the source tree, which is what prompted the investigation. Fixed directly (a one-line path correction to already-reviewed, already-tested code, plus the three matching test-path references) rather than re-dispatched, and disclosed explicitly in the PR body under a "Note on integration" section rather than merged quietly.

**Test coverage.** New tests in `tests/test_github_app_auth.py` cover: cache-file creation and persistence, `0o600` permission enforcement, expired-token filtering on read, and pruning of expired entries on write. Full suite after the fix: `pytest tests/ -q` → 1413 passed, 2 skipped.

## Brainstorm Visuals Used

None — straightforward bug fix from a filed issue, no brainstorm needed.

## What This Achieved on the Path to Autonomy

Closes the second of two integrity gaps #517 explicitly flagged and deferred. Redaction now actually works across the process boundary where it matters — a dispatched job's minted GitHub App token won't leak into a human operator's terminal via a later `synlynk logs` call. It's also a concrete data point for why dispatched diffs need independent verification even when the job reports success and its own tests pass: self-consistent tests can bake in the same bug they're meant to catch.

## Strategic Note: The Goal at the End of This PR

#525 (`synlynk doctor`'s CLI entrypoint never reaching its 10 registered `HEALTH_CHECKS`) was investigated and dispatched in parallel with this fix, landing separately as PR #536. With both #524 and #525 closed, the per-role GitHub identity work opened in #517 is now fully closed out — no more known follow-ups from that PR remain open.
