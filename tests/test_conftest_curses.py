import curses
import importlib.util
import os
import signal


def test_ensure_curses_initialized_restores_signal_handlers():
    """Test #2486: ensure curses initialization does not leave ncurses signal handlers active."""
    spec = importlib.util.spec_from_file_location("root_conftest", "conftest.py")
    root_conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_conftest)

    tracked_sigs = [
        getattr(signal, name)
        for name in ("SIGWINCH", "SIGTSTP", "SIGTERM", "SIGINT")
        if hasattr(signal, name)
    ]
    handlers_before = {s: signal.getsignal(s) for s in tracked_sigs}

    root_conftest.ensure_curses_initialized()

    handlers_after = {s: signal.getsignal(s) for s in tracked_sigs}
    assert handlers_after == handlers_before


def test_curses_pad_rendering_functions_after_initialization():
    """Verify curses pad allocation and string rendering continue to work."""
    spec = importlib.util.spec_from_file_location("root_conftest", "conftest.py")
    root_conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_conftest)

    root_conftest.ensure_curses_initialized()

    pad = curses.newpad(10, 80)
    assert pad is not None
    pad.addstr(0, 0, "synlynk-tui")
    rendered = pad.instr(0, 0, 11).decode("utf-8")
    assert rendered == "synlynk-tui"


def test_sigwinch_signal_delivery_safety():
    """Test that delivering SIGWINCH after curses initialization is safe."""
    sigwinch = getattr(signal, "SIGWINCH", None)
    if sigwinch is None:
        return

    spec = importlib.util.spec_from_file_location("root_conftest", "conftest.py")
    root_conftest = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(root_conftest)

    root_conftest.ensure_curses_initialized()

    # Sending SIGWINCH to self should not trigger ncurses endwin() recursion abort
    os.kill(os.getpid(), sigwinch)
