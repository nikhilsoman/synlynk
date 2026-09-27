import pytest
from synlynk.viz import (
    generate_product_html,
    generate_logical_html,
    generate_infra_html,
    generate_world_html,
    generate_index_html,
    generate_viz_data,
)


def test_generate_product_html():
    data = generate_viz_data()
    html = generate_product_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Product View" in html or "User Journeys" in html
    assert "journeys" in html.lower() or "screens" in html.lower()


def test_generate_logical_html():
    data = generate_viz_data()
    html = generate_logical_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Logical" in html
    assert any(k in html for k in ("HLD", "LLD", "Sequence", "layer", "module", "Package", "Class"))


def test_generate_infra_html():
    data = generate_viz_data()
    html = generate_infra_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Infra" in html
    assert "service" in html.lower() or "daemon" in html.lower() or "host" in html.lower()


def test_generate_world_html():
    data = generate_viz_data()
    html = generate_world_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "World" in html or "Ecosystem Radar" in html
    assert "radar" in html.lower() or "ring" in html.lower()


def test_index_navigation_includes_bs6_views():
    data = generate_viz_data()
    index_html = generate_index_html(data, 8721)
    assert 'href="product.html"' in index_html
    assert 'href="logical.html"' in index_html
    assert 'href="infra.html"' in index_html
    assert 'href="world.html"' in index_html
