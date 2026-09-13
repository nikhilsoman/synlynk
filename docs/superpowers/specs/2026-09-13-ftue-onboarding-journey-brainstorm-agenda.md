# Synlynk v0.21.0 FTUE & Onboarding Journey — Brainstorm Agenda

**Document:** `docs/superpowers/specs/2026-09-13-ftue-onboarding-journey-brainstorm-agenda.md`  
**Target Release:** v0.21.0 ("The Visual & Autonomous Onboarding Release")  
**Date:** 2026-09-13  
**Author / Conductor:** Agy (`@agy`, AntiGravity)  
**Panel Harnesses for `synlynk decide`:** Claude (`@claude`), Codex (`@codex`), Agy (`@agy`), Grok (`@grok`)  
**Status:** APPROVED (Consensus Decision `dec-fcff261a` recorded in `project-docs/decisions/2026-09-13-synlynk-v0-21-0-ftue-onboarding-journey.md`)  

---

## 1. Executive Summary & Thesis

### The Core Problem
First-time developer onboarding in complex codebases is broken. When an engineer or autonomous agent enters a repository, they are typically met with a dense file tree, an outdated `README.md`, fragmented configs, and silent tribal knowledge. Previous attempts at autonomous developer tooling fell into three major anti-patterns:
1. **Interrogation Fatigue:** Text-based wizard CLIs that pepper the user with 10–15 sequential terminal questions before delivering any value.
2. **Static Read-Only Dead-Ends:** Tools that scan the repo and spit out a 500-line Markdown file or static report, leaving the user with the classic cliff: *"Now what?"*
3. **Fragmented & Disconnected Views:** File trees living in CLI text, module graphs in separate web diagrams, cloud infra in AWS/Terraform consoles, and business logic locked in Jira.

### The Synlynk v0.21.0 Thesis: Intent Transmission & First-Win
Synlynk's purpose is to be the **synaptic link** between human architectural intent and multi-agent autonomous execution. Onboarding cannot simply be an inventory script—it must be an **interactive, progressive-disclosure onboarding journey** that moves the user from zero to their **First Real Autonomous Win** in under 5 minutes.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE 5-MINUTE ONBOARDING JOURNEY                                   │
│                                                                                                  │
│   [1. Quick Install]  ──►  [2. 3D Discovery]  ──►  [3. Confirm & Tweak] ──►  [4. 3-View Canvas] │
│      (< 30s)                  (< 45s)                    (< 30s)                   (< 30s)       │
│   curl / pipx / brew       Domain, Physical,          Visual Chips &          Physical, Logical, │
│   Zero external deps       Logical Inference          Inline Corrections       Application Views │
│                                                                                    │             │
│                                                                                    ▼             │
│   [PR Merged / First Win] ◄── [Dispatched Task] ◄── [Approve Goals] ◄── [5. Gap Discovery]      │
│          (< 5 min)                  (< 3 min)                  (< 30s)             (< 30s)       │
│      Standard SOP Task          Isolated Worktree           GOVERNS Goals &        Untested Code │
│      Automated Verification     TDD Test + PR Created       Stories in state.db    Security Gaps │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Retrospective Audit: Past Specs, Code & Lessons Learned

### A. Past Synlynk Specifications Audited
1. **BS-17 FTUE & Onboarding Design (`docs/superpowers/specs/2026-07-01-bs17-ftue-onboarding-design.md`):**
   - *Strengths:* Identified the need for an 8-stage setup (welcome, harness selection, role assignment, project detection, doctor preflight).
   - *Shortcomings:* Relied heavily on a multi-step modal curses/TUI sequence in the terminal, causing user friction on wide vs. narrow terminals and lacking visual context.
2. **Zero-Risk Onboarding & First Win (`docs/superpowers/specs/2026-09-03-zero-risk-onboarding-and-first-win-design.md`):**
   - *Strengths:* Introduced the non-destructive safety contract: git dirty-tree gate, backup tarball/stash before touching files, and the concept of generating a non-destructive diagnostic PR within 2 minutes.
   - *Shortcomings:* Remained focused on diagnostic health rather than deep application discovery (entities, information flow, screens).
3. **Cold-Start & Intent Transmission (`docs/superpowers/specs/2026-08-09-cold-start-design.md`):**
   - *Strengths:* Framed the core philosophy: *"intent transmission, not command execution"*. Differentiated cold start on empty vs. existing repos. Scanned git tags to generate retrospective roadmaps with cited commit hashes.
   - *Shortcomings:* Handed the user a static `workspace-canon.md` file without an interactive visual bridge or automated goal generation.
