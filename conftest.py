"""Initialize curses for tests that exercise pad-backed TUI rendering."""
import curses
import os


def ensure_curses_initialized():
    # curses.initscr() depends on TERM resolving to a valid terminfo entry.
    # CI runners don't reliably set TERM, which previously caused intermittent
    # "must call initscr() first" failures (issue #745) depending on the
    # runner's ambient TERM at the moment pytest started.
    os.environ.setdefault("TERM", "xterm")
    return curses.initscr()


def pytest_sessionstart(session):
    ensure_curses_initialized()


def pytest_sessionfinish(session, exitstatus):
    try:
        curses.endwin()
    except curses.error:
        pass

