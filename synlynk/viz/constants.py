"""Paths, ports, and agent names shared by the Vizor package.

Mutable bindings that the daemon and tests rebind (``VIZ_CACHE_DIR``,
``_get_db``) live on ``synlynk.viz`` itself. Readers that must observe those
rebinds go through ``_pkg()`` rather than this module.
"""

VIZ_CACHE_DIR = ".synlynk/viz-cache"
VIZ_NOTES_PATH = ".synlynk/viz-notes.json"
VIZ_META_PATH = ".synlynk/viz-meta.json"
VIZ_WORKSPACE_MAP_PATH = ".synlynk/vizor-workspace-map.json"
MEMORABLE_VIZOR_PORTS = [33333, 44444, 55555, 22222, 11111]
DEFAULT_PORT = MEMORABLE_VIZOR_PORTS[0]
_KNOWN_AGENTS = {"claude", "agy", "codex", "grok", "muse"}
