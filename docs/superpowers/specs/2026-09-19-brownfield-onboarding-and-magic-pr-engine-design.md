# Design Spec: Deep Brownfield Ingestion & 5-Minute Magic PR Engine

- **Governing Goal:** [`goal-85656c82`](file:///Users/nikhilsoman/dev/synlynk/project-docs/roadmap.md) (Developer Experience v1.0 Launch & Time-to-Wow)
- **Tracking Stories:** [`story-ffb0f3e6`](file:///Users/nikhilsoman/dev/synlynk/project-docs/todo.md) (Wave 1 Dev Preview)
- **Author:** Agy (Antigravity CLI) [@agy]
- **Collaborator / Approver:** Nikhil Soman [@nikhilsoman]
- **Date:** 2026-09-19
- **Status:** Approved Spec

---

## 1. Executive Summary & Objective

The primary metric of success for the Developer Preview launch (01 Oct 2026) is **"Time-to-Wow" ($< 300\text{s}$)**.

When a developer runs `synlynk init --brownfield` on an existing legacy repository (Python, TypeScript/JavaScript, Go, Rust, Ruby, Java), Synlynk must:
1. **Reverse-Engineer the Entire Environment (Zero Prompts):** Auto-detect package managers, test runners, linters, and high-churn git hotspots.
2. **Synthesize Autonomous Living Documentation:** Produce initial `project-docs/roadmap.md`, `memory.md`, and `todo.md` without requiring human boilerplate setup.
3. **Present 1-Click Magic PR Candidates:** Discover high-confidence quick wins (circular import repairs, dead import pruning, broken doc fixes, leaf unit tests).
4. **Open a Fully Attested Magic PR in $< 5$ Minutes:** Execute in an isolated worktree with 3-tier attribution ($\langle @username, \text{role App}, \text{harness} \rangle$) and 100% test pass attestation.

```
                    BROWNFIELD ONBOARDING & MAGIC PR TIMELINE
                    
  00:00 ──────────────────> 00:30 ──────────────────> 01:30 ──────────────────> 03:00 ──> 05:00
  [ Zero-Terminal Scan ]    [ Tech Stack & Git ]     [ Doc Synthesis ]        [ Magic PR Generated ]
  • Dirty tree guard        • Test runner detection  • project-docs/roadmap   • Circle heal / Lints
  • Graphify AST indexing   • Churn hotspot analysis • project-docs/memory    • Tests pass 100%
  • External boundary scan  • Contributor handles    • project-docs/todo      • Attested PR Opened!
```

---

## 2. Architecture & Components

```
 ┌──────────────────────────────────────────────────────────────────┐
 │                    synlynk init --brownfield                     │
 └────────────────────────────────┬─────────────────────────────────┘
                                  │
         ┌────────────────────────┼────────────────────────┐
         ▼                        ▼                        ▼
 ┌───────────────┐        ┌───────────────┐        ┌───────────────┐
 │ Environment   │        │ Living Doc    │        │ 1-Click Magic │
 │ Reverse-Eng   │        │ Synthesizer   │        │ PR Engine     │
 ├───────────────┤        ├───────────────┤        ├───────────────┤
 │ Probes test   │        │ roadmap.md    │        │ Circular heal │
 │ runner, lint, │        │ memory.md     │        │ Dead imports  │
 │ 90d git churn │        │ todo.md       │        │ Missing tests │
 └───────────────┘        └───────────────┘        └───────────────┘
```

### Component A: Zero-Terminal Environment Reverse-Engineering
`synlynk/coldstart.py` and `synlynk/scan.py` inspect the codebase without interactive questions:

| Ecosystem | Manifest Signals | Test Runner Auto-Detected | Linter / Formatter Auto-Detected |
| :--- | :--- | :--- | :--- |
| **Python** | `pyproject.toml`, `setup.py`, `requirements.txt`, `Pipfile` | `pytest`, `unittest` | `ruff`, `flake8`, `black`, `mypy` |
| **TypeScript / Node** | `package.json`, `pnpm-lock.yaml`, `yarn.lock`, `tsconfig.json` | `vitest`, `jest`, `mocha` | `eslint`, `prettier`, `biome` |
| **Go** | `go.mod`, `go.sum` | `go test ./...` | `golangci-lint` |
| **Rust** | `Cargo.toml`, `Cargo.lock` | `cargo test` | `clippy`, `rustfmt` |
| **Ruby** | `Gemfile`, `Gemfile.lock` | `bundle exec rspec` | `rubocop` |
| **Java / Kotlin** | `pom.xml`, `build.gradle`, `build.gradle.kts` | `mvn test`, `./gradlew test` | `spotless`, `checkstyle` |

### Component B: Git Churn & Hotspot Forensics
- Executes `git log --since="90 days ago" --stat` to calculate file churn frequency.
- Flags "God Files" ($> 1,000$ lines with $> 20$ commits in 90 days) for Architect awareness.
- Extracts principal committer identities (`git log --format="%an <%ae>"`) to auto-populate default reviewers and attribution metadata.

### Component C: Autonomous Living Doc Synthesis
1. **`project-docs/roadmap.md`:** Pre-populated with detected technology stack, active modules, and default 4-wave release horizon.
2. **`project-docs/memory.md`:** Pre-populated with detected test commands, directory conventions, and repository invariants.
3. **`project-docs/todo.md`:** Pre-populated by ingesting open GitHub issues (`synlynk backlog ingest --sync-github`).
4. **AST Knowledge Base:** Builds Graphify AST graph (`synlynk pack`) in `.synlynk/graphify-out/graph.json`.

---

## 3. The 5-Minute "Magic PR" Engine

### A. Candidate Discovery & Priority Hierarchy
Upon completing the scan, `synlynk heal --magic` detects low-hanging, zero-risk improvements and ranks them:

1. **Circular Import Repair (Priority 1 - AST Verified):**
   - Detects import cycles (e.g. `module A -> module B -> module A`) and extracts shared types/constants to break the cycle.
2. **Dead Symbol / Import Pruning (Priority 2):**
   - Safely removes unused imports without touching functional code logic.
3. **Broken Documentation & Markdown Link Healer (Priority 3):**
   - Scans all `.md` files for 404 URLs, missing section anchors, or broken relative file paths.
4. **Untested Pure Leaf Function Coverage (Priority 4):**
   - Uses Graphify call-graph to identify 0-dependency pure helper functions lacking unit test coverage, authors standard unit tests, and verifies 100% pass locally.

### B. Interactive 1-Click Candidate Confirmation UX
The CLI / Vizor displays all discovered quick-win candidates with individual confirmation chips:

```
  ✨ Discovered 3 Instant Magic PR Candidates:
  
  [1] Circular Import Fix: Break cycle between auth.py <-> user.py (AST verified)  [Y/n]
  [2] Dead Import Cleanup: Prune 18 unused imports across 6 modules                [Y/n]
  [3] Test Coverage Booster: Add unit tests for 3 untested leaf helpers            [Y/n]
  
  Press [1] to dispatch Candidate 1 immediately (opens PR in < 2 minutes).
```

### C. Three-Tier Attribution & PR Body
The generated PR strictly enforces 3-tier attribution:
- **Branch Name:** `feat/<username>/magic-fix-circular-imports`
- **Author:** `@username` (or role App `synlynk-dev[bot]`)
- **Commit Trailers:**
  ```
  Co-Authored-By: <harness-name> <<harness-email>>
  Co-Authored-By: <username> <<user-email>>
  ```
- **PR Description:** Contains detailed before/after explanation, AST blast-radius impact attestation, and local test execution pass logs.

---

## 4. Verification & Acceptance Criteria

- [ ] **AC-1 (Zero-Terminal Probe):** `synlynk init --brownfield` accurately detects test commands and package managers across Python, TS, Go, Rust, Ruby, and Java without prompt pauses.
- [ ] **AC-2 (Doc Synthesis):** Initial `project-docs/roadmap.md`, `memory.md`, and `todo.md` are automatically written with correct repo metadata.
- [ ] **AC-3 (Candidate Selection):** Discovered candidates are presented as individual 1-click confirmation options.
- [ ] **AC-4 (Worktree Isolation & Attestation):** The selected candidate executes in an isolated worktree, passes all tests, and opens a GitHub PR with full 3-tier attribution in $< 300\text{s}$.
