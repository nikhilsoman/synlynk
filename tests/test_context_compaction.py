def test_context_compaction_module_importable():
    import synlynk.context_compaction as cc_module

    assert hasattr(cc_module, "CONTEXT_COMPACTION_SETTINGS_SCHEMA")
    assert "auto_checkpoint_on_pack" in cc_module.CONTEXT_COMPACTION_SETTINGS_SCHEMA["fields"]


def test_gather_snapshot_includes_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")

    assert snapshot["story_id"] == "story-abc"
    assert len(snapshot["head_sha"]) == 40
    assert snapshot["is_dirty"] is False


def test_gather_snapshot_detects_dirty_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("changed")

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")
    assert snapshot["is_dirty"] is True


def test_compute_dirty_hash_stable_for_same_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("changed")

    from synlynk.context_compaction import compute_dirty_hash
    h1 = compute_dirty_hash()
    h2 = compute_dirty_hash()
    assert h1 == h2
    assert len(h1) == 12  # short hash for readability in the marker comment


def test_compute_dirty_hash_changes_with_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("changed once")

    from synlynk.context_compaction import compute_dirty_hash
    h1 = compute_dirty_hash()

    (tmp_path / "f.txt").write_text("changed differently")
    h2 = compute_dirty_hash()
    assert h1 != h2


def test_build_marker_clean_tree():
    from synlynk.context_compaction import build_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash=None)
    assert marker == "<!-- SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=story-abc head_sha=" + "a" * 40 + " -->"


def test_build_marker_dirty_tree_includes_dirty_hash():
    from synlynk.context_compaction import build_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash="deadbeef1234")
    assert "dirty_hash=deadbeef1234" in marker


def test_parse_marker_round_trip():
    from synlynk.context_compaction import build_marker, parse_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash="deadbeef1234")
    parsed = parse_marker(marker)
    assert parsed == {"story_id": "story-abc", "head_sha": "a" * 40, "dirty_hash": "deadbeef1234"}


def test_parse_marker_clean_tree_has_no_dirty_hash_key():
    from synlynk.context_compaction import build_marker, parse_marker
    marker = build_marker(story_id="story-abc", head_sha="a" * 40, dirty_hash=None)
    parsed = parse_marker(marker)
    assert "dirty_hash" not in parsed


def test_parse_marker_rejects_non_marker_line():
    from synlynk.context_compaction import parse_marker
    assert parse_marker("not a marker") is None



