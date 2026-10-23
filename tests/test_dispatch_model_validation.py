"""Tests verifying explicit --model preflight validation (gh:#2291)."""

import pytest
import synlynk as sl
import synlynk.dispatch as dispatch_mod
from synlynk.models import ModelSpec


def test_dispatch_rejects_unknown_explicit_grok_model(project_dir, monkeypatch):
    """Repro from gh:#2291: synlynk dispatch grok ... --model grok-code-fast-1."""
    monkeypatch.setattr(
        dispatch_mod.subprocess, "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )

    with pytest.raises(ValueError) as exc_info:
        dispatch_mod.dispatch_agent(
            "grok", "run task", model="grok-code-fast-1",
            skip_preflight=True, context_mode="none", skip_permissions=True,
        )

    message = str(exc_info.value)
    assert "Invalid model 'grok-code-fast-1' for harness 'grok'" in message
    assert "Valid model ids:" in message


def test_dispatch_rejects_unknown_explicit_codex_model(project_dir, monkeypatch):
    """Repro from gh:#2291: synlynk dispatch codex ... --model gpt-5.1-codex."""
    monkeypatch.setattr(
        dispatch_mod.subprocess, "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )

    with pytest.raises(ValueError) as exc_info:
        dispatch_mod.dispatch_agent(
            "codex", "run task", model="gpt-5.1-codex",
            skip_preflight=True, context_mode="none",
        )

    message = str(exc_info.value)
    assert "Invalid model 'gpt-5.1-codex' for harness 'codex'" in message
    assert "Valid model ids:" in message


def test_dispatch_rejects_unknown_explicit_agy_model(project_dir, monkeypatch):
    monkeypatch.setattr(
        dispatch_mod.subprocess, "Popen",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("must not spawn")),
    )

    with pytest.raises(ValueError) as exc_info:
        dispatch_mod.dispatch_agent(
            "agy", "run task", model="non-existent-agy-model",
            skip_preflight=True, context_mode="none",
        )

    message = str(exc_info.value)
    assert "Invalid model 'non-existent-agy-model' for harness 'agy'" in message
    assert "Valid model ids:" in message


def test_dispatch_accepts_valid_explicit_grok_model(project_dir, monkeypatch):
    spawned = []

    def fake_popen(cmd, *args, **kwargs):
        spawned.append(cmd)
        return type("DummyProc", (), {"pid": 9999})()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)

    job = dispatch_mod.dispatch_agent(
        "grok", "run task", model="grok-4.6",
        skip_preflight=True, context_mode="none", skip_permissions=True,
    )
    assert job["pid"] == 9999


def test_dispatch_accepts_valid_explicit_codex_model(project_dir, monkeypatch):
    spawned = []

    def fake_popen(cmd, *args, **kwargs):
        spawned.append(cmd)
        return type("DummyProc", (), {"pid": 9999})()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)

    job = dispatch_mod.dispatch_agent(
        "codex", "run task", model="gpt-5.6-luna",
        skip_preflight=True, context_mode="none",
    )
    assert job["pid"] == 9999
