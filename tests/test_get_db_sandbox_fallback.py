"""Regression tests for #648: _get_db sandbox fallback.

Dispatched-agent sandboxes often mount $HOME read-only. Creating
~/.synlynk/projects/<key>/ raises OSError(EROFS) — a plain OSError, not
PermissionError. _get_db must fall back to ./.synlynk/state.db and warn
instead of crashing with sqlite3.OperationalError / uncaught OSError.
"""

from __future__ import annotations

import errno
import os
import sqlite3

import pytest


def test_get_db_falls_back_on_erofs_oserror(tmp_path, monkeypatch, capsys):
    """OSError(EROFS) from makedirs (not PermissionError) must fall back."""
    import synlynk

    primary = tmp_path / "readonly_home" / "projects" / "deadbeef" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(primary))
    monkeypatch.chdir(tmp_path)

    real_makedirs = os.makedirs
    calls = {"n": 0}

    def fake_makedirs(path, exist_ok=False):
        calls["n"] += 1
        if calls["n"] == 1:
            # Plain OSError, NOT PermissionError — the sandbox case from #648.
            raise OSError(errno.EROFS, "Read-only file system", path)
        return real_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(os, "makedirs", fake_makedirs)

    conn = synlynk._get_db()
    try:
        # Usable connection against the in-repo fallback path.
        conn.execute("SELECT 1").fetchone()
        fallback = tmp_path / ".synlynk" / "state.db"
        assert fallback.exists(), "expected fallback .synlynk/state.db"
        assert not primary.exists(), "primary path must not have been created"
    finally:
        conn.close()

    err = capsys.readouterr().err
    assert "falling back" in err.lower()
    assert "no project state" in err.lower() or "cannot open" in err.lower()


def test_get_db_falls_back_on_permissionerror(tmp_path, monkeypatch, capsys):
    """PermissionError (existing path) still falls back and warns."""
    import synlynk

    primary = tmp_path / "no_access" / "state.db"
    monkeypatch.setattr(synlynk, "DB_PATH", str(primary))
    monkeypatch.chdir(tmp_path)

    real_makedirs = os.makedirs
    calls = {"n": 0}

    def fake_makedirs(path, exist_ok=False):
        calls["n"] += 1
        if calls["n"] == 1:
            raise PermissionError(errno.EACCES, "Permission denied", path)
        return real_makedirs(path, exist_ok=exist_ok)

    monkeypatch.setattr(os, "makedirs", fake_makedirs)

    conn = synlynk._get_db()
    try:
        conn.execute("SELECT 1").fetchone()
        assert (tmp_path / ".synlynk" / "state.db").exists()
    finally:
        conn.close()

    err = capsys.readouterr().err
    assert "falling back" in err.lower()


def test_get_db_falls_back_on_sqlite_operational_error(tmp_path, monkeypatch, capsys):
    """sqlite3.OperationalError on connect (dir exists, FS read-only) falls back."""
    import synlynk

    primary = tmp_path / "primary" / "state.db"
    # Pre-create the directory so makedirs succeeds; connect is what fails.
    primary.parent.mkdir(parents=True)
    monkeypatch.setattr(synlynk, "DB_PATH", str(primary))
    monkeypatch.chdir(tmp_path)

    real_connect = synlynk._sqlite3.connect
    calls = {"n": 0}

    def fake_connect(path, *a, **k):
        calls["n"] += 1
        if os.path.abspath(str(path)) == os.path.abspath(str(primary)):
            raise sqlite3.OperationalError("unable to open database file")
        return real_connect(path, *a, **k)

    monkeypatch.setattr(synlynk._sqlite3, "connect", fake_connect)

    conn = synlynk._get_db()
    try:
        conn.execute("SELECT 1").fetchone()
        assert (tmp_path / ".synlynk" / "state.db").exists()
    finally:
        conn.close()

    err = capsys.readouterr().err
    assert "falling back" in err.lower()
    assert "unable to open database file" in err or "cannot open" in err.lower()


def test_get_db_reraise_when_fallback_also_fails(tmp_path, monkeypatch):
    """If both primary and fallback fail, the exception must propagate."""
    import synlynk

    monkeypatch.setattr(synlynk, "DB_PATH", str(tmp_path / "p" / "state.db"))
    monkeypatch.chdir(tmp_path)

    def always_fail(path, exist_ok=False):
        raise OSError(errno.EROFS, "Read-only file system", path)

    monkeypatch.setattr(os, "makedirs", always_fail)

    with pytest.raises(OSError, match="Read-only file system"):
        synlynk._get_db()


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
