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


def _init_git_repo(tmp_path):
    import subprocess
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"], cwd=tmp_path)


def test_checkpoint_writes_marker_and_ledger_to_devlog(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")

    content = devlog_path.read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME story_id=story-abc" in content


def test_checkpoint_idempotent_on_unchanged_state(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")
    first_content = devlog_path.read_text()
    checkpoint(story_id="story-abc", username="testuser")  # same head_sha, same dirty state
    second_content = devlog_path.read_text()

    assert first_content == second_content  # no duplicate entry appended


def test_checkpoint_writes_new_entry_after_head_changes(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os, subprocess
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")
    first_marker_count = devlog_path.read_text().count("SYNLYNK_CONTEXT_COMPACTION_RESUME")

    (tmp_path / "f2.txt").write_text("y")
    subprocess.run(["git", "add", "f2.txt"], cwd=tmp_path)
    subprocess.run(["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "second"], cwd=tmp_path)

    checkpoint(story_id="story-abc", username="testuser")
    second_marker_count = devlog_path.read_text().count("SYNLYNK_CONTEXT_COMPACTION_RESUME")
    assert second_marker_count == first_marker_count + 1


def test_pack_builds_five_part_content_model(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)

    from synlynk.context_compaction import pack
    content_pack = pack(story_id="story-abc", task_description="implement widget")

    assert set(content_pack.keys()) == {
        "story_summary", "recent_decisions", "open_threads",
        "relevant_files", "task_description",
    }
    assert content_pack["task_description"] == "implement widget"


def test_pack_with_auto_checkpoint_enabled_calls_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.context_compaction import pack
    pack(story_id="story-abc", task_description="t", username="testuser", auto_checkpoint=True)

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME" in content


def test_pack_with_auto_checkpoint_disabled_does_not_call_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    import os
    os.makedirs("project-docs/devlogs", exist_ok=True)
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.context_compaction import pack
    pack(story_id="story-abc", task_description="t", username="testuser", auto_checkpoint=False)

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME" not in content


def test_apply_token_budget_truncates_longest_fields_first():
    from synlynk.context_compaction import apply_token_budget
    content_pack = {
        "story_summary": "a" * 100,
        "recent_decisions": "b" * 500,
        "open_threads": "c" * 50,
        "relevant_files": "d" * 300,
        "task_description": "e" * 20,
    }
    # budget in characters for this test's purposes (real token counting is
    # an estimation detail; the truncation *order* is what's under test)
    truncated = apply_token_budget(content_pack, budget_chars=600)

    total_len = sum(len(v) for v in truncated.values())
    assert total_len <= 600
    assert truncated["task_description"] == "e" * 20  # smallest/highest-priority field untouched
    assert len(truncated["recent_decisions"]) < 500  # longest field truncated first


def test_apply_token_budget_noop_when_under_budget():
    from synlynk.context_compaction import apply_token_budget
    content_pack = {"story_summary": "short", "task_description": "x"}
    result = apply_token_budget(content_pack, budget_chars=10000)
    assert result == content_pack


def test_inject_renders_content_pack_as_markdown():
    from synlynk.context_compaction import inject
    content_pack = {
        "story_summary": "Build widget",
        "recent_decisions": ["Use SQLite"],
        "open_threads": ["Need review"],
        "relevant_files": ["synlynk/widget.py"],
        "task_description": "implement widget",
    }
    rendered = inject(content_pack)

    assert "Build widget" in rendered
    assert "Use SQLite" in rendered
    assert "Need review" in rendered
    assert "synlynk/widget.py" in rendered
    assert "implement widget" in rendered







