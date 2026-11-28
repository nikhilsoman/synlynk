# Generalized Domain Framework & Tri-Graph Architecture (Domain Pack v2.0) — Design Spec

- **Date:** 2026-11-28
- **Status:** Proposed Specification — Pending Operator Review & DECIDE Panel
- **Issue Anchor:** [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339) ("Domain Graph for common SWE stacks @pm @tpm")
- **Goal Anchor:** `goal-4459c851` ("synlynk ships a versioned, technical-stack domain graph ... closing brownfield discovery gap")
- **Target Release:** v0.40.0 (First major post-v0.39 release arc)
- **Author:** Product Manager (`pm` role via AGY Conductor / Claude Sonnet 5.5)

---

## 1. Executive Summary & Intent

Modern software engineering and business systems operate with profound domain-specific context: architectural patterns, framework conventions, idioms, anti-patterns, compliance requirements, and specialized tooling. Currently, autonomous agent dispatch in Synlynk relies on generic model pre-training, leaving brownfield discovery vulnerable to:
1. Hallucinating compiler flags, test commands, or execution harnesses (e.g. attempting to run `./gradlew test` with wrong JDK versions, or guessing mobile build targets).
2. Missing domain idioms and violating architectural constraints (e.g., passing `ViewModel` instances past navigation boundaries in Jetpack Compose, or blocking on `Dispatchers.Main`).
3. Disconnected context across the codebase AST (`Code-Graph`) and markdown documentation (`Doc-Graph`).

This specification establishes **Domain Pack Framework v2.0** and the **Tri-Graph Architecture** (`Code-Graph` × `Doc-Graph` × `Domain-Graph`), realizing **Approach C (Interactive Multi-Tier Ontology Engine)**. It generalises the domain graph from a narrow compiler lookup into an exhaustive, multi-industry organizational and technical ontology while maintaining strict sub-1.5k prompt context budgets and a zero-bloat modular distribution engine.

---

## 2. The Ontological Axiom & The Tri-Graph

### 2.1 The Core Invariant Hierarchy

Every organizational, functional, and technical capability in Synlynk maps onto a strict, bidirectional hierarchy:

```
Industry
  └── Domain (has Stacks)
        ├── Function
        │     └── Workflow
        │           └── Task (owned by Role)
        └── Stack
              ├── Tools (CLI binaries, MCP servers, Skills)
              ├── Manifests (Fingerprint markers & lockfiles)
              ├── Competencies (Idioms & Best Practices)
              └── Anti-Patterns (Syntactic & architectural traps)
```

- **Industry:** Broad economic vertical (e.g., `Software & Technology`, `Financial Services`, `Healthcare & Life Sciences`).
- **Domain:** Distinct operating arena (e.g., `Mobile Applications`, `Cloud Infrastructure`, `Payments & Ledger`, `Digital Health`).
- **Function:** High-level departmental objective (e.g., `Client Engineering`, `Platform Security`, `Compliance Auditing`).
- **Workflow:** End-to-end operational sequence (e.g., `Deliver Composable Screen Feature`, `PCI-DSS Tokenization Pipeline`).
- **Task:** Unit of autonomous or collaborative work with verifiable exit criteria (e.g., `Author Espresso Acceptance Test`), explicitly **owned by a Role** (`dev`, `qa`, `architect`, `security`).
- **Stack:** Technical execution substrate (e.g., `android_kotlin`, `aws_cdk_typescript`, `fastapi_postgresql`).
- **Tools:** Executable CLI tools, MCP server resources, and Superpowers skills required to verify and execute tasks.
- **Competencies:** Curated engineering priors, idioms, and design patterns injected into dispatch prompts.
- **Anti-Patterns:** Negative examples and common AI pitfalls explicitly guarded against during verification.

---

### 2.2 The Tri-Graph Architecture: Code × Doc × Domain Cross-Indexing

In Synlynk's sub-3k context packager (`synlynk/pack.py`), brownfield discovery previously operated on two graphs:
1. **Code-Graph (Graphify AST):** Structural code symbols, callsites, and inheritance (`.synlynk/graphify-out/graph.json`).
2. **Doc-Graph (Sidecar Knowledge Graph):** Architectural specs, plans, decisions, devlogs, and reverse code-to-doc references (`.synlynk/docgraph.json`).

The **Domain-Graph (`.synlynk/domaingraph.json`)** is the missing third pillar. It acts as the semantic coordination fabric:

```
                      ┌───────────────────────────────────────────────┐
                      │                 Domain-Graph                  │
                      │           (.synlynk/domaingraph.json)         │
                      │  Industry -> Domain -> Function -> Workflow   │
                      │              └── Stack -> Tools/Competencies  │
                      └──────────────┬─────────────────┬──────────────┘
                                     │                 │
         code_to_domain_index        │                 │ doc_to_domain_index
         domain_to_code_index        ▼                 ▼ domain_to_doc_index
                      ┌──────────────────────┐   ┌──────────────────────┐
                      │      Code-Graph      │   │      Doc-Graph       │
                      │ (AST Calls & Symbols)│<─>│(Specs, ADRs & Memory)│
                      └──────────────────────┘   └──────────────────────┘
```

