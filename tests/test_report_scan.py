from synlynk.report_scan import find_secrets


def test_flags_known_token_shapes():
    text = "token ghp_" + "a" * 36 + " and AKIA" + "A" * 16
    hits = find_secrets(text)
    assert len(hits) == 2


def test_flags_credentialed_url_and_bearer():
    assert find_secrets("https://user:pw@example.com/x")
    assert find_secrets("Authorization: Bearer abcdefghijklmnop1234")


def test_clean_text_has_no_hits():
    assert find_secrets("synlynk 0.38.3 on darwin, doctor: 3 warn") == []


def test_flags_fine_grained_github_and_anthropic_tokens():
    assert find_secrets("github_pat_" + "A" * 40)
    assert find_secrets("sk-ant-api03-" + "A" * 40)
