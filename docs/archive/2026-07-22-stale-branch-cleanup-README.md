# Archived docs from removed branches — 2026-07-22

These subdirectories preserve doc-only content from worktrees/branches deleted during the
2026-07-22 dispatch-branch and worktree housekeeping pass. None of this content was merged
into `main` before the branch was removed; it's kept here for reference rather than lost.

- `chore-sdlc-goal-design/` — BS-8 Goal Hierarchy + GOVERNS stage rollout design spec, two
  implementation plans, and three decision-log entries. The GOVERNS vocabulary and BS-8 goal
  hierarchy feature itself already shipped (PR #146); this is the design trail that predated it.
- `feat-vision-doc-consolidation/` — `synlynk-vision.md` and `docs/agent-workers/` (assessment,
  GitHub PM playbook, perf tracker). Never merged; branch was 663 commits behind main when removed.
- `feat-v0.4.0-autonomy-driver/` — a single blog post draft from the v0.4.0-era site. Branch's
  PR #27 was closed (not merged); 645 commits behind main when removed.
- `docs-rescue-fable-strategy-roadmap/`, `feat-bs19-t6t7-screens/` — a duplicate quickstart HTML
  export unique to these branches. Both branches' real feature content had already shipped
  through other PRs (#428 and the bs19 launch-screen work respectively) before removal.

Policy going forward: any worktree/branch removed as stale/superseded has its not-yet-merged
docs archived here first — see memory `feedback_archive_before_branch_removal`.
