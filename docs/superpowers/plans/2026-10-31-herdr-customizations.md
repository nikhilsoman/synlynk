# Herdr Customizations (Core) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the thin, always-on synlynk-core half of Herdr integration: `synlynk/cockpit.py`, the `synlynk herdr init`/`tab <epic>` CLI, a `herdr_cockpit` `FeatureSpec`, the 3-step resolution logic (disabled → hint; enabled-but-no-Herdr → tmux/terminal fallback; enabled-and-Herdr-live → delegate to linked plugin or fall back to a raw pane-split sequence), and version-checked plugin-contract delegation via `herdr plugin action invoke`.

**Architecture:** `synlynk/cockpit.py` registers `FeatureSpec(name="herdr_cockpit", extra_name=None, default_enabled=False)` — Herdr is an external binary, not a pip dependency, so `import_probe` checks binary presence on `PATH` rather than a Python import. `resolve_cockpit_action()` implements the 3-step gate explicitly as named, testable branches (not an implicit cascade), each independently unit-tested. The plugin-contract delegation path checks a minimum interface version before calling `herdr plugin action invoke`, with a documented, logged fallback to the raw pane-split sequence on version mismatch or invoke failure — named as intentional duplication for core self-sufficiency, not deferred scope. The `herdr-synlynk` plugin repo's own build is out of scope.

**Tech Stack:** Python 3 stdlib only (`shutil.which` for binary detection, `subprocess` for `herdr` CLI calls). No new dependency (`extra_name=None`). Depends on `docs/superpowers/plans/2026-10-31-configurability-framework.md` being implemented first.

---

## File Structure

| File | Responsibility |
| --- | --- |
| `synlynk/cockpit.py` | New. `FeatureSpec` registration, `herdr_binary_present()`, `plugin_is_linked()`, `resolve_cockpit_action()` (3-step gate), plugin-version-check + `invoke_plugin_action()` with fallback, `raw_pane_split_sequence()` (named-duplication fallback), `tmux_fallback()`. |
| `synlynk/features/__init__.py` | Modified: add `"synlynk.cockpit"` to `_FEATURE_MODULES`. |
| `synlynk/cli.py` | Modified: add `synlynk herdr init`/`tab <epic>` subcommand group. |
| `tests/test_cockpit.py` | New. FeatureSpec registration, 3-step resolution gate (all branches), plugin version-check/fallback, raw pane-split sequence, tmux fallback. |
| `tests/test_cli_herdr.py` | New. `synlynk herdr init`/`tab <epic>` CLI round-trip. |

---

### Task 1: `FeatureSpec` registration with binary-presence `import_probe`

**Files:**
- Create: `synlynk/cockpit.py`
- Modify: `synlynk/features/__init__.py`
- Test: `tests/test_cockpit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cockpit.py
import pytest


@pytest.fixture(autouse=True)
def clear_registry():
    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    yield
    FEATURE_MANIFEST.clear()


def test_cockpit_module_registers_feature():
    import importlib
    import synlynk.cockpit as cockpit_module
    importlib.reload(cockpit_module)

    from synlynk.features.registry import FEATURE_MANIFEST
    assert "herdr_cockpit" in FEATURE_MANIFEST
    spec = FEATURE_MANIFEST["herdr_cockpit"]
    assert spec.extra_name is None
    assert spec.default_enabled is False


def test_herdr_binary_present_checks_path(monkeypatch):
    from synlynk.cockpit import herdr_binary_present
    monkeypatch.setattr("shutil.which", lambda name: "/usr/local/bin/herdr" if name == "herdr" else None)
    assert herdr_binary_present() is True


def test_herdr_binary_absent(monkeypatch):
    from synlynk.cockpit import herdr_binary_present
    monkeypatch.setattr("shutil.which", lambda name: None)
    assert herdr_binary_present() is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.cockpit'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/cockpit.py
"""Herdr Customizations -- synlynk-core half. See
docs/superpowers/specs/2026-10-31-herdr-customizations-design.md.

This module implements the always-on, thin core side only. The optional
herdr-synlynk plugin repo (pane-layout actions, worktree.created hook,
GitHub link handlers, sentinel.md-to-toast notifier) is a separate,
independently-versioned GitHub repo, out of scope for this module.
"""
import shutil

from synlynk.features.registry import FeatureSpec, register_feature

HERDR_COCKPIT_SETTINGS_SCHEMA = {
    "fields": {
        "herdr_auto_tab_on_epic": {"type": "boolean", "required": False},
    },
}


def herdr_binary_present() -> bool:
    return shutil.which("herdr") is not None


register_feature(FeatureSpec(
    name="herdr_cockpit",
    extra_name=None,
    import_probe=lambda: True,  # feature itself has no pip dependency; herdr
                                 # binary presence is a runtime *resolution*
                                 # concern (Task 2), not an install-probe concern
    settings_schema=HERDR_COCKPIT_SETTINGS_SCHEMA,
    default_enabled=False,
    supports_packs=False,
    pack_loader=None,
))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cockpit.py synlynk/features/__init__.py tests/test_cockpit.py
git commit -m "feat: register herdr_cockpit FeatureSpec

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

Also add to `synlynk/features/__init__.py`:

```python
# synlynk/features/__init__.py
_FEATURE_MODULES: tuple[str, ...] = (
    "synlynk.companion",
    "synlynk.context_compaction",
    "synlynk.cockpit",
)
```

---

### Task 2: `plugin_is_linked()`

**Files:**
- Modify: `synlynk/cockpit.py`
- Test: `tests/test_cockpit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cockpit.py (append)
def test_plugin_is_linked_true_when_config_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk/herdr_plugin.json").write_text('{"linked": true, "interface_version": "1.2.0"}')

    from synlynk.cockpit import plugin_is_linked
    assert plugin_is_linked() is True


