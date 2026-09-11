import pytest
from synlynk.viz import (
    generate_product_html,
    generate_logical_html,
    generate_infra_html,
    generate_index_html,
    generate_viz_data,
)


def test_generate_product_html():
    data = generate_viz_data()
    html = generate_product_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Product View" in html
    assert "am-drawer" in html


def test_generate_logical_html():
    data = generate_viz_data()
    html = generate_logical_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Logical View" in html
    assert "Package" in html or "Module" in html


def test_generate_infra_html():
    data = generate_viz_data()
    html = generate_infra_html(data, 8721)
    assert "<!DOCTYPE html>" in html
    assert "Infra View" in html
    assert "service" in html.lower() or "daemon" in html.lower()


def test_index_navigation_includes_bs6_views():
    data = generate_viz_data()
    index_html = generate_index_html(data, 8721)
    assert 'href="product.html"' in index_html
    assert 'href="logical.html"' in index_html
    assert 'href="infra.html"' in index_html
