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


def test_redacts_github_app_installation_token():
    # Classic alphanumeric ghs_ token
    text1 = "token=ghs_16u5S23058PzAALpPpBVo3243abcdef"
    assert "ghs_16u5S23058PzAALpPpBVo3243abcdef" not in _redact_secret_patterns(text1)
    assert "[REDACTED]" in _redact_secret_patterns(text1)

    # JWT / long ghs_ token with '.', '-', '_'
    text2 = "token=ghs_16u5S23058PzAALpPpBVo3243.eyJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2-abcdef_1234567890"
    assert "ghs_16u5S23058PzAALpPpBVo3243.eyJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2-abcdef_1234567890" not in _redact_secret_patterns(text2)
    assert "[REDACTED]" in _redact_secret_patterns(text2)


def test_bug__secret_patterns_regex_doesnt_redact_ghs_installation_token():
    text = "ghs_16u5S23058PzAALpPpBVo3243.eyJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2-abcdef_1234567890"
    result = _redact_secret_patterns(text)
    assert text not in result
    assert result == "[REDACTED]"


def test_normal_text_passes_through_unchanged():
    text = "Running tests... 30 passed in 2.01s. No issues found."
    assert _redact_secret_patterns(text) == text

