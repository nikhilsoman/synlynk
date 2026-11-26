from datetime import datetime, timezone
import pytest

from synlynk.maintainer import (
    triage_sentinel_alerts,
    format_triage_issue,
    probe_reproduction,
    cluster_open_issues,
    is_issue_remediated,
)


def test_triage_sentinel_alerts_groups_and_ranks_by_severity_and_frequency(tmp_path):
    path = tmp_path / "sentinel.md"
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    path.write_text(
        "# Sentinel Alerts\n"
        f"- [CRITICAL] [{now}] SEV1_FAULT: Crash during fork [occurrences: 2; first seen: {now}; last seen: {now}]\n"
        f"- [WARN] [{now}] TOKEN_BLOAT: High tokens [occurrences: 5; first seen: {now}; last seen: {now}]\n"
        f"- [INFO] [{now}] NOTICE: Routine pulse [occurrences: 1; first seen: {now}; last seen: {now}]\n"
    )

    groups = triage_sentinel_alerts(path=str(path), max_age_days=7)
    assert len(groups) == 3

    # CRITICAL should rank first despite lower count
    assert groups[0]["code"] == "SEV1_FAULT"
    assert groups[0]["severity"] == "CRITICAL"
    assert groups[0]["total_occurrences"] == 2

    # WARN should rank second with 5 occurrences
    assert groups[1]["code"] == "TOKEN_BLOAT"
    assert groups[1]["severity"] == "WARN"
    assert groups[1]["total_occurrences"] == 5


def test_format_triage_issue_contains_standard_sections():
    group = {
        "fingerprint": "CRITICAL:SEV1_FAULT",
        "severity": "CRITICAL",
        "code": "SEV1_FAULT",
        "total_occurrences": 3,
        "first_seen": "2026-10-25 10:00:00 UTC",
        "last_seen": "2026-10-25 12:00:00 UTC",
        "sample_messages": ["Crash during fork in JWT minting"],
    }
    body = format_triage_issue(group)
    assert "[Maintainer Triage] SEV1_FAULT" in body
    assert "## Intent" in body
    assert "## Context" in body
    assert "## Reproduction Recipe" in body
    assert "## Acceptance Criteria" in body
    assert "CRITICAL:SEV1_FAULT" in body
    assert "Crash during fork in JWT minting" in body


def test_probe_reproduction_executes_check(tmp_path):
    group = {
        "code": "SEV1_FAULT",
        "severity": "CRITICAL",
        "fingerprint": "CRITICAL:SEV1_FAULT",
    }
    res = probe_reproduction(group, workspace_root=str(tmp_path))
    assert isinstance(res, dict)
    assert "reproduced" in res
    assert "output" in res

def test_cluster_open_issues_uses_repo_taxonomy_file(tmp_path, monkeypatch):
    import json
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "maintainer_taxonomy.json").write_text(json.dumps({
        "schema_version": 1,
        "cluster_keywords": {"video": ["ffmpeg", "transcode"]},
        "remediation_topics": [],
    }))
    monkeypatch.chdir(tmp_path)

    issues = [{"number": 1, "title": "ffmpeg transcode crashes on odd framerates", "labels": []}]
    clustered = cluster_open_issues(issues)
    assert "video" in clustered
    assert clustered["video"][0]["number"] == 1


def test_is_issue_remediated_uses_repo_remediation_topics(tmp_path, monkeypatch):
    import json
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "maintainer_taxonomy.json").write_text(json.dumps({
        "schema_version": 1,
        "cluster_keywords": {},
        "remediation_topics": ["frame drop"],
    }))
    monkeypatch.chdir(tmp_path)

    remediated = is_issue_remediated(
        issue_text="frame drop bug in the renderer",
        commit_messages=["fix: resolve frame drop issue in renderer path"],
    )
    assert remediated is True


