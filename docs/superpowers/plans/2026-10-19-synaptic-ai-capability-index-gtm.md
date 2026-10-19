# Synaptic AI Capability Index Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and launch the standalone Synaptic AI Capability Index public service: the capability pack snapshot exporter, universal pre-flight routing engine/CLI (`synlynk preflight`), glassmorphic interactive Prompt Oracle web app (`website/index-oracle/`), and universal MCP pre-flight skill (`@synlynk/preflight-mcp`).

**Architecture:** A zero-friction public utility layered over Synlynk's empirical 2,700+ task telemetry and SFIA 8/9 classification substrate. The engine exports daily signed capability packs (`capability-pack-latest.json`), evaluates task prompts via `synlynk/preflight.py` into optimal multi-vendor routing recommendations (`primary`, `failover`, `budget`), renders real-time recommendations in a standalone client-side web oracle, and provides a zero-dependency MCP server for Cursor, Claude Desktop, and Cline.

**Tech Stack:** Python 3.10+ (core CLI, preflight routing, capability pack), Vanilla HTML5/CSS3/ES6 (Prompt Oracle UI, zero runtime build dependencies), Node.js (MCP server `@synlynk/preflight-mcp`), pytest (TDD suites).

**Spec:** `docs/superpowers/specs/2026-10-19-synaptic-ai-capability-index-gtm-design.md`

## Global Constraints

- **Spec Alignment:** Strict adherence to `docs/superpowers/specs/2026-10-19-synaptic-ai-capability-index-gtm-design.md` JSON contract and architecture.
- **Privacy First:** Zero raw prompt persistence by default; deterministic SHA-256 hashing and SFIA code extraction only.
- **Sample Floor:** Cells with $n < 5$ tasks must be explicitly marked unmeasured (`Unmeasured` badge); active attribution must meet $\ge 1\%$ volume threshold.
- **Repo Hygiene:** Co-Authored-By trailer `Co-Authored-By: AGY <noreply@antigravity.dev>` on all commits. Worktree-isolated development.
- **TDD:** Write failing unit tests before implementing each module. Verify 100% test pass.

---

### Task 1: Capability Pack Generator & Snapshot Exporter (`synlynk/capability_pack.py`)

**Files:**
- Create: `synlynk/capability_pack.py`
- Create: `tests/test_capability_pack.py`
- Modify: `synlynk/cli.py`

**Interfaces:**
- Consumes: `synlynk/capability_window.py` (`get_active_sfia_disciplines`, `sync_harness_models_window`), `synlynk/sfia.py` (`SFIA_DISCIPLINES`, `get_sfia_name`).
- Produces: `export_capability_pack(conn, output_path=None) -> dict` returning complete capability pack JSON matching Spec Section 3.2.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_capability_pack.py
import json
import sqlite3
import pytest
from synlynk.capability_pack import export_capability_pack, generate_pack_metadata

