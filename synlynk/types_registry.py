"""Dependency-free product type registry and canonical industry packs."""
from __future__ import annotations

import json
from pathlib import Path

from synlynk.product_store import ensure_product_dirs, types_dir, types_yaml_path


class TypeExists(RuntimeError): pass
class UnknownKind(ValueError): pass

PACK_DIR = Path(__file__).with_name("packs")
PACK_IDS = ("software-product", "studio", "agency")

# Kind skills are product-wide review/working laws. A type stores only its
# delta, so changing a baseline affects every type with that kind.
KIND_BASELINE_SKILLS: dict[str, tuple[str, ...]] = {
    "pm": ("roadmap-authority",),
    "tpm": ("task-planning",),
    "architect": ("architecture-review",),
    "qa": ("non-author-review", "instruction-receipts", "qa-gate"),
    "dev": ("implementation",),
    "designer": ("design-review",),
    "marketing": ("marketing-comms",),
    "synlynk-bot": ("automation-receipts",),
    "infra": ("infrastructure-safety",),
    "edit": ("editing",),
    "color": ("color-review",),
    "script": ("script-review",),
    "sound": ("sound-review",),
    "account": ("account-management",),
    "creative": ("creative-review",),
    "media": ("media-planning",),
    "research": ("research-synthesis",),
}


def _load_pack(pack_id: str) -> dict:
    if pack_id not in PACK_IDS:
        raise ValueError(f"unknown pack: {pack_id}")
    try:
        data = json.loads((PACK_DIR / f"{pack_id}.yaml").read_text())
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"invalid pack: {pack_id}") from exc
    if not isinstance(data, dict) or data.get("id") != pack_id:
        raise ValueError(f"invalid pack: {pack_id}")
    return data


def _pack_types(pack_id: str) -> dict[str, tuple[str, str]]:
    return {
        type_id: (entry["kind"], entry["label"])
        for type_id, entry in _load_pack(pack_id).get("types", {}).items()
    }


# Kept as a public compatibility constant for Wave 1 callers.
PACK_TYPES = _pack_types("software-product")


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("types", {}) if isinstance(data, dict) else {}


def load_types(slug: str) -> dict:
    return _load(types_yaml_path(slug))


def resolve_type(slug: str, type_id: str) -> dict:
    """Resolve a product type or fail closed with a useful error."""
    entry = load_types(slug).get(type_id)
    if not isinstance(entry, dict) or not isinstance(entry.get("kind"), str):
        raise ValueError(f"unknown product type {type_id!r} for {slug!r}")
    return entry


def effective_skills(slug: str, type_id: str) -> list[str]:
    """Return kind baseline skills plus the type's add/remove delta."""
    entry = resolve_type(slug, type_id)
    baseline = list(KIND_BASELINE_SKILLS.get(entry["kind"], ()))
    removed = {skill for skill in entry.get("skills_remove", []) if isinstance(skill, str)}
    added = [skill for skill in entry.get("skills_add", []) if isinstance(skill, str)]
    result = [skill for skill in baseline if skill not in removed]
    for skill in added:
        if skill not in result:
            result.append(skill)
    return result


def _save(slug: str, types: dict) -> None:
    path = types_yaml_path(slug)
    path.parent.mkdir(parents=True, exist_ok=True)
    # JSON is valid YAML 1.2 and keeps this package dependency-free.
    path.write_text(json.dumps({"schema_version": 1, "types": types}, indent=2) + "\n")


def _charter(slug: str, type_id: str, kind: str) -> None:
    target = types_dir(slug) / type_id
    target.mkdir(parents=True, exist_ok=True)
    charter = target / "charter.md"
    if not charter.exists():
        charter.write_text(f"# {type_id}\n\nProduct type `{type_id}` inherits the `{kind}` kind.\n")
    (target / "memory.md").touch()


def seed_canonical_types(slug: str, pack_id: str = "software-product") -> dict:
    pack_types = _pack_types(pack_id)
    ensure_product_dirs(slug)
    types = load_types(slug)
    for type_id, (kind, label) in pack_types.items():
        types.setdefault(type_id, {"kind": kind, "canonical": True, "label": label})
        _charter(slug, type_id, kind)
    _save(slug, types)
    return types


def type_create(slug: str, type_id: str, kind: str) -> dict:
    approved_kinds = {"connector"}
    approved_kinds.update(
        pack_kind
        for pack_id in PACK_IDS
        for pack_kind, _label in _pack_types(pack_id).values()
    )
    if kind not in approved_kinds:
        raise UnknownKind(kind)
    types = load_types(slug)
    if type_id in types or any(type_id in _pack_types(pack_id) for pack_id in PACK_IDS):
        raise TypeExists(type_id)
    types[type_id] = {"kind": kind, "canonical": False, "skills_add": [], "skills_remove": []}
    _save(slug, types)
    _charter(slug, type_id, kind)
    return types[type_id]
