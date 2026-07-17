import stat

import pytest


def test_install_pre_commit_hook_writes_executable_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)

    from synlynk.instructions import install_pre_commit_hook

    install_pre_commit_hook(repo_root=tmp_path)

    hook_path = hook_dir / "pre-commit"
    assert hook_path.exists()
    assert hook_path.stat().st_mode & stat.S_IXUSR
    assert "-m synlynk instructions status --pre-commit" in hook_path.read_text()


def test_install_pre_commit_hook_appends_to_existing_shebang_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)
    hook_path = hook_dir / "pre-commit"
    hook_path.write_text("#!/bin/sh\nexit 0\n")

    from synlynk.instructions import install_pre_commit_hook

    install_pre_commit_hook(repo_root=tmp_path)

    text = hook_path.read_text()
    assert text.startswith("#!/bin/sh")
    assert "exit 0" in text
    assert text.count("-m synlynk instructions status --pre-commit") == 1
    assert hook_path.stat().st_mode & stat.S_IXUSR


def test_install_pre_commit_hook_rejects_non_shebang_hook(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)
    hook_path = hook_dir / "pre-commit"
    hook_path.write_text("echo nope\n")

    from synlynk.instructions import install_pre_commit_hook

    with pytest.raises(RuntimeError, match="unexpected pre-commit hook content"):
        install_pre_commit_hook(repo_root=tmp_path)


def test_tier0_fixture_only_gets_tier0_and_gateway_phrases():
    from synlynk.instructions import render_trigger_phrase_section

    section = render_trigger_phrase_section(current_tier=0)
    assert "let's build X" not in section
    assert "set up synlynk here" in section
    assert "where are we" in section


def test_tier2_fixture_gets_tier0_through_tier2_phrases():
    from synlynk.instructions import render_trigger_phrase_section

    section = render_trigger_phrase_section(current_tier=2)
    assert "let's build X" in section
    assert "set up synlynk here" in section
    assert "rate this agent's output" not in section


def test_instructions_status_pre_commit_exits_on_drift(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    hook_dir = tmp_path / ".git" / "hooks"
    hook_dir.mkdir(parents=True)

    instruction_text = (
        "# Title\n"
        "<!-- synlynk:start version=\"0.4.1\" tool=\"claude\" -->\n"
        "old instruction text\n"
        "<!-- synlynk:end -->\n"
    )
    (tmp_path / "CLAUDE.md").write_text(instruction_text)

    from synlynk.instructions import (
        _compute_section_sha,
        _extract_synlynk_section,
        _write_instruction_manifest,
        cmd_instructions_status,
    )

    section = _extract_synlynk_section(instruction_text, "html")
    _write_instruction_manifest(
        {"CLAUDE.md": {"tool": "claude", "sha": "0" * 16}}
    )
    assert _compute_section_sha(section) != "0" * 16

    with pytest.raises(SystemExit) as exc:
        cmd_instructions_status(pre_commit=True)

    assert exc.value.code == 1
    output = capsys.readouterr().out
    assert "Instruction drift detected. Commit blocked." in output
    assert "synlynk instructions diff CLAUDE.md" in output
    assert "synlynk instructions update CLAUDE.md" in output
    assert "synlynk instructions ack CLAUDE.md" in output
