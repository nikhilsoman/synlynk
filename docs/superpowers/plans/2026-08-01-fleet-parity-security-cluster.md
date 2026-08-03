# Fleet-Parity Security Cluster Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close two security-severity fleet-parity gaps — dispatched subprocesses inheriting the full host environment (#348), and permission "enforcement" that silently no-ops for agents with no real CLI-level restriction mechanism (#338) — by making both fail closed/allowlisted instead of open/copy-everything.

**Architecture:** Two new centralized functions in `synlynk/dispatch.py`, each with a single call site: `_permissions_to_flags()` gains a `PermissionEnforcementError` raise path for Local (always) and Agy (read-only-only requests); a new `_build_subprocess_env()` replaces the unconditional `os.environ.copy()` with an allowlist built from a fixed base set plus a new per-agent `env_passthrough` baseline field. A third, independent change adds generic secret-pattern redaction to `synlynk/__init__.py`'s existing captured-output redaction path.

**Tech Stack:** Python 3 stdlib only (`re`, `os`), pytest.

Spec: `docs/superpowers/specs/2026-08-01-fleet-parity-security-cluster-design.md`

---

### Task 1: `PermissionEnforcementError` + fail-closed for Local and Agy read-only

**Files:**
- Modify: `synlynk/dispatch.py:203-230` (`_permissions_to_flags`)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`, near the existing `test_permissions_to_flags_agy_*` tests (around line 359):

```python
def test_permissions_to_flags_agy_raises_on_read_only_permissions():
    from synlynk.dispatch import _permissions_to_flags, PermissionEnforcementError

    with pytest.raises(PermissionEnforcementError, match="agy"):
        _permissions_to_flags("agy", ["read:*"])


def test_permissions_to_flags_local_raises_on_any_permissions():
    from synlynk.dispatch import _permissions_to_flags, PermissionEnforcementError

    with pytest.raises(PermissionEnforcementError, match="local"):
        _permissions_to_flags("local", ["read:*"])

    with pytest.raises(PermissionEnforcementError, match="local"):
        _permissions_to_flags("local", ["write:src/"])


def test_permissions_to_flags_local_no_permissions_is_noop():
    from synlynk.dispatch import _permissions_to_flags

    assert _permissions_to_flags("local", []) == []
    assert _permissions_to_flags("local", None) == []
