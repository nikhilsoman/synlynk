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