4. **BS-6 Visualization Architecture (`docs/superpowers/specs/2026-09-09-bs6-repo-workspace-visualization-design.md`):**
   - *Strengths:* Defined the 3-layer mental model: Product View (routes/screens), Logical View (modules/entities/tubemap), Infra View (Docker/cloud/queues). Mandated offline self-contained SVG without external CDN dependencies.
   - *Shortcomings:* Treated visualization as a separate passive status dashboard rather than the primary interactive canvas for onboarding.
5. **Real-World Client Adoption Lessons (`docs/proposals/rxcc-wow-observations.md` & Track 1 Rollouts):**
   - *Strengths:* Hardened against real production multi-repo stacks (`rxcc`, `cc-videoreframing`, `playblazer-ng`, `hitchcock`).
   - *Key Lesson:* When CI is unconfigured or strict type-check environments (e.g. Docker-only mypy) exist, autonomous agents must not fail closed or hallucinate PR approvals. The onboarding experience must adapt gracefully to repo-specific constraints.

### B. Existing Code Implementation Inventory
- **Stack & Tool Fingerprinting (`synlynk/scan.py`):**
  - `fingerprint_stack()` detects languages, frameworks (FastAPI, React, Next, Django, Rails, Go, Rust), container configs, and discovered tools/skills in `~/.claude/plugins` and `~/.config/gstack`.
- **Cold-Start Engine (`synlynk/coldstart.py`):**
  - `cmd_start()` triages between existing and new repos, creates baseline `.synlynk/` layout, and initializes `workspace-canon.md`.
- **Vizor Engine (`synlynk/viz.py` & `synlynk/viz_views.py`):**
  - Offline SVG rendering: `generate_product_html`, `generate_logical_html`, `generate_infra_html`, `generate_tube_html`.
  - Database-backed projection schema: `workspace_view_nodes`, `workspace_view_edges`, `workspace_view_meta`.
  - In-browser role provisioning wizard (`/onboarding/roles` and `/auth/sync`).
- **Readiness Matrix (`synlynk/readiness.py`):**
  - 10-point health and security verification matrix (role tokens, branch protections, harness probes, worktree hygiene).

---

## 3. Industry Best Practices & Deconstructed Developer Benchmarks

### A. CLI & UNIX Design Foundations (`clig.dev` & 12-Factor CLI)
- **Sub-100ms Immediate Responsiveness:** A CLI must never hang silently during scanning or network requests. Immediate visual feedback (spinners, phase indicators) prevents perceived deadlocks.
- **TTY-Aware Interactivity:** If running in an interactive terminal, provide delightful visual menus and progress bars; if piped or run with `--no-input`, run deterministically with machine-readable `--json`.
- **Do What I Mean (DWIM) with Smart Defaults:** Never demand manual input when the answer can be determined with 95% confidence from package manifests and directory layouts.
- **Idempotent & Crash-Only Architecture:** If interrupted with `Ctrl-C` or network drops, re-running the command must cleanly resume from the last known good state without leaving orphaned lockfiles or half-written states.

### B. High-Regard Developer Product Onboarding Benchmarks
| Product | Onboarding Superpower | How Synlynk Adopts It |
| :--- | :--- | :--- |
| **Vercel CLI** (`vercel`) | Auto-detects framework, build command, and output dir. Outputs single summary with *"Want to modify these settings? [y/N]"* (default No/Proceed). | Synlynk scans repo, presents detected Domain, Stack, and Deployment in interactive chips, defaulting to 1-click continuation. |
| **Fly.io** (`fly launch`) | Scans repo, creates config, detects DB requirements, offers immediate terminal or web-based tweak dashboard before provisioning. | Hybrid approach: CLI scans in seconds, then prompts or auto-launches local Vizor UI for rich 3-view validation. |
| **Supabase CLI** (`supabase init`) | Zero-config bootstrap, scaffolds local configs, instantly spins up local dashboard at `http://localhost:54323`. | `synlynk init` spins up local Vizor at `http://localhost:27472` with zero cloud dependencies and immediate visual feedback. |
| **Astro CLI** (`create-astro`) | Warm personality (Houston mascot), animated stage transitions, sub-second step completions, delight without cognitive drag. | Clean, branded visual stages with live animated terminal indicators and clear time-budget transparency. |
| **Stripe CLI** (`stripe login` / `listen`) | Browser pairing link, terminal connects without pasting tokens, immediate live event listener proving connectivity. | GitHub App manifest flow (`/onboarding/roles`) pairs the local repo with GitHub Apps in 1 click without manual token handling. |
| **PostHog / Sentry** | Real-time event listener waiting for the first event; fires green success banners and confetti the instant it arrives. | Live readiness polling: when the first role token is minted or the first task PR is created, Vizor celebrates the First Win live. |

