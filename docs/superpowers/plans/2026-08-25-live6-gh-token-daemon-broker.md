# LIVE-6 (#1140) GitHub App Token Daemon Cache Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move GitHub App JWT-signing and token-minting out of `synlynk dispatch`'s code path (where it triggers Claude Code's auto-mode classifier) into the existing `synlynk daemon`, which refreshes all role tokens on a timer and caches them to disk; `dispatch` becomes a pure reader of that cache.

**Architecture:** `synlynk/github_app_auth.py` splits `get_installation_token()` into `refresh_installation_token()` (daemon-only: signs + mints + writes `.synlynk/github_apps/<role>.token.json`) and `read_cached_installation_token()` (dispatch-only: pure file read, no signing, no network). `synlynk/daemon.py`'s `WatchDaemon` calls `refresh_installation_token()` for every provisioned role once at startup and every 50 minutes thereafter. `synlynk/dispatch.py` and `synlynk/team.py`'s `cmd_identity_init_role()` are repointed to the new split functions.

**Tech Stack:** Python 3 stdlib only (`subprocess`, `urllib.request`, `json`, `os`, `time`) — no new dependencies.

---

### Task 1: Split `get_installation_token()` into `refresh_installation_token()` + `read_cached_installation_token()`

**Files:**
- Modify: `synlynk/github_app_auth.py:157-168` (replace `get_installation_token`, remove `_token_cache`)
- Test: `tests/test_github_app_auth.py`

Current code being replaced (`synlynk/github_app_auth.py:15-17` and `:157-168`):

```python
GITHUB_API = "https://api.github.com"
_token_cache = {}  # role -> {"token": str, "expires_at": float}
_openssl_path_cache = None
```

```python
def get_installation_token(role: str, app_config: dict) -> str:
    """Return a cached-or-freshly-minted installation token for `role`."""
    cached = _token_cache.get(role)
    if cached and cached["expires_at"] - 60 > time.time():
        return cached["token"]
    token, expires_at = _mint_installation_token(
        app_config["app_id"], app_config["installation_id"], app_config["private_key_path"],
    )
    _token_cache[role] = {"token": token, "expires_at": expires_at}
    _persist_token_for_redaction(role, token, expires_at)
    return token
```

- [ ] **Step 1: Write the failing tests**

Replace the five `get_installation_token`-based tests in `tests/test_github_app_auth.py` (lines 47-152: `test_get_installation_token_uses_cache_when_unexpired`, `test_get_installation_token_mints_when_cache_expired`, `test_get_installation_token_mints_when_no_cache_entry`, `test_get_installation_token_persists_redaction_cache`, `test_get_installation_token_prunes_expired_redaction_entries`) with:

```python
def test_read_cached_installation_token_returns_fresh_token(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".synlynk" / "github_apps"
    cache_dir.mkdir(parents=True)
    (cache_dir / "dev.token.json").write_text(json.dumps({
        "token": "fresh-token", "expires_at": time.time() + 300,
    }))

    assert gh_auth.read_cached_installation_token("dev") == "fresh-token"


def test_read_cached_installation_token_returns_none_when_stale(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".synlynk" / "github_apps"
    cache_dir.mkdir(parents=True)
    (cache_dir / "dev.token.json").write_text(json.dumps({
        "token": "stale-token", "expires_at": time.time() - 10,
    }))

    assert gh_auth.read_cached_installation_token("dev") is None


def test_read_cached_installation_token_returns_none_when_missing(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    assert gh_auth.read_cached_installation_token("dev") is None


def test_read_cached_installation_token_returns_none_when_corrupt(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    cache_dir = tmp_path / ".synlynk" / "github_apps"
    cache_dir.mkdir(parents=True)
    (cache_dir / "dev.token.json").write_text("not json")

    assert gh_auth.read_cached_installation_token("dev") is None


def test_refresh_installation_token_writes_cache_file_with_0600(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    expires = time.time() + 3600
    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("fresh-token", expires),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("dev", app_config)

    cache_path = tmp_path / ".synlynk" / "github_apps" / "dev.token.json"
    assert cache_path.exists()
    data = json.loads(cache_path.read_text())
    assert data["token"] == "fresh-token"
    assert data["expires_at"] == expires
    assert (cache_path.stat().st_mode & 0o777) == 0o600


def test_refresh_installation_token_persists_redaction_cache(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("persisted-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("dev", app_config)

    cache_path = tmp_path / ".synlynk" / "token_redaction_cache.json"
    assert cache_path.exists()
    cache_data = json.loads(cache_path.read_text())
    assert cache_data["persisted-token"]["role"] == "dev"


def test_refresh_installation_token_round_trips_into_read_cache(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("round-trip-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}

    gh_auth.refresh_installation_token("qa", app_config)

    assert gh_auth.read_cached_installation_token("qa") == "round-trip-token"
```

