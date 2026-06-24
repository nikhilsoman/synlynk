# Observations on Synlynk Bootstrap (RxCC.me Repo)

**Date:** 2026-06-01  
**Agent:** Gemini 2.5 Pro  
**Context:** Assessment of bootstrapping Synlynk standards in a mature, high-activity repository with existing GitHub Project V2 workflows.

---

## 1. Steps and Outcomes of a Bootstrap

If `synlynk bootstrap` were run in the `rxcc` repository, the following chronological actions would occur:

| Step | Action | Outcome |
| :--- | :--- | :--- |
| **1** | Create `/project-docs` directory. | Centralized home for project metadata. |
| **2** | Migrate `roadmap.md` to standard location. | Feature release and regional priorities are standardized. |
| **3** | Migrate `todo.md` to standard location. | Task execution and dependencies are moved into management. |
| **4** | Migrate/Rename `rxcc_memory.md` to `memory.md`. | Consolidated architectural decisions (India + US). |
| **5** | Migrate/Rename `rxcc_costs.md` to `costs.md`. | Standardized token and hierarchical cost tracking. |
| **6** | Migrate `devlog.md` to standard location. | Chronological record of engineering changes. |
| **7** | Activate Maintenance Mandate. | Agent begins autonomous upkeep of documentation. |

---

## 2. Changes to GEMINI.md

To align with the Synlynk structure, the following surgical updates would be made to the `GEMINI.md` instruction harness:

1.  **Path Internalization:** All file references (e.g., `todo.md`, `memory.md`) updated to use the `/project-docs/` prefix.
2.  **Maintenance Mandate:** Explicit instruction added making the agent responsible for updating `memory.md` and `devlog.md` before session close.
3.  **Session Start Protocol:** Mandatory 2-row status message (Last Task + Next Priority) formalized in the agent's prompt context.
4.  **Governance Reference:** A documentation index table added to the header to prevent agents from searching the root for source-of-truth files.

---

## 3. Engineering Standards

Synlynk bootstrap activates the following agentic engineering standards:

*   **The Attribution Standard:** Multi-layer tracing via `git config user.name` (Layer 1) and `Co-Authored-By` commit trailers (Layer 2).
*   **The Branching & Routing Convention:** Segmented prefixes (`type/agent/description`) allowing automated labelling and board movement.
*   **The Maintenance Mandate:** Documentation treated as code; `memory.md` becomes the supreme logic authority for agents.
*   **CI/CD Hygiene Rule:** Mandatory `paths:` filters for Actions to prevent unnecessary test runs on doc updates.
*   **Performance Protocol:** Standardized task evaluation using quality metrics and autonomy scores (0–2).

---

## 4. Multi-Agent Persistence

A single `synlynk bootstrap` run is sufficient for all agents (Claude, Gemini, Codex).
*   **Filesystem (Global):** The reorganization of `/project-docs` is a permanent change visible to any agent entering the repo.
*   **Instructions (Local):** The bootstrap process updates all detected agent instruction files (`CLAUDE.md`, `GEMINI.md`, and creates `CODEX.md` if missing) in one pass, ensuring every harness knows the new protocols.

---

## 5. Risks and Recommendations for Mature Repos

Running a standard bootstrap in a mature repo like `rxcc` at this stage carries specific risks:

### Identified Risks
1.  **Authority Conflict:** Standard Synlynk treats the local `todo.md` as the source of truth, while `rxcc` is governed by a human-led **GitHub Project V2** board. This creates a risk of "agentic drift."
2.  **Worktree Instability:** Moving core instruction files mid-sprint will cause immediate merge conflicts and "missing file" errors for agents currently working in other branches/worktrees.
3.  **Loss of Battle-Hardened Context:** Generic standardization might prune extremely specific instructions (e.g., GraphQL board mutations, SSE hijacking rules) recently built during intense production fixes.

### Final Recommendation: The "Hybrid" Approach
Don't run an automated bootstrap yet. Wait for a "clean" master branch, then perform a **surgical migration**:
1.  Move files to `/project-docs` manually.
2.  Update `GEMINI.md` to explicitly state that the **GitHub Project V2 Board** overrides the local `todo.md` for priority.
3.  Preserve and integrate existing GraphQL sync tooling into the new documentation structure.
