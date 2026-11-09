"""Activates a known role as a real, dispatchable agent: registers it in the
agent_store registry and writes its first charter revision.

Idempotent — calling activate_role() for an already-registered role_slug is
a no-op. Does not provision a GitHub App identity; call
synlynk identity init --role <role> separately (Phase 1 Task 6 wires this
into the same CLI command this module's caller uses).
"""
from synlynk import agent_store


def activate_role(role: str, actor: str, actor_type: str = "human") -> str:
    """Register `role` as a dispatchable agent and write its seed charter.

    Returns the agent_id (same as `role` for activated roles — no suffix,
    unlike Vizor's ad-hoc _handle_role_create which mints a random one).
    Raises ValueError if `role` has no entry in agent_cli.SEED_CHARTERS.
    """
    from synlynk.agent_cli import SEED_CHARTERS

    existing_ids = {e["agent_id"] for e in agent_store.list_agents()}
    if role in existing_ids:
        return role

    seed = SEED_CHARTERS.get(role)
    if not seed:
        raise ValueError(f"no seed charter for role {role!r}; add one to agent_cli.SEED_CHARTERS first")

    agent_store.register_agent(role, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(
        role, seed, actor=actor, parent_revision=0, actor_type=actor_type,
    )
    return role
