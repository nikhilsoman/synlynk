"""Tests for BS-12a: synlynk roles subcommand + load_config roles default."""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import synlynk


def test_load_config_roles_default_has_four_agents(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = synlynk.load_config()
    roles = cfg.get("roles", {})
    assert set(roles.keys()) >= {"claude", "agy", "grok", "codex"}


def test_load_config_roles_claude_is_pm(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = synlynk.load_config()
    assert "pm" in cfg["roles"]["claude"]


def test_load_config_roles_codex_is_implement(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    cfg = synlynk.load_config()
    assert "implement" in cfg["roles"]["codex"]


def test_fence_exists_false_when_no_fence(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "CLAUDE.md"
    f.write_text("# Some file\nno fence here\n")
    assert not synlynk._fence_exists(str(f))


def test_fence_exists_true_when_fence_present(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    f = tmp_path / "GEMINI.md"
    f.write_text(
        "# Header\n"
        "<!-- synlynk:harness v1 verified:2026-01-01 -->\n"
        "body\n"
        "<!-- /synlynk:harness -->\n"
    )
    assert synlynk._fence_exists(str(f))


def test_cmd_roles_prints_table(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    synlynk.cmd_roles(fix=False)
    out = capsys.readouterr().out
    assert "claude" in out
    assert "agy" in out
    assert "codex" in out
    assert "pm" in out


def test_cmd_roles_fix_writes_fence(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    claude_md = tmp_path / "CLAUDE.md"
    claude_md.write_text("# Claude\nSome content\n")
    synlynk.cmd_roles(fix=True)
    content = claude_md.read_text()
    assert "<!-- synlynk:harness" in content


def test_cmd_roles_fix_skips_missing_file(tmp_path, monkeypatch, capsys):
    """--fix should not create files that don't exist, just skip them."""
    monkeypatch.chdir(tmp_path)
    synlynk.cmd_roles(fix=True)
    _ = capsys.readouterr()
    assert not (tmp_path / "CLAUDE.md").exists()
