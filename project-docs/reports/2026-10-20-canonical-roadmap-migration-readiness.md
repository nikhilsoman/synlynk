# Canonical Roadmap Migration Readiness

Date: 2026-10-20

## Snapshot and Authority

The canonical state database was snapshotted before this assessment.

- Snapshot: `/private/tmp/synlynk-roadmap-reconciliation-backup/pre-canonical-migration-2026-10-20-20261020T031630Z.db`
- SHA-256: `b29f0a47533e68520d523b17b84d2d0780f8a02b685eb2607f41b8b4480f56c5`
- Integrity: `ok`
- Version-authority blocker: #1914 closed by PR #2462 (`a4375e1a`)
- Parent reconciliation epic: #2458

## Read-only Inventory

| Measure | Count |
| --- | ---: |
| Roadmap arcs | 46 |
| Roadmap phases | 76 |
| Stories | 2,013 |
| Active stories | 1,753 |
| Active goals | 35 |
| Active stories without a goal | 242 |
| Active stories without a GitHub ticket | 1,631 |
| Planned/active phases without a story | 35 |

The active story population is not a release backlog. It contains 202
`story-adhoc-*` records and a larger history of generated execution artifacts.
Those records must remain traceable, but they are not evidence that a delivery
item belongs in a named release.

## Existing Named-Release Collisions

| Existing arc | Current meaning | Canonical action |
| --- | --- | --- |
| `v0.25.2` | Daemon health activation; two completed phases | Re-scope as model-catalog recovery; retain completed daemon evidence under the v0.26 autonomy lineage. |
| `v0.26.0` | Universal Gateway provider integration | Re-scope as supervised execution and daemon reliability; defer Gateway work to v0.28.0. |
| `v0.27.0` | Meta Muse fleet GA | Re-scope as developer surfaces; retain valid surface work as candidate evidence. |
| `1.0.0`, `v1.0.0-preview`, `v1.0.0-rc1` | Competing Developer Preview paths | Supersede only after the v0.25.2--v0.29.0 release chain has linked, ticketed phases. |

## Delivery Disposition Rules

1. A delivery story must have one active goal, a GitHub issue, and one release
   phase before it is marked ready.
2. A phase may not be ready with a null story link.
3. `story-adhoc-*`, test probes, and calibration artifacts are preserved as
   evidence but quarantined from release readiness.
4. Historical open issue stories are reviewed individually: live product work
   is mapped by thematic adjacency; obsolete/replaced work is superseded or
   archived with its source reference intact.
5. No new Developer Preview date is created. Preview remains a decision gate
   after v0.29.0, not a roadmap release.

## Approved Canonical Sequence

| Release | Theme |
| --- | --- |
| v0.25.2 | Model catalog recovery |
| v0.25.3 | Trust contracts |
| v0.25.4 | Canonical state and release integrity |
| v0.26.0 | Supervised execution and daemon reliability |
| v0.26.1 | Workspace-agent operations |
| v0.26.2 | Evidence-gated supervised autonomy |
| v0.27.0 | Developer surfaces |
| v0.27.1 | Onboarding first win |
| v0.27.2 | Marketplace distribution |
| v0.28.0 | Swarms and Universal Gateway |
| v0.28.1 | Capability crawler, index, and GTM |
| v0.29.0 | Backlog consolidation |

## Next Controlled Mutation

Create one GitHub parent issue per canonical release, associate its named goals,
and create only ticketed delivery phases. The migration then supersedes the
three competing Preview arcs and quarantines non-delivery artifacts without
silently deleting their evidence.

## Migration Checkpoint

The release-epic and release-header portion of the next mutation is complete.

| Release | Parent issue |
| --- | --- |
| v0.25.2 | #2465 |
| v0.25.3 | #2466 |
| v0.25.4 | #2467 |
| v0.26.0 | #2468 |
| v0.26.1 | #2469 |
| v0.26.2 | #2470 |
| v0.27.0 | #2471 |
| v0.27.1 | #2472 |
| v0.27.2 | #2473 |
| v0.28.0 | #2474 |
| v0.28.1 | #2475 |
| v0.29.0 | #2476 |

All 12 headers are `planned` and explicitly non-ready. Their notes name the
parent issue and associated goals. This is intentionally not a release claim:
the next checkpoint links verified delivery stories to existing or newly
created GitHub tickets, then creates the release phases.

## Reconciliation Progress

The following evidence-preserving changes have been applied to canonical state.

- Five v0.25.2 phases now link model-recovery delivery stories to goals and
  tickets #2291 and #2447--#2450.
- Five model-catalog subtask stories with an encoded, existing issue reference
  are linked to #2291.
- 691 open `story-adhoc-*` implementation/review records are now archived as
  `artifact-quarantine-2026-10-20`; no evidence was deleted.
- 645 active `story-issue-<number>` records with an all-numeric suffix now
  carry that deterministic GitHub ticket number.
- `goal-51c4be3f` owns v0.29.0 backlog consolidation.

After the initial changes, the active ledger was 1,056 stories, with zero stories
without a goal and 281 still without a ticket. The final six ungoaled records
were explicit placeholders and were archived. The 31 issue-backed records
were assigned by theme to trust contracts, state integrity, daemon reliability,
onboarding, or v0.29 consolidation; the three R12 task records now point to
#1868 and v0.29.

The next evidence disposition was protected by snapshot
`pre-ticketless-evidence-disposition-2026-10-20-20261020T032740Z.db`
(SHA-256 `5feb648c7f6d2066c768eaa19078b19057837e1228d60903ff87957a974ca315`).
It archived 118 explicitly identifiable execution-evidence records--task,
review, merge, seeding, and plan-step prompts--as
`execution-evidence-archive-2026-10-20`. These remain in the ledger with their
source text and are not deleted. Seventeen genuine delivery stories whose
titles unambiguously contained `gh:#<number>` now link to that existing ticket.

The active ledger is now 939 stories, with zero stories without a goal and 147
without a ticket. That remaining cohort requires individual delivery versus
evidence classification. Opening a speculative issue for each record would
recreate the drift this reconciliation is intended to remove.
