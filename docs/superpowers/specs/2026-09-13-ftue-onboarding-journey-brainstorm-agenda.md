# Synlynk v0.21.0 FTUE & Onboarding Journey — Specification & Architecture

**Document:** `docs/superpowers/specs/2026-09-13-ftue-onboarding-journey-brainstorm-agenda.md`  
**Target Release:** v0.21.0 ("The Visual, Cross-Environment & Autonomous Onboarding Release")  
**Date:** 2026-09-13  
**Author / Conductor:** Agy (`@agy`, AntiGravity)  
**Collaborators:** Claude (`@claude`), Codex (`@codex`), Grok (`@grok`)  
**Status:** APPROVED (Consensus Decision `dec-fcff261a` updated and ratified)  

---

## 1. Executive Summary & Core Thesis

### The Core Problem
First-time developer onboarding in complex codebases is broken. When an engineer or autonomous agent enters a repository, they are typically met with a dense file tree, an outdated `README.md`, fragmented configs, and silent tribal knowledge. Previous attempts at autonomous developer tooling fell into three major anti-patterns:
1. **Interrogation Fatigue:** Text-based wizard CLIs that pepper the user with 10–15 sequential terminal questions before delivering any value.
2. **Static Read-Only Dead-Ends:** Tools that scan the repo and spit out a 500-line Markdown file or static report, leaving the user with the classic cliff: *"Now what?"*
3. **Fragmented & Disconnected Views:** File trees living in CLI text, module graphs in separate web diagrams, cloud infra in AWS/Terraform consoles, and business logic locked in Jira.
4. **Terminal/CLI Elitism:** Forcing all developers to install and learn standalone terminal CLI harness wrappers (`claude`, `agy`, `codex`, `grok`), ignoring the fact that the vast majority of modern developers work natively inside AI IDEs (Cursor, Windsurf, VS Code, Antigravity IDE), cloud platforms (Replit, Emergent), or modern terminals (Warp).

### The Synlynk v0.21.0 Thesis: Intent Transmission, Surface Agnosticism & First Real Win
Synlynk's purpose is to be the **synaptic link** between human architectural intent and multi-agent autonomous execution. Onboarding cannot simply be an inventory script—it must be an **interactive, progressive-disclosure onboarding journey** that moves the user from zero to their **First Real Autonomous Win** in under 5 minutes, meeting them on whichever surface they prefer (Web Browser, AI IDE, Cloud Workspace, or Modern Terminal).

