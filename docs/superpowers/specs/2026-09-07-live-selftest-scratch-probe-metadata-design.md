# Live selftest scratch-DB probe metadata — design

**Date:** 2026-09-07
**Status:** Draft (needs Nikhil sign-off; no implementation until approved)
**Issue:** #1486 (follow-up to #1484 / PR #1485, merged as `6bb73fec`)
**Author:** Claude (design-only investigation). No production code changed in this branch.

## 1. What this ticket asked

> The #1485 remediation merged as `6bb73fec`, but `synlynk selftest --live` from that exact
> merged tip still produces 127 passed, 4 failed: `dispatch[claude]`, `dispatch[codex]`,
> `dispatch[grok]`, and `dispatch[local]` report no probe data in the scratch repo. Reproduce
> from a clean checkout at origin/main. Investigate how probe metadata is provisioned into the
> selftest scratch state; preserve fail-loud behavior and add an end-to-end regression proving
> the live path is green.

This doc is the root-cause investigation and fix design. No implementation until sign-off
(Brainstorm-First policy).

## 2. Reproduction (clean checkout, exactly as the issue asks)

```
cd /tmp && git clone <repo-root> synlynk-clean-1486
cd synlynk-clean-1486 && git checkout origin/main   # tip is 6bb73fec
python3 -c "import synlynk as s; print(s._project_root()); print(s.DB_PATH)"
# -> /private/tmp/synlynk-clean-1486
# -> /Users/nikhilsoman/.synlynk/projects/cf76f4a5/state.db   (does not exist)
```

