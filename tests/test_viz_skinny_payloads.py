"""View-scoped Vizor embeds must not dump the logical graph (gh:#2671)."""
import json

from synlynk.viz import (
    generate_architect_map_html,
    generate_efficiency_html,
    generate_effort_html,
    generate_gantt_html,
    generate_logical_html,
)

FAT_SENTINEL = "FAT_LOGICAL_SENTINEL_2671"
MAX_HTML_BYTES = 750_000


def _fat_data():
    nodes = []
    edges = []
    for i in range(3000):
        nodes.append(
            {
                "id": f"n{i}",
                "label": f"Node {i}",
                "kind": "function",
                "attrs_json": json.dumps(
                    {"community": i % 12, "path": "synlynk/" + "x" * 80, "mark": FAT_SENTINEL}
                ),
                "head_sha": "a" * 40,
                "scanned_at": "2026-10-30T00:00:00Z",
                "provenance": "extracted",
            }
        )
    for i in range(6000):
        edges.append(
            {
                "id": f"e{i}",
                "from_id": f"n{i % 3000}",
                "to_id": f"n{(i + 1) % 3000}",
                "attrs_json": json.dumps({"mark": FAT_SENTINEL, "weight": i}),
                "head_sha": "a" * 40,
            }
        )
    return {
        "workspace": {"name": "synlynk", "updated_at": "2026-10-31T00:00:00Z", "repos": []},
        "workspace_views": {"logical": {"nodes": nodes, "edges": edges, "stale": False}},
        "releases": [
            {
                "id": "v0.26.6",
                "name": "Heartbeat",
                "status": "active",
                "stages": [
                    {
                        "key": "execute",
                        "status": "active",
                        "start_frac": 0.1,
                        "width_frac": 0.2,
                        "agents": ["grok"],
                        "tasks": [],
                    }
                ],
            }
        ],
        "dreams": [],
        "goals": [{"id": "goal-e3840370", "outcome": "Vizor HUD", "status": "active"}],
        "spec_verifications": [],
        "product_id": "synlynk",
        "notes": {},
        "costs": {"total_usd": 1.0, "total_usd_estimated": 0.0, "by_agent": {}, "by_stage": {}},
        "agents": {"grok": {"tasks_done": 1, "tasks_active": 0, "total_usd": 1.0, "success_rate": 1.0, "alert_count": 0}},
        "telemetry": {"recent": [], "sentinel_alerts": []},
        "ecosystem": {},
        "file_tree": {"name": ".", "dirs": {}, "files": []},
        "workspace_map": {"edges": [], "edge_types": {}},
    }


def test_fat_logical_graph_stays_out_of_timeline_views():
    data = _fat_data()
    pages = {
        "gantt": generate_gantt_html(data, 33333),
        "effort": generate_effort_html(data, 33333),
        "efficiency": generate_efficiency_html(data, 33333),
        "tube": generate_architect_map_html(data, 33333),
        "logical": generate_logical_html(data, 33333),
    }
    for name, html in pages.items():
        assert FAT_SENTINEL not in html, name
        assert "workspace_views" not in html, name
        assert len(html.encode("utf-8")) < MAX_HTML_BYTES, (name, len(html))


def test_gantt_embed_keeps_releases_and_goals():
    html = generate_gantt_html(_fat_data(), 33333)
    assert "Heartbeat" in html
    assert "goal-e3840370" in html
    assert "window.VIZOR_DATA =" in html


def test_logical_first_paint_is_a_projection():
    html = generate_logical_html(_fat_data(), 33333)
    assert "window.LOGICAL_NODES =" in html
    assert html.count('"id": "n') <= 16
    assert "Node 0" in html
