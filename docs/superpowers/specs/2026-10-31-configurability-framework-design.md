---
title: "Configurability Framework Design"
date: 2026-10-31
status: draft
author: "Claude (Home Conductor)"
goal: "goal-85656c82"
epic: "#2458"
milestone: "v0.26.8"
arc: "developer-experience"
---

# Configurability Framework Design

## 1. Problem

v0.26.8 bundles three features that each need the same kind of control: whether
they ship at all, whether a given user has turned them on, and how deep/custom
their behavior is for that user — plus, for at least one of them (the
at-the-fence Companion), an open-ended way for the community to add new
behavior without touching synlynk's own code.

- **Companion** (at-the-fence personality/voice messages) needs a fence-message
  composition pipeline (`cost` + `companion` + future contributors) and
  swappable theme packs.
- **Harness Context Compaction Protocol** and **Herdr Customizations** (both
  separately brainstormed next) will need the identical on/off + depth-settings
  treatment.
- Today, the only precedent is `FeatureFlags.is_enabled(flag, tier)`
  (`synlynk/uxcore.py`) — a flat, **subscription-tier** gate (individual/team),
  not a user-preference depth control — and the `fenced_commands` allowlist,
  which is single-purpose. Neither generalizes. Inventing a bespoke on/off +
  settings pattern per feature has already caused real drift once before: the
  `roles`/capability-mapping triplication tracked separately as `gh:#2145`.

This design is the shared foundation the other three specs will consume,
rather than each reinventing it.

## 2. Non-goals

- No retrofit of every existing synlynk feature to this model in this spec.
  That's a standing design principle (documented once, applied to new work
  and opportunistically backfilled into old work), not a migration project
  scoped here.
- No build-time manifest/allowlist beyond pip extras (a maintainer-controlled
  "strip features from a custom build" layer was considered and explicitly
  deferred — extras are the only build-level control in v1).
- No Vizor settings UI. CLI/terminal only, matching the scope the Companion
  brainstorm already settled on.
- No design of Companion's, Compaction's, or Herdr's own settings schemas or
  pack content — those are feature-owned and specified in their own documents.

## 3. Three layers

### Layer 1 — Build footprint (pip extras)

