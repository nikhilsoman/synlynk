"""Tests for Vizor Product View and universal product extraction."""

import json
import os
import sqlite3
import tempfile
from synlynk.viz import generate_product_html
from synlynk.viz_views import extract_product_nodes, build_workspace_views_snapshot


def test_extract_product_nodes_fallback_and_discovered():
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = sqlite3.connect(":memory:")
        # Test fresh repo with no docs/journeys directory
        nodes, edges = extract_product_nodes(conn, tmpdir)
        assert len(nodes) > 0, "extract_product_nodes must never return empty even on fresh repos"
        
        # Check node kinds
        kinds = {n["kind"] for n in nodes}
        assert "journey" in kinds or "screen" in kinds or "cli_command" in kinds


def test_generate_product_html_rendering():
    data = {
        "workspace": {"name": "test-repo", "path": "/test/path"},
        "product": {
            "nodes": [
                {
                    "id": "product:test-repo:journey:onboarding",
                    "kind": "journey",
                    "label": "Zero-Friction Onboarding",
                    "attrs_json": json.dumps({"description": "First time user setup", "steps": ["init", "scan", "launch"]})
                }
            ],
            "edges": []
        }
    }
    html_out = generate_product_html(data, port=8721)
    assert "<!DOCTYPE html>" in html_out
    assert "Product View" in html_out or "User Journeys" in html_out
    assert "Zero-Friction Onboarding" in html_out
    assert "Claude" in html_out
    assert "Codex" in html_out
    assert "Agy" in html_out
    assert "Grok" in html_out
    # Check BS-6 navigation links
    assert "tube.html" in html_out
    assert "logical.html" in html_out
    assert "infra.html" in html_out
    assert "world.html" in html_out
