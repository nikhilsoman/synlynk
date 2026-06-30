# BS-14 Harness Compatibility System Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the synlynk Harness Compatibility System — eliminating silent dispatch hangs, enforcing per-harness execution contracts, and maintaining a live Command Interoperability Matrix across all agents.

**Architecture:** CLI wrapper stays in `synlynk/__init__.py` (no package split). All harness state lives in `state.db` (five new tables). Three trigger chains: `synlynk probe` (install/init/repair), dispatch preflight (every dispatch, ~2s), and sentinel-triggered background `synlynk doctor`. Stub CLIs via `tmp_path` + `PATH` monkeypatching for all tests — never call real vendor CLIs in tests.

**Tech Stack:** Python 3 stdlib only (`subprocess`, `socket`, `re`, `hashlib`, `sqlite3`). PTY fallback via `pty` module — POSIX only (`sys.platform != 'win32'`), no Windows support in scope.

---

## Architect Decisions (do not re-debate in implementation)

| Question | Decision |
|---|---|
| PTY portability | POSIX only. Guard with `sys.platform != 'win32'`. No Windows support. |
| Version check frequency on dispatch | Cache: read `harness_records.installed_version` + compare `last_probe_at`. Only spawn `--version` if record is stale (>1hr). Dispatch target stays ~2s. |
| Doctor auto-remedy vs log-only | Log-only by default. `synlynk doctor --apply` flag applies fixes. Sentinel always fires; repair is opt-in. |
| `check_stall()` reuse | Do NOT reuse existing `check_stall()` — it is job-global and state-file-based. Replace with per-job log-byte check inside `_reconcile_jobs()`. |
| Background doctor queue | Reuse existing job/daemon machinery. Doctor runs as a regular dispatched job with `--agent internal`. No second queue. |

---

## Sequencing Constraints

```
Phase 1 (v0.10.1):
  story-bs14-grok-flags   ─┐
  story-bs14-agy-contract  ├──► story-bs14-sentinel-stall ──► story-bs14-preflight
  (fixes before guard)     ┘    (stall before preflight)

Phase 2 (v0.11.0):
  story-bs14-schema ──► story-bs14-probe
                    ──► story-bs14-doctor
                    ──► story-bs14-fence
                    ──► story-bs14-agent-json
                    ──► story-bs14-verb-map ──► story-bs14-palette
                    ──► story-bs14-drift
```

**Critical:** `story-bs14-schema` must land first in Phase 2. All subsequent tasks write to the new tables. Do not wire the preflight hard-block until schema + backfill are in place.

---

## Agent Allocations

| Story | Owner | Reviewer | Rationale |
|---|---|---|---|
| story-bs14-grok-flags | **Grok** | Claude | Knows its own CLI baseline; can live-verify flag rejection |
| story-bs14-agy-contract | **Agy** | Claude | Knows its own PTY/pipe behaviour; can verify PYTHONUNBUFFERED contract |
| story-bs14-sentinel-stall | **Agy** | Claude | Process state management + config extension |
| story-bs14-preflight | **Codex** | Claude | Network socket code + flag matching — clean Python systems code |
| story-bs14-schema | **Codex** | Claude | SQL migrations — precision required, no hallucination risk |
| story-bs14-probe | **Codex** | Claude | Complex multi-path flow; needs implementation precision |
| story-bs14-doctor | **Codex** | Claude | TC-1–TC-4 systems compliance; Agy + Grok validate their harness branches |
| story-bs14-verb-map | **Agy** | Claude | Structured cross-harness matrix data entry |
| story-bs14-palette | **Codex** | Claude | Regex/parser for `--help` tree |
| story-bs14-fence | **Agy** | Claude | Markdown fence upsert + text file byte-preservation |
| story-bs14-agent-json | **Codex** | Claude | Schema field migration + loader/writer updates |
| story-bs14-drift | **Codex** | Claude | SHA256 hash computation + append-only history log |

Claude role: architect, code review, deploy only. No implementation.

---

## File Map

| File | Changes |
|---|---|
| `synlynk/__init__.py` | All new functions — probe, doctor, preflight, fence, stall detection, schema migration |
| `tests/test_synlynk.py` | New test cases for all BS-14 stories |
| `tests/test_harness_compatibility.py` | New file — dedicated harness tests (palette scan, verb map, fence upsert) |
| `tests/test_instruction_reach.py` | Extend with fence upsert tests |
| `.agents/grok.json` | Remove `--always-approve`, add `network_deps` |
| `.agents/agy.json` | Add `headless_contract`, `harness`, `model` fields |
| `.agents/claude.json` | Add `harness`, `model` fields |
| `.agents/codex.json` | Add `harness`, `model` fields |
| `.synlynk/config.json` | Add `agents.{name}.stall_timeout_minutes` per-agent config |

---

## Phase 1: v0.10.1 — LIVE-1 Fixes

---

### Task 1: story-bs14-grok-flags
**Owner: Grok**

Fix the two LIVE-1 Grok failures: `--always-approve` flag contamination and missing network preflight for `cli-chat-proxy.grok.com`.

**Files:**
- Modify: `synlynk/__init__.py` — `AGENT_CAPABILITY_BASELINES["grok"]`
- Modify: `.agents/grok.json`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_synlynk.py
def test_grok_baseline_excludes_always_approve():
    from synlynk import AGENT_CAPABILITY_BASELINES
    grok = AGENT_CAPABILITY_BASELINES.get("grok", {})
    flags = grok.get("dispatch_flags", {})
    invalid = flags.get("invalid_flags", [])
    assert "--always-approve" in invalid, "LIVE-1: --always-approve must be in invalid_flags"
    assert "--always-approve" not in flags.get("valid_flags", [])

def test_grok_baseline_has_network_deps():
    from synlynk import AGENT_CAPABILITY_BASELINES
    grok = AGENT_CAPABILITY_BASELINES.get("grok", {})
    endpoints = grok.get("network_deps", {}).get("required_endpoints", [])
    assert any("cli-chat-proxy.grok.com" in e for e in endpoints)
```

- [ ] **Step 2: Run to confirm failure**

```bash
cd /Users/nikhilsoman/dev/synlynk
python -m pytest tests/test_synlynk.py::test_grok_baseline_excludes_always_approve tests/test_synlynk.py::test_grok_baseline_has_network_deps -v
```
Expected: FAIL — `AGENT_CAPABILITY_BASELINES` missing `invalid_flags` and `network_deps`.

- [ ] **Step 3: Fix `AGENT_CAPABILITY_BASELINES["grok"]` in `synlynk/__init__.py`**

Find `AGENT_CAPABILITY_BASELINES` dict and update the `"grok"` entry:

```python
"grok": {
    "dispatch_flags": {
        "valid_flags": ["--prompt", "--yes", "--model"],
        "invalid_flags": ["--always-approve", "--dangerously-skip-permissions", "--print"],
        "required_flags": ["--yes"],
    },
    "headless_contract": {
        "requires_pty": False,
        "stdout_flush_method": "native",
        "env_vars_required": [],
        "non_interactive_flag": "--yes",
    },
    "network_deps": {
        "required_endpoints": ["cli-chat-proxy.grok.com:443"],
        "optional_endpoints": [],
    },
},
```

- [ ] **Step 4: Update `.agents/grok.json`**

```json
{
  "agent": "grok",
  "harness": "grok",
  "model": "grok-3",
  "dispatch_flags": ["--yes", "--model", "grok-3"],
  "network_deps": {
    "required_endpoints": ["cli-chat-proxy.grok.com:443"]
  }
}
```

- [ ] **Step 5: Run tests to confirm pass**

```bash
python -m pytest tests/test_synlynk.py::test_grok_baseline_excludes_always_approve tests/test_synlynk.py::test_grok_baseline_has_network_deps -v
```
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py .agents/grok.json tests/test_synlynk.py
git commit -m "fix(bs14): remove --always-approve from Grok baseline, add network_deps"
```

---

### Task 2: story-bs14-agy-contract
**Owner: Agy**

Encode the Agy headless execution contract: pipe mode with `PYTHONUNBUFFERED=1`, PTY fallback if stdout hangs.

**Files:**
- Modify: `synlynk/__init__.py` — `AGENT_CAPABILITY_BASELINES["agy"]`, `dispatch_agent()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_agy_baseline_has_headless_contract():
    from synlynk import AGENT_CAPABILITY_BASELINES
    agy = AGENT_CAPABILITY_BASELINES.get("agy", {})
    contract = agy.get("headless_contract", {})
    assert contract.get("requires_pty") is False
    assert contract.get("stdout_flush_method") == "unbuffered"
    assert "PYTHONUNBUFFERED=1" in contract.get("env_vars_required", [])

def test_agy_dispatch_injects_pythonunbuffered(tmp_path, monkeypatch):
    # Stub agy CLI that prints its environment
    stub = tmp_path / "agy"
    stub.write_text("#!/bin/sh\nenv | grep PYTHONUNBUFFERED\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    captured_env = {}
    original_popen = subprocess.Popen
    def mock_popen(cmd, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        return original_popen(cmd, **kwargs)
    monkeypatch.setattr(subprocess, "Popen", mock_popen)
    # call dispatch_agent for agy with a minimal task
    # ... (set up minimal state, call dispatch_agent("agy", "echo test", tmp_path))
    assert "PYTHONUNBUFFERED" in captured_env
    assert captured_env["PYTHONUNBUFFERED"] == "1"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_synlynk.py::test_agy_baseline_has_headless_contract tests/test_synlynk.py::test_agy_dispatch_injects_pythonunbuffered -v
```
Expected: FAIL

