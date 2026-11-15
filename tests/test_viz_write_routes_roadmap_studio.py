from synlynk.viz.write_routes import WRITE_ROUTES


def test_roadmap_studio_routes_are_classified_keep():
    for action in ("approve", "hold", "revise", "drop", "reorder", "pin"):
        assert WRITE_ROUTES[f"roadmap_studio/{action}"] == "keep"
