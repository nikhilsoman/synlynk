# Capability Matrix Taxonomy Reference

This document serves as the canonical reference for the four mandatory per-task tag dimensions of the `synlynk` Capability Matrix. Every task created or rated within the workspace must be tagged along these four dimensions. This ensures that the agent routing scheduler (`_best_agent_for_story()`) can precisely match tasks to the best-suited agent based on historical capability ratings.

For details on the enforcement logic and schema, see the [Capability Matrix Hardening Design Spec](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-538b20f9/docs/superpowers/specs/2026-07-11-capability-matrix-hardening-design.md).

---

## 1. Business Domain (`org_domain`)

The `org_domain` dimension classifies tasks according to their functional business area. It consists of **9 values**:

| Value | Scope & Codebase Mapping |
| :--- | :--- |
| `personalization` | Tailored experiences, user-specific recommendations, and behavior-adaptive settings (e.g., configuring agent-specific execution overrides in `.agents/<agent>.json`). |
| `monetization` | Billing models, pricing tiers, token/request cost attribution, and the Tokq marketplace integration layers (as tracked via `costs` table and `gas tank` configurations). |
| `adtech` | Advertisement delivery, targeting, campaign management, and ad-related metrics or telemetry. |
| `workflow` | Process automation, task scheduling, Trio orchestrator flow, worktree isolation, and coordination loops. |
| `analytics` | Performance monitoring, telemetry aggregation, and dashboard statistics (e.g., `synlynk status`, `.synlynk/telemetry.json`, and the Live Job Observatory). |
| `growth` | User acquisition, marketing campaigns, and viral referral loops. This directly ties to the market-facing scope of the **Notify** stage (release notes, public blog posts, changelogs) as defined in the `chore/sdlc-goal-design` branch's `docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md` spec. |
| `content` | CMS integrations, documentation assets, blog copy templates, and documentation hosting (e.g., `docs/blog/` stubs created during `release`). |
| `platform` | Core OS layer runtime, SQLite database engine, local daemons, sandbox path permission verification, and multi-repo workspace configurations. |
| `identity` | User authentication, session management, and cryptographic keys (e.g., machine-level Ed25519 identity keypairs stored in `~/.synlynk/identity.key`). |

---

## 2. Competency (`discipline`)

The `discipline` dimension denotes the technical competency area of a task. It replaces the old, unstructured `engg_domain` field with **9 values**. 

Along with the discipline, tasks are annotated with a list of `stack_tags` representing the specific technologies or languages used. The following table documents the canonical disciplines and the recommended convention values for `stack_tags` (derived from imports, shebangs, and package manifests in this repository):

| Discipline | Description | Recommended `stack_tags` (Codebase Conventions) |
| :--- | :--- | :--- |
| `architecture` | High-level system design, schema definitions, and inter-component protocols. | `python`, `json`, `mermaid`, `markdown`, `trio-protocol` |
| `frontend` | User interface structure, CSS styles, web components, and TUI layouts. | `html`, `css`, `javascript`, `nunjucks`, `eleventy`, `ansi-tui`, `svg` |
| `backend` | Core logic, command-line arguments, system services, and routing. | `python`, `argparse`, `subprocess`, `socketserver` |
| `data` | Database migrations, queries, and structured text/log parsers. | `sqlite`, `sql`, `regex`, `json` |
| `ml` | Large language model configuration, system instructions, and prompts. | `gemini-api`, `anthropic-api`, `grok-api`, `prompt-engineering` |
| `testing` | Unit tests, black-box E2E test suites, and regression testing. | `pytest`, `pytest-mock`, `bash`, `python` |
| `security` | Cryptographic signature validation, file path sandboxing, and permissions. | `ed25519`, `ssh-keygen`, `cryptography`, `posix-permissions` |
| `devops` | Build system files, packaging, dependencies, and environment setup. | `setuptools`, `pipx`, `bash`, `github-actions`, `install-sh` |
| `docs` | Codebase documentation, specs, roadmaps, and devlogs. | `markdown`, `html`, `changelog-md` |

---

## 3. Role Persona (`role`)

The `role` dimension classifies tasks according to the required persona. This prevents the static capabilities of an agent from being conflated with the runtime requirements of a specific task. It consists of **6 values**, aligned with the personas speced across the agent design documents:

*   **`architect`**: Handles high-level system layout, protocol definitions, and technical spec authoring. (See the Architect role scope in the [TPM Agent Design Spec](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-538b20f9/docs/superpowers/specs/2026-06-23-tpm-agent-design.md)).
*   **`dev`**: Implements feature sets, writes source code, modifies existing logic, and creates PRs.
*   **`pm`**: Product manager role responsible for product intent, goals, success criteria, and user/market feedback loops (Goal and Notify stages).
*   **`tpm`**: Technical Project Manager role coordinating parallel agent waves, resolving task dependency graphs, and managing agent quotas. (See the [TPM Agent Design Spec](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-538b20f9/docs/superpowers/specs/2026-06-23-tpm-agent-design.md)).
*   **`qa`**: Quality Assurance, corresponding to the "Verifier" persona responsible for running test suites, verifying compliance tags (such as `VERIFY_SKIP`), and investigating telemetry drops. (See the [Support Engineer Agent Design Spec](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-538b20f9/docs/superpowers/specs/2026-06-21-support-engineer-agent-design.md)).
*   **`designer`**: Visual/UX designer responsible for visual interface mapping, SVG graphs, and interactive TUI overlays (such as Vizor views or HUD layouts).

---

## 4. Execution Stage (`stage`)

The `stage` dimension represents the current lifecycle stage of the task. It is governed by the **7-stage GOVERNS model** (which renames `CYCLES` in [synlynk/hud.py](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-538b20f9/synlynk/hud.py) to goal, open, visualize, execute, release, notify, sustain):

| Stage | Command/Context | Description |
| :--- | :--- | :--- |
| `goal` | `synlynk goal` | Product intent, outcomes, success criteria, and deadlines (100% human-driven). |
| `open` | `synlynk open` | Kickoff of a work session or branch scoped to a story. The human configures the scope and the agent drafts the approach. |
| `visualize` | `synlynk viz` | Mapping architecture and file structures before building. The agent proposes the structure, and the human refines it. |
| `execute` | `synlynk exec` / `dispatch` | The build itself (~90% agent-driven implementation, verified by human tech-lead approval). |
| `release` | `synlynk release` | Pipeline execution including version bumps, automated test checks, and tagging. |
| `notify` | Outbound Comms | Redefined to cover market-facing announcements, blog drafts, and changelog updates to drive adoption. |
| `sustain` | `synlynk status` / `doctor` | Long-term operational continuity, including **Sustain/Maintain** (upkeep, dependency bumps) and **Sustain/Alert** (sentinel checks, doctor runs, pager alerts). |

---

## Tagging a Task

When creating a task (story) using the command line, all four dimensions must be filled in using their respective enum values. 

### Worked Example

Below is a worked example showing how to create a story representing the implementation of a new user session authentication API endpoint:

```bash
synlynk story create \
  --title "feat: implement user session authentication endpoint" \
  --org identity \
  --discipline backend \
  --role dev \
  --stage execute
```

*   **`--title`**: A conventional commit-style description of the task.
*   **`--org`**: Maps to the `identity` business domain.
*   **`--discipline`**: Maps to the `backend` technical competency (will be validated against the 9-value discipline enum).
*   **`--role`**: Declares that the task requires the developer (`dev`) persona.
*   **`--stage`**: Specifies that the task is ready for building and execution (`execute`).
