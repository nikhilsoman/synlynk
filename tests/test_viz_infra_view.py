"""Tests for Vizor Infra View and dual-zone infrastructure extraction."""

import json
import sqlite3
import tempfile
from synlynk.viz import generate_infra_html
from synlynk.viz_views import extract_infra_nodes


def test_extract_infra_nodes_dual_zone():
    with tempfile.TemporaryDirectory() as tmpdir:
        conn = sqlite3.connect(":memory:")
        nodes, edges = extract_infra_nodes(conn, tmpdir)
        assert len(nodes) > 0, "extract_infra_nodes must extract infra nodes"
        
        # Check that we have both host-local and outbound egress nodes
        zones = {n.get("attrs", {}).get("zone") if isinstance(n.get("attrs"), dict) else json.loads(n.get("attrs_json", "{}")).get("zone") for n in nodes}
        assert "host_local" in zones
        assert "outbound_egress" in zones


def test_generate_infra_html_rendering():
    data = {
        "workspace": {"name": "test-repo", "path": "/test/path"},
        "infra": {
            "nodes": [
                {
                    "id": "infra:test-repo:service:daemon",
                    "kind": "service",
                    "label": "Vizor Server (:8721)",
                    "attrs_json": json.dumps({"zone": "host_local", "port": 8721, "type": "daemon"})
                },
                {
                    "id": "infra:test-repo:egress:anthropic",
                    "kind": "egress",
                    "label": "Anthropic API (Claude)",
                    "attrs_json": json.dumps({"zone": "outbound_egress", "endpoint": "api.anthropic.com:443", "category": "llm"})
                }
            ],
            "edges": []
        }
    }
    html_out = generate_infra_html(data, port=8721)
    assert "<!DOCTYPE html>" in html_out
    assert "Infra" in html_out or "Infrastructure" in html_out
    assert "Host-Local" in html_out or "host-local" in html_out.lower()
    assert "Outbound" in html_out or "Egress" in html_out
    assert "100% Host-Local" in html_out
    assert "Zero Cloud Telemetry" in html_out
    # Check BS-6 navigation links
    assert "tube.html" in html_out
    assert "logical.html" in html_out
    assert "product.html" in html_out
    assert "world.html" in html_out
