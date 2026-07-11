from synlynk import _recommend_handoff_agent


def test_task_to_cycle_uses_governs_keys(monkeypatch):
    import synlynk
    captured = {}

    class FakeConn:
        def execute(self, query, params):
            captured["cycle"] = params[0]

            class R:
                def fetchall(self):
                    return []

            return R()

    monkeypatch.setattr(
        "synlynk.status._classify_task_type", lambda prompt: "review", raising=False
    )
    _recommend_handoff_agent("review this PR", "codex", FakeConn())
    assert captured["cycle"] == "execute"
