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

### Layer 1 — Dependency presence (pip extras)

**Precision correction (DECIDE panel, 2026-10-31):** Layer 1 answers "is this
feature's non-stdlib dependency installed," not "was this feature stripped
from the build." `pip`'s `packages.find` ships all of synlynk's code
regardless of which extras a given install selected — extras gate importable
*dependencies*, not *presence of code*. A maintainer-controlled build-time
code-stripping/allowlist layer remains explicitly out of scope (see Non-goals);
Layer 1 is "dependency presence via extras," full stop.

Each optional feature ships as its own extra, following the precedent already
set by the unreleased NATS relay feature (`hub` extra; core CLI stays
stdlib-only). `pyproject.toml` gains one `[project.optional-dependencies]`
group per feature that has non-stdlib dependencies; a feature with no extra
dependencies (e.g. Companion's static-template mode) still registers in the
manifest below with no corresponding extra, and `import_probe()` for it always
returns `True` ("present" by definition, since there's no dependency to be
missing).

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

**Bootstrap hook (DECIDE panel, 2026-10-31 — required before any consumer
registers):** `FEATURE_MANIFEST` is only populated if the owning module has
actually been imported, so a single, named load point is required or a
hardcoded import list creeps back in by necessity. `synlynk/features/__init__.py`
exposes `load_all_features() -> None`, which imports every module listed in
a plain Python tuple, `_FEATURE_MODULES`, inside that same file (e.g.
`("synlynk.companion", "synlynk.context_compaction", "synlynk.herdr_cockpit")`)
— each import's top-level `register_feature(...)` call does the rest.
`load_all_features()` is called once, at CLI startup (`synlynk/cli.py`'s
`main()`, before argument dispatch), and is idempotent (importing an
already-imported module is a no-op). Each of the three consuming specs adds
its own module's dotted path to `_FEATURE_MODULES` as part of landing its
`FeatureSpec` — the registry file itself still never hardcodes a feature
*name*, only the list of modules to import.

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

**Missing-config semantics, stated once (DECIDE panel, 2026-10-31):** there is
exactly one rule, and it is fail-closed: a missing `features.json`, a missing
entry for a given feature name, and an uninstalled extra (`import_probe()`
returns `False`) all fall through to `spec.default_enabled` — which is
`False` unless a feature spec explicitly opts into `True`. There is no
separate "missing → always False, ignore default_enabled" case; the code
above (`entry.get("enabled", spec.default_enabled)`) and the Compatibility
section below both follow this single rule. Never an error, never a silent
`True` for an unrecognized or uninstalled feature.

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
    under that feature's own settings at the reserved key `pack_paths`
    (a list of strings, populated via `synlynk config feature <name> pack
    add <path>` — this command appends to that key, it does not define a
    new storage location). Order: `.synlynk/packs/<feature_name>/*.json`
    first (sorted by filename), then `pack_paths` in list order; duplicate
    resolved paths are de-duplicated keeping the first occurrence. Returns
    paths only — never opens, parses, or validates them. That is the
    feature's own `pack_loader`'s job, including any pack-content security
    checks (e.g. refusing a pack path outside the workspace root) — the
    framework performs no such checks itself."""
```

The framework's responsibility stops at *finding* candidate pack files.
Parsing, schema validation, and interpretation of pack content is 100%
feature-owned — this is what lets Companion's theme packs and some future
Compaction or Herdr pack concept have completely different internal shapes
without the framework needing to know about either.

**Scoping correction (DECIDE panel, 2026-10-31):** composing a fence message
out of multiple contributors (`cost + companion + opt1..optN`) is **not**
part of `discover_packs()` or this framework. It is Companion v2's own
composition pipeline, built using this framework's Layers 2–3 (each
contributor is independently enabled/configured) plus, if Companion chooses,
its own call to `discover_packs("companion")` for pack-sourced contributors.
This framework provides the building blocks; it does not itself define a
`fencing` composition point.

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
    registered `pack_paths` extra paths, in that order; returns `[]` for a
    feature with no packs and no error for a missing directory; a path
    appearing in both sources is returned once.
  - `load_all_features()` populates `FEATURE_MANIFEST` from `_FEATURE_MODULES`
    and is idempotent on a second call (no duplicate registration, no error).
  - Settings schema validation rejects an invalid value with the same error
    type `config_schema.py` raises today for an invalid `workspace.json`.
- `tests/test_cli_config_feature.py`: `list`/`enable`/`disable`/`set`/`show`
  round-trip against a temp `features.json`.

## 7. What the three consuming specs inherit

| Spec | Feature name | Needs from this framework |
| --- | --- | --- |
| Companion v2 | `companion` | Layers 2–3 for theme/voice-density/remix settings; pack discovery (`discover_packs("companion")`) for theme packs. Fence-message composition itself is Companion's own pipeline, not provided by this framework. |
| Harness Context Compaction Protocol | `context_compaction` | Layers 2–3 for threshold/aggressiveness settings; no packs needed unless that spec decides otherwise |
| Herdr Customizations | `herdr_cockpit` | Layers 2–3 for pane-layout/auto-launch settings; possibly packs for alternate layout templates |

Each of those specs registers its own `FeatureSpec` and settings schema; none
of them modify `synlynk/features/registry.py` itself.
