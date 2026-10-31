from pathlib import Path

from synlynk.viz.write_routes import WRITE_ROUTES


def test_every_spec_row_has_an_action():
    required = {
        "board/stage", "board/status", "note", "roles/create",
        "dispatch", "approve", "kill", "worktrees/clean",
        "architect-map/view-pref", "graph/refresh", "tools/install",
    }
    assert required <= set(WRITE_ROUTES)
    assert WRITE_ROUTES["note"] == "proxy"
    assert WRITE_ROUTES["tools/install"] == "hide"
    assert WRITE_ROUTES["board/stage"] == "keep"
    assert WRITE_ROUTES["dispatch"] == "hide"


def test_generators_have_no_site_root_write_fetches():
    root = Path("synlynk/viz")
    forbidden = (
        "fetch('/note'",
        "fetch('/dispatch'",
        "fetch('/approve'",
        "fetch('/kill'",
        "fetch('/roles/create'",
        "fetch('/worktrees/clean'",
        "fetch('/architect-map/view-pref'",
        "/tools/install",
        "/graph/refresh",
    )
    hits = []
    for path in root.rglob("*.py"):
        if path.name in {"server.py", "write_routes.py"}:
            continue
        text = path.read_text()
        for needle in forbidden:
            if needle in text:
                hits.append(f"{path}:{needle}")
    assert hits == [], hits
