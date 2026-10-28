"""One-shot ensure tick for the machine-scoped Vizor daemon.

Launchd and systemd start this with SYNLYNK_VIZOR_DAEMON=1 and cwd set to the
daemon home. It must not keep running.
"""
from __future__ import annotations

import json
import os


def main() -> int:
    os.environ.setdefault("SYNLYNK_VIZOR_DAEMON", "1")
    from synlynk.vizor_daemon import ensure

    result = ensure()
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
