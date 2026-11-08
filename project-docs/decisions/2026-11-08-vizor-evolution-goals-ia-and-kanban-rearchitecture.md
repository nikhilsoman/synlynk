<!-- generated - source of truth is state.db -->
---
decision_id: dec-71b3e9a5
topic: "Vizor Evolution, Goals IA Re-architecture, and Kanban Board UX Stabilization"
date: 2026-11-08
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Review and resolve critical Vizor UX disconnects, specifically:
1. Root cause and remediation for the empty `◆ Goal` column on the GOVERNS Kanban board.
2. Architectural treatment of Goals as long-lived, continuous strategic objectives rather than disposable task cards.
3. Pruning dead/secondary links and consolidating Vizor around 3 high-impact surfaces: Executive Overview, GOVERNS Board (Goals & Stories), and Sentinel/Incident HUD.
4. Seamless integration with the autonomous GitHub workflow, routing card actions directly to GitHub Issues/PRs.

## Panel Inputs

### claude
[model=claude-3-7-sonnet; role=architect/pm]

**Analysis & Perspective: The Separation of Strategic Intent (Goals) and Tactical Delivery (Stories)**

The empirical bug where the `◆ Goal` column on the Kanban board is perpetually empty exposes an architectural conflation between **Goals** and **Stories**:
1. **The Bug:** In `synlynk/viz/board.py`, the Kanban board renders 7 stages (`['goal', 'open', 'visualize', 'execute', 'release', 'notify', 'sustain']`) but filters exclusively against the `stories` table (`c.governs_stage === st`). Stories represent bounded execution tasks; none of them ever have `governs_stage = 'goal'`. Meanwhile, the `goals` table is never queried for board cards.
2. **Goals Lifecycle:** Goals represent strategic north stars (e.g. *Autonomous GOVERNS Control Plane*, *Zero-Regression CI Gate*). They do not "finish and vanish". Instead, as milestones are achieved, operators raise the bar on the same goal or attach new execution phases.
3. **The Architectural Fix:** The GOVERNS Board must query both `goals` and `stories`. The `◆ Goal` column must render active Goal cards displaying their current outcome, target metrics, linked active stories count, and roadmap phase. Clicking a Goal card filters the remaining 6 columns (`Open → Sustain`) to show only the stories fulfilling that goal.

**Position:** Strongly approve. Re-anchoring the Kanban board around active goals restores the intended hierarchical delivery model.

### agy
[model=gemini-3.8-flash; role=frontend/onboarding]

**Analysis & Perspective: Streamlined Information Architecture and Friction Elimination**

From a user experience standpoint, the current Vizor dashboard suffers from cognitive bloat and broken pathways:
1. **Eliminate Dead & 404 Routes:** Secondary links (`/w/<slug>/journeys`, `/w/<slug>/logical`, and broken brainstorm links) distract from core observability. Vizor must adopt a clean 3-tab navigation hierarchy:
   - **Overview:** Fleet status, active budget burn rate, and top-level progress.
   - **GOVERNS Board:** The re-architected Kanban board showing Goals in column 1, and stories flowing through execution stages.
   - **Sentinel HUD:** Live alert triage, incident details, and one-click acknowledge/clear actions.
2. **Visual Differentiation for Goal Cards:** Goal cards in column 1 must look visually distinct from story cards—styled with an emerald accent border, a badge showing the number of linked tasks, and an expandable drawer showing historical completed phases.
3. **GitHub Direct Linking:** Every story card must render an explicit, clickable badge linking to its GitHub Issue (`#5166`) or PR (`#5165`), allowing the operator to jump instantly to the review surface without manual searches.

**Position:** Approve. This transforms Vizor from a noisy experimental canvas into a focused, production-grade control cockpit.

### codex
[model=codex-cli-0.163.0; role=core-systems/cli-plumbing]

**Analysis & Perspective: Data Layer Integrity & SQL Optimization**

The backend plumbing in `synlynk/board.py` requires straightforward, safe schema adjustments:
1. **Unified Query in `board_data()`:**
   - Update `board_data()` to query `goals`:
     ```sql
     SELECT goal_id, outcome, criterion, status, phase_id, kind 
     FROM goals WHERE status = 'active' ORDER BY created_at
     ```
   - Transform these into `goal` cards with `card_type: 'goal'` and `governs_stage: 'goal'`.
   - Retain stories as `card_type: 'story'` for stages `open` through `sustain`.
2. **Safe Schema Fallback:**
   - The `goals` table schema uses `outcome` (not `title`) for its textual description. In `board_data()`, alias `outcome AS title` so the frontend card renderer consumes a uniform `{id, title, status, ...}` payload.
3. **Zero-Lock Read Concurrency:**
   - Ensure `_open_product_db(read_only=True)` handles WAL read transactions without lock contention against the Vizor daemon or concurrent agent dispatches.

**Position:** Approve. The SQL refactoring is lightweight, hermetic, and solves the empty column bug immediately.

### grok
[model=grok-1.0.70; role=infra/capability-routing]

**Analysis & Perspective: Autonomous Alignment & Operator Observability**

For Nikhil's preferred operating model—where interaction is strictly high-level planning and approvals—the Vizor board must become the visual twin of GitHub:
1. **GitHub Sync Reflection:** When a GitHub Issue is closed by Nikhil, the background sweeper updates the story stage to `release`/`done` in `state.db`. The Vizor board must reflect this via its real-time SSE stream (`api/board`) without requiring full page reloads.
2. **Sentinel HUD Integration:** Alerts like `CONTEXT_BUILD_DEGRADED` or `VIZOR_DAEMON_CRASHLOOP` should not just sit in terminal logs—they must render high-visibility banner warnings at the top of the GOVERNS board with direct links to the tracking GitHub issue.
3. **Living Goals Swimlane View:** In addition to the column layout, support a toggle for "Swimlanes by Goal", where each active goal forms a horizontal track, making blocked and executing stories immediately evident.

**Position:** Approve. Aligns Vizor with autonomous GitHub-first governance.

---

## Synthesis & Consensus Decision

The panel unanimously approves the **Vizor Evolution & Goals IA Re-architecture**:
1. **Kanban Goal Column Refactor:** In `synlynk/board.py`, query `goals` alongside `stories` so active Goal records populate the `◆ Goal` column with outcome text, phase tags, and linked task counts.
2. **Goals as Living Strategic Anchors:** Treat Goals as persistent objectives that spawn child stories and roadmap phases over time, rather than disposable tickets.
3. **Navigation Consolidation:** Streamline Vizor to 3 primary navigation views (Overview, Board, Sentinel HUD) and prune dead secondary routes.
4. **GitHub Direct Linking:** Add direct clickable links to GitHub Issues and PRs on every board card.
