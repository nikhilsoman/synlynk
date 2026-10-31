<!-- generated - source of truth is state.db -->
---
decision_id: dec-98202ded
topic: "Review and approve/reject the Configurability Framework design (docs/superpowers/specs/2026-10-31-configurability-framework-design.md, committed 6d322dd2): a 3-layer config model (pip-extra build footprint via FeatureSpec registry, user enable/disable via .synlynk/features.json, depth settings validated via existing config_schema.py helpers) plus a generic discover_packs() expansion-pack discovery mechanism, intended as the shared foundation that Companion v2, Harness Context Compaction Protocol, and Herdr Customizations will each register against for v0.26.8. Evaluate: does the 3-layer split correctly separate build/enable/depth concerns, is the generic pack-discovery boundary (framework finds files, feature parses them) the right line, and does deferring a build-time manifest/allowlist and Vizor settings UI as non-goals make sense for v1?"
date: 2026-10-31
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Review and approve/reject the Configurability Framework design (docs/superpowers/specs/2026-10-31-configurability-framework-design.md, committed 6d322dd2): a 3-layer config model (pip-extra build footprint via FeatureSpec registry, user enable/disable via .synlynk/features.json, depth settings validated via existing config_schema.py helpers) plus a generic discover_packs() expansion-pack discovery mechanism, intended as the shared foundation that Companion v2, Harness Context Compaction Protocol, and Herdr Customizations will each register against for v0.26.8. Evaluate: does the 3-layer split correctly separate build/enable/depth concerns, is the generic pack-discovery boundary (framework finds files, feature parses them) the right line, and does deferring a build-time manifest/allowlist and Vizor settings UI as non-goals make sense for v1?

## Panel Inputs

### claude
[model=default; version=2.1.311 (Claude Code)]

## Review: Configurability Framework Design

