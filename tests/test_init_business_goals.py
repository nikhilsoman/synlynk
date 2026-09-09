def test_fallback_roadmap_includes_business_goals_section():
    import synlynk.instructions
    import inspect
    src = inspect.getsource(synlynk.instructions)
    assert "## Business Goals" in src
