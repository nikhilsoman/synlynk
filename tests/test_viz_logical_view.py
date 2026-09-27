import pytest
from synlynk.viz import generate_logical_html

def test_logical_view_renders_hld_lld_and_sequence_player():
    data = {
        "workspace": {"name": "synlynk", "path": "."},
        "workspace_views": {
            "logical": {
                "nodes": [
                    {"id": "synlynk.viz", "label": "Vizor Server", "kind": "service", "layer": "presentation"},
                    {"id": "synlynk.db", "label": "State Database", "kind": "database", "layer": "persistence"},
                ],
                "edges": [
                    {"from_id": "synlynk.viz", "to_id": "synlynk.db", "relation": "reads"}
                ]
            }
        },
        "repos": [{"name": "synlynk", "path": ".", "primary": True}],
    }
    html = generate_logical_html(data, port=27472)
    # Check for the 3 tabs: HLD Architecture, LLD Component Model, and Sequence Flows
    assert "Layered HLD Architecture" in html or "HLD Architecture" in html
    assert "LLD Component Model" in html or "Component Model" in html
    assert "Interactive Sequence Player" in html or "Sequence Flows" in html
    # Check for key sequence diagrams
    assert "Unattended Autonomous Milestone Loop" in html or "Autonomous Milestone Loop" in html
    assert "AST Drift &amp; Knowledge Graph Lifecycle" in html or "AST Drift & Knowledge Graph Lifecycle" in html or "AST Drift" in html
    assert "Universal GOVERNS" in html or "GOVERNS Lifecycle" in html
    # Check for layer tiers in HLD
    assert "Presentation" in html or "API Surface" in html
    assert "Persistence" in html or "State Ledger" in html