- [ ] **Step 3: Update `AGENT_CAPABILITY_BASELINES["agy"]`**

```python
"agy": {
    "dispatch_flags": {
        "valid_flags": ["--prompt", "--non-interactive", "--model", "--output-format"],
        "invalid_flags": ["--always-approve", "--dangerously-skip-permissions", "--print"],
        "required_flags": ["--non-interactive"],
    },
    "headless_contract": {
        "requires_pty": False,
        "stdout_flush_method": "unbuffered",
        "env_vars_required": ["PYTHONUNBUFFERED=1"],
        "non_interactive_flag": "--non-interactive",
    },
    "network_deps": {
        "required_endpoints": ["generativelanguage.googleapis.com:443", "oauth2.googleapis.com:443"],
        "optional_endpoints": [],
    },
},
```

- [ ] **Step 4: In `dispatch_agent()`, inject env vars from headless contract**

Find the `subprocess.Popen(...)` call in `dispatch_agent()`. Before it, build the env:

```python
baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
contract = baseline.get("headless_contract", {})
env = os.environ.copy()
for var in contract.get("env_vars_required", []):
    if "=" in var:
        k, v = var.split("=", 1)
        env[k] = v
# pass env= to Popen
```

- [ ] **Step 5: Add PTY fallback wrapper**

After the pipe-mode Popen, if stdout produces no bytes within 5 seconds on a smoke-test path, retry with PTY:

```python
import sys
def _spawn_with_pty_fallback(cmd, env, cwd):
    """Try pipe mode first; fall back to PTY if stdout hangs (POSIX only)."""
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            env=env, cwd=cwd)
    try:
        out, _ = proc.communicate(timeout=5)
        if out:
            return proc, out
    except subprocess.TimeoutExpired:
        proc.kill()
    # PTY fallback (POSIX only)
    if sys.platform != "win32":
        import pty, os as _os
        master_fd, slave_fd = pty.openpty()
        proc = subprocess.Popen(cmd, stdout=slave_fd, stderr=slave_fd,
                                stdin=slave_fd, env=env, cwd=cwd,
                                close_fds=True)
        _os.close(slave_fd)
        return proc, b""
    raise RuntimeError("stdout hang in pipe mode and PTY unavailable on this platform")
```

- [ ] **Step 6: Update `.agents/agy.json`**

```json
{
  "agent": "agy",
  "harness": "agy",
  "model": "gemini-2.5-pro",
  "dispatch_flags": ["--non-interactive", "--model", "gemini-2.5-pro"],
  "headless_contract": {
    "requires_pty": false,
    "stdout_flush_method": "unbuffered",
    "env_vars_required": ["PYTHONUNBUFFERED=1"],
    "non_interactive_flag": "--non-interactive"
  }
}
```

- [ ] **Step 7: Run tests**

```bash
python -m pytest tests/test_synlynk.py::test_agy_baseline_has_headless_contract tests/test_synlynk.py::test_agy_dispatch_injects_pythonunbuffered -v
```
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add synlynk/__init__.py .agents/agy.json tests/test_synlynk.py
git commit -m "fix(bs14): encode Agy headless contract — PYTHONUNBUFFERED + PTY fallback"
```

---

### Task 3: story-bs14-sentinel-stall
**Owner: Agy**

Add `STALL_NO_OUTPUT` sentinel pattern. Replace the existing global `check_stall()` logic with a per-job log-byte check inside `_reconcile_jobs()`. Make timeout configurable per agent.

**Files:**
- Modify: `synlynk/__init__.py` — `_reconcile_jobs()`, `load_config()`
- Modify: `.synlynk/config.json` defaults
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_reconcile_detects_stall_and_kills_process(tmp_path, monkeypatch):
    import signal, time
    from synlynk import _reconcile_jobs, _load_config

    # Create a fake job: running, started 2h ago, log file is 0 bytes
    job_id = "job-stall-test"
    jobs_dir = tmp_path / ".synlynk" / "jobs"
    jobs_dir.mkdir(parents=True)
    log_file = jobs_dir / f"{job_id}.log"
    log_file.write_bytes(b"")  # 0 bytes

    import json, time as _time
    state = {
        "id": job_id, "agent": "agy", "status": "running",
        "pid": 99999,  # non-existent PID
        "started_at": _time.time() - 7200,  # 2h ago
        "log_file": str(log_file),
    }
    state_file = jobs_dir / f"{job_id}.json"
    state_file.write_text(json.dumps(state))

    config = {"agents": {"agy": {"stall_timeout_minutes": 30}}}
    sentinel_path = tmp_path / "sentinel.md"

    killed = []
    def mock_kill(pid, sig):
        killed.append((pid, sig))
    monkeypatch.setattr(os, "kill", mock_kill)

    _reconcile_jobs(str(jobs_dir), config, str(sentinel_path))

    updated = json.loads(state_file.read_text())
    assert updated["status"] == "failed"
    assert len(killed) > 0
    assert "STALL_NO_OUTPUT" in sentinel_path.read_text()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_synlynk.py::test_reconcile_detects_stall_and_kills_process -v
```
Expected: FAIL

- [ ] **Step 3: Add per-agent stall timeout to `load_config()` defaults**

```python
DEFAULT_CONFIG = {
    ...
    "agents": {},  # per-agent overrides, e.g. {"agy": {"stall_timeout_minutes": 45}}
    "stall_timeout_minutes": 30,  # global default
}
```

- [ ] **Step 4: Implement per-job stall detection in `_reconcile_jobs()`**

Replace or extend the existing stall check:

```python
def _check_job_stall(job: dict, config: dict, sentinel_path: str) -> bool:
    """Returns True if job was stalled and killed."""
    if job.get("status") != "running":
        return False
    log_file = job.get("log_file", "")
    if not log_file or not os.path.exists(log_file):
        return False
    if os.path.getsize(log_file) > 0:
        return False  # has output, not stalled

    agent = job.get("agent", "")
    global_timeout = config.get("stall_timeout_minutes", 30)
    timeout = config.get("agents", {}).get(agent, {}).get("stall_timeout_minutes", global_timeout)
    elapsed_minutes = (time.time() - job.get("started_at", time.time())) / 60

    if elapsed_minutes < timeout:
        return False

    # Kill the process
    pid = job.get("pid")
    if pid:
        try:
            os.kill(pid, signal.SIGKILL)
        except ProcessLookupError:
            pass

    job["status"] = "failed"
    job["exit_code"] = -1
    job["ended_at"] = time.time()

    # Write sentinel alert
    _write_sentinel_alert(
        "CRITICAL", "STALL_NO_OUTPUT",
        f"Job {job['id']} on agent '{agent}' stalled with zero output after {timeout}min. Process killed.",
        sentinel_path,
    )
    return True
```

- [ ] **Step 5: Run test**

```bash
python -m pytest tests/test_synlynk.py::test_reconcile_detects_stall_and_kills_process -v
```
Expected: PASS

- [ ] **Step 6: Run full test suite to check no regressions**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```
Expected: all passing

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_synlynk.py
git commit -m "feat(bs14): STALL_NO_OUTPUT sentinel — per-job stall detection with configurable timeout"
```

---

### Task 4: story-bs14-preflight
**Owner: Codex**

Add dispatch preflight: version staleness check, flag validation, and network reachability check. Block dispatch and fire sentinel on any failure. Do NOT wire the hard block until Phase 2 schema is in place — for v0.10.1, preflight runs but falls back to baseline data from `AGENT_CAPABILITY_BASELINES`.

