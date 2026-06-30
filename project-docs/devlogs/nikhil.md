# Devlog - Nikhil Soman

## 2026-06-28 — Session: BS-5 Phase 1 Website Scaffold (grok)

### Shipped
- **Phase 1 complete** for story-048f5fe5: standalone `website/` 11ty v3 site.
  - Standard layout: package.json (synlynk-website), .eleventy.js (passthrough+filters+blog stub), base.njk (fonts + fixed nav + S-glyph 28px from extracted svg + Docs/Features/Blog/Changelog + Install CTA + footer), index.njk (8 section shells #top #carousel #relief #how #features #vision #docs #waitlist), main.css (exact tokens + nav + primitives + typography), .gitignore, README.md.
  - Logo: `website/src/assets/img/logo/s-glyph.svg` (extracted icon-only 28px viewBox).
  - `npm run build` → `_site/index.html` with nav + all 8 sections.
  - `npm run serve` configured for port 8081.
  - CSS tokens exactly: --bg:#0E0E0F etc matching hero-v4 + spec.
  - Committed: `feat(bs5): Phase 1 scaffold — 11ty v3 shell, nav, section stubs, design tokens (grok)`
  - Co-Authored-By: Grok <noreply@x.ai>
  - Full `tests/test_capability_scoring.py` : 48/48 pass. Specific -k filter runs clean (0 or 1 matched, no failures).

### Key decisions & implementation notes
- Used 11ty layout frontmatter (not extends blocks) to match existing site/ conventions.
- Logo via passthrough <img>, nav matches task spec (not full mock links).
- _site/ and node_modules/ gitignored; package-lock committed for repro.
- No files outside website/; old site/ untouched.
- Build verified before commit. Phase 2/3 will add content, carousel, canvas by Agy/Grok.

### Next
- Agy: Phase 2 sections + CSS system + templates.
- Review checkpoint 1 for Claude.
- Update gh-pages workflow only in Phase 4.

---

## 2026-06-29 — Session: BS-5 Website Redesign Polish & Merge

### Shipped

**PR #78 — BS-5 Website Redesign (merged to main, 528 tests passing)**
Finished Phase 3 and visual polish/review for synlynk.com:
- Fixed navigation by removing duplicate "Install" CTA and restoring the GitHub anchor link.
- Repositioned the 4 agent logos immediately above the CTA buttons, enlarged them, and removed box container borders and names.
- Fixed layout centering and margins on the main tagline ("Dispatch, monitor...") and terminal carousel.
- Widened the tagline hero install command container and increased font size to avoid layout clipping.
- Restructured color theme contrast in light background sections: overrode `.section-light .section-title` to `#0E0E0F` and darkened body copy.
- Wrote and ran a headless screenshot script to capture visual diagrams for all 25 blog posts, saving them under `assets/blog-heroes/` and populating `blogHeroes.json`.
- Unlinked header/card preview thumbnail visual hero attachments on posts to keep them fallback gradient only, keeping visuals strictly inline.
- Archived the legacy `site/` directory as `synlynk-website-v1-arch/` in the repository.

### Next
- BS-6: brainstorm — repo/workspace visualization: product view · logical view · infra view

---

## 2026-06-28 — Session: BS-13 Live Job Observatory Brainstorm

### Started
Scoped a new brainstorm for a cross-repo live job monitoring board.

### Direction
- Add a read-only `synlynk watch` experience with near real-time refresh, targeting about 10s cadence.
- Group running jobs by repo and stage, and show cost, token, and request accumulation inline.
- Ship both a terminal view and a web view, backed by the same underlying monitoring model.
- Keep interaction limited to opening the relevant terminal or web link from the top-level board; no control CTAs.
- Make job provenance explicit: originating agent, executing agent, and input context size are foundational fields.

### Next
- BS-13 brainstorming session and eventual feed into `synlynk viz`

### Spec
- `docs/superpowers/specs/2026-06-28-bs13-live-job-observatory-design.md`

## 2026-06-27 — Session: v0.9.8 Health Pulse + Lifecycle

### Shipped
**v0.9.8 — exit, repair, sync lifecycle commands (PR #70, 524 tests)**

Closes OB-13–17. Three commands completing the install/uninstall lifecycle:

- `synlynk exit` — strips synlynk sections from tracked instruction files, removes `.agents/` + `.synlynk/`, writes `SYNLYNK_HANDOFF.md`. Dry-run default, `--confirm` to execute
- `synlynk repair` — captures config, exits, re-inits with same parameters
- `synlynk sync` — re-writes instruction sections + creates missing `.agents/` profiles without full reinit
- `_strip_synlynk_section()` helper — removes html/hash/none marker blocks, preserves surrounding user content
- 13 new tests; suite 513 → 524 passing

### Key decisions
- Strip synlynk sections (not delete files): CLAUDE.md has user custom instructions; destroying the file would lose user work
- `_strip_synlynk_section("none")` deletes the file entirely — synlynk owns 100% of `.cursorrules`

### Next
- BS-7 brainstorm 2026-06-28/29 — skill pack interoperability + benchmarks
- v0.10.0 Developer Preview — pipx packaging, `synlynk viz`, README overhaul

## 2026-06-27 — Session: BS-5 Website Redesign Design Phase

### Completed
Full design phase for synlynk.com redesign. Narrative arc locked: C→D→A (reveal hook → unlock → OS vision).

**Deliverables:**
- `docs/brainstorm/bs5-website-redesign/` — 13 HTML files (hero mockups v1–v4, diagram iterations, page structure explorations, Agy's diagram directions)
- `docs/superpowers/specs/2026-06-27-bs5-website-redesign-design.md` — full design spec
- Isometric motherboard diagram (`diagram-isometric.html`) — canvas-based, animated data packets, London Tube metro routes, 4 CPU stacks (Claude/Gemini/Grok/Codex) around central synlynk NPU

**Multi-agent dispatch during session:**
- Agy: 3 diagram direction concepts (connectome / constellation / integrated circuit)
- Codex: SVG implementation (concentric rings) — superseded by isometric approach
- Grok: image gen failed (CLI `--single` flag issue — deferred)

**Key design decisions:**
- Isometric motherboard wins over SVG network graph — CPU-stack-per-harness metaphor maps to model tier hierarchy
- Persistent install bar (always visible) over modal copy component
- Hero split: byline (problem, muted) + headline (unlock, gradient)
- Carousel: one slide at a time with command pills, 4 commands (init/join/dispatch/status)
- No carousel peek element — looked disconnected

### Next
- Implementation session in ~1 week: convert hero-v4.html to 11ty/Nunjucks, integrate isometric diagram, build actual site pages

## 2026-06-26 — Session: v0.9.7 Grok Agent Support

### Shipped
**v0.9.7 — Grok as first-class fourth agent peer (PRs #62/#63/#64, merged 2026-06-26, 488 tests)**

Multi-agent delivery: Agy owned Tasks 1–3 (PR #62), Codex owned Tasks 4–6 (PR #63), Claude owned Task 7 + spec + plan + PR review (PR #64). Claude sole reviewer.

- T1: AGENT_CAPABILITY_BASELINES["grok"] + AGENT_DISCOVERY_DEFAULTS + version probe (`grok -v` + pattern)
- T2: `_grok_md` template + `_INSTRUCTION_TARGETS` + `_MARKER_STYLE_FOR_TOOL` entries
- T3: Init wizard — GROK.md in trio_content/_agent_guards, agent_slots/agent_set defaults expanded, argparse updated
- T4: `_inject_grok_rules()` — `--rules GROK.md` (all grok exec) + `--rules .synlynk/context.md` (headless only)
- T5: `dispatch_agent()` — `--always-approve` fallback to `--permission-mode bypassPermissions`; `--output-format json`
- T6: `extract_tokens()` nested usage JSON pattern; `extract_model_version()` tier-2 agent profile path
- T7: GROK.md written for synlynk repo itself (100 lines, markers bookending)

### Dispatch issues surfaced
- **story-5b86c353** — both concurrent dispatch jobs wrote to global `.synlynk/context.md` (RCA below); deferred fix post-v0.9.7
- **Same-worktree collision** — Codex hit `index.lock` while Agy held it; filed for worktree-per-job isolation

### Key decisions
- Separate GROK.md (not injecting into CLAUDE.md): Grok auto-reads CLAUDE.md natively; GROK.md is synlynk's managed section via `--rules`
- `--always-approve` as default dispatch flag; `.agents/grok.json` `always_approve_unsupported: true` → `--permission-mode bypassPermissions`
- `grok-composer-2.5-fast` = Cursor Composer 2.5 Fast (not xAI-native) — stored verbatim
- `Co-Authored-By: Grok <noreply@x.ai>`

### Next
- v0.9.5 Health Pulse (`synlynk doctor`, per-command silent auditor)
- v0.9.6 Exit + Repair + Sync
- story-5b86c353 fix: per-job context file (`.synlynk/contexts/<job_id>.md`)

---

## 2026-06-26 — Bug RCA: story-5b86c353 — dispatch job context overwrites global context.md

### RCA — `dispatch_agent` writes job context to global `.synlynk/context.md`

**Story:** `story-5b86c353`
**Severity:** Sev2 — concurrent dispatches race on a shared file; no data loss but context is stale for all but the last dispatch
**Found:** 2026-06-26 during v0.9.7 Grok dispatch (two agents dispatched in parallel)

#### Root cause

`dispatch_agent` calls `generate_context(scope=scope)` (line 2169) or `_generate_task_context(story_id)` (line 4851). Both functions write their output to the single shared file `.synlynk/context.md`. There is no per-job context file.

The per-job directory structure exists for logs (`.synlynk/logs/<job_id>.log`) and prompts (`.synlynk/prompts/<job_id>.md`) but was never extended to context.

Additionally: when `dispatch_agent` is called without a `story_id` (the common case for ad-hoc dispatch), line 2165 falls back `scope = "full"` even when `context_mode == "task"`, generating a full 55KB global snapshot.

The context text IS embedded in the prompt file at format time (line 2193), so dispatched agents receive correct context regardless. The race condition is real but silent — agents are not harmed in practice unless they re-read `.synlynk/context.md` mid-job via `--rules` injection.

#### Impact

- Concurrent dispatches overwrite each other's context.md — last writer wins
- The grok `--rules .synlynk/context.md` injection (added in v0.9.7) would expose agents to a stale file if they re-read it during execution
- `synlynk relay broadcast context` serves the clobbered file to all subscribers

#### Fix (deferred — implement after Grok v0.9.7 PRs merge)

Three-part change to `synlynk/__init__.py`:

1. **`dispatch_agent`**: After `job_id` is generated (line 2154), write context to `.synlynk/contexts/<job_id>.md` instead of calling `generate_context` directly. Pass the job-specific path into the prompt.

2. **`_generate_task_context`**: Accept an optional `out_path` parameter. Default to `.synlynk/context.md` only when called from non-dispatch paths (exec, daemon). Dispatch callers pass the job path.

3. **`_inject_grok_rules` (v0.9.7 addition)**: Inject `.synlynk/contexts/<job_id>.md` (passed via env or arg) in headless dispatch mode instead of the global `context.md`. Interactive exec mode keeps injecting the global path (refreshed by `exec_command` → `generate_context()` at line 6250).

#### Not broken today because
- Prompt files embed the context at dispatch time (static snapshot)
- The two v0.9.7 grok dispatch jobs (job-aad2f7f1, job-4eb3a76b) each got their context embedded in their prompt files before the race could affect them

---

## 2026-06-24 — Session: v0.9.4 Context/Dispatch/Relay + Three-Tier Docs Suite

### Shipped

**v0.9.4 — Context / Dispatch / Relay (PR #60, merged 2026-06-24, 472 tests)**

All 5 tasks completed by Codex via `synlynk dispatch`:
- T1: SQLite-primary task state — `stories.status` column; `_generate_todo_md()` writes `todo.md` as generated view; `_import_todo_to_stories()` syncs hand-written tasks (now idempotent, title-dedup via MD5)
- T2: Agent profiles — `.agents/<agent>.json` → `_load_agent_profile()`; `synlynk agent configure <name>`; `context_mode=None` default (profile fills None, explicit CLI flag wins)
- T3: Jobs + preflight — `cmd_jobs()` reads `daemon_jobs` SQLite with `--watch`; `_preflight_dispatch()`; mirrors jobs to `daemon_jobs` on dispatch
- T4: HTTP SSE relay — `RELAY_EVENT_TYPES` (7 types); `SynlynkRelay` broker (`GET /events`, `POST /publish`, port 27472); `synlynk relay start/broadcast`
- T5: VERIFY_SKIP sentinel — `_extract_compliance_tags()` word-boundary regex; Pattern 4 fires informational alert when exit 0 but no test/verify evidence

**Dispatch fixes shipped in PR #60 (from R1 Claude review of the branch):**
- `cwd=os.getcwd()` in `Popen` — Agy was resetting its CWD to scratch space
- `dispatch_flags` key in `AGENT_CAPABILITY_BASELINES` — `--dangerously-skip-permissions` scoped to dispatch only, not all exec
- `_import_todo_to_stories()` deterministic MD5 ID + title-dedup guard (no duplicate rows on re-run)
- `queue.Full` properly classified in relay (slow subscriber, keep alive vs. dead)
- `--watch` loop now catches render exceptions gracefully

**Three-tier documentation suite (v0.9.4):**
- `docs/synlynk-official-reference.html` + PDF — 14-page full reference (architecture, all commands, agent profiles, relay, SQLite schema, changelog)
- `docs/synlynk-command-reference.html` + PDF — 9-page command catalog by category with flags, options, usage scenarios
- `docs/synlynk-quickstart-guide.html` + PDF — 5-page getting-started guide

**GitHub release v0.9.4 cut.**

**Website updated:** docs download section with thumbnail cards, v0.9.4 roadmap, new Workgroup Relay feature card, agent profiles in capability card, hero description updated, version badge 0.9.4, Releases nav link added.

### Dispatch Dogfooding Learnings
- Codex: reliable for TDD loops — completed all 5 tasks cleanly
- Agy: auth expired mid-session (re-auth via `! agy`); CWD fix worked; stalls on multi-step tasks that require blocking shell commands (good for read-only only)
- Claude headless: needs `--dangerously-skip-permissions` scoped to dispatch_flags (now correct post-R1)
- `dispatch_flags` pattern: good general pattern for any future dispatch-only flags

### Next
BS-2 (Onboarding + Mode Taxonomy), BS-3 (Agent Behaviour), BS-4 (Command Audit) brainstorm series — unblock Agent Ecosystem Epic (v0.8.1–v0.8.4)

---

## 2026-06-23b — Session: v0.9.2 Release SOP

### Shipped

**v0.9.2 Release SOP — PR #54**
All 6 SOP items completed:
1. VERSION bumped to `0.9.2` in `synlynk/__init__.py`, `install.sh`, and version test (394 tests pass)
2. `CHANGELOG.md` backfilled with all 10 missing releases: v0.4.1, v0.4.2, v0.5.0, v0.6.0, v0.6.1, v0.7.0, v0.8.0, v0.9.0, v0.9.1, v0.9.2
3. `README.md` updated: v0.9.1 marked shipped, v0.9.2 marked shipped, v0.9.3/v0.9.4 as next, lede updated to v0.9.2 features
4. `site/src/_data/releases.json` updated: v0.9.1 + v0.9.2 patches added to v0.9 entry, theme updated
5. Blog post #21 written: v0.9.2 Team Onboarding + Consensus (join, team status, decide, arbitration, decisions as first-class artifacts)
6. Quick Start Guide updated v0.4.1 → v0.9.2: cover, command reference (all v0.5–v0.9.2 commands added), dispatch/consensus page, roadmap back page; PDF regenerated at 1.3MB

### Next
Agent Ecosystem Epic (v0.8.1–v0.8.4) — Foundation spec first when ready

---

## 2026-06-23 — Session: v0.9.2 Wave Merges + Agent Ecosystem Brainstorm

### Shipped

**v0.9.2 — Team Onboarding + Consensus (PR #30, merged)**
Wave 1 (T2→T1→T3) and Wave 2 (T4→T5→T6) all merged into main:
- T1: `estimated_tokens` + `actual_tokens` columns on stories table; `synlynk story create --tokens`
- T2: `_check_upstream_divergence()` — warns on unpulled remote commits; injected into `update_costs()` + `checkpoint()`
- T3: `_seed_devlog()`, `_generate_ai_context_files()`, `_build_team_digest()` helpers
- T4: `synlynk join` — onboards new user, seeds devlog, sets team mode
- T5: `synlynk team status` — prints team digest
- T6: `synlynk decide` — multi-agent consensus panel with signed Decision records
- 394 tests passing

### Brainstormed + Specced

**Release Agent** (`docs/superpowers/specs/2026-06-22-release-agent-design.md`)
Config-driven release pipeline. Steps: run_tests → bump_version → git_tag → github_release → update_binary → blog_post. Per-step consent (auto/notify/approve). Readiness detection: version gap + commits since last tag. Runtime state in `.synlynk/release-state.json`.

**TPM Agent + Lifecycle-as-first-class-entity** (`docs/superpowers/specs/2026-06-23-tpm-agent-design.md`)
Key insight: lifecycle is a typed, configurable artifact chain — not just "Architect → TPM → Agents". Each stage has an agent attachment point and produces an actionable artifact. Per-story lifecycle state in state.db (`lifecycle_instances` + `tasks` tables). TPM assembles waves from dependency graph, assigns agents via capability matrix, surfaces cross-story batching opportunities. Self-improving: writes to `capability_ratings` after every task; ROI summary printed after every wave.

**Three agent design principles** (applies to all future agents):
1. Opt-in at `synlynk init` / toggleable via `synlynk config --agents`
2. Nothing breaks without agents — core workflow always functional
3. Agents must earn their place — ROI summary after every wave

### Roadmap update

Regrouped v0.8.1–v0.8.4 into Agent Ecosystem Epic (parked for contiguous effort):
- v0.8.1: Foundation (lifecycle engine, opt-in gate, Support Engineer unified)
- v0.8.2: TPM Agent + Release Agent
- v0.8.3: Marketing Intern + PM Agent
- v0.8.4: Docs Keeper + Security Guard + Compliance Officer

### Brainstorm visuals saved
`docs/brainstorm/tpm-agent/` — 4 files: tpm-lifecycle, lifecycle-schema, tpm-board, tpm-design

### Next
- Pick up Agent Ecosystem Epic when ready — start with v0.8.1 Foundation spec
- Older brainstorm sessions in `.superpowers/brainstorm/` not yet copied to `docs/brainstorm/` — ~18 sessions with HTML content

---

## 2026-06-22 — Session: Post-v0.9.0 Install + Init Hardening

### Context
First use of synlynk in an external repo (rxcc). Exposed two production gaps immediately — neither caught by the 365-test suite.

### Shipped (3 hotfix commits to main)

**1. Install broken after package split (`fix: update install.sh for v0.9.0 package split`)**
- Root cause: `install.sh` was written when `bin/synlynk.py` was self-contained. After the v0.9.0 package split, the installed shim's `sys.path.insert` resolved to `~/.synlynk/` — which has no `synlynk/` package.
- Fix: install.sh now copies `synlynk/` to `~/.synlynk/lib/synlynk/`. Shim's path line patched at install time to use `~/.synlynk/lib`. Curl install downloads `synlynk/__init__.py` directly. Also patched the already-installed shim immediately for the user.

**2. Configurable `project_docs_dir` (`fix: configurable project_docs_dir`)**
- All ~35 hardcoded `"project-docs/"` strings replaced with `_docs_dir()` helper.
- Reads `project_docs_dir` from `.synlynk/config.json` (default `"project-docs"` — no change for existing repos).
- `synlynk init --docs-dir .` writes the setting before any file creation. All downstream functions (generate_context, checkpoint, update_costs, get_mode, _deep_scan) respect it.

**3. Doc migration on init (`feat: synlynk init migrates existing docs instead of generating blank skeletons`)**
- `_find_existing_doc()` searches root, `project-docs/`, project-prefixed variants (`rxcc_memory.md`), uppercase names. First match >200 bytes wins.
- `_write_informed_skeleton()` now migrates found content verbatim; generates blank skeleton from git history only as last resort.
- Output now shows: `✓ ./roadmap.md  (migrated from project-docs/roadmap.md)` vs `(generated from git history)`.

### Key decisions
- AGY ran `synlynk init` in rxcc, saw two doc sets, proposed symlinks. User declined. This exposed the gap cleanly. Fixed the root cause rather than the symptom.
- `_find_existing_doc()` logic will be reused in `synlynk migrate` (invisible-state spec step 6).

### Tests
- 365 passing (unchanged — no regressions, hotfixes were structural only)

### Next
- User review of invisible-state spec (`docs/superpowers/specs/2026-06-21-invisible-state-design.md`) before v0.9.1 implementation plan

## 2026-06-21
### Session: v0.9.0 Kernel Fixes + Package Split — PR #53, merged

- **Merged:** PR #53 (`feat/v0.9.0-kernel-fixes`) — all 7 tasks + cross-review fixes shipped
- **Method:** Hybrid dispatch — Claude subagents (Tasks 1–4, 6 fallback), AGY (Task 5 Ed25519), Codex (Task 7 package split). First PR built using synlynk's own `dispatch_agent` mechanism.
- **What shipped:**
  - **Task 1 — Scoped context:** `generate_context(scope="task:<id>")` + `_generate_task_context()` — story metadata, active tasks only, up to 20 domain-filtered source files. Eliminates 7-day devlog dump from every dispatch.
  - **Task 2 — Relevant Files injection:** `_relevant_files_for_story()` queries story `engg_domain` against scan cache skeleton; up to 10 matching paths injected as `## Relevant Files`.
  - **Task 3 — Verify contract:** `_verify_contract_for_story()` derives pytest invocation from story title; injected as `## How to Verify` when `tests/` exists.
  - **Task 4 — Per-agent framing:** `_format_prompt_for_agent()` — Codex gets `## Task Criteria` bullets; AGY gets `Task: ` prefix + 2000-char context; Claude gets full narrative.
  - **Task 5 — Ed25519 signing (AGY):** `_ensure_identity_key()`, `_sign_capability_rating()`, `synlynk identity init`. `capability_ratings.ed25519_sig` now populated on every write.
  - **Task 6 — Anti-gaming cap (Claude fallback):** `_extract_auto_signals` returns `test_count`; `quality_auto` capped at 5.0 when `test_pass_rate==1.0 and test_count<3`. 4 new tests in `test_capability_scoring.py`.
  - **Task 7 — Package split (Codex):** `bin/synlynk.py` → 5-line shim; all code in `synlynk/__init__.py`. Test sys.path updated across all 4 test files.
  - **Cross-review fixes (d450e19):** `try/except` around ssh-keygen; `sig_file=None` init + finally cleanup; `entry.get("symbols") or []` (2 sites); `if not pattern: return ""`; `with open()` for pub + sig reads.
  - **Python 3.8 compat (54102b4):** `str | None` → `Optional[str]` in `_extract_diff`.
- **Tests:** 365 passing (219 test_synlynk + 47 test_capability_scoring + 99 other)
- **Blog post:** `docs/blog/19-v0.9.0-kernel-fixes.md`
- **Key learning:** AGY can internally `cd` away from worktree CWD during background dispatch — adds noise/incorrect results. CWD pinning needed in dispatch context (backlog).
- **Roadmap:** v0.9.0 → ✅ Shipped

## 2026-06-17
### Session: v0.4.1 Instruction Reach — PR #45, merged

- **Merged:** PR #45 (`feat/v0.4.1-instruction-reach`) — v0.4.1 Instruction Reach fully shipped
- **Method:** Subagent-driven development (session resumed from prior context). 10 TDD tasks. Final code review subagent (whole implementation), post-review fixes, R1 + R2 review cycles, then merge.
- **What shipped:**
  - **AGY cleanup:** `"gemini"` CLI removed from `AGENT_CAPABILITY_BASELINES`, `AGENT_DISCOVERY_DEFAULTS`, `_probe_model_version` probe commands, argparse help. `GEMINI.md` template now AGY-only (`agy-2.x`, no transition note). `agent_slots` `"agy":"gemini"` → `"agy":"agy"`.
  - **Section marker system:** Three styles — `html` (`<!-- synlynk:start -->` / `<!-- synlynk:end -->`), `hash` (`# synlynk:start`), `none` (synlynk owns whole file). `_extract_synlynk_section()` + `_compute_section_sha()` helpers.
  - **`_write_instruction_file(path, tool, content, marker_style)`:** Three-case logic — create (file absent), append (no markers), replace-section (markers found). SHA covers section content only — user edits outside markers never trigger false drift.
  - **Tool-native templates:** `_build_cursor_mdc()` (MDC frontmatter, `alwaysApply: true`), `_build_copilot_instructions()`, `_build_windsurf_rules()` (6-line hash-marked).
  - **`_INSTRUCTION_TARGETS`:** Single source of truth — 7 tracked files as `(path, tool, marker_style, detection_fn)`. Guards derived from `detection_fn` in `init()`; no duplicate `ext_guards` dict.
  - **SHA manifest (`.synlynk/instructions.json`):** Written by `init()` and `_write_instruction_manifest()`. Tracks per-file section SHAs.
  - **`init()` refactored:** Now writes all 7 targets; uses `_INSTRUCTION_TARGETS` for guards.
  - **`_check_instruction_drift()`:** Hooked into `exec_command()`. SHA-compares each manifest entry against current file. Fires `INSTRUCTION_DRIFT` sentinel, updates manifest SHA (deduplication — won't re-fire next exec).
  - **`synlynk instructions` CLI:** `status` (columnar table, 5 status values) / `diff` (user content outside markers) / `update` (re-generate + refresh manifest) / `ack` (remove INSTRUCTION_DRIFT from sentinel.md).
  - **`DB_PATH` fix (R1):** Moved from `.synlynk/state/state.db` (flat-file collision with v0.3.0 daemon state file) to `~/.synlynk/projects/<8-char-git-root-hash>/state.db`. All worktrees for a repo now share one DB (resolves worktree isolation bug).
  - **`isolated_db` autouse fixture (R1):** Added to `tests/conftest.py` — every test gets its own temp `state.db`; no cross-test DB pollution.
  - **Post-review fixes:** `ext_guards` dict eliminated from `init()` (guards now from `_INSTRUCTION_TARGETS[i][3]`); `AGENTS.md` added to `_AGENT_FILE_NAMES` (scan now surfaces it).
- **Tests:** 265 passing (34 new in `tests/test_instruction_reach.py`)
- **Blog post:** `docs/blog/13-v0.4.1-instruction-reach.md`
- **Roadmap:** v0.4.1 row added between v0.4.0 and v0.5.0, marked ✅ Shipped.

### Session: Quick Start Guide PDF Generation (v0.4.1)
- **Activity:** Updated and compiled the modern, minimalist Apple-style quick start guide to reflect v0.4.1 Instruction Reach features. Relaid out Page 6 to fix overflow and edge-to-edge layout issues.
- **Updates:**
  - Modified `docs/synlynk-quickstart-apple.html` to bump versioning to v0.4.1 and set the theme to Instruction Reach.
  - Added the fifth sentinel pattern `DRIFT` (Instruction file edited outside synlynk) to the Safety Systems page.
  - Updated Command Reference on Page 6: relayout to 2-column command grid with 16mm margins (was edge-filling). Added `synlynk instructions status/diff/update/ack` commands.
  - Updated roadmap on Page 7 back cover to show v0.5 and v0.6 as `✓ Live · June 2026`.
  - Fixed all page containers: `min-height: 297mm` → `height: 297mm; max-height: 297mm; overflow: hidden` to prevent Chrome overflow splitting.
  - Fixed all 6 "gemini" references → "agy" in terminal/diagram samples.
  - Generated PDF using headless Google Chrome at `docs/synlynk-quickstart-apple.pdf`.

### Session: v0.4.2 Task Status Model — PR #46, merged

- **Merged:** PR #46 (`feat/v0.4.2-task-status-model`) — 5-state todo.md model
- **What shipped:**
  - **`TASK_STATUSES` constant:** `"[ ]": "active"`, `"[x]": "done"`, `"[-]": "deferred"`, `"[~]": "superseded"`, `"[>]": "absorbed"` — module-level dict, testable
  - **`generate_context()`:** deferred `[-]` tasks now included under `### Deferred`; superseded `[~]` and absorbed `[>]` excluded (resolved, no agent attention needed)
  - **`checkpoint()`:** archives `[x]`, `[~]`, `[>]` as "Resolved"; keeps `[ ]` and `[-]`; devlog section renamed "Resolved (checkpoint)"
  - **Agent instruction templates:** all 3 builders (`_build_templates`, GEMINI.md/AGENTS.md variant, `_build_windsurf_rules`) updated with 5-state legend instead of "Mark tasks `[x]`"
  - **`init()` todo template:** HTML comment legend `<!-- Status: [ ] active  [x] done  [-] deferred  [~] superseded  [>] absorbed -->`
- **Tests:** 251 passing (7 new)
- **Blog post:** `docs/blog/14-v0.4.2-task-status-model.md`

### Session: Version sync fix — PR #47, v0.6.1 GitHub release

- **Bug found:** `VERSION = "0.4.2"` while GitHub releases were at v0.6.0; `synlynk upgrade` showed "upgrade available: v0.6.0" perpetually after installing from main
- **Root cause:** v0.5.0 and v0.6.0 features were fully in `bin/synlynk.py` but `VERSION` constant was never synced to match published GitHub release tags
- **Fix (PR #47):** `VERSION = "0.6.1"` — reflects v0.6.0 base + v0.4.1 instruction reach + v0.4.2 task status model patches
- **Release:** Cut GitHub release `v0.6.1` with full changelog; `synlynk upgrade` now reports "latest version" correctly
- **Tests:** 251 passing

## 2026-06-14
### Session: v0.6.0 Job Control — R2 fix, merge PR #42

- **Merged:** PR #42 (`feat/v060-job-control`) — v0.6.0 Job Control + model-aware capability engine fully shipped
- **R2 critical bug fixed:** Tier resolution bypass in `_write_capability_rating()` — calling `extract_model_version(log_text, agent=agent)` fell through to Tier 3 (config default) when no synlynk-meta header present, then compared config default against live-probed `model_at_dispatch`, incorrectly setting `split_model=1` on normal single-model runs and silently excluding them from `capability_scores` aggregation.
  - Fix: extract Tier 1 only via `agent=None`, resolve hierarchy explicitly (Tier 1 > Tier 2 > Tier 3), flag `split_model=1` only when both Tier 1 and Tier 2 are concretely known and differ.
- **Also applied:** `quality_auto` normalization (`weighted_sum/total_weight`) from PR #44 — this branch predated that hotfix merge.
- **Tests:** 43 passing (2 new R2 regression tests)
- **Blog post:** `docs/blog/12-pr42-v0.6.0-job-control.md`
- **Roadmap:** v0.5.0 + v0.6.0 marked ✅ Shipped. Next: v0.7.0 async pipeline + daemon.

### Session: Quick Start Guide PDF Generation (v0.6.0)
- **Activity:** Designed and compiled a modern, minimalist Apple-style quick start guide covering all features of synlynk (up to v0.6.0).
- **Updates:**
  - Modified `docs/synlynk-quickstart-apple.html` to bump versioning to v0.6.0.
  - Refined Command Reference on Page 6: converted to a 2-column grid layout to fit `Story & Capability Scoring (v0.5.0/v0.6.0)` commands (`story create/list`, `score add/list`, `score attest`, `pr check`).
  - Replaced outdated "Hold off on dispatch..." warning callout on Page 6 to indicate that the Capability Engine and Smart Routing are fully live.
  - Marked v0.5 and v0.6 milestones as Live on Page 7 roadmap.
  - Generated PDF using headless Google Chrome at `docs/synlynk-quickstart-apple.pdf`.
  - Copied compiled PDF to root `synlynk_quick_start.pdf` and `docs/synlynk-quickstart-guide.pdf`.

### Session: v0.4.0 Hybrid Workgroup Bootstrap

- **Shipped:** v0.4.0 — 14 TDD tasks, 11 commits, 183 tests (PR #39, open)
- **Method:** Full subagent-driven development via `superpowers:subagent-driven-development`. Fresh subagent per task, spec + quality review after each. Session hit Claude rate limit mid-flight (Tasks 9-11 partial); resumed directly in main session.
- **Pre-implementation fix:** Tokq memory unit schema gap — redesigned from file-grain to 5 purpose-typed DB view units (`strategic`, `context`, `execution`, `activity`, `capability`). Visual in `docs/brainstorm/tokq-data-metamorphosis/`. Schema fix committed separately (PR #37, merged).
- **Bug caught in review:** `_reconcile_jobs()` was catching `PermissionError` alongside `ProcessLookupError` and marking jobs failed. `PermissionError` from `os.kill(pid,0)` means the process exists but is unsiglable — not dead. Fixed to `except ProcessLookupError:` only.
- **What shipped:**
  - `AGENT_CAPABILITY_BASELINES` (claude/gemini/codex/agy), job store constants, ANSI helpers
  - `_load_jobs()`, `_save_jobs()`, `_reconcile_jobs()` (PID probe on startup)
  - `_check_agent_functional()`, `discover_agents()` with configurable paths
  - `_static_scan()` (git log + README + file tree)
  - `_write_informed_skeleton()`, `_llm_enrich()` (opt-in, non-interactive)
  - `init()` refactored to 6-step wizard: scan → **Magic Moment 1** (workgroup table) → doc bootstrap → LLM enrichment offer → cloud nudge → finalise
  - `dispatch_agent()` with `start_new_session=True` background dispatch
  - `cmd_jobs`, `cmd_logs`, `cmd_shell`, `cmd_launch`, `cmd_run_trio`
  - Subcommand wiring in `main()` + 4 new E2E tests
- **Milestone:** First release where `synlynk dispatch claude --task "..."` actually works end-to-end. **Magic Moment 2** — parallel dispatch from shell — is now real.
- **Next:** v0.5.0 Capability Engine — SQLite WAL, data-driven capability routing, `synlynk migrate`.

## 2026-06-10
### Session: v0.3.1 Sentinel + Observability + E2E Test Suite

- **Discovery:** Upgraded installed synlynk from v1.2.0-lite → v0.3.0; found `extract_tokens()` and `update_costs()` were silently dropped in v0.3.0 TTY pass-through refactor. Confirmed v0.5.0 state.db spec explicitly depends on `extract_tokens()`.
- **Decision:** Insert v0.3.1 patch before v0.4.0 to restore regressions and harden the sentinel layer while the surface area was open.
- **Shipped:** v0.3.1 — 9 features, 40 new tests, 12 commits (PR #29, merged 2026-06-10):
  - `extract_tokens()` + `update_costs()` restored; tee-based stdout capture for non-interactive execs; cost pulse after each non-interactive exec
  - `WatchDaemon._health()` tri-state + `check_daemon_health()` ZOMBIE_DAEMON CRITICAL alert
  - `check_stall()` using `.synlynk/state` mtime + `exec_timeout_minutes` config key
  - `check_sentinel_patterns()` — flatline (existing) + success loop (new) + quota-exhausted (new)
  - `_check_pre_exec_gate()` — CRITICAL alerts block exec; `synlynk exec --force` bypasses
  - `_compute_burn_rate()` + burn rate / runway in `synlynk status`
  - Context bloat warning in `generate_context()` at 32 KB / 64 KB thresholds
  - `synlynk sentinel list/clear` CLI with structured `[SEVERITY] [TIMESTAMP] CODE:` format
  - VERSION bumped to 0.3.1 in `bin/synlynk.py` and `install.sh`
- **Shipped:** E2E test suite — 17 black-box CLI tests in `tests/test_e2e.py` (PR #30, merged 2026-06-10)
  - `Cli` helper class wraps subprocess calls; `cli` fixture provides initialized project
  - Covers: CLI basics, exec (exit codes, telemetry), sentinel CRUD, pre-exec gate, status
  - `pytest.ini` registers `e2e` mark; `pytest tests/` now runs 140 tests total
- **Method:** First full subagent-driven development session — 10 tasks, fresh subagent per task, spec + quality review after each. Caught 2 real bugs before PR: severity filter false-positive (substring → regex), dead `check_flatline()` left after rename.
- **Milestone:** `main` is now v0.3.1. Release checklist = `pytest tests/` (140 tests). v0.4.0 is next.

## 2026-06-07
### Session: Workspace & Multi-Repo Design

**Activity:** Third brainstorm session. Designed workspace concept (multi-repo support), machine-level identity, event-log team sync. Resolved the async drift concern that makes export/import unworkable at agentic velocity.

**Key Outcomes:**

1. **Workspace concept:** Unit of organization above a repo. One product = one workspace, N repos. Solo dev gets workspace with one member — invisible. `~/.synlynk/workspaces/<name>/state.db` is the single state store per product.

2. **Machine-level identity:** `~/.synlynk/identity.key` — one Ed25519 keypair per person per machine. Closes Gap 10 (network identity). Per-project keypair retired.

3. **Cross-repo Epics first-class:** One Epic spans repos. Stories have `repo_id` FK. Architect sees full cross-repo epic. Builder/Verifier sees workspace shared + repo slice.

4. **Event-log sync replaces export/import:** Daemon pushes new events to per-member branch in shared git repo every 5 min. Max drift ≈ 5 min — workable at agentic velocity. Becomes NATS at Tokq Alpha.

5. **Simulated team on one machine:** `git config user.name` switch — events record different git_user, all signed by machine key. Full cost attribution per simulated member. Enables Gaurav/Kunal simulation.

6. **Schedule impact:** workspace-aware init at v0.4.0, workspace join at v0.5.0, team attribution at v0.6.0, event sync at v0.7.0 (with daemon). Gap 10 closed.

**Spec committed:** `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md`

**PR opened:** https://github.com/nikhilsoman/synlynk/pull/28

---

### Session: Agent Identity, Dispatch & Entitlements + Arc Gap Analysis

**Activity:** Second major brainstorm session. Designed agent identity (two-layer: local Ed25519 + Role + Agent Profile), addressability (inbox table → NATS), dispatch architecture (4 modes), and entitlements (authorization + sandboxing). Followed with a milestone-wise gap analysis covering v0.4.0 through Tokq GA.

**Key Outcomes:**

1. **Identity is two-layered:** Local Identity (Ed25519 keypair, machine-scoped) answers "who made this decision." Role (Architect/Builder/Verifier) answers "what can this work touch." Agent Profile (CLI × model × environment × competency) answers "who fills this role best right now." These never mix.

2. **Ed25519 identity pulled forward from v0.9.0 to v0.5.0.** Every dispatch event and completion event is signed. Audit trail is non-repudiable at v0.5.0, verified by Tokq cloud at Tokq Alpha.

3. **Dispatch: 4 modes.** A=daemon (persistent, primary). B=self-chain (completion triggers re-evaluate). C=`synlynk dispatch` one-shot (universal fallback, CI/cron-compatible). D=agent-native scheduling (`use_native_scheduling` flag in agent_profiles). Fallback priority: A fails → C always works.

4. **Dispatch address → inbox table.** Logical address `synlynk://<project_id>/roles/<role>/inbox` resolves to state.db row today, NATS subject at v1.0. Forward-compatible scheme.

5. **Human-agent bridge is email, not dispatch.** Send-only SMTP at v0.7.0. Approval via `synlynk story approve <id>` CLI (not email reply). Gmail reply parsing deferred to v0.8.0.

6. **Entitlements: two layers.** Authorization (gate before dispatch — auto/approval/hold/reject). Sandboxing (constraints while running — token ceiling, time ceiling, network, path ACLs). Merge to main: always approval-required, no override.

7. **Gap analysis completed.** 12 gaps across v0.5.0–v1.0.0 identified. Priority: Gap 1 (v0.5.0 scope split) is the only blocker for next implementation plan. Gaps 2–4 (v0.6.0 design questions) can be resolved in one session.

**Specs committed:**
- `docs/superpowers/specs/2026-06-07-agent-identity-dispatch-design.md`
- `docs/superpowers/2026-06-07-arc-gap-analysis.md`

**Next:** Implement v0.4.0 (Trio Protocol — spec is ready). Then gaps 1–4 reconciliation session before v0.5.0 plan.

---

### Session: State DB & Agentic PM Design

**Activity:** Full brainstorm session. Diagnosed the merge conflict root cause (state branching with code), designed the state.db migration from project-docs/, and designed the full Agentic PM hierarchy as a consequence.

**Key Outcomes:**

1. **Root cause confirmed:** `project-docs/` tracked in git causes worktree snapshots to drift. The fix: state.db at `~/.synlynk/projects/<project_id>/` shared by all worktrees. Core invariant: state never branches.

2. **Agentic PM hierarchy locked:** Project → Arc → Phase → Epic → Story → Event. Arc is the strategic direction layer missing from all existing PM tools — handles pivots, convergences, and external triggers. Phase is structural backbone. Epic = one implementation plan. Story = one agent task with `done_criteria` and dependency graph. Event = append-only universal log replacing devlogs.

3. **Token budget as execution constraint:** `estimated_tokens` on stories replaces story points. Agent routing: capability score → quota headroom → cost. `agent_quotas` table tracks per-agent limits. Throughput = tokens/quota-period.

4. **Costs fully attributed:** `costs` table gains project FKs (`story_id`, `epic_id`, `phase_id`). Phase-level cost rollup now queryable.

5. **Platform sync:** `external_refs` table maps to GitHub/Jira/Linear. state.db is canonical; platforms are views.

6. **Schema verified against generate_context():** Three schema corrections found — memory uses `heading/body` (not key/value); tasks use `milestone` not `priority`; roadmap needs `os_layer` and `infrastructure` columns.

7. **Spec committed:** `docs/superpowers/specs/2026-06-07-synlynk-state-db-agentic-pm-design.md`

**Next:** Agent identity, addressability, scheduling, entitlements brainstorm.

---

## 2026-06-06
### Session: Unified Roadmap — OS Framing, Tokq Convergence, Tokq Gap Analysis

**Activity:** Full-day brainstorm + doc consolidation session. Scanned all proposals across the
repo, assessed competitive positioning vs. GStack/SuperPowers, converged the Tokq + synlynk vision,
designed the v0.4→v1.0 release staircase, absorbed the SQLite→NATS infrastructure arc, and closed
5 Tokq PRD requirement gaps.

**Key Outcomes:**

1. **Positioning locked:** "The OS for multi-agent development." Tier model (Solo/Team/Enterprise)
   retired. OS layer model replaces it — one product, increasing depth through 8 releases.

2. **Competitive positioning resolved:** GStack, SuperPowers, HermesAgent, OpenClaw, NmoClaw are
   Applications layer tools. synlynk is the OS they run on. Not competition. Coexistence via Open
   Context Protocol (two commands: `context --for` / `checkpoint --from`).

3. **Tokq convergence:** Recognized synlynk (May 2026) was the missing local OS client that Tokq
   (Jan 2026) always needed. Same author, same vision, different ends of the stack. Unified:
   synlynk = local OS, Tokq = cloud layer. Bridge at v1.0 via NATS leaf node.

4. **Release staircase designed (v0.4→v1.0):** 7 releases, each usable on its own, each unlocking
   one new capability. SQLite→NATS infrastructure arc absorbed into each release as the backbone:
   - v0.4: Conventions + Trio Bootstrap (IPC layer, flat files)
   - v0.5: Capability Engine (Scheduler, SQLite WAL)
   - v0.6: Job Control + Constraints (SQLite extended)
   - v0.7: Async Pipeline + Daemon (HTTP Context Server)
   - v0.8: Open Context Protocol (ecosystem interface)
   - v0.9: Review TUI + Team Safety + Agent Identity
   - v1.0: Stable OS + Tokq Bridge Ready (NATS leaf schema, frozen CLI)

5. **5 Tokq PRD gaps identified and closed:**
   - Gap 1 (FR-1, Agent Identity): `synlynk identity init` → Ed25519 keypair in v0.9.0
   - Gap 2 (FR-2/3, Memory Unit Schema): Section 3.1 mapping project-docs/ → Tokq units, frozen v1.0
   - Gap 3 (FR-4, ZK Encryption): AES-256-GCM via HKDF-SHA256, Tokq Alpha, `synlynk[tokq]` extra
   - Gap 4 (FR-5/7, Marketplace): `synlynk publish` / `subscribe` in Tokq Alpha
   - Gap 5 (FR-6, Ledger Boundary): costs.md = local (permanent), gas tank = cloud (additive). Coexist.

**Documents created/updated:**
- `docs/superpowers/specs/2026-06-06-synlynk-unified-roadmap.md` — canonical single source of truth
- `project-docs/roadmap.md` — replaced stale pre-Trio table with 9-release view
- `project-docs/todo.md` — 80+ discrete todos across v0.4→Tokq Alpha
- `project-docs/memory.md` — full rewrite with all 2026-06-06 decisions
- `docs/archive/` — 8 superseded proposals archived (consolidated-roadmap, multi-agent-impl-plan,
  agy-arch-review, public-launch-plan, agent-workers-assessment, agent-workers-git-managed,
  agent-perf, polyglot-bootstrap)
- `docs/brainstorm/synlynk-unified-roadmap/` — 6 visual companion HTML files committed

**Visual companion created:** 6 HTML pages at `docs/brainstorm/synlynk-unified-roadmap/`:
- `positioning-map.html` — 2x2 competitive map + capability matrix
- `os-framing.html` — OS layer stack diagram + release overview
- `tokq-convergence.html` — convergence map + product combination options
- `unified-vision.html` — origin story arc (Tokq→synlynk→unified)
- `unified-roadmap.html` — ecosystem coexistence map + five milestone roadmap
- `release-staircase.html` — full v0.3→v1.0 release staircase with infra arc

**Commits:** `a7fe8fc` (unified roadmap + archive + visuals), `f5ce10f` (5 Tokq gaps absorbed)

**Status:** Unified roadmap complete and committed. Ready to start v0.4.0 implementation planning.

**Next:** Invoke `superpowers:writing-plans` on the Trio Protocol spec
(`docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md`) to produce the v0.4.0
implementation plan.

## 2026-06-01
### Session: Trio Protocol Rearchitecture Brainstorm
- **Activity:** Deep review of current roadmap vs. three hybrid workgroup study papers (Claude, Codex,
  Gemini participant-observer analyses of the RxCC team). Brainstormed full rearchitecture of synlynk
  for solo human + emergent trio of AI agents.
- **Key Outcome:** Designed the **Trio Protocol** — two execution modes sharing a common core:
  - **Candidate 1 (Async):** `synlynk dispatch` → lightweight daemon → Architect→Build→Verify pipeline → interactive TUI review
  - **Candidate 2 (Sync):** `synlynk run` → foreground streaming, Ctrl+C interrupt → immediate TUI review. Plus `synlynk schedule` (OS-native + agent-native via Claude routines) and `synlynk queue`.
- **Core design decisions locked:**
  - Role assignment: emergent from usage (empirical scoring, no vendor defaults)
  - Domain tagging: keyword inference, `--domain` overrides
  - Cold-start routing: round-robin across all slots until 3 samples
  - Score decay: recency-weighted, default half-life = 10 tasks
  - Phase failure: auto-retry once with next-best agent, then halt
  - Verify: fully agent-driven (agent decides what to run; `test_cmd` injected as suggestion)
  - Review: interactive curses-based TUI
- **Revised roadmap:** v0.3.0 (Trio Bootstrap + Sync MVP) → v0.4.0 (Capability Engine) → v0.5.0
  (Async Mode + Full Pipeline) → v0.5.1 (Context Architecture) → v0.6.0 (Scheduled Autonomy) →
  v0.7.0 (TUI + Cost Observability) → v1.0.0 (Stable Trio)
- **Spec committed:** `docs/superpowers/specs/2026-06-01-synlynk-trio-protocol-design.md`
- **Status:** Parked. Spec approved, ready for implementation planning when resumed.
- **Next:** Invoke `superpowers:writing-plans` on the spec to produce the phased implementation plan.

## 2026-05-17
### Session: v0.2.1 Correctness Patch
- **Activity:** Received and evaluated external code review feedback on v0.2.0.
- **Review Findings:** Confirmed 5 bugs: exit code not propagated from `exec_command`, `parse_costs_md` reading wrong column (parts[6] vs parts[5]), `install.sh` version drift (1.2.0-lite vs 0.2.0), 3 dead functions never called, sparse `.gitignore`. Also stale roadmap.md.
- **TDD:** Wrote failing tests first for exit code propagation and costs schema mismatch before touching production code. Updated `conftest.py` fixture to match real `costs.md` 6-column schema.
- **Fixes shipped:** All 6 0.2.1 items — exit code propagation, costs parser column, dead code removal (`log_telemetry`, `extract_tokens`, `update_costs`), install.sh version, .gitignore expansion, roadmap refresh.
- **Milestone:** v0.2.1 merged to main via PR#3. 47 tests passing. `synlynk exec python3 -c 'sys.exit(7)'` now correctly exits 7 in shell.
- **Next:** v0.3.0 — subprocess CLI tests, checkpoint idempotency, `synlynk doctor`, shell completions.

## 2026-05-16
### Session: Product Definition Brainstorming
- **Activity:** Stepped back from implementation to define the long-term vision for synlynk.
- **Key Outcome:** Defined a two-tier strategy (Free/Solo and Paid/Team/Enterprise).
- **Solo Tier Vision:** A "Context Switchboard" for AI developers that manages context, projects, costs, models, and environments across various CLIs (Claude Code, Gemini, etc.) and IDEs (Cursor, VS Code).
- **Architectural Shift:** Moving from a simple template repository to a lightweight Local Context CLI/Daemon that uses MCP (Model Context Protocol) and wrapper scripts to maintain state across different AI engines.
- **Interoperability:** Focus on seamless context hand-offs between different AI tools (e.g., starting in Claude Code and finishing in Cursor).
- **Strategy Shift:** Adopted a "Lite vs Full" Free tier approach. Lite focuses on file-based context and shell wrappers; Full introduces the LCP Daemon and MCP Server.
- **Resolved Grilling Points:** 
    - Concurrency via Append-Only logs.
    - Telemetry via shell aliases.
    - Hallucination detection via process wrappers and context injection.
    - Shipping frequently with a built-in `upgrade` path.
- **Activity:** Created public README.md and scaffolded the initial `synlynk` CLI (v1.2.0-lite) in Python.
- **Milestone:** Established final brand identity as **synlynk**.
- **Activity:** Implemented `synlynk init` command in `bin/synlynk.py`.
- **Verification:** Verified `init` command successfully creates `project-docs/`, `.synlynk/`, and all template markdown files in a test environment.
- **Activity:** Implemented `synlynk exec` command in `bin/synlynk.py`.
- **Feature:** `exec` command now generates a unified `.synlynk/context.md` snapshot and captures execution telemetry (duration).
- **Verification:** Verified `exec` successfully aggregates project-docs and wraps terminal commands.
- **Activity:** Implemented `synlynk upgrade` simulation (auto-update path foundation).
- **Activity:** Added frictionless alias recommendations to `synlynk init` to encourage telemetry adoption.
- **Verification:** Verified `upgrade` and `init` (with tips) via manual execution.
- **Activity:** Implemented `install.sh` for global installation of the `synlynk` CLI to `~/.synlynk/bin`.
- **Feature:** Added a shebang to `bin/synlynk.py` to allow direct execution.
- **Verification:** Verified `install.sh` correctly installs the binary and provides PATH configuration instructions.
- **Activity:** Refined AI instructions in `GEMINI.md` and `CLAUDE.md` to prioritize the `.synlynk/context.md` snapshot.
- **Activity:** Implemented telemetry logging to `.synlynk/telemetry.json` (timestamp, command, duration, exit_code).
- **Activity:** Implemented the "Flatline" Sentinel (v0.1) to detect and flag 3 consecutive command failures.
- **Verification:** Verified telemetry and Sentinel detection via manual loop simulation in a test environment.
- **Activity:** Automated multi-environment PATH setup in `install.sh` for zsh, bash, and fish.
- **Feature:** `install.sh` now intelligently appends the `PATH` export to shell configuration files if not already present.
- **Milestone:** synlynk Lite installation is now a seamless "one-click" experience.
- **Activity:** Implemented token count extraction from CLI output in `synlynk exec`.
- **Feature:** `exec` now parses stdout for token patterns (Claude, Gemini, etc.) and automatically updates `project-docs/costs.md`.
- **Feature:** Added real-time cost estimation and session summary display after each command execution.
- **Feature:** Expanded `costs.md` to track Request Counts and aligned the template with professional observability standards.
- **Feature:** Implemented "Budget Pulse" in `exec_command` to show cumulative request totals alongside session costs.
- **Feature:** Added `.synlynk/config.json` for per-project budget configuration (USD and Request limits).
- **Feature:** Implemented runtime Budget Alerts (80% warning, 100% critical) for both cost and request counts.
- **Verification:** Verified request counting and pulse display via repeated command execution in a test environment.
- **Activity:** Standardized "Interoperability Protocol" by adding `AI_INSTRUCTIONS.md` and `.cursorrules` to the `init` templates.
- **Milestone:** synlynk Lite now supports "Quota-Hopping" across Claude, Gemini, Cursor, and Codex-based tools with shared context snapshots.
- **Verification:** Verified token parsing and cost logging via simulated CLI output.
- **Activity:** Discussed and defined architectural strategies for Context Compaction (Active vs. Archive) and Sub-Agent Context Routing (Task-scoped views).
- **Milestone:** Core "Lite Tier" infrastructure is verified and documented. Next phase focuses on token extraction and scaling strategies.

## 2026-06-20 — Session: v0.7.0 Static Scan Quality

### Shipped
- **PR #49 merged → v0.7.0** — Static Scan Quality: language-agnostic source scanner injects `## Source Architecture` into every `synlynk exec` context
- **316 tests passing** (65 new in `tests/test_static_scan.py`)
- **GitHub release v0.7.0** cut at https://github.com/nikhilsoman/synlynk/releases/tag/v0.7.0

### Key decisions & implementation notes
- Passive cache invalidation: `_check_scan_cache()` compares `git rev-parse HEAD` to `.synlynk/scan-meta.json` — zero overhead on every exec when HEAD unchanged
- File prioritization: +3 entry-point bonus, +1/commit appearance (last 50), −1/dir level beyond 2; top 15 cap
- Symbol extraction: 9 languages, regex only, ≤300 lines/file, up to 8 symbols in skeleton
- Shell patterns: both `name()` and `function name()` syntax; discovered and fixed during code quality review
- `scanned_at` uses ISO 8601 T-separator (`%Y-%m-%dT%H:%M:%S`) to match rest of codebase
- `_format_source_architecture` uses `current_sha` (not stale meta SHA) to avoid stale header on cache miss
- Dual storage: SQLite `source_symbols` table (Tokq-sync-ready) + `project-docs/source-map.md` + hot skeleton cache
- `synlynk scan / scan --deep / scan --status` CLI added

### Updated
- `project-docs/roadmap.md` — v0.7.0 marked Shipped; v0.8.0 is next (Async Pipeline + Daemon)
- `site/src/_data/releases.json` — v0.7.0 entry added, v0.6.x marked not current
- `README.md` — intro copy, commands table, roadmap table all updated
- Memory updated: project-synlynk.md

### Next
- v0.8.0 Async Pipeline + Daemon (HTTP Context Server, `synlynk daemon start/stop`, `synlynk review` TUI)
- Capability Dogfood initiative: use synlynk to dispatch real tasks and accumulate capability ledger data

## 2026-06-21 — Session: Ed25519 Signing for Capability Ratings

### Shipped
- **Feature:** Ed25519 identity signing for capability ratings in `bin/synlynk.py`.
- **Feature:** Added `synlynk identity init` CLI subcommand to manage agent identity key pairs.
- **346 tests passing** (4 new tests added to `tests/test_synlynk.py`)

### Key decisions & implementation notes
- Key pair generation is handled using standard `ssh-keygen` command, storing keys in `~/.synlynk/identity.key`.
- Implemented `_sign_capability_rating` using SSH signing mechanisms (`ssh-keygen -Y sign`) with a custom namespace `"synlynk-rating"`.
- Wired signature validation automatically into capability rating writes, inserting signatures into the database table row.
- Updated CLI subcommand list in `main` to expose `identity init` parser under the `identity` namespace.

## 2026-06-21 — Session: Anti-gaming Quality Cap & test_count Extraction

### Shipped
- **Feature:** Extracted `test_count` inside `_extract_auto_signals` and added it to auto signals.
- **Feature:** Implemented anti-gaming cap in `_write_capability_rating` to cap `quality_auto` at 5.0 for trivial test suites (where `< 3` tests ran with a perfect pass rate of 1.0).
- **350 tests passing** (4 new tests added to `tests/test_synlynk.py`).

### Key decisions & implementation notes
- Parsed test count from logs in `_extract_auto_signals` for both the standard multi-pattern matches and the all-passed shortcut case.
- Applied anti-gaming baseline cap of 5.0 in `_write_capability_rating` if `test_count` is less than 3 and the pass rate is 1.0.

## 2026-06-23 — Session: v0.9.3 Async Daemon — shipped

### Shipped
- **v0.9.3 complete** — 3 PRs merged, 432 tests passing, tagged `v0.9.3`
- Multi-agent delivery: Claude owned Tasks 1–3 (PR #56), Agy owned Task 4 (PR #57), Codex owned Tasks 5–6 (PR #58)
- PRs reviewed by non-authoring agents: Agy reviewed #56, Codex reviewed #57, Claude reviewed #58

### What shipped in v0.9.3
- `SynlynkDaemon` — double-fork daemon with HTTP server thread on `localhost:27471` + persistent job queue dispatch on every poll tick
- `daemon_jobs` table in `state.db` — priority queue with dependency chains; zombie-safe reaping via `os.waitpid(WNOHANG)`; per-job commit for crash-safe restarts; dep-failure propagation
- 10-endpoint HTTP API — `/context`, `/status`, `/jobs`, `/jobs/<id>`, `/dispatch`, `/stories`, `/stories/<id>`, `/capability`, `/sentinel`, `/checkpoint`; `threading.Lock` for context generation; `allow_reuse_address` for rapid restart
- `synlynk daemon start|stop|status|restart` CLI
- `synlynk daemon --install-service` / `--uninstall-service` — launchd (macOS), systemd user unit (Linux), crontab fallback

### Key decisions
- Architecture B: `SynlynkDaemon` subclasses `WatchDaemon` — clean separation, reuses double-fork + mtime polling, HTTP as second thread
- Authoring-agent review rule enforced throughout: non-author reviews, fixes only by author
- Codex twice failed to apply the `~/.synlynk/` log path fix; applied directly as reviewer after second miss

### Next
- v0.9.2 Team Onboarding + Consensus (`synlynk join`, `synlynk decide`, write-arbitration)
- v0.9.4 Workgroup Relay (WSS/443, LAN/Cloudflare/VPS modes)

## 2026-06-23 — Session: Strengthen Daemon CLI Restart Test

### Shipped
- **Feature:** Strengthened `test_daemon_cli_restart_not_running` to assert that both `stop()` and `start()` are called by the daemon restart CLI action.
- Ran tests successfully and pushed the change to `feat/v0.9.3-t4-cli`.

### Key decisions & implementation notes
- Replaced the monkeypatch of `start()` with dummy lists tracking `stop` and `start` calls to explicitly assert call sequences.

## 2026-06-29 — Session: BS-15 synlynk as a standalone harness

### Completed
- Specced the strategy and architecture for transitioning synlynk from a CLI wrapper of vendor harnesses to hosting its own native execution harness in [synlynk-as-a-harness.md](file:///Users/nikhilsoman/dev/synlynk/docs/strategy/synlynk-as-a-harness.md).
- Noted this decision in [memory.md](file:///Users/nikhilsoman/dev/synlynk/project-docs/memory.md) with `@agy` attribution.
- Created `story-2ebedf92` (BS-15: brainstorm — synlynk as a standalone harness) in state.db, which automatically updated the tasks list in [todo.md](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md).
- Imported un-synced hand-written tasks (`BS-14`, `BS-12a`) into state.db using `_import_todo_to_stories()`.
- Verified the code changes by running all 528 tests successfully.

## 2026-06-30 — Session: BS-14 Sentinel Stall Implementation

### Completed
- **Feature**: Implemented per-job stall check logic `_check_job_stall` in `synlynk/__init__.py` using dynamic timeout configs overrideable per-agent.
- **Feature**: Integrated `_check_job_stall` in `_reconcile_jobs` to terminate stalled jobs with zero output and write `STALL_NO_OUTPUT` sentinel alerts.
- **TDD Test**: Added a regression test `test_reconcile_detects_stall_and_kills_process` to `tests/test_synlynk.py`.
- **Config**: Added defaults for `stall_timeout_minutes` and `agents` config sections to `load_config()` and configuration templates.
- **Verification**: Verified implementation against 485 tests, ensuring all tests passed.

