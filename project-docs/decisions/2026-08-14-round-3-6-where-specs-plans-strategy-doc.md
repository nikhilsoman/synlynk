---
decision_id: dec-fa884bfd
topic: "ROUND 3/6 — Where specs/plans/strategy docs/reports/decisions actually live, and how far each repo's convention has diverged.

EVIDENCE — direct comparison of the "occasional document" folders across all 4 repos:

synlynk (98 specs, 81 plans, 4 rca, 135 blog, 11 archive, 0 brainstorm, 6 reference):
  docs/superpowers/specs/, docs/superpowers/plans/, docs/rca/, docs/blog/, docs/archive/, docs/brainstorm/ (empty despite being referenced in CLAUDE.md global instructions), docs/reference/, docs/handoffs/ + docs/superpowers/handoffs/ (duplicate)

rxcc (33 specs, 25 plans):
  docs/superpowers/specs/, docs/superpowers/plans/ (same convention as synlynk) — BUT ALSO: docs/rca/ (2 files) + 17 loose docs/claude-rca-*.md; docs/blog/ (34 files); docs/archive/accuracy-strategy/ (4); docs/brainstorm/ (17 subdirs, ~100+ HTML mockup files — the ONLY repo where brainstorm/ is actually used); docs/proposals/ (8, includes the stale DOCUMENTATION_FRAMEWORK.md); docs/mbr/, docs/runbooks/, docs/strategy/, docs/mktg/, docs/dev/, docs/ux-redesign/, docs/visuals/ — plus ~90 loose agent-prefixed docs directly in docs/ root with no folder at all.

playblazer-ng (6 specs, 0 plans):
  docs/superpowers/specs/ only (6 files, all from a single early batch 2026-05-09/10) — NO docs/superpowers/plans/, NO docs/rca/, NO docs/blog/, NO docs/archive/, NO docs/brainstorm/ exist at all. Separately has docs/strategy/ (1 file), docs/papers/ (2), docs/ux-prompts/ (9) — categories that don't exist in any other repo.

cc-videoreframing (25 specs, 46 plans):
  docs/superpowers/specs/, docs/superpowers/plans/ (same convention, most populated plans/ of any repo) — plus docs/research/ (8, with 2 sub-topic subfolders), docs/strategy/ (4), docs/rca/ (4, correctly named/foldered), docs/blog/ (2, README + 1 post — protocol says "draft a blog post for every PR" but only 1 exists despite dozens of merged PRs), docs/archive/pre-synlynk-migration/ (the one clean archive example from Round 2), plus ~9 loose standalone docs at docs/ root (infra-architecture-deep-dive.md, unit_economics.md, MigrationGuide.md, vdowrx_strategy.md, etc.) and docs/paperclip/ subfolder.

Cross-cutting pattern: docs/superpowers/specs/ and docs/superpowers/plans/ are the ONE convention all 4 repos actually share (because Brainstorm-First Policy / writing-plans skill hardcodes that path). Everything else — RCA, blog, archive, strategy, research, brainstorm, reports, decisions, handoffs — has a different ad hoc location and population level in every single repo, and none of the repos have all the folder types the global CLAUDE.md's protocols assume exist (e.g. Blog Post Protocol mandates a post per PR in every repo, but cc-videoreframing has 1 post for dozens of PRs, playblazer-ng has docs/blog/ missing entirely).