**Files:**
- Modify: `synlynk/__init__.py` — new `_preflight_dispatch()`, called from `dispatch_agent()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_preflight_blocks_invalid_flag(tmp_path):
    from synlynk import _preflight_dispatch, AGENT_CAPABILITY_BASELINES
    result = _preflight_dispatch(
        agent_name="grok",
        dispatch_flags=["--always-approve"],  # invalid flag
        db_conn=None,  # v0.10.1: no DB yet, falls back to baseline
    )
    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "--always-approve" in result["reason"]

def test_preflight_blocks_unreachable_endpoint(tmp_path, monkeypatch):
    import socket
    def mock_connect(self, addr):
        raise ConnectionRefusedError("unreachable")
    monkeypatch.setattr(socket.socket, "connect", mock_connect)

    from synlynk import _preflight_dispatch
    result = _preflight_dispatch(
        agent_name="grok",
        dispatch_flags=["--yes"],
        db_conn=None,
    )
    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "cli-chat-proxy.grok.com" in result["reason"]

def test_preflight_passes_for_valid_claude_dispatch():
    from synlynk import _preflight_dispatch
    result = _preflight_dispatch(
        agent_name="claude",
        dispatch_flags=["--print", "--dangerously-skip-permissions"],
        db_conn=None,
    )
    assert result["passed"] is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_synlynk.py::test_preflight_blocks_invalid_flag tests/test_synlynk.py::test_preflight_blocks_unreachable_endpoint tests/test_synlynk.py::test_preflight_passes_for_valid_claude_dispatch -v
```
Expected: FAIL — `_preflight_dispatch` not defined

- [ ] **Step 3: Implement `_preflight_dispatch()`**

```python
import socket as _socket
import hashlib

def _preflight_dispatch(agent_name: str, dispatch_flags: list, db_conn=None) -> dict:
    """
    Fast preflight guard before every dispatch.
    Falls back to AGENT_CAPABILITY_BASELINES when harness_records not yet available (v0.10.1).
    Returns: {"passed": bool, "sentinel": str|None, "reason": str|None}
    """
    # Resolve baseline: prefer live DB record, fallback to hardcoded baseline
    baseline = {}
    if db_conn:
        row = db_conn.execute(
            "SELECT active_flags, active_contract FROM harness_records WHERE agent_name=?",
            (agent_name,)
        ).fetchone()
        if row:
            import json
            baseline["dispatch_flags"] = json.loads(row[0])
            baseline["headless_contract"] = json.loads(row[1])
    if not baseline:
        baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})

    flags_spec = baseline.get("dispatch_flags", {})
    invalid_flags = set(flags_spec.get("invalid_flags", []))
    valid_flags = set(flags_spec.get("valid_flags", []))

    # Check 1: flag validation
    for flag in dispatch_flags:
        f = flag.split("=")[0]  # strip =value
        if f in invalid_flags:
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Flag {f!r} is invalid for agent '{agent_name}' (LIVE-1 class error)",
            }

    # Check 2: network reachability
    required = baseline.get("network_deps", {}).get("required_endpoints", [])
    for endpoint in required:
        host, _, port_str = endpoint.rpartition(":")
        port = int(port_str) if port_str.isdigit() else 443
        try:
            s = _socket.socket(_socket.AF_INET, _socket.SOCK_STREAM)
            s.settimeout(2.0)
            s.connect((host, port))
            s.close()
        except (OSError, ConnectionRefusedError, _socket.timeout):
            return {
                "passed": False,
                "sentinel": "HARNESS_PREFLIGHT_FAIL",
                "reason": f"Required endpoint {endpoint!r} unreachable for agent '{agent_name}'",
            }

    return {"passed": True, "sentinel": None, "reason": None}
```

- [ ] **Step 4: Wire `_preflight_dispatch()` into `dispatch_agent()`**

At the top of `dispatch_agent()`, before spawning the subprocess:

```python
preflight = _preflight_dispatch(agent_name=agent_name, dispatch_flags=cmd_flags, db_conn=None)
if not preflight["passed"]:
    _write_sentinel_alert("CRITICAL", preflight["sentinel"], preflight["reason"], sentinel_path)
    raise RuntimeError(f"Dispatch blocked — preflight failed: {preflight['reason']}")
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py::test_preflight_blocks_invalid_flag tests/test_synlynk.py::test_preflight_blocks_unreachable_endpoint tests/test_synlynk.py::test_preflight_passes_for_valid_claude_dispatch -v
```
Expected: PASS

- [ ] **Step 6: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_synlynk.py
git commit -m "feat(bs14): dispatch preflight — flag validation + network check + HARNESS_PREFLIGHT_FAIL sentinel"
```

---

## Phase 2: v0.11.0 — Full System

---

### Task 5: story-bs14-schema
**Owner: Codex**

Add five new tables to `state.db` via `_migrate_db()`. Seed curated baseline rows from `AGENT_CAPABILITY_BASELINES`.

**Files:**
- Modify: `synlynk/__init__.py` — `_migrate_db()`
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_bs14_schema_tables_exist(tmp_path):
    import sqlite3
    from synlynk import _migrate_db
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
    for t in ["harness_baselines", "harness_records", "harness_verb_map",
              "harness_command_palette", "harness_version_history"]:
        assert t in tables, f"Missing table: {t}"
    conn.close()

def test_bs14_schema_migration_is_idempotent(tmp_path):
    import sqlite3
    from synlynk import _migrate_db
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    _migrate_db(conn)  # second run must not raise
    conn.close()

def test_bs14_baseline_seeded_for_known_agents(tmp_path):
    import sqlite3, json
    from synlynk import _migrate_db
    db_path = tmp_path / "state.db"
    conn = sqlite3.connect(str(db_path))
    _migrate_db(conn)
    rows = conn.execute("SELECT harness_name FROM harness_baselines").fetchall()
    harnesses = {r[0] for r in rows}
    for h in ["claude-cli", "agy", "grok", "codex"]:
        assert h in harnesses, f"Missing baseline for harness: {h}"
    conn.close()
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_synlynk.py::test_bs14_schema_tables_exist tests/test_synlynk.py::test_bs14_schema_migration_is_idempotent tests/test_synlynk.py::test_bs14_baseline_seeded_for_known_agents -v
```
Expected: FAIL

- [ ] **Step 3: Add tables to `_migrate_db()`**

Append inside `_migrate_db(conn)`:

```python
conn.executescript("""
    CREATE TABLE IF NOT EXISTS harness_baselines (
        harness_name TEXT NOT NULL,
        cli_version TEXT NOT NULL DEFAULT 'any',
        headless_contract TEXT NOT NULL DEFAULT '{}',
        dispatch_flags TEXT NOT NULL DEFAULT '{}',
        network_deps TEXT NOT NULL DEFAULT '{}',
        baseline_source TEXT NOT NULL DEFAULT 'curated',
        PRIMARY KEY (harness_name, cli_version)
    );

    CREATE TABLE IF NOT EXISTS harness_records (
        agent_name TEXT PRIMARY KEY,
        harness_name TEXT NOT NULL,
        installed_version TEXT NOT NULL DEFAULT 'unknown',
        compliance_status TEXT NOT NULL DEFAULT 'unknown',
        active_contract TEXT NOT NULL DEFAULT '{}',
        active_flags TEXT NOT NULL DEFAULT '{}',
        last_probe_at TEXT,
        capability_hash TEXT NOT NULL DEFAULT ''
    );

    CREATE TABLE IF NOT EXISTS harness_verb_map (
        synlynk_verb TEXT NOT NULL,
        verb_category TEXT NOT NULL,
        agent_name TEXT NOT NULL,
        agent_command TEXT,
        supported TEXT NOT NULL DEFAULT 'none',
        partial_notes TEXT,
        min_cli_version TEXT,
        PRIMARY KEY (synlynk_verb, agent_name)
    );

    CREATE TABLE IF NOT EXISTS harness_command_palette (
        harness_name TEXT NOT NULL,
        cli_version TEXT NOT NULL,
        command TEXT NOT NULL,
        command_type TEXT NOT NULL,
        synlynk_verb TEXT,
        help_text TEXT,
        first_seen_version TEXT NOT NULL,
        last_seen_version TEXT,
        PRIMARY KEY (harness_name, cli_version, command)
    );

    CREATE TABLE IF NOT EXISTS harness_version_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        agent_name TEXT NOT NULL,
        cli_version TEXT NOT NULL,
        event_type TEXT NOT NULL,
        prev_hash TEXT,
        new_hash TEXT,
        recorded_at TEXT NOT NULL
    );
""")
```

- [ ] **Step 4: Seed baselines from `AGENT_CAPABILITY_BASELINES`**

After the schema creation, add a seeding block:

```python
import json as _json
_HARNESS_MAP = {"claude": "claude-cli", "agy": "agy", "grok": "grok", "codex": "codex"}
for agent_name, baseline in AGENT_CAPABILITY_BASELINES.items():
    harness_name = _HARNESS_MAP.get(agent_name, agent_name)
    conn.execute("""
        INSERT OR IGNORE INTO harness_baselines
            (harness_name, cli_version, headless_contract, dispatch_flags, network_deps, baseline_source)
        VALUES (?, 'any', ?, ?, ?, 'curated')
    """, (
        harness_name,
        _json.dumps(baseline.get("headless_contract", {})),
        _json.dumps(baseline.get("dispatch_flags", {})),
        _json.dumps(baseline.get("network_deps", {})),
    ))
conn.commit()
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_synlynk.py::test_bs14_schema_tables_exist tests/test_synlynk.py::test_bs14_schema_migration_is_idempotent tests/test_synlynk.py::test_bs14_baseline_seeded_for_known_agents -v
```
Expected: PASS

