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

### 5.2 `AutonomousActionRegistry` (new, `synlynk/maintainer_registry.py`, role-aware despite the module path)

**Revised per DECIDE panel 2026-11-24 (Claude + Codex defect #1):** the registry is not Maintainer-shaped. It takes a `role_slug` at registration time, assigns each action a stable `action_id` (`f"{role_slug}:{name}"`, not a bare `name` — this is the persistence key in `.synlynk/config.json` and the only id the Role Operations Panel, §5.4, is allowed to key off), and `filter_schema` is a typed field-spec list, not a free-form dict, because §5.4's panel renders form controls directly from it:

```python
register_action(
    role_slug="maintainer",
    name="sentinel_triage",
    default_config={"enabled": True, "mode": "dry_run"},
    filter_schema=[
        FieldSpec(name="exclude_codes", type="list[str]", default=[], label="Exclude alert codes"),
    ],
    run_fn=triage_sentinel_alerts_and_act,
)
```

`FieldSpec` (`name`, `type` — one of `str`/`bool`/`list[str]`/`int`, `default`, `label`) is validated at registration time; an unknown `type` raises at import, not at render time. `registered_actions(role_slug=None)` lists specs filtered by role (or all, for the panel's cross-role views). `get_action_config(action_id)` reads/validates against the owning action's `default_config` shape, rejecting unknown keys.

Registration automatically produces: a settings entry under `.synlynk/config.json`'s `<role_slug>_autonomy` block (`maintainer_autonomy` for this spec's three actions), a toggle/filter card in the Role Operations Panel (§5.4), and wake-cycle participation. Example resulting config:

```json
"maintainer_autonomy": {
  "sentinel_triage": {"enabled": true, "mode": "dry_run", "exclude_codes": ["TOKEN_CIRCUIT_BREAKER_TRIPPED"]},
  "backlog_burndown": {"enabled": true, "mode": "dry_run", "exclude_labels": ["do-not-autosweep"]},
  "mesh_sweep": {"enabled": true, "mode": "dry_run"}
}
```

`mode` is `dry_run` or `promote` — see §5.3a for what each actually does; "no side effects in dry-run" is a stronger guarantee than originally described, and is now the thing being fixed.

### 5.3 Proposal data shape — shared schema, not `release_proposal`-specific (revised per DECIDE panel defect #4)

Every staged proposal, regardless of source, is a `Proposal` record in a new shared table/schema (`synlynk/proposal_schema.py` or equivalent — exact module decided at plan time), not a reuse of TPM's `release_proposal` rows with Maintainer fields bolted on:

```json
{
  "proposal_id": "...",
  "source": "maintainer:backlog_burndown",
  "title": "...",
  "severity": "critical|high|normal",
  "lifecycle": "staged|approved|held|dropped",
  "approval": {"approved_by": null, "approved_at": null},
  "stories": [{"story_id": "...", "github_issue": 1234}]
}
```

`source` is namespaced `<role_slug>:<action_name>` (`tpm:release_proposal`, `maintainer:backlog_burndown`, ...) so Proposal Studio (§5.5) can query/filter across sources without a source-specific code path. TPM's existing `release_proposal` rows are read through an adapter that maps them into this shape — TPM's own write path is unchanged (§4 non-goal), only the read side generalizes. `github_issue` is enforced non-null per story at staging time — if a finding has no existing GH issue, Maintainer opens one (via the `qa`-role write path) before staging, so Proposal Studio never shows an orphaned story. Opening that issue is itself a promotion-boundary action — see §5.3a.

### 5.3a Dry-run vs. promotion boundary (new section, DECIDE panel defect #2)

The original spec described `dry_run` as side-effect-free, but staging a proposal that needs a GitHub issue (§5.3) opens one even in `dry_run` mode — that is a real side effect under a label promising none. This section is the fix:

- **Local staging** (writing a `Proposal` row, computing clusters/findings, running proximal selection) is side-effect-free in both `dry_run` and `promote` mode. It never touches GitHub.
- **Promotion** — opening a GitHub issue for an orphaned story, closing an issue on backlog-burndown remediation, or any other external write — happens **only** in `promote` mode, and only through these guards, all enforced in `synlynk/maintainer.py`'s promotion path:
  1. **Per-action opt-in, recorded.** An action's `mode: promote` setting is necessary but not sufficient — each individual promotion call records an audit-log entry (`.synlynk/maintainer_audit.jsonl` or the existing telemetry log, decided at plan time) with the action id, the external write performed, and a timestamp, before the write executes.
  2. **Per-cycle cap.** A `max_promotions_per_cycle` setting (default: a small fixed number, e.g. 10) hard-stops further promotions once hit within a single `run_maintainer_wake_cycle()` invocation; remaining candidates stay in `staged` lifecycle for the next cycle.
  3. **Dedupe.** Before opening an issue, Maintainer searches existing open issues for the same finding signature (same cluster + same file/topic fingerprint) and attaches to the existing issue instead of opening a duplicate.
  4. **Rate limit.** Promotions respect a minimum spacing between consecutive external writes (reusing whatever rate-limit helper `synlynk gh` already wraps, if one exists; otherwise a simple sleep/backoff) — this is about not hammering the GitHub API in one sweep, not security.
  5. **No host-token fallback.** If no `qa`-role (or other configured writer-role) GitHub App token is provisioned, the promotion step stages the finding and skips the external write — it does **not** fall back to a host-authenticated `gh` call. This matches the Hardened PR Review Policy's standing invariant (CLAUDE.md: "Personal GitHub token is strictly off-limits to every agent/harness") — there is no carve-out for Maintainer.
- GitHub Actions running `synlynk maintainer wake` (§5.8) is itself scoped least-privilege (issues: write only, not full repo), runs under a named writer identity (the `qa`-role App token, injected as a secret — never the workflow's default `GITHUB_TOKEN` acting as a human), and uses a `concurrency` group keyed on the workflow name so overlapping scheduled + manual runs can't race each other's promotion caps/dedupe.

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

### 5.6 Proximal selection (dual-graph, with keyword fallback) — revised per DECIDE panel defect #3

**The original description under-specified the mechanism — Codex's review found the implied implementation omits distance-two traversal, `reverse_doc_index`, and issue/PR evidence entirely.** This section replaces it with one normalized evidence model, evaluated once per candidate finding, with a single deterministic scoring/tie-break instead of three independent "first match wins" tiers:

**Evidence model.** For each candidate finding and each existing open proposal, collect zero or more `Evidence` records:

```python
Evidence(tier="code_graph", weight=..., detail="distance-1 import edge: a.py -> b.py")
Evidence(tier="code_graph", weight=..., detail="distance-2 via shared caller")
Evidence(tier="doc_graph",  weight=..., detail="shared reverse_doc_index entry: spec.md")
Evidence(tier="doc_graph",  weight=..., detail="shared issues_and_prs: #1234")
Evidence(tier="keyword",    weight=..., detail="cluster match: backend")
```

- **`code_graph` tier** — via `ensure_graph_for_head()`/`write_traversal_cache()` (`synlynk/scan.py`, `synlynk/graph_cache.py`): evaluates both **distance-1** (direct edge between touched files) and **distance-2** (shared neighbor/caller) adjacency to an existing proposal's files. Distance-2 carries a lower weight than distance-1 — both are config-driven (`.synlynk/maintainer_taxonomy.json`'s `proximal_selection.code_graph_weights`, §6), not hardcoded.
- **`doc_graph` tier** — via `docgraph.py`'s `reverse_code_index` **and** `reverse_doc_index` (the original spec named `reverse_code_index` only and dropped the second): a shared referencing doc, OR a shared `issues_and_prs` entry, OR a shared `code_references` entry each produce one `Evidence` record with their own configured weight.
- **`keyword` tier** — today's `cluster_open_issues()` mechanism, reading its taxonomy from `.synlynk/maintainer_taxonomy.json` (§6) instead of a hardcoded Python dict. Lowest default weight of the three tiers.

**Resolution.** Sum each open proposal's evidence weights; the candidate joins the highest-scoring proposal if that score clears a configured `join_threshold` (`.synlynk/maintainer_taxonomy.json`'s `proximal_selection.join_threshold`, §6 — not a hardcoded constant). Ties break deterministically by proposal age (oldest wins), then `proposal_id` lexical order. If no proposal clears the threshold and the finding isn't critical/high-severity, it accumulates toward the minimum-cluster-volume threshold under its keyword bucket, same as today.

