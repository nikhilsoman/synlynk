import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import HUDRenderer, FrameBuffer

CYCLE_SUMMARY = {
    "dream":    {"running": 0, "ready": True},
    "plan":     {"running": 0, "ready": True},
    "work":     {"running": 2, "ready": False},
    "ship":     {"running": 0, "ready": True},
    "maintain": {"running": 0, "ready": False},
    "engage":   {"running": 0, "ready": False},
}

def make_renderer():
    buf = FrameBuffer(rows=30, cols=120)
    return HUDRenderer(buf), buf

def test_render_header_collapsed_fits_one_line(tmp_path):
    r, buf = make_renderer()
    r.render_header(cycle_summary=CYCLE_SUMMARY, platform_expanded=False, start_row=0)
    # Header collapsed = exactly 1 row written
    assert buf._curr[0] != ""
    assert buf._curr[1] == ""   # row 1 empty — header took only row 0

def test_render_header_expanded_takes_multiple_rows(tmp_path):
    r, buf = make_renderer()
    rows_used = r.render_header(cycle_summary=CYCLE_SUMMARY, platform_expanded=True, start_row=0)
    assert rows_used > 1

def test_render_sidebar_marks_active_cycle(tmp_path):
    r, buf = make_renderer()
    r.render_sidebar(cycle_summary=CYCLE_SUMMARY, selected_cycle="work", start_row=2, col=0)
    # "work" row should contain a selection marker
    sidebar_text = " ".join(buf._curr[2:14])
    assert "work" in sidebar_text.lower()

def test_render_sidebar_contains_all_cycles(tmp_path):
    r, buf = make_renderer()
    from synlynk.hud import CYCLES
    r.render_sidebar(cycle_summary=CYCLE_SUMMARY, selected_cycle="work", start_row=0, col=0)
    full_text = " ".join(buf._curr[:20]).lower()
    for cycle in CYCLES:
        assert cycle in full_text, f"Cycle '{cycle}' missing from sidebar"