Keep `test_load_redaction_tokens_omits_expired_entries` (lines 114-127) unchanged — it doesn't touch `get_installation_token`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_github_app_auth.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.github_app_auth' has no attribute 'read_cached_installation_token'` (and similarly for `refresh_installation_token`)

- [ ] **Step 3: Implement the split**

In `synlynk/github_app_auth.py`, remove the `_token_cache = {}` line (line 16) — it's replaced by the on-disk cache. Add a path helper near `_redaction_cache_path()` (after line 21):

```python
def _role_token_cache_path(role: str) -> str:
    return os.path.join(".synlynk", "github_apps", f"{role}.token.json")
```

Add `from typing import Optional` to the top-of-file import block, alongside the existing `from datetime import datetime` line (`synlynk/github_app_auth.py:12`):

```python
from datetime import datetime
from typing import Optional
```

Replace `get_installation_token()` (lines 157-168) with:

```python
def refresh_installation_token(role: str, app_config: dict) -> None:
    """Mint a fresh installation token for `role` and cache it to disk.

    Daemon-only: this is the only remaining caller of _mint_installation_token
    (and transitively _sign_jwt/openssl). dispatch must never call this —
    it only reads the cache via read_cached_installation_token().
    """
    token, expires_at = _mint_installation_token(
        app_config["app_id"], app_config["installation_id"], app_config["private_key_path"],
    )
    cache_path = _role_token_cache_path(role)
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w") as f:
        json.dump({"token": token, "expires_at": expires_at}, f)
    os.chmod(cache_path, 0o600)
    _persist_token_for_redaction(role, token, expires_at)


def read_cached_installation_token(role: str) -> Optional[str]:
    """Return the daemon-cached installation token for `role`, or None.

    Pure file read — never signs a JWT, never calls the GitHub API. Returns
    None on a missing file, a stale (expired) token, or corrupt JSON.
    """
    cache_path = _role_token_cache_path(role)
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path) as f:
            data = json.load(f)
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    expires_at = data.get("expires_at")
    if not isinstance(expires_at, (int, float)) or expires_at - 60 <= time.time():
        return None
    return data.get("token")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_github_app_auth.py -v`
Expected: PASS (all tests in the file)

- [ ] **Step 5: Grep for any other caller of `get_installation_token` before removing it**

Run: `grep -rn "get_installation_token" --include="*.py" .`
Expected output at this point: only `synlynk/dispatch.py:68` (import) and `synlynk/dispatch.py:265` (call site) — both handled in Task 3. No other production callers exist (confirmed already this session).

- [ ] **Step 6: Commit**

```bash
git add synlynk/github_app_auth.py tests/test_github_app_auth.py
git commit -m "refactor(github-app-auth): split get_installation_token into refresh/read-cache pair"
```

---

### Task 2: Daemon refreshes all role tokens on a timer

**Files:**
- Modify: `synlynk/daemon.py:32-35` (`__init__`), `:36-63` (`start`), `:141-153` (`_run_loop`)
- Test: `tests/test_daemon_token_refresh.py` (new file)

Current `__init__` (`synlynk/daemon.py:32-35`):

```python
    def __init__(self):
        self.pidfile = ".synlynk/watch.pid"
        self.logfile = ".synlynk/watch.log"
        self.settle_seconds = 3
