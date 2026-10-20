# Roadmap Reconciliation Baseline

Date: 2026-10-20  
Parent epic: gh:#2458  
Canonical database: `~/.synlynk/workspaces/synlynk/state.db`  
Snapshot: `/private/tmp/synlynk-roadmap-reconciliation-backup/pre-reconciliation-2026-10-20-20261019T195534Z.db`  
SHA-256: `47492372d01efc2810ed27a163abf8172a4de3b8a28a02ebce0db4192bf4e3da`

## Inventory

| Metric | Count |
|---|---:|
| Total stories | 2,011 |
| Active stories | 1,752 |
| Active goals | 35 |
| Active stories without a goal | 242 |
| Active stories without a GitHub issue | 1,631 |
| Open phases without a linked story | 37 |

The active-story count is not an actionable product backlog. Of the 242
ungoaled active records, 202 are ad-hoc dispatch artifacts and 40 are other
unticketed records. They require disposition rather than automatic promotion
into a release.

## Competing Planned Arcs

The canonical DB currently holds all of the following planned arcs. The first
three are competing Developer Preview representations and must be superseded
under the approved design, while commercial v1.x remains long-horizon.

| Version | Current title | Target | Required disposition |
|---|---|---|---|
| `1.0.0` | Developer Preview Public Launch | 2026-10-31 | Supersede into v0.25.2--v0.27.2. |
| `v1.0.0-rc1` | 15-Minute First Win Field Trials & Zero-Risk Install | 2026-10-31 | Supersede into v0.27.1. |
| `v1.0.0-preview` | v1.0.0 Developer Preview | 2026-10-31 | Supersede into the canonical sequence. |
| `v0.25.2` | Daemon Health & Autonomous Pipeline Activation | none | Re-scope as model-catalog recovery; move daemon scope to v0.26.0. |
| `v0.26.0` | Universal Gateway: OpenRouter & Fal.ai | 2026-11-05 | Re-scope as supervised execution and daemon reliability. |
| `v0.27.0` | Core 5 Fleet: Meta Muse GA | 2026-11-19 | Re-scope as developer surfaces. |
| `v1.0.0` | GA: The Tokq Network & Commercial Launch | 2027-01-15 | Retain as long-horizon commercial arc. |

## Guardrails

- This baseline does not mutate the canonical database.
- The snapshot must be retained until reconciliation acceptance criteria pass.
- Subsequent migration records must link every old arc, phase, and story to a
  successor, explicit archive disposition, or later-goal owner.
