from synlynk.viz.gantt import generate_gantt_html
from synlynk.viz.gantt_model import drill_grid, visible_row_window


def _release():
    return {
        "id": "v0.26.7",
        "target_date": "2026-11-15",
        "stages": [
            {"key": "plan", "status": "done", "tasks": []},
            {"key": "execute", "status": "active", "tasks": [
                {"name": "links", "status": "active"},
                {"name": "gantt", "status": "blocked"},
                {"name": "notes", "status": "queued"},
            ]},
            {"key": "release", "status": "queued", "tasks": []},
        ],
    }


def test_drill_grid_columns_are_stages_not_tasks():
    grid = drill_grid(_release(), stage_key="execute")
    assert grid["columns"] == ["plan", "execute", "release"]
    assert [row["name"] for row in grid["rows"]] == ["links", "gantt", "notes"]
    assert grid["column_width_px"] == 120
    assert grid["label_width_px"] == 260
    gantt_row = grid["rows"][1]
    assert gantt_row["occupying"] == "execute"
    assert gantt_row["cell_state"] == "blocked"
    assert grid["wip"] == {"plan": 0, "execute": 1, "release": 0}
    assert grid["target_date"] == "2026-11-15"
    assert grid["target_date_is_chip"] is True


def _mini_gantt():
    return {
        "workspace": {"name": "synlynk"},
        "releases": [_release()],
        "dreams": [],
        "goals": [],
        "spec_verifications": [],
        "product_id": "synlynk",
        "notes": {},
    }


def test_gantt_js_uses_stage_columns():
    html = generate_gantt_html(_mini_gantt(), 33333)
    assert "repeat(${total}, 1fr)" not in html
    assert "120px" in html
    assert "date-chip" in html
    assert "tb-blocked" in html
    assert "workspace_views" not in html


def test_gantt_html_has_no_hardcoded_spend_or_jul24():
    html = generate_gantt_html(_mini_gantt(), 33333)
    assert "$28.50" not in html
    assert "Jul 24" not in html
    assert 'id="spend-value"' in html
    assert 'id="next-ship-value"' in html
    assert 'id="agent-count"' in html


def test_visible_row_window():
    start, end = visible_row_window(scroll_top=400, row_height=28, viewport=280, total=500, buffer=5)
    assert start >= 0
    assert end <= 500
    assert (end - start) < 500
    assert end - start <= (280 // 28) + 10 + 2


def test_gantt_js_virtualizes_and_uses_relative_sse():
    html = generate_gantt_html(_mini_gantt(), 33333)
    assert "renderVisibleRows" in html
    assert "EventSource('/events')" not in html
    assert "EventSource('api/daemon/stream')" in html
    assert "workspace_views" not in html
    assert len(html.encode("utf-8")) < 750_000