**Provenance.** Every proposal join records which tier(s) and which specific `Evidence` entries produced the winning score, surfaced in Proposal Studio (§5.5) as a "why this grouping" expandable detail on the card — this is what makes the mechanism auditable instead of a black box, and is what the fixture tests (§8) assert against directly (tier 1/2/3 resolution order, not just "a match happened").

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

Both move out of `maintainer.py` into a new per-workspace config file, `.synlynk/maintainer_taxonomy.json`. **Revised per DECIDE panel defect #5:** this file (and `.synlynk/domain_pack.json`, §7) is a versioned, validated schema, not a loosely-shaped JSON blob — a malformed or missing file must degrade safely, not crash the wake cycle:

```json
{
  "schema_version": 1,
  "cluster_keywords": {
    "backend": ["sqlite", "api", "server"],
    "frontend": ["css", "html", "vizor"],
    "cli": ["argparse", "subcommand"],
    "docs": ["readme", "docstring"],
    "sentinel": ["alert", "circuit breaker"],
    "testing": ["pytest", "fixture"]
  },
  "remediation_topics": ["invariant 1", "circuit breaker", "daemon supervision"],
  "proximal_selection": {
    "code_graph_weights": {"distance_1": 10, "distance_2": 4},
    "doc_graph_weights": {"reverse_doc_index": 6, "issues_and_prs": 8, "code_references": 5},
    "keyword_weight": 2,
    "join_threshold": 6
  }
}
```