---

## 4. The 6 Pillars of the Synlynk v0.21.0 Onboarding Architecture

```
                                  SYNLYNK v0.21.0 ONBOARDING
  ┌────────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                        │
  │  [Pillar 1: Quick Install] ──────► One-line bootstrap (<30s), zero external runtime   │
  │                                                                                        │
  │  [Pillar 2: 3D Discovery]  ──────► A. Industry Domain (e.g. Healthcare, Media AI)     │
  │                                    B. Physical Structure (Dir tree, configs, CI/CD)    │
  │                                    C. Logical Structure (Entities, flows, schemas)     │
  │                                                                                        │
  │  [Pillar 3: Validate & Tweak] ───► Interactive "Confirm & Tweak" chips (web/TUI)       │
  │                                                                                        │
  │  [Pillar 4: 3-View Canvas] ──────► 1. Physical View: Drillable file/component tree     │
  │                                    2. Logical View: Tubemap & sequence data flows      │
  │                                    3. Application View: Rendered screens & cloud infra │
  │                                                                                        │
  │  [Pillar 5: Goal Discovery] ─────► Automated gap analysis -> GOVERNS Goals in state.db │
  │                                                                                        │
  │  [Pillar 6: First-Win Task] ─────► 1-Click SOP task dispatch -> Real PR in < 3 minutes │
  │                                                                                        │
  └────────────────────────────────────────────────────────────────────────────────────────┘
```

---

### Pillar 1: Quick Install & Frictionless Bootstrap
**Goal:** A new user goes from zero to a running Synlynk binary in $< 30$ seconds.

- **Distribution Channels:**
  1. `curl -fsSL https://synlynk.com/install.sh | sh` (zero-dependency standalone script).
  2. `pipx install synlynk` (isolated Python application environment).
  3. `brew install synlynk/tap/synlynk` (macOS / Linux native formula).
  4. Standalone pre-compiled PyInstaller / PyOxidizer binary (zero Python runtime requirement on host).
- **Instant Preflight (`synlynk doctor --quick`):**
  - Verifies Git $\ge 2.38$ (worktree support), SSH/GitHub CLI authentication, and detects available harness binaries (`claude`, `codex`, `agy`, `grok`).
  - Gracefully adapts to whichever harness is present without failing if some are missing.

---

### Pillar 2: Three-Dimensional Automated Discovery Engine (`synlynk scan --deep`)
**Goal:** In $< 45$ seconds, reconstruct the complete physical, logical, and business reality of the workspace without requiring the user to write documentation manually.

```
                           3-DIMENSIONAL DISCOVERY ENGINE
   
       DIMENSION A: DOMAIN SPACE                DIMENSION B: PHYSICAL LAYOUT
   ┌──────────────────────────────┐         ┌────────────────────────────────┐
   │ • Industry: Healthcare AI    │         │ • Frontend: Next.js (App Dir)  │
   │ • Function: Video Processing │         │ • Backend: FastAPI Services    │
   │ • Model: B2B Multi-tenant    │         │ • Workers: Celery / Redis      │
   │ • Compliance: HIPAA, SOC2    │         │ • Infra: Pulumi / Docker / ECS │
   └──────────────┬───────────────┘         └───────────────┬────────────────┘
                  │                                         │
                  └────────────────────┬────────────────────┘
                                       │
                                       ▼
                          DIMENSION C: LOGICAL ARCHITECTURE
   ┌─────────────────────────────────────────────────────────────────────────┐
   │ • Entities: User, VideoAsset, TranscodeJob, BillingRecord               │
   │ • Information Flow: Ingestion -> Webhook -> Worker -> S3 -> Notification│
   │ • Datastores: PostgreSQL (schema v14), Redis Cache, S3 Storage          │
   │ • External Integrations: Stripe, AWS Rekognition, Sendgrid              │
   └─────────────────────────────────────────────────────────────────────────┘
```

