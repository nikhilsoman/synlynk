from synlynk.harness_adapters.grok import GrokAdapter


def test_grok_translate_permissions_nonempty_grants_always_approve():
    adapter = GrokAdapter()
    flags = adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=True)
    assert flags == ["--always-approve", "--permission-mode", "bypassPermissions"]


def test_grok_translate_permissions_raises_when_not_skipped():
    import pytest
    from synlynk.harness_adapters.base import PermissionEnforcementError

    adapter = GrokAdapter()
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False, skip_permissions=False)


def test_grok_translate_permissions_raises_by_default_when_skip_permissions_omitted():
    import pytest
    from synlynk.harness_adapters.base import PermissionEnforcementError

    adapter = GrokAdapter()
    with pytest.raises(PermissionEnforcementError):
        adapter.translate_permissions(["write:repo"], read_only=False)


def test_grok_translate_permissions_empty_grants_no_flags():
    adapter = GrokAdapter()
    assert adapter.translate_permissions([], read_only=False) == []


def test_grok_classify_failure_billing_exhaustion_regression_fixture():
    """Regression fixture: this session's 402 Grok Build usage balance exhausted."""
    adapter = GrokAdapter()
    raw = "API error (status 402 Payment Required): Grok Build usage balance exhausted"
    result = adapter.classify_failure(exit_code=1, stderr=raw, raw_text=raw)
    assert result.value == "quota_exhausted"


def test_grok_classify_failure_session_expiry_regression_fixture():
    """Regression fixture: this session's 'Not signed in' session expiry."""
    adapter = GrokAdapter()
    raw = "Not signed in... run grok login --device-code"
    result = adapter.classify_failure(exit_code=1, stderr=raw, raw_text=raw)
    assert result.value == "auth_expired"


def test_grok_classify_failure_sandbox_bash_denial_regression_fixture():
    """Regression fixture: this session's silent bash-denying sandbox (exit 0, no real work)."""
    adapter = GrokAdapter()
    raw = "permission denied: bash execution is not allowed in this sandbox"
    result = adapter.classify_failure(exit_code=0, stderr="", raw_text=raw)
    assert result.value == "sandbox_denied"
