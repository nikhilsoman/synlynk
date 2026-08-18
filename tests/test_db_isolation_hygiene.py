"""Static guard against tests accidentally opening the shared state database."""

from __future__ import annotations

import ast
from pathlib import Path


def _function_nodes(tree: ast.AST):
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and node.name.startswith("test_"):
            yield node


def _source_has_isolation(
    node: ast.AST,
    source: str,
    fixture_names: set[str],
    has_global_fixture: bool = False,
) -> bool:
    """Recognize the supported per-test DB isolation idioms."""
    text = ast.get_source_segment(source, node) or ""
    return has_global_fixture or any(
        marker in text
        for marker in (
            "SYNLYNK_STATE_DB_PATH",
            "SYNLYNK_DB_PATH",
            "tmp_path",
            "project_dir",
            "monkeypatch.setattr(\"synlynk",
            "monkeypatch.setattr(synlynk",
            "patch(\"synlynk",
            "SYNLYNK_ALLOW_SHARED_STATE_DB",
        )
    ) or bool(fixture_names.intersection(_function_arguments(node)))


def _function_arguments(node: ast.AST) -> set[str]:
    arguments = getattr(node, "args", None)
    if arguments is None:
        return set()
    return {arg.arg for arg in (*arguments.posonlyargs, *arguments.args, *arguments.kwonlyargs)}


def find_unisolated_db_tests(test_root: Path) -> list[str]:
    """Return test functions that can reach a non-isolated on-disk DB."""
    offenders: list[str] = []
    for path in sorted(test_root.glob("test_*.py")):
        source = path.read_text()
        tree = ast.parse(source, filename=str(path))
        fixture_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(
                (
                    isinstance(dec, ast.Call)
                    and isinstance(dec.func, ast.Name)
                    and dec.func.id == "fixture"
                )
                or (
                    isinstance(dec, ast.Attribute)
                    and isinstance(dec.value, ast.Name)
                    and dec.value.id == "pytest"
                    and dec.attr == "fixture"
                )
                for dec in node.decorator_list
            )
            and _source_has_isolation(node, source, set())
        }
        # tests/conftest.py applies this fixture to every test in the suite.
        has_global_fixture = path.parent.joinpath("conftest.py").exists()
        for node in _function_nodes(tree):
            calls_db = False
            for child in ast.walk(node):
                if not isinstance(child, ast.Call):
                    continue
                if isinstance(child.func, ast.Name) and child.func.id == "_get_db":
                    calls_db = True
                elif isinstance(child.func, ast.Attribute) and child.func.attr == "_get_db":
                    calls_db = True
                elif (
                    isinstance(child.func, ast.Attribute)
                    and child.func.attr == "connect"
                    and isinstance(child.func.value, ast.Name)
                    and child.func.value.id == "sqlite3"
                ):
                    argument = ast.get_source_segment(source, child.args[0]) if child.args else ""
                    if argument and ":memory:" not in argument and "tmp_path" not in argument:
                        calls_db = True
            if calls_db and not _source_has_isolation(
                node, source, fixture_names, has_global_fixture
            ):
                offenders.append(f"{path.relative_to(test_root)}::{node.name}")
    return offenders


def test_all_db_tests_are_isolated():
    offenders = find_unisolated_db_tests(Path(__file__).parent)
    assert not offenders, (
        "Tests opening a resolved state DB must use SYNLYNK_STATE_DB_PATH, "
        "a tmp_path DB, or an explicit DB mock; offending functions:\n- "
        + "\n- ".join(offenders)
    )


def test_meta_test_catches_synthetic_unisolated_test(tmp_path):
    synthetic = tmp_path / "test_synthetic_bad.py"
    synthetic.write_text(
        "import sqlite3\n"
        "from synlynk import _get_db\n\n"
        "def test_bad():\n"
        "    _get_db()\n"
        "    sqlite3.connect('state.db')\n"
    )
    assert find_unisolated_db_tests(tmp_path) == ["test_synthetic_bad.py::test_bad"]
