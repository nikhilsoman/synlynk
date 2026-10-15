# GenericAPIAdapter / OpenRouter Gateway Dispatch Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make `synlynk dispatch --force-harness openrouter` actually spawn a real, non-CLI-vendor subprocess that talks to OpenRouter (or any OpenAI-compatible endpoint) over HTTP, by wiring the already-existing but dormant `synlynk/gateway.py` + `.synlynk/registry.json` OpenRouter subsystem into the live `dispatch_agent()` path, per gh:#2076.

**Architecture:** `dispatch_agent()`'s legacy subprocess-spawn code (`synlynk/dispatch.py:3878-4400`) only ever reads `HARNESS_CAPABILITY_BASELINES[agent]["cli"]` + flags and `Popen`s it — it does not consult `synlynk/harness_adapters/registry.py` at all. So the critical path is: (1) add an `"openrouter"` entry to `HARNESS_CAPABILITY_BASELINES` whose `"cli"` is `synlynk` itself, driving the already-wired `synlynk gateway dispatch --model <m> --prompt <p>` CLI subcommand (`synlynk/cli.py:598-603,2999-3001`); (2) flip the gateway config's `enabled`/`dispatch_active` gates so `gateway.py`'s `dispatch_openrouter()` (already fully implemented, stdlib `urllib.request` only) stops raising; (3) add a 6th structured-JSON cost parser to `synlynk/costs.py::extract_tokens` for this harness's stdout shape (`cmd_gateway_dispatch` already prints the raw OpenAI-compatible `usage` object as JSON). A `GenericAPIAdapter` class satisfying `HarnessAdapter`'s Protocol is added as a smaller, separate, non-blocking task for `tests/test_adapter_conformance.py` parity — it is not on the path that makes dispatch actually work.

**Tech Stack:** Python stdlib only (`urllib.request`, `json`) — no new dependency, per `CLAUDE.md`'s "No dependencies beyond Python 3 stdlib".

---

### Task 1: Enable the OpenRouter gateway config

**Files:**
- Create: `.synlynk/registry.json` (does not exist yet in this checkout — `synlynk/registry.py::load_registry()` falls back to `DEFAULT_REGISTRY` when absent)

- [ ] **Step 1: Write the registry file**

```bash
mkdir -p .synlynk
cat > .synlynk/registry.json <<'EOF'
{
  "supabase": {"enabled": true, "auth_type": "byok", "vault_key": "SUPABASE_ACCESS_TOKEN"},
  "vercel": {"enabled": true, "auth_type": "byok", "vault_key": "VERCEL_TOKEN"},
  "openrouter": {"enabled": true, "auth_type": "byok", "vault_key": "OPENROUTER_API_KEY"},
  "fal_ai": {"enabled": false, "auth_type": "byok", "vault_key": "FAL_KEY"},
  "gateways": {
    "openrouter": {
      "enabled": true,
      "dispatch_active": true,
      "base_url": "https://openrouter.ai/api/v1",
      "api_key_env": "OPENROUTER_API_KEY",
      "models": ["anthropic/claude-sonnet-5"],
      "note": "Dispatch active. models provides fallback model IDs in attempt order."
    }
  }
}
EOF
```

- [ ] **Step 2: Verify it parses and the gateway reports active**

Run: `OPENROUTER_API_KEY=dummy python3 -c "from synlynk.gateway import _read_gateway_config; print(_read_gateway_config('.synlynk/registry.json'))"`
Expected: prints a dict whose `gateways["openrouter"]["dispatch_active"]` is `True`.

- [ ] **Step 3: Commit**

```bash
git add .synlynk/registry.json
git commit -m "chore(gateway): enable OpenRouter gateway dispatch (gh:#2076)"
```

### Task 2: Add the `openrouter` entry to `HARNESS_CAPABILITY_BASELINES`

