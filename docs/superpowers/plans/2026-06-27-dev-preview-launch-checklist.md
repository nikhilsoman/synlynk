# Dev Preview Launch Checklist — synlynk

**Target:** `v0.10.0 — Developer Preview`  
**Weekend:** 2026-06-28/29  
**Pitch:** "The coordination OS for multi-agent development — ship your first AI-native workgroup in minutes."

---

## Strategic decisions locked in before this checklist

**v0.8.x version gap:** Do not retrofit. v0.8.1–v0.8.4 (Agent Fleet: TPM, Marketing Intern, PM, Docs Keeper, Security Guard) are renumbered to **v1.1.x–v1.2.x** — they require the community layer (v1.0.0 workgroup protocol) to be meaningful. The gap in the version arc is a historical footnote, not a problem.

**Pilots (autonomous agent fleet) timing:** After GA (v1.0.0+). The dev preview story is "one developer + four AI agents working in sync." Adding autonomous fleet agents before dev preview muddies the message and adds complexity before the core workflow is validated with real users. Fleet agents become the v1.1.0 "Autopilot" milestone.

---

## Weekend Agenda

### Friday evening — Policy + Roadmap cleanup (1–2h)

- [x] **Named Release Policy** added to global `~/.claude/CLAUDE.md` — applies to all projects
- [ ] **Roadmap v0.8.x cleanup** — rename v0.8.1–v0.8.4 slots as `📦 Deferred → v1.1–1.2`; add v0.10.0 as "Developer Preview" Named Release target
- [ ] **Commit roadmap update** — docs PR on synlynk

---

### Saturday — Install + First-run experience (half day)

**Goal:** A new developer can install synlynk in 30 seconds and get a working `synlynk init` in their repo.

#### 1. `pipx install` support (currently install.sh only — hard barrier)

- [ ] Add `pyproject.toml` with entry_point `synlynk = "synlynk:main"` and package metadata
- [ ] Verify `python -m synlynk` and `pipx install git+https://github.com/nikhilsoman/synlynk` both work
- [ ] Update install.sh to note pipx as the recommended path
- [ ] Test on clean shell: `pipx install git+https://...` → `synlynk --version` → `synlynk init` → `synlynk exec claude "hello"`
- [ ] Branch: `feat/pipx-install` → PR → Named Release in v0.10.0 batch

*Note: PyPI publish can wait for GA. `pipx install git+<url>` is sufficient for dev preview.*

#### 2. `synlynk doctor` — v0.9.5 Health Pulse (dispatch)

- [ ] Write plan for v0.9.5: per-command auditor, `synlynk doctor` command, registry-based `HealthCheck` dataclass
- [ ] Dispatch Codex with the plan (TDD loop, single-file, well-specced)
- [ ] Merge when green — ships as part of v0.10.0 batch

#### 3. First-run polish

- [ ] `synlynk init` output: ensure it prints a "what to do next" guide — not just "created files"
- [ ] `synlynk exec claude` with no AI installed: clear error with install link, not a stack trace
- [ ] README: add 60-second quickstart at the top (install → init → exec)

---

### Saturday afternoon — Website (BS-5 brainstorm, 2h)

- [ ] Open BS-5 brainstorm session — visual companion, mockups
- [ ] Decision: rebuild synlynk.com on what stack? (current: 11ty — keep or move to Astro/plain HTML?)
- [ ] Define: hero narrative, feature storytelling sections, install CTA
- [ ] Output: spec + wireframes → implementation plan
- [ ] **Do not build the site this weekend** — brainstorm only, implementation is a separate session

---

### Sunday morning — Visualization brainstorm (BS-6, 2h)

- [ ] Dispatch Agy for `docs/okf_assessment.md` if not already done (pre-session task) ✅ done
- [ ] Open BS-6 brainstorm — three-view viz architecture, OKF alignment
- [ ] Agenda: `docs/superpowers/specs/bs6-project-intelligence-okf-viz-agenda.md`
- [ ] Decision: which view ships first? Product view (user-story graph) is most compelling for launch
- [ ] Output: spec → implementation plan for `synlynk viz`

---

### Sunday morning (optional slot) — BS-7 Brainstorm: Skill Pack Interoperability (2h)

*Can trade with BS-6 if BS-6 runs long. BS-7 is the stronger pre-launch asset.*

- [ ] Open BS-7 brainstorm: "Skill Pack Interoperability + Benchmarks"
- [ ] Agenda: `docs/superpowers/specs/bs7-skill-pack-interop-agenda.md` (to be written at session start)
- [ ] Key design questions for session:
  - Which skill packs to benchmark? (Superpowers, GStack/GBrain, GSD, Everything-ClaudeCode — top 5 by adoption)
  - Define the test task precisely: "build a To-do app with CRUD, tests, and deploy config" — exact spec
  - Define metrics: token cost per session, session count to completion, test coverage achieved, retry/loop incidents, hallucination count
  - How does synlynk's `--context-mode task` reduce skill pack token bloat? (hypothesis: scoped context injection means only relevant `project-docs/` slice is injected, not 55KB full context dump that amplifies every skill pack prompt)
  - Technical coexistence: how do synlynk's `synlynk:start/end` blocks coexist with Superpowers hooks and GStack additions? (connect to AB-11 conflict taxonomy)
  - What is the narrative? "synlynk is the coordination OS; skill packs are domain expertise modules — different layers, better together"
