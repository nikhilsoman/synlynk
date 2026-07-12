# Local Agent (5th Agent) — oMLX/MLX Driver Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project override:** this repo's `CLAUDE.md` locks Claude to PM/reviewer only. Do not
> execute this plan via a Claude subagent writing code directly. Execution happens via
> `synlynk dispatch <codex|agy|grok> --force-agent --context-mode full`, one **whole task
> group** (PR) per dispatch call — not task-by-task — per the confirmed finding in
> `docs/blog/49-prTBD-bs8-goal-hierarchy.md`: task-by-task dispatch caused agents to
> recreate prior work from stale `main` on every call; whole-group dispatch with literal
> code pinned in the prompt was the fix. Claude reviews the diff for plan fidelity and
> does git integration between groups.

**Goal:** Onboard a 5th dispatch agent, `local`, that runs zero-cost on-device inference
via oMLX, routed through the existing capability→quota→cost scheduler.

**Architecture:** `local` is invoked exactly like any CLI agent — `dispatch_agent()`
spawns `python3 -m synlynk.local_agent_runner < prompt_file`, a small stdin-reading
script that POSTs to oMLX's OpenAI-compatible endpoint and prints the response text plus
a `prompt_tokens: N completion_tokens: N` line to stdout. This is a refinement discovered
during planning (see spec's "new HTTP driver path" framing): wrapping the HTTP call in a
thin CLI-shaped runner means **zero changes** to `dispatch_agent()`'s subprocess/worktree/
log-polling machinery, and the existing `extract_tokens()` regex (pattern 5:
`prompt_tokens`/`completion_tokens`) already parses the runner's output with no changes
to `costs.py`'s extraction logic — only new rate-table entries.

**Tech Stack:** Python 3 stdlib only (`urllib.request` for the HTTP call — no new
dependency), SQLite (`state.db`), pytest.

**Reference spec:** `docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md`

---

## Task Group 1: Driver wiring — `local` agent, `.agents/local.json`, runner script

**Branch:** `feat/local-agent-1-driver-wiring`

**Files:**
- Create: `.agents/local.json`
- Create: `synlynk/local_agent.py`
- Create: `synlynk/local_agent_runner.py`
- Modify: `synlynk/_constants.py` (add `AGENT_CAPABILITY_BASELINES["local"]`, add 3 rows to `_MODEL_RATE_TABLE` — wait, rate table lives in `costs.py`, see below)
- Modify: `synlynk/costs.py:137-145` (`_MODEL_RATE_TABLE`)
- Test: `tests/test_local_agent.py`

### Step 1: Write failing tests for the config loader and health check

Create `tests/test_local_agent.py`:

```python
"""Tests for synlynk.local_agent — config loading, health check, chat completion.
All HTTP calls are mocked; no real oMLX instance required (standard CI tier)."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock

from synlynk import local_agent


class TestLoadLocalConfig(unittest.TestCase):
    def test_loads_valid_config(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "name": "local",
                    "driver": "http",
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [
                        {"id": "ornith-1.0-9b", "pinned": True},
                        {"id": "qwen-coder", "pinned": False},
                    ],
                    "hardware_tier": "16gb-default",
                    "max_concurrent": 1,
                }, f)
            config = local_agent._load_local_config(path)
        self.assertEqual(config["endpoint"], "http://127.0.0.1:8080")
        self.assertEqual(len(config["models"]), 2)

    def test_missing_config_raises_clear_error(self):
        with self.assertRaises(FileNotFoundError):
            local_agent._load_local_config("/nonexistent/local.json")


class TestPinnedModel(unittest.TestCase):
    def test_returns_pinned_model(self):
        config = {"models": [
            {"id": "a", "pinned": False},
            {"id": "b", "pinned": True},
        ]}
        self.assertEqual(local_agent._pinned_model(config), "b")

    def test_falls_back_to_first_model_when_none_pinned(self):
        config = {"models": [{"id": "a", "pinned": False}, {"id": "b", "pinned": False}]}
        self.assertEqual(local_agent._pinned_model(config), "a")


class TestHealthCheck(unittest.TestCase):
    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_ok(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps(
            {"data": [{"id": "ornith-1.0-9b"}, {"id": "qwen-coder"}]}
        ).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        result = local_agent._health_check("http://127.0.0.1:8080")
        self.assertTrue(result["reachable"])
        self.assertIn("ornith-1.0-9b", result["available_models"])

    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_health_check_unreachable(self, mock_urlopen):
        import urllib.error
        mock_urlopen.side_effect = urllib.error.URLError("connection refused")
        result = local_agent._health_check("http://127.0.0.1:8080")
        self.assertFalse(result["reachable"])
        self.assertIn("connection refused", result["error"])


class TestChatCompletion(unittest.TestCase):
    @patch("synlynk.local_agent.urllib.request.urlopen")
    def test_chat_completion_returns_text_and_usage(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = json.dumps({
            "choices": [{"message": {"content": "def add(a, b): return a + b"}}],
            "usage": {"prompt_tokens": 120, "completion_tokens": 15},
        }).encode("utf-8")
        mock_urlopen.return_value.__enter__.return_value = mock_resp
        text, usage = local_agent._chat_completion(
            "http://127.0.0.1:8080", "ornith-1.0-9b", "write an add function"
        )
        self.assertEqual(text, "def add(a, b): return a + b")
        self.assertEqual(usage["prompt_tokens"], 120)
        self.assertEqual(usage["completion_tokens"], 15)


if __name__ == "__main__":
    unittest.main()
```

### Step 2: Run tests to verify they fail

Run: `pytest tests/test_local_agent.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.local_agent'`

### Step 3: Create `.agents/local.json`

```json
{
  "name": "local",
  "driver": "http",
  "endpoint": "http://127.0.0.1:8080",
  "models": [
    {"id": "ornith-1.0-9b", "pinned": true},
    {"id": "qwen-coder", "pinned": false},
    {"id": "gemma-coder", "pinned": false}
  ],
  "hardware_tier": "16gb-default",
  "max_concurrent": 1
}
```

### Step 4: Create `synlynk/local_agent.py`

```python
"""synlynk local agent: config loading, health check, and chat-completion
helpers for the oMLX-backed 'local' dispatch agent. Shared by
local_agent_runner.py (dispatch execution) and cmd_local_doctor (CLI health check)."""

import json
import os
import urllib.error
import urllib.request

_DEFAULT_CONFIG_PATH = os.path.join(".agents", "local.json")


def _load_local_config(path: str = _DEFAULT_CONFIG_PATH) -> dict:
    """Reads and parses .agents/local.json. Raises FileNotFoundError if missing."""
    if not os.path.exists(path):
        raise FileNotFoundError(
            f"{path} not found. Run `synlynk local doctor` for setup guidance."
        )
    with open(path) as f:
        return json.load(f)


def _pinned_model(config: dict) -> str:
    """Returns the pinned model id, or the first roster entry if none pinned."""
    for m in config["models"]:
        if m.get("pinned"):
            return m["id"]
    return config["models"][0]["id"]


def _health_check(endpoint: str, timeout: int = 5) -> dict:
    """GETs {endpoint}/v1/models. Returns {reachable, available_models} or
    {reachable: False, error}."""
    req = urllib.request.Request(f"{endpoint}/v1/models", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {"reachable": False, "error": str(exc)}
    available = [m.get("id") for m in payload.get("data", [])]
    return {"reachable": True, "available_models": available}


def _chat_completion(endpoint: str, model: str, prompt_text: str, timeout: int = 300):
    """POSTs one /v1/chat/completions request. Returns (text, usage_dict).
    Raises urllib.error.URLError/HTTPError on failure — caller handles it."""
    body = json.dumps({
        "model": model,
        "messages": [{"role": "user", "content": prompt_text}],
    }).encode("utf-8")
    req = urllib.request.Request(
        f"{endpoint}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        payload = json.loads(resp.read().decode("utf-8"))
    text = payload["choices"][0]["message"]["content"]
    usage = payload.get("usage", {"prompt_tokens": 0, "completion_tokens": 0})
    return text, usage


def cmd_local_doctor(config_path: str = _DEFAULT_CONFIG_PATH) -> int:
    """Prints oMLX reachability + roster status. Returns 0 if healthy, 1 otherwise."""
    try:
        config = _load_local_config(config_path)
    except FileNotFoundError as exc:
        print(f"  ✗ {exc}")
        return 1
    endpoint = config["endpoint"]
    result = _health_check(endpoint)
    if not result["reachable"]:
        print(f"  ✗ oMLX unreachable at {endpoint}: {result['error']}")
        print("    Start it with: omlx serve")
        return 1
    print(f"  ✓ oMLX reachable at {endpoint}")
    roster_ids = [m["id"] for m in config["models"]]
    available = set(result["available_models"])
    missing = [m for m in roster_ids if m not in available]
    for model_id in roster_ids:
        mark = "✓" if model_id not in missing else "✗"
        print(f"  {mark} {model_id}")
    if missing:
        print(f"    Missing models: {', '.join(missing)} — download via oMLX admin panel or CLI")
        return 1
    return 0
```

### Step 5: Run tests to verify they pass

Run: `pytest tests/test_local_agent.py -v`
Expected: PASS (all 6 tests)

### Step 6: Create `synlynk/local_agent_runner.py`

```python
"""Dispatch entrypoint for the 'local' agent: `python3 -m synlynk.local_agent_runner`.

Reads the task prompt from stdin, sends one chat-completion request to the
oMLX endpoint declared in .agents/local.json, and prints the response text
followed by a `prompt_tokens: N completion_tokens: N` line. That trailing
line matches extract_tokens()'s existing pattern 5 (synlynk/costs.py) — no
changes to token extraction are needed for this agent.

Exit code 1 (with a stderr message) on any failure — this is picked up by
dispatch_agent()'s existing log/.exit polling exactly like a CLI agent
failure, so oMLX being down produces a normal failed job, not a hang.
"""
import sys
import urllib.error

from synlynk.local_agent import _load_local_config, _pinned_model, _chat_completion


def run(prompt_text: str, config_path: str = None) -> int:
    try:
        config = _load_local_config(config_path) if config_path else _load_local_config()
    except FileNotFoundError as exc:
        sys.stderr.write(f"local agent: {exc}\n")
        return 1
    endpoint = config["endpoint"]
    model = _pinned_model(config)
    try:
        text, usage = _chat_completion(endpoint, model, prompt_text)
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        sys.stderr.write(f"local agent: oMLX endpoint unreachable at {endpoint}: {exc}\n")
        return 1
    print(text)
    print(f"\nprompt_tokens: {usage.get('prompt_tokens', 0)} "
          f"completion_tokens: {usage.get('completion_tokens', 0)}")
    return 0


def main():
    prompt_text = sys.stdin.read()
    sys.exit(run(prompt_text))


if __name__ == "__main__":
    main()
```

### Step 7: Write failing test for the runner

Add to `tests/test_local_agent.py`:

```python
from synlynk import local_agent_runner


class TestRunnerMain(unittest.TestCase):
    @patch("synlynk.local_agent_runner._chat_completion")
    @patch("synlynk.local_agent_runner._load_local_config")
    def test_run_prints_text_and_token_line(self, mock_load, mock_chat, ):
        mock_load.return_value = {
            "endpoint": "http://127.0.0.1:8080",
            "models": [{"id": "ornith-1.0-9b", "pinned": True}],
        }
        mock_chat.return_value = (
            "print('hi')",
            {"prompt_tokens": 50, "completion_tokens": 5},
        )
        import io
        import contextlib
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            exit_code = local_agent_runner.run("write hello world")
        output = buf.getvalue()
        self.assertEqual(exit_code, 0)
        self.assertIn("print('hi')", output)
        self.assertIn("prompt_tokens: 50 completion_tokens: 5", output)

    @patch("synlynk.local_agent_runner._load_local_config")
    def test_run_returns_1_when_config_missing(self, mock_load):
        mock_load.side_effect = FileNotFoundError(".agents/local.json not found")
        exit_code = local_agent_runner.run("task")
        self.assertEqual(exit_code, 1)
```

Run: `pytest tests/test_local_agent.py -v`
Expected: FAIL — `test_run_prints_text_and_token_line` and
`test_run_returns_1_when_config_missing` FAIL because `local_agent_runner.run` doesn't
yet accept being imported this way (it does — re-run after step 6's file exists; if it
still fails, check the mock patch targets match the actual import path used inside
`local_agent_runner.py`, i.e. `_chat_completion` must be imported by name into
`local_agent_runner`'s namespace, which it is per Step 6's `from synlynk.local_agent
import ... _chat_completion`).

### Step 8: Confirm pass

Run: `pytest tests/test_local_agent.py -v`
Expected: PASS (all 8 tests)

### Step 9: Register `local` in `AGENT_CAPABILITY_BASELINES`

Modify `synlynk/_constants.py`. Find the closing of the `"grok"` entry (the dict entry
ending around where `"strengths": [...]` for grok is followed by `}`, then the next
top-level key or the closing `}` of `AGENT_CAPABILITY_BASELINES`). Add immediately after
the `"grok"` entry's closing `},`:

```python
    "local": {
        "cli": "python3",
        "non_interactive_flags": ["-m", "synlynk.local_agent_runner"],
        "dispatch_flags": [],
        "roles": ["builder"],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
    },
```

No `prompt_flag`/`prompt_via_arg` — this falls through `dispatch_agent()`'s existing
`else` branch (`synlynk/dispatch.py:730-733`), which pipes the prompt file via stdin:
`python3 -m synlynk.local_agent_runner < prompt_file > log_file 2>&1`. That's exactly
`local_agent_runner.main()`'s expected input.

### Step 10: Add local model rates to `costs.py`

Modify `synlynk/costs.py:137-145`, add 3 entries to `_MODEL_RATE_TABLE`:

```python
    "ornith-1.0-9b": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    "qwen-coder": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
    "gemma-coder": {"input": 0.0, "output": 0.0, "cache_read": 0.0},
```

Add this as a test in `tests/test_local_agent.py`:

```python
from synlynk.costs import _model_rate_for_version


class TestLocalModelRates(unittest.TestCase):
    def test_local_models_are_zero_cost(self):
        for model_id in ("ornith-1.0-9b", "qwen-coder", "gemma-coder"):
            rates = _model_rate_for_version(model_id)
            self.assertEqual(rates["input"], 0.0)
            self.assertEqual(rates["output"], 0.0)
            self.assertEqual(rates["cache_read"], 0.0)
```

Run: `pytest tests/test_local_agent.py -v`
Expected: PASS (all 9 tests)

### Step 11: Wire `synlynk local doctor` CLI command

Modify `synlynk/cli.py`. Find the `goal_parser` block (`subparsers.add_parser("goal", ...)`,
around line 249) and add immediately after its block ends (after
`goal_sub.add_parser("status", ...)`):

```python
    local_parser = subparsers.add_parser("local", help="Manage the local (oMLX) agent")
    local_sub = local_parser.add_subparsers(dest="local_action")
    local_sub.add_parser("doctor", help="Check oMLX endpoint reachability and model roster")
```

Find where `goal_action` is dispatched in the command-handling section of `cli.py`
(search for `args.goal_action` or `elif args.command == "goal"`) and add a matching
branch:

```python
    elif args.command == "local":
        from synlynk.local_agent import cmd_local_doctor
        if args.local_action == "doctor":
            sys.exit(cmd_local_doctor())
        else:
            local_parser.print_help()
```

### Step 12: Manual verification

Run: `python3 bin/synlynk.py local doctor`
Expected (no oMLX running): `✗ oMLX unreachable at http://127.0.0.1:8080: ...` and exit
code 1 — confirms the command wires up and fails cleanly without a live server.

### Step 13: Full test suite + commit

Run: `pytest tests/ -q --tb=short`
Expected: all tests pass, no regressions.

```bash
git add .agents/local.json synlynk/local_agent.py synlynk/local_agent_runner.py \
        synlynk/_constants.py synlynk/costs.py synlynk/cli.py tests/test_local_agent.py
git commit -m "feat(local-agent): driver wiring — .agents/local.json, runner, doctor command"
```

---

## Task Group 2: Capability envelope seeding + concurrency guard

**Branch:** `feat/local-agent-2-capability-seed-quota`

**Files:**
- Create: `synlynk/local_agent_seed.py`
- Modify: `synlynk/dispatch.py` (concurrency guard in `dispatch_agent()`)
- Test: `tests/test_local_agent_seed.py`
- Test: `tests/test_local_agent_concurrency.py`

### Step 1: Write failing test for the seed function

Create `tests/test_local_agent_seed.py`:

```python
"""Tests for seeding the local agent's starter capability envelope.
capability_scores is a VIEW over capability_ratings — seeding means inserting
synthetic calibration stories + capability_ratings rows for a narrow starter
whitelist (docs/testing discipline, execute stage, small estimated_tokens)."""
import sqlite3
import unittest

from synlynk.local_agent_seed import seed_local_capability_envelope, STARTER_WHITELIST


def _fresh_db():
    conn = sqlite3.connect(":memory:")
    conn.execute("""
        CREATE TABLE stories (
            story_id TEXT PRIMARY KEY, engg_domain TEXT, org_domain TEXT,
            industry TEXT, phase TEXT, estimated_tokens INTEGER, goal_id TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE capability_ratings (
            id INTEGER PRIMARY KEY AUTOINCREMENT, story_id TEXT, agent TEXT,
            model_version TEXT DEFAULT 'unknown', split_model INTEGER DEFAULT 0,
            engg_domain TEXT, discipline TEXT, org_domain TEXT, role TEXT,
            stage TEXT, industry TEXT, phase TEXT, signal_source TEXT DEFAULT 'auto',
            quality REAL, ts TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    return conn


class TestSeedLocalCapabilityEnvelope(unittest.TestCase):
    def test_seeds_one_row_per_starter_coordinate(self):
        conn = _fresh_db()
        seed_local_capability_envelope(conn)
        rows = conn.execute(
            "SELECT discipline, stage, quality FROM capability_ratings WHERE agent='local'"
        ).fetchall()
        self.assertEqual(len(rows), len(STARTER_WHITELIST))

    def test_seeded_stories_are_tagged_calibration(self):
        conn = _fresh_db()
        seed_local_capability_envelope(conn)
        story_ids = [r[0] for r in conn.execute(
            "SELECT story_id FROM stories WHERE story_id LIKE 'local-seed-%'"
        ).fetchall()]
        self.assertEqual(len(story_ids), len(STARTER_WHITELIST))

    def test_is_idempotent(self):
        conn = _fresh_db()
        seed_local_capability_envelope(conn)
        seed_local_capability_envelope(conn)
        rows = conn.execute(
            "SELECT COUNT(*) FROM capability_ratings WHERE agent='local'"
        ).fetchone()[0]
        self.assertEqual(rows, len(STARTER_WHITELIST))


if __name__ == "__main__":
    unittest.main()
```

### Step 2: Run to verify failure

Run: `pytest tests/test_local_agent_seed.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.local_agent_seed'`

### Step 3: Create `synlynk/local_agent_seed.py`

```python
"""Seeds a conservative starter capability envelope for the 'local' agent.

capability_scores (synlynk/__init__.py's _DB_SCORES_VIEW) is a VIEW computed
from capability_ratings — there's no table to seed directly. To make the
existing _best_agent_for_story() router surface 'local' for a narrow set of
granular task coordinates (and stay cold/absent everywhere else), this inserts
one synthetic calibration story + capability_ratings row per starter
coordinate. Real job completions layer on top via the normal
_write_capability_rating() path — the envelope widens itself with no
local-specific code."""

MODEL_VERSION = "ornith-1.0-9b"

# (discipline, org_domain, role, stage, engg_domain, industry, phase, estimated_tokens)
STARTER_WHITELIST = [
    ("docs", "content", "dev", "execute", "docs", "unknown", "build", 800),
    ("testing", "platform", "dev", "execute", "testing", "unknown", "build", 1200),
]

# Moderate, not maxed — proves capability without out-competing paid agents
# on tasks it hasn't actually done yet.
SEED_QUALITY = 0.6


def seed_local_capability_envelope(conn) -> None:
    """Idempotent: re-running does not duplicate rows (checks by story_id)."""
    for i, (discipline, org_domain, role, stage, engg_domain, industry, phase,
            est_tokens) in enumerate(STARTER_WHITELIST):
        story_id = f"local-seed-{i:02d}"
        exists = conn.execute(
            "SELECT 1 FROM stories WHERE story_id=?", (story_id,)
        ).fetchone()
        if exists:
            continue
        conn.execute(
            "INSERT INTO stories (story_id, engg_domain, org_domain, industry, "
            "phase, estimated_tokens) VALUES (?, ?, ?, ?, ?, ?)",
            (story_id, engg_domain, org_domain, industry, phase, est_tokens),
        )
        conn.execute(
            "INSERT INTO capability_ratings (story_id, agent, model_version, "
            "split_model, engg_domain, discipline, org_domain, role, stage, "
            "industry, phase, signal_source, quality) VALUES "
            "(?, 'local', ?, 0, ?, ?, ?, ?, ?, ?, ?, 'seed', ?)",
            (story_id, MODEL_VERSION, engg_domain, discipline, org_domain, role,
             stage, industry, phase, SEED_QUALITY),
        )
    conn.commit()
```

### Step 4: Run tests to verify pass

Run: `pytest tests/test_local_agent_seed.py -v`
Expected: PASS (3 tests)

### Step 5: Wire seeding into `synlynk local doctor`

Modify `synlynk/local_agent.py`'s `cmd_local_doctor()` (from Task Group 1) — after the
successful health-check branch (`print(f"  ✓ oMLX reachable...")`), add:

```python
    from synlynk import _get_db
    from synlynk.local_agent_seed import seed_local_capability_envelope
    seed_local_capability_envelope(_get_db())
    print("  ✓ starter capability envelope seeded (docs/testing, execute stage)")
```

This makes the first successful `synlynk local doctor` run also seed the envelope —
one command, no separate migration step for the user to remember.

### Step 6: Write failing test for the concurrency guard

Create `tests/test_local_agent_concurrency.py`:

```python
"""Tests the local-agent concurrency guard in dispatch_agent(): max_concurrent
running 'local' jobs from .agents/local.json is enforced before spawning a new one."""
import sqlite3
import unittest
from unittest.mock import patch

from synlynk.dispatch import _local_concurrency_exceeded


def _db_with_running_jobs(count, agent="local"):
    conn = sqlite3.connect(":memory:")
    conn.execute(
        "CREATE TABLE daemon_jobs (job_id TEXT, agent TEXT, status TEXT)"
    )
    for i in range(count):
        conn.execute(
            "INSERT INTO daemon_jobs (job_id, agent, status) VALUES (?, ?, 'running')",
            (f"job-{i}", agent),
        )
    conn.commit()
    return conn


class TestLocalConcurrencyGuard(unittest.TestCase):
    def test_not_exceeded_when_under_limit(self):
        conn = _db_with_running_jobs(0)
        self.assertFalse(_local_concurrency_exceeded(conn, max_concurrent=1))

    def test_exceeded_when_at_limit(self):
        conn = _db_with_running_jobs(1)
        self.assertTrue(_local_concurrency_exceeded(conn, max_concurrent=1))

    def test_other_agents_dont_count(self):
        conn = _db_with_running_jobs(3, agent="codex")
        self.assertFalse(_local_concurrency_exceeded(conn, max_concurrent=1))


if __name__ == "__main__":
    unittest.main()
```

### Step 7: Run to verify failure

Run: `pytest tests/test_local_agent_concurrency.py -v`
Expected: FAIL — `ImportError: cannot import name '_local_concurrency_exceeded'`

### Step 8: Implement the guard in `dispatch.py`

Modify `synlynk/dispatch.py`. Add this function near the top, after
`_load_harness_overrides` (around line 51):

```python
def _local_concurrency_exceeded(conn, max_concurrent: int = 1) -> bool:
    """True if the 'local' agent already has max_concurrent+ running jobs.

    One Mac, one GPU/unified-memory pool — this is a concurrency guard, not a
    $-based quota, so it's checked directly against daemon_jobs rather than
    agent_quotas (which models time-windowed spend, a different concept)."""
    row = conn.execute(
        "SELECT COUNT(*) FROM daemon_jobs WHERE status='running' AND agent='local'"
    ).fetchone()
    running = row[0] if row else 0
    return running >= max_concurrent
```

Then in `dispatch_agent()` (`synlynk/dispatch.py:635`), immediately after the
`if agent not in baselines_map:` check (around line 651) and before
`baselines = baselines_map[agent]`, add:

```python
    if agent == "local":
        get_db = _pkg("_get_db")
        conn = get_db() if get_db else None
        if conn is not None:
            try:
                local_config = json.load(open(os.path.join(".agents", "local.json")))
            except (OSError, json.JSONDecodeError):
                local_config = {}
            max_concurrent = local_config.get("max_concurrent", 1)
            if _local_concurrency_exceeded(conn, max_concurrent=max_concurrent):
                raise RuntimeError(
                    f"local agent at max concurrency ({max_concurrent}); "
                    "wait for the running job to finish"
                )
```

### Step 9: Run tests to verify pass

Run: `pytest tests/test_local_agent_concurrency.py -v`
Expected: PASS (3 tests)

### Step 10: Full suite + commit

Run: `pytest tests/ -q --tb=short`
Expected: all tests pass.

```bash
git add synlynk/local_agent_seed.py synlynk/local_agent.py synlynk/dispatch.py \
        tests/test_local_agent_seed.py tests/test_local_agent_concurrency.py
git commit -m "feat(local-agent): capability envelope seeding + concurrency guard"
```

---

## Task Group 3: Real-hardware test tier

**Branch:** `feat/local-agent-3-hardware-tests`

**Files:**
- Modify: `pytest.ini` (register `local_hardware` marker)
- Create: `tests/test_local_agent_hardware.py`

### Step 1: Register the marker

Modify `pytest.ini`:

```ini
[pytest]
markers =
    e2e: black-box end-to-end tests that invoke the synlynk CLI as a subprocess
    local_hardware: requires a real running oMLX instance with the model roster installed; skipped by default, run explicitly with `pytest -m local_hardware`
```

### Step 2: Create the real-hardware test file

```python
"""Real-inference tests against a live oMLX instance. NOT run in standard CI —
requires oMLX running locally (`omlx serve`) with the .agents/local.json roster
downloaded. Run explicitly: `pytest tests/test_local_agent_hardware.py -m local_hardware -v`"""
import subprocess
import sys
import unittest

import pytest

from synlynk.local_agent import _load_local_config, _health_check, _chat_completion


@pytest.mark.local_hardware
class TestRealOmlxHealthCheck(unittest.TestCase):
    def setUp(self):
        self.config = _load_local_config()
        result = _health_check(self.config["endpoint"])
        if not result["reachable"]:
            self.skipTest(f"oMLX not reachable at {self.config['endpoint']} — start with `omlx serve`")

    def test_pinned_model_is_available(self):
        result = _health_check(self.config["endpoint"])
        from synlynk.local_agent import _pinned_model
        pinned = _pinned_model(self.config)
        self.assertIn(pinned, result["available_models"])

    def test_chat_completion_returns_nonempty_code(self):
        from synlynk.local_agent import _pinned_model
        pinned = _pinned_model(self.config)
        text, usage = _chat_completion(
            self.config["endpoint"], pinned,
            "Write a Python function `add(a, b)` that returns a + b. Only output the code.",
        )
        self.assertIn("def add", text)
        self.assertGreater(usage["prompt_tokens"], 0)
        self.assertGreater(usage["completion_tokens"], 0)


@pytest.mark.local_hardware
class TestRunnerEndToEnd(unittest.TestCase):
    def test_runner_subprocess_via_stdin(self):
        config = _load_local_config()
        result = _health_check(config["endpoint"])
        if not result["reachable"]:
            self.skipTest("oMLX not reachable")
        proc = subprocess.run(
            [sys.executable, "-m", "synlynk.local_agent_runner"],
            input="Write a Python function that returns the string 'hello'. Only output the code.",
            capture_output=True, text=True, timeout=120,
        )
        self.assertEqual(proc.returncode, 0)
        self.assertIn("prompt_tokens:", proc.stdout)
        self.assertIn("completion_tokens:", proc.stdout)


if __name__ == "__main__":
    unittest.main()
```

### Step 3: Verify the default suite still skips these

Run: `pytest tests/ -q --tb=short`
Expected: all previously-passing tests still pass; `test_local_agent_hardware.py`'s
tests do not appear as failures (no marker filter is applied by default here since the
marker is registered but not excluded — confirm project convention: check whether
`pytest.ini` or CI config filters `-m "not local_hardware"`. If CI runs plain
`pytest tests/ -q`, add `-m "not local_hardware"` to this repo's CI test-invocation step
so hardware tests don't attempt to run/skip-noisily on every PR. Locate the CI test step
(likely `.github/workflows/*.yml`) and confirm/update it in this task.)

Run: `grep -rn "pytest tests" .github/workflows/ 2>/dev/null`

If found, modify that line to append `-m "not local_hardware"`.

### Step 4: Manual verification (if oMLX is available locally)

Run: `pytest tests/test_local_agent_hardware.py -m local_hardware -v`
Expected: PASS if oMLX is running with the roster installed; otherwise clean skips with
the "oMLX not reachable" message, not errors.

### Step 5: Commit

```bash
git add pytest.ini tests/test_local_agent_hardware.py
git commit -m "test(local-agent): opt-in real-hardware inference tier"
```

(If the CI workflow file was modified in Step 3, include it in this commit.)

---

## Task Group 4: Docs

**Branch:** `feat/local-agent-4-docs`

**Files:**
- Modify: `docs/reference/capability-matrix-taxonomy.md`
- Create: `docs/blog/53-prTBD-local-agent-mlx-driver.md`

### Step 1: Add the local-agent worked example

Modify `docs/reference/capability-matrix-taxonomy.md` — after the existing "Worked
Example" section at the end of the file, add:

```markdown

### Local Agent Worked Example

The `local` agent (oMLX/MLX, zero marginal cost) is routed through the same four
dimensions as every other agent — no special-cased taxonomy. Its capability envelope
starts narrow by design: `synlynk local doctor` seeds two starter coordinates
(`discipline=docs`, `discipline=testing`, both `stage=execute`) with a moderate
calibration score, so `_best_agent_for_story()` only surfaces it for small, granular
tasks until real job completions widen the envelope. See
`docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md` for the full design.
```

### Step 2: Write the blog post

Follow this repo's Blog Post Protocol (`CLAUDE.md`) and the template in
`docs/blog/README.md`. Create `docs/blog/53-prTBD-local-agent-mlx-driver.md` covering:
goal at end of previous PR (BS-8 goal hierarchy shipped, GOVERNS rollout in progress),
what shifted in this PR (Ornith turned out to have MLX conversions after initial belief
it was GGUF-only, which changed the driver recommendation from llama.cpp to oMLX
mid-brainstorm), what shipped (driver wiring, capability seeding, concurrency guard,
two-tier tests), reference to this plan/spec (no separate brainstorm visuals were used
for this feature), and the new goalpost (observe real local-agent job completions,
consider widening the starter whitelist and/or adding a second Linux/Windows driver).

### Step 3: Commit

```bash
git add docs/reference/capability-matrix-taxonomy.md docs/blog/53-prTBD-local-agent-mlx-driver.md
git commit -m "docs(local-agent): taxonomy worked example + blog post"
```

---

## Task Group 5: Role-split integration (GATED — do not dispatch until Task Groups 1-4 have shipped and `local` is live in a release)

**Why deferred:** per user decision (2026-07-12), `local` stays out of the formal
agent-role-split surface (`.synlynk/config.json` `agent_slots`, the wizard's role
screen, CLAUDE.md's Default Agent Role table) until it has actually shipped and proven
itself — not speculatively wired in alongside the driver work. This task group exists so
the follow-up isn't forgotten, not to be executed now.

**Files:**
- Modify: `synlynk/wizard.py:702-707` (`_DEFAULT_ROLES` dict in `_wiz_screen_roles`)
- Modify: `synlynk/__init__.py:2777` and `:2846` (`known_agents` lists — both currently
  `["claude", "agy", "codex", "grok", "gemini"]`, missing `local`)
- Modify: `synlynk/__init__.py:3269` (fallback `agent_set` default
  `{"claude", "agy", "codex", "grok"}`)
- Modify: `synlynk/__init__.py:292-294` (GOVERNS stage→agent-list defaults, e.g.
  `"build": ["agy", "codex", "grok"]`, `"sustain": [...]` — decide at execution time
  whether `local` belongs in `build` given it's now a genuine CLI-subprocess coding
  agent per the revised Aider-based architecture)
- Modify: `/Users/nikhilsoman/dev/synlynk/CLAUDE.md` (Default Agent Role table — add a
  `local` row once its role is proven, e.g. "granular implementation offload (zero-cost,
  capability-gated)")
- **Open question to resolve at execution time, not now:** `_agent_guards` in
  `synlynk/__init__.py:3279` maps directive files to agents (`CLAUDE.md`→claude,
  `GEMINI.md`→agy, `AGENTS.md`→codex, `GROK.md`→grok) — each existing agent reads its own
  directive file for role/SOP injection. Aider does not read a fixed `AGENTS.md`-style
  directive file the way Claude/Codex/Agy/Grok do; it supports `.aider.conf.yml` and a
  conventions file passed via `--read`. Whoever executes this task group must decide
  whether `local` needs its own guard file (e.g. a generated `.aider.conf.yml` with a
  role/SOP block) or whether Aider should simply be pointed at the existing `AGENTS.md`
  via `--read` at dispatch time. Do not guess — check Aider's current docs for the
  supported mechanism, since Aider's config surface may have changed between now and
  when this task group executes.

- [ ] **Step 1: Confirm `local` has shipped and is live** — verify Task Groups 1-4 are
  merged to `main`, `synlynk local doctor` passes on a real machine, and at least one
  real dispatched job has completed successfully (not just mocked-CI tests).

- [ ] **Step 2: Write the failing test for `_DEFAULT_ROLES` including `local`**

```python
def test_default_roles_includes_local_agent():
    from synlynk import wizard
    assert "local" in wizard._DEFAULT_ROLES
    assert wizard._DEFAULT_ROLES["local"]  # non-empty description
```

Run: `pytest tests/test_wizard.py::test_default_roles_includes_local_agent -v`
Expected: FAIL with `AssertionError` (key not present).

- [ ] **Step 3: Add `local` to `_DEFAULT_ROLES`**

```python
_DEFAULT_ROLES = {
    "claude": "PM · code review · deployments",
    "agy": "implementation · testing · templates",
    "codex": "CLI plumbing · refactoring",
    "grok": "canvas/JS · infra scaffold · complex data structures",
    "local": "granular implementation offload (zero-cost, capability-gated)",
}
```

Run: `pytest tests/test_wizard.py::test_default_roles_includes_local_agent -v`
Expected: PASS

- [ ] **Step 4: Write the failing test for `known_agents` including `local`**

```python
def test_known_agents_includes_local():
    from synlynk import known_agents  # or wherever the list is imported from in tests
    assert "local" in known_agents
```

(Adjust the import path to match wherever `known_agents` is actually exposed at
execution time — it is currently an inline list literal at two call sites in
`synlynk/__init__.py`, not a named module-level constant; consider extracting it to one
`KNOWN_AGENTS` constant as part of this step so both call sites and the test share a
single source of truth, rather than editing two duplicated list literals.)

Run the test, confirm it fails, then extract/update `known_agents` at both call sites
(`synlynk/__init__.py:2777`, `:2846`) and the `agent_set` fallback default at `:3269` to
include `"local"`. Re-run to confirm it passes.

- [ ] **Step 5: Update CLAUDE.md's Default Agent Role table**

Add a row to the table in `/Users/nikhilsoman/dev/synlynk/CLAUDE.md` under "## Default
Agent Role" (created when the local-agent implementation shipped):

```markdown
| local (Aider + oMLX) | Granular implementation offload — zero-cost, capability-gated, starts narrow |
```

- [ ] **Step 6: Resolve the directive-file question (see Open question above), implement
  whichever mechanism was decided, and add a test asserting it.**

- [ ] **Step 7: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS, no regressions.

- [ ] **Step 8: Commit**

```bash
git add synlynk/wizard.py synlynk/__init__.py CLAUDE.md tests/test_wizard.py
git commit -m "feat(local-agent): fold local into role-split surface post-ship (agent_slots, wizard, CLAUDE.md)"
```

---

## Self-Review Notes (for whoever executes this plan)

- **Spec coverage:** Task Group 1 covers Architecture + Model Roster + `.agents/local.json`;
  Group 2 covers Capability Envelope + Cost & Quota; Group 3 covers the two-tier Testing
  section; Group 4 covers the Docs PR. The spec's "Open Risks" section (oMLX maturity,
  MLX-conversion churn, 16GB tightness) has no dedicated task — it's a monitoring
  concern for after Task Group 3's real-hardware run, not an implementation task. Task
  Group 5 (role-split integration into `.synlynk/config.json`/wizard/CLAUDE.md) is
  explicitly out of the original spec's scope by user decision (2026-07-12) — added as a
  gated follow-up task, not to be dispatched until `local` has shipped and proven itself.
- **Note (2026-07-12, post-Fable-review revision):** Task Group 1's Files/Steps sections
  still describe the original single-shot HTTP `local_agent_runner.py` design
  (`urllib.request`, `_chat_completion`, `_health_check` mocks). This is now stale — the
  Architecture section above was rewritten to reflect Aider-as-agentic-editor-over-oMLX
  (see the revised design spec), but Task Group 1's step-by-step content has NOT yet been
  rewritten to match. Per user decision, this rewrite is deliberately held until other
  Fable-review findings (the dispatch-path bug, the cost-accounting gap) are resolved, so
  Task Group 1 and Task Group 3 (its mocked tests) get one consolidated rewrite instead of
  two. **Do not dispatch Task Group 1 or Task Group 3 as currently written — they build
  the wrong thing.**
- **Type consistency:** `_load_local_config`, `_pinned_model`, `_health_check`,
  `_chat_completion` are defined once in `synlynk/local_agent.py` (Task Group 1, Step 4)
  and imported by name into `local_agent_runner.py`, `local_agent_seed.py`'s doctor
  wiring, and both test files — no redefinition or signature drift across groups.
- **PR discipline:** each task group is its own branch/worktree/PR per this repo's
  global git workflow (`feat/local-agent-<n>-<slug>`), matching the spec's 4-PR sequence.
