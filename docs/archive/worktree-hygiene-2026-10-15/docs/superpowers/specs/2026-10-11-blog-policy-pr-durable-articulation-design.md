# Blog Policy Overhaul: PR-Durable Articulation — Design Spec

**Date:** 2026-10-11
**Status:** Approved by Nikhil, pending plan + dispatch
**GOVERNS:** story-0ab760c5, linked under goal-0c4e96ff ("Grow readership of the book manuscript + blog series")

## Problem

The current Blog Post Protocol (documented in both the global `~/.claude/CLAUDE.md`
and this project's `CLAUDE.md`) requires every merged PR to carry a committed
`docs/blog/NN-prN-<slug>.md` file following a fixed 6-point structure. This has
three concrete costs:

1. **Compliance gap.** ~294 posts exist against 400+ merged PRs (~70% at best),
   so the protocol is already not uniformly followed despite being "enforced by
   discipline."
2. **Fragile cross-PR coupling.** `synlynk pr check`'s `validate_all_blog_posts()`
   (in `synlynk/marketing.py`, invoked from `cmd_pr_check` in `synlynk/db.py`
   ~line 4790–4830) validates the *entire* `docs/blog/` tree whenever a PR's
   dispatch worktree contains `website/` — a single malformed historical post
   can block any unrelated PR. This happened concretely on 2026-10-11: a missing
   `author`/`version`/`tags` frontmatter on post 267 blocked PRs #2196 and #2198
   until fixed via a standalone PR #2199.
3. **Duplicated articulation surface.** The `marketing` agent role
   (`SEED_CHARTERS["marketing"]` in `synlynk/agent_cli.py`) already has its own
   blog-writing responsibility (a "limited treatment" per-PR path and a "full
   treatment" per-Named-Release path), so the committed-file-per-PR requirement
   and marketing's charter are two parallel, overlapping blog-generating
   surfaces.

The valuable part of the existing protocol — long-form technical articulation
written at the moment of each PR, capturing why intent shifted — is not the
problem. The committed-markdown-file delivery mechanism is.

## Decision

**Move the per-PR long-form write-up into the merge PR's own GitHub body/comments,
and make `marketing` the only agent/process that generates anything published as
a "blog post."**

This is consistent with how this project already treats PR/issue content as a
permanent record — decision docs, RCA cross-links, and cost-provenance backfills
already live there, not in committed markdown files.

### 1. Per-PR articulation moves into the PR itself

The implementer of a PR writes its long-form summary directly into the PR body
(or a pinned top comment), using the tiered IA defined in §4 below, instead of
creating a `docs/blog/*.md` file. The committed-file-per-PR requirement in both
CLAUDE.md files is retired for implementers.

### 2. `marketing` becomes the sole blog-generating surface

`SEED_CHARTERS["marketing"]`'s existing **per-PR "limited treatment"** path is
retired. Its **Named-Release "full treatment"** path evolves into the new
cadence:

- **Weekly roundup post** — Tier 1 (§4), summarizing the week's merged PRs.
- **One post per Named Release** — Tier 2 (§4).
- **Ad hoc posts** for genuinely meaningful non-release events: major
  enhancements, policy changes (such as this one).

Marketing authors these by reading the CHANGELOG and the actual merged PRs for
the relevant window — not by being handed pre-written content. This is the
mechanism that recovers PR-level articulation at a coarser, curated grain
instead of a mechanical one-file-per-PR grain.

### 3. Historical migration (294 posts)

Every existing `docs/blog/*.md` post's content is copied into its corresponding
PR's GitHub issue — the PR body if that body has no real description yet,
otherwise a comment. This is a backfill operation (mechanical content move), not
294 individual editorial decisions. Once migrated, the files in `docs/blog/`
are superseded by the PRs that now hold their content; cleanup of the files
themselves and the website's blog listing is a follow-on implementation task
(§6), not part of this spec's architecture decision.

### 4. Per-release backfill posts

For every **past Named Release**, marketing additionally authors one **new**
long-form retrospective post — sourced from that release's CHANGELOG section
and its constituent PRs (now holding their own long-form bodies) — to replace
the per-PR archive as the historical narrative surface on the website. This is
new synthesized content, not a copy of old posts.

### 5. Editorial thesis (applies to all go-forward content)

All blog content — weekly, release, ad hoc, and release-retrospective
backfills — is written to foreground **the project's intent and how it
changed**: what was believed true, what event or discovery falsified it, what
intent emerged next. This replaces a flat "here's what shipped" changelog
voice. It is the one voice/formatting rule added to marketing's charter, not a
rigid template — the structural IA (§4) is deliberately tiered rather than a
single fixed format.

## IA for the long-form content (both PR bodies and blog posts)

Every PR body and every blog post must include at least one diagram or
architectural artifact (Mermaid preferred, since both GitHub PR bodies and the
website's markdown renderer support it). The depth of the writeup and diagram
count scales with the PR's/post's impact — picked by the same triage instinct
this project already uses for Live Issue severity (Sev1/Sev2/Sev3), not applied
uniformly.

### Per-PR tiers (chosen by implementer at PR-creation time)

**Tier A — Minimal** (bugfixes, chores, mechanical refactors)
- `## Why` (one sentence), `## What Changed` (2–4 sentences), one Mermaid
  diagram showing before→after behavior at a glance.

**Tier B — Narrative** (default: features, meaningful fixes — direct successor
to today's 6-point blog structure, condensed into the PR body)
- `## Prior Goal` → `## Strategic Shift (if any)` → `## What Shipped` → one
  Mermaid diagram (sequence/flowchart/state, whichever fits the change) → `##
  Path Forward`.

**Tier C — Deep** (foundational/architectural PRs)
- Same narrative sections as Tier B, plus `## Architecture Before` and
  `## Architecture After` diagrams (the diff should be visually obvious between
  them), an optional sequence diagram if call/data order changed, and a
  `## Related Docs` section linking RCA/spec/decision docs.

### Per-release/roundup tiers (chosen by marketing)

**Tier 1 — Weekly Roundup**
- Bullet list of the week's merged PRs, one line each pulled from each PR's own
  Tier A/B/C body (not re-derived from scratch). One diagram: current system
  state with the week's deltas highlighted.

**Tier 2 — Named Release retrospective** (minimum bar for every Named Release)
- Structured as an intent arc: **What we believed going in → What broke / what
  we learned → What shipped (grouped by theme) → Where intent moved**. Two
  diagrams: (a) architecture delta for the release, (b) a short
  belief→event→new-belief timeline making the intent shift visible rather than
  only stated. Synthesized from the release's CHANGELOG + its PRs' own bodies.

**Tier 3 — Deep historical retrospective** (used for: the 294-post backfill
described in §3/§4, and any future landmark release)
- Full intent-arc narrative, potentially spanning multiple past releases.
  Multiple diagrams: before/after architecture, a longer intent-metamorphosis
  timeline, pull-quotes lifted directly from the migrated PR bodies/comments
  (closing the loop from PR-level record to release-level narrative), and links
  to RCA/spec/decision docs for provenance.

**Default rule:** every PR gets at least Tier A (no PR ships without some
diagram); every Named Release gets at least Tier 2; the 294-post migration
backfill and any landmark release get Tier 3.

## Consequences / what becomes obsolete

- `synlynk/marketing.py`'s frontmatter validator (`validate_all_blog_posts()`,
  `REQUIRED_BLOG_FRONTMATTER_KEYS`, `BlogValidationError`,
  `validate_blog_post_frontmatter()`, `split_frontmatter()`) and
  `synlynk/db.py`'s tree-wide blog-validation trigger inside `cmd_pr_check`
  become dead code once no PR writes a `docs/blog/*.md` file. Removing this
  validator is the direct fix for the class of bug that blocked PR #2196/#2198
  on 2026-10-11 — a gate that can't recur once posts aren't a per-PR
  requirement.
- `extract_social_changelog_snippets()` and `update_blog_index()` need
  repointing from markdown-file scanning to GitHub PR/release data, or
  retirement if marketing's new workflow doesn't need them — a follow-on
  implementation decision, not fixed by this spec.
- Both CLAUDE.md files' Blog Post Protocol sections need rewriting to describe
  the new PR-body requirement and marketing's new charter — a documentation PR,
  separate from the code changes.
- The website's blog page is reduced to the release/weekly/ad-hoc posts
  marketing produces going forward, once the 294-post migration lands; the
  specific IA/cleanup of that page is implementation-level, not decided here.

## Explicitly out of scope for this spec

- The exact migration script mechanics (how PR body vs. comment is chosen, rate
  limiting against GitHub API, idempotency for partial runs).
- The literal CLAUDE.md diff.
- `marketing.py` code removal/refactor specifics.
- The website blog page's final post-cleanup layout.

These are Design → Plan → Build follow-ons, scoped as separate plans/dispatches
once this spec is signed off, consistent with this project's standing policy of
keeping specs focused on *what and why*.

## Rollout sequencing (non-binding suggestion for the plan)

1. Update `marketing`'s charter (`SEED_CHARTERS["marketing"]`) and both
   CLAUDE.md files first — this is the policy switch-over point.
2. Build and run the 294-post → PR-comment migration script.
3. Remove `validate_all_blog_posts()`'s `cmd_pr_check` trigger (and the now-dead
   code in `marketing.py`) once migration is confirmed complete, so no PR is
   blocked by it during the transition.
4. Marketing backfills one Tier 2/3 retrospective per past Named Release.
5. Website blog page cleanup, once backfill posts exist to replace the
   per-PR archive.
