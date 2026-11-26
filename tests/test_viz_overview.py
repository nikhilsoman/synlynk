def test_overview_renders_maintainer_operations_widget():
    from synlynk.viz.overview import generate_overview_html

    data = {
        "workspace": {"name": "test-workspace", "updated_at": "2026-11-24"},
        "telemetry": {"sentinel_alerts": []},
        "sentinel_acks": {},
        "maintainer_ops": {"actions": [{"name": "sentinel_triage", "enabled": True, "mode": "dry_run", "last_run": None,
                                         "pending_proposals": [{"proposal_id": "p1", "title": "Sentinel: E501", "tier_provenance": ["sentinel"]}],
                                         "filter_schema": [], "config": {}}],
                           "taxonomy_status": {"schema_valid": True, "validation_error": None}},
    }
    html = generate_overview_html(data, port=8321)
    assert "ops-widget" in html
    assert "sentinel_triage" in html
