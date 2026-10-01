<!-- generated - source of truth is state.db -->
---
decision_id: dec-bf3f40d7
topic: "Phase 2 Topology Discovery & Workspace Modeling: Distinguishing Multi-Project Directories (e.g. /dev), Monorepos, Polyrepo Application Groups (frontend + backend + api in 1 workspace), and Standalone Repos; Discovery Clustering Heuristics and User Confirmation/Modification Flow"
date: 2026-10-01
panel: [claude, codex, agy]
status: approved
---

## Topic
Phase 2 Topology Discovery & Workspace Modeling: Distinguishing Multi-Project Directories (e.g. /dev), Monorepos, Polyrepo Application Groups (frontend + backend + api in 1 workspace), and Standalone Repos; Discovery Clustering Heuristics and User Confirmation/Modification Flow

## Panel Inputs

### claude
[model=sonnet; version=2.1.284 (Claude Code)]

**Analysis**

The four shapes differ on two axes: how many independent VCS roots exist, and whether those roots are *coupled*. A container directory like `~/dev` has many roots and no coupling. A monorepo has one root and many internal packages. A polyrepo app group has many roots and real coupling. A standalone repo has one root and no coupling. Directory layout alone can't separate the "container" case from the "polyrepo group" case, so coupling evidence has to do that work.

**Discovery heuristics, in order of reliability**

1. **Hard boundaries.** Each `.git` root is a candidate repo. Nested `.git` roots are the base unit.
2. **Monorepo signals.** `pnpm-workspace.yaml`, `package.json` workspaces, `go.work`, Cargo `[workspace]`, `nx.json`, `turbo.json`, and a `packages/` or `apps/` layout. These mean one repo, with subprojects that are not separate repos.
3. **Coupling evidence across repos.** This is the strongest cluster signal:
   - Shared docker-compose files or env var names.
   - A frontend's API base URL or OpenAPI client that points at a sibling.
   - Shared package names in manifests.
   - Matching git remote org and name prefixes (`acme-web`, `acme-api`).
   - Commit-time correlation.
4. **Weak signals.** Name affinity, a common parent, and similar mtime. These only break ties.

Score each pairwise edge, then cluster by connected components above a threshold. Repos with no strong edges stay standalone. A parent with many unconnected repos gets classified as a container and is never auto-merged into one workspace.

**Failure asymmetry**

A false merge puts unrelated repos under one workspace. That leaks context and misroutes dispatch, which is the worse error. A false split only costs the user a manual merge. So the heuristics should default conservative: split unless the evidence is strong.

**Confirmation flow**

Discovery proposes and never commits. Show a tree: proposed workspaces, their member repos, the evidence for each grouping ("api URL in web/.env → api"), and a confidence label. The user can accept all, merge, split, move a repo, rename, or mark a repo "ignore". Persist the confirmed topology, plus the user's overrides, as the source of truth. Re-discovery on later runs should only surface *diffs* (new repo appeared, an edge strengthened) and must never overwrite a user decision. Non-interactive mode should write the proposal to a pending file and apply nothing.

**Position**

I recommend evidence-scored clustering with a conservative default (split on weak evidence), and a mandatory confirm-before-persist step that shows evidence per grouping. Treat monorepos as a single repo with subprojects, and treat container directories like `/dev` as non-workspaces. User overrides are authoritative and persisted, and re-discovery proposes diffs without silently changing confirmed topology.

### codex
[model=default; version=codex-cli 0.155.1]

Phase 2 should model workspace topology as a confidence-ranked hypothesis rather than a binary classification. The same directory can contain unrelated repositories, a monorepo, or a deliberately grouped polyrepo application, and filesystem structure alone cannot reliably establish intent.

Discovery should begin with repository boundaries: Git roots, nested repositories, worktrees, package manifests, build files, dependency references, shared configuration, and common deployment metadata. Candidate clusters can then be scored using signals such as:

- shared parent directory and naming conventions;
- cross-repository references, local package dependencies, API contracts, or shared environment configuration;
- synchronized commit activity, branches, remotes, and issue/project metadata;
- common scripts, CI workflows, Docker Compose files, and development commands;
- language/framework compatibility and directory roles such as `frontend`, `backend`, or `api`.

The system should distinguish three concepts: physical containment, logical application grouping, and repository ownership. A `/dev` directory should normally be treated as a multi-project directory unless evidence supports a cluster. A monorepo should remain one project with internal packages. A frontend/backend/API set may be proposed as an application group even when each repository has a different remote. Standalone repositories should remain independent by default.

Every inferred relationship should include an explanation and confidence level. The confirmation flow should present detected projects and proposed groups visually, allowing users to merge, split, rename, reclassify, exclude, or designate a primary repository. User corrections must be persisted as explicit workspace metadata and should override future heuristic results unless the underlying topology materially changes. The system should also support “not now” decisions without forcing premature organization.

My recommendation is to adopt a conservative, evidence-based clustering model with reversible user confirmation as a required phase boundary. Preserve repository independence by default, propose polyrepo groups only when multiple signals agree, and treat user-defined groupings as authoritative. This balances discovery usefulness with the risk of silently imposing an incorrect project structure.

### agy
[model=default; version=1.2.14]

[model=default; version=1.2.14]

**Last completed task:** `docs: checkpoint Specs 1–3 completion, archive finished stories, and update cost log (#1893)`  
**Next task from `todo.md`:** `BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform]`

---

