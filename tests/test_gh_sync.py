def test_content_hash_is_stable_for_same_input():
    from synlynk.gh_sync import _content_hash

    a = _content_hash({"title": "v1.0.0", "status": "shipped", "due_on": "2026-01-01"})
    b = _content_hash({"title": "v1.0.0", "status": "shipped", "due_on": "2026-01-01"})
    assert a == b


def test_content_hash_differs_when_input_differs():
    from synlynk.gh_sync import _content_hash

    a = _content_hash({"title": "v1.0.0", "status": "shipped"})
    b = _content_hash({"title": "v1.0.0", "status": "planned"})
    assert a != b


def test_gh_api_json_parses_successful_response(monkeypatch):
    import subprocess

    from synlynk import gh_sync

    def fake_run_gh(args, **kwargs):
        assert args[0] == "api"
        return subprocess.CompletedProcess(args, 0, '[{"number": 1, "title": "v1.0.0"}]', "")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)
    result = gh_sync._gh_api_json(["repos/o/r/milestones", "--paginate"])
    assert result == [{"number": 1, "title": "v1.0.0"}]


def test_gh_api_json_raises_on_nonzero_exit(monkeypatch):
    import subprocess

    import pytest

    from synlynk import gh_sync

    def fake_run_gh(args, **kwargs):
        return subprocess.CompletedProcess(args, 1, "", "refused")

    monkeypatch.setattr(gh_sync, "run_gh", fake_run_gh)
    with pytest.raises(RuntimeError, match="refused"):
        gh_sync._gh_api_json(["repos/o/r/milestones"])
