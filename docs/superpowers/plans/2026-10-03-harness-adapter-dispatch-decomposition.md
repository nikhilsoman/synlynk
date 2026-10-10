# HarnessAdapter Protocol + Dispatch Pipeline Decomposition Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace `dispatch_agent()`'s scattered `agent == "codex"/"grok"/"agy"/"claude"` branching with a `HarnessAdapter` Protocol (one class per harness) and an explicit pipeline (`resolve → authorize → prepare_worktree → spawn → observe → finalize`) driven by a typed `DispatchRequest`, with zero change to `dispatch_agent()`'s public signature or return shape.

**Architecture:** A new `synlynk/harness_adapters/` package holds the `HarnessAdapter` Protocol, a `LegacyAdapter` that delegates to today's code unchanged, and one real adapter per harness landed incrementally (Codex pilot first). A new `synlynk/dispatch_pipeline.py` holds the five stage functions; `dispatch_agent()` becomes a thin shim that builds a `DispatchRequest` and calls the stages in order.

**Tech Stack:** Python 3 stdlib (`dataclasses`, `typing.Protocol`), pytest, existing `synlynk.dispatch` internals (`resolve_dispatch_harness`, `_permissions_to_flags`, `_grok_permission_flags`, `resolve_dispatch_model`, `_create_job_worktree`, `_write_job_summary`).

---

## Spec Coverage Map

| Spec section | Covered by |
|---|---|
| `DispatchRequest` dataclass | Task 1 |
| `HarnessAdapter` Protocol + registry | Task 2 |
| `dispatch_pipeline.py` 5 stages | Task 3 |
| `dispatch_agent()` compatibility shim | Task 4 |
| PR1 complete, zero behavior change | Task 1–4 (one PR) |
| `CodexAdapter` pilot, real `build_cmd`/`translate_permissions`/`classify_failure`/`resolve_model` | Task 5–8 (PR2) |
| Verify Codex pilot against real dispatch traffic | Task 9 |
| `GrokAdapter` port | Task 10 (PR3) |
| `AgyAdapter` port | Task 11 (PR4) |
| `ClaudeAdapter` + `LocalAdapter` port, delete `LegacyAdapter` | Task 12 (PR5) |
| Regression fixtures for this session's 4 real incidents | Task 6, 8, 10, 11 |

---

## PR 1: Foundation — DispatchRequest, Protocol, Pipeline, Shim (no behavior change)

### Task 1: `DispatchRequest` dataclass

**Files:**
- Create: `synlynk/harness_adapters/__init__.py`
- Create: `synlynk/harness_adapters/request.py`
- Test: `tests/test_dispatch_request.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_request.py
from synlynk.harness_adapters.request import DispatchRequest


def test_dispatch_request_holds_core_fields():
    req = DispatchRequest(
        agent="codex",
        task="fix the thing",
        story_id="S1",
        permissions=["write:repo"],
        model="gpt-5-codex",
        read_only=False,
    )
    assert req.agent == "codex"
    assert req.task == "fix the thing"
    assert req.permissions == ["write:repo"]


def test_dispatch_request_is_frozen():
    req = DispatchRequest(agent="codex", task="x")
    try:
        req.agent = "grok"
        assert False, "expected FrozenInstanceError"
    except AttributeError:
        pass
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_request.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_adapters'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/__init__.py
"""HarnessAdapter protocol and per-harness implementations (gh:#1924)."""
```

```python
# synlynk/harness_adapters/request.py
"""Typed request object threaded through the dispatch pipeline (gh:#1924)."""
from dataclasses import dataclass, field
from typing import Optional


@dataclass(frozen=True)
class DispatchRequest:
    """Immutable snapshot of a single dispatch_agent() call.

    Mirrors dispatch_agent()'s kwargs 1:1 so the compatibility shim (Task 4)
    can build one without changing any caller's signature.
    """
    agent: str
    task: str
    story_id: Optional[str] = None
    agent_id: Optional[str] = None
    force_agent: bool = False
    context_mode: Optional[str] = None
    cycle: str = "work"
    skip_preflight: bool = False
    requires_gh_write: bool = False
    static_baseline: bool = False
    task_type: Optional[str] = None
    requires: list = field(default_factory=list)
    grants: list = field(default_factory=list)
    revokes: list = field(default_factory=list)
    job_id: Optional[str] = None
    issue: Optional[int] = None
    base: Optional[str] = None
    scope_paths: list = field(default_factory=list)
    session_id: Optional[str] = None
    gh_write_target_kind: str = "issue"
    gh_write_expect: Optional[str] = None
    model: Optional[str] = None
    effort: Optional[str] = None
    model_tier: Optional[str] = None
    role: Optional[str] = None
    task_domain: Optional[str] = None
    criticality: float = 1.0
    lambda_: float = 1.0
    permissions: list = field(default_factory=list)
    read_only: bool = False
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch_request.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_adapters/__init__.py synlynk/harness_adapters/request.py tests/test_dispatch_request.py
git commit -m "feat(dispatch): add DispatchRequest dataclass (gh:#1924)"
```

---

### Task 2: `HarnessAdapter` Protocol, `FailureKind`, `DispatchEvent`, registry

