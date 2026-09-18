import json
import pytest

from synlynk.types_registry import TypeExists, UnknownKind, load_types, seed_canonical_types, type_create


def setup_product(tmp_path, monkeypatch, slug="vdowrx"):
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"identity_slug": slug}))


def test_seed_is_idempotent_and_writes_charter(tmp_path, monkeypatch):
    setup_product(tmp_path, monkeypatch, "synlynk")
    seed_canonical_types("synlynk")
    seed_canonical_types("synlynk")
    assert load_types("synlynk")["qa"]["canonical"] is True
    assert (tmp_path / "home/.synlynk/workspaces/synlynk/types/qa/charter.md").is_file()


def test_type_create_and_validation(tmp_path, monkeypatch):
    setup_product(tmp_path, monkeypatch)
    seed_canonical_types("vdowrx")
    type_create("vdowrx", "frontend-qa", "qa")
    assert load_types("vdowrx")["frontend-qa"]["canonical"] is False
    with pytest.raises(TypeExists):
        type_create("vdowrx", "qa", "qa")
    with pytest.raises(UnknownKind):
        type_create("vdowrx", "colorist", "not-a-kind")


def test_studio_seed_and_pack_kind_creation(tmp_path, monkeypatch):
    setup_product(tmp_path, monkeypatch, "hitchcock")
    seed_canonical_types("hitchcock", "studio")
    types = load_types("hitchcock")
    assert types["director"] == {"kind": "pm", "canonical": True, "label": "Director"}
    type_create("hitchcock", "colorist", "edit")
    assert load_types("hitchcock")["colorist"]["kind"] == "edit"


def test_agency_seed_and_unknown_pack(tmp_path, monkeypatch):
    setup_product(tmp_path, monkeypatch, "agency")
    seed_canonical_types("agency", "agency")
    assert load_types("agency")["partner"]["label"] == "Partner"
    with pytest.raises(ValueError, match="unknown pack"):
        seed_canonical_types("agency", "unknown")
