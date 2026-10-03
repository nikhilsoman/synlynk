"""Lookup of harness name -> HarnessAdapter instance (gh:#1924)."""

from synlynk.harness_adapters.base import HarnessAdapter
from synlynk.harness_adapters.codex import CodexAdapter
from synlynk.harness_adapters.grok import GrokAdapter
from synlynk.harness_adapters.legacy import LegacyAdapter


_ADAPTERS: dict[str, HarnessAdapter] = {}


def register_adapter(name: str, adapter: HarnessAdapter) -> None:
    _ADAPTERS[name] = adapter


def get_adapter(name: str) -> HarnessAdapter:
    return _ADAPTERS[name]


register_adapter("codex", CodexAdapter())
register_adapter("grok", GrokAdapter())
for _name in ("agy", "claude", "local"):
    register_adapter(_name, LegacyAdapter(agent=_name))
