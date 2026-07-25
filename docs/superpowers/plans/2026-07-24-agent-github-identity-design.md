# Per-Role GitHub Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.
>
> **Project-specific override (do not skip):** synlynk's CLAUDE.md locks Claude to PM/review/deploy only — Claude must never implement. Whichever skill above is invoked, every implementation task in this plan must be executed via `python3 -m synlynk dispatch <agent> --task "..." --force-agent --context-mode full` routed to Codex (this is pure Python/CLI/tests work — see synlynk's Capability-Based Task Allocation table), **not** through the generic-subagent dispatch built into `subagent-driven-development`. If you are a session about to execute this plan, flag this explicitly before starting.

**Goal:** Give each dispatched `gh` operation (PR authorship, comments, reviews) a distinct, role-scoped GitHub identity (`<project>-<role>[bot]`) instead of the single ambient personal token, using one GitHub App per role provisioned via the App Manifest flow and short-lived installation tokens minted at dispatch time.

**Architecture:** A new `synlynk/github_app_auth.py` module signs GitHub App JWTs by shelling out to the system `openssl` binary (RS256 needs asymmetric RSA signing, which the Python stdlib cannot do — and this codebase has zero third-party Python dependencies today, confirmed via `pyproject.toml` having no `dependencies` key and no non-stdlib imports anywhere in `synlynk/*.py`), then exchanges that JWT for a short-lived installation token via the GitHub REST API using `urllib.request` (the same HTTP approach already used in `synlynk/upgrade.py` and `synlynk/doctor.py`). Provisioning is a new `--role` flag on the *existing* `synlynk identity init` subcommand (it already exists for Ed25519 identity bootstrap in `synlynk/team.py` — this plan extends it, it does not create a new top-level command). Role-scoped tokens are injected into the dispatched job's subprocess environment at the exact point `synlynk/dispatch.py:1112` already builds `proc_env`, keyed off the `stories.role` column that already exists (`_ROLES = ("architect", "dev", "pm", "tpm", "qa", "designer")` in `synlynk/db.py:37`).

**Tech Stack:** Python 3.9+ stdlib only (`urllib.request`, `subprocess`, `json`, `base64`, `time`, `os`), system `openssl` CLI for RSA signing, pytest for tests (matching `tests/test_roles.py` and `tests/test_dispatch.py` conventions — `tmp_path`, `monkeypatch.chdir`, `monkeypatch.setattr`).

---

## Panel Decision (2026-07-25) — Read This Second

Before execution, a `synlynk decide --panel claude,agy,codex,grok --record` review ran against this plan given the auth-adjacent surface (recorded at `project-docs/decisions/2026-07-25-should-synlynk-implement-per-role-github.md`). Verdict: **proceed, but narrower**, with specific revisions this plan now incorporates:

1. **Narrower first slice.** Do not provision all six taxonomy roles up front. Task 8's manual validation now provisions and validates **`dev` only** — the role most GitHub-write dispatches are tagged with — end-to-end, before any second role is provisioned. Do not generalize beyond `dev` until that slice is confirmed working in real dispatch use.
2. **`GH_TOKEN` injection scoped to declared GitHub-write need, not every dispatch.** Task 5 originally injected a token into every job's `proc_env` whenever *any* role identity existed. Revised: only inject when the job was dispatched with `requires_gh_write=True` (the parameter `dispatch_agent()` already accepts at `synlynk/dispatch.py:815` for the #426 routing gate) — this is the existing, already-tested hook for "this job needs to do GitHub writes," reused rather than duplicated.
3. **Harden the `openssl` invocation** (Task 2): resolve an absolute, verified path via `shutil.which` once at import/call time instead of trusting a bare `"openssl"` PATH lookup, and fail with a clear error if not found. (The plan already passed the signing input via `stdin` and the private key via a *file path* argument, never as secret content on argv — the panel confirmed this part was already sound.)
4. **Enforce `0o600` on identity files at rest, checked, not just set-and-forget.** New Task 6b adds a doctor check that both the `.json` and `.pem` files under `.synlynk/github_apps/` still have `0o600` permissions, and a test that `.gitignore` actually excludes that directory (not just relying on the top-level `.synlynk/` ignore continuing to hold).
5. **Scrub token-shaped values from logs/telemetry.** New Task 9 adds a redaction pass so a minted `GH_TOKEN` value can never end up captured verbatim in `.synlynk/telemetry.json`, job logs, or sentinel alerts.
6. **Extra review gate.** Codex still implements this (Python/CLI/tests — matches the Capability-Based Task Allocation table), but per the panel, the resulting PR requires an **explicit security-focused review pass by Claude** — covering the threat model and token-handling details specifically — in addition to (not instead of) the standard non-authoring-reviewer + `synlynk pr check` rule. Do not merge on the standard path alone.

---

## Naming Collision — Read This First

There are **two unrelated things called "role" in this codebase**, and this feature adds a **third**. Do not conflate them:

1. **Permission-scope roles** (existing) — `.synlynk/config.json`'s `"roles"` key maps *agent* (`claude`/`agy`/`grok`/`codex`) → list of permission-scope strings (`"pm"`, `"implement"`, `"css"`, ...) defined in `_ROLE_PERMISSION_DEFAULTS` (`synlynk/_constants.py:19`). Governs which CLI flags/tools an agent gets. **Untouched by this plan.**
2. **Capability-taxonomy roles** (existing) — the `stories.role` column / `_ROLES` enum (`synlynk/db.py:37`): `architect`, `dev`, `pm`, `tpm`, `qa`, `designer`. This is the dimension this plan hooks into for token routing — **this is the "role" the spec means**.
3. **`.synlynk/roles.yaml`** (new, this plan) — the project's declared identity-role list (defaults to the `_ROLES` enum values, but per the spec is not hardcoded to it — see Task 1). Drives which GitHub Apps get provisioned.

Every task below says explicitly which of these three it means.

## Naming Collision #2 — `identity init` already exists

`synlynk identity init` (no args) already creates an Ed25519 key for capability-rating signing (`synlynk/team.py:502`, wired in `synlynk/cli.py:346-348,1060-1064`). This plan adds a `--role <name>` flag to the *same* subcommand: called with `--role`, it runs GitHub App provisioning instead of Ed25519 bootstrap. Called with no args, existing behavior is unchanged.

## Gitignore Collision

`.gitignore:2` currently ignores the entire `.synlynk/` directory. The spec requires `.synlynk/roles.yaml` to be **committed** (project config) while `.synlynk/github_apps/*.json` and `*.pem` stay gitignored (secrets). Task 1 adds a negation line.

---

## Task 1: `.synlynk/roles.yaml` data model + gitignore fix

**Files:**
- Create: `synlynk/identity_roles.py`
- Modify: `.gitignore`
- Test: `tests/test_identity_roles.py`

- [ ] **Step 1: Write the failing test for loading roles.yaml with a default fallback**

```python
# tests/test_identity_roles.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.identity_roles import load_declared_roles, DEFAULT_ROLES


def test_load_declared_roles_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    assert load_declared_roles() == list(DEFAULT_ROLES)


def test_load_declared_roles_reads_yaml_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text(
        "roles:\n  - director\n  - screenwriter\n  - editor\n"
    )
    assert load_declared_roles() == ["director", "screenwriter", "editor"]


def test_load_declared_roles_ignores_malformed_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("not: valid: yaml: [[[")
    assert load_declared_roles() == list(DEFAULT_ROLES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_roles.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.identity_roles'`

