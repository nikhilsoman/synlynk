"""#291: agent_quotas populated from telemetry + synlynk quota CLI."""

import json
import os
import sqlite3
import time
from pathlib import Path
import importlib.util
import subprocess

import pytest


@pytest.fixture
def project_dir(tmp_path, monkeypatch):
    """Minimal initialized project cwd for quota helpers."""
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({
        "schema_version": 1,
        "budget": {
            "limit_usd": 10.0,
            "limit_requests": 100,
            "quota_limits": {
                "5h": {"tokens": 200_000, "requests": 50},
                "hourly": {"tokens": 100_000, "requests": 20},
                "daily": {"tokens": 500_000, "requests": 100},
                "weekly": {"tokens": 2_000_000, "requests": 500},
                "monthly": {"tokens": 5_000_000, "requests": 2000},
            },
        },
    }))
    return tmp_path


def _write_telemetry(project_dir, events):
    (project_dir / ".synlynk" / "telemetry.json").write_text(json.dumps(events))


def _write_repair_config(tmp_path, config):
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps(config))


def _seed_harness_record(db, *, agent="agy", compliance_status="ok", last_probe_at=None):
    from synlynk import _migrate_db

    _migrate_db(db)
    last_probe_at = last_probe_at or time.strftime(
        "%Y-%m-%dT%H:%M:%SZ", time.localtime(time.time())
    )
    db.execute(
        """
        INSERT INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (agent, agent, "1.0.0", compliance_status, "{}", "{}", "cap-hash", last_probe_at),
    )
    db.commit()


def test_pr_review_discipline_instructions_say_synlynk_pr_check_without_pr_number():
    """Documented PR check usage must match the zero-argument CLI parser."""
    from synlynk.cli import build_parser
    from synlynk.probe import _PR_REVIEW_SOP, _repair_pr_review_sop

    parser = build_parser()
    parser.parse_args(["pr", "check"])
    with pytest.raises(SystemExit):
        parser.parse_args(["pr", "check", "711"])

    for sop in (_PR_REVIEW_SOP, _repair_pr_review_sop({"roles": {}})):
        assert "synlynk pr check <pr#>" not in sop
        assert "synlynk pr check`" in sop
        assert "From within the PR's own checked-out worktree/branch" in sop


def test_repair_sops_only_injects_synlynks_own_h_repo_specific_config(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {
                "agy": ["pm", "review"],
                "codex": ["implement", "test", "refactor"],
            },
            "workgroup_agents": ["agy", "codex"],
            "branch_conventions": {
                "agy": "feat/agy/<description>",
                "codex": "feat/codex/<description>",
            },
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "GEMINI.md").write_text("# Gemini\n")
    (tmp_path / "AGENTS.md").write_text("# Codex\n")

    import synlynk as sl

    sl._repair_sops_only(dry_run=False)

    gemini = (tmp_path / "GEMINI.md").read_text()
    agents = (tmp_path / "AGENTS.md").read_text()

    assert "escalate to Agy." in gemini
    assert "`feat/agy/<description>`" in gemini
    assert "| pm / review | Agy | pm, review |" in gemini
    assert "| implement / test / refactor | Codex | implement, test, refactor |" in gemini

    assert "escalate to Agy." in agents
    assert "`feat/codex/<description>`" in agents
    assert "| pm / review | Agy | pm, review |" in agents


def test_repair_sops_only_injects_synlynks_own_h_generic_branch_fallback(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {"claude": ["pm", "review"]},
            "workgroup_agents": ["claude"],
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")

    import synlynk as sl

    sl._repair_sops_only(dry_run=False)

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "Use the repo's documented task-scoped branch pattern" in content
    assert "feat/<agent>/<description>" not in content
    assert "escalate to Claude." in content


def test_repair_sops_only_injects_synlynks_own_h_default_config_keeps_current_shape(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {
                "claude": ["pm", "review", "deploy"],
                "agy": ["implement", "test", "css", "templates", "content"],
                "codex": ["implement", "test", "refactor"],
                "grok": ["implement", "test", "canvas", "js", "infra"],
            },
            "workgroup_agents": ["claude", "agy", "codex", "grok"],
            "branch_convention": "feat/<description>",
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text("# Claude\n")

    import synlynk as sl

    sl._repair_sops_only(dry_run=False)

    content = (tmp_path / "CLAUDE.md").read_text()
    assert "escalate to Claude." in content
    assert "`feat/<description>`" in content
    assert "| pm / review / deploy | Claude | pm, review, deploy |" in content
    assert "| implement / test / css / templates / content | Agy | implement, test, css, templates, content |" in content


def test_repair_sops_only_refreshes_stale_capability_allocation_with_single_blank_line(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_repair_config(
        tmp_path,
        {
            "roles": {
                "claude": ["pm", "review"],
                "codex": ["implement", "test"],
            },
            "workgroup_agents": ["claude", "codex"],
        },
    )
    (tmp_path / ".agents").mkdir(exist_ok=True)
    (tmp_path / "CLAUDE.md").write_text(
        "<!-- synlynk:harness v0.1 verified:2026-01-01T00:00:00Z -->\n"
        "# Harness Instructions (synlynk-managed — do not edit)\n\n"
        "## Capability-Based Task Allocation\n"
        "| Role | Agent | Tasks |\n"
        "| :--- | :--- | :--- |\n"
        "| stale | data | stale |\n"
        "Do not start a task outside your role column without explicit approval from Claude.\n\n"
        "**GitHub write routing (#426):** stale text.\n\n"
        "This table is generated from `.synlynk/config.json` so it tracks the repo's own routing "
        "rather than synlynk's default fleet assumptions.\n\n"
        "## Cost Visibility\n"
        "1. Log estimated_cost in the job context header before dispatch.\n"
        "2. Check `synlynk status` for current burn rate.\n"
        "3. Confirm all work is captured via telemetry and manual/PM work is logged via `synlynk cost log`.\n"
        "4. Append actual cost to `project-docs/costs.md`.\n\n"
        "<!-- /synlynk:harness -->\n"
    )

    import synlynk as sl

    monkeypatch.setattr(sl, "_run_tc5", lambda files: {"passed": True, "missing": {"claude": []}})

    sl._repair_sops_only(dry_run=False, agent_name="claude")

    repaired = (tmp_path / "CLAUDE.md").read_text()
    boundary = (
        "This table is generated from `.synlynk/config.json` so it tracks the repo's own routing "
        "rather than synlynk's default fleet assumptions.\n\n## Cost Visibility"
    )
    assert boundary in repaired
    assert boundary.replace("\n\n## Cost Visibility", "\n\n\n## Cost Visibility") not in repaired
    assert "\n\n<!-- /synlynk:harness -->" in repaired


def test_repair_capability_allocation_sop_uses_committed_capability_roles(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".synlynk").mkdir(exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({
        "schema_version": 1,
        "budget": {"limit_usd": 10.0, "limit_requests": 100},
    }))
    (tmp_path / ".synlynk" / "capability-roles.json").write_text(json.dumps({
        "roles": {
            "claude": ["pm", "review", "deploy", "brainstorm"],
            "agy": ["implement", "test", "css", "templates", "content", "subpages"],
            "grok": ["implement", "test", "canvas", "js", "infra"],
            "codex": ["implement", "test", "refactor", "cli-plumbing"],
        }
    }))

    import synlynk as sl

    sop = sl._repair_capability_allocation_sop(sl.load_config())

    assert "| pm / review / deploy / brainstorm | Claude | pm, review, deploy, brainstorm |" in sop
    assert "| implement / test / refactor / cli-plumbing | Codex | implement, test, refactor, cli-plumbing |" in sop
    assert "**GitHub write routing (#426):**" in sop


def test_refresh_populates_agent_quotas_from_telemetry(project_dir):
    import synlynk as sl

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "claude --print do stuff",
            "_ts": now - 60,
            "in_tokens": 10_000,
            "out_tokens": 2_000,
        },
        {
            "type": "exec",
            "command": "claude --print more",
            "_ts": now - 120,
            "in_tokens": 5_000,
            "out_tokens": 1_000,
        },
        {
            "type": "exec",
            "agent": "codex",
            "_ts": now - 30,
            "in_tokens": 3_000,
            "out_tokens": 500,
        },
        # Outside all short windows but inside monthly/weekly — still counts for those
        {
            "type": "exec",
            "command": "agy -p task",
            "_ts": now - (3 * 86400),
            "in_tokens": 1_000,
            "out_tokens": 0,
        },
    ])

    written = sl.refresh_agent_quotas_from_telemetry(now=now)
    assert written > 0

    conn = sl._get_db()
    try:
        rows = conn.execute(
            "SELECT agent, quota_type, unit, limit_tokens, used_tokens, reset_at "
            "FROM agent_quotas ORDER BY agent, quota_type, unit"
        ).fetchall()
    finally:
        conn.close()

    assert rows, "agent_quotas must be non-empty after telemetry refresh"
    by_key = {(r[0], r[1], r[2]): r for r in rows}

    # claude: 12k + 6k = 18k tokens, 2 requests inside 5h/hourly/daily/...
    claude_5h_tok = by_key[("claude", "5h", "tokens")]
    assert claude_5h_tok[4] == 18_000
    assert claude_5h_tok[3] == 200_000  # limit from config
    assert claude_5h_tok[5]  # reset_at set

    claude_5h_req = by_key[("claude", "5h", "requests")]
    assert claude_5h_req[4] == 2

    codex_hourly = by_key[("codex", "hourly", "tokens")]
    assert codex_hourly[4] == 3_500

    # agy event is 3 days old → not in 5h, is in weekly/monthly
    assert ("agy", "5h", "tokens") not in by_key or by_key[("agy", "5h", "tokens")][4] == 0
    agy_weekly = by_key[("agy", "weekly", "tokens")]
    assert agy_weekly[4] == 1_000


def test_quota_headroom_helper_used_by_refresh(project_dir):
    import synlynk as sl

    assert sl._quota_headroom(100_000, 18_000) == 82_000
    assert sl._quota_headroom(50, 50) == 0
    assert sl._quota_headroom(10, 99) == 0


def test_stage2_gate_sees_nonzero_usage_after_refresh(project_dir, monkeypatch):
    """Stage-2 quota gate must not stay stuck in degraded empty-table mode
    once telemetry has been rolled into agent_quotas (#291 acceptance)."""
    import synlynk as sl

    monkeypatch.setattr(sl, "_project_request_quota_from_config", lambda: None)

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "claude --print",
            "_ts": now - 10,
            "in_tokens": 40_000,
            "out_tokens": 10_000,
        },
    ])

    # Before refresh: empty table → degraded/unknown
    conn = sl._get_db()
    try:
        before = sl._quota_status_for_agent(conn, "claude", estimated_tokens=1_000)
        assert before["status"] == "unknown"
        assert before["degraded"] is True
        assert before["reason"] == "no_quota_rows"
    finally:
        conn.close()


    written = sl.refresh_agent_quotas_from_telemetry(now=now)
    assert written > 0

    conn = sl._get_db()
    try:
        after = sl._quota_status_for_agent(conn, "claude", estimated_tokens=1_000)
        assert after["degraded"] is False
        assert after["status"] == "ok"
        assert after["unit"] == "tokens"
        assert after["headroom"] is not None
        assert after["headroom"] > 0
        # used was 50k on a 100k hourly default -> headroom finite and < limit
        assert after["headroom"] < 200_000

        # Exhausting estimate: 200k needed, headroom should block if lower
        exhausted = sl._quota_status_for_agent(
            conn, "claude", estimated_tokens=10_000_000
        )
        assert exhausted["status"] == "exhausted"
        assert exhausted["degraded"] is False
    finally:
        conn.close()


