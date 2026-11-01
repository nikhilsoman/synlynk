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

**Hook-seam correction (DECIDE panel, 2026-10-31):** a named `from synlynk
import companion` inside `fencing.py` — even function-local, even though it
avoids a module-load-time circular import — gives the generic fencing
primitive a hardcoded dependency on one specific feature, and risks
re-entrancy if a future contributor's composition logic itself triggers a
fence render. Instead, `fencing.py` exposes a generic, feature-agnostic
registration seam:

```python
# synlynk/fencing.py
_HINT_CONTRIBUTORS: list[Callable[[FenceData], None]] = []

def register_hint_contributor(fn: Callable[[FenceData], None]) -> None:
    """Any enabled feature can register a callback that may append to
    FenceData.hints. fencing.py never imports or names a contributor."""
    _HINT_CONTRIBUTORS.append(fn)

def render_task_fence(data: FenceData) -> str:
    for contributor in _HINT_CONTRIBUTORS:
        contributor(data)
    ...  # unchanged rendering below, now sees any hints contributors appended
```

`synlynk/companion.py` calls `register_hint_contributor(maybe_add_hint)` at
import time (inside the same module-load block that calls
`register_feature(...)`, Section 3) — so wiring happens through the same
bootstrap path (`load_all_features()`) the Configurability Framework already
defines, and `fencing.py` stays zero-call-site-changed for every existing
caller while never naming "companion" anywhere in its own source.

`maybe_add_hint(data: FenceData) -> None` (Companion's own contributor
callback):
1. Returns immediately (no-op) if `is_feature_enabled("companion")` is
   `False` — the fast path for every caller that hasn't opted in.
2. Computes significance tier from `data.kind`/`data.cost_usd`/`data.label`
   heuristics (e.g. a job-complete fence with `cost_usd` above a rolling
   median is `notable`; a fence tagged with specific milestone markers —
   release cut, epic close — is `milestone`; everything else is `routine`).
3. Resolves `stage`/`segment`/`theme`/`voice_density`/`remix` from settings
   (explicit override, else auto-inferred — see Section 4a on inference
   timing).
4. If `voice_density == "off"`, or tier is `routine` and `voice_density ==
   "low"`, returns without appending anything.
5. Composes one line: template lookup by `(theme, stage, tier)`, or — only
   when `remix == "milestone_only"` and tier is `milestone` — a harness-exec
   remix call using the template line as a seed/constraint (see Section 6
   for how `domain_vocab` interacts with remix specifically).
6. Applies the `domain_vocab` substitution pass (Section 6) to
   template-sourced lines only.
7. Appends the result to `data.hints`, so it renders as an existing `tip:`
   line inside the existing bordered block — no new rendering code path.

This is Companion's own composition pipeline, as scoped by the
Configurability Framework's DECIDE-panel correction: `discover_packs()`
only locates pack files; it has no opinion on fence composition.

### 4a. Stage/segment inference timing

**Consistency fix (DECIDE panel, 2026-10-31):** inferring stage/segment
fresh on every individual fence call creates a real bug, not just a
performance question — an estimate fence and a completion fence within the
*same command* can read telemetry at different moments and infer different
values, producing two different voices for one command's output. Fix:
stage/segment inference is **pinned once per command invocation** (cached
for the lifetime of that one `synlynk <command>` process/call), computed
fresh on every new command — never persisted across commands, never cached
longer than one invocation. This keeps the "never stale, never advances on
elapsed time" property while eliminating within-command inconsistency.
Implementation: a process-local (not disk-persisted) memo keyed by
`os.getpid()`-scoped module state, cleared implicitly on process exit.

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
helpers. A pack's top-level `name` field is what a user sets `theme` to.

**Named Layer-3 exception (DECIDE panel, 2026-10-31):** setting `theme` to a
name that resolves to neither a built-in archetype nor a discovered pack
falls back to `"standard"`. This is an explicit, documented departure from
the Configurability Framework's Layer-2 fail-closed convention (missing/bad
config → disabled) — here, fail-*open* to the safe default is correct
because an unresolvable theme is a content-availability gap, not a
security or enablement concern; disabling Companion entirely over a typo'd
theme name would be a worse outcome than silently using `standard`. The
warning is **not** one-time: it repeats on every affected invocation (not
suppressed after the first), so a persistently misconfigured theme name
doesn't quietly keep producing the wrong voice indefinitely without the
user noticing.

## 6. Domain vocabulary

`domain_vocab` is a flat `{term: replacement}` dict.

**Scope correction (DECIDE panel, 2026-10-31):** a blind post-substitution
pass over *remix* output is unsafe — remix text is free-form harness-exec
prose, not text under this design's control, so a vocab key can collide
with an ordinary word the LLM happened to use in an unrelated sense and
silently rewrite it. The post-substitution pass therefore applies **only to
template-sourced lines** (step 6 of Section 4's composition, for the
non-remix path). For remix-generated lines, `domain_vocab` is instead
passed as a generation constraint inside the remix prompt itself (e.g. "use
these workspace terms where natural: {domain_vocab}") — the harness
produces text that already reflects the vocabulary, rather than having its
output edited afterward.

For the template path, the substitution pass is applied over the fully
composed template line:

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
  existing caller. With no contributors registered (Companion disabled or
  `synlynk.companion` never imported), `_HINT_CONTRIBUTORS` is empty and the
  loop is a no-op — identical output to today.
- `fencing.py` gains the generic `register_hint_contributor()` seam but adds
  no new import of, or reference to, any specific feature.
- `NudgeData`/`render_nudge_fence()` (workspace-agent nudges) are untouched;
  Companion only hooks into the cost-fence path.
- No existing `FenceData` call site changes.

## 9. Testing

- `tests/test_fencing_hint_contributors.py`:
  - `register_hint_contributor()` / `render_task_fence()` round-trip: a
    registered callback is invoked and can append to `data.hints`; an
    unregistered feature (empty contributor list) renders identically to
    today's output.
  - `fencing.py` imports no feature module by name (a static grep-style
    assertion that `companion`/`context_compaction`/`herdr_cockpit` don't
    appear as import targets in `fencing.py`'s source).
- `tests/test_companion.py`:
  - `maybe_add_hint()` no-ops when `companion` is disabled — `data.hints`
    unchanged.
  - Significance-tier heuristic: a table of `(kind, cost_usd, label) →
    expected tier` cases.
  - Stage/segment resolution: explicit override wins; absent override, a
    fixed telemetry fixture produces the expected inferred value.
  - Stage/segment pinning: two fence calls within the same simulated
    command invocation (same pinned-inference scope) resolve to the same
    value even when the underlying telemetry fixture changes between the
    two calls; a new invocation re-infers.
  - `voice_density` gating: `off` never appends; `low` only appends at
    `notable`/`milestone`; `full` always appends (down to `routine`).
  - Template composition: `(theme, stage, tier)` resolves to a line from
    the expected archetype table; an unknown `theme` falls back to
    `"standard"` with the warning firing on every affected call (not
    suppressed after the first).
  - Domain vocabulary (template path only): longest-key-first ordering,
    word-boundary-only matching, no recursive substitution.
  - Domain vocabulary (remix path): the remix prompt sent to harness-exec
    includes the configured `domain_vocab` as a constraint; the
    post-substitution pass is never applied to remix output (asserted by
    mocking harness-exec to return text containing a vocab key and
    confirming it is left unmodified).
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