```

Current `start()` (`synlynk/daemon.py:36-63`):

```python
    def start(self) -> None:
        if self._is_running():
            print("  synlynk watch is already running.")
            return
        if os.path.exists(self.pidfile):
            os.remove(self.pidfile)
        if not hasattr(os, "fork"):
            print("  ⚠ watch daemon requires Unix (macOS/Linux). Not supported on Windows.")
            return
        pid = os.fork()
        if pid > 0:
            print("  ● synlynk watch started.")
            return
        os.setsid()
        pid = os.fork()
        if pid > 0:
            sys.exit(0)
        # Daemon process: redirect stdio to log
        sys.stdout.flush()
        sys.stderr.flush()
        with open(self.logfile, "a") as log:
            os.dup2(log.fileno(), sys.stdout.fileno())
            os.dup2(log.fileno(), sys.stderr.fileno())
        with open(self.pidfile, "w") as f:
            f.write(str(os.getpid()))
        _pkg("set_state")("watching")
        self._run_loop()
```

Current `_run_loop()` (`synlynk/daemon.py:141-153`):

```python
    def _run_loop(self) -> None:
        config = _pkg("load_config")()
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                _pkg("set_state")("active")
                self.on_change(changed[0])
                _pkg("set_state")("watching")
                last_mtimes = self._get_mtimes("project-docs")
```

- [ ] **Step 1: Write the failing test**

Create `tests/test_daemon_token_refresh.py`:

```python
"""Tests for WatchDaemon's GitHub App token refresh responsibility."""

import glob
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.daemon import WatchDaemon


def test_refresh_github_tokens_refreshes_each_provisioned_role(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "2", "installation_id": "20", "private_key_path": "qa.pem",
    }))

    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append(role),
    )

    WatchDaemon()._refresh_github_tokens()

    assert sorted(refreshed) == ["dev", "qa"]


def test_refresh_github_tokens_one_role_failure_does_not_block_others(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "2", "installation_id": "20", "private_key_path": "qa.pem",
    }))

    refreshed = []
    import synlynk.daemon as daemon_mod

    def fake_refresh(role, app_config):
        if role == "dev":
            raise RuntimeError("installation revoked")
        refreshed.append(role)

    monkeypatch.setattr(daemon_mod.github_app_auth, "refresh_installation_token", fake_refresh)

    WatchDaemon()._refresh_github_tokens()

    assert refreshed == ["qa"]
    assert "installation revoked" in capsys.readouterr().err


def test_refresh_github_tokens_skips_token_cache_files(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "10", "private_key_path": "dev.pem",
    }))
    (apps_dir / "dev.token.json").write_text(json.dumps({"token": "x", "expires_at": time.time() + 3600}))

    refreshed = []
    import synlynk.daemon as daemon_mod
    monkeypatch.setattr(
        daemon_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append(role),
    )

    WatchDaemon()._refresh_github_tokens()

    assert refreshed == ["dev"]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_daemon_token_refresh.py -v`
Expected: FAIL with `AttributeError: 'WatchDaemon' object has no attribute '_refresh_github_tokens'`

- [ ] **Step 3: Implement the refresh method and wire it into start()/`_run_loop()`**

Add the import at the top of `synlynk/daemon.py` (after line 16's `from synlynk.team import get_username`):

```python
from synlynk import github_app_auth
```

Update `__init__` (`synlynk/daemon.py:32-35`) to:

```python
    def __init__(self):
        self.pidfile = ".synlynk/watch.pid"
        self.logfile = ".synlynk/watch.log"
        self.settle_seconds = 3
        self.token_refresh_interval_seconds = 50 * 60
```

Add `_refresh_github_tokens()` as a new method, placed directly after `on_change()` (which currently ends at `synlynk/daemon.py:130`, right before `_run_loop`):

```python
    def _refresh_github_tokens(self) -> None:
        """Mint fresh tokens for every provisioned role's GitHub App.

        Best-effort per role: one role's failure (revoked App, bad
        installation_id) must not stop the others or crash the daemon loop.
        """
        apps_dir = os.path.join(".synlynk", "github_apps")
        if not os.path.isdir(apps_dir):
            return
        for json_path in sorted(glob.glob(os.path.join(apps_dir, "*.json"))):
            if json_path.endswith(".token.json"):
                continue
            role = os.path.basename(json_path)[: -len(".json")]
            try:
                with open(json_path) as fh:
                    app_config = json.load(fh)
                if not app_config.get("installation_id"):
                    continue
                github_app_auth.refresh_installation_token(role, app_config)
            except Exception as exc:
                print(f"  ⚠ could not refresh GitHub App token for role '{role}': {exc}", file=sys.stderr)