def test_fix_issue_616__maybe_open_worktree_pr_sy_prefers_recorded_base_branch_when_valid(
    tmp_path, monkeypatch
):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:5] == [
            "git",
            "-C",
            str(worktree_path),
            "rev-parse",
            "--symbolic-full-name",
        ]:
            assert cmd[-1] == "dispatch/claude/some-branch^{commit}"
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="refs/heads/dispatch/claude/some-branch\n",
                stderr="",
            )
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="https://github.com/octo/repo/pull/42\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("octo", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    pr_number = jobs_mod._maybe_open_worktree_pr(
        {
            "id": "job-1",
            "task": "do the thing",
            "base_branch": "dispatch/claude/some-branch",
        },
        str(worktree_path),
        "feat/example",
    )

    assert pr_number == 42
    create_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert "--base" in create_call
    assert create_call[create_call.index("--base") + 1] == "dispatch/claude/some-branch"


def test_fix_issue_616__maybe_open_worktree_pr_sy_preserves_multisegment_remote_branch_name(
    tmp_path, monkeypatch
):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:5] == [
            "git",
            "-C",
            str(worktree_path),
            "rev-parse",
            "--symbolic-full-name",
        ]:
            assert cmd[-1] == "dispatch/claude/some-branch^{commit}"
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="refs/remotes/origin/dispatch/claude/some-branch\n",
                stderr="",
            )
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="https://github.com/octo/repo/pull/42\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("octo", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    pr_number = jobs_mod._maybe_open_worktree_pr(
        {
            "id": "job-1",
            "task": "do the thing",
            "base_branch": "dispatch/claude/some-branch",
        },
        str(worktree_path),
        "feat/example",
    )

    assert pr_number == 42
    create_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert "--base" in create_call
    assert create_call[create_call.index("--base") + 1] == "dispatch/claude/some-branch"


