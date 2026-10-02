import pytest
from synlynk.gc_cmd import cmd_gc

def test_gc_dry_run_does_not_crash(capsys):
    # Just verify it can run without errors when not in a git repo or whatever
    # It might print "Not a git repository" if we mock it, but we are inside one.
    cmd_gc(dry_run=True, yes=False, retention_days=14)
    captured = capsys.readouterr()
    assert "Running synlynk gc" in captured.out
