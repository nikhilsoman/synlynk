# synlynk.com Platform Vision: Accounts, Entitlements, Hosted Infrastructure

**Date:** 2026-10-23
**Status:** Approved
**Roadmap entry:** New GOVERNS goal, "synlynk.com platform migration" — long-term infrastructure vision superseding the current static GitHub Pages site

---

## Context

synlynk.com today is a static Eleventy (11ty) site — Nunjucks templates, vanilla CSS/JS, blog sourced from `docs/blog/`, built to `_site/`, deployed as a static artifact (GitHub Pages-style). There is no backend, no accounts, nothing stateful.

This spec defines the long-term vision for turning synlynk.com into the home for downloads, onboarding, accounts (individual/team/enterprise), entitlements/licensing, a hosted dev workstation, a hosted relay service, a swarm infrastructure provisioning gateway, and a user community — while identifying which existing synlynk surfaces this reuses and which are genuinely new.

This is a **vision document covering five sequential phases**, not an implementation plan for all of them at once. Each phase gets its own `docs/superpowers/specs/` design and `docs/superpowers/plans/` implementation plan when it's time to build it, per the project's Design → Plan → Build sequence. This document exists to lock the shared architecture (entity model, stack, cost philosophy) that every phase's later spec will build against, so phases don't drift into incompatible models.

### Why not decompose into separate PRDs now

The entity model (Account/Org/Workspace/Repo), the cost philosophy (ephemeral compute, pay-as-you-go datastores), and the AWS/Pulumi stack choice are shared dependencies across all five phases. Writing them once here, and letting each phase's own spec reference this document, avoids five independent documents re-deriving the same foundational decisions — and avoids the drift that would create.

---

## Entity / Account Model

### The problem with early proposals

An early draft proposed `Account → Workspace → Project`, treating "Workspace" and "Project" as new terms. Two things were wrong with this:

1. **"Workspace" already has a meaning in synlynk** — `~/.synlynk/workspaces/<name>/state.db` is today's named grouping of multiple repos (e.g. one person's `synlynk` workspace spans the `rxcc`, `cc-videoreframing`, `playblazer-ng`, and `synlynk` repos), with consolidated stories/leases/capability-ratings across all of them. Inventing a new word ("Project") for this same concept, and then nesting "Workspace" *underneath* it, would have created two names for one thing and buried the real multi-repo container under a layer of new vocabulary.
2. **"Entitlement" already has a meaning in synlynk** — `EntitlementTier` in `synlynk/models.py` is an enum describing which AI-model billing tier a given model call falls under (`INCLUDED_IN_BASE`, `SUBSCRIPTION_CAPPED`, `METERED_EXTRA_USAGE_ONLY`, `ZERO_COST_LOCAL`). This spec's "entitlements" (what a human account is allowed/paying to use) is a different concept entirely and must not collide with it in code or docs.

Resolution: adopt synlynk's existing meaning of **Workspace** as the multi-repo container, add one new tier (**Org**) between Account and Workspace for the cases that need delegated administration below the billing root, and use **Plan** / **License Tier** (not "Entitlement") for the new account-level concept — leaving `EntitlementTier` untouched as the unrelated, pre-existing per-model-billing concept.

### Hierarchy

```
Account  (Individual | Team | Enterprise — billing root, exactly one Owner)
  └─ Org          (optional grouping; collapses to an implicit default Org
  │                 for Individual/Team; becomes real department/business-unit
  │                 boundaries at Enterprise scale; holds delegated Admins)
  │    └─ Workspace    (named multi-repo container — matches today's
  │         │            ~/.synlynk/workspaces/<name>/state.db concept exactly)
  │         └─ Repo        (single git repository — leaf node)
  │
  └─ Application   (scoped API credential / integration grant — CLI install,
                     IDE plugin, Herdr pairing, future swarm-gateway client —
                     tied to the Account, optionally scoped to one Org/Workspace)
```