- [ ] **Step 6: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_synlynk.py
git commit -m "feat(bs14): add five harness compatibility tables to state.db + seed curated baselines"
```

---

### Task 6: story-bs14-agent-json
**Owner: Codex**

Add `harness` and `model` fields to `.agents/<agent>.json` schema. Update all loader/writer paths.

**Files:**
- Modify: `synlynk/__init__.py` — `_load_agent_profile()`, `discover_agents()`, `cmd_agent_configure()`
- Modify: `.agents/claude.json`, `.agents/codex.json` (agy + grok done in Phase 1)
- Test: `tests/test_synlynk.py`

- [ ] **Step 1: Write the failing test**

```python
def test_agent_json_roundtrips_harness_and_model(tmp_path):
    import json
    from synlynk import _load_agent_profile

    agents_dir = tmp_path / ".agents"
    agents_dir.mkdir()
    (agents_dir / "claude.json").write_text(json.dumps({
        "agent": "claude", "harness": "claude-cli", "model": "claude-sonnet-4-6",
        "dispatch_flags": ["--print", "--dangerously-skip-permissions"]
    }))

    profile = _load_agent_profile("claude", str(agents_dir))
    assert profile["harness"] == "claude-cli"
    assert profile["model"] == "claude-sonnet-4-6"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_synlynk.py::test_agent_json_roundtrips_harness_and_model -v
```
Expected: FAIL — `_load_agent_profile` doesn't return `harness`/`model`

- [ ] **Step 3: Update `_load_agent_profile()` to pass through `harness` and `model`**

```python
def _load_agent_profile(agent_name: str, agents_dir: str = ".agents") -> dict:
    path = os.path.join(agents_dir, f"{agent_name}.json")
    if not os.path.exists(path):
        return {"agent": agent_name, "harness": agent_name, "model": "unknown"}
    with open(path) as f:
        profile = json.load(f)
    profile.setdefault("harness", agent_name)
    profile.setdefault("model", "unknown")
    return profile
```

- [ ] **Step 4: Update `.agents/claude.json` and `.agents/codex.json`**

`.agents/claude.json`:
```json
{
  "agent": "claude",
  "harness": "claude-cli",
  "model": "claude-sonnet-4-6",
  "dispatch_flags": ["--print", "--dangerously-skip-permissions"]
}
```

`.agents/codex.json`:
```json
{
  "agent": "codex",
  "harness": "codex",
  "model": "o4-mini",
  "dispatch_flags": ["--quiet", "--approval-policy=auto-edit"]
}
```

- [ ] **Step 5: Run tests and full suite**

```bash
python -m pytest tests/test_synlynk.py::test_agent_json_roundtrips_harness_and_model -v
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py .agents/claude.json .agents/codex.json tests/test_synlynk.py
git commit -m "feat(bs14): add harness + model fields to .agents/<agent>.json schema"
```

---

### Task 7: story-bs14-probe
**Owner: Codex**

Implement `synlynk probe` command: version fingerprint → baseline lookup → dynamic discovery fallback → network preflight → write `harness_records` + `harness_version_history` → rewrite fences.

**Files:**
- Modify: `synlynk/__init__.py` — new `cmd_probe()`, `_probe_agent()`, `_compute_capability_hash()`
- Test: `tests/test_synlynk.py`, `tests/test_harness_compatibility.py`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_harness_compatibility.py
import os, json, sqlite3, subprocess, pytest

def _make_stub_cli(tmp_path, name, version="1.0.0", help_text="--flag1  A flag\n--flag2  Another\n"):
    stub = tmp_path / name
    stub.write_text(f"""#!/bin/sh
case "$1" in
  --version) echo "{name} {version}"; exit 0 ;;
  --help)    echo "{help_text}"; exit 0 ;;
  *)         echo "stub output"; exit 0 ;;
esac
""")
    stub.chmod(0o755)
    return stub

def test_probe_fastpath_skips_deep_probe_when_hash_matches(tmp_path, monkeypatch):
    from synlynk import _probe_agent, _compute_capability_hash, AGENT_CAPABILITY_BASELINES
    _make_stub_cli(tmp_path, "agy", version="1.0.0")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    db = sqlite3.connect(":memory:")
    from synlynk import _migrate_db
    _migrate_db(db)

    # Pre-populate harness_records with matching hash
    baseline = AGENT_CAPABILITY_BASELINES.get("agy", {})
    h = _compute_capability_hash(baseline.get("headless_contract", {}), baseline.get("dispatch_flags", {}))
    db.execute("""
        INSERT INTO harness_records (agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at)
        VALUES ('agy','agy','1.0.0','ok','{}','{}',?,datetime('now'))
    """, (h,))
    db.commit()

    result = _probe_agent("agy", db, fast_path_ok=True)
    assert result["skipped"] is True  # fast path triggered

def test_probe_writes_harness_records_on_new_version(tmp_path, monkeypatch):
    from synlynk import _probe_agent
    _make_stub_cli(tmp_path, "agy", version="2.0.0")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    db = sqlite3.connect(":memory:")
    from synlynk import _migrate_db
    _migrate_db(db)

    result = _probe_agent("agy", db, fast_path_ok=True)
    row = db.execute("SELECT installed_version FROM harness_records WHERE agent_name='agy'").fetchone()
    assert row and row[0] == "2.0.0"
    assert result["skipped"] is False

def test_probe_appends_history_on_version_change(tmp_path, monkeypatch):
    from synlynk import _probe_agent
    _make_stub_cli(tmp_path, "agy", version="2.0.0")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    db = sqlite3.connect(":memory:")
    from synlynk import _migrate_db
    _migrate_db(db)
    db.execute("""
        INSERT INTO harness_records (agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at)
        VALUES ('agy','agy','1.0.0','ok','{}','{}','oldhash',datetime('now'))
    """)
    db.commit()

    _probe_agent("agy", db, fast_path_ok=True)
    history = db.execute("SELECT event_type FROM harness_version_history WHERE agent_name='agy'").fetchall()
    assert any(r[0] == "version_change" for r in history)
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_harness_compatibility.py -v
```
Expected: FAIL — `_probe_agent`, `_compute_capability_hash` not defined

- [ ] **Step 3: Implement `_compute_capability_hash()`**

```python
import hashlib, json as _json

def _compute_capability_hash(headless_contract: dict, dispatch_flags: dict) -> str:
    payload = _json.dumps({"contract": headless_contract, "flags": dispatch_flags}, sort_keys=True)
    return hashlib.sha256(payload.encode()).hexdigest()[:16]
```

- [ ] **Step 4: Implement `_probe_agent()`**

```python
import subprocess, time as _time

def _probe_agent(agent_name: str, db_conn, fast_path_ok: bool = True) -> dict:
    """
    Probe one agent. Returns {"skipped": bool, "version": str, "status": str}.
    """
    import json as _json
    harness_map = {"claude": "claude-cli", "agy": "agy", "grok": "grok", "codex": "codex"}
    harness_name = harness_map.get(agent_name, agent_name)
    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})

    # Step 1: version fingerprint
    try:
        result = subprocess.run([agent_name, "--version"], capture_output=True, text=True, timeout=5)
        installed_version = result.stdout.strip().split()[-1] if result.stdout.strip() else "unknown"
    except (FileNotFoundError, subprocess.TimeoutExpired):
        installed_version = "unavailable"

    # Step 2: fast path check
    if fast_path_ok:
        row = db_conn.execute(
            "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
            (agent_name,)
        ).fetchone()
        if row and row[0] == installed_version:
            new_hash = _compute_capability_hash(
                baseline.get("headless_contract", {}),
                baseline.get("dispatch_flags", {}),
            )
            if row[1] == new_hash:
                return {"skipped": True, "version": installed_version, "status": "ok"}

    # Step 3: full probe — use curated baseline (dynamic discovery in doctor/TC-1)
    contract = baseline.get("headless_contract", {})
    flags = baseline.get("dispatch_flags", {})
    new_hash = _compute_capability_hash(contract, flags)

    # Step 4: network preflight
    network_ok = True
    for endpoint in baseline.get("network_deps", {}).get("required_endpoints", []):
        import socket as _sock
        host, _, port_s = endpoint.rpartition(":")
        try:
            s = _sock.create_connection((host, int(port_s or 443)), timeout=2)
            s.close()
        except OSError:
            network_ok = False

    compliance = "ok" if network_ok else "degraded"

    # Step 5: detect version change before upsert
    prev_row = db_conn.execute(
        "SELECT installed_version, capability_hash FROM harness_records WHERE agent_name=?",
        (agent_name,)
    ).fetchone()

    now = _time.strftime("%Y-%m-%dT%H:%M:%SZ", _time.gmtime())
    event_type = None
    if prev_row:
        if prev_row[0] != installed_version:
            event_type = "version_change"
        elif prev_row[1] != new_hash:
            event_type = "drift_detected"
    
    # Step 6: upsert harness_records
    db_conn.execute("""
        INSERT INTO harness_records
            (agent_name, harness_name, installed_version, compliance_status, active_contract, active_flags, capability_hash, last_probe_at)
        VALUES (?,?,?,?,?,?,?,?)
        ON CONFLICT(agent_name) DO UPDATE SET
            harness_name=excluded.harness_name,
            installed_version=excluded.installed_version,
            compliance_status=excluded.compliance_status,
            active_contract=excluded.active_contract,
            active_flags=excluded.active_flags,
            capability_hash=excluded.capability_hash,
            last_probe_at=excluded.last_probe_at
    """, (agent_name, harness_name, installed_version, compliance,
          _json.dumps(contract), _json.dumps(flags), new_hash, now))

    if event_type:
        db_conn.execute("""
            INSERT INTO harness_version_history (agent_name, cli_version, event_type, prev_hash, new_hash, recorded_at)
            VALUES (?,?,?,?,?,?)
        """, (agent_name, installed_version, event_type,
              prev_row[1] if prev_row else None, new_hash, now))

    db_conn.commit()
    return {"skipped": False, "version": installed_version, "status": compliance}
```

