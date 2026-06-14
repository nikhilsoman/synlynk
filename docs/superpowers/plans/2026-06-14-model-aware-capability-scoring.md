# Model-Aware Capability Scoring Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend synlynk's capability scoring system so every quality rating is anchored to a specific model version, a 3-dimensional domain coordinate, and a tiered quality signal — making routing model-aware and Tokq Memory Units structurally complete.

**Spec:** `docs/superpowers/specs/2026-06-14-model-aware-capability-scoring-design.md`

**Architecture:** Introduce SQLite WAL (`state.db`) as the capability ledger. Two new tables (`stories`, `capability_ratings`) and one derived view (`capability_scores`) sit alongside the existing flat-file telemetry. `dispatch_agent()` is updated to query the view for routing when data exists; all post-job processing writes rating rows. New `score` and `story` subcommands expose the system to users and agents.

**Tech Stack:** Python 3 stdlib only (`sqlite3`, `re`, `json`, `os`). No new pip dependencies. SQLite WAL mode for concurrent read safety.

---

## Release Mapping

Tasks are split across two releases. Implement the v0.5.0 block first (Tasks 1–10); the v0.6.0 block (Tasks 11–14) extends the same schema and can be picked up independently.

| Tasks | Release | Theme | Target |
|-------|---------|-------|--------|
| 1–10 | **v0.5.0** | Capability Engine — core ledger, auto signals, basic routing, score CLI | Aug 2026 |
| 11–14 | **v0.6.0** | Job Control — statusline probe, PR attestation, verifier pipeline, Tokq tags | Sep 2026 |
| Future | v1.0 / Tokq Alpha | `synlynk tokq export`, model family registry pull | Q3 2027 |

**Release impact notes:**

- **v0.5.0** scope grows from its original "data-driven routing + `capability.json` → SQLite" description. This spec is the correct definition of v0.5.0 — the roadmap entry should be updated to reflect the richer domain taxonomy and quality signal work.
- **v0.6.0** gains two new concerns (PR attestation tier 4, statusline probe tier 2) on top of its existing "constraint propagation + job state machine" theme. These are additive — they don't conflict with the job control work; they make the job record richer.
- **v0.7.0+** is unaffected.

---

## File Structure

| File | Change | Responsible tasks |
|------|--------|------------------|
| `bin/synlynk.py` | All changes — new functions, modified `dispatch_agent`, `_reconcile_jobs`, `init`, `main` | 1–14 |
| `tests/test_capability_scoring.py` | New test file — all capability scoring tests | 1–14 |
| `tests/test_synlynk.py` | Updated tests for modified `dispatch_agent` and `_reconcile_jobs` signatures | 9, 11 |
| `.synlynk/state/state.db` | Created at runtime by `_get_db()` | 1 |

No new source files beyond the test file. All logic stays in `bin/synlynk.py`.

---

## v0.5.0 Tasks

---

### Task 1: SQLite Bootstrap — `_get_db()`, Schema Migrations

**Files:**
- Modify: `bin/synlynk.py` — add `_get_db()`, `_migrate_db()`, schema constants near top of file
- Create: `tests/test_capability_scoring.py`

The database lives at `.synlynk/state/state.db`. The migration system is a simple version counter in a `schema_version` table — idempotent, no rollback needed.

- [ ] **Step 1: Write failing test for db creation**

```python
# tests/test_capability_scoring.py
import os, sqlite3, tempfile, sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'bin'))

def test_get_db_creates_state_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    conn.close()
    assert os.path.exists(".synlynk/state/state.db")

def test_migrate_db_creates_tables(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    conn = _get_db()
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    ).fetchall()}
    conn.close()
    assert "stories" in tables
    assert "capability_ratings" in tables

def test_migrate_db_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db
    _get_db().close()
    _get_db().close()  # second call must not crash
```

- [ ] **Step 2: Run tests to verify they fail**

```bash
pytest tests/test_capability_scoring.py -v
```

Expected: ImportError or AttributeError — `_get_db` not defined.

- [ ] **Step 3: Add `_get_db()` and `_migrate_db()` to `bin/synlynk.py`**

Add near the top of the file, after the imports section:

```python
import sqlite3 as _sqlite3

DB_PATH = ".synlynk/state/state.db"

_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version (version INTEGER NOT NULL);

CREATE TABLE IF NOT EXISTS stories (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id      TEXT NOT NULL UNIQUE,
    title         TEXT,
    engg_domain   TEXT DEFAULT 'unknown',
    org_domain    TEXT DEFAULT 'unknown',
    org_domain_tags TEXT DEFAULT '[]',
    industry      TEXT DEFAULT 'unknown',
    phase         TEXT DEFAULT 'build',
    created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS capability_ratings (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    story_id              TEXT NOT NULL REFERENCES stories(story_id),
    agent                 TEXT NOT NULL,
    model_version         TEXT NOT NULL DEFAULT 'unknown',
    model_at_dispatch     TEXT,
    model_at_completion   TEXT,
    split_model           INTEGER DEFAULT 0,
    engg_domain           TEXT NOT NULL DEFAULT 'unknown',
    org_domain            TEXT NOT NULL DEFAULT 'unknown',
    org_domain_tags       TEXT DEFAULT '[]',
    industry              TEXT NOT NULL DEFAULT 'unknown',
    phase                 TEXT NOT NULL DEFAULT 'build',
    signal_source         TEXT NOT NULL DEFAULT 'auto',
    quality               REAL NOT NULL DEFAULT 0.0,
    quality_auto          REAL,
    verifier_agent        TEXT,
    verifier_model        TEXT,
    test_pass_rate        REAL,
    build_success         INTEGER,
    dispatch_rework       INTEGER DEFAULT 0,
    micro_rework          INTEGER DEFAULT 0,
    pr_review_cycles      INTEGER DEFAULT 0,
    duration_vs_estimate  REAL,
    verified_by_ci        INTEGER,
    correct               INTEGER DEFAULT 1,
    note                  TEXT,
    ed25519_sig           TEXT,
    ts                    TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
"""

_DB_SCORES_VIEW = """
CREATE VIEW IF NOT EXISTS capability_scores AS
SELECT
    agent,
    model_version,
    engg_domain,
    org_domain,
    industry,
    phase,
    SUM(quality * (0.85 * MAX(0, CAST((julianday('now') - julianday(ts)) / 7.0 AS INTEGER))))
        / SUM(0.85 * MAX(0, CAST((julianday('now') - julianday(ts)) / 7.0 AS INTEGER)))
        AS weighted_score,
    COUNT(*) AS sample_count,
    MAX(ts) AS last_seen
FROM capability_ratings
WHERE split_model = 0
GROUP BY agent, model_version, engg_domain, org_domain, industry, phase;
"""

def _get_db() -> _sqlite3.Connection:
    """Returns a WAL-mode SQLite connection to state.db, running migrations."""
    os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
    conn = _sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    _migrate_db(conn)
    return conn

def _migrate_db(conn: _sqlite3.Connection) -> None:
    """Idempotent schema migrations. Adds tables/views if absent."""
    conn.executescript(_DB_SCHEMA)
    try:
        conn.executescript(_DB_SCORES_VIEW)
    except _sqlite3.OperationalError:
        pass  # view already exists with same definition
    conn.commit()
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_capability_scoring.py -v
```

