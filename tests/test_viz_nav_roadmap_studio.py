from synlynk.viz.home import generate_index_html


def test_status_nav_includes_roadmap_studio():
    out = generate_index_html({"workspace": {"repos": []}}, 44444)
    assert 'href="roadmap_studio.html"' in out
    assert 'data-view="roadmap_studio"' in out
