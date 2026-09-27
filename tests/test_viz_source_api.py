import json
import pytest
from pathlib import Path
from synlynk.viz import _get_source_slice

def test_api_source_endpoint_returns_file_content(tmp_path):
    test_file = tmp_path / "demo.py"
    test_file.write_text("line 1\nline 2\nline 3\nline 4\nline 5\n")

    res = _get_source_slice(str(tmp_path), "demo.py", start_line=2, end_line=4)
    assert res["status"] == "ok"
    assert res["start_line"] == 2
    assert res["end_line"] == 4
    assert res["content"] == "line 2\nline 3\nline 4"
    assert res["total_lines"] == 5

def test_api_source_full_file(tmp_path):
    test_file = tmp_path / "demo.py"
    test_file.write_text("a = 1\nb = 2\n")

    res = _get_source_slice(str(tmp_path), "demo.py")
    assert res["status"] == "ok"
    assert res["start_line"] == 1
    assert res["end_line"] == 2
    assert res["content"] == "a = 1\nb = 2"

def test_api_source_rejects_path_traversal(tmp_path):
    res = _get_source_slice(str(tmp_path), "../../etc/passwd")
    assert res["status"] == "error"
    assert "traversal" in res["error"].lower() or res.get("code") in (400, 403)

def test_api_source_file_not_found(tmp_path):
    res = _get_source_slice(str(tmp_path), "nonexistent.py")
    assert res["status"] == "error"
    assert "not found" in res["error"].lower() or res.get("code") == 404
