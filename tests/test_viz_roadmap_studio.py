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
