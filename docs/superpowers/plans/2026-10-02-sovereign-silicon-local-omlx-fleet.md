# v0.25.0 Sovereign Silicon — Local oMLX Fleet Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete, validate, and harden the local oMLX harness so `synlynk dispatch local` works reliably on Apple Silicon, expand the model roster to all three downloaded models, add hardware-tier-aware doctor, tier-0 auto-routing, an Orb Stack Docker image, and an OpenRouter config preview.

**Architecture:** `local` is dispatched as an Aider CLI subprocess over oMLX's OpenAI-compatible API — identical lifecycle to `agy`/`codex`/`grok` in `dispatch_agent()`. New work is additive: `_detect_hardware_tier()` in `local_agent.py`, `_resolve_dispatch_agent()` in `dispatch.py`, `gateway.py` (new), and `docker/Dockerfile.sovereign` (new). No existing dispatch path is altered for non-`local`/`auto` agents.

**Tech Stack:** Python 3 stdlib only for new synlynk code (`subprocess`, `urllib.request`, `importlib.util`). Aider-chat (external CLI, not vendored). oMLX (local inference server). Docker multi-stage build. pytest + `unittest.mock`.

**Spec:** `docs/superpowers/specs/2026-10-02-sovereign-silicon-local-omlx-fleet-design.md`

## Global Constraints

- Python 3.10 minimum — no `match`, no `tomllib`, no `3.11+`-only stdlib features
- No new pip dependencies in `synlynk` core — use stdlib only (`subprocess`, `urllib`, `importlib.util`, `json`, `os`)
- All tests must pass with `pytest -m "not local_hardware"` on Linux and macOS without a real oMLX or Aider instance
- `aider` and `prism-ml` are external tools — check with `shutil.which` / `importlib.util.find_spec`, never import
- Never modify `.synlynk/config.json` fields that already exist — only add missing keys with defaults
- Branch pattern: `feat/agy/v025-<tg-name>` per task group
- Commit trailer: `Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>` (Codex: `Co-Authored-By: Codex <noreply@openai.com>`, Grok: `Co-Authored-By: Grok <noreply@x.ai>`)
- `synlynk dispatch` for all code implementation — no inline code edits by orchestrator

---

## Task Group 1: Live End-to-End Validation (Manual — Hard Gate)

**This is a manual operator step, not a dispatch job. All subsequent task groups are blocked until this passes.**

**Files:** None created or modified.

**What to do:**

- [ ] **Step 1: Confirm oMLX is running and authenticated**

```bash
export OPENAI_API_KEY=<your-key-from-~/.omlx/settings.json>
synlynk local doctor
```

Expected output includes `✓ oMLX reachable` and `✓ Ornith-1.0-9B-4bit` in roster.
If you see `401 Unauthorized`, set `OPENAI_API_KEY` from oMLX's own settings file.

- [ ] **Step 2: Run a minimal live dispatch**

```bash
synlynk story create --title "TG1 validation: add docstring to _pinned_model" \
  --label testing --id story-v025-validate-01

synlynk dispatch local \
  --task "Add a one-line docstring to the _pinned_model() function in synlynk/local_agent.py. The docstring should read: \"Returns the pinned model id, or the first roster entry if no model is pinned.\" Make only this change." \
  --story story-v025-validate-01
```

- [ ] **Step 3: Verify the result — read the log directly, do not trust job status alone**

```bash
synlynk logs --job <job-id-from-step-2> --tail 50
```

Expected: log shows Aider producing a real `diff` hunk adding the docstring. `files_touched >= 1`.

If the log shows `litellm.BadRequestError` → the `openai/` prefix fix didn't apply; check `local_agent.py:_local_dispatch_model_flags()`.
If the log shows destructive whole-file rewrites → the `edit_format` is still `whole`; check `.agents/local.json`.
If the log shows `exit 0` but `files_touched == 0` → Aider ran but did nothing; read Aider's own log lines before concluding.

- [ ] **Step 4: Gate check**

If Step 3 confirms a real file edit was produced: ✅ proceed to Task Group 2.
If it failed: diagnose, fix, and re-run Step 2 before proceeding. File a bug issue for any root cause found.

---

## Task Group 2: Roster Expansion + Ternary-Bonsai Loader Detection

**Dispatch via:** `synlynk dispatch codex`
**Branch:** `feat/agy/v025-tg2-roster`

**Files:**
- Modify: `.agents/local.json`
- Modify: `synlynk/local_agent.py` — add `_check_prism_ml_available()`, extend `cmd_local_doctor()`
- Modify: `tests/test_local_agent.py` — add loader detection tests

