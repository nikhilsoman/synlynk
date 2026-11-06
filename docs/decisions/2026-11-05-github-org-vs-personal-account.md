# GitHub org vs. personal account for synlynk

**Decision: stay on the personal account (`nikhilsoman/synlynk`) for now.** Revisit at a defined trigger, not on a timer.

## Context

synlynk currently lives under Nikhil's personal GitHub account. The question was
whether to move it to a dedicated GitHub organization, as has already been done
for other company/product projects (e.g. `playblazer` org for pbmr, per the
Pulumi org-isolation policy in global CLAUDE.md).

## Reasons an org would help

- **Identity separation** — commits/PRs/issues stop mixing with unrelated personal
  repos in profile/activity feeds.
- **Billing/seat isolation** — org-level billing for Actions minutes, GitHub Apps,
  Copilot seats, etc., separate from personal subscriptions.
- **Fits synlynk's own multi-identity design** — synlynk is already building
  role-scoped GitHub Apps per agent (Agy/Grok/Codex/Claude). Orgs allow org-level
  App installs, teams, and permission scoping instead of per-repo installs under
  a personal account.
- **Future collaborators/investors** — signals institutional presence if synlynk
  ever takes contributors or a legal entity.
- **Transferability** — org-to-org or ownership handoff is cleaner than personal
  repo transfer.

## Reasons to hold off

- **Migration friction** — a transfer breaks all clone URLs, forces updates to
  every local worktree, CI secrets, and any OIDC trust policies scoped to
  `repo:nikhilsoman/synlynk:*`.
- **GitHub App re-auth** — existing role-scoped GitHub Apps
  (`.synlynk/github_apps/`) are installed at the repo/personal-account level;
  moving orgs means re-provisioning every installation and re-testing the
  dispatch/review pipeline, which has had multiple hard-won fixes (see
  `daemon-persistence-gap-1228`, `worktree-github-apps-gap` in project memory).
- **Operational risk mid-flight** — active worktrees and in-flight dispatch jobs
  reference the current remote; a transfer during active development risks
  silently breaking jobs.
- **No immediate functional need** — single-maintainer project, no teams, no
  seat/billing requirement today.
- **Agent-identity model is still mid-reassessment** — the default agent role
  split was suspended 2026-10-04 for empirical review. Migrating GitHub App
  installs now risks redoing the work if that model's shape changes again.

## Trigger conditions to revisit

1. A human collaborator or co-founder joins with their own GitHub account, or
2. The agent-identity/GitHub-Apps work matures to where org-level team scoping
   would measurably simplify it versus per-repo installs, or
3. synlynk needs org-level billing/seats (paid Actions minutes, Copilot, etc.)
   separate from the personal account.

Until one of these is true, the migration cost outweighs the benefit.