#### Bi-Directional Cross-Index Schema

Persisted at `.synlynk/domaingraph.json`, the compiler generates four deterministic lookup indexes:

1. **`code_to_domain_index`:**
   Maps physical file paths or AST symbols to their governing Domain, Stack, and Function:
   ```json
   {
     "app/src/main/java/com/synlynk/ui/HomeScreen.kt": {
       "industry": "software_and_technology",
       "domain": "mobile_applications",
       "stack": "android_kotlin",
       "function": "client_engineering",
       "matched_by": "extension:.kt + manifest:build.gradle.kts"
     }
   }
   ```
2. **`doc_to_domain_index`:**
   Maps markdown specs, ADRs, and plans to their governing Workflows and Tasks:
   ```json
   {
     "docs/superpowers/specs/2026-11-28-domain-pack-framework-v2.md": {
       "domain": "mobile_applications",
       "workflow": "feature_screen_delivery",
       "tasks": ["state_hoisting_architecture"]
     }
   }
   ```
3. **`domain_to_code_index`:**
   Given a Stack competency or anti-pattern, resolves all physical files, symbols, and test entrypoints in the workspace that embody or touch that competency.
4. **`domain_to_doc_index`:**
   Given a Role or Task, resolves relevant organizational memory, SOPs, and architectural decisions.

---

## 3. Data Models & Typed Schema (`DomainPackV2`)

The three historical pack definitions (`domain_packs.py` vertical lifecycle, `packs/*.yaml` org archetypes, and compiler proposal heuristics) collapse into a single typed schema implemented in `synlynk/domain_pack_schema.py`:

```python
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class TaskDefinition:
    id: str
    title: str
    owner_role: str
    summary: str
    competency_refs: List[str] = field(default_factory=list)
    tool_bindings: List[str] = field(default_factory=list)
    verification_command: Optional[str] = None

@dataclass
class WorkflowDefinition:
    id: str
    title: str
    summary: str
    tasks: List[TaskDefinition] = field(default_factory=list)

@dataclass
class FunctionDefinition:
    id: str
    title: str
    workflows: List[WorkflowDefinition] = field(default_factory=list)

@dataclass
class CompetencyDefinition:
    id: str
    name: str
    guidance: str
    anti_patterns: List[str] = field(default_factory=list)
    reference_urls: List[str] = field(default_factory=list)

@dataclass
class StackDefinition:
    id: str
    name: str
    manifests: List[str]
    extensions: List[str]
    lockfiles: List[str] = field(default_factory=list)
    tools: List[str] = field(default_factory=list)
    competencies: List[CompetencyDefinition] = field(default_factory=list)

@dataclass
class DomainPackV2:
    schema_version: str
    industry: str
    domain: str
    version: str
    title: str
    description: str
    stacks: List[StackDefinition] = field(default_factory=list)
    functions: List[FunctionDefinition] = field(default_factory=list)
    recommended_roles: List[str] = field(default_factory=list)
    scaffolding_templates: Dict[str, str] = field(default_factory=dict)
```

---

## 4. Distribution, Sizing & Prompt Budget

### 4.1 Zero-Bloat Sideloading Architecture
To prevent bloating the primary Synlynk Python package and CLI installer:
- **Core CLI Runtime (~15MB):** Contains only the metamodel schema validator, stack scanner (`scan.py`), and a single minimal software seed pack (`software_generic.json`).
- **Federated Pack Registry:** Community and official domain packs are hosted externally in `https://github.com/synlynk/domain-packs` and distributed via Synlynk Cloud / GitHub Releases as standalone JSON assets.
- **Sideloading CLI:**
  - `synlynk pack list`: Queries remote and locally cached packs.
  - `synlynk pack install <industry>/<domain>`: Downloads and verifies the pack into `~/.synlynk/cache/packs/` (user global) or `.synlynk/packs/` (workspace local).
  - `synlynk pack update`: Checks for newer revisions with backward-compatible schema migration.

### 4.2 Byte Size & Context Budget Calculations
- **On-Disk Footprint:**
  A production domain pack with 10 Functions, 25 Workflows, 50 Tasks, 3 Stacks, and 80 Competencies measures **~32 KB to 45 KB uncompressed JSON** (~6.5 KB gzipped).
