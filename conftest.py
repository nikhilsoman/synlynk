"""Initialize curses for tests that exercise pad-backed TUI rendering."""
import curses
import os
import signal


_CURSES_SIGNALS = [
    getattr(signal, name)
    for name in ("SIGWINCH", "SIGTSTP", "SIGTERM", "SIGINT")
    if hasattr(signal, name)
]


def ensure_curses_initialized():
    # curses.initscr() depends on TERM resolving to a valid terminfo entry.
    # CI runners don't reliably set TERM, which previously caused intermittent
    # "must call initscr() first" failures (issue #745) depending on the
    # runner's ambient TERM at the moment pytest started.
    os.environ.setdefault("TERM", "xterm")

    # In modern macOS (Darwin) and POSIX, curses.initscr() registers C-level
    # sigaction handlers for SIGWINCH, SIGTSTP, and SIGTERM. If a signal
    # arrives while the main thread is inside fork() or libc locking routines,
    # ncurses's signal handler invokes endwin() -> sprintf() -> localeconv_l(),
    # attempting to recursively acquire an os_unfair_lock, triggering an immediate
    # process abort (_os_unfair_lock_recursive_abort, issue #2486).
    # Save the existing signal handlers and restore them immediately.
    saved_handlers = {}
    for sig in _CURSES_SIGNALS:
        try:
            saved_handlers[sig] = signal.getsignal(sig)
        except (ValueError, OSError):
            pass

    scr = curses.initscr()

    for sig, handler in saved_handlers.items():
        try:
            signal.signal(sig, handler)
        except (ValueError, OSError):
            pass

    return scr


def pytest_sessionstart(session):
    ensure_curses_initialized()


def pytest_sessionfinish(session, exitstatus):
    try:
        curses.endwin()
    except curses.error:
        pass

