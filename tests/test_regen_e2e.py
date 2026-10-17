from synlynk.db import _write_generated_project_doc

def test_regen_e2e_isolated_sandbox_allows_regeneration(tmp_path, monkeypatch):
    # Even in an isolated checkout, generated state exports belong beside the
    # canonical product database rather than in project docs.
    import synlynk

    monkeypatch.setattr("synlynk._is_migrated", lambda: False)
    monkeypatch.setattr("synlynk._docs_dir", lambda: str(tmp_path))
    canonical_docs = tmp_path / "canonical" / "project-docs"
    monkeypatch.setattr(synlynk, "_generated_project_docs_dir", lambda: str(canonical_docs))
    monkeypatch.setenv("SYNLYNK_TEST_PROJECT_DIR", "1")

    # 1. Write known state (simulates initial write)
    _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\n")
    costs_path = canonical_docs / "costs.md"
    assert costs_path.exists()
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\n"
    
    # 2. Append is allowed
    _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\nRow 3\n")
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\nRow 3\n"
    
    # 3. A regeneration that misses "Row 3" is still valid in this sandbox.
    _write_generated_project_doc("costs.md", "Header\nRow 1\nRow 2\n")
    assert costs_path.read_text() == "Header\nRow 1\nRow 2\n"
    assert not (tmp_path / "costs.md").exists()