**Files:**
- Create: `synlynk/harness_adapters/base.py`
- Create: `synlynk/harness_adapters/registry.py`
- Test: `tests/test_harness_adapter_registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_harness_adapter_registry.py
import pytest
from synlynk.harness_adapters.base import HarnessAdapter, FailureKind, DispatchEvent
from synlynk.harness_adapters.registry import get_adapter, register_adapter


def test_failure_kind_has_expected_members():
    assert FailureKind.AUTH_EXPIRED.value == "auth_expired"
    assert FailureKind.QUOTA_EXHAUSTED.value == "quota_exhausted"
    assert FailureKind.SANDBOX_DENIED.value == "sandbox_denied"


def test_dispatch_event_is_a_plain_data_holder():
    event = DispatchEvent(raw_text="hello", failure=None)
    assert event.raw_text == "hello"
    assert event.failure is None


def test_registry_rejects_unknown_harness():
    with pytest.raises(KeyError):
        get_adapter("not-a-real-harness")


def test_registry_register_and_get_roundtrip():
    class FakeAdapter:
        def build_cmd(self, request):
            return ["fake"]

        def parse_output(self, raw_text):
            return DispatchEvent(raw_text=raw_text, failure=None)

        def translate_permissions(self, permissions, read_only):
            return []

        def classify_failure(self, exit_code, stderr, raw_text):
            return None

        def resolve_model(self, tier, effort):
            return "fake-model"

    register_adapter("fake-harness-for-test", FakeAdapter())
    assert get_adapter("fake-harness-for-test").build_cmd(None) == ["fake"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness_adapter_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_adapters.base'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/base.py
"""HarnessAdapter Protocol and shared value types (gh:#1924)."""
from dataclasses import dataclass
from enum import Enum
from typing import Optional, Protocol

from synlynk.harness_adapters.request import DispatchRequest


class FailureKind(Enum):
    """Classification of a harness run's failure, independent of exit code."""
    AUTH_EXPIRED = "auth_expired"
    QUOTA_EXHAUSTED = "quota_exhausted"
    SANDBOX_DENIED = "sandbox_denied"


@dataclass
class DispatchEvent:
    """A structured parse of one harness's raw output."""
    raw_text: str
    failure: Optional[FailureKind]


class HarnessAdapter(Protocol):
    """Everything that varies by harness, behind one interface.

    One implementation per harness (Codex, Grok, Agy, Claude, local). The
    dispatch pipeline (synlynk/dispatch_pipeline.py) calls these methods and
    never branches on harness name itself.
    """

    def build_cmd(self, request: DispatchRequest) -> list:
        """Return the full subprocess argv for this dispatch request."""
        ...

    def parse_output(self, raw_text: str) -> DispatchEvent:
        """Turn raw subprocess output into a structured DispatchEvent."""
        ...

    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        """Translate permission strings into this harness's CLI flags."""
        ...

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        """Classify a failed run; None means not a recognized auth/quota/sandbox failure."""
        ...

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        """Resolve the concrete model name to use for this tier/effort."""
        ...
```

```python
# synlynk/harness_adapters/registry.py
"""Lookup of harness name -> HarnessAdapter instance (gh:#1924)."""
from synlynk.harness_adapters.base import HarnessAdapter

_ADAPTERS: dict[str, HarnessAdapter] = {}


def register_adapter(name: str, adapter: HarnessAdapter) -> None:
    """Register (or overwrite) the adapter for a harness name."""
    _ADAPTERS[name] = adapter


def get_adapter(name: str) -> HarnessAdapter:
    """Look up the adapter for a harness name; raises KeyError if unregistered."""
    return _ADAPTERS[name]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness_adapter_registry.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_adapters/base.py synlynk/harness_adapters/registry.py tests/test_harness_adapter_registry.py
git commit -m "feat(dispatch): add HarnessAdapter Protocol and registry (gh:#1924)"
```

---

### Task 3: `LegacyAdapter` — delegates to today's code unchanged

**Files:**
- Create: `synlynk/harness_adapters/legacy.py`
- Test: `tests/test_legacy_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_legacy_adapter.py
from synlynk.harness_adapters.legacy import LegacyAdapter
from synlynk.harness_adapters.request import DispatchRequest
from synlynk.harness_adapters.base import FailureKind


def test_legacy_adapter_translate_permissions_matches_existing_codex_logic():
    adapter = LegacyAdapter(agent="codex")
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["-s", "workspace-write"]


def test_legacy_adapter_translate_permissions_matches_existing_grok_logic():
    adapter = LegacyAdapter(agent="grok")
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]


def test_legacy_adapter_classify_failure_returns_none_by_default():
    adapter = LegacyAdapter(agent="codex")
    assert adapter.classify_failure(1, "some generic error", "some generic error") is None


def test_legacy_adapter_resolve_model_delegates_to_resolve_tier_model():
    adapter = LegacyAdapter(agent="grok")
    model = adapter.resolve_model(tier="standard", effort=None)
    assert isinstance(model, str) and model
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_legacy_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_adapters.legacy'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/legacy.py
"""Adapter that delegates to today's dispatch.py branching, unchanged.

Used for every harness not yet ported to a real adapter (see migration order
in docs/superpowers/specs/2026-10-03-harness-adapter-dispatch-decomposition-design.md).
Deleted once all harnesses have a real adapter (Task 12).
"""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class LegacyAdapter:
    def __init__(self, agent: str):
        self.agent = agent

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        return _dispatch_flags_for_agent(self.agent)

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=None)

    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk.dispatch import _permissions_to_flags

        return _permissions_to_flags(self.agent, permissions, read_only=read_only)

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, self.agent)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_legacy_adapter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_adapters/legacy.py tests/test_legacy_adapter.py
git commit -m "feat(dispatch): add LegacyAdapter delegating to existing branching (gh:#1924)"
```

---

### Task 4: Register all five harnesses to `LegacyAdapter`

