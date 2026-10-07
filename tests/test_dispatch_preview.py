from unittest.mock import patch

from synlynk.dispatch import compose_dispatch_preview


def test_preview_promotes_empirically_better_harness(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    policy_path = tmp_path / ".synlynk" / "policy.json"
    policy_path.parent.mkdir(parents=True)
    policy_path.write_text(
        '{"schema_version": 1, "repo_id": "test", "capability_policy": {},'
        ' "overrides": {"dev_authority": {"task_allocation": '
        '{"implement": {"harness": "codex", "fallback": ["grok"]}}}}}'
    )
    with patch("synlynk.capability.ranked_harness_for_task", return_value="grok"):
        preview = compose_dispatch_preview("implement a new login form", task_type="implement")
    # _infer_dispatch_defaults (the function at dispatch.py:636, which the
    # design calls compose_dispatch_preview) returns the resolved harness
    # under "harness", not "agent".
    assert preview["harness"] == "grok"
