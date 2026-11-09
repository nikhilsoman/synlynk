def test_check_dedup_flags_similar_open_issue(monkeypatch):
    from synlynk import upstream_dedup_gate

    def fake_search(query):
        return [{"number": 2139, "title": "Agy charter drift", "state": "open"}]

    monkeypatch.setattr(upstream_dedup_gate, "_search_issues", fake_search)
    result = upstream_dedup_gate.check_dedup("Agy charter drift on activation")
    assert result["has_candidate_duplicate"] is True
    assert result["candidates"][0]["number"] == 2139


def test_check_dedup_clean_when_no_matches(monkeypatch):
    from synlynk import upstream_dedup_gate

    monkeypatch.setattr(upstream_dedup_gate, "_search_issues", lambda query: [])
    result = upstream_dedup_gate.check_dedup("totally novel capability request")
    assert result["has_candidate_duplicate"] is False
    assert result["candidates"] == []


def test_check_dedup_ignores_closed_issues(monkeypatch):
    from synlynk import upstream_dedup_gate

    monkeypatch.setattr(
        upstream_dedup_gate, "_search_issues",
        lambda query: [{"number": 1, "title": "old thing", "state": "closed"}],
    )
    result = upstream_dedup_gate.check_dedup("old thing")
    assert result["has_candidate_duplicate"] is False
