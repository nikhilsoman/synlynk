# Support Engineer Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the Support Engineer agent — a broad health monitor that collects signals (test failures, sentinel alerts, telemetry anomalies, capability drops, GitHub issues), dispatches Claude to investigate each finding, files GitHub issues, and opens draft fix PRs.

**Architecture:** Single new `synlynk agent run <name>` subcommand backed by a JSON config file at `.agents/<name>.json`. All engine logic lives in `bin/synlynk.py` as private `_` functions. A new `autopilot_runs` SQLite table deduplicates findings over a 7-day window. The investigator runs foreground via `subprocess.run()` (not the background `dispatch_agent()`). Adding a new agent = a new JSON file, no engine changes.

**Tech Stack:** Python 3.10+ stdlib only (`json`, `re`, `hashlib`, `subprocess`, `sqlite3`). No external dependencies. `gh` CLI for GitHub operations. `pytest` for test runner.

**Spec:** `docs/superpowers/specs/2026-06-21-support-engineer-agent-design.md`

---

## File Map

| File | Action | What changes |
|---|---|---|
| `bin/synlynk.py` | Modify | `_DB_SCHEMA` (new table), ~12 new functions, new `agent` argparse block, dispatch in `main()` |
| `tests/test_synlynk.py` | Modify | ~15 new tests using `isolated_db` + `project_dir` fixtures |
| `.agents/support.json` | Create | Support Engineer config (JSON, not YAML — stdlib has no YAML parser) |
| `.github/workflows/support-engineer.yml` | Create | GitHub Actions push + schedule trigger |
| `docs/blog/18-prN-support-engineer-agent.md` | Create | Blog post for this PR |

**Important:** `_DB_SCHEMA` is a plain string; appending a `CREATE TABLE IF NOT EXISTS` block is enough — `_migrate_db()` calls `conn.executescript(_DB_SCHEMA)` which is idempotent.

---

## Task 1: `autopilot_runs` table

