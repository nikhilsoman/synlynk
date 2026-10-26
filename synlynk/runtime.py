"""Runtime utilities for process isolation, tempdirs, and user UID boundaries."""

import os
from pathlib import Path


def get_user_tmp_dir(subdir: str = "") -> Path:
    """Return a user-isolated temporary directory (/tmp/synlynk-{uid}) with mode 0700.

    Ensures multi-user isolation on shared hosts so that separate user accounts
    do not collide on shared filenames or encounter permission lockouts.
    """
    uid = os.getuid() if hasattr(os, "getuid") else "default"
    base = Path(f"/tmp/synlynk-{uid}")
    base.mkdir(mode=0o700, parents=True, exist_ok=True)
    try:
        os.chmod(base, 0o700)
    except OSError:
        pass

    if subdir:
        target = base / subdir
        target.mkdir(mode=0o700, parents=True, exist_ok=True)
        try:
            os.chmod(target, 0o700)
        except OSError:
            pass
        return target

    return base
