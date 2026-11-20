from synlynk import report_cmd as rc


def _body():
    return "## What happened\nboom\n\nfingerprint: abc123abc123\n"


def test_no_y_means_nothing_filed(monkeypatch):
    calls = []
    monkeypatch.setattr(
        rc, "_gh_issue_create", lambda *args, **kwargs: calls.append(args) or "url"
    )
    assert (
        rc.confirm_and_file(_body(), "t", answer=lambda _: "n", interactive=True)
        is None
    )
    assert calls == []


def test_non_interactive_never_files(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        rc, "_gh_issue_create", lambda *args, **kwargs: calls.append(args) or "url"
    )
    out = rc.confirm_and_file(
        _body(), "t", answer=lambda _: "y", interactive=False, local_dir=tmp_path
    )
    assert calls == [] and out.endswith(".md")


def test_secret_in_body_blocks_filing(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(
        rc, "_gh_issue_create", lambda *args, **kwargs: calls.append(args) or "url"
    )
    body = _body() + "password=hunter2hunter2\n"
    assert (
        rc.confirm_and_file(
            body, "t", answer=lambda _: "y", interactive=True, local_dir=tmp_path
        )
        is None
    )
    assert calls == []


def test_secret_body_is_not_printed_when_blocked(monkeypatch, capsys):
    secret = "github_pat_" + "A" * 40
    monkeypatch.setattr(rc, "_gh_issue_create", lambda *args: "unexpected")

    assert (
        rc.confirm_and_file(
            _body() + secret, "t", answer=lambda _: "y", interactive=True
        )
        is None
    )

    assert secret not in capsys.readouterr().out


def test_y_files_via_gh(monkeypatch):
    monkeypatch.setattr(
        rc,
        "_gh_issue_create",
        lambda title, body: "https://github.com/o/r/issues/1",
    )
    assert rc.confirm_and_file(
        _body(), "t", answer=lambda _: "y", interactive=True
    ).endswith("/issues/1")


def test_gh_unavailable_falls_back_to_url_and_file(monkeypatch, tmp_path):
    def unavailable(*args, **kwargs):
        raise FileNotFoundError("gh")

    monkeypatch.setattr(rc, "_gh_issue_create", unavailable)
    out = rc.confirm_and_file(
        _body(), "t", answer=lambda _: "y", interactive=True, local_dir=tmp_path
    )
    assert "issues/new" in out or out.endswith(".md")


def test_report_registered_in_taxonomy_and_parser():
    from synlynk.cli import _TOP_LEVEL_COMMANDS, build_parser
    from synlynk.taxonomy import COMMAND_TAXONOMY

    assert any(entry["command"] == "report" for entry in COMMAND_TAXONOMY)
    assert "report" in _TOP_LEVEL_COMMANDS
    assert build_parser().parse_args(["report"]).command == "report"


def test_issue_form_has_required_bundle_field():
    import json
    from pathlib import Path
    import subprocess

    path = Path(".github/ISSUE_TEMPLATE/bug_report.yml")
    result = subprocess.run(
        ["ruby", "-rjson", "-ryaml", "-e",
         "puts JSON.generate(YAML.safe_load(File.read(ARGV[0])))", str(path)],
        capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
    form = json.loads(result.stdout)
    bundle = next(field for field in form["body"] if field.get("id") == "bundle")
    assert bundle["validations"]["required"] is True
    assert not Path(".github/ISSUE_TEMPLATE/bug_report.md").exists()


def test_cli_reconciliation_does_not_initialize_bare_directory(monkeypatch, tmp_path):
    from synlynk.jobs import _reconcile_jobs

    monkeypatch.chdir(tmp_path)
    _reconcile_jobs()

    assert not (tmp_path / ".synlynk").exists()


def test_redirected_preview_never_files(monkeypatch, tmp_path):
    calls = []
    monkeypatch.setattr(rc.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(rc.sys.stdout, "isatty", lambda: False)
    monkeypatch.setattr(rc, "_gh_issue_create", lambda *args: calls.append(args) or "url")

    out = rc.confirm_and_file(_body(), "t", local_dir=tmp_path)

    assert calls == []
    assert out.endswith(".md")


def test_cmd_report_can_withhold_remote(monkeypatch):
    bundle = {"remote": "github.com/private/repo", "fingerprint": "abc123abc123"}
    answers = iter(["boom", "n"])
    captured = {}
    monkeypatch.setattr(rc.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(rc, "_input", lambda _: next(answers))
    monkeypatch.setattr(rc, "collect_bundle", lambda: bundle.copy())
    monkeypatch.setattr(
        rc,
        "confirm_and_file",
        lambda body, title: captured.update(body=body, title=title),
    )

    assert rc.cmd_report() == 1
    assert "github.com/private/repo" not in captured["body"]
    assert "Withheld: remote." in captured["body"]


def test_noninteractive_cmd_report_withholds_remote(monkeypatch):
    bundle = {"remote": "github.com/private/repo", "fingerprint": "abc123abc123"}
    captured = {}
    monkeypatch.setattr(rc.sys.stdin, "isatty", lambda: False)
    monkeypatch.setattr(rc, "collect_bundle", lambda: bundle.copy())
    monkeypatch.setattr(
        rc,
        "confirm_and_file",
        lambda body, title: captured.update(body=body, title=title),
    )

    assert rc.cmd_report() == 1
    assert "github.com/private/repo" not in captured["body"]
    assert "Withheld: remote." in captured["body"]


def test_remote_consent_prompt_does_not_echo_remote(monkeypatch):
    bundle = {"remote": "github.com/private/repo", "fingerprint": "abc123abc123"}
    prompts = []
    answers = iter(["boom", "n"])
    monkeypatch.setattr(rc.sys.stdin, "isatty", lambda: True)
    monkeypatch.setattr(
        rc, "_input", lambda prompt: prompts.append(prompt) or next(answers)
    )
    monkeypatch.setattr(rc, "collect_bundle", lambda: bundle.copy())
    monkeypatch.setattr(rc, "confirm_and_file", lambda body, title: None)

    rc.cmd_report()

    assert all("github.com/private/repo" not in prompt for prompt in prompts)


def test_reserved_part_two_flags_do_not_start_filing(capsys):
    from types import SimpleNamespace

    assert rc.cmd_report(SimpleNamespace(last=True, clear_flight=False)) == 2
    assert rc.cmd_report(SimpleNamespace(last=False, clear_flight=True)) == 2
    assert "Part 2" in capsys.readouterr().err
