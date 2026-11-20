import json
import re
import shutil
import subprocess
from html.parser import HTMLParser

import pytest

from synlynk.viz import _compute_underused_feature_banner, generate_index_html, generate_viz_data


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


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
@pytest.mark.parametrize(
    ("stored_snooze", "expected_removed"),
    [("2000", True), ("999", False), ("not-a-timestamp", False)],
)
def test_underused_banner_script_honors_snooze_timestamp(stored_snooze, expected_removed):
    rendered = generate_index_html(
        {"jobs": [{"status": "done"} for _ in range(12)], "pending_approvable_prs": [{"number": 42}]},
        8721,
    )
    script = re.search(r"<script>\s*(\(\(\) => \{.*?\}\)\(\);)\s*</script>", rendered, re.DOTALL)
    assert script is not None
    javascript = script.group(1)
    runner = f'''\
const banner = {{
  removed: false,
  remove() {{ this.removed = true; }},
  querySelector() {{ return {{ addEventListener() {{}} }}; }},
}};
global.document = {{ getElementById: () => banner }};
global.localStorage = {{
  getItem: () => {json.dumps(stored_snooze)},
  setItem: () => {{}},
}};
Date.now = () => 1000;
{javascript}
console.log(JSON.stringify({{ removed: banner.removed }}));
'''
    result = subprocess.run(["node", "-e", runner], check=True, capture_output=True, text=True)
    assert json.loads(result.stdout)["removed"] is expected_removed


def test_viz_data_assembles_banner_gates_from_pr_and_merge_policy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()
    monkeypatch.setattr(
        "synlynk.viz.data.build_job_observatory_snapshot",
        lambda: {"jobs": [{"status": "done"} for _ in range(12)]},
    )

    class Completed:
        returncode = 0
        stdout = '[{"number": 42, "isDraft": false, "mergeStateStatus": "CLEAN"}]'

    monkeypatch.setattr("synlynk.viz.data.subprocess.run", lambda *args, **kwargs: Completed())
    policy = {"merge_authority": {"can_merge": ["dev"]}}
    monkeypatch.setattr("synlynk.policy.load_policy", lambda **kwargs: policy)

    data = generate_viz_data()

    assert data["pending_approvable_prs"] == [{"number": 42, "isDraft": False, "mergeStateStatus": "CLEAN"}]
    assert data["reviewer_dispatch"] is False
    assert _compute_underused_feature_banner(data) is not None

    policy["merge_authority"]["can_merge"] = ["qa"]
    reviewer_data = generate_viz_data()
    assert reviewer_data["reviewer_dispatch"] is True
    assert _compute_underused_feature_banner(reviewer_data) is None


def test_generate_index_html_omits_underused_banner_when_not_applicable():
    data = {"jobs": [{"status": "done"} for _ in range(3)]}
    html = generate_index_html(data, 8721)
    assert 'id="vizor-first-visit-banner"' not in html