**Analysis**  
Topology discovery is the foundational data contract for synlynk’s multi-workspace runtime. Inaccurate clustering causes catastrophic dispatch leakage, corrupted worktree boundaries, and cross-repo context pollution. Discovery must unambiguously distinguish four core archetypes:
1. **Multi-Project Directories (e.g., `/dev`)**: Unorchestrated parent folders containing independent projects; must never be grouped into a single workspace.
2. **Monorepos**: A single `.git` root containing declared workspace manifests (`pnpm-workspace.yaml`, `Cargo.toml [workspace]`, `go.work`, `turbo.json`).
3. **Polyrepo Application Groups**: Multiple `.git` roots tied by explicit root orchestration (shared `docker-compose.yml`, root reverse-proxy configs, or mutual env/service bindings).
4. **Standalone Repos**: A single `.git` root with no monorepo package manifests or sibling coupling.

To discover these safely without hallucinating relationships, we should implement a deterministic, read-only 3-pass heuristic:
- **Pass 1 (VCS Boundaries):** Walk directory trees to depth *N* to index `.git` boundaries, worktrees, and submodules.
- **Pass 2 (Monorepo Signatures):** Inspect `.git` roots for native workspace manifests. If present, classify as Monorepo.
- **Pass 3 (Affinity Scoring):** For sibling `.git` roots, calculate an affinity score based on shared orchestration manifests, local inter-service references, and GitHub repository organization parity. If affinity falls below a strict threshold or cross-orchestration is absent, siblings default to separate Standalone Repos under an unmanaged container directory.

**Confirmation and Modification Flow**  
Discovery must be strictly non-mutating. The engine emits a candidate graph proposal (`topology.candidate.json`) consumed by the headless onboarding state machine and rendered across both TUI and Vizor surfaces. Users can split polyrepos, merge siblings, promote standalone repos, or customize workspace slugs before any configuration is written to `state.db`.

**Position & Recommendation**  
I **support approval** of the Phase 2 Topology Discovery architecture with a strict **fail-isolated default**: uncoupled sibling repos must remain independent Standalone Repos rather than speculative polyrepo groups. Discovery must execute as a read-only 3-pass heuristic engine paired with a mandatory, dual-surface confirmation gate prior to state persistence.

## Synthesis
All three panelists agree on the core shape, so this is mostly a merge of details.

**Where they agree**
- **Four archetypes:** a container directory like `~/dev` (many unrelated repos), a monorepo (one `.git` root with internal packages), a polyrepo application group (multiple roots with real coupling), and a standalone repo.
- **Filesystem layout can't tell a container from a polyrepo group.** Coupling evidence has to separate them.
- **A false merge is worse than a false split.** A false merge leaks context and misroutes dispatch. A false split costs one manual merge. Heuristics therefore default to split.
- **Discovery proposes and never persists.** The user confirms, and confirmed topology is authoritative.

**Merged design**

*Discovery* is a read-only, deterministic pass pipeline:
1. **Boundaries.** Index `.git` roots, worktrees and submodules to a bounded depth.
2. **Monorepo signatures.** Look for `pnpm-workspace.yaml`, package.json workspaces, `go.work`, Cargo `[workspace]`, `turbo.json` and `nx.json`. A root with any of these is one project with subpackages and is never split.
3. **Pairwise affinity scoring between sibling roots.**
   - *Strong signals:* a shared compose or orchestration file, cross-repo URL or OpenAPI client references, shared package names, shared env contracts.
   - *Medium signals:* matching remote org and name prefix, CI references, correlated commits.
   - *Weak signals:* a common parent, naming, mtime. These only break ties.
4. **Clustering.** Group connected components above a threshold. A group needs at least one strong edge, or several agreeing medium edges. Weak signals alone never group repos.
5. **Container rule.** A parent with many unconnected repos is a non-workspace container. Its repos stay standalone.

*Model.* Keep three concepts separate, as Codex proposed: physical containment, logical application grouping, and repo ownership. A group may have a designated primary repo. Every inferred edge carries its evidence and a confidence label.

*Confirmation flow:*
- Discovery emits `topology.candidate.json` and applies nothing to `state.db`.
- The TUI and Vizor render the same proposal as a tree of workspaces, member repos, per-grouping evidence and confidence.
- The user can accept, merge, split, move a repo, rename or re-slug, set the primary repo, ignore a repo, or choose "not now".
- Confirmed topology and overrides persist as explicit workspace metadata.
- Re-discovery only surfaces diffs: a new repo, a strengthened edge, or a material topology change. It never overwrites a user decision.
- Non-interactive mode writes the pending proposal and applies nothing.

Decision: Adopt conservative, evidence-scored topology discovery as a read-only multi-pass engine (VCS boundaries, then monorepo signatures, then pairwise affinity clustering). Treat monorepos as single projects and container directories like `/dev` as non-workspaces. Group polyrepos only on at least one strong coupling signal or several agreeing medium signals. Every inference carries evidence and a confidence label. Persist nothing until the user confirms in a mandatory gate on both TUI and Vizor, with merge, split, rename, primary, ignore and "not now" actions. Confirmed topology and user overrides are authoritative, re-discovery only proposes diffs, and non-interactive runs write a pending candidate file and apply nothing.

## Decision
Decision: Adopt conservative, evidence-scored topology discovery as a read-only multi-pass engine (VCS boundaries, then monorepo signatures, then pairwise affinity clustering). Treat monorepos as single projects and container directories like `/dev` as non-workspaces. Group polyrepos only on at least one strong coupling signal or several agreeing medium signals. Every inference carries evidence and a confidence label. Persist nothing until the user confirms in a mandatory gate on both TUI and Vizor, with merge, split, rename, primary, ignore and "not now" actions. Confirmed topology and user overrides are authoritative, re-discovery only proposes diffs, and non-interactive runs write a pending candidate file and apply nothing.

> Signatures: see 2026-10-01-phase-2-topology-discovery-workspace-mod.json
