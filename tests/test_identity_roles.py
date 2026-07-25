import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.identity_roles import load_declared_roles, DEFAULT_ROLES


def test_load_declared_roles_defaults_when_file_missing(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    assert load_declared_roles() == list(DEFAULT_ROLES)


def test_load_declared_roles_reads_yaml_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text(
        "roles:\n  - director\n  - screenwriter\n  - editor\n"
    )
    assert load_declared_roles() == ["director", "screenwriter", "editor"]


def test_load_declared_roles_ignores_malformed_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    (tmp_path / ".synlynk" / "roles.yaml").write_text("not: valid: yaml: [[[")
    assert load_declared_roles() == list(DEFAULT_ROLES)
