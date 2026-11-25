import json


def assistant(msg_id, model="claude-sonnet-5-5", ts="2026-11-24T10:00:00.000Z",
              i=10, o=20, cc=30, cr=40, session="s1"):
    return json.dumps({
        "type": "assistant", "timestamp": ts, "sessionId": session,
        "message": {"id": msg_id, "model": model, "usage": {
            "input_tokens": i, "output_tokens": o,
            "cache_creation_input_tokens": cc, "cache_read_input_tokens": cr}},
    })


def pr_link(pr, session="s1", ts="2026-11-24T10:05:00.000Z"):
    return json.dumps({"type": "pr-link", "sessionId": session, "prNumber": pr,
                       "prUrl": f"https://github.com/o/r/pull/{pr}", "timestamp": ts})


def write(path, lines):
    path.write_text("\n".join(lines) + "\n")
    return path