This is a **fixed four-level hierarchy** (Account → Org → Workspace → Repo), not arbitrary-depth nesting. Full AWS-Organizations-style unlimited nesting was considered and rejected: synlynk has zero enterprise customers today, and unlimited nesting would ship complexity nobody uses (YAGNI). If a future enterprise customer genuinely needs deeper nesting than Org, that is a new spec written against real demand, not speculative up-front design.

### Roles

- **Account Owner** — exactly one per Account, billing-liable, full control. Transferable, but never absent.
- **Org Admin** — delegated management rights scoped to one Org, grantable by the Account Owner without transferring billing ownership. This is the "Administrator" concept from the original ask.
- **Workspace Admin / Member** — delegated further within a Workspace; Workspace Admins can manage Repo membership and Workspace-level settings without Org-wide rights. This is the "Delegator" concept from the original ask: an Org Admin *delegates* a narrower slice of control to a Workspace Admin.
- A **Member** (Person) is **not owned by one Account** — the same human identity can hold membership (with independent roles) in multiple Accounts simultaneously. This is what makes freelancer/contractor and multi-employer scenarios work: a Person has one global identity and N account memberships, each with its own role.

### Portability and non-tree cases

Every resource (Account, Org, Workspace, Repo, Application) gets a **stable, globally unique ID independent of its current parent** — referenced via an ARN-style address, e.g.:

```
synlynk:account/<account-id>:org/<org-id>:workspace/<workspace-id>:repo/<repo-id>
```

Containment is stored as a **re-pointable parent edge** (a foreign key), not baked into the resource's identity. Moving a Workspace from a freelancer's Individual account into a client's Enterprise account — or an Org being re-parented during a company reorg — is a parent-edge update, not a resource recreation: the Workspace's state.db history, `cost_entries`, and `capability_ratings` carry over untouched.

**Repo-to-Workspace is not strictly one-to-one.** Each Repo has exactly one **canonical owning edge** (the Workspace where its authoritative state/history lives), plus optional **many-to-many attachment edges** (read/link-only) into other Workspaces. This covers the real case of a shared library repo used by two different product Workspaces without creating ambiguous ownership or duplicated history.

---

## Existing-Surface Mapping

| Existing synlynk surface | Role in this vision |
|---|---|
| `synlynk/relay_hub.py` + `docs/personal-hosted-relay.md` (personal hosted relay, device pairing via `devices.json`) | Becomes the connectivity/signaling layer underneath the multi-tenant **Hosted Relay** (Phase 3). The "Administrator" language already used for the host/key-holder role maps onto this spec's Org Admin for relay-scoped permissions. |
| `synlynk/team.py` (`synlynk join`, `mode: single\|team`, per-user devlogs) | Becomes Workspace/Repo member onboarding under the Account model. Today's binary `single\|team` config collapses into an Account-tier distinction (Individual accounts default to `single`-equivalent behavior; Team/Enterprise accounts default to `team`-equivalent). |
| `capability_ratings` / `cost_entries` tables (`synlynk/jobs.py`) | Directly reusable, no redesign — becomes the metering substrate for Hosted Workstation compute-seconds and Plan/License billing. This is the one piece of this vision with the least new engineering, since the data model already exists. |
| `.synlynk/vizor-workspace-map.json` + `synlynk/viz_views.py` (`workspace_view_nodes`/`workspace_view_edges`) | Vizor's Architect Map becomes the visualization layer for the Workspace entity's multi-repo relationship graph. Already conceptually aligned — no rename or redesign needed, just a new consumer (the account dashboard) of an existing projection. |
| `website/` (Eleventy static site on S3+CloudFront) | Stays exactly as-is for marketing/blog/docs (Phase 0 does not redesign the static content or its information architecture — see Named Release Policy's "retain existing IA" rule). Phase 0 adds a thin dynamic shell (login, account dashboard) alongside it. |
| `.synlynk/policy.json`, GOVERNS linkage gate, `merge_authority` | **Explicitly a separate axis — not folded into the human Account role system.** These govern agent-charter/dispatch behavior *within* a repo (pm/architect/tpm/dev/designer/qa/marketing/support), which is orthogonal to human Account/Org/Workspace permissions. Calling this out explicitly here so a future spec doesn't conflate "who can merge a PR" (GOVERNS/merge_authority) with "who can administer this Workspace" (this spec's roles). |
| `synlynk dispatch` + `HARNESS_CAPABILITY_BASELINES` (`synlynk/_constants.py`) | The execution engine that both Hosted Workstation (Phase 2) and the Swarm Gateway (Phase 4) ultimately invoke inside whatever compute node gets provisioned for them. Dispatch itself is unchanged by this vision; only *where it runs* changes. |

