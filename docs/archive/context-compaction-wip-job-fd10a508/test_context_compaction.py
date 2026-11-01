"""Tests for synlynk.context_compaction — Tasks 1–6 of the
Harness Context Compaction Protocol implementation plan.
"""

import os
import subprocess


# ── Task 1: Module skeleton ──────────────────────────────────────────


def test_context_compaction_module_importable():
    import synlynk.context_compaction as cc_module

    assert hasattr(cc_module, "CONTEXT_COMPACTION_SETTINGS_SCHEMA")
    assert "auto_checkpoint_on_pack" in cc_module.CONTEXT_COMPACTION_SETTINGS_SCHEMA["fields"]


# ── Shared helper ────────────────────────────────────────────────────


def _init_git_repo(tmp_path):
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.txt").write_text("x")
    subprocess.run(["git", "add", "f.txt"], cwd=tmp_path)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
    )


# ── Task 2: _gather_snapshot() ───────────────────────────────────────


def test_gather_snapshot_includes_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")

    assert snapshot["story_id"] == "story-abc"
    assert len(snapshot["head_sha"]) == 40
    assert snapshot["is_dirty"] is False


def test_gather_snapshot_detects_dirty_tree(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / "f.txt").write_text("changed")

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")
    assert snapshot["is_dirty"] is True


def test_gather_snapshot_includes_ast_grounded_signatures(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init", "-q"], cwd=tmp_path)
    (tmp_path / "f.py").write_text("def foo():\n    pass\n")
    subprocess.run(["git", "add", "f.py"], cwd=tmp_path)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "init"],
        cwd=tmp_path,
    )
    (tmp_path / "f.py").write_text("def foo():\n    pass\n\ndef bar():\n    pass\n")

    from synlynk.context_compaction import _gather_snapshot
    snapshot = _gather_snapshot(story_id="story-abc")
    assert "bar" in snapshot["changed_file_signatures"]["f.py"]


# ── Task 3: compute_dirty_hash() ─────────────────────────────────────


def test_compute_dirty_hash_stable_for_same_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / "f.txt").write_text("changed")

    from synlynk.context_compaction import compute_dirty_hash
    h1 = compute_dirty_hash()
    h2 = compute_dirty_hash()
    assert h1 == h2
    assert len(h1) == 12  # short hash for readability in the marker comment


def test_compute_dirty_hash_changes_with_diff(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    (tmp_path / "f.txt").write_text("changed once")

    from synlynk.context_compaction import compute_dirty_hash
    h1 = compute_dirty_hash()

    (tmp_path / "f.txt").write_text("changed differently")
    h2 = compute_dirty_hash()
    assert h1 != h2


# ── Task 4: Marker build/parse ───────────────────────────────────────


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


# ── Task 5: checkpoint() — idempotent devlog write ────────────────────


def test_checkpoint_writes_marker_and_ledger_to_devlog(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
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
    os.makedirs("project-docs/devlogs", exist_ok=True)
    devlog_path = tmp_path / "project-docs/devlogs/testuser.md"
    devlog_path.write_text("# Devlog\n")

    from synlynk.context_compaction import checkpoint
    checkpoint(story_id="story-abc", username="testuser")
    first_marker_count = devlog_path.read_text().count("SYNLYNK_CONTEXT_COMPACTION_RESUME")

    (tmp_path / "f2.txt").write_text("y")
    subprocess.run(["git", "add", "f2.txt"], cwd=tmp_path)
    subprocess.run(
        ["git", "-c", "user.email=t@t.com", "-c", "user.name=t", "commit", "-q", "-m", "second"],
        cwd=tmp_path,
    )

    checkpoint(story_id="story-abc", username="testuser")
    second_marker_count = devlog_path.read_text().count("SYNLYNK_CONTEXT_COMPACTION_RESUME")
    assert second_marker_count == first_marker_count + 1


# ── Task 6: Context-pack 5-part content model + pack() ───────────────


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
    os.makedirs("project-docs/devlogs", exist_ok=True)
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.context_compaction import pack
    pack(story_id="story-abc", task_description="t", username="testuser", auto_checkpoint=True)

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME" in content


def test_pack_with_auto_checkpoint_disabled_does_not_call_checkpoint(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _init_git_repo(tmp_path)
    os.makedirs("project-docs/devlogs", exist_ok=True)
    (tmp_path / "project-docs/devlogs/testuser.md").write_text("# Devlog\n")

    from synlynk.context_compaction import pack
    pack(story_id="story-abc", task_description="t", username="testuser", auto_checkpoint=False)

    content = (tmp_path / "project-docs/devlogs/testuser.md").read_text()
    assert "SYNLYNK_CONTEXT_COMPACTION_RESUME" not in content
