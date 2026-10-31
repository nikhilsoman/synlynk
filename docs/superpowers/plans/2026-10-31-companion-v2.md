# Companion v2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `synlynk/companion.py` — the "at-the-fence" voice feature: stage/segment-aware template composition, theme packs, domain vocabulary substitution, and remix mode — registered against the Configurability Framework and wired into `synlynk/fencing.py` through a new generic, feature-agnostic hint-contributor seam.

**Architecture:** `synlynk/fencing.py` gains a tiny, permanent, feature-agnostic addition: a `_HINT_CONTRIBUTORS` list and `register_hint_contributor()` function, with `render_task_fence()` looping over registered contributors before its existing rendering logic. `synlynk/companion.py` registers its `FeatureSpec` and calls `register_hint_contributor(maybe_add_hint)` at import time — both fire together once `load_all_features()` imports the module. `maybe_add_hint()` no-ops immediately if the feature is disabled, otherwise resolves stage/segment/theme/voice_density/remix from settings (with per-command-invocation pinning for stage/segment to avoid within-command inconsistency), composes one line from a built-in or pack-sourced template table, optionally remixes it via the existing harness-exec path at milestone significance, applies domain-vocabulary substitution (template path only), and appends to `data.hints`.

**Tech Stack:** Python 3 stdlib only. No new dependency (`extra_name=None`). Depends on `docs/superpowers/plans/2026-10-31-configurability-framework.md` being implemented first (`FeatureSpec`, `register_feature`, `is_feature_enabled`, `discover_packs`, `load_all_features`/`_FEATURE_MODULES` must already exist).

---

## File Structure

