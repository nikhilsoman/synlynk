# Canonical Release Execution Schedule

**Effective date:** 2026-10-20  
**Authority:** `dec-f8835ba3`, roadmap parent #2458, and user approval on 2026-10-20  
**Status:** Active execution contract

## Operating rule

The dates below are hard release-gate dates. A release may be marked `shipped`
only when its defined evidence gate passes. Missing a gate does not silently
move downstream work: the release remains `planned`, its parent epic receives
a blocker rollup within one business day, and the revised date requires an
explicit decision comment on #2458.

Developer Preview is deliberately not dated. It remains a decision after the
v0.29.0 consolidation gate.

## Calendar and gates

| Release | Gate date | Delivery gate |
| --- | --- | --- |
| v0.25.2 | 2026-11-06 | All supported models resolve and dispatch correctly; cost and quota records reconcile to evidence. |
| v0.25.3 | 2026-11-20 | GitHub-write, approval, provenance, and cost-trust contracts fail closed and are auditable. |
| v0.25.4 | 2026-12-04 | One canonical state/projection path, DR evidence, release integrity, and review findings closed or explicitly deferred. |
| v0.26.0 | 2026-12-18 | Daemon restart, cancellation, recovery, scan containment, and replay journeys are evidence-tested. |
| v0.26.1 | 2027-01-08 | Workspace-agent charters, authority, SOPs, and operational ownership are signed off and exercised. |
| v0.26.2 | 2027-01-22 | Containment and approval controls pass before any autonomous execution expansion. |
| v0.27.0 | 2027-02-05 | VS Code client is publicly listed; OpenVSX publication, install, upgrade, and dispatch smoke tests pass. |
| v0.27.1 | 2027-02-19 | Five independent fresh-project journeys reach first verified dispatch in under 15 minutes. |
| v0.27.2 | 2027-03-05 | Marketplace/distribution installation, update, rollback, and support runbooks are verified. |
| v0.28.0 | 2027-03-26 | Bounded swarms and Universal Gateway run with lease, budget, containment, and evidence controls. |
| v0.28.1 | 2027-04-09 | Capability crawler/index publishes reproducible, privacy-safe, sample-floor-gated evidence and GTM surface. |
| v0.29.0 | 2027-04-23 | Every residual candidate is promoted, archived, or explicitly held; a human makes the Developer Preview decision. |

## Mandatory schedule controls

1. **2026-10-27 ticket lock:** every active delivery story selected for
   v0.25.2--v0.28.1 has one current GitHub delivery ticket and one release
   parent epic. Related legacy stories may share an outcome-sized ticket, but
   may not enter `ready` without that ticket.
2. **Every pickup:** revalidate the issue, comments, linked PRs, current
   `origin/main`, tests, source spec/plan, and the release gate. Start a new
   worktree from current `origin/main`; do not revive or rebase a dormant
   branch until its unique diff has been reviewed.
3. **Every Friday gate:** post a status, evidence links, changed ticket count,
   blockers, and next-week commitment on #2458.
4. **No auto-promotion:** a stale plan, an old green test, or a merged PR is
   not evidence that the release gate is complete.

## Proposed placement of the 94 ticketless candidate stories

This is a scheduling allocation, not an approval to implement every item. The
ticket-lock pass groups related IDs under outcome-sized delivery tickets and
archives candidates that fail the freshness check.

