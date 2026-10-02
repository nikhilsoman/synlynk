import pytest
from synlynk.registry import load_registry, redact_secrets


def test_registry_default_integrations(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    reg = load_registry()
    assert "supabase" in reg
    assert "openrouter" in reg
    assert reg["openrouter"]["auth_type"] == "byok"


def test_secret_redaction_masks_tokens():
    text = "Deploying to https://api.supabase.com with token sb_secret_key_12345."
    redacted = redact_secrets(text, secrets=["sb_secret_key_12345"])
    assert "sb_secret_key_12345" not in redacted
    assert "[REDACTED_SECRET]" in redacted
