import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from synlynk.hud import LiveRenderer, FrameBuffer

ACTIVE_JOBS = [
    {"id": "job-aaa", "agent": "codex", "task": "feat/bs20-deep-scan",
     "cycle": "work", "status": "running", "elapsed_s": 252},
]

def make_live():
    buf = FrameBuffer(rows=24, cols=100)
    return LiveRenderer(buf), buf

def test_live_renders_job_cards():
    r, buf = make_live()
    r.render(active_jobs=ACTIVE_JOBS, show_all=False)
    full = " ".join(buf._curr).lower()
    assert "codex" in full
    assert "feat/bs20-deep-scan" in full

def test_live_shows_empty_state_when_no_jobs():
    r, buf = make_live()
    r.render(active_jobs=[], show_all=False)
    full = " ".join(buf._curr).lower()
    assert "no" in full and ("active" in full or "running" in full)

def test_live_header_shows_live_indicator():
    r, buf = make_live()
    r.render(active_jobs=ACTIVE_JOBS, show_all=False)
    assert "live" in buf._curr[0].lower() or "◉" in buf._curr[0]

def test_live_footer_shows_count_and_hint():
    r, buf = make_live()
    r.render(active_jobs=ACTIVE_JOBS, show_all=False)
    footer = buf._curr[-2] + buf._curr[-1]
    # Footer should contain count and refresh/quit hints
    assert "1" in footer or "running" in footer.lower()