---

## Cost Philosophy

**No resource carries a sustained fixed hourly/monthly cost unless genuinely unavoidable.** This governs every phase's architecture:

- **Compute scales to zero.** Lambda for APIs/webhooks/auth; Fargate tasks (not EC2, not always-on ECS services) for workstations and dispatch jobs. Both bill per-second-running with zero cost at rest.
- **The core relational datastore (Accounts/Orgs/Workspaces/Repos/Plans/billing) is Aurora Serverless v2 with scale-to-zero ACU.** Chosen over DynamoDB on-demand because the domain is genuinely relational (hierarchy traversal, role/entitlement joins) and matches how synlynk already models state (SQLite tables, SQL queries) — easiest to reason about and to migrate existing data into later. Trade-off accepted: a short cold-start resume delay after scale-to-zero, versus DynamoDB's zero-fixed-cost-at-any-traffic-level with no cold start but a much harder single-table/adjacency-list modeling effort for this hierarchy. If a specific hot path (e.g. token/session validation) later needs DynamoDB-grade latency at scale, it can be added as a complementary cache in front of Aurora — not a reason to abandon Aurora for the domain model itself.
- **Persistent state for ephemeral compute lives in EFS**, not in the compute resource itself. A Fargate task for a Hosted Workstation or dispatch job mounts EFS on start — instantly, no snapshot-restore step — and the state survives independently of the task's lifecycle. Workstations idle for 30+ days have their EFS contents archived to S3/Glacier and reclaimed, restored on next connection.
- **Idle-shutdown is a first-class mechanism in every ephemeral-compute phase, not an afterthought.** Every workstation/dispatch task has an idle-timeout watcher (no active connection + no CPU activity for N minutes) that tears the Fargate task down. Billing meters actual compute-seconds (via the existing `cost_entries`/`capability_ratings` substrate) against the Account's Plan tier.
- **Avoid NAT Gateway's flat hourly fee** — Fargate tasks get public IPs directly where security allows, or routes go through VPC endpoints instead of a NAT Gateway.
- **The static site keeps its current near-zero-cost shape** (S3 storage pennies, CloudFront pay-per-request) — only the new dynamic shell (login/dashboard) adds Lambda + API Gateway, not an ALB or a 24×7 service.

---

## Required Stack

**AWS/Pulumi end-to-end**, consistent with every other project's existing conventions (ECS, CloudFront, S3, SQS, GitHub OIDC — see global `CLAUDE.md`), **built with explicit seams for future provider flexibility**:

- **Infrastructure-as-code:** Pulumi, as already standard. Cloud-provider-specific resources stay behind Pulumi's provider abstraction so a future GCP/Azure component (if ever needed) doesn't require re-architecting the rest.
- **Auth/billing sit behind thin internal interfaces**, not directly wired to AWS-native primitives throughout the domain logic. The domain model (Account/Org/Workspace/Repo/Role/Plan) is AWS-service-agnostic; only the adapter layer underneath knows it's talking to, say, Cognito or hand-rolled JWT issuance plus Stripe. This is what allows a managed identity provider (Clerk/Auth0/WorkOS) or GCP/Azure compute to be adopted later for a specific phase without rewriting the account model itself.
- **Relational store:** Aurora Serverless v2 (Postgres-compatible), scale-to-zero (see Cost Philosophy).
- **Compute:** Lambda (APIs, webhooks, auth flows) + Fargate (workstations, dispatch jobs).
- **Persistent ephemeral-compute state:** EFS, with S3/Glacier for long-dormant archival.
- **Static site hosting:** unchanged — S3 + CloudFront.
- **Billing:** Stripe (industry-standard, not AWS-native; sits behind the same billing interface seam as auth).

