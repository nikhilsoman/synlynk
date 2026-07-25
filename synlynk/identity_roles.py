"""Project-declared identity roles for GitHub App provisioning (.synlynk/roles.yaml).

Distinct from _ROLE_PERMISSION_DEFAULTS (agent permission scopes) and the
stories.role taxonomy column — see docs/superpowers/plans/2026-07-24-agent-github-identity-design.md
"Naming Collision" section.
"""

import os

DEFAULT_ROLES = ("dev", "qa")

ROLES_YAML_PATH = os.path.join(".synlynk", "roles.yaml")


def load_declared_roles() -> list:
    """Read .synlynk/roles.yaml's flat `roles:` list; fall back to DEFAULT_ROLES."""
    if not os.path.exists(ROLES_YAML_PATH):
        return list(DEFAULT_ROLES)
    try:
        with open(ROLES_YAML_PATH) as fh:
            lines = fh.readlines()
    except OSError:
        return list(DEFAULT_ROLES)
    roles = []
    in_roles_block = False
    for line in lines:
        stripped = line.strip()
        if stripped == "roles:":
            in_roles_block = True
            continue
        if in_roles_block:
            if stripped.startswith("- "):
                roles.append(stripped[2:].strip())
            elif stripped and not stripped.startswith("#"):
                break
    return roles if roles else list(DEFAULT_ROLES)


def write_declared_roles(roles: list) -> None:
    """Write .synlynk/roles.yaml as a flat `roles:` list. Overwrites any existing file."""
    os.makedirs(".synlynk", exist_ok=True)
    lines = ["roles:\n"] + [f"  - {role}\n" for role in roles]
    with open(ROLES_YAML_PATH, "w") as fh:
        fh.writelines(lines)
