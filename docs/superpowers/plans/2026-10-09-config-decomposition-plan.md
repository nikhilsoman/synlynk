# Config Decomposition (gh:#2101) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `.synlynk/config.json` into `workspace.json`, `billing.json`, and four fields folded into the existing `policy.json`, while `load_config()` keeps returning the exact same flat merged dict every one of its ~80+ call sites already expects.

**Architecture:** `synlynk/__init__.py` gains `load_workspace()` and `load_billing()`, each owning one slice of the current `load_config()` defaults dict and reading/writing its own file. A new `_migrate_legacy_config_if_needed()` does the one-time, idempotent split of a legacy `config.json` into the three target files (renaming the legacy file to `.bak` only after all three writes succeed). `load_config()` becomes a thin facade: run the migration, then merge `load_workspace()` + `load_billing()` + the four migrated policy fields into one dict. Every other direct `.synlynk/config.json` reader/writer in the codebase (`dispatch.py`, `qa_gate.py`, `uxcore.py`, `workspace.py`, `doctor.py`, `coldstart.py`, `selftest.py`, `db.py`, `parity.py`, and several more inside `__init__.py` itself) gets updated to target the file that now actually holds its key.

**Tech Stack:** Python 3 stdlib only (`json`, `os`, `tempfile`) — no new dependencies, consistent with `pyproject.toml`'s `dependencies=[]`.

**Reference spec:** `docs/superpowers/specs/2026-10-09-config-decomposition-design.md` (approved 2026-10-09; corrected during this plan's research for the `features`/`repo_id`/`dr_sync_path`/`mode` field-list gaps and the Section 7 gitignore-tracking direction — both corrections are in the spec file now, this plan reflects the corrected version).

---

## Task 1: Split `config_schema.py` into `WORKSPACE_SCHEMA` + `BILLING_SCHEMA`, extend `POLICY_SCHEMA`

**Files:**
- Modify: `synlynk/config_schema.py`
- Test: `tests/test_config_schema.py` (new file — none exists today for this module)

The current file (full contents, 81 lines) has one `CONFIG_SCHEMA` mixing workspace- and billing-bound fields, and a `POLICY_SCHEMA` with no fields for the four keys migrating in.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_schema.py
from synlynk.config_schema import validate, WORKSPACE_SCHEMA, BILLING_SCHEMA, POLICY_SCHEMA


def test_workspace_schema_accepts_valid_document():
    doc = {"schema_version": 1, "workspace_id": "ws-1", "local_fallback": "agy"}
    assert validate(doc, WORKSPACE_SCHEMA) == []


def test_workspace_schema_rejects_missing_schema_version():
    doc = {"workspace_id": "ws-1"}
    errors = validate(doc, WORKSPACE_SCHEMA)
    assert any("schema_version" in e for e in errors)


def test_billing_schema_accepts_valid_document():
    doc = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "harness_billing": {},
    }
    assert validate(doc, BILLING_SCHEMA) == []


def test_billing_schema_rejects_wrong_budget_type():
    doc = {"schema_version": 1, "budget": "not-a-dict", "harness_billing": {}}
    errors = validate(doc, BILLING_SCHEMA)
    assert any("budget" in e for e in errors)


def test_policy_schema_accepts_migrated_fields():
    doc = {
        "schema_version": 1,
        "repo_id": "synlynk",
        "qa_gate_mode": "block-only",
        "roles": {"claude": ["pm", "review"]},
        "story_classification": {"method": "heuristic"},
        "sentinel": {"dedup_window_seconds": 86400},
    }
    assert validate(doc, POLICY_SCHEMA) == []


def test_policy_schema_rejects_bad_qa_gate_mode_type():
    doc = {"schema_version": 1, "repo_id": "synlynk", "qa_gate_mode": 123}
    errors = validate(doc, POLICY_SCHEMA)
    assert any("qa_gate_mode" in e for e in errors)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_schema.py -v`
Expected: `ImportError: cannot import name 'WORKSPACE_SCHEMA'` (module doesn't define it yet)

- [ ] **Step 3: Replace `CONFIG_SCHEMA` with `WORKSPACE_SCHEMA`/`BILLING_SCHEMA`, extend `POLICY_SCHEMA`**

Replace lines 55–80 of `synlynk/config_schema.py` (the `CONFIG_SCHEMA` and `POLICY_SCHEMA` definitions) with:

```python
WORKSPACE_SCHEMA = {
    "fields": {
        "schema_version": {"type": int, "required": True},
        "workspace_id": {"type": str},
        "identity_slug": {"type": str},
        "local_fallback": {"type": str},
        "local_auto_threshold": {"type": (int, float)},
        "org": {"type": str},
        "owner": {"type": str},
        "repo": {"type": str},
        "project_id": {"type": str},
        "project_docs_dir": {"type": str},
        "repo_id": {"type": str},
        "dr_sync_path": {"type": str},
        "mode": {"type": str, "enum": ["solo", "team"]},
    }
}

BILLING_SCHEMA = {
    "fields": {
        "schema_version": {"type": int, "required": True},
        "budget": {"type": dict, "required": True, "fields": _BUDGET_FIELDS},
        "harness_billing": {"type": dict, "required": True},
        "payment_models": {"type": dict},
        "capability_sweep": {"type": dict},
    }
}

POLICY_SCHEMA = {
    "fields": {
        "schema_version": {"type": int, "required": True},
        "repo_id": {"type": str, "required": True},
        "capability_policy": {
            "type": dict,
            "fields": {
                "mode": {"type": str, "enum": ["empirical", "heuristic"]},
                "min_sample_size": {"type": int},
            },
        },
        "overrides": {"type": dict},
        "qa_gate_mode": {"type": str, "enum": ["block-only", "merge-restricted-classes"]},
        "roles": {"type": dict},
        "story_classification": {"type": dict},
        "sentinel": {"type": dict},
    }
}
```

`WORKSPACE_SCHEMA` deliberately does not enumerate every field from the spec's Section 2 list (e.g. `dispatch`, `nudges`, `agent_slots`) — the hand-rolled validator only needs to catch real failure modes (wrong type, missing required key), and those nested dicts have no fixed shape worth asserting on here. This matches the existing file's own stated scope ("key set... is small and known").

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config_schema.py -v`
Expected: 6 passed

- [ ] **Step 5: Check no other module imports the removed `CONFIG_SCHEMA` name**

Run: `grep -rn "CONFIG_SCHEMA" synlynk/ tests/`
Expected: no remaining references outside `config_schema.py` itself and the test file just written. (`doctor.py`'s `_hc_config_schema` — handled in Task 9 — imports it; confirm that grep result and leave it for Task 9 to fix in the same pass as the other `doctor.py` functions, don't fix it here.)

