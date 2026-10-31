from synlynk.viz.nav import VIEW_CATALOG, workspace_view_href, switcher_html, iframe_nav_script


def test_timeline_maps_to_gantt():
    href, view_id = workspace_view_href("timeline")
    assert view_id == "gantt"
    assert href == "gantt.html"
    assert not href.startswith("/")


def test_switcher_has_no_site_root_or_timeline():
    html = switcher_html(active="product")
    assert "/tube.html" not in html
    assert "/timeline.html" not in html
    assert 'href="gantt.html"' in html
    assert 'data-viz-view="gantt"' in html
    assert 'data-viz-view="tube"' in html
    assert "nav-btn active" in html


def test_iframe_script_calls_parent_setview_or_falls_back():
    js = iframe_nav_script()
    assert "parent.setView" in js
    assert "data-viz-view" in js
    assert "index.html?view=" in js


import pathlib
from synlynk.viz.canvases import generate_product_html, generate_infra_html, generate_world_html
from synlynk.viz.overview import generate_overview_html
from synlynk.viz.home import generate_index_html
from synlynk.viz.gantt import generate_gantt_html
from synlynk.viz.nav import VIEW_CATALOG, workspace_view_href

ROOT = pathlib.Path("synlynk/viz")
FORBIDDEN = (
    'href="/tube.html"',
    'href="/timeline.html"',
    'href="/logical.html"',
    'href="/product.html"',
    'href="/infra.html"',
    'href="/world.html"',
    'href="/board.html"',
)


def _mini():
    return {"workspace": {"name": "synlynk"}, "releases": [], "dreams": [], "goals": [],
            "spec_verifications": [], "notes": {}, "product_id": "synlynk"}


def test_viz_generators_emit_no_site_root_view_hrefs():
    hits = []
    for path in ROOT.rglob("*.py"):
        text = path.read_text()
        for needle in FORBIDDEN:
            if needle in text:
                hits.append(f"{path}:{needle}")
    assert hits == [], hits


def test_product_html_switcher_is_workspace_relative():
    html = generate_product_html(_mini(), 33333)
    assert 'href="/tube.html"' not in html
    assert 'href="/timeline.html"' not in html
    assert 'data-viz-view="tube"' in html
    assert "parent.setView" in html


def test_infra_and_world_html_are_workspace_relative():
    for fn in (generate_infra_html, generate_world_html):
        html = fn(_mini(), 33333)
        assert 'href="/tube.html"' not in html
        assert 'data-viz-view="gantt"' in html


def test_overview_chips_carry_data_viz_view():
    html = generate_overview_html(_mini(), 33333)
    assert 'data-viz-view="gantt"' in html
    assert 'data-viz-view="board"' in html
    assert 'data-viz-view="observatory"' in html


def test_chrome_honors_view_query_and_postmessage():
    html = generate_index_html(_mini(), 33333)
    assert "URLSearchParams" in html
    assert "vizor-navigate" in html
    assert "window.setView = setView" in html
