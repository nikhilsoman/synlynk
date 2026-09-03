from synlynk.team import _audit_metrics


def test_audit_metrics_exposes_required_dimensions():
    metrics = _audit_metrics()
    assert set(metrics) == {"Codebase Modularity", "AI-Readiness", "Tech Debt", "Cost Efficiency"}
