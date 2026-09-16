# 203 — Workspace identity W0: vocabulary before Apps

**Goal going in (previous work):** Control-plane trust on a *single* repo: jobs record real PRs, qa-gate+CI merge, non-author qa App, stories close, worktrees reap. Epic #1581 landed 22/23 children; #914 (workspace-level identities) stayed OPEN on purpose.

**Shift in this PR:** #914 is foundational for Teams, multi-repo products, and member-dispatch, but it is not one ticket. This PR does **not** implement multi-repo Apps. It records **W0** — locked vocabulary and authority — so later specs do not invent a second identity system.

**What shipped:** `docs/superpowers/specs/2026-09-16-workspace-identity-w0-vocabulary-design.md`. Product ≠ repo topology; agent **type** vs ephemeral **worker**; charter (constant) vs context pack (tpm-sharded, ephemeral); install surface vs work surface; canonical `qa` as sole train merger; specialists as `kind: qa` with their own App and charter; swarm = N workers × 1 type × N packs, not N Apps. No code.

**Brainstorm:** chat 2026-09-16 on #914; no companion HTML this slice (vocabulary, not topology diagrams).

**Toward autonomy:** Unattended merge already needs an honest GitHub actor. W0 says that actor is a **product-scoped type**, not a human and not a swarm of Apps. W1 is install/secrets.

**Also in this PR:** W1 install/secrets — PEMs live in `~/.synlynk/workspaces/<product>/github_apps/` now (approach A). PEM-less members (approach C) wait for Teams/W4.

**New goalpost:** Review W0+W1 on PR; next brainstorm is W5 (declaring a specialist type) or W6 (swarm write/blast radius), still no identity-init code until a plan.
