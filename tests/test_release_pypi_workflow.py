from pathlib import Path


WORKFLOW = Path(".github/workflows/release-pypi.yml")


def test_pypi_publish_is_gated_until_the_trusted_publisher_exists():
    """gh:#2647 — a tag must not go red while PyPI has no trusted publisher."""
    workflow = WORKFLOW.read_text(encoding="utf-8")

    assert 'tags:\n      - "v*"' in workflow
    assert "types: [published]" in workflow
    assert "id-token: write" in workflow
    assert "python -m build" in workflow
    assert "twine check dist/*" in workflow
    assert "if: vars.PYPI_PUBLISH == 'true'" in workflow
    assert "pypa/gh-action-pypi-publish@release/v1" in workflow
    assert "skip-existing: true" in workflow
    assert "if: vars.PYPI_PUBLISH != 'true'" in workflow
    assert "gh:#2647" in workflow
    assert ".github/workflows/release-pypi.yml" in workflow
    assert "no environment" in workflow
