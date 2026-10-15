# Autonomy-pass daemon wiring — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development
> (recommended) or superpowers:executing-plans to implement this plan
> task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Call the already-shipped `_autonomy_pass()` (synlynk/scheduler.py)
from `SynlynkDaemon._run_loop`'s existing poll tick, under a hybrid
interval+idle trigger, so `autonomy_mode` finally has an effect on daemon
behavior without a human running `synlynk schedule`/`synlynk backlog ...`
by hand. This is Task 4 of gh:#2262 — Tasks 1-3 (goal-match threshold,
`no_goal_link` scheduler gate, `_autonomy_pass()` itself) are already merged
into `main`; this plan does not touch them.

**Spec:** `docs/superpowers/specs/2026-10-15-autonomy-pass-daemon-wiring-design.md`
(gh:#2262, story-f67acd86, linked to goal-bd5eaa14/goal-06758149)

**Tech stack:** Python 3 stdlib only (sqlite3, time). pytest for tests.

---

### Task 1: Add trigger state + `_maybe_run_autonomy_pass` to `SynlynkDaemon`

**Files:**
- Modify: `synlynk/daemon.py` (imports near top; `SynlynkDaemon.__init__`
  around line 1070-1090; new method after `_run_capability_watch_tick`,
  around line 1103-1125; `_run_loop`'s dispatch block around line
  1349-1353)
- Test: whichever of `tests/test_daemon_supervision_discovery.py` /
  `tests/test_daemon_token_refresh.py` already instantiates `SynlynkDaemon`
  without a real fork/sleep loop — check both files' existing fixtures
  before picking one or adding a new `tests/test_autonomy_pass_trigger.py`.

- [ ] **Step 1: Write the failing tests**

Add (adjust fixture names to match whatever harness the chosen test file
already provides for constructing a `SynlynkDaemon` instance in-process):

```python
def test_maybe_run_autonomy_pass_fires_on_interval_elapsed(monkeypatch):
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = 0.0
    d._last_dispatch_count = 0

    calls = {"n": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 0)

    d._maybe_run_autonomy_pass(launched=0)

    assert calls["n"] == 1
    assert d._last_dispatch_count == 0


def test_maybe_run_autonomy_pass_fires_on_idle_transition(monkeypatch):
    import time
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = time.time()  # interval just reset, won't fire on its own
    d._last_dispatch_count = 2  # previous tick launched 2 jobs

    calls = {"n": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 999999)

    class _FakeConn:
        def execute(self, query, params=()):
            class _Row:
                def fetchone(self):
                    return (0,)
            return _Row()
        def close(self):
            pass

    monkeypatch.setattr(daemon_mod, "_pkg", lambda name: (lambda: _FakeConn()) if name == "_get_db" else None)

    d._maybe_run_autonomy_pass(launched=0)  # this tick launched 0, previous tick launched 2

    assert calls["n"] == 1
    assert d._last_dispatch_count == 0


def test_maybe_run_autonomy_pass_no_trigger_does_not_fire(monkeypatch):
    import time
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = time.time()
    d._last_dispatch_count = 0  # nothing was running, so launched==0 is not an idle transition

    calls = {"n": 0}
    monkeypatch.setattr(daemon_mod, "_autonomy_pass", lambda conn=None: calls.__setitem__("n", calls["n"] + 1))
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 999999)

    d._maybe_run_autonomy_pass(launched=0)

    assert calls["n"] == 0
    assert d._last_dispatch_count == 0


def test_maybe_run_autonomy_pass_swallows_exception(monkeypatch):
    from synlynk.daemon import SynlynkDaemon
    from synlynk import daemon as daemon_mod

    d = SynlynkDaemon()
    d._last_autonomy_pass_at = 0.0
    d._last_dispatch_count = 0

    def boom(conn=None):
        raise RuntimeError("autonomy pass exploded")

    monkeypatch.setattr(daemon_mod, "_autonomy_pass", boom)
    monkeypatch.setattr(daemon_mod, "_autonomy_pass_interval_seconds", lambda: 0)

    d._maybe_run_autonomy_pass(launched=0)  # must not raise
```

(If `SynlynkDaemon()` requires more setup than a bare constructor call in
this codebase's actual test environment — e.g. a `project_dir`/chdir
fixture — wrap these four tests in whatever fixture the chosen test file's
other `SynlynkDaemon`-constructing tests already use. Check before writing
a new fixture.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest <chosen_test_file> -k maybe_run_autonomy_pass -q`
Expected: FAIL — `SynlynkDaemon` has no `_maybe_run_autonomy_pass` method,
`self._last_autonomy_pass_at`/`self._last_dispatch_count` don't exist yet,
and `synlynk.daemon` has no `_autonomy_pass`/`_autonomy_pass_interval_seconds`
names to monkeypatch.

- [ ] **Step 3: Add the import**

In `synlynk/daemon.py`, add to the existing `from synlynk...import` block
near the top of the file (alongside the other `from synlynk.X import Y`
lines, e.g. near line 16-23):

```python
from synlynk.scheduler import _autonomy_pass, _autonomy_pass_interval_seconds
```

- [ ] **Step 4: Add the new instance state**

In `SynlynkDaemon.__init__` (around line 1070-1078), add two lines right
after the existing `self._last_autonomous_run = 0.0`:

```python
        self.autonomous = autonomous
        self._last_autonomous_run = 0.0
        self._last_autonomy_pass_at = 0.0
        self._last_dispatch_count = 0
```

- [ ] **Step 5: Add `_maybe_run_autonomy_pass`**

Add a new method to `SynlynkDaemon`, placed right after
`_run_capability_watch_tick` (after the method ending around line 1124,
before `_prepare_start`):

```python
    def _maybe_run_autonomy_pass(self, launched: int) -> None:
        """Hybrid interval+idle trigger for the backlog/scheduling autonomy pass.

        Both triggers call the exact same _autonomy_pass() -- no divergent
        logic path. Resets the interval timer on every actual run so the
        two triggers can't double-fire back to back in the same tick.
        See docs/superpowers/specs/2026-10-15-autonomy-pass-daemon-wiring-design.md
        """
        import time as _time

        now = _time.time()
        interval_elapsed = (now - self._last_autonomy_pass_at) >= _autonomy_pass_interval_seconds()

        idle_transition = False
        if self._last_dispatch_count > 0 and launched == 0:
            conn = None
            try:
                conn = _pkg("_get_db")()
                row = conn.execute(
                    "SELECT COUNT(*) FROM daemon_jobs WHERE status IN ('queued','running')"
                ).fetchone()
                idle_transition = bool(row and row[0] == 0)
            except Exception:
                idle_transition = False
            finally:
                if conn is not None:
                    conn.close()

        if interval_elapsed or idle_transition:
            try:
                _autonomy_pass()
            except Exception:
                import traceback as _traceback
                _traceback.print_exc()
            self._last_autonomy_pass_at = now

        self._last_dispatch_count = launched
```

- [ ] **Step 6: Wire the call site into `_run_loop`**

In `_run_loop` (around line 1349-1353), change:

```python
            try:
                _reconcile_daemon_jobs()
                _dispatch_ready_jobs(max_parallel=max_parallel)
            except Exception:
                _traceback.print_exc()
```

to:

```python
            try:
                _reconcile_daemon_jobs()
                launched = _dispatch_ready_jobs(max_parallel=max_parallel)
            except Exception:
                _traceback.print_exc()
                launched = 0
            self._maybe_run_autonomy_pass(launched)
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest <chosen_test_file> -k maybe_run_autonomy_pass -q`
Expected: PASS

- [ ] **Step 8: Run the full daemon test suite to check for regressions**

Run: `pytest tests/test_daemon_supervision_discovery.py tests/test_control_plane_daemon_health.py tests/test_daemon_liveness_1572.py tests/test_daemon_token_refresh.py tests/test_vizor_daemon.py -q`
Expected: PASS

- [ ] **Step 9: Commit**

```bash
git add synlynk/daemon.py <chosen_test_file>
git commit -m "feat(daemon): wire hybrid interval+idle autonomy-pass trigger into poll loop (gh:#2262 Task 4)

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_01AEEUKUxhneCr5htf6Nwk68"
```

---

### Task 2: Full-suite verification and PR

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `pytest -q` (per gh:#2240's standing feedback memory — `-q`, not `-v`,
to avoid an oversized transcript on resend).
Expected: all tests pass, or only the pre-existing sparse-checkout-worktree
failures already catalogued this week (PR #2324's dispatch job: 54
failed/18 errors, all root-caused to missing `githooks/`, `scripts/`,
`.github/` in a sparse dispatch worktree, not to any diff). If a *new*
failure type shows up beyond that catalogued set, stop and investigate
before opening the PR.

- [ ] **Step 2: Manual smoke check — daemon actually fires the pass**

After merge, restart the daemon (`synlynk daemon stop && synlynk daemon
start`) from the canonical repo root and tail `.synlynk/daemon.log` for at
least one `watch_interval_seconds`-length tick, then set
`autonomy_pass_interval_seconds` low (e.g. `30`) in `.synlynk/config.json`
temporarily and confirm `_autonomy_pass`'s own stage output (or absence of
errors) appears in the log within that window. Revert the interval
override afterward — this is a one-off manual verification step, not a
permanent config change.

- [ ] **Step 3: Open the PR**

Follow CLAUDE.md's PR Review Discipline: assign a non-authoring,
cross-harness+model reviewer; the reviewer's own dispatch runs `synlynk pr
check` and performs the merge itself. Link the PR to story-f67acd86 /
goal-bd5eaa14 (100% GOVERNS adherence) and reference gh:#2262.

No `.synlynk/vizor-workspace-map.json` update needed — this PR is entirely
internal to synlynk's own daemon/scheduler modules, no cross-repo
relationship changes. Note that explicitly in the PR per the Workspace Map
Update Protocol.

---

## Execution Handoff

Per CLAUDE.md's Capability-Based Task Allocation, implementation and
testing are delegated to Agy/Grok/Codex via `synlynk dispatch` — the home
Claude session (PM/review/deploy lane) does not execute Task 1 directly.
Dispatch Task 1 as a single `synlynk dispatch` job
(`synlynk dispatch --role dev --story story-f67acd86 --task "<task text>"
<harness-hint>`), matching the pattern already used for gh:#2261/#2263 and
today's daemon-cwd-health fix (PR #2324). Task 2's full-suite run + PR open
follows after Task 1's dispatch completes and lands; the reviewer-dispatch
performs the actual merge per PR Review Discipline §3.
