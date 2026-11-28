# Brainstorm — Unified Generalized Domain Framework: Beyond SWE Stacks

- **Date:** 2026-11-28
- **Issue:** [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339) — "Domain Graph for common SWE stacks @pm @tpm"
- **Author:** Product Manager (`pm` role via Claude Sonnet 5.5 / AGY Conductor)
- **Status:** Strategic Brainstorm & Architecture Alternatives (Pre-spec)
- **Goal Anchor:** `goal-4459c851` (Unified Domain Graph & Autonomous Ontology Engine)

---

## 1. Intent & Core Ontological Axiom

Following operator guidance on [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339#issuecomment-7238431384), this brainstorm reframes and generalizes the "Domain Graph" from a narrow software syntax/compiler lookup into an **exhaustive, multi-industry organizational and technical ontology**.

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

## 2. Structural Synthesis: Unifying the Three Fragmented "Packs"

Prior to this generalization, Synlynk suffered from semantic namespace collision across three separate mechanisms:
1. `synlynk/domain_packs.py` (`industry-vertical lifecycle`: NAICS code, APQC, SFIA).
2. `packs/*.yaml` (`org/role packs`: Studio, Software Product, Agency).
3. `gh:#5339 technical stack proposals` (build tools, compiler flags, framework priors).

### The Unified Domain Pack Schema v2.0

Under the Generalized Domain Framework, all three collapse into a cohesive, typed JSON/YAML structure:

```json
{
  "$schema": "https://synlynk.com/schemas/domain-pack-v2.json",
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
        "manifests": ["build.gradle.kts", "settings.gradle.kts"],
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

## 3. The 3 Architectural Approaches for Synlynk Integration

### Approach A: Static Graph Manifests (Local File Prior)
- **Concept:** Store domain packs as versioned static JSONs in `.synlynk/domain_packs/`. `scan.py` matches stack fingerprints to detect the domain; dispatches inject relevant stack tools & competencies into prompt context.
- **Pros:** Zero network dependencies; works offline; immediate deterministic lookups.
- **Cons:** Rigid; hard to update across external ecosystems without core Synlynk version updates.

### Approach B: Dynamic Dual-Layer Ontology (Core Framework + Hosted/Federated Corpus)
- **Concept:** Synlynk core maintains the typed metamodel and runtime fingerprinting scanner (`scan.py` / `repo_classifier.py`). The actual domain pack definitions (Android, Cloud Infra, Healthcare HIPAA Data, Video Transcoding) are modularized packages fetched via `synlynk pack install <industry>/<domain>` or sideloaded via Synlynk Cloud.
- **Pros:** Fits the existing `editions.py` hosted-tiering model; communities and enterprises can author custom industry/stack packs; keeps core CLI sub-3k token lean.
- **Cons:** Requires a registry index and version resolution engine.

### Approach C: Interactive Ontology Graph with Multi-Modal Role Discovery (Agent Studio Integration)
- **Concept:** Combine Approach B with visual introspection in Proposal Studio (`synlynk viz proposals`) and Agent Studio (`synlynk viz roles`). When an unfamiliar repository or industry domain is opened, the system auto-infers the Functions, Workflows, Roles, and Stacks, rendering an interactive ontology canvas where operators can reassign role ownership or toggle stack tool bindings.
- **Pros:** Directly unifies the Maintainer's role ops panel, TPM's story decomposition, and agent dispatch priors into a single visual control plane.
- **Cons:** Higher initial engineering scope across both Python CLI backend and Vizor frontend.

---

## 4. Immediate Concrete Next Steps

1. **Submit Brainstorm to Branch & Commit:** Save this agenda to `docs/brainstorm/2026-11-28-generalized-domain-framework.md` and commit to branch `feat/pm/generalized-domain-graph-brainstorm`.
2. **Post Rollup to [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339):** Summarize the hierarchy and the 3 architectural integration options for operator review.
3. **Formalize into Spec & DECIDE Panel:** Once Nikhil indicates preferred approach (A, B, or C), author the specification in `docs/superpowers/specs/2026-11-28-domain-pack-framework-v2.md` and run the formal DECIDE panel.