- [ ] **Step 5: Add `cmd_probe()` entrypoint**

```python
def cmd_probe(args):
    agents = [args.agent] if getattr(args, "agent", None) else list(AGENT_CAPABILITY_BASELINES.keys())
    db_conn = _get_db_connection()
    for agent in agents:
        result = _probe_agent(agent, db_conn)
        status = "skipped (up to date)" if result["skipped"] else result["status"]
        print(f"  probe [{agent}] {result['version']} → {status}")
```

Wire into `main()` argument parser under subcommand `probe`.

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_harness_compatibility.py -v
```
Expected: PASS

- [ ] **Step 7: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/__init__.py tests/test_harness_compatibility.py
git commit -m "feat(bs14): implement synlynk probe — version fingerprint, baseline lookup, harness_records upsert"
```

---

### Task 8: story-bs14-doctor
**Owner: Codex** (Agy validates agy branch, Grok validates grok branch)

Extend `cmd_doctor()` with TC-1 through TC-4 compliance checks. Update `harness_records`, fire sentinels, append history on failures.

**Files:**
- Modify: `synlynk/__init__.py` — `cmd_doctor()`, new `_run_tc1()` through `_run_tc4()`
- Test: `tests/test_harness_compatibility.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_tc1_detects_pipe_hang_and_records_pty_required(tmp_path, monkeypatch):
    """Stub CLI that never flushes stdout in pipe mode."""
    stub = tmp_path / "agy"
    stub.write_text("#!/bin/sh\nsleep 30\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    from synlynk import _run_tc1
    result = _run_tc1("agy", timeout=1)
    assert result["requires_pty"] is True
    assert result["passed"] is False  # pipe mode failed

def test_tc2_flags_invalid_flag_as_noncompliant(tmp_path, monkeypatch):
    stub = _make_stub_cli(tmp_path, "grok")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    from synlynk import _run_tc2, AGENT_CAPABILITY_BASELINES
    # inject a bad flag into baseline for test
    test_flags = {"valid_flags": ["--yes"], "invalid_flags": ["--always-approve"]}
    result = _run_tc2("grok", test_flags)
    assert "--always-approve" in result["failed_flags"]

def test_tc3_marks_unreachable_endpoint(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "create_connection", lambda *a, **kw: (_ for _ in ()).throw(OSError("refused")))
    from synlynk import _run_tc3
    result = _run_tc3([("cli-chat-proxy.grok.com", 443)])
    assert result["reachable"] == []
    assert ("cli-chat-proxy.grok.com", 443) in result["unreachable"]
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_harness_compatibility.py::test_tc1_detects_pipe_hang_and_records_pty_required tests/test_harness_compatibility.py::test_tc2_flags_invalid_flag_as_noncompliant tests/test_harness_compatibility.py::test_tc3_marks_unreachable_endpoint -v
```
Expected: FAIL

- [ ] **Step 3: Implement TC-1 through TC-4**

```python
def _run_tc1(agent_name: str, timeout: int = 5) -> dict:
    """TC-1: Headless stdout contract. Returns {"requires_pty": bool, "passed": bool}."""
    import sys
    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    contract = baseline.get("headless_contract", {})
    non_interactive_flag = contract.get("non_interactive_flag", "--non-interactive")
    env = os.environ.copy()
    for var in contract.get("env_vars_required", []):
        if "=" in var:
            k, v = var.split("=", 1)
            env[k] = v
    try:
        proc = subprocess.Popen(
            [agent_name, non_interactive_flag, "--version"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env,
        )
        out, _ = proc.communicate(timeout=timeout)
        return {"requires_pty": False, "passed": True, "stdout_method": "pipe"}
    except subprocess.TimeoutExpired:
        proc.kill()
        # PTY fallback check
        if sys.platform != "win32":
            return {"requires_pty": True, "passed": False, "stdout_method": "pty"}
        return {"requires_pty": False, "passed": False, "stdout_method": "unavailable"}

def _run_tc2(agent_name: str, flags_spec: dict) -> dict:
    """TC-2: Flag compliance. Returns {"failed_flags": list, "passed": bool}."""
    failed = []
    for flag in flags_spec.get("invalid_flags", []):
        failed.append(flag)  # invalid flags are known-bad by definition; trust the baseline
    # For unknown flags, attempt --help and grep:
    try:
        result = subprocess.run([agent_name, "--help"], capture_output=True, text=True, timeout=5)
        help_text = result.stdout + result.stderr
        for flag in flags_spec.get("valid_flags", []):
            f = flag.lstrip("-")
            if f and f not in help_text and flag not in help_text:
                failed.append(flag)
    except (FileNotFoundError, subprocess.TimeoutExpired):
        pass
    return {"failed_flags": failed, "passed": len(failed) == 0}

def _run_tc3(endpoints: list) -> dict:
    """TC-3: Network dependency. Returns {"reachable": list, "unreachable": list}."""
    import socket as _sock
    reachable, unreachable = [], []
    for host, port in endpoints:
        try:
            s = _sock.create_connection((host, port), timeout=2)
            s.close()
            reachable.append((host, port))
        except OSError:
            unreachable.append((host, port))
    return {"reachable": reachable, "unreachable": unreachable, "passed": len(unreachable) == 0}

def _run_tc4(agent_name: str, db_conn) -> dict:
    """TC-4: Verb map validation. Returns {"failed_verbs": list, "passed": bool}."""
    import json as _json
    failed = []
    rows = db_conn.execute(
        "SELECT synlynk_verb, agent_command, supported FROM harness_verb_map WHERE agent_name=?",
        (agent_name,)
    ).fetchall()
    for verb, cmd_template, supported in rows:
        if supported == "none" or not cmd_template:
            continue
        cmd = cmd_template.split()[0] if cmd_template else agent_name
        try:
            subprocess.run([cmd, "--help"], capture_output=True, timeout=3)
        except (FileNotFoundError, subprocess.TimeoutExpired):
            failed.append(verb)
    return {"failed_verbs": failed, "passed": len(failed) == 0}
```

- [ ] **Step 4: Wire TC-1–TC-4 into `cmd_doctor()`**

```python
def cmd_doctor(args):
    agent_filter = getattr(args, "agent", None)
    db_conn = _get_db_connection()
    agents = [agent_filter] if agent_filter else list(AGENT_CAPABILITY_BASELINES.keys())

    for agent in agents:
        print(f"\n  doctor [{agent}]")
        baseline = AGENT_CAPABILITY_BASELINES.get(agent, {})

        tc1 = _run_tc1(agent)
        tc2 = _run_tc2(agent, baseline.get("dispatch_flags", {}))
        endpoints = [(h.rpartition(":")[0], int(h.rpartition(":")[2] or 443))
                     for h in baseline.get("network_deps", {}).get("required_endpoints", [])]
        tc3 = _run_tc3(endpoints)
        tc4 = _run_tc4(agent, db_conn)

        all_passed = tc1["passed"] and tc2["passed"] and tc3["passed"] and tc4["passed"]
        status = "ok" if all_passed else "degraded"

        # Update harness_records
        import json as _j, time as _t
        db_conn.execute(
            "UPDATE harness_records SET compliance_status=?, last_probe_at=? WHERE agent_name=?",
            (status, _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime()), agent)
        )
        # Append history
        db_conn.execute("""
            INSERT INTO harness_version_history (agent_name, cli_version, event_type, recorded_at)
            VALUES (?, 'unknown', 'doctor_run', ?)
        """, (agent, _t.strftime("%Y-%m-%dT%H:%M:%SZ", _t.gmtime())))
        db_conn.commit()

        print(f"    TC-1 stdout:  {'✓' if tc1['passed'] else '✗ requires_pty=' + str(tc1['requires_pty'])}")
        print(f"    TC-2 flags:   {'✓' if tc2['passed'] else '✗ failed=' + str(tc2['failed_flags'])}")
        print(f"    TC-3 network: {'✓' if tc3['passed'] else '✗ unreachable=' + str(tc3['unreachable'])}")
        print(f"    TC-4 verbs:   {'✓' if tc4['passed'] else '✗ failed=' + str(tc4['failed_verbs'])}")
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_harness_compatibility.py::test_tc1_detects_pipe_hang_and_records_pty_required tests/test_harness_compatibility.py::test_tc2_flags_invalid_flag_as_noncompliant tests/test_harness_compatibility.py::test_tc3_marks_unreachable_endpoint -v
```
Expected: PASS