**Files:**
- Modify: `synlynk/harness_adapters/registry.py`
- Test: `tests/test_harness_adapter_registry.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_harness_adapter_registry.py
def test_all_five_harnesses_resolve_to_an_adapter():
    from synlynk.harness_adapters.registry import get_adapter

    for name in ("codex", "grok", "agy", "claude", "local"):
        adapter = get_adapter(name)
        assert adapter is not None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_harness_adapter_registry.py::test_all_five_harnesses_resolve_to_an_adapter -v`
Expected: FAIL with `KeyError: 'codex'`

- [ ] **Step 3: Write minimal implementation**

```python
# Append to synlynk/harness_adapters/registry.py
from synlynk.harness_adapters.legacy import LegacyAdapter

for _name in ("codex", "grok", "agy", "claude", "local"):
    register_adapter(_name, LegacyAdapter(agent=_name))
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_harness_adapter_registry.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_adapters/registry.py tests/test_harness_adapter_registry.py
git commit -m "feat(dispatch): register all harnesses to LegacyAdapter by default (gh:#1924)"
```

---

### Task 5: `dispatch_pipeline.py` — five stage functions over `DispatchRequest`

**Files:**
- Create: `synlynk/dispatch_pipeline.py`
- Test: `tests/test_dispatch_pipeline_stages.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_pipeline_stages.py
from synlynk.dispatch_pipeline import spawn
from synlynk.harness_adapters.request import DispatchRequest
from synlynk.harness_adapters.legacy import LegacyAdapter


def test_spawn_stage_calls_adapter_build_cmd(monkeypatch):
    calls = []

    class FakeAdapter(LegacyAdapter):
        def build_cmd(self, request):
            calls.append(request.agent)
            return ["echo", "hi"]

    def fake_popen(cmd, **kwargs):
        class FakeProc:
            def communicate(self, timeout=None):
                return (b"hi\n", None)
            returncode = 0
        return FakeProc()

    monkeypatch.setattr("subprocess.Popen", fake_popen)
    req = DispatchRequest(agent="codex", task="do a thing")
    adapter = FakeAdapter(agent="codex")
    result = spawn(req, adapter, env={}, cwd=".")
    assert calls == ["codex"]
    assert result["exit_code"] == 0
    assert "hi" in result["raw_output"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_pipeline_stages.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.dispatch_pipeline'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/dispatch_pipeline.py
"""Explicit dispatch stages over a DispatchRequest + HarnessAdapter (gh:#1924).

Stage order: resolve -> authorize -> prepare_worktree -> spawn -> observe -> finalize.
Each stage is independently testable with a fake adapter; none of them branch
on harness name directly -- that's entirely the adapter's job.
"""
import subprocess
from typing import Optional

from synlynk.harness_adapters.base import HarnessAdapter
from synlynk.harness_adapters.request import DispatchRequest


def resolve(request: DispatchRequest) -> DispatchRequest:
    """Harness routing. Delegates to the existing, unchanged routing logic."""
    from synlynk.dispatch import resolve_dispatch_harness
    from dataclasses import replace

    resolved_agent = resolve_dispatch_harness(
        request.agent,
        agent_id=request.agent_id,
        story_id=request.story_id,
        force_agent=request.force_agent,
        requires_gh_write=request.requires_gh_write,
        static_baseline=request.static_baseline,
        task_domain=request.task_domain,
        criticality=request.criticality,
        lambda_=request.lambda_,
        task=request.task,
        task_type=request.task_type,
        requires=request.requires,
        grants=request.grants,
        revokes=request.revokes,
    )
    return replace(request, agent=resolved_agent)


def authorize(request: DispatchRequest) -> None:
    """Policy/authority + gh-write gating. Delegates to existing checks unchanged."""
    from synlynk.dispatch import check_authority

    if request.task_type:
        try:
            authority = check_authority(
                f"task_dispatch:{request.task_type}",
                role=request.role or "dev",
                repo_path=".",
            )
        except ValueError:
            authority = None
        if authority is not None and not authority.allowed:
            raise RuntimeError(
                f"Dispatch refused: task_type {request.task_type!r} is not an authorized "
                f"task_type for role {request.role or 'dev'!r} per policy.json (see #423, #569)."
            )


def prepare_worktree(request: DispatchRequest) -> dict:
    """Worktree creation / base-ref freshness. Delegates to existing logic unchanged."""
    from synlynk.dispatch import _create_job_worktree

    return _create_job_worktree(
        agent=request.agent,
        job_id=request.job_id,
        base=request.base,
    )


def spawn(request: DispatchRequest, adapter: HarnessAdapter, env: dict, cwd: str) -> dict:
    """Build the command via the adapter and run it, returning exit code + raw output."""
    cmd = adapter.build_cmd(request)
    proc = subprocess.Popen(
        cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=env, cwd=cwd,
    )
    out, _ = proc.communicate(timeout=None)
    raw_output = out.decode("utf-8", errors="replace") if isinstance(out, bytes) else (out or "")
    return {"exit_code": proc.returncode, "raw_output": raw_output}


def observe(spawn_result: dict, adapter: HarnessAdapter) -> dict:
    """Parse the raw output and classify any failure via the adapter."""
    event = adapter.parse_output(spawn_result["raw_output"])
    failure = adapter.classify_failure(
        spawn_result["exit_code"], spawn_result["raw_output"], spawn_result["raw_output"]
    )
    return {"event": event, "failure": failure, **spawn_result}


def finalize(request: DispatchRequest, observed: dict) -> dict:
    """Job summary, telemetry, cost log. Delegates to existing logic unchanged."""
    from synlynk.dispatch import _write_job_summary

    _write_job_summary(
        job_id=request.job_id or "",
        agent=request.agent,
        story_id=request.story_id,
        result_text=observed["raw_output"],
        exit_code=observed["exit_code"],
    )
    return observed
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_dispatch_pipeline_stages.py -v`
Expected: PASS (1 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch_pipeline.py tests/test_dispatch_pipeline_stages.py
git commit -m "feat(dispatch): add dispatch_pipeline stage functions (gh:#1924)"
```

> **Note for the implementer:** `prepare_worktree` and `finalize` above call
> `_create_job_worktree` / `_write_job_summary` with a narrowed subset of
> their real keyword arguments for readability in this plan. Before wiring
> Task 6 (the compatibility shim), re-read the full current signatures of
> `_create_job_worktree` (`synlynk/dispatch.py:2220`) and `_write_job_summary`
> (`synlynk/dispatch.py:1582`) and pass through every argument
> `dispatch_agent()` currently passes them — this task's test only exercises
> `spawn`, so a signature mismatch in the other four stages won't be caught
> until Task 6's shim test.

---

### Task 6: `dispatch_agent()` compatibility shim — zero behavior change

**Files:**
- Modify: `synlynk/dispatch.py` (the body of `dispatch_agent`, currently `synlynk/dispatch.py:2950`–`3989`)
- Test: `tests/test_dispatch.py` (existing file — must keep passing unmodified)
- Test: `tests/test_dispatch_pipeline_shim.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_pipeline_shim.py
from unittest.mock import patch


def test_dispatch_agent_still_accepts_all_existing_kwargs(monkeypatch):
    """dispatch_agent()'s signature must not change shape for any existing caller."""
    import inspect
    from synlynk.dispatch import dispatch_agent

    sig = inspect.signature(dispatch_agent)
    existing_kwargs = {
        "agent", "task", "story_id", "agent_id", "force_agent", "context_mode",
        "cycle", "skip_preflight", "requires_gh_write", "static_baseline",
        "task_type", "requires", "grants", "revokes", "job_id", "issue", "base",
        "scope_paths", "session_id", "gh_write_target_kind", "gh_write_expect",
        "model", "effort", "model_tier", "role", "task_domain", "criticality",
        "lambda_", "db_conn", "_startup_failover",
    }
    assert existing_kwargs.issubset(set(sig.parameters.keys()))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_dispatch_pipeline_shim.py -v`
Expected: PASS already (signature hasn't changed yet) — this test is a guard
rail for the refactor in Step 3, not a red/green TDD step. Confirm it passes
*before* touching `dispatch_agent()`'s body, then re-run after Step 3 to
confirm it still passes.

- [ ] **Step 3: Refactor `dispatch_agent()`'s body to build a `DispatchRequest` and delegate to the pipeline stages**

This is the highest-risk step in PR1: `dispatch_agent()`'s current body
(`synlynk/dispatch.py:2950`–`3989`) inlines all the logic that Task 5's
stages now hold, interleaved with job-DB bookkeeping, telemetry, and sentinel
checks that are **not** part of this spec's scope and must not move. Do this
refactor as a pure extraction, not a rewrite:

1. Read the full current body of `dispatch_agent()` end to end first.
2. At the top, after the existing `task_type`/authority/`requires_gh_write`
   inference logic (unchanged), construct:
   ```python
   from synlynk.harness_adapters.request import DispatchRequest
   from synlynk.harness_adapters.registry import get_adapter
   from synlynk import dispatch_pipeline as pipeline

   request = DispatchRequest(
       agent=agent, task=task, story_id=story_id, agent_id=agent_id,
       force_agent=force_agent, context_mode=context_mode, cycle=cycle,
       skip_preflight=skip_preflight, requires_gh_write=requires_gh_write,
       static_baseline=static_baseline, task_type=task_type,
       requires=requires or [], grants=grants or [], revokes=revokes or [],
       job_id=job_id, issue=issue, base=base, scope_paths=scope_paths or [],
       session_id=session_id, gh_write_target_kind=gh_write_target_kind,
       gh_write_expect=gh_write_expect, model=model, effort=effort,
       model_tier=model_tier, role=role, task_domain=task_domain,
       criticality=criticality, lambda_=lambda_,
   )
   request = pipeline.resolve(request)
   pipeline.authorize(request)
   adapter = get_adapter(request.agent)
   ```
3. Replace the existing inline worktree-creation call with
   `worktree_info = pipeline.prepare_worktree(request)`, keeping every piece
   of existing bookkeeping that reads from `worktree_info` as-is.
4. **Do NOT wire `pipeline.spawn()` / `pipeline.observe()` / `pipeline.finalize()`
   into `dispatch_agent()`.** This corrects an architecture error in the
   original version of this task (caught during implementation of
   job-423915c1 / gh:#1924): `dispatch_agent()`'s real subprocess spawn
   (`synlynk/dispatch.py` around the `Popen(..., stdout=DEVNULL,
   stderr=DEVNULL, start_new_session=True)` call) is fire-and-forget — it
   returns a running `job` dict immediately and does not wait on, read the
   output of, or summarize the process. `pipeline.spawn()` (Task 5) instead
   calls `proc.communicate()`, which blocks until exit. Wiring it in here
   would turn every dispatch synchronous, a real behavior change the "zero
   behavior change" framing explicitly forbids.
   `_write_job_summary()` (what `pipeline.finalize()` wraps) confirmed to have
   no call site inside `dispatch_agent()` at all, on `origin/main`, even
   before this PR — its one production caller is `_reconcile_jobs_unlocked()`
   in `synlynk/jobs.py`, a separate ~600-line multi-branch reaper function
   (circuit-breaker trip, stall, normal exit each have their own
   `_write_job_summary()` call with different sourced args) that polls PIDs
   asynchronously and runs on every `synlynk` invocation. Wiring
   `pipeline.observe()`/`pipeline.finalize()` into that function instead is
   real, separate work — deserving its own task/PR with its own design pass
   over each terminal branch, not a drop-in swap. Tracked as a follow-up
   (file a gh issue referencing gh:#1924 before starting it); out of scope
   for PR1.
5. Leave every line of bookkeeping that isn't one of the three stages above
   (sentinel pattern checks, cost logging, circuit breaker, telemetry writes,
   the subprocess spawn itself, output handling, job-summary writing) exactly
   where it is in the function body — this step only swaps *which function*
   resolves the harness, authorizes the task type, and creates the worktree;
   it does not touch surrounding logic.

- [ ] **Step 4: Run the full existing dispatch test suite**

Run: `pytest tests/test_dispatch.py tests/test_dispatch_auto_routing.py tests/test_dispatch_capability_routing.py tests/test_dispatch_context_mode_hint.py tests/test_dispatch_cycle.py tests/test_dispatch_github_identity.py tests/test_dispatch_local_agent.py tests/test_dispatch_model_defaults.py tests/test_dispatch_model_routing.py tests/test_dispatch_nudges.py tests/test_dispatch_session_threading.py tests/test_resolve_dispatch_harness.py tests/test_dispatch_pipeline_shim.py -v`

Expected: PASS, same pass count as the pre-refactor baseline (run this same
command once *before* Step 3 and diff the pass counts — any new failure or
newly-skipped test means the extraction changed behavior and must be fixed
before continuing).

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_pipeline_shim.py
git commit -m "refactor(dispatch): route dispatch_agent() through resolve/authorize/prepare_worktree (gh:#1924)

No behavior change: every harness still resolves to LegacyAdapter, which
delegates to the exact same code dispatch_agent() called before this PR.
spawn/observe/finalize wiring is deferred to a follow-up targeting
_reconcile_jobs_unlocked() in synlynk/jobs.py, not dispatch_agent() — see
Task 6 Step 3.4 for why."
```

> **This closes PR 1.** Open a PR titled `feat(dispatch): HarnessAdapter
> foundation — DispatchRequest, Protocol, pipeline stages (gh:#1924, PR1/5)`.
> Per repo policy, assign a non-authoring reviewer and run `synlynk pr check`
> from the PR's own worktree before merge.

---

## PR 2: `CodexAdapter` pilot

### Task 7: `CodexAdapter.translate_permissions` + `build_cmd`

**Files:**
- Create: `synlynk/harness_adapters/codex.py`
- Test: `tests/test_codex_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_codex_adapter.py
from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.request import DispatchRequest


def test_codex_translate_permissions_write_grant_uses_workspace_write():
    adapter = CodexAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["-s", "workspace-write"]


def test_codex_translate_permissions_read_only_uses_read_only_profile():
    adapter = CodexAdapter()
    flags = adapter.translate_permissions([], read_only=True)
    assert flags == ["-s", "read-only"]


def test_codex_build_cmd_includes_dispatch_flags():
    adapter = CodexAdapter()
    request = DispatchRequest(agent="codex", task="fix it", permissions=["write:repo"])
    cmd = adapter.build_cmd(request)
    assert isinstance(cmd, list) and len(cmd) > 0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_codex_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_adapters.codex'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/codex.py
"""Codex HarnessAdapter -- pilot harness for the strangler migration (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest

_CODEX_NETWORK_PERMISSION = "network:*"


class CodexAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk.dispatch import _codex_network_flags

        has_write = any((perm or "").startswith("write:") for perm in (permissions or []))
        flags = []
        if read_only and _CODEX_NETWORK_PERMISSION in (permissions or []) and not has_write:
            flags = ["-s", "workspace-write"]
        elif has_write:
            flags = ["-s", "workspace-write"]
        elif read_only or (not has_write and _CODEX_NETWORK_PERMISSION not in (permissions or [])):
            flags = ["-s", "read-only"]
        if _CODEX_NETWORK_PERMISSION in (permissions or []):
            flags += _codex_network_flags(read_only=read_only and not has_write)
        return flags

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("codex")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=self._classify(raw_text))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "--ask-for-approval" in lowered and ("unrecognized" in lowered or "unknown option" in lowered):
            return FailureKind.SANDBOX_DENIED
        if "not signed in" in lowered or "please log in" in lowered:
            return FailureKind.AUTH_EXPIRED
        if "402" in lowered or "quota exceeded" in lowered or "rate limit" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        import os
        from pathlib import Path
        from synlynk.models import resolve_tier_model
        from synlynk.probe import _read_toml_string_value

        try:
            codex_home = Path(os.environ.get("CODEX_HOME", os.path.expanduser("~/.codex")))
            configured = _read_toml_string_value(str(codex_home / "config.toml"), "model")
            if configured:
                return configured
        except Exception:
            pass
        return resolve_tier_model(tier, "codex")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_codex_adapter.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add synlynk/harness_adapters/codex.py tests/test_codex_adapter.py
git commit -m "feat(dispatch): add CodexAdapter.translate_permissions + build_cmd (gh:#1924)"
```

---

### Task 8: `CodexAdapter.classify_failure` regression fixture (this session's incident)

**Files:**
- Modify: `tests/test_codex_adapter.py`

- [ ] **Step 1: Write the failing test**

```python
# Append to tests/test_codex_adapter.py
def test_codex_classify_failure_flags_ask_for_approval_incompatibility():
    """Regression fixture: this session's --ask-for-approval CLI incompatibility."""
    adapter = CodexAdapter()
    stderr = "error: unrecognized arguments: --ask-for-approval never"
    result = adapter.classify_failure(exit_code=2, stderr=stderr, raw_text=stderr)
    assert result.value == "sandbox_denied"


def test_codex_classify_failure_returns_none_for_unrelated_errors():
    adapter = CodexAdapter()
    result = adapter.classify_failure(exit_code=1, stderr="some unrelated traceback", raw_text="")
    assert result is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_codex_adapter.py -v`
Expected: FAIL if the `unrecognized` string match in Task 7's `_classify` doesn't
cover this exact phrasing — adjust the match condition in `_classify` (Task 7,
Step 3) to cover both `"unrecognized"` and `"unrecognized arguments"` if this
fails; re-run until green.

- [ ] **Step 3: Confirm it passes (no new implementation needed if Task 7's `_classify` already matches)**

Run: `pytest tests/test_codex_adapter.py -v`
Expected: PASS (5 passed total)

- [ ] **Step 4: Commit**

```bash
git add tests/test_codex_adapter.py
git commit -m "test(dispatch): add CodexAdapter regression fixture for --ask-for-approval incompatibility (gh:#1924)"
```

---

### Task 9: Register `CodexAdapter`, verify against real dispatch traffic

**Files:**
- Modify: `synlynk/harness_adapters/registry.py`

- [ ] **Step 1: Update the registry to use the real adapter for Codex**

```python
# In synlynk/harness_adapters/registry.py, replace the codex LegacyAdapter registration:
from synlynk.harness_adapters.codex import CodexAdapter

register_adapter("codex", CodexAdapter())
# Grok/Agy/Claude/local remain on LegacyAdapter until Tasks 10-12.
```

- [ ] **Step 2: Run the full existing dispatch test suite**

Run: `pytest tests/test_dispatch.py tests/test_dispatch_auto_routing.py tests/test_codex_adapter.py tests/test_dispatch_pipeline_shim.py -v`
Expected: PASS, no regressions.

- [ ] **Step 3: Commit**

```bash
git add synlynk/harness_adapters/registry.py
git commit -m "feat(dispatch): route Codex dispatches through CodexAdapter (gh:#1924)"
```

- [ ] **Step 4: Verify against real dispatch traffic before calling this proven**

This step has no code — it's a verification gate before PR3 starts. Dispatch
a small, low-risk real task to Codex (e.g., a docs-only fix) via
`synlynk dispatch codex --task "..."`, then confirm ground truth directly —
per the standing "never trust job status alone" lesson:
```bash
gh pr view <pr-number> --json state,mergedAt,reviews
git log origin/main --oneline -5
```
Do not proceed to Task 10 until at least one real Codex dispatch has been
verified this way with the new adapter path active.

> **This closes PR 2.** Open a PR titled `feat(dispatch): CodexAdapter pilot
> (gh:#1924, PR2/5)`. Same non-authoring-reviewer + `synlynk pr check`
> discipline as PR1.

---

## PR 3: `GrokAdapter` port

### Task 10: `GrokAdapter` — permissions, build_cmd, classify_failure (402/session-expiry fixtures)

**Files:**
- Create: `synlynk/harness_adapters/grok.py`
- Test: `tests/test_grok_adapter.py`
- Modify: `synlynk/harness_adapters/registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_grok_adapter.py
from synlynk.harness_adapters.grok import GrokAdapter


def test_grok_translate_permissions_nonempty_grants_always_approve():
    adapter = GrokAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]


def test_grok_translate_permissions_empty_grants_no_flags():
    adapter = GrokAdapter()
    assert adapter.translate_permissions([], read_only=False) == []


def test_grok_classify_failure_billing_exhaustion_regression_fixture():
    """Regression fixture: this session's 402 Grok Build usage balance exhausted."""
    adapter = GrokAdapter()
    raw = "API error (status 402 Payment Required): Grok Build usage balance exhausted"
    result = adapter.classify_failure(exit_code=1, stderr=raw, raw_text=raw)
    assert result.value == "quota_exhausted"


def test_grok_classify_failure_session_expiry_regression_fixture():
    """Regression fixture: this session's 'Not signed in' session expiry."""
    adapter = GrokAdapter()
    raw = "Not signed in... run grok login --device-code"
    result = adapter.classify_failure(exit_code=1, stderr=raw, raw_text=raw)
    assert result.value == "auth_expired"


def test_grok_classify_failure_sandbox_bash_denial_regression_fixture():
    """Regression fixture: this session's silent bash-denying sandbox (exit 0, no real work)."""
    adapter = GrokAdapter()
    raw = "permission denied: bash execution is not allowed in this sandbox"
    result = adapter.classify_failure(exit_code=0, stderr="", raw_text=raw)
    assert result.value == "sandbox_denied"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_grok_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_adapters.grok'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/grok.py
"""Grok HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class GrokAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        permission_set = {perm for perm in (permissions or []) if perm}
        if not permission_set:
            return []
        return ["--always-approve", "--permission-mode", "bypassPermissions"]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("grok")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=self._classify(raw_text, exit_code=0))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}", exit_code=exit_code)

    @staticmethod
    def _classify(text: str, exit_code: int) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "not signed in" in lowered or "login --device-code" in lowered:
            return FailureKind.AUTH_EXPIRED
        if "402" in lowered or "balance exhausted" in lowered or "payment required" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        if "permission denied" in lowered and "bash" in lowered:
            return FailureKind.SANDBOX_DENIED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "grok")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_grok_adapter.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Register and verify**

```python
# In synlynk/harness_adapters/registry.py:
from synlynk.harness_adapters.grok import GrokAdapter

register_adapter("grok", GrokAdapter())
```

Run: `pytest tests/test_dispatch.py tests/test_grok_adapter.py tests/test_dispatch_pipeline_shim.py -v`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add synlynk/harness_adapters/grok.py tests/test_grok_adapter.py synlynk/harness_adapters/registry.py
git commit -m "feat(dispatch): add GrokAdapter with 402/session-expiry/sandbox-denial regression fixtures (gh:#1924)"
```

> **This closes PR 3.** Verify a real Grok dispatch the same way as Task 9
> before opening `feat(dispatch): GrokAdapter port (gh:#1924, PR3/5)`.

---

## PR 4: `AgyAdapter` port

### Task 11: `AgyAdapter` — permissions, build_cmd, classify_failure (429 fixture)

**Files:**
- Create: `synlynk/harness_adapters/agy.py`
- Test: `tests/test_agy_adapter.py`
- Modify: `synlynk/harness_adapters/registry.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_agy_adapter.py
from synlynk.harness_adapters.agy import AgyAdapter


def test_agy_translate_permissions_read_only_uses_plan_mode():
    adapter = AgyAdapter()
    flags = adapter.translate_permissions(["read:*"], read_only=False)
    assert flags == ["--mode", "plan"]


def test_agy_translate_permissions_no_permissions_returns_empty():
    adapter = AgyAdapter()
    assert adapter.translate_permissions([], read_only=False) == []


def test_agy_translate_permissions_write_grant_uses_sandbox():
    adapter = AgyAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["--sandbox"]


def test_agy_classify_failure_credit_exhaustion_regression_fixture():
    """Regression fixture: this session's 429 RESOURCE_EXHAUSTED AI credits balance."""
    adapter = AgyAdapter()
    raw = 'RESOURCE_EXHAUSTED (code 429) "Your AI credits balance is too low to continue."'
    result = adapter.classify_failure(exit_code=1, stderr=raw, raw_text=raw)
    assert result.value == "quota_exhausted"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agy_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.harness_adapters.agy'`

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/agy.py
"""Agy (Gemini) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class AgyAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        if not permissions:
            return []
        if set(permissions) <= {"read:*"}:
            return ["--mode", "plan"]
        return ["--sandbox"]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("agy")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=self._classify(raw_text))

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return self._classify(f"{stderr}\n{raw_text}")

    @staticmethod
    def _classify(text: str) -> Optional[FailureKind]:
        lowered = (text or "").lower()
        if "resource_exhausted" in lowered or "429" in lowered or "credits balance" in lowered:
            return FailureKind.QUOTA_EXHAUSTED
        if "timeout waiting for response" in lowered:
            return FailureKind.AUTH_EXPIRED
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "agy")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agy_adapter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Register and verify**

```python
# In synlynk/harness_adapters/registry.py:
from synlynk.harness_adapters.agy import AgyAdapter

register_adapter("agy", AgyAdapter())
```

Run: `pytest tests/test_dispatch.py tests/test_agy_dispatch_fix.py tests/test_agy_adapter.py tests/test_dispatch_pipeline_shim.py -v`
Expected: PASS, no regressions.

- [ ] **Step 6: Commit**

```bash
git add synlynk/harness_adapters/agy.py tests/test_agy_adapter.py synlynk/harness_adapters/registry.py
git commit -m "feat(dispatch): add AgyAdapter with 429 credit-exhaustion regression fixture (gh:#1924)"
```

> **This closes PR 4.** Verify a real Agy dispatch before opening
> `feat(dispatch): AgyAdapter port (gh:#1924, PR4/5)`.

---

## PR 5: `ClaudeAdapter` + `LocalAdapter`, delete `LegacyAdapter`

### Task 12: `ClaudeAdapter`, `LocalAdapter`, remove `LegacyAdapter`

**Execution note (2026-10-07, gh:#2062):** Muse is already dispatchable through
the experimental baseline and has a live dispatch regression test. Its existing
behavior is preserved with a registry adapter in the retirement change; this
does not change the separate roadmap sequence for Muse calibration and promotion.

**Files:**
- Create: `synlynk/harness_adapters/claude.py`
- Create: `synlynk/harness_adapters/local.py`
- Delete: `synlynk/harness_adapters/legacy.py`
- Modify: `synlynk/harness_adapters/registry.py`
- Test: `tests/test_claude_adapter.py`
- Test: `tests/test_local_adapter.py`
- Modify: `tests/test_legacy_adapter.py` (delete — no longer applicable)

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_claude_adapter.py
from synlynk.harness_adapters.claude import ClaudeAdapter


def test_claude_translate_permissions_maps_tools():
    adapter = ClaudeAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags[0] == "--allowedTools"


def test_claude_translate_permissions_empty_returns_empty():
    adapter = ClaudeAdapter()
    assert adapter.translate_permissions([], read_only=False) == []
```

```python
# tests/test_local_adapter.py
import pytest
from synlynk.harness_adapters.local import LocalAdapter, PermissionEnforcementError


def test_local_translate_permissions_raises_if_any_requested():
    adapter = LocalAdapter()
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False)


def test_local_translate_permissions_empty_returns_empty():
    adapter = LocalAdapter()
    assert adapter.translate_permissions([], read_only=False) == []
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_claude_adapter.py tests/test_local_adapter.py -v`
Expected: FAIL with `ModuleNotFoundError` for both new modules.

- [ ] **Step 3: Write minimal implementation**

```python
# synlynk/harness_adapters/claude.py
"""Claude HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class ClaudeAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        from synlynk._constants import _PERMISSION_TO_TOOL_MAP

        tools = []
        for perm in permissions or []:
            tools.extend(_PERMISSION_TO_TOOL_MAP.get(perm, []))
        tools = sorted(set(tools))
        if not tools:
            return []
        return ["--allowedTools", ",".join(tools)]

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        flags = _dispatch_flags_for_agent("claude")
        flags += self.translate_permissions(request.permissions, request.read_only)
        return flags

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=None)

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "claude")
```

```python
# synlynk/harness_adapters/local.py
"""Local (aider/oMLX) HarnessAdapter (gh:#1924)."""
from typing import Optional