@pytest.mark.parametrize("job", [{"id": "job-legacy-none", "task": "do the thing", "base_branch": None}, {"id": "job-legacy-missing", "task": "do the thing"}])
def test_fix_issue_616__maybe_open_worktree_pr_sy_falls_back_to_default_base_when_missing(
    tmp_path, monkeypatch, job
):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:4] == ["git", "-C", str(worktree_path), "symbolic-ref"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="refs/remotes/origin/main\n",
                stderr="",
            )
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="https://github.com/octo/repo/pull/42\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("octo", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    pr_number = jobs_mod._maybe_open_worktree_pr(job, str(worktree_path), "feat/example")

    assert pr_number == 42
    create_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert create_call[create_call.index("--base") + 1] == "main"


def test_fix_issue_616__maybe_open_worktree_pr_sy_falls_back_when_recorded_base_is_stale(
    tmp_path, monkeypatch
):
    import subprocess
    import synlynk.jobs as jobs_mod

    worktree_path = tmp_path / "repo"
    worktree_path.mkdir()
    calls = []

    def fake_run(cmd, **kwargs):
        calls.append(cmd)
        if cmd[:5] == [
            "git",
            "-C",
            str(worktree_path),
            "rev-parse",
            "--symbolic-full-name",
        ] and cmd[-1] == "dispatch/claude/deleted-branch^{commit}":
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[:4] == ["git", "-C", str(worktree_path), "symbolic-ref"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="refs/remotes/origin/master\n",
                stderr="",
            )
        if cmd[:5] == ["git", "-C", str(worktree_path), "rev-parse", "--verify"]:
            if cmd[5] == "origin/master":
                return subprocess.CompletedProcess(cmd, 0, stdout="deadbeef\n", stderr="")
            return subprocess.CompletedProcess(cmd, 1, stdout="", stderr="")
        if cmd[:3] == ["gh", "pr", "list"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="[]\n", stderr="")
        if cmd[:3] == ["gh", "pr", "create"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="https://github.com/octo/repo/pull/42\n",
                stderr="",
            )
        raise AssertionError(f"unexpected command: {cmd}")

    monkeypatch.setattr(jobs_mod.subprocess, "run", fake_run)
    monkeypatch.setattr(
        jobs_mod,
        "_pkg",
        lambda name, default=None: (lambda: ("octo", "repo")) if name == "detect_remote_owner_repo" else default,
    )

    pr_number = jobs_mod._maybe_open_worktree_pr(
        {
            "id": "job-stale",
            "task": "do the thing",
            "base_branch": "dispatch/claude/deleted-branch",
        },
        str(worktree_path),
        "feat/example",
    )

    assert pr_number == 42
    create_call = next(cmd for cmd in calls if cmd[:3] == ["gh", "pr", "create"])
    assert create_call[create_call.index("--base") + 1] == "master"


def test_phase_6_of_docssuperpowersplans20260730h_trust_gate_forces_no_coverage_for_fresh_probe(tmp_path, monkeypatch):
    from synlynk.dispatch import _dispatch_capability_preflight

    monkeypatch.chdir(tmp_path)
    db = sqlite3.connect(":memory:")
    _seed_harness_record(db, last_probe_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()))

    result = _dispatch_capability_preflight(
        "agy",
        "ship the fix",
        db_conn=db,
        cwd=str(tmp_path),
        requires=[],
    )

    assert result["passed"] is True
    assert result["status"] == "degraded"
    assert result["branch"] == "no-coverage"
    assert result["probe_trustworthy"] is False
    assert result["reason"]


def test_phase_6_of_docssuperpowersplans20260730h_stale_probe_branch_reprobes_and_blocks_on_timeout(tmp_path, monkeypatch):
    from synlynk.dispatch import _dispatch_capability_preflight
    dispatch_globals = _dispatch_capability_preflight.__globals__

    monkeypatch.chdir(tmp_path)
    db = sqlite3.connect(":memory:")
    stale_probe_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time() - 7200))
    _seed_harness_record(db, last_probe_at=stale_probe_at)
    original_trust = dispatch_globals["_probe_results_trustworthy"]
    original_reprobe = dispatch_globals["_reprobe_harness_sync"]
    dispatch_globals["_probe_results_trustworthy"] = lambda: True
    dispatch_globals["_reprobe_harness_sync"] = lambda agent, timeout_s=120: {
        "passed": False,
        "reason": f"Fresh probe for '{agent}' timed out after {timeout_s}s.",
    }
    try:
        result = _dispatch_capability_preflight(
            "agy",
            "ship the fix",
            db_conn=db,
            cwd=str(tmp_path),
            requires=[],
        )

        assert result["passed"] is False
        assert result["status"] == "blocked"
        assert result["branch"] == "stale"
        assert "timed out" in result["reason"]
    finally:
        dispatch_globals["_probe_results_trustworthy"] = original_trust
        dispatch_globals["_reprobe_harness_sync"] = original_reprobe


