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
