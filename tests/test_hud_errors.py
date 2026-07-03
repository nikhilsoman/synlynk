import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.hud import FrameBuffer, HUDRenderer


def test_render_error_shows_message():
    buf = FrameBuffer(rows=10, cols=80)
    r = HUDRenderer(buf)
    r.render_error("state.db not found -- run synlynk scan first")
    full = " ".join(buf._curr).lower()
    assert "not found" in full or "scan" in full


def test_narrow_terminal_shows_warning():
    buf = FrameBuffer(rows=10, cols=55)
    r = HUDRenderer(buf)
    r.render_narrow_warning(cols=55)
    full = " ".join(buf._curr).lower()
    assert "narrow" in full or "widen" in full or "wide" in full