Driving `_ensure_workspace_scaffold` / `_provision_probe_metadata` (synlynk/selftest.py, the
exact code PR #1485 added) from inside that clean checkout, then running the same two
preflight functions `dispatch_agent()` calls (`_dispatch_capability_preflight`,
`_preflight_dispatch` in synlynk/dispatch.py) against the resulting scratch DB reproduces the
issue verbatim:

```
claude => preflight passed: False | reason: no probe data for agent; run synlynk probe claude
codex  => preflight passed: False | reason: no probe data for agent; run synlynk probe codex
grok   => preflight passed: False | reason: no probe data for agent; run synlynk probe grok
local  => preflight passed: False | reason: no probe data for agent; run synlynk probe local
```

This is the exact string `_preflight_dispatch` returns at synlynk/dispatch.py:2344 when
`db_conn.execute("... WHERE harness_name=?")` finds no row.

Control: running the identical repro from **this** worktree (which shares `_project_root()`
with the main synlynk checkout, whose ledger has real `synlynk probe` rows from today's
session) does **not** reproduce — every agent passes preflight. That difference is the root
cause signal.

## 3. Root cause

`DB_PATH` is not a fixed path — `synlynk/__init__.py:874` `_resolve_db_path()` keys it off an
md5 hash of `_project_root()` (the git common-dir of the current checkout):

```python
def _resolve_db_path() -> str:
    root = _project_root()
    key = _h.md5(root.encode()).hexdigest()[:8]
    return os.path.expanduser(f"~/.synlynk/projects/{key}/state.db")
```

PR #1485's `_provision_probe_metadata()` (synlynk/selftest.py:114) reads from
`synlynk_pkg._get_db()` **before** patching `DB_PATH`, i.e. from whatever ledger the *invoking
checkout's own path* resolves to, and copies those `harness_records` rows into the scratch
workspace's isolated DB:

```python
source_conn = synlynk_pkg._get_db()          # <- real ledger for THIS checkout path
rows = source_conn.execute("SELECT ... FROM harness_records").fetchall()
...
if not rows:
    return 0                                  # <- silently copies nothing, by design
```

This mechanism is not broken — I verified independently (§2, and again directly against this
worktree's already-probed ledger) that the copy faithfully round-trips whatever is in the
source table, including all five current baselines (`claude`, `codex`, `grok`, `local`,
`agy`), through the exact `DB_PATH`-patched destination path `_dispatch_scenario` /
`_exec_scenario` use. The `INSERT OR REPLACE`, the destination path computation
(`workspace / ".synlynk" / "state.db"`), and the scratch-workspace scaffolding are all
correct.

**The actual gap is a false premise**: PR #1485's fix assumes "the current workspace" already
has authoritative probe records to copy — true only if `synlynk probe` has previously been run
from that *exact checkout path* (because the ledger key is a hash of `_project_root()`, a
fresh clone/worktree never shares a prior checkout's key). It happened to hold on the
developer machine that authored and reviewed #1485 (this repo's ledger has been probed
repeatedly all day), so the fix looked correct. It does not hold for:

- a genuinely clean `git clone` (the issue's own repro instructions),
- CI runners,
- any freshly created dispatch worktree that hasn't independently run `synlynk probe`.

`synlynk selftest --live` never calls `synlynk probe` (or any equivalent) itself, so on any of
those paths the source table is empty and `_provision_probe_metadata` — correctly, per its own
docstring ("Never synthesize records") — copies zero rows. Every `dispatch[<agent>]` and
`exec[<agent>]` scenario then hits the real, unmodified `_preflight_dispatch` "no probe data"
block. This is not a regression in preflight logic; it is `synlynk selftest --live` failing to
establish its own precondition.

### Why PR #1485's regression test didn't catch this

`test_make_live_selftest_provision_probe_metadata` (tests/test_agent_cli.py, added by #1485)
seeds the **source** DB directly with a hand-written `INSERT` and `monkeypatch.setattr(synlynk,
"DB_PATH", str(source_db))`, then asserts the copy landed in the scratch DB. It proves the copy
mechanism works when the source already has rows — it never exercises the "source ledger has
never been probed" case, which is exactly the case `synlynk selftest --live` hits on a clean
checkout. This is the same class of gap as the pytest-worktree-isolation guard in
`_get_db()` (`_should_isolate_worktree_db`): a test that is green under `PYTEST_CURRENT_TEST`
can diverge from a real CLI invocation's environment. Not a new instance of that mechanism,
just the same shape of "test env implicitly differs from the CLI env" trap.

### Two separate, unrelated observations along the way (not part of this fix)

- `_dispatch_scenario` / `_exec_scenario` never call `_ensure_workspace_scaffold` — they reuse
  `ctx.repo_path`, which `run_selftest(live=True)` (selftest.py:1415-1422) sets to the *same*
  scratch workspace `_ensure_workspace_scaffold` already returned once, up front. So in
  practice the paths agree today, but this is coincidental sequencing in `run_selftest`, not an
  invariant `_dispatch_scenario` itself enforces. Not touching this — no observed failure
  traces to it, and reproduction confirms path agreement holds on `origin/main`. Flagging only
  so a future refactor of `run_selftest`'s scratch-workspace wiring doesn't silently reintroduce
  a path mismatch.
- `_dispatch_capability_preflight`'s `trusted = _probe_results_trustworthy()` gate
  (dispatch.py:2012) is hardcoded `return False` pending #578/#580. This makes that function's
  own probe-coverage branch always resolve to `"no_coverage"` regardless of DB content — but
  since none of the four failing scenarios declare `--requires`, that function's `no_coverage`
  branch is non-blocking (`passed: True, status: "degraded"`) and only prints a warning. It is
  `_preflight_dispatch` (the second, independent preflight call, gated on
  `valid_flags or required_flags` being declared in `HARNESS_CAPABILITY_BASELINES`) that
  produces the hard fail reproduced above. `_probe_results_trustworthy()` is unrelated to
  #1486's failure and stays out of scope here.

## 4. Smallest safe fix

Make the live selftest self-sufficient: if the source ledger has no (or no relevant) probe
rows when `_ensure_workspace_scaffold` goes to provision the scratch DB, run a **real** probe
against the source ledger first, then copy — instead of silently copying nothing.

`synlynk/probe.py:cmd_probe(agent=None, write_fence=True)` already does exactly the probe work
needed (iterates `HARNESS_CAPABILITY_BASELINES`, writes real `harness_records` rows via
`_probe_agent`). Reuse it rather than inventing new probe logic:

```python
def _provision_probe_metadata(workspace: Path) -> int:
    import synlynk as synlynk_pkg
    from synlynk.probe import cmd_probe

    source_conn = synlynk_pkg._get_db()
    try:
        rows = source_conn.execute(
            "SELECT harness_name, installed_version, compliance_status, "
            "active_contract, active_flags, last_probe_at, capability_hash "
            "FROM harness_records"
        ).fetchall()
    except sqlite3.Error:
        rows = []
    finally:
        source_conn.close()

    if not rows:
        # No prior `synlynk probe` has run against this checkout's ledger (fresh clone,
        # CI runner, fresh dispatch worktree). Probe for real rather than silently
        # copying nothing — the scratch DB must reflect real, current tool availability,
        # never a synthesized/assumed value.
        cmd_probe(write_fence=False)
        source_conn = synlynk_pkg._get_db()
        try:
            rows = source_conn.execute(
                "SELECT harness_name, installed_version, compliance_status, "
                "active_contract, active_flags, last_probe_at, capability_hash "
                "FROM harness_records"
            ).fetchall()
        finally:
            source_conn.close()

    if not rows:
        return 0
    ... # unchanged INSERT OR REPLACE into the scratch DB
```

Key decisions:

- **`write_fence=False`.** `cmd_probe`'s default writes synlynk harness fences into the
  invoking checkout's real instruction files (CLAUDE.md etc. — see `_fence_exists` /
  `_probe_agent`). A selftest run must not mutate the real repo's tracked files as a side
  effect of a diagnostic command. Fence maintenance stays exclusively the job of an explicit
  `synlynk probe` invocation.
- **Probe only when the source table is empty**, not on every live-selftest run. A ledger that
  already has rows (any machine that has run `synlynk probe` before, including CI that primes
  it in an earlier step) must not eat the extra probe latency/subprocess cost on every
  `selftest --live` invocation. This mirrors the existing 1-hour staleness window used
  elsewhere in preflight (dispatch.py `_is_stale` check at line ~2295) conceptually, but is
  intentionally simpler: "zero rows" is the only trigger, not "stale rows," because re-probing
  on every run regardless of freshness would make `selftest --live` measurably slower and does
  not match what #1486 asked for (fixing the missing-data case, not adding continuous
  freshness enforcement — that's #578/#580's territory).
- **Fail loud, unchanged.** If a real probe genuinely fails for one of the Core 4 (tool not
  installed, network unavailable, etc.), `cmd_probe` still writes that failure's real
  `compliance_status` into `harness_records`, and `_preflight_dispatch` still blocks that
  agent's dispatch scenario with the real reason — never with the generic "no probe data"
  message once a probe has actually been attempted. This preserves the fail-loud requirement
  from #1486: a probe that failed must remain visible, only a probe that was **never run**
  gets auto-triggered.
- **No change to `_dispatch_capability_preflight` or `_preflight_dispatch`.** Both already do
  the right thing once the ledger has real data; the gap was entirely upstream, in provisioning.

### Alternatives considered and rejected

- *Weaken `_preflight_dispatch`'s "no probe data" block for selftest specifically* (e.g. skip
  it under a selftest-only env var). Rejected: PR #1485's own stated goal was "keep normal
  dispatch preflight behavior," and #1486 explicitly asks to "preserve fail-loud behavior" —
  special-casing the check would make the live selftest stop testing the real preflight path,
  defeating its purpose.
- *Synthesize placeholder rows when the source table is empty.* Rejected outright — this is the
  exact behavior `_provision_probe_metadata`'s own docstring forbids ("Never synthesize
  records: an absent or failing real probe must remain visible"), and it would make the live
  selftest pass without ever proving the Core 4 tools are actually reachable in the environment
  running it.
- *Require operators to run `synlynk probe` manually before `selftest --live`.* Rejected as the
  fix: it "fixes" the symptom via a documentation/process requirement instead of the tool being
  self-sufficient, and is exactly the kind of precondition-drift #1486 was filed to close.

## 5. Sentinel interactions

- Today, a failed live-selftest dispatch scenario already flows through
  `dispatch_agent()`'s normal preflight failure path (dispatch.py:2875-2878), which calls
  `_write_sentinel_alert("CRITICAL", "HARNESS_PREFLIGHT_FAIL", reason, sentinel_path)` with
  `sentinel_path = ".synlynk/sentinel.md"` relative to cwd. Because `_dispatch_scenario` /
  `_exec_scenario` `os.chdir(ctx.repo_path)` into the *scratch* workspace before calling
  `dispatch_agent`, this alert lands in the scratch workspace's own `.synlynk/sentinel.md`,
  which is discarded with the `tempfile.TemporaryDirectory`. **No real-repo sentinel.md
  pollution occurs today, and the fix must preserve that**: `cmd_probe(write_fence=False)`
  writes only to the real ledger's `harness_records` table (via `_get_db()`, unpatched at the
  point it's called — before the `DB_PATH` patch for the scratch copy), not to any sentinel
  file, so no new sentinel-file side effect is introduced by this fix in either the real repo
  or the scratch workspace.
- If the auto-triggered probe itself fails for an agent (tool missing, etc.), that failure is
  recorded as a normal `compliance_status != "ok"` row exactly the way an operator-run
  `synlynk probe` would record it — same downstream `HARNESS_VERSION_DRIFT` /
  `HARNESS_PREFLIGHT_FAIL` sentinel semantics as any other probe failure, nothing selftest-specific.

## 6. Regression tests to add

1. **New unit test** (tests/test_agent_cli.py, alongside
   `test_make_live_selftest_provision_probe_metadata`): seed an **empty** source DB (no
   `harness_records` rows at all — the clean-checkout case), monkeypatch `cmd_probe` to a stub
   that inserts a known fixture row instead of shelling out to real CLIs, call
   `_ensure_workspace_scaffold`, and assert (a) the stub was invoked with `write_fence=False`,
   and (b) the scratch DB ends up with the fixture row. This is the direct regression for
   today's bug — the existing test only covers the already-populated-source case.
2. **New unit test**: source DB already has rows → assert `cmd_probe` is **not** called (guards
   the "don't re-probe every run" performance decision in §4).
3. **End-to-end regression proving the live path is green**, as #1486 asks: a test that runs
   `run_selftest(live=True)` (or `cmd_selftest(live=True)`) from a fixture git repo whose
   `_project_root()` hash is guaranteed fresh (e.g. `monkeypatch` `_resolve_db_path`/`DB_PATH`
   to a `tmp_path`-scoped ledger with zero rows, the same pattern
   `test_dispatch_scenario_patches_db_path_to_scratch_workspace` already uses), with `cmd_probe`
   stubbed to avoid spawning real Core 4 CLIs, and asserts none of the `dispatch[*]` /
   `exec[*]` results contain `"no probe data"` in their `detail`. This is the test class
   #1486 explicitly asked for and that PR #1485 lacked — proving the **full live selftest
   invocation** is green, not just the provisioning helper in isolation.
4. Extend `tests/test_selftest.py`'s existing dispatch-scenario suite (it already monkeypatches
   `discover_agents` and `dispatch_agent` around line 214+) with a case that does *not* stub
   `dispatch_agent`'s preflight, to catch any future regression in the real
   `_dispatch_capability_preflight` / `_preflight_dispatch` chain the other dispatch-scenario
   tests currently bypass by mocking `dispatch_agent` wholesale.

