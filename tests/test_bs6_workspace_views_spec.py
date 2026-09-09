"""Guard the BS-6 product/logical/infra visualization spec against silent section loss."""
from pathlib import Path


SPEC_PATH = (
    Path(__file__).resolve().parents[1]
    / "docs"
    / "superpowers"
    / "specs"
    / "2026-09-09-bs6-repo-workspace-visualization-design.md"
)

REQUIRED_HEADINGS = (
    "## 2. User value",
    "## 5. Data sources and model",
    "## 7. Refresh and observability",
    "## 8. Staged implementation",
    "## 9. Acceptance criteria",
    "## 11. Risks",
)

REQUIRED_PHRASES = (
    "Product",
    "Logical",
    "Infra",
    "WORKSPACE_VIEW_STALE",
    "workspace_view_nodes",
    "does not authorize implementation",
)


def test_bs6_workspace_views_spec_exists():
    assert SPEC_PATH.is_file(), f"missing design spec at {SPEC_PATH}"


def test_bs6_workspace_views_spec_covers_required_sections():
    text = SPEC_PATH.read_text(encoding="utf-8")
    missing_headings = [heading for heading in REQUIRED_HEADINGS if heading not in text]
    missing_phrases = [phrase for phrase in REQUIRED_PHRASES if phrase not in text]
    assert not missing_headings, f"spec missing headings: {missing_headings}"
    assert not missing_phrases, f"spec missing locked phrases: {missing_phrases}"
    assert "TBD" not in text
    assert "TODO" not in text