- **In-Prompt Context Budget:**
  `pack.py` never dumps an entire domain pack into an agent's prompt. When dispatching on a story, `pack.py` identifies the active `Task` -> resolves its `Workflow` and associated `Stack Competencies` -> extracts an exact sub-slice:
  - Task Objective & Tools: ~150 tokens.
  - Recommended Idioms & Best Practices: ~450 tokens.
  - Anti-Patterns & Verification Commands: ~300 tokens.
  - **Total Dispatch Injection:** **~900 to 1,350 tokens** (well below the 1.5k token target, preserving headroom for diffs and memory).

---

## 5. Catalog of Initial Domain Packs

Upon initial release, the registry will feature five foundational packs across three key industries:

### 5.1 Industry: Software & Technology
1. **`mobile_applications` (Reference Implementation):**
   - Stacks: `android_kotlin` (Jetpack Compose, Gradle KTS), `ios_swift` (SwiftUI, SPM, CocoaPods), `cross_platform_react_native`.
   - Functions: `client_engineering`, `release_distribution`, `mobile_qa`.
2. **`cloud_infrastructure`:**
   - Stacks: `terraform_hcl`, `kubernetes_helm`, `aws_cdk_typescript`, `hetzner_fly_nodes`.
   - Functions: `platform_engineering`, `site_reliability`, `secops`.
3. **`web_saas`:**
   - Stacks: `nextjs_react_tailwind`, `fastapi_postgresql_sqlalchemy`, `go_grpc_microservices`.
   - Functions: `frontend_ux`, `api_platform`, `data_persistence`.

### 5.2 Industry: Financial Services & Fintech
4. **`payments_and_ledger`:**
   - Stacks: `double_entry_ledger`, `stripe_plaid_integrations`, `pci_dss_tokenization`.
   - Functions: `ledger_integrity`, `transaction_routing`, `financial_audit`.

### 5.3 Industry: Healthcare & Life Sciences
5. **`digital_health`:**
   - Stacks: `hipaa_audit_trail`, `hl7_fhir_apis`, `dicom_imaging_pipeline`.
   - Functions: `clinical_workflows`, `patient_privacy_secops`, `regulatory_filings`.

---

## 6. Dual-Lifecycle Engine: Day 0 Onboarding vs. Day 1..N Living Radar

### 6.1 Day 0: Onboarding Sideloading
During initial project setup (`synlynk init` / `synlynk onboard`):
1. **Scanner Extension (`scan.py` & `repo_classifier.py`):**
   Scans the repository for extended stack manifest signatures:
   - Android: `build.gradle.kts`, `settings.gradle.kts`, `gradle/libs.versions.toml`.
   - iOS: `Package.swift`, `Podfile`, `*.xcodeproj/project.pbxproj`.
   - Cloud: `main.tf`, `helmfile.yaml`, `fly.toml`.
2. **Automatic Domain Match & Prompt:**
   The wizard surfaces the inferred domain:
   ```
   [Found Mobile Application]: Android Kotlin / Jetpack Compose detected.
   Sideloading official pack 'software_and_technology/mobile_applications'... Done.
   ```
3. **Graph Initialization:**
   `domaingraph.py` compiles `.synlynk/domaingraph.json`, immediately binding tool paths (e.g. `./gradlew connectedAndroidTest`) and role competencies.

### 6.2 Day 1..N: Living Workspace Context Engine
1. **Maintainer Drift Radar (`synlynk maintainer sweep`):**
   On scheduled wake cycles, the Maintainer inspects workspace manifest changes (e.g., a new dependency added in `libs.versions.toml` or `package.json`).
2. **Automatic Competency Enrichment:**
   When dependencies change (e.g. introducing Room Database or AWS DynamoDB), Maintainer updates the active stack competencies in `.synlynk/domaingraph.json`.
3. **Local Customization & Institutional Learning:**
   When an agent successfully passes a difficult verification after fixing an architectural bug, Maintainer surfaces an option to record the discovered rule into `.synlynk/packs/workspace_overrides.json`.

---

## 7. Visual Introspection & Control Plane (Agent Studio & Proposal Studio)

### 7.1 Agent Studio Organigram (`synlynk viz roles`)
- Renders the full `Industry -> Domain -> Function -> Workflow -> Task -> Role` hierarchy as an interactive visual graph.
- **Role Binding Matrix:** Operators can view which roles own which workflows. Drag-and-drop rebinding allows transferring workflow ownership (e.g. assigning `Author Acceptance Suite` from `dev` to `qa`).
- **Tool & Skill Discovery:** Each role card displays bound Skills, MCP servers, and CLI binaries. Missing local binaries are flagged with one-click "Provision" actions.

### 7.2 Proposal Studio Filtering (`synlynk viz proposals`)
- Backlog proposals and release candidates are automatically tagged with Domain and Stack badges (e.g. `[Mobile / Android]`, `[Cloud / Fly.io]`).
- Preflights verify that all required role competencies and tools are satisfied before dispatch approval.

---

## 8. Greenfield & Brownfield Architecture Scaffolding

