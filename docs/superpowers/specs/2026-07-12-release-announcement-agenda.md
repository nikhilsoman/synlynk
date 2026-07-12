# Synlynk Release Announcement — Agenda

**Date:** 2026-07-12
**Goal:** Synlynk release announcement
**Basis:** Current `main` state (v0.11.0 tag + unreleased Job Lifecycle epic + Capability Matrix Hardening/Fleet Scheduler + Dispatch Reliability trio + Vizor Architect Map v2, all shipped but never bundled into a Named Release), `docs/strategy/2026-07-06-four-pov-evaluation-and-company-roadmap.md`

Documentation has fallen behind shipped work. README badge still reads v0.10.0 / 623 tests; actual is v0.11.0-and-unreleased / 973 tests. No Named Release has been cut since v0.11.0 (2026-07-05) despite 3+ thematically related PR clusters landing since (Job Lifecycle epic, Capability Matrix Hardening + Fleet Scheduler, Dispatch Reliability trio, Vizor Architect Map v2) — this itself triggers the Named Release policy.

---

## 1. Cut the Named Release first (blocks everything else)

Per the global Named Release Policy, the docs work below should describe a real, tagged release — not just catch up prose to an untagged `main`.

- [ ] Bump `VERSION` (`synlynk/_constants.py`) — propose `v0.12.0` given the scope (Job Lifecycle epic + Capability Matrix Hardening/Fleet Scheduler + Dispatch Reliability trio + Vizor Architect Map v2 + CI hygiene fix)
- [ ] Consolidate `CHANGELOG.md` `[Unreleased]` section — fold in the four shipped-but-unreleased clusters, not just the Job Lifecycle epic currently listed
- [ ] `gh release create v0.12.0` with release notes
- [ ] One-sentence release pitch (required before anything else makes sense — if this can't be written cleanly, the scope isn't coherent enough)
- [ ] Roadmap rows already show ✅ Shipped for the underlying epics — verify no stragglers

## 2. README (github repo)

- [ ] Version badge → current release tag; test-count badge → `973 passing`
- [ ] **Reframe the hero paragraph around wedge features, not full surface area** (Four-POV, POV 1): the honest first question a multi-agent power user asks is "what are the three commands I run every day?" Lead with flatline/sentinel detection and cross-agent cost tracking — not the full command list (dispatch, jobs, watch, viz, status, probe, doctor, sync, relay, scan, story, score…). Push full surface area into the reference docs, not the hero.
- [ ] Update the "Documentation" PDF table thumbnails/links if PDF filenames or page counts change (Item 3 below)
- [ ] Add a line on the license (MIT, confirmed already in badges) — no change needed unless Epic 0 licensing decision (below) changes it

## 3. Website (synlynk.com)

- [ ] Reposition messaging around the **"neutral coordination layer / Switzerland" narrative** (Four-POV, POV 2) — the durable pitch is cross-vendor routing and comparison, specifically the thing no single model vendor will build because of conflict of interest. Current site likely reads as a feature list; needs a positioning paragraph a founder/exec reader would recognize.
- [ ] **Do not market permission/governance features as enforced controls** (Four-POV, POV 3) — `--allowedTools` is real for Claude, but the Agy translation is a `## Permissions` *context header*, i.e. an instruction to the model, not an enforcement boundary. Any copy implying "access control" or "security policy" needs a qualifier or removal until Epic 3 (enforcement plane) ships. This is a trust/credibility risk if overclaimed publicly — flagged explicitly in the Four-POV doc as a "governance theater" risk.
- [ ] Reflect latest shipped features on the site: Vizor Architect Map v2 (live force-directed graph, PR #167), fleet dispatch scheduler (`synlynk schedule`), dispatch reliability fixes
- [ ] Update version/test-count references site-wide (same staleness as README)

## 4. Quick Start PDFs (3 docs, referenced from README's Documentation table)

- `docs/synlynk-official-reference.pdf` — 14-page full reference (architecture, all commands, agent profiles, relay, SQLite schema, changelog)
- `docs/synlynk-command-reference.pdf` — 9-page command catalog
- `docs/synlynk-quickstart-guide.pdf` — 5-page getting started

All three need a regeneration pass for: new commands shipped since last PDF gen (`synlynk schedule`, `synlynk story ready/draft`, updated `synlynk dispatch` flags), current version number, and the wedge-feature-first framing from item 2 carried into the quickstart guide specifically (it's the first thing a new user reads).

## 5. Blog series (`docs/blog/`)

- [ ] Resolve outstanding `prTBD` placeholders in existing posts (41, 49, 50, 51) with real PR numbers now that they've merged
- [ ] Write new posts for unblogged shipped work: Dispatch Reliability trio (#163 worktree git-refs, #164 stale agent list, #165 harness-internal-timeout detection), CI baseline test-isolation fix (#171 / issue #134)
- [ ] Release announcement post itself — ties the whole series together under the v0.12.0 pitch
- [ ] **Timing decision needed before writing further implementation-detail posts** (Four-POV, POV 4, explicit caveat): 48 public posts already constitute prior art; the US grace period is running on everything already published and there is no EU grace period. If provisional patent filings on sentinel detection, permission translation, or the handoff protocol (Four-POV IP candidates #1–#3) matter, they should precede further detailed disclosure. **This is a business decision for Nikhil, not something to resolve inside the docs story** — flagged here so it isn't missed, not auto-resolved.

## 6. Other release-announcement prerequisites surfaced by the Four-POV doc (Epic 0/2, company-roadmap section)

Not doc-writing tasks, but the Four-POV doc frames these as due "now, before GA" — surfacing them because a public release announcement increases exposure on all of them:

- [ ] **Licensing decision**: Apache-2.0 proposed for the OSS core vs. current MIT — confirm before or explicitly defer past this release
- [ ] **CLA**: doc flags introducing one *immediately*, before external contributions accumulate — a release announcement is exactly what invites first external PRs
- [ ] **Trademark "synlynk"**: unfiled per the doc; a public announcement increases naming-collision exposure
- [ ] **Dependabot findings**: this session enabled Dependabot on the repo and it immediately surfaced 4 vulnerabilities (1 high, 3 moderate) on `main` — worth triaging before a release announcement draws more traffic to the repo
- [ ] **Launch assets**: roadmap already earmarks "HN/dev.to launch hooks" and the BS-7 benchmark narrative as launch assets — not built yet; out of scope for this story unless explicitly pulled in

---

## Explicitly out of scope for this story

- Structured Integration Layer (Epic 1) — pre-GA technical priority, not a docs task
- Enforcement plane (Epic 3), team control plane (Epic 4) — future epics, not release-announcement blockers
