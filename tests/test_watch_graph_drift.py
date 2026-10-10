import json
import pytest
from pathlib import Path
from synlynk.watch import check_and_refresh_ast_on_drift, _get_head_commit

def test_watch_detects_head_drift_and_triggers_extract(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    syn = repo / ".synlynk"
    syn.mkdir()
    graph_out = syn / "graphify-out"
    graph_out.mkdir()
    manifest = graph_out / "manifest.json"
    manifest.write_text(json.dumps({"built_at_commit": "old-sha-123"}))

    # Mock git rev-parse HEAD
    monkeypatch.setattr("synlynk.watch._get_head_commit", lambda r: "new-sha-456")
    extracted = []
    def fake_extract(r):
        extracted.append(r)
        manifest.write_text(json.dumps({"built_at_commit": "new-sha-456"}))
        return True
    monkeypatch.setattr("synlynk.scan._run_graphify_extract", fake_extract)

    refreshed = check_and_refresh_ast_on_drift(str(repo))
    assert refreshed is True
    assert len(extracted) == 1
    updated_manifest = json.loads(manifest.read_text())
    assert updated_manifest["built_at_commit"] == "new-sha-456"

def test_watch_no_drift_skips_extract(tmp_path, monkeypatch):
    repo = tmp_path / "repo"
    repo.mkdir()
    syn = repo / ".synlynk" / "graphify-out"
    syn.mkdir(parents=True)
    manifest = syn / "manifest.json"
    manifest.write_text(json.dumps({"built_at_commit": "same-sha-123"}))

    monkeypatch.setattr("synlynk.watch._get_head_commit", lambda r: "same-sha-123")
    extracted = []
    monkeypatch.setattr("synlynk.scan._run_graphify_extract", lambda r: extracted.append(r) or True)

    refreshed = check_and_refresh_ast_on_drift(str(repo))
    assert refreshed is False
    assert len(extracted) == 0