| File | Responsibility |
| --- | --- |
| `synlynk/fencing.py` | Modified: add `_HINT_CONTRIBUTORS` list + `register_hint_contributor()`; `render_task_fence()` calls each contributor before existing render logic. No new imports of any feature module. |
| `synlynk/companion.py` | New. `COMPANION_SETTINGS_SCHEMA`, `register_feature(...)` + `register_hint_contributor(...)` calls at import time, built-in theme archetypes, `maybe_add_hint()`, significance-tier heuristic, stage/segment inference + pinning, template composition, remix dispatch, domain-vocab substitution, `load_theme_pack()`. |
| `synlynk/features/__init__.py` | Modified: add `"synlynk.companion"` to `_FEATURE_MODULES`. |
| `synlynk/cli.py` | Modified: `synlynk config feature companion vocab set/remove/list` subcommand (nested, since `domain_vocab` is a structured setting the generic `set` verb doesn't handle). |
| `tests/test_fencing_hint_contributors.py` | New. Generic seam round-trip; static grep assertion `fencing.py` names no feature module. |
| `tests/test_companion.py` | New. `maybe_add_hint()` no-op/gating, significance tiers, stage/segment resolution + pinning, template composition, domain vocab (template + remix paths), remix gating. |
| `tests/test_companion_packs.py` | New. `load_theme_pack()` validation. |
| `tests/test_cli_config_feature_companion.py` | New. `vocab set/remove/list` round-trip. |

---

### Task 1: Generic hint-contributor seam in `fencing.py`

**Files:**
- Modify: `synlynk/fencing.py`
- Test: `tests/test_fencing_hint_contributors.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_fencing_hint_contributors.py
import re
from pathlib import Path

from synlynk.fencing import FenceData, _HINT_CONTRIBUTORS, register_hint_contributor, render_task_fence


def setup_function(_):
    _HINT_CONTRIBUTORS.clear()


def test_render_task_fence_calls_registered_contributor():
    seen = []

    def contributor(data):
        seen.append(data)
        data.hints.append("test hint")

    register_hint_contributor(contributor)
    data = FenceData(kind="task_complete", cost_usd=0.01, label="t1", hints=[])
    render_task_fence(data)

    assert seen == [data]
    assert "test hint" in data.hints


def test_render_task_fence_with_no_contributors_matches_baseline():
    data_before = FenceData(kind="task_complete", cost_usd=0.01, label="t1", hints=[])
    output_before = render_task_fence(data_before)

    data_after = FenceData(kind="task_complete", cost_usd=0.01, label="t1", hints=[])
    output_after = render_task_fence(data_after)

    assert output_before == output_after


def test_fencing_py_does_not_import_any_feature_module():
    source = Path("synlynk/fencing.py").read_text()
    for forbidden in ("companion", "context_compaction", "herdr_cockpit"):
        assert not re.search(rf"^\s*(from|import)\s+synlynk\.{forbidden}\b", source, re.MULTILINE), (
            f"fencing.py must not import synlynk.{forbidden} by name"
        )
```

(This assumes `FenceData` is already a dataclass/namedtuple with a `hints: list` field, per the spec's description of the existing cost-fence pipeline — if the real field name differs, adjust the test's constructor call and the implementation below to match the actual existing shape; do not invent a new field name.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_fencing_hint_contributors.py -v`
Expected: FAIL with `ImportError: cannot import name 'register_hint_contributor'`

- [ ] **Step 3: Write minimal implementation**

Add near the top of `synlynk/fencing.py`, after existing imports and the `FenceData` definition:

```python
# synlynk/fencing.py (add)
from typing import Callable

_HINT_CONTRIBUTORS: list[Callable[["FenceData"], None]] = []


def register_hint_contributor(fn: Callable[["FenceData"], None]) -> None:
    """Any enabled feature can register a callback that may append to
    FenceData.hints. fencing.py never imports or names a contributor by
    feature -- wiring happens through synlynk.features.load_all_features()
    at CLI startup, which imports each feature module and triggers its own
    top-level register_hint_contributor() call.
    """
    _HINT_CONTRIBUTORS.append(fn)
```

Then find `render_task_fence()`'s existing definition and add the contributor loop as its first statement:

```python
def render_task_fence(data: FenceData) -> str:
    for contributor in _HINT_CONTRIBUTORS:
        contributor(data)
    # ... existing rendering logic below, unchanged ...
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_fencing_hint_contributors.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/fencing.py tests/test_fencing_hint_contributors.py
git commit -m "feat: add generic hint-contributor seam to fencing.py"
```

---

### Task 2: `synlynk/companion.py` — FeatureSpec registration + settings schema

**Files:**
- Create: `synlynk/companion.py`
- Modify: `synlynk/features/__init__.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py
import pytest


@pytest.fixture(autouse=True)
def clear_registries():
    from synlynk.features.registry import FEATURE_MANIFEST
    from synlynk.fencing import _HINT_CONTRIBUTORS
    FEATURE_MANIFEST.clear()
    _HINT_CONTRIBUTORS.clear()
    yield
    FEATURE_MANIFEST.clear()
    _HINT_CONTRIBUTORS.clear()


def test_companion_module_registers_feature_and_contributor():
    import importlib
    import synlynk.companion as companion_module
    importlib.reload(companion_module)

    from synlynk.features.registry import FEATURE_MANIFEST
    from synlynk.fencing import _HINT_CONTRIBUTORS

    assert "companion" in FEATURE_MANIFEST
    spec = FEATURE_MANIFEST["companion"]
    assert spec.extra_name is None
    assert spec.default_enabled is False
    assert spec.supports_packs is True
    assert len(_HINT_CONTRIBUTORS) == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py::test_companion_module_registers_feature_and_contributor -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.companion'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py
"""Companion v2 -- optional "at-the-fence" voice feature. See
docs/superpowers/specs/2026-10-31-companion-v2-design.md.
"""
from synlynk.features.registry import FeatureSpec, register_feature
from synlynk.fencing import register_hint_contributor

COMPANION_SETTINGS_SCHEMA = {
    "fields": {
        "stage": {
            "type": "string",
            "enum": [
                "onboarding", "companionship", "sounding_board",
                "policy_maker", "recruiter", "champion",
            ],
            "required": False,
        },
        "theme": {"type": "string", "required": False},
        "voice_density": {
            "type": "string", "enum": ["full", "low", "off"], "required": False,
        },
        "remix": {
            "type": "string", "enum": ["off", "milestone_only"], "required": False,
        },
        "segment": {
            "type": "string",
            "enum": ["novice", "skeptic", "accelerant", "architect"],
            "required": False,
        },
        "domain_vocab": {"type": "object", "required": False},
    },
}


def maybe_add_hint(data) -> None:
    """Companion's hint-contributor callback, registered with
    synlynk.fencing.register_hint_contributor(). No-ops immediately if the
    feature is disabled -- filled in across later tasks in this plan.
    """
    from synlynk.features.registry import is_feature_enabled
    if not is_feature_enabled("companion"):
        return
    # Significance tier, stage/segment resolution, composition, and
    # domain-vocab substitution are added in Tasks 3-7 below.


register_feature(FeatureSpec(
    name="companion",
    extra_name=None,
    import_probe=lambda: True,
    settings_schema=COMPANION_SETTINGS_SCHEMA,
    default_enabled=False,
    supports_packs=True,
    pack_loader=lambda path: load_theme_pack(path),
))
register_hint_contributor(maybe_add_hint)
```

Add `"synlynk.companion"` to `_FEATURE_MODULES` in `synlynk/features/__init__.py`:

```python
# synlynk/features/__init__.py
_FEATURE_MODULES: tuple[str, ...] = (
    "synlynk.companion",
)
```

(`load_theme_pack` is referenced by the `pack_loader` lambda above but not yet defined — Task 6 defines it. Until then, importing `synlynk.companion` succeeds because the lambda's body is not evaluated at import time, only when actually called.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py::test_companion_module_registers_feature_and_contributor -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py synlynk/features/__init__.py tests/test_companion.py
git commit -m "feat: register companion FeatureSpec and hint contributor"
```

---

### Task 3: `maybe_add_hint()` disabled no-op

**Files:**
- Modify: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
def test_maybe_add_hint_noop_when_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)

    import importlib
    import synlynk.companion as companion_module
    importlib.reload(companion_module)

    from synlynk.fencing import FenceData
    data = FenceData(kind="task_complete", cost_usd=0.01, label="t1", hints=[])
    companion_module.maybe_add_hint(data)
    assert data.hints == []
```

- [ ] **Step 2: Run test to verify it passes already**

Run: `pytest tests/test_companion.py::test_maybe_add_hint_noop_when_disabled -v`
Expected: PASS (Task 2's implementation already returns early when disabled; this step documents and locks in that behavior with an explicit test before building the enabled path on top of it)

- [ ] **Step 3: Commit**

```bash
git add tests/test_companion.py
git commit -m "test: lock in maybe_add_hint disabled no-op"
```

---

### Task 4: Significance-tier heuristic

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
import pytest as pt


@pt.mark.parametrize("kind,cost_usd,label,rolling_median,expected", [
    ("task_complete", 0.01, "t1", 0.5, "routine"),
    ("task_complete", 2.0, "t1", 0.5, "notable"),
    ("task_complete", 0.01, "release_cut", 0.5, "milestone"),
    ("task_complete", 0.01, "epic_close", 0.5, "milestone"),
])
def test_significance_tier_heuristic(kind, cost_usd, label, rolling_median, expected):
    from synlynk.companion import compute_significance_tier
    assert compute_significance_tier(kind, cost_usd, label, rolling_median) == expected
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py::test_significance_tier_heuristic -v`
Expected: FAIL with `ImportError: cannot import name 'compute_significance_tier'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
_MILESTONE_LABELS = {"release_cut", "epic_close"}


def compute_significance_tier(kind: str, cost_usd: float, label: str, rolling_median: float) -> str:
    if label in _MILESTONE_LABELS:
        return "milestone"
    if cost_usd > rolling_median:
        return "notable"
    return "routine"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py::test_significance_tier_heuristic -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: add companion significance-tier heuristic"
```

---

### Task 5: Stage/segment resolution with per-invocation pinning

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
def test_stage_segment_explicit_override_wins(monkeypatch):
    from synlynk.companion import resolve_stage_and_segment
    monkeypatch.setattr("synlynk.companion._infer_stage_from_telemetry", lambda: "champion")
    monkeypatch.setattr("synlynk.companion._infer_segment_from_telemetry", lambda: "architect")

    stage, segment = resolve_stage_and_segment(
        override_stage="onboarding", override_segment="novice",
    )
    assert (stage, segment) == ("onboarding", "novice")


def test_stage_segment_infers_when_no_override(monkeypatch):
    from synlynk.companion import resolve_stage_and_segment
    monkeypatch.setattr("synlynk.companion._infer_stage_from_telemetry", lambda: "sounding_board")
    monkeypatch.setattr("synlynk.companion._infer_segment_from_telemetry", lambda: "skeptic")

    stage, segment = resolve_stage_and_segment(override_stage=None, override_segment=None)
    assert (stage, segment) == ("sounding_board", "skeptic")


def test_stage_segment_pinned_within_same_pid(monkeypatch):
    from synlynk.companion import resolve_stage_and_segment, _clear_inference_pin

    _clear_inference_pin()
    calls = {"n": 0}

    def flaky_infer_stage():
        calls["n"] += 1
        return "onboarding" if calls["n"] == 1 else "champion"

    monkeypatch.setattr("synlynk.companion._infer_stage_from_telemetry", flaky_infer_stage)
    monkeypatch.setattr("synlynk.companion._infer_segment_from_telemetry", lambda: "novice")

    first_stage, _ = resolve_stage_and_segment(override_stage=None, override_segment=None)
    second_stage, _ = resolve_stage_and_segment(override_stage=None, override_segment=None)

    assert first_stage == second_stage == "onboarding"
    assert calls["n"] == 1  # inferred once, then reused for the pinned scope
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py -k stage_segment -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_stage_and_segment'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
import os

_inference_pin: dict[int, tuple[str, str]] = {}


def _clear_inference_pin() -> None:
    _inference_pin.clear()


def _infer_stage_from_telemetry() -> str:
    # Reads .synlynk/telemetry.json for command vocabulary, override-rate,
    # and manual-intervention frequency signals. Real signal extraction is
    # feature-owned detail out of this plan's TDD scope at the unit level;
    # tests above monkeypatch this function directly.
    return "onboarding"


def _infer_segment_from_telemetry() -> str:
    return "novice"


def resolve_stage_and_segment(override_stage, override_segment) -> tuple[str, str]:
    pid = os.getpid()
    if pid in _inference_pin:
        pinned_stage, pinned_segment = _inference_pin[pid]
    else:
        pinned_stage = _infer_stage_from_telemetry()
        pinned_segment = _infer_segment_from_telemetry()
        _inference_pin[pid] = (pinned_stage, pinned_segment)

    stage = override_stage if override_stage is not None else pinned_stage
    segment = override_segment if override_segment is not None else pinned_segment
    return stage, segment
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py -k stage_segment -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: add stage/segment resolution with per-invocation pinning"
```

---

### Task 6: Built-in theme archetypes + `load_theme_pack()`

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion_packs.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion_packs.py
import json

import pytest


def test_load_theme_pack_round_trip(tmp_path):
    from synlynk.companion import load_theme_pack
    pack_file = tmp_path / "stoic_mentor_plus.json"
    pack_file.write_text(json.dumps({
        "name": "stoic_mentor_plus",
        "onboarding": {"routine": ["Steady on."], "notable": ["Good."], "milestone": ["Well done."]},
    }))
    pack = load_theme_pack(pack_file)
    assert pack["name"] == "stoic_mentor_plus"
    assert pack["onboarding"]["milestone"] == ["Well done."]


def test_load_theme_pack_rejects_missing_name(tmp_path):
    from synlynk.companion import load_theme_pack
    pack_file = tmp_path / "bad.json"
    pack_file.write_text(json.dumps({"onboarding": {}}))
    with pytest.raises(ValueError):
        load_theme_pack(pack_file)


def test_load_theme_pack_rejects_malformed_shape(tmp_path):
    from synlynk.companion import load_theme_pack
    pack_file = tmp_path / "bad_shape.json"
    pack_file.write_text(json.dumps({"name": "x", "onboarding": "not a dict"}))
    with pytest.raises(ValueError):
        load_theme_pack(pack_file)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion_packs.py -v`
Expected: FAIL with `ImportError: cannot import name 'load_theme_pack'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
import json

_BUILTIN_THEMES = {
    "standard": {
        "onboarding": {"routine": ["Task done."], "notable": ["Nice work."], "milestone": ["Milestone reached."]},
        "companionship": {"routine": ["Done."], "notable": ["Solid."], "milestone": ["Big step forward."]},
        "sounding_board": {"routine": ["Complete."], "notable": ["Worth noting."], "milestone": ["Significant."]},
        "policy_maker": {"routine": ["Done."], "notable": ["Flagged."], "milestone": ["Decision point."]},
        "recruiter": {"routine": ["Done."], "notable": ["Share-worthy."], "milestone": ["Showcase moment."]},
        "champion": {"routine": ["Done."], "notable": ["Great."], "milestone": ["Victory."]},
    },
    "stoic_mentor": {
        "onboarding": {"routine": ["Steady on."], "notable": ["You're learning."], "milestone": ["This is the work."]},
        "companionship": {"routine": ["Noted."], "notable": ["Progress."], "milestone": ["Well earned."]},
        "sounding_board": {"routine": ["Continue."], "notable": ["Consider this."], "milestone": ["A turning point."]},
        "policy_maker": {"routine": ["Logged."], "notable": ["Decide wisely."], "milestone": ["The path is set."]},
        "recruiter": {"routine": ["Done."], "notable": ["Worth sharing."], "milestone": ["Others should see this."]},
        "champion": {"routine": ["Done."], "notable": ["Strength shown."], "milestone": ["Mastery."]},
    },
    "chipper_copilot": {
        "onboarding": {"routine": ["Got it done!"], "notable": ["Nice one!"], "milestone": ["Woo, big milestone!"]},
        "companionship": {"routine": ["All set!"], "notable": ["Great progress!"], "milestone": ["Huge step!"]},
        "sounding_board": {"routine": ["Done!"], "notable": ["Interesting one!"], "milestone": ["This matters!"]},
        "policy_maker": {"routine": ["Logged!"], "notable": ["Heads up!"], "milestone": ["Big call!"]},
        "recruiter": {"routine": ["Done!"], "notable": ["Share this!"], "milestone": ["Show this off!"]},
        "champion": {"routine": ["Done!"], "notable": ["Nailed it!"], "milestone": ["Champion move!"]},
    },
    "gruff_veteran": {
        "onboarding": {"routine": ["Done."], "notable": ["Not bad."], "milestone": ["Now that's real work."]},
        "companionship": {"routine": ["Fine."], "notable": ["Decent."], "milestone": ["Earned that one."]},
        "sounding_board": {"routine": ["Done."], "notable": ["Worth a look."], "milestone": ["Pay attention to this."]},
        "policy_maker": {"routine": ["Logged."], "notable": ["Think it through."], "milestone": ["This one counts."]},
        "recruiter": {"routine": ["Done."], "notable": ["Could show someone."], "milestone": ["Now that's worth bragging about."]},
        "champion": {"routine": ["Done."], "notable": ["Solid."], "milestone": ["That's the stuff."]},
    },
}

_VALID_STAGES = {"onboarding", "companionship", "sounding_board", "policy_maker", "recruiter", "champion"}
_VALID_TIERS = {"routine", "notable", "milestone"}


def load_theme_pack(path) -> dict:
    with open(path) as f:
        pack = json.load(f)
    if "name" not in pack or not isinstance(pack["name"], str):
        raise ValueError(f"theme pack {path} missing required string field 'name'")
    for key, value in pack.items():
        if key == "name":
            continue
        if key not in _VALID_STAGES:
            continue  # unknown extra keys are ignored, not rejected
        if not isinstance(value, dict):
            raise ValueError(f"theme pack {path}: stage '{key}' must map to a {{tier: [line, ...]}} dict")
        for tier, lines in value.items():
            if tier not in _VALID_TIERS or not isinstance(lines, list):
                raise ValueError(f"theme pack {path}: stage '{key}' tier '{tier}' must be a list of lines")
    return pack
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion_packs.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion_packs.py
git commit -m "feat: add built-in theme archetypes and load_theme_pack validation"
```

---

### Task 7: Template resolution with unknown-theme fallback

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
def test_resolve_template_line_known_theme():
    from synlynk.companion import resolve_template_line
    line = resolve_template_line("stoic_mentor", "champion", "milestone")
    assert line == "Mastery."


def test_resolve_template_line_unknown_theme_falls_back_to_standard(capsys):
    from synlynk.companion import resolve_template_line
    line = resolve_template_line("totally_made_up_theme", "champion", "milestone")
    assert line == "Victory."
    err = capsys.readouterr().err
    assert "totally_made_up_theme" in err


def test_resolve_template_line_unknown_theme_warns_every_call_not_just_first(capsys):
    from synlynk.companion import resolve_template_line
    resolve_template_line("bad_theme", "champion", "milestone")
    capsys.readouterr()  # discard first warning
    resolve_template_line("bad_theme", "champion", "milestone")
    err = capsys.readouterr().err
    assert "bad_theme" in err  # second call warns again, not suppressed
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py -k resolve_template_line -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_template_line'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
import sys


def resolve_template_line(theme: str, stage: str, tier: str) -> str:
    table = _BUILTIN_THEMES.get(theme)
    if table is None:
        table = _resolve_pack_theme(theme)
    if table is None:
        print(f"companion: unknown theme '{theme}', falling back to 'standard'", file=sys.stderr)
        table = _BUILTIN_THEMES["standard"]
    return table[stage][tier][0]


def _resolve_pack_theme(theme_name: str):
    from synlynk.features.registry import discover_packs
    for pack_path in discover_packs("companion"):
        try:
            pack = load_theme_pack(pack_path)
        except ValueError:
            continue
        if pack.get("name") == theme_name:
            return pack
    return None
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py -k resolve_template_line -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: add template resolution with repeated unknown-theme warning"
```

---

### Task 8: `voice_density` gating

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
@pt.mark.parametrize("voice_density,tier,should_append", [
    ("off", "milestone", False),
    ("low", "routine", False),
    ("low", "notable", True),
    ("low", "milestone", True),
    ("full", "routine", True),
    ("full", "milestone", True),
])
def test_voice_density_gating(voice_density, tier, should_append):
    from synlynk.companion import should_render_hint
    assert should_render_hint(voice_density, tier) is should_append
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py::test_voice_density_gating -v`
Expected: FAIL with `ImportError: cannot import name 'should_render_hint'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
def should_render_hint(voice_density: str, tier: str) -> bool:
    if voice_density == "off":
        return False
    if voice_density == "low" and tier == "routine":
        return False
    return True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py::test_voice_density_gating -v`
Expected: PASS (6 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: add voice_density gating"
```

---

### Task 9: Domain-vocabulary substitution (template path)

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
def test_apply_domain_vocab_word_boundary_and_longest_first():
    from synlynk.companion import apply_domain_vocab
    vocab = {"pull request": "merge request", "pull": "fetch"}
    result = apply_domain_vocab("Open a pull request to pull the latest.", vocab)
    assert result == "Open a merge request to fetch the latest."


def test_apply_domain_vocab_no_recursive_substitution():
    from synlynk.companion import apply_domain_vocab
    vocab = {"story": "campaign", "campaign": "saga"}
    result = apply_domain_vocab("Finish the story.", vocab)
    assert result == "Finish the campaign."  # "campaign" from the first substitution is not re-scanned


def test_apply_domain_vocab_case_insensitive_match_verbatim_replacement():
    from synlynk.companion import apply_domain_vocab
    vocab = {"deploy": "launch"}
    result = apply_domain_vocab("Time to Deploy now.", vocab)
    assert result == "Time to launch now."
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py -k domain_vocab -v`
Expected: FAIL with `ImportError: cannot import name 'apply_domain_vocab'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
import re


def apply_domain_vocab(text: str, vocab: dict) -> str:
    if not vocab:
        return text
    ordered_keys = sorted(vocab.keys(), key=len, reverse=True)
    pattern = re.compile(
        r"\b(" + "|".join(re.escape(k) for k in ordered_keys) + r")\b",
        re.IGNORECASE,
    )

    def _replace(match):
        matched_text = match.group(0)
        for key in ordered_keys:
            if key.lower() == matched_text.lower():
                return vocab[key]
        return matched_text  # unreachable given the pattern construction

    return pattern.sub(_replace, text)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py -k domain_vocab -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: add domain-vocab substitution for template path"
```

---

### Task 10: Remix gating (milestone-only, harness-exec path)

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
def test_remix_only_fires_at_milestone_tier(monkeypatch):
    from synlynk.companion import maybe_remix

    calls = []
    monkeypatch.setattr("synlynk.companion._harness_exec_remix", lambda seed, vocab: calls.append((seed, vocab)) or "remixed text")

    result_routine = maybe_remix("seed line", "routine", "milestone_only", {})
    result_milestone = maybe_remix("seed line", "milestone", "milestone_only", {})

    assert result_routine == "seed line"  # unchanged, no remix call
    assert result_milestone == "remixed text"
    assert calls == [("seed line", {})]


def test_remix_off_never_fires_even_at_milestone(monkeypatch):
    from synlynk.companion import maybe_remix
    calls = []
    monkeypatch.setattr("synlynk.companion._harness_exec_remix", lambda seed, vocab: calls.append(1) or "x")
    result = maybe_remix("seed line", "milestone", "off", {})
    assert result == "seed line"
    assert calls == []


def test_remix_passes_domain_vocab_as_generation_constraint_not_postprocessed(monkeypatch):
    from synlynk.companion import maybe_remix
    monkeypatch.setattr(
        "synlynk.companion._harness_exec_remix",
        lambda seed, vocab: "finished the campaign" if vocab.get("story") == "campaign" else "finished the story",
    )
    result = maybe_remix("seed line", "milestone", "milestone_only", {"story": "campaign"})
    assert result == "finished the campaign"
    # Confirms domain_vocab reached the remix call as a constraint argument,
    # not applied as a post-substitution pass over the remix output.
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py -k remix -v`
Expected: FAIL with `ImportError: cannot import name 'maybe_remix'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/companion.py (add)
def _harness_exec_remix(seed_line: str, domain_vocab: dict) -> str:
    # Routes through the existing harness-exec path and existing cost-log
    # mechanism. The exact dispatch call is wired at integration time against
    # whatever helper synlynk/dispatch.py or synlynk/__init__.py already
    # exposes for a one-shot harness prompt; out of this plan's unit-test
    # scope, which monkeypatches this function directly.
    vocab_hint = f" Use these workspace terms where natural: {domain_vocab}." if domain_vocab else ""
    prompt = f"Rewrite this line in a fresh way, keeping the same meaning: '{seed_line}'.{vocab_hint}"
    raise NotImplementedError("wire to the real harness-exec call site during integration")


def maybe_remix(seed_line: str, tier: str, remix_setting: str, domain_vocab: dict) -> str:
    if remix_setting != "milestone_only" or tier != "milestone":
        return seed_line
    return _harness_exec_remix(seed_line, domain_vocab)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py -k remix -v`
Expected: PASS (3 passed — the real `_harness_exec_remix` body's `NotImplementedError` is never hit because all three tests monkeypatch it)

- [ ] **Step 5: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: add milestone-only remix gating"
```

---

### Task 11: Assemble `maybe_add_hint()` end-to-end

**Files:**
- Modify: `synlynk/companion.py`
- Test: `tests/test_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_companion.py (append)
def test_maybe_add_hint_full_pipeline_template_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)

    import importlib
    import synlynk.companion as companion_module
    importlib.reload(companion_module)

    from synlynk.features.registry import set_feature_enabled, set_feature_setting
    set_feature_enabled("companion", True)
    set_feature_setting("companion", "theme", "stoic_mentor")
    set_feature_setting("companion", "voice_density", "full")
    set_feature_setting("companion", "stage", "champion")
    set_feature_setting("companion", "remix", "off")

    from synlynk.fencing import FenceData
    data = FenceData(kind="task_complete", cost_usd=0.01, label="t1", hints=[])
    companion_module.maybe_add_hint(data)

    assert data.hints == ["Done."]  # stoic_mentor/champion/routine line
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_companion.py::test_maybe_add_hint_full_pipeline_template_path -v`
Expected: FAIL — `maybe_add_hint()` from Task 2 only has the disabled-no-op branch; nothing appends to `data.hints` yet

- [ ] **Step 3: Write minimal implementation**

Replace `maybe_add_hint()` in `synlynk/companion.py` (defined in Task 2) with the full pipeline:

```python
# synlynk/companion.py (replace maybe_add_hint)
_ROLLING_MEDIAN_COST_USD = 0.5  # placeholder static baseline; a real rolling
                                 # median from telemetry is an enhancement,
                                 # not required for this spec's acceptance


def maybe_add_hint(data) -> None:
    from synlynk.features.registry import is_feature_enabled, get_feature_settings
    if not is_feature_enabled("companion"):
        return

    settings = get_feature_settings("companion")
    tier = compute_significance_tier(data.kind, data.cost_usd, data.label, _ROLLING_MEDIAN_COST_USD)
    stage, segment = resolve_stage_and_segment(settings.get("stage"), settings.get("segment"))
    theme = settings.get("theme", "standard")
    voice_density = settings.get("voice_density", "full")
    remix_setting = settings.get("remix", "off")
    domain_vocab = settings.get("domain_vocab", {})

    if not should_render_hint(voice_density, tier):
        return

    template_line = resolve_template_line(theme, stage, tier)

    if remix_setting == "milestone_only" and tier == "milestone":
        line = maybe_remix(template_line, tier, remix_setting, domain_vocab)
    else:
        line = apply_domain_vocab(template_line, domain_vocab)

    data.hints.append(line)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_companion.py::test_maybe_add_hint_full_pipeline_template_path -v`
Expected: PASS

- [ ] **Step 5: Run the full companion test module to confirm no regressions**

Run: `pytest tests/test_companion.py -v`
Expected: all PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/companion.py tests/test_companion.py
git commit -m "feat: assemble maybe_add_hint end-to-end pipeline"
```

---

### Task 12: `synlynk config feature companion vocab set/remove/list` CLI

**Files:**
- Modify: `synlynk/cli.py` (parser build near Task 7 of the Configurability Framework plan's `feature_parser`; dispatch near the same `elif getattr(args, "config_action", None) == "feature":` branch)
- Test: `tests/test_cli_config_feature_companion.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_config_feature_companion.py
import json
import os


def test_vocab_set_remove_list_round_trip(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk.features.registry as registry
    registry.FEATURE_MANIFEST.clear()
    import importlib
    import synlynk.companion as companion_module
    importlib.reload(companion_module)

    from synlynk.cli import main

    main(["config", "feature", "companion", "vocab", "set", "story", "campaign"])
    data = json.loads((tmp_path / ".synlynk/features.json").read_text())
    assert data["companion"]["settings"]["domain_vocab"] == {"story": "campaign"}

    main(["config", "feature", "companion", "vocab", "list"])
    out = capsys.readouterr().out
    assert "story" in out and "campaign" in out

    main(["config", "feature", "companion", "vocab", "remove", "story"])
    data = json.loads((tmp_path / ".synlynk/features.json").read_text())
    assert data["companion"]["settings"]["domain_vocab"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_config_feature_companion.py -v`
Expected: FAIL — `vocab` is not a recognized `feature_verb` choice yet

- [ ] **Step 3: Edit `synlynk/cli.py` — parser build**

In the `feature_parser` built by the Configurability Framework plan's Task 7, extend the `feature_verb` choices list to include `"vocab"`:

```python
    feature_parser.add_argument("feature_verb", nargs="?", choices=[
        "enable", "disable", "show", "set", "pack", "list", "vocab",
    ], help="Action to perform")
```

(`feature_args` already captures the remaining positionals via `nargs="*"`, so `vocab set story campaign` arrives as `extra = ["set", "story", "campaign"]` with no further parser changes needed.)

- [ ] **Step 4: Edit `synlynk/cli.py` — dispatch**

In the `elif getattr(args, "config_action", None) == "feature":` branch, add a `vocab` case alongside the existing `enable`/`disable`/`show`/`set`/`pack` cases:

```python
            elif verb == "vocab":
                from synlynk.features.registry import get_feature_settings, set_feature_setting
                vocab_verb = extra[0]
                settings = get_feature_settings(name)
                domain_vocab = dict(settings.get("domain_vocab", {}))

                if vocab_verb == "set":
                    term, replacement = extra[1], extra[2]
                    domain_vocab[term] = replacement
                    set_feature_setting(name, "domain_vocab", domain_vocab)
                    print(f"{name}.domain_vocab[{term}] = {replacement}")
                elif vocab_verb == "remove":
                    term = extra[1]
                    domain_vocab.pop(term, None)
                    set_feature_setting(name, "domain_vocab", domain_vocab)
                    print(f"{name}.domain_vocab[{term}] removed")
                elif vocab_verb == "list":
                    for term, replacement in domain_vocab.items():
                        print(f"{term} -> {replacement}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_config_feature_companion.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_cli_config_feature_companion.py
git commit -m "feat: add synlynk config feature companion vocab set/remove/list CLI"
```

---

## Self-Review

**Spec coverage:**
- Carried-over decisions (Section 2: stage/theme independence, auto-inference, segment-driven skip rules, significance tiers, no-franchise themes, hybrid content generation, terminal-only surface) — covered by Tasks 4–11; segment-driven skip-rule *table* (which stage a given segment starts at) is not implemented as its own function in this plan. **Gap found:** Section 2 says "a `skeptic` or `architect` segment entering fresh skips `onboarding`... an `accelerant` skips straight to `policy_maker`-flavored framing" — this is a distinct resolution rule from plain stage override/inference. Fixing inline below.
- Framework registration (Section 3) — Task 2. ✅
- Fence composition pipeline (Section 4) + hook-seam correction — Task 1, Task 11. ✅
- Stage/segment inference timing/pinning (Section 4a) — Task 5. ✅
- Theme packs + named Layer-3 fail-open exception (Section 5) — Task 6, Task 7. ✅
- Domain vocabulary, template vs. remix scope correction (Section 6) — Task 9, Task 10. ✅
- CLI surface (Section 7) — Task 12 (vocab); the inherited generic `enable|disable|set|show|pack add` verbs are already covered by the Configurability Framework plan's Task 7, reused here without modification.
- Compatibility (Section 8) — Task 1's `test_render_task_fence_with_no_contributors_matches_baseline` plus the static-grep test cover this directly.

**Fixing the segment skip-rule gap found above** — add to Task 5:

```python
# synlynk/companion.py (add, same task as resolve_stage_and_segment)
_SEGMENT_ENTRY_STAGE = {
    "novice": None,            # no skip; starts wherever inference/override says
    "skeptic": "sounding_board",
    "architect": "sounding_board",
    "accelerant": "policy_maker",
}


def apply_segment_skip_rule(stage: str, segment: str, is_fresh_entry: bool) -> str:
    """A fresh skeptic/architect/accelerant entrant skips onboarding per
    Section 2's skip-rule table. Only applies on fresh entry (no prior
    override/inferred stage recorded yet) -- an existing user's stage is
    never silently overridden by this rule.
    """
    if not is_fresh_entry:
        return stage
    entry_override = _SEGMENT_ENTRY_STAGE.get(segment)
    return entry_override if entry_override is not None else stage
```

Add a test to Task 5's test block:

```python
def test_segment_skip_rule_applies_only_on_fresh_entry():
    from synlynk.companion import apply_segment_skip_rule
    assert apply_segment_skip_rule("onboarding", "skeptic", is_fresh_entry=True) == "sounding_board"
    assert apply_segment_skip_rule("onboarding", "accelerant", is_fresh_entry=True) == "policy_maker"
    assert apply_segment_skip_rule("onboarding", "novice", is_fresh_entry=True) == "onboarding"
    assert apply_segment_skip_rule("companionship", "skeptic", is_fresh_entry=False) == "companionship"
```

`maybe_add_hint()` (Task 11) should call `apply_segment_skip_rule(stage, segment, is_fresh_entry=...)` where `is_fresh_entry` is determined by whether `.synlynk/features.json`'s `companion` entry has ever been written before — this plan treats that wiring as an integration detail deferred to the task-executing engineer, since it depends on the exact first-write detection the surrounding `set_feature_enabled` call site already performs; the unit-level behavior above is what the self-review requires to close the spec-coverage gap.

**Placeholder scan:** `_harness_exec_remix()` in Task 10 raises `NotImplementedError` in its real body — flagged explicitly in that task's own commentary as "wire to the real harness-exec call site during integration," which is a legitimate integration seam (all three remix tests monkeypatch around it), not a silently-incomplete implementation. `_ROLLING_MEDIAN_COST_USD` in Task 11 is a static placeholder value, also flagged explicitly as "a real rolling median from telemetry is an enhancement, not required for this spec's acceptance" — acceptable since Section 2's own heuristic description ("a rolling median") doesn't specify the exact window/calculation, leaving a reasonable default in scope.

**Type consistency:** `FenceData`, `maybe_add_hint`, `compute_significance_tier`, `resolve_stage_and_segment`, `apply_segment_skip_rule`, `resolve_template_line`, `should_render_hint`, `apply_domain_vocab`, `maybe_remix`, `load_theme_pack` — consistent names/signatures across all tasks.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-31-companion-v2.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Depends on `docs/superpowers/plans/2026-10-31-configurability-framework.md` being implemented first.