#### A. Domain & Business Space Discovery
- **Extraction Sources:** Root `README.md`, package descriptions, documentation in `docs/`, OpenAPI endpoint descriptions, database model names, and git release history.
- **Inferred Attributes:**
  - *Industry:* e.g., Healthcare & Telemedicine, Media Tech & Generative Video, Developer Tooling, Fintech, Gaming.
  - *Application Function:* e.g., Asynchronous Video Ingestion & Reframing Pipeline, Real-time Collaborative Canvas, Distributed Billing & Metering.
  - *Target Persona:* e.g., Enterprise Compliance Officers, Video Creators, Platform Engineers.
  - *Compliance & Constraints:* e.g., HIPAA, GDPR, SOC-2, strict zero-data-retention.

#### B. Physical Structure Discovery
- **Directory Hierarchy:** Identifies source roots, entry points, frontend vs. backend vs. shared libraries, workers, migrations, and test suites.
- **Configuration & Build Manifests:** Detects `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `docker-compose.yml`, `Dockerfile`, `Pulumi.yaml`, `terraform/`, `.env.example`.
- **Deployment & CI/CD Pipeline:** Detects GitHub Actions workflows (`.github/workflows/`), target environments (AWS ECS, Kubernetes, Vercel, Fly.io, Cloudflare Workers), and release scripts.

#### C. Logical Structure Discovery
- **Domain Entities & Schemas:** Parses ORM definitions (SQLAlchemy, Prisma, Django Models, Pydantic, TypeORM) to map core business entities, their fields, and foreign-key relations.
- **Information Flow & Message Lifecycles:** Maps incoming HTTP request routes $\rightarrow$ auth middleware $\rightarrow$ service controllers $\rightarrow$ background event queues (Kafka, Redis, RabbitMQ, SQS) $\rightarrow$ persistent storage $\rightarrow$ outbound webhooks.
- **Services & Boundaries:** Identifies microservice boundaries, internal RPC interfaces (gRPC, FastAPI routers, Express routes), and third-party SaaS integrations (Stripe, Twilio, OpenAI, AWS S3).

---

### Pillar 3: Interactive Context Validation & Enrichment UI ("Confirm & Tweak")
**Goal:** Present discovered facts to the user with zero cognitive burden, allowing immediate 1-click confirmation or quick surgical tweaks.

- **Interface:** Launches local browser directly into `http://localhost:27472/onboarding` (with full terminal TUI fallback for headless SSH environments).
- **The "Confirm & Tweak" Card Pattern:**
  - Discovered facts are rendered as interactive visual **chips**:
    - **Industry Domain:** `[Healthcare AI ✕]` `[Video Processing ✕]` `[+ Add Tag]`
    - **Physical Components:** `[Frontend: Next.js 14]` `[Backend: FastAPI]` `[Infra: AWS ECS / Pulumi]`
    - **Logical Flow:** `[Auth: OAuth2/JWT]` `[Queue: Redis Streams]` `[DB: Postgres 16]`
  - **Zero-Typing Default:** The primary action is a prominent button: **`Looks Perfect — Continue (Press Enter)`**.
  - **Inline Editing:** Clicking any chip turns it into a quick editable text field without triggering a multi-page re-scan.

---