**Interfaces:**
- Produces: `_check_prism_ml_available() -> bool` (used by TG-3's `_detect_hardware_tier` to determine `32gb-pro` pin)
- Produces: updated `.agents/local.json` schema with `"loader"` and `"tier"` fields per model, top-level `"pinned_model"` key

### Task 2.1 — Write failing tests for loader detection and new schema

- [ ] **Step 1: Write failing tests**

Add to `tests/test_local_agent.py`:

```python
import importlib.util
from unittest.mock import patch


class TestPrismMlCheck(unittest.TestCase):
    def test_returns_true_when_prism_ml_importable(self):
        with patch("importlib.util.find_spec", return_value=object()):
            from synlynk.local_agent import _check_prism_ml_available
            self.assertTrue(_check_prism_ml_available())

    def test_returns_false_when_prism_ml_missing(self):
        with patch("importlib.util.find_spec", return_value=None):
            from synlynk.local_agent import _check_prism_ml_available
            self.assertFalse(_check_prism_ml_available())


class TestNewRosterSchema(unittest.TestCase):
    def test_pinned_model_top_level_key_used_when_present(self):
        config = {
            "endpoint": "http://127.0.0.1:8000",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": False, "edit_format": "diff"},
            ],
            "pinned_model": "Ornith-1.0-9B-4bit",
        }
        from synlynk.local_agent import _pinned_model
        self.assertEqual(_pinned_model(config), "Ornith-1.0-9B-4bit")

    def test_falls_back_to_model_pinned_field_when_top_level_absent(self):
        config = {
            "endpoint": "http://127.0.0.1:8000",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": True, "edit_format": "diff"},
            ],
        }
        from synlynk.local_agent import _pinned_model
        self.assertEqual(_pinned_model(config), "Ornith-1.0-9B-4bit")

    def test_bonsai_excluded_from_dispatch_flags_when_prism_ml_absent(self):
        """When prism-ml is missing and bonsai is pinned_model, flags builder
        must fall back to the first non-loader-gated model."""
        config = {
            "endpoint": "http://127.0.0.1:8000",
            "pinned_model": "Ternary-Bonsai-2-27B-mlx-2bit",
            "models": [
                {"id": "Ornith-1.0-9B-4bit", "pinned": False, "edit_format": "diff"},
                {
                    "id": "Ternary-Bonsai-2-27B-mlx-2bit",
                    "pinned": False,
                    "edit_format": "diff",
                    "loader": "prism-ml",
                },
            ],
        }
        import tempfile, json
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(config, f)
            path = f.name
        with patch("importlib.util.find_spec", return_value=None):
            from synlynk.local_agent import _local_dispatch_model_flags
            flags = _local_dispatch_model_flags(config_path=path)
        # Must fall back to Ornith, not Bonsai
        self.assertIn("openai/Ornith-1.0-9B-4bit", flags)
        self.assertNotIn("openai/Ternary-Bonsai-2-27B-mlx-2bit", flags)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/test_local_agent.py::TestPrismMlCheck \
       tests/test_local_agent.py::TestNewRosterSchema -v
```

Expected: `ImportError` or `AttributeError` — `_check_prism_ml_available` does not exist yet.

### Task 2.2 — Implement `_check_prism_ml_available()` and update `_pinned_model()` + `_local_dispatch_model_flags()`

- [ ] **Step 3: Add `_check_prism_ml_available()` to `synlynk/local_agent.py`**

Add after the existing imports block (after `from synlynk import _get_db`):

```python
import importlib.util


def _check_prism_ml_available() -> bool:
    """Returns True if the prism-ml package is importable (needed for Ternary-Bonsai)."""
    return importlib.util.find_spec("prism_ml") is not None
```

- [ ] **Step 4: Update `_pinned_model()` to respect top-level `pinned_model` key**

Replace the existing `_pinned_model()` function body (currently iterates `config["models"]` looking for `model.get("pinned")`):

```python
def _pinned_model(config: dict) -> str:
    """Returns the pinned model id.

    Checks top-level 'pinned_model' key first (new schema), then falls back
    to the per-model 'pinned': true field (legacy schema). Returns first
    roster entry if neither is set.
    """
    if "pinned_model" in config:
        return config["pinned_model"]
    for model in config["models"]:
        if model.get("pinned"):
            return model["id"]
    return config["models"][0]["id"]
```

- [ ] **Step 5: Update `_local_dispatch_model_flags()` to skip loader-gated models when loader is absent**

In `_local_dispatch_model_flags()`, after resolving `model_id = _pinned_model(config)`, add a loader check before building flags:

```python
def _local_dispatch_model_flags(config_path: str = None) -> list:
    """Builds aider model flags from .agents/local.json.

    Skips models that require a custom loader (e.g. prism-ml) if that
    loader is not installed, falling back to the first loader-free model.
    Always appends Starter-tier safety guardrails.
    """
    try:
        if config_path is None:
            config_path = _DEFAULT_CONFIG_PATH
        config = _load_local_config(config_path)
    except FileNotFoundError:
        return []
    endpoint = config["endpoint"]
    model_id = _pinned_model(config)

    # Resolve the model entry; if it needs a loader that's absent, fall back.
    def _entry_for(mid):
        return next((m for m in config["models"] if m["id"] == mid), {})

    entry = _entry_for(model_id)
    if entry.get("loader") == "prism-ml" and not _check_prism_ml_available():
        # Fall back to first model without a loader requirement
        fallback = next(
            (m for m in config["models"] if not m.get("loader")), None
        )
        if fallback is None:
            return []  # no dispatch-eligible model available
        model_id = fallback["id"]
        entry = fallback

    edit_format = entry.get("edit_format", "diff")
    return [
        "--openai-api-base", f"{endpoint}/v1",
        "--model", f"openai/{model_id}",
        "--edit-format", edit_format,
    ] + _STARTER_TIER_GUARDRAIL_FLAGS
```

- [ ] **Step 6: Update `.agents/local.json` with full three-model roster**

```json
{
  "name": "local",
  "endpoint": "http://127.0.0.1:8000",
  "models": [
    {
      "id": "Ornith-1.0-9B-4bit",
      "pinned": false,
      "edit_format": "diff",
      "tier": ["8gb-light", "16gb-default"]
    },
    {
      "id": "Qwen3.6-27B-4bit",
      "pinned": false,
      "edit_format": "whole",
      "tier": ["64gb-fleet"]
    },
    {
      "id": "Ternary-Bonsai-2-27B-mlx-2bit",
      "pinned": false,
      "edit_format": "diff",
      "loader": "prism-ml",
      "tier": ["32gb-pro", "64gb-fleet"]
    }
  ],
  "hardware_tier": "32gb-pro",
  "pinned_model": "Ternary-Bonsai-2-27B-mlx-2bit",
  "max_concurrent": 1
}
```

- [ ] **Step 7: Extend `cmd_local_doctor()` to report loader status per model**

In `cmd_local_doctor()`, replace the existing roster-check loop:

```python
    roster_ids = [model["id"] for model in config["models"]]
    available = set(result["available_models"])
    missing = [mid for mid in roster_ids if mid not in available]
    for model in config["models"]:
        mid = model["id"]
        in_roster = mid not in missing
        loader = model.get("loader")
        loader_ok = True
        loader_note = ""
        if loader == "prism-ml":
            loader_ok = _check_prism_ml_available()
            loader_note = " [prism-ml: ✓]" if loader_ok else " [prism-ml: ✗ — pip install prism-ml]"
        mark = "✓" if (in_roster and loader_ok) else ("⚠" if in_roster else "✗")
        print(f"  {mark} {mid}{loader_note}")
    if missing:
        print(f"    Missing from oMLX roster: {', '.join(missing)}")
```

- [ ] **Step 8: Run tests to confirm PASS**

```bash
pytest tests/test_local_agent.py -v
```

Expected: all tests pass including the three new ones.

- [ ] **Step 9: Run the full suite to confirm no regressions**

```bash
pytest tests/ -m "not local_hardware" -n 4 --dist loadfile -q
```

Expected: all pass.

- [ ] **Step 10: Commit**

```bash
git add .agents/local.json synlynk/local_agent.py tests/test_local_agent.py
git commit -m "feat(local): three-model roster, prism-ml loader detection, pinned_model schema

- Add Qwen3.6-27B-4bit and Ternary-Bonsai-2-27B-mlx-2bit to .agents/local.json
- _check_prism_ml_available() guards Bonsai dispatch when loader absent
- _pinned_model() prefers top-level pinned_model key (backward-compatible)
- _local_dispatch_model_flags() falls back to loader-free model when needed
- cmd_local_doctor() reports per-model loader status

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task Group 3: Hardware Tier Prober + `doctor --init`

**Dispatch via:** `synlynk dispatch codex`
**Branch:** `feat/agy/v025-tg3-hw-tier`
**Depends on:** TG-2 (uses `_check_prism_ml_available()` from TG-2)

**Files:**
- Modify: `synlynk/local_agent.py` — add `_detect_hardware_tier()`, `_select_model_for_tier()`, extend `cmd_local_doctor()`
- Modify: `tests/test_local_agent.py` — hardware tier detection tests

**Interfaces:**
- Consumes: `_check_prism_ml_available() -> bool` (TG-2)
- Produces: `_detect_hardware_tier() -> str` — one of `"8gb-light"`, `"16gb-default"`, `"32gb-pro"`, `"64gb-fleet"`
- Produces: `_select_model_for_tier(tier: str, config: dict) -> str` — model id for the tier

### Task 3.1 — Write failing tests

- [ ] **Step 1: Write failing tests**

Add to `tests/test_local_agent.py`:

```python
class TestDetectHardwareTier(unittest.TestCase):
    def _run_with_ram(self, ram_bytes):
        """Helper: mock platform RAM detection to return ram_bytes."""
        import sys
        with patch("subprocess.check_output", return_value=str(ram_bytes).encode()):
            # Force macOS path regardless of test runner OS
            with patch("sys.platform", "darwin"):
                from synlynk.local_agent import _detect_hardware_tier
                return _detect_hardware_tier()

    def test_under_12gb_returns_8gb_light(self):
        self.assertEqual(self._run_with_ram(8 * 1024**3), "8gb-light")

    def test_16gb_returns_16gb_default(self):
        self.assertEqual(self._run_with_ram(16 * 1024**3), "16gb-default")

    def test_24gb_returns_32gb_pro(self):
        self.assertEqual(self._run_with_ram(24 * 1024**3), "32gb-pro")

    def test_64gb_returns_64gb_fleet(self):
        self.assertEqual(self._run_with_ram(64 * 1024**3), "64gb-fleet")

    def test_linux_reads_meminfo(self):
        meminfo = "MemTotal:       25165824 kB\nMemFree: 1000 kB\n"
        with patch("builtins.open", unittest.mock.mock_open(read_data=meminfo)):
            with patch("sys.platform", "linux"):
                from synlynk.local_agent import _detect_hardware_tier
                result = _detect_hardware_tier()
        self.assertEqual(result, "32gb-pro")  # 24 GB


class TestSelectModelForTier(unittest.TestCase):
    CONFIG = {
        "models": [
            {"id": "Ornith-1.0-9B-4bit", "edit_format": "diff",
             "tier": ["8gb-light", "16gb-default"]},
            {"id": "Qwen3.6-27B-4bit", "edit_format": "whole",
             "tier": ["64gb-fleet"]},
            {"id": "Ternary-Bonsai-2-27B-mlx-2bit", "edit_format": "diff",
             "loader": "prism-ml", "tier": ["32gb-pro", "64gb-fleet"]},
        ]
    }

    def test_32gb_pro_returns_bonsai_when_loader_present(self):
        with patch("importlib.util.find_spec", return_value=object()):
            from synlynk.local_agent import _select_model_for_tier
            result = _select_model_for_tier("32gb-pro", self.CONFIG)
        self.assertEqual(result, "Ternary-Bonsai-2-27B-mlx-2bit")

    def test_32gb_pro_falls_back_to_ornith_when_loader_absent(self):
        with patch("importlib.util.find_spec", return_value=None):
            from synlynk.local_agent import _select_model_for_tier
            result = _select_model_for_tier("32gb-pro", self.CONFIG)
        self.assertEqual(result, "Ornith-1.0-9B-4bit")

    def test_8gb_light_returns_ornith(self):
        from synlynk.local_agent import _select_model_for_tier
        result = _select_model_for_tier("8gb-light", self.CONFIG)
        self.assertEqual(result, "Ornith-1.0-9B-4bit")
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/test_local_agent.py::TestDetectHardwareTier \
       tests/test_local_agent.py::TestSelectModelForTier -v
```

Expected: `ImportError` — `_detect_hardware_tier` and `_select_model_for_tier` do not exist.

### Task 3.2 — Implement hardware tier detection

- [ ] **Step 3: Add `_detect_hardware_tier()` and `_select_model_for_tier()` to `synlynk/local_agent.py`**

Add after `_check_prism_ml_available()`:

```python
import sys
import subprocess as _subprocess


_TIER_THRESHOLDS = [
    (12 * 1024**3, "8gb-light"),
    (20 * 1024**3, "16gb-default"),
    (48 * 1024**3, "32gb-pro"),
    (float("inf"), "64gb-fleet"),
]


def _detect_hardware_tier() -> str:
    """Detects RAM and returns the hardware tier name.

    Uses sysctl on macOS and /proc/meminfo on Linux.
    Returns '16gb-default' on any detection failure.
    """
    try:
        if sys.platform == "darwin":
            raw = _subprocess.check_output(
                ["sysctl", "-n", "hw.memsize"], timeout=5
            )
            ram_bytes = int(raw.strip())
        else:
            with open("/proc/meminfo") as f:
                for line in f:
                    if line.startswith("MemTotal:"):
                        kb = int(line.split()[1])
                        ram_bytes = kb * 1024
                        break
                else:
                    return "16gb-default"
    except Exception:
        return "16gb-default"

    for threshold, tier in _TIER_THRESHOLDS:
        if ram_bytes < threshold:
            return tier
    return "64gb-fleet"


def _select_model_for_tier(tier: str, config: dict) -> str:
    """Returns the best model id for the given hardware tier.

    Prefers the first model whose 'tier' list includes the given tier.
    Skips loader-gated models when the loader is unavailable.
    Falls back to the first model with no tier restriction.
    """
    candidates = [
        m for m in config["models"]
        if tier in m.get("tier", [])
    ]
    # Filter out unavailable loaders
    eligible = [
        m for m in candidates
        if not (m.get("loader") == "prism-ml" and not _check_prism_ml_available())
    ]
    if eligible:
        return eligible[0]["id"]
    # Fallback: first model with no loader requirement
    fallback = next((m for m in config["models"] if not m.get("loader")), None)
    if fallback:
        return fallback["id"]
    return config["models"][0]["id"]
```

### Task 3.3 — Add `--init` flag to `cmd_local_doctor()`

- [ ] **Step 4: Update `cmd_local_doctor()` signature and add `--init` logic**

Update `cmd_local_doctor()` to accept `init: bool = False`:

```python
def cmd_local_doctor(config_path: str = None, init: bool = False) -> int:
    """Prints oMLX reachability plus roster status.

    With init=True: also detects hardware tier, selects the best model,
    and writes 'hardware_tier' and 'pinned_model' back to config_path.
    Returns 0 if healthy, 1 otherwise.
    """
```

At the point where the endpoint check passes and before the roster loop, add:

```python
    tier = _detect_hardware_tier()
    best_model = _select_model_for_tier(tier, config)
    print(f"  ✓ hardware tier: {tier}")
    print(f"  ✓ recommended model: {best_model}")

    if init:
        config["hardware_tier"] = tier
        config["pinned_model"] = best_model
        write_path = config_path or _DEFAULT_CONFIG_PATH
        with open(write_path, "w") as f:
            json.dump(config, f, indent=2)
        print(f"  ✓ wrote hardware_tier={tier!r} and pinned_model={best_model!r} to {write_path}")
```

- [ ] **Step 5: Wire `--init` in `synlynk/cli.py`**

Find the `synlynk local doctor` subcommand parser (search for `local_doctor` or `cmd_local_doctor` in `cli.py`). Add:

```python
local_doctor_parser.add_argument(
    "--init",
    action="store_true",
    default=False,
    help="Detect hardware tier and write pinned_model to .agents/local.json",
)
```

In the dispatch for `local doctor`, pass `init=args.init` to `cmd_local_doctor()`.

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_local_agent.py -v
```

Expected: all pass.

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -m "not local_hardware" -n 4 --dist loadfile -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add synlynk/local_agent.py synlynk/cli.py tests/test_local_agent.py
git commit -m "feat(local): hardware tier prober and doctor --init

_detect_hardware_tier() reads sysctl/meminfo to classify RAM tier.
_select_model_for_tier() picks best model respecting prism-ml gate.
cmd_local_doctor(init=True) writes hardware_tier + pinned_model back to
.agents/local.json.
synlynk local doctor --init flag wired in cli.py.

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task Group 4: Tier-0 Zero-Trust Auto-Routing

**Dispatch via:** `synlynk dispatch codex`
**Branch:** `feat/agy/v025-tg4-auto-routing`
**Depends on:** TG-3 (uses `_detect_hardware_tier`, config keys written by `doctor --init`)

**Files:**
- Modify: `synlynk/dispatch.py` — add `_resolve_dispatch_agent()`
- Modify: `synlynk/cli.py` — wire `synlynk dispatch auto`
- Create: `tests/test_dispatch_auto_routing.py`

**Interfaces:**
- Consumes: `_preflight_local(silent=True)` — existing function in `local_agent.py`; add `silent` kwarg that suppresses print output and returns a result object (or raises). If `_preflight_local` does not support `silent`, add the kwarg with `silent=False` default (no behaviour change for existing callers).
- Produces: `_resolve_dispatch_agent(requested_agent: str | None, task_type: str, db) -> str`

### Task 4.1 — Write failing tests

- [ ] **Step 1: Create `tests/test_dispatch_auto_routing.py`**

```python
"""Tests for _resolve_dispatch_agent() — tier-0 zero-trust auto-routing."""
import unittest
from unittest.mock import patch, MagicMock


class TestResolveDispatchAgent(unittest.TestCase):
    def _resolve(self, requested, task_type="testing", preflight_ok=True, cap_score=0.8):
        import synlynk.dispatch as dispatch_mod
        mock_db = MagicMock()
        with patch.object(dispatch_mod, "_preflight_local_silent",
                          return_value=preflight_ok):
            with patch.object(dispatch_mod, "_get_local_capability_score",
                              return_value=cap_score):
                with patch.object(dispatch_mod, "_read_local_fallback",
                                  return_value="agy"):
                    with patch.object(dispatch_mod, "_read_local_threshold",
                                      return_value=0.5):
                        return dispatch_mod._resolve_dispatch_agent(
                            requested, task_type, mock_db
                        )

    def test_explicit_agent_bypasses_routing(self):
        self.assertEqual(self._resolve("agy"), "agy")

    def test_explicit_local_bypasses_routing(self):
        self.assertEqual(self._resolve("local"), "local")

    def test_auto_routes_to_local_when_healthy_and_capable(self):
        self.assertEqual(self._resolve("auto", preflight_ok=True, cap_score=0.8), "local")

    def test_auto_routes_to_fallback_when_local_unhealthy(self):
        self.assertEqual(self._resolve("auto", preflight_ok=False, cap_score=0.9), "agy")

    def test_auto_routes_to_fallback_when_cap_below_threshold(self):
        self.assertEqual(self._resolve("auto", preflight_ok=True, cap_score=0.3), "agy")

    def test_none_agent_routes_to_fallback(self):
        # None means no explicit agent; treat as auto for now
        result = self._resolve(None, preflight_ok=True, cap_score=0.9)
        self.assertIn(result, ("local", "agy"))  # must return a valid agent string

    def test_auto_prints_routing_decision(self):
        import io, sys
        captured = io.StringIO()
        with patch("sys.stdout", captured):
            self._resolve("auto", preflight_ok=True, cap_score=0.72)
        output = captured.getvalue()
        self.assertIn("Routing to:", output)
        self.assertIn("local", output)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/test_dispatch_auto_routing.py -v
```

Expected: `ImportError` — `_resolve_dispatch_agent` not in `dispatch.py`.

### Task 4.2 — Implement `_resolve_dispatch_agent()`

- [ ] **Step 3: Add helper functions and `_resolve_dispatch_agent()` to `synlynk/dispatch.py`**

Add near the top of `dispatch.py`, after the existing imports:

```python
def _preflight_local_silent(config_path=None) -> bool:
    """Returns True if the local oMLX endpoint is reachable, False otherwise.
    Does not print anything. Used by auto-routing."""
    try:
        from synlynk.local_agent import _load_local_config, _health_check
        import os
        cfg = _load_local_config(config_path)
        api_key = os.environ.get("OPENAI_API_KEY")
        result = _health_check(cfg["endpoint"], timeout=3, api_key=api_key)
        return result.get("reachable", False)
    except Exception:
        return False


def _get_local_capability_score(task_type: str, db) -> float:
    """Returns the local agent's capability score for the given task_type.
    Returns 0.0 if not found."""
    try:
        row = db.execute(
            "SELECT score FROM capability_scores "
            "WHERE agent='local' AND task_type=? ORDER BY recorded_at DESC LIMIT 1",
            (task_type,)
        ).fetchone()
        return float(row[0]) if row else 0.0
    except Exception:
        return 0.0


def _read_local_fallback(config_path=".synlynk/config.json") -> str:
    """Reads local_fallback from .synlynk/config.json, defaults to 'agy'."""
    import json, os
    try:
        with open(config_path) as f:
            return json.load(f).get("local_fallback", "agy")
    except Exception:
        return "agy"


def _read_local_threshold(config_path=".synlynk/config.json") -> float:
    """Reads local_auto_threshold from .synlynk/config.json, defaults to 0.5."""
    import json
    try:
        with open(config_path) as f:
            return float(json.load(f).get("local_auto_threshold", 0.5))
    except Exception:
        return 0.5


def _resolve_dispatch_agent(
    requested_agent,
    task_type: str,
    db,
    config_path: str = ".synlynk/config.json",
) -> str:
    """Resolves which agent to use for a dispatch.

    If requested_agent is not 'auto' (and not None), returns it unchanged.
    For 'auto': checks local health and capability score; routes to local
    if healthy and capable, otherwise routes to the configured fallback.
    """
    if requested_agent is not None and requested_agent != "auto":
        return requested_agent

    fallback = _read_local_fallback(config_path)
    threshold = _read_local_threshold(config_path)

    if not _preflight_local_silent():
        print(f"Routing to: {fallback} (local oMLX unreachable)")
        return fallback

    cap = _get_local_capability_score(task_type, db)
    if cap >= threshold:
        print(f"Routing to: local (tier-0, capability score: {cap:.2f})")
        return "local"
    else:
        print(f"Routing to: {fallback} (local capability score {cap:.2f} < threshold {threshold:.2f})")
        return fallback
```

- [ ] **Step 4: Wire `auto` into `synlynk/cli.py` dispatch subcommand**

Find where `synlynk dispatch <agent>` is parsed in `cli.py`. The agent argument is likely a positional or `--agent` flag. Add `"auto"` to the list of valid agent choices (or to the help text if it's free-form). Then in the dispatch handler, before calling `dispatch_agent()`, resolve the agent:

```python
# In the dispatch command handler, before calling dispatch_agent():
if args.agent == "auto" or args.agent is None:
    from synlynk.dispatch import _resolve_dispatch_agent
    db = _get_db()
    args.agent = _resolve_dispatch_agent(
        args.agent, getattr(args, "task_type", "testing"), db
    )
```

- [ ] **Step 5: Add default config keys to `synlynk init` config writer**

Find the function that writes the initial `.synlynk/config.json` (search for `"local_fallback"` or the config writer in `synlynk/__init__.py` or `synlynk/init_cmd.py`). Add these keys if not already present:

```python
config.setdefault("local_auto_threshold", 0.5)
config.setdefault("local_fallback", "agy")
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_dispatch_auto_routing.py -v
```

Expected: all pass.

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -m "not local_hardware" -n 4 --dist loadfile -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_dispatch_auto_routing.py
git commit -m "feat(dispatch): tier-0 zero-trust auto-routing via synlynk dispatch auto

_resolve_dispatch_agent() checks local health + capability score.
Routes to local if healthy and cap >= 0.5 (configurable).
Falls back to local_fallback (default: agy) otherwise.
synlynk dispatch auto wired in cli.py.
local_auto_threshold + local_fallback added to init config defaults.

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task Group 5: OpenRouter Config Preview + `synlynk gateway probe`

**Dispatch via:** `synlynk dispatch codex`
**Branch:** `feat/agy/v025-tg5-gateway-preview`
**Depends on:** TG-4 (independent — can overlap if desired, but sequential is safer)

**Files:**
- Create: `synlynk/gateway.py`
- Modify: `synlynk/cli.py` — wire `synlynk gateway probe`
- Modify: `synlynk/registry.py` (or wherever `registry.json` is read/written) — add `gateways` schema
- Create: `tests/test_gateway.py`

**Interfaces:**
- Produces: `cmd_gateway_probe(gateway: str | None, config_path: str) -> int`
- Produces: `_read_gateway_config(config_path: str) -> dict` — returns the `"gateways"` dict from registry.json

### Task 5.1 — Write failing tests

- [ ] **Step 1: Create `tests/test_gateway.py`**

```python
"""Tests for synlynk.gateway — gateway probe command and registry schema."""
import json
import os
import tempfile
import unittest
from unittest.mock import patch, MagicMock


class TestReadGatewayConfig(unittest.TestCase):
    def _write_registry(self, content):
        d = tempfile.mkdtemp()
        path = os.path.join(d, "registry.json")
        with open(path, "w") as f:
            json.dump(content, f)
        return path

    def test_returns_gateways_dict(self):
        path = self._write_registry({
            "gateways": {"openrouter": {"enabled": True, "base_url": "https://openrouter.ai/api/v1",
                                         "api_key_env": "OPENROUTER_API_KEY", "models": []}}
        })
        from synlynk.gateway import _read_gateway_config
        result = _read_gateway_config(path)
        self.assertIn("openrouter", result)

    def test_returns_empty_dict_when_no_gateways_key(self):
        path = self._write_registry({"products": {}})
        from synlynk.gateway import _read_gateway_config
        result = _read_gateway_config(path)
        self.assertEqual(result, {})

    def test_returns_empty_dict_on_missing_file(self):
        from synlynk.gateway import _read_gateway_config
        result = _read_gateway_config("/nonexistent/registry.json")
        self.assertEqual(result, {})


class TestGatewayProbe(unittest.TestCase):
    REGISTRY = {
        "gateways": {
            "openrouter": {
                "enabled": True,
                "base_url": "https://openrouter.ai/api/v1",
                "api_key_env": "OPENROUTER_API_KEY",
                "models": []
            }
        }
    }

    def _probe(self, registry_content, env=None, gateway=None, mock_response=None):
        with tempfile.TemporaryDirectory() as d:
            path = os.path.join(d, "registry.json")
            with open(path, "w") as f:
                json.dump(registry_content, f)
            env = env or {}
            with patch.dict(os.environ, env, clear=False):
                if mock_response is not None:
                    import urllib.request
                    mock_resp = MagicMock()
                    mock_resp.read.return_value = json.dumps(mock_response).encode()
                    mock_resp.__enter__ = lambda s: s
                    mock_resp.__exit__ = MagicMock(return_value=False)
                    with patch("urllib.request.urlopen", return_value=mock_resp):
                        from synlynk.gateway import cmd_gateway_probe
                        return cmd_gateway_probe(gateway=gateway, config_path=path)
                else:
                    from synlynk.gateway import cmd_gateway_probe
                    return cmd_gateway_probe(gateway=gateway, config_path=path)

    def test_returns_0_when_reachable(self):
        mock_data = {"data": [{"id": "model-a"}, {"id": "model-b"}]}
        result = self._probe(self.REGISTRY, env={"OPENROUTER_API_KEY": "test-key"},
                             mock_response=mock_data)
        self.assertEqual(result, 0)

    def test_returns_1_when_api_key_missing(self):
        # Remove key from env
        with patch.dict(os.environ, {}, clear=True):
            from synlynk.gateway import cmd_gateway_probe
            import tempfile, json as j2
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                j2.dump(self.REGISTRY, f)
                path = f.name
            result = cmd_gateway_probe(gateway="openrouter", config_path=path)
        self.assertEqual(result, 1)

    def test_returns_0_when_gateway_disabled(self):
        registry = {"gateways": {"openrouter": {"enabled": False,
                                                  "base_url": "https://x.ai",
                                                  "api_key_env": "X_KEY", "models": []}}}
        result = self._probe(registry)
        self.assertEqual(result, 0)  # disabled gateways: no error, just skipped

    def test_filters_by_gateway_name(self):
        registry = {
            "gateways": {
                "openrouter": {"enabled": True, "base_url": "https://or.ai/api/v1",
                               "api_key_env": "OR_KEY", "models": []},
                "other": {"enabled": True, "base_url": "https://other.ai/api/v1",
                          "api_key_env": "OTHER_KEY", "models": []},
            }
        }
        mock_data = {"data": [{"id": "m1"}]}
        # Probe only openrouter; other should not be called
        with patch("urllib.request.urlopen") as mock_open:
            mock_resp = MagicMock()
            mock_resp.read.return_value = json.dumps(mock_data).encode()
            mock_resp.__enter__ = lambda s: s
            mock_resp.__exit__ = MagicMock(return_value=False)
            mock_open.return_value = mock_resp
            with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
                json.dump(registry, f)
                path = f.name
            with patch.dict(os.environ, {"OR_KEY": "k"}, clear=False):
                from synlynk.gateway import cmd_gateway_probe
                cmd_gateway_probe(gateway="openrouter", config_path=path)
        self.assertEqual(mock_open.call_count, 1)
```

- [ ] **Step 2: Run to confirm FAIL**

```bash
pytest tests/test_gateway.py -v
```

Expected: `ModuleNotFoundError` — `synlynk.gateway` does not exist.

### Task 5.2 — Implement `synlynk/gateway.py`

- [ ] **Step 3: Create `synlynk/gateway.py`**

```python
"""synlynk gateway: registry-driven gateway probe for external model providers.

Reads .synlynk/registry.json's 'gateways' section and probes each enabled
gateway for connectivity. No dispatch integration — this is a config preview
for v0.26.0's Universal Provider Aggregator.
"""
import json
import os
import urllib.error
import urllib.request


def _read_gateway_config(config_path: str) -> dict:
    """Returns the 'gateways' dict from registry.json, or {} if absent/unreadable."""
    try:
        with open(config_path) as f:
            return json.load(f).get("gateways", {})
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _probe_gateway(name: str, cfg: dict) -> int:
    """Probes a single gateway. Returns 0 on success, 1 on failure."""
    if not cfg.get("enabled", False):
        print(f"  - {name}: disabled (skipped)")
        return 0

    api_key_env = cfg.get("api_key_env", "")
    api_key = os.environ.get(api_key_env)
    if not api_key:
        print(f"  ✗ {name}: {api_key_env} not set in environment")
        return 1

    base_url = cfg["base_url"].rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"}
    req = urllib.request.Request(
        f"{base_url}/models", method="GET", headers=headers
    )
    try:
        with urllib.request.urlopen(req, timeout=8) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except (urllib.error.URLError, urllib.error.HTTPError) as exc:
        print(f"  ✗ {name}: unreachable — {exc}")
        return 1

    models = payload.get("data", [])
    model_ids = [m.get("id", "?") for m in models[:5]]
    print(f"  ✓ {name}: reachable ({len(models)} models available)")
    if model_ids:
        print(f"    top models: {', '.join(model_ids)}")
    if not cfg.get("dispatch_active", False):
        print(f"  ⚠ {name}: dispatch integration not yet active (ships in v0.26.0)")
    return 0


def cmd_gateway_probe(gateway: str = None, config_path: str = ".synlynk/registry.json") -> int:
    """Probes enabled gateways from registry.json for connectivity.

    Args:
        gateway: probe only this gateway name; None probes all enabled.
        config_path: path to registry.json.

    Returns 0 if all probed gateways are reachable or disabled, 1 if any fail.
    """
    gateways = _read_gateway_config(config_path)
    if not gateways:
        print("  No gateways configured in registry.json")
        return 0

    if gateway is not None and gateway not in gateways:
        print(f"  ✗ Unknown gateway: {gateway!r}. Available: {list(gateways)}")
        return 1

    targets = {gateway: gateways[gateway]} if gateway else gateways
    exit_code = 0
    for name, cfg in targets.items():
        rc = _probe_gateway(name, cfg)
        if rc != 0:
            exit_code = rc
    return exit_code
```

### Task 5.3 — Add schema to registry + wire CLI

- [ ] **Step 4: Add `gateways` schema to `synlynk/registry.py` (or equivalent)**

Find the function that reads or initialises `registry.json` (search for `registry.json` in `synlynk/`). Add a `setdefault` call for the gateways key:

```python
# In the function that loads or initialises registry.json:
registry.setdefault("gateways", {
    "openrouter": {
        "enabled": False,
        "base_url": "https://openrouter.ai/api/v1",
        "api_key_env": "OPENROUTER_API_KEY",
        "models": [],
        "note": "Dispatch integration ships in v0.26.0. Use synlynk gateway probe to test connectivity."
    }
})
```

- [ ] **Step 5: Wire `synlynk gateway probe` in `synlynk/cli.py`**

Find the subcommand parser section in `cli.py`. Add:

```python
# Under the 'gateway' subcommand group (create group if absent):
gateway_parser = subparsers.add_parser("gateway", help="Manage external model gateways")
gateway_sub = gateway_parser.add_subparsers(dest="gateway_cmd")

probe_parser = gateway_sub.add_parser("probe", help="Test gateway connectivity")
probe_parser.add_argument("--gateway", default=None,
                          help="Name of gateway to probe (default: all enabled)")
probe_parser.add_argument("--config", default=".synlynk/registry.json",
                          help="Path to registry.json")
```

In the main command dispatch:

```python
elif args.command == "gateway":
    if args.gateway_cmd == "probe":
        from synlynk.gateway import cmd_gateway_probe
        sys.exit(cmd_gateway_probe(
            gateway=args.gateway,
            config_path=args.config,
        ))
```

- [ ] **Step 6: Run tests**

```bash
pytest tests/test_gateway.py -v
```

Expected: all pass.

- [ ] **Step 7: Run full suite**

```bash
pytest tests/ -m "not local_hardware" -n 4 --dist loadfile -q
```

Expected: all pass.

- [ ] **Step 8: Commit**

```bash
git add synlynk/gateway.py synlynk/cli.py tests/test_gateway.py
git commit -m "feat(gateway): OpenRouter config preview and synlynk gateway probe

New synlynk/gateway.py: _read_gateway_config(), _probe_gateway(),
cmd_gateway_probe(). No dispatch integration — config schema preview
for v0.26.0 Universal Provider Aggregator.
registry.json gains 'gateways' key with openrouter schema.
synlynk gateway probe --gateway <name> wired in cli.py.

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task Group 6: Orb Stack Docker Image

**Dispatch via:** `synlynk dispatch grok` (infra)
**Branch:** `feat/agy/v025-tg6-orb-stack`
**Depends on:** TG-5 (independent — can run in parallel if desired)

**Files:**
- Create: `docker/Dockerfile.sovereign`
- Create: `docker/entrypoint.sh`
- Create: `.github/workflows/sovereign-build.yml`

**Interfaces:**
- Consumes: `synlynk local doctor` (must be installed inside image)
- Produces: `ghcr.io/nikhilsoman/synlynk-sovereign:v0.25.0` OCI image

### Task 6.1 — Dockerfile + entrypoint

- [ ] **Step 1: Create `docker/Dockerfile.sovereign`**

```dockerfile
# Stage 1: install Python dependencies
FROM python:3.12-slim AS builder

WORKDIR /install

# Install synlynk from the local source (CI build context)
COPY . /src
RUN pip install --no-cache-dir --prefix=/install/pkg /src[full] \
    aider-chat \
    prism-ml

# Stage 2: runtime image
FROM python:3.12-slim AS runtime

COPY --from=builder /install/pkg /usr/local

# oMLX lives on the host; default to Docker/Orbstack bridge address
ENV OMLX_ENDPOINT=http://host.docker.internal:8000

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

WORKDIR /workspace
ENTRYPOINT ["/entrypoint.sh"]
```

- [ ] **Step 2: Create `docker/entrypoint.sh`**

```bash
#!/bin/bash
set -e

ENDPOINT="${OMLX_ENDPOINT:-http://host.docker.internal:8000}"

# Write minimal .agents/local.json pointing at the host oMLX
mkdir -p .agents
cat > .agents/local.json <<JSON
{
  "name": "local",
  "endpoint": "${ENDPOINT}",
  "models": [
    {"id": "Ornith-1.0-9B-4bit", "pinned": false, "edit_format": "diff",
     "tier": ["8gb-light", "16gb-default"]},
    {"id": "Qwen3.6-27B-4bit", "pinned": false, "edit_format": "whole",
     "tier": ["64gb-fleet"]},
    {"id": "Ternary-Bonsai-2-27B-mlx-2bit", "pinned": false, "edit_format": "diff",
     "loader": "prism-ml", "tier": ["32gb-pro", "64gb-fleet"]}
  ],
  "hardware_tier": "16gb-default",
  "pinned_model": "Ornith-1.0-9B-4bit",
  "max_concurrent": 1
}
JSON

# Health check (non-fatal — oMLX may not be reachable at image start)
synlynk local doctor || echo "[sovereign] oMLX not reachable — start oMLX on host first"

# If TASK env var is set, dispatch it; otherwise drop to shell
if [ -n "${TASK}" ]; then
  exec synlynk dispatch local --task "${TASK}"
else
  exec bash
fi
```

### Task 6.2 — GitHub Actions workflow

- [ ] **Step 3: Create `.github/workflows/sovereign-build.yml`**

```yaml
name: Orb Stack Docker Build

on:
  push:
    tags:
      - "v0.25.*"
  pull_request:
    paths:
      - "docker/**"

jobs:
  build:
    runs-on: ubuntu-latest
    permissions:
      contents: read
      packages: write

    steps:
      - uses: actions/checkout@v4

      - name: Set up Docker Buildx
        uses: docker/setup-buildx-action@v3

      - name: Log in to GitHub Container Registry
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')
        uses: docker/login-action@v3
        with:
          registry: ghcr.io
          username: ${{ github.actor }}
          password: ${{ secrets.GITHUB_TOKEN }}

      - name: Build image (smoke test)
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.sovereign
          push: false
          tags: synlynk-sovereign-test:latest
          cache-from: type=gha
          cache-to: type=gha,mode=max

      - name: Smoke test — verify synlynk installed
        run: |
          docker run --rm synlynk-sovereign-test:latest synlynk local doctor --help

      - name: Push image (tag pushes only)
        if: github.event_name == 'push' && startsWith(github.ref, 'refs/tags/')
        uses: docker/build-push-action@v5
        with:
          context: .
          file: docker/Dockerfile.sovereign
          push: true
          tags: |
            ghcr.io/nikhilsoman/synlynk-sovereign:${{ github.ref_name }}
            ghcr.io/nikhilsoman/synlynk-sovereign:latest
```

- [ ] **Step 4: Commit**

```bash
git add docker/Dockerfile.sovereign docker/entrypoint.sh \
        .github/workflows/sovereign-build.yml
git commit -m "feat(docker): Orb Stack sovereign silicon Docker image

docker/Dockerfile.sovereign: multi-stage build, synlynk + aider + prism-ml.
docker/entrypoint.sh: writes .agents/local.json at container start,
runs local doctor, dispatches TASK or drops to bash.
.github/workflows/sovereign-build.yml: CI build smoke test + push on tag.

Co-Authored-By: Grok <noreply@x.ai>"
```

---

## Task Group 7: Integration, Version Bump + PR

**Dispatch via:** `synlynk dispatch codex`
**Branch:** All TG branches squash-merged into a single `feat/agy/v025-sovereign-silicon` PR

**Files:**
- Modify: `project-docs/roadmap.md` — mark v0.25.0 items as `[x]`
- Modify: `CHANGELOG.md` — add v0.25.0 entry
- Modify: `pyproject.toml` — bump version `0.24.x` → `0.25.0`
- Modify: `synlynk/_constants.py` — add `HARNESS_CAPABILITY_BASELINES["local"]` update if needed
- Add: `docs/blog/97-pr<N>-v025-sovereign-silicon.md` — blog post

### Task 7.1 — CHANGELOG + version bump

- [ ] **Step 1: Update `CHANGELOG.md`**

Add at the top (below the `# Changelog` heading):

```markdown
## v0.25.0 — Sovereign Silicon: Local oMLX Fleet (2026-10-22)

### Added
- Three-model roster: Ornith-1.0-9B-4bit, Qwen3.6-27B-4bit, Ternary-Bonsai-2-27B-mlx-2bit
- Hardware tier prober (`_detect_hardware_tier()`) on macOS and Linux
- `synlynk local doctor --init`: auto-detects tier, writes pinned_model to .agents/local.json
- prism-ml loader detection for Ternary-Bonsai; graceful fallback to Ornith when absent
- Tier-0 zero-trust auto-routing: `synlynk dispatch auto` routes to local when healthy + capable
- `local_auto_threshold` and `local_fallback` config keys
- OpenRouter gateway config preview in `.synlynk/registry.json`
- `synlynk gateway probe [--gateway openrouter]` connectivity check
- Orb Stack Docker image: `ghcr.io/nikhilsoman/synlynk-sovereign:v0.25.0`

### Fixed
- Validated end-to-end local dispatch with Ornith post-diff-format fix (TG-1)

### Deferred to v0.27.0
- System 1 decision routing (Ternary-Bonsai-as-classifier, Jev local, LoRA fine-tune)
```

- [ ] **Step 2: Bump version in `pyproject.toml`**

```toml
[project]
version = "0.25.0"
```

- [ ] **Step 3: Mark roadmap items done in `project-docs/roadmap.md`**

Change the three `- [ ]` items under `## v0.25.0` to `- [x]`.

- [ ] **Step 4: Run final full test suite**

```bash
pytest tests/ -m "not local_hardware" -n 4 --dist loadfile -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add CHANGELOG.md pyproject.toml project-docs/roadmap.md
git commit -m "release: v0.25.0 Sovereign Silicon local oMLX fleet

Co-Authored-By: Agy (Gemini) <noreply@antigravity.dev>"
```

### Task 7.2 — Merge PR

- [ ] **Step 6: Create PR**

```bash
gh pr create \
  --title "feat: v0.25.0 Sovereign Silicon — local oMLX fleet" \
  --body "Closes #1710. Three-model roster, hardware tier prober, tier-0 auto-routing, Orb Stack Docker image, OpenRouter config preview. System 1 deferred to v0.27.0." \
  --base main
```

- [ ] **Step 7: PR review**

```bash
synlynk pr check
synlynk policy check-merge --role qa
```

- [ ] **Step 8: Merge**

```bash
gh pr merge <pr-number> --squash --admin --delete-branch
git worktree remove worktrees/v025-spec
```

---

## Execution Order

Tasks are **serial** due to interface dependencies:

```
TG-1 (manual gate) → TG-2 → TG-3 → TG-4 → TG-5 → TG-6 (parallel ok) → TG-7
                                              ↑
                                     TG-6 can overlap TG-5
```

TG-6 (Docker/Grok infra) may run in parallel with TG-5 (gateway probe) since they touch no shared files.
