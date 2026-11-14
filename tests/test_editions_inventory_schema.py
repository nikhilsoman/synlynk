"""Schema and content tests for docs/strategy/editions-inventory.json."""

import json
from pathlib import Path

from synlynk.editions import CAPABILITIES, EDITION_ORDER


def test_editions_inventory_json_schema():
    """Verify that editions-inventory.json conforms to the expected capability schema."""
    inv_path = Path("docs/strategy/editions-inventory.json")
    assert inv_path.is_file(), "docs/strategy/editions-inventory.json must exist"

    with open(inv_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert isinstance(data, list)
    assert len(data) >= len(CAPABILITIES)

    known_names = set()
    for item in data:
        assert isinstance(item, dict)
        assert "name" in item and isinstance(item["name"], str)
        name = item["name"]
        assert name not in known_names, f"Duplicate capability name: {name}"
        known_names.add(name)

        assert "category" in item
        assert item["category"] in ("core", "opt_in", "hosted")

        if item["category"] == "hosted":
            assert item.get("hosted_key") is not None
            assert isinstance(item["hosted_key"], str) and len(item["hosted_key"]) > 0
            if item.get("min_edition") is not None:
                assert item["min_edition"] in EDITION_ORDER
        else:
            assert item.get("min_edition") is None
            assert item.get("hosted_key") is None

        assert "note" in item and isinstance(item["note"], str)

    # All baseline capabilities in CAPABILITIES must exist in inventory
    for cap_name in CAPABILITIES:
        assert cap_name in known_names, f"Baseline capability '{cap_name}' missing from inventory JSON"


def test_editions_inventory_md_exists():
    """Verify that human-readable docs/strategy/editions-inventory.md exists."""
    md_path = Path("docs/strategy/editions-inventory.md")
    assert md_path.is_file(), "docs/strategy/editions-inventory.md must exist"
    content = md_path.read_text(encoding="utf-8")
    assert "# Synlynk Full Module & Capability Inventory" in content
    assert "Core Capabilities" in content
    assert "Opt-in Capabilities" in content
    assert "Hosted Capabilities" in content