```
┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
│                                 THE 5-MINUTE ONBOARDING JOURNEY                                   │
│                                                                                                  │
│   [Stage 0: Foundation] ──► [Stage 1: Surface Binding] ──► [Stage 2: Greenfield & Tour]         │
│   • What Synlynk IS/ISN'T    • Auto-Detect IDE/Browser      • Micro-App ("syn-ping") Loop        │
│   • Home vs. Away Model      • Non-Destructive Fencing      • "Behind the Curtain" Tour          │
│   • Agy & Claude Roles       • Cursor, Windsurf, VS Code,   • Vizor 3-View Canvas (Tree,         │
│   • GitHub App Identities      Warp, Agy, Replit, Emergent    Tubemap, Application Screens)      │
│                              • 1-Click GitHub Apps via Vizor                                     │
│                                                                   │                              │
│                                                                   ▼                              │
│   [Stage 5: Uninstall]  ◄── [Stage 4: Upgrade] ◄── [Stage 3: Brownfield Real Adoption]            │
│   • Zero-Zombie Cleanup      • Safe DB Migration            • Git Safety Gates & Snapshots       │
│   • Service & Shim Removal   • Instruction Refresh          • 3D Discovery & Confirm Chips       │
│   • Zero Host Residue        • Zero-Downtime Daemon         • Gap Discovery ➔ GOVERNS Goal       │
│                                Restart                      • First Real Win PR in < 5 minutes   │
└──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Stage 0: The Mental Model (Upfront Education)

Before creating files or modifying configuration, Synlynk introduces the developer to the foundational concepts of multi-agent engineering.

### A. What Synlynk IS vs. What It ISN'T
- **What it IS:** The **control plane and coordination substrate** for multi-agent software development. It orchestrates execution through state persistence (`state.db`), continuous context synchronization (`.synlynk/context.md`), structured project documentation (`project-docs/`), and git worktree isolation.
- **What it ISN'T:**
  - *Not an LLM model:* Synlynk does not sell proprietary models; it orchestrates the best models from Google, Anthropic, OpenAI, and xAI.
  - *Not a disposable chat wrapper:* Chat sessions lose memory; Synlynk maintains persistent project memory across months of execution.
  - *Not a SaaS lock-in:* Operates 100% locally on your machine with zero cloud telemetry requirements.
  - *Not a Terminal-only CLI:* It is surface-agnostic, integrating natively into Cursor, Windsurf, VS Code, Warp, Antigravity IDE, Replit, Emergent, Claude Desktop, and browser web interfaces.

### B. Home Conductor vs. Away Workers (Separation of Concerns)
- **Home Conductor (The Brain):** The interactive intelligence pair-programming with the human operator (in Cursor, Antigravity IDE, Claude, or terminal). It holds the PM, TPM, and Lead Architect charters, owns `state.db`, `project-docs/todo.md`, and `project-docs/roadmap.md`, and directs the milestone execution loop.
- **Away Workers (The Hands):** Ephemeral, headless worker instances dispatched into isolated git worktrees (`synlynk dispatch <harness> --task "..."`). They execute focused tasks, write unit tests, push branches, and open pull requests without touching global project state.

### C. Recommended Home Conductors: Why Agy & Claude Lead
- **Agy (AntiGravity / Gemini 1.5 & 2.0 Pro) — The Autonomy & Context Champion:**
  - *1M to 2M Token Context Window:* Ingests entire codebases, complete git histories, and extensive documentation simultaneously without mid-session amnesia or premature context compaction.
  - *Deep Analytical Autonomy:* Excels at repo-wide 3D discovery, structural refactoring, and multi-file synthesis.
- **Claude (Claude 3.5 Sonnet) — The Architectural & Design Specialist:**
  - *Precision Code Synthesis & PM Rigor:* Unmatched in architectural spec brainstorming, edge-case analysis, and structured policy generation.

### D. Dedicated GitHub Apps for Workspace Agents
Rather than running all agent operations under a single personal GitHub token, Synlynk provisions lightweight, dedicated GitHub App identities (`@syn-pm[bot]`, `@syn-qa[bot]`, `@syn-arch[bot]`, `@syn-dev[bot]`, `@syn-infra[bot]`).
- **Why this is critical:**
  1. **Separation of Concerns:** Commit and PR histories clearly reflect *who* did what (e.g. dev wrote the code, qa reviewed and approved).
  2. **Non-Authoring Review Compliance:** Bypasses GitHub's self-approval block (`"Can not approve your own pull request"`), enabling authentic, automated CI/CD merge gating.
  3. **Least Privilege Security:** QA bots only need read/review access; only release bots get merge permissions.

---

## 3. Stage 1: Surface & Fleet Binding (Cross-Environment Architecture)

Developers do not need to install or learn terminal CLI harnesses to use Synlynk. Synlynk automatically binds to whichever environment the developer already uses.

```
                                  SYNLYNK UNIVERSAL SURFACES
  ┌──────────────────────────────────────────────────────────────────────────────────────────────────┐
  │                                                                                                  │
  │   SURFACE 1: WEB GUI (VIZOR)          SURFACE 2: AI IDEs & DESKTOP       SURFACE 3: CLOUD & TERM │
  │   (Zero-Terminal / Browser-First)     (Cursor, Windsurf, VS Code, Agy)   (Warp, Replit, Emergent)│
  │   • http://localhost:27472            • Native Rules (.cursorrules/mdc)  • .warp/workflows/*.yaml│
  │   • 3D Discovery Chips                • Model Context Protocol (MCP)     • .replitrules & nix run│
  │   • 3-View Canvas (Tree, Tube, UI)    • IDE AI acts as Home Conductor    • Emergent MicroVM agent│
  │   • 1-Click GitHub App Provisioning   • Reads .synlynk/context.md        • Headless CLI & daemon │
  │                                                                                                  │
  └──────────────────────────────────────────────────────────────────────────────────────────────────┘