**Files:**
- Modify: `synlynk/_constants.py:239` (insert a new top-level key alongside `"local"`/`"muse"`, before line 307's closing `}`)

- [ ] **Step 1: Insert the baseline entry**

Insert immediately after the `"local": {...}` block (ends at line 268) and before the `"muse": {...}` block (starts at line 269):

```python
    "openrouter": {
        "cli": "synlynk",
        "can_gh_write": False,
        # "gateway dispatch" is the real subcommand (synlynk/cli.py:598-603).
        # --model is appended generically by dispatch_agent() when a model
        # is passed; --prompt is appended by the prompt_flag/prompt_via_arg
        # mechanism below (dispatch.py:4280-4289), carrying the task text.
        "non_interactive_flags": ["gateway", "dispatch"],
        "prompt_flag": "--prompt",
        "prompt_via_arg": True,
        "dispatch_flags": {
            "valid_flags": ["--model", "--config"],
            "invalid_flags": ["--dangerously-skip-permissions", "--always-approve", "--non-interactive"],
            "required_flags": [],
        },
        "headless_contract": {
            "requires_pty": False,
            "stdout_flush_method": "native",
            "env_vars_required": [],
            "non_interactive_flag": "--prompt",
        },
        "network_deps": {
            "required_endpoints": ["openrouter.ai:443"],
            "optional_endpoints": [],
        },
        "roles": ["builder"],
        "env_passthrough": ["OPENROUTER_API_KEY"],
        "strengths": ["model-agnostic HTTP dispatch", "BYOK provider aggregation", "no vendor CLI required"],
    },
```

- [ ] **Step 2: Verify the dict still loads and the new key is present**

Run: `python3 -c "from synlynk._constants import HARNESS_CAPABILITY_BASELINES as B; assert 'openrouter' in B; assert B['openrouter']['cli'] == 'synlynk'; print('ok')"`
Expected: `ok`

- [ ] **Step 3: Commit**

```bash
git add synlynk/_constants.py
git commit -m "feat(dispatch): add openrouter harness baseline (gh:#2076)"
```

### Task 3: Confirm `--model` plumbing produces a valid command line

**Files:**
- No code changes in this task — verification only, against `synlynk/dispatch.py:3878-3890` (flags assembly) and `4271-4292` (prompt-arg assembly).

- [ ] **Step 1: Dry-run the command construction**

`dispatch_agent()` with `agent="openrouter"`, `model="anthropic/claude-sonnet-5"` builds, per the existing logic:
```
flags = baselines["non_interactive_flags"] + dispatch_flags  # ["gateway", "dispatch"] + []
if model: flags += ["--model", model]                        # + ["--model", "anthropic/claude-sonnet-5"]
```
then (`prompt_via_arg=True`, `prompt_flag="--prompt"`, lines 4280-4289):
```
cmd_str = "synlynk gateway dispatch --model anthropic/claude-sonnet-5 --prompt"
shell_cmd = 'synlynk_prompt=$(cat <prompt_file>); synlynk gateway dispatch --model anthropic/claude-sonnet-5 --prompt "$synlynk_prompt" > <log> 2>&1; echo $? > <log>.exit'
```
This matches `synlynk/cli.py:598-603`'s `gateway dispatch` subparser (`--model` required, `--prompt` required) exactly — no further plumbing changes needed.

- [ ] **Step 2: Confirm by running the literal shell_cmd shape by hand**

```bash
echo "hello from a test dispatch" > /tmp/synlynk-test-prompt.txt
synlynk_prompt=$(cat /tmp/synlynk-test-prompt.txt)
OPENROUTER_API_KEY=dummy python3 bin/synlynk.py gateway dispatch --model anthropic/claude-sonnet-5 --prompt "$synlynk_prompt"
```
Expected: fails with a real HTTP error (`✗ openrouter: ...` from `cmd_gateway_dispatch`'s `except (RuntimeError, ValueError)` branch, since `dummy` is not a real key) — NOT the config-gate errors ("OpenRouter gateway is disabled" / "dispatch is not active" / "not set in environment"). Getting an HTTP/auth error here (not a config error) proves Task 1 + the `--model`/`--prompt` plumbing both work end-to-end; no code to write in this task, just evidence gathering before Task 4/5.

- [ ] **Step 3: No commit** — this task produces no file changes, only confirms Tasks 1-2 are wired correctly before building the cost parser on top.

### Task 4: Add the `openrouter` structured token parser to `costs.py`

**Files:**
- Modify: `synlynk/costs.py` (add new function after `_extract_grok_structured`, ending at line 431; wire into `extract_tokens` at line 452-455)
- Test: `tests/test_costs.py` (confirm this file exists and follows this pattern — if a per-agent structured-parser test already exists for e.g. grok, add a case right next to it)

- [ ] **Step 1: Write the failing test**

Find the existing grok-structured-parser test in `tests/test_costs.py` (search `_extract_grok_structured` or `test_extract_tokens_recognizes_grok`) and add a sibling test immediately after it:

```python
def test_extract_tokens_recognizes_openrouter_format():
    output = json.dumps({
        "id": "gen-abc123",
        "model": "anthropic/claude-sonnet-5",
        "choices": [{"message": {"role": "assistant", "content": "ok"}}],
        "usage": {"prompt_tokens": 120, "completion_tokens": 45, "total_tokens": 165},
    }, indent=2)
    result = extract_tokens(output, agent="openrouter")
    assert result.input_tokens == 120 if hasattr(result, "input_tokens") else result[0] == 120
    assert result.cache_read_tokens == 0
```

(Match whichever of `.input_tokens`/`result[0]` the existing grok test in this file actually asserts — read that test first and mirror its exact access pattern rather than guessing; `_TokenCounts` is a tuple-compatible namedtuple per the module's docstring.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_costs.py::test_extract_tokens_recognizes_openrouter_format -v`
Expected: FAIL — `extract_tokens` returns a regex-fallback result (0, 0, ...) or raises, since no `agent == "openrouter"` branch exists yet.

- [ ] **Step 3: Write the parser function**

Insert into `synlynk/costs.py` immediately after `_extract_grok_structured` (after line 431):

```python
def _extract_openrouter_structured(output_text: str) -> Optional[_TokenCounts]:
    """Parses `synlynk gateway dispatch`'s printed OpenRouter/OpenAI-compatible
    chat-completion response (`cmd_gateway_dispatch` in synlynk/gateway.py
    prints `json.dumps(response, indent=2)`).

    The response is the standard OpenAI-compatible shape: a top-level
    `usage: {prompt_tokens, completion_tokens, total_tokens}` object, no
    cache-read or reasoning-token fields to fold in (unlike Codex/Grok/Agy).
    """
    try:
        event = json.loads(output_text.strip())
    except (ValueError, TypeError):
        return None
    if not isinstance(event, dict):
        return None
    usage = event.get("usage")
    if not isinstance(usage, dict):
        return None
    try:
        in_tokens = int(usage["prompt_tokens"])
        out_tokens = int(usage["completion_tokens"])
    except (KeyError, TypeError, ValueError):
        return None
    return _TokenCounts(in_tokens, out_tokens, 0, "structured_output")
```

- [ ] **Step 4: Wire it into `extract_tokens`**

In `synlynk/costs.py`, immediately after the `if agent == "muse":` block (lines 456-459), add:

```python
    if agent == "openrouter":
        structured = _extract_openrouter_structured(output_text)
        if structured is not None:
            return structured
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_costs.py::test_extract_tokens_recognizes_openrouter_format -v`
Expected: PASS

- [ ] **Step 6: Run the full costs test file to check for regressions**

Run: `pytest tests/test_costs.py -v`
Expected: all pass, same count as before plus the 1 new test.

- [ ] **Step 7: Commit**

```bash
git add synlynk/costs.py tests/test_costs.py
git commit -m "feat(costs): add openrouter structured token parser (gh:#2076)"
```

### Task 5: Verify terminal-status reconciliation needs no changes

**Files:**
- Read only: `synlynk/jobs.py:3755` (`_reconcile_terminal_jobs_json`), `synlynk/jobs.py:4205` (`_verify_daemon_terminal_status`)

- [ ] **Step 1: Confirm reconciliation keys off exit code, not a stdout marker**

Run: `sed -n '3755,3820p' synlynk/jobs.py` and `sed -n '4205,4260p' synlynk/jobs.py`, and check whether either function requires a specific marker string in stdout (e.g. `SYNLYNK_TASK_RECEIVED:`) to classify a job as genuinely completed, or whether it relies on the `<log>.exit` file's exit code (written by the `shell_cmd` in `dispatch.py:4279/4288/4292`) plus `extract_tokens` succeeding.

- [ ] **Step 2: If a marker IS required**, note it here and add one more task before merging: append that exact marker string as a final line of `cmd_gateway_dispatch`'s stdout in `synlynk/gateway.py` (it currently ends with `print(json.dumps(response, indent=2))` at line 161 — append `print("<the required marker>")` after it, matching the exact format another CLI adapter emits). **If no marker is required** (exit-code + extract_tokens based), no change needed — record that finding as a one-line comment in the PR description instead of a code change.

- [ ] **Step 3: No commit if no change was needed; otherwise commit the one-line gateway.py addition with**

```bash
git add synlynk/gateway.py
git commit -m "fix(gateway): emit terminal-status receipt marker (gh:#2076)"
```

### Task 6 (optional, non-blocking): `GenericAPIAdapter` Protocol class for conformance-test parity

**Files:**
- Create: `synlynk/harness_adapters/generic_api.py`
- Modify: `tests/test_adapter_conformance.py` (add to `ALL_ADAPTERS`; mirror `LocalAdapter`'s treatment since it is the closest non-structured-cache, no-gh-write precedent)

- [ ] **Step 1: Read `synlynk/harness_adapters/local.py` in full as the reference** (closest adapter: no gh-write, no cache tiers, single structured-or-regex token path) before writing step 2.

- [ ] **Step 2: Write `generic_api.py`**

```python
"""HarnessAdapter Protocol wrapper for the openrouter gateway harness.

This class exists for tests/test_adapter_conformance.py parity and any
future migration to dispatch_pipeline.py's build_cmd()-driven spawn() path.
The live dispatch_agent() path (synlynk/dispatch.py) does not consult this
class or synlynk/harness_adapters/registry.py at all today — it reads
HARNESS_CAPABILITY_BASELINES["openrouter"] directly (see Task 2 of
docs/superpowers/plans/2026-10-11-generic-api-adapter.md).
"""

from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.costs import extract_tokens
from synlynk.harness_adapters.base import FailureKind


class GenericAPIAdapter:
    def build_cmd(self, request):
        baseline = HARNESS_CAPABILITY_BASELINES["openrouter"]
        cmd = [baseline["cli"]] + baseline["non_interactive_flags"]
        if getattr(request, "model", None):
            cmd += ["--model", request.model]
        cmd += ["--prompt", getattr(request, "task", "")]
        return cmd

    def parse_output(self, raw_text):
        return extract_tokens(raw_text, agent="openrouter")

    def translate_permissions(self, permissions, read_only, skip_permissions=False):
        return []

    def classify_failure(self, exit_code, stderr, raw_text):
        if exit_code != 0:
            return FailureKind.UNKNOWN
        return None

    def resolve_model(self, tier, effort=None):
        baseline = HARNESS_CAPABILITY_BASELINES["openrouter"]
        return baseline.get("default_model", "anthropic/claude-sonnet-5")
```

(Match the exact `FailureKind` enum member names and `build_cmd`/`resolve_model` signatures to what `local.py` actually uses — read it first per Step 1 and correct any mismatch here before committing; this snippet is a starting point, not a verified-against-protocol final form.)

- [ ] **Step 3: Add to the conformance suite**

In `tests/test_adapter_conformance.py`:
```python
from synlynk.harness_adapters.generic_api import GenericAPIAdapter
```
Add `GenericAPIAdapter` to `ALL_ADAPTERS` (line 16). Do NOT add it to `SIGNATURE_ADAPTERS` or `RECEIPT_ADAPTERS` yet — those lists encode known xfail drift (gh:#2078/#2079) for the 5 CLI adapters; adding `GenericAPIAdapter` there requires first confirming its signatures/receipt marker match, which is Task 6's own scope creep — leave it only in `ALL_ADAPTERS` for now and file a follow-up issue if `test_implements_protocol_methods` reveals a gap.

- [ ] **Step 4: Run the conformance suite**

Run: `pytest tests/test_adapter_conformance.py -v`
Expected: `test_implements_protocol_methods[GenericAPIAdapter]` passes; no other test's parametrization changed (since it's absent from SIGNATURE_ADAPTERS/RECEIPT_ADAPTERS).

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_adapters/generic_api.py tests/test_adapter_conformance.py
git commit -m "feat(adapters): add GenericAPIAdapter Protocol wrapper for conformance parity (gh:#2076)"
```

### Task 7: End-to-end smoke test (manual, not CI — requires a real or mocked key)

**Files:** none — verification only.

- [ ] **Step 1: Mocked smoke test**

```bash
python3 - <<'EOF'
from unittest.mock import patch
from synlynk.gateway import cmd_gateway_dispatch

fake_response = {
    "id": "gen-test",
    "choices": [{"message": {"content": "hello"}}],
    "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
}

with patch("synlynk.gateway.dispatch_openrouter", return_value=fake_response):
    code = cmd_gateway_dispatch("anthropic/claude-sonnet-5", "say hello", config_path=".synlynk/registry.json")
    assert code == 0
print("smoke test ok")
EOF
```
Expected: `smoke test ok`, and stdout (captured by `cmd_gateway_dispatch`'s own `print`) is the `json.dumps(fake_response, indent=2)` text, which `extract_tokens(..., agent="openrouter")` from Task 4 correctly parses into `(10, 5, 0, "structured_output")`.

- [ ] **Step 2: Real round-trip (only if the implementer has a live `OPENROUTER_API_KEY`)**

```bash
OPENROUTER_API_KEY=<real key> python3 bin/synlynk.py gateway dispatch --model "anthropic/claude-sonnet-5" --prompt "reply with the single word: ok"
```
Expected: exit 0, JSON response printed with `usage.completion_tokens >= 1`. Not required for merge if no live key is available — note in the PR description whether this step ran.

## Self-Review

1. **Spec coverage:** Config resolution (Task 1, bridges `.synlynk/registry.json` instead of inventing `generic_endpoints`) ✓. Invocation (Task 2/3, HARNESS_CAPABILITY_BASELINES entry + existing `gateway dispatch` CLI subcommand, no new urllib call site) ✓. Cost-entry write-through (Task 4) ✓. Timeout handling — `gateway.py`'s `dispatch_openrouter` already wraps the call with `timeout=GATEWAY_TIMEOUT_SECONDS` (30s) and catches `URLError`/`HTTPError`/`OSError`/`ValueError`; no new timeout wrapper needed, confirmed by reading `synlynk/gateway.py:87-143` — no separate task required. Receipt marker (Task 5, verify-then-act). Registry wiring (superseded — Task 2's baseline entry replaces the original `registry.py`-only plan). Conformance testing (Task 6, explicitly scoped as optional/non-blocking since it doesn't affect live dispatchability).
2. **Placeholder scan:** No TBD/TODO. Task 4 Step 1 and Task 6 Step 2 both explicitly instruct reading an existing file first to match its exact pattern rather than guessing — this is a deliberate "verify before copying a pattern" instruction, not a placeholder, since the exact code is unknowable without that file's current content and guessing wrong here would silently break the test suite's existing conventions.
3. **Type consistency:** `_TokenCounts(in_tokens, out_tokens, cache_read_tokens, source)` 4-tuple matches the exact positional shape used by `_extract_grok_structured`/`_extract_codex_structured`/`_extract_agy_structured` (all return `_TokenCounts(int, int, int, "structured_output")`). `GenericAPIAdapter`'s methods match the 5-method Protocol list from `tests/test_adapter_conformance.py:44-50` (`build_cmd`, `parse_output`, `translate_permissions`, `classify_failure`, `resolve_model`) exactly.

## Execution Handoff

Per this project's Default Agent Role policy and `.synlynk/policy.json`'s `dev_authority.task_allocation` (implement → codex, fallback grok/agy), implementation should be dispatched via `synlynk dispatch --force-harness codex`, not implemented by Claude directly.

Before dispatch: search `synlynk story list` / `synlynk goal list` for an existing Wave-4/provider-aggregator goal under gh:#1708 or gh:#1711. If none exists, create one (`synlynk goal create ...` per this project's GOVERNS conventions) and link a new story for this plan to it, per the Hardened PR Review Policy's 100% GOVERNS adherence requirement. Do not dispatch without a linked story/goal.

Per the Cross-Harness+Model Review requirement (CLAUDE.md, Hardened PR Review Policy §3), the reviewer for the resulting PR must differ from Codex in both harness and model — route review to Agy or Grok, not another Codex session.