def test_phase_6_of_docssuperpowersplans20260730h_failing_probe_branch_blocks(tmp_path, monkeypatch):
    from synlynk.dispatch import _dispatch_capability_preflight
    dispatch_globals = _dispatch_capability_preflight.__globals__
    from synlynk import _migrate_db

    monkeypatch.chdir(tmp_path)
    db = sqlite3.connect(":memory:")
    _migrate_db(db)
    last_probe_at = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime(time.time()))
    db.execute(
        """
        INSERT INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        ("codex", "codex", "1.0.0", "degraded", "{}", "{}", "cap-hash", last_probe_at),
    )
    db.commit()
    original_trust = dispatch_globals["_probe_results_trustworthy"]
    dispatch_globals["_probe_results_trustworthy"] = lambda: True
    try:
        result = _dispatch_capability_preflight(
            "codex",
            "ship the fix",
            db_conn=db,
            cwd=str(tmp_path),
            requires=[],
        )

        assert result["passed"] is False
        assert result["status"] == "blocked"
        assert result["branch"] == "failing"
        assert "compliance_status" in result["reason"]
    finally:
        dispatch_globals["_probe_results_trustworthy"] = original_trust


def test_phase_6_of_docssuperpowersplans20260730h_no_coverage_required_blocks(tmp_path, monkeypatch):
    from synlynk.dispatch import _dispatch_capability_preflight

    monkeypatch.chdir(tmp_path)
    db = sqlite3.connect(":memory:")
    _seed_harness_record(db)

    result = _dispatch_capability_preflight(
        "agy",
        "ship the fix",
        db_conn=db,
        cwd=str(tmp_path),
        requires=["docker"],
    )

    assert result["passed"] is False
    assert result["status"] == "blocked"
    assert result["branch"] == "no-coverage"
    assert "doctor --fix agy" in result["remediation"]


def test_phase_6_of_docssuperpowersplans20260730h_no_coverage_optional_degrades(tmp_path, monkeypatch):
    from synlynk.dispatch import _dispatch_capability_preflight

    monkeypatch.chdir(tmp_path)
    db = sqlite3.connect(":memory:")
    _seed_harness_record(db)

    result = _dispatch_capability_preflight(
        "codex",
        "ship the fix",
        db_conn=db,
        cwd=str(tmp_path),
        requires=[],
    )

    assert result["passed"] is True
    assert result["status"] == "degraded"
    assert result["branch"] == "no-coverage"


def test_phase_6_of_docssuperpowersplans20260730h_repo_artifact_presence_vs_declared_split(tmp_path, monkeypatch):
    from synlynk.dispatch import _dispatch_capability_preflight

    monkeypatch.chdir(tmp_path)
    db = sqlite3.connect(":memory:")
    _seed_harness_record(db)
    (tmp_path / "Dockerfile").write_text("FROM python:3.11\n")
    (tmp_path / ".github" / "workflows").mkdir(parents=True)
    (tmp_path / ".github" / "workflows" / "ci.yml").write_text("name: ci\n")

    soft_result = _dispatch_capability_preflight(
        "codex",
        "ship the fix",
        db_conn=db,
        cwd=str(tmp_path),
        requires=[],
    )
    hard_result = _dispatch_capability_preflight(
        "codex",
        "ship the fix",
        db_conn=db,
        cwd=str(tmp_path),
        requires=["docker"],
    )

    assert soft_result["passed"] is True
    assert soft_result["status"] == "degraded"
    assert "docker" in soft_result["reason"]
    assert hard_result["passed"] is False
    assert hard_result["status"] == "blocked"
    assert hard_result["branch"] == "no-coverage"
def _flag_values(flags, name):
    values = []
    for idx, flag in enumerate(flags):
        if flag == name and idx + 1 < len(flags):
            values.append(flags[idx + 1])
    return values


@pytest.mark.parametrize(
    "role_name, expected_allow, expected_deny",
    [
        ("pm", {"Read", "Grep", "Glob", "LS"}, {"Edit", "Write", "MultiEdit", "Bash"}),
        ("review", {"Read", "Grep", "Glob", "LS"}, {"Edit", "Write", "MultiEdit", "Bash"}),
        ("deploy", {"Read", "Grep", "Glob", "LS"}, {"Edit", "Write", "MultiEdit", "Bash"}),
        (
            "implement",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "Bash(pytest:*)"},
            set(),
        ),
        (
            "test",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "Bash(pytest:*)"},
            set(),
        ),
        (
            "refactor",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "Bash(pytest:*)"},
            set(),
        ),
        (
            "css",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit"},
            {"Bash"},
        ),
        (
            "templates",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit"},
            {"Bash"},
        ),
        (
            "content",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit"},
            {"Bash"},
        ),
        (
            "canvas",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "Bash"},
            set(),
        ),
        (
            "js",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "Bash"},
            set(),
        ),
        (
            "infra",
            {"Read", "Grep", "Glob", "LS", "Edit", "Write", "MultiEdit", "Bash"},
            set(),
        ),
    ],
)
def test_phase_2_of_docssuperpowersplans20260730h_grok_role_permission_flags(role_name, expected_allow, expected_deny):
    from synlynk.dispatch import _permissions_to_flags, _resolve_dispatch_permissions

    permissions = _resolve_dispatch_permissions("grok", role_list=[role_name])
    flags = _permissions_to_flags("grok", permissions)

    assert flags[:2] == ["--permission-mode", "dontAsk"]
    assert "--always-approve" not in flags
    assert set(_flag_values(flags, "--allow")) == expected_allow
    assert set(_flag_values(flags, "--deny")) == expected_deny


def test_phase_2_of_docssuperpowersplans20260730h_grok_regression_no_empty_fallthrough():
    from synlynk.dispatch import _permissions_to_flags

    flags = _permissions_to_flags("grok", ["read:*"])
    assert flags
    assert flags[:2] == ["--permission-mode", "dontAsk"]
    assert "--always-approve" not in flags
    assert "Read" in _flag_values(flags, "--allow")


def test_phase_7_of_docssuperpowersplans20260730h_panel_timeout_override_respected(monkeypatch):
    import synlynk.team as team

    calls = []

    class Result:
        stdout = "panel output\n"

    def fake_run(cmd, **kwargs):
        calls.append((cmd, kwargs))
        return Result()

    monkeypatch.setattr(team.subprocess, "run", fake_run)

    codex_output = team._run_agent_sync("codex", "review prompt")
    claude_output = team._run_agent_sync("claude", "review prompt")

    assert codex_output == "panel output"
    assert claude_output == "panel output"
    assert calls[0][1]["timeout"] == 300
    assert calls[1][1]["timeout"] == 120


def test_best_agent_refreshes_quotas_before_gate(project_dir, monkeypatch):
    """_best_agent_for_story must call telemetry refresh so gate sees real usage."""
    import synlynk as sl

    monkeypatch.setattr(sl, "_project_request_quota_from_config", lambda: None)

    now = time.time()
    # Exhaust claude via telemetry; leave agy with capacity
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "claude --print",
            "_ts": now - 5,
            # blow past hourly 100k default for tokens
            "in_tokens": 99_000,
            "out_tokens": 5_000,
        },
    ])

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories "
        "(story_id, title, engg_domain, org_domain, industry, phase, estimated_tokens) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("story-q291", "Quota wire", "backend", "platform", "ott", "build", 10_000),
    )
    for agent, quality, model in (
        ("claude", 9.0, "claude-sonnet-4-6"),
        ("agy", 6.0, "gemini-2.5-pro"),
    ):
        conn.execute(
            "INSERT INTO capability_ratings "
            "(story_id, agent, model_version, engg_domain, org_domain, industry, phase, "
            " signal_source, quality, quality_auto) VALUES (?,?,?,?,?,?,?,?,?,?)",
            ("story-q291", agent, model, "backend", "platform", "ott", "build",
             "auto", quality, quality),
        )
    # Seed agy with known headroom so it is not degraded-only
    sl._upsert_agent_quota(
        "agy", "hourly", limit_tokens=200_000, used_tokens=0,
        model="gemini-2.5-pro", unit="tokens", conn=conn,
    )
    conn.commit()
    conn.close()

    # Routing should drop exhausted claude and pick agy (after refresh)
    chosen = sl._best_agent_for_story("story-q291")
    assert chosen == "agy"

    # Confirm claude rows were written with non-zero used
    conn = sl._get_db()
    try:
        used = conn.execute(
            "SELECT used_tokens FROM agent_quotas "
            "WHERE agent='claude' AND unit='tokens' AND quota_type='hourly'"
        ).fetchone()
    finally:
        conn.close()
    assert used is not None
    assert used[0] == 104_000


def test_cmd_quota_prints_headroom(project_dir, capsys):
    import synlynk as sl

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "command": "codex exec -",
            "_ts": now - 1,
            "in_tokens": 1_000,
            "out_tokens": 200,
        },
    ])

    sl.cmd_quota()
    out = capsys.readouterr().out
    assert "codex" in out
    assert "headroom" in out.lower() or "Headroom" in out or "status=" in out
    assert "telemetry" in out.lower()


def test_cmd_quota_json(project_dir, capsys):
    import synlynk as sl

    now = time.time()
    _write_telemetry(project_dir, [
        {
            "type": "exec",
            "agent": "grok",
            "_ts": now - 1,
            "in_tokens": 500,
            "out_tokens": 100,
        },
    ])

    sl.cmd_quota(json_output=True)
    out = capsys.readouterr().out
    payload = json.loads(out)
    assert payload["source"] == "telemetry_proxy"
    agents = {a["agent"]: a for a in payload["agents"]}
    assert "grok" in agents
    assert agents["grok"]["windows"]
    assert any(w["used"] == 600 for w in agents["grok"]["windows"] if w["unit"] == "tokens")


@pytest.mark.parametrize(
    "reconcile_order",
    [
        ("jobs", "daemon"),
        ("daemon", "jobs"),
    ],
)
def test_fix_synlynk_jobs_all_permanently_shows_unknown_shared_exit_marker_race(
    project_dir, monkeypatch, reconcile_order
):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    log_path = project_dir / ".synlynk" / "logs" / "job-shared.log"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("Input tokens: 12\nOutput tokens: 34\n")
    exit_path = str(log_path) + ".exit"
    with open(exit_path, "w") as f:
        f.write("0")

    sl._save_jobs([
        {
            "id": "job-shared",
            "agent": "claude",
            "story_id": "story-shared",
            "task": "shared exit marker test",
            "pid": 99999999,
            "log_file": str(log_path),
            "worktree_path": "",
            "worktree_branch": "",
            "started_at": "2026-07-25T10:00:00",
            "ended_at": None,
            "status": "running",
            "exit_code": None,
        }
    ])

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, pid, enqueued_at, started_at, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "job-shared",
            "claude",
            "shared exit marker test",
            "story-shared",
            "running",
            5,
            "[]",
            99999999,
            "2026-07-25T10:00:00",
            "2026-07-25T10:00:00",
            str(log_path),
        ),
    )
    conn.commit()
    conn.close()

    monkeypatch.setattr(
        jobs_mod.os,
        "kill",
        lambda *a, **kw: (_ for _ in ()).throw(ProcessLookupError()),
    )
    monkeypatch.setattr(
        jobs_mod.os,
        "waitpid",
        lambda *a, **kw: (_ for _ in ()).throw(ChildProcessError()),
    )

    for reconcile in reconcile_order:
        if reconcile == "jobs":
            jobs_mod._reconcile_jobs()
        else:
            jobs_mod._reconcile_daemon_jobs()

    jobs = sl._load_jobs()
    job_row = next(job for job in jobs if job["id"] == "job-shared")
    assert job_row["status"] == "completed"
    assert job_row["exit_code"] == 0

    conn = sl._get_db()
    try:
        daemon_row = conn.execute(
            "SELECT status, exit_code FROM daemon_jobs WHERE job_id=?",
            ("job-shared",),
        ).fetchone()
    finally:
        conn.close()
    assert daemon_row == ("done", 0)
    assert os.path.exists(exit_path)


def test_wire_health_checks_into_real_synlynk_doc(project_dir, monkeypatch, capsys):
    import synlynk as sl
    import synlynk.doctor as doctor_mod

    monkeypatch.setattr(
        doctor_mod,
        "HEALTH_CHECKS",
        [lambda: sl.HealthCheck("identity_roles", "ok", "all declared roles provisioned")],
    )
    monkeypatch.setattr(
        doctor_mod,
        "AGENT_CAPABILITY_BASELINES",
        {
            "agy": {
                "cli": "agy",
                "dispatch_flags": {},
                "network_deps": {"required_endpoints": []},
                "headless_contract": {},
            }
        },
    )
    monkeypatch.setattr(sl, "_run_tc0", lambda agent, baseline=None: {"passed": True, "schema_issues": []})
    monkeypatch.setattr(sl, "_run_tc1", lambda agent: {"passed": True})
    monkeypatch.setattr(sl, "_run_tc2", lambda agent, flags_spec: {"passed": True, "failed_flags": []})
    monkeypatch.setattr(sl, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(sl, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(sl, "_run_tc5", lambda files: {"passed": True, "missing": {}})
    monkeypatch.setattr(sl, "load_config", lambda: {"roles": {}})

    exit_code = sl.cmd_doctor()
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "synlynk doctor" in out
    assert "identity_roles" in out
    assert "doctor [agy]" in out


def test_synlynk_doctor_tc1tc2tc3tc5_silently_noop_regression_reports_schema_incomplete(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"roles": {}}))

    import synlynk as sl

    monkeypatch.setattr(
        sl,
        "AGENT_CAPABILITY_BASELINES",
        {
            "claude": {
                "cli": "claude",
                "dispatch_flags": {},
                "headless_contract": {},
                "network_deps": {"required_endpoints": []},
                "non_interactive_flags": ["--print"],
            }
        },
    )
    monkeypatch.setattr(sl._constants, "AGENT_CAPABILITY_BASELINES", sl.AGENT_CAPABILITY_BASELINES)
    monkeypatch.setattr(sl.doctor, "AGENT_CAPABILITY_BASELINES", sl.AGENT_CAPABILITY_BASELINES)
    monkeypatch.setattr(sl, "_run_tc1", lambda agent: {"passed": True, "requires_pty": False})
    monkeypatch.setattr(sl, "_run_tc2", lambda agent, flags_spec: {"passed": True, "failed_flags": []})
    monkeypatch.setattr(sl, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(sl, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(sl, "_run_tc5", lambda files: {"passed": True, "missing": {}})

    exit_code = sl.cmd_doctor()
    out = capsys.readouterr().out

    assert exit_code == 1
    assert "TC-0 schema" in out
    assert "schema incomplete" in out


def test_synlynk_doctor_reports_local_tc5_skip(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    (tmp_path / ".synlynk" / "config.json").write_text(json.dumps({"roles": {}}))

    import synlynk as sl

    patched_baselines = {
        "local": {
            "cli": "aider",
            "dispatch_flags": {
                "valid_flags": ["--no-auto-commits", "--yes-always", "--openai-api-base", "--model", "--edit-format"],
                "invalid_flags": ["--dangerously-skip-permissions", "--non-interactive"],
                "required_flags": ["--no-auto-commits", "--yes-always"],
            },
            "headless_contract": {
                "requires_pty": False,
                "stdout_flush_method": "native",
                "env_vars_required": [],
                "non_interactive_flag": "--version",
            },
            "network_deps": {"required_endpoints": ["127.0.0.1:8080"], "optional_endpoints": []},
            "non_interactive_flags": [],
        }
    }
    monkeypatch.setattr(sl, "AGENT_CAPABILITY_BASELINES", patched_baselines)
    monkeypatch.setattr(sl._constants, "AGENT_CAPABILITY_BASELINES", patched_baselines)
    monkeypatch.setattr(sl.doctor, "AGENT_CAPABILITY_BASELINES", patched_baselines)
    monkeypatch.setattr(sl, "_run_tc0", lambda agent, baseline=None: {"passed": True, "schema_issues": []})
    monkeypatch.setattr(sl, "_run_tc1", lambda agent: {"passed": True, "requires_pty": False})
    monkeypatch.setattr(sl, "_run_tc2", lambda agent, flags_spec: {"passed": True, "failed_flags": []})
    monkeypatch.setattr(sl, "_run_tc3", lambda endpoints: {"passed": True, "unreachable": []})
    monkeypatch.setattr(sl, "_run_tc4", lambda agent, db_conn: {"passed": True, "failed_verbs": []})
    monkeypatch.setattr(sl, "_run_tc5", lambda files: {"passed": True, "missing": {}})

    exit_code = sl.cmd_doctor()
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "TC-5 sops" in out
    assert "intentionally skipped" in out


def test_fix_stale_capability_scores_view_missing_discipline_column(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import synlynk as sl

    db_path = tmp_path / ".synlynk" / "state.db"
    conn = sqlite3.connect(db_path)
    conn.executescript(sl._DB_SCHEMA)
    conn.execute("INSERT INTO stories (story_id, title) VALUES ('story-stale', 'Stale view')")
    conn.execute(
        "INSERT INTO capability_ratings "
        "(story_id, agent, model_version, engg_domain, discipline, org_domain, role, stage, "
        " industry, phase, signal_source, quality) "
        "VALUES ('story-stale', 'claude', 'claude-sonnet-4-6', 'backend', 'backend', "
        "'platform', 'dev', 'open', 'ott', 'build', 'auto', 9.0)"
    )
    conn.execute("DROP VIEW IF EXISTS capability_scores")
    conn.executescript("""
        CREATE VIEW capability_scores AS
        SELECT
            agent,
            model_version,
            engg_domain,
            org_domain,
            industry,
            phase,
            SUM(quality * pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER))) /
              SUM(pow(0.85, CAST((julianday('now') - julianday(ts)) / 7 AS INTEGER)))
              AS weighted_score,
            COUNT(*) AS sample_count,
            MAX(ts) AS last_seen
        FROM capability_ratings
        WHERE split_model = 0
        GROUP BY agent, model_version, engg_domain, org_domain, industry, phase;
    """)
    conn.commit()
    conn.close()

    monkeypatch.setattr(sl, "DB_PATH", str(db_path))

    conn = sl._get_db()
    try:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_scores)")}
        assert {"discipline", "role", "stage"} <= cols

        discipline = conn.execute(
            "SELECT discipline FROM capability_scores LIMIT 1"
        ).fetchone()[0]
        count = conn.execute(
            "SELECT COUNT(*) FROM capability_scores WHERE discipline=?",
            (discipline,),
        ).fetchone()[0]
        assert count >= 1
    finally:
        conn.close()


def test_agent_from_command_path_and_gemini_alias(project_dir):
    from synlynk.quota import _agent_from_telemetry_event, _aggregate_usage_from_telemetry

    assert _agent_from_telemetry_event({"command": "/usr/local/bin/claude --print"}) == "claude"
    assert _agent_from_telemetry_event({"agent": "gemini"}) == "agy"
    assert _agent_from_telemetry_event({"command": "gemini -p x"}) == "agy"
    assert _agent_from_telemetry_event({"command": "echo hi"}) is None

    now = time.time()
    usage = _aggregate_usage_from_telemetry(
        [{"type": "exec", "command": "gemini -p", "_ts": now, "in_tokens": 10, "out_tokens": 0}],
        now=now,
    )
    assert "agy" in usage
    assert usage["agy"]["hourly"]["tokens"] == 10


def test_empty_telemetry_writes_nothing(project_dir):
    import synlynk as sl

    _write_telemetry(project_dir, [])
    assert sl.refresh_agent_quotas_from_telemetry() == 0
    conn = sl._get_db()
    try:
        n = conn.execute("SELECT COUNT(*) FROM agent_quotas").fetchone()[0]
    finally:
        conn.close()
    assert n == 0


def test_fix_github_issue_378_nikhilsomansynk_terminal_summary_survives_unknown_overwrite(project_dir, monkeypatch):
    import synlynk as sl

    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": []})

    terminal = sl._write_job_summary(
        "job-race",
        "codex",
        "story-378",
        0,
        4.0,
        120,
        30,
        0.02,
        ["src/terminal.py"],
        status_label="OK (exit 0)",
    )

    overwritten = sl._write_job_summary(
        "job-race",
        "codex",
        "story-378",
        None,
        5.0,
        0,
        0,
        0.00,
        [],
        status_label="FAILED_UNVERIFIED (exit unknown)",
    )

    summary_path = project_dir / ".synlynk" / "logs" / "job-race.summary"
    assert summary_path.read_text() == terminal
    assert overwritten == terminal


def test_chore_synlynk_jobs_all_shows_stale_faile_terminal_summary_survives_daemon_reconcile(
    project_dir, monkeypatch
):
    import synlynk as sl
    import synlynk.jobs as jobs_mod

    monkeypatch.setattr(sl, "load_config", lambda: {"fenced_commands": []})

    summary_path = project_dir / ".synlynk" / "logs" / "job-race.summary"
    terminal = sl._write_job_summary(
        "job-race",
        "codex",
        "story-202",
        0,
        4.0,
        120,
        30,
        0.02,
        ["src/terminal.py"],
        status_label="OK (exit 0)",
    )

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO daemon_jobs (job_id, agent, task, story_id, status, priority, "
        "depends_on, pid, enqueued_at, started_at, log_path) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
        (
            "job-race",
            "codex",
            "task",
            "story-202",
            "running",
            5,
            "[]",
            99999999,
            "2026-07-25T00:00:00",
            "2026-07-25T00:00:01",
            str(project_dir / ".synlynk" / "logs" / "job-race.log"),
        ),
    )
    conn.commit()
    conn.close()

    def pkg_side_effect(name, default=None):
        if name == "_get_db":
            return sl._get_db
        if name == "extract_tokens":
            return lambda log_text, agent="": (0, 0)
        if name == "extract_model_version":
            return lambda log_text, agent="": "unknown"
        if name == "update_costs":
            return lambda *args, **kwargs: None
        return getattr(sl, name, default)

    monkeypatch.setattr(jobs_mod, "_pkg", pkg_side_effect)
    monkeypatch.setattr(jobs_mod.os, "waitpid", lambda pid, opts: (_ for _ in ()).throw(ChildProcessError()))
    monkeypatch.setattr(jobs_mod.os, "kill", lambda pid, sig: (_ for _ in ()).throw(ProcessLookupError()))

    jobs_mod._reconcile_daemon_jobs()

    assert summary_path.read_text() == terminal
    assert "FAILED (exit -1)" not in summary_path.read_text()
    assert "files:    0 touched" not in summary_path.read_text()


def test_harden_preflight_dispatch_check_agent_auth_fails_loudly_on_not_signed_in(
    tmp_path, monkeypatch
):
    import sqlite3
    import socket
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.setenv("HOME", str(tmp_path))
    db = sqlite3.connect(str(tmp_path / "state.db"))
    sl._migrate_db(db)

    db.execute(
        """
        INSERT OR REPLACE INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, 'ok', ?, ?, ?, ?)
        """,
        (
            "grok",
            "grok",
            "1.0.0",
            json.dumps(sl.AGENT_CAPABILITY_BASELINES["grok"]["headless_contract"]),
            json.dumps(sl.AGENT_CAPABILITY_BASELINES["grok"]["dispatch_flags"]),
            "seeded-probe",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime()),
        ),
    )
    db.commit()

    def fake_run(cmd, **kwargs):
        if cmd == ["grok", "--version"]:
            return subprocess.CompletedProcess(
                cmd,
                0,
                stdout="grok 1.0.0\n",
                stderr="Not signed in. Please authenticate.\n",
            )
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(dispatch_mod.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")

    class _SuccessSocket:
        def settimeout(self, timeout):
            return None

        def connect(self, addr):
            return None

        def close(self):
            return None

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: _SuccessSocket())

    result = _preflight_dispatch("grok", ["--always-approve"], db_conn=db)

    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "not authenticated" in result["reason"].lower()


def _seed_hardened_preflight_record(db, agent_name: str, baseline: dict):
    db.execute(
        """
        INSERT OR REPLACE INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, 'ok', ?, ?, ?, ?)
        """,
        (
            agent_name,
            agent_name,
            "1.0.0",
            json.dumps(baseline["headless_contract"]),
            json.dumps(baseline["dispatch_flags"]),
            "seeded-probe",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        ),
    )
    db.commit()


def test_fixdispatch_harden_reporting_and_preflight_allows_agy_dangerously_skip_permissions_flag(
    tmp_path, monkeypatch
):
    import sqlite3
    import socket
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    db = sqlite3.connect(str(tmp_path / "state.db"))
    sl._migrate_db(db)
    _seed_hardened_preflight_record(db, "agy", sl.AGENT_CAPABILITY_BASELINES["agy"])

    class _SuccessSocket:
        def settimeout(self, timeout):
            return None

        def connect(self, addr):
            return None

        def close(self):
            return None

    monkeypatch.setattr(dispatch_mod.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: _SuccessSocket())

    result = _preflight_dispatch(
        "agy",
        ["--dangerously-skip-permissions"],
        db_conn=db,
        permissions=["read:*"],
    )

    assert result["passed"] is True
    assert result["reason"] is None


def test_fixdispatch_harden_reporting_and_preflight_blocks_invalid_flag(
    tmp_path, monkeypatch
):
    import sqlite3
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    db = sqlite3.connect(str(tmp_path / "state.db"))
    sl._migrate_db(db)
    _seed_hardened_preflight_record(db, "grok", sl.AGENT_CAPABILITY_BASELINES["grok"])

    monkeypatch.setattr(dispatch_mod.shutil, "which", lambda cmd: None)

    result = _preflight_dispatch("grok", ["--yes"], db_conn=db)

    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "--yes" in result["reason"]


def test_fixdispatch_harden_reporting_and_preflight_blocks_unreachable_endpoint(
    tmp_path, monkeypatch
):
    import sqlite3
    import socket
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    db = sqlite3.connect(str(tmp_path / "state.db"))
    sl._migrate_db(db)
    _seed_hardened_preflight_record(db, "grok", sl.AGENT_CAPABILITY_BASELINES["grok"])

    class _FailSocket:
        def settimeout(self, timeout):
            return None

        def connect(self, addr):
            raise OSError("unreachable")

        def close(self):
            return None

    monkeypatch.setattr(dispatch_mod.shutil, "which", lambda cmd: None)
    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: _FailSocket())

    result = _preflight_dispatch("grok", ["--always-approve"], db_conn=db)

    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "cli-chat-proxy.grok.com" in result["reason"]


def test_harden_preflight_dispatch_check_agent_au_blocks_known_headless_permission_denial(
    tmp_path, monkeypatch
):
    import sqlite3
    import socket
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk.dispatch import _preflight_dispatch

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("HOME", str(tmp_path))
    (tmp_path / ".synlynk" / "logs").mkdir(parents=True, exist_ok=True)
    auth_state = tmp_path / ".gemini" / "antigravity-cli"
    auth_state.mkdir(parents=True, exist_ok=True)
    (auth_state / "jetski_state.pbtxt").write_text("session: valid\n")
    db = sqlite3.connect(str(tmp_path / "state.db"))
    sl._migrate_db(db)

    db.execute(
        """
        INSERT OR REPLACE INTO harness_records (
            agent_name, harness_name, installed_version, compliance_status,
            active_contract, active_flags, capability_hash, last_probe_at
        ) VALUES (?, ?, ?, 'ok', ?, ?, ?, ?)
        """,
        (
            "agy",
            "agy",
            "1.0.0",
            json.dumps(sl.AGENT_CAPABILITY_BASELINES["agy"]["headless_contract"]),
            json.dumps(sl.AGENT_CAPABILITY_BASELINES["agy"]["dispatch_flags"]),
            "seeded-probe",
            time.strftime("%Y-%m-%dT%H:%M:%SZ", time.localtime()),
        ),
    )
    db.commit()

    log_path = tmp_path / ".synlynk" / "logs" / "job-4cb54c47.log"
    log_path.write_text(
        "jetski: no output produced - a tool required the \"command\" permission that headless mode cannot prompt for, so it was auto-denied\n"
        '{"conversation_id":"07557e08-f4d5-4b97-abcc-430e7ed79df6","status":"SUCCESS","response":"","duration_seconds":6.436941,"num_turns":1,"usage":{"input_tokens":0,"output_tokens":0}}\n'
    )
    sl._save_jobs([
        {
            "id": "job-4cb54c47",
            "agent": "agy",
            "story_id": "story-4cb54c47",
            "task": "review PR 416",
            "pid": 1,
            "log_file": str(log_path),
            "started_at": "2026-07-19T18:00:00",
            "ended_at": None,
            "status": "permission_denied",
            "exit_code": 0,
        }
    ])

    def fake_run(cmd, **kwargs):
        if cmd == ["agy", "--version"]:
            return subprocess.CompletedProcess(cmd, 0, stdout="agy 1.0.0\n", stderr="")
        return subprocess.CompletedProcess(cmd, 0, stdout="", stderr="")

    monkeypatch.setattr(sl.subprocess, "run", fake_run)
    monkeypatch.setattr(dispatch_mod.shutil, "which", lambda cmd: f"/usr/bin/{cmd}")

    class _SuccessSocket:
        def settimeout(self, timeout):
            return None

        def connect(self, addr):
            return None

        def close(self):
            return None

    monkeypatch.setattr(socket, "socket", lambda *args, **kwargs: _SuccessSocket())

    result = _preflight_dispatch("agy", [], db_conn=db, permissions=["read:*"])

    assert result["passed"] is False
    assert result["sentinel"] == "HARNESS_PREFLIGHT_FAIL"
    assert "auto-denial" in result["reason"].lower()


def _load_backfill_script():
    script_path = Path(__file__).resolve().parents[1] / "bin" / "backfill_api_equivalent_usd.py"
    spec = importlib.util.spec_from_file_location("backfill_api_equivalent_usd", script_path)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _seed_cost_entries_db(db_path):
    import sqlite3

    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_date TEXT NOT NULL,
            agent TEXT,
            model TEXT,
            input_tokens INTEGER,
            output_tokens INTEGER,
            cache_read_tokens INTEGER,
            api_equivalent_usd REAL,
            payment_mode TEXT,
            actual_usd REAL,
            cost_source TEXT NOT NULL,
            recorded_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-01", "claude", "claude-sonnet-4-6", 1000, 500, 250, None, "subscription", None, "estimated_manual"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-02", "codex", "gpt-5-codex", 2000, 1000, 0, None, "subscription", None, "estimated_manual"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-03", "claude", "claude-sonnet-4-6", 3000, 1500, 0, None, "subscription", None, "legacy_unknown"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-04", "claude", "claude-sonnet-4-6", 4000, 2000, 0, 0.99, "subscription", 1.23, "estimated_manual"),
    )
    conn.execute(
        """INSERT INTO cost_entries
           (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
            api_equivalent_usd, payment_mode, actual_usd, cost_source)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        ("2026-07-05", "claude", "claude-sonnet-4-6", 5000, None, 0, None, "subscription", None, "estimated_manual"),
    )
    conn.commit()
    conn.close()


