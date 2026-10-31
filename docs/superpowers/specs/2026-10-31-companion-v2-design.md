---
title: "Companion v2 Design"
date: 2026-10-31
status: draft
author: "Claude (Home Conductor)"
goal: "goal-85656c82"
epic: "#2458"
milestone: "v0.26.8"
arc: "developer-experience"
depends_on: "docs/superpowers/specs/2026-10-31-configurability-framework-design.md"
---

# Companion v2 Design

## 1. Problem

v0.26.8's "at-the-fence" communication — the moment a harness calls back into
synlynk between tasks — is today a plain cost block (`FenceData`/
`render_task_fence()` in `synlynk/fencing.py`). The goal is to turn that
moment into an optional, configurable "voice" that meets four very different
developer segments (novice, skeptic, accelerant, architect) where they are
on an acceptance ladder toward AI-assisted development, without becoming
noise for anyone who doesn't want it.

This spec is Companion v2: it supersedes the original (pre-expansion)
Companion brainstorm by registering against the newly-approved
[Configurability Framework](2026-10-31-configurability-framework-design.md)
instead of defining its own ad hoc config block, and adds fence-message
composition, theme packs, and domain vocabulary.

## 2. Carried-over decisions (settled in the original Companion brainstorm, unchanged)

- **Stage and theme are independent axes.** `stage` (`onboarding |
  companionship | sounding_board | policy_maker | recruiter | champion`) is
  a relationship-ladder position; `theme` is a pure vocabulary/tone skin.
  Neither implies the other.
- **Stage is auto-inferred from behavior, user-overridable.** Signals:
  command vocabulary, override-rate of suggested actions, frequency of
  manual intervention vs. accepting defaults. Never advanced purely on
  elapsed time. The `stage` setting (Section 4) holds an explicit override
  when set; absent an override, Companion computes it fresh each time from
  recent telemetry (`.synlynk/telemetry.json`) rather than persisting an
  inferred value, so behavior change is reflected without a stale cache.
- **Developer segment sets entry point + skip rules, not just tone.**
  `segment` (`novice | skeptic | accelerant | architect`) is inferred the
  same way as stage and is independently overridable. A `skeptic` or
  `architect` segment entering fresh skips `onboarding` and starts at
  `sounding_board`; an `accelerant` skips straight to `policy_maker`-flavored
  framing. This is a starting-point/skip-rule table, not a tone change.
- **Significance tiers gate content, not frequency.** Every fence still
  renders (frequency is the existing cost-fence cadence, untouched);
  `routine | notable | milestone` controls how much "voice" content is
  attached. `routine` gets a short generic line or nothing (depending on
  `voice_density`); `milestone` is the only tier eligible for `remix` mode.
- **Built-in themes are generic pastiche archetypes, not franchise content.**
  No literal franchise names, trademarks, or copyrighted dialogue ship with
  synlynk. The theme *mechanism* is pluggable (Section 5) so the community
  can author and load franchise-flavored packs at their own legal risk —
  synlynk itself never ships or endorses copyrighted-universe content.
- **Content generation is hybrid.** Static template tables are the default
  (zero cost, deterministic). `remix` mode is opt-in and restricted to
  `milestone`-significance events, routed through the existing harness-exec
  path and logged through the existing cost-log mechanism — no hidden cost,
  no new LLM-client dependency.