```

Add `import glob` to the top-of-file import block (`synlynk/daemon.py:3-11`), alphabetically after `import http.server`:

```python
import glob
import http.server
```

Update `start()` to refresh once immediately before entering the loop — insert right before the `self._run_loop()` call at the end of `start()` (`synlynk/daemon.py:63`):

```python
        _pkg("set_state")("watching")
        self._refresh_github_tokens()
        self._run_loop()
```

Update `_run_loop()` (`synlynk/daemon.py:141-153`) to also check the token-refresh interval each iteration:

```python
    def _run_loop(self) -> None:
        config = _pkg("load_config")()
        interval = config.get("watch_interval_seconds", 30)
        last_mtimes = self._get_mtimes("project-docs")
        last_token_refresh = time.time()
        while True:
            time.sleep(interval)
            current_mtimes = self._get_mtimes("project-docs")
            changed = [f for f in current_mtimes
                       if current_mtimes[f] != last_mtimes.get(f)]
            if changed:
                time.sleep(self.settle_seconds)
                _pkg("set_state")("active")
                self.on_change(changed[0])
                _pkg("set_state")("watching")
                last_mtimes = self._get_mtimes("project-docs")
            if time.time() - last_token_refresh >= self.token_refresh_interval_seconds:
                self._refresh_github_tokens()
                last_token_refresh = time.time()
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_daemon_token_refresh.py -v`
Expected: PASS (3 tests)

Also run the full daemon-adjacent suite to confirm nothing else broke:

Run: `python3 -m pytest tests/ -k daemon -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/daemon.py tests/test_daemon_token_refresh.py
git commit -m "feat(daemon): refresh all provisioned GitHub App tokens every 50 min"
```

---

### Task 3: `dispatch.py` reads the cache instead of minting

**Files:**
- Modify: `synlynk/dispatch.py:68` (import), `:245-272` (`_resolve_dispatch_gh_token`), `:526-533` (fail-closed error message)
- Test: `tests/test_dispatch_github_identity.py`

Current import (`synlynk/dispatch.py:68`):

```python
from synlynk.github_app_auth import get_installation_token
```

Current `_resolve_dispatch_gh_token` (`synlynk/dispatch.py:245-272`):

```python
def _resolve_dispatch_gh_token(role: str) -> Optional[str]:
    """Resolve a role-scoped GitHub App installation token for dispatch.

    Falls back to the synlynk-bot catch-all identity if the role has no
    provisioned App. Returns None (never a human's personal token) if
    neither is provisioned — dispatch proceeds using whatever `gh auth`
    is already configured on the host in that case.
    """
    for candidate_role in (role, "synlynk-bot"):
        json_path = os.path.join(".synlynk", "github_apps", f"{candidate_role}.json")
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path) as fh:
                app_config = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not app_config.get("installation_id"):
            continue
        try:
            return get_installation_token(candidate_role, app_config)
        except Exception as exc:
            print(
                f"  ⚠ could not mint GitHub App token for role '{candidate_role}': {exc}",
                file=sys.stderr,
            )
            return None
    return None
```

Current fail-closed error (`synlynk/dispatch.py:526-533`):

```python
            raise RuntimeError(
                "Dispatch refused: --requires-gh-write requires a role-scoped GitHub App "
                f"token, but none is available for role {role!r} "
                f"(checked .synlynk/github_apps/{role}.json and synlynk-bot.json). "
                f"Run: synlynk identity init --role {role}  "
                "Or set SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1 to opt into host `gh` auth "
                "(uses personal keyring — not recommended; see #569)."
            )
```

- [ ] **Step 1: Write the failing tests**

In `tests/test_dispatch_github_identity.py`, replace `test_resolve_dispatch_gh_token_uses_role_specific_app` (lines 10-25) and `test_resolve_dispatch_gh_token_falls_back_to_synlynk_bot` (lines 28-43) with:

```python
def test_resolve_dispatch_gh_token_uses_role_specific_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "1", "installation_id": "2", "private_key_path": "qa.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod, "read_cached_installation_token",
        lambda role: f"token-for-{role}",
    )
    token = dispatch_mod._resolve_dispatch_gh_token("qa")
    assert token == "token-for-qa"


