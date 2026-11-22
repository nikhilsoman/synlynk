from html.parser import HTMLParser
from urllib.parse import parse_qs, urlparse

import pytest

from synlynk.viz import generate_index_html


class _Find(HTMLParser):
    def __init__(self):
        super().__init__()
        self.found = False
        self.href = None

    def handle_starttag(self, tag, attrs):
        if dict(attrs).get("data-action") == "report-issue":
            self.found = True
            self.href = dict(attrs).get("href")


@pytest.fixture
def render_home():
    return lambda: generate_index_html({"workspace": {"name": "synlynk"}}, 8721)


def test_report_action_in_footer(render_home):
    p = _Find()
    p.feed(render_home())
    assert p.found
    parsed = urlparse(p.href)
    assert parsed.netloc == "github.com"
    assert parsed.path == "/nikhilsoman/synlynk/issues/new"
    assert parse_qs(parsed.query)["template"] == ["bug_report.yml"]
    assert "bundle" in parse_qs(parsed.query)


def test_payload_contains_only_allowed_keys():
    from synlynk.viz.data import report_issue_payload

    payload = report_issue_payload(
        route="/w/synlynk/overview.html",
        meta={"version": "1", "token": "x", "secret": "y"},
    )
    assert set(payload) <= {"route", "version", "fingerprint"}
    assert "x" not in payload.values()
    assert "y" not in payload.values()