**Validation and fallback:** `synlynk/maintainer_taxonomy.py::load_taxonomy()` validates `schema_version` is a known value (currently `1`; an unrecognized version logs a warning and falls back to built-in defaults rather than guessing at a migration), checks every `cluster_keywords` value is a list of strings and every weight is a non-negative number, and on any validation failure — malformed JSON, missing file, bad types — falls back to the built-in default taxonomy (synlynk's own current lists, hardcoded as the ultimate fallback in `maintainer_taxonomy.py` itself) rather than raising. This failure is logged, and the Role Operations Panel (§5.4) surfaces a "using built-in defaults — config failed validation" banner so the gap doesn't go silent.

synlynk's own repo ships this file pre-populated with its current lists (no behavior change for this repo). A fresh `synlynk init` elsewhere scaffolds an empty/minimal version; burndown's `#N`/`fixes #N` commit-reference matching (already domain-agnostic) still works with zero configuration, so a new workspace isn't crippled on day one — it just won't catch topic-based matches until someone fills this in. The Role Operations Panel (§5.4) gains a "Cluster taxonomy" editor (cluster name → keyword chips) so this is user-editable without touching code.

`mesh_sweep`'s value is inherently proportional to how much of the workspace is actual source code; for a content/doc-heavy workspace it will have near-zero signal. The Role Operations Panel shows a "low signal" hint next to `mesh_sweep` when `ensure_graph_for_head()` indexes under a small file-count threshold, so a user on such a workspace knows to leave it disabled rather than wondering why it never finds anything.

## 7. Domain Pack Extension Point (schema + loader; packs themselves are future work)

To support the stated future plan of shipping industry/domain-specific resource packs that populate the taxonomy or doc-graph classifier, this spec adds the extension point without building the packs:

- New schema, `.synlynk/domain_pack.json`, also versioned per defect #5:

```json
{
  "schema_version": 1,
  "pack_name": "synlynk-default",
  "cluster_keywords": { "...": ["..."] },
  "remediation_topics": ["..."],
  "doc_type_extensions": {
    "compliance_doc": ["hipaa", "compliance/"],
    "shot_list": ["shotlist", "shot-list"]
  }
}
```

- New loader `load_domain_pack()` (`synlynk/maintainer_taxonomy.py`), called at wake-cycle start: merges `cluster_keywords`/`remediation_topics` into `.synlynk/maintainer_taxonomy.json`'s runtime values, and merges `doc_type_extensions` into `docgraph.py::classify_doc_type()`'s classification (checked after the built-in structural buckets, before falling through to `general_doc`). **Documented precedence (defect #5):** domain pack values layer *over* `.synlynk/maintainer_taxonomy.json`'s own values for any key present in both (pack wins), which in turn layer over `maintainer_taxonomy.py`'s hardcoded built-in defaults (taxonomy file wins over built-ins). Same `schema_version`/fallback validation as §6 applies — a malformed or unversioned domain pack is skipped entirely (logged, panel banner shown) rather than partially merged.
- v1 ships exactly one worked pack: synlynk's own current software-engineering lists, expressed in this format as the "default" pack — this is what proves the mechanism works, without requiring fabricated specifics about rxcc/vdowrx/Hitchcock's actual current vocabulary.
- Building the rxcc/vdowrx/Hitchcock-specific packs themselves is out of scope for this spec (§4) — flagged as the natural next step once this mechanism lands.

## 8. Testing Approach

- Unit tests per registered action: dry-run vs. promote branching, settings-registry defaults, filter application (`exclude_codes`/`exclude_labels`).
- Unit tests for proximal selection (revised per defect #3): fixture asserting distance-1 vs. distance-2 code-graph weighting, a fixture `DocGraph` exercising **both** `reverse_code_index` and `reverse_doc_index` plus `issues_and_prs`/`code_references` evidence, keyword-only fallback, threshold tie-breaking (proposal age then `proposal_id`), and the "non-code-dominant workspace" fixture (mostly non-`_SOURCE_SUFFIXES` files) proving graceful degradation to doc-graph/keyword tiers without error. Each case asserts the recorded tier provenance matches which `Evidence` records actually won, not just that *a* match happened.
- Unit test for severity-override bypass of the minimum-cluster-volume threshold.
- Unit tests for `.synlynk/maintainer_taxonomy.json`/`.synlynk/domain_pack.json` schema validation and fallback (defect #5): unknown `schema_version`, malformed JSON, missing file, bad field types — each must fall back to built-in defaults and log/surface the panel banner, never raise.
- Unit test for `load_domain_pack()` merge/precedence behavior (pack > taxonomy file > built-in defaults; `doc_type_extensions` checked before `general_doc` fallback).
- Unit tests for the promotion boundary (defect #2): dry-run staging makes zero external calls (asserted via a mocked/forbidden `gh` call in the test), per-cycle cap stops promotion mid-cycle, dedupe attaches to an existing issue instead of opening a duplicate, and the no-host-token-fallback path stages without erroring when no role App token is configured.
- Integration test for the full wake cycle against a fixture `sentinel.md` + fixture open-issues list, asserting staged proposals have non-null `github_issue` per story.
- Vizor rendering tests: Role Operations Panel renders all three registered actions with correct toggle/mode state from typed `FieldSpec`s; Overview widget renders condensed badges; Proposal Studio renders multi-source cards (via the shared `Proposal` schema, defect #4, including a TPM `release_proposal` row read through the adapter) with correct `source` badges, "why this grouping" provenance detail, and the "Needs attention now" lane for severity-flagged proposals.
- CLI test for `synlynk maintainer wake` subcommand wiring.

## 8a. Implementation Sequencing (added per DECIDE panel 2026-11-24)

Reviewed by `synlynk decide --record` (panel: claude, agy, codex — grok excluded, 402 billing exhaustion; see `project-docs/decisions/2026-11-24-maintainer-full-autonomy-docs-superpower.md`). Verdict: conditionally approved, contingent on the revisions in §5.2, §5.3/§5.3a, §5.6, §6, §7 above (registry role-awareness + typed `FieldSpec`, dry-run/promotion split with audit/cap/dedupe/rate-limit/no-host-fallback, evidence-based proximal selection with config-driven weights and tier provenance, shared `Proposal` schema, versioned taxonomy/domain-pack schemas with validated fallback) — all now folded into this spec.

Dispatch order:
1. **Foundation wave (T1–T4 in the implementation plan):** taxonomy/domain-pack schema + loader + validation (§6, §7), registry (§5.2). No dependency on the proximal-selection or promotion-boundary work.
2. **Hold** the proximal-selection task (plan T5) until its evidence model/weights/provenance (§5.6) are fully specified in the plan — not yet true as of this spec revision; the plan itself still needs updating to match.
3. **Hold** the Role Operations Panel and Proposal Studio generalization tasks (plan T13–T14) until the registry contract (§5.2) is proven working end-to-end, since both render from it.
4. Re-run `synlynk decide --record` on this revised spec before dispatching anything, per standing policy ([[feedback_decide_panel_for_specs]]).

## 9. Future Work (explicitly out of scope here)

- The slash-command dispatcher (GH comment/slash-command → role trigger) for any role, not just Maintainer.
- Actual rxcc/vdowrx/Hitchcock domain packs.
- Applying this same reference pattern (action registry, operations panel, proposal-source generalization) to roles beyond TPM/Maintainer.