def test_resolve_dispatch_gh_token_falls_back_to_synlynk_bot(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "synlynk-bot.json").write_text(json.dumps({
        "role": "synlynk-bot", "app_id": "9", "installation_id": "8", "private_key_path": "bot.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod, "read_cached_installation_token",
        lambda role: f"token-for-{role}",
    )
    token = dispatch_mod._resolve_dispatch_gh_token("dev")  # dev.json does not exist
    assert token == "token-for-synlynk-bot"


def test_resolve_dispatch_gh_token_returns_none_when_cache_stale(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "installation_id": "2", "private_key_path": "dev.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "read_cached_installation_token", lambda role: None)
    assert dispatch_mod._resolve_dispatch_gh_token("dev") is None
```

Leave `test_resolve_dispatch_gh_token_returns_none_when_nothing_provisioned` (lines 46-52) unchanged — it doesn't reference `get_installation_token`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_dispatch_github_identity.py -v`
Expected: FAIL — `monkeypatch.setattr(dispatch_mod, "read_cached_installation_token", ...)` raises `AttributeError` because `dispatch.py` doesn't import that name yet.

- [ ] **Step 3: Repoint `dispatch.py` to the cache-reading function**

Change the import at `synlynk/dispatch.py:68` to:

```python
from synlynk.github_app_auth import read_cached_installation_token
```

Replace `_resolve_dispatch_gh_token` (`synlynk/dispatch.py:245-272`) with:

```python
def _resolve_dispatch_gh_token(role: str) -> Optional[str]:
    """Resolve a role-scoped GitHub App installation token for dispatch.

    Reads the daemon-maintained token cache only — never signs a JWT or
    calls the GitHub API itself (that live-credential action is what
    triggered Claude Code's auto-mode classifier to block dispatch, #1140).
    Falls back to the synlynk-bot catch-all identity if the role has no
    provisioned App. Returns None if neither is provisioned, or if the
    provisioned role's cached token is missing/stale (daemon not running
    or hasn't refreshed yet) — dispatch's caller decides whether that's a
    fail-closed error (--requires-gh-write) or a silent host-auth fallback.
    """
    for candidate_role in (role, "synlynk-bot"):
        json_path = os.path.join(".synlynk", "github_apps", f"{candidate_role}.json")
        if not os.path.exists(json_path):
            continue
        try:
            with open(json_path) as fh:
                app_config = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if not app_config.get("installation_id"):
            continue
        return read_cached_installation_token(candidate_role)
    return None
```

Update the fail-closed error message at `synlynk/dispatch.py:526-533` to:

```python
            raise RuntimeError(
                "Dispatch refused: --requires-gh-write requires a role-scoped GitHub App "
                f"token, but none is available for role {role!r} "
                f"(checked .synlynk/github_apps/{role}.json and synlynk-bot.json). "
                f"If the App is provisioned, ensure the token cache is fresh: "
                f"synlynk daemon status  (start it with: synlynk daemon start — "
                f"it refreshes tokens automatically every ~50 min). "
                f"If the App isn't provisioned yet: synlynk identity init --role {role}  "
                "Or set SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1 to opt into host `gh` auth "
                "(uses personal keyring — not recommended; see #569)."
            )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_dispatch_github_identity.py -v`
Expected: PASS (all tests, including the pre-existing fail-closed and host-auth-escape-hatch tests, which are unaffected since they already monkeypatch `_resolve_dispatch_gh_token` directly rather than `get_installation_token`)

Run the broader dispatch suite too:

Run: `python3 -m pytest tests/test_dispatch.py tests/test_dispatch_github_identity.py tests/test_agy_dispatch_fix.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_github_identity.py
git commit -m "fix(dispatch): read GitHub App token from daemon cache instead of minting inline (#1140)"
```

---

### Task 4: `synlynk identity init --role` seeds the cache immediately

**Files:**
- Modify: `synlynk/team.py:783-882` (`cmd_identity_init_role`)
- Test: `tests/test_identity_init_role_token_seed.py` (new file)

Current relevant excerpts of `cmd_identity_init_role` (`synlynk/team.py:783-882`):

Early-return "already has an App, resuming at install confirmation" branch (`synlynk/team.py:797-806`):

```python
        if (
            existing.get("app_id")
            and existing.get("client_id")
            and existing.get("app_slug")
            and existing.get("private_key_path")
            and os.path.exists(existing["private_key_path"])
        ):
            print(f"  role '{role}' has an App already created ({existing['app_slug']}) — resuming at install confirmation")
            _confirm_installation(existing["app_slug"], json_path)
            print(f"  role '{role}' provisioned at {json_path}")
            from synlynk.identity_roles import load_declared_roles, write_declared_roles
            declared = load_declared_roles()
            if role not in declared:
                write_declared_roles(declared + [role])
                print(f"  ✓ added '{role}' to .synlynk/roles.yaml")
            return
```

Main new-App-creation completion (`synlynk/team.py:874-882`):

```python
    config = _write_role_app_config(role, conversion)
    _confirm_installation(config["app_slug"], json_path)
    print(f"  role '{role}' provisioned at {json_path}")

    from synlynk.identity_roles import load_declared_roles, write_declared_roles

    declared = load_declared_roles()
    if role not in declared:
        write_declared_roles(declared + [role])
        print(f"  ✓ added '{role}' to .synlynk/roles.yaml")
```

Both branches call `_confirm_installation(app_slug, json_path)`, which writes an updated `installation_id` into the file at `json_path` but does not return the full config dict (it returns the raw `installation` API object instead) — the caller needs to re-read `json_path` to get a complete `app_config` for `refresh_installation_token`.

- [ ] **Step 1: Write the failing test**

Create `tests/test_identity_init_role_token_seed.py`:

```python
"""Tests that cmd_identity_init_role seeds the token cache immediately after provisioning."""

import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_identity_init_role_resuming_branch_seeds_token_cache(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_path = apps_dir / "dev.pem"
    pem_path.write_text("fake-pem")
    json_path = apps_dir / "dev.json"
    json_path.write_text(json.dumps({
        "role": "dev", "app_id": "1", "client_id": "c1", "app_slug": "synlynk-dev",
        "installation_id": None, "private_key_path": str(pem_path),
    }))

    import synlynk.team as team_mod

    def fake_confirm_installation(app_slug, json_path_arg):
        data = json.loads(json_path_arg.read_text())
        data["installation_id"] = "999"
        json_path_arg.write_text(json.dumps(data))
        return {"id": "999"}

    refreshed = []
    monkeypatch.setattr(team_mod, "_confirm_installation", fake_confirm_installation)
    monkeypatch.setattr(
        team_mod.github_app_auth, "refresh_installation_token",
        lambda role, app_config: refreshed.append((role, app_config["installation_id"])),
    )
    monkeypatch.setattr(
        team_mod, "load_declared_roles" if hasattr(team_mod, "load_declared_roles") else "_noop",
        lambda: [], raising=False,
    )
    import synlynk.identity_roles as identity_roles_mod
    monkeypatch.setattr(identity_roles_mod, "load_declared_roles", lambda: [])
    monkeypatch.setattr(identity_roles_mod, "write_declared_roles", lambda roles: None)

    team_mod.cmd_identity_init_role("dev")

    assert refreshed == [("dev", "999")]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_identity_init_role_token_seed.py -v`
Expected: FAIL — `refreshed == []` (nothing calls `refresh_installation_token` yet)

- [ ] **Step 3: Wire in the immediate refresh**

Add the import at the top of `synlynk/team.py` (find the existing `from synlynk...` import block near the top of the file and add):

```python
from synlynk import github_app_auth
```

Update the "resuming" branch (`synlynk/team.py:797-806`) to:

```python
        if (
            existing.get("app_id")
            and existing.get("client_id")
            and existing.get("app_slug")
            and existing.get("private_key_path")
            and os.path.exists(existing["private_key_path"])
        ):
            print(f"  role '{role}' has an App already created ({existing['app_slug']}) — resuming at install confirmation")
            _confirm_installation(existing["app_slug"], json_path)
            with open(json_path) as fh:
                refreshed_config = json.load(fh)
            github_app_auth.refresh_installation_token(role, refreshed_config)
            print(f"  role '{role}' provisioned at {json_path}")
            from synlynk.identity_roles import load_declared_roles, write_declared_roles
            declared = load_declared_roles()
            if role not in declared:
                write_declared_roles(declared + [role])
                print(f"  ✓ added '{role}' to .synlynk/roles.yaml")
            return
```

Update the main completion (`synlynk/team.py:874-882`) to:

```python
    config = _write_role_app_config(role, conversion)
    _confirm_installation(config["app_slug"], json_path)
    with open(json_path) as fh:
        refreshed_config = json.load(fh)
    github_app_auth.refresh_installation_token(role, refreshed_config)
    print(f"  role '{role}' provisioned at {json_path}")

    from synlynk.identity_roles import load_declared_roles, write_declared_roles

    declared = load_declared_roles()
    if role not in declared:
        write_declared_roles(declared + [role])
        print(f"  ✓ added '{role}' to .synlynk/roles.yaml")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_identity_init_role_token_seed.py -v`
Expected: PASS

Run the broader team-identity suite:

Run: `python3 -m pytest tests/ -k identity -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/team.py tests/test_identity_init_role_token_seed.py
git commit -m "feat(identity): seed GitHub App token cache immediately after role provisioning"
```

---

### Task 5: Full suite regression check

**Files:** none (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/ -q`
Expected: PASS, 0 new failures. (Two pre-existing unrelated failures may appear —
`tests/test_agent_quota_tracking.py::test_cmd_probewrite_fencetrue_clobbers_sop_harness` and
`tests/test_roles.py::test_cmd_agent_add_onboards_agent` — both are `sqlite3.OperationalError:
database is locked` flakes from shared state-db access across parallel test workers, confirmed
pre-existing on `origin/main` this session, unrelated to this change. If either shows up alone,
proceed. If any *other* test fails, stop and investigate before continuing.)

- [ ] **Step 2: Grep for any remaining reference to the removed `get_installation_token` or `_token_cache`**

Run: `grep -rn "get_installation_token\|_token_cache" --include="*.py" .`
Expected: no matches anywhere in `synlynk/` or `tests/` (the old name and the in-memory cache are fully removed).

- [ ] **Step 3: Push the branch**

```bash
git push origin fix/1140-gh-token-daemon-cache
```

---

### Task 6: Live dogfood verification (Claude-direct, NOT dispatched)

Per project CLAUDE.md, this task is PM/deploy work Claude runs directly — do not dispatch it.

**Steps:**

1. Confirm which repo location has provisioned GitHub Apps: `ls .synlynk/github_apps/*.json` in this worktree. Per #1160 (parallel, unresolved), worktrees may not inherit `.synlynk/github_apps/` from the main repo — if this worktree's directory is empty or missing, run the remaining steps from the main repo root (`/Users/nikhilsoman/dev/synlynk`) instead, after merging this branch there, and note explicitly in the PR that live verification ran from main-repo-root due to #1160.
2. Start the daemon: `synlynk daemon start`. Confirm via `synlynk daemon status`.
3. Within a few seconds, inspect the cache: `cat .synlynk/github_apps/<role>.token.json` for at least one real provisioned role (e.g. `dev` or `qa`) — confirm it contains a `token` string and an `expires_at` roughly one hour in the future, and confirm file permissions are `600` (`stat -f "%A" .synlynk/github_apps/<role>.token.json` on macOS).
4. Run one real (non-dry-run) gh-write dispatch: `synlynk dispatch codex --task "<a small real gh-write-triggering task>" --role <role> --requires-gh-write --force-agent --context-mode full`.
5. Confirm the dispatch call itself is not blocked by Claude Code's auto-mode classifier (this is the actual proof of the #1140 fix) and that the underlying GitHub write (issue/PR/comment, whatever the task produced) actually happened — check directly via `gh issue view <n>` / `gh pr view <n>` / `synlynk jobs --all`, not by trusting dispatch's own printed summary alone.
6. Stop the daemon when done if it wasn't already running as a standing service: `synlynk daemon stop`.
7. Post a comment on [#1140](https://github.com/nikhilsoman/synlynk/issues/1140) documenting the fix (PR link) and this verification, then close the issue.
