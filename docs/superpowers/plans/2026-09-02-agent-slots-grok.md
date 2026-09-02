# Fleet Parity: Add Grok to agent_slots in Default Config Templates — Implementation Plan

**Goal:** Ensure all four Core Fleet harnesses (`claude`, `agy`, `codex`, `grok`) are consistently present across `agent_slots` in `load_config()` defaults, generated template configurations, diagnostic health checks, and dispatch slot resolution, closing Issue #863.

**Architecture:** Defined in `docs/superpowers/specs/2026-09-02-agent-slots-grok-design.md`.

---

### Task 1: Add Grok to `load_config()` Defaults (TDD)

**Files:**
- Modify: `synlynk/__init__.py`
- Modify: `tests/test_synlynk.py`
- Modify: `tests/test_agent_cli.py`

- [x] **Step 1: Write unit test in `tests/test_agent_cli.py`**
  Add `test_config_add_grok_to_agent_slots_in_synlynk_and_default_config_templates` asserting `load_config()`, `_build_templates()`, and `_hc_agent_profiles()` include `grok`.

- [x] **Step 2: Update `load_config()` defaults in `synlynk/__init__.py`**
  Update `defaults["agent_slots"]` to `{"claude": "claude", "agy": "agy", "codex": "codex", "grok": "grok"}`.

- [x] **Step 3: Update `test_load_config_has_new_defaults` in `tests/test_synlynk.py`**
  Add `assert config["agent_slots"]["grok"] == "grok"`.

- [x] **Step 4: Run targeted test verification**
  `pytest tests/test_agent_cli.py -k 'config_add_grok_to_agent_slots_in_synlyn' -v`

---

### Task 2: Documentation, Memory & Blog Post

**Files:**
- Create: `docs/superpowers/specs/2026-09-02-agent-slots-grok-design.md`
- Create: `docs/superpowers/plans/2026-09-02-agent-slots-grok.md`
- Create: `docs/blog/156-pr1327-agent-slots-grok.md`
- Modify: `docs/blog/README.md`
- Modify: `project-docs/memory.md`
- Modify: `project-docs/devlogs/agy.md`

- [x] **Step 1: Author design spec**
- [x] **Step 2: Author implementation plan**
- [x] **Step 3: Author blog post 156**
- [x] **Step 4: Update blog series index in `docs/blog/README.md`**
- [x] **Step 5: Record design decision in `project-docs/memory.md`**
- [x] **Step 6: Update devlog in `project-docs/devlogs/agy.md`**

---

### Task 3: Full Test Suite Verification

- [x] **Step 1: Run full pytest suite across `tests/`**
