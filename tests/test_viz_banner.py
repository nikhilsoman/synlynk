from html.parser import HTMLParser

from synlynk.viz import _compute_underused_feature_banner, generate_index_html


class _BodyChildParser(HTMLParser):
    """Record direct children of the document body."""

    def __init__(self):
        super().__init__()
        self._depth = 0
        self.body_children = []

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == "body":
            self._depth = 1
            return
        if self._depth == 1:
            self.body_children.append((tag, attributes.get("id"), attributes.get("class")))
        if self._depth:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._depth:
            self._depth -= 1


def test_underused_banner_for_12_jobs_without_approve_or_kill():
    data = {
        "jobs": [{"status": "done"} for _ in range(12)],
        "pending_approvable_prs": [{"number": 42}],
    }

    banner = _compute_underused_feature_banner(data)

    assert banner is not None
    assert "approve/kill" in banner


def test_underused_banner_is_hidden_after_approve_or_kill():
    data = {"jobs": [{"status": "done"} for _ in range(11)] + [{"status": "killed"}]}

    assert _compute_underused_feature_banner(data) is None


def test_underused_banner_is_hidden_for_fewer_than_10_jobs():
    data = {"jobs": [{"status": "done"}], "pending_approvable_prs": [{"number": 42}]}

    assert _compute_underused_feature_banner(data) is None


def test_underused_banner_is_hidden_for_reviewer_dispatch_workflow():
    data = {
        "jobs": [{"status": "done"} for _ in range(12)],
        "pending_approvable_prs": [{"number": 42}],
        "reviewer_dispatch": True,
    }

    assert _compute_underused_feature_banner(data) is None


def test_underused_banner_is_hidden_without_pending_approvable_prs():
    data = {"jobs": [{"status": "done"} for _ in range(12)]}

    assert _compute_underused_feature_banner(data) is None


def test_generate_index_html_renders_underused_banner():
    data = {
        "jobs": [{"status": "done"} for _ in range(12)],
        "pending_approvable_prs": [{"number": 42}],
    }
    html = generate_index_html(data, 8721)
    assert 'id="vizor-first-visit-banner"' in html
    assert "You've dispatched 12 jobs but never used approve/kill -- try it" in html


def test_underused_banner_is_a_top_bar_and_persists_dismissal_for_14_days():
    data = {
        "jobs": [{"status": "done"} for _ in range(12)],
        "pending_approvable_prs": [{"number": 42}],
    }

    rendered = generate_index_html(data, 8721)
    parser = _BodyChildParser()
    parser.feed(rendered)

    assert parser.body_children[:2] == [
        ("div", "vizor-first-visit-banner", "vizor-underused-banner"),
        ("div", None, "shell"),
    ]
    assert "flex-direction:column" in rendered
    assert "width:100%" in rendered
    assert 'role="status"' in rendered
    assert "localStorage.setItem(VIZOR_UNDERUSED_BANNER_SNOOZE_KEY" in rendered
    assert "14 * 24 * 60 * 60 * 1000" in rendered


def test_generate_index_html_omits_underused_banner_when_not_applicable():
    data = {"jobs": [{"status": "done"} for _ in range(3)]}
    html = generate_index_html(data, 8721)
    assert 'id="vizor-first-visit-banner"' not in html