- [ ] Output: BS-7 spec doc + benchmark methodology
- [ ] **Do NOT run benchmarks this session** — design only; benchmark execution is next week's dispatch job

---

### Sunday afternoon — Launch artifacts (2h)

#### 4. GitHub README overhaul

- [ ] Hero: what synlynk is in two sentences + one command
- [ ] 60-second quickstart: `pipx install git+...` → `synlynk init` → `synlynk exec claude "write me a test for X"`
- [ ] Feature table: what synlynk does that raw AI CLIs don't
- [ ] Agent roster: Claude / Agy / Codex / Grok — what each is good at
- [ ] Blog series link: "follow the build" → `docs/blog/`
- [ ] Branch: `chore/readme-overhaul` → PR

#### 5. Announcement draft

- [ ] Write draft HN launch post: `docs/proposals/blog/hn-launch-post.md`
  - "Ask HN: I built a coordination OS for AI agent teams — synlynk"
  - What pain it solves (agent coordination overhead)
  - What you can do in 5 minutes
  - What's planned
- [ ] Write draft dev.to / blog post cross-post
- [ ] Do NOT publish yet — publish on Named Release day

#### 6. v0.10.0 Named Release prep

- [ ] Collect all PRs merged since v0.9.7: pipx, Health Pulse, README, viz (if ready)
- [ ] Write CHANGELOG `[0.10.0] - 2026-06-29` entry
- [ ] VERSION bump: `synlynk/__init__.py`, `install.sh`, `pyproject.toml`
- [ ] `gh release create v0.10.0` with dev preview framing
- [ ] Publish HN + dev.to post

---

## Dev Preview "Done" Criteria

Before calling it a dev preview:

| Gate | Status |
|---|---|
| `pipx install git+<url>` works on a clean machine | ⬜ |
| `synlynk init` + `synlynk exec claude` works end-to-end | ⬜ |
| `synlynk doctor` surfaces at least version + identity status | ⬜ |
| README has a 60-second quickstart | ⬜ |
| CHANGELOG + GitHub Release tagged | ⬜ |
| HN / dev.to post ready to publish | ⬜ |

Website (BS-5) and `synlynk viz` (BS-6) can trail dev preview — they're nice-to-have for launch, not blockers.

**BS-7 benchmark results are a strong-to-have** — having data in the HN post ("R4 beats R1 by X tokens at Y% better test coverage") is materially better than a claim. If BS-7 design is done this weekend and benchmarks run Monday/Tuesday, results can land in the launch post.

---

## What ships at dev preview vs. GA

| Capability | Dev Preview (v0.10.0) | GA (v1.0.0) |
|---|---|---|
| `pipx install` | git+URL | PyPI |
| Homebrew | ✗ | ✓ |
| `synlynk init/exec/dispatch/jobs/relay` | ✓ | ✓ |
| `synlynk doctor` | ✓ | ✓ |
| `synlynk viz` (product view) | maybe | ✓ |
| New website (BS-5) | maybe | ✓ |
| Agent fleet (TPM, Marketing, PM, etc.) | ✗ | ✗ (v1.1+) |
| Community workgroup protocol | ✗ | ✓ |
| Signed capability ledger | ✗ | ✓ |
| Multi-repo workspace | ✗ | ✓ |

---

## Brainstorm Session Status

| Session | Topic | Status | Drives |
|---|---|---|---|
| BS-1 | Context Layer + Dispatch Architecture | ✅ Done | v0.9.4 |
| BS-2 | Onboarding Model + Mode Taxonomy | ✅ Done | v0.9.4 |
| BS-3 | Agent Behaviour + Instruction Adherence | 📋 Queued — pre-GA (not this weekend) | AB-11 conflict taxonomy; v1.0 |
| BS-4 | Command Audit + Autopilot Trigger Map | 📋 Queued — pre-GA (not this weekend) | v1.0 agent fleet triggers; moved post-fleet-deferral |
| BS-5 | Website Redesign | 📋 This weekend — Saturday PM | Dev preview + GA |
| BS-6 | Project Intelligence: OKF + Visualization | 📋 This weekend — Sunday AM | Dev preview hook; v0.10.0 |
| BS-7 | Skill Pack Interoperability + Benchmarks | 📋 This weekend — Sunday AM/PM | Pre-launch narrative + benchmark data |
| BYOA | Ollama / OpenCode / OpenRouter / DeepSeek | ⏸ Parked — post dev preview | Own dedicated session |

## Related
- BS-5 brainstorm: story-048f5fe5 (website redesign)
- BS-6 brainstorm + agenda: `docs/superpowers/specs/bs6-project-intelligence-okf-viz-agenda.md`
- BS-7 brainstorm agenda: `docs/superpowers/specs/bs7-skill-pack-interop-agenda.md` (written at session start)
- Named Release Policy: `~/.claude/CLAUDE.md` — "Named Release Policy" section
- v0.9.8 Health Pulse + Lifecycle spec: needs writing