- **Surface is terminal/CLI only.** No Vizor UI in this spec (matches the
  Configurability Framework's own non-goal).
- **`Stage` is distinct from `onboarding_state.py`'s 10-stage FTUE model.**
  The two are not merged; a user can be in any FTUE onboarding stage and any
  Companion acceptance-ladder stage independently.

## 3. Framework registration

`synlynk/companion.py` registers itself at import time:

```python
from synlynk.features.registry import FeatureSpec, register_feature

register_feature(FeatureSpec(
    name="companion",
    extra_name=None,          # remix mode reuses existing harness-dispatch
                               # exec path; no new pip dependency, so Layer 1
                               # ("dependency presence") is always satisfied.
    import_probe=lambda: True,
    settings_schema=COMPANION_SETTINGS_SCHEMA,
    default_enabled=False,    # opt-in, matches Layer 2's fail-closed default
    supports_packs=True,
    pack_loader=load_theme_pack,
))
```

`synlynk.companion` is added to `_FEATURE_MODULES` in
`synlynk/features/__init__.py` per the framework's bootstrap-hook
requirement, so `load_all_features()` at CLI startup picks it up.

`COMPANION_SETTINGS_SCHEMA` (validated via `config_schema.py`'s existing
`validate()`/`validate_fields()` helpers):

| Key | Type | Default | Notes |
| --- | --- | --- | --- |
| `stage` | enum or `null` | `null` (auto-infer) | one of the six stages; explicit override |
| `theme` | string | `"standard"` | built-in archetype name or a discovered pack's `name` |
| `voice_density` | enum | `"full"` | `full \| low \| off` |
| `remix` | enum | `"off"` | `off \| milestone_only` |
| `segment` | enum or `null` | `null` (auto-infer) | one of the four segments; explicit override |
| `domain_vocab` | object | `{}` | flat `{term: replacement}` string map |

Resulting `.synlynk/features.json` entry example:

```json
{
  "companion": {
    "enabled": true,
    "settings": {
      "theme": "stoic_mentor",
      "voice_density": "low",
      "remix": "milestone_only",
      "domain_vocab": { "story": "campaign", "deploy": "launch" }
    }
  }
}
```

## 4. Fence composition

`render_task_fence()` (`synlynk/fencing.py`) gains one internal call at the
top, before it builds `lines`:

```python
def render_task_fence(data: FenceData) -> str:
    from synlynk import companion
    companion.maybe_add_hint(data)
    ...  # unchanged rendering below, now sees any hint companion appended
```

`companion.maybe_add_hint(data: FenceData) -> None`:
1. Returns immediately (no-op) if `is_feature_enabled("companion")` is
   `False` — this is the fast path for every caller that hasn't opted in,
   and the three existing call sites (`dispatch.py` x2, `cli.py` x1) need
   no changes.
2. Computes significance tier from `data.kind`/`data.cost_usd`/`data.label`
   heuristics (e.g. a job-complete fence with `cost_usd` above a rolling
   median is `notable`; a fence tagged with specific milestone markers —
   release cut, epic close — is `milestone`; everything else is `routine`).
3. Resolves `stage`/`segment`/`theme`/`voice_density`/`remix` from settings
   (explicit override, else auto-inferred).
4. If `voice_density == "off"`, or tier is `routine` and `voice_density ==
   "low"`, returns without appending anything.
5. Composes one line: template lookup by `(theme, stage, tier)`, or — only
   when `remix == "milestone_only"` and tier is `milestone` — a harness-exec
   remix call using the template line as a seed/constraint.
6. Applies the `domain_vocab` substitution pass (Section 5) to the composed
   line.
7. Appends the result to `data.hints`, so it renders as an existing `tip:`
   line inside the existing bordered block — no new rendering code path.

This is Companion's own composition pipeline, as scoped by the
Configurability Framework's DECIDE-panel correction: `discover_packs()`
only locates pack files; it has no opinion on fence composition.

## 5. Theme packs

Built-in archetypes (`"standard"` plus 2-3 generic, IP-safe pastiche
archetypes — e.g. `stoic_mentor`, `chipper_copilot`, `gruff_veteran`) are
Python dict literals inside `synlynk/companion.py`:
`{stage: {tier: [line, ...]}}` per archetype.

Community/BYO themes are JSON files discovered via
`discover_packs("companion")` (scans `.synlynk/packs/companion/*.json` plus
any `pack_paths` entries in Companion's own settings) and parsed by
`load_theme_pack(path) -> dict`, validating against the same
`{stage: {tier: [line, ...]}}` shape using `config_schema.py`'s hand-rolled
helpers. A pack's top-level `name` field is what a user sets `theme` to;
setting `theme` to a name that resolves to neither a built-in archetype nor
a discovered pack falls back to `"standard"` with a one-time warning on the
next CLI invocation (not a hard error — fail-open to the safe default here
is about availability, not security, unlike Layer 2's fail-closed on/off
gate).

## 6. Domain vocabulary

`domain_vocab` is a flat `{term: replacement}` dict. Applied as the last
step of composition (Section 4, step 6), over the fully composed line
(template or remix output — vocabulary substitution doesn't care which
produced the text):

- Match whole words only (word-boundary regex), case-insensitive matching,
  case-preserving replacement is not attempted — the replacement string is
  inserted verbatim as configured.
- Keys are applied longest-first, so a multi-word key (`"pull request"`)
  doesn't get pre-empted by a shorter one (`"pull"`) matching part of it
  first.
- No recursive substitution: a replacement's own text is never re-scanned
  against the table in the same pass.
- Managed via `synlynk config feature companion vocab set|list|remove <term>
  [<replacement>]` (Section 7) rather than the generic `set` command, since
  it's a nested structure the generic flat-key setter doesn't handle.

## 7. CLI surface

Inherited from the framework, unchanged:
```
synlynk config feature companion enable|disable
synlynk config feature companion set <key> <value>   # stage/theme/voice_density/remix/segment
synlynk config feature companion show
synlynk config feature companion pack add <path>
```

Companion-owned addition for the nested `domain_vocab` setting:
```
synlynk config feature companion vocab set <term> <replacement>
synlynk config feature companion vocab remove <term>
synlynk config feature companion vocab list
```

## 8. Compatibility

- `render_task_fence()`'s signature and output shape are unchanged for every
  existing caller when Companion is disabled (the default) — `maybe_add_hint`
  is a no-op and `data.hints` is whatever the caller already set.
- `NudgeData`/`render_nudge_fence()` (workspace-agent nudges) are untouched;
  Companion only hooks into the cost-fence path.
- No existing `FenceData` call site changes.

## 9. Testing

- `tests/test_companion.py`:
  - `maybe_add_hint()` no-ops when `companion` is disabled — `data.hints`
    unchanged.
  - Significance-tier heuristic: a table of `(kind, cost_usd, label) →
    expected tier` cases.
  - Stage/segment resolution: explicit override wins; absent override, a
    fixed telemetry fixture produces the expected inferred value.
  - `voice_density` gating: `off` never appends; `low` only appends at
    `notable`/`milestone`; `full` always appends (down to `routine`).
  - Template composition: `(theme, stage, tier)` resolves to a line from
    the expected archetype table; an unknown `theme` falls back to
    `"standard"` with the one-time-warning behavior.
  - Domain vocabulary: longest-key-first ordering, word-boundary-only
    matching, no recursive substitution, applied identically to a
    template-sourced and a (mocked) remix-sourced line.
  - `remix == "milestone_only"` only triggers a harness-exec call at
    `milestone` tier, never at `routine`/`notable`.
- `tests/test_companion_packs.py`: `load_theme_pack()` round-trips a valid
  pack file; rejects a pack missing the `name` field or with a malformed
  `{stage: {tier: [...]}}` shape, using the same error type
  `config_schema.py` raises for an invalid `workspace.json`.
- `tests/test_cli_config_feature_companion.py`: `vocab set/remove/list`
  round-trip against a temp `features.json`.

## 10. Out of scope

- Any FTUE onboarding-journey redesign (deferred per the original
  brainstorm's scope decision).
- Vizor UI surface for Companion settings.
- A build-time manifest/allowlist beyond the framework's pip-extra layer.
- Designing the Harness Context Compaction Protocol or Herdr Customizations
  specs — each is its own document, registering independently against the
  same Configurability Framework.