- [ ] **Step 3: Write `synlynk/identity_roles.py`**

No YAML library is available (stdlib-only project) — hand-write a minimal parser for the flat `roles:\n  - x\n  - y` shape this file always has (it is never hand-authored with nested structures; `synlynk identity` tooling is the only writer).

```python
"""Project-declared identity roles for GitHub App provisioning (.synlynk/roles.yaml).

Distinct from _ROLE_PERMISSION_DEFAULTS (agent permission scopes) and the
stories.role taxonomy column — see docs/superpowers/plans/2026-07-24-agent-github-identity-design.md
"Naming Collision" section.
"""

import os

DEFAULT_ROLES = ("dev", "qa")

ROLES_YAML_PATH = os.path.join(".synlynk", "roles.yaml")


def load_declared_roles() -> list:
    """Read .synlynk/roles.yaml's flat `roles:` list; fall back to DEFAULT_ROLES."""
    if not os.path.exists(ROLES_YAML_PATH):
        return list(DEFAULT_ROLES)
    try:
        with open(ROLES_YAML_PATH) as fh:
            lines = fh.readlines()
    except OSError:
        return list(DEFAULT_ROLES)
    roles = []
    in_roles_block = False
    for line in lines:
        stripped = line.strip()
        if stripped == "roles:":
            in_roles_block = True
            continue
        if in_roles_block:
            if stripped.startswith("- "):
                roles.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("#"):
                break
    return roles if roles else list(DEFAULT_ROLES)


def write_declared_roles(roles: list) -> None:
    """Write .synlynk/roles.yaml as a flat `roles:` list. Overwrites any existing file."""
    os.makedirs(".synlynk", exist_ok=True)
    lines = ["roles:\n"] + [f"  - {role}\n" for role in roles]
    with open(ROLES_YAML_PATH, "w") as fh:
        fh.writelines(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_identity_roles.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Fix the gitignore collision**

Edit `.gitignore` — after the existing `.synlynk/` block, add a negation so `roles.yaml` is committed while everything else under `.synlynk/` (including the `github_apps/` directory added in Task 2) stays ignored:

```
.synlynk/
.synlynk/viz-cache/
.synlynk/viz-meta.json
!.synlynk/roles.yaml
```

- [ ] **Step 6: Verify the gitignore fix works**

Run: `cd /tmp && rm -rf giti-test && mkdir giti-test && cd giti-test && git init -q && cp /Users/nikhilsoman/dev/synlynk/.worktrees/chore+agent-github-identity-design/.gitignore . && mkdir .synlynk && touch .synlynk/roles.yaml .synlynk/config.json && git add -A && git status --short`
Expected: only `.gitignore` and `.synlynk/roles.yaml` show as staged (`A`); `.synlynk/config.json` does not appear.

- [ ] **Step 7: Commit**

```bash
git add synlynk/identity_roles.py tests/test_identity_roles.py .gitignore
git commit -m "feat: add .synlynk/roles.yaml identity-role data model

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 2: `synlynk/github_app_auth.py` — JWT signing + installation token minting

**Files:**
- Create: `synlynk/github_app_auth.py`
- Test: `tests/test_github_app_auth.py`

**Data model this task reads/writes:**
- `.synlynk/github_apps/<role>.json` (gitignored, one per provisioned role):
  ```json
  {
    "role": "dev",
    "app_id": "123456",
    "client_id": "Iv1.abc123",
    "app_slug": "rxcc-dev",
    "installation_id": "78901234",
    "private_key_path": ".synlynk/github_apps/dev.pem"
  }
  ```
- `.synlynk/github_apps/synlynk-bot.json` — same shape, the catch-all fallback identity (role field is `"synlynk-bot"`).
- Private key: sibling `.pem` file, `chmod 600` (Task 3 writes these; this task only reads them).

- [ ] **Step 1: Write the failing test for JWT construction (header/payload, not signature)**

```python
# tests/test_github_app_auth.py
import base64
import json
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.github_app_auth import _build_jwt_signing_input, _b64url_decode


def test_build_jwt_signing_input_has_correct_header_and_claims():
    signing_input, header, payload = _build_jwt_signing_input(app_id="123456", now=1700000000)
    header_json = json.loads(_b64url_decode(header))
    payload_json = json.loads(_b64url_decode(payload))
    assert header_json == {"alg": "RS256", "typ": "JWT"}
    assert payload_json["iss"] == "123456"
    assert payload_json["iat"] == 1700000000 - 60
    assert payload_json["exp"] == 1700000000 + 540
    assert signing_input == header + b"." + payload
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.github_app_auth'`

- [ ] **Step 3: Write the JWT-construction half of `synlynk/github_app_auth.py`**