- [ ] **Step 6: Commit**

```bash
git add synlynk/config_schema.py tests/test_config_schema.py
git commit -m "$(cat <<'EOF'
feat(config): split CONFIG_SCHEMA into WORKSPACE_SCHEMA/BILLING_SCHEMA

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 2: Add `load_workspace()`, `load_billing()`, and the one-time migration

**Files:**
- Modify: `synlynk/__init__.py` (add new functions right after `_write_json_atomic`, which ends at line 1016, and before the ANSI-helper block at line 1018)
- Test: `tests/test_config_split.py` (new file)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_config_split.py
import json
import os
import synlynk


def test_load_workspace_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ws = synlynk.load_workspace()
    assert ws["local_fallback"] == "agy"
    assert ws["dispatch"]["stacking"] == "auto"
    assert ws["mode"] == "solo"


def test_load_billing_defaults_when_no_files_exist(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    billing = synlynk.load_billing()
    assert billing["budget"] == {"limit_usd": 10.0, "limit_requests": 100}
    assert "claude" in billing["harness_billing"] or billing["harness_billing"] == {}


def test_load_workspace_reads_existing_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"schema_version": 1, "local_fallback": "codex"}, f)
    assert synlynk.load_workspace()["local_fallback"] == "codex"


def test_migration_splits_legacy_config_into_three_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    legacy = {
        "schema_version": 1,
        "local_fallback": "codex",
        "budget": {"limit_usd": 25.0, "limit_requests": 50},
        "harness_billing": {},
        "qa_gate_mode": "merge-restricted-classes",
        "roles": {"claude": ["pm"]},
    }
    with open(".synlynk/config.json", "w") as f:
        json.dump(legacy, f)

    synlynk._migrate_legacy_config_if_needed()

    assert os.path.exists(".synlynk/workspace.json")
    assert os.path.exists(".synlynk/billing.json")
    assert os.path.exists(".synlynk/policy.json")
    assert os.path.exists(".synlynk/config.json.bak")
    assert not os.path.exists(".synlynk/config.json")

    with open(".synlynk/workspace.json") as f:
        workspace = json.load(f)
    assert workspace["local_fallback"] == "codex"
    assert "budget" not in workspace

    with open(".synlynk/billing.json") as f:
        billing = json.load(f)
    assert billing["budget"] == {"limit_usd": 25.0, "limit_requests": 50}

    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    assert policy["qa_gate_mode"] == "merge-restricted-classes"
    assert policy["roles"] == {"claude": ["pm"]}


def test_migration_preserves_existing_policy_json_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1, "qa_gate_mode": "block-only"}, f)
    with open(".synlynk/policy.json", "w") as f:
        json.dump({"schema_version": 1, "repo_id": "synlynk", "overrides": {"foo": "bar"}}, f)

    synlynk._migrate_legacy_config_if_needed()

    with open(".synlynk/policy.json") as f:
        policy = json.load(f)
    assert policy["repo_id"] == "synlynk"
    assert policy["overrides"] == {"foo": "bar"}
    assert policy["qa_gate_mode"] == "block-only"


def test_migration_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1}, f)
    synlynk._migrate_legacy_config_if_needed()
    workspace_mtime = os.path.getmtime(".synlynk/workspace.json")

    synlynk._migrate_legacy_config_if_needed()

    assert os.path.getmtime(".synlynk/workspace.json") == workspace_mtime


def test_migration_noop_when_no_legacy_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk._migrate_legacy_config_if_needed()
    assert not os.path.exists(".synlynk")


def test_migration_aborts_on_corrupt_policy_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1}, f)
    with open(".synlynk/policy.json", "w") as f:
        f.write("{not valid json")

    synlynk._migrate_legacy_config_if_needed()

    assert os.path.exists(".synlynk/config.json")
    assert not os.path.exists(".synlynk/config.json.bak")
    assert not os.path.exists(".synlynk/workspace.json")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_split.py -v`
Expected: `AttributeError: module 'synlynk' has no attribute 'load_workspace'`

- [ ] **Step 3: Implement `load_workspace()`, `load_billing()`, and the migration**

Insert the following into `synlynk/__init__.py` immediately after `_write_json_atomic()` (after line 1016, before the `# ANSI helpers` comment on line 1018):

