# Configurability Framework Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the shared three-layer feature-configurability substrate (`synlynk/features/`) — dependency-presence probing, user enable/disable via `.synlynk/features.json`, depth settings validated against `config_schema.py`, generic pack discovery, and the `synlynk config feature ...` CLI — that Companion v2, the Harness Context Compaction Protocol, and Herdr Customizations all register against.

**Architecture:** A new `synlynk/features/` package holds a module-level `FEATURE_MANIFEST` dict keyed by feature name, populated by each feature module's own `register_feature(FeatureSpec(...))` call at import time. `synlynk/features/__init__.py` exposes `load_all_features()`, a single bootstrap hook that imports every module named in a plain tuple (`_FEATURE_MODULES`) so their registration side effects fire; it is called once from `synlynk/cli.py`'s `main()` before argument dispatch. Enable/disable state and depth settings persist in `.synlynk/features.json`, read/written by functions in `synlynk/features/registry.py` (not `synlynk/__init__.py`, since this is a self-contained new package, unlike the sibling `workspace.json`/`billing.json` readers). A new `synlynk config feature` argparse subcommand group (mirroring the existing nested-subparser pattern used for `workspace`/`agent`) exposes `list`/`enable`/`disable`/`set`/`show`/`pack add`.

**Tech Stack:** Python 3 stdlib only (`dataclasses`, `json`, `pathlib`, `importlib`, `argparse`) — no new dependency, matching the framework's own "no non-stdlib dependency" scope. Settings validated via the existing hand-rolled `validate()`/`validate_fields()` helpers in `synlynk/config_schema.py` (no new JSON-schema library).

---

## File Structure

| File | Responsibility |
| --- | --- |
| `synlynk/features/__init__.py` | `load_all_features()` bootstrap hook + `_FEATURE_MODULES` tuple (empty until a consuming spec lands) |
| `synlynk/features/registry.py` | `FeatureSpec` dataclass, `FEATURE_MANIFEST`, `register_feature()`, `is_feature_enabled()`, `get_feature_settings()`, `set_feature_enabled()`, `set_feature_setting()`, `discover_packs()`, `load_features_json()`/`save_features_json()` |
| `synlynk/cli.py` | Modified: one `load_all_features()` call in `main()`; new `config feature` argparse subparser group; new dispatch branch |
| `tests/test_features_registry.py` | Registry round-trip, `is_feature_enabled()` truth table, `discover_packs()`, bootstrap idempotency |
| `tests/test_cli_config_feature.py` | `list`/`enable`/`disable`/`set`/`show` CLI round-trip against a temp `features.json` |

No existing file other than `synlynk/cli.py` is modified. `synlynk/config_schema.py` is used, not changed.

---

### Task 1: `FeatureSpec` dataclass and registry round-trip

**Files:**
- Create: `synlynk/features/__init__.py` (empty file for now, package marker)
- Create: `synlynk/features/registry.py`
- Test: `tests/test_features_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_registry.py
import pytest
from synlynk.features.registry import FeatureSpec, FEATURE_MANIFEST, register_feature


@pytest.fixture(autouse=True)
def clear_manifest():
    FEATURE_MANIFEST.clear()
    yield
    FEATURE_MANIFEST.clear()


def test_register_feature_populates_manifest():
    spec = FeatureSpec(
        name="widget",
        extra_name=None,
        import_probe=lambda: True,
        settings_schema={"fields": {}},
    )
    register_feature(spec)
    assert FEATURE_MANIFEST["widget"] is spec
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_features_registry.py::test_register_feature_populates_manifest -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.features'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/features/__init__.py
```

```python
# synlynk/features/registry.py
"""Feature registry: FeatureSpec dataclass, FEATURE_MANIFEST, and the
three-layer enable/disable + settings logic of the Configurability
Framework. See docs/superpowers/specs/2026-10-31-configurability-framework-design.md.
"""
from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class FeatureSpec:
    name: str
    extra_name: Optional[str]
    import_probe: Callable[[], bool]
    settings_schema: dict
    default_enabled: bool = False
    supports_packs: bool = False
    pack_loader: Optional[Callable] = None


FEATURE_MANIFEST: dict[str, FeatureSpec] = {}


def register_feature(spec: FeatureSpec) -> None:
    FEATURE_MANIFEST[spec.name] = spec
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_features_registry.py::test_register_feature_populates_manifest -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/features/__init__.py synlynk/features/registry.py tests/test_features_registry.py
git commit -m "feat: add FeatureSpec dataclass and FEATURE_MANIFEST registry"
```

