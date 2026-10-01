import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib  # type: ignore


ROOT = Path(__file__).resolve().parents[1]


def test_pyproject_metadata_constraints():
    pyproject_path = ROOT / "pyproject.toml"
    assert pyproject_path.exists(), "pyproject.toml missing"
    with pyproject_path.open("rb") as file:
        data = tomllib.load(file)

    project = data.get("project", {})
    assert project.get("requires-python") == ">=3.10"
    assert project.get("dependencies") == []
    assert project.get("scripts", {}).get("synlynk") == "synlynk:main"

    classifiers = project.get("classifiers", [])
    for version in ("3.10", "3.11", "3.12", "3.13"):
        assert f"Programming Language :: Python :: {version}" in classifiers


def test_pep561_py_typed_marker_present():
    py_typed = ROOT / "synlynk" / "py.typed"
    assert py_typed.exists(), "synlynk/py.typed PEP 561 marker missing"