```python
_WORKSPACE_KEYS = [
    "org", "owner", "repo", "project_id", "identity_slug", "project_docs_dir",
    "workspace_id", "agent_slots", "workgroup_agents", "agents", "team",
    "sync_endpoint", "dispatch", "local_auto_threshold", "local_fallback",
    "watch_interval_seconds", "auto_smoke_test", "auto_launch_after_wizard",
    "dispatch_mode", "fenced_commands", "nudges", "exec_timeout_minutes",
    "stall_timeout_minutes", "review_stall_timeout_minutes", "swarm_runners",
    "last_housekeeping_date", "features", "repo_id", "dr_sync_path", "mode",
]
_BILLING_KEYS = ["budget", "harness_billing", "payment_models", "capability_sweep"]
_POLICY_MIGRATED_KEYS = ["qa_gate_mode", "roles", "story_classification", "sentinel"]


def load_workspace() -> dict:
    """Loads .synlynk/workspace.json with schema-v1 defaults."""
    defaults = {
        "schema_version": 1,
        "dispatch": {"stacking": "auto", "gate_suite_cmd": ""},
        "local_auto_threshold": 0.5,
        "local_fallback": "agy",
        "watch_interval_seconds": 30,
        "auto_smoke_test": False,
        "auto_launch_after_wizard": True,
        "dispatch_mode": "daily-grind",
        "fenced_commands": ["dispatch", "jobs", "exec", "schedule"],
        "nudges": {"enabled": True, "dismissed_ids": [], "last_shown": {}},
        "org": None,
        "owner": None,
        "repo": None,
        "project_id": None,
        "identity_slug": None,
        "project_docs_dir": "project-docs",
        "agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"},
        "workgroup_agents": [],
        "last_housekeeping_date": None,
        "team": None,
        "sync_endpoint": None,
        "exec_timeout_minutes": 30,
        "stall_timeout_minutes": 30,
        "swarm_runners": {"default": "local", "enabled": ["local"], "timeout_seconds": 900},
        "review_stall_timeout_minutes": 90,
        "agents": {},
        "features": {},
        "repo_id": None,
        "dr_sync_path": None,
        "mode": "solo",
    }
    config_file = ".synlynk/workspace.json"
    if not os.path.exists(config_file):
        return defaults
    try:
        with open(config_file) as f:
            config = json.load(f)
        for key, val in defaults.items():
            if key not in config:
                config[key] = val
        for key, val in defaults["dispatch"].items():
            if key not in config.get("dispatch", {}):
                config.setdefault("dispatch", {})[key] = val
        for key, val in defaults["nudges"].items():
            if key not in config.get("nudges", {}):
                config.setdefault("nudges", {})[key] = val
        return config
    except (json.JSONDecodeError, IOError):
        return defaults


def load_billing() -> dict:
    """Loads .synlynk/billing.json with schema-v1 defaults."""
    defaults = {
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
        "payment_models": {},
        "harness_billing": _default_harness_billing(),
        "capability_sweep": {"cost_cap_usd": 10.0},
    }
    config_file = ".synlynk/billing.json"
    if not os.path.exists(config_file):
        return defaults
    try:
        with open(config_file) as f:
            config = json.load(f)
        has_harness_billing = "harness_billing" in config
        for key, val in defaults.items():
            if key not in config:
                config[key] = {} if key == "harness_billing" else val
        for key, val in defaults["budget"].items():
            if key not in config.get("budget", {}):
                config.setdefault("budget", {})[key] = val
        if not isinstance(config.get("harness_billing"), dict):
            config["harness_billing"] = _default_harness_billing()
        elif not config["harness_billing"] and has_harness_billing:
            config["harness_billing"] = _default_harness_billing()
        for billing in config["harness_billing"].values():
            if isinstance(billing, dict):
                billing.setdefault("payment_mode", "pay_as_you_go")
                billing.setdefault("monthly_base_fee_usd", billing.get("subscription_fee_usd", 0.0))
                billing.setdefault("projected_monthly_tokens", 10_000_000)
                billing.setdefault("allow_extra_usage", False)
                billing.setdefault("extra_usage_cap_usd", None)
        return config
    except (json.JSONDecodeError, IOError):
        return defaults


def _read_raw_policy() -> dict:
    """Raw (undefaulted) read of .synlynk/policy.json, or {} if absent/corrupt."""
    try:
        with open(".synlynk/policy.json") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _read_policy_migrated_fields() -> dict:
    """Reads the four fields migrated into policy.json (qa_gate_mode, roles,
    story_classification, sentinel), applying the same defaults load_config()
    applied to them before the split. Not sourced via load_policy() — that
    function only surfaces its own defaults/overrides merge tier, not these
    plain top-level sibling fields."""
    capability_roles = _load_capability_roles()
    policy = _read_raw_policy()
    result = {
        "roles": capability_roles if capability_roles is not None else _default_roles_map(),
        "story_classification": {"method": "heuristic"},
        "qa_gate_mode": "block-only",
        "sentinel": {
            "dedup_window_seconds": 86400,
            "active_ttl_seconds": {"CRITICAL": 180 * 86400, "WARN": 180 * 86400, "INFO": 180 * 86400},
        },
    }
    if capability_roles is None and "roles" in policy:
        result["roles"] = policy["roles"]
    for key in ("story_classification", "qa_gate_mode", "sentinel"):
        if key in policy:
            result[key] = policy[key]
    return result


def _migrate_legacy_config_if_needed() -> None:
    """One-time, idempotent split of a legacy .synlynk/config.json into
    workspace.json + billing.json + policy.json, then renames the legacy
    file to config.json.bak. No-op if workspace.json or billing.json already
    exist, or if there is no legacy config.json to migrate."""
    legacy_path = ".synlynk/config.json"
    workspace_path = ".synlynk/workspace.json"
    billing_path = ".synlynk/billing.json"
    policy_path = ".synlynk/policy.json"

    if not os.path.exists(legacy_path):
        return
    if os.path.exists(workspace_path) or os.path.exists(billing_path):
        return

    try:
        with open(legacy_path) as f:
            legacy = json.load(f)
    except (json.JSONDecodeError, IOError):
        return
    if not isinstance(legacy, dict):
        return

    workspace_payload = {"schema_version": 1}
    workspace_payload.update({k: legacy[k] for k in _WORKSPACE_KEYS if k in legacy})

    billing_payload = {"schema_version": 1}
    billing_payload.update({k: legacy[k] for k in _BILLING_KEYS if k in legacy})

    policy_payload = _read_raw_policy()
    policy_payload.update({k: legacy[k] for k in _POLICY_MIGRATED_KEYS if k in legacy})
    policy_payload.setdefault("schema_version", 1)

    _write_json_atomic(workspace_path, workspace_payload)
    _write_json_atomic(billing_path, billing_payload)
    _write_json_atomic(policy_path, policy_payload)
    os.replace(legacy_path, legacy_path + ".bak")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config_split.py -v`
Expected: 8 passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_config_split.py
git commit -m "$(cat <<'EOF'
feat(config): add load_workspace()/load_billing() and legacy-config migration

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 3: Rewrite `load_config()` as a facade over the split files

**Files:**
- Modify: `synlynk/__init__.py:1080-1162` (the current `load_config()` body)
- Test: `tests/test_config_split.py` (append)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_config_split.py`:

```python
def test_load_config_facade_matches_old_flat_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    config = synlynk.load_config()
    assert config["schema_version"] == 1
    assert config["budget"] == {"limit_usd": 10.0, "limit_requests": 100}
    assert config["local_fallback"] == "agy"
    assert config["qa_gate_mode"] == "block-only"
    assert config["dispatch"]["stacking"] == "auto"