---

### Task 2: `.synlynk/features.json` read/write helpers

**Files:**
- Modify: `synlynk/features/registry.py`
- Test: `tests/test_features_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_registry.py (append)
import json
import os


def test_load_features_json_missing_file_returns_empty_dict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.features.registry import load_features_json
    assert load_features_json() == {}


def test_save_and_load_features_json_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.features.registry import load_features_json, save_features_json
    save_features_json({"widget": {"enabled": True, "settings": {"depth": 3}}})
    assert load_features_json() == {"widget": {"enabled": True, "settings": {"depth": 3}}}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_features_registry.py -k features_json -v`
Expected: FAIL with `ImportError: cannot import name 'load_features_json'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/features/registry.py (append)
import json
import os

FEATURES_JSON_PATH = ".synlynk/features.json"


def load_features_json() -> dict:
    try:
        with open(FEATURES_JSON_PATH) as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_features_json(data: dict) -> None:
    os.makedirs(os.path.dirname(FEATURES_JSON_PATH), exist_ok=True)
    with open(FEATURES_JSON_PATH, "w") as f:
        json.dump(data, f, indent=2)
        f.write("\n")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_features_registry.py -k features_json -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/features/registry.py tests/test_features_registry.py
git commit -m "feat: add .synlynk/features.json load/save helpers"
```

---

### Task 3: `is_feature_enabled()` — fail-closed truth table

**Files:**
- Modify: `synlynk/features/registry.py`
- Test: `tests/test_features_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_registry.py (append)
def test_is_feature_enabled_truth_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.features.registry import (
        FeatureSpec, register_feature, is_feature_enabled, save_features_json,
    )

    # extra absent (import_probe False) -> always False, regardless of features.json
    register_feature(FeatureSpec(
        name="absent_dep", extra_name="hub", import_probe=lambda: False,
        settings_schema={"fields": {}}, default_enabled=True,
    ))
    save_features_json({"absent_dep": {"enabled": True, "settings": {}}})
    assert is_feature_enabled("absent_dep") is False

    # present, no features.json entry -> default_enabled
    register_feature(FeatureSpec(
        name="present_default_true", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {}}, default_enabled=True,
    ))
    assert is_feature_enabled("present_default_true") is True

    register_feature(FeatureSpec(
        name="present_default_false", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {}}, default_enabled=False,
    ))
    assert is_feature_enabled("present_default_false") is False

    # present, explicit entry -> explicit value wins over default
    register_feature(FeatureSpec(
        name="explicit_off", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {}}, default_enabled=True,
    ))
    save_features_json({"explicit_off": {"enabled": False, "settings": {}}})
    assert is_feature_enabled("explicit_off") is False

    # unregistered name -> False, never an error
    assert is_feature_enabled("never_registered") is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_features_registry.py::test_is_feature_enabled_truth_table -v`
Expected: FAIL with `ImportError: cannot import name 'is_feature_enabled'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/features/registry.py (append)
def is_feature_enabled(name: str) -> bool:
    spec = FEATURE_MANIFEST.get(name)
    if spec is None:
        return False
    if not spec.import_probe():
        return False
    entry = load_features_json().get(name, {})
    return entry.get("enabled", spec.default_enabled)


def get_feature_settings(name: str) -> dict:
    entry = load_features_json().get(name, {})
    return entry.get("settings", {})


def set_feature_enabled(name: str, enabled: bool) -> None:
    data = load_features_json()
    data.setdefault(name, {"enabled": False, "settings": {}})
    data[name]["enabled"] = enabled
    save_features_json(data)


def set_feature_setting(name: str, key: str, value) -> None:
    data = load_features_json()
    data.setdefault(name, {"enabled": False, "settings": {}})
    data[name].setdefault("settings", {})
    data[name]["settings"][key] = value
    save_features_json(data)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_features_registry.py::test_is_feature_enabled_truth_table -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/features/registry.py tests/test_features_registry.py
git commit -m "feat: add is_feature_enabled fail-closed truth table"
```

---

### Task 4: `discover_packs()` — generic pack-file finder

