import json
import pytest
from pathlib import Path
from synlynk.pack import synthesize_context_pack, extract_symbol_signatures_and_tests

def test_synthesize_context_pack_inlines_signatures_and_tests(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    syn = repo / ".synlynk" / "graphify-out"
    syn.mkdir(parents=True)

    # Create dummy source and test files
    src = repo / "calculator.py"
    src.write_text('def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b\n')

    test_file = repo / "tests" / "test_calc.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('from calculator import add\ndef test_add():\n    assert add(1, 2) == 3\n')

    graph_data = {
        "nodes": [
            {"id": "calculator.py::add", "name": "add", "file": "calculator.py", "kind": "Function", "community": 0},
            {"id": "tests/test_calc.py::test_add", "name": "test_add", "file": "tests/test_calc.py", "kind": "Function", "community": 0}
        ],
        "edges": [
            {"source": "tests/test_calc.py::test_add", "target": "calculator.py::add", "relation": "calls"}
        ]
    }
    (syn / "graph.json").write_text(json.dumps(graph_data))

    pack = synthesize_context_pack(str(repo), task_text="Fix bug in add function")
    assert "calculator.py" in pack
    assert "add" in pack
    assert "tests/test_calc.py" in pack or "test_calc.py" in pack

def test_extract_symbol_signatures_and_tests(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    src = repo / "service.py"
    src.write_text('class UserService:\n    """Manage user accounts."""\n    def get_user(self, user_id: str) -> dict:\n        return {"id": user_id}\n')

    test_file = repo / "tests" / "test_user_service.py"
    test_file.parent.mkdir(parents=True)
    test_file.write_text('from service import UserService\ndef test_get_user():\n    pass\n')

    res = extract_symbol_signatures_and_tests(str(repo), ["service.py::UserService"])
    assert "service.py::UserService" in res
    entry = res["service.py::UserService"]
    assert "UserService" in entry["signature"] or "class UserService" in entry["signature"]
    assert "Manage user accounts" in entry["docstring"]
    assert any("test_user_service.py" in t for t in entry["tests"])
