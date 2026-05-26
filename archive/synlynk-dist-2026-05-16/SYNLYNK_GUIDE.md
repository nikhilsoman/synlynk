# synlynk AI Instructions

Apply these instructions to your AI agent (Global System Prompt, Gemini Custom Instructions, or Claude Project Instructions).

---

## 1. Context Identification & User Identity
Upon starting a session:
1. Check `/project-docs/.synlynk_config.json` for the mode (`single` vs `team`).
2. Identify the current user (`@username`) via `git config user.name` or environment variables.

## 2. Mandatory Maintenance
Keep the documents in `/project-docs` updated in every session:
- **roadmap.md**: Prioritized release order.
- **todo.md**: Task-level execution and assignments.
- **memory.md**: Decision log with attribution (e.g., `[@username]`).
- **costs.md**: Token/request tracking attributed to the current user.
- **devlog.md / devlogs/@username.md**: Maintain a chronological log of your specific interactions, outcomes, and blockers. In Team Mode, these are stored in `/project-docs/devlogs/`.

## 3. Session Start Protocol
Begin EVERY session with a structured status message:
- **Row 1:** Last completed task by YOU (e.g., "Refactored API [by @nikhil]").
- **Row 2:** Your next task from `todo.md`.
- **Row 3+ (Team Mode):** Summarize the last 1-2 entries from other collaborators' devlogs to provide cross-team visibility (e.g., "@sara: Finished UI layout", "@alex: Setup ScyllaDB cluster").

## 4. Conflict Resolution & Collaboration
- **Git Awareness:** Always `git pull` before modifying Pulse docs to avoid conflicts.
- **Decision Integrity:** If you notice a teammate's decision in `memory.md` contradicts your current path, pause and ask for clarification.
- **Proactive Logging:** If a session ends unexpectedly (e.g., crash, timeout), the next session should attempt to reconstruct and log the partial progress in your `devlog`.
