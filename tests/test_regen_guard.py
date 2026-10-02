import os
import pytest
from synlynk.regen_guard import check_regen_write_guard, RegenConflictError

def test_regen_guard_append(tmp_path):
    f = tmp_path / "costs.md"
    f.write_text("Row 1\nRow 2\n")
    
    # Pure append should not raise
    check_regen_write_guard(str(f), "Row 1\nRow 2\nRow 3\n")
    
def test_regen_guard_conflict(tmp_path):
    f = tmp_path / "costs.md"
    f.write_text("Row 1\nRow 2\nRow 3\n")
    
    # Removing a row should raise
    with pytest.raises(RegenConflictError, match="would remove or replace 1 existing lines"):
        check_regen_write_guard(str(f), "Row 1\nRow 3\n")
        
def test_regen_guard_rewrite_with_change(tmp_path):
    f = tmp_path / "costs.md"
    f.write_text("Row 1\nRow 2\n")
    
    # Modifying a row should raise
    with pytest.raises(RegenConflictError):
        check_regen_write_guard(str(f), "Row 1\nRow X\n")

def test_regen_guard_new_file(tmp_path):
    f = tmp_path / "costs.md"
    # File doesn't exist
    check_regen_write_guard(str(f), "Row 1\nRow 2\n")
