# SYNLYNK_STATE_DB_PATH Override Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let an operator/harness force `_get_db()` to use an explicit, unconditional DB path via the `SYNLYNK_STATE_DB_PATH` env var, so dispatch works under sandboxes restricted to the repo workspace root (#681), where the existing home-path and tmpdir fallbacks are both unreachable.

**Architecture:** Add a single early-return branch at the top of `_get_db()` (`synlynk/__init__.py:1031`) that checks `os.environ.get("SYNLYNK_STATE_DB_PATH")`. If set, connect to that path directly — skipping `assert_not_nested_product_ledger`, `sandbox_fallback_db_path`, and the existing retry loop entirely — and let any failure propagate uncaught.

**Tech Stack:** Python 3 stdlib (`os`, `sqlite3`), `pytest` + `monkeypatch`/`tmp_path` fixtures (matches existing `tests/test_get_db_sandbox_fallback.py` conventions).

---

### Task 1: Add failing tests for the override behavior

**Files:**
- Modify: `tests/test_get_db_sandbox_fallback.py` (append new tests after the existing 4, which end at line 129)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_get_db_sandbox_fallback.py`:

```python
def test_get_db_override_env_var_used_verbatim(tmp_path, monkeypatch):
    """SYNLYNK_STATE_DB_PATH, when set, is used exactly as given."""
    import synlynk

    override = tmp_path / "custom" / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(override))
    # A normally-fine DB_PATH must NOT be touched when override is set.
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "unused" / "state.db"))

    conn = synlynk._get_db()
    try:
        conn.execute("SELECT 1").fetchone()
        assert override.exists()
        assert not (tmp_path / "unused").exists()
    finally:
        conn.close()


def test_get_db_override_wins_even_when_primary_would_succeed(tmp_path, monkeypatch):
    """Override takes precedence over a perfectly writable primary path."""
    import synlynk

    primary = tmp_path / "primary" / "state.db"
    override = tmp_path / "override" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(primary))
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(override))

    conn = synlynk._get_db()
    try:
        conn.execute("SELECT 1").fetchone()
        assert override.exists()
        assert not primary.exists()
    finally:
        conn.close()


def test_get_db_override_failure_propagates_without_fallback(tmp_path, monkeypatch):
    """An unwritable override path raises directly; no fallback is attempted."""
    import synlynk

    override = tmp_path / "blocked" / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(override))
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "primary" / "state.db"))

    def always_fail(path, exist_ok=False):
        raise OSError(errno.EROFS, "Read-only file system", path)

    monkeypatch.setattr(os, "makedirs", always_fail)

    with pytest.raises(OSError, match="Read-only file system"):
        synlynk._get_db()

    # No fallback DB should have been created anywhere.
    assert not (tmp_path / "primary").exists()


def test_get_db_override_bypasses_nested_worktree_guard(tmp_path, monkeypatch):
    """Override path under a worktree-like tree succeeds (guard bypassed)."""
    import synlynk

    override = tmp_path / ".claude" / "worktrees" / "job-1" / ".synlynk" / "state.db"
    monkeypatch.setenv("SYNLYNK_STATE_DB_PATH", str(override))
    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "primary" / "state.db"))

    conn = synlynk._get_db()
    try:
        conn.execute("SELECT 1").fetchone()
        assert override.exists()
    finally:
        conn.close()


def test_get_db_unset_override_preserves_existing_behavior(tmp_path, monkeypatch):
    """No SYNLYNK_STATE_DB_PATH means DB_PATH is used exactly as before."""
    import synlynk

    monkeypatch.delenv("SYNLYNK_STATE_DB_PATH", raising=False)
    primary = tmp_path / "primary" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(primary))

    conn = synlynk._get_db()
    try:
        conn.execute("SELECT 1").fetchone()
        assert primary.exists()
    finally:
        conn.close()