- [ ] **Step 6: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_harness_compatibility.py
git commit -m "feat(bs14): synlynk doctor compliance suite — TC-1 through TC-4"
```

---

### Task 9: story-bs14-verb-map
**Owner: Agy**

Seed `harness_verb_map` with the full synlynk verb surface across all four harnesses. Wire verb support lookup into dispatch so `partial` warns and `none` blocks.

**Files:**
- Modify: `synlynk/__init__.py` — `_migrate_db()` seeding, `_check_verb_support()`
- Test: `tests/test_harness_compatibility.py`

- [ ] **Step 1: Write the failing test**

```python
def test_verb_map_seeded_for_all_categories(tmp_path):
    import sqlite3
    from synlynk import _migrate_db, _seed_verb_map
    db = sqlite3.connect(":memory:")
    _migrate_db(db)
    _seed_verb_map(db)

    rows = db.execute("SELECT DISTINCT verb_category FROM harness_verb_map").fetchall()
    categories = {r[0] for r in rows}
    for cat in ["dispatch", "observability", "harness", "pm", "workspace"]:
        assert cat in categories, f"Missing verb category: {cat}"

def test_verb_none_blocks_dispatch(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import _migrate_db, _seed_verb_map, _check_verb_support
    db = sqlite3.connect(":memory:")
    _migrate_db(db)
    _seed_verb_map(db)
    result = _check_verb_support("dispatch.approve", "grok", db)
    assert result["supported"] == "none"
    assert result["block"] is True
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_harness_compatibility.py::test_verb_map_seeded_for_all_categories tests/test_harness_compatibility.py::test_verb_none_blocks_dispatch -v
```
Expected: FAIL

- [ ] **Step 3: Implement `_seed_verb_map()`**

```python
_VERB_MAP_SEED = [
    # (synlynk_verb, category, agent, agent_command, supported, partial_notes)
    ("dispatch.task",     "dispatch",      "claude", "claude --print {task} --dangerously-skip-permissions", "full", None),
    ("dispatch.task",     "dispatch",      "agy",    "agy --prompt {task} --non-interactive --model gemini-2.5-pro", "full", None),
    ("dispatch.task",     "dispatch",      "grok",   "grok --prompt {task} --yes --model grok-3", "full", None),
    ("dispatch.task",     "dispatch",      "codex",  "codex --quiet {task} --approval-policy=auto-edit", "full", None),
    ("dispatch.headless", "dispatch",      "claude", "claude --print {task}", "full", None),
    ("dispatch.headless", "dispatch",      "agy",    "agy --non-interactive --prompt {task}", "partial", "May hang without PTY on some agy versions"),
    ("dispatch.headless", "dispatch",      "grok",   "grok --yes --prompt {task}", "partial", "Network dep required"),
    ("dispatch.headless", "dispatch",      "codex",  "codex --quiet {task}", "full", None),
    ("dispatch.resume",   "dispatch",      "claude", "claude --resume {session_id}", "full", None),
    ("dispatch.resume",   "dispatch",      "agy",    None, "none", None),
    ("dispatch.resume",   "dispatch",      "grok",   None, "none", None),
    ("dispatch.resume",   "dispatch",      "codex",  None, "none", None),
    ("dispatch.approve",  "dispatch",      "claude", "claude --allowedTools {tools}", "full", None),
    ("dispatch.approve",  "dispatch",      "agy",    None, "none", None),
    ("dispatch.approve",  "dispatch",      "grok",   None, "none", None),
    ("dispatch.approve",  "dispatch",      "codex",  None, "partial", "approval-policy=none only"),
    ("dispatch.model",    "dispatch",      "claude", "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "agy",    "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "grok",   "--model {model}", "full", None),
    ("dispatch.model",    "dispatch",      "codex",  "--model {model}", "full", None),
    ("dispatch.tools",    "dispatch",      "claude", "--allowedTools {tools}", "full", None),
    ("dispatch.tools",    "dispatch",      "agy",    None, "partial", "No tool_list flag"),
    ("dispatch.tools",    "dispatch",      "grok",   None, "none", None),
    ("dispatch.tools",    "dispatch",      "codex",  None, "partial", "approval-policy only"),
    ("dispatch.context",  "dispatch",      "claude", "claude --print {task}", "full", None),
    ("dispatch.context",  "dispatch",      "agy",    "agy --prompt {task}", "full", None),
    ("dispatch.context",  "dispatch",      "grok",   "grok --prompt {task}", "partial", "No explicit context file flag"),
    ("dispatch.context",  "dispatch",      "codex",  "codex {task}", "full", None),
    ("jobs",              "observability", "claude", None, "partial", "No native jobs subcommand"),
    ("jobs",              "observability", "agy",    None, "none", None),
    ("jobs",              "observability", "grok",   None, "none", None),
    ("jobs",              "observability", "codex",  None, "none", None),
    ("status",            "observability", "claude", None, "partial", None),
    ("status",            "observability", "agy",    None, "none", None),
    ("status",            "observability", "grok",   None, "none", None),
    ("status",            "observability", "codex",  None, "none", None),
    ("telemetry",         "observability", "claude", None, "none", None),
    ("telemetry",         "observability", "agy",    None, "none", None),
    ("telemetry",         "observability", "grok",   None, "none", None),
    ("telemetry",         "observability", "codex",  None, "none", None),
    ("costs",             "observability", "claude", None, "partial", "Token count via /cost"),
    ("costs",             "observability", "agy",    None, "none", None),
    ("costs",             "observability", "grok",   None, "none", None),
    ("costs",             "observability", "codex",  None, "none", None),
    ("probe",             "harness",       "claude", "claude --version", "full", None),
    ("probe",             "harness",       "agy",    "agy --version", "full", None),
    ("probe",             "harness",       "grok",   "grok --version", "full", None),
    ("probe",             "harness",       "codex",  "codex --version", "full", None),
    ("doctor",            "harness",       "claude", None, "full", None),
    ("doctor",            "harness",       "agy",    None, "full", None),
    ("doctor",            "harness",       "grok",   None, "full", None),
    ("doctor",            "harness",       "codex",  None, "full", None),
    ("story",             "pm",            "claude", None, "none", None),
    ("story",             "pm",            "agy",    None, "none", None),
    ("story",             "pm",            "grok",   None, "none", None),
    ("story",             "pm",            "codex",  None, "none", None),
    ("epic",              "pm",            "claude", None, "none", None),
    ("epic",              "pm",            "agy",    None, "none", None),
    ("epic",              "pm",            "grok",   None, "none", None),
    ("epic",              "pm",            "codex",  None, "none", None),
    ("decide",            "pm",            "claude", None, "none", None),
    ("decide",            "pm",            "agy",    None, "none", None),
    ("decide",            "pm",            "grok",   None, "none", None),
    ("decide",            "pm",            "codex",  None, "none", None),
    ("workspace",         "workspace",     "claude", None, "none", None),
    ("workspace",         "workspace",     "agy",    None, "none", None),
    ("workspace",         "workspace",     "grok",   None, "none", None),
    ("workspace",         "workspace",     "codex",  None, "none", None),
    ("upgrade",           "workspace",     "claude", None, "partial", "Via /upgrade slash command"),
    ("upgrade",           "workspace",     "agy",    None, "partial", "Via agy update"),
    ("upgrade",           "workspace",     "grok",   None, "partial", None),
    ("upgrade",           "workspace",     "codex",  None, "partial", None),
]

def _seed_verb_map(db_conn):
    db_conn.executemany("""
        INSERT OR IGNORE INTO harness_verb_map
            (synlynk_verb, verb_category, agent_name, agent_command, supported, partial_notes)
        VALUES (?,?,?,?,?,?)
    """, _VERB_MAP_SEED)
    db_conn.commit()
```

- [ ] **Step 4: Implement `_check_verb_support()`**

```python
def _check_verb_support(verb: str, agent_name: str, db_conn) -> dict:
    row = db_conn.execute(
        "SELECT supported, partial_notes, agent_command FROM harness_verb_map WHERE synlynk_verb=? AND agent_name=?",
        (verb, agent_name)
    ).fetchone()
    if not row:
        return {"supported": "unknown", "block": False, "notes": None, "command": None}
    supported, notes, cmd = row
    return {
        "supported": supported,
        "block": supported == "none",
        "warn": supported == "partial",
        "notes": notes,
        "command": cmd,
    }
```

- [ ] **Step 5: Call `_seed_verb_map()` inside `_migrate_db()`**

At the end of `_migrate_db()`, after schema creation:
```python
_seed_verb_map(conn)
```

- [ ] **Step 6: Run tests and full suite**

```bash
python -m pytest tests/test_harness_compatibility.py::test_verb_map_seeded_for_all_categories tests/test_harness_compatibility.py::test_verb_none_blocks_dispatch -v
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_harness_compatibility.py
git commit -m "feat(bs14): seed harness_verb_map — full synlynk verb surface across all four harnesses"
```

---

### Task 10: story-bs14-palette
**Owner: Codex**

Parse each harness's `--help` tree to populate `harness_command_palette`. Diff on version change; surface unmapped commands in `synlynk doctor --report`.

**Files:**
- Modify: `synlynk/__init__.py` — `_scan_command_palette()`, wired into `_probe_agent()`
- Test: `tests/test_harness_compatibility.py`

- [ ] **Step 1: Write the failing test**

```python
def test_palette_scan_populates_commands(tmp_path, monkeypatch):
    stub = _make_stub_cli(tmp_path, "agy", version="1.0.0",
        help_text="  --non-interactive  Run without prompts\n  --model MODEL  Model to use\n  config set  Set config value\n")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    import sqlite3
    from synlynk import _migrate_db, _scan_command_palette
    db = sqlite3.connect(":memory:")
    _migrate_db(db)

    _scan_command_palette("agy", "agy", "1.0.0", db)

    rows = db.execute("SELECT command FROM harness_command_palette WHERE harness_name='agy'").fetchall()
    commands = {r[0] for r in rows}
    assert "--non-interactive" in commands
    assert "--model" in commands

def test_palette_marks_removed_commands(tmp_path, monkeypatch):
    import sqlite3
    from synlynk import _migrate_db, _scan_command_palette

    db = sqlite3.connect(":memory:")
    _migrate_db(db)

    # First scan: --old-flag present
    stub = _make_stub_cli(tmp_path, "agy", version="1.0.0", help_text="  --old-flag  Old\n")
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])
    _scan_command_palette("agy", "agy", "1.0.0", db)

    # Second scan: --old-flag removed in v2.0.0
    stub.write_text("#!/bin/sh\necho '  --new-flag  New'\n")
    _scan_command_palette("agy", "agy", "2.0.0", db)

    row = db.execute(
        "SELECT last_seen_version FROM harness_command_palette WHERE command='--old-flag' AND harness_name='agy'"
    ).fetchone()
    assert row and row[0] == "1.0.0"
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_harness_compatibility.py::test_palette_scan_populates_commands tests/test_harness_compatibility.py::test_palette_marks_removed_commands -v
```
Expected: FAIL

- [ ] **Step 3: Implement `_scan_command_palette()`**

```python
import re as _re

