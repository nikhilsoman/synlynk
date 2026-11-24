from pathlib import Path


README = Path(__file__).parents[1] / "README.md"


def test_readme_has_first_run_contract():
    text = README.read_text(encoding="utf-8")

    assert "pipx install synlynk" in text
    assert "## 60-second quickstart" in text
    assert "## Command reference" in text
    assert "## Dispatch tasks" in text
    assert "| Command | What it does |" in text


def test_readme_badges_cover_release_health_and_license():
    text = README.read_text(encoding="utf-8")

    assert "alt=\"Tests passing\"" in text
    assert "alt=\"Version\"" in text
    assert "alt=\"License\"" in text