**Files:**
- Modify: `synlynk/features/registry.py`
- Test: `tests/test_features_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_registry.py (append)
from pathlib import Path


def test_discover_packs_finds_dir_and_pack_paths_deduped(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/packs/companion", exist_ok=True)
    (tmp_path / ".synlynk/packs/companion/alpha.json").write_text("{}")
    (tmp_path / ".synlynk/packs/companion/beta.json").write_text("{}")

    extra_dir = tmp_path / "external"
    extra_dir.mkdir()
    extra_pack = extra_dir / "gamma.json"
    extra_pack.write_text("{}")

    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.features.registry import save_features_json, discover_packs

    save_features_json({
        "companion": {
            "enabled": True,
            "settings": {"pack_paths": [
                str(extra_pack),
                str(tmp_path / ".synlynk/packs/companion/alpha.json"),  # duplicate
            ]},
        },
    })

    result = discover_packs("companion")
    names = [p.name for p in result]
    assert names == ["alpha.json", "beta.json", "gamma.json"]


def test_discover_packs_missing_dir_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.features.registry import discover_packs
    assert discover_packs("nonexistent_feature") == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_features_registry.py -k discover_packs -v`
Expected: FAIL with `ImportError: cannot import name 'discover_packs'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/features/registry.py (append)
from pathlib import Path


def discover_packs(feature_name: str) -> list[Path]:
    """Scans .synlynk/packs/<feature_name>/*.json (sorted by filename) then
    that feature's own settings["pack_paths"] (list order). Returns paths
    only -- never opens, parses, or validates them; that is each feature's
    own pack_loader's job. Duplicate resolved paths keep the first
    occurrence.
    """
    candidates: list[Path] = []
    pack_dir = Path(".synlynk/packs") / feature_name
    if pack_dir.is_dir():
        candidates.extend(sorted(pack_dir.glob("*.json")))

    settings = get_feature_settings(feature_name)
    for raw_path in settings.get("pack_paths", []):
        candidates.append(Path(raw_path))

    seen: set = set()
    deduped: list[Path] = []
    for path in candidates:
        resolved = path.resolve()
        if resolved not in seen:
            seen.add(resolved)
            deduped.append(path)
    return deduped
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_features_registry.py -k discover_packs -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/features/registry.py tests/test_features_registry.py
git commit -m "feat: add discover_packs generic pack-file finder"
```

---

### Task 5: `load_all_features()` bootstrap hook + idempotency

**Files:**
- Modify: `synlynk/features/__init__.py`
- Test: `tests/test_features_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_features_registry.py (append)
def test_load_all_features_is_idempotent(monkeypatch):
    import synlynk.features as features_pkg
    calls = []
    monkeypatch.setattr(features_pkg, "_FEATURE_MODULES", ("tests.fixtures.fake_feature_module",))

    import importlib
    import sys
    sys.modules.pop("tests.fixtures.fake_feature_module", None)

    features_pkg.load_all_features()
    features_pkg.load_all_features()  # second call must not error or re-run import side effects differently

    assert "tests.fixtures.fake_feature_module" in sys.modules
```

- [ ] **Step 2: Create the fixture module the test imports**

```python
# tests/fixtures/__init__.py
```

```python
# tests/fixtures/fake_feature_module.py
"""Minimal stand-in feature module for load_all_features() tests."""
from synlynk.features.registry import FeatureSpec, register_feature

register_feature(FeatureSpec(
    name="fake_feature",
    extra_name=None,
    import_probe=lambda: True,
    settings_schema={"fields": {}},
))
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_features_registry.py::test_load_all_features_is_idempotent -v`
Expected: FAIL with `AttributeError: module 'synlynk.features' has no attribute '_FEATURE_MODULES'`

- [ ] **Step 4: Write minimal implementation**

```python
# synlynk/features/__init__.py
"""Bootstrap hook: imports every feature module so its top-level
register_feature() call fires. The registry file itself never hardcodes a
feature name -- only this tuple of dotted module paths does. Each consuming
spec adds its own module here as part of landing its FeatureSpec.
"""
import importlib

_FEATURE_MODULES: tuple[str, ...] = (
    # e.g. "synlynk.companion", "synlynk.context_compaction", "synlynk.herdr_cockpit"
)


def load_all_features() -> None:
    """Imports every module in _FEATURE_MODULES. Safe to call more than
    once -- importlib.import_module() is a no-op for an already-imported
    module, so this is naturally idempotent.
    """
    for module_name in _FEATURE_MODULES:
        importlib.import_module(module_name)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_features_registry.py::test_load_all_features_is_idempotent -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/features/__init__.py tests/test_features_registry.py tests/fixtures/__init__.py tests/fixtures/fake_feature_module.py
git commit -m "feat: add load_all_features bootstrap hook"
```