Verification command for all of the above once implemented:
```
pytest tests/test_agent_cli.py -k 'provision_probe_metad or live_selftest' -v
pytest tests/test_selftest.py -q
```
(Do not use a guessed `-k` selector derived only from the issue title — verify the exact test
names once written, per this ticket's own "How to Verify" note.)

## 7. Rollback plan

The fix is additive and fully contained inside `_provision_probe_metadata`
(synlynk/selftest.py) — no schema change, no change to `_preflight_dispatch` /
`_dispatch_capability_preflight`, no change to `cmd_probe`'s public signature (it already
accepts `write_fence`). Rollback is a single revert of the follow-up PR; nothing else in the
codebase depends on the new "probe when empty" branch. No data migration, no state left behind
beyond the same scratch-workspace tempdir cleanup that already happens today.

## 8. Acceptance criteria

- [ ] `synlynk selftest --live`, run from a **clean `git clone` of `origin/main`** (no prior
      `synlynk probe` run against that checkout path), reports 0 `dispatch[*]` / `exec[*]`
      failures with reason `"no probe data for agent"`.
- [ ] `synlynk selftest --live`, run twice in a row from the same already-probed checkout,
      does not re-invoke `cmd_probe` on the second run (source ledger already has rows) —
      i.e. the fix does not add a probe subprocess spawn to every invocation, only to the
      cold-start case.
- [ ] A genuinely failing/missing Core-4 CLI (e.g. `codex` binary not on `PATH`) still surfaces
      as a real, specific preflight failure in the live selftest output — never silently
      passes and never reverts to the generic "no probe data" message once a probe has been
      attempted.
- [ ] `cmd_probe` invoked from inside `_provision_probe_metadata` never writes harness fences
      into the real repo's instruction files (`write_fence=False` verified by test).
- [ ] No new `.synlynk/sentinel.md` writes in the **real** repo (outside the ephemeral scratch
      workspace) attributable to a live selftest run.
- [ ] New end-to-end regression test (per §6.3) passes and is the test cited in the follow-up
      PR's verification section — not a re-run of #1485's existing (insufficient) unit test.
- [ ] `pytest tests/test_agent_cli.py tests/test_selftest.py -q` green with no new failures.
