from synlynk.viz import generate_gantt_html

def test_gantt_html_renders_goal_count_id():
    data = {
        "workspace": {"name": "test-ws"},
        "dreams": [],
        "goals": [
            {"id": "goal-1", "outcome": "First Goal", "criterion": "Test Criterion", "deadline": "2026-07-31", "status": "active"}
        ]
    }
    html = generate_gantt_html(data, 8765)
    assert 'id="goal-count"' in html
    assert 'id="goal-sub"' in html
    assert 'id="goals-panel"' in html
    assert 'First Goal' in html
    assert 'Test Criterion' in html
    assert '2026-07-31' in html

def test_gantt_html_empty_goals_shows_empty_state():
    data = {
        "workspace": {"name": "test-ws"},
        "dreams": [],
        "goals": []
    }
    html = generate_gantt_html(data, 8765)
    assert "goal create" in html
