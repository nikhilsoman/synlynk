"""Session-hook dispatcher: `synlynk hook <agent> <event>` reads the hook payload on stdin."""
import json
import os
from pathlib import Path

ERROR_LOG = Path(os.path.expanduser("~/.synlynk/native_capture_errors.log"))


def _log(msg: str) -> None:
    try:
        ERROR_LOG.parent.mkdir(parents=True, exist_ok=True)
        with open(ERROR_LOG, "a") as f:
            f.write(msg.replace("\n", " ")[:300] + "\n")
    except OSError:
        pass


STOP_BUDGET_S = 0.15        # Stop must stay well under the 200 ms spec budget
SESSION_END_BUDGET_S = 5.0  # below the 10 s hook timeout; leftover work is finished by the sweep


def _get_conn():
    from synlynk import _get_db

    return _get_db()


def _cost_capture(payload: dict, final: bool) -> None:
    from synlynk import native_capture as nc

    nc.capture(_get_conn(), payload["session_id"], payload["transcript_path"], final=final,
               budget_s=SESSION_END_BUDGET_S if final else STOP_BUDGET_S)


_HANDLERS = {("claude", "Stop"): [("cost_capture", False)], ("claude", "SessionEnd"): [("cost_capture", True)]}


def run(agent: str, event: str, stdin) -> int:
    try:
        payload = json.load(stdin)
    except Exception as exc:  # garbage input must never fail the session
        _log(f"hook {agent}/{event}: unreadable payload ({type(exc).__name__})")
        return 0
    for name, final in _HANDLERS.get((agent, event), []):
        try:
            if name == "cost_capture":
                _cost_capture(payload, final)
        except Exception as exc:
            _log(f"hook {agent}/{event} {name}: {type(exc).__name__}")
    return 0