def test_select_proposal_target_sums_weighted_evidence_across_tiers(monkeypatch):
    from synlynk.maintainer import Evidence, select_proposal_target

    open_proposals = [{"proposal_id": "p1", "touched_files": ["synlynk/maintainer.py"]}]
    candidate = {"touched_files": ["synlynk/maintainer_registry.py"]}

    def fake_collect_evidence(candidate, proposal, repo_root="."):
        return [
            Evidence(tier="code_graph", weight=0.6, detail="distance-1 adjacency"),
            Evidence(tier="doc_graph", weight=0.3, detail="shared doc docs/a.md"),
        ]

    monkeypatch.setattr("synlynk.maintainer._collect_evidence", fake_collect_evidence)

    target, tier_provenance = select_proposal_target(candidate, open_proposals, repo_root=".")
    assert target == "p1"
    assert tier_provenance == ["code_graph", "doc_graph"]


def test_select_proposal_target_respects_join_threshold(monkeypatch, tmp_path):
    from synlynk.maintainer import Evidence, select_proposal_target

    (tmp_path / ".synlynk").mkdir()
    open_proposals = [{"proposal_id": "p1", "touched_files": ["unrelated.py"]}]
    candidate = {"touched_files": ["another.py"]}

    monkeypatch.setattr(
        "synlynk.maintainer._collect_evidence",
        lambda candidate, proposal, repo_root=".": [Evidence(tier="keyword", weight=0.1, detail="weak match")],
    )

    target, tier_provenance = select_proposal_target(candidate, open_proposals, repo_root=str(tmp_path))
    assert target is None
    assert tier_provenance == []


def test_select_proposal_target_tie_break_prefers_older_proposal_then_lexical_id(monkeypatch, tmp_path):
    from synlynk.maintainer import Evidence, select_proposal_target

    (tmp_path / ".synlynk").mkdir()
    open_proposals = [
        {"proposal_id": "p2", "touched_files": [], "created_at": "2026-11-20T00:00:00Z"},
        {"proposal_id": "p1", "touched_files": [], "created_at": "2026-11-20T00:00:00Z"},
    ]
    candidate = {"touched_files": []}

    monkeypatch.setattr(
        "synlynk.maintainer._collect_evidence",
        lambda candidate, proposal, repo_root=".": [Evidence(tier="keyword", weight=0.9, detail="tied match")],
    )

    target, _ = select_proposal_target(candidate, open_proposals, repo_root=str(tmp_path))
    assert target == "p1"  # same created_at -> lexical proposal_id tie-break


def test_select_proposal_target_degrades_gracefully_on_non_code_dominant_workspace(monkeypatch, tmp_path):
    """A workspace with mostly non-source files (e.g. a content/doc-heavy
    rxcc/vdowrx/Hitchcock-style workspace) must not raise -- _collect_evidence
    itself is responsible for returning [] per tier it can't evaluate, and
    select_proposal_target must handle an all-empty-evidence set without error."""
    from synlynk.maintainer import select_proposal_target

    (tmp_path / ".synlynk").mkdir()
    open_proposals = [{"proposal_id": "p1", "touched_files": ["content/episode-12.fcpxml"]}]
    candidate = {"touched_files": ["content/episode-13.fcpxml"]}

    # No monkeypatch of _collect_evidence here: exercise the real function
    # against files with no code-graph or doc-graph nodes at all.
    target, tier_provenance = select_proposal_target(candidate, open_proposals, repo_root=str(tmp_path))
    assert target is None
    assert tier_provenance == []


def test_collect_evidence_resolves_code_graph_tier_from_real_graph_json(tmp_path):
    """DECIDE panel re-review 2026-11-24 (Codex): proves the unmocked
    _collect_evidence actually resolves a code_graph Evidence record against
    a real .synlynk/graphify-out/graph.json, not a monkeypatched stand-in."""
    import json
    from synlynk.maintainer import _collect_evidence

    graphify_dir = tmp_path / ".synlynk" / "graphify-out"
    graphify_dir.mkdir(parents=True)
    (graphify_dir / "graph.json").write_text(json.dumps({
        "nodes": [
            {"id": "n1", "file": "synlynk/a.py"},
            {"id": "n2", "file": "synlynk/b.py"},
        ],
        "edges": [{"source": "n1", "target": "n2"}],
    }))

    candidate = {"touched_files": ["synlynk/a.py"]}
    proposal = {"touched_files": ["synlynk/b.py"]}

    evidence = _collect_evidence(candidate, proposal, repo_root=str(tmp_path))
    code_graph_evidence = [e for e in evidence if e.tier == "code_graph"]
    assert len(code_graph_evidence) == 1
    assert code_graph_evidence[0].weight == 0.6  # proximal_selection default distance_1 weight


