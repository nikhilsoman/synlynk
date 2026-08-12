---
title: "chore/identity-slug-override — Untangling Repo Name from Product Name"
date: 2026-08-12
series: "Building the OS for Multi-Agent Development"
post: 114
pr: "TBD"
---

# 114: Untangling Repo Name from Product Name

## Broader goal (previous)

By PR #901 (org-scoped manifest fix), cc-videoreframing's role-identity provisioning (`synlynk identity init --role pm`) had cleared its last technical blocker — the manifest URL builder now worked against org-owned repos. The next step was simply to retry provisioning and move on to the remaining seven roles.

## Why this PR

Retrying surfaced a naming question instead: `_resolve_project_slug()` derives the GitHub App name slug purely from `os.path.basename(cwd)` — for cc-videoreframing, that's the literal directory name `cc-videoreframing`. But the live product name is "vdowrx," and the user wanted App identities named `synlynk-vdowrx-<role>`, not `synlynk-ccvidreframe-<role>`.

The first framing of that ask was broad — "we anyways need to think of this holistically... needs a deeper review of possible combinations" — raising the question of whether synlynk's per-repo identity model needed to become multi-repo-aware. Brainstorming narrowed this down considerably. The already-approved autonomous-ops spec had a line that read, on first pass, like vdowrx was a *retired* name; the user corrected that — vdowrx is live, and only the identity slug needed to change, not the git repo name itself. That reduced the scope from "redesign identity architecture for multi-repo workspaces" to "let one repo's config override one string."

Two naming collisions got caught before they became implementation mistakes. `project_id` already means a GitHub Projects v2 node ID (`PVT_...`), consumed by the instructions template builder — reusing it for the App slug would have silently overloaded two unrelated concepts. `workspace_name`/`workspace_id` was also rejected: `synlynk scan --workspace <name>` already names a *different*, genuinely multi-repo concept (a named grouping of repos under `~/.synlynk/workspaces/<name>/`). The field ended up named `identity_slug` — deliberately distinct from both.

## What shipped

- **`synlynk/__init__.py`** — `identity_slug: None` added to `load_config()`'s schema defaults, backfilled into any existing `.synlynk/config.json` like every other default field.
- **`synlynk/team.py`** — `_resolve_project_slug()` now checks `load_config().get("identity_slug")` first (via the existing `_pkg()` cross-module accessor, which avoids a circular import since `team.py` is imported *by* `synlynk/__init__.py`), and only falls through to the original git-root/cwd-basename logic when unset or empty. No other call site changed — `_build_app_manifest_url`, `_truncate_app_name`, and `cmd_identity_init_role` all already reach the slug exclusively through this one function.
- **`tests/test_identity_init_role.py`** — two new tests: override behavior when `identity_slug` is set, and unchanged fallback behavior (regression guard) when it isn't.
- No CLI flag. This is a persistent, per-repo config field, not a per-invocation override — matching how every other identity-scoped setting in `.synlynk/config.json` already works.

Execution followed brainstorming → writing-plans → subagent-driven-development end to end: design spec and plan authored and committed by Claude (PM/review role), implementation dispatched to Codex as a single combined job (`synlynk dispatch codex`) covering both the schema field and the TDD'd resolver change. Codex's own sandboxed dispatch environment reported the job as BLOCKED — 5 failing tests, none of them the two new ones — which turned out to be a environment artifact: `HTTPServer.server_bind` and state-db writes are blocked by permission inside that sandbox. Independently re-running the exact same tests, then the full file, then the entire 1869-test suite in this session's own unrestricted environment came back clean (1869 passed, 2 skipped, zero failures) — confirming the diff itself introduced no regressions. Codex's job summary had also claimed an unrelated `GEMINI.md` file was "left untouched," when in fact it had an uncommitted stray edit; caught by diffing directly rather than trusting the self-report, and discarded before merge — a recurrence of the standing "never trust job status alone" lesson from #202, this time on Codex's self-report rather than `synlynk jobs`.

Both review stages (spec-compliance, code-quality) and a final holistic review passed clean with no changes requested.

## New goalpost

With `identity_slug` support merged, the remaining step for cc-videoreframing is mechanical: add `"identity_slug": "vdowrx"` to its `.synlynk/config.json` and retry `synlynk identity init --role pm`, then work through the remaining seven roles (architect, tpm, dev, designer, qa, marketing, synlynk-bot). That rollout step is deliberately out of scope for this PR — it's a one-line manual config change for one specific repo, not a code change.
