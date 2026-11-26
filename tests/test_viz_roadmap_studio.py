"""Rendering test for synlynk/viz/roadmap_studio.py's generate_roadmap_studio_html()."""
from synlynk.viz.roadmap_studio import generate_roadmap_studio_html


def test_generate_roadmap_studio_html_has_shell_and_actions():
    out = generate_roadmap_studio_html(44444)
    assert "<!DOCTYPE html>" in out
    assert "Roadmap Studio" in out
    assert "api/roadmap_studio" in out
    for action in ("approve", "hold", "revise", "drop", "reorder", "pin"):
        assert f"api/roadmap_studio/{action}" in out
    assert "vizorAuthHeaders" in out


def test_generate_roadmap_studio_html_is_deterministic_per_port():
    first = generate_roadmap_studio_html(55555)
    second = generate_roadmap_studio_html(55555)
    assert first == second


def test_generate_proposal_studio_html_renders_the_shell_page():
    from synlynk.viz.roadmap_studio import generate_proposal_studio_html

    html = generate_proposal_studio_html(port=8321)
    # generate_proposal_studio_html's existing signature takes only `port` and
    # renders a static shell whose JS fetches studioData from api/roadmap_studio
    # client-side (see synlynk/roadmap_studio.py's studio_data(), Task 14 Step 0/3)
    # -- this test only confirms the renamed function is importable and still
    # returns a non-empty page, plus the new badge/lane markup.
    assert "<html" in html.lower()
    assert "source-badge" in html
    assert "needs-attention-lane" in html


def test_generate_roadmap_studio_html_alias_still_importable():
    from synlynk.viz.roadmap_studio import generate_roadmap_studio_html, generate_proposal_studio_html

    assert generate_roadmap_studio_html is generate_proposal_studio_html

