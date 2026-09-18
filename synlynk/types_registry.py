"""Small, dependency-free product type registry for W5's Wave 1 slice."""
from __future__ import annotations

import json
from pathlib import Path

from synlynk.product_store import ensure_product_dirs, types_dir, types_yaml_path


class TypeExists(RuntimeError): pass
class UnknownKind(ValueError): pass

PACK_TYPES = {
    "pm": ("pm", "PM"), "tpm": ("tpm", "TPM"), "architect": ("architect", "Architect"),
    "qa": ("qa", "QA"), "dev": ("dev", "Dev"), "designer": ("designer", "Designer"),
    "marketing": ("marketing", "Marketing"), "synlynk-bot": ("synlynk-bot", "synlynk-bot"),
}


def _load(path: Path) -> dict:
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    return data.get("types", {}) if isinstance(data, dict) else {}


def load_types(slug: str) -> dict:
    return _load(types_yaml_path(slug))


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
    if pack_id != "software-product":
        raise ValueError(f"unknown pack: {pack_id}")
    ensure_product_dirs(slug)
    types = load_types(slug)
    for type_id, (kind, label) in PACK_TYPES.items():
        types.setdefault(type_id, {"kind": kind, "canonical": True, "label": label})
        _charter(slug, type_id, kind)
    _save(slug, types)
    return types


def type_create(slug: str, type_id: str, kind: str) -> dict:
    if kind not in PACK_TYPES:
        try:
            from synlynk.charter_schema import KNOWN_ROLES
            approved = set(KNOWN_ROLES) | {"infra"}
        except ImportError:
            approved = set(PACK_TYPES)
        if kind not in approved:
            raise UnknownKind(kind)
    types = load_types(slug)
    if type_id in types:
        raise TypeExists(type_id)
    types[type_id] = {"kind": kind, "canonical": False, "skills_add": [], "skills_remove": []}
    _save(slug, types)
    _charter(slug, type_id, kind)
    return types[type_id]
