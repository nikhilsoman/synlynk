from pathlib import Path

from synlynk.standalone_venv import (
    create_standalone_release,
    activate_release_symlink,
    rollback_standalone_release,
)


def test_standalone_release_creation_and_atomic_swap(tmp_path):
    base_dir = tmp_path / ".synlynk"
    bin_dir = tmp_path / ".local" / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)

    rel_v1 = create_standalone_release("0.23.0", base_dir=base_dir)
    assert rel_v1.exists()
    launcher = activate_release_symlink(rel_v1, bin_dir=bin_dir)
    assert launcher.exists()
    assert (base_dir / "releases" / "current").resolve() == rel_v1.resolve()

    rel_v2 = create_standalone_release("0.24.0", base_dir=base_dir)
    activate_release_symlink(rel_v2, bin_dir=bin_dir)
    assert (base_dir / "releases" / "current").resolve() == rel_v2.resolve()

    # Test atomic rollback
    rolled_back_version = rollback_standalone_release(base_dir=base_dir, bin_dir=bin_dir)
    assert rolled_back_version == "0.23.0"
    assert (base_dir / "releases" / "current").resolve() == rel_v1.resolve()