Expected: 3 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_capability_scoring.py
git commit -m "feat: sqlite state.db bootstrap — _get_db, schema migrations, capability tables"
```

---

### Task 2: Industry Vertical in Init Wizard + Config

**Files:**
- Modify: `bin/synlynk.py:1934` — `init()` function, `_update_config()`

`init()` already writes `.synlynk/config.json`. Add an `industry` field and a prompt (with README inference as default).

- [ ] **Step 1: Write failing test**

```python
def test_init_writes_industry_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    # Patch input() to return "ott"
    monkeypatch.setattr("builtins.input", lambda _: "ott")
    from synlynk import init
    init(force=True)
    import json
    config = json.load(open(".synlynk/config.json"))
    assert config.get("industry") == "ott"

def test_init_infers_industry_from_readme(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "README.md").write_text("# MyApp\nA fintech platform for trading.")
    # Patch input() to press Enter (accept inferred value)
    monkeypatch.setattr("builtins.input", lambda _: "")
    from synlynk import init, _infer_industry
    inferred = _infer_industry(str(tmp_path))
    assert inferred == "fintech"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py::test_init_writes_industry_to_config tests/test_capability_scoring.py::test_init_infers_industry_from_readme -v
```

- [ ] **Step 3: Add `_infer_industry()` and update `init()`**

Add `_infer_industry()` near `_static_scan()`:

```python
_INDUSTRY_KEYWORDS = {
    "ott": ["ott", "over-the-top", "streaming service", "video platform"],
    "streaming": ["streaming", "live stream", "media delivery"],
    "fintech": ["fintech", "financial", "payment", "trading", "investment"],
    "banking": ["banking", "bank", "loan", "mortgage", "deposit"],
    "securities": ["securities", "stock", "equity", "portfolio", "brokerage"],
    "healthcare": ["healthcare", "medical", "patient", "clinical", "health"],
    "ecommerce": ["ecommerce", "e-commerce", "shop", "cart", "marketplace"],
    "edtech": ["edtech", "education", "learning", "course", "student"],
    "gaming": ["gaming", "game", "player", "leaderboard", "matchmaking"],
}

def _infer_industry(root: str = ".") -> str:
    """Infers industry vertical from README content. Returns 'unknown' if no match."""
    for fname in ("README.md", "README.rst", "README.txt"):
        path = os.path.join(root, fname)
        if os.path.exists(path):
            text = open(path).read().lower()
            for industry, keywords in _INDUSTRY_KEYWORDS.items():
                if any(kw in text for kw in keywords):
                    return industry
    return "unknown"
```

In `init()`, after the existing wizard prompts, add:

```python
# Industry vertical
inferred = _infer_industry()
industry_prompt = f"Industry vertical [{inferred}]: "
industry = input(industry_prompt).strip() or inferred
if industry not in list(_INDUSTRY_KEYWORDS.keys()) + ["unknown"]:
    industry = "unknown"
_update_config({"industry": industry})
```

- [ ] **Step 4: Run tests to verify they pass**

```bash
pytest tests/test_capability_scoring.py::test_init_writes_industry_to_config tests/test_capability_scoring.py::test_init_infers_industry_from_readme -v
```

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: industry vertical prompt in init wizard — infers from README, writes to config"
```

---

### Task 3: `synlynk story create/list` — Story Management CLI

**Files:**
- Modify: `bin/synlynk.py` — add `cmd_story_create()`, `cmd_story_list()`, wire into `main()`

Stories are the unit of work that capability ratings reference. A story needs: title, engg_domain (manual for now, agent-inferred in Task 4), org_domain, phase.

- [ ] **Step 1: Write failing tests**

```python
def test_story_create_writes_to_db(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, _get_db
    cmd_story_create(title="Add billing endpoint", engg_domain="backend",
                     org_domain="monetization", phase="build")
    conn = _get_db()
    rows = conn.execute("SELECT * FROM stories WHERE title=?",
                        ("Add billing endpoint",)).fetchall()
    conn.close()
    assert len(rows) == 1

def test_story_create_generates_unique_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, _get_db
    cmd_story_create(title="Story A", engg_domain="backend", org_domain="platform", phase="build")
    cmd_story_create(title="Story B", engg_domain="frontend", org_domain="growth", phase="build")
    conn = _get_db()
    rows = conn.execute("SELECT story_id FROM stories").fetchall()
    conn.close()
    ids = [r[0] for r in rows]
    assert len(set(ids)) == 2

def test_story_list_returns_rows(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import cmd_story_create, cmd_story_list
    cmd_story_create(title="My story", engg_domain="data", org_domain="analytics", phase="build")
    cmd_story_list()
    out = capsys.readouterr().out
    assert "My story" in out
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py::test_story_create_writes_to_db tests/test_capability_scoring.py::test_story_create_generates_unique_id tests/test_capability_scoring.py::test_story_list_returns_rows -v
```

- [ ] **Step 3: Add `cmd_story_create()` and `cmd_story_list()`**

```python
def cmd_story_create(title: str, engg_domain: str = "unknown",
                     org_domain: str = "unknown", phase: str = "build") -> str:
    """Creates a story record in state.db. Returns the generated story_id."""
    import hashlib as _hashlib
    story_id = "story-" + _hashlib.md5(
        f"{title}{time.time()}".encode()
    ).hexdigest()[:8]
    config = load_config()
    industry = config.get("industry", "unknown")
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (story_id, title, engg_domain, org_domain, industry, phase)
    )
    conn.commit()
    conn.close()
    print(f"  ✓ Story created: {story_id}  [{engg_domain} · {org_domain} · {industry}]")
    return story_id

def cmd_story_list() -> None:
    """Prints all stories in state.db."""
    conn = _get_db()
    rows = conn.execute(
        "SELECT story_id, title, engg_domain, org_domain, industry, phase, created_at "
        "FROM stories ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    if not rows:
        print("  No stories yet. Use: synlynk story create --title '...'")
        return
    print(f"\n  {'ID':<14} {'Title':<30} {'Engg':<12} {'Org':<14} {'Industry':<12} Phase")
    print("  " + "-" * 90)
    for r in rows:
        print(f"  {r[0]:<14} {(r[1] or '')[:29]:<30} {r[2]:<12} {r[3]:<14} {r[4]:<12} {r[5]}")
```

