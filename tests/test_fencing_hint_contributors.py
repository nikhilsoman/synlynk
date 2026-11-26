# tests/test_fencing_hint_contributors.py
import re
from pathlib import Path

from synlynk.fencing import (
    FenceData,
    _HINT_CONTRIBUTORS,
    clear_hint_contributors,
    register_hint_contributor,
    render_task_fence,
)


def setup_function(_):
    clear_hint_contributors()


def test_render_task_fence_calls_registered_contributor():
    seen = []

    def contributor(data):
        seen.append(data)
        data.hints.append("test hint")

    register_hint_contributor(contributor)
    data = FenceData(command="test", kind="task_complete", in_tokens=10, out_tokens=20, cost_usd=0.01, basis="actual", hints=[])
    render_task_fence(data)

    assert seen == [data]
    assert "test hint" in data.hints


def test_render_task_fence_with_no_contributors_matches_baseline():
    data_before = FenceData(command="test", kind="task_complete", in_tokens=10, out_tokens=20, cost_usd=0.01, basis="actual", hints=[])
    output_before = render_task_fence(data_before)

    data_after = FenceData(command="test", kind="task_complete", in_tokens=10, out_tokens=20, cost_usd=0.01, basis="actual", hints=[])
    output_after = render_task_fence(data_after)

    assert output_before == output_after


def test_fencing_py_does_not_import_any_feature_module():
    source = Path("synlynk/fencing.py").read_text()
    for forbidden in ("companion", "context_compaction", "herdr_cockpit"):
        assert not re.search(rf"^\s*(from|import)\s+synlynk\.{forbidden}\b", source, re.MULTILINE), (
            f"fencing.py must not import synlynk.{forbidden} by name"
        )


def test_maintainer_fence_hint_contributor_adds_hint_when_proposals_pending(monkeypatch):
    clear_hint_contributors()
    from synlynk.maintainer_hints import maintainer_fence_hint_contributor
    register_hint_contributor(maintainer_fence_hint_contributor)

    monkeypatch.setattr("synlynk.maintainer_hints._pending_proposal_count", lambda: 3)

    data = FenceData(command="exec", kind="actual", in_tokens=10, out_tokens=10, cost_usd=0.01, basis="actual")
    rendered = render_task_fence(data)
    assert "3 maintainer proposals pending" in rendered

    clear_hint_contributors()


def test_maintainer_fence_hint_contributor_silent_when_nothing_pending(monkeypatch):
    clear_hint_contributors()
    from synlynk.maintainer_hints import maintainer_fence_hint_contributor
    register_hint_contributor(maintainer_fence_hint_contributor)

    monkeypatch.setattr("synlynk.maintainer_hints._pending_proposal_count", lambda: 0)

    data = FenceData(command="exec", kind="actual", in_tokens=10, out_tokens=10, cost_usd=0.01, basis="actual")
    rendered = render_task_fence(data)
    assert "maintainer proposal" not in rendered

    clear_hint_contributors()