Each optional feature ships as its own extra, following the precedent already
set by the unreleased NATS relay feature (`hub` extra; core CLI stays
stdlib-only). `pyproject.toml` gains one `[project.optional-dependencies]`
group per feature that has non-stdlib dependencies; a feature with no extra
dependencies (e.g. Companion's static-template mode) still registers in the
manifest below with no corresponding extra, and Layer 1 for it is always
"present."

`synlynk/features/registry.py` (new):

```python
from dataclasses import dataclass, field
from typing import Callable, Optional

@dataclass
class FeatureSpec:
    name: str                              # "companion", "context_compaction", "herdr_cockpit"
    extra_name: Optional[str]              # pip extra name, or None if no extra dependencies
    import_probe: Callable[[], bool]       # returns True if the feature's code is importable
    settings_schema: dict                  # hand-rolled schema, validated via config_schema.py helpers
    default_enabled: bool = False
    supports_packs: bool = False
    pack_loader: Optional[Callable] = None # only meaningful if supports_packs

FEATURE_MANIFEST: dict[str, FeatureSpec] = {}

def register_feature(spec: FeatureSpec) -> None:
    FEATURE_MANIFEST[spec.name] = spec
```

Each feature module calls `register_feature(...)` at import time — the
registry itself never hardcodes feature names.

### Layer 2 — User enable/disable

New `.synlynk/features.json` (sibling to `workspace.json`/`billing.json`/
`policy.json` from the `2026-10-09-config-decomposition-design.md` split):

```json
{
  "companion": { "enabled": false, "settings": {} },
  "context_compaction": { "enabled": false, "settings": {} }
}
```

```python
def is_feature_enabled(name: str) -> bool:
    spec = FEATURE_MANIFEST.get(name)
    if spec is None:
        return False
    if not spec.import_probe():
        return False                          # Layer 1: code not present
    entry = load_features_json().get(name, {})
    return entry.get("enabled", spec.default_enabled)
```

Fail-closed, consistent with `FeatureFlags.is_enabled()`'s existing convention:
a missing file, missing key, or an extra that isn't installed all resolve to
`False`, never an error.

### Layer 3 — Depth settings

`<feature>.settings` in `features.json` holds arbitrary nested JSON, validated
against `FeatureSpec.settings_schema` using the existing hand-rolled
`validate()`/`validate_fields()`/`_check_field()` helpers in
`config_schema.py` (no new JSON-schema dependency, matching that document's
own stated preference). A feature adds a new setting by editing its own
manifest entry's schema — the registry and CLI code never change.

### Generic expansion-pack pattern

A feature with `supports_packs=True` gets:

```python
def discover_packs(feature_name: str) -> list[Path]:
    """Scans .synlynk/packs/<feature_name>/*.json plus any paths registered
    via `synlynk config feature <name> pack add <path>` (stored in that
    feature's own settings under a conventional `pack_paths` key). Returns
    paths only — never opens or validates them. That is the feature's own
    `pack_loader`'s job."""
```

The framework's responsibility stops at *finding* candidate pack files.
Parsing, schema validation, and interpretation of pack content is 100%
feature-owned — this is what lets Companion's theme packs and some future
Compaction or Herdr pack concept have completely different internal shapes
without the framework needing to know about either.

This is also the mechanism that makes a composed fence message
(`cost + companion + opt1..optN`) possible: each contributor registers itself
as a pack-like unit under the `fencing` composition point, independently
enabled and configured through the same three layers.

## 4. CLI surface

```
synlynk config feature list                      # name, build-present?, enabled?, settings summary
synlynk config feature <name> enable|disable
synlynk config feature <name> set <key> <value>
synlynk config feature <name> show
synlynk config feature <name> pack add <path>    # only for supports_packs=True features
```

`list` is the single place a user (or support) can answer "how deep/wide is
my install" across every registered feature at once.

## 5. Compatibility

- `FeatureFlags.is_enabled(flag, tier)` is untouched. It answers a different
  question (does this subscription tier have this capability) than
  `is_feature_enabled(name)` (has this user turned this on). No call sites
  change.
- `features.json` is a new file; a workspace with no file for a given feature
  simply gets `default_enabled` behavior (`False` unless a feature spec opts
  into `default_enabled=True`), exactly like a missing `workspace.json`
  `features{}` key does today for `FeatureFlags`.

## 6. Testing

- `tests/test_features_registry.py`:
  - `register_feature()` / `FEATURE_MANIFEST` round-trip.
  - `is_feature_enabled()` truth table: extra absent → `False` regardless of
    `features.json`; extra present + no `features.json` entry → `default_enabled`;
    extra present + explicit `enabled: true/false` → that value.
  - `discover_packs()` finds files under `.synlynk/packs/<feature>/` and
    registered extra paths; returns `[]` for a feature with no packs and
    no error for a missing directory.
  - Settings schema validation rejects an invalid value with the same error
    type `config_schema.py` raises today for an invalid `workspace.json`.
- `tests/test_cli_config_feature.py`: `list`/`enable`/`disable`/`set`/`show`
  round-trip against a temp `features.json`.

## 7. What the three consuming specs inherit

| Spec | Feature name | Needs from this framework |
| --- | --- | --- |
| Companion v2 | `companion` | Layers 2–3 for theme/voice-density/remix settings; pack discovery for theme packs; fence-message composition point |
| Harness Context Compaction Protocol | `context_compaction` | Layers 2–3 for threshold/aggressiveness settings; no packs needed unless that spec decides otherwise |
| Herdr Customizations | `herdr_cockpit` | Layers 2–3 for pane-layout/auto-launch settings; possibly packs for alternate layout templates |

Each of those specs registers its own `FeatureSpec` and settings schema; none
of them modify `synlynk/features/registry.py` itself.
