def test_fallback_roadmap_includes_business_goals_section():
    import synlynk
    import inspect
    src = inspect.getsource(synlynk)
    assert "## Business Goals" in src
