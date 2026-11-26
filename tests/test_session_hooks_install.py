from synlynk import session_hooks as sh
from tests.test_native_capture_ledger import conn  # noqa: F401

EXISTING = {"hooks": {"Stop": [{"hooks": [{"type": "command", "command": "bash /h/auto-checkpoint-docs.sh"}]}],
                      "PreCompact": [{"hooks": [{"type": "command", "command": "bash /h/x.sh"}]}]}, "theme": "dark"}


def test_merge_preserves_existing_hooks_and_other_keys():
    out = sh.merge_hooks(EXISTING)
    cmds = [h["command"] for g in out["hooks"]["Stop"] for h in g["hooks"]]
    assert "bash /h/auto-checkpoint-docs.sh" in cmds
    assert any(c.startswith("synlynk hook claude Stop") for c in cmds)
    assert any(h["command"].startswith("synlynk hook claude SessionEnd") for g in out["hooks"]["SessionEnd"] for h in g["hooks"])
    assert out["theme"] == "dark" and out["hooks"]["PreCompact"] == EXISTING["hooks"]["PreCompact"]


def test_merge_is_idempotent():
    once = sh.merge_hooks(EXISTING)
    assert sh.merge_hooks(once) == once


def test_remove_deletes_only_synlynk_entries():
    assert sh.remove_hooks(sh.merge_hooks(EXISTING)) == EXISTING


def test_inputs_are_not_mutated():
    import copy
    snap = copy.deepcopy(EXISTING)
    sh.merge_hooks(EXISTING)
    assert EXISTING == snap


def test_hook_commands_have_a_timeout():
    out = sh.merge_hooks({})
    assert all(h["timeout"] <= 10 for g in out["hooks"]["Stop"] for h in g["hooks"])
