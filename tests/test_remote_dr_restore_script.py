from pathlib import Path


SCRIPT = Path(__file__).parents[1] / "scripts" / "verify-dr-restore-remote.sh"


def test_remote_dr_restore_script_runs_read_only_checks_on_remote_node():
    content = SCRIPT.read_text()

    assert "ssh" in content
    assert "synlynk state inventory --all" in content
    assert "synlynk status" in content
    assert "synlynk checkpoint" in content
    assert "--apply" not in content


def test_remote_dr_restore_script_requires_remote_and_canonical_state_arguments():
    content = SCRIPT.read_text()

    assert 'REMOTE=' in content
    assert 'CANONICAL_STATE=' in content
    assert 'PRODUCT_SLUG=' in content
    assert 'PRODUCT_ID=' in content
    assert 'SNAPSHOT=' in content