In `main()`, add subcommand wiring after the existing `run_parser` block:

```python
story_parser = subparsers.add_parser("story", help="Manage stories")
story_sub = story_parser.add_subparsers(dest="story_action")
story_create_parser = story_sub.add_parser("create", help="Create a story")
story_create_parser.add_argument("--title", required=True)
story_create_parser.add_argument("--engg", default="unknown", dest="engg_domain")
story_create_parser.add_argument("--org", default="unknown", dest="org_domain")
story_create_parser.add_argument("--phase", default="build")
story_sub.add_parser("list", help="List all stories")
```

And in the `main()` dispatch block:

```python
elif args.command == "story":
    if args.story_action == "create":
        cmd_story_create(args.title, args.engg_domain, args.org_domain, args.phase)
    elif args.story_action == "list":
        cmd_story_list()
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py::test_story_create_writes_to_db tests/test_capability_scoring.py::test_story_create_generates_unique_id tests/test_capability_scoring.py::test_story_list_returns_rows -v
```

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: story create/list commands — capability ledger unit of work"
```

---

### Task 4: Engineering Domain Inference from File Paths

**Files:**
- Modify: `bin/synlynk.py` — add `_infer_engg_domain()`

When a job completes, we can examine the files it touched via the log output. For now, we infer from the log file text using path heuristics. Agent-based LLM classification is deferred to a future release.

- [ ] **Step 1: Write failing test**

```python
def test_infer_engg_domain_from_paths():
    from synlynk import _infer_engg_domain
    assert _infer_engg_domain("Modified src/api/billing.py and tests/test_billing.py") == "backend"
    assert _infer_engg_domain("Updated src/components/Button.tsx") == "frontend"
    assert _infer_engg_domain("Added pipeline/etl_job.py and models/schema.sql") == "data"
    assert _infer_engg_domain("No matching paths here") == "unknown"

def test_infer_engg_domain_prefers_specific_over_generic():
    from synlynk import _infer_engg_domain
    # ML beats backend when both patterns present
    assert _infer_engg_domain("src/ml/train.py and src/api/serve.py") in ("ml", "backend")
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py::test_infer_engg_domain_from_paths -v
```

- [ ] **Step 3: Add `_infer_engg_domain()`**

```python
_ENGG_DOMAIN_PATTERNS = [
    ("ml",           [r"ml/", r"models/", r"train\.", r"inference/", r"embeddings/"]),
    ("security",     [r"auth/", r"oauth", r"jwt", r"crypto", r"certs/"]),
    ("devops",       [r"\.github/", r"dockerfile", r"terraform", r"pulumi", r"k8s/", r"helm/"]),
    ("data",         [r"etl", r"pipeline/", r"schema\.sql", r"migrations/", r"dbt/"]),
    ("testing",      [r"tests/", r"test_", r"spec/", r"\.spec\.", r"fixtures/"]),
    ("frontend",     [r"components/", r"pages/", r"\.tsx?", r"\.vue", r"\.svelte", r"styles/"]),
    ("backend",      [r"api/", r"routes/", r"handlers/", r"controllers/", r"services/"]),
    ("docs",         [r"docs/", r"readme", r"\.md$", r"changelogs?"]),
    ("architecture", [r"design/", r"specs/", r"adr/", r"diagrams/"]),
]

def _infer_engg_domain(log_text: str) -> str:
    """Infers engineering domain from file path patterns in job log output."""
    lower = log_text.lower()
    for domain, patterns in _ENGG_DOMAIN_PATTERNS:
        if any(re.search(p, lower) for p in patterns):
            return domain
    return "unknown"
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py::test_infer_engg_domain_from_paths -v
```

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: engineering domain inference from file path heuristics in job log"
```

---

### Task 5: Model Version Extraction — Tier 1 (synlynk-meta header) + Tier 3 (config)

**Files:**
- Modify: `bin/synlynk.py` — add `extract_model_version()`

The agent embeds a `# synlynk-meta` block in its output. We parse `model_version=<value>` from it. Tier 3 (config default) is the fallback when the header is absent.

- [ ] **Step 1: Write failing tests**

```python
def test_extract_model_version_from_meta_header():
    from synlynk import extract_model_version
    output = """
Some agent output here.

# synlynk-meta
model_version=claude-opus-4-8
quality=8
correct=true
"""
    assert extract_model_version(output) == "claude-opus-4-8"

def test_extract_model_version_missing_returns_unknown():
    from synlynk import extract_model_version
    assert extract_model_version("No meta block here") == "unknown"

def test_extract_model_version_falls_back_to_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    import json
    json.dump({"agents": {"claude": {"default_model": "claude-sonnet-4-6"}}},
              open(".synlynk/config.json", "w"))
    from synlynk import extract_model_version
    result = extract_model_version("No meta block", agent="claude")
    assert result == "claude-sonnet-4-6"

def test_extract_model_version_parses_various_formats():
    from synlynk import extract_model_version
    # Whitespace tolerance
    assert extract_model_version("# synlynk-meta\n model_version = gemini-2.5-pro\n") == "gemini-2.5-pro"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "extract_model_version" -v
```

- [ ] **Step 3: Add `extract_model_version()`**

Add after `extract_tokens()`:

```python
def extract_model_version(output_text: str, agent: str = None) -> str:
    """
    Tier 1: Parse model_version from # synlynk-meta block in agent output.
    Tier 3 fallback: read default_model from .synlynk/config.json for the agent.
    Returns 'unknown' if neither source provides a value.
    """
    # Tier 1: structured header
    m = re.search(r"#\s*synlynk-meta.*?model_version\s*=\s*(\S+)", output_text,
                  re.DOTALL | re.IGNORECASE)
    if m:
        return m.group(1).strip()

    # Tier 3: config default
    if agent:
        config = load_config()
        agents_cfg = config.get("agents", {})
        default = agents_cfg.get(agent, {}).get("default_model")
        if default:
            return default

    return "unknown"
```

Also update `.synlynk/config.json` schema documentation in comments near `load_config()`:

```python
# config.json structure additions (v0.5.0):
# {
#   "industry": "ott",
#   "agents": {
#     "claude": {"default_model": "claude-opus-4-8"},
#     "gemini": {"default_model": "gemini-2.5-pro"}
#   }
# }
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py -k "extract_model_version" -v
```

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: model version extraction — tier 1 synlynk-meta header, tier 3 config fallback"
```

---

### Task 6: Auto Signal Capture in `_reconcile_jobs()`

**Files:**
- Modify: `bin/synlynk.py:151` — `_reconcile_jobs()` — add `_extract_auto_signals()`

When a job transitions to `completed`, read its log file and extract test pass rate, build success, and duration signals.

- [ ] **Step 1: Write failing tests**

```python
def test_extract_auto_signals_test_pass_rate():
    from synlynk import _extract_auto_signals
    log = "Tests: 47 passed, 3 failed, 50 total"
    signals = _extract_auto_signals(log, started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:05:00")
    assert abs(signals["test_pass_rate"] - 0.94) < 0.01

def test_extract_auto_signals_build_success_on_zero_exit():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("Build OK", started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:01:00", exit_code=0)
    assert signals["build_success"] is True

def test_extract_auto_signals_build_fail_on_nonzero_exit():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("Error: compilation failed",
                                    started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:01:00", exit_code=1)
    assert signals["build_success"] is False

def test_extract_auto_signals_duration_computed():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("", started_at="2026-06-14T10:00:00",
                                    ended_at="2026-06-14T10:10:00")
    assert signals["duration_seconds"] == pytest.approx(600.0, abs=1)

def test_extract_auto_signals_all_zeros_on_empty_log():
    from synlynk import _extract_auto_signals
    signals = _extract_auto_signals("", started_at=None, ended_at=None)
    assert signals["test_pass_rate"] is None
    assert signals["build_success"] is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "extract_auto_signals" -v
```

- [ ] **Step 3: Add `_extract_auto_signals()`**

```python
def _extract_auto_signals(log_text: str, started_at: str = None,
                           ended_at: str = None, exit_code: int = None) -> dict:
    """Extracts objective quality signals from a completed job's log text."""
    signals = {
        "test_pass_rate": None,
        "build_success": None,
        "duration_seconds": None,
    }

    # Test pass rate — multiple runner formats
    patterns = [
        r"(\d+)\s+passed.*?(\d+)\s+(?:failed|error)",   # pytest: "47 passed, 3 failed"
        r"Tests:\s+(\d+)\s+passed.*?(\d+)\s+failed",     # jest variant
        r"(\d+)/(\d+)\s+tests?\s+passed",                # generic "47/50 tests passed"
    ]
    for pat in patterns:
        m = re.search(pat, log_text, re.IGNORECASE)
        if m:
            passed = int(m.group(1))
            second = int(m.group(2))
            if "passed" in pat and "failed" in pat:
                total = passed + second
            else:
                total = second
            signals["test_pass_rate"] = passed / total if total else None
            break

    # All-passed shortcut: "X passed" with no failures mentioned
    if signals["test_pass_rate"] is None:
        m = re.search(r"(\d+)\s+passed", log_text, re.IGNORECASE)
        if m and "failed" not in log_text.lower() and "error" not in log_text.lower():
            signals["test_pass_rate"] = 1.0

    # Build success from exit code
    if exit_code is not None:
        signals["build_success"] = (exit_code == 0)

    # Duration
    if started_at and ended_at:
        try:
            fmt = "%Y-%m-%dT%H:%M:%S"
            import datetime as _dt
            delta = _dt.datetime.strptime(ended_at, fmt) - _dt.datetime.strptime(started_at, fmt)
            signals["duration_seconds"] = delta.total_seconds()
        except Exception:
            pass

    return signals
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py -k "extract_auto_signals" -v
```

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: auto signal extraction — test pass rate, build success, duration from job log"
```

---

### Task 7: `dispatch_rework` + `micro_rework` Tracking in Job Store

**Files:**
- Modify: `bin/synlynk.py:151` — `_reconcile_jobs()`, job dict structure

Add `dispatch_rework` and `micro_rework` counters to the job record. `dispatch_rework` increments each time a new job is dispatched for the same `story_id` (the previous job for that story completed). `micro_rework` is reserved for sub-task retry counting by agent frameworks that emit retry signals in their output.

- [ ] **Step 1: Write failing tests**

```python
def test_dispatch_rework_increments_on_same_story(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    os.makedirs(".synlynk/prompts", exist_ok=True)
    import json
    # Pre-populate jobs: one completed job for story-abc
    jobs = [{
        "id": "job-prev", "agent": "claude", "story_id": "story-abc",
        "status": "completed", "exit_code": 0,
        "dispatch_rework": 0, "micro_rework": 0,
        "started_at": "2026-06-14T10:00:00", "ended_at": "2026-06-14T10:05:00"
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    from synlynk import _count_dispatch_rework
    assert _count_dispatch_rework("story-abc") == 1  # one prior completed dispatch

def test_micro_rework_extracted_from_log():
    from synlynk import _extract_micro_rework
    log = "Retrying step 1...\nRetrying step 1...\nRetrying step 2..."
    assert _extract_micro_rework(log) == 3

def test_micro_rework_zero_when_no_retries():
    from synlynk import _extract_micro_rework
    assert _extract_micro_rework("All steps passed cleanly.") == 0
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "rework" -v
```

- [ ] **Step 3: Add `_count_dispatch_rework()` and `_extract_micro_rework()`**

```python
def _count_dispatch_rework(story_id: str) -> int:
    """Counts completed jobs for this story_id — each represents one dispatch cycle."""
    if not story_id:
        return 0
    jobs = _load_jobs()
    return sum(1 for j in jobs
               if j.get("story_id") == story_id and j.get("status") == "completed")

def _extract_micro_rework(log_text: str) -> int:
    """Counts sub-task retry signals in agent log output."""
    patterns = [r"retrying step", r"retry attempt", r"re-trying", r"attempt \d+"]
    count = 0
    for pat in patterns:
        count += len(re.findall(pat, log_text, re.IGNORECASE))
    return count
```

Update `dispatch_agent()` — add `dispatch_rework` and `micro_rework` to the job dict:

```python
    job = {
        # ... existing fields ...
        "dispatch_rework": _count_dispatch_rework(story_id),
        "micro_rework": 0,  # populated by _reconcile_jobs() on completion
    }
```

In `_reconcile_jobs()`, when marking a job `completed`, add:

```python
    if log_file and os.path.exists(log_file):
        log_text = open(log_file).read()
        job["micro_rework"] = _extract_micro_rework(log_text)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py -k "rework" -v
```

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: dispatch_rework and micro_rework tracking — routing signal vs noise"
```

---

### Task 8: Write `capability_ratings` Row on Job Completion

**Files:**
- Modify: `bin/synlynk.py:151` — `_reconcile_jobs()` — add `_write_capability_rating()`

When a job transitions to `completed`, gather all signals and write a row to `capability_ratings`.

- [ ] **Step 1: Write failing test**

```python
def test_reconcile_writes_capability_rating_on_completion(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    os.makedirs(".synlynk/logs", exist_ok=True)
    import json

    log_content = "# synlynk-meta\nmodel_version=claude-opus-4-8\n\n47 passed"
    log_path = str(tmp_path / ".synlynk/logs/job-test.log")
    open(log_path, "w").write(log_content)
    exit_path = log_path + ".exit"
    open(exit_path, "w").write("0")

    jobs = [{
        "id": "job-test", "agent": "claude", "story_id": "story-xyz",
        "status": "running", "pid": 99999999,  # dead PID
        "log_file": log_path, "prompt_file": None,
        "started_at": "2026-06-14T10:00:00", "ended_at": None,
        "exit_code": None, "dispatch_rework": 0, "micro_rework": 0
    }]
    json.dump(jobs, open(".synlynk/jobs.json", "w"))
    json.dump({"industry": "ott"}, open(".synlynk/config.json", "w"))

    # Insert story so FK is satisfied
    from synlynk import _get_db, _reconcile_jobs
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?, ?)", ("story-xyz", "Test"))
    conn.commit()
    conn.close()

    _reconcile_jobs()

    conn = _get_db()
    row = conn.execute(
        "SELECT model_version, test_pass_rate, build_success FROM capability_ratings "
        "WHERE story_id=?", ("story-xyz",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "claude-opus-4-8"
    assert row[2] == 1  # build_success True
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py::test_reconcile_writes_capability_rating_on_completion -v
```

- [ ] **Step 3: Add `_write_capability_rating()` and call from `_reconcile_jobs()`**

```python
def _write_capability_rating(job: dict, log_text: str) -> None:
    """Writes a capability_ratings row for a completed job."""
    story_id = job.get("story_id", "")
    if not story_id:
        return

    # Check story exists in DB
    conn = _get_db()
    exists = conn.execute("SELECT 1 FROM stories WHERE story_id=?", (story_id,)).fetchone()
    if not exists:
        conn.close()
        return  # no story record = no rating

    # Gather signals
    agent = job.get("agent", "unknown")
    model_version = extract_model_version(log_text, agent=agent)
    signals = _extract_auto_signals(
        log_text,
        started_at=job.get("started_at"),
        ended_at=job.get("ended_at"),
        exit_code=job.get("exit_code"),
    )
    engg_domain = _infer_engg_domain(log_text)
    dispatch_rework = job.get("dispatch_rework", 0)
    micro_rework = job.get("micro_rework", 0)

    # Fetch story's org_domain + industry
    story_row = conn.execute(
        "SELECT org_domain, industry, phase FROM stories WHERE story_id=?", (story_id,)
    ).fetchone()
    org_domain = story_row[0] if story_row else "unknown"
    industry = story_row[1] if story_row else load_config().get("industry", "unknown")
    phase = story_row[2] if story_row else "build"

    # Auto composite quality: weighted average of available signals
    scores = []
    if signals["test_pass_rate"] is not None:
        scores.append(signals["test_pass_rate"] * 10 * 0.35)
    if signals["build_success"] is not None:
        scores.append((10.0 if signals["build_success"] else 0.0) * 0.30)
    rework_penalty = min(dispatch_rework * 2.0, 10.0)  # cap at 10
    scores.append(max(0.0, 10.0 - rework_penalty) * 0.35)
    quality_auto = sum(scores) if scores else 5.0  # neutral default

    conn.execute(
        """INSERT INTO capability_ratings
           (story_id, agent, model_version, model_at_completion,
            engg_domain, org_domain, industry, phase,
            signal_source, quality, quality_auto,
            test_pass_rate, build_success,
            dispatch_rework, micro_rework,
            duration_vs_estimate, verified_by_ci)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (story_id, agent, model_version, model_version,
         engg_domain, org_domain, industry, phase,
         "auto", quality_auto, quality_auto,
         signals["test_pass_rate"], 1 if signals["build_success"] else 0,
         dispatch_rework, micro_rework,
         None, None)
    )
    conn.commit()
    conn.close()
```

In `_reconcile_jobs()`, in the `ProcessLookupError` branch after marking job `completed`, add:

```python
    if log_file and os.path.exists(log_file):
        log_text = open(log_file).read()
        job["micro_rework"] = _extract_micro_rework(log_text)
        _write_capability_rating(job, log_text)
```

- [ ] **Step 4: Run to verify test passes**

```bash
pytest tests/test_capability_scoring.py::test_reconcile_writes_capability_rating_on_completion -v
```

- [ ] **Step 5: Run full test suite to check for regressions**

```bash
pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: write capability_ratings row on job completion — auto signals, model version, domain"
```

---

### Task 9: Routing — `dispatch_agent()` Queries `capability_scores`

**Files:**
- Modify: `bin/synlynk.py:478` — `dispatch_agent()`

When a story_id is provided and capability data exists for its coordinate, prefer the agent with the highest weighted score. Falls back to the caller's explicit `agent` argument if no data or cold start.

- [ ] **Step 1: Write failing tests**

```python
def test_dispatch_uses_capability_score_when_available(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story
    conn = _get_db()
    # Seed story
    conn.execute("INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase) "
                 "VALUES (?, ?, ?, ?, ?, ?)", ("story-1", "Test", "backend", "monetization", "ott", "build"))
    # Seed capability rating for gemini (better score)
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "gemini", "gemini-2.5-pro", "backend", "monetization", "ott",
         "build", "auto", 8.5, 8.5)
    )
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 6.0, 6.0)
    )
    conn.commit()
    conn.close()
    result = _best_agent_for_story("story-1")
    assert result == "gemini"

def test_dispatch_returns_none_when_no_capability_data(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title, engg_domain, org_domain, industry, phase) "
                 "VALUES (?, ?, ?, ?, ?, ?)", ("story-2", "Test", "backend", "monetization", "ott", "build"))
    conn.commit()
    conn.close()
    assert _best_agent_for_story("story-2") is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "dispatch" -v
```

- [ ] **Step 3: Add `_best_agent_for_story()` and update `dispatch_agent()`**

```python
def _best_agent_for_story(story_id: str) -> Optional[str]:
    """
    Returns the agent with the highest capability score for the story's coordinate.
    Falls back through progressively wider coordinates. Returns None on cold start.
    """
    if not story_id:
        return None
    conn = _get_db()
    story = conn.execute(
        "SELECT engg_domain, org_domain, industry, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        return None

    engg, org, industry, phase = story

    # Try full coordinate first, then progressively widen
    queries = [
        ("full",     "engg_domain=? AND org_domain=? AND industry=? AND phase=?",
                     (engg, org, industry, phase)),
        ("no-industry", "engg_domain=? AND org_domain=? AND phase=?",
                     (engg, org, phase)),
        ("engg-only", "engg_domain=? AND phase=?",
                     (engg, phase)),
    ]
    for _, where, params in queries:
        row = conn.execute(
            f"SELECT agent FROM capability_scores WHERE {where} "
            "ORDER BY weighted_score DESC LIMIT 1",
            params
        ).fetchone()
        if row:
            conn.close()
            return row[0]

    conn.close()
    return None
```

In `dispatch_agent()`, after the existing agent validation, add routing:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None) -> dict:
    # Capability-based routing: override agent if story has data
    if story_id:
        best = _best_agent_for_story(story_id)
        if best and best in AGENT_CAPABILITY_BASELINES:
            agent = best
    # ... rest of existing function unchanged ...
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py -k "dispatch" -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: capability-based agent routing in dispatch_agent — queries capability_scores with coordinate fallback"
```

---

### Task 10: `synlynk score add` + `synlynk score list`

**Files:**
- Modify: `bin/synlynk.py` — add `cmd_score_add()`, `cmd_score_list()`, wire into `main()`

Human rating override: sets `signal_source = 'human'` and `quality = rating`. Score list shows the capability_scores view for a given coordinate.

- [ ] **Step 1: Write failing tests**

```python
def test_score_add_writes_human_rating(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_add
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-1", "Test"))
    # Existing auto row
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 6.0, 6.0)
    )
    conn.commit()
    conn.close()
    cmd_score_add("story-1", 9.0, note="Clean first-pass implementation")
    conn = _get_db()
    row = conn.execute(
        "SELECT signal_source, quality, note FROM capability_ratings "
        "WHERE story_id=? AND signal_source='human'", ("story-1",)
    ).fetchone()
    conn.close()
    assert row is not None
    assert row[1] == 9.0
    assert "Clean" in row[2]

def test_score_add_rejects_out_of_range(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_add
    _get_db().close()
    import pytest
    with pytest.raises(ValueError):
        cmd_score_add("story-1", 11.0)
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "score_add" -v
```

- [ ] **Step 3: Add `cmd_score_add()` and `cmd_score_list()`**

```python
def cmd_score_add(story_id: str, rating: float, note: str = None,
                  rework: bool = False) -> None:
    """Add a human quality rating for a story. Inserts a new 'human' row."""
    if not 0.0 <= rating <= 10.0:
        raise ValueError(f"Rating must be 0–10, got {rating}")
    conn = _get_db()
    story = conn.execute(
        "SELECT engg_domain, org_domain, industry, phase FROM stories WHERE story_id=?",
        (story_id,)
    ).fetchone()
    if not story:
        conn.close()
        print(f"  Story '{story_id}' not found. Create it first with: synlynk story create")
        return
    engg, org, industry, phase = story
    # Infer agent from most recent auto row for this story
    prev = conn.execute(
        "SELECT agent, model_version FROM capability_ratings "
        "WHERE story_id=? ORDER BY ts DESC LIMIT 1", (story_id,)
    ).fetchone()
    agent = prev[0] if prev else "unknown"
    model_version = prev[1] if prev else "unknown"
    dispatch_rework = 1 if rework else 0
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, dispatch_rework, note) "
        "VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (story_id, agent, model_version, engg, org, industry, phase,
         "human", rating, dispatch_rework, note)
    )
    conn.commit()
    conn.close()
    flag = " [rework]" if rework else ""
    print(f"  ✓ Score recorded: {rating}/10{flag} for {story_id}")
    if note:
        print(f"    Note: {note}")

def cmd_score_list(engg: str = None, org: str = None, industry: str = None) -> None:
    """Display capability_scores for a domain coordinate."""
    conn = _get_db()
    where_parts, params = [], []
    if engg:
        where_parts.append("engg_domain=?"); params.append(engg)
    if org:
        where_parts.append("org_domain=?"); params.append(org)
    if industry:
        where_parts.append("industry=?"); params.append(industry)
    where = ("WHERE " + " AND ".join(where_parts)) if where_parts else ""
    rows = conn.execute(
        f"SELECT agent, model_version, engg_domain, org_domain, industry, phase, "
        f"weighted_score, sample_count FROM capability_scores {where} "
        f"ORDER BY weighted_score DESC",
        params
    ).fetchall()
    conn.close()
    if not rows:
        print("  No capability data yet for this coordinate.")
        return
    print(f"\n  {'Agent':<10} {'Model':<22} {'Engg':<12} {'Org':<14} "
          f"{'Industry':<12} {'Phase':<10} {'Score':>6} {'N':>4}")
    print("  " + "-" * 96)
    for r in rows:
        score_str = f"{r[6]:.2f}" if r[6] is not None else "  n/a"
        print(f"  {r[0]:<10} {r[1]:<22} {r[2]:<12} {r[3]:<14} "
              f"{r[4]:<12} {r[5]:<10} {score_str:>6} {r[7]:>4}")
```

Wire into `main()`:

```python
score_parser = subparsers.add_parser("score", help="Manage capability scores")
score_sub = score_parser.add_subparsers(dest="score_action")
score_add_parser = score_sub.add_parser("add", help="Add a human quality rating")
score_add_parser.add_argument("story_id")
score_add_parser.add_argument("rating", type=float)
score_add_parser.add_argument("--note", default=None)
score_add_parser.add_argument("--rework", action="store_true")
score_list_parser = score_sub.add_parser("list", help="Show capability scores")
score_list_parser.add_argument("--engg", default=None)
score_list_parser.add_argument("--org", default=None)
score_list_parser.add_argument("--industry", default=None)
```

Dispatch in `main()`:

```python
elif args.command == "score":
    if args.score_action == "add":
        cmd_score_add(args.story_id, args.rating, note=args.note, rework=args.rework)
    elif args.score_action == "list":
        cmd_score_list(engg=args.engg, org=args.org, industry=args.industry)
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py -k "score_add" -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -25
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: synlynk score add/list — human rating override, capability scores dashboard"
```

---

## v0.6.0 Tasks

> These tasks extend the schema and CLI introduced in Tasks 1–10. Implement after v0.5.0 is shipped.

---

### Task 11: Model Version Tier 2 — Statusline Probe at Dispatch

**Files:**
- Modify: `bin/synlynk.py:478` — `dispatch_agent()` — add `_probe_model_version()`

Before spawning the job, run a quick `synlynk status` (or equivalent agent statusline command) to capture the agent's currently active model. Store as `model_at_dispatch` in the job dict.

- [ ] **Step 1: Write failing tests**

```python
def test_probe_model_version_parses_claude_statusline(monkeypatch):
    from synlynk import _probe_model_version
    # Mock subprocess to return a statusline containing model info
    import subprocess
    fake = type("R", (), {"stdout": "claude-opus-4-8 | ctx: 45%", "returncode": 0})()
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: fake)
    result = _probe_model_version("claude", "claude")
    assert result == "claude-opus-4-8"

def test_probe_model_version_returns_unknown_on_failure(monkeypatch):
    from synlynk import _probe_model_version
    import subprocess
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: (_ for _ in ()).throw(Exception()))
    result = _probe_model_version("claude", "claude")
    assert result == "unknown"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "probe_model" -v
```

- [ ] **Step 3: Add `_probe_model_version()`**

```python
def _probe_model_version(agent_name: str, cli: str) -> str:
    """
    Tier 2: Probe the agent's active model by reading its statusline output.
    Runs `<cli> /status` or equivalent. Times out after 3s to avoid blocking dispatch.
    """
    probe_cmds = {
        "claude": [cli, "/status"],
        "gemini": [cli, "--version"],
        "codex":  [cli, "--version"],
    }
    cmd = probe_cmds.get(agent_name, [cli, "--version"])
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=3
        )
        text = result.stdout + result.stderr
        # Look for known model name patterns
        patterns = [
            r"(claude-(?:opus|sonnet|haiku)-[\d.-]+)",
            r"(gemini-[\d.]+-(?:pro|flash|ultra))",
            r"(gpt-[\d.]+-(?:turbo|preview)?)",
            r"(codex-[\w-]+)",
        ]
        for pat in patterns:
            m = re.search(pat, text, re.IGNORECASE)
            if m:
                return m.group(1).lower()
    except Exception:
        pass
    return "unknown"
```

In `dispatch_agent()`, after computing `job_id`, add:

```python
    model_at_dispatch = _probe_model_version(agent, cli)
    # ...
    job = {
        # ... existing fields ...
        "model_at_dispatch": model_at_dispatch,
    }
```

In `_write_capability_rating()`, set `model_at_dispatch` from the job dict and detect split:

```python
    model_at_dispatch = job.get("model_at_dispatch", "unknown")
    model_at_completion = model_version  # from synlynk-meta
    split_model = 1 if (model_at_dispatch != model_at_completion
                        and model_at_dispatch != "unknown"
                        and model_at_completion != "unknown") else 0
```

- [ ] **Step 4: Run to verify tests pass**

```bash
pytest tests/test_capability_scoring.py -k "probe_model" -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: model version tier 2 — statusline probe at dispatch time, split-model detection"
```

---

### Task 12: Verifier Output Parsing — `verifier_agent` / `verifier_model` in synlynk-meta

**Files:**
- Modify: `bin/synlynk.py` — extend `extract_model_version()`, update `_write_capability_rating()`

When the Verifier agent runs and emits a `synlynk-meta` block with `quality=`, `verifier_model=`, and `correct=` fields, capture those as a `verifier`-source rating row.

- [ ] **Step 1: Write failing tests**

```python
def test_extract_verifier_meta_block():
    from synlynk import extract_verifier_meta
    output = """
Code review complete.

# synlynk-meta
quality=8
correct=true
rework_needed=false
verifier_model=gemini-2.5-pro
"""
    meta = extract_verifier_meta(output)
    assert meta["quality"] == 8.0
    assert meta["correct"] is True
    assert meta["rework_needed"] is False
    assert meta["verifier_model"] == "gemini-2.5-pro"

def test_extract_verifier_meta_returns_none_when_absent():
    from synlynk import extract_verifier_meta
    assert extract_verifier_meta("No meta block here") is None
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "verifier_meta" -v
```

- [ ] **Step 3: Add `extract_verifier_meta()` and update `_write_capability_rating()`**

```python
def extract_verifier_meta(output_text: str) -> Optional[dict]:
    """
    Parses the # synlynk-meta block from a verifier agent's output.
    Returns dict with quality, correct, rework_needed, verifier_model — or None if absent.
    """
    m = re.search(r"#\s*synlynk-meta\s*\n((?:[^\n]+\n?)+)", output_text, re.IGNORECASE)
    if not m:
        return None
    block = m.group(1)
    meta = {}
    for line in block.splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            k, v = k.strip(), v.strip()
            if k == "quality":
                try: meta["quality"] = float(v)
                except ValueError: pass
            elif k == "correct":
                meta["correct"] = v.lower() in ("true", "yes", "1")
            elif k == "rework_needed":
                meta["rework_needed"] = v.lower() in ("true", "yes", "1")
            elif k == "verifier_model":
                meta["verifier_model"] = v
    return meta if "quality" in meta else None
```

In `_write_capability_rating()`, after computing `quality_auto`, check for verifier block:

```python
    verifier_meta = extract_verifier_meta(log_text)
    if verifier_meta:
        signal_source = "verifier"
        quality = verifier_meta["quality"]
        verifier_model = verifier_meta.get("verifier_model")
        verifier_agent_val = agent  # same agent ran the verify phase
    else:
        signal_source = "auto"
        quality = quality_auto
        verifier_model = None
        verifier_agent_val = None
```

Update the INSERT to include `verifier_agent` and `verifier_model` columns.

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_capability_scoring.py -k "verifier" -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: verifier output parsing — extract synlynk-meta quality block, write verifier-source rating"
```

---

### Task 13: `synlynk pr check` + `synlynk score attest`

**Files:**
- Modify: `bin/synlynk.py` — add `cmd_pr_check()`, `cmd_score_attest()`, wire into `main()`

`pr check` hard-blocks if any story with `status != completed` has `model_version = 'unknown'`. `score attest` lets an agent or human retroactively fill in the model version.

- [ ] **Step 1: Write failing tests**

```python
def test_pr_check_blocks_on_unknown_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_pr_check
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-1", "T"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-1", "claude", "unknown", "backend", "monetization", "ott",
         "build", "auto", 5.0, 5.0)
    )
    conn.commit(); conn.close()
    import pytest
    with pytest.raises(SystemExit) as exc:
        cmd_pr_check()
    assert exc.value.code != 0

def test_pr_check_passes_when_all_models_known(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_pr_check
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-2", "T"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-2", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 8.0, 8.0)
    )
    conn.commit(); conn.close()
    cmd_pr_check()  # must not raise

def test_score_attest_updates_model_version(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_score_attest
    conn = _get_db()
    conn.execute("INSERT INTO stories (story_id, title) VALUES (?,?)", ("story-3", "T"))
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
        " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("story-3", "claude", "unknown", "backend", "monetization", "ott",
         "build", "auto", 5.0, 5.0)
    )
    conn.commit(); conn.close()
    cmd_score_attest("story-3", "claude-opus-4-8")
    conn = _get_db()
    row = conn.execute("SELECT model_version FROM capability_ratings WHERE story_id=?",
                       ("story-3",)).fetchone()
    conn.close()
    assert row[0] == "claude-opus-4-8"
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "pr_check or score_attest" -v
```

- [ ] **Step 3: Implement `cmd_pr_check()` and `cmd_score_attest()`**

```python
def cmd_pr_check() -> None:
    """
    Hard-blocks merge if any capability_ratings row has model_version='unknown'.
    Exit code 1 if blocked. Exit code 0 if clean.
    """
    conn = _get_db()
    rows = conn.execute(
        "SELECT DISTINCT story_id, agent FROM capability_ratings WHERE model_version='unknown'"
    ).fetchall()
    conn.close()
    if rows:
        print("\n  🚫 [PR CHECK BLOCKED] Unattested model versions found:")
        for story_id, agent in rows:
            print(f"    story: {story_id}  agent: {agent}")
        print("\n  Fix with: synlynk score attest <story-id> --model <version>")
        print("  Or ask the author agent to run: synlynk score attest <story-id> --model <version>")
        raise SystemExit(1)
    print("  ✓ PR check passed — all model versions attested.")

def cmd_score_attest(story_id: str, model_version: str) -> None:
    """Retroactively sets model_version on all 'unknown' rows for a story."""
    conn = _get_db()
    updated = conn.execute(
        "UPDATE capability_ratings SET model_version=?, model_at_completion=? "
        "WHERE story_id=? AND model_version='unknown'",
        (model_version, model_version, story_id)
    ).rowcount
    conn.commit()
    conn.close()
    if updated:
        print(f"  ✓ Attested {updated} row(s) for {story_id} → {model_version}")
    else:
        print(f"  No 'unknown' rows found for {story_id}")
```

Wire into `main()`:

```python
pr_parser = subparsers.add_parser("pr", help="PR workflow commands")
pr_sub = pr_parser.add_subparsers(dest="pr_action")
pr_sub.add_parser("check", help="Block PR if model versions are unattested")

# Add to score sub:
attest_parser = score_sub.add_parser("attest", help="Retroactively attest model version")
attest_parser.add_argument("story_id")
attest_parser.add_argument("--model", required=True)
```

Dispatch:

```python
elif args.command == "pr":
    if args.pr_action == "check":
        cmd_pr_check()
elif args.command == "score":
    # ...
    elif args.score_action == "attest":
        cmd_score_attest(args.story_id, args.model)
```

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_capability_scoring.py -k "pr_check or score_attest" -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: synlynk pr check + score attest — hard-block merge on unknown model versions (tier 4)"
```

---

### Task 14: `org_domain_tags` — Secondary Tags for Tokq Discoverability

**Files:**
- Modify: `bin/synlynk.py` — `cmd_story_create()`, `cmd_score_add()`, `cmd_score_list()` output

`org_domain_tags` is a JSON array on `stories` and `capability_ratings`. Secondary tags are Tokq-only — never used in routing queries. Added at story creation time via `--org-tags`.

- [ ] **Step 1: Write failing tests**

```python
def test_story_create_stores_org_domain_tags(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, cmd_story_create
    cmd_story_create(title="Ad insertion", engg_domain="backend",
                     org_domain="adtech", phase="build",
                     org_domain_tags=["monetization", "workflow"])
    conn = _get_db()
    row = conn.execute("SELECT org_domain_tags FROM stories WHERE title=?",
                       ("Ad insertion",)).fetchone()
    conn.close()
    import json
    tags = json.loads(row[0])
    assert "monetization" in tags
    assert "workflow" in tags

def test_org_domain_tags_not_used_in_routing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    from synlynk import _get_db, _best_agent_for_story
    conn = _get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, "
        "org_domain_tags, industry, phase) VALUES (?,?,?,?,?,?,?)",
        ("s-1", "T", "backend", "adtech", '["monetization"]', "ott", "build")
    )
    # Only data for "monetization" org_domain (not "adtech")
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, engg_domain, "
        "org_domain, industry, phase, signal_source, quality, quality_auto) "
        "VALUES (?,?,?,?,?,?,?,?,?,?)",
        ("s-1", "claude", "claude-opus-4-8", "backend", "monetization", "ott",
         "build", "auto", 9.0, 9.0)
    )
    conn.commit(); conn.close()
    # Should NOT match — routing uses org_domain="adtech", not the tag "monetization"
    result = _best_agent_for_story("s-1")
    assert result is None  # no data for adtech at full coordinate
```

- [ ] **Step 2: Run to verify failure**

```bash
pytest tests/test_capability_scoring.py -k "org_domain_tags" -v
```

- [ ] **Step 3: Update `cmd_story_create()` to accept `org_domain_tags`**

```python
def cmd_story_create(title: str, engg_domain: str = "unknown",
                     org_domain: str = "unknown", phase: str = "build",
                     org_domain_tags: list = None) -> str:
    import json as _json
    tags_json = _json.dumps(org_domain_tags or [])
    # ... existing story_id generation and config loading ...
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, org_domain, "
        "org_domain_tags, industry, phase) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (story_id, title, engg_domain, org_domain, tags_json, industry, phase)
    )
```

Update `main()` story create parser:

```python
story_create_parser.add_argument("--org-tags", nargs="*", default=[], dest="org_domain_tags",
                                  help="Secondary org domain tags (Tokq discoverability only)")
```

In dispatch: `cmd_story_create(args.title, args.engg_domain, args.org_domain, args.phase, args.org_domain_tags)`

- [ ] **Step 4: Run tests**

```bash
pytest tests/test_capability_scoring.py -k "org_domain_tags" -v
```

- [ ] **Step 5: Run full test suite**

```bash
pytest tests/ -v 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py
git commit -m "feat: org_domain_tags — secondary tags on stories for Tokq discoverability, not routing"
```

---

## Post-Implementation

After all v0.5.0 tasks (1–10) are complete, update the roadmap:
- v0.5.0 theme: "Capability Engine — model-aware routing, SQLite WAL, 3D domain taxonomy, quality signal hierarchy"
- Mark `capability.json` reference obsolete (replaced by state.db)

After v0.6.0 tasks (11–14): update roadmap entry to include PR attestation and verifier pipeline integration.