1. **Greenfield (`synlynk init --new`):**
   - User specifies an industry and domain.
   - The engine unpacks `scaffolding_templates` defined in the domain pack, creating clean directory structures, recommended linters, version catalogs, CI pipelines, and standard Synlynk docs (`roadmap.md`, `todo.md`, `memory.md`, `costs.md`).
2. **Brownfield (`synlynk scan` / `synlynk onboard`):**
   - Non-destructive ingestion: existing repository files are never overwritten.
   - The wizard detects structural gaps (e.g., missing CI test workflow or missing architectural documentation) and offers to generate targeted companion scaffolds.

---

## 9. GitHub Comment Verbs & Event-Driven Wakeups

To ensure operator comments and instructions on GitHub issues (such as [gh:#5339](https://github.com/nikhilsoman/synlynk/issues/5339)) are processed reliably without relying on manual CLI runs:

### 9.1 Supported Command Verbs
The intake engine parses issue comments for explicit `@synlynk` command verbs:
- `@synlynk /pm [instructions]`: Wakes PM role to ingest guidance, refine specs, and respond on GitHub.
- `@synlynk /spec [topic]`: Initiates or updates the superpower design specification.
- `@synlynk /decide`: Convenes the multi-harness DECIDE panel on open Key Decisions.
- `@synlynk /sweep`: Wakes TPM sweep to evaluate linked stories immediately.
- `@synlynk /dispatch [role] [story_id]`: Dispatches an assigned story to an agent.

### 9.2 Event-Driven Polling in Daemon
`synlynk watch` / `daemon.py` is augmented with an `IssueCommentPoller`:
- Polls `repos/:owner/:repo/issues/comments?since=<last_poll_ts>` every 10 minutes.
- Matches active tickets and goal anchors.
- When an `@synlynk` command is detected, dispatches the designated role with the comment payload.

---

## 10. Phased Implementation Roadmap

| Phase | Milestone | Scope & Deliverables | Estimated Cost / Tests |
|:---|:---|:---|:---|
| **Phase 1** | **Schema & Fingerprint Core** | Author `synlynk/domain_pack_schema.py`; extend `scan.py` and `repo_classifier.py` for mobile & cloud manifests; author `mobile_applications.json` reference pack. | 15 new tests, ~0.08 USD |
| **Phase 2** | **Tri-Graph Compiler & Packager** | Implement `synlynk/domaingraph.py` producing `.synlynk/domaingraph.json`; wire cross-indexing into `docgraph.py` and sub-1.5k extraction into `pack.py`. | 25 new tests, ~0.12 USD |
| **Phase 3** | **Sideloading CLI & Maintainer Radar** | Implement `synlynk pack install / list / update`; wire drift detection into `maintainer.py` wake cycle and `init --wizard`. | 20 new tests, ~0.10 USD |
| **Phase 4** | **Agent Studio Visual Canvas & Verbs** | Render domain organigram in `synlynk viz roles`; implement GitHub comment command parser in `gh_role.py` and daemon watcher. | 20 new tests, ~0.15 USD |

---

## 11. Key Decisions for DECIDE Panel (KD1–KD12)

Before implementation dispatches begin, the following Key Decisions will be formally evaluated by the cross-harness DECIDE panel:

- **KD1: Pack Format:** Strictly JSON (optimized for fast serialization & typing) vs. Dual JSON/YAML support.
- **KD2: Schema Location:** Standalone `synlynk/domain_pack_schema.py` vs. folded into `synlynk/models.py`.
- **KD3: Storage Location:** Workspace-local `.synlynk/packs/` vs. global `~/.synlynk/cache/packs/` with workspace symlinks.
- **KD4: Reverse Index Invalidation:** Rebuild `.synlynk/domaingraph.json` on git commit hooks vs. lazy query-time staleness check via mtime.
- **KD5: Fallback Behavior:** If no domain pack matches during brownfield scan, fall back to `software_generic` seed pack vs. empty graph.
- **KD6: Prompt Injection Cap:** Hard ceiling of 1,500 tokens in `pack.py` vs. dynamic slider based on target harness context window.
- **KD7: Tool Resolution:** Require explicit local executable path vs. allow advisory MCP server names.
- **KD8: Role Deprecation:** How domain packs handle custom user-defined roles outside the standard 8 fleet roles.
- **KD9: Greenfield Scaffolding:** Opt-in prompt during `init` vs. dedicated command `synlynk scaffold --domain <name>`.
- **KD10: Comment Polling Interval:** 10-minute cron in daemon vs. GitHub Actions webhook push dispatch.
- **KD11: Pack Versioning:** Strict SemVer (`2.0.0`) with backward compatibility checks vs. date-stamped revisions.
- **KD12: External Registry Hosting:** GitHub Releases raw assets vs. dedicated Synlynk.com package API endpoint.
