# Maintainer Full Autonomy — Design Spec

**Date:** 2026-11-24
**Status:** Draft — pending user review
**Author:** Claude (PM session)

## 1. Problem Statement

TPM has a real autonomous wake cycle (`run_tpm_wake_cycle()` in `synlynk/tpm_sweep.py`) that is scheduled, acts on its findings, and surfaces them through Vizor's Roadmap Studio. Maintainer has the equivalent *data* (`triage_sentinel_alerts()`, `run_backlog_burndown_sweep()`, `cmd_maintainer_sweep()` in `synlynk/maintainer.py`) but no equivalent *loop*: `_run_maintainer_triage_pass()` in `synlynk/scheduler.py` calls `triage_sentinel_alerts()` and discards the return value. Maintainer's other two capabilities are CLI-only, with no scheduling, no UI, and no cross-surface notification path.

This spec brings Maintainer to parity with TPM's autonomy model, and in doing so, establishes a **reference pattern** other roles (beyond TPM/Maintainer) can reuse: a generic settings-driven action registry, a generic Agent Studio operations panel, a generalized multi-source proposal-review surface, and — new in this revision — a configurable domain-vocabulary layer so the pattern holds across synlynk-managed workspaces outside this repo's own software-engineering domain (e.g. rxcc, vdowrx, Hitchcock).

## 2. Current State (verified against code)

