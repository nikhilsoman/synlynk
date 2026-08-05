"""Initialize curses for tests that exercise pad-backed TUI rendering."""
import curses


def pytest_sessionstart(session):
    try:
        curses.initscr()
    except curses.error:
        pass


def pytest_sessionfinish(session, exitstatus):
    try:
        curses.endwin()
    except curses.error:
        pass