def test_export_capability_pack_structure(tmp_path):
    db_path = tmp_path / "test_state.db"
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE capability_ratings (
            harness TEXT,
            model TEXT,
            discipline TEXT,
            quality REAL,
            quality_verified INTEGER,
            review_cycles REAL,
            cost_usd REAL,
            task_count INTEGER,
            PRIMARY KEY (harness, model, discipline)
        )
    """)
    cur.execute("""
        CREATE TABLE harness_models (
            harness TEXT,
            model TEXT,
            active INTEGER,
            PRIMARY KEY (harness, model)
        )
    """)
    cur.execute("INSERT INTO harness_models VALUES ('codex', 'gpt-5.6-terra', 1)")
    cur.execute("INSERT INTO harness_models VALUES ('grok', 'grok-4.6', 1)")
    cur.execute("INSERT INTO harness_models VALUES ('agy', 'gemini-3.8-flash', 1)")
    
    cur.execute("INSERT INTO capability_ratings VALUES ('codex', 'gpt-5.6-terra', 'PROG', 9.04, 1, 1.1, 0.52, 410)")
    cur.execute("INSERT INTO capability_ratings VALUES ('grok', 'grok-4.6', 'PROG', 8.55, 1, 1.2, 0.48, 176)")
    cur.execute("INSERT INTO capability_ratings VALUES ('agy', 'gemini-3.8-flash', 'PROG', 7.58, 1, 1.6, 0.08, 89)")
    conn.commit()

    pack = export_capability_pack(conn)
    assert "schema_version" in pack
    assert "matrix" in pack
    assert "PROG" in pack["matrix"]
    prog_ratings = pack["matrix"]["PROG"]
    assert len(prog_ratings) == 3
    assert prog_ratings[0]["harness"] == "codex"
    assert prog_ratings[0]["quality_score"] == 9.04
    assert prog_ratings[0]["sample_size"] == 410
    assert "snapshot_metadata" in pack
    assert pack["snapshot_metadata"]["sha256"] is not None
```

- [x] **Step 2: Run pytest to verify failure**

Run: `pytest tests/test_capability_pack.py -v`  
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.capability_pack'`

- [x] **Step 3: Implement `synlynk/capability_pack.py`**

Implement `export_capability_pack`, `generate_pack_metadata`, and wire into `synlynk capability export-pack` CLI.

- [x] **Step 4: Run pytest and confirm 100% pass**

Run: `pytest tests/test_capability_pack.py -v`  
Expected: PASS

- [x] **Step 5: Commit task**

`feat(capability): add capability pack snapshot exporter and CLI command`

---

### Task 2: Preflight Routing Engine & CLI (`synlynk/preflight.py`)

**Files:**
- Create: `synlynk/preflight.py`
- Create: `tests/test_preflight.py`
- Modify: `synlynk/cli.py`
- Modify: `synlynk/taxonomy.py`
- Modify: `docs/reference/commands.md`

**Interfaces:**
- Consumes: `synlynk/sfia.py` (`classify_task_sfia`, `get_sfia_name`), `synlynk/capability_pack.py` (`export_capability_pack`).
- Produces: `evaluate_preflight(prompt, pack, preferences=None) -> dict` returning routing decision (`task_classification`, `recommendations: {primary, failover, budget}`, `quota_advisory`, `cta`).

- [x] **Step 1: Write the failing tests**

```python
# tests/test_preflight.py
import pytest
from synlynk.preflight import evaluate_preflight, estimate_task_complexity

def test_estimate_task_complexity():
    assert estimate_task_complexity("fix typo in readme") == "low"
    assert estimate_task_complexity("refactor postgresql connection pool and fix async race condition") == "complex"
    assert estimate_task_complexity("add unit tests for user authentication") == "medium"

def test_evaluate_preflight_balanced(sample_pack):
    res = evaluate_preflight(
        prompt="Fix race condition in PostgreSQL connection pool during reconnection burst",
        pack=sample_pack,
        preferences={"optimize_for": "quality"}
    )
    assert res["task_classification"]["sfia_code"] in {"PROG", "DBDS"}
    assert "primary" in res["recommendations"]
    assert res["recommendations"]["primary"]["harness"] == "codex"
    assert "failover" in res["recommendations"]
    assert "budget" in res["recommendations"]
    assert res["cta"]["install_cmd"] == "brew install synlynk"
```

- [x] **Step 2: Run pytest to verify failure**

Run: `pytest tests/test_preflight.py -v`  
Expected: FAIL with `ModuleNotFoundError`

- [x] **Step 3: Implement `synlynk/preflight.py` & register CLI**

Implement `estimate_task_complexity`, `evaluate_preflight`, and `cmd_preflight` in `synlynk/cli.py`.
Register in `synlynk/taxonomy.py` and run `python3 scripts/generate_command_docs.py`.

- [x] **Step 4: Run pytest and confirm 100% pass**

Run: `pytest tests/test_preflight.py tests/test_docs_sync.py -v`  
Expected: PASS

- [x] **Step 5: Commit task**

`feat(preflight): implement universal preflight routing engine and CLI command`

---

### Task 3: Interactive Prompt Oracle UI (`website/index-oracle/`)

**Files:**
- Create: `website/index-oracle/index.html`
- Create: `website/index-oracle/style.css`
- Create: `website/index-oracle/app.js`
- Create: `website/index-oracle/pack-latest.json`
- Create: `tests/test_oracle_ui.py`

**Interfaces:**
- Consumes: `capability-pack-latest.json` schema.
- Produces: Standalone responsive web application featuring instant client-side keyword classification, trade-off slider, 4-tier recommendation cards, quota warnings, and conversion CTAs.

- [x] **Step 1: Write verification test for static assets & contracts**

```python
# tests/test_oracle_ui.py
from pathlib import Path
import json

def test_oracle_ui_assets_exist():
    root = Path("website/index-oracle")
    assert (root / "index.html").exists()
    assert (root / "style.css").exists()
    assert (root / "app.js").exists()
    assert (root / "pack-latest.json").exists()

def test_oracle_html_contains_core_elements():
    html = (Path("website/index-oracle/index.html")).read_text()
    assert 'id="prompt-input"' in html
    assert 'id="preference-slider"' in html
    assert 'id="classification-badge"' in html
    assert 'id="recommendations-container"' in html
    assert 'brew install synlynk' in html
```

- [x] **Step 2: Run pytest to verify failure**

Run: `pytest tests/test_oracle_ui.py -v`  
Expected: FAIL (files missing)

- [x] **Step 3: Build `index.html`, `style.css`, and `app.js`**

Implement glassmorphic dark-mode UI with high-contrast accessibility, live prompt classification, instant recommendation cards, responsive layout, and copyable terminal command. Generate `pack-latest.json` from `synlynk capability export-pack`.

- [x] **Step 4: Run test to verify passes**

Run: `pytest tests/test_oracle_ui.py -v`  
Expected: PASS

- [x] **Step 5: Commit task**

`feat(web): build standalone interactive Prompt Oracle single-page UI`

---

### Task 4: Universal Preflight Skill & MCP Server (`packages/preflight-mcp/`)

**Files:**
- Create: `packages/preflight-mcp/package.json`
- Create: `packages/preflight-mcp/bin/cli.js`
- Create: `packages/preflight-mcp/index.js`
- Create: `packages/preflight-mcp/README.md`
- Create: `tests/test_preflight_mcp.py`

**Interfaces:**
- Consumes: Standard Model Context Protocol (MCP) JSON-RPC protocol over `stdio`.
- Produces: Tools `synlynk_preflight(prompt, optimize_for, available_harnesses)` callable by Cursor, Claude Desktop, and Cline.

- [x] **Step 1: Write the failing tests**

```python
# tests/test_preflight_mcp.py
from pathlib import Path
import json
import subprocess

def test_preflight_mcp_package_manifest():
    pkg_path = Path("packages/preflight-mcp/package.json")
    assert pkg_path.exists()
    data = json.loads(pkg_path.read_text())
    assert data["name"] == "@synlynk/preflight-mcp"
    assert "bin" in data
```

- [x] **Step 2: Run pytest to verify failure**

Run: `pytest tests/test_preflight_mcp.py -v`  
Expected: FAIL

- [x] **Step 3: Implement MCP package and CLI**

Implement lightweight Node.js MCP server exposing tool `synlynk_preflight` with embedded offline fallback pack.

- [x] **Step 4: Run pytest and confirm pass**

Run: `pytest tests/test_preflight_mcp.py -v`  
Expected: PASS

- [x] **Step 5: Commit task**

`feat(mcp): create universal @synlynk/preflight-mcp server and CLI runner`

---

### Task 5: End-to-End Verification & Production Readiness

**Files:**
- Create: `tests/test_preflight_e2e.py`
- Modify: `project-docs/devlogs/nikhilsoman.md`
- Modify: `project-docs/roadmap.md`

- [x] **Step 1: Run comprehensive capability, preflight, and MCP test suites**

Run: `pytest tests/test_capability*.py tests/test_sfia.py tests/test_preflight*.py tests/test_oracle_ui.py -v`  
Expected: 100% PASS

- [x] **Step 2: Test live CLI command `synlynk preflight` on real task prompts**

Run: `synlynk preflight "Refactor database pool to handle async reconnection bursts"`  
Verify formatted terminal output with SFIA classification, primary, failover, and budget picks.

- [x] **Step 3: Export production `website/index-oracle/pack-latest.json` from live `state.db`**

Run: `synlynk capability export-pack --output website/index-oracle/pack-latest.json`

- [x] **Step 4: Document in devlog and update roadmap**

- [x] **Step 5: Commit task**

`chore(release): complete Phase 2B/2C Synaptic AI Capability Index verification`