```

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `pytest tests/test_get_db_sandbox_fallback.py -v -k override`
Expected: 5 failures (or errors) — `SYNLYNK_STATE_DB_PATH` isn't read anywhere yet, so every override test either falls through to `DB_PATH` behavior or leaves the wrong file on disk. The `test_get_db_unset_override_preserves_existing_behavior` test may pass already (that's fine — it's the regression guard for Task 2's change and should stay green throughout).

---

### Task 2: Implement the override in `_get_db()`

**Files:**
- Modify: `synlynk/__init__.py:1031-1076` (the `_get_db` function body and docstring)

- [ ] **Step 1: Update the docstring and add the override branch**

Replace the current `_get_db` function (lines 1031–1076) with:

```python
def _get_db() -> _sqlite3.Connection:
    """Returns a WAL-mode SQLite connection to state.db, running migrations.

    SYNLYNK_STATE_DB_PATH, if set, is used verbatim and takes precedence over
    everything below: no nested-worktree guard, no fallback chain. A caller
    setting this env var has made a deliberate choice about ledger location
    (e.g. a sandbox restricted to the repo workspace root, where neither the
    home path nor the tmpdir fallback is reachable). If that path is itself
    unwritable, the resulting exception propagates uncaught — an explicit
    override that fails should surface loudly, not be silently re-routed.
    See #681.

    Falls back to ./.synlynk/state.db when the centralised path under
    ~/.synlynk/projects/<key>/ is unwritable. Dispatched-agent sandboxes
    commonly mount $HOME read-only; that surfaces as OSError(EROFS) from
    os.makedirs (not PermissionError) or as sqlite3.OperationalError from
    connect when the directory already exists. See #648.

    Primary product ledger must not live under job/feature worktrees when the
    home path is the intended path (#330 / fleet S2a). Sandbox fallback after
    OSError/OperationalError uses a path that never lands under worktrees
    (tmpdir when cwd is a job/feature worktree) so nested_state matrix stays clean.
    """
    override = os.environ.get("SYNLYNK_STATE_DB_PATH")
    if override:
        os.makedirs(os.path.dirname(override), exist_ok=True)
        conn = _sqlite3.connect(override)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA foreign_keys=ON")
        _migrate_db(conn)
        return conn

    from synlynk.fleet import assert_not_nested_product_ledger, sandbox_fallback_db_path

    db_path = DB_PATH
    fallback_path = sandbox_fallback_db_path()
    tried_fallback = False
    while True:
        try:
            # Refuse nested worktree product ledger on the primary attempt only.
            if not tried_fallback:
                assert_not_nested_product_ledger(db_path, home_writable=True)
            os.makedirs(os.path.dirname(db_path), exist_ok=True)
            conn = _sqlite3.connect(db_path)
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA foreign_keys=ON")
            _migrate_db(conn)
            return conn
        # OSError covers PermissionError, EROFS (read-only mounts), ENOSPC, etc.
        # OperationalError covers "unable to open database file" when the dir
        # exists but the file/FS is still unwritable (sandbox case in #648).
        # RuntimeError from nested-ledger refusal must not trigger fallback.
        except (OSError, _sqlite3.OperationalError) as exc:
            if tried_fallback:
                raise
            print(
                f"warning: cannot open project state DB at {db_path} ({exc}); "
                f"no project state found on this machine — falling back to "
                f"local {fallback_path}",
                file=sys.stderr,
            )
            db_path = fallback_path
            tried_fallback = True
```

Note: `os`, `sys`, and `sqlite3 as _sqlite3` are already imported at the top of `synlynk/__init__.py` (lines 3, 4, 15) — no new imports needed.

- [ ] **Step 2: Run the override tests to verify they now pass**

Run: `pytest tests/test_get_db_sandbox_fallback.py -v -k override`
Expected: PASS (5 passed)

- [ ] **Step 3: Run the full sandbox-fallback test file to check for regressions**

Run: `pytest tests/test_get_db_sandbox_fallback.py -v`
Expected: PASS (9 passed — the original 4 plus the 5 new ones)

- [ ] **Step 4: Run the broader DB test suite**

Run: `pytest tests/test_db.py tests/test_get_db_sandbox_fallback.py -v`
Expected: PASS, 0 failures

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_get_db_sandbox_fallback.py
git commit -m "fix: add SYNLYNK_STATE_DB_PATH override for restricted sandboxes (#681)

Lets an operator/harness force an explicit, unconditional DB path when
neither the home path nor the tmpdir fallback is reachable under a
sandbox restricted to the repo workspace root."
```

---

### Task 3: Full test suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: PASS, 0 failures, 0 new errors relative to the pre-change baseline

- [ ] **Step 2: If any unrelated test fails**

Stop and report the failure to the user before proceeding — do not modify unrelated tests to force a pass.

---

## Notes for the implementing agent

- Per this repo's `SYNLYNK_STATE_DB_PATH` docstring change, keep the existing `#648`/`#330` references in the docstring intact — they document *why* the fallback chain below the override exists, and should not be removed.
- Do not add a config-file (`.synlynk/config.json`) key for this — the approved design is env-var-only.
- Do not add a preflight diagnostic or new documentation file — those are explicitly out of scope per the design spec (`docs/superpowers/specs/2026-08-03-state-db-path-override-design.md`).
