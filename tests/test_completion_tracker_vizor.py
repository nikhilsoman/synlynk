from synlynk.events import emit_event
from synlynk.viz import generate_viz_data


def test_generate_viz_data_includes_spec_verifications(project_dir):
    emit_event(
        "spec_verified",
        {
            "pr_number": 501,
            "spec_path": "docs/superpowers/specs/example.md",
            "verdict": "fulfilled",
            "rationale": "Matches the approved spec",
        },
        emitted_by="test",
    )

    data = generate_viz_data()

    assert data["spec_verifications"] == [
        {
            "pr_number": 501,
            "spec_path": "docs/superpowers/specs/example.md",
            "verdict": "fulfilled",
            "rationale": "Matches the approved spec",
        }
    ]


def test_generate_viz_data_spec_verifications_empty_when_no_events(project_dir):
    assert generate_viz_data()["spec_verifications"] == []


def test_generate_viz_data_spec_verifications_newest_first(project_dir):
    emit_event("spec_verified", {"pr_number": 501}, emitted_by="test")
    emit_event("spec_verified", {"pr_number": 502}, emitted_by="test")

    verifications = generate_viz_data()["spec_verifications"]

    assert [entry["pr_number"] for entry in verifications] == [502, 501]
