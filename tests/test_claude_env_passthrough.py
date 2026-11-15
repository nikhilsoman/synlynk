import os
from pathlib import Path
from synlynk._constants import HARNESS_CAPABILITY_BASELINES
from synlynk.dispatch import _build_subprocess_env
from synlynk.probe_binding import _auth_config_path


def test_claude_env_passthrough_retains_gateway_vars(monkeypatch):
    """Verify ANTHROPIC_BASE_URL, ANTHROPIC_API_KEY, and CLAUDE_CONFIG_DIR are preserved (Fixes #5298)."""
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:4000")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-mock-key")
    monkeypatch.setenv("ANTHROPIC_AUTH_TOKEN", "mock-auth-token")
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/tmp/mock-claude-profile")
    monkeypatch.setenv("UNRELATED_SECRET", "super-secret")

    # Verify declared in baseline
    claude_passthrough = HARNESS_CAPABILITY_BASELINES["claude"]["env_passthrough"]
    assert "ANTHROPIC_BASE_URL" in claude_passthrough
    assert "ANTHROPIC_AUTH_TOKEN" in claude_passthrough
    assert "ANTHROPIC_API_KEY" in claude_passthrough
    assert "CLAUDE_CONFIG_DIR" in claude_passthrough

    # Verify subprocess env builder retains them and excludes unrelated
    proc_env, tmp_dir = _build_subprocess_env("claude", {}, False, None)
    try:
        assert proc_env.get("ANTHROPIC_BASE_URL") == "http://127.0.0.1:4000"
        assert proc_env.get("ANTHROPIC_API_KEY") == "sk-mock-key"
        assert proc_env.get("ANTHROPIC_AUTH_TOKEN") == "mock-auth-token"
        assert proc_env.get("CLAUDE_CONFIG_DIR") == "/tmp/mock-claude-profile"
        assert "UNRELATED_SECRET" not in proc_env
    finally:
        if tmp_dir:
            tmp_dir.cleanup()


def test_probe_binding_respects_claude_config_dir(tmp_path, monkeypatch):
    """Verify _auth_config_path respects CLAUDE_CONFIG_DIR when provided (Fixes #5298)."""
    custom_dir = tmp_path / "custom_claude_dir"
    custom_dir.mkdir()
    config_file = custom_dir / ".claude.json"
    config_file.write_text("{}", encoding="utf-8")

    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(custom_dir))
    auth_path = _auth_config_path("claude")
    assert auth_path == config_file
