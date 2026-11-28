# Brainstorm — Unified Generalized Domain Framework: Beyond SWE Stacks

- **Date:** 2026-11-28
- **Issue:** [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339) — "Domain Graph for common SWE stacks @pm @tpm"
- **Author:** Product Manager (`pm` role via Claude Sonnet 5.5 / AGY Conductor)
- **Status:** Strategic Brainstorm & Deep-Dive Architecture Specification (Pre-spec)
- **Goal Anchor:** `goal-4459c851` (Unified Domain Graph & Autonomous Ontology Engine)

---

## 1. Intent & Core Ontological Axiom

Following operator guidance on [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339#issuecomment-7238431384) and [#5339 (comment #7239020742)](https://github.com/nikhilsoman/synlynk/issues/5339#issuecomment-7239020742), this document formalizes the **Tri-Graph Architecture** (`Code-Graph` × `Doc-Graph` × `Domain-Graph`) and details **Approach C: The Interactive Multi-Tier Ontology Engine**.

### The Core Invariant Hierarchy

```
Industry
  └── Domain (has Stacks)
        ├── Function
        │     └── Workflow
        │           └── Task (owned by Role)
        └── Stack
              ├── Tools
              └── Competencies
```

Every concept in the Synlynk autonomous execution engine maps cleanly onto this hierarchy:

1. **Industries** contain **Domains** (e.g. `Software & Cloud Services`, `Media & Entertainment`, `Healthcare & Life Sciences`).
2. **Domains** contain **Functions** (e.g. in `Software`: `Core Infrastructure`, `Frontend UX`, `Data Engineering`, `Platform SRE`; in `Media`: `Post-Production`, `Transcoding`, `Asset Distribution`).
3. **Functions** have **Workflows** (e.g. `Release Readiness Gate`, `Incident Remediation Loop`, `Automated Video Localization`).
4. **Workflows** have **Tasks** (discrete atomic units of verifiable work, corresponding to Synlynk `stories`).
5. **Tasks** have **Owners**, and **Owners** are **Roles** (e.g. `dev`, `qa`, `architect`, `pm`, `maintainer`, `colorist`, `sound_engineer`).
6. **Domains** also have **Stacks** (e.g. `Android Kotlin/Compose`, `iOS Swift/SwiftUI`, `Python/FastAPI/SQLite`, `FFmpeg/Wasm`).
7. **Stacks** have **Tools** (e.g. `gradle`, `pytest`, `ffmpeg`, `docker`) and **Competencies** (e.g. `State Hoisting`, `Schema Migration Safety`, `Color Grading`).

---

## 2. The Tri-Graph Architecture: Code × Doc × Domain Cross-Indexing

In Synlynk's sub-3k context packager (`pack.py`), brownfield discovery previously leaned on two graphs:
1. **Code-Graph (Graphify AST):** Structural code symbols, callsites, and inheritance (`.synlynk/graphify-out/graph.json`).
2. **Doc-Graph (Sidecar Knowledge Graph):** Architectural specs, plans, decisions, and reverse code-to-doc references (`.synlynk/docgraph.json`).

### The Missing Third Pillar: Domain-Graph (`.synlynk/domaingraph.json`)
The **Domain-Graph** bridges the abstract intention of a task to the physical realities of the codebase and documentation. It turns implicit model assumptions into **versioned, traversable, inspectable semantic edges**:

```
[ Domain Graph Node: Android Compose Stack ]
       │
       ├── (recommends_competency) ──> [ Compose State Hoisting ]
       │                                       │
       │                                       ├── (cited_in_doc) ──> docs/superpowers/specs/...
       │                                       │
       │                                       └── (matches_code_pattern) ──> @Composable fun HomeScreen(...)
       │
       └── (binds_tool) ──────────────> [ ./gradlew test ]
                                               │
                                               └── (verifies_task) ──> Task: Instrumented Acceptance Suite
```

### Bi-Directional Cross-Index Schema

The domain pack compiles directly into a cross-indexed graph file persisted at `.synlynk/domaingraph.json`:

1. **`code_to_domain_index`**: Maps a code file path or AST symbol to its matching Domain, Stack, and Function (e.g., `app/src/main/.../HomeScreen.kt` -> `{"domain": "mobile", "stack": "android_kotlin", "function": "frontend_ux"}`).
2. **`doc_to_domain_index`**: Maps markdown specs, ADRs, and plans to their governing Workflows and Tasks.
3. **`domain_to_code_index`**: Given a Domain or Stack competency, returns all matching symbols, entrypoints, and manifest files in the codebase.
4. **`domain_to_doc_index`**: Given a Task or Role, returns relevant institutional knowledge, guidelines, and SOPs.

---

## 3. Deep Dive into Approach C: Interactive Multi-Tier Ontology Engine

Approach C is an end-to-end operational system spanning:
1. **Onboarding Sideloading (Day 0)**
2. **Continuous Living Context (Day 1..N)**
3. **Visual Interactive Control Plane (Agent Studio & Proposal Studio)**

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Approach C: Architecture Flow                         │
└─────────────────────────────────────────────────────────────────────────────┘

       Onboarding Intake                     Living Workspace Traversal
     (Initial Fingerprint)                       (Day 1..N Cadence)
               │                                         │
               ▼                                         ▼
   ┌───────────────────────┐                 ┌───────────────────────┐
   │ scan.py / classifier  │                 │    TPM / Maintainer   │
   │ detects manifests     │                 │   Wake Cycle & Sweeps │
   └───────────┬───────────┘                 └───────────┬───────────┘
               │                                         │
               ▼                                         ▼
   ┌───────────────────────┐                 ┌───────────────────────┐
   │ Download / Sideload   │                 │ Continual Discovery & │
   │ Domain Packs (v2.0)   │                 │ Graph Traversal Sync  │
   └───────────┬───────────┘                 └───────────┬───────────┘
               │                                         │
               └───────────────────┬─────────────────────┘
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │         Tri-Graph Federation Core         │
             │   Code-Graph × Doc-Graph × Domain-Graph   │
             │        (.synlynk/domaingraph.json)        │
             └─────────────────────┬─────────────────────┘
                                   │
                                   ▼
             ┌───────────────────────────────────────────┐
             │       Interactive Visual HUD (Vizor)      │
             │                                           │
             │  • Proposal Studio: Workflow/Task lanes   │
             │  • Agent Studio: Role Operations Panel    │
             │  • Domain Graph Canvas: Visual Topology   │
             └───────────────────────────────────────────┘
```

### Pillar 1: Onboarding Sideload & Progressive Context Enrichment
- **Detection at Intake:** During `synlynk init` / `synlynk quickstart`, `scan.py` and `repo_classifier.py` inspect manifest fingerprints (e.g., `build.gradle.kts`, `Package.swift`, `go.mod`, `docker-compose.yml`, `package.json`).
- **Prompted Sideloading:** If an Android project is detected, the CLI prompts:
  > *"Detected Android Native stack. Download & link domain pack `technology_software/mobile_client_engineering`? [Y/n]"*
- **Local Cache & Offline Guarantee:** Downloaded packs are cached globally in `~/.synlynk/packs/` and mirrored locally into `.synlynk/domain_packs/`. Subsequent operations require zero internet access.

### Pillar 2: Ongoing Context Engine (Living Workspace Radar)
- **Beyond Initial Setup:** Domain packs do not go stale after onboarding. As new code directories, modules, or workflow specs are added, the Maintainer's wake cycle (`run_maintainer_wake_cycle`) audits the repository for stack/function drift.
- **Dynamic Context Injection in `pack.py`:** When `dispatch_agent` prepares a prompt for a task:
  1. It checks the task's linked `Workflow` and `Role`.
  2. It pulls the specific **Stack Competencies** and **Idiomatic Patterns** from the Domain Graph.
  3. It joins with Doc-Graph references and AST code symbols.
  4. It compresses this into a sub-1.5k token prompt prior:
     > *"Stack Prior (Android Kotlin): Use Jetpack Compose state hoisting; Room migrations must use autoMigrations or explicit Migration(X, Y); verify via `./gradlew test`."*

### Pillar 3: Visual Introspection & Control Plane (Agent Studio & Proposal Studio)
- **Agent Studio Integration (`synlynk viz roles`):**
  - Displays the active Industry, Domains, and Stacks.
  - The Role Operations Panel renders the matrix of **Functions -> Workflows -> Tasks** alongside the designated **Role Owners**.
  - Operators can visually adjust role ownership (e.g., reassigning "Contract Effect Verification" from `qa` to `dev`, or customizing stack build tools).
- **Proposal Studio Integration (`synlynk viz proposals`):**
  - TPM and Maintainer proposals display rich domain badges (e.g., `[Domain: Mobile Client]`, `[Workflow: Release Hardening]`, `[Stack: Android Kotlin]`).
  - Tasks can be filtered or staged by business Function or technical Stack.

---

## 4. Unified Typed Schema: `domain-pack-v2.json`

```json
{
  "$schema": "https://synlynk.com/schemas/domain-pack-v2.json",
  "version": "2.0.0",
  "industry": "technology_software",
  "domain": "mobile_client_engineering",
  "display_name": "Mobile Client Engineering (Android & iOS)",
  "naics": "541511",
  "apqc_id": "3.0.0",
  
  "stacks": [
    {
      "stack_id": "android_kotlin",
      "display_name": "Android Kotlin Native",
      "fingerprints": {
        "manifests": ["build.gradle.kts", "settings.gradle.kts", "build.gradle"],
        "extensions": [".kt", ".kts", ".xml"],
        "lockfiles": ["gradle/libs.versions.toml"]
      },
      "tools": [
        {"name": "gradle", "executable": "./gradlew", "role": "build_system"},
        {"name": "adb", "executable": "adb", "role": "device_runner"}
      ],
      "competencies": [
        "State Hoisting (Jetpack Compose)",
        "Room Database Migrations",
        "Coroutines / Flow Concurrency"
      ],
      "anti_patterns": [
        "Blocking calls on Dispatchers.Main",
        "Hardcoded version strings outside version catalogs"
      ]
    }
  ],

  "functions": [
    {
      "function_id": "client_release_hardening",
      "name": "Client Release Hardening & Verification",
      "workflows": [
        {
          "workflow_id": "pre_submission_qa_matrix",
          "name": "Pre-Submission Device Matrix QA",
          "tasks": [
            {
              "task_type": "test",
              "name": "Run Instrumented Acceptance Suite",
              "owner_role": "qa",
              "required_competency": "Android UI Testing",
              "required_tools": ["gradle"]
            },
            {
              "task_type": "implement",
              "name": "Update Version Catalogs & Bump Build Code",
              "owner_role": "dev",
              "required_competency": "Version Catalog Maintenance",
              "required_tools": ["gradle"]
            }
          ]
        }
      ]
    }
  ]
}
```

---

## 5. Phased Delivery Roadmap for Approach C

| Phase | Milestone | Scope | Deliverables |
|:---|:---|:---|:---|
| **Phase 1** | **Ontology Metamodel & Fingerprinting Core** | Define schema models; extend `scan.py` & `repo_classifier.py` for mobile/cloud manifests; author reference packs (`software`, `mobile_client`, `media_transcoding`). | `synlynk/domain_pack_schema.py`, updated `scan.py`, reference JSON packs. |
| **Phase 2** | **Tri-Graph Compilation & Cross-Indexing** | Build `synlynk/domaingraph.py` creating `.synlynk/domaingraph.json`; wire bi-directional cross-indexing into `docgraph.py` and `pack.py`. | Reverse index queries, sub-1.5k stack prior packaging. |
| **Phase 3** | **Sideloading & Living Workspace Radar** | Implement `synlynk pack install / list / update`; wire into `onboarding_state.py` and Maintainer wake cycle audit. | Local caching, automatic drift detection. |
| **Phase 4** | **Visual Canvas & Agent Studio Integration** | Render interactive domain graph in `synlynk viz roles` and `synlynk viz proposals`; interactive role-workflow rebinding. | Agent Studio canvas, Proposal Studio domain filters. |

---

## 6. Next Actions

1. Commit this detailed Approach C architecture into `docs/brainstorm/2026-11-28-generalized-domain-framework.md` on branch `feat/pm/generalized-domain-graph-brainstorm`.
2. Push and update PR #5577.
3. Post the detailed rollup response on [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339).
4. Proceed to drafting the formal specification (`docs/superpowers/specs/2026-11-28-domain-pack-framework-v2.md`).
