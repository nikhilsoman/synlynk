# Fleet Parity: Add Grok to agent_slots in Default Config Templates — Design Spec

**Date:** 2026-09-02  
**Status:** Approved  
**Author:** Agy (implementer)  
**Issue:** Resolves #863  
**Tracking Story:** `story-1744cccb`  

---

## 1. Motivation & Problem Statement

Synlynk establishes a 4-harness Core Fleet consisting of **Claude**, **Agy**, **Codex**, and **Grok** (`CORE_FLEET = frozenset({"claude", "agy", "codex", "grok"})`).

While `synlynk/instructions.py` initialized `_agent_slots` to `{"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"}` when rendering template configs, the fallback dictionary in `load_config()` (`synlynk/__init__.py`) retained a legacy 3-harness dictionary:
```python
"agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex"}
```

This caused subtle behavioral discrepancies:
1. In uninitialized workspaces or environments where `.synlynk/config.json` was omitted, `load_config()` omitted Grok from `agent_slots`.
2. Diagnostic checks such as `synlynk doctor` (`_hc_agent_profiles`) and repair routines (`synlynk repair` / `synlynk sync`) relying on `cfg.get("agent_slots", {})` would miss verifying Grok's agent profile unless explicitly configured.
3. Fleet parity across all 4 harnesses was broken between static config generation and dynamic runtime defaults.

---

## 2. Design & Implementation

### A. Update `load_config()` Defaults in `synlynk/__init__.py`
Update `defaults["agent_slots"]` in `load_config()` to include all four Core Fleet harnesses:
```python
"agent_slots": {"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"},
```

### B. Fleet Parity Verification Across Subsystems
1. **Config Generation (`synlynk/instructions.py`):**
   `_build_templates()` continues to generate `config.json` containing all 4 slots.
2. **Doctor Health Checks (`synlynk/doctor.py`):**
   `_hc_agent_profiles()` checks `.agents/<name>.json` profiles for all configured slots in `agent_slots`, ensuring Grok profile validation succeeds when default slots are loaded.
3. **Dispatch & Slot Resolution (`synlynk/dispatch.py`):**
   Slot resolution and harness discovery map Grok directly without missing slot fallbacks.

---

## 3. Verification & Test Plan

1. **Unit Test (`tests/test_agent_cli.py`):**
   `test_config_add_grok_to_agent_slots_in_synlynk_and_default_config_templates` verifies:
   - `synlynk.load_config()` default `agent_slots` contains `claude`, `agy`, `codex`, and `grok`.
   - `_build_templates()["config.json"]` contains `claude`, `agy`, `codex`, and `grok`.
   - `_hc_agent_profiles()` validates `grok` profile presence.
2. **Suite Regression (`tests/test_synlynk.py`):**
   Updated `test_load_config_has_new_defaults` to assert `config["agent_slots"]["grok"] == "grok"`.
3. **Execution Command:**
   `pytest tests/test_agent_cli.py -k 'config_add_grok_to_agent_slots_in_synlyn' -v` passes cleanly.
