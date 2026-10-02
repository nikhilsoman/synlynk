import os
import pytest
from synlynk.regen_guard import RegenConflictError, check_regen_write_guard
from synlynk.db import _write_generated_project_doc, _write_decision_record_md

def test_regen_e2e_guard_rejects_deletions(tmp_path, monkeypatch):
    # Mock _docs_dir and _is_migrated for _write_generated_project_doc
    monkeypatch.setattr("synlynk._is_migrated", lambda: False)
    monkeypatch.setattr("synlynk._docs_dir", lambda: str(tmp_path))
    
    # 1. Write known state (simulates initial write)
    _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\n")
    costs_path = tmp_path / "costs.md"
    assert costs_path.exists()
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\n"
    
    # 2. Append is allowed
    _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\nRow 3\n")
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\nRow 3\n"
    
    # 3. Simulate second concurrent write that missed "Row 3" (deletes it)
    with pytest.raises(RegenConflictError, match="would remove or replace 1 existing lines"):
        _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\n")
        
    # File is untouched
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\nRow 3\n"

