"""Shared UX core: typed reads, capability-gated writes, and the event stream
that back both the TUI (synlynk/tui.py) and Vizor (synlynk/viz.py), and are the
public BYOUX library contract documented in docs/api/uxcore.md.

`Role` here is the RBAC role for uxcore actors -- deliberately distinct from
synlynk.identity_roles (GitHub App provisioning roles, .synlynk/roles.yaml)
and synlynk.capability_roles (capability-classifier mappings). See
docs/superpowers/plans/2026-07-24-agent-github-identity-design.md's "Naming
Collision" section for the project's existing precedent on this. Always
import as `uxcore.Role`, never as a bare unqualified `Role`.
"""
import dataclasses
import enum
import json
import os
import time
from typing import Iterator, Optional


class Role(enum.Enum):
    OWNER = "owner"
    MEMBER = "member"
    VIEWER = "viewer"


@dataclasses.dataclass(frozen=True)
class Actor:
    id: str
    role: Role


class LocalActor(Actor):
    """The only actor that exists in 1.0: the local user running the CLI/TUI/Vizor."""

    def __init__(self):
        super().__init__(id="local", role=Role.OWNER)


DEFAULT_ACTOR = LocalActor()


class UxCoreError(Exception):
    """Raised when a uxcore call fails outright (bad args, file I/O error).

    Surfaces (TUI/Vizor/notifiers) catch this and display it in their own
    idiom. It is never allowed to reach a user as a bare traceback.
    """


@dataclasses.dataclass(frozen=True)
class Event:
    actor_id: str
    action: str
    params: dict
    timestamp: str
    result: dict


@dataclasses.dataclass(frozen=True)
class WriteResult:
    ok: bool
    message: str
    job_id: Optional[str] = None
