"""Run `gh` as a role-scoped GitHub App (#1436 Hole B)."""

from __future__ import annotations

import os
import subprocess
import sys

from synlynk.charter_schema import KNOWN_ROLES
from synlynk.dispatch import (
    _gh_write_allow_host_auth,
    _isolated_gh_config_dir,
    _resolve_dispatch_gh_token,
)


def cmd_gh(role: str, gh_args: list) -> int:
    """Execute `gh` with the role App token. Fail closed if none is cached."""
    if not role:
        print("  usage: synlynk gh --role <role> -- <gh-args>", file=sys.stderr)
        raise SystemExit(1)
    if role not in KNOWN_ROLES:
        print(
            f"  unknown role {role!r}. Known roles: {', '.join(KNOWN_ROLES)}",
            file=sys.stderr,
        )
        raise SystemExit(1)

    args = list(gh_args or [])
    if args and args[0] == "--":
        args = args[1:]
    if not args:
        print("  usage: synlynk gh --role <role> -- <gh-args>", file=sys.stderr)
        raise SystemExit(1)

    env = os.environ.copy()
    token = _resolve_dispatch_gh_token(role)
    if token:
        env.pop("GH_TOKEN", None)
        env.pop("GITHUB_TOKEN", None)
        env["GH_TOKEN"] = token
        env["GITHUB_TOKEN"] = token
        env["GH_CONFIG_DIR"] = _isolated_gh_config_dir()
    elif _gh_write_allow_host_auth():
        print(
            f"  ⚠ synlynk gh: no App token for role {role!r}; "
            "SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH is set — using host gh keyring.",
            file=sys.stderr,
        )
    else:
        print(
            f"  synlynk gh refused: no role-scoped GitHub App token for {role!r}. "
            f"Provision with: synlynk identity init --role {role} "
            "(and ensure the daemon has refreshed the token cache). "
            "Host gh (nikhilsoman) is not used unless SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH=1.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    try:
        result = subprocess.run(["gh"] + args, env=env)
    except FileNotFoundError:
        print("  gh binary not found on PATH", file=sys.stderr)
        raise SystemExit(1)
    return result.returncode
