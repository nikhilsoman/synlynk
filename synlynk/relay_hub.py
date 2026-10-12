"""Opt-in NATS-backed hub bridge for the local relay (synlynk/relay.py).

Credential model deviation from the design spec (docs/superpowers/specs/
2026-10-12-personal-hosted-relay-design.md): per-device bearer tokens scoped
via NATS `authorization { users: [...] }` permission blocks, not nkey+JWT.
Real nkey/JWT minting needs the `nsc` toolchain and is deferred until a
multi-tenant managed hub actually requires it. See plan's "Decision Flagged
for Review" section for full rationale.

`nats-py` is an optional dependency (pyproject.toml `[hub]` extra) and is
imported lazily inside functions that need it, so importing this module
(or synlynk's core CLI) never requires it to be installed.
"""

from __future__ import annotations


def _import_nats():
    try:
        import nats  # noqa: F401
        return nats
    except ImportError as exc:
        raise RuntimeError(
            "Hub features require the optional 'hub' extra: "
            "pip install 'synlynk[hub]'"
        ) from exc