def test_collect_evidence_resolves_doc_graph_tier_from_real_docgraph_json(tmp_path):
    """Same proof as above, for the doc_graph tier against a real
    .synlynk/docgraph.json (reverse_code_index), not a mocked DocGraph."""
    import json
    from synlynk.docgraph import DocGraph
    from synlynk.maintainer import _collect_evidence

    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    docgraph = DocGraph(reverse_code_index={
        "synlynk/a.py": ["docs/superpowers/specs/shared-spec.md"],
        "synlynk/b.py": ["docs/superpowers/specs/shared-spec.md"],
    })
    (synlynk_dir / "docgraph.json").write_text(json.dumps(docgraph.to_dict()))

    candidate = {"touched_files": ["synlynk/a.py"]}
    proposal = {"touched_files": ["synlynk/b.py"]}

    evidence = _collect_evidence(candidate, proposal, repo_root=str(tmp_path))
    doc_graph_evidence = [e for e in evidence if e.tier == "doc_graph"]
    assert len(doc_graph_evidence) == 1
    assert doc_graph_evidence[0].weight == 0.4  # proximal_selection default shared_doc weight


def test_wake_cycle_actions_are_registered_in_registry():
    import json
    from synlynk.maintainer_registry import registered_actions
    import synlynk.maintainer  # noqa: F401 -- re-import triggers registration if cleared
    actions = registered_actions()
    assert set(actions.keys()) >= {"maintainer:sentinel_triage", "maintainer:backlog_burndown", "maintainer:mesh_sweep"}


def test_run_maintainer_wake_cycle_dry_run_stages_without_side_effects(tmp_path, monkeypatch):
    import json
    from synlynk.maintainer import run_maintainer_wake_cycle
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )
    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", lambda **kwargs: 0)

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    assert result["sentinel_triage"]["mode"] == "dry_run"
    assert result["backlog_burndown"]["mode"] == "dry_run"
    assert result["mesh_sweep"]["mode"] == "dry_run"


def test_run_maintainer_wake_cycle_skips_disabled_actions(tmp_path, monkeypatch):
    import json
    from synlynk.maintainer import run_maintainer_wake_cycle
    monkeypatch.chdir(tmp_path)
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text('{"maintainer_autonomy": {"mesh_sweep": {"enabled": false}}}')

    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )

    def _should_not_run(**kwargs):
        raise AssertionError("mesh_sweep must not run when disabled")

    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", _should_not_run)

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    assert result["mesh_sweep"]["skipped"] is True


def test_run_maintainer_wake_cycle_critical_finding_bypasses_cluster_minimum(tmp_path, monkeypatch):
    import json
    from synlynk.maintainer import run_maintainer_wake_cycle
    monkeypatch.chdir(tmp_path)
    synlynk_dir = tmp_path / ".synlynk"
    synlynk_dir.mkdir()
    (synlynk_dir / "config.json").write_text(json.dumps({
        "maintainer_autonomy": {"sentinel_triage": {"mode": "promote"}}
    }))

    critical_group = {
        "fingerprint": "CRITICAL:SEV1_FAULT",
        "severity": "CRITICAL",
        "code": "SEV1_FAULT",
        "total_occurrences": 1,
        "sample_messages": ["crash"],
    }
    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [critical_group])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )
    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", lambda **kwargs: 0)
    monkeypatch.setattr(
        "synlynk.maintainer._ensure_github_issue_for_story",
        lambda story, repo_root=".", cycle_id="": 999,
    )

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    proposals = result["sentinel_triage"]["proposals"]
    assert len(proposals) == 1
    assert proposals[0]["severity"] == "critical"
    assert proposals[0]["stories"][0]["github_issue"] == 999