def test_plugin_is_linked_false_when_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.cockpit import plugin_is_linked
    assert plugin_is_linked() is False


def test_plugin_is_linked_false_when_malformed(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk/herdr_plugin.json").write_text("not json")

    from synlynk.cockpit import plugin_is_linked
    assert plugin_is_linked() is False  # fails closed on malformed config, per DECIDE panel fix
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit.py -k plugin_is_linked -v`
Expected: FAIL with `ImportError: cannot import name 'plugin_is_linked'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/cockpit.py (add)
import json
from pathlib import Path

PLUGIN_CONFIG_PATH = Path(".synlynk/herdr_plugin.json")


def _load_plugin_config() -> dict:
    if not PLUGIN_CONFIG_PATH.exists():
        return {}
    try:
        with open(PLUGIN_CONFIG_PATH) as f:
            return json.load(f)
    except json.JSONDecodeError:
        return {}  # fails closed on malformed config -- DECIDE panel requirement


def plugin_is_linked() -> bool:
    config = _load_plugin_config()
    return config.get("linked", False) is True
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit.py -k plugin_is_linked -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cockpit.py tests/test_cockpit.py
git commit -m "feat: add plugin_is_linked with fail-closed malformed-config handling

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 3: `resolve_cockpit_action()` — 3-step gate

**Files:**
- Modify: `synlynk/cockpit.py`
- Test: `tests/test_cockpit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cockpit.py (append)
def test_resolve_cockpit_action_disabled_returns_hint(monkeypatch):
    from synlynk.cockpit import resolve_cockpit_action
    monkeypatch.setattr("synlynk.cockpit.is_feature_enabled", lambda name: False)
    action = resolve_cockpit_action()
    assert action == "hint"


def test_resolve_cockpit_action_enabled_no_herdr_returns_tmux_fallback(monkeypatch):
    from synlynk.cockpit import resolve_cockpit_action
    monkeypatch.setattr("synlynk.cockpit.is_feature_enabled", lambda name: True)
    monkeypatch.setattr("synlynk.cockpit.herdr_binary_present", lambda: False)
    action = resolve_cockpit_action()
    assert action == "tmux_fallback"


def test_resolve_cockpit_action_enabled_herdr_live_no_plugin_returns_raw_pane_split(monkeypatch):
    from synlynk.cockpit import resolve_cockpit_action
    monkeypatch.setattr("synlynk.cockpit.is_feature_enabled", lambda name: True)
    monkeypatch.setattr("synlynk.cockpit.herdr_binary_present", lambda: True)
    monkeypatch.setattr("synlynk.cockpit.plugin_is_linked", lambda: False)
    action = resolve_cockpit_action()
    assert action == "raw_pane_split"


def test_resolve_cockpit_action_enabled_herdr_live_plugin_linked_returns_delegate(monkeypatch):
    from synlynk.cockpit import resolve_cockpit_action
    monkeypatch.setattr("synlynk.cockpit.is_feature_enabled", lambda name: True)
    monkeypatch.setattr("synlynk.cockpit.herdr_binary_present", lambda: True)
    monkeypatch.setattr("synlynk.cockpit.plugin_is_linked", lambda: True)
    action = resolve_cockpit_action()
    assert action == "delegate_to_plugin"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit.py -k resolve_cockpit_action -v`
Expected: FAIL with `ImportError: cannot import name 'resolve_cockpit_action'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/cockpit.py (add)
from synlynk.features.registry import is_feature_enabled


def resolve_cockpit_action() -> str:
    """3-step resolution gate, each branch independently named and tested:
      1. herdr_cockpit disabled -> "hint" (no Herdr-related behavior runs)
      2. enabled but herdr binary absent -> "tmux_fallback" (consented-to
         multiplexer behavior, gated behind the feature being enabled)
      3. enabled and herdr live:
         a. plugin linked -> "delegate_to_plugin"
         b. plugin not linked -> "raw_pane_split" (core self-sufficiency
            fallback, intentionally duplicating the plugin's own layout
            logic -- not deferred scope)
    """
    if not is_feature_enabled("herdr_cockpit"):
        return "hint"
    if not herdr_binary_present():
        return "tmux_fallback"
    if plugin_is_linked():
        return "delegate_to_plugin"
    return "raw_pane_split"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit.py -k resolve_cockpit_action -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cockpit.py tests/test_cockpit.py
git commit -m "feat: add resolve_cockpit_action 3-step resolution gate

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 4: `tmux_fallback()`

**Files:**
- Modify: `synlynk/cockpit.py`
- Test: `tests/test_cockpit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cockpit.py (append)
def test_tmux_fallback_invokes_tmux_split(monkeypatch):
    from synlynk.cockpit import tmux_fallback
    calls = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kwargs: calls.append(cmd))

    tmux_fallback(epic="epic-123")

    assert len(calls) == 1
    assert calls[0][0] == "tmux"
    assert "split-window" in calls[0]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit.py -k tmux_fallback -v`
Expected: FAIL with `ImportError: cannot import name 'tmux_fallback'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/cockpit.py (add)
import subprocess