```

### A. Surface Auto-Discovery
During initialization, Synlynk inspects the project and host environment to configure native bindings:
1. **Cursor:** Detects `.cursor/` or running `Cursor.app` $\rightarrow$ generates `.cursor/rules/synlynk.mdc` with `alwaysApply: true`.
2. **Windsurf:** Detects `.windsurf/` or `.windsurfrules` $\rightarrow$ generates `.windsurfrules`.
3. **VS Code / Copilot:** Detects `.vscode/` $\rightarrow$ generates `.github/copilot-instructions.md` and `.vscode/extensions.json`.
4. **Warp Terminal:**
   - Detects `~/.warp` directory or `$TERM_PROGRAM=WarpTerminal`.
   - Generates `.warp/workflows/synlynk.yaml`, exposing parameterized command workflows in Warp's Command Palette (`synlynk start`, `synlynk dispatch <harness>`, `synlynk watch`, `synlynk status`, `synlynk viz`).
   - Registers `synlynk mcp` over `stdio` in Warp AI Assistant settings (`~/.warp/mcp.json`).
   - Emits OSC 133 semantic prompt markers so command outputs render cleanly as distinct, navigable Warp blocks.
5. **Antigravity IDE (`Agy`):**
   - Detects `~/.gemini/antigravity-cli/` or `$ANTIGRAVITY_ENV`.
   - Installs `skills/synlynk/SKILL.md` skill pack into Antigravity builtin skills.
   - Generates Model Context Protocol (MCP) server definition in `~/.gemini/antigravity-cli/mcp/synlynk/` with eager tool definitions (`synlynk_get_context.json`, `synlynk_checkpoint.json`).
   - Injects non-destructive instructions into `GEMINI.md` (Stage 0 mental model, Home Conductor role, worktree policy).
   - Context Priming: leverages Agy's 1M–2M token context window to ingest the full `.synlynk/context.md` snapshot without mid-session amnesia or compaction.
6. **Replit (Replit Agent & Cloud Containers):**
   - Detects `.replit` configuration or `$REPL_ID` / `$REPLIT_ENVIRONMENT`.
   - Injects `synlynk` daemon service into `replit.nix` and `.replit` (`[processes.synlynk-daemon] run = "synlynk daemon start --port 27471"`), auto-starting on container boot.
   - Writes `.replitrules` priming Replit Agent with Synlynk's context snapshot and worktree discipline.
   - Dockable Vizor Extension: mounts `http://localhost:27472/onboarding` directly as a docked webview tab in the Replit workspace.
7. **Emergent (Autonomous Agent Platform / Cloud MicroVMs):**
   - Detects `.emergent/` or `$EMERGENT_ENV`.
   - Tool Provider: binds local daemon HTTP/SSE endpoints to Emergent's external MCP gateway (`.emergent/synlynk.json`).
   - Remote Worker Sandbox: implements `synlynk dispatch emergent` adapter, provisioning ephemeral cloud microVM sandboxes for compute-intensive refactors and fleet sweeps.
   - Bidirectional Webhooks: listens on `/api/emergent/callback` for asynchronous task status updates, test logs, and automated PR generation.
8. **Claude Desktop:** Exposes Model Context Protocol (MCP) server via `synlynk mcp` configured in `claude_desktop_config.json`.
9. **Terminal CLI:** Drops `CLAUDE.md`, `AGENTS.md`, and `GROK.md` for terminal harness users.

### B. Non-Destructive Fenced Instruction Generation
All generated instruction targets use standard non-destructive boundaries:
```markdown
<!-- synlynk:start version="0.21.0" tool="<target>" -->
# synlynk Instructions
... managed SOPs, Session Start protocols, and Worktree rules ...
<!-- synlynk:end -->
```
- **Safety Invariant:** 100% of user-authored custom instructions outside the fences are preserved intact.

### C. 1-Click GitHub App Role Provisioning via Vizor
- Launches browser to `http://localhost:27472/onboarding/roles`.
- Generates pre-filled GitHub App Manifests for both personal and organization accounts conforming to the deterministic length budget: `syn-{owner}-{slug}-{role}`.
- Handled roles: `pm`, `architect` (`arch`), `qa`, `dev`, `marketing` (`mktg`), `tpm`, `infra`.
- Captures OAuth callback loopback at `/auth/callback` or `/auth/sync`, automatically refreshing and minting installation tokens to `~/.synlynk/github_apps/` with `0o600` permissions.

---

## 4. Stage 2: The Greenfield Sandbox & The Behind-the-Curtain Tour

To build confidence without risking production code, Synlynk offers an immediate, zero-stakes starter experience.

### A. The Greenfield Micro-App ("syn-ping")
Synlynk creates a tiny, self-contained project (e.g. an endpoint health-check micro-app) and executes the **Unattended Milestone Loop** in under 3 minutes:
1. **Spec Creation:** Auto-generates a clean specification in `docs/superpowers/specs/`.
2. **TDD Implementation Plan:** Decomposes spec into a test-driven plan in `docs/superpowers/plans/`.
3. **Isolated Worktree Dispatch:** Dispatches an away worker to `.worktrees/feat+syn-ping` to implement the code and unit tests.
4. **Verification:** Executes unit tests locally; confirms 100% green output.
5. **PR & Review:** Creates a GitHub Pull Request, dispatches `@syn-qa[bot]` to review and approve, and squashes to main.

