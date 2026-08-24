"""GitHub App JWT signing and installation token minting."""

import base64
import calendar
import json
import os
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from datetime import datetime
from typing import Optional


GITHUB_API = "https://api.github.com"
_openssl_path_cache = None


def _redaction_cache_path() -> str:
    return os.path.join(".synlynk", "token_redaction_cache.json")


def _role_token_cache_path(role: str) -> str:
    return os.path.join(".synlynk", "github_apps", f"{role}.token.json")


def _persist_token_for_redaction(role: str, token: str, expires_at: float) -> None:
    """Best-effort: append this token to the on-disk redaction cache so a
    later `synlynk logs` process (different PID) can still redact it."""
    path = _redaction_cache_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        entries = {}
        if os.path.exists(path):
            with open(path) as f:
                entries = json.load(f)
        if not isinstance(entries, dict):
            entries = {}
        now = time.time()
        entries = {
            k: v for k, v in entries.items()
            if isinstance(v, dict) and v.get("expires_at", 0) > now
        }
        entries[token] = {"expires_at": expires_at, "role": role}
        with open(path, "w") as f:
            json.dump(entries, f)
        os.chmod(path, 0o600)
    except OSError:
        pass


def _load_redaction_tokens() -> list:
    """Return currently-valid token strings from the on-disk redaction cache."""
    path = _redaction_cache_path()
    if not os.path.exists(path):
        return []
    try:
        with open(path) as f:
            entries = json.load(f)
        if not isinstance(entries, dict):
            return []
    except (OSError, ValueError, TypeError):
        return []
    now = time.time()
    return [
        tok
        for tok, meta in entries.items()
        if isinstance(meta, dict) and meta.get("expires_at", 0) > now
    ]


def _resolve_openssl_path() -> str:
    """Resolve a verified, absolute openssl path once."""
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
    resolved = os.path.realpath(resolved)
    if not os.path.isabs(resolved):
        raise RuntimeError(
            f"resolved openssl path is not absolute: {resolved!r}"
        )
    if not os.path.exists(resolved) or not os.access(resolved, os.X_OK):
        raise RuntimeError(
            f"resolved openssl path is not executable: {resolved!r}"
        )
    _openssl_path_cache = resolved
    return resolved


def _b64url(data: bytes) -> bytes:
    return base64.urlsafe_b64encode(data).rstrip(b"=")


def _b64url_decode(data: bytes) -> bytes:
    padding = b"=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def _build_jwt_signing_input(app_id: str, now: float = None) -> tuple:
    """Return (signing_input, header_b64, payload_b64) for a GitHub App JWT."""
    now = int(now if now is not None else time.time())
    header = _b64url(json.dumps({"alg": "RS256", "typ": "JWT"}, separators=(",", ":")).encode())
    payload = _b64url(json.dumps(
        {"iat": now - 60, "exp": now + 540, "iss": str(app_id)},
        separators=(",", ":"),
    ).encode())
    return header + b"." + payload, header, payload


def _sign_jwt(app_id: str, private_key_path: str) -> str:
    """Sign a GitHub App JWT by shelling out to openssl for RS256."""
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
    expires_dt = datetime.strptime(data["expires_at"], "%Y-%m-%dT%H:%M:%SZ")
    expires_at = calendar.timegm(expires_dt.timetuple())
    return token, expires_at


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
