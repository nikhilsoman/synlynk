from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.request import DispatchRequest


def test_codex_translate_permissions_write_grant_uses_workspace_write():
    adapter = CodexAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False)
    assert flags == ["-s", "workspace-write"]


def test_codex_translate_permissions_read_only_uses_read_only_profile():
    adapter = CodexAdapter()
    flags = adapter.translate_permissions([], read_only=True)
    assert flags == ["-s", "read-only"]


def test_codex_build_cmd_includes_dispatch_flags():
    adapter = CodexAdapter()
    request = DispatchRequest(agent="codex", task="fix it", permissions=["write:repo"])
    cmd = adapter.build_cmd(request)
    assert isinstance(cmd, list) and len(cmd) > 0


def test_codex_classify_failure_flags_ask_for_approval_incompatibility():
    """Regression fixture: this session's --ask-for-approval CLI incompatibility."""
    adapter = CodexAdapter()
    stderr = "error: unrecognized arguments: --ask-for-approval never"
    result = adapter.classify_failure(exit_code=2, stderr=stderr, raw_text=stderr)
    assert result.value == "sandbox_denied"


def test_codex_classify_failure_returns_none_for_unrelated_errors():
    adapter = CodexAdapter()
    result = adapter.classify_failure(exit_code=1, stderr="some unrelated traceback", raw_text="")
    assert result is None
