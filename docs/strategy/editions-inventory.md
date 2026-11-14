# Synlynk Full Module & Capability Inventory

**Generated:** 2026-11-14  
**Governing Specification:** [`docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md`](file:///Users/nikhilsoman/dev/synlynk/docs/superpowers/specs/2026-11-13-synlynk-editions-boundary-and-opt-in-gating-design.md)  
**Structured Source of Truth:** [`docs/strategy/editions-inventory.json`](file:///Users/nikhilsoman/dev/synlynk/docs/strategy/editions-inventory.json)

---

## 1. Classification Methodology

Synlynk capabilities and modules are categorized strictly by **who bears the marginal cost of their existence**:

1. **Core:** No external hosting cost. Runs 100% locally on the operator's machine or self-hosted hardware.
2. **Opt-in:** The operator bears the cost via their own accounts, API keys, or self-managed servers (e.g., personal GitHub App, custom VPS relay).
3. **Hosted:** Synlynk bears the cloud infrastructure, bandwidth, storage, or operational cost. These are provided as cloud bolt-ons or enterprise services.

---

## 2. Core Capabilities

Core capabilities form the foundation of Synlynk's local substrate. They are fully functional in all editions (**Core**, **Personal**, **Team**, **Enterprise**) with zero artificial walls or DRM restrictions:

| Capability | Scope / Purpose | Marginal Cost Bearer |
|---|---|---|
| `capability_tracking` | Self-measurement of model quality, calibration, and dispatch history | Local runtime (SQLite `state.db`) |
| `local_pilot` | Autonomous single-operator orchestration and Wingman driver | Local operator CPU / CLI |
| `quota_tracking` | Token, request, and cost limits against user's API credentials | Local runtime accounting |
| `swarm_local` | Parallel agent dispatch across local Git worktrees | Local Git & process execution |
| `governs_engine` | Intent-to-PR invariants, policy checks, and database contracts | Local SQLite WAL transactions |
| `context_packager` | Sub-3k token AST minimization and graph pruning | Local offline Tree-sitter / AST engine |
| `doctor_diagnostics` | Installation health checks and compliance probes (TC-1..TC-9) | Local system inspection |
| `finops_dual_ledger` | Dual-ledger token rate and cost provenance tracking | Local database storage |
| `spec_linter` | Constitutional spec contract and frontmatter enforcement | Local regex / markdown parsing |
| `autonomous_tpm_daemon` | Background wake cycles, heartbeat, and story triage | Local double-fork daemon process |
| `organogram_canvas` | Visual organogram SVG tree rendering and archetype viewer | Offline HTML5/SVG canvas |
| `domain_packs` | Industry archetypes, tool baselines, and charter validation | Local packaged JSON templates |
| `greenfield_genesis` | Project initialization and guided progressive fleet assembly | Local CLI interactive prompts |

---

## 3. Opt-in Capabilities

Opt-in capabilities integrate with external systems, but the cost and credentials are provided entirely by the user:

| Capability | Scope / Purpose | Marginal Cost Bearer |
|---|---|---|
| `github_app_auth` | Attributed non-author reviews and automated PR merges | User-provided GitHub App / Tokens |
| `relay_local` | Peer-to-peer relay broker between distributed local instances | User-hosted network infrastructure |
| `vizor_local` | Interactive web dashboard and live graph explorer on `:33333` | User-run local web server |
| `mcp_server_local` | Model Context Protocol servers and dynamic sidecar tools | User-configured local subprocesses |

---

## 4. Hosted Capabilities

Hosted capabilities require cloud infrastructure managed and operated by Synlynk. These are either bundled into commercial editions (**Team**, **Enterprise**) or purchased as unbundled à la carte add-ons:

| Capability | Min Edition | Hosted Key | Scope / Status |
|---|---|---|---|
| `hosted_relay` | Personal (Add-on) / Team (Bundled) | `hosted_relay` | Centralized relay broker eliminating manual NAT traversal / port forwarding. |
| `audit_retention` | Enterprise | `audit_retention` | Immutable, long-term compliance log storage and export. Blocked on Platform Vision Phase 1. |
| `sso` | Enterprise | `sso` | Enterprise SAML / OIDC single sign-on. Blocked on Platform Vision Phase 1. |
| `rbac` | Enterprise | `rbac` | Fine-grained role-based access control. Blocked on Platform Vision Phase 1. |
| `data_residency` | Enterprise | `data_residency` | Guaranteed regional data storage compliance. Blocked on Platform Vision Phase 1. |
| `swarm_cloud_provisioning` | Any (Add-on) | `swarm_cloud_provisioning` | Elastic cloud compute orchestration for fleet swarms (Phase 4). |