def test_run_maintainer_wake_cycle_persists_proposals_across_all_actions(tmp_path, monkeypatch):
    from synlynk.maintainer import run_maintainer_wake_cycle, load_maintainer_proposals

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    sentinel_group = {
        "fingerprint": "ERROR:E501", "severity": "ERROR", "code": "E501",
        "total_occurrences": 3, "sample_messages": ["line too long"],
    }
    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [sentinel_group])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {
            "dry_run": True,
            "sprint_staged": {
                "domain": "backend", "count": 3,
                "title": "Backlog Burndown Sprint: backend (3 issues)",
                "issue_numbers": [1, 2, 3],
            },
        },
    )
    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", lambda **kwargs: 0)

    run_maintainer_wake_cycle(repo_root=str(tmp_path))

    persisted = load_maintainer_proposals(repo_root=str(tmp_path))
    sources = {p["source"] for p in persisted}
    assert sources == {"maintainer:sentinel_triage", "maintainer:backlog_burndown"}
    actions = {p["action"] for p in persisted}
    assert actions == {"sentinel_triage", "backlog_burndown"}


def test_load_maintainer_proposals_returns_empty_list_when_file_missing(tmp_path):
    from synlynk.maintainer import load_maintainer_proposals

    assert load_maintainer_proposals(repo_root=str(tmp_path)) == []


def test_ensure_github_issue_for_story_stages_without_host_fallback_when_no_qa_token(tmp_path):
    from synlynk.maintainer import _ensure_github_issue_for_story

    (tmp_path / ".synlynk").mkdir()
    result = _ensure_github_issue_for_story({"title": "finding"}, repo_root=str(tmp_path))
    assert result is None


def _fake_qa_token(tmp_path):
    app_dir = tmp_path / ".synlynk" / "github_apps" / "qa"
    app_dir.mkdir(parents=True)
    (app_dir / "token.json").write_text("{}")


def test_ensure_github_issue_for_story_writes_audit_entry_before_external_write(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _ensure_github_issue_for_story, _read_promotion_audit_log

    _fake_qa_token(tmp_path)

    def _boom(*args, **kwargs):
        raise RuntimeError("network down mid-write")

    monkeypatch.setattr("subprocess.run", _boom)

    with pytest.raises(RuntimeError):
        _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")

    entries = _read_promotion_audit_log(str(tmp_path))
    assert any(e["status"] == "attempting" and e["signature"] == "s1" for e in entries)
    assert not any(e["status"] == "completed" for e in entries)


def test_ensure_github_issue_for_story_dedupes_against_audit_log(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _append_promotion_audit_log, _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)
    _append_promotion_audit_log(str(tmp_path), {
        "cycle_id": "cycle-0", "signature": "s1", "status": "completed",
        "ts": 0, "issue_number": 42,
    })

    def _should_not_run(*args, **kwargs):
        raise AssertionError("must not call gh for an already-promoted signature")

    monkeypatch.setattr("subprocess.run", _should_not_run)

    result = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    assert result is None


def test_ensure_github_issue_for_story_dedupes_against_open_github_issues(tmp_path, monkeypatch):
    import json
    import subprocess
    from synlynk.maintainer import _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)

    def _fake_run(cmd, **kwargs):
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout=json.dumps(
                [{"body": "some finding\n\n<!-- finding-signature: s1 -->"}]
            ), stderr="")
        raise AssertionError("must not call gh issue create for an already-open signature")

    monkeypatch.setattr("subprocess.run", _fake_run)

    result = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    assert result is None


