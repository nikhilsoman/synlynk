from pathlib import Path


def test_pytest_configuration_excludes_archived_duplicate_modules():
    config = (Path(__file__).parents[1] / "pytest.ini").read_text(encoding="utf-8")

    assert "testpaths = tests" in config
    assert "norecursedirs = docs/archive" in config
    assert "collect_imported_tests = false" in config
