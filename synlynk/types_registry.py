"""Dependency-free product type registry and canonical industry packs."""
from __future__ import annotations

import json
from pathlib import Path

from synlynk.product_store import ensure_product_dirs, types_dir, types_yaml_path


class TypeExists(RuntimeError): pass
class UnknownKind(ValueError): pass

PACK_DIR = Path(__file__).with_name("packs")
PACK_IDS = ("software-product", "studio", "agency")


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
    approved_kinds = {
        pack_kind
        for pack_id in PACK_IDS
        for pack_kind, _label in _pack_types(pack_id).values()
    }
    if kind not in approved_kinds:
        raise UnknownKind(kind)
    types = load_types(slug)
    if type_id in types:
        raise TypeExists(type_id)
    types[type_id] = {"kind": kind, "canonical": False, "skills_add": [], "skills_remove": []}
    _save(slug, types)
    _charter(slug, type_id, kind)
    return types[type_id]
