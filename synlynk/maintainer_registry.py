"""Generic, role-aware action-registration object for any role's autonomous
wake cycle (spec §5.2, docs/superpowers/specs/2026-11-24-maintainer-full-autonomy-design.md).

Not Maintainer-specific despite the module name (kept for import-path
continuity with the rest of this plan): any role registers an action under
its own role_slug. The stable action_id is f"{role_slug}:{name}" - this is
the only id the Role Operations Panel (synlynk/viz/role_ops_panel.py,
Task 13) is allowed to key off, and the persistence key under
.synlynk/config.json's "<role_slug>_autonomy" block.
"""
import json
import os
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional

_KNOWN_FIELD_TYPES = {"str", "bool", "list[str]", "int"}


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str
    default: Any
    label: str

    def __post_init__(self):
        if self.type not in _KNOWN_FIELD_TYPES:
            raise ValueError(
                f"unknown FieldSpec type {self.type!r} for field {self.name!r}; "
                f"must be one of {sorted(_KNOWN_FIELD_TYPES)}"
            )


@dataclass
class RegisteredAction:
    role_slug: str
    name: str
    default_config: Dict[str, Any] = field(default_factory=dict)
    filter_schema: List[FieldSpec] = field(default_factory=list)
    run_fn: Optional[Callable[..., Dict[str, Any]]] = None

    @property
    def action_id(self) -> str:
        return f"{self.role_slug}:{self.name}"


_REGISTRY: Dict[str, RegisteredAction] = {}


def register_action(
    role_slug: str,
    name: str,
    default_config: Dict[str, Any],
    filter_schema: List[FieldSpec],
    run_fn: Callable[..., Dict[str, Any]],
) -> None:
    """Register (or re-register, idempotently) an autonomous action.

    Raises ValueError (via FieldSpec.__post_init__) at registration time if
    filter_schema contains an unknown field type - not at render time.
    """
    action = RegisteredAction(
        role_slug=role_slug,
        name=name,
        default_config=dict(default_config),
        filter_schema=list(filter_schema),
        run_fn=run_fn,
    )
    _REGISTRY[action.action_id] = action


def registered_actions(role_slug: str = None) -> Dict[str, RegisteredAction]:
    """All currently registered actions, keyed by action_id.

    Pass role_slug to filter to one role's actions (what the Role Operations
    Panel's per-role card needs); omit it for cross-role views.
    """
    if role_slug is None:
        return dict(_REGISTRY)
    return {k: v for k, v in _REGISTRY.items() if v.role_slug == role_slug}


def clear_registry() -> None:
    """Clear all registered actions (test isolation)."""
    _REGISTRY.clear()


def get_action_config(action_id: str, repo_root: str = ".") -> Dict[str, Any]:
    """Registered action's default_config, overridden by
    .synlynk/config.json's "<role_slug>_autonomy" block for this action.

    Raises ValueError if the config file supplies a key not present in the
    action's own default_config (unknown-key rejection, DECIDE panel
    defect #1) - a typo in config should fail loudly, not silently no-op.
    """
    action = _REGISTRY.get(action_id)
    if action is None:
        raise KeyError(f"no registered action with id {action_id!r}")

    config = dict(action.default_config)
    path = os.path.join(repo_root, ".synlynk", "config.json")
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            section = data.get(f"{action.role_slug}_autonomy") or {}
            overrides = section.get(action.name) or {}
        except (json.JSONDecodeError, OSError):
            overrides = {}
        allowed_keys = set(config) | {spec.name for spec in action.filter_schema}
        unknown = set(overrides) - allowed_keys
        if unknown:
            raise ValueError(f"unknown config key(s) {sorted(unknown)} for action {action_id!r}")
        config.update(overrides)
    return config


def build_maintainer_ops_data(role_slug: str, repo_root: str = ".") -> Dict[str, Any]:
    """Assemble the Role Operations Panel's input dict for one role from
    this registry's registered actions and Task 6's persisted proposals.

    Caller still has to attach the result under data["maintainer_ops"] (for
    generate_overview_html) or agent["ops_data"] (for generate_roles_html) --
    see Task 13's "Known residual item" note above for where that wiring
    still needs to happen in synlynk/viz/data.py.
    """
    from synlynk.maintainer import load_maintainer_proposals
    from synlynk.maintainer_taxonomy import load_taxonomy

    proposals_by_action: Dict[str, List[Dict[str, Any]]] = {}
    for proposal in load_maintainer_proposals(repo_root=repo_root):
        proposals_by_action.setdefault(proposal.get("action", ""), []).append(proposal)

    actions = []
    for action in registered_actions(role_slug=role_slug).values():
        config = get_action_config(action.action_id, repo_root=repo_root)
        actions.append({
            "name": action.name,
            "enabled": bool(config.get("enabled", True)),
            "mode": config.get("mode", "dry_run"),
            "last_run": None,
            "config": config,
            "filter_schema": [
                {"name": f.name, "type": f.type, "default": f.default, "label": f.label}
                for f in action.filter_schema
            ],
            "pending_proposals": proposals_by_action.get(action.name, []),
        })

    taxonomy = load_taxonomy(repo_root=repo_root)
    return {
        "actions": actions,
        "taxonomy_status": {
            "schema_valid": taxonomy["schema_valid"],
            "validation_error": taxonomy["validation_error"],
        },
    }

