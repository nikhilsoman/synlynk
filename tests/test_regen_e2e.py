import os
from synlynk.regen_guard import check_regen_write_guard
from synlynk.db import _write_generated_project_doc, _write_decision_record_md

def test_regen_e2e_isolated_sandbox_allows_regeneration(tmp_path, monkeypatch):
    # An isolated fixture has no committed origin/main baseline and should be
    # allowed to regenerate its own project-docs files.
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
    
    # 3. A regeneration that misses "Row 3" is still valid in this sandbox.
    _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\n")
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\n"
