from synlynk.viz import generate_viz_data


def test_viz_data_includes_goals_key():
    data = generate_viz_data()
    assert "goals" in data
    assert isinstance(data["goals"], list)
