# 203 — Workspace identity W0: vocabulary before Apps

**Goal going in (previous work):** Control-plane trust on a *single* repo: jobs record real PRs, qa-gate+CI merge, non-author qa App, stories close, worktrees reap. Epic #1581 landed 22/23 children; #914 (workspace-level identities) stayed OPEN on purpose.

**Shift in this PR:** #914 is foundational for Teams, multi-repo products, and member-dispatch, but it is not one ticket. This PR does **not** implement multi-repo Apps, `synlynk type`, or Vizor organigram code. It records **W0** vocabulary, **W1** PEM home, **W5** type store, and **W8** packs/onboard/connectors.

**What shipped:** W0, W1, W5, W8 specs. Product ≠ repo; type vs worker; product-store Apps and types; two-step create then mint; three industry packs (`software-product`, `studio`, `agency`); Vizor organigram onboard with App minting; `connector` kind + creds + `gateway` slot (no vendor). No code.

**Brainstorm:** chat 2026-09-16 on #914; no companion HTML this slice (vocabulary, not topology diagrams).

**Toward autonomy:** Unattended merge already needs an honest GitHub actor. W0 says that actor is a **product-scoped type**, not a human and not a swarm of Apps. W1 is install/secrets.

**Also in this PR:** W1 install/secrets — PEMs live in `~/.synlynk/workspaces/<product>/github_apps/` now (approach A). PEM-less members (approach C) wait for Teams/W4.

**New goalpost:** Review W0+W1+W5+W8 on PR #1647; next brainstorm is **W6** (policy, blast radius, swarm review vs merge, connector firewall engine). Still no identity-init / `type create` / Vizor organigram code until a plan. #914 stays OPEN.