def test_ensure_github_issue_for_story_caps_promotions_per_cycle(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)
    monkeypatch.setattr("synlynk.maintainer._MAX_PROMOTIONS_PER_CYCLE", 2)

    created = []

    def _fake_run(cmd, **kwargs):
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        created.append(cmd)
        return subprocess.CompletedProcess(cmd, 0, stdout="Created issue #1", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    results = [
        _ensure_github_issue_for_story({"story_id": f"s{i}", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
        for i in range(3)
    ]
    assert results[0] is not None
    assert results[1] is not None
    assert results[2] is None  # 3rd write exceeds the per-cycle cap of 2
    assert len(created) == 2


def test_ensure_github_issue_for_story_rate_limits_across_cycles(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)
    monkeypatch.setattr("synlynk.maintainer._MAX_PROMOTIONS_PER_CYCLE", 10)
    monkeypatch.setattr("synlynk.maintainer._MAX_PROMOTIONS_PER_WINDOW", 1)

    def _fake_run(cmd, **kwargs):
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="Created issue #1", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    first = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    second = _ensure_github_issue_for_story({"story_id": "s2", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-2")
    assert first is not None
    assert second is None  # window budget of 1 already spent by the first write


def test_ensure_github_issue_for_story_cap_counts_incomplete_attempts(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _append_promotion_audit_log, _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)
    monkeypatch.setattr("synlynk.maintainer._MAX_PROMOTIONS_PER_CYCLE", 2)
    _append_promotion_audit_log(str(tmp_path), {
        "cycle_id": "cycle-1", "signature": "crashed-sig", "status": "attempting", "ts": 0,
    })

    def _fake_run(cmd, **kwargs):
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="Created issue #1", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    first = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    second = _ensure_github_issue_for_story({"story_id": "s2", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    assert first is not None
    assert second is None  # the stale attempting entry + first write already filled the cap of 2


def test_ensure_github_issue_for_story_parses_issue_number_from_url_stdout(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)

    def _fake_run(cmd, **kwargs):
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        return subprocess.CompletedProcess(
            cmd, 0, stdout="https://github.com/acme/widget/issues/123\n", stderr="",
        )

    monkeypatch.setattr("subprocess.run", _fake_run)

    result = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    assert result == 123


def test_ensure_github_issue_for_story_writes_completed_entry_even_if_number_parse_fails(tmp_path, monkeypatch):
    import subprocess
    from synlynk.maintainer import _ensure_github_issue_for_story, _read_promotion_audit_log

    _fake_qa_token(tmp_path)

    def _fake_run(cmd, **kwargs):
        if "list" in cmd:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="no issue number here", stderr="")

    monkeypatch.setattr("subprocess.run", _fake_run)

    result = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-1")
    assert result is None  # number unknown, but the write still succeeded
    entries = _read_promotion_audit_log(str(tmp_path))
    assert any(e["status"] == "completed" and e["signature"] == "s1" for e in entries)


def test_ensure_github_issue_for_story_blocks_retry_while_attempt_in_flight(tmp_path, monkeypatch):
    import time
    import subprocess
    from synlynk.maintainer import _append_promotion_audit_log, _ensure_github_issue_for_story

    _fake_qa_token(tmp_path)
    _append_promotion_audit_log(str(tmp_path), {
        "cycle_id": "cycle-1", "signature": "s1", "status": "attempting", "ts": time.time(),
    })

    def _should_not_run(*args, **kwargs):
        raise AssertionError("must not call gh while a same-signature attempt is in flight")

    monkeypatch.setattr("subprocess.run", _should_not_run)

    result = _ensure_github_issue_for_story({"story_id": "s1", "title": "t"}, repo_root=str(tmp_path), cycle_id="cycle-2")
    assert result is None


def test_run_maintainer_wake_cycle_dry_run_stories_carry_github_issue_placeholder(tmp_path, monkeypatch):
    from synlynk.maintainer import run_maintainer_wake_cycle

    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir()

    critical_group = {
        "fingerprint": "CRITICAL:SEV1_FAULT", "severity": "CRITICAL", "code": "SEV1_FAULT",
        "total_occurrences": 1, "sample_messages": ["crash"],
    }
    monkeypatch.setattr("synlynk.maintainer.triage_sentinel_alerts", lambda **kwargs: [critical_group])
    monkeypatch.setattr(
        "synlynk.maintainer.run_backlog_burndown_sweep",
        lambda **kwargs: {"closed": [], "sprint_staged": None, "clustered": {}},
    )
    monkeypatch.setattr("synlynk.maintainer.cmd_maintainer_sweep", lambda **kwargs: 0)

    result = run_maintainer_wake_cycle(repo_root=str(tmp_path))
    story = result["sentinel_triage"]["proposals"][0]["stories"][0]
    assert "github_issue" in story
    assert story["github_issue"] is None


