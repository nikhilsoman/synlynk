import pytest

import synlynk.db as db


class _Connection:
    def close(self):
        pass


@pytest.mark.parametrize(
    "path",
    [
        "project-docs/todo.md",
        "project-docs/roadmap.md",
        "project-docs/costs.md",
    ],
)
def test_pr_check_rejects_legacy_checkout_export_diff(path, monkeypatch, capsys):
    monkeypatch.setattr(db, "_get_db", lambda: _Connection())
    monkeypatch.setattr(db, "_is_github_remote", lambda: True)
    monkeypatch.setattr(db, "_current_pr_number", lambda pr_number=None: 123)
    monkeypatch.setattr(db, "_gh_pr_changed_files", lambda pr_number: [path])

    with pytest.raises(SystemExit) as exc:
        db.cmd_pr_check()

    assert exc.value.code == 1
    assert path in capsys.readouterr().out
