"""Late-binding lookup into the lazily populated :mod:`synlynk` namespace.

``synlynk.__init__`` populates its namespace lazily via
``_load_legacy_imports``, so command modules must defer symbol lookup until
call time to avoid circular imports.
"""

import sys


def pkg(name: str, default=None):
    package = sys.modules.get("synlynk")
    if package is None:
        return default
    return getattr(package, name, default)
