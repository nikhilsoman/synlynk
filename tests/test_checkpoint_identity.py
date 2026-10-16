import pytest

pytestmark = pytest.mark.usefixtures("daemon_workspace_root")


def test_checkpoint_writes_to_canonical_member_path(project_dir, monkeypatch):
    import os

    from synlynk import _get_db, checkpoint

    monkeypatch.setattr("synlynk.get_username", lambda: "nikhil")

    canonical_todo = os.path.join(
        __import__("synlynk")._generated_project_docs_dir(), "todo.md"
    )
    os.makedirs(os.path.dirname(canonical_todo), exist_ok=True)
    with open(canonical_todo, "a") as f:
        f.write("- [x] Ship the thing <!-- id: 99 -->\n")
    checkout_todo = os.path.join("project-docs", "todo.md")
    with open(checkout_todo) as f:
        checkout_todo_before = f.read()

    checkpoint()

    canonical_path = os.path.join("project-docs", "devlogs", "nikhilsoman.md")
    assert os.path.exists(canonical_path)
    assert "Ship the thing" in open(canonical_path).read()
    assert open(checkout_todo).read() == checkout_todo_before
    assert not os.path.exists(os.path.join("project-docs", "devlogs", "nikhil.md"))