---

## Phased Architecture

### Phase 0 — Migrate off GitHub Pages

Move the existing static Eleventy site's hosting to S3 + CloudFront (prerequisite plumbing already standard elsewhere in this account's conventions), preserving the current information architecture, page structure, and layout exactly — this is a hosting migration, not a redesign. Add the thin dynamic shell (Lambda + API Gateway HTTP API, no ALB) that later phases' login/dashboard pages will sit behind. No account/auth functionality ships in this phase; it only makes the *next* phase possible without a second hosting migration.

### Phase 1 — Accounts / Entitlements

Implement the Account → Org → Workspace → Repo model on Aurora Serverless v2: schema, role/permission checks, Plan/License tiers, the ARN-style addressing and re-pointable parent edges described above, and Application-scoped API credentials. This phase has no infrastructure-provisioning component (no Fargate/EFS yet) — it is the identity/permission/billing substrate that every later phase gates against.

### Phase 2 — Hosted Workstation

A persistent, full cloud dev environment per Workspace (or per-Account for Individual tier): Fargate task running a container image with the dev environment (synlynk CLI, worktrees, harnesses, a web-based terminal/IDE such as code-server), EFS-mounted home directory, idle-timeout teardown, compute-second metering against the Account's Plan via `cost_entries`. This directly addresses the stated problem — a dev environment that doesn't depend on a laptop being up, and isn't subject to flaky remote-into-a-laptop access — by always connecting to the same stable cloud endpoint rather than tunneling into a personal machine.

This phase's Fargate+EFS provisioning engine is built once here and **reused, not rebuilt**, in Phase 4.

### Phase 3 — Hosted Relay (multi-tenant)

Extends today's personal hosted relay (`synlynk/relay_hub.py`) to multi-tenant: Account-scoped device/team pairing, and connectivity between a Hosted Workstation and any local-only resources (local models, local-only files/secrets) the user still wants reachable from their cloud workstation. Gated by the Account's Plan tier via Phase 1's entitlement model.

### Phase 4 — Swarm Infrastructure Provisioning Gateway

Generalizes Phase 2's Fargate+EFS provisioning primitive from "one long-lived interactive node" to "N short-lived, orchestrated ephemeral dispatch nodes" for swarm work — i.e., `synlynk dispatch` targets, provisioned on demand rather than assumed to already exist on someone's machine. Dispatch jobs are naturally even more amenable to ephemeral infrastructure than an interactive workstation (spin up, run one `synlynk dispatch` invocation, tear down), so this phase is comparatively lighter-weight once Phase 2's primitive exists.

### Phase 5 — User Community

Lowest technical dependency on the preceding phases; scoped in its own later spec when the prior four phases are shipped and there's a real account/user base to build a community around.

---

## Testing

- **Entity model (Phase 1):** unit tests for parent-edge re-pointing (Workspace moves Account→Account without losing child Repos or history), many-to-many Repo attachment (a Repo with one canonical owning Workspace and one attached Workspace resolves correctly in both), and role-check correctness at each of Owner/Org Admin/Workspace Admin/Member.
- **Cost/ephemeral infra (Phases 2 & 4):** integration test that a Fargate task's EFS-backed state survives an idle-timeout teardown and is correctly remounted by a freshly provisioned task; a test asserting idle-timeout actually fires (no connection + no CPU activity for N minutes → task torn down) rather than leaking a running task indefinitely.
- **Billing/metering:** test that compute-seconds recorded in `cost_entries` for a Hosted Workstation or dispatch job correctly resolve to a charge against the owning Account's Plan tier, including the case where a Workspace has been re-parented to a different Account mid-billing-period.
- **Static-site migration (Phase 0):** visual/structural diff between the pre- and post-migration site to confirm information architecture, page structure, and layout are unchanged — this phase should be invisible to end users except for the hosting change itself.