def test_fix_github_issue_382_nikhilsomansynlynk_backfill_updates_only_eligible_rows(project_dir, monkeypatch, capsys):
    import sqlite3
    import synlynk as sl

    db_path = project_dir / "state.db"
    _seed_cost_entries_db(db_path)
    monkeypatch.setattr(sl, "_resolve_db_path", lambda: str(db_path))

    backfill_mod = _load_backfill_script()
    assert backfill_mod.main([]) == 0

    out = capsys.readouterr().out
    assert "Updated 2 rows" in out

    conn = sqlite3.connect(db_path)
    try:
        rows = conn.execute(
            "SELECT session_date, agent, model, api_equivalent_usd, payment_mode, actual_usd, cost_source "
            "FROM cost_entries ORDER BY id"
        ).fetchall()
    finally:
        conn.close()

    assert rows[0][3] == pytest.approx(
        sl._model_rate_for_version("claude-sonnet-4-6", agent="claude")["input"] +
        (0.5 * sl._model_rate_for_version("claude-sonnet-4-6", agent="claude")["output"]) +
        (0.25 * sl._model_rate_for_version("claude-sonnet-4-6", agent="claude")["cache_read"])
    )
    assert rows[1][3] == pytest.approx(
        (2.0 * sl._model_rate_for_version("gpt-5-codex", agent="codex")["input"]) +
        (1.0 * sl._model_rate_for_version("gpt-5-codex", agent="codex")["output"])
    )
    assert rows[2][3] is None
    assert rows[3][3] == pytest.approx(0.99)
    assert rows[4][3] is None
    assert rows[0][4] == "subscription"
    assert rows[0][5] is None
    assert rows[1][4] == "subscription"
    assert rows[1][5] is None
    assert rows[2][4] == "subscription"
    assert rows[2][5] is None


