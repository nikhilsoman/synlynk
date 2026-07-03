import argparse
import os
import sys

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


def test_cmd_watch_exits_on_db_missing(tmp_path, monkeypatch, capsys):
    import synlynk.cli as cli_mod

    monkeypatch.setattr(cli_mod, "_SYNLYNK_DIR", str(tmp_path / ".synlynk"))

    args = argparse.Namespace(command="watch", live=False)
    with pytest.raises(SystemExit) as exc:
        cli_mod.cmd_watch(args)

    assert exc.value.code != 0
    out = capsys.readouterr()
    assert "not found" in out.err.lower()
