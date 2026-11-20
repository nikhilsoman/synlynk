"""Canonical bug-report bundle: schema, normalization, fingerprint, renderer.

FROZEN CONTRACT: the issue form, CLI renderer, CI ``intake`` check and Vizor
route all derive from BUNDLE_SCHEMA_VERSION / ALLOWED_FIELDS. Change them only
with a version bump.
"""
from __future__ import annotations

import hashlib
import os
import re
import secrets
from pathlib import Path

BUNDLE_SCHEMA_VERSION = 1
ALLOWED_FIELDS = (
    "schema",
    "synlynk_version",
    "python_version",
    "os",
    "arch",
    "install_method",
    "harnesses",
    "env_set",
    "doctor",
    "config_schema",
    "policy_schema",
    "db_shape",
    "worktree",
    "remote",
    "identity",
    "fingerprint",
)

_DEFAULT_SALT_PATH = Path.home() / ".synlynk" / "report_salt"


def normalize_path(path: str) -> str:
    home = os.environ.get("HOME") or str(Path.home())
    return "~" + path[len(home) :] if home and path.startswith(home) else path


def _salt(salt_path: Path) -> bytes:
    if salt_path.exists():
        return salt_path.read_bytes()
    salt_path.parent.mkdir(parents=True, exist_ok=True)
    salt = secrets.token_bytes(16)
    salt_path.write_bytes(salt)
    os.chmod(salt_path, 0o600)
    return salt


def salted_hash(value: str, salt_path: Path = _DEFAULT_SALT_PATH) -> str:
    return hashlib.sha256(_salt(Path(salt_path)) + value.encode()).hexdigest()[:10]


def normalize_remote(url: str) -> str:
    url = re.sub(r"^[a-z+]+://", "", url.strip())
    url = re.sub(r"^[^@/]+(:[^@/]*)?@", "", url)
    url = url.replace(":", "/", 1) if re.match(r"^[^/]+:[^/0-9]", url) else url
    return re.sub(r"\.git$", "", url)


_VARIABLE = [
    (re.compile(r"(/[\w.~-]+)+"), "<path>"),
    (re.compile(r"\b[0-9a-f]{7,}\b"), "<hex>"),
    (re.compile(r"\d+"), "<n>"),
]


def normalize_error_line(line: str) -> str:
    for pattern, replacement in _VARIABLE:
        line = pattern.sub(replacement, line)
    return line.strip()


def fingerprint(
    failing_check_ids: list[str], command: str, exit_code: int, first_error: str
) -> str:
    material = "|".join(
        [
            ",".join(sorted(failing_check_ids)),
            command,
            str(exit_code),
            normalize_error_line(first_error),
        ]
    )
    return hashlib.sha256(material.encode()).hexdigest()[:12]
