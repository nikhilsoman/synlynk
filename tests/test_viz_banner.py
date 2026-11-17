from synlynk.viz import _compute_underused_feature_banner, generate_index_html


def test_underused_banner_for_12_jobs_without_approve_or_kill():
    data = {"jobs": [{"status": "done"} for _ in range(12)]}

    banner = _compute_underused_feature_banner(data)

    assert banner is not None
    assert "approve/kill" in banner


def test_underused_banner_is_hidden_after_approve_or_kill():
    data = {"jobs": [{"status": "done"} for _ in range(11)] + [{"status": "killed"}]}

    assert _compute_underused_feature_banner(data) is None


def test_underused_banner_is_hidden_for_fewer_than_10_jobs():
    data = {"jobs": [{"status": "done"}]}

    assert _compute_underused_feature_banner(data) is None


def test_generate_index_html_renders_underused_banner():
    data = {"jobs": [{"status": "done"} for _ in range(12)]}
    html = generate_index_html(data, 8721)
    assert 'id="vizor-first-visit-banner"' in html
    assert "You've dispatched 12 jobs but never used approve/kill -- try it" in html


def test_generate_index_html_omits_underused_banner_when_not_applicable():
    data = {"jobs": [{"status": "done"} for _ in range(3)]}
    html = generate_index_html(data, 8721)
    assert 'id="vizor-first-visit-banner"' not in html
