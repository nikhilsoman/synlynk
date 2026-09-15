"""Unit tests for coldstart flows (wrapper for tests/test_coldstart.py)."""

from tests import test_coldstart as _src

for _name, _obj in list(_src.__dict__.items()):
    if _name.startswith("test_") and callable(_obj):
        _fn = type(_obj)(
            _obj.__code__,
            _obj.__globals__,
            _name,
            _obj.__defaults__,
            _obj.__closure__,
        )
        _fn.__module__ = __name__
        globals()[_name] = _fn
