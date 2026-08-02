from synlynk import _redact_secret_patterns


def test_redacts_github_pat():
    text = "token=ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in _redact_secret_patterns(text)
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_redacts_github_oauth_token():
    text = "gho_abcdefghijklmnopqrstuvwxyz0123456789"
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_redacts_aws_access_key_id():
    text = "AWS_ACCESS_KEY_ID=AKIAABCDEFGHIJKLMNOP"
    result = _redact_secret_patterns(text)
    assert "AKIAABCDEFGHIJKLMNOP" not in result
    assert "[REDACTED]" in result


def test_redacts_openai_style_key():
    text = "sk-abcdefghijklmnopqrstuvwxyz123456"
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_redacts_slack_token():
    text = "xoxb-not-a-real-token-fixture-0000"
    assert "[REDACTED]" in _redact_secret_patterns(text)


def test_normal_text_passes_through_unchanged():
    text = "Running tests... 30 passed in 2.01s. No issues found."
    assert _redact_secret_patterns(text) == text
