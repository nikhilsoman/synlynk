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
spawns a real `aider` CLI subprocess pointed at oMLX as an OpenAI-compatible backend
(`aider --openai-api-base <endpoint>/v1 --model <roster-id> --edit-format <whole|diff>
--no-auto-commits --yes-always --message-file <prompt_file>`), inside the job's normal
worktree. oMLX is the inference/serving layer only; Aider is the agentic editor that
reads/plans/writes real files and is git-aware. This is a revision from the original
single-shot-HTTP-chat-completion design (external review, Fable, 2026-07-12): a plain
`POST /v1/chat/completions` call returns text but cannot edit files, which left nothing
for `_write_capability_rating()` to score. Because `local` is a genuine CLI subprocess,
**no new spawn path** is needed in `dispatch_agent()` — only two small, additive changes
(dynamic flag assembly, a `--message-file` cmd branch) alongside the untouched
worktree/log-polling/reconciliation machinery every other agent already uses. Cost
accounting needs no local-specific change either — `_model_rate_for_version(...,
agent=...)` already forces `$0.00` for any `agent == "local"` job (landed via #189).

**Tech Stack:** Python 3 stdlib only for the config/preflight helpers (`urllib.request`
for the oMLX reachability check — no new dependency), `aider` (Apache-2.0, external CLI
dependency, not vendored) as the agentic editor, SQLite (`state.db`), pytest.

**Reference spec:** `docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md`

---

## Task Group 1: Driver wiring — `local` agent as an Aider subprocess over oMLX

**Branch:** `feat/local-agent-1-driver-wiring`

**Rewritten 2026-07-13** to match the Aider-over-oMLX architecture (design spec's
"Two layers" section) instead of the original bespoke HTTP chat-completion driver. This
version dispatches `local` as a real CLI subprocess (`aider ...`) exactly like `codex`/
`agy`/`grok`, so it participates in the existing worktree/log-polling/reconciliation
pipeline with **no new spawn path** — only additive, targeted changes to
`dispatch_agent()`'s flag-assembly and preflight steps.

**Already done, no action needed in this task group:** `synlynk/costs.py:148-152`
(`_model_rate_for_version`) already forces `{input: 0.0, output: 0.0, cache_read: 0.0}`
whenever `os.path.basename(agent) == "local"`, regardless of `model_version` — this
landed as part of #189/PR194's per-model rate-table fix, before this rewrite. The
original Task Group 1's "add 3 rows to `_MODEL_RATE_TABLE`" step is **removed** — it's
redundant with, and narrower than, that existing agent-level override.

**Files:**
- Create: `.agents/local.json`
- Create: `synlynk/local_agent.py`
- Modify: `synlynk/_constants.py` (add `AGENT_CAPABILITY_BASELINES["local"]`)
- Modify: `synlynk/dispatch.py`:
  - `_dispatch_flags_for_agent()` (line 25) — append dynamic model flags for `agent == "local"`
  - flag/cmd assembly in `dispatch_agent()` (lines 786-801) — add a `prompt_file_flag` branch
- Modify: `synlynk/cli.py` — `synlynk local doctor` subcommand
- Test: `tests/test_local_agent.py`
- Test: `tests/test_dispatch_local_agent.py`

### Step 1: Write failing tests for the config loader and preflight helpers

Create `tests/test_local_agent.py`:

```python
"""Tests for synlynk.local_agent — config loading, model/edit-format selection,
oMLX reachability check. All HTTP calls are mocked; no real oMLX instance required
(standard CI tier). This module does NOT talk to Aider — Aider is spawned as a CLI
subprocess by dispatch.py (see tests/test_dispatch_local_agent.py); this module only
owns the config/preflight helpers Aider's invocation is built from."""
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
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [
                        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
                        {"id": "qwen-coder", "pinned": False, "edit_format": "whole"},
                    ],
                    "hardware_tier": "16gb-default",
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
            {"id": "a", "pinned": False, "edit_format": "diff"},
            {"id": "b", "pinned": True, "edit_format": "whole"},
        ]}
        self.assertEqual(local_agent._pinned_model(config), "b")

    def test_falls_back_to_first_model_when_none_pinned(self):
        config = {"models": [
            {"id": "a", "pinned": False, "edit_format": "diff"},
            {"id": "b", "pinned": False, "edit_format": "whole"},
        ]}
        self.assertEqual(local_agent._pinned_model(config), "a")


class TestHealthCheck(unittest.TestCase):
    """oMLX's OpenAI-compatible /v1/models endpoint — used both by `synlynk local
    doctor` and (via network_deps in AGENT_CAPABILITY_BASELINES) by dispatch_agent()'s
    existing generic preflight reachability check. No local-specific preflight
    function is needed; see Step 9."""

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


class TestLocalDispatchModelFlags(unittest.TestCase):
    """The flags dispatch_agent() appends to the aider invocation, built from
    .agents/local.json's endpoint + selected model + that model's edit_format."""

    def test_builds_openai_base_model_and_edit_format_flags(self):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "local.json")
            with open(path, "w") as f:
                json.dump({
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [
                        {"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"},
                        {"id": "gemma-coder", "pinned": False, "edit_format": "diff"},
                    ],
                }, f)
            flags = local_agent._local_dispatch_model_flags(config_path=path)
        self.assertEqual(flags, [
            "--openai-api-base", "http://127.0.0.1:8080/v1",
            "--model", "ornith-1.0-9b",
            "--edit-format", "whole",
        ])

    def test_returns_empty_list_when_config_missing(self):
        flags = local_agent._local_dispatch_model_flags(config_path="/nonexistent/local.json")
        self.assertEqual(flags, [])


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
  "endpoint": "http://127.0.0.1:8080",
  "models": [
    {"id": "ornith-1.0-9b", "pinned": true, "edit_format": "whole"},
    {"id": "qwen-coder", "pinned": false, "edit_format": "whole"},
    {"id": "gemma-coder", "pinned": false, "edit_format": "diff"}
  ],
  "hardware_tier": "16gb-default"
}
```

`edit_format` is per-model (see design spec's "Architecture" section): `whole` for
models that struggle with clean unified diffs, `diff` for stronger models — read by
`_local_dispatch_model_flags()` (Step 4) to build the `aider --edit-format ...` flag.
There is no `max_concurrent` field here — Task Group 2's concurrency guard reads
`local_config.get("max_concurrent", 1)` from this same file with a default fallback, so
no schema addition is required in this task group; an operator can add the key later to
override the default of 1.

### Step 4: Create `synlynk/local_agent.py`

```python
"""synlynk local agent: config loading and oMLX reachability helpers for the
'local' dispatch agent. 'local' is dispatched as a real CLI subprocess (`aider`,
pointed at oMLX as an OpenAI-compatible backend) via the existing dispatch_agent()
machinery — this module owns only the config/flag-building helpers that invocation
needs, and the `synlynk local doctor` health-check command. It does not talk to
Aider or oMLX's chat-completions endpoint directly; Aider does that."""

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


def _pinned_model(config: dict) -> dict:
    """Returns the id of the pinned model, or the first roster entry if none pinned."""
    for m in config["models"]:
        if m.get("pinned"):
            return m["id"]
    return config["models"][0]["id"]


def _health_check(endpoint: str, timeout: int = 5) -> dict:
    """GETs {endpoint}/v1/models (oMLX's OpenAI-compatible model-list endpoint).
    Returns {reachable, available_models} or {reachable: False, error}."""
    req = urllib.request.Request(f"{endpoint}/v1/models", method="GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        return {"reachable": False, "error": str(exc)}
    available = [m.get("id") for m in payload.get("data", [])]
    return {"reachable": True, "available_models": available}


def _local_dispatch_model_flags(config_path: str = _DEFAULT_CONFIG_PATH) -> list:
    """Builds the --openai-api-base/--model/--edit-format flags for the aider
    subprocess from .agents/local.json. Returns [] if the config is missing —
    dispatch_agent()'s generic network_deps preflight (Step 9) already fails the
    job with an actionable oMLX-unreachable message before flags matter in that
    case, and _preflight_dispatch runs before _dispatch_flags_for_agent in
    dispatch_agent()'s call order, so an empty flags list here is never the
    reason a job fails silently."""
    try:
        config = _load_local_config(config_path)
    except FileNotFoundError:
        return []
    endpoint = config["endpoint"]
    model_id = _pinned_model(config)
    model_entry = next((m for m in config["models"] if m["id"] == model_id), {})
    edit_format = model_entry.get("edit_format", "whole")
    return [
        "--openai-api-base", f"{endpoint}/v1",
        "--model", model_id,
        "--edit-format", edit_format,
    ]


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
Expected: PASS (all 7 tests)

### Step 6: Register `local` in `AGENT_CAPABILITY_BASELINES`

Modify `synlynk/_constants.py`. The `AGENT_CAPABILITY_BASELINES` dict currently ends
with the `"grok"` entry (confirmed shape as of this rewrite — `cli`, `non_interactive_flags`,
`prompt_flag`, `prompt_via_arg`, `dispatch_flags` as a `{valid_flags, invalid_flags,
required_flags}` dict, `network_deps` as `{required_endpoints, optional_endpoints}`,
`roles`, `strengths`). Add immediately after `"grok"`'s closing `},`:

```python
    "local": {
        "cli": "aider",
        "non_interactive_flags": [],
        "dispatch_flags": ["--no-auto-commits", "--yes-always"],
        "prompt_file_flag": "--message-file",
        "network_deps": {
            "required_endpoints": ["127.0.0.1:8080"],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
    },
```

`dispatch_flags` here is a plain list (like `codex`'s shape elsewhere in the same dict),
not the `grok`-style dict — `_dispatch_flags_for_agent()` (Step 7) already handles both
shapes via its `isinstance(dispatch_flags, dict)` branch. `--no-auto-commits` stops Aider
from committing on every edit (the dispatch pipeline owns worktree commits itself, per
the design spec). `--yes-always` makes Aider non-interactive. `prompt_file_flag` is a new
baseline key, read by Step 8's cmd-assembly change — see there for why `local` needs a
new branch instead of reusing the existing `prompt_via_arg` one.

`network_deps.required_endpoints` reuses `_preflight_dispatch()`'s existing generic
TCP-reachability check (`synlynk/dispatch.py:555-571`, already used by `grok`'s
`cli-chat-proxy.grok.com:443` entry) — **no bespoke `_preflight_local()` function is
needed**, matching the design spec's "no special-case in `_dispatch_flags_for_agent()`
or `_permissions_to_flags()`" framing (that framing was about *permission* flags
specifically; the model/endpoint flags below are a separate, necessary addition since
they carry per-job config values the static baseline dict can't hold). If oMLX isn't
running, `_preflight_dispatch()` already returns a `HARNESS_PREFLIGHT_FAIL` sentinel with
a "Required endpoint '127.0.0.1:8080' unreachable for agent 'local'" reason — this is
less specific than "Start it with: omlx serve" (which only `cmd_local_doctor` prints),
but consistent with how every other agent's unreachable-dependency case is surfaced, and
avoids a parallel preflight code path to maintain.

### Step 7: Append dynamic model flags in `_dispatch_flags_for_agent()`

Modify `synlynk/dispatch.py:25-36` (`_dispatch_flags_for_agent`). The static
`dispatch_flags` baseline value (`["--no-auto-commits", "--yes-always"]` from Step 6)
covers Aider's non-interactive behavior, but `--openai-api-base`/`--model`/
`--edit-format` need config values from `.agents/local.json`, which isn't something a
static baseline dict can hold — hence a small per-agent addition, mirroring the existing
per-agent special-casing already present in `_permissions_to_flags()` just below it:

```python
def _dispatch_flags_for_agent(agent: str) -> list:
    """Return the executable dispatch flags for an agent baseline."""
    baselines_map = _pkg("AGENT_CAPABILITY_BASELINES", AGENT_CAPABILITY_BASELINES)
    baselines = baselines_map.get(agent, {})
    dispatch_flags = baselines.get("dispatch_flags", [])
    if isinstance(dispatch_flags, dict):
        ordered = []
        for flag in dispatch_flags.get("required_flags", []) or []:
            if flag not in ordered:
                ordered.append(flag)
        flags = ordered
    else:
        flags = list(dispatch_flags or [])
    if agent == "local":
        from synlynk.local_agent import _local_dispatch_model_flags
        flags = flags + _local_dispatch_model_flags()
    return flags
```

Only the `if agent == "local":` block and the `flags = ...` refactor (previously a bare
`return` per branch) are new; behavior for every other agent is unchanged.

### Step 8: Write failing test for the flag-assembly and cmd-string change

Create `tests/test_dispatch_local_agent.py`:

```python
"""Tests dispatch.py's local-agent-specific wiring: dynamic model flags appended
to the static baseline flags, and the new prompt_file_flag cmd-assembly branch
that passes the prompt via `aider --message-file <path>` instead of stdin (the
default branch other agents use) or an inline arg (the grok-style prompt_via_arg
branch) — Aider needs a file path, not inline text or a stdin stream, to receive
its one-shot task message non-interactively."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch

from synlynk import dispatch as dispatch_mod


class TestDispatchFlagsForLocalAgent(unittest.TestCase):
    @patch("synlynk.dispatch._pkg")
    def test_appends_dynamic_model_flags_for_local(self, mock_pkg):
        mock_pkg.return_value = {
            "local": {
                "dispatch_flags": ["--no-auto-commits", "--yes-always"],
            }
        }
        with tempfile.TemporaryDirectory() as d:
            config_path = os.path.join(d, "local.json")
            with open(config_path, "w") as f:
                json.dump({
                    "endpoint": "http://127.0.0.1:8080",
                    "models": [{"id": "ornith-1.0-9b", "pinned": True, "edit_format": "whole"}],
                }, f)
            with patch("synlynk.local_agent._DEFAULT_CONFIG_PATH", config_path):
                flags = dispatch_mod._dispatch_flags_for_agent("local")
        self.assertEqual(flags, [
            "--no-auto-commits", "--yes-always",
            "--openai-api-base", "http://127.0.0.1:8080/v1",
            "--model", "ornith-1.0-9b",
            "--edit-format", "whole",
        ])

    @patch("synlynk.dispatch._pkg")
    def test_other_agents_unaffected(self, mock_pkg):
        mock_pkg.return_value = {
            "codex": {"dispatch_flags": {"required_flags": ["--approval-policy"]}},
        }
        flags = dispatch_mod._dispatch_flags_for_agent("codex")
        self.assertEqual(flags, ["--approval-policy"])


if __name__ == "__main__":
    unittest.main()
```

### Step 9: Run to verify failure

Run: `pytest tests/test_dispatch_local_agent.py -v`
Expected: FAIL — `_dispatch_flags_for_agent` doesn't yet special-case `local` (Step 7
not applied), and no `prompt_file_flag` cmd branch exists yet (Step 10 not applied — the
second test above passes already since it only exercises the unaffected-codex path;
the first test fails).

### Step 10: Add the `prompt_file_flag` branch to `dispatch_agent()`'s cmd assembly

Modify `synlynk/dispatch.py:786-801` (inside `dispatch_agent()`, right after `prompt` is
written to `prompt_file`). The existing code has two branches — `prompt_via_arg` (grok:
inline text substituted into the command string) and the stdin-redirect default (codex/
agy/claude: `< prompt_file`). Aider needs neither — it takes a file path via
`--message-file`. Add a third branch, checked first:

```python
    import shlex as _shlex
    prompt_file_flag = baselines.get("prompt_file_flag")
    prompt_via_arg = baselines.get("prompt_via_arg", False)
    prompt_flag = baselines.get("prompt_flag")
    if prompt_file_flag:
        cmd_str = " ".join(
            _shlex.quote(c) for c in [cli] + flags + [prompt_file_flag, prompt_file]
        )
        shell_cmd = f"{cmd_str} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"
    elif prompt_via_arg:
        if prompt_flag:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags + [prompt_flag])
        else:
            cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = (
            f"PROMPT=$(cat {_shlex.quote(prompt_file)}); "
            f"{cmd_str} \"$PROMPT\" > {_shlex.quote(log_file)} 2>&1; "
            f"echo $? > {_shlex.quote(log_file)}.exit"
        )
    else:
        cmd_str = " ".join(_shlex.quote(c) for c in [cli] + flags)
        shell_cmd = f"{cmd_str} < {_shlex.quote(prompt_file)} > {_shlex.quote(log_file)} 2>&1; echo $? > {_shlex.quote(log_file)}.exit"
```

Only the `prompt_file_flag`/`if` branch and the reordered `elif`/`else` are new; the
`prompt_via_arg` and default-stdin branches are byte-for-byte unchanged from what's
already in `dispatch_agent()` today.

### Step 11: Run tests to verify pass

Run: `pytest tests/test_dispatch_local_agent.py -v`
Expected: PASS (2 tests)

### Step 12: Wire `synlynk local doctor` CLI command

Modify `synlynk/cli.py`. Find the `goal_parser` block (`subparsers.add_parser("goal", ...)`)
and add immediately after its block ends:

```python
    local_parser = subparsers.add_parser("local", help="Manage the local (oMLX) agent")
    local_sub = local_parser.add_subparsers(dest="local_action")
    local_sub.add_parser("doctor", help="Check oMLX endpoint reachability and model roster")
```

Find where `args.command` is dispatched to per-command handlers and add a matching
branch:

```python
    elif args.command == "local":
        from synlynk.local_agent import cmd_local_doctor
        if args.local_action == "doctor":
            sys.exit(cmd_local_doctor())
        else:
            local_parser.print_help()
```

### Step 13: Manual verification

Run: `python3 bin/synlynk.py local doctor`
Expected (no oMLX running): `✗ oMLX unreachable at http://127.0.0.1:8080: ...` and exit
code 1 — confirms the command wires up and fails cleanly without a live server.

### Step 14: Full test suite + commit

Run: `pytest tests/ -q --tb=short`
Expected: all tests pass, no regressions.

```bash
git add .agents/local.json synlynk/local_agent.py synlynk/_constants.py \
        synlynk/dispatch.py synlynk/cli.py \
        tests/test_local_agent.py tests/test_dispatch_local_agent.py
git commit -m "feat(local-agent): dispatch 'local' as an Aider subprocess over oMLX"
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

**Rewritten 2026-07-13** to exercise the real Aider-subprocess dispatch path (spawn
`aider` for real against a live oMLX instance, same code path `dispatch_agent()` uses in
production) instead of the original bespoke HTTP `_chat_completion()`/`local_agent_runner`
calls, which no longer exist after Task Group 1's rewrite.

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
"""Real-inference tests against a live oMLX instance + real Aider subprocess.
NOT run in standard CI — requires oMLX running locally (`omlx serve`) with the
.agents/local.json roster downloaded, and the `aider` CLI installed. Run explicitly:
`pytest tests/test_local_agent_hardware.py -m local_hardware -v`"""
import os
import subprocess
import tempfile
import unittest

import pytest

from synlynk.local_agent import (
    _load_local_config, _health_check, _pinned_model, _local_dispatch_model_flags,
)


@pytest.mark.local_hardware
class TestRealOmlxHealthCheck(unittest.TestCase):
    def setUp(self):
        self.config = _load_local_config()
        result = _health_check(self.config["endpoint"])
        if not result["reachable"]:
            self.skipTest(f"oMLX not reachable at {self.config['endpoint']} — start with `omlx serve`")

    def test_pinned_model_is_available(self):
        result = _health_check(self.config["endpoint"])
        pinned = _pinned_model(self.config)
        self.assertIn(pinned, result["available_models"])


@pytest.mark.local_hardware
class TestAiderSubprocessEndToEnd(unittest.TestCase):
    """Spawns the real `aider` CLI against the real oMLX endpoint, mirroring
    exactly what dispatch_agent() does for agent='local' in production (Task
    Group 1, Steps 7 and 10): static dispatch_flags + dynamic model flags,
    prompt delivered via --message-file, run inside a scratch git worktree
    (Aider requires a git repo to operate in)."""

    def setUp(self):
        self.config = _load_local_config()
        result = _health_check(self.config["endpoint"])
        if not result["reachable"]:
            self.skipTest(f"oMLX not reachable at {self.config['endpoint']} — start with `omlx serve`")

    def test_aider_edits_a_real_file(self):
        with tempfile.TemporaryDirectory() as d:
            subprocess.run(["git", "init", "-q"], cwd=d, check=True)
            subprocess.run(["git", "config", "user.email", "test@test.com"], cwd=d, check=True)
            subprocess.run(["git", "config", "user.name", "test"], cwd=d, check=True)
            target = os.path.join(d, "add.py")
            with open(target, "w") as f:
                f.write("# implement add(a, b) below\n")
            prompt_file = os.path.join(d, "prompt.txt")
            with open(prompt_file, "w") as f:
                f.write(
                    "In add.py, implement a function add(a, b) that returns a + b. "
                    "Only edit add.py."
                )
            flags = ["--no-auto-commits", "--yes-always"] + _local_dispatch_model_flags()
            proc = subprocess.run(
                ["aider"] + flags + ["--message-file", prompt_file, "add.py"],
                cwd=d, capture_output=True, text=True, timeout=180,
            )
            with open(target) as f:
                content = f.read()
        self.assertEqual(proc.returncode, 0)
        self.assertIn("def add", content)


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

### Step 4: Manual verification (if oMLX + aider are available locally)

Run: `pytest tests/test_local_agent_hardware.py -m local_hardware -v`
Expected: PASS if oMLX is running with the roster installed and `aider` is on `PATH`;
otherwise clean skips with the "oMLX not reachable" message, not errors.

### Step 5: Commit

```bash
git add pytest.ini tests/test_local_agent_hardware.py
git commit -m "test(local-agent): opt-in real-hardware Aider+oMLX inference tier"
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
- **Note (2026-07-13, consolidated rewrite):** Task Group 1 and Task Group 3 have been
  rewritten to match the Aider-over-oMLX architecture (Architecture section above,
  unchanged since the 2026-07-12 Fable-review revision). The rewrite was deliberately
  held until issues #189 (per-model cost accounting), #190 (dispatch queue unification),
  and #191 (capability router `discipline` fix) merged into `main` — all three landed
  2026-07-12 (PRs #193, #194, #195) — so this task group's design could build on the
  corrected `dispatch_agent()`/`_dispatch_flags_for_agent()` code paths instead of the
  pre-fix versions. One concrete benefit of waiting: #189 already added a
  `_model_rate_for_version(model_version, agent=...)` override that forces zero cost for
  any `agent == "local"` job regardless of model — Task Group 1's original "add rate-table
  rows" step is now redundant and was removed. `local` is now dispatched as a real `aider`
  CLI subprocess (no bespoke HTTP driver, no `local_agent_runner.py`), reusing the
  existing worktree/log-polling/reconciliation pipeline with two small, additive changes
  to `dispatch.py`: a per-agent branch in `_dispatch_flags_for_agent()` for dynamic
  `--openai-api-base`/`--model`/`--edit-format` flags, and a new `prompt_file_flag`
  cmd-assembly branch (alongside the existing `prompt_via_arg` and stdin-default
  branches) so Aider receives its task via `--message-file` instead of stdin or an inline
  arg. **Task Group 1 and Task Group 3 are ready to dispatch.**
- **Type consistency:** `_load_local_config`, `_pinned_model`, `_health_check`,
  `_local_dispatch_model_flags` are defined once in `synlynk/local_agent.py` (Task Group
  1, Step 4) and imported by name into `dispatch.py`'s `_dispatch_flags_for_agent()`,
  `local_agent_seed.py`'s doctor wiring, and all three test files — no redefinition or
  signature drift across groups.
- **PR discipline:** each task group is its own branch/worktree/PR per this repo's
  global git workflow (`feat/local-agent-<n>-<slug>`), matching the spec's 4-PR sequence.
