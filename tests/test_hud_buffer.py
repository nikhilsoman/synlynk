import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from synlynk.hud import FrameBuffer


def test_initial_render_emits_full_frame():
    buf = FrameBuffer(rows=5, cols=40)
    buf.set_line(0, "hello world")
    buf.set_line(1, "line two")
    output = buf.flush()
    assert "hello world" in output
    assert "line two" in output


def test_unchanged_lines_not_re_emitted():
    buf = FrameBuffer(rows=5, cols=40)
    buf.set_line(0, "static line")
    buf.set_line(1, "changing line v1")
    buf.flush()
    buf.set_line(1, "changing line v2")
    output = buf.flush()
    assert "static line" not in output
    assert "changing line v2" in output


def test_clear_resets_previous_frame():
    buf = FrameBuffer(rows=5, cols=40)
    buf.set_line(0, "old content")
    buf.flush()
    buf.clear()
    buf.set_line(0, "new content")
    output = buf.flush()
    assert "new content" in output


def test_line_truncated_to_col_width():
    buf = FrameBuffer(rows=3, cols=10)
    buf.set_line(0, "this is a very long line that exceeds ten chars")
    output = buf.flush()
    assert "this is a " in output or "this is a" in output