from synlynk.harness_adapters.base import DispatchEvent, FailureKind
from synlynk.harness_adapters.request import DispatchRequest


class PermissionEnforcementError(RuntimeError):
    pass


class LocalAdapter:
    def translate_permissions(self, permissions: list, read_only: bool) -> list:
        if permissions:
            raise PermissionEnforcementError(
                f"local (aider) has no mechanism to enforce permissions {sorted(permissions)}; "
                "aider's declared CLI flags include no read-only/file-scope restriction. "
                "Refusing to dispatch rather than silently granting full read/write access."
            )
        return []

    def build_cmd(self, request: DispatchRequest) -> list:
        from synlynk.dispatch import _dispatch_flags_for_agent

        return _dispatch_flags_for_agent("local")

    def parse_output(self, raw_text: str) -> DispatchEvent:
        return DispatchEvent(raw_text=raw_text, failure=None)

    def classify_failure(self, exit_code: int, stderr: str, raw_text: str) -> Optional[FailureKind]:
        return None

    def resolve_model(self, tier: str, effort: Optional[str]) -> str:
        from synlynk.models import resolve_tier_model

        return resolve_tier_model(tier, "local")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_claude_adapter.py tests/test_local_adapter.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Register both, delete `LegacyAdapter` and its test**

```python
# Replace the whole contents of synlynk/harness_adapters/registry.py:
from synlynk.harness_adapters.agy import AgyAdapter
from synlynk.harness_adapters.claude import ClaudeAdapter
from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.grok import GrokAdapter
from synlynk.harness_adapters.local import LocalAdapter
from synlynk.harness_adapters.base import HarnessAdapter

_ADAPTERS: dict[str, HarnessAdapter] = {}


def register_adapter(name: str, adapter: HarnessAdapter) -> None:
    _ADAPTERS[name] = adapter


def get_adapter(name: str) -> HarnessAdapter:
    return _ADAPTERS[name]


register_adapter("codex", CodexAdapter())
register_adapter("grok", GrokAdapter())
register_adapter("agy", AgyAdapter())
register_adapter("claude", ClaudeAdapter())
register_adapter("local", LocalAdapter())
```

