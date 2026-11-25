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

TAG = "synlynk hook claude "


def _entry(event: str) -> dict:
    return {"hooks": [{"type": "command", "command": f"{TAG}{event}", "timeout": 10}]}


def merge_hooks(settings: dict) -> dict:
    import copy
    out = copy.deepcopy(settings)
    hooks = out.setdefault("hooks", {})
    for event in ("Stop", "SessionEnd"):
        groups = hooks.setdefault(event, [])
        if not any(h.get("command", "").startswith(TAG) for g in groups for h in g.get("hooks", [])):
            groups.append(_entry(event))
    return out


def remove_hooks(settings: dict) -> dict:
    import copy
    out = copy.deepcopy(settings)
    for event in list(out.get("hooks", {})):
        groups = [g for g in out["hooks"][event]
                  if not any(h.get("command", "").startswith(TAG) for h in g.get("hooks", []))]
        if groups:
            out["hooks"][event] = groups
        else:
            del out["hooks"][event]
    if not out.get("hooks"):
        out.pop("hooks", None)
    return out


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
