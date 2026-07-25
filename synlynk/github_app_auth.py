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


GITHUB_API = "https://api.github.com"
_token_cache = {}  # role -> {"token": str, "expires_at": float}
_openssl_path_cache = None


def _redaction_cache_path() -> str:
    return os.path.join(".synlynk", "token_redaction_cache.json")


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