| Release | Candidates | Allocation |
| --- | ---: | --- |
| v0.25.2 | 7 | `story-9791a697`, `story-d84372cd`, `story-f336c1c5`, `harness-capability-registry-v2-plan-b-786`, `harness-rename-plan-a-786`, `story-5e2d2db2`, `story-bs8-probe` |
| v0.25.3 | 4 | `story-a7b5674c`, `story-7117bb01`, `story-74193239`, `story-a302384c` |
| v0.25.4 | 13 | `story-089c524e`, `story-08f5e280`, `story-1ade229f`, `story-514fde89`, `story-6e5795cf`, `story-78664ab2`, `story-8814681b`, `story-a5032986`, `story-b1f9d66b`, `story-d481115a`, `1218`, `story-057d4312`, `story-e4cd6595` |
| v0.26.0 | 6 | `story-a4442387`, `story-2e48a8c5`, `story-6f97c5a0`, `story-b4a90209`, `story-cb2c1d93`, `story-c04f64b1` |
| v0.26.1 | 5 | `story-0ad6c02b`, `story-272f0252`, `story-5ce5a997`, `story-bs8-consult`, `story-d59e1b3b` |
| v0.26.2 | 11 | `story-5dfe6b3f`, `story-620ca244`, `story-8faedf0a`, `story-b950515c`, `story-e0f0b014`, `story-f4171bdd`, `story-bs8-loop`, `governs-backlog-automation`, `story-bs8-meta-goals`, `story-bs8-split`, `story-ee4529d9` |
| v0.27.0 | 7 | `story-126d706f`, `story-43346243`, `story-8e8c952c`, `story-e528c886`, `story-18983f9f`, `story-3652dafe`, `story-3d52ea96` |
| v0.27.1 | 13 | `story-5019a85b`, `story-db3ce74c`, `story-0989ce14`, `story-615bc8f4`, `story-d5341d65`, `story-e5896237`, `story-e8c5d15f`, `ux1.0-regression-fix`, `story-4b288e24`, `story-9e2296f3`, `story-ca84004b`, `story-c822fd03`, `story-d4b40958` |
| v0.27.2 | 2 | `story-bs7-interop`, `story-fda756fd` |
| v0.28.0 | 5 | `story-9442caf8`, `story-c7064c40`, `story-2ebedf92`, `story-3aeb1c7a`, `story-ab6a0586` |
| v0.28.1 | 3 | `story-0ab760c5`, `story-33ab504a`, `story-c8e2b987` |
| v0.29.0 | 18 | `story-ffb0f3e6`, `story-1aab8f81`, `story-54d83487`, `story-6c5ff44e`, `story-b4b1167e`, `story-0127066f`, `story-2348ac34`, `story-541995f4`, `story-b75cb3e7`, `story-4fe0a8bf`, `story-5ef38956`, `story-f4dbf2ce`, `story-2161a277`, `story-565bf96f`, `story-631a6a86`, `story-e3a3170a`, `story-028d26d9`, `story-f6782d57` |

## Required additions to make the release promises truthful

- **v0.25.2:** live issue #1767 (explicit-model fallback) must be linked or
  superseded after reproduction; cost/accounting defects #481 and #510 need
  outcome tickets if still reproducible.
- **v0.25.4:** live DR validation #1686 and current architectural-review epic
  #2384 require canonical child stories.
- **v0.26.0:** live issues #2464 and #2477 are mandatory daemon-reliability
  tickets; #2463 is triaged here unless reproduction proves it is model-only.
- **v0.27.0:** #2103 covers the already-merged VS Code client and remaining
  marketplace/OpenVSX listing gate. It is not complete until installation and
  update smoke evidence exists.
- **v0.27.2:** add explicit marketplace package, signing, discovery, update,
  rollback, and support tickets; the two inherited stories are only enablers.
- **v0.28.1:** recreate a current child ticket under #2475 for the approved
  Capability Index/Crawler design, because its former parent #2431 is closed.

## Artifact and planning policy

Existing approved plans may be used only after the pickup freshness check.
Draft or cross-cutting work requires renewed brainstorm/spec/plan approval:
workspace-agent charters, GOVERNS autonomy, swarms/gateway, capability
crawler/index, hosted Teams/relay, and any scope that materially changes the
VS Code distribution promise. Bounded bugs and regressions use a refreshed
mini-spec/plan where needed, rather than a new broad brainstorm.
