import pytest


@pytest.mark.parametrize(
    ("flags", "expected"),
    [
        (["--dry-run"], (True, False)),
        (["--backfill"], (False, True)),
        (["--dry-run", "--backfill"], (True, True)),
    ],
)
def test_sync_roadmap_accepts_only_supported_flags(monkeypatch, flags, expected):
    from synlynk import cli, gh_sync_cli, github_repo

    calls = []
    monkeypatch.setattr(cli, "_warn_stale_repo_version", lambda *args, **kwargs: None)
    monkeypatch.setattr(github_repo, "resolve_owner_repo", lambda: ("o", "r"))
    monkeypatch.setattr(
        gh_sync_cli,
        "cmd_sync_roadmap",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main(["gh", "--role", "pm", "sync-roadmap", *flags])

    assert exc.value.code == 0
    assert calls == [
        {
            "dry_run": expected[0],
            "backfill": expected[1],
            "owner": "o",
            "repo": "r",
            "role": "pm",
        }
    ]


@pytest.mark.parametrize("flag", ["--help", "-h", "--dry-rnu"])
def test_sync_roadmap_rejects_unsupported_flags_without_syncing(
    monkeypatch, capsys, flag
):
    from synlynk import cli, gh_sync_cli, github_repo

    calls = []
    monkeypatch.setattr(cli, "_warn_stale_repo_version", lambda *args, **kwargs: None)
    monkeypatch.setattr(github_repo, "resolve_owner_repo", lambda: ("o", "r"))
    monkeypatch.setattr(
        gh_sync_cli,
        "cmd_sync_roadmap",
        lambda **kwargs: calls.append(kwargs),
    )

    with pytest.raises(SystemExit) as exc:
        cli.main(["gh", "sync-roadmap", flag])

    assert exc.value.code != 0
    assert calls == []
    stderr = capsys.readouterr().err
    assert "usage: synlynk gh sync-roadmap [--dry-run] [--backfill]" in stderr
    assert flag in stderr