### Pillar 4: Unified 3-View Interactive Visualization Canvas in Vizor
**Goal:** Provide three complementary, interactive mental models of the codebase in a single unified canvas.

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                  SYNLYNK VIZOR UNIFIED CANVAS                                    │
│  [View 1: Physical File Tree]   │  [View 2: Logical Tubemap / Flow]  │  [View 3: Application & Infra]│
├─────────────────────────────────┼────────────────────────────────────┼───────────────────────────┤
│  📁 src/                        │  (Client)                          │  📱 Screen Catalog        │
│  ├── 📁 api/ [Backend: 14 rts]  │     │ [POST /api/v1/reframing]     │  ├── /login [Wireframe]   │
│  ├── 📁 web/ [Frontend: React]  │     ▼                              │  ├── /dashboard [Live]    │
│  ├── 📁 workers/ [Celery]       │  [FastAPI Gateway] ──► [Redis Q]   │  └── /editor [Canvas]     │
│  └── 📁 infra/ [Pulumi/AWS]     │     │                      │       │                           │
│                                 │     ▼                      ▼       │  ☁️ Cloud Topology        │
│  📊 Component Breakdown:        │  [PostgreSQL]        [Worker Pods] │  ├── AWS VPC (us-west-2)  │
│  ■ 45% Backend (Python)         │  (Users, Jobs)       (FFmpeg/AI)   │  ├── ECS Fargate Cluster  │
│  ■ 35% Frontend (TypeScript)    │                            │       │  └── RDS Postgres MultiAZ │
│  ■ 20% Infra & Tests            │                            ▼       │                           │
│                                 │                         (AWS S3)   │                           │
└─────────────────────────────────┴────────────────────────────────────┴───────────────────────────┘
```

#### View 1: Physical View (Drillable File Tree & Component Hotspots)
- Collapsible, hierarchical directory tree enriched with component metadata badges.
- Heatmap visualization highlighting file sizes, test coverage density, and recent git churn hotspots.
- Clicking any directory displays its declared role ownership and component boundary.

#### View 2: Logical View (Graphify / Data Flow / Architect Tube Map)
- Interactive Tube Map and sequence flow diagrams representing the system's operational nervous system.
- Metro lines represent data streams (e.g., Red Line = User Auth Flow, Blue Line = Video Processing Pipeline, Green Line = Billing Webhooks).
- Stations represent database entities, message queues, and service endpoints. Interchange stations represent shared domain models.

#### View 3: Application View (Rendered Screens & Cloud Infrastructure Topology)
- **Screen & Route Catalog:** Visual layout of all user-facing screens and API routes. For web apps, leverages Stitch MCP or AST component extractors to render wireframe cards of each page.
- **Cloud Infrastructure Topology:** Self-contained SVG diagram showing cloud VPC boundaries, container task definitions, database clusters, caches, ingress load balancers, and DNS routing.

---

### Pillar 5: Gap & Opportunity Discovery $\rightarrow$ GOVERNS Goal Generation
**Goal:** Rather than leaving the user with a passive diagram, Synlynk actively diagnoses codebase gaps and translates them into GOVERNS-compliant goals.

- **The Automated Gap Scanner:**
  1. *Test Coverage Voids:* Discovers high-traffic API routes or core domain entities lacking unit or integration test coverage.
  2. *Security & Hygiene Gaps:* Unvalidated incoming webhooks, missing rate limiters, or unencrypted secrets in configs.
  3. *Documentation Drift:* Public API routes missing OpenAPI/Swagger docstrings, or `README.md` out of sync with actual CLI commands.
  4. *Architectural Debt:* Circular imports between modules, unindexed database foreign keys, or missing CI/CD lint/type-check stages.
- **GOVERNS Goal Formulation:**
  - Candidate goals are formulated adhering strictly to the GOVERNS standard (`--outcome "..." --criterion "..."`):
    - *Example Goal 1:* `--outcome "Establish 100% test coverage for video ingestion pipeline" --criterion "pytest tests/test_ingest.py passes with zero failures across valid and malformed payloads"`
    - *Example Goal 2:* `--outcome "Automate GitHub Actions CI lint and type-checking" --criterion "GitHub Actions workflow executes ruff, black, and mypy on all pull requests with zero errors"`
- **One-Click User Approval:**
  - User reviews candidate goals in the Vizor UI or CLI prompt.
  - Clicking **`[Approve Goal]`** immediately writes to `state.db` via `synlynk goal create`, decomposes the goal into prioritized Ready Stories (`synlynk story create`), and establishes full project traceability.

---

### Pillar 6: First-Win Task Selection & Autonomous SOP Dispatch
**Goal:** Deliver the user's first tangible code victory within 5 minutes of launching onboarding.

- **Curated First-Win Candidates:**
  Synlynk presents 3 bite-sized, high-confidence, non-destructive tasks:
  1. *Candidate A (Verification):* "Generate comprehensive unit test suite for `api/routes/auth.py`" (Safe, high value, zero risk to existing behavior).
  2. *Candidate B (Hygiene):* "Add GitHub Actions CI workflow for automated testing and linting" (Safe, additive, unblocks team velocity).
  3. *Candidate C (Documentation & Typing):* "Add strict Pydantic request/response schemas for all unvalidated endpoints" (Safe, self-documenting).
- **Autonomous Unattended SOP Execution:**
  1. User clicks **`[Implement Candidate A]`**.
  2. Synlynk creates a dedicated git worktree (`git worktree add ../feat+auth-tests feat/codex/auth-tests`).
  3. Dispatches the task to the optimal harness (e.g. Codex or Agy) with explicit TDD instructions.
  4. Agent implements tests, runs verification locally, verifies green output.
  5. Pushes branch, creates GitHub Pull Request (`gh pr create`), and assigns non-authoring role (`qa`) for review.
  6. Vizor displays a live notification banner: **"First Win Complete! Pull Request #1 created and verified."**

---

## 5. Multi-Harness Debate Topics & Consensus Decisions (`dec-fcff261a`)

The multi-harness panel (`claude`, `codex`, `agy`, `grok`) convened on 2026-09-13 and reached unanimous consensus on the four architectural trade-offs:

### Debate 1: Terminal TUI vs. Local Vizor Browser Tab
- **Verdict: Adopt Hybrid CLI-First.**
- **Details:** Fast, responsive TTY summary with interactive chips. `Enter` accepts defaults and continues immediately. `Space` opens the interactive browser canvas at `http://localhost:27472/onboarding`. Full `--no-input` and headless CI sessions stay 100% terminal/JSON-only and never block waiting for a browser.

