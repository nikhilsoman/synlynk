"""Lookup of harness name -> HarnessAdapter instance (gh:#1924)."""

from synlynk.harness_adapters.base import HarnessAdapter


_ADAPTERS: dict[str, HarnessAdapter] = {}


def register_adapter(name: str, adapter: HarnessAdapter) -> None:
    _ADAPTERS[name] = adapter


def get_adapter(name: str) -> HarnessAdapter:
    return _ADAPTERS[name]