QUESTION: Given that docs/superpowers/specs/ and docs/superpowers/plans/ are the only convention that actually held across independently-evolved repos (because it's enforced by a skill, not by developer discipline), what's the minimum set of "occasional document" categories that should be similarly skill/tool-enforced with a fixed path (RCA, blog, archive, decisions, handoffs, brainstorm, reports) versus left as genuinely repo-specific/optional (strategy, research, papers, ux-prompts — categories that appear in only 1-2 repos and reflect real domain differences, not drift)? For the ones that should be standardized, should the enforcement mechanism be the same skill-injection pattern that made docs/superpowers/ stick, or something else? Address specifically why the Blog Post Protocol is failing to produce 1:1 PR-to-post compliance in 3 of 4 repos despite being a "global, all-projects" CLAUDE.md rule."
date: 2026-08-14
panel: [codex, grok]
status: approved
---

## Topic
ROUND 3/6 — Where specs/plans/strategy docs/reports/decisions actually live, and how far each repo's convention has diverged.

EVIDENCE — direct comparison of the "occasional document" folders across all 4 repos:

synlynk (98 specs, 81 plans, 4 rca, 135 blog, 11 archive, 0 brainstorm, 6 reference):
  docs/superpowers/specs/, docs/superpowers/plans/, docs/rca/, docs/blog/, docs/archive/, docs/brainstorm/ (empty despite being referenced in CLAUDE.md global instructions), docs/reference/, docs/handoffs/ + docs/superpowers/handoffs/ (duplicate)

rxcc (33 specs, 25 plans):
  docs/superpowers/specs/, docs/superpowers/plans/ (same convention as synlynk) — BUT ALSO: docs/rca/ (2 files) + 17 loose docs/claude-rca-*.md; docs/blog/ (34 files); docs/archive/accuracy-strategy/ (4); docs/brainstorm/ (17 subdirs, ~100+ HTML mockup files — the ONLY repo where brainstorm/ is actually used); docs/proposals/ (8, includes the stale DOCUMENTATION_FRAMEWORK.md); docs/mbr/, docs/runbooks/, docs/strategy/, docs/mktg/, docs/dev/, docs/ux-redesign/, docs/visuals/ — plus ~90 loose agent-prefixed docs directly in docs/ root with no folder at all.

playblazer-ng (6 specs, 0 plans):
  docs/superpowers/specs/ only (6 files, all from a single early batch 2026-05-09/10) — NO docs/superpowers/plans/, NO docs/rca/, NO docs/blog/, NO docs/archive/, NO docs/brainstorm/ exist at all. Separately has docs/strategy/ (1 file), docs/papers/ (2), docs/ux-prompts/ (9) — categories that don't exist in any other repo.

cc-videoreframing (25 specs, 46 plans):
  docs/superpowers/specs/, docs/superpowers/plans/ (same convention, most populated plans/ of any repo) — plus docs/research/ (8, with 2 sub-topic subfolders), docs/strategy/ (4), docs/rca/ (4, correctly named/foldered), docs/blog/ (2, README + 1 post — protocol says "draft a blog post for every PR" but only 1 exists despite dozens of merged PRs), docs/archive/pre-synlynk-migration/ (the one clean archive example from Round 2), plus ~9 loose standalone docs at docs/ root (infra-architecture-deep-dive.md, unit_economics.md, MigrationGuide.md, vdowrx_strategy.md, etc.) and docs/paperclip/ subfolder.

Cross-cutting pattern: docs/superpowers/specs/ and docs/superpowers/plans/ are the ONE convention all 4 repos actually share (because Brainstorm-First Policy / writing-plans skill hardcodes that path). Everything else — RCA, blog, archive, strategy, research, brainstorm, reports, decisions, handoffs — has a different ad hoc location and population level in every single repo, and none of the repos have all the folder types the global CLAUDE.md's protocols assume exist (e.g. Blog Post Protocol mandates a post per PR in every repo, but cc-videoreframing has 1 post for dozens of PRs, playblazer-ng has docs/blog/ missing entirely).

QUESTION: Given that docs/superpowers/specs/ and docs/superpowers/plans/ are the only convention that actually held across independently-evolved repos (because it's enforced by a skill, not by developer discipline), what's the minimum set of "occasional document" categories that should be similarly skill/tool-enforced with a fixed path (RCA, blog, archive, decisions, handoffs, brainstorm, reports) versus left as genuinely repo-specific/optional (strategy, research, papers, ux-prompts — categories that appear in only 1-2 repos and reflect real domain differences, not drift)? For the ones that should be standardized, should the enforcement mechanism be the same skill-injection pattern that made docs/superpowers/ stick, or something else? Address specifically why the Blog Post Protocol is failing to produce 1:1 PR-to-post compliance in 3 of 4 repos despite being a "global, all-projects" CLAUDE.md rule.

## Panel Inputs

### codex
The minimum standard set should be the categories that represent cross-repo process artifacts, not subject-matter content:

- `docs/rca/`
- `docs/blog/`
- `docs/archive/`
- `docs/decisions/`
- `docs/handoffs/`
- `docs/brainstorm/`
- `docs/reports/`

These categories describe recurring workflow states or governance outputs. Their absence or inconsistency creates discoverability and audit problems. `strategy/`, `research/`, `papers/`, and `ux-prompts/` should remain repo-specific because their meaning and expected volume depend on the product. They are not evidence of drift merely because they differ.

The enforcement mechanism should reuse the successful `docs/superpowers/` pattern, but with stronger lifecycle tooling. A skill should define the canonical path, filename schema, required metadata, and creation triggers. CLI checks should validate references, detect misplaced documents, and optionally scaffold missing artifacts. `archive/` should be treated as a lifecycle destination rather than a free-form category: documents move there under explicit archival rules. `decisions/`, `handoffs/`, and `reports/` need lightweight templates; otherwise teams will create them inconsistently despite having fixed directories.

The Blog Post Protocol is failing because a CLAUDE.md instruction is passive policy. It does not create a post, identify which PRs require one, block completion when one is missing, or provide an obvious command for generating it. The evidence also suggests that “every PR” is too broad: many PRs are mechanical, internal, or not publication-worthy. A workable protocol must either enforce literal 1:1 compliance through PR tooling that scaffolds a draft automatically, or redefine the rule around externally meaningful changes and require an explicit “no post needed” declaration.

My position: standardize all seven workflow categories through skill-injected templates plus CLI/CI checks, leave domain categories optional, and replace the current blog rule with an enforceable, trigger-based protocol rather than a global prose mandate.

### grok
I'll ground this in how specs/plans actually get enforced versus how the Blog Post Protocol is written, then give a minimum standard set and a clear recommendation.**Specs and plans stuck because they sit on the critical path.** The brainstorming skill writes `docs/superpowers/specs/`; writing-plans writes `docs/superpowers/plans/`. You cannot start build without those files. Everything else is a post-hoc CLAUDE.md instruction, so it drifted.

**Standardize only process artifacts** (same shape as specs/plans: one path, created on first use, not pre-seeded empty):

| Category | Path | When it is written |
|---|---|---|
| RCA | `docs/rca/` | Sev1 live-issue SOP fires |
| Archive | `docs/archive/<topic>/` | Worktree hygiene / abandoned branch |
| Decisions | `docs/decisions/` | A call is locked and must outlive `memory.md` |
| Handoffs | `docs/handoffs/` | Cross-session or cross-repo transfer |
| Brainstorm | `docs/brainstorm/<topic>/` | Visual companion actually produced HTML |

Leave as repo-local: `strategy/`, `research/`, `papers/`, `ux-prompts/`, `runbooks/`, `mktg/`, `paperclip/`. Those encode domain, not forgetfulness.

**Do not skill-enforce a 1:1 blog.** Named Release Policy already treats PRs as engineering units and releases as the communication event. synlynk’s own practice contradicts the protocol (one post for PRs #824–#830; a paused-then-informally-resumed hold). The 1:1 rule is the wrong contract.

**Why Blog Post Protocol fails in 3 of 4 repos:** it is prose, explicitly “enforced by discipline, not CI.” It runs *after* the merge-blocking work, so it loses to token pressure. Implementers never load a skill that writes `docs/blog/`. Claude is the intended author but is also told not to implement and to keep docs PRs separate — which fights “commit the post on the same branch.” playblazer-ng never got `docs/blog/` from init. cc-videoreframing has dozens of PRs and one post because the template cost (six-section essay) exceeds the value of a chore PR. synlynk only looks compliant because it *is* the product being diary’d.

**Enforcement:** reuse the skill-injection pattern, not more global markdown. Hook RCA into the live-issue skill, archive into finishing-a-development-branch, handoffs into dispatch closeout, brainstorm copy into the visual-companion exit. `synlynk init` may create the five paths as documented conventions; do not CI-fail missing blogs. Demote blog to named-release / thematic cluster only.

**Position:** five process folders, skill-gated like specs/plans; domain folders stay optional; kill 1:1 PR blogs. A rule that is not on the write path is not a convention — it is a wish.

## Synthesis
The panel converges on standardizing workflow artifacts, while leaving domain knowledge repo-specific.

Standardize these canonical paths:

- `docs/rca/`
- `docs/archive/`
- `docs/decisions/`
- `docs/handoffs/`
- `docs/brainstorm/`
- `docs/blog/`

`strategy/`, `research/`, `papers/`, and `ux-prompts/` should remain optional and repo-specific. `reports/` should also remain optional: “report” is too generic, and its useful structure depends on whether it means metrics, investigations, market analysis, or project status.

Use the same successful skill-injection pattern as `docs/superpowers/`, but add lifecycle tooling: canonical filename rules, lightweight templates, creation triggers, and CLI/CI checks for misplaced or missing required artifacts. The directories need not all be pre-created; the tool should scaffold them on first use.

Blogging needs a different contract. Keep `docs/blog/` standardized, but abandon literal 1:1 PR-to-post enforcement. The current protocol is passive prose, runs after the critical implementation path, has no generator or merge gate, and imposes a costly essay format. It also conflicts with the release-oriented model and lacks an explicit “not publication-worthy” path. Replace it with a trigger-based policy: require a post for externally meaningful releases or thematic batches, provide a scaffold command, and require an explicit `no blog needed` declaration for other PRs. If literal 1:1 compliance is ever desired, it must be implemented as PR automation that creates or verifies the draft—not as a CLAUDE.md instruction.

Decision: standardize `rca`, `archive`, `decisions`, `handoffs`, `brainstorm`, and `blog` through skill-injected templates plus lifecycle checks; leave `strategy`, `research`, `papers`, `ux-prompts`, and generic `reports` repo-specific; and replace the failing 1:1 Blog Post Protocol with an enforceable, trigger-based release communication workflow.

## Decision
Decision: standardize `rca`, `archive`, `decisions`, `handoffs`, `brainstorm`, and `blog` through skill-injected templates plus lifecycle checks; leave `strategy`, `research`, `papers`, `ux-prompts`, and generic `reports` repo-specific; and replace the failing 1:1 Blog Post Protocol with an enforceable, trigger-based release communication workflow.

> Signatures: see 2026-08-14-round-3-6-where-specs-plans-strategy-doc.json