def tmux_fallback(epic: str) -> None:
    subprocess.run(
        ["tmux", "split-window", "-h", "-c", ".",
         f"echo 'synlynk cockpit (tmux fallback) for {epic}'"],
        check=False,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit.py -k tmux_fallback -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cockpit.py tests/test_cockpit.py
git commit -m "feat: add tmux_fallback cockpit action

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 5: `raw_pane_split_sequence()` — named-duplication fallback

**Files:**
- Modify: `synlynk/cockpit.py`
- Test: `tests/test_cockpit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cockpit.py (append)
def test_raw_pane_split_sequence_invokes_herdr_pane_split_four_times(monkeypatch):
    from synlynk.cockpit import raw_pane_split_sequence
    calls = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kwargs: calls.append(cmd))

    raw_pane_split_sequence(epic="epic-123")

    split_calls = [c for c in calls if "split" in c]
    assert len(split_calls) == 4  # 4-pane layout, matching the plugin's
                                   # own apply-4pane action -- intentional
                                   # duplication for core self-sufficiency
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit.py -k raw_pane_split -v`
Expected: FAIL with `ImportError: cannot import name 'raw_pane_split_sequence'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/cockpit.py (add)
def raw_pane_split_sequence(epic: str) -> None:
    """Intentional duplication of the herdr-synlynk plugin's own
    apply-4pane/tab-epic logic, inlined here so core works standalone
    without the plugin installed. Not deferred scope -- a documented
    design decision (DECIDE panel, 2026-10-31).
    """
    for i in range(4):
        subprocess.run(
            ["herdr", "pane", "split", "--current", "--direction",
             "right" if i % 2 == 0 else "down", "--cwd", "."],
            check=False,
        )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit.py -k raw_pane_split -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cockpit.py tests/test_cockpit.py
git commit -m "feat: add raw_pane_split_sequence core-self-sufficiency fallback

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 6: Plugin-contract version check + `invoke_plugin_action()` with fallback

**Files:**
- Modify: `synlynk/cockpit.py`
- Test: `tests/test_cockpit.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cockpit.py (append)
_MIN_PLUGIN_INTERFACE_VERSION = (1, 0, 0)


def test_invoke_plugin_action_calls_plugin_when_version_compatible(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk/herdr_plugin.json").write_text('{"linked": true, "interface_version": "1.2.0"}')

    calls = []
    monkeypatch.setattr("subprocess.run", lambda cmd, **kwargs: calls.append(cmd))

    from synlynk.cockpit import invoke_plugin_action
    invoke_plugin_action(action="apply-4pane", epic="epic-123")

    assert calls[0] == ["herdr", "plugin", "action", "invoke", "apply-4pane", "--epic", "epic-123"]


def test_invoke_plugin_action_falls_back_on_version_mismatch(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk/herdr_plugin.json").write_text('{"linked": true, "interface_version": "0.5.0"}')

    fallback_calls = []
    monkeypatch.setattr("synlynk.cockpit.raw_pane_split_sequence", lambda epic: fallback_calls.append(epic))

    from synlynk.cockpit import invoke_plugin_action
    invoke_plugin_action(action="apply-4pane", epic="epic-123")

    assert fallback_calls == ["epic-123"]
    err = capsys.readouterr().err
    assert "version" in err.lower()


def test_invoke_plugin_action_falls_back_on_invoke_failure(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk/herdr_plugin.json").write_text('{"linked": true, "interface_version": "1.2.0"}')

    def raise_on_run(cmd, **kwargs):
        import subprocess as sp
        raise sp.CalledProcessError(1, cmd)

    monkeypatch.setattr("subprocess.run", raise_on_run)
    fallback_calls = []
    monkeypatch.setattr("synlynk.cockpit.raw_pane_split_sequence", lambda epic: fallback_calls.append(epic))

    from synlynk.cockpit import invoke_plugin_action
    invoke_plugin_action(action="apply-4pane", epic="epic-123")

    assert fallback_calls == ["epic-123"]
    err = capsys.readouterr().err
    assert "invoke" in err.lower() or "failed" in err.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cockpit.py -k invoke_plugin_action -v`
Expected: FAIL with `ImportError: cannot import name 'invoke_plugin_action'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/cockpit.py (add)
import sys

_MIN_PLUGIN_INTERFACE_VERSION = (1, 0, 0)


def _parse_version(version_str: str) -> tuple:
    return tuple(int(part) for part in version_str.split("."))


def invoke_plugin_action(action: str, epic: str) -> None:
    config = _load_plugin_config()
    interface_version = config.get("interface_version", "0.0.0")

    if _parse_version(interface_version) < _MIN_PLUGIN_INTERFACE_VERSION:
        print(
            f"herdr-synlynk plugin interface version {interface_version} is "
            f"below the minimum supported {'.'.join(map(str, _MIN_PLUGIN_INTERFACE_VERSION))}; "
            f"falling back to raw_pane_split_sequence",
            file=sys.stderr,
        )
        raw_pane_split_sequence(epic=epic)
        return

    try:
        subprocess.run(
            ["herdr", "plugin", "action", "invoke", action, "--epic", epic],
            check=True,
        )
    except subprocess.CalledProcessError:
        print(
            f"herdr plugin action invoke failed for action '{action}'; "
            f"falling back to raw_pane_split_sequence",
            file=sys.stderr,
        )
        raw_pane_split_sequence(epic=epic)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cockpit.py -k invoke_plugin_action -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/cockpit.py tests/test_cockpit.py
git commit -m "feat: add plugin-contract version check with documented fallback

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 7: `synlynk herdr init`/`tab <epic>` CLI

**Files:**
- Modify: `synlynk/cli.py`
- Test: `tests/test_cli_herdr.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_herdr.py
def test_cli_herdr_init_enables_feature(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)

    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    import importlib
    import synlynk.cockpit as cockpit_module
    importlib.reload(cockpit_module)

    from synlynk.cli import main
    main(["herdr", "init"])

    from synlynk.features.registry import is_feature_enabled
    assert is_feature_enabled("herdr_cockpit") is True


def test_cli_herdr_tab_dispatches_to_resolved_action(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)

    from synlynk.features.registry import FEATURE_MANIFEST
    FEATURE_MANIFEST.clear()
    import importlib
    import synlynk.cockpit as cockpit_module
    importlib.reload(cockpit_module)
    from synlynk.features.registry import set_feature_enabled
    set_feature_enabled("herdr_cockpit", True)

    calls = []
    monkeypatch.setattr("synlynk.cockpit.resolve_cockpit_action", lambda: "tmux_fallback")
    monkeypatch.setattr("synlynk.cockpit.tmux_fallback", lambda epic: calls.append(epic))

    from synlynk.cli import main
    main(["herdr", "tab", "epic-123"])

    assert calls == ["epic-123"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_herdr.py -v`
Expected: FAIL — `herdr` is not a recognized `synlynk` subcommand yet

- [ ] **Step 3: Edit `synlynk/cli.py` — parser build**

```python
    herdr_parser = subparsers.add_parser("herdr", help="Herdr cockpit commands")
    herdr_subparsers = herdr_parser.add_subparsers(dest="herdr_action")

    herdr_subparsers.add_parser("init", help="Enable the herdr_cockpit feature")

    herdr_tab_parser = herdr_subparsers.add_parser("tab", help="Open a cockpit tab for an epic")
    herdr_tab_parser.add_argument("epic")
```

- [ ] **Step 4: Edit `synlynk/cli.py` — dispatch**

```python
    elif args.command == "herdr":
        from synlynk.features.registry import set_feature_enabled
        import synlynk.cockpit as cockpit

        if args.herdr_action == "init":
            set_feature_enabled("herdr_cockpit", True)
            print("herdr_cockpit feature enabled")
        elif args.herdr_action == "tab":
            action = cockpit.resolve_cockpit_action()
            if action == "hint":
                print("herdr_cockpit is disabled -- run 'synlynk herdr init' to enable it")
            elif action == "tmux_fallback":
                cockpit.tmux_fallback(epic=args.epic)
            elif action == "raw_pane_split":
                cockpit.raw_pane_split_sequence(epic=args.epic)
            elif action == "delegate_to_plugin":
                cockpit.invoke_plugin_action(action="tab-epic", epic=args.epic)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_cli_herdr.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_cli_herdr.py
git commit -m "feat: add synlynk herdr init/tab CLI

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

## Self-Review

**Spec coverage:**
- Two-artifact split, core side only — entire plan. Plugin repo's own build correctly excluded (no files/tasks target a `herdr-synlynk` repo). ✅
- `FeatureSpec(herdr_cockpit, extra_name=None, default_enabled=False)` — Task 1. ✅
- 3-step resolution (disabled→hint; enabled-no-herdr→tmux/terminal fallback; enabled-and-live→delegate-or-raw-split) — Task 3, with Task 4/5/6 implementing each terminal action. ✅
- DECIDE panel fix #1 (gate precision: tmux fallback is consented-to since gated behind enabled state; plugin's `worktree.created` hook must fail closed on missing/malformed config) — Task 2's `plugin_is_linked()` fails closed on malformed config, directly satisfying the config-reading half of this fix. **Gap found:** the `worktree.created` *hook's own* execution-vs-effect gating is plugin-side behavior (lives in the separate `herdr-synlynk` repo), correctly out of scope for this core-only plan — no fix needed here, but worth stating explicitly so the plan doesn't appear to have silently dropped it.
- DECIDE panel fix #2 (plugin contract hardening: version check before invoke, documented fallback on mismatch/failure) — Task 6. ✅
- DECIDE panel fix #3 (name the fallback duplication honestly) — Task 5's docstring explicitly states this. ✅
- Client Surface Consistency section (Section 5 of spec) — this is a cross-cutting branding/framing convention with no shared code, applying to this plugin and the existing VS Code/Open VSX extension; it has no corresponding implementation task because the spec itself states "no shared code" — correctly not represented as a code task in this plan.
- CLI surface (`synlynk herdr init`/`tab <epic>`) — Task 7. ✅

**Placeholder scan:** none found — every function has a real, tested body. `invoke_plugin_action()`'s fallback path is a genuine documented behavior per DECIDE fix #2, not a stub.

**Type consistency:** `herdr_binary_present()`, `plugin_is_linked()`, `resolve_cockpit_action()`, `tmux_fallback()`, `raw_pane_split_sequence()`, `invoke_plugin_action()` — consistent names/signatures across all tasks and the CLI dispatch in Task 7.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-10-31-herdr-customizations.md`. Two execution options:

1. **Subagent-Driven (recommended)** — dispatch a fresh subagent per task, review between tasks, fast iteration
2. **Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints

Depends on `docs/superpowers/plans/2026-10-31-configurability-framework.md` being implemented first.

---

## All Four Plans Complete

| # | Plan | Status |
| --- | --- | --- |
| 1 | `2026-10-31-configurability-framework.md` | Written, self-reviewed |
| 2 | `2026-10-31-companion-v2.md` | Written, self-reviewed |
| 3 | `2026-10-31-harness-context-compaction-protocol.md` | Written, self-reviewed |
| 4 | `2026-10-31-herdr-customizations.md` | Written, self-reviewed |

All four plans are uncommitted in the working tree. Recommend committing them together (they're one logical unit — the platform-vision decomposition's implementation-plan phase) before choosing an execution path.