def test_synlynk_selftest_live_clobbers_real_repo(monkeypatch, tmp_path):
    from synlynk import selftest as selftest_mod
    import synlynk.scheduler as scheduler_mod

    real_repo = tmp_path / "real-repo"
    (real_repo / "project-docs").mkdir(parents=True)
    (real_repo / ".synlynk").mkdir(parents=True)
    (real_repo / "project-docs" / "todo.md").write_text(
        "# Project Todo List\n"
        "- [ ] keep me <!-- id: story-keep -->\n"
    )
    (real_repo / "GEMINI.md").write_text(
        "<!-- synlynk:start version=\"1\" tool=\"agy\" -->\n"
        "## keep me\n"
        "<!-- synlynk:end -->\n"
    )
    (real_repo / ".synlynk" / "config.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "budget": {"limit_usd": 10.0, "limit_requests": 100},
                "project_docs_dir": "project-docs",
                "dispatch_mode": "daily-grind",
            }
        )
    )
    subprocess.run(["git", "init", "-q"], cwd=real_repo, check=True)
    subprocess.run(["git", "config", "user.email", "codex@example.com"], cwd=real_repo, check=True)
    subprocess.run(["git", "config", "user.name", "Codex"], cwd=real_repo, check=True)
    subprocess.run(["git", "add", "."], cwd=real_repo, check=True)
    subprocess.run(["git", "commit", "-m", "baseline", "-q"], cwd=real_repo, check=True)

    todo_before = (real_repo / "project-docs" / "todo.md").read_text()
    gemini_before = (real_repo / "GEMINI.md").read_text()

    monkeypatch.chdir(real_repo)
    monkeypatch.setattr(
        selftest_mod,
        "dispatch_agent",
        lambda *args, **kwargs: {"id": "job-selftest", "pid": 1, "fence": None},
    )
    monkeypatch.setattr(selftest_mod, "exec_command", lambda argv: 0)
    monkeypatch.setattr(scheduler_mod, "cmd_schedule", lambda execute=True, max_stories=1: None)

    results = selftest_mod.run_selftest(live=True)

    assert all(result.status != "fail" for result in results)
    assert subprocess.run(
        ["git", "status", "--short"],
        cwd=real_repo,
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip() == ""
    assert (real_repo / "project-docs" / "todo.md").read_text() == todo_before
    assert (real_repo / "GEMINI.md").read_text() == gemini_before


def test_live_selftest_scenario_coverage_gap_init(tmp_path):
    from synlynk import selftest as selftest_mod

    ctx = selftest_mod.ScenarioContext(repo_path=str(tmp_path), live=True)
    entry = {"command": "init"}

    result = selftest_mod.SELFTEST_SCENARIOS["init"](entry, ctx)

    assert result.status == "pass"
    assert "without clobbering existing files" in result.detail


def test_bug__secret_patterns_regex_doesnt_redact_ghs_installation_token():
    from synlynk import _redact_secret_patterns

    text = "ghs_16u5S23058PzAALpPpBVo3243.eyJhbGciOiJSUzI1NiJ9.eyJpYXQiOjE2-abcdef_1234567890"
    result = _redact_secret_patterns(text)
    assert text not in result
    assert result == "[REDACTED]"