- `synlynk/maintainer.py::cluster_open_issues()` — keyword/label clustering into fixed buckets (`backend`, `frontend`, `cli`, `docs`, `sentinel`, `testing`, `other`), hardcoded to this repo's software vocabulary.
- `synlynk/maintainer.py::run_backlog_burndown_sweep()` — auto-closes remediated issues (via commit-reference matching and a hardcoded `_REMEDIATION_TOPICS` tuple), stages a `sprint_staged` dict once a cluster reaches a minimum volume.
- `synlynk/maintainer.py::cmd_maintainer_sweep()` — mesh/contract-drift detection via `ensure_graph_for_head()` (`synlynk/scan.py`) and `write_traversal_cache()` (`synlynk/graph_cache.py`), consuming `build_federated_mesh`/`contract_drift` from `synlynk/mesh.py` across `_workspace_repos()`.
- `synlynk/scan.py` — explicitly documented as "language-agnostic" but in practice restricted to `_SOURCE_SUFFIXES = {.py, .js, .ts, .tsx, .go, .rs, .java, .rb, .php}`, with AST-level analysis Python-only. This is a **code graph**, not a general file graph.
- `synlynk/docgraph.py` (added ~2 weeks ago, v0.32.1) — a separate **document graph**: indexes markdown specs/plans/decisions/devlogs/etc. into `.synlynk/docgraph.json`, with `reverse_code_index`, `reverse_doc_index`, per-node `code_references` and `issues_and_prs`. Its `classify_doc_type()` buckets key off synlynk's own structural conventions (`docs/superpowers/specs/`, `project-docs/decisions/`, ...), not this repo's domain. Currently has exactly one consumer (`scan.py`'s refresh path feeding the sub-3k context packager) — no proximal-selection or clustering logic uses it yet.
- `synlynk/viz/roles.py::generate_roles_html()` — generic per-role card renderer (charter edit + onboarding wizard). The onboarding wizard's Function-family dropdown already lists `maintainer — platform`. No operational/action content exists for any role here.
- `synlynk/viz/onboarding.py::roles_info` — the GitHub App identity provisioning list. Contains `pm`, `tpm`, `qa`, `dev`, `architect`, `marketing`, `infra`. **`maintainer` is missing.**
- `synlynk/viz/overview.py::generate_overview_html()` — no role-specific widgets of any kind exist today (confirmed: no TPM widget either).
- `synlynk/viz/roadmap_studio.py` — the only existing per-role approval UI, hardcoded to TPM's `release_proposal` tickets. Cards keyed by `story_id`/`data-ticket-id`; JS actions `dropStory`/`reorderStories`/`pinStory` post to `api/roadmap_studio/drop`/`/reorder`/`/pin`.
- `synlynk/fencing.py` — `register_hint_contributor()`/`render_task_fence()`: the CLI/TUI inline-hint mechanism shown after every `synlynk exec` invocation.
- `synlynk/notifiers/slack.py` — the only external notification channel today.
- No webhook/slash-command listener infrastructure exists for any role (`find -iname "*webhook*" -o -iname "*listener*"` returns nothing).

## 3. Goals

1. Give Maintainer a real wake cycle, scheduled the same way TPM's is, with dry-run-by-default / explicit-promotion semantics.
2. Make every sub-action (sentinel triage, backlog burndown, mesh sweep, and any future addition) independently toggleable and filterable via settings, without code changes.
3. Surface Maintainer's state in Agent Studio (full operations panel), the Overview page (condensed widget), the generalized Proposal Studio (approval queue), and the CLI/TUI fence-hint system.
4. Fix the onboarding gap (`maintainer` missing from `viz/onboarding.py::roles_info`).
5. Add a GitHub Actions trigger for the wake cycle, with a documented (not yet built) extension point for a future slash-command dispatcher.
6. Ensure every mechanism introduced generalizes to a synlynk-managed workspace in a different industry/domain than this repo (rxcc, vdowrx, Hitchcock) — concretely, by moving domain-specific vocabulary out of code and into per-workspace config, and by using the newer doc-graph as a fallback proximity signal where the code-graph has no signal.
7. Establish this as the **reference implementation** future roles follow for the same autonomy journey — every new component (settings registry, operations panel, proposal-source generalization) must be built generically, not Maintainer-specific.

## 4. Non-Goals

- Building the slash-command dispatcher itself (extension point only).
- Building actual rxcc/vdowrx/Hitchcock domain packs (schema + loader + one worked example only; see §9).
- Changing TPM's own wake cycle or Roadmap Studio's existing TPM behavior beyond the minimum needed to generalize it to multiple proposal sources.
- Any new external (non-Slack) notification channel.

## 5. Architecture

### 5.1 `run_maintainer_wake_cycle()` (new, `synlynk/maintainer.py`)

Mirrors `run_tpm_wake_cycle()`'s shape. Runs three registered actions in sequence:

1. **`sentinel_triage`** — existing `triage_sentinel_alerts()` ranking, now acted on: CRITICAL/high-severity groups stage a standalone proposal immediately (bypassing the minimum-cluster-volume rule below); everything else accumulates toward the normal cluster minimum.
2. **`backlog_burndown`** — existing `run_backlog_burndown_sweep()`, with `dry_run` read from settings (default `True`).
3. **`mesh_sweep`** — existing `cmd_maintainer_sweep(refresh_graph=True)`, contract-drift findings staged the same way.

Called from `_run_maintainer_triage_pass()` in `synlynk/scheduler.py` on the existing cadence, replacing today's discarded call.

### 5.2 `MaintainerActionRegistry` (new, `synlynk/maintainer_registry.py`)

A small registration object, not a Maintainer-specific concept — any future autonomous action (for Maintainer or another role adopting this pattern) registers:

```python
register_action(
    name="sentinel_triage",
    default_config={"enabled": True, "mode": "dry_run"},
    filter_schema={"exclude_codes": "list[str]"},
    run_fn=triage_sentinel_alerts_and_act,
)
```

Registration automatically produces: a settings entry under `.synlynk/config.json`'s `maintainer_autonomy` block, a toggle/filter card in the Role Operations Panel (§5.4), and wake-cycle participation. Example resulting config:

```json
"maintainer_autonomy": {
  "sentinel_triage": {"enabled": true, "mode": "dry_run", "exclude_codes": ["TOKEN_CIRCUIT_BREAKER_TRIPPED"]},
  "backlog_burndown": {"enabled": true, "mode": "dry_run", "exclude_labels": ["do-not-autosweep"]},
  "mesh_sweep": {"enabled": true, "mode": "dry_run"}
}
```

`mode` is `dry_run` (findings staged, visible, no side effects) or `promote` (real side effects — GH issue close, graph rebuild — execute).

### 5.3 Proposal data shape (consumed by Proposal Studio, §5.5)

Every staged proposal, regardless of source:

```json
{
  "proposal_id": "...",
  "source": "maintainer:backlog_burndown",
  "title": "...",
  "severity": "critical|high|normal",
  "stories": [{"story_id": "...", "github_issue": 1234}]
}
```

`github_issue` is enforced non-null per story at staging time — if a finding has no existing GH issue, Maintainer opens one (via the `qa`-role write path) before staging, so Proposal Studio never shows an orphaned story.

### 5.4 Role Operations Panel (new, `synlynk/viz/role_ops_panel.py`)

A reusable `generate_role_ops_panel_html(role_slug, data)`, consumed from two places:

- **Agent Studio** (`viz/roles.py`) — a new "Operations" `<details>` sibling to the existing "Edit Charter" section on Maintainer's role card: per-action enabled toggle, mode selector, scope-filter editor, last-run timestamp/outcome, pending-proposal count linking to Proposal Studio.
- **Overview page** (`viz/overview.py`) — a condensed widget: three action-state badges (Dry-run / Promoted / Off) + pending-proposal count + last-wake-cycle timestamp, linking out to the full panel.

The panel is written generically (keyed by `role_slug` + the registry's registered actions for that role) so a future role adopting this pattern gets the same UI for free.

### 5.5 Proposal Studio (generalized `viz/roadmap_studio.py`)

- Renamed function `generate_proposal_studio_html` (old route kept as an alias — no broken bookmarks).
- Cards render a `source` badge (`tpm` / `maintainer:backlog_burndown` / `maintainer:mesh_sweep` / `maintainer:sentinel_triage`).
- Every `story_id` renders its linked `github_issue` as a clickable link (enforced non-null per §5.3).
- **Proximal selection** decides whether a new finding joins an existing open proposal or starts a new one — see §5.6 for the mechanism, which is the piece most affected by the portability requirement (§6).
- Severity-flagged (`critical`/`high`) proposals render in a "Needs attention now" lane above the normal volume-clustered lane, and bypass the minimum-cluster-volume threshold entirely.
- Existing drag/drop/pin actions (`api/roadmap_studio/drop` etc.) work unchanged — they only need `story_id`.

### 5.6 Proximal selection (dual-graph, with keyword fallback)

Replaces `cluster_open_issues()`'s pure keyword matching with a three-tier resolution order, checked in this sequence for each candidate finding:

1. **Code-graph proximity** — via `ensure_graph_for_head()`/`write_traversal_cache()` (`synlynk/scan.py`, `synlynk/graph_cache.py`): if the candidate's touched files are graph-adjacent (under a distance threshold) to an existing open proposal's files, join it. Meaningful only where the workspace has enough `_SOURCE_SUFFIXES` coverage for the graph to carry signal.
2. **Doc-graph proximity** — via `docgraph.py`'s `reverse_code_index`/`reverse_doc_index`: if the candidate shares a referencing doc, or shares `issues_and_prs`/`code_references`, with an existing proposal's stories, join it. This graph's classification keys off synlynk's own structural conventions (every `synlynk init`-created workspace has `project-docs/decisions/` etc.), so it carries signal even in a workspace with little or no source code.
3. **Keyword clustering** (fallback, today's mechanism) — now reading its taxonomy from `.synlynk/maintainer_taxonomy.json` (§6) instead of a hardcoded Python dict.

If no tier produces a match and the finding isn't critical/high-severity, it accumulates toward the minimum-cluster-volume threshold under its keyword bucket, same as today.

### 5.7 Notifications & fence comms

- Vizor dashboard surfaces are always updated (Role Operations Panel, Overview widget, Proposal Studio) — this is the default, always-on channel.
- A per-action `notify_slack: bool` setting (default `false`) gates a push through the existing `synlynk/notifiers/slack.py` path on promote (and always for a CRITICAL standalone proposal, regardless of mode).
- A Maintainer hint contributor registers with `synlynk/fencing.py::register_hint_contributor()` at import time, surfacing a one-line hint after any `synlynk exec`/`synlynk maintainer ...` invocation when a pending proposal or dry-run finding exists — the terminal-side notification surface for people not looking at Vizor.

### 5.8 CLI / GitHub trigger surface

- New CLI subcommand: `synlynk maintainer wake` (wraps `run_maintainer_wake_cycle()`), following the existing `tpm wake`/`pm wake` pattern in `synlynk/cli.py`.
- New GitHub Actions workflow (`.github/workflows/maintainer-sweep.yml`): `workflow_dispatch` + nightly cron, calling `synlynk maintainer wake`.
- New top-level settings flag `slash_command_dispatch: false` — documented as "not yet implemented, flip when the generic GH slash-command dispatcher ships." No dispatcher is built in this spec.

### 5.9 Onboarding fix

Add `maintainer` to `synlynk/viz/onboarding.py::roles_info`:

```python
("maintainer", "Platform Maintainer", "claude", "Sentinel-alert triage, backlog burndown, and mesh/contract-drift sweeps."),
```

Bundled here because the Role Operations Panel (§5.4) is meaningless if the role was never onboardable with its own GitHub identity.

## 6. Portability: Domain Vocabulary as Config, Not Code

Two pieces of Maintainer's current logic are hardcoded to this repo's software-engineering domain and will not generalize to rxcc/vdowrx/Hitchcock as-is:

1. `cluster_open_issues()`'s keyword taxonomy (`backend`/`frontend`/`cli`/`docs`/`sentinel`/`testing`, keywords like `sqlite`, `css`, `pytest`).
2. `_REMEDIATION_TOPICS = ("invariant 1", "circuit breaker", "daemon supervision")` — synlynk-engineering-specific fix-matching vocabulary.

Both move out of `maintainer.py` into a new per-workspace config file, `.synlynk/maintainer_taxonomy.json`:

```json
{
  "cluster_keywords": {
    "backend": ["sqlite", "api", "server"],
    "frontend": ["css", "html", "vizor"],
    "cli": ["argparse", "subcommand"],
    "docs": ["readme", "docstring"],
    "sentinel": ["alert", "circuit breaker"],
    "testing": ["pytest", "fixture"]
  },
  "remediation_topics": ["invariant 1", "circuit breaker", "daemon supervision"]
}
```

synlynk's own repo ships this file pre-populated with its current lists (no behavior change for this repo). A fresh `synlynk init` elsewhere scaffolds an empty/minimal version; burndown's `#N`/`fixes #N` commit-reference matching (already domain-agnostic) still works with zero configuration, so a new workspace isn't crippled on day one — it just won't catch topic-based matches until someone fills this in. The Role Operations Panel (§5.4) gains a "Cluster taxonomy" editor (cluster name → keyword chips) so this is user-editable without touching code.

`mesh_sweep`'s value is inherently proportional to how much of the workspace is actual source code; for a content/doc-heavy workspace it will have near-zero signal. The Role Operations Panel shows a "low signal" hint next to `mesh_sweep` when `ensure_graph_for_head()` indexes under a small file-count threshold, so a user on such a workspace knows to leave it disabled rather than wondering why it never finds anything.

## 7. Domain Pack Extension Point (schema + loader; packs themselves are future work)

To support the stated future plan of shipping industry/domain-specific resource packs that populate the taxonomy or doc-graph classifier, this spec adds the extension point without building the packs:

- New schema, `.synlynk/domain_pack.json`:

```json
{
  "pack_name": "synlynk-default",
  "cluster_keywords": { "...": ["..."] },
  "remediation_topics": ["..."],
  "doc_type_extensions": {
    "compliance_doc": ["hipaa", "compliance/"],
    "shot_list": ["shotlist", "shot-list"]
  }
}
```

- New loader `load_domain_pack()` (`synlynk/maintainer_taxonomy.py`), called at wake-cycle start: merges `cluster_keywords`/`remediation_topics` into `.synlynk/maintainer_taxonomy.json`'s runtime values, and merges `doc_type_extensions` into `docgraph.py::classify_doc_type()`'s classification (checked after the built-in structural buckets, before falling through to `general_doc`).
- v1 ships exactly one worked pack: synlynk's own current software-engineering lists, expressed in this format as the "default" pack — this is what proves the mechanism works, without requiring fabricated specifics about rxcc/vdowrx/Hitchcock's actual current vocabulary.
- Building the rxcc/vdowrx/Hitchcock-specific packs themselves is out of scope for this spec (§4) — flagged as the natural next step once this mechanism lands.

## 8. Testing Approach

- Unit tests per registered action: dry-run vs. promote branching, settings-registry defaults, filter application (`exclude_codes`/`exclude_labels`).
- Unit tests for proximal selection: code-graph match, doc-graph match (using a fixture `DocGraph` with overlapping `reverse_code_index` entries), keyword fallback, and the "non-code-dominant workspace" fixture (mostly non-`_SOURCE_SUFFIXES` files) proving graceful degradation to doc-graph/keyword tiers without error.
- Unit test for severity-override bypass of the minimum-cluster-volume threshold.
- Unit test for `load_domain_pack()` merge behavior (pack values layer over repo defaults, `doc_type_extensions` checked before `general_doc` fallback).
- Integration test for the full wake cycle against a fixture `sentinel.md` + fixture open-issues list, asserting staged proposals have non-null `github_issue` per story.
- Vizor rendering tests: Role Operations Panel renders all three registered actions with correct toggle/mode state; Overview widget renders condensed badges; Proposal Studio renders multi-source cards with correct `source` badges and the "Needs attention now" lane for severity-flagged proposals.
- CLI test for `synlynk maintainer wake` subcommand wiring.

## 9. Future Work (explicitly out of scope here)

- The slash-command dispatcher (GH comment/slash-command → role trigger) for any role, not just Maintainer.
- Actual rxcc/vdowrx/Hitchcock domain packs.
- Applying this same reference pattern (action registry, operations panel, proposal-source generalization) to roles beyond TPM/Maintainer.