def _scan_command_palette(agent_name: str, harness_name: str, cli_version: str, db_conn) -> list:
    """Parse --help output and populate harness_command_palette. Returns list of command dicts."""
    try:
        result = subprocess.run([agent_name, "--help"], capture_output=True, text=True, timeout=5)
        help_text = result.stdout + result.stderr
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return []

    found_commands = {}
    for line in help_text.splitlines():
        line = line.strip()
        # Match flags: --flag or --flag VALUE
        flag_match = _re.match(r"^(--[\w-]+(?:=\S+)?)\s+(.*)", line)
        if flag_match:
            cmd, desc = flag_match.group(1).split("=")[0], flag_match.group(2).strip()
            found_commands[cmd] = {"type": "flag", "help": desc}
            continue
        # Match subcommands: "word word  description"
        sub_match = _re.match(r"^([\w][\w\s-]{1,30}?)\s{2,}(.*)", line)
        if sub_match:
            cmd, desc = sub_match.group(1).strip(), sub_match.group(2).strip()
            if cmd and len(cmd.split()) <= 3:
                found_commands[cmd] = {"type": "subcommand", "help": desc}

    now_version = cli_version
    # Mark removed commands from previous scans
    prev_rows = db_conn.execute(
        "SELECT command FROM harness_command_palette WHERE harness_name=? AND last_seen_version IS NULL",
        (harness_name,)
    ).fetchall()
    prev_commands = {r[0] for r in prev_rows}
    removed = prev_commands - set(found_commands.keys())
    for cmd in removed:
        db_conn.execute(
            "UPDATE harness_command_palette SET last_seen_version=? WHERE harness_name=? AND command=? AND last_seen_version IS NULL",
            (cli_version, harness_name, cmd)
        )

    # Insert new commands
    for cmd, meta in found_commands.items():
        db_conn.execute("""
            INSERT OR IGNORE INTO harness_command_palette
                (harness_name, cli_version, command, command_type, help_text, first_seen_version)
            VALUES (?,?,?,?,?,?)
        """, (harness_name, now_version, cmd, meta["type"], meta["help"], now_version))

    db_conn.commit()
    return list(found_commands.keys())
```

- [ ] **Step 4: Wire into `_probe_agent()`**

At Step 7 of `_probe_agent()`, after writing `harness_records`, call:
```python
_scan_command_palette(agent_name, harness_name, installed_version, db_conn)
```

- [ ] **Step 5: Run tests**

```bash
python -m pytest tests/test_harness_compatibility.py::test_palette_scan_populates_commands tests/test_harness_compatibility.py::test_palette_marks_removed_commands -v
```
Expected: PASS

- [ ] **Step 6: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 7: Commit**

```bash
git add synlynk/__init__.py tests/test_harness_compatibility.py
git commit -m "feat(bs14): harness_command_palette scan — --help parser, removal detection, extension opportunity surface"
```

---

### Task 11: story-bs14-fence
**Owner: Agy**

Implement `_upsert_harness_fence()` — idempotent write of the managed `<!-- synlynk:harness -->` section into agent instruction files. Wire into probe and doctor.

**Files:**
- Modify: `synlynk/__init__.py` — `_upsert_harness_fence()`, `_build_fence_content()`
- Test: `tests/test_harness_compatibility.py`, `tests/test_instruction_reach.py`

- [ ] **Step 1: Write the failing tests**

```python
def test_fence_upsert_replaces_existing_fence(tmp_path):
    from synlynk import _upsert_harness_fence
    md = tmp_path / "GEMINI.md"
    md.write_text("# Human content above\n\n<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\nold content\n<!-- /synlynk:harness -->\n\n# Human content below\n")

    _upsert_harness_fence(str(md), "v0.2", "new fence content line")

    text = md.read_text()
    assert "new fence content line" in text
    assert "old content" not in text
    assert "# Human content above" in text
    assert "# Human content below" in text

def test_fence_upsert_appends_when_missing(tmp_path):
    from synlynk import _upsert_harness_fence
    md = tmp_path / "CLAUDE.md"
    md.write_text("# Human only content\n")

    _upsert_harness_fence(str(md), "v0.1", "fence body here")

    text = md.read_text()
    assert "<!-- synlynk:harness" in text
    assert "fence body here" in text
    assert "# Human only content" in text

def test_fence_upsert_skips_missing_file(tmp_path, capsys):
    from synlynk import _upsert_harness_fence
    _upsert_harness_fence(str(tmp_path / "NONEXISTENT.md"), "v0.1", "body")
    captured = capsys.readouterr()
    assert "fence skipped" in captured.out or "fence skipped" in captured.err

def test_fence_preserves_surrounding_bytes(tmp_path):
    from synlynk import _upsert_harness_fence
    before = "# Top\nLine A\nLine B\n"
    after = "\n# Bottom\nLine C\n"
    md = tmp_path / "GEMINI.md"
    md.write_text(before + "<!-- synlynk:harness v0.1 verified:X -->\nOLD\n<!-- /synlynk:harness -->" + after)

    _upsert_harness_fence(str(md), "v0.2", "NEW")

    text = md.read_text()
    assert text.startswith(before)
    assert text.endswith(after)
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_harness_compatibility.py::test_fence_upsert_replaces_existing_fence tests/test_harness_compatibility.py::test_fence_upsert_appends_when_missing tests/test_harness_compatibility.py::test_fence_upsert_skips_missing_file tests/test_harness_compatibility.py::test_fence_preserves_surrounding_bytes -v
```
Expected: FAIL

- [ ] **Step 3: Implement `_upsert_harness_fence()`**

```python
import re as _re
from datetime import datetime, timezone

_FENCE_OPEN_PATTERN = _re.compile(
    r"<!-- synlynk:harness v\S+ verified:\S+ -->.*?<!-- /synlynk:harness -->",
    _re.DOTALL,
)

