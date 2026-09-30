import sys
import types

from synlynk._lazy import pkg


def test_pkg_returns_attribute_from_synlynk_module():
    saved = sys.modules.get("synlynk")
    fake = types.ModuleType("synlynk")
    fake.SOME_CONST = "hello"
    sys.modules["synlynk"] = fake
    try:
        assert pkg("SOME_CONST") == "hello"
    finally:
        if saved is not None:
            sys.modules["synlynk"] = saved
        else:
            del sys.modules["synlynk"]


def test_pkg_returns_default_when_attribute_missing():
    saved = sys.modules.get("synlynk")
    fake = types.ModuleType("synlynk")
    sys.modules["synlynk"] = fake
    try:
        assert pkg("MISSING", "fallback") == "fallback"
        assert pkg("MISSING") is None
    finally:
        if saved is not None:
            sys.modules["synlynk"] = saved
        else:
            del sys.modules["synlynk"]


def test_pkg_returns_default_when_synlynk_not_imported_yet():
    saved = sys.modules.pop("synlynk", None)
    try:
        assert pkg("ANYTHING", "fallback") == "fallback"
        assert pkg("ANYTHING") is None
    finally:
        if saved is not None:
            sys.modules["synlynk"] = saved
