"""Standalone venv release directories with atomic `current` symlink swapping.

Tier 4 of the install ladder: when neither `uv` nor `pipx` is available, synlynk
installs into a versioned, self-contained venv under `~/.synlynk/releases/v<version>`
and points an atomically-swapped `current` symlink at it. Rollback is therefore an
offline symlink swap, with no network or package manager involvement.
"""

import os
import venv
from pathlib import Path
from typing import Optional

DEFAULT_SYNLYNK_DIR = Path.home() / ".synlynk"
DEFAULT_BIN_DIR = Path.home() / ".local" / "bin"


def create_standalone_release(version: str, base_dir: Optional[Path] = None) -> Path:
    """Create (or reuse) a standalone venv for `version` and return its directory."""
    syn_dir = base_dir if base_dir is not None else DEFAULT_SYNLYNK_DIR
    release_dir = syn_dir / "releases" / f"v{version}"
    if release_dir.exists():
        return release_dir

    release_dir.parent.mkdir(parents=True, exist_ok=True)
    builder = venv.EnvBuilder(with_pip=True, symlinks=True)
    builder.create(release_dir)
    return release_dir


def activate_release_symlink(release_dir: Path, bin_dir: Optional[Path] = None) -> Path:
    """Point `releases/current` at `release_dir` atomically and expose the launcher."""
    releases_dir = release_dir.parent
    current_symlink = releases_dir / "current"

    # Atomic symlink replacement: build alongside, then rename over the old link.
    tmp_link = current_symlink.with_name("current.tmp")
    if tmp_link.is_symlink() or tmp_link.exists():
        tmp_link.unlink()
    os.symlink(release_dir, tmp_link)
    os.replace(tmp_link, current_symlink)

    target_bin = bin_dir if bin_dir is not None else DEFAULT_BIN_DIR
    target_bin.mkdir(parents=True, exist_ok=True)
    synlynk_bin = target_bin / "synlynk"

    release_bin = release_dir / "bin" / "synlynk"
    # Before the package itself is installed into the venv, write a thin launcher
    # so activation (and rollback) never depends on pip having run yet.
    if not release_bin.exists():
        release_bin.parent.mkdir(parents=True, exist_ok=True)
        py_exe = release_dir / "bin" / "python3"
        release_bin.write_text(
            f"#!{py_exe}\n"
            "import sys\n"
            "from synlynk import main\n"
            "if __name__ == '__main__':\n"
            "    sys.exit(main())\n"
        )
        release_bin.chmod(0o755)

    if synlynk_bin.is_symlink() or synlynk_bin.exists():
        synlynk_bin.unlink()
    os.symlink(release_bin, synlynk_bin)
    return synlynk_bin


def rollback_standalone_release(
    base_dir: Optional[Path] = None, bin_dir: Optional[Path] = None
) -> Optional[str]:
    """Swap `current` back to the newest release that is not currently active.

    Returns the version string rolled back to, or None when there is nothing to
    roll back (no releases directory, no active release, or no prior version).
    """
    syn_dir = base_dir if base_dir is not None else DEFAULT_SYNLYNK_DIR
    releases_dir = syn_dir / "releases"
    if not releases_dir.exists():
        return None

    versions = sorted(
        (
            d
            for d in releases_dir.iterdir()
            if d.is_dir() and d.name.startswith("v") and not d.is_symlink()
        ),
        key=lambda p: p.name,
    )

    current_link = releases_dir / "current"
    if not current_link.exists():
        return None

    current_target = current_link.resolve()
    prior_versions = [v for v in versions if v.resolve() != current_target]
    if not prior_versions:
        return None

    target_prev = prior_versions[-1]
    activate_release_symlink(target_prev, bin_dir=bin_dir)
    return target_prev.name[1:]