def test_load_config_triggers_migration_on_first_call(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w") as f:
        json.dump({"schema_version": 1, "local_fallback": "codex"}, f)

    config = synlynk.load_config()

    assert config["local_fallback"] == "codex"
    assert os.path.exists(".synlynk/workspace.json")
    assert os.path.exists(".synlynk/config.json.bak")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_config_split.py -k facade_matches -v`
Expected: `KeyError: 'qa_gate_mode'` or similar — old `load_config()` body hasn't been swapped yet, so this passes already; confirm instead by temporarily checking the migration test fails (no workspace.json yet, since old `load_config()` never migrates):

Run: `pytest tests/test_config_split.py -k triggers_migration -v`
Expected: FAIL — `assert os.path.exists(".synlynk/workspace.json")` is False

- [ ] **Step 3: Replace `load_config()`'s body**

Replace lines 1080–1162 of `synlynk/__init__.py` (the entire current `load_config()` function) with:

```python
def load_config() -> dict:
    """Facade over workspace.json + billing.json + the four migrated
    policy.json fields, preserving load_config()'s pre-split flat-dict
    shape for all existing call sites. Runs the one-time legacy-config
    migration on every call; the migration itself is a cheap no-op once
    the split files exist."""
    _migrate_legacy_config_if_needed()
    config = {"schema_version": 1}
    config.update(load_workspace())
    config.update(load_billing())
    config.update(_read_policy_migrated_fields())
    return config
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_config_split.py -v`
Expected: 10 passed

- [ ] **Step 5: Run the full existing test suite to check facade compatibility**

Run: `pytest tests/ -x -q 2>&1 | tail -60`
Expected: the pre-existing `test_qa_gate.py` and `test_uxcore_writes.py` tests that write directly to `.synlynk/config.json` will now fail (they're fixed in Tasks 6/7, not this one) — confirm the *only* new failures are in those two files plus `test_doctor_config_schema.py` (fixed in Task 9) and `test_dispatch_fallback_logging.py`/`test_dispatch_auto_routing.py` (confirm these still pass unmodified — they mock the function objects directly, not the file path, so the facade change shouldn't touch them). If any other test newly fails, stop and investigate before proceeding — that's an unaccounted-for `load_config()` call site.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_config_split.py
git commit -m "$(cat <<'EOF'
refactor(config): rewrite load_config() as a facade over the split files

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 4: Route `cmd_config_set()` to the correct target file

**Files:**
- Modify: `synlynk/__init__.py:1165-1171`
- Test: `tests/test_synlynk.py` (search for existing `cmd_config_set` tests first)

- [ ] **Step 1: Check for existing coverage**

Run: `grep -n "cmd_config_set" tests/test_synlynk.py`

If a test exists, read it in full before writing new ones so you extend rather than duplicate.

- [ ] **Step 2: Write the failing tests**

Add to `tests/test_synlynk.py` (or create `tests/test_config_split.py` additions if no existing `cmd_config_set` coverage was found):

```python
def test_cmd_config_set_routes_workspace_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    synlynk.cmd_config_set("local_fallback", "codex")
    with open(".synlynk/workspace.json") as f:
        data = json.load(f)
    assert data["local_fallback"] == "codex"
    assert not os.path.exists(".synlynk/billing.json") or "local_fallback" not in json.load(open(".synlynk/billing.json"))


def test_cmd_config_set_routes_billing_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    synlynk.cmd_config_set("budget", {"limit_usd": 5.0, "limit_requests": 10})
    with open(".synlynk/billing.json") as f:
        data = json.load(f)
    assert data["budget"] == {"limit_usd": 5.0, "limit_requests": 10}


def test_cmd_config_set_routes_policy_key_preserving_other_policy_content(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/policy.json", "w") as f:
        json.dump({"schema_version": 1, "repo_id": "synlynk"}, f)
    synlynk.cmd_config_set("qa_gate_mode", "merge-restricted-classes")
    with open(".synlynk/policy.json") as f:
        data = json.load(f)
    assert data["qa_gate_mode"] == "merge-restricted-classes"
    assert data["repo_id"] == "synlynk"
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_synlynk.py -k cmd_config_set_routes -v`
Expected: FAIL — current `cmd_config_set()` always writes `.synlynk/config.json`

- [ ] **Step 4: Implement the routing**

Replace `synlynk/__init__.py:1165-1171` with:

```python
def cmd_config_set(key: str, value) -> None:
    """Set a top-level config key, routed to whichever of
    workspace.json/billing.json/policy.json now owns that key."""
    _migrate_legacy_config_if_needed()
    if key in _BILLING_KEYS:
        path = ".synlynk/billing.json"
        data = load_billing()
    elif key in _POLICY_MIGRATED_KEYS:
        path = ".synlynk/policy.json"
        data = _read_raw_policy()
        data.setdefault("schema_version", 1)
    else:
        path = ".synlynk/workspace.json"
        data = load_workspace()
    data[key] = value
    _write_json_atomic(path, data)
    print(f"  ✓ {key} = {value!r} saved to {path}")
```

Note the signature change `value: str` → `value` (no annotation): the existing CLI entry point always passes a string from argv, but the new tests above pass a dict directly for `budget`. Check the CLI wiring:

Run: `grep -n "cmd_config_set(" synlynk/cli.py synlynk/*.py | grep -v "def cmd_config_set"`

If the only caller passes a raw argv string, leave the CLI wiring as-is (it still passes a string; the function itself no longer declares a type it doesn't enforce anyway) — the dict-accepting test above is exercising the Python API directly, which is a legitimate use of `cmd_config_set()` as a function, not just a CLI shim.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_synlynk.py -k cmd_config_set_routes -v`
Expected: 3 passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_synlynk.py
git commit -m "$(cat <<'EOF'
fix(config): route cmd_config_set() to the correct split file by key

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 5: Update `dispatch.py`'s direct config readers

**Files:**
- Modify: `synlynk/dispatch.py:120-215` (`_read_local_fallback`, `_read_local_threshold`, `_resolve_dispatch_agent`)
- Test: `tests/test_dispatch_auto_routing.py`, `tests/test_dispatch_fallback_logging.py` (verify unmodified)

These two tests already mock `_read_local_fallback`/`_read_local_threshold` as whole-function replacements (`patch.object(dispatch_mod, "_read_local_fallback", ...)` and monkeypatched lambdas), so changing what's *inside* those functions doesn't break either test file — confirmed in Task 3's Step 5 full-suite run. This task only needs to change the function bodies themselves.

- [ ] **Step 1: Read current implementation**

Run: `sed -n '120,170p' synlynk/dispatch.py`

- [ ] **Step 2: Write a new direct test for the updated read path**

```python
# Add to tests/test_dispatch_auto_routing.py
import json
import os


def test_read_local_fallback_reads_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"local_fallback": "codex"}, f)
    import synlynk.dispatch as dispatch_mod
    assert dispatch_mod._read_local_fallback() == "codex"


def test_read_local_threshold_reads_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"local_auto_threshold": 0.9}, f)
    import synlynk.dispatch as dispatch_mod
    assert dispatch_mod._read_local_threshold() == 0.9
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_auto_routing.py -k reads_workspace_json -v`
Expected: FAIL — functions still read `.synlynk/config.json`

- [ ] **Step 4: Update the three functions**

Each of `_read_local_fallback(config_path=".synlynk/config.json")` and `_read_local_threshold(config_path=".synlynk/config.json")` hand-rolls its own `open()`/`json.load()` against the default path. Change the default path argument on both from `".synlynk/config.json"` to `".synlynk/workspace.json"` — keep the `config_path` parameter itself (existing callers/tests that pass it explicitly, if any, still work; `grep -rn "_read_local_fallback(" synlynk/ tests/` and `grep -rn "_read_local_threshold(" synlynk/ tests/` to confirm none pass an explicit `config_path=".synlynk/config.json"` that would now silently read the empty/migrated-away legacy file — if any do, update that call site's literal to `.synlynk/workspace.json` too). Leave `_resolve_dispatch_agent()` itself unchanged — it only calls the two functions above, never touches a path directly.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_auto_routing.py tests/test_dispatch_fallback_logging.py -v`
Expected: all passed, including the 2 new tests

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_auto_routing.py
git commit -m "$(cat <<'EOF'
fix(dispatch): read local_fallback/local_auto_threshold from workspace.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 6: Update `qa_gate.py`'s `_qa_gate_mode()` to read `policy.json`

**Files:**
- Modify: `synlynk/qa_gate.py:18-24`
- Test: `tests/test_qa_gate.py:16-32` (rewrite the three tests that write to `config.json`)

- [ ] **Step 1: Update the existing tests first (they currently assert the old, now-wrong, source file)**

Replace `tests/test_qa_gate.py` lines 16–32 with:

```python
def test_qa_gate_mode_defaults_to_block_only_when_key_absent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text('{}')
    assert _qa_gate_mode() == 'block-only'


def test_qa_gate_mode_reads_configured_value(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "policy.json").write_text('{"qa_gate_mode": "merge-restricted-classes"}')
    assert _qa_gate_mode() == 'merge-restricted-classes'


def test_qa_gate_mode_defaults_to_block_only_when_config_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert _qa_gate_mode() == 'block-only'
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_qa_gate.py -k qa_gate_mode -v`
Expected: FAIL — `_qa_gate_mode()` still reads `config.json`

- [ ] **Step 3: Implement**

Replace `synlynk/qa_gate.py:18-24`:

```python
def _qa_gate_mode() -> str:
    try:
        with open(".synlynk/policy.json") as f:
            policy = json.load(f)
    except Exception:
        return "block-only"
    return policy.get("qa_gate_mode") or "block-only"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_qa_gate.py -v`
Expected: all passed, including `test_load_config_defaults_qa_gate_mode_to_block_only` and `test_load_config_preserves_explicit_qa_gate_mode` at lines 164–175, which go through `synlynk.load_config()` (the facade) rather than `_qa_gate_mode()` directly — these should already pass unmodified since Task 3's facade still surfaces `qa_gate_mode` in its flat dict.

- [ ] **Step 5: Commit**

```bash
git add synlynk/qa_gate.py tests/test_qa_gate.py
git commit -m "$(cat <<'EOF'
fix(qa-gate): read qa_gate_mode from policy.json, not config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 7: Update `uxcore.py`'s `FeatureFlags.is_enabled()` to read `workspace.json`

**Files:**
- Modify: `synlynk/uxcore.py` (the `FeatureFlags.is_enabled` staticmethod, ~line 513-520 per the earlier read)
- Test: `tests/test_uxcore_writes.py:15-29`

- [ ] **Step 1: Update the existing tests**

Replace `tests/test_uxcore_writes.py` lines 15–29:

```python
def test_feature_flags_missing_key_is_disabled(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({}, f)
    assert uxcore.FeatureFlags.is_enabled("gantt_view", tier="individual") is False


def test_feature_flags_enabled_for_tier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"features": {"gantt_view": ["individual", "team"]}}, f)
    assert uxcore.FeatureFlags.is_enabled("gantt_view", tier="individual") is True
    assert uxcore.FeatureFlags.is_enabled("gantt_view", tier="enterprise") is False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_uxcore_writes.py -k feature_flags -v`
Expected: FAIL — `is_enabled()` still reads `config.json`

- [ ] **Step 3: Implement**

In `synlynk/uxcore.py`, change:

```python
    @staticmethod
    def is_enabled(flag: str, tier: str) -> bool:
        try:
            with open(".synlynk/config.json") as f:
                config = json.load(f)
        except Exception:
            return False
        tiers_for_flag = config.get("features", {}).get(flag, [])
        return tier in tiers_for_flag
```

to:

```python
    @staticmethod
    def is_enabled(flag: str, tier: str) -> bool:
        try:
            with open(".synlynk/workspace.json") as f:
                workspace = json.load(f)
        except Exception:
            return False
        tiers_for_flag = workspace.get("features", {}).get(flag, [])
        return tier in tiers_for_flag
```

Also update the class docstring's `.synlynk/config.json` mention to `.synlynk/workspace.json`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_uxcore_writes.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/uxcore.py tests/test_uxcore_writes.py
git commit -m "$(cat <<'EOF'
fix(uxcore): read FeatureFlags from workspace.json, not config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 8: Update `workspace.py`'s `add_repo()` to read/write `workspace.json`

**Files:**
- Modify: `synlynk/workspace.py:25-38`
- Test: `tests/test_workspace.py` (check for existing coverage first)

- [ ] **Step 1: Check existing coverage**

Run: `grep -n "add_repo\|configured_identity_slug" tests/test_workspace.py`

Read any existing test in full before extending.

- [ ] **Step 2: Write the failing test**

```python
# Add to tests/test_workspace.py
import json
import os
from synlynk.workspace import add_repo


def test_add_repo_reads_and_writes_repo_id_in_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w") as f:
        json.dump({"identity_slug": "test-product"}, f)

    result = add_repo(nwo="org/myrepo", repo_path=".")

    with open(".synlynk/workspace.json") as f:
        workspace = json.load(f)
    assert workspace["repo_id"] == "myrepo" or workspace["repo_id"] == result["repo_id"]
    assert not os.path.exists(".synlynk/config.json")
```

Note: this test needs `configured_identity_slug()` (from `synlynk.product_store`) to resolve against `.synlynk/workspace.json` too — check that function's own source before assuming it already reads the right file:

Run: `grep -n "def configured_identity_slug" -A 15 synlynk/product_store.py`

If `configured_identity_slug()` itself hardcodes `.synlynk/config.json`, add it to this task's scope (same pattern: change the hardcoded path literal to `.synlynk/workspace.json`) and add a matching test for it in `tests/test_product_store.py` (check if that file exists first; create it if not, following the same `tmp_path`/`monkeypatch.chdir` pattern as the other tests in this plan).

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_workspace.py -k repo_id_in_workspace_json -v`
Expected: FAIL — `add_repo()` still reads/writes `.synlynk/config.json`

- [ ] **Step 4: Implement**

In `synlynk/workspace.py`, change `add_repo()` (lines 25–38):

```python
def add_repo(nwo: Optional[str] = None, repo_path: str = ".") -> dict:
    """Register a clone without creating an App or calling GitHub."""
    repo = Path(repo_path).resolve()
    slug = configured_identity_slug(repo)
    if not slug:
        raise RuntimeError(
            "workspace add-repo requires .synlynk/workspace.json with identity_slug; refusing to guess the product"
        )
    config_path = repo / ".synlynk" / "workspace.json"
    config = _read_json(config_path)
    nwo = (nwo or "").strip() or repo.name
    repo_id = config.get("repo_id") or nwo or repo.name
    config["repo_id"] = repo_id
    _write_json(config_path, config)
    ...
```

(the rest of the function body, from `types = load_types(slug)` onward, is unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_workspace.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/workspace.py synlynk/product_store.py tests/test_workspace.py tests/test_product_store.py
git commit -m "$(cat <<'EOF'
fix(workspace): read/write repo_id in workspace.json, not config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

(Omit `synlynk/product_store.py` from the `git add` if Step 2's check found it already reads the right file / doesn't exist as a concern.)

---

## Task 9: Update `doctor.py`'s health checks

**Files:**
- Modify: `synlynk/doctor.py` (`_hc_project_init`, `_hc_identity_slug`, `_hc_config_schema`, `_hc_spof_audit` — `_hc_policy_schema` already targets `policy.json` and needs no path change, but its `POLICY_SCHEMA` import now has extra fields from Task 1, so just re-verify it)
- Test: `tests/test_doctor_config_schema.py`, `tests/test_pm_sweep_watchdog.py`, `tests/test_synlynk.py::test_hc_project_init_ok`

- [ ] **Step 1: Read current bodies**

Run: `sed -n '75,150p;985,1005p' synlynk/doctor.py`

- [ ] **Step 2: Update `test_doctor_config_schema.py`**

Read the current test file in full (`cat -n tests/test_doctor_config_schema.py`) before editing — it currently seeds `.synlynk/config.json` and checks `_hc_config_schema()`'s verdict. Update its fixture setup to seed `.synlynk/workspace.json` and `.synlynk/billing.json` instead (both now need to independently validate against `WORKSPACE_SCHEMA`/`BILLING_SCHEMA`), matching whatever pass/fail assertions the existing two tests make.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_doctor_config_schema.py -v`
Expected: FAIL — `_hc_config_schema()` still reads/validates `config.json` against the now-removed `CONFIG_SCHEMA` name

- [ ] **Step 4: Implement**

- `_hc_config_schema()`: change its import from `CONFIG_SCHEMA` to `WORKSPACE_SCHEMA, BILLING_SCHEMA`; validate `.synlynk/workspace.json` against `WORKSPACE_SCHEMA` and `.synlynk/billing.json` against `BILLING_SCHEMA` (run both, combine the error lists, same overall health-check contract: pass only if both are clean).
- `_hc_project_init()`: wherever it checks `os.path.exists(".synlynk/config.json")` as a signal that `synlynk init` has run, change it to check for `.synlynk/workspace.json` OR the legacy `.synlynk/config.json` (so a freshly-cloned legacy repo that hasn't yet triggered migration still reports "initialized").
- `_hc_identity_slug()`: change its direct config.json read to read `.synlynk/workspace.json`.
- `_hc_spof_audit()`: read its current body from Step 1's output; update any `.synlynk/config.json` path literal it contains to `.synlynk/workspace.json` (SPOF = single point of failure audit — this almost certainly checks for the existence of exactly one canonical config source, so update the literal path it's auditing).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_doctor_config_schema.py tests/test_pm_sweep_watchdog.py tests/test_synlynk.py -k "hc_" -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/doctor.py tests/test_doctor_config_schema.py
git commit -m "$(cat <<'EOF'
fix(doctor): validate workspace.json/billing.json, not legacy config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 10: Update `coldstart.py`'s init-detection check

**Files:**
- Modify: `synlynk/coldstart.py:195-220`
- Test: check existing coverage, extend if present

- [ ] **Step 1: Read current implementation**

Run: `sed -n '195,220p' synlynk/coldstart.py`

- [ ] **Step 2: Write the failing test**

```python
# Add to tests/test_coldstart.py (check file exists first: ls tests/test_coldstart.py)
import os


def test_cmd_start_detects_init_via_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    open(".synlynk/workspace.json", "w").write("{}")
    from synlynk.coldstart import cmd_start
    # Assert whatever cmd_start()'s init-detected branch does differently
    # from its not-initialized branch — read the function body from Step 1
    # to know the exact observable (return value, printed string, etc.)
    # before writing this assertion.
```

This test's body is intentionally left to be finished once Step 1's read reveals the exact observable `cmd_start()` produces on the init-detected path — do not guess at the assertion; `grep -n "def cmd_start" -A 40 synlynk/coldstart.py` first and mirror whatever existing test(s) for `cmd_start()` already assert for the "already initialized" case, just swapping the seed file.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_coldstart.py -k workspace_json -v`
Expected: FAIL

- [ ] **Step 4: Implement**

Change the `os.path.exists(".synlynk/config.json")` check at `coldstart.py:195-220` to check `.synlynk/workspace.json` OR the legacy `.synlynk/config.json` (same reasoning as Task 9's `_hc_project_init` — a not-yet-migrated legacy repo is still "initialized").

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_coldstart.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/coldstart.py tests/test_coldstart.py
git commit -m "$(cat <<'EOF'
fix(coldstart): detect init via workspace.json or legacy config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 11: Update `selftest.py`'s bootstrap commit and `init()`'s fresh-project path

**Files:**
- Modify: `synlynk/selftest.py:90-115`
- No change needed to `init()` itself (see rationale below)

- [ ] **Step 1: Confirm `init()` needs no code change**

`init()` (line 2990) writes a legacy-shaped `config.json` from its template (lines 3145–3158) for a brand-new project, same as it does today. This plan does **not** change that — the very next `load_config()` call (which happens almost immediately after `init()` runs, e.g. via `generate_context()` or any subsequent command) triggers `_migrate_legacy_config_if_needed()` and splits it into the three target files automatically. Changing `init()` itself to emit `workspace.json`/`billing.json` directly would duplicate the split logic in two places for no behavioral benefit — confirm this by running:

Run: `grep -n "load_config()" synlynk/__init__.py | grep -A0 -B0 "320[0-9]\|32[1-9][0-9]\|33[0-9][0-9]"`

to check whether any code between `init()`'s config-write (line ~3158) and its return calls `load_config()` already in the same invocation — if so, migration happens within the same `synlynk init` run; if not, it happens on the *next* command, which is still correct (idempotent, no data loss either way).

- [ ] **Step 2: Read `selftest.py`'s bootstrap commit**

Run: `sed -n '90,115p' synlynk/selftest.py`

- [ ] **Step 3: Write the failing test**

```python
# Add to tests/test_selftest.py (check file exists: ls tests/test_selftest.py)
# After locating the bootstrap-commit code from Step 2, assert the git add
# list it builds includes workspace.json/billing.json once migration has
# run, instead of a hardcoded config.json. Mirror whatever existing selftest
# test fixture already exercises this bootstrap path.
```

Read the existing test file in full before writing this — selftest's test suite likely runs the whole selftest flow end-to-end in a tmp dir, so the fix may just be: let migration run naturally and assert the final `git ls-files` includes the new filenames, rather than hand-asserting the `git add` argument list.

- [ ] **Step 4: Implement**

Change the `git add .synlynk/config.json project-docs/.gitkeep` line at `selftest.py:90-115` to `git add .synlynk/workspace.json .synlynk/billing.json .synlynk/policy.json project-docs/.gitkeep` — but only after confirming (via Step 1's reasoning) that by the time this line runs, `load_config()` has already been called at least once in the same selftest flow so the split files actually exist on disk to add. If selftest's flow calls `init()` and then exits without any `load_config()` call before this git-add line, insert an explicit `load_config()` call (or `_migrate_legacy_config_if_needed()`) immediately before it to force migration first.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_selftest.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/selftest.py tests/test_selftest.py
git commit -m "$(cat <<'EOF'
fix(selftest): bootstrap-commit the split config files, not legacy config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 12: Update the remaining direct readers inside `synlynk/__init__.py` itself

**Files:**
- Modify: `synlynk/__init__.py` — `_docs_dir()` (~line 1030), `_dr_sync()` (~line 659), `_update_config()` (~line 2096), `_run_daily_housekeeping()`'s existence guard (~line 2089), and the two reset/re-init preview blocks (~lines 1243 and 1360)
- Test: extend whichever test files already cover these (`grep -rln` each function name under `tests/`)

- [ ] **Step 1: Read each site in full**

Run: `sed -n '655,672p;1030,1055p;1238,1252p;1355,1370p;2088,2104p' synlynk/__init__.py`

- [ ] **Step 2: For each site, write/extend a failing test seeding `.synlynk/workspace.json` instead of `.synlynk/config.json`**

For `_docs_dir()` (reads `project_docs_dir`) and `_dr_sync()` (reads `dr_sync_path`), both keys now live in `workspace.json` per Task 2's `_WORKSPACE_KEYS`. Locate their existing tests first:

Run: `grep -rln "_docs_dir\|_dr_sync" tests/`

Extend each located test to seed `.synlynk/workspace.json` instead of `.synlynk/config.json` and confirm it fails against the current (unmodified) implementation.

- [ ] **Step 3: Implement each**

- `_docs_dir()`: change its `config_file = ".synlynk/config.json"` literal (line 1037) to `.synlynk/workspace.json`.
- `_dr_sync()`: change its `cfg_path = os.path.join('.synlynk', 'config.json')` literal (line 660) to `os.path.join('.synlynk', 'workspace.json')`.
- `_update_config(updates: dict)` (line ~2096): this function merges arbitrary `updates` into "config" and writes it back as one flat file — with the split, a single `updates` dict can span multiple target files. Change it to partition `updates` by `_WORKSPACE_KEYS`/`_BILLING_KEYS`/`_POLICY_MIGRATED_KEYS` (same partitioning logic as `_migrate_legacy_config_if_needed()`) and write each non-empty partition to its own file via `_write_json_atomic`, reading each target's current content first (`load_workspace()`/`load_billing()`/`_read_raw_policy()`) so the merge doesn't clobber unrelated keys already in that file.
- `_run_daily_housekeeping()`'s existence guard (line ~2089, `if not os.path.exists(config_path): return` where `config_path = ".synlynk/config.json"`): change the guard to check `.synlynk/workspace.json` OR the legacy path (same "not yet migrated but still initialized" reasoning as Tasks 9–10).
- The two reset/re-init preview blocks (lines ~1243 and ~1360, both doing `cfg = json.load(open(".synlynk/config.json"))` wrapped in a bare `except Exception: pass` for a dry-run preview): change both path literals to `.synlynk/workspace.json`. These are read-only previews with existing fail-soft behavior (silently keep `cfg = {}` on any error), so no behavior change beyond pointing at the right file.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_synlynk.py -v` (and any other file touched in Step 2)
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/
git commit -m "$(cat <<'EOF'
fix(config): point remaining __init__.py config.json readers at workspace.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 13: Update `db.py`'s disaster-recovery sync functions

**Files:**
- Modify: `synlynk/db.py` — `_migrate_dr_mirror()` (~line 2624-2646) and the `setup_dr` block in `cmd_migrate()` (~line 2656-2671)
- Test: `tests/test_db.py:398`, `tests/test_migrate.py:156,168,548`

- [ ] **Step 1: Update the existing tests first**

In `tests/test_db.py`, line 398 currently does `json.dump({"dr_sync_path": str(dr_dir)}, f)` against a `config.json`-named file — read the surrounding fixture (`sed -n '385,405p' tests/test_db.py`) to find the exact filename variable, then change it to write `workspace.json` instead. Do the same for `tests/test_migrate.py` lines 156, 168, and 548 (`sed -n '150,172p;540,555p' tests/test_migrate.py` first).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_db.py tests/test_migrate.py -k dr -v`
Expected: FAIL — code still reads/writes `config.json`

- [ ] **Step 3: Implement**

In `synlynk/db.py`:
- `_migrate_dr_mirror()`: change `cfg_path = os.path.join(".synlynk", "config.json")` to `os.path.join(".synlynk", "workspace.json")`.
- `cmd_migrate()`'s `setup_dr` block: change `cfg_path = os.path.join(project_root, ".synlynk", "config.json")` to `os.path.join(project_root, ".synlynk", "workspace.json")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_db.py tests/test_migrate.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/db.py tests/test_db.py tests/test_migrate.py
git commit -m "$(cat <<'EOF'
fix(db): read/write dr_sync_path in workspace.json, not config.json

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 14: Update `parity.py`'s onboarding `.gitignore` template, `files_to_touch`, and gap-check messages

**Files:**
- Modify: `synlynk/parity.py` — `ensure_recursive_gitignore()` (~line 167-189), the `files_to_touch` list (~line 290-305), and the gap-check (~line 495-510)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_parity.py (check it exists: ls tests/test_parity.py)
def test_ensure_recursive_gitignore_tracks_split_config_files(tmp_path, monkeypatch):
    from synlynk.parity import ensure_recursive_gitignore
    ensure_recursive_gitignore(str(tmp_path))
    content = (tmp_path / ".gitignore").read_text()
    assert "!**/.synlynk/workspace.json" in content
    assert "!**/.synlynk/billing.json" in content
    assert "!**/.synlynk/config.json" in content  # still present for the legacy/.bak transition period
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_parity.py -k tracks_split_config -v`
Expected: FAIL — current rules string has no `workspace.json`/`billing.json` lines

- [ ] **Step 3: Implement**

In `synlynk/parity.py`'s `ensure_recursive_gitignore()`, change the `rules` string (currently lines ~175-181) from:

```python
    rules = (
        "\n# synlynk state & secret stores\n"
        "**/.synlynk/*\n"
        "!**/.synlynk/config.json\n"
        "!**/.synlynk/policy.json\n"
        "!**/.synlynk/roles.yaml\n"
        "!**/.synlynk/instructions.json\n"
        "!**/.synlynk/model_rates.json\n"
    )
```

to:

```python
    rules = (
        "\n# synlynk state & secret stores\n"
        "**/.synlynk/*\n"
        "!**/.synlynk/config.json\n"
        "!**/.synlynk/workspace.json\n"
        "!**/.synlynk/billing.json\n"
        "!**/.synlynk/policy.json\n"
        "!**/.synlynk/roles.yaml\n"
        "!**/.synlynk/instructions.json\n"
        "!**/.synlynk/model_rates.json\n"
    )
```

(`config.json` keeps its exception line — newly onboarded repos won't have a legacy file to migrate, but existing repos mid-migration still briefly have one, and the `.bak` file after migration should also stay out of the blanket ignore for visibility; if `.bak` visibility turns out unwanted, that's a follow-up, not blocking here.)

Then update the `files_to_touch` list (~line 290-305) to add `.synlynk/workspace.json` and `.synlynk/billing.json` alongside the existing `.synlynk/config.json` entry, and the gap-check block (~line 495-510) — read its current `.synlynk/config.json malformed/missing` cosmetic message check (`sed -n '495,510p' synlynk/parity.py`) and add equivalent checks for `.synlynk/workspace.json` and `.synlynk/billing.json`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_parity.py -v`
Expected: all passed

- [ ] **Step 5: Commit**

```bash
git add synlynk/parity.py tests/test_parity.py
git commit -m "$(cat <<'EOF'
feat(parity): track workspace.json/billing.json by default in onboarded repos

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 15: This repo's own dogfooded migration — track the split files, stop tracking `config.json`

**Files:**
- Modify: this repo's root `.gitignore`
- Modify: this repo's own `.synlynk/config.json` → split into `.synlynk/workspace.json`, `.synlynk/billing.json`, merged into `.synlynk/policy.json`

- [ ] **Step 1: Add the two new tracked exceptions to this repo's root `.gitignore`**

Run: `grep -n "synlynk/config.json\|synlynk/policy.json\|synlynk/\*" .gitignore`

Add `!**/.synlynk/workspace.json` and `!**/.synlynk/billing.json` immediately after the existing `!**/.synlynk/config.json`/`!**/.synlynk/policy.json` lines (mirroring Task 14's `parity.py` template change, applied directly to this repo's own already-bootstrapped `.gitignore`).

- [ ] **Step 2: Run the migration against this repo's real `.synlynk/config.json`**

Run: `python3 -c "import synlynk; synlynk._migrate_legacy_config_if_needed()"`

Verify:

Run: `ls -la .synlynk/workspace.json .synlynk/billing.json .synlynk/policy.json .synlynk/config.json.bak`
Expected: all four files exist; `.synlynk/config.json` no longer exists

- [ ] **Step 3: Verify the repo's own CLI still works end-to-end against the split files**

Run: `python3 bin/synlynk.py status`
Expected: runs without error (confirms `load_config()`'s facade is producing a working merged dict for this repo's real, previously-legacy-shaped config)

- [ ] **Step 4: Diff `policy.json` to confirm the four migrated keys landed alongside this repo's existing policy content**

Run: `git diff .synlynk/policy.json`
Expected: the diff shows `qa_gate_mode`/`roles`/`story_classification`/`sentinel` added as new top-level keys; every pre-existing key (`overrides`, `capability_policy`, `repo_id`, `schema_version`) unchanged.

- [ ] **Step 5: Stage and commit — add the new files, remove the old one, same commit**

```bash
git add .gitignore .synlynk/workspace.json .synlynk/billing.json .synlynk/policy.json
git rm .synlynk/config.json
git status --short
```

Review the `git status --short` output before committing — confirm no unrelated files are staged, and that `.synlynk/config.json.bak` is **not** staged (it should still be caught by the blanket `**/.synlynk/*` ignore rule, with no exception line added for `.bak` files; leave it on disk, untracked, as the local recoverability copy Section 6 of the spec describes — do not commit it).

```bash
git commit -m "$(cat <<'EOF'
chore(config): migrate this repo's own config.json into the split files

Runs the gh:#2101 migration against this repo's real dogfooded config,
replacing the tracked .synlynk/config.json sample with tracked
workspace.json/billing.json, and folding qa_gate_mode/roles/
story_classification/sentinel into the existing policy.json.

Refs gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

- [ ] **Step 6: Run the full test suite one final time**

Run: `pytest tests/ -q 2>&1 | tail -30`
Expected: all passed — this confirms the migration hasn't just worked in isolated `tmp_path` tests, but the repo's own real on-disk state is also consistent with everything built in Tasks 1–14.

---

## Self-Review Notes

- **Spec coverage:** Section 2 (file split + the three corrected scope-gap fields) → Tasks 1, 2. Section 3 (precedence) → Task 2's `load_workspace()`/`load_billing()` re-reading every call, no new merge tier. Section 4 (schema validation) → Task 1. Section 5 (API compatibility) → Tasks 3, 4, plus Task 3 Step 5's full-suite compatibility check. Section 6 (migration) → Task 2. Section 7 (corrected dogfooding direction) → Tasks 14, 15. Section 8 (error handling) → Task 2's corrupt-policy-abort test. Section 9 (testing) → covered throughout; Section 10 (out of scope) → untouched, no task references `capability-roles.json` consolidation or a `jsonschema` migration.
- **Call-site coverage:** every direct-read/write site found during research is now covered by a task: `dispatch.py` (5), `qa_gate.py` (6), `uxcore.py` (7), `workspace.py`/`product_store.py` (8), `doctor.py` (9), `coldstart.py` (10), `selftest.py`/`init()` (11), `__init__.py`'s own six remaining sites (12), `db.py` (13), `parity.py` (14), this repo's dogfooded files (15).
- **Placeholder scan:** Tasks 10 and 11 contain deliberately-scoped "read the function first, then assert/implement" steps rather than fully-blind code, because their exact current behavior (what `cmd_start()` prints/returns, whether `init()` calls `load_config()` before selftest's git-add line) wasn't read in full during this plan's research — these are investigation steps with a concrete, falsifiable completion condition (a specific grep/read command), not open-ended "add appropriate handling" placeholders.
- **Type consistency:** `_WORKSPACE_KEYS`/`_BILLING_KEYS`/`_POLICY_MIGRATED_KEYS` (introduced in Task 2) are the single source of truth for the partitioning, reused unchanged in Tasks 3, 4, and 12 (`_update_config()`) — no task redefines its own copy of these lists.