### Debate 2: Deterministic Static Heuristics vs. LLM Semantic Inference
- **Verdict: Tiered, Offline-First Scan.**
- **Details:** Deterministic AST/manifest scan (<10s, idempotent, zero LLM calls, `--json`) forms the onboarding-critical path. LLM-based domain/semantic labeling is strictly a non-blocking Tier 2 overlay with clear provenance tags; a token outage or missing model API key will never block onboarding.

### Debate 3: Non-Destructive Safety Guarantees & Dirty Tree Protection
- **Verdict: Zero Footprint Outside `.synlynk/` with Scoped Rollback.**
- **Details:** All writes stay fail-closed and strictly scoped to `.synlynk/` with a real snapshot so `synlynk rollback` is reliable. Dirty working trees fail closed or force an isolated git worktree rather than unexpectedly stashing or modifying the user's working copy.

### Debate 4: GOVERNS Goal Deconstruction Granularity
- **Verdict: Single North-Star First-Win Goal.**
- **Details:** Present ONE recommended, high-confidence, additive first-win goal (e.g., test suite generation or CI workflow addition), with explicit user approval required before writing to `state.db` or dispatching. Success is defined as a verified, PR-created-and-checked outcome (`gh pr create` + `synlynk pr check`); actual merging is outside the 5-minute promise.

### Scope Calibrations for v0.21.0
- **Cut/Deferred to Follow-on Vizor Release:** Heavy 3D spatial discovery and deeper rendered screen catalogs/cloud topology are deferred to a dedicated follow-on release, adhering to the project principle *"opt-in, nothing breaks without it, measurable ROI required."* v0.21.0 leverages the existing proven two/three-view SVG canvas (physical file tree, logical tubemap, route cards).
- **Distribution Formalized as 4th Workstream:** Distribution (`curl | sh`, pipx, brew, binaries, update/rollback) receives its own security/maintenance verification plan rather than being treated as an assumed detail.

---

## 6. Calibrated Implementation Workstreams for v0.21.0

| Workstream | Deliverable | Scope & Verification Gate | Harness Owner |
| :--- | :--- | :--- | :--- |
| **Workstream 1: Distribution** | Fast Install Engine & Security Verification | `curl \| sh`, `pipx`, Homebrew formula, preflight doctor, and signed rollback verification. | Codex |
| **Workstream 2: Discovery & Context** | Tiered Static AST Discovery & Chip Validation | <10s offline AST/manifest scanner, non-blocking Tier 2 LLM overlay, and CLI/Vizor "Confirm & Tweak" chips. | Codex & Agy |
| **Workstream 3: Vizor Canvas** | Existing 3-View Onboarding Canvas (`localhost:27472`) | Physical file tree, logical tubemap, route cards with zero external CDN dependencies. | Agy |
| **Workstream 4: GOVERNS First-Win** | Single North-Star Goal & SOP Task Dispatch | Automated gap discovery, GOVERNS goal generation in `state.db`, and 1-click isolated worktree dispatch creating verified PR. | Claude & Codex |

---

## 7. Next Action

Proceed to authoring the detailed Implementation Plan for v0.21.0 (`docs/superpowers/plans/2026-09-13-v0-21-0-ftue-onboarding-journey.md`) decomposing the 4 calibrated workstreams into sequential, verifiable TDD stories.