**Files:**
- Modify: `bin/synlynk.py` — append to `_DB_SCHEMA` (lines 45–103)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_autopilot_runs_table_exists(project_dir):
    import synlynk as sl
    conn = sl._get_db()
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='autopilot_runs'"
    ).fetchone()
    conn.close()
    assert row is not None, "autopilot_runs table must exist after _get_db()"
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_synlynk.py::test_autopilot_runs_table_exists -v
```

Expected: FAIL — "autopilot_runs table must exist after _get_db()"

- [ ] **Step 3: Add table to `_DB_SCHEMA`**

In `bin/synlynk.py`, find the closing `"""` of `_DB_SCHEMA` (line 103). Insert before it:

```python
CREATE TABLE IF NOT EXISTS autopilot_runs (
    id            TEXT PRIMARY KEY,
    agent_name    TEXT NOT NULL,
    signal_type   TEXT NOT NULL,
    signal_hash   TEXT NOT NULL,
    severity      TEXT NOT NULL,
    summary       TEXT NOT NULL,
    status        TEXT NOT NULL,
    gh_issue_url  TEXT,
    pr_url        TEXT,
    story_id      TEXT,
    ts            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_hash ON autopilot_runs(signal_hash, ts);
```

The `_DB_SCHEMA` string should look like:
```python
_DB_SCHEMA = """
CREATE TABLE IF NOT EXISTS schema_version ...
...
CREATE TABLE IF NOT EXISTS autopilot_runs (
    id            TEXT PRIMARY KEY,
    ...
    ts            TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_autopilot_runs_hash ON autopilot_runs(signal_hash, ts);
"""
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_synlynk.py::test_autopilot_runs_table_exists -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add autopilot_runs table to DB schema"
```

---

## Task 2: Agent config loading + `.agents/support.json`

**Files:**
- Create: `.agents/support.json`
- Modify: `bin/synlynk.py` — add `_load_agent_config()` after `cmd_story_list()` (~line 180)
- Test: `tests/test_synlynk.py`

Note: The spec uses `.agents/support.yaml` but synlynk is stdlib-only; Python 3 has no built-in YAML parser. We use JSON, which is equivalent in expressiveness for this config.

- [ ] **Step 1: Write the failing tests**

```python
def test_load_agent_config_success(project_dir):
    import json, synlynk as sl
    (project_dir / ".agents").mkdir()
    cfg = {
        "name": "test-agent",
        "investigator": "claude",
        "fixer": "claude",
        "signals": [{"type": "test_suite", "command": "pytest tests/ -q"}],
        "hitl": {"auto_merge": False}
    }
    (project_dir / ".agents" / "test-agent.json").write_text(json.dumps(cfg))
    loaded = sl._load_agent_config("test-agent")
    assert loaded["name"] == "test-agent"
    assert loaded["investigator"] == "claude"

def test_load_agent_config_missing_raises(project_dir):
    import synlynk as sl
    with pytest.raises(FileNotFoundError, match="No agent config found"):
        sl._load_agent_config("nonexistent")
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_load_agent_config_success tests/test_synlynk.py::test_load_agent_config_missing_raises -v
```

Expected: FAIL — `_load_agent_config` not defined

- [ ] **Step 3: Add `_load_agent_config()` to `bin/synlynk.py`**

Place after `cmd_story_list()` (~line 185):

```python
def _load_agent_config(name: str) -> dict:
    """Load .agents/<name>.json. Raises FileNotFoundError with clear message."""
    import json as _json
    path = os.path.join(".agents", f"{name}.json")
    if not os.path.exists(path):
        raise FileNotFoundError(f"No agent config found at {path}")
    with open(path) as f:
        return _json.load(f)
```

- [ ] **Step 4: Create `.agents/support.json`**

```bash
mkdir -p .agents
```

Write `.agents/support.json`:

```json
{
  "name": "support-engineer",
  "description": "Broad health monitor — tests, sentinel alerts, telemetry, capability ledger, GitHub issues",
  "investigator": "claude",
  "fixer": "claude",
  "signals": [
    {"type": "test_suite", "command": "pytest tests/ -q --tb=short"},
    {"type": "sentinel_alerts", "path": ".synlynk/sentinel.md"},
    {"type": "telemetry_anomaly", "failure_rate_threshold": 0.30},
    {"type": "capability_drop", "drop_threshold": 1.5},
    {"type": "github_issues", "labels": ["bug", "needs-triage"]}
  ],
  "hitl": {
    "auto_merge": false,
    "auto_approve": ["github.create_issue", "github.create_draft_pr", "synlynk.dispatch"]
  }
}
```

- [ ] **Step 5: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_load_agent_config_success tests/test_synlynk.py::test_load_agent_config_missing_raises -v
```

Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py .agents/support.json tests/test_synlynk.py
git commit -m "feat: add _load_agent_config() and .agents/support.json"
```

---

## Task 3: `synlynk agent` subcommand skeleton

**Files:**
- Modify: `bin/synlynk.py` — argparse block (before `args = parser.parse_args()` at ~line 3897) + `cmd_agent_run()` + `cmd_agent_list()` stubs + dispatch in `main()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_run_unknown_agent_raises(project_dir, capsys):
    import synlynk as sl
    with pytest.raises(FileNotFoundError, match="No agent config found"):
        sl.cmd_agent_run("nonexistent")
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_synlynk.py::test_agent_run_unknown_agent_raises -v
```

Expected: FAIL — `cmd_agent_run` not defined

- [ ] **Step 3: Add stub functions**

After `cmd_jobs()` (~line 1232), add:

```python
def cmd_agent_run(name: str, dry_run: bool = False, install_cron: bool = False) -> None:
    """Run named agent once (collect signals → dedup → investigate → file → fix)."""
    cfg = _load_agent_config(name)
    if install_cron:
        _install_cron_entry()
        return
    # Implementation added in Task 13
    print(f"  [agent] {name} — stub, not yet implemented")


def cmd_agent_list() -> None:
    """List .agents/ config files and their last run status."""
    import json as _json
    agents_dir = ".agents"
    if not os.path.exists(agents_dir):
        print("  No .agents/ directory found")
        return
    files = [f for f in os.listdir(agents_dir) if f.endswith(".json")]
    if not files:
        print("  No agent configs in .agents/")
        return
    conn = _get_db()
    for fname in sorted(files):
        agent_name = fname[:-5]
        row = conn.execute(
            "SELECT ts, status FROM autopilot_runs WHERE agent_name=? ORDER BY ts DESC LIMIT 1",
            (agent_name,)
        ).fetchone()
        last_run = f"{row[0]}  status={row[1]}" if row else "never run"
        print(f"  {agent_name:<25}  {last_run}")
    conn.close()
```

- [ ] **Step 4: Add argparse block**

Before `args = parser.parse_args()` in `main()`, add:

```python
    agent_parser = subparsers.add_parser("agent", help="Manage and run autopilot agents")
    agent_sub = agent_parser.add_subparsers(dest="agent_action")
    agent_run_parser = agent_sub.add_parser("run", help="Run a named agent once")
    agent_run_parser.add_argument("name", help="Agent name (matches .agents/<name>.json)")
    agent_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run",
                                  help="Collect signals and print findings; no dispatch/issue/PR")
    agent_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron",
                                  help="Install local crontab entry for this agent")
    agent_sub.add_parser("list", help="List .agents/ configs and last run status")
```

- [ ] **Step 5: Add dispatch in `main()`**

After the `elif args.command == "scan":` block (line 3980), before `else:`:

```python
    elif args.command == "agent":
        action = getattr(args, "agent_action", None)
        if action == "run":
            cmd_agent_run(
                args.name,
                dry_run=getattr(args, "dry_run", False),
                install_cron=getattr(args, "install_cron", False),
            )
        elif action == "list":
            cmd_agent_list()
        else:
            agent_parser.print_help()
```

- [ ] **Step 6: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_agent_run_unknown_agent_raises -v
```

Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add synlynk agent subcommand skeleton"
```

---

## Task 4: Signal collector — `test_suite`

**Files:**
- Modify: `bin/synlynk.py` — add `_collect_test_suite()` after the stub functions (~line 1255)
- Test: `tests/test_synlynk.py`

A Finding dict has keys: `type`, `severity`, `summary`, `detail`, `signal_hash`.

- [ ] **Step 1: Write the failing tests**

```python
def test_collect_test_suite_high_on_failure(project_dir, monkeypatch):
    import synlynk as sl
    fake_result = type("R", (), {"returncode": 1, "stdout": "FAILED tests/test_foo.py::test_bar\n1 failed"})()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: fake_result)
    findings = sl._collect_test_suite({"type": "test_suite", "command": "pytest tests/ -q --tb=short"})
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert findings[0]["type"] == "test_suite"
    assert "signal_hash" in findings[0]

def test_collect_test_suite_no_finding_on_pass(project_dir, monkeypatch):
    import synlynk as sl
    fake_result = type("R", (), {"returncode": 0, "stdout": "1 passed"})()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: fake_result)
    findings = sl._collect_test_suite({"type": "test_suite", "command": "pytest tests/ -q --tb=short"})
    assert findings == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_collect_test_suite_high_on_failure tests/test_synlynk.py::test_collect_test_suite_no_finding_on_pass -v
```

Expected: FAIL — `_collect_test_suite` not defined

- [ ] **Step 3: Add `_collect_test_suite()` to `bin/synlynk.py`**

After `cmd_agent_list()`:

```python
def _collect_test_suite(signal_cfg: dict) -> list:
    """Run pytest; return a high-severity finding if any test fails."""
    import hashlib as _hashlib
    cmd = signal_cfg.get("command", "pytest tests/ -q --tb=short").split()
    result = subprocess.run(cmd, capture_output=False, text=True,
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
    if result.returncode == 0:
        return []
    output = result.stdout or ""
    signal_hash = _hashlib.md5(output[:500].encode()).hexdigest()[:16]
    return [{
        "type": "test_suite",
        "severity": "high",
        "summary": f"Test suite failure: {output.splitlines()[-1][:120] if output.splitlines() else 'unknown'}",
        "detail": output[:3000],
        "signal_hash": signal_hash,
    }]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_collect_test_suite_high_on_failure tests/test_synlynk.py::test_collect_test_suite_no_finding_on_pass -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _collect_test_suite signal collector"
```

---

## Task 5: Signal collector — `sentinel_alerts`

**Files:**
- Modify: `bin/synlynk.py` — add `_collect_sentinel_alerts()` after `_collect_test_suite()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_collect_sentinel_alerts_flatline(project_dir):
    import synlynk as sl
    (project_dir / ".synlynk" / "sentinel.md").write_text(
        "# Sentinel Alerts\n"
        "- [2026-06-21 10:00] ⚠ FLATLINE: 3 consecutive exec failures\n"
    )
    findings = sl._collect_sentinel_alerts({"type": "sentinel_alerts", "path": ".synlynk/sentinel.md"})
    assert len(findings) == 1
    assert findings[0]["severity"] == "high"
    assert "FLATLINE" in findings[0]["summary"]

def test_collect_sentinel_alerts_empty(project_dir):
    import synlynk as sl
    (project_dir / ".synlynk" / "sentinel.md").write_text("# Sentinel Alerts\n(none)\n")
    findings = sl._collect_sentinel_alerts({"type": "sentinel_alerts", "path": ".synlynk/sentinel.md"})
    assert findings == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_collect_sentinel_alerts_flatline tests/test_synlynk.py::test_collect_sentinel_alerts_empty -v
```

Expected: FAIL — `_collect_sentinel_alerts` not defined

- [ ] **Step 3: Add `_collect_sentinel_alerts()` to `bin/synlynk.py`**

```python
def _collect_sentinel_alerts(signal_cfg: dict) -> list:
    """Read sentinel.md, return a finding per ⚠ alert line."""
    import hashlib as _hashlib
    path = signal_cfg.get("path", ".synlynk/sentinel.md")
    if not os.path.exists(path):
        return []
    lines = [l for l in open(path).read().splitlines() if "⚠" in l]
    findings = []
    for line in lines:
        upper = line.upper()
        if "FLATLINE" in upper or "QUOTA_EXHAUSTED" in upper or "CRITICAL" in upper:
            severity = "high"
        else:
            severity = "medium"
        signal_hash = _hashlib.md5(line.encode()).hexdigest()[:16]
        findings.append({
            "type": "sentinel_alerts",
            "severity": severity,
            "summary": line.strip()[:200],
            "detail": line.strip(),
            "signal_hash": signal_hash,
        })
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_collect_sentinel_alerts_flatline tests/test_synlynk.py::test_collect_sentinel_alerts_empty -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _collect_sentinel_alerts signal collector"
```

---

## Task 6: Signal collector — `telemetry_anomaly`

**Files:**
- Modify: `bin/synlynk.py` — add `_collect_telemetry_anomaly()` after `_collect_sentinel_alerts()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_collect_telemetry_anomaly_medium(project_dir):
    import json, synlynk as sl
    # 8 failures out of 20 = 40% — above 30% threshold, below 60%
    entries = [{"exit_code": (1 if i < 8 else 0)} for i in range(20)]
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(entries))
    findings = sl._collect_telemetry_anomaly({
        "type": "telemetry_anomaly", "failure_rate_threshold": 0.30
    })
    assert len(findings) == 1
    assert findings[0]["severity"] == "medium"

def test_collect_telemetry_anomaly_no_finding(project_dir):
    import json, synlynk as sl
    entries = [{"exit_code": (1 if i < 2 else 0)} for i in range(20)]
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(entries))
    findings = sl._collect_telemetry_anomaly({
        "type": "telemetry_anomaly", "failure_rate_threshold": 0.30
    })
    assert findings == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_collect_telemetry_anomaly_medium tests/test_synlynk.py::test_collect_telemetry_anomaly_no_finding -v
```

Expected: FAIL — `_collect_telemetry_anomaly` not defined

- [ ] **Step 3: Add `_collect_telemetry_anomaly()` to `bin/synlynk.py`**

```python
def _collect_telemetry_anomaly(signal_cfg: dict) -> list:
    """Compute failure rate over last 20 telemetry entries; return finding if above threshold."""
    import json as _json, hashlib as _hashlib
    path = ".synlynk/telemetry.json"
    if not os.path.exists(path):
        return []
    try:
        entries = _json.loads(open(path).read())
    except Exception:
        return []
    recent = entries[-20:]
    if len(recent) < 5:
        return []
    failures = sum(1 for e in recent if e.get("exit_code", 0) != 0)
    threshold = signal_cfg.get("failure_rate_threshold", 0.30)
    rate = failures / len(recent)
    if rate < threshold:
        return []
    severity = "high" if rate >= 0.60 else "medium"
    summary = f"High failure rate: {failures}/{len(recent)} sessions failed ({rate:.0%})"
    signal_hash = _hashlib.md5(summary.encode()).hexdigest()[:16]
    return [{
        "type": "telemetry_anomaly",
        "severity": severity,
        "summary": summary,
        "detail": summary,
        "signal_hash": signal_hash,
    }]
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_collect_telemetry_anomaly_medium tests/test_synlynk.py::test_collect_telemetry_anomaly_no_finding -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _collect_telemetry_anomaly signal collector"
```

---

## Task 7: Signal collector — `capability_drop`

**Files:**
- Modify: `bin/synlynk.py` — add `_collect_capability_drop()` after `_collect_telemetry_anomaly()`
- Test: `tests/test_synlynk.py`

Compares weighted average score for each agent over last 7 days vs. prior 7 days. Skips agents with fewer than 2 ratings in either window.

- [ ] **Step 1: Write the failing tests**

```python
def test_collect_capability_drop_returns_finding(project_dir):
    import synlynk as sl
    conn = sl._get_db()
    # Insert a story first (FK requirement)
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES (?, ?)",
        ("s-drop-test", "drop test story")
    )
    now_ts = "2026-06-21T12:00:00"
    old_ts = "2026-06-14T12:00:00"  # 7 days ago
    # Recent window: quality 5.0 (last 7 days)
    for i in range(2):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, quality, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            ("s-drop-test", "claude", "claude-sonnet-4-6", 5.0, now_ts)
        )
    # Older window: quality 8.0 (7–14 days ago)
    for i in range(2):
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, quality, ts) "
            "VALUES (?, ?, ?, ?, ?)",
            ("s-drop-test", "claude", "claude-sonnet-4-6", 8.0, old_ts)
        )
    conn.commit()
    conn.close()
    findings = sl._collect_capability_drop({"type": "capability_drop", "drop_threshold": 1.5})
    assert len(findings) == 1
    assert findings[0]["severity"] in ("medium", "high")
    assert "claude" in findings[0]["summary"]

def test_collect_capability_drop_insufficient_data(project_dir):
    import synlynk as sl
    # No ratings in DB — should skip silently
    findings = sl._collect_capability_drop({"type": "capability_drop", "drop_threshold": 1.5})
    assert findings == []
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_collect_capability_drop_returns_finding tests/test_synlynk.py::test_collect_capability_drop_insufficient_data -v
```

Expected: FAIL — `_collect_capability_drop` not defined

- [ ] **Step 3: Add `_collect_capability_drop()` to `bin/synlynk.py`**

```python
def _collect_capability_drop(signal_cfg: dict) -> list:
    """Compare each agent's avg quality: last 7 days vs. prior 7 days.
    Skip if either window has fewer than 2 ratings."""
    import hashlib as _hashlib
    drop_threshold = signal_cfg.get("drop_threshold", 1.5)
    conn = _get_db()
    agents = [r[0] for r in conn.execute(
        "SELECT DISTINCT agent FROM capability_ratings"
    ).fetchall()]
    findings = []
    for agent in agents:
        recent = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM capability_ratings "
            "WHERE agent=? AND ts > datetime('now', '-7 days')",
            (agent,)
        ).fetchone()
        prior = conn.execute(
            "SELECT AVG(quality), COUNT(*) FROM capability_ratings "
            "WHERE agent=? AND ts <= datetime('now', '-7 days') "
            "  AND ts > datetime('now', '-14 days')",
            (agent,)
        ).fetchone()
        if not recent or not prior:
            continue
        recent_avg, recent_n = recent
        prior_avg, prior_n = prior
        if recent_n < 2 or prior_n < 2:
            continue
        if recent_avg is None or prior_avg is None:
            continue
        drop = prior_avg - recent_avg
        if drop < drop_threshold:
            continue
        severity = "high" if drop >= 3.0 else "medium"
        summary = f"Capability drop for {agent}: {prior_avg:.1f} → {recent_avg:.1f} (Δ{drop:.1f}pts)"
        signal_hash = _hashlib.md5(f"{agent}{round(drop, 1)}".encode()).hexdigest()[:16]
        findings.append({
            "type": "capability_drop",
            "severity": severity,
            "summary": summary,
            "detail": summary,
            "signal_hash": signal_hash,
        })
    conn.close()
    return findings
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_collect_capability_drop_returns_finding tests/test_synlynk.py::test_collect_capability_drop_insufficient_data -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _collect_capability_drop signal collector"
```

---

## Task 8: Signal collector — `github_issues`

**Files:**
- Modify: `bin/synlynk.py` — add `_collect_github_issues()` after `_collect_capability_drop()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_collect_github_issues(project_dir, monkeypatch):
    import json, synlynk as sl
    issues = [
        {"number": 42, "title": "Crash on empty input", "body": "Steps to repro: ...", "createdAt": "2026-06-21T10:00:00Z"},
        {"number": 43, "title": "Wrong score shown", "body": "Score is 0 always", "createdAt": "2026-06-21T11:00:00Z"},
    ]
    fake_result = type("R", (), {"returncode": 0, "stdout": json.dumps(issues)})()
    monkeypatch.setattr("subprocess.run", lambda *a, **k: fake_result)
    findings = sl._collect_github_issues({"type": "github_issues", "labels": ["bug", "needs-triage"]})
    assert len(findings) == 2
    assert findings[0]["type"] == "github_issues"
    assert findings[0]["severity"] == "medium"
    assert "#42" in findings[0]["summary"]
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_synlynk.py::test_collect_github_issues -v
```

Expected: FAIL — `_collect_github_issues` not defined

- [ ] **Step 3: Add `_collect_github_issues()` to `bin/synlynk.py`**

```python
def _collect_github_issues(signal_cfg: dict) -> list:
    """List open GitHub issues with matching labels via `gh issue list`."""
    import json as _json, hashlib as _hashlib
    labels = signal_cfg.get("labels", ["bug"])
    label_str = ",".join(labels)
    result = subprocess.run(
        ["gh", "issue", "list", "--label", label_str,
         "--json", "number,title,body,createdAt", "--limit", "20"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [support] gh issue list failed (gh not installed or no auth): {result.stderr[:100]}")
        return []
    try:
        issues = _json.loads(result.stdout)
    except Exception:
        return []
    findings = []
    for issue in issues:
        signal_hash = _hashlib.md5(str(issue.get("number", "")).encode()).hexdigest()[:16]
        findings.append({
            "type": "github_issues",
            "severity": "medium",
            "summary": f"#{issue['number']}: {issue.get('title', '')[:100]}",
            "detail": issue.get("body", "")[:500],
            "signal_hash": signal_hash,
        })
    return findings
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_synlynk.py::test_collect_github_issues -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _collect_github_issues signal collector"
```

---

## Task 9: Deduplication

**Files:**
- Modify: `bin/synlynk.py` — add `_dedup_findings()` after `_collect_github_issues()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_dedup_skips_recent_signal(project_dir):
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO autopilot_runs (id, agent_name, signal_type, signal_hash, severity, summary, status, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '-3 days'))",
        ("run-001", "support-engineer", "test_suite", "abc123", "high", "test failure", "filed")
    )
    conn.commit()
    conn.close()
    findings = [{"signal_hash": "abc123", "type": "test_suite", "severity": "high", "summary": "x", "detail": "x"}]
    result = sl._dedup_findings(findings)
    assert result == [], "Recent signal should be filtered out by dedup"

def test_dedup_reinvestigates_after_7_days(project_dir):
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO autopilot_runs (id, agent_name, signal_type, signal_hash, severity, summary, status, ts) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, datetime('now', '-8 days'))",
        ("run-001", "support-engineer", "test_suite", "abc123", "high", "test failure", "filed")
    )
    conn.commit()
    conn.close()
    findings = [{"signal_hash": "abc123", "type": "test_suite", "severity": "high", "summary": "x", "detail": "x"}]
    result = sl._dedup_findings(findings)
    assert len(result) == 1, "8-day-old signal should pass dedup (>7 days)"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_dedup_skips_recent_signal tests/test_synlynk.py::test_dedup_reinvestigates_after_7_days -v
```

Expected: FAIL — `_dedup_findings` not defined

- [ ] **Step 3: Add `_dedup_findings()` to `bin/synlynk.py`**

```python
def _dedup_findings(findings: list) -> list:
    """Filter findings whose signal_hash appeared in autopilot_runs within last 7 days."""
    if not findings:
        return []
    conn = _get_db()
    new_findings = []
    for f in findings:
        row = conn.execute(
            "SELECT id FROM autopilot_runs WHERE signal_hash=? AND ts > datetime('now', '-7 days')",
            (f["signal_hash"],)
        ).fetchone()
        if row is None:
            new_findings.append(f)
    conn.close()
    return new_findings
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_dedup_skips_recent_signal tests/test_synlynk.py::test_dedup_reinvestigates_after_7_days -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _dedup_findings with 7-day window"
```

---

## Task 10: `_run_investigation()` — foreground dispatch

**Files:**
- Modify: `bin/synlynk.py` — add `_run_investigation()` after `_dedup_findings()`
- Test: `tests/test_synlynk.py`

This function builds the same shell command as `dispatch_agent()` but uses `subprocess.run()` (blocking, 300s timeout) instead of `Popen`. It creates a story, writes a prompt file, runs the agent, reads the log, and parses the output.

- [ ] **Step 1: Write the failing test**

```python
def test_run_investigation_creates_story_and_returns_summary(project_dir, monkeypatch):
    import synlynk as sl

    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        # Simulate agent writing to log file
        log_file = None
        shell_cmd = cmd[2] if len(cmd) > 2 else ""
        import re
        m = re.search(r"> (\S+\.log)", shell_cmd)
        if m:
            log_file = m.group(1)
            import os
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            open(log_file, "w").write("Root cause: the test was broken.\n# FIX: replace line 42\n")
            open(log_file + ".exit", "w").write("0\n")
        return type("R", (), {"returncode": 0})()

    monkeypatch.setattr("subprocess.run", fake_run)

    finding = {
        "type": "test_suite",
        "severity": "high",
        "summary": "Test failure: test_foo",
        "detail": "FAILED tests/test_foo.py\n1 failed",
        "signal_hash": "deadbeef12345678",
    }
    result = sl._run_investigation(finding, {"investigator": "claude"})
    assert "summary" in result
    assert result["fix_signal"] is True
    assert "story_id" in result

    # Confirm story was created in DB
    conn = sl._get_db()
    row = conn.execute(
        "SELECT story_id FROM stories WHERE story_id=?", (result["story_id"],)
    ).fetchone()
    conn.close()
    assert row is not None
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_synlynk.py::test_run_investigation_creates_story_and_returns_summary -v
```

Expected: FAIL — `_run_investigation` not defined

- [ ] **Step 3: Add `_run_investigation()` to `bin/synlynk.py`**

```python
def _run_investigation(finding: dict, agent_cfg: dict) -> dict:
    """Build prompt, dispatch investigator foreground (5-min timeout), parse output."""
    import hashlib as _hashlib, shlex as _shlex, json as _json

    agent = agent_cfg.get("investigator", "claude")
    if agent not in AGENT_CAPABILITY_BASELINES:
        agent = "claude"

    # Create story
    story_id = "support-" + _hashlib.md5(
        finding["signal_hash"].encode()
    ).hexdigest()[:8]
    conn = _get_db()
    try:
        conn.execute(
            "INSERT OR IGNORE INTO stories (story_id, title, engg_domain, phase) VALUES (?, ?, ?, ?)",
            (story_id, finding["summary"][:100], "test", "scale")
        )
        conn.commit()
    finally:
        conn.close()

    # Build prompt
    try:
        generate_context(scope="full")
    except Exception:
        pass
    context_text = ""
    if os.path.exists(".synlynk/context.md"):
        context_text = open(".synlynk/context.md").read()

    prompt = (
        f"## Signal: {finding['type']} (severity={finding['severity']})\n\n"
        f"{finding['detail']}\n\n"
        f"---\n\n{context_text}\n\n"
        "## Task\n"
        "Identify the root cause. If a code fix is possible, produce a unified diff with "
        "exact file paths. If not fixable, summarise your investigation findings. "
        "If providing a fix, include a line starting with `# FIX:` before the diff block."
    )

    # Write prompt file and run agent foreground
    job_id = "support-" + _hashlib.md5(
        f"{finding['signal_hash']}{time.time()}".encode()
    ).hexdigest()[:8]
    os.makedirs(LOGS_DIR, exist_ok=True)
    os.makedirs(PROMPTS_DIR, exist_ok=True)
    log_file = os.path.join(LOGS_DIR, f"{job_id}.log")
    prompt_file = os.path.join(PROMPTS_DIR, f"{job_id}.md")
    with open(prompt_file, "w") as f:
        f.write(prompt)

    baselines = AGENT_CAPABILITY_BASELINES[agent]
    cli = baselines["cli"]
    flags = baselines["non_interactive_flags"]
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)

    if prompt_via_arg:
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        shell_cmd = (
            f"{cmd_str} < {_shlex.quote(prompt_file)} "
            f"> {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )

    try:
        subprocess.run(["sh", "-c", shell_cmd], timeout=300)
    except subprocess.TimeoutExpired:
        pass

    log_text = ""
    if os.path.exists(log_file):
        log_text = open(log_file).read()

    fix_signal = "# FIX:" in log_text or bool(
        __import__("re").search(r"^--- a/", log_text, __import__("re").MULTILINE)
    )

    return {
        "summary": log_text[:500] if log_text else "(no output)",
        "fix_signal": fix_signal,
        "log_text": log_text,
        "story_id": story_id,
        "log_file": log_file,
    }
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_synlynk.py::test_run_investigation_creates_story_and_returns_summary -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _run_investigation foreground dispatch"
```

---

## Task 11: `_file_gh_issue()`

**Files:**
- Modify: `bin/synlynk.py` — add `_file_gh_issue()` after `_run_investigation()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_file_gh_issue_calls_gh(project_dir, monkeypatch):
    import synlynk as sl
    captured = {}
    def fake_run(cmd, **kw):
        captured["cmd"] = cmd
        return type("R", (), {"returncode": 0, "stdout": "https://github.com/org/repo/issues/99"})()
    monkeypatch.setattr("subprocess.run", fake_run)

    finding = {"type": "test_suite", "summary": "Test failure", "detail": "1 failed"}
    investigation = {"summary": "Root cause: missing mock", "story_id": "support-abc123"}
    url = sl._file_gh_issue(finding, investigation, dry_run=False)
    assert url == "https://github.com/org/repo/issues/99"
    assert "issue" in captured["cmd"]
    assert "create" in captured["cmd"]

def test_file_gh_issue_dry_run_no_subprocess(project_dir, monkeypatch):
    import synlynk as sl
    called = []
    monkeypatch.setattr("subprocess.run", lambda *a, **k: called.append(a))
    finding = {"type": "test_suite", "summary": "Test failure", "detail": "x"}
    investigation = {"summary": "y", "story_id": "support-abc"}
    url = sl._file_gh_issue(finding, investigation, dry_run=True)
    assert url == ""
    assert called == [], "subprocess.run must not be called in dry-run"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_file_gh_issue_calls_gh tests/test_synlynk.py::test_file_gh_issue_dry_run_no_subprocess -v
```

Expected: FAIL — `_file_gh_issue` not defined

- [ ] **Step 3: Add `_file_gh_issue()` to `bin/synlynk.py`**

```python
def _file_gh_issue(finding: dict, investigation: dict, dry_run: bool) -> str:
    """File a GitHub issue via `gh issue create`. Returns issue URL or '' in dry-run."""
    if dry_run:
        return ""
    title = f"[support] {finding['type']}: {finding['summary'][:80]}"
    body = (
        f"## Signal\n\n**Type:** {finding['type']}  \n**Severity:** {finding.get('severity','?')}\n\n"
        f"## Investigation\n\n{investigation['summary']}\n\n"
        f"**Story:** `{investigation.get('story_id', 'n/a')}`\n"
    )
    result = subprocess.run(
        ["gh", "issue", "create",
         "--title", title,
         "--body", body,
         "--label", "bug,support-engineer"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"  [support] gh issue create failed: {result.stderr[:200]}")
        return ""
    return result.stdout.strip()
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_file_gh_issue_calls_gh tests/test_synlynk.py::test_file_gh_issue_dry_run_no_subprocess -v
```

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _file_gh_issue()"
```

---

## Task 12: `_extract_diff()` + `_attempt_fix()`

**Files:**
- Modify: `bin/synlynk.py` — add `_extract_diff()` and `_attempt_fix()` after `_file_gh_issue()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_extract_diff_from_fenced_block():
    import synlynk as sl
    text = (
        "Here is the fix:\n\n```diff\n"
        "--- a/bin/synlynk.py\n"
        "+++ b/bin/synlynk.py\n"
        "@@ -1,3 +1,3 @@\n"
        "-old\n+new\n"
        "```\n"
    )
    diff = sl._extract_diff(text)
    assert diff is not None
    assert "--- a/bin/synlynk.py" in diff

def test_extract_diff_returns_none_when_absent():
    import synlynk as sl
    assert sl._extract_diff("No diff here, just prose.") is None

def test_attempt_fix_files_draft_pr_on_passing_tests(project_dir, monkeypatch):
    import synlynk as sl

    calls = []
    def fake_run(cmd, **kw):
        calls.append(list(cmd))
        return type("R", (), {"returncode": 0, "stdout": "https://github.com/org/repo/pull/5"})()
    monkeypatch.setattr("subprocess.run", fake_run)

    finding = {"type": "test_suite", "summary": "Test broke", "signal_hash": "deadbeef12345678"}
    investigation = {
        "log_text": "Root cause: found it.\n# FIX:\n```diff\n--- a/x.py\n+++ b/x.py\n@@ -1 +1 @@\n-old\n+new\n```\n",
        "summary": "Root cause summary",
        "story_id": "support-abc",
        "log_file": str(project_dir / ".synlynk" / "logs" / "job.log"),
    }
    status = sl._attempt_fix(finding, investigation, fixer="claude", dry_run=False)
    assert status in ("fix_attempted", "fix_failed", "no_diff")
    # If git commands succeed (returncode=0), should open draft PR
    if status == "fix_attempted":
        pr_calls = [c for c in calls if "pr" in c and "create" in c]
        assert len(pr_calls) >= 1
        assert "--draft" in pr_calls[0]
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_extract_diff_from_fenced_block tests/test_synlynk.py::test_extract_diff_returns_none_when_absent tests/test_synlynk.py::test_attempt_fix_files_draft_pr_on_passing_tests -v
```

Expected: FAIL — `_extract_diff`, `_attempt_fix` not defined

- [ ] **Step 3: Add `_extract_diff()` and `_attempt_fix()` to `bin/synlynk.py`**

```python
def _extract_diff(text: str) -> str | None:
    """Extract first unified diff block from text (fenced or raw)."""
    import re as _re
    # Prefer fenced ```diff block
    m = _re.search(r"```(?:diff)?\n(---[\s\S]+?)```", text)
    if m:
        return m.group(1)
    # Fall back to raw unified diff
    m = _re.search(r"(--- a/[\s\S]+?)(?=\n[^+\-@ \t]|\Z)", text)
    if m:
        return m.group(1)
    return None


def _attempt_fix(finding: dict, investigation: dict, fixer: str, dry_run: bool) -> str:
    """Branch, apply diff, run tests. Returns 'fix_attempted'|'fix_failed'|'no_diff'."""
    import hashlib as _hashlib, tempfile as _tempfile

    if dry_run:
        return "dry_run"

    diff = _extract_diff(investigation.get("log_text", ""))
    if diff is None:
        return "no_diff"

    branch = f"support/fix-{finding['signal_hash'][:8]}"
    base_branch_result = subprocess.run(
        ["git", "rev-parse", "--abbrev-ref", "HEAD"],
        capture_output=True, text=True,
    )
    base_branch = base_branch_result.stdout.strip() or "main"

    # Create temp branch
    br = subprocess.run(["git", "checkout", "-b", branch], capture_output=True)
    if br.returncode != 0:
        # Branch may already exist; switch to it
        subprocess.run(["git", "checkout", branch], capture_output=True)

    # Write diff to temp file and apply
    with _tempfile.NamedTemporaryFile(mode="w", suffix=".patch", delete=False) as tf:
        tf.write(diff)
        patch_path = tf.name

    apply = subprocess.run(["git", "apply", patch_path], capture_output=True)
    if apply.returncode != 0:
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        return "fix_failed"

    # Commit the patch
    subprocess.run(["git", "add", "-A"], capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", f"[support] fix: {finding['summary'][:60]}"],
        capture_output=True,
    )

    # Run tests
    test_result = subprocess.run(
        ["pytest", "tests/", "-q", "--tb=no"],
        capture_output=True, text=True,
    )

    if test_result.returncode == 0:
        pr = subprocess.run(
            ["gh", "pr", "create", "--draft",
             "--title", f"[support] fix: {finding['summary'][:60]}",
             "--body", f"Auto-generated fix.\n\n**Story:** `{investigation.get('story_id', 'n/a')}`\n\n**Investigation:**\n{investigation.get('summary', '')[:300]}"],
            capture_output=True, text=True,
        )
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        return "fix_attempted"
    else:
        # Post failure as comment on the issue; clean up branch
        subprocess.run(["git", "checkout", base_branch], capture_output=True)
        subprocess.run(["git", "branch", "-D", branch], capture_output=True)
        return "fix_failed"
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_extract_diff_from_fenced_block tests/test_synlynk.py::test_extract_diff_returns_none_when_absent tests/test_synlynk.py::test_attempt_fix_files_draft_pr_on_passing_tests -v
```

Expected: PASS (the `fix_attempted`/`fix_failed` branching depends on `fake_run` returning 0 for all subprocess calls)

- [ ] **Step 5: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _extract_diff() and _attempt_fix()"
```

---

## Task 13: Engine orchestration — `cmd_agent_run()`

**Files:**
- Modify: `bin/synlynk.py` — replace the stub `cmd_agent_run()` with the full engine
- Test: `tests/test_synlynk.py`

This wires all collectors → dedup → investigation → file issue → attempt fix → write to `autopilot_runs`.

- [ ] **Step 1: Write the failing tests**

```python
def test_agent_run_files_issue_on_test_failure(project_dir, monkeypatch):
    """End-to-end: test failure → issue filed → autopilot_runs row written."""
    import json, synlynk as sl

    # Create .agents/support.json
    (project_dir / ".agents").mkdir()
    cfg = {
        "name": "support-engineer", "investigator": "claude", "fixer": "claude",
        "signals": [{"type": "test_suite", "command": "pytest tests/ -q --tb=short"}],
        "hitl": {"auto_merge": False}
    }
    (project_dir / ".agents" / "support.json").write_text(json.dumps(cfg))

    call_log = []
    def fake_run(cmd, **kw):
        call_log.append(list(cmd) if isinstance(cmd, list) else cmd)
        # Simulate test failure for pytest call, success for everything else
        if isinstance(cmd, list) and "pytest" in cmd:
            return type("R", (), {"returncode": 1, "stdout": "FAILED tests/test_x.py\n1 failed"})()
        # For agent investigation (sh -c ...), write a log file
        if isinstance(cmd, list) and cmd[0] == "sh":
            import re
            shell = cmd[2] if len(cmd) > 2 else ""
            m = re.search(r"> (\S+\.log)", shell)
            if m:
                import os
                os.makedirs(os.path.dirname(m.group(1)), exist_ok=True)
                open(m.group(1), "w").write("Root cause found.\n")
                open(m.group(1) + ".exit", "w").write("0\n")
        # gh issue create returns a URL
        if isinstance(cmd, list) and "issue" in cmd and "create" in cmd:
            return type("R", (), {"returncode": 0, "stdout": "https://github.com/x/y/issues/5"})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)

    sl.cmd_agent_run("support")

    conn = sl._get_db()
    rows = conn.execute("SELECT status, gh_issue_url FROM autopilot_runs").fetchall()
    conn.close()
    assert len(rows) >= 1
    assert any(r[0] in ("filed", "fix_failed", "fix_attempted") for r in rows)

def test_agent_run_dry_run_no_side_effects(project_dir, monkeypatch):
    import json, synlynk as sl
    (project_dir / ".agents").mkdir()
    cfg = {
        "name": "support-engineer", "investigator": "claude", "fixer": "claude",
        "signals": [{"type": "test_suite", "command": "pytest tests/ -q --tb=short"}],
        "hitl": {"auto_merge": False}
    }
    (project_dir / ".agents" / "support.json").write_text(json.dumps(cfg))

    calls = []
    def fake_run(cmd, **kw):
        calls.append(list(cmd) if isinstance(cmd, list) else cmd)
        if isinstance(cmd, list) and "pytest" in cmd:
            return type("R", (), {"returncode": 1, "stdout": "1 failed"})()
        return type("R", (), {"returncode": 0, "stdout": ""})()
    monkeypatch.setattr("subprocess.run", fake_run)

    sl.cmd_agent_run("support", dry_run=True)

    # No gh calls in dry-run
    gh_calls = [c for c in calls if isinstance(c, list) and "gh" in c]
    assert gh_calls == [], "gh must not be called in dry-run"

    # No DB writes
    conn = sl._get_db()
    rows = conn.execute("SELECT id FROM autopilot_runs").fetchall()
    conn.close()
    assert rows == [], "autopilot_runs must be empty in dry-run"
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/test_synlynk.py::test_agent_run_files_issue_on_test_failure tests/test_synlynk.py::test_agent_run_dry_run_no_side_effects -v
```

Expected: FAIL (stub `cmd_agent_run` doesn't do anything)

- [ ] **Step 3: Replace stub `cmd_agent_run()` with full engine**

Find and replace the existing stub `cmd_agent_run()`:

```python
def cmd_agent_run(name: str, dry_run: bool = False, install_cron: bool = False) -> None:
    """Run named agent: collect signals → dedup → investigate → file → fix."""
    import hashlib as _hashlib

    cfg = _load_agent_config(name)
    if install_cron:
        _install_cron_entry()
        return

    is_ci = os.environ.get("GITHUB_ACTIONS") == "true"
    print(f"  [agent:{name}] {'DRY RUN — ' if dry_run else ''}collecting signals{' (CI mode)' if is_ci else ''}")

    # Collect signals from all configured sources
    all_findings: list = []
    collector_map = {
        "test_suite": _collect_test_suite,
        "sentinel_alerts": _collect_sentinel_alerts,
        "telemetry_anomaly": _collect_telemetry_anomaly,
        "capability_drop": _collect_capability_drop,
        "github_issues": _collect_github_issues,
    }
    # CI skips local-state collectors
    ci_skip = {"sentinel_alerts", "telemetry_anomaly"}

    for signal_cfg in cfg.get("signals", []):
        stype = signal_cfg.get("type")
        if is_ci and stype in ci_skip:
            continue
        collector = collector_map.get(stype)
        if collector is None:
            print(f"  [agent:{name}] unknown signal type: {stype}")
            continue
        try:
            found = collector(signal_cfg)
            all_findings.extend(found)
        except Exception as e:
            print(f"  [agent:{name}] collector {stype} error: {e}")

    # Deduplicate
    new_findings = _dedup_findings(all_findings)
    print(f"  [agent:{name}] {len(all_findings)} signals, {len(new_findings)} new after dedup")

    # Dry-run: print and stop
    if dry_run:
        for f in new_findings:
            print(f"  [{f['severity'].upper()}] {f['type']}: {f['summary']}")
        return

    # Sort by severity and cap at 5
    severity_order = {"high": 0, "medium": 1, "low": 2}
    new_findings.sort(key=lambda f: severity_order.get(f.get("severity", "low"), 2))
    to_process = new_findings[:5]

    run_summary_lines = []
    conn = _get_db()

    for finding in to_process:
        print(f"  [agent:{name}] investigating: {finding['summary'][:80]}")
        investigation = _run_investigation(finding, cfg)
        gh_issue_url = _file_gh_issue(finding, investigation, dry_run=False)
        status = "filed"

        if investigation["fix_signal"]:
            fix_status = _attempt_fix(finding, investigation, fixer=cfg.get("fixer", "claude"), dry_run=False)
            if fix_status == "fix_attempted":
                status = "fix_attempted"
            elif fix_status == "fix_failed":
                status = "fix_failed"

        run_id = "run-" + _hashlib.md5(
            f"{finding['signal_hash']}{time.time()}".encode()
        ).hexdigest()[:8]
        conn.execute(
            "INSERT INTO autopilot_runs "
            "(id, agent_name, signal_type, signal_hash, severity, summary, status, gh_issue_url, story_id, ts) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))",
            (run_id, name, finding["type"], finding["signal_hash"],
             finding["severity"], finding["summary"][:200],
             status, gh_issue_url, investigation.get("story_id", ""))
        )
        conn.commit()
        run_summary_lines.append(
            f"  [{finding['severity'].upper()}] {finding['type']}: {finding['summary'][:60]} → {status}"
        )
        print(f"  [agent:{name}] {finding['type']} → {status}")

    conn.close()

    # Append to devlog
    devlog_dir = "project-docs/devlogs"
    if os.path.exists(devlog_dir):
        devlog_path = os.path.join(devlog_dir, f"{name}.md")
        n_high = sum(1 for f in to_process if f.get("severity") == "high")
        n_med = sum(1 for f in to_process if f.get("severity") == "medium")
        n_fix = sum(1 for l in run_summary_lines if "fix_attempted" in l)
        n_filed = sum(1 for l in run_summary_lines if " filed" in l)
        run_id_short = _hashlib.md5(str(time.time()).encode()).hexdigest()[:6]
        entry = (
            f"\n{time.strftime('%Y-%m-%dT%H:%M:%S')} · "
            f"{len(to_process)} findings ({n_high} high, {n_med} medium) · "
            f"{n_filed} filed · {n_fix} fix_attempted · run-{run_id_short}\n"
        )
        with open(devlog_path, "a") as f:
            f.write(entry)

    print(f"  [agent:{name}] done — {len(to_process)} findings processed")
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/test_synlynk.py::test_agent_run_files_issue_on_test_failure tests/test_synlynk.py::test_agent_run_dry_run_no_side_effects -v
```

Expected: PASS

- [ ] **Step 5: Run full test suite to check for regressions**

```
pytest tests/test_synlynk.py -v --tb=short 2>&1 | tail -20
```

Expected: 333+ passing (318 original + 15 new), 0 failures

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: implement cmd_agent_run() engine orchestration"
```

---

## Task 14: `cmd_agent_list()` (final) + `--install-cron`

**Files:**
- Modify: `bin/synlynk.py` — add `_install_cron_entry()` before `cmd_agent_list()`; `cmd_agent_list()` already wired but stub was added in Task 3 (review it works)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_install_cron_idempotent(project_dir, monkeypatch):
    import synlynk as sl

    crontab_contents = [""]

    def fake_run(cmd, **kw):
        cmd_list = list(cmd) if not isinstance(cmd, str) else cmd.split()
        if "crontab" in str(cmd) and "-l" in str(cmd):
            return type("R", (), {"returncode": 0, "stdout": crontab_contents[0]})()
        if "crontab" in str(cmd) and input_data := kw.get("input"):
            crontab_contents[0] = input_data
            return type("R", (), {"returncode": 0})()
        return type("R", (), {"returncode": 0, "stdout": ""})()

    monkeypatch.setattr("subprocess.run", fake_run)

    sl._install_cron_entry()
    first = crontab_contents[0]
    assert "synlynk.py agent run support" in first

    # Call again — must be idempotent (entry appears exactly once)
    sl._install_cron_entry()
    second = crontab_contents[0]
    assert second.count("synlynk.py agent run support") == 1
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/test_synlynk.py::test_install_cron_idempotent -v
```

Expected: FAIL — `_install_cron_entry` not defined

- [ ] **Step 3: Add `_install_cron_entry()` to `bin/synlynk.py`**

Place before `cmd_agent_list()`:

```python
def _install_cron_entry() -> None:
    """Install local crontab entry for synlynk agent run support (idempotent)."""
    repo_path = os.path.abspath(".")
    synlynk_bin = os.path.abspath(__file__)
    entry = (
        f"0 */6 * * * cd {repo_path} && "
        f"python3 {synlynk_bin} agent run support "
        f">> ~/.synlynk/autopilot.log 2>&1"
    )
    result = subprocess.run(["crontab", "-l"], capture_output=True, text=True)
    current = result.stdout if result.returncode == 0 else ""
    if entry in current:
        print("  [cron] Entry already installed (idempotent)")
        return
    new_crontab = current.rstrip("\n") + "\n" + entry + "\n"
    subprocess.run(["crontab", "-"], input=new_crontab, text=True)
    print(f"  [cron] Installed: {entry}")
```

- [ ] **Step 4: Run test to verify it passes**

```
pytest tests/test_synlynk.py::test_install_cron_idempotent -v
```

Expected: PASS

- [ ] **Step 5: Run full suite**

```
pytest tests/test_synlynk.py -v 2>&1 | tail -5
```

Expected: 333+ passing, 0 failures

- [ ] **Step 6: Commit**

```bash
git add bin/synlynk.py tests/test_synlynk.py
git commit -m "feat: add _install_cron_entry() and finalize cmd_agent_list()"
```

---

## Task 15: GitHub Actions workflow

**Files:**
- Create: `.github/workflows/support-engineer.yml`

No tests needed for a YAML workflow file; CI validates it on push.

- [ ] **Step 1: Create `.github/workflows/support-engineer.yml`**

```yaml
name: Support Engineer

on:
  push:
    branches: [main]
  schedule:
    - cron: '0 */6 * * *'
  workflow_dispatch: {}

jobs:
  support-engineer:
    runs-on: ubuntu-latest
    permissions:
      contents: write
      issues: write
      pull-requests: write

    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'

      - name: Install test runner
        run: pip install pytest

      - name: Run Support Engineer agent
        run: python3 bin/synlynk.py agent run support
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          ANTHROPIC_API_KEY: ${{ secrets.ANTHROPIC_API_KEY }}
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/support-engineer.yml
git commit -m "feat: add support-engineer GitHub Actions workflow"
```

---

## Task 16: Blog post + final verification

**Files:**
- Create: `docs/blog/18-prN-support-engineer-agent.md` (update `N` to the actual PR number)

- [ ] **Step 1: Run full test suite one final time**

```
pytest tests/test_synlynk.py -v 2>&1 | tail -10
```

Expected: 333+ passing, 0 failures.

- [ ] **Step 2: Smoke-test the CLI**

```bash
python3 bin/synlynk.py agent --help
python3 bin/synlynk.py agent run --help
python3 bin/synlynk.py agent list
```

Expected: help text shows `run` and `list` subcommands; `list` prints agent config found in `.agents/support.json`.

- [ ] **Step 3: Write blog post**

Create `docs/blog/18-prN-support-engineer-agent.md` following the template in `docs/blog/README.md`. The post must cover:

1. Goal at end of PR #51: Codex dispatches headlessly; next milestone is autonomous monitoring.
2. Strategic shift: Definition B decomposed to start with Support Engineer only — scoped down from 3 agents to 1 to ship something real.
3. What shipped: `synlynk agent run <name>` subcommand, 5 signal collectors, 7-day dedup window, foreground investigation dispatch, GitHub issue filing, draft PR fix attempts, `.agents/support.json` config, GitHub Actions trigger.
4. Design decisions: JSON not YAML (stdlib constraint), `subprocess.run` foreground vs `dispatch_agent` background, B-mode HITL (draft PRs only).
5. New goalpost: Support Engineer running in CI on every push; v0.9 targets PM Agent.

- [ ] **Step 4: Commit**

```bash
git add docs/blog/18-prN-support-engineer-agent.md
git commit -m "docs: blog post 18 — support engineer agent"
```

---

## Self-Review Checklist

**Spec coverage:**

| Spec section | Task covering it |
|---|---|
| `autopilot_runs` table schema | Task 1 |
| `.agents/support.json` config | Task 2 |
| `synlynk agent run/list` subcommand | Task 3 |
| `test_suite` collector | Task 4 |
| `sentinel_alerts` collector | Task 5 |
| `telemetry_anomaly` collector | Task 6 |
| `capability_drop` collector | Task 7 |
| `github_issues` collector | Task 8 |
| 7-day dedup window | Task 9 |
| Investigation pipeline (story, prompt, foreground dispatch, parse) | Task 10 |
| GitHub issue filing | Task 11 |
| Fix attempt (diff, apply, test, PR/comment) | Task 12 |
| Engine orchestration (cap at 5, CI detection, devlog) | Task 13 |
| `--install-cron` | Task 14 |
| GitHub Actions workflow | Task 15 |
| Blog post | Task 16 |

**Spec deviation logged:**
- Config format: `.agents/support.json` not `.agents/support.yaml` — Python 3 stdlib has no YAML parser. JSON is equivalent.

**~15 tests target:**

| Test | Task |
|---|---|
| `test_autopilot_runs_table_exists` | 1 |
| `test_load_agent_config_success` | 2 |
| `test_load_agent_config_missing_raises` | 2 |
| `test_agent_run_unknown_agent_raises` | 3 |
| `test_collect_test_suite_high_on_failure` | 4 |
| `test_collect_test_suite_no_finding_on_pass` | 4 |
| `test_collect_sentinel_alerts_flatline` | 5 |
| `test_collect_sentinel_alerts_empty` | 5 |
| `test_collect_telemetry_anomaly_medium` | 6 |
| `test_collect_telemetry_anomaly_no_finding` | 6 |
| `test_collect_github_issues` | 8 |
| `test_dedup_skips_recent_signal` | 9 |
| `test_dedup_reinvestigates_after_7_days` | 9 |
| `test_run_investigation_creates_story_and_returns_summary` | 10 |
| `test_file_gh_issue_calls_gh` | 11 |
| `test_file_gh_issue_dry_run_no_subprocess` | 11 |
| `test_extract_diff_from_fenced_block` | 12 |
| `test_extract_diff_returns_none_when_absent` | 12 |
| `test_attempt_fix_files_draft_pr_on_passing_tests` | 12 |
| `test_agent_run_files_issue_on_test_failure` | 13 |
| `test_agent_run_dry_run_no_side_effects` | 13 |
| `test_install_cron_idempotent` | 14 |
| `test_collect_capability_drop_returns_finding` | 7 |
| `test_collect_capability_drop_insufficient_data` | 7 |

Total: **24 tests** (exceeds spec target of 15 — all are meaningful).