```bash
rm synlynk/harness_adapters/legacy.py tests/test_legacy_adapter.py
```

- [ ] **Step 6: Run the full existing dispatch test suite**

Run: `pytest tests/ -k "dispatch or harness_adapter or codex_adapter or grok_adapter or agy_adapter or claude_adapter or local_adapter" -v`
Expected: PASS, no regressions, no references to `LegacyAdapter` remain.

- [ ] **Step 7: Commit**

```bash
git add synlynk/harness_adapters/ tests/test_claude_adapter.py tests/test_local_adapter.py
git rm tests/test_legacy_adapter.py
git commit -m "feat(dispatch): add ClaudeAdapter + LocalAdapter, delete LegacyAdapter (gh:#1924)

All five harnesses now route through a real HarnessAdapter. Closes the
strangler migration described in docs/superpowers/specs/2026-10-03-harness-adapter-dispatch-decomposition-design.md."
```

> **This closes PR 5 and gh:#1924.** Verify real dispatches for Claude and
> local the same way as prior PRs before opening
> `feat(dispatch): ClaudeAdapter + LocalAdapter, delete LegacyAdapter (gh:#1924, PR5/5)`.

---

## Self-Review Notes

- **Spec coverage:** All six spec sections (DispatchRequest, Protocol+registry,
  pipeline stages, compatibility shim, strangler migration order with Codex
  pilot, testing approach) map to tasks above — see coverage table at the top.
- **Placeholder scan:** No TBD/TODO; every code step is complete, runnable
  code. Task 6's extraction step is necessarily narrative (it modifies a
  1000-line function in place) but gives the exact replacement snippets and
  an explicit instruction to preserve all non-stage bookkeeping untouched.
- **Type consistency:** `DispatchRequest`, `HarnessAdapter`, `FailureKind`,
  and `DispatchEvent` are defined once (Tasks 1–2) and referenced identically
  by name in every later task; `get_adapter`/`register_adapter` signatures
  match between Task 2 and their later registry edits (Tasks 9–12).
- **Known risk carried forward explicitly:** Task 5's note flags that
  `prepare_worktree`/`finalize`'s example bodies narrow the real
  `_create_job_worktree`/`_write_job_summary` signatures for plan readability;
  the implementer must reconcile full argument lists during Task 6, not
  assume Task 5's snippets are copy-paste-complete.
