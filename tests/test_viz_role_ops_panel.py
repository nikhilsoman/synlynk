# tests/test_viz_role_ops_panel.py
from synlynk.viz.role_ops_panel import generate_role_ops_panel_html, generate_condensed_widget_html


def test_panel_renders_each_registered_action_with_toggle_state():
    data = {
        "actions": [
            {"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": "2026-11-23T10:00:00Z",
             "pending_proposals": [{"proposal_id": "maintainer-sentinel-abc", "title": "Sentinel: E501", "tier_provenance": ["sentinel"]}],
             "filter_schema": [{"name": "exclude_codes", "type": "list[str]", "default": [], "label": "Exclude alert codes"}],
             "config": {"exclude_codes": []}},
            {"name": "backlog_burndown", "enabled": False, "mode": "dry_run", "last_run": None, "pending_proposals": [],
             "filter_schema": [{"name": "exclude_labels", "type": "list[str]", "default": [], "label": "Exclude labels"}],
             "config": {"exclude_labels": []}},
            {"name": "mesh_sweep", "enabled": True, "mode": "promote", "last_run": "2026-11-24T06:00:00Z", "pending_proposals": [],
             "filter_schema": [], "config": {}, "low_signal": True},
        ],
        "taxonomy_status": {"schema_valid": True, "validation_error": None},
    }
    html = generate_role_ops_panel_html("maintainer", data)
    assert "sentinel_triage" in html
    assert "backlog_burndown" in html
    assert "mesh_sweep" in html
    assert "2026-11-23T10:00:00Z" in html
    assert "low-signal" in html.lower() or "low signal" in html.lower()
    # FieldSpec-driven rendering: the field's label and a form control for it
    assert "Exclude alert codes" in html
    assert 'name="exclude_codes"' in html
    # provenance detail on the pending proposal
    assert "sentinel" in html
    assert "Sentinel: E501" in html
    # no defaults banner when taxonomy is valid
    assert "using built-in defaults" not in html.lower()


def test_panel_is_generic_across_role_slugs():
    data = {
        "actions": [{"name": "custom_action", "enabled": True, "mode": "dry_run", "last_run": None,
                     "pending_proposals": [], "filter_schema": [], "config": {}}],
        "taxonomy_status": {"schema_valid": True, "validation_error": None},
    }
    html = generate_role_ops_panel_html("tpm", data)
    assert "custom_action" in html
    assert "tpm" in html.lower()


def test_panel_renders_defaults_banner_when_taxonomy_invalid():
    data = {
        "actions": [{"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": None,
                     "pending_proposals": [], "filter_schema": [], "config": {}}],
        "taxonomy_status": {"schema_valid": False, "validation_error": "unsupported schema_version 99 in maintainer_taxonomy.json"},
    }
    html = generate_role_ops_panel_html("maintainer", data)
    assert "using built-in defaults" in html.lower()
    assert "unsupported schema_version 99" in html


def test_panel_renders_why_this_grouping_provenance_for_each_pending_proposal():
    data = {
        "actions": [{"name": "mesh_sweep", "enabled": True, "mode": "dry_run", "last_run": None,
                     "pending_proposals": [
                         {"proposal_id": "p1", "title": "Contract drift: billing-service", "tier_provenance": ["code_graph", "doc_graph"]},
                     ],
                     "filter_schema": [], "config": {}}],
        "taxonomy_status": {"schema_valid": True, "validation_error": None},
    }
    html = generate_role_ops_panel_html("maintainer", data)
    assert "code_graph" in html and "doc_graph" in html
    assert "why this grouping" in html.lower()


def test_condensed_widget_renders_badges_and_counts():
    data = {
        "actions": [
            {"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": "2026-11-23T10:00:00Z",
             "pending_proposals": [{"proposal_id": "p1"}], "filter_schema": [], "config": {}},
            {"name": "backlog_burndown", "enabled": True, "mode": "promote", "last_run": "2026-11-24T12:00:00Z",
             "pending_proposals": [], "filter_schema": [], "config": {}},
        ],
        "taxonomy_status": {"schema_valid": True, "validation_error": None},
    }
    html = generate_condensed_widget_html("maintainer", data)
    assert "ops-widget" in html
    assert "Maintainer Operations" in html
    assert "sentinel_triage" in html
    assert "backlog_burndown" in html
    assert "1 pending proposal" in html
    assert "2026-11-24T12:00:00Z" in html
