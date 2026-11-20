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