```python
"""GitHub App JWT signing (via system openssl) and installation token minting.

RS256 needs asymmetric RSA signing, which the Python stdlib cannot do and this
project has zero third-party Python dependencies (see plan doc's Architecture
section) — so signing shells out to `openssl dgst -sha256 -sign`.
"""

import base64
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request

GITHUB_API = "https://api.github.com"

_token_cache = {}  # role -> {"token": str, "expires_at": float}
_openssl_path_cache = None  # resolved once, not re-looked-up per signing call


def _resolve_openssl_path() -> str:
    """Resolve an absolute, verified openssl path via shutil.which — never trust
    a bare "openssl" argv[0] to PATH resolution inside subprocess.run, so a
    malicious PATH entry ahead of the real binary can't be silently invoked
    for RSA signing. Cached after first successful resolution."""
    global _openssl_path_cache
    if _openssl_path_cache:
        return _openssl_path_cache
    resolved = shutil.which("openssl")
    if not resolved:
        raise RuntimeError(
            "openssl not found on PATH — required for GitHub App JWT signing (RS256). "
            "Install it (already present on virtually all dev machines/CI images) or "
            "GitHub identity provisioning/token minting cannot proceed."
        )
    _openssl_path_cache = resolved
    return resolved


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _b64url_decode(data: bytes) -> bytes:
    padding = b"=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _build_jwt_signing_input(app_id: str, now: float = None) -> tuple:
    """Returns (signing_input, header_b64, payload_b64). iat is backdated 60s
    for clock drift; exp is 9 minutes out (GitHub's max is 10)."""
    now = int(now if now is not None else time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps(
        {"iat": now - 60, "exp": now + 540, "iss": str(app_id)},
        separators=(",", ":"),
    ).encode())
    return header + b"." + payload, header, payload


def _sign_jwt(app_id: str, private_key_path: str) -> str:
    """Sign a GitHub App JWT by shelling out to openssl for RS256.

    The signing input goes over stdin and the key is passed as a file path —
    never as secret key material on argv, where it would be visible via `ps`
    to any other process on the host.
    """
    signing_input, _, _ = _build_jwt_signing_input(app_id)
    openssl = _resolve_openssl_path()
    result = subprocess.run(
        [openssl, "dgst", "-sha256", "-sign", private_key_path],
        input=signing_input,
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"openssl JWT signing failed for app_id={app_id}: "
            f"{result.stderr.decode(errors='replace')}"
        )
    signature = _b64url(result.stdout)
    return (signing_input + b"." + signature).decode("ascii")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: PASS (1 passed)

- [ ] **Step 4b: Write the failing test for hardened openssl path resolution (panel-mandated hygiene item)**

```python
def test_resolve_openssl_path_raises_clear_error_when_missing(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._openssl_path_cache = None
    monkeypatch.setattr(gh_auth.shutil, "which", lambda name: None)
    with pytest.raises(RuntimeError, match="openssl not found"):
        gh_auth._resolve_openssl_path()


def test_resolve_openssl_path_caches_after_first_resolution(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._openssl_path_cache = None
    calls = []
    monkeypatch.setattr(gh_auth.shutil, "which", lambda name: calls.append(name) or "/usr/bin/openssl")
    first = gh_auth._resolve_openssl_path()
    second = gh_auth._resolve_openssl_path()
    assert first == second == "/usr/bin/openssl"
    assert len(calls) == 1  # second call hit the cache, not shutil.which again
```

Add `import pytest` to the top of `tests/test_github_app_auth.py` if not already present from Step 1.

- [ ] **Step 4c: Run tests to verify they pass**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write the failing test for installation token minting + caching**

```python
def test_get_installation_token_uses_cache_when_unexpired(monkeypatch, tmp_path):
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    gh_auth._token_cache["dev"] = {"token": "cached-token", "expires_at": time.time() + 300}

    def fail_if_called(*a, **kw):
        raise AssertionError("should not mint a new token when cache is fresh")

    monkeypatch.setattr(gh_auth, "_mint_installation_token", fail_if_called)
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    token = gh_auth.get_installation_token("dev", app_config)
    assert token == "cached-token"


def test_get_installation_token_mints_when_cache_expired(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    gh_auth._token_cache["dev"] = {"token": "stale-token", "expires_at": time.time() - 10}

    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("fresh-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    token = gh_auth.get_installation_token("dev", app_config)
    assert token == "fresh-token"
    assert gh_auth._token_cache["dev"]["token"] == "fresh-token"


def test_get_installation_token_mints_when_no_cache_entry(monkeypatch):
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    monkeypatch.setattr(
        gh_auth, "_mint_installation_token",
        lambda app_id, installation_id, private_key_path: ("brand-new-token", time.time() + 3600),
    )
    app_config = {"app_id": "1", "installation_id": "2", "private_key_path": "unused.pem"}
    token = gh_auth.get_installation_token("qa", app_config)
    assert token == "brand-new-token"
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.github_app_auth' has no attribute 'get_installation_token'`

- [ ] **Step 7: Append the token-minting half to `synlynk/github_app_auth.py`**

```python
def _mint_installation_token(app_id: str, installation_id: str, private_key_path: str) -> tuple:
    """POST /app/installations/{id}/access_tokens. Returns (token, expires_at_epoch)."""
    jwt = _sign_jwt(app_id, private_key_path)
    req = urllib.request.Request(
        f"{GITHUB_API}/app/installations/{installation_id}/access_tokens",
        method="POST",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"Installation token mint failed ({exc.code}): {body}") from exc
    token = data["token"]
    # expires_at looks like "2026-07-24T12:34:56Z"
    import calendar
    from datetime import datetime

    expires_dt = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires_at = calendar.timegm(expires_dt.timetuple())
    return token, expires_at


def get_installation_token(role: str, app_config: dict) -> str:
    """Return a cached-or-freshly-minted installation token for `role`.

    Re-mints with a 60s safety margin before actual expiry.
    """
    cached = _token_cache.get(role)
    if cached and cached["expires_at"] - 60 > time.time():
        return cached["token"]
    token, expires_at = _mint_installation_token(
        app_config["app_id"], app_config["installation_id"], app_config["private_key_path"],
    )
    _token_cache[role] = {"token": token, "expires_at": expires_at}
    return token
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: PASS (6 passed)

- [ ] **Step 9: Commit**

```bash
git add synlynk/github_app_auth.py tests/test_github_app_auth.py
git commit -m "feat: GitHub App JWT signing and installation token minting

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 3: `synlynk identity init --role <name>` provisioning flow

**Files:**
- Modify: `synlynk/team.py` (extend `cmd_identity_init`)
- Modify: `synlynk/cli.py:346-348` (add `--role` arg), `synlynk/cli.py:1060-1064` (dispatch on it)
- Test: `tests/test_identity_init_role.py`

This is the two-click App Manifest flow. It cannot be fully automated (GitHub requires a human to click "Create GitHub App" in a browser), so the function opens the manifest URL, waits for the user to paste back the resulting `code` query-param, and does the rest programmatically.

- [ ] **Step 1: Write the failing test for manifest URL construction**

```python
# tests/test_identity_init_role.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.team import _build_app_manifest_url


def test_build_app_manifest_url_encodes_role_and_project():
    url = _build_app_manifest_url(project="rxcc", role="dev")
    assert url.startswith("https://github.com/settings/apps/new")
    assert "state=rxcc%3Adev" in url
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_init_role.py -v`
Expected: FAIL with `ImportError: cannot import name '_build_app_manifest_url'`

- [ ] **Step 3: Read `synlynk/team.py` around `cmd_identity_init` (line 502) to confirm imports available**

Run: `grep -n "^import\|^from" synlynk/team.py`
Expected output includes `os`, `json`, `sys` — confirms no new stdlib imports are needed beyond `urllib.parse` and `urllib.request`.

- [ ] **Step 4: Add manifest-flow helpers to `synlynk/team.py`, above `cmd_identity_init`**

```python
import urllib.parse
import urllib.request
import urllib.error


def _build_app_manifest_url(project: str, role: str) -> str:
    """GitHub App Manifest flow entry URL. User clicks through, GitHub redirects
    back with a one-time `code` param that _exchange_manifest_code trades for
    app credentials."""
    manifest = {
        "name": f"{project}-{role}",
        "url": "https://github.com",
        "hook_attributes": {"active": False},
        "public": False,
        "default_permissions": {
            "contents": "write",
            "pull_requests": "write",
            "issues": "write",
        },
    }
    import json as _json

    state = urllib.parse.quote(f"{project}:{role}")
    query = urllib.parse.urlencode({"manifest": _json.dumps(manifest), "state": state})
    return f"https://github.com/settings/apps/new?{query}"


def _exchange_manifest_code(code: str) -> dict:
    """POST /app-manifests/{code}/conversions -> {id, client_id, pem, slug, ...}."""
    req = urllib.request.Request(
        f"https://api.github.com/app-manifests/{code}/conversions",
        method="POST",
        headers={"Accept": "application/vnd.github+json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            import json as _json

            return _json.loads(resp.read())
    except urllib.error.HTTPError as exc:
        body = exc.read().decode(errors="replace")
        raise RuntimeError(f"App manifest conversion failed ({exc.code}): {body}") from exc


def _write_role_app_config(role: str, conversion: dict) -> str:
    """Writes .synlynk/github_apps/<role>.json + <role>.pem. Returns the json path."""
    apps_dir = os.path.join(".synlynk", "github_apps")
    os.makedirs(apps_dir, exist_ok=True)
    pem_path = os.path.join(apps_dir, f"{role}.pem")
    with open(pem_path, "w") as fh:
        fh.write(conversion["pem"])
    os.chmod(pem_path, 0o600)
    config = {
        "role": role,
        "app_id": str(conversion["id"]),
        "client_id": conversion["client_id"],
        "app_slug": conversion["slug"],
        "installation_id": None,  # filled in by _confirm_installation
        "private_key_path": pem_path,
    }
    json_path = os.path.join(apps_dir, f"{role}.json")
    import json as _json

    with open(json_path, "w") as fh:
        _json.dump(config, fh, indent=2)
    os.chmod(json_path, 0o600)
    return json_path


def _confirm_installation(app_slug: str, json_path: str) -> None:
    """After the user installs the App on the org, GET /app/installations to find
    the installation_id and patch it into the role's json file."""
    import json as _json

    with open(json_path) as fh:
        config = _json.load(fh)
    print(f"  → Install the App now: https://github.com/apps/{app_slug}/installations/new")
    input("  Press Enter once you've installed it on the org... ")
    # Installation lookup requires an app-level JWT, not an installation token —
    # reuse github_app_auth's JWT signer directly.
    from synlynk.github_app_auth import _sign_jwt

    jwt = _sign_jwt(config["app_id"], config["private_key_path"])
    req = urllib.request.Request(
        "https://api.github.com/app/installations",
        headers={
            "Authorization": f"Bearer {jwt}",
            "Accept": "application/vnd.github+json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as resp:
        installations = _json.loads(resp.read())
    match = next((i for i in installations if i["app_id"] == int(config["app_id"])), None)
    if not match:
        raise RuntimeError(
            f"No installation found for app_id={config['app_id']} — "
            "did you install it on the correct org?"
        )
    config["installation_id"] = str(match["id"])
    with open(json_path, "w") as fh:
        _json.dump(config, fh, indent=2)
    print(f"  ✓ installation_id={config['installation_id']} confirmed")


def cmd_identity_init_role(role: str, project: str = None) -> None:
    """Provision a GitHub App identity for `role` via the App Manifest flow."""
    json_path = os.path.join(".synlynk", "github_apps", f"{role}.json")
    if os.path.exists(json_path):
        print(f"  identity for role '{role}' already provisioned at {json_path}")
        return
    if project is None:
        project = os.path.basename(os.getcwd())
    url = _build_app_manifest_url(project, role)
    print(f"  1. Open this URL and click 'Create GitHub App':\n\n    {url}\n")
    print("  2. GitHub will redirect to a URL containing '?code=...&state=...'")
    code = input("  3. Paste the 'code' value here: ").strip()
    conversion = _exchange_manifest_code(code)
    json_path = _write_role_app_config(role, conversion)
    _confirm_installation(conversion["slug"], json_path)
    print(f"  ✓ Role '{role}' provisioned: {json_path}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_identity_init_role.py -v`
Expected: PASS (1 passed)

- [ ] **Step 6: Write the failing test for idempotency (already-provisioned role no-ops)**

```python
def test_cmd_identity_init_role_noops_if_already_provisioned(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text('{"role": "dev"}')

    from synlynk.team import cmd_identity_init_role

    cmd_identity_init_role("dev")
    captured = capsys.readouterr()
    assert "already provisioned" in captured.out
```

- [ ] **Step 7: Run test to verify it passes (no new code needed — the guard clause already exists from Step 4)**

Run: `pytest tests/test_identity_init_role.py -v`
Expected: PASS (2 passed)

- [ ] **Step 8: Wire the `--role` flag into the CLI parser**

Edit `synlynk/cli.py`, replace lines 346-348:

```python
    identity_parser = subparsers.add_parser("identity", help="Manage synlynk agent identity")
    identity_sub = identity_parser.add_subparsers(dest="identity_action")
    identity_sub.add_parser("init", help="Create local Ed25519 identity key")
```

with:

```python
    identity_parser = subparsers.add_parser("identity", help="Manage synlynk agent identity")
    identity_sub = identity_parser.add_subparsers(dest="identity_action")
    identity_init_parser = identity_sub.add_parser(
        "init", help="Create local Ed25519 identity key, or provision a role's GitHub App identity")
    identity_init_parser.add_argument(
        "--role", default=None,
        help="Provision a GitHub App identity for this role instead of the Ed25519 key")
    identity_sub.add_parser("list", help="List provisioned role identities and installation status")
```

- [ ] **Step 9: Wire the dispatch logic**

Edit `synlynk/cli.py`, replace the `elif args.command == "identity":` block (around line 1060):

```python
    elif args.command == "identity":
        action = getattr(args, "identity_action", None)
        if action == "init" or action is None:
            role = getattr(args, "role", None)
            if role:
                cmd_identity_init_role(role)
            else:
                cmd_identity_init()
        elif action == "list":
            cmd_identity_list()
        else:
            help_parsers.get("identity", parser).print_help()
```

Add `cmd_identity_init_role` and `cmd_identity_list` (written in Task 4) to the `from synlynk import (...)` block near line 719, alphabetically alongside `cmd_identity_init`.

- [ ] **Step 10: Run the full test suite for regressions on the identity command**

Run: `pytest tests/test_identity_init_role.py tests/test_cli_parser.py -v`
Expected: All pass. `cmd_identity_list` will not exist yet — if `test_cli_parser.py` imports the full CLI module, this step may fail until Task 4 lands; if so, stub `cmd_identity_list` as a one-line placeholder in `team.py` now (`def cmd_identity_list(): pass`) and let Task 4 replace it with the real implementation and its own test.

- [ ] **Step 11: Commit**

```bash
git add synlynk/team.py synlynk/cli.py tests/test_identity_init_role.py
git commit -m "feat: add --role flag to synlynk identity init for GitHub App provisioning

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 4: `synlynk identity list`

**Files:**
- Modify: `synlynk/team.py`
- Test: `tests/test_identity_list.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_identity_list.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cmd_identity_list_reports_provisioned_and_missing(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("roles:\n  - dev\n  - qa\n")
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir()
    (apps_dir / "dev.json").write_text(json.dumps({
        "role": "dev", "app_id": "1", "app_slug": "proj-dev", "installation_id": "9",
    }))

    from synlynk.team import cmd_identity_list

    cmd_identity_list()
    out = capsys.readouterr().out
    assert "dev" in out and "proj-dev" in out
    assert "qa" in out and "not provisioned" in out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_list.py -v`
Expected: FAIL (either `ImportError` if the Task 3 stub was never added, or `AssertionError` if the stub is a no-op).

- [ ] **Step 3: Implement `cmd_identity_list` in `synlynk/team.py`**

Replace any stub from Task 3 Step 10 with:

```python
def cmd_identity_list() -> None:
    """List every declared role's GitHub App identity provisioning status."""
    from synlynk.identity_roles import load_declared_roles

    roles = load_declared_roles()
    print(f"\n  {'role':<14}  {'app_slug':<24}  status")
    print(f"  {'─' * 14}  {'─' * 24}  {'─' * 20}")
    for role in roles:
        json_path = os.path.join(".synlynk", "github_apps", f"{role}.json")
        if not os.path.exists(json_path):
            print(f"  {role:<14}  {'—':<24}  not provisioned")
            continue
        with open(json_path) as fh:
            config = json.load(fh)
        slug = config.get("app_slug", "—")
        status = "provisioned" if config.get("installation_id") else "pending installation"
        print(f"  {role:<14}  {slug:<24}  {status}")
    print()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_identity_list.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/team.py tests/test_identity_list.py
git commit -m "feat: add synlynk identity list command

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 5: Inject role-scoped `GH_TOKEN` at dispatch time

**Files:**
- Modify: `synlynk/dispatch.py:1111-1113` (the `proc_env` build site)
- Test: `tests/test_dispatch_github_identity.py`

This is the call-routing rule from the spec: resolve the job's role from `stories.role` (via `story_id`), look up `.synlynk/github_apps/<role>.json`, mint/inject a token; if the role has no identity file, fall back to `.synlynk/github_apps/synlynk-bot.json`; if neither exists, inject nothing (falls through to whatever `GH_TOKEN`/`gh auth` is already on the host — never silently uses a human's personal token as an intentional substitution, but also never blocks dispatch if GitHub identity isn't provisioned yet).

**Panel-mandated scope narrowing (see "Panel Decision" section above):** injection only happens when the job was dispatched with `requires_gh_write=True` — the existing `dispatch_agent()` parameter at `synlynk/dispatch.py:815` used for the #426 GitHub-write routing gate. Every other dispatched job's `proc_env` is untouched by this task, regardless of whether a role identity is provisioned. This shrinks the blast radius of a minted token being present in a subprocess environment to only the jobs that actually declared a need to touch GitHub.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_dispatch_github_identity.py
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


def test_resolve_dispatch_gh_token_uses_role_specific_app(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "qa.json").write_text(json.dumps({
        "role": "qa", "app_id": "1", "installation_id": "2", "private_key_path": "qa.pem",
    }))

    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod, "get_installation_token",
        lambda role, app_config: f"token-for-{role}",
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
        dispatch_mod, "get_installation_token",
        lambda role, app_config: f"token-for-{role}",
    )
    token = dispatch_mod._resolve_dispatch_gh_token("dev")  # dev.json does not exist
    assert token == "token-for-synlynk-bot"


def test_resolve_dispatch_gh_token_returns_none_when_nothing_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.dispatch as dispatch_mod

    assert dispatch_mod._resolve_dispatch_gh_token("dev") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_github_identity.py -v`
Expected: FAIL with `AttributeError: module 'synlynk.dispatch' has no attribute '_resolve_dispatch_gh_token'`

- [ ] **Step 3: Add `_resolve_dispatch_gh_token` to `synlynk/dispatch.py`**

Add near the top of the file, after the existing `_load_harness_overrides` function (around line 68), and add the import at the top with the other `synlynk.*` imports:

```python
from synlynk.github_app_auth import get_installation_token


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
            print(f"  ⚠ could not mint GitHub App token for role '{candidate_role}': {exc}", file=sys.stderr)
            return None
    return None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch_github_identity.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Write the failing integration test — GH_TOKEN actually reaches `proc_env`**

```python
def _dispatch_with_fake_popen(monkeypatch, tmp_path, **dispatch_kwargs):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    os.makedirs(".agents", exist_ok=True)

    import synlynk.dispatch as dispatch_mod

    captured_env = {}

    class FakeProc:
        pid = 12345

    def fake_popen(cmd, **kwargs):
        captured_env.update(kwargs.get("env", {}))
        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_resolve_dispatch_gh_token", lambda role: "minted-token-abc")
    monkeypatch.setattr(dispatch_mod, "_create_job_worktree", lambda job_id, agent: str(tmp_path))
    monkeypatch.setattr(dispatch_mod, "_job_worktree_details", lambda job_id, agent: (str(tmp_path), "branch"))
    # story_id resolves to a role via the stories table lookup added below
    monkeypatch.setattr(dispatch_mod, "_role_for_story", lambda story_id: "qa")

    dispatch_mod.dispatch_agent(
        "codex", "do a thing", story_id="story-1", skip_preflight=True, job_id="job-test",
        **dispatch_kwargs,
    )
    return captured_env


def test_dispatch_agent_injects_gh_token_when_requires_gh_write(tmp_path, monkeypatch):
    captured_env = _dispatch_with_fake_popen(monkeypatch, tmp_path, requires_gh_write=True)
    assert captured_env.get("GH_TOKEN") == "minted-token-abc"


def test_dispatch_agent_does_not_inject_gh_token_by_default(tmp_path, monkeypatch):
    # requires_gh_write defaults to False — most dispatched jobs never touch GitHub,
    # and per the 2026-07-25 panel decision, injection must not happen for them.
    captured_env = _dispatch_with_fake_popen(monkeypatch, tmp_path)
    assert "GH_TOKEN" not in captured_env
```

- [ ] **Step 6: Run tests to verify they fail**

Run: `pytest tests/test_dispatch_github_identity.py -k "injects_gh_token or does_not_inject" -v`
Expected: FAIL — `GH_TOKEN` not in `captured_env` for the positive case (nothing injects it yet), or an `AttributeError` on `_role_for_story` not existing.

- [ ] **Step 7: Add `_role_for_story` and wire the injection into `proc_env`**

Add near `_resolve_dispatch_gh_token`:

```python
def _role_for_story(story_id: str) -> Optional[str]:
    """Look up stories.role for a story_id. Returns None if no story_id or no row."""
    if not story_id:
        return None
    get_db = _pkg("_get_db")
    if not get_db:
        return None
    conn = get_db()
    if conn is None:
        return None
    row = conn.execute("SELECT role FROM stories WHERE story_id=?", (story_id,)).fetchone()
    return row[0] if row else None
```

Edit the `proc_env` block at `synlynk/dispatch.py:1111-1113` from:

```python
    proc_env = os.environ.copy()
    proc_env.update(overrides.get("env", {}))
    for var in contract.get("env_vars_required", []):
```

to:

```python
    proc_env = os.environ.copy()
    proc_env.update(overrides.get("env", {}))
    if requires_gh_write:
        gh_token = _resolve_dispatch_gh_token(_role_for_story(story_id) or "dev")
        if gh_token:
            proc_env["GH_TOKEN"] = gh_token
    for var in contract.get("env_vars_required", []):
```

`requires_gh_write` is already an in-scope parameter of `dispatch_agent()` (`synlynk/dispatch.py:815`) — no new parameter needed, this just reads the one that already exists.

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_dispatch_github_identity.py -v`
Expected: PASS (5 passed)

- [ ] **Step 9: Run the full dispatch test file to check for regressions**

Run: `pytest tests/test_dispatch.py tests/test_dispatch_cycle.py tests/test_dispatch_local_agent.py tests/test_dispatch_context_mode_hint.py -v`
Expected: All pass — this task only adds two lines to the `proc_env` build path and one new lookup function; no existing behavior changes for jobs where no GitHub App is provisioned (fallback returns `None`, nothing gets injected, `proc_env` behaves exactly as before).

- [ ] **Step 10: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch_github_identity.py
git commit -m "feat: inject role-scoped GH_TOKEN at dispatch time via GitHub App installation tokens

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 6: Doctor health check for un-provisioned declared roles

**Files:**
- Modify: `synlynk/doctor.py`
- Test: `tests/test_doctor_identity_roles.py`

This is the "diff `.synlynk/roles.yaml` against `.synlynk/github_apps/`" step from the spec's Onboarding Integration section — implemented as a `doctor` health check (matching the existing `_hc_identity_key` pattern at `synlynk/doctor.py:96`) rather than hooking into `synlynk upgrade`, since `synlynk upgrade` in this codebase is exclusively the self-upgrade-the-synlynk-binary command (`synlynk/upgrade.py`) and has no per-project migration/diff mechanism today — `doctor` is the existing extension point for "is this project's setup complete" checks.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_doctor_identity_roles.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_hc_identity_roles_warns_on_missing_provisioning(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("roles:\n  - dev\n  - qa\n")

    from synlynk.doctor import _hc_identity_roles

    result = _hc_identity_roles()
    assert result.status == "warn"
    assert "dev" in result.message and "qa" in result.message
    assert "synlynk identity init --role" in result.fix


def test_hc_identity_roles_ok_when_all_provisioned(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("roles:\n  - dev\n")
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir()
    (apps_dir / "dev.json").write_text('{"role": "dev", "installation_id": "1"}')

    from synlynk.doctor import _hc_identity_roles

    result = _hc_identity_roles()
    assert result.status == "ok"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_doctor_identity_roles.py -v`
Expected: FAIL with `ImportError: cannot import name '_hc_identity_roles'`

- [ ] **Step 3: Add `_hc_identity_roles` to `synlynk/doctor.py`, directly after `_hc_identity_key` (line ~110)**

```python
def _hc_identity_roles() -> HealthCheck:
    """Diffs .synlynk/roles.yaml's declared roles against provisioned GitHub Apps."""
    from synlynk.identity_roles import load_declared_roles

    roles = load_declared_roles()
    missing = []
    for role in roles:
        json_path = os.path.join(".synlynk", "github_apps", f"{role}.json")
        if not os.path.exists(json_path):
            missing.append(role)
            continue
        try:
            with open(json_path) as fh:
                config = json.load(fh)
        except (OSError, ValueError):
            missing.append(role)
            continue
        if not config.get("installation_id"):
            missing.append(role)
    if not missing:
        return HealthCheck("identity_roles", "ok", f"All declared roles provisioned ({', '.join(roles)})")
    return HealthCheck(
        "identity_roles",
        "warn",
        f"Missing GitHub App identity for role(s): {', '.join(missing)}",
        fix=f"Run: synlynk identity init --role {missing[0]}" + (
            f" (and {len(missing) - 1} more)" if len(missing) > 1 else ""
        ),
    )
```

- [ ] **Step 4: Register it in `HEALTH_CHECKS`**

Edit `synlynk/doctor.py:222-230`, add `_hc_identity_roles` after `_hc_identity_key`:

```python
HEALTH_CHECKS = [
    _hc_python_version,
    _hc_project_init,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_identity_roles,
    _hc_agent_profiles,
    _hc_instruction_files,
    _hc_model_rates,
    _hc_version_current,
]
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_doctor_identity_roles.py -v`
Expected: PASS (2 passed)

- [ ] **Step 6: Run the full doctor test file for regressions**

Run: `pytest tests/test_synlynk.py -k doctor -v` (or the correct doctor test file if one exists separately — check with `find . -iname "*doctor*" -path "*/tests/*"` first)
Expected: All existing doctor tests still pass; `HEALTH_CHECKS` list length increases by one and any test asserting an exact count needs updating to match — if such a test exists, update its expected count in this same step.

- [ ] **Step 7: Commit**

```bash
git add synlynk/doctor.py tests/test_doctor_identity_roles.py
git commit -m "feat: add doctor health check for un-provisioned identity roles

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 7: Hygiene hardening — permission enforcement + gitignore verification

**Files:**
- Modify: `synlynk/doctor.py` (new health check)
- Modify: `synlynk/team.py` (`_write_role_app_config` — set perms defensively, don't just trust the initial `os.chmod`)
- Test: `tests/test_identity_file_permissions.py`

Panel-mandated hygiene items #2 and #4 from the "Panel Decision" section: `.pem`/`.json` identity files must actually carry `0o600` at rest (not just at the moment they're written — a doctor check catches drift, e.g. from an `umask` misconfiguration or a careless `cp`), and `.gitignore` must be proven to exclude `.synlynk/github_apps/` rather than assumed to inherit the top-level `.synlynk/` ignore.

- [ ] **Step 1: Write the failing test for the gitignore verification**

```python
# tests/test_identity_file_permissions.py
import os
import stat
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_gitignore_excludes_github_apps_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], check=True, cwd=tmp_path)
    gitignore_src = os.path.join(os.path.dirname(__file__), "..", ".gitignore")
    with open(gitignore_src) as fh:
        gitignore_content = fh.read()
    (tmp_path / ".gitignore").write_text(gitignore_content)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    (apps_dir / "dev.json").write_text("{}")
    (apps_dir / "dev.pem").write_text("fake-key")

    result = subprocess.run(
        ["git", "check-ignore", ".synlynk/github_apps/dev.json", ".synlynk/github_apps/dev.pem"],
        cwd=tmp_path, capture_output=True, text=True,
    )
    assert result.returncode == 0, (
        f".synlynk/github_apps/*.json and *.pem must be gitignored — "
        f"git check-ignore exited {result.returncode}: {result.stderr}"
    )
```

- [ ] **Step 2: Run test to verify it currently passes (this locks in existing behavior from Task 1's gitignore edit, it's a regression guard, not new functionality)**

Run: `pytest tests/test_identity_file_permissions.py::test_gitignore_excludes_github_apps_directory -v`
Expected: PASS — Task 1's `!.synlynk/roles.yaml` negation only un-ignores that one file; `.synlynk/github_apps/` is still covered by the top-level `.synlynk/` ignore. This test exists so a future edit to `.gitignore` can't silently break that without a test failing.

- [ ] **Step 3: Write the failing test for the doctor permission check**

```python
def test_hc_identity_file_perms_warns_on_loose_permissions(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_path = apps_dir / "dev.pem"
    pem_path.write_text("fake-key")
    os.chmod(pem_path, 0o644)  # too permissive

    from synlynk.doctor import _hc_identity_file_perms

    result = _hc_identity_file_perms()
    assert result.status == "warn"
    assert "dev.pem" in result.message


def test_hc_identity_file_perms_ok_when_0600(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    apps_dir = tmp_path / ".synlynk" / "github_apps"
    apps_dir.mkdir(parents=True)
    pem_path = apps_dir / "dev.pem"
    pem_path.write_text("fake-key")
    os.chmod(pem_path, 0o600)
    json_path = apps_dir / "dev.json"
    json_path.write_text("{}")
    os.chmod(json_path, 0o600)

    from synlynk.doctor import _hc_identity_file_perms

    result = _hc_identity_file_perms()
    assert result.status == "ok"


def test_hc_identity_file_perms_ok_when_no_apps_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    from synlynk.doctor import _hc_identity_file_perms

    result = _hc_identity_file_perms()
    assert result.status == "ok"
```

- [ ] **Step 4: Run tests to verify they fail**

Run: `pytest tests/test_identity_file_permissions.py -k "perms" -v`
Expected: FAIL with `ImportError: cannot import name '_hc_identity_file_perms'`

- [ ] **Step 5: Add `_hc_identity_file_perms` to `synlynk/doctor.py`, directly after `_hc_identity_roles` (added in Task 6)**

```python
def _hc_identity_file_perms() -> HealthCheck:
    """Verifies .synlynk/github_apps/*.{json,pem} are still 0o600 — private key
    material and installation IDs at rest must not be group/world-readable."""
    apps_dir = os.path.join(".synlynk", "github_apps")
    if not os.path.isdir(apps_dir):
        return HealthCheck("identity_file_perms", "ok", "No .synlynk/github_apps/ directory yet")
    loose = []
    for fname in sorted(os.listdir(apps_dir)):
        if not (fname.endswith(".json") or fname.endswith(".pem")):
            continue
        path = os.path.join(apps_dir, fname)
        mode = stat.S_IMODE(os.stat(path).st_mode)
        if mode != 0o600:
            loose.append(f"{fname} ({oct(mode)})")
    if not loose:
        return HealthCheck("identity_file_perms", "ok", "All identity files are 0o600")
    return HealthCheck(
        "identity_file_perms",
        "warn",
        f"Loose permissions on: {', '.join(loose)}",
        fix="Run: chmod 600 .synlynk/github_apps/*.json .synlynk/github_apps/*.pem",
    )
```

Add `import stat` to `synlynk/doctor.py`'s imports if not already present.

- [ ] **Step 6: Register it in `HEALTH_CHECKS`, directly after `_hc_identity_roles`**

```python
HEALTH_CHECKS = [
    _hc_python_version,
    _hc_project_init,
    _hc_docs_dir,
    _hc_identity_key,
    _hc_identity_roles,
    _hc_identity_file_perms,
    _hc_agent_profiles,
    _hc_instruction_files,
    _hc_model_rates,
    _hc_version_current,
]
```

- [ ] **Step 7: Run tests to verify they pass**

Run: `pytest tests/test_identity_file_permissions.py -v`
Expected: PASS (4 passed)

- [ ] **Step 8: Commit**

```bash
git add synlynk/doctor.py tests/test_identity_file_permissions.py
git commit -m "feat: doctor checks for identity file permission drift and gitignore coverage

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 8: Auto-register newly provisioned roles into `.synlynk/roles.yaml`

**Files:**
- Modify: `synlynk/team.py` (`cmd_identity_init_role`)
- Test: `tests/test_role_add_identity_prompt.py`

**Confirmed before writing this task:** `grep -rn "\"add\"" synlynk/cli.py | grep -i role` and `grep -n "def cmd_role" synlynk/*.py` return no `role add` subcommand — only `cmd_roles` (`synlynk/__init__.py:1104`), which is a read-only table viewer with `--fix` for directive-file fences, not a role-registration command. The spec's "`synlynk role add <name>` prompts to provision" therefore has no existing command to extend. Instead, this task wires the registration the other direction: `cmd_identity_init_role` (Task 3) auto-appends the role to `.synlynk/roles.yaml` on successful provisioning, so any role provisioned via `identity init --role` becomes "declared" without a separate `role add` step. If a real `synlynk role add` command is added later, it should call `write_declared_roles` the same way.

- [ ] **Step 1: Write the test**

```python
# tests/test_role_add_identity_prompt.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_identity_init_role_registers_new_role_in_roles_yaml(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    import synlynk.team as team_mod

    monkeypatch.setattr(team_mod, "_build_app_manifest_url", lambda project, role: "http://fake")
    monkeypatch.setattr(team_mod, "input", lambda prompt: "fake-code", raising=False)
    monkeypatch.setattr(team_mod, "_exchange_manifest_code", lambda code: {
        "id": 1, "client_id": "c1", "slug": "proj-designer", "pem": "fake-pem",
    })
    monkeypatch.setattr(team_mod, "_confirm_installation", lambda slug, path: None)

    team_mod.cmd_identity_init_role("designer")

    from synlynk.identity_roles import load_declared_roles

    assert "designer" in load_declared_roles()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_add_identity_prompt.py -v`
Expected: FAIL — `designer` not in declared roles (nothing writes to `roles.yaml` yet).

- [ ] **Step 3: Apply the edit to `cmd_identity_init_role` in `synlynk/team.py`**

(Full updated function, replacing the Task 3 Step 4 version's final two lines)

```python
def cmd_identity_init_role(role: str, project: str = None) -> None:
    """Provision a GitHub App identity for `role` via the App Manifest flow."""
    json_path = os.path.join(".synlynk", "github_apps", f"{role}.json")
    if os.path.exists(json_path):
        print(f"  identity for role '{role}' already provisioned at {json_path}")
        return
    if project is None:
        project = os.path.basename(os.getcwd())
    url = _build_app_manifest_url(project, role)
    print(f"  1. Open this URL and click 'Create GitHub App':\n\n    {url}\n")
    print("  2. GitHub will redirect to a URL containing '?code=...&state=...'")
    code = input("  3. Paste the 'code' value here: ").strip()
    conversion = _exchange_manifest_code(code)
    json_path = _write_role_app_config(role, conversion)
    _confirm_installation(conversion["slug"], json_path)
    print(f"  ✓ Role '{role}' provisioned: {json_path}")

    from synlynk.identity_roles import load_declared_roles, write_declared_roles

    declared = load_declared_roles()
    if role not in declared:
        write_declared_roles(declared + [role])
        print(f"  ✓ added '{role}' to .synlynk/roles.yaml")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_add_identity_prompt.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/team.py tests/test_role_add_identity_prompt.py
git commit -m "feat: auto-register newly provisioned roles into .synlynk/roles.yaml

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 9: Redact minted GH_TOKEN values from `synlynk logs` display

**Files:**
- Modify: `synlynk/__init__.py` (`cmd_logs`)
- Test: `tests/test_logs_token_redaction.py`

Panel-mandated hygiene item #5. `synlynk/dispatch.py:1096-1109` redirects the dispatched CLI's raw stdout+stderr straight into `.synlynk/logs/<job_id>.log` via shell `2>&1` — Python never sees that content as it's written, so it can't be filtered at write time without restructuring the subprocess model (out of scope here). What *is* in scope: `.synlynk/logs/` is already gitignored (covered by the top-level `.synlynk/` ignore, same as `.synlynk/github_apps/` — see Task 7), so the persistence risk is local-disk only, not repo/remote leakage. The realistic exposure surface this task closes is **display**: `cmd_logs` (`synlynk/__init__.py:2281`) prints that file's raw content straight to the terminal via `synlynk logs <job_id>` — if the dispatched CLI ever echoed its env (crash dump, debug flag, a sub-command that runs `env`), a viewer would see the token verbatim. Redact any minted token value at display time, using the in-memory cache `github_app_auth._token_cache` already populated during that session.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_logs_token_redaction.py
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cmd_logs_redacts_active_token_values(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    logs_dir = tmp_path / ".synlynk" / "logs"
    logs_dir.mkdir(parents=True)
    log_file = logs_dir / "job-test.log"
    log_file.write_text("normal output line\nGH_TOKEN=ghs_supersecrettoken123 leaked by accident\nmore output\n")

    import synlynk as sl
    from synlynk import github_app_auth as gh_auth

    gh_auth._token_cache.clear()
    gh_auth._token_cache["dev"] = {"token": "ghs_supersecrettoken123", "expires_at": 9999999999}

    monkeypatch.setattr(sl, "_load_jobs", lambda: [
        {"id": "job-test", "agent": "codex", "log_file": str(log_file)}
    ])

    sl.cmd_logs("job-test", tail=50)
    out = capsys.readouterr().out
    assert "ghs_supersecrettoken123" not in out
    assert "***REDACTED***" in out
    assert "normal output line" in out  # non-secret lines still display normally
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_logs_token_redaction.py -v`
Expected: FAIL — `ghs_supersecrettoken123` appears verbatim in captured output (no redaction exists yet).

- [ ] **Step 3: Add a redaction helper and wire it into `cmd_logs` in `synlynk/__init__.py`**

Add near `cmd_logs` (before its definition, around line 2280):

```python
def _redact_active_tokens(text: str) -> str:
    """Strip any currently-cached GitHub App installation token values from
    display text. Best-effort: only catches tokens minted this process
    lifetime (github_app_auth._token_cache), not tokens from prior runs —
    those have already expired by the time a later `synlynk logs` call
    could display them, since installation tokens live ~1hr."""
    from synlynk.github_app_auth import _token_cache

    for entry in _token_cache.values():
        token = entry.get("token")
        if token:
            text = text.replace(token, "***REDACTED***")
    return text
```

Edit `cmd_logs`'s display loop — replace:

```python
    if renderer is not None:
        for line in display_lines:
            rendered = renderer(line)
            if rendered is not None:
                print(rendered, end="")
    else:
        for line in display_lines:
            print(line, end="")
```

with:

```python
    if renderer is not None:
        for line in display_lines:
            rendered = renderer(line)
            if rendered is not None:
                print(_redact_active_tokens(rendered), end="")
    else:
        for line in display_lines:
            print(_redact_active_tokens(line), end="")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_logs_token_redaction.py -v`
Expected: PASS

- [ ] **Step 5: Run the existing `cmd_logs` test coverage for regressions**

Run: `grep -rn "cmd_logs" tests/*.py` to find existing tests, then run them, e.g. `pytest tests/test_jobs.py -k logs -v`
Expected: All pass — redaction is a no-op when `_token_cache` is empty (the common case for any job that isn't a `requires_gh_write` dispatch), so non-GitHub-identity jobs see identical output to before this task.

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_logs_token_redaction.py
git commit -m "feat: redact minted GH_TOKEN values from synlynk logs display

Co-Authored-By: Codex <noreply@openai.com>"
```

---

## Task 10: End-to-end manual validation (rollout step 2 from the spec, narrowed per panel decision)

**Not automatable — this is the spec's explicit real-world validation pass.** No file changes; this is a checklist to run once Tasks 1-9 are merged.

**Narrowed per the 2026-07-25 panel decision: validate a single role (`dev`) end-to-end first. Do not provision `qa` or any other role in this pass — that's an explicit follow-up step gated on this validation succeeding, not bundled into it.**

- [ ] **Step 1:** On the `rxcc` repo (or synlynk itself, whichever the user designates), run `synlynk identity init --role dev` and complete the two-click flow against the `Dialify` org (per the spec's provisioning target).
- [ ] **Step 2:** Run `synlynk identity list` — confirm `dev` shows `provisioned`.
- [ ] **Step 3:** Run `synlynk doctor` — confirm `_hc_identity_roles` and `_hc_identity_file_perms` (Task 7) both report `ok`.
- [ ] **Step 4:** Dispatch a trivial `dev`-role job that opens a PR (`--requires-gh-write`); confirm via `gh pr view <n> --json author` that the author is `rxcc-dev[bot]`, not the human's personal account.
- [ ] **Step 5:** Run `synlynk logs <job-id>` on that dispatch and confirm the minted token does not appear verbatim in the output (Task 9's redaction working against a real token, not just the unit test's fake one).
- [ ] **Step 6:** Report results back to the user. Only after this single-role slice is confirmed working should a follow-up plan be written to (a) provision the `qa` role and validate the cross-role review scenario from #423/#417 (`gh pr review <n> --approve` succeeding with a non-empty `reviewDecision`), and (b) generalize `GH_TOKEN` injection beyond the current `--requires-gh-write`-gated single-role case. Do not fold either into this validation pass — that's the "ship fully as planned" scope the panel explicitly rejected.

---

## Self-Review Notes

**Spec coverage:** Identity model (role-not-agent) — Tasks 1, 3. Provisioning via App Manifest flow — Task 3. Token minting/caching — Task 2. Call-routing at dispatch — Task 5. Role extensibility (not hardcoded to the 6-value enum) — Task 1's `load_declared_roles` reads arbitrary role names from `roles.yaml`. Onboarding integration (`synlynk init`/`upgrade` diffing) — implemented as a `doctor` check in Task 6 instead, since neither `init` nor `upgrade` has a per-project migration mechanism in the current codebase (documented as a deliberate deviation, not a gap — flag to the user if the literal `init`/`upgrade` hook is still wanted). `synlynk identity list` — Task 4. Fallback to `synlynk-bot` catch-all — Task 5. Non-goals (Mode B, GOVERNS domain-adaptivity, retroactive rewrite, webhooks) — correctly out of scope, nothing in this plan touches them.

**Gaps flagged to the user, not silently resolved:** the RS256-signing dependency question (resolved via user decision: shell out to `openssl`) and the `init`/`upgrade` vs. `doctor` integration point (flagged above, recommend confirming before Task 6 execution if the literal spec wording matters more than matching existing extension points).

**Type/name consistency check:** `get_installation_token(role, app_config)` (Task 2) is called identically in Task 5's `_resolve_dispatch_gh_token`. `load_declared_roles()`/`write_declared_roles()` (Task 1) are called identically in Tasks 6 and 7. `cmd_identity_init_role(role, project=None)` (Task 3) signature matches its Task 7 modification and its Task 3/8 CLI call site (`cmd_identity_init_role(role)`). `_token_cache` (Task 2, `github_app_auth.py`) is read identically by Task 9's `_redact_active_tokens`.

**Panel review (2026-07-25):** Because this touches auth, `synlynk decide --panel claude,agy,codex,grok --record` was run before dispatch (`project-docs/decisions/2026-07-25-should-synlynk-implement-per-role-github.md`). All three responding panelists (agy returned no output) converged: proceed with Codex as implementer per the capability table, but narrow scope and add hygiene gates before merge. This plan was revised in response — see "Panel Decision (2026-07-25) — Read This Second" near the top, and the six items it lists map onto this plan as: narrower first slice → Task 10 validates `dev` only, `qa` deferred; `GH_TOKEN` injection gated on `requires_gh_write` → Task 5 (already matched existing #426 pattern, no change needed); hardened openssl path resolution → Task 2's `_resolve_openssl_path`; 0o600 permission drift-check → Task 7's `_hc_identity_file_perms`; log/telemetry secret scrubbing → Task 9; extra security review gate before merge → this is a process instruction for the PR itself (not a code task): **the PR implementing this plan requires an explicit Claude security-focused review pass covering the threat model and token-handling details, in addition to the standard non-authoring-reviewer + `synlynk pr check` rule from CLAUDE.md's PR Review Discipline** — flag this to whoever merges the PR.

**Total tasks: 10** (was 8 before panel revision — Task 7 "Hygiene hardening" and Task 9 "Redact minted GH_TOKEN values" are new; old Task 7 "Auto-register roles" renumbered to Task 8; old Task 8 "End-to-end manual validation" renumbered to Task 10 and narrowed to single-role scope).