**3-layer split.** The build/enable/depth separation is sound and maps cleanly to distinct failure modes: "code not present" (Layer 1, pip extras) vs. "code present but user hasn't opted in" (Layer 2, `features.json`) vs. "opted in, now tune it" (Layer 3, schema-validated settings). `is_feature_enabled()`'s fail-closed chain (extra missing → False → no entry → `default_enabled` → explicit value) is the right order of precedence and mirrors the existing `FeatureFlags` convention, which keeps the mental model consistent for anyone who's touched that code. Explicitly leaving `FeatureFlags.is_enabled(flag, tier)` untouched and documenting it answers a different question (tier capability vs. user preference) is the correct call — conflating those two was exactly the kind of drift that caused the `roles`/capability-mapping triplication (gh:#2145) this spec cites as precedent to avoid.

**Pack-discovery boundary.** "Framework finds files, feature parses them" is the right line. `discover_packs()` returning bare `Path` objects with zero parsing keeps the registry genuinely generic — Companion's theme packs and a hypothetical Compaction/Herdr pack format can diverge completely in shape without forcing a change to `registry.py`. The fencing composition point (`cost + companion + opt1..optN` each as an independently-configured pack-like unit) is a clean reuse of the same primitive rather than a bespoke composition mechanism, which is the kind of reuse this framework exists to enable.

**Non-goals.** Deferring the build-time manifest/allowlist (beyond pip extras) is correct for v1 — that's a maintainer-facing "strip features from a custom build" concern with no consumer demand yet from any of the three named specs, and bolting it on speculatively would be exactly the premature abstraction this framework is trying to avoid elsewhere. Deferring the Vizor settings UI is also right since it matches scope already settled in the Companion brainstorm, and CLI-only keeps the framework's first implementation small enough to actually validate against three real consumers before a UI locks in assumptions about shape.

**Position: Approve.** The layering is coherent, the pack boundary is drawn at the right generality, and both deferred non-goals are genuinely premature rather than corner-cut. One thing worth a follow-up issue rather than blocking this spec: `settings_schema` being hand-rolled per feature with no shared "common setting types" (e.g., depth/aggressiveness enums) means Compaction and Herdr may still duplicate schema boilerplate — not a blocker, but worth flagging for the maintainers of those two specs when they register.

### agy
[model=default; version=1.4.12]

Last completed task: docs: configurability framework design spec (`6d322dd2`)
Next task from `todo.md`: Reconcile project-docs drift stranded in PR #2571 review worktree (PR #2572)

***

### Evaluation & Analysis

The proposed [Configurability Framework Design](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/docs/superpowers/specs/2026-10-31-configurability-framework-design.md) provides a clean, decoupled foundation for the v0.26.8 feature set (Companion v2, Context Compaction, and Herdr Customizations).

1. **3-Layer Split (Build / Enable / Depth):**
   The separation between **build footprint** (Layer 1: pip extras + `import_probe`), **workspace enable/disable** (Layer 2: `.synlynk/features.json`), and **depth settings** (Layer 3: validated nested JSON) is architecturally sound. It cleanly untangles user configuration from subscription-tier gating (`FeatureFlags.is_enabled`) without breaking existing call sites. Gating Layer 2 evaluation on Layer 1 importability ensures a fail-closed model, preventing broken runtime states if dependencies are omitted. Furthermore, reusing existing validation helpers from [`config_schema.py`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/synlynk/config_schema.py) avoids bloat and heavy third-party JSON schema dependencies.

2. **Pack-Discovery Boundary:**
   The boundary defined in `discover_packs()`—where the framework handles filesystem resolution (`.synlynk/packs/<feature>/*.json` + registered paths) while the domain-specific `pack_loader` handles file parsing and validation—strikes the right balance. It avoids leaky abstractions, allowing Companion voice themes, compaction heuristics, and Herdr pane presets to evolve their schemas independently without modifying the core framework.

3. **Deferred Non-Goals:**
   Deferring a build-time manifest/allowlist and Vizor settings UI is pragmatic for v1. Python’s optional dependencies (`extras`) are sufficient for maintaining a lightweight core distribution; adding a bespoke build-time compilation allowlist would add maintenance friction with negligible benefit. Similarly, terminal-driven configuration (`synlynk config feature ...`) matches current operational workflows and avoids blocking foundational backend delivery on UI development.

### Recommendation

I **APPROVE** the Configurability Framework design spec (`2026-10-31-configurability-framework-design.md`). It establishes a minimal, extensible, and fail-closed pattern that resolves configuration drift across upcoming v0.26.8 initiatives.

### codex
[model=default; version=codex-cli 0.163.0]

The three-layer split is conceptually sound. Build footprint, user activation, and behavioral depth are different axes, and keeping them separate avoids conflating “installed,” “enabled,” and “configured.” Reusing `config_schema.py` also preserves the project’s existing validation model and avoids introducing a second schema dependency. The CLI surface is appropriately uniform, while feature-owned schemas keep the framework from becoming a bottleneck.

The pack-discovery boundary is also the right abstraction: the framework should identify candidate paths, while each feature owns parsing, validation, and interpretation. That permits Companion theme packs, future Compaction packs, and Herdr layout packs to evolve independently. However, v1 should specify deterministic ordering, duplicate handling, supported file extensions, and behavior for unreadable or out-of-root paths. The “registered extra paths” mechanism also needs a precise security and persistence contract; arbitrary paths should not silently become a trust boundary.

I see two design gaps worth resolving before implementation. First, import-time registration is underspecified: if feature modules are not imported, their `FeatureSpec` entries never exist, so `FEATURE_MANIFEST` cannot discover them. The design needs an explicit module-loading/bootstrap mechanism, or a small static registration entry point. Second, the missing-file semantics are slightly inconsistent: `is_feature_enabled()` uses `default_enabled`, while the prose says missing files/keys resolve to false. That is harmless with all defaults false, but should be stated consistently and tested explicitly. Settings validation should also define whether invalid persisted settings fail commands, disable the feature, or fall back to defaults.

Deferring a build-time manifest/allowlist and Vizor UI is sensible for v1: pip extras provide a sufficient build-level control, and CLI-only scope matches the consuming work. I recommend approval with these conditions: clarify registration/bootstrap and missing-config semantics, and add pack path/order/security rules before implementation.

### grok
[model=default; version=grok 1.0.70 (f50904eaee6c) [stable]]

I'll read the configurability framework spec and the surrounding design context, then judge the three-layer split, pack-discovery boundary, and the deferred non-goals.The three-layer split is the right product model. Build presence, user enablement, and depth settings are different questions, and today's `FeatureFlags.is_enabled(flag, tier)` answers only the subscription one. Leaving that API untouched, and storing `{enabled, settings}` in a new `.synlynk/features.json` beside the 2026-10-09 config split, keeps tier policy and user preference apart. Fail-closed on an unknown name, a failed probe, or a missing file matches `FeatureFlags`. A missing entry follows `default_enabled`, which a spec may set true. Reusing `config_schema.validate()` stays stdlib-only. That helper returns error strings and does not raise, so the test plan should say so. Callers must AND the tier gate with `is_feature_enabled`; this spec should say that once.

Layer 1 is thinner than "build footprint." The `hub` extra only adds `nats-py`; `packages.find` still ships every `synlynk*` module. An extra records dependency presence. Companion's static mode has no extra, so for that consumer Layer 1 is always present. That is acceptable for v1. A maintainer allowlist that strips code would be a second packaging system with no current consumer. Deferring it is right if consuming specs do not treat a missing extra as "code not in the wheel."

Import-time `register_feature` into a process-global dict is the real hole. Something must import each feature module or `config feature list` is empty, which smuggles a hardcoded import list back in. An explicit loader, called once at CLI startup, is enough for v1.

`discover_packs()` returning paths only is the right boundary. Theme JSON, layout templates, and compaction packs will not share a schema. Limiting the scan to `*.json` keeps packs as data. The framework may reserve `settings.pack_paths`. It should not also be the fence-composition bus: `cost + companion + optN` is an ordered set of in-process contributors, and that registry belongs to the Companion spec.

Deferring Vizor is right. The three consumers have not frozen their schemas, Companion is already CLI-scoped, and `features.json` plus `config feature list` is a shape a later UI can read without a migration.

**Approve** `6d322dd2` as the v0.26.8 foundation, after three edits before the other specs register: name the startup load hook, reserve `pack_paths` and keep fence composition out of `discover_packs`, and describe Layer 1 as dependency presence with code-stripping explicitly deferred.

## Synthesis
Decision: **Approve** the Configurability Framework design (`6d322dd2`) as the shared foundation for v0.26.8, with three fixes required before Companion v2, Context Compaction, or Herdr Customizations register against it.

All five reviewers converge on the core architecture: the build/enable/depth 3-layer split correctly separates distinct questions (code present? → user opted in? → how deep?), properly leaves `FeatureFlags.is_enabled(tier)` untouched as an orthogonal axis, and reuses `config_schema.py` rather than introducing a second validation system. The pack-discovery boundary — framework resolves paths, feature parses content — is unanimously endorsed as the correct generality: it lets Companion themes, Compaction heuristics, and Herdr layouts diverge in schema without touching `registry.py`. Deferring the build-time manifest/allowlist and Vizor settings UI is correctly scoped out: no consumer demand exists yet, and CLI-only keeps the first implementation small enough to validate against three real consumers before a UI locks in assumptions.

Codex and Grok independently surface the same material gap, which elevates it from a nitpick to a blocking condition: **feature/pack registration has no specified bootstrap.** `FeatureSpec` entries only exist if their module is imported, and nothing in the spec says who imports what, when — without this, `FEATURE_MANIFEST`/`discover_packs()` silently return empty and a hardcoded import list creeps back in by necessity. Grok additionally flags that Layer 1 should be documented as "dependency presence" rather than "build footprint" (since `packages.find` still ships all code regardless of extras), and that fence composition (`cost + companion + optN`) belongs to the Companion spec, not inside `discover_packs()` itself. Codex separately flags underspecified pack ordering/duplicate/security handling for registered extra paths, and inconsistent missing-config semantics (`default_enabled` vs. "missing → false" prose) that should be stated once, consistently, and tested.

**Required before the three dependent specs register:** (1) name an explicit startup load/bootstrap hook for `FeatureSpec`/pack registration, (2) reserve `pack_paths` as a settings key and keep fence-composition logic out of `discover_packs()`, (3) state Layer 1 precisely as dependency-presence-via-extras (code-stripping explicitly out of scope) and resolve the `default_enabled`-vs-missing inconsistency in one place. These are scoping/precision fixes to the committed spec, not architectural rework — none block approval, but Companion v2/Compaction/Herdr should not register against the framework until they land.

## Decision
Decision: **Approve** the Configurability Framework design (`6d322dd2`) as the shared foundation for v0.26.8, with three fixes required before Companion v2, Context Compaction, or Herdr Customizations register against it.

> Signatures: see 2026-10-31-review-and-approve-reject-the-configurab.json