```

Confirm `import pytest` is already present at the top of `tests/test_dispatch.py` (it is — used by the existing `pytest.raises` call at line 352).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dispatch.py -k "permissions_to_flags" -v`
Expected: the three new tests FAIL — `test_permissions_to_flags_agy_raises_on_read_only_permissions` and the two `local` tests fail with `ImportError: cannot import name 'PermissionEnforcementError'` (it doesn't exist yet); the existing two `agy` tests (empty permissions, write permissions) still PASS.

- [ ] **Step 3: Implement `PermissionEnforcementError` and the fail-closed branches**

In `synlynk/dispatch.py`, add the exception class immediately above `def _permissions_to_flags` (currently line 203):

```python
class PermissionEnforcementError(RuntimeError):
    """Raised when an agent has no real mechanism to enforce requested permissions."""


def _permissions_to_flags(agent: str, permissions: list) -> list:
    """Translate permission strings into agent-specific CLI flags."""
    from synlynk._constants import _PERMISSION_TO_TOOL_MAP

    if agent == "agy":
        if not permissions:
            print(
                "  ⚠ agy dispatched with no write/run permissions granted -- "
                "headless mode will auto-deny command/write tool calls and may silently no-op"
            )
            return []
        if set(permissions) <= {"read:*"}:
            raise PermissionEnforcementError(
                f"agy has no mechanism to enforce a read-only-only permission set {sorted(permissions)}; "
                "headless mode cannot reliably block write/command tool calls. Refusing to dispatch "
                "rather than silently granting more than requested."
            )
        return ["--dangerously-skip-permissions"]
    if agent == "claude":
        tools = []
        for perm in permissions or []:
            tools.extend(_PERMISSION_TO_TOOL_MAP.get(perm, []))
        tools = sorted(set(tools))
        if not tools:
            return []
        return ["--allowedTools", ",".join(tools)]
    if agent == "codex":
        has_write = any((perm or "").startswith("write:") for perm in (permissions or []))
        if not has_write:
            return ["--ask-for-approval", "untrusted"]
        return []
    if agent == "grok":
        return _grok_permission_flags(permissions)
    if agent == "local":
        if permissions:
            raise PermissionEnforcementError(
                f"local (aider) has no mechanism to enforce permissions {sorted(permissions)}; "
                "aider's declared CLI flags include no read-only/file-scope restriction. Refusing "
                "to dispatch rather than silently granting full read/write access."
            )
        return []
    return []
```

This replaces the existing `_permissions_to_flags` function body in place (same signature, same import line). Note the `agy` branch is restructured (separate `if not permissions` and `if set(permissions) <= {"read:*"}` checks) instead of the original combined `if not permissions or set(permissions) <= {"read:*"}:` — this preserves the exact warn-and-return-`[]` behavior for the empty-permissions case (matching the existing `test_permissions_to_flags_agy_warns_on_empty_permissions` test) while adding the new raise only for the genuine non-empty read-only case.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dispatch.py -k "permissions_to_flags" -v`
Expected: all 5 tests PASS (2 pre-existing + 3 new).

- [ ] **Step 5: Run the full dispatch test suite to check for regressions**

Run: `python3 -m pytest tests/test_dispatch.py tests/test_dispatch_local_agent.py tests/test_dispatch_github_identity.py -v`
Expected: all PASS. `_permissions_to_flags` is called from the main dispatch flow — this catches any caller that wasn't expecting an exception from a `local`/`agy` read-only dispatch.

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix(dispatch): fail closed for agents with no permission enforcement mechanism (#338)"
```

---

### Task 2: `env_passthrough` baseline field

**Files:**
- Modify: `synlynk/_constants.py:44-199` (`AGENT_CAPABILITY_BASELINES`)
- Test: `tests/test_dispatch.py` or a new `tests/test_constants.py` (create if it doesn't exist)

**Context:** Each agent baseline dict gets a new `env_passthrough: []` key — additional env var *names* (not values) that specific agent's CLI needs beyond the fixed base allowlist Task 3 builds. This task documents the investigation finding for each agent using evidence already in this codebase (each baseline's existing `auth_check` block, where present, describes how that agent authenticates):

- **claude**: no `auth_check` block; Claude Code CLI authenticates via a login/keychain state, not an env var read by this dispatch path. `env_passthrough: []`.
- **codex**: no `auth_check` block; `codex exec` runs under its own login state (`codex login`), not an env-var API key read at dispatch time. `env_passthrough: []`.
- **agy**: has `auth_check.required_paths: ["~/.gemini/antigravity-cli/jetski_state.pbtxt"]` — auth is file-based, not env-var based. `env_passthrough: []`.
- **grok**: has `auth_check.probe: ["grok", "--version"]` with no required env var. `env_passthrough: []`.
- **local**: `network_deps.required_endpoints: ["127.0.0.1:8080"]` and `dispatch_flags` already pass `--openai-api-base` explicitly as a CLI flag (not read from env) — no API key needed for a local endpoint. `env_passthrough: []`.

All five start empty. This is a documented finding, not a placeholder — if a future dispatch fails with an agent-specific auth error traceable to a missing env var, that's the signal to add a real entry here.

- [ ] **Step 1: Write the failing test**

Create `tests/test_constants.py` if it doesn't already exist (check first: `ls tests/test_constants.py`). Add:

```python
from synlynk._constants import AGENT_CAPABILITY_BASELINES


def test_every_agent_baseline_declares_env_passthrough():
    for agent, baseline in AGENT_CAPABILITY_BASELINES.items():
        assert "env_passthrough" in baseline, f"{agent} baseline missing env_passthrough"
        assert isinstance(baseline["env_passthrough"], list), f"{agent} env_passthrough must be a list"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_constants.py -v`
Expected: FAIL — `AssertionError: claude baseline missing env_passthrough` (or similar, for the first agent dict-ordered).

- [ ] **Step 3: Add `env_passthrough: []` to each of the 5 baselines**

In `synlynk/_constants.py`, add `"env_passthrough": [],` as a new key to each of the five agent dicts inside `AGENT_CAPABILITY_BASELINES` (lines 44-199). Place it directly after each dict's `"roles"` line for consistency:

```python
        "roles": ["architect", "builder"],
        "env_passthrough": [],
        "strengths": ["long context", "reasoning", "code review", "planning"],
    },
```
(claude, after line 64)

```python
        "roles": ["builder"],
        "env_passthrough": [],
        "strengths": ["code completion", "inline edits", "fast iteration"],
    },
```
(codex, after line 102)

```python
        "roles": ["builder", "verifier"],
        "env_passthrough": [],
        "strengths": ["multimodal", "large context", "search-augmented"],
    },
```
(agy, after line 135)

```python
        "roles": ["builder", "architect"],
        "env_passthrough": [],
        "strengths": ["codebase understanding", "inline edits", "composer model", "fast iteration"],
    },
```
(grok, after line 167)

```python
        "roles": ["builder"],
        "env_passthrough": [],
        "strengths": ["zero-cost inference", "on-device", "granular tasks"],
    },
```
(local, after line 196)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_constants.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/_constants.py tests/test_constants.py
git commit -m "feat(dispatch): add env_passthrough baseline field for per-agent env allowlisting (#348)"
```

---

### Task 3: `_build_subprocess_env()` replaces `os.environ.copy()`

**Depends on:** Task 2 (reads `env_passthrough` from baselines).

**Files:**
- Modify: `synlynk/dispatch.py:1836-1856` (proc_env construction) and the `Popen` call at `1857-1864`
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/test_dispatch.py`:

```python
def test_build_subprocess_env_allowlists_base_vars_only(monkeypatch):
    from synlynk.dispatch import _build_subprocess_env

    monkeypatch.setenv("PATH", "/usr/bin")
    monkeypatch.setenv("HOME", "/home/test")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "leaked-if-present")
    monkeypatch.setenv("SOME_RANDOM_API_TOKEN", "also-leaked-if-present")

    env = _build_subprocess_env("codex", {}, requires_gh_write=False, story_id="story-1")

    assert env.get("PATH") == "/usr/bin"
    assert env.get("HOME") == "/home/test"
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "SOME_RANDOM_API_TOKEN" not in env


def test_build_subprocess_env_includes_env_passthrough_vars(monkeypatch):
    from synlynk.dispatch import _build_subprocess_env
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setenv("MY_AGENT_TOKEN", "should-be-included")
    fake_baselines = {
        "codex": {"env_passthrough": ["MY_AGENT_TOKEN"], "headless_contract": {}},
    }
    monkeypatch.setattr(dispatch_mod, "AGENT_CAPABILITY_BASELINES", fake_baselines)

    env = _build_subprocess_env("codex", {}, requires_gh_write=False, story_id="story-1")

    assert env.get("MY_AGENT_TOKEN") == "should-be-included"


def test_build_subprocess_env_applies_headless_contract_required_vars():
    from synlynk.dispatch import _build_subprocess_env
    import synlynk.dispatch as dispatch_mod

    fake_baselines = {
        "agy": {"env_passthrough": [], "headless_contract": {"env_vars_required": ["PYTHONUNBUFFERED=1"]}},
    }
    dispatch_mod_patch_target = dispatch_mod.AGENT_CAPABILITY_BASELINES
    dispatch_mod.AGENT_CAPABILITY_BASELINES = fake_baselines
    try:
        env = _build_subprocess_env("agy", {}, requires_gh_write=False, story_id="story-1")
        assert env.get("PYTHONUNBUFFERED") == "1"
    finally:
        dispatch_mod.AGENT_CAPABILITY_BASELINES = dispatch_mod_patch_target


def test_build_subprocess_env_overrides_win_over_allowlist(monkeypatch):
    from synlynk.dispatch import _build_subprocess_env

    monkeypatch.setenv("PATH", "/usr/bin")

    env = _build_subprocess_env("codex", {"env": {"PATH": "/custom/bin"}}, requires_gh_write=False, story_id="story-1")

    assert env.get("PATH") == "/custom/bin"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dispatch.py -k "build_subprocess_env" -v`
Expected: all 4 FAIL with `ImportError: cannot import name '_build_subprocess_env'`.

- [ ] **Step 3: Implement `_build_subprocess_env()` and swap the call site**

First read the current call site to confirm exact context:

Run: `grep -n "proc_env = os.environ.copy()" synlynk/dispatch.py`
Expected output: `1836:    proc_env = os.environ.copy()`

Add the new function directly above the main dispatch function that contains this call site (find it with `grep -n "^def dispatch_agent" synlynk/dispatch.py` — place `_build_subprocess_env` just before that function definition, keeping it a module-level function like `_permissions_to_flags`):

```python
_ENV_ALLOWLIST_BASE = [
    "PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR",
    "USER", "SHELL", "SSH_AUTH_SOCK",
    "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
    "GIT_SSH_COMMAND",
]


def _build_subprocess_env(agent: str, overrides: dict, requires_gh_write: bool, story_id: str) -> dict:
    """Build a minimal, allowlisted environment for a dispatched subprocess.

    Replaces copying the full parent environment: only a fixed base set of
    vars (PATH/HOME/git identity/etc.) plus each agent's declared
    env_passthrough vars are inherited. Everything else the operator's shell
    happens to have set (AWS keys, unrelated API tokens, ...) is excluded by
    default.
    """
    baseline = AGENT_CAPABILITY_BASELINES.get(agent, {})
    allowed = set(_ENV_ALLOWLIST_BASE) | set(baseline.get("env_passthrough", []))

    proc_env = {k: v for k, v in os.environ.items() if k in allowed}
    proc_env.update(overrides.get("env", {}))

    for var in baseline.get("headless_contract", {}).get("env_vars_required", []):
        if "=" in var:
            k, v = var.split("=", 1)
            proc_env[k] = v

    if requires_gh_write:
        gh_token = _resolve_dispatch_gh_token(_role_for_story(story_id) or "dev")
        if gh_token:
            proc_env["GH_TOKEN"] = gh_token
        else:
            proc_env.pop("GH_TOKEN", None)
            proc_env.pop("GITHUB_TOKEN", None)
            print(
                "  ⚠ no role-scoped GitHub token available for this --requires-gh-write "
                "dispatch — stripping any inherited GH_TOKEN/GITHUB_TOKEN so the job cannot "
                "silently fall back to a personal credential; GitHub write actions in this "
                "job will fail until a role App is provisioned (see `synlynk identity init`).",
                file=sys.stderr,
            )
    return proc_env
```

Then replace the old inline block (lines 1836-1856, the `proc_env = os.environ.copy()` through the `for var in contract.get(...)` loop) with a single call. Read the exact surrounding lines first:

Run: `sed -n '1830,1865p' synlynk/dispatch.py`

Replace the block from `proc_env = os.environ.copy()` (line 1836) through the end of the `for var in contract.get("env_vars_required", []):` loop (line 1855) with:

```python
    proc_env = _build_subprocess_env(agent, overrides, requires_gh_write, story_id)
```

The `contract = baselines.get("headless_contract", {})` line (1835) that precedes it becomes unused by this block specifically — check with `grep -n "contract\b" synlynk/dispatch.py` whether `contract` is referenced anywhere else in the same function after line 1856. If it is still used elsewhere in the function, leave line 1835 in place. If not, remove it as part of this edit (dead variable).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dispatch.py -k "build_subprocess_env" -v`
Expected: all 4 PASS.

- [ ] **Step 5: Run the GH_TOKEN regression tests and full dispatch suite**

Run: `python3 -m pytest tests/test_dispatch_github_identity.py tests/test_dispatch.py tests/test_dispatch_local_agent.py tests/test_dispatch_cycle.py tests/test_agy_dispatch_fix.py tests/test_dispatch_context_mode_hint.py -v`
Expected: all PASS, including the three existing GH_TOKEN tests in `test_dispatch_github_identity.py` (`test_dispatch_agent_injects_gh_token_when_requires_gh_write`, `test_dispatch_agent_strips_inherited_gh_tokens_when_requires_gh_write_token_missing`, `test_dispatch_agent_does_not_inject_gh_token_by_default`) — these are the regression guard that the GH_TOKEN inject/strip behavior survived the refactor unchanged.

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "fix(dispatch): allowlist dispatched subprocess environment instead of inheriting full host env (#348)"
```

---

### Task 4: Generic secret-pattern redaction

**Files:**
- Modify: `synlynk/__init__.py:2275-2320`
- Test: `tests/test_redaction.py` (create — check first with `ls tests/test_redaction.py`)

- [ ] **Step 1: Write the failing tests**

Create `tests/test_redaction.py`:

```python
from synlynk import _redact_secret_patterns


def test_redacts_github_pat():
    text = "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in _redact_secret_patterns(text)
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_redacts_github_oauth_token():
    text = "gho_abcdefghijklmnopqrstuvwxyz0123456789"
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_redacts_aws_access_key_id():
    text = "AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP"
    result = _redact_secret_patterns(text)
    assert "AKIAABCDEFGHIJKLMNOP" not in result
    assert "[REDACTED]" in result


def test_redacts_openai_style_key():
    text = "sk-abcdefghijklmnopqrstuvwxyz123456"
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_redacts_slack_token():
    text = "xoxb-not-a-real-token-fixture-0000"
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_normal_text_passes_through_unchanged():
    text = "Running tests... 30 passed in 2.01s. No issues found."
    assert _redact_secret_patterns(text) == text
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_redaction.py -v`
Expected: all 6 FAIL with `ImportError: cannot import name '_redact_secret_patterns' from 'synlynk'`.

- [ ] **Step 3: Implement `_redact_secret_patterns()` and wire it in**

In `synlynk/__init__.py`, add directly above `_redact_active_tokens` (currently line 2275):

```python
_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),           # GitHub personal access token
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{36}"),     # GitHub OAuth/App/refresh/server tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS access key ID
    re.compile(r"sk-[A-Za-z0-9]{20,}"),            # OpenAI-style secret key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),   # Slack token
]


def _redact_secret_patterns(text: str) -> str:
    """Redact common, recognizable secret-shaped substrings from captured output.

    Pattern-based and necessarily incomplete (can't catch arbitrary
    high-entropy secrets with no recognizable prefix) — defense-in-depth
    alongside the dispatched-subprocess env allowlist, for the case where a
    secret still ends up in captured output some other way.
    """
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
```

`re` is already imported at the top of `synlynk/__init__.py` (line 9) — no new import needed.

Then wire it into the two existing call sites (currently lines 2317 and 2320, inside `cmd_logs`):

```python
    if renderer is not None:
        for line in display_lines:
            rendered = renderer(line)
            if rendered is not None:
                print(_redact_secret_patterns(_redact_active_tokens(rendered)), end="")
    else:
        for line in display_lines:
            print(_redact_secret_patterns(_redact_active_tokens(line)), end="")
```

This replaces the two `print(_redact_active_tokens(...), end="")` lines with `print(_redact_secret_patterns(_redact_active_tokens(...)), end="")` — token redaction (specific, known synlynk-minted tokens) runs first, then generic pattern redaction as a second pass.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_redaction.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Run any existing tests that cover `cmd_logs`/`_redact_active_tokens` to check for regressions**

Run: `grep -rln "_redact_active_tokens\|cmd_logs" tests/` to find affected test files, then run them, e.g.:
Run: `python3 -m pytest tests/ -k "redact or cmd_logs or logs" -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_redaction.py
git commit -m "feat: redact generic secret-shaped patterns from captured job output (#348)"
```

---

### Task 5: Full regression suite gate

**Depends on:** Tasks 1-4 complete and committed.

**Files:** None modified — verification only.

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest tests/ -q`
Expected: all tests PASS, 0 failures. This is the final gate before opening a PR — the env-allowlist and permission-enforcement changes touch a shared code path used by every dispatch, so regression risk is broad across the whole suite, not just the new/modified test files.

- [ ] **Step 2: If any pre-existing test fails**

Read the failure carefully — determine whether it's a legitimate behavior change this plan intended (e.g., a test that dispatched to `local` or `agy` with restrictive permissions and expected silent success) versus an unintended regression.

- If it's a test asserting the *old* no-op/warn behavior for a case this plan deliberately changed to fail closed: update that test to assert `PermissionEnforcementError` is now raised, matching Task 1's intent.
- If it's anything else: this is an unintended regression — stop and fix the underlying cause before proceeding, per the "no shortcuts" project discipline. Do not skip or `xfail` the test to make the suite green.

- [ ] **Step 3: Confirm no leftover debug artifacts**

Run: `git status --short`
Expected: clean working tree (everything from Tasks 1-4 already committed) — only untracked files should be things unrelated to this plan (e.g., `.pytest_cache/`, already gitignored).
