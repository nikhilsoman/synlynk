import os
import sqlite3
import pytest
from synlynk.viz_views import (
    extract_infra_nodes,
    extract_product_nodes,
    extract_world_nodes,
)
from synlynk.viz import generate_architect_map_html


@pytest.fixture
def mock_db():
    conn = sqlite3.connect(":memory:")
    yield conn
    conn.close()


def test_rxcc_live_or_fixture_repo_truth(mock_db):
    rxcc_path = "/Users/nikhilsoman/dev/rxcc"
    if not os.path.isdir(rxcc_path):
        pytest.skip(f"Live rxcc workspace not found at {rxcc_path}")

    # 1. Product extraction
    p_nodes, _ = extract_product_nodes(mock_db, rxcc_path)
    p_labels = [n["label"] for n in p_nodes]
    p_kinds = {n["label"]: n.get("kind") for n in p_nodes}

    # Zero synlynk journeys
    assert "Zero-Friction Onboarding" not in p_labels, "Synlynk onboarding journey leaked into rxcc!"
    assert "Interactive Home Harness Pairing" not in p_labels

    # Discovered rxcc apps
    assert any("web" in l.lower() for l in p_labels), "Failed to discover rxcc apps/web"
    assert any("api" in l.lower() for l in p_labels), "Failed to discover rxcc apps/api"

    # Discovered brainstorm HTML mockups
    mock_screens = [n for n in p_nodes if n.get("kind") == "screen" and n.get("attrs_json") and "prototype" in n.get("attrs_json", "")]
    assert len(mock_screens) > 0, "Failed to discover any .superpowers/brainstorm/ HTML prototypes in rxcc!"

    # 2. Infra extraction
    i_nodes, _ = extract_infra_nodes(mock_db, rxcc_path)
    i_labels = [n["label"] for n in i_nodes]
    i_text = " ".join(i_labels + [n.get("source_path", "") for n in i_nodes])

    # Zero synlynk daemons
    assert "Vizor Server (:8721)" not in i_labels, "Synlynk Vizor daemon leaked into rxcc!"
    assert "SSE Relay Broker (:27472)" not in i_labels, "Synlynk SSE Relay leaked into rxcc!"
    assert "StateDB SQLite Ledger" not in i_labels, "Synlynk StateDB leaked into rxcc!"
    assert "Anthropic Claude API" not in i_labels, "Synlynk LLM egress leaked into rxcc!"
    assert "synlynk/viz.py" not in i_text
    assert "synlynk/dispatch.py" not in i_text

    # Discovered rxcc infrastructure (Prisma / Dockerfile)
    assert any("prisma" in l.lower() or "container" in l.lower() or "docker" in l.lower() or "host-local" in l.lower() for l in i_labels)

    # 3. World extraction
    w_nodes, _ = extract_world_nodes(mock_db, rxcc_path)
    w_text = " ".join((n.get("source_path") or "") for n in w_nodes)
    assert "synlynk/gh.py" not in w_text
    assert "synlynk/dispatch.py" not in w_text
    assert "synlynk/media.py" not in w_text

    # 4. Architect Map HUD
    data = {
        "workspace": {"name": "rxcc", "repos": [{"path": rxcc_path, "name": "rxcc"}]},
        "workspace_map": {"edges": [], "edge_types": {}},
    }
    hud_html = generate_architect_map_html(data, port=8721)
    assert "am-empty-hud" in hud_html or "AWAITING AST INDEXING" in hud_html
    assert "synlynk scan --deep" in hud_html
