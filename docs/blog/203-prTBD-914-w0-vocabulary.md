# 203 — Workspace identity W0: vocabulary before Apps

**Goal going in (previous work):** Control-plane trust on a *single* repo: jobs record real PRs, qa-gate+CI merge, non-author qa App, stories close, worktrees reap. Epic #1581 landed 22/23 children; #914 (workspace-level identities) stayed OPEN on purpose.

**Shift in this PR:** #914 is foundational for Teams, multi-repo products, and member-dispatch, but it is not one ticket. This PR does **not** implement Apps, join/relay, Vizor hosting, or the `state.db` move. It records the **full W0–W9** identity program as specs.

**What shipped:** W0–W9 design files (vocabulary, PEMs, work graph, board, members, types, policy, runtime, packs, hosted Vizor). No code.

**Brainstorm:** chat 2026-09-16 on #914; no companion HTML this slice (vocabulary, not topology diagrams).

**Toward autonomy:** Unattended merge already needs an honest GitHub actor. W0 says that actor is a **product-scoped type**, not a human and not a swarm of Apps. W1 is install/secrets.

**Also in this PR:** W1 install/secrets — PEMs live in `~/.synlynk/workspaces/<product>/github_apps/` now (approach A). PEM-less members (approach C) wait for Teams/W4.

**New goalpost:** Review W0–W9 on PR #1647. Next is **writing-plans** (or qa merge of this docs PR) on explicit go — no identity-init code until a plan. #914 stays OPEN until scoped implementation lands.
