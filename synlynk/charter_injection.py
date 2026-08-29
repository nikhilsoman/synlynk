"""Resolve and render the charter for the current human authority role."""

from synlynk import agent_store
from synlynk.policy import get_human_authority_role


class CharterInjectionError(Exception):
    """Raised when the authority role has no usable registered charter."""


def _find_agent_for_role(role: str, entries):
    for entry in entries:
        role_slug = next(
            (alias["value"] for alias in entry["aliases"] if alias["kind"] == "role_slug"),
            None,
        )
        if role_slug == role and not entry.get("disabled"):
            return entry
    return None


def render_charter_section(repo_path: str) -> str:
    """Return the resolved authority role's charter as a Markdown section."""
    role = get_human_authority_role(repo_path=repo_path)
    entries = agent_store.list_agents()
    if not entries:
        return ""

    entry = _find_agent_for_role(role, entries)
    if entry is None:
        raise CharterInjectionError(
            f"human_authority_role is {role!r} but no registered agent has "
            f"role_slug {role!r} (see agent_store.list_agents())"
        )

    content, revision = agent_store.read_charter(entry["agent_id"])
    if not content.strip():
        raise CharterInjectionError(
            f"role {role!r} (agent_id {entry['agent_id']!r}) has no charter content "
            f"(revision {revision})"
        )
    return f"## Role Charter ({role}, revision {revision})\n\n{content.strip()}\n\n---\n\n"
