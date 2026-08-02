---
title: "Fleet-Parity Security Cluster — Fail Closed, Not Warn-and-Proceed"
date: 2026-08-02
series: "Building the OS for Multi-Agent Development"
post: 91
pr: "TBD"
merged: status open
---

## The Broader Goal at the End of the Previous PR

PR #587 (post #90) closed out the harness-capability-drift-regression-classification chain, and with it the last dependency blocking the fleet-parity audit — eight issues (#332, #338, #340, #342, #347, #348, #419, #461) queued since mid-project as "known gaps between what synlynk assumes about dispatched agents and what those agents' CLIs can actually enforce." Three of the eight (#332/#419/#461) turned out to already be fixed by PR #604 and were closed by inspection. The remaining five split cleanly along one axis: does the gap let a dispatched agent **do more than it was granted** (security severity), or does it **fail or drift without exceeding scope** (reliability severity)? This PR is the security half — #348 and #338. The reliability half (#340/#342/#347) stays queued as a follow-up spec.

## Strategic Shifts in This PR

The brainstorm surfaced a decision point that shaped everything downstream: when an agent has no real CLI mechanism to enforce a requested restriction, should dispatch warn and proceed, or refuse outright? The codebase's existing behavior for Agy's read-only case was warn-and-proceed — print a caveat, then run with full permissions anyway. That's strictly worse than having no restriction mechanism at all, because it creates the appearance of a boundary that isn't there. The locked-in decision: fail closed. A loud refusal beats a silent no-op that gives false confidence.

The same question came up for the environment leak (#348): strip known-secret-shaped patterns from the inherited environment, or allowlist a minimal fixed set and add to it only on confirmed need? Denylists only ever catch patterns someone thought to strip; allowlists default to nothing. Went with the allowlist — `_build_subprocess_env()` replaces `os.environ.copy()` entirely rather than filtering it.

Two scope cuts kept this from sprawling into the reliability cluster's territory: Local (aider) gets the same fail-closed treatment as any agent with no declared enforcement mechanism, rather than investing in wiring up aider's actual `--read` flag (unverified in this environment — aider isn't installed here) — that's logged as a follow-up, not solved here. Same for Agy's `--sandbox` flag, whose real semantics aren't documented in this repo. Both are explicit "fail closed now, investigate later" calls rather than either doing the investigation or leaving warn-and-proceed in place.

## What This PR Shipped

Four tasks, dispatched to Codex in dependency order, each verified via direct worktree diff + targeted test run before merge — not from job-status summaries alone, which this session confirmed can misreport `files: 0 touched` even on real, correctly-scoped commits (a display quirk, distinguished from an actual false-completion pattern seen earlier in unrelated dispatch history).

- **`PermissionEnforcementError`** (`synlynk/dispatch.py`): a new exception `_permissions_to_flags()` raises instead of warning. Agy's read-only branch (`set(permissions) <= {"read:*"}`) now raises rather than printing a caveat and returning `[]`; Local raises for any non-empty permission set (empty permissions — no restriction requested — stays a no-op). Claude/Codex/Grok/Agy-write paths are unchanged; they already have real per-permission enforcement. The caller lets the exception propagate, so dispatch fails before any worktree or subprocess work begins — cheap, immediate failure instead of a wasted dispatch.
- **`env_passthrough` baseline field** (`synlynk/_constants.py`): every entry in `AGENT_CAPABILITY_BASELINES` gained an `env_passthrough: []` key. Investigation for this spec found all five agents currently authenticate via login state or file-based credentials rather than environment variables — so the field starts empty everywhere, populated only when a future agent genuinely needs an env var passed through.
- **`_build_subprocess_env()`** (`synlynk/dispatch.py`): replaces the single `proc_env = os.environ.copy()` call site with a function that builds the subprocess environment from a fixed base allowlist (`PATH`, `HOME`, `LANG`, git identity vars, etc.) plus each agent's `env_passthrough` list — nothing else from the parent shell crosses over. The existing GH_TOKEN inject/strip logic for `--requires-gh-write` dispatches is preserved verbatim inside the new function; three pre-existing regression tests in `test_dispatch_github_identity.py` confirm that behavior survived the refactor unchanged.
- **`_redact_secret_patterns()`** (`synlynk/__init__.py`): a second redaction pass layered after the existing `_redact_active_tokens()` (which only catches synlynk's own minted GitHub App tokens). Five compiled patterns cover GitHub PATs/OAuth tokens, AWS access key IDs, OpenAI-style keys, and Slack tokens — applied to captured job output before it's printed or logged. This is explicitly defense-in-depth: the env allowlist is the primary control that keeps secrets out of the subprocess in the first place; this pass catches the case where a secret still ends up in captured stdout some other way (e.g., echoed by the dispatched agent itself).

One pre-existing test needed updating as part of the regression gate: `test_synlynk.py::test_permissions_to_flags_agy_returns_empty_for_read_only` asserted the exact old behavior Task 1 deliberately changed. Replaced with an assertion that `PermissionEnforcementError` is now raised — the plan itself pre-authorized this class of fix, distinguishing it from an unintended regression.

Full suite: 1536 passed, 2 skipped, stable.

## Brainstorm Visuals Used

None — every decision in this spec was a text/tradeoff question (fail-closed vs. warn, allowlist vs. denylist), not a visual one.

## What This Achieved on the Path to Autonomy

Every dispatched agent's declared permission scope is now something synlynk either genuinely enforces or refuses to pretend it enforces — no more silent gaps between the permission a caller requests and what actually reaches the subprocess. And no dispatched subprocess, regardless of trust level, inherits the operator's full shell environment by default; every var it sees is either a fixed baseline or an agent's declared, confirmed-necessary requirement. Combined with the generic secret redaction, this closes both the write-path (what the subprocess can access) and read-path (what makes it into logs) versions of the same underlying gap.

## Strategic Note: The Goal at the End of This PR

The reliability cluster (#340/#342/#347 — jobs that fail or drift without exceeding granted scope) is next up as its own spec, following the same brainstorm → plan → dispatch → verify discipline this PR used. Two explicitly-deferred follow-ups from this spec remain logged for whenever there's a real aider/Agy `--sandbox` install to test against: Local's `--read` flag and Agy's `--sandbox` semantics, both currently fail-closed rather than genuinely scoped.
