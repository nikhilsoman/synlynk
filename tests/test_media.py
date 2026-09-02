from pathlib import Path

from synlynk.media import (
    cmd_media_generate,
    generate_og_card,
    generate_svg_diagram,
)


def test_generate_svg_diagram(tmp_path):
    out_file = tmp_path / "diagram.svg"
    svg = generate_svg_diagram(
        title="Custom Architecture",
        output_path=out_file,
    )
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "Custom Architecture" in svg
    assert "MARKETING AGENT ENGINE" in svg
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == svg


def test_generate_og_card(tmp_path):
    out_file = tmp_path / "og_card.svg"
    svg = generate_og_card(
        title="Autonomous Growth Engine",
        subtitle="Multi-Agent Development",
        tag="GROWTH & PROMOTION",
        author="Agy (Gemini)",
        output_path=out_file,
    )
    assert "<svg" in svg
    assert "</svg>" in svg
    assert "1200" in svg and "630" in svg
    assert "Autonomous Growth Engine" in svg
    assert "Agy (Gemini)" in svg
    assert "GROWTH & PROMOTION" in svg
    assert out_file.exists()
    assert out_file.read_text(encoding="utf-8") == svg


def test_cmd_media_generate_all(tmp_path):
    results = cmd_media_generate(media_type="all", output=str(tmp_path))
    assert "diagram" in results
    assert "og_card" in results
    assert Path(results["diagram"]).exists()
    assert Path(results["og_card"]).exists()


def test_cmd_media_generate_diagram_only(tmp_path):
    out_file = tmp_path / "diag.svg"
    results = cmd_media_generate(media_type="diagram", output=str(out_file))
    assert "diagram" in results
    assert "og_card" not in results
    assert Path(results["diagram"]).exists()


def test_cmd_media_generate_og_only(tmp_path):
    out_file = tmp_path / "og.svg"
    results = cmd_media_generate(media_type="og", output=str(out_file))
    assert "og_card" in results
    assert "diagram" not in results
    assert Path(results["og_card"]).exists()
