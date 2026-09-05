import argparse
import json
import os

import pytest


def test_cmd_home_displays_status(capsys, monkeypatch, tmp_path):
    import synlynk
    from synlynk import cli

    cfg = {"home_harness": "claude"}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "load_config", lambda: cfg)

    args = argparse.Namespace(command="home", harness=None)
    cli.cmd_home(args)

    out = capsys.readouterr().out
    assert "Home Harness Status:" in out
    assert "Configured in .synlynk/config.json : claude" in out


def test_cmd_home_switches_harness(capsys, monkeypatch, tmp_path):
    import synlynk
    from synlynk import cli
    import synlynk.context

    cfg = {"home_harness": "claude"}
    saved = {}

    def fake_update(updates):
        saved.update(updates)
        cfg.update(updates)

    refreshed = []
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(synlynk, "load_config", lambda: cfg)
    monkeypatch.setattr(synlynk, "_update_config", fake_update)
    monkeypatch.setattr(synlynk.context, "generate_context", lambda: refreshed.append(True))

    args = argparse.Namespace(command="home", harness="agy")
    cli.cmd_home(args)

    out = capsys.readouterr().out
    assert "Home harness switched to: agy" in out
    assert saved.get("home_harness") == "agy"
    assert refreshed == [True]