### B. The "Behind the Curtain" Artifact Tour
After the loop completes, Synlynk presents a visual tour of what happened behind the scenes:
1. **`state.db`:** The SQLite ledger storing stories, goals, and worker execution logs.
2. **`.synlynk/context.md`:** The runtime context snapshot keeping agents synchronized with workspace state.
3. **`project-docs/`:** The 4-doc governance discipline (`roadmap.md`, `todo.md`, `memory.md`, `devlogs/`).
4. **Git Worktrees:** Demonstrates how the developer's working directory remained untouched while the agent worked in isolation.

### C. The Vizor 3-View Canvas (`http://localhost:27472`)
Presents the three complementary mental models of the project:
1. **Physical View:** Hierarchical file tree heatmap showing component boundaries, file sizes, and test coverage density.
2. **Logical View (London Tube Map):** Metro lines represent data streams (e.g. Auth Flow, Video Pipeline, Billing Webhooks); stations represent database entities and message queues.
3. **Application View:** Wireframe cards of discovered routes and screens alongside cloud infrastructure topology (VPC, containers, databases).

---

## 5. Stage 3: "How Do YOU Want to Use It?" (Brownfield Adoption)

With intuition built, the developer transitions to their real existing codebase.

### A. Non-Destructive Safety Gates
1. **Git Dirty-Tree Check:** If uncommitted changes exist, prompts to commit, stash, or automatically isolates the onboarding run in a dedicated git worktree.
2. **Automatic Rollback Snapshot:** Creates a complete timestamped backup archive of `.synlynk/` before modifying any files, ensuring `synlynk rollback` is guaranteed.

### B. Three-Dimensional Automated Discovery Engine (`synlynk scan --deep`)
Runs in $< 45$ seconds without blocking on external LLM APIs:
1. **Dimension A: Domain & Business Space:**
   - Detects industry (Healthcare, Media AI, Fintech, DevTools), core functional capabilities, and compliance constraints (HIPAA, SOC2, GDPR).
2. **Dimension B: Physical Structure:**
   - Maps directory trees, frontend frameworks, backend microservices, worker queues, and CI/CD pipelines.
3. **Dimension C: Logical Architecture:**
   - Extracts ORM models, entity-relationship graphs, event brokers, and third-party SaaS integrations.

### C. Interactive "Confirm & Tweak" Chips
Rendered in Vizor (or TTY terminal):
- Facts are displayed as interactive chips: `[Domain: Media AI ✕]` `[Frontend: Next.js 14]` `[Backend: FastAPI]` `[DB: Postgres 16]`.
- Default zero-typing action: **`[Looks Perfect — Continue (Press Enter)]`**.
- Clicking any chip allows immediate inline editing without re-scanning.

### D. Gap Discovery $ightarrow$ GOVERNS Goal Generation
Scans the codebase for actionable opportunities:
1. Untested high-traffic API routes.
2. Missing CI/CD linting or type-checking pipelines.
3. Unindexed foreign keys or architectural circular dependencies.
- Generates a GOVERNS-compliant goal in `state.db`:
  `--outcome "Establish 100% test coverage for video ingestion" --criterion "pytest tests/test_ingest.py passes cleanly"`

### E. The First Real Win
- Dispatches a single additive, high-confidence task to an isolated worktree.
- Away worker writes tests, implements the feature, passes verification, and opens a verified Pull Request.
- Total time from launch to First Win: **$< 5$ minutes**.

---

## 6. Stages 4 & 5: Upgrade & Uninstall Lifecycles

### Stage 4: The Upgrade Journey (`synlynk upgrade`)
- **Schema Migration:** Automatically upgrades SQLite `state.db` through database migrations without data loss.
- **Instruction Refresh:** Re-fences and updates SOPs in `.cursorrules`, `GEMINI.md`, `CLAUDE.md`, etc., preserving all user custom content.
- **Fleet Re-Probe:** Probes installed harness versions and updates capability baselines.
- **Zero-Downtime Daemon Restart:** Restarts background daemon process safely without dropping port 27471 or creating orphaned processes.

