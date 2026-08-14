def test_checkpoint_writes_to_canonical_member_path(project_dir, monkeypatch):
    import os

    from synlynk import _get_db, checkpoint

    monkeypatch.setattr("synlynk.get_username", lambda: "nikhil")

    with open("project-docs/todo.md", "a") as f:
        f.write("- [x] Ship the thing <!-- id: 99 -->\n")

    checkpoint()

    canonical_path = os.path.join("project-docs", "devlogs", "nikhilsoman.md")
    assert os.path.exists(canonical_path)
    assert "Ship the thing" in open(canonical_path).read()
    assert not os.path.exists(os.path.join("project-docs", "devlogs", "nikhil.md"))