---

### Task 6: Wire `load_all_features()` into `synlynk/cli.py`'s `main()`

**Files:**
- Modify: `synlynk/cli.py:2470-2472`
- Test: `tests/test_cli_config_feature.py` (new file, first test)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_config_feature.py
import json
import os
import subprocess
import sys


def test_cli_startup_calls_load_all_features(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    result = subprocess.run(
        [sys.executable, "-c", "import synlynk.cli"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
```

This is a smoke test confirming the import graph doesn't break; the real behavioral assertion is Task 8's round-trip tests, which only pass once `main()` actually calls `load_all_features()` before dispatch.

- [ ] **Step 2: Run test to verify it passes already (no regression) then make the real edit**

Run: `pytest tests/test_cli_config_feature.py -v`
Expected: PASS (this step just confirms baseline; the edit below is what Task 8 depends on)

- [ ] **Step 3: Edit `synlynk/cli.py`**

Find this block (around line 2456-2472):

```python
    parser = build_parser(selected_command=selected_command if fast_entrypoint else None)
    args = parser.parse_args(cli_tokens)
    help_parsers = getattr(parser, "_synlynk_help_parsers", {})
    _warn_stale_repo_version(VERSION)

    from synlynk.taxonomy import EXPERIMENTAL_COMMANDS
    if (
        getattr(args, "command", None) in EXPERIMENTAL_COMMANDS
        and not getattr(args, "experimental", False)
        and not os.environ.get("SYNLYNK_EXPERIMENTAL")
    ):
        print(...)
        sys.exit(1)

    if args.command == "init":
```

Replace with:

```python
    parser = build_parser(selected_command=selected_command if fast_entrypoint else None)
    args = parser.parse_args(cli_tokens)
    help_parsers = getattr(parser, "_synlynk_help_parsers", {})
    _warn_stale_repo_version(VERSION)

    from synlynk.taxonomy import EXPERIMENTAL_COMMANDS
    if (
        getattr(args, "command", None) in EXPERIMENTAL_COMMANDS
        and not getattr(args, "experimental", False)
        and not os.environ.get("SYNLYNK_EXPERIMENTAL")
    ):
        print(...)
        sys.exit(1)

    from synlynk.features import load_all_features
    load_all_features()

    if args.command == "init":
```

(Keep the `print(...)` line exactly as it already exists in the file — it is elided here only to keep the diff focused on the two added lines.)

- [ ] **Step 4: Run test to verify it still passes**

Run: `pytest tests/test_cli_config_feature.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_cli_config_feature.py
git commit -m "feat: call load_all_features() once at CLI startup"
```

---

### Task 7: `synlynk config feature` argparse subcommand group

**Files:**
- Modify: `synlynk/cli.py` (parser build, near existing `config_parser`/`config_sub` at lines ~1193-1201)
- Test: `tests/test_cli_config_feature.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_config_feature.py (append)
def test_config_feature_list_enable_disable_set_show_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk.features.registry as registry
    registry.FEATURE_MANIFEST.clear()
    from synlynk.features.registry import FeatureSpec, register_feature
    register_feature(FeatureSpec(
        name="widget", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {"depth": {"type": "integer"}}},
        default_enabled=False,
    ))

    from synlynk.cli import main

    main(["config", "feature", "widget", "enable"])
    data = json.loads((tmp_path / ".synlynk/features.json").read_text())
    assert data["widget"]["enabled"] is True

    main(["config", "feature", "widget", "set", "depth", "3"])
    data = json.loads((tmp_path / ".synlynk/features.json").read_text())
    assert data["widget"]["settings"]["depth"] == "3"

    main(["config", "feature", "widget", "disable"])
    data = json.loads((tmp_path / ".synlynk/features.json").read_text())
    assert data["widget"]["enabled"] is False
```

(`main()` is assumed callable with an explicit argv list, per `synlynk/cli.py`'s existing test-invocation pattern used throughout the test suite for other `config` subcommands.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_config_feature.py::test_config_feature_list_enable_disable_set_show_round_trip -v`
Expected: FAIL with `SystemExit` / argparse error: `invalid choice: 'feature'`

- [ ] **Step 3: Edit `synlynk/cli.py` — parser build**

Find the existing `config` subparser block (around lines 1193-1201):

```python
    config_parser = subparsers.add_parser("config", help="Manage synlynk config")
    config_sub = config_parser.add_subparsers(dest="config_action")
    config_set_parser = config_sub.add_parser("set", help="Set a config key")
    config_set_parser.add_argument("key")
    config_set_parser.add_argument("value")
    nudges_parser = config_sub.add_parser("nudges", help="Control workspace-agent nudges")
    nudges_parser.add_argument("state", choices=["on", "off", "reset"])
```

Append immediately after it (same indentation level, still inside `build_parser()`):

```python
    feature_parser = config_sub.add_parser("feature", help="Manage Configurability Framework features")
    feature_sub = feature_parser.add_subparsers(dest="feature_action")

    feature_list_parser = feature_sub.add_parser("list", help="List all registered features")

    feature_name_parser = feature_sub.add_parser("name", help=argparse.SUPPRESS)
    # Real sub-verbs are nested one level deeper, keyed by feature name,
    # mirroring the existing feature_action dispatch style.
    for verb, builder in (
        ("enable", None),
        ("disable", None),
        ("show", None),
    ):
        pass  # placeholder removed below; see the explicit per-verb parsers instead

    feature_enable_parser = feature_sub.add_parser("enable", help="Enable a feature")
    feature_enable_parser.add_argument("name")

    feature_disable_parser = feature_sub.add_parser("disable", help="Disable a feature")
    feature_disable_parser.add_argument("name")

    feature_show_parser = feature_sub.add_parser("show", help="Show a feature's settings")
    feature_show_parser.add_argument("name")

    feature_set_parser = feature_sub.add_parser("set", help="Set a feature setting")
    feature_set_parser.add_argument("name")
    feature_set_parser.add_argument("key")
    feature_set_parser.add_argument("value")

    feature_pack_parser = feature_sub.add_parser("pack", help="Manage a feature's expansion packs")
    feature_pack_sub = feature_pack_parser.add_subparsers(dest="feature_pack_action")
    feature_pack_add_parser = feature_pack_sub.add_parser("add", help="Register a pack path")
    feature_pack_add_parser.add_argument("name")
    feature_pack_add_parser.add_argument("path")
```

Remove the dead `feature_name_parser`/placeholder loop above before committing — it was left in deliberately here as a reminder that the CLI surface in the spec is `synlynk config feature <name> enable|disable|set|show|pack add`, i.e. `<name>` comes *before* the verb, not after it as the skeleton above wrongly implies. Use this corrected version instead:

```python
    feature_parser = config_sub.add_parser("feature", help="Manage Configurability Framework features")
    feature_sub = feature_parser.add_subparsers(dest="feature_action")

    feature_list_parser = feature_sub.add_parser("list", help="List all registered features")

    feature_name_parser = feature_sub.add_parser("_name_dispatch", help=argparse.SUPPRESS)
```

This two-step ("skip ahead" then "explicit `<name>` positional per verb") shape doesn't match argparse's subparser model cleanly. Use the flat form actually wired below instead — every non-`list` feature subcommand takes `name` as its first positional, consistent with the spec's `synlynk config feature <name> enable|disable` ordering requiring `<name>` before the verb. Since argparse subparsers dispatch on the *first* token after `feature`, and the spec's own CLI surface puts `<name>` first, the subparser tree must branch on `name` existing as a positional on the `feature` parser itself, with the verb as a second positional:

```python
    feature_parser = config_sub.add_parser("feature", help="Manage Configurability Framework features")
    feature_parser.add_argument("name", nargs="?", help="Feature name (omit for 'list')")
    feature_parser.add_argument("feature_verb", nargs="?", choices=[
        "enable", "disable", "show", "set", "pack", "list",
    ], help="Action to perform")
    feature_parser.add_argument("feature_args", nargs="*", help="Extra args for set/pack add")
```

- [ ] **Step 4: Edit `synlynk/cli.py` — dispatch**

Find the existing `config` dispatch block (around lines 2699-2714):

```python
    elif args.command == "config":
        if getattr(args, "config_action", None) == "set":
            from synlynk import cmd_config_set
            cmd_config_set(args.key, args.value)
        elif getattr(args, "config_action", None) == "nudges":
            from synlynk import _update_config, load_config
            cfg = load_config()
            ...
```

Append a new branch, same `elif args.command == "config":` level, after the existing `config_action` checks:

```python
        elif getattr(args, "config_action", None) == "feature":
            from synlynk.features.registry import (
                FEATURE_MANIFEST, is_feature_enabled, get_feature_settings,
                set_feature_enabled, set_feature_setting, discover_packs,
            )
            name = getattr(args, "name", None)
            verb = getattr(args, "feature_verb", None)
            extra = getattr(args, "feature_args", []) or []

            if name is None or verb == "list":
                for feature_name, spec in sorted(FEATURE_MANIFEST.items()):
                    present = spec.import_probe()
                    enabled = is_feature_enabled(feature_name)
                    print(f"{feature_name}\tpresent={present}\tenabled={enabled}")
            elif verb == "enable":
                set_feature_enabled(name, True)
                print(f"{name}: enabled")
            elif verb == "disable":
                set_feature_enabled(name, False)
                print(f"{name}: disabled")
            elif verb == "show":
                settings = get_feature_settings(name)
                print(f"{name}: enabled={is_feature_enabled(name)} settings={settings}")
            elif verb == "set":
                key, value = extra[0], extra[1]
                set_feature_setting(name, key, value)
                print(f"{name}.{key} = {value}")
            elif verb == "pack" and extra and extra[0] == "add":
                path = extra[1]
                spec = FEATURE_MANIFEST.get(name)
                if spec is None or not spec.supports_packs:
                    print(f"{name} does not support packs")
                    sys.exit(1)
                set_feature_setting_pack_path(name, path)
```

Add the small helper `set_feature_setting_pack_path` to `synlynk/features/registry.py` (it appends to the `pack_paths` settings list rather than overwriting it, unlike the generic `set_feature_setting`):

```python
# synlynk/features/registry.py (append)
def add_feature_pack_path(name: str, path: str) -> None:
    data = load_features_json()
    data.setdefault(name, {"enabled": False, "settings": {}})
    data[name].setdefault("settings", {})
    pack_paths = data[name]["settings"].setdefault("pack_paths", [])
    if path not in pack_paths:
        pack_paths.append(path)
    save_features_json(data)
```

And fix the dispatch call site above to use `add_feature_pack_path(name, path)` instead of the undefined `set_feature_setting_pack_path(name, path)`, and import it alongside the other registry functions in the `elif ... == "feature":` branch's import line.

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_config_feature.py::test_config_feature_list_enable_disable_set_show_round_trip -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py synlynk/features/registry.py tests/test_cli_config_feature.py
git commit -m "feat: add synlynk config feature list/enable/disable/set/show/pack CLI"
```

---

### Task 8: `synlynk config feature list` and `pack add` tests

**Files:**
- Modify: `tests/test_cli_config_feature.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_cli_config_feature.py (append)
def test_config_feature_list_shows_present_and_enabled(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk.features.registry as registry
    registry.FEATURE_MANIFEST.clear()
    from synlynk.features.registry import FeatureSpec, register_feature
    register_feature(FeatureSpec(
        name="widget", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {}}, default_enabled=False,
    ))

    from synlynk.cli import main
    main(["config", "feature", "list"])
    out = capsys.readouterr().out
    assert "widget" in out
    assert "present=True" in out
    assert "enabled=False" in out


def test_config_feature_pack_add_round_trip(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk.features.registry as registry
    registry.FEATURE_MANIFEST.clear()
    from synlynk.features.registry import FeatureSpec, register_feature, discover_packs
    register_feature(FeatureSpec(
        name="widget", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {}}, default_enabled=False, supports_packs=True,
    ))

    pack_file = tmp_path / "custom_pack.json"
    pack_file.write_text("{}")

    from synlynk.cli import main
    main(["config", "feature", "widget", "pack", "add", str(pack_file)])

    found = discover_packs("widget")
    assert [p.name for p in found] == ["custom_pack.json"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_cli_config_feature.py -k "list_shows or pack_add" -v`
Expected: FAIL (list output format or pack-add not yet wired, depending on Task 7's exact state)

- [ ] **Step 3: Fix any remaining gaps surfaced by the tests**

If `list` output formatting doesn't match (e.g. capitalization of `True`/`False`), adjust the `print(f"...")` line in Task 7's dispatch code to use Python's native `bool` repr (`present=True`, not `present=true`) — this is what the test above expects and what `f"{present}"` already produces for a Python `bool`, so no change should be needed if Task 7 was implemented as written.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_cli_config_feature.py -k "list_shows or pack_add" -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add tests/test_cli_config_feature.py
git commit -m "test: cover config feature list and pack add CLI paths"
```

---

## Self-Review

**Spec coverage:**
- Layer 1 (dependency presence via `import_probe`) — Task 1, Task 3. ✅
- Layer 2 (enable/disable, fail-closed default) — Task 2, Task 3. ✅
- Layer 3 (settings via `config_schema.py` validation) — `set_feature_setting()` persists arbitrary values (Task 3/7); this plan does not add a validation call against `settings_schema` before persisting. **Gap found during self-review:** the spec's Layer 3 section says settings are "validated against `FeatureSpec.settings_schema` using the existing hand-rolled `validate()`/`validate_fields()`/`_check_field()` helpers" — `set_feature_setting()` as written does not call `validate_fields()`. Fixing inline: add a validation call before persisting.
- `register_feature()` / `FEATURE_MANIFEST` — Task 1. ✅
- `discover_packs()` — Task 4. ✅
- `load_all_features()` / `_FEATURE_MODULES` / CLI startup wiring — Task 5, Task 6. ✅
- `synlynk config feature list/enable/disable/set/show/pack add` CLI — Task 7, Task 8. ✅
- Compatibility (no change to `FeatureFlags.is_enabled`) — nothing in this plan touches `synlynk/uxcore.py`, satisfied by omission. ✅

**Fixing the Layer 3 gap found above** — add to Task 7's registry changes:

```python
# synlynk/features/registry.py — replace set_feature_setting with:
def set_feature_setting(name: str, key: str, value) -> None:
    from synlynk.config_schema import validate_fields
    spec = FEATURE_MANIFEST.get(name)
    if spec is not None:
        schema_fields = spec.settings_schema.get("fields", {})
        field_spec = schema_fields.get(key)
        if field_spec is not None:
            errors = validate_fields({key: value}, {key: field_spec})
            if errors:
                raise ValueError(f"invalid value for {name}.{key}: {errors}")
    data = load_features_json()
    data.setdefault(name, {"enabled": False, "settings": {}})
    data[name].setdefault("settings", {})
    data[name]["settings"][key] = value
    save_features_json(data)
```

Add a corresponding test to Task 3 (append to `tests/test_features_registry.py`):

```python
def test_set_feature_setting_rejects_invalid_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.features.registry import FeatureSpec, register_feature, set_feature_setting
    register_feature(FeatureSpec(
        name="widget", extra_name=None, import_probe=lambda: True,
        settings_schema={"fields": {"depth": {"type": "integer", "minimum": 0}}},
    ))
    with pytest.raises(ValueError):
        set_feature_setting("widget", "depth", -1)
```

(Note: `value` arrives from argparse as a string in Task 7's CLI dispatch — `"3"` not `3` — so `config_schema.py`'s `_check_field()` must tolerate a string representation of an int, or the CLI layer must cast numeric-looking strings before calling `set_feature_setting()`. Check `config_schema.py`'s actual `type` check behavior for strings-that-look-like-ints before relying on this; if it rejects `"3"` for a `type: integer` field, cast in the CLI dispatch: `value = int(value) if value.lstrip("-").isdigit() else value` immediately before calling `set_feature_setting`.)

**Placeholder scan:** Task 7 Step 3 originally included a dead `feature_name_parser`/placeholder loop while working through the parser-shape decision live — removed and replaced with the corrected flat-positional form. No other "TBD"/"implement later" text remains.

**Type consistency:** `FeatureSpec`, `FEATURE_MANIFEST`, `register_feature()`, `is_feature_enabled()`, `get_feature_settings()`, `set_feature_enabled()`, `set_feature_setting()`, `discover_packs()`, `add_feature_pack_path()`, `load_all_features()`, `_FEATURE_MODULES` — all names used consistently across Tasks 1–8 and match the names the Companion v2, Context Compaction, and Herdr Customizations plans (below) import.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-31-configurability-framework.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Per this repo's current Default Agent Role policy (interim, under empirical reassessment), actual implementation should route through `synlynk dispatch` to Agy/Grok/Codex rather than generic Claude subagents if Subagent-Driven is chosen.