### Stage 5: The Uninstall Journey (`synlynk uninstall`)
- **Service Teardown:** Unloads macOS `launchd` plist or Linux `systemd` user units, terminating daemon processes cleanly.
- **Shim & PATH Removal:** Removes `~/.synlynk/gh-shim/` and restores clean system environment.
- **Worktree Clean:** Audits and removes stale worktrees.
- **Zero Orphan Guarantee:** Removes all lockfiles, sockets, and temporary files, leaving the host system 100% clean.

---

## 7. Cross-Environment Testing Matrix

To guarantee reliability across diverse developer environments, Synlynk enforces a **4-Tier Testing Matrix**:

| Tier | Environment Target | Testing Mechanism | Verification & Assertion |
| :--- | :--- | :--- | :--- |
| **Tier 1: Syntax & Schema Attestation** | Cursor (`.mdc`), Windsurf, Copilot, Warp, Antigravity, Replit, Emergent | Automated Pytest in CI (`tests/test_instructions.py`, `tests/test_surface.py`, `tests/test_mcp.py`) | • Valid YAML frontmatter in `.cursor/rules/synlynk.mdc`<br>• Exact markdown syntax in `.windsurfrules`, `.replitrules`, and `.github/copilot-instructions.md`<br>• Valid YAML workflows in `.warp/workflows/synlynk.yaml`<br>• Valid JSON-RPC 2.0 schemas for MCP tool definitions across Cursor, Antigravity, Claude Desktop, and Emergent |
| **Tier 2: Prompt & Persona Emulation** | Claude, Gemini (Agy), GPT-4o, Replit Agent, Emergent Agents | Headless LLM Evaluation Harness (`tests/test_persona_emulation.py`) | • Feed generated rule files + `.synlynk/context.md` to models in CI.<br>• Assert model identifies as Home Conductor.<br>• Assert model enforces Worktree-First policy.<br>• Assert model records decisions to `project-docs/memory.md`. |
| **Tier 3: Browser UI Automated Testing** | Vizor Web UI (`localhost:27472`) | Playwright / Chrome DevTools MCP (`tests/test_viz_onboarding.py`) | • Zero-terminal onboarding flow.<br>• Chip click-and-edit interactions.<br>• Live SSE/WebSocket streaming.<br>• 1-Click GitHub App manifest submission. |
| **Tier 4: Golden Fixture Repositories** | 8 Pre-Configured Testbeds (`fixture-cursor`, `fixture-windsurf`, `fixture-vscode`, `fixture-warp`, `fixture-antigravity`, `fixture-replit`, `fixture-emergent`, `fixture-cli`) | `synlynk doctor --environment` in CI (`tests/test_environment_fixtures.py`) | • Test auto-detection of environment markers (`.cursor/`, `.vscode/`, `.windsurf/`, `~/.warp`, `~/.gemini`, `.replit`, `.emergent/`).<br>• Verify appropriate rules, workflows, and MCP configurations are injected non-destructively without collisions. |

---

## 8. Calibrated Implementation Workstreams for v0.21.0

| Workstream | Deliverable | Scope & Verification Gate | Harness Owner |
| :--- | :--- | :--- | :--- |
| **Workstream 1: Distribution & Cross-Environment Binding** | Installer & Universal Surface Generator | `install.sh`, `pipx`/`brew` packages, `.cursor/rules/`, `.windsurfrules`, `.github/copilot-instructions.md`, `.warp/workflows/`, Antigravity skill/MCP, Replit nix/rules, Emergent gateway, and MCP server. | Codex & Agy |
| **Workstream 2: Discovery & Greenfield Sandbox** | 3D AST Discovery & Starter Micro-App | Deterministic AST/manifest scanner (<10s), "syn-ping" sandbox generator, and "Confirm & Tweak" chips. | Codex & Agy |
| **Workstream 3: Vizor 3-View Canvas & Artifact Tour** | Local Visual Canvas (`localhost:27472`) | Physical file tree heatmap, logical tubemap, application screen cards, and "Behind the Curtain" tour. | Agy |
| **Workstream 4: GOVERNS First-Win & Lifecycles** | Goal Formulation & Upgrade/Uninstall | Automated gap discovery, GOVERNS goal creation, 1-click isolated worktree PR, `synlynk upgrade`, `synlynk uninstall`. | Claude & Codex |

---

## 9. Next Action

Proceed to updating the comprehensive Implementation Plan (`docs/superpowers/plans/2026-09-13-v0-21-0-ftue-onboarding-journey.md`) decomposing the 4 calibrated workstreams into sequential, verifiable TDD tasks.