def _build_fence_content(harness_version: str, body: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    return (
        f"<!-- synlynk:harness v{harness_version} verified:{ts} -->\n"
        f"# Harness Instructions (synlynk-managed — do not edit)\n\n"
        f"{body}\n"
        f"<!-- /synlynk:harness -->"
    )

def _upsert_harness_fence(file_path: str, harness_version: str, body: str) -> None:
    if not os.path.exists(file_path):
        print(f"  warning: {file_path} not found — fence skipped. Run synlynk init to create.", file=sys.stderr)
        return

    fence = _build_fence_content(harness_version, body)
    with open(file_path, "r", encoding="utf-8") as f:
        current = f.read()

    if _FENCE_OPEN_PATTERN.search(current):
        updated = _FENCE_OPEN_PATTERN.sub(fence, current, count=1)
    else:
        sep = "\n" if current.endswith("\n") else "\n\n"
        updated = current + sep + fence + "\n"

    with open(file_path, "w", encoding="utf-8") as f:
        f.write(updated)
```

- [ ] **Step 4: Implement `_build_fence_body_from_record()`**

```python
def _build_fence_body_from_record(agent_name: str, db_conn=None) -> str:
    import json as _j
    baseline = AGENT_CAPABILITY_BASELINES.get(agent_name, {})
    contract = baseline.get("headless_contract", {})
    flags_spec = baseline.get("dispatch_flags", {})
    net_deps = baseline.get("network_deps", {})

    if db_conn:
        row = db_conn.execute(
            "SELECT active_contract, active_flags FROM harness_records WHERE agent_name=?",
            (agent_name,)
        ).fetchone()
        if row:
            contract = _j.loads(row[0]) or contract
            flags_spec = _j.loads(row[1]) or flags_spec

    mode = "pty" if contract.get("requires_pty") else "pipe"
    flush = contract.get("stdout_flush_method", "native")
    ni_flag = contract.get("non_interactive_flag", "")
    env_vars = contract.get("env_vars_required", [])
    valid = " ".join(flags_spec.get("valid_flags", []))
    invalid = " ".join(flags_spec.get("invalid_flags", []))
    endpoints = "\n".join(f"- Required: {e}" for e in net_deps.get("required_endpoints", []))

    env_line = f"- Stdout flush: unbuffered (set {' '.join(env_vars)})" if env_vars else f"- Stdout flush: {flush}"

    return f"""## Headless Execution Contract
- Execution mode: {mode}
- Non-interactive flag: {ni_flag}
{env_line}

## Active Dispatch Flags
- Valid: {valid}
- Invalid (do not use): {invalid}

## Network Dependencies
{endpoints or '- None required'}"""
```

- [ ] **Step 5: Wire into probe — call after `harness_records` upsert**

In `_probe_agent()`, after step 6 (upsert harness_records):
```python
# Find the instruction files for this agent
_INSTRUCTION_FILES = {
    "claude": "CLAUDE.md",
    "agy": "GEMINI.md",
    "grok": "GROK.md",
    "codex": "AGENTS.md",
}
instr_file = _INSTRUCTION_FILES.get(agent_name)
if instr_file and os.path.exists(instr_file):
    body = _build_fence_body_from_record(agent_name, db_conn)
    _upsert_harness_fence(instr_file, installed_version, body)
```

- [ ] **Step 6: Run tests**

```bash
python -m pytest tests/test_harness_compatibility.py::test_fence_upsert_replaces_existing_fence tests/test_harness_compatibility.py::test_fence_upsert_appends_when_missing tests/test_harness_compatibility.py::test_fence_upsert_skips_missing_file tests/test_harness_compatibility.py::test_fence_preserves_surrounding_bytes -v
```
Expected: PASS

- [ ] **Step 7: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 8: Commit**

```bash
git add synlynk/__init__.py tests/test_harness_compatibility.py
git commit -m "feat(bs14): instruction fence upsert — managed synlynk:harness section in agent instruction files"
```

---

### Task 12: story-bs14-drift
**Owner: Codex**

Wire `HARNESS_VERSION_DRIFT` sentinel into the dispatch preflight version check (using the 1hr cache) and into `_probe_agent()` hash diff. Ensure `harness_version_history` is always appended on drift.

**Files:**
- Modify: `synlynk/__init__.py` — `_preflight_dispatch()` version stale check, `_probe_agent()` drift path
- Test: `tests/test_harness_compatibility.py`

- [ ] **Step 1: Write the failing test**

```python
def test_preflight_fires_drift_sentinel_on_version_change(tmp_path, monkeypatch):
    import sqlite3, json
    from synlynk import _migrate_db, _preflight_dispatch

    db = sqlite3.connect(":memory:")
    _migrate_db(db)
    # Record says 1.0.0 was last probed 2hrs ago
    import time
    old_time = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
    db.execute("""
        INSERT INTO harness_records (agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at)
        VALUES ('agy','agy','1.0.0','ok','{}','{}','abc123',?)
    """, (old_time,))
    db.commit()

    # Stub CLI returns 2.0.0
    stub = tmp_path / "agy"
    stub.write_text("#!/bin/sh\necho 'agy 2.0.0'\n")
    stub.chmod(0o755)
    monkeypatch.setenv("PATH", str(tmp_path) + ":" + os.environ["PATH"])

    sentinel_events = []
    import synlynk
    original_write = synlynk._write_sentinel_alert
    def capture_sentinel(level, pattern, msg, *args):
        sentinel_events.append(pattern)
        original_write(level, pattern, msg, *args)
    monkeypatch.setattr(synlynk, "_write_sentinel_alert", capture_sentinel)

    result = _preflight_dispatch("agy", ["--non-interactive"], db_conn=db)
    assert "HARNESS_VERSION_DRIFT" in sentinel_events
```

- [ ] **Step 2: Run to confirm failure**

```bash
python -m pytest tests/test_harness_compatibility.py::test_preflight_fires_drift_sentinel_on_version_change -v
```
Expected: FAIL

- [ ] **Step 3: Update `_preflight_dispatch()` to use 1hr cache + fire drift sentinel**

Add at the start of `_preflight_dispatch()`, before flag/network checks:

```python
import time as _time
STALE_THRESHOLD_SECONDS = 3600  # 1hr

if db_conn:
    row = db_conn.execute(
        "SELECT installed_version, last_probe_at FROM harness_records WHERE agent_name=?",
        (agent_name,)
    ).fetchone()
    if row:
        recorded_version, last_probe_at = row
        # Check if cache is stale
        is_stale = True
        if last_probe_at:
            try:
                probe_ts = _time.mktime(_time.strptime(last_probe_at, "%Y-%m-%dT%H:%M:%SZ"))
                is_stale = (_time.time() - probe_ts) > STALE_THRESHOLD_SECONDS
            except ValueError:
                is_stale = True

        if is_stale:
            # Spawn --version to check for drift
            try:
                ver_result = subprocess.run([agent_name, "--version"],
                                            capture_output=True, text=True, timeout=3)
                live_version = ver_result.stdout.strip().split()[-1] if ver_result.stdout.strip() else "unknown"
                if live_version != recorded_version:
                    _write_sentinel_alert(
                        "WARNING", "HARNESS_VERSION_DRIFT",
                        f"Agent '{agent_name}' version changed: {recorded_version} → {live_version}. Run synlynk probe.",
                    )
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass
```

- [ ] **Step 4: Run tests**

```bash
python -m pytest tests/test_harness_compatibility.py::test_preflight_fires_drift_sentinel_on_version_change -v
```
Expected: PASS

- [ ] **Step 5: Full suite**

```bash
python -m pytest tests/ -x -q 2>&1 | tail -20
```

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_harness_compatibility.py
git commit -m "feat(bs14): HARNESS_VERSION_DRIFT sentinel — 1hr cache + live version check in dispatch preflight"
```

---

## Self-Review Checklist (run before marking complete)

```bash
# Full suite must pass
python -m pytest tests/ -q 2>&1 | tail -5

# Verify all five tables exist in a fresh DB
python -c "
import sqlite3, synlynk
db = sqlite3.connect(':memory:')
synlynk._migrate_db(db)
tables = {r[0] for r in db.execute(\"SELECT name FROM sqlite_master WHERE type='table'\").fetchall()}
required = {'harness_baselines','harness_records','harness_verb_map','harness_command_palette','harness_version_history'}
missing = required - tables
print('PASS' if not missing else f'MISSING: {missing}')
"

# Verify Grok baseline excludes --always-approve
python -c "
from synlynk import AGENT_CAPABILITY_BASELINES
grok = AGENT_CAPABILITY_BASELINES['grok']
assert '--always-approve' in grok['dispatch_flags']['invalid_flags']
print('PASS: grok baseline clean')
"

# Verify preflight blocks invalid Grok flag
python -c "
from synlynk import _preflight_dispatch
r = _preflight_dispatch('grok', ['--always-approve'], db_conn=None)
assert r['passed'] is False
print('PASS: preflight blocks --always-approve')
"
```
