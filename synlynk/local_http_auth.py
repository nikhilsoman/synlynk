"""Shared-secret auth for the local daemon and Vizor HTTP servers.

Token lives in ``~/.synlynk/daemon.token`` (mode 0600), matching the existing
GitHub-app token-file pattern. Clients must send it as ``X-Synlynk-Token`` —
never a cookie, which browsers would auto-attach on cross-site POSTs.
"""

from __future__ import annotations

import os
import secrets
from urllib.parse import urlparse
from typing import Mapping, Optional, Tuple, Union

TOKEN_HEADER = "X-Synlynk-Token"
_LOCAL_HOSTNAMES = {"localhost", "127.0.0.1", "::1"}

Headers = Union[Mapping[str, str], object]


def http_token_path() -> str:
    return os.path.join(os.path.expanduser("~"), ".synlynk", "daemon.token")


def ensure_local_token(path: Optional[str] = None) -> str:
    """Return the local HTTP token, creating it with mode 0600 if missing."""
    token_path = os.path.abspath(path or http_token_path())
    directory = os.path.dirname(token_path)
    if directory:
        os.makedirs(directory, exist_ok=True)
    if os.path.exists(token_path):
        try:
            with open(token_path, encoding="utf-8") as handle:
                existing = handle.read().strip()
        except OSError:
            existing = ""
        if existing:
            try:
                os.chmod(token_path, 0o600)
            except OSError:
                pass
            return existing
    token = secrets.token_urlsafe(32)
    flags = os.O_WRONLY | os.O_CREAT | os.O_TRUNC
    fd = os.open(token_path, flags, 0o600)
    try:
        os.write(fd, token.encode("utf-8"))
        os.fsync(fd)
    finally:
        os.close(fd)
    os.chmod(token_path, 0o600)
    return token


def header_value(headers: Optional[Headers], name: str) -> str:
    if headers is None:
        return ""
    getter = getattr(headers, "get", None)
    if getter is None:
        return ""
    value = getter(name)
    if not value:
        value = getter(name.lower())
    if not value:
        return ""
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ""
    return str(value).strip()


def _is_local_url(value: str) -> bool:
    if not value or value.lower() == "null":
        return False
    parsed = urlparse(value)
    if parsed.scheme not in ("http", "https"):
        return False
    hostname = (parsed.hostname or "").lower()
    if hostname.startswith("[") and hostname.endswith("]"):
        hostname = hostname[1:-1]
    return hostname in _LOCAL_HOSTNAMES


def local_browser_origin_ok(headers: Optional[Headers]) -> bool:
    """Allow CLI callers with no Origin/Referer; reject non-local browsers."""
    origin = header_value(headers, "Origin")
    if origin:
        return _is_local_url(origin)
    referer = header_value(headers, "Referer")
    if referer:
        return _is_local_url(referer)
    return True


def authorize_local_request(
    headers: Optional[Headers],
    path: Optional[str] = None,
) -> Tuple[bool, int, str]:
    """Return ``(ok, status, message)`` for a local HTTP request."""
    expected = ensure_local_token(path)
    if not expected:
        return False, 401, "unauthorized"
    provided = header_value(headers, TOKEN_HEADER)
    if not provided or not secrets.compare_digest(provided, expected):
        return False, 401, "unauthorized"
    if not local_browser_origin_ok(headers):
        return False, 403, "forbidden origin"
    return True, 200, ""
