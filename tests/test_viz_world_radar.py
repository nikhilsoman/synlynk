"""Tests for Vizor World View 3-ring concentric ecosystem radar."""

import json
import sqlite3
import tempfile
from synlynk.viz import generate_world_html
from synlynk.viz_views import extract_world_nodes


def test_extract_world_nodes_3_rings():
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = sqlite3.connect(":memory:")
        nodes, edges = extract_world_nodes(conn, tmpdir)
        assert len(nodes) > 0, "extract_world_nodes must never be empty"

        rings = {
            n.get("attrs", {}).get("ring")
            if isinstance(n.get("attrs"), dict)
            else json.loads(n.get("attrs_json", "{}")).get("ring")
            for n in nodes
        }
        # Must have Ring 0 (Core), Ring 1 (Egress), Ring 2 (Peripherals), Ring 3 (Opportunity Horizon)
        assert 0 in rings, "Ring 0 (Workspace Core) must exist"
        assert 1 in rings, "Ring 1 (Critical Egress) must exist"
        assert 2 in rings, "Ring 2 (Ecosystem Peripherals) must exist"
        assert 3 in rings, "Ring 3 (Opportunity Horizon) must exist"


def test_generate_world_html_radar_rendering():
    data = {
        "workspace": {"name": "test-repo", "path": "/test/path"},
        "world": {
            "nodes": [
                {
                    "id": "world:test-repo:workspace:core",
                    "kind": "workspace",
                    "label": "test-repo (Workspace Core)",
                    "attrs_json": json.dumps({"ring": 0, "tier": "core"})
                },
                {
                    "id": "world:test-repo:llm:gemini",
                    "kind": "llm",
                    "label": "Google Gemini API",
                    "attrs_json": json.dumps({"ring": 1, "tier": "egress", "category": "llm"})
                }
            ],
            "edges": []
        }
    }
    html_out = generate_world_html(data, port=8721)
    assert "<!DOCTYPE html>" in html_out
    assert "Ecosystem Radar" in html_out or "World View" in html_out
    assert "svg" in html_out.lower()
    assert "radar" in html_out.lower()
    assert "Ring 0" in html_out or "Workspace Core" in html_out
    assert "Ring 1" in html_out or "Primary Egress" in html_out
    assert "Ring 2" in html_out or "Ecosystem" in html_out
    assert "Ring 3" in html_out or "Opportunity" in html_out
    # Check BS-6 navigation links
    assert "tube.html" in html_out
    assert "logical.html" in html_out
    assert "product.html" in html_out
    assert "infra.html" in html_out
