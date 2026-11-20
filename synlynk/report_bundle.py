"""Canonical bug-report bundle: schema, normalization, fingerprint, renderer.

FROZEN CONTRACT: the issue form, CLI renderer, CI ``intake`` check and Vizor
route all derive from BUNDLE_SCHEMA_VERSION / ALLOWED_FIELDS. Change them only
with a version bump.
"""
from __future__ import annotations

import hashlib
import json
import os
import platform
import re
import secrets
import shutil
import sqlite3
import subprocess
import sys
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


def _env_names() -> list[str]:
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    names: set[str] = set()
    for config in HARNESS_CAPABILITY_BASELINES.values():
        names.update(config.get("env_passthrough", []))
    return sorted(names)


def _collect_harnesses() -> list[dict[str, object]]:
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    return [
        {"name": name, "binary_found": shutil.which(name) is not None}
        for name in sorted(HARNESS_CAPABILITY_BASELINES)
    ]


def _collect_doctor() -> list[dict[str, str]]:
    from synlynk.doctor import HEALTH_CHECKS

    rows = []
    for check in HEALTH_CHECKS:
        try:
            result = check()
            rows.append({"id": result.name, "status": result.status})
        except Exception:
            rows.append(
                {"id": getattr(check, "__name__", "check"), "status": "unavailable"}
            )
    return rows


def _schema_version(path: Path) -> int | str:
    data = json.loads(path.read_text())
    version = data.get("schema_version") if isinstance(data, dict) else None
    return version if isinstance(version, int) else "unavailable"


def _collect_config_schema(root: Path = Path(".")) -> dict[str, int | str] | str:
    """Collect schema versions from an allowlist of configuration files."""
    config_dir = Path(root) / ".synlynk"
    versions = {}
    for name in ("billing", "config", "workspace"):
        path = config_dir / f"{name}.json"
        if path.is_file():
            versions[name] = _schema_version(path)
    return versions or "unavailable"


def _collect_policy_schema(root: Path = Path(".")) -> int | str:
    """Collect only the policy document's integer schema version."""
    path = Path(root) / ".synlynk" / "policy.json"
    return _schema_version(path) if path.is_file() else "unavailable"


def _quote_identifier(identifier: str) -> str:
    return '"' + identifier.replace('"', '""') + '"'


def _collect_db_shape(db_path: Path | str | None = None) -> dict[str, int]:
    """Return aggregate state-DB schema and row counts, never row content."""
    if db_path is None:
        from synlynk import get_state_db_path

        db_path = get_state_db_path()
    path = Path(db_path).expanduser().resolve()
    with sqlite3.connect(f"file:{path}?mode=ro", uri=True, timeout=5.0) as conn:
        user_version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        table_names = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master "
                "WHERE type = 'table' AND name NOT LIKE 'sqlite_%'"
            )
        ]
        row_count = sum(
            int(conn.execute(f"SELECT COUNT(*) FROM {_quote_identifier(name)}").fetchone()[0])
            for name in table_names
        )
    return {
        "user_version": user_version,
        "table_count": len(table_names),
        "row_count": row_count,
    }


def _git(*args: str) -> str:
    try:
        return subprocess.run(
            ["git", *args], capture_output=True, text=True, timeout=5, check=False
        ).stdout.strip()
    except Exception:
        return ""


def _safe(function, default="unavailable"):
    try:
        return function()
    except Exception:
        return default


def collect_bundle(
    salt_path: Path = _DEFAULT_SALT_PATH,
    command: str = "",
    exit_code: int = 0,
    first_error: str = "",
) -> dict[str, object]:
    from synlynk._constants import VERSION

    doctor = _safe(_collect_doctor)
    failing = [
        row["id"]
        for row in doctor
        if isinstance(doctor, list) and row["status"] == "fail"
    ]
    branch = _git("rev-parse", "--abbrev-ref", "HEAD")
    bundle = {
        "schema": BUNDLE_SCHEMA_VERSION,
        "synlynk_version": VERSION,
        "python_version": platform.python_version(),
        "os": platform.system(),
        "arch": platform.machine(),
        "install_method": "pipx"
        if "pipx" in sys.prefix
        else ("venv" if sys.prefix != sys.base_prefix else "other"),
        "harnesses": _safe(_collect_harnesses),
        "env_set": {name: bool(os.environ.get(name)) for name in _env_names()},
        "doctor": doctor,
        "config_schema": _safe(_collect_config_schema),
        "policy_schema": _safe(_collect_policy_schema),
        "db_shape": _safe(_collect_db_shape),
        "worktree": {
            "dirty": bool(_git("status", "--porcelain")),
            "branch_kind": "main"
            if branch in ("main", "master")
            else ("detached" if branch == "HEAD" else "feature"),
        },
        "remote": normalize_remote(_git("config", "--get", "remote.origin.url"))
        or "none",
        "identity": salted_hash(
            f"{os.environ.get('USER', '')}@{platform.node()}", salt_path
        ),
    }
    bundle["fingerprint"] = fingerprint(failing, command, exit_code, first_error)
    return bundle


PUBLIC_NOTICE = (
    "This report will be PUBLIC and indexed. Editing or deleting it later does "
    "not remove cached copies."
)


def render_body(
    bundle: dict[str, object],
    description: str,
    withheld: list[str] | None = None,
) -> str:
    lines = [
        "## What happened",
        description or "(no description)",
        "",
        "## Bundle (generated)",
    ]
    for key in ALLOWED_FIELDS:
        if key in bundle and key != "fingerprint":
            lines.append(f"- {key}: {bundle[key]}")
    lines += ["", f"fingerprint: {bundle['fingerprint']}", ""]
    lines.append(
        "Withheld: "
        + (", ".join(withheld) if withheld else "none")
        + ". No secret values, file contents or database rows were collected."
    )
    return "\n".join(lines)
