"""Unit tests for Meta Muse harness integration (Milestone v0.20.0 Cluster D, #1508)."""

import json
import sqlite3
from unittest.mock import MagicMock, patch

import pytest
from synlynk._constants import HARNESS_CAPABILITY_BASELINES, NEXT_GEN_FLEET, EXTENDED_FLEET
from synlynk.costs import _extract_muse_structured, extract_tokens
from synlynk.dispatch import (
    _dispatch_flags_for_agent,
    _format_prompt_for_agent,
    _permissions_to_flags,
    dispatch_agent,
)
from synlynk.probe import _probe_agent, _run_tc0


def test_muse_model_resolves_to_real_catalog_id():
    """resolve_tier_model must not fall through to the 'muse-default' placeholder."""
    from synlynk.models import resolve_tier_model

    assert resolve_tier_model("pro", "muse") == "muse-spark-1.3"
    assert resolve_tier_model("fast", "muse") == "muse-spark-1.3"
    assert resolve_tier_model("unknown-tier", "muse") == "muse-spark-1.3"


def test_muse_baseline_schema_tc0():
    """Verify Meta Muse baseline passes TC-0 schema validation with zero issues."""
    assert "muse" in HARNESS_CAPABILITY_BASELINES
    baseline = HARNESS_CAPABILITY_BASELINES["muse"]

    assert baseline["cli"] == "muse"
    assert baseline["can_gh_write"] is True
    assert "builder" in baseline["roles"]
    assert "verifier" in baseline["roles"]
    assert "architect" in baseline["roles"]
    assert baseline["non_interactive_flags"] == ["exec"]
    assert "prompt_flag" not in baseline
    assert baseline["prompt_via_arg"] is True
    assert baseline["env_passthrough"] == ["MUSE_API_KEY", "META_API_KEY"]
    assert baseline["dispatch_flags"]["valid_flags"] == [
        "--json",
        "--provider",
        "--model",
        "--approval-mode",
        "--workspace",
        "--yolo",
    ]
    assert baseline["dispatch_flags"]["required_flags"] == ["--json", "--approval-mode"]
    assert baseline["headless_contract"]["non_interactive_flag"] == "exec"

    # TC-0 schema check
    res = _run_tc0("muse", baseline)
    assert res["schema_issues"] == [], f"TC-0 schema issues: {res['schema_issues']}"

    assert "muse" in NEXT_GEN_FLEET
    assert "muse" in EXTENDED_FLEET


def test_muse_adapter_permission_translation_does_not_invent_unsupported_flags():
    """Muse permissions must not add flags outside its real CLI contract."""
    assert _dispatch_flags_for_agent("muse") == ["--json", "--approval-mode"]
    assert _permissions_to_flags(
        "muse", ["read:*", "write:src/"], read_only=False
    ) == []


def test_muse_adapter_build_cmd():
    """Verify MuseAdapter.build_cmd constructs real exec CLI flags."""
    from synlynk.harness_adapters.muse import MuseAdapter
    from synlynk.harness_adapters.request import DispatchRequest

    adapter = MuseAdapter()
    req = DispatchRequest(agent="muse", task="implement feature")
    cmd = adapter.build_cmd(req)
    assert "--json" in cmd
    assert "--approval-mode" in cmd
    assert "never" in cmd
    assert "--dangerously-skip-permissions" not in cmd
    assert "--always-approve" not in cmd
    assert "--non-interactive" not in cmd
    assert "-C" not in cmd


def test_muse_dispatch_flags_skip_permissions_never_adds_invalid_flags():
    """Skip-permissions must never add invalid flags to Muse dispatch flags."""
    flags = _dispatch_flags_for_agent("muse", skip_permissions=True)
    assert "--dangerously-skip-permissions" not in flags
    assert "--always-approve" not in flags
    assert "--json" in flags
    assert "--approval-mode" in flags


def test_muse_dispatch_flags_and_command_construction(tmp_path, monkeypatch):
    """Verify dispatch constructs correct muse invocation flags and worktree options."""
    import synlynk.dispatch as dispatch_mod

    worktree_dir = str(tmp_path / "mock_worktree")

    captured_cmds = []

    class FakeProc:
        pid = 99999
        returncode = 0
        def poll(self):
            return 0

    def fake_popen(cmd, **kwargs):
        captured_cmds.append((cmd, kwargs))
        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_create_job_worktree", lambda *a, **kw: {
        "path": worktree_dir,
        "base_branch": "main",
        "base_sha": "abcdef1",
    })
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda *a, **kw: {"passed": True})
    monkeypatch.setattr(dispatch_mod, "_dispatch_capability_preflight", lambda *a, **kw: {"passed": True})

    # Dispatch to muse
    res = dispatch_mod.dispatch_agent(
        agent="muse",
        task="refactor core parser",
        force_agent=True,
        skip_preflight=True,
        context_mode="none",
    )

    assert res is not None
    muse_cmds = [
        c for c in captured_cmds
        if isinstance(c[0], (list, tuple)) and c[0] and c[0][0] in ("sh", "bash") and "muse" in str(c[0][-1])
    ]
    assert len(muse_cmds) == 1
    cmd_run, kwargs = muse_cmds[0]

    # Inspect shell command string
    shell_cmd = cmd_run[2] if isinstance(cmd_run, (list, tuple)) and len(cmd_run) > 2 else str(cmd_run)
    assert "muse" in shell_cmd
    assert "exec" in shell_cmd
    assert "--workspace" in shell_cmd
    assert worktree_dir in shell_cmd
    assert "--json" in shell_cmd
    assert "--approval-mode" in shell_cmd
    assert "never" in shell_cmd
    assert "--non-interactive" not in shell_cmd
    assert "--output-format" not in shell_cmd
    assert "-C " not in shell_cmd
    assert "--prompt" not in shell_cmd


def test_muse_dispatch_with_skip_permissions(tmp_path, monkeypatch):
    """Verify dispatch with skip_permissions constructs valid muse command without invalid flags."""
    import synlynk.dispatch as dispatch_mod

    worktree_dir = str(tmp_path / "mock_worktree_skip")
    captured_cmds = []

    class FakeProc:
        pid = 99998
        returncode = 0
        def poll(self):
            return 0

    def fake_popen(cmd, **kwargs):
        captured_cmds.append((cmd, kwargs))
        return FakeProc()

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", fake_popen)
    monkeypatch.setattr(dispatch_mod, "_create_job_worktree", lambda *a, **kw: {
        "path": worktree_dir,
        "base_branch": "main",
        "base_sha": "abcdef1",
    })
    monkeypatch.setattr(dispatch_mod, "_preflight_dispatch", lambda *a, **kw: {"passed": True})
    monkeypatch.setattr(dispatch_mod, "_dispatch_capability_preflight", lambda *a, **kw: {"passed": True})

    res = dispatch_mod.dispatch_agent(
        agent="muse",
        task="refactor core parser",
        force_agent=True,
        skip_preflight=True,
        context_mode="none",
        skip_permissions=True,
    )

    assert res is not None
    muse_cmds = [
        c for c in captured_cmds
        if isinstance(c[0], (list, tuple)) and c[0] and c[0][0] in ("sh", "bash") and "muse" in str(c[0][-1])
    ]
    assert len(muse_cmds) == 1
    shell_cmd = muse_cmds[0][0][2]
    assert "muse" in shell_cmd
    assert "exec" in shell_cmd
    assert "--workspace" in shell_cmd
    assert "--json" in shell_cmd
    assert "--approval-mode" in shell_cmd
    assert "never" in shell_cmd
    assert "--dangerously-skip-permissions" not in shell_cmd
    assert "--always-approve" not in shell_cmd


def test_muse_prompt_formatting():
    """Verify muse prompt format includes task receipt headers and working directory constraint."""
    prompt = _format_prompt_for_agent(
        agent="muse",
        context_text="Context: project overview",
        story_id="story-1234",
        task="implement fast path",
        file_section="\n\n## Relevant Files\n- `synlynk/fast.py`",
        verify_section="\n\n## Verification\npytest tests/test_fast.py",
        cwd_hint="/tmp/worktree_muse",
        task_sha256="deadbeefcafe1234",
    )

    assert "SYNLYNK_TASK_RECEIVED: deadbeefcafe1234" in prompt
    assert "## Working Directory\n/tmp/worktree_muse" in prompt
    assert "All file edits MUST be in this directory." in prompt
    assert "## Story / Task Reference\nStory ID: story-1234" in prompt
    assert "implement fast path" in prompt
    assert "synlynk/fast.py" in prompt
    assert "pytest tests/test_fast.py" in prompt


def test_muse_structured_token_extraction():
    """Verify _extract_muse_structured parses single and streaming JSON outputs."""
    # Single JSON object
    single_json = json.dumps({
        "status": "SUCCESS",
        "usage": {
            "input_tokens": 1250,
            "output_tokens": 320,
            "cached_tokens": 400
        }
    })
    counts1 = _extract_muse_structured(single_json)
    assert counts1 is not None
    assert counts1.input_tokens == 1250
    assert counts1.output_tokens == 320
    assert counts1.cache_read_tokens == 400
    assert counts1.basis == "structured_output"

    # Streaming event lines with prompt_tokens/completion_tokens aliases
    stream_output = (
        '{"type": "init"}\n'
        '{"type": "delta", "content": "processing..."}\n'
        '{"type": "result", "usage": {"prompt_tokens": 2100, "completion_tokens": 550, "cache_read_tokens": 120}}\n'
    )
    counts2 = _extract_muse_structured(stream_output)
    assert counts2 is not None
    assert counts2.input_tokens == 2100
    assert counts2.output_tokens == 550
    assert counts2.cache_read_tokens == 120

    # Delegation through extract_tokens
    counts3 = extract_tokens(single_json, agent="muse")
    assert counts3.input_tokens == 1250
    assert counts3.output_tokens == 320


def test_muse_structured_token_extraction_from_raw_exec_envelope():
    """Parse usage nested in the raw Muse exec JSONL event envelope.

    This is the shape emitted by the installed Muse CLI: each line is a
    session record and the model completion's usage is below ``payload``.
    It is intentionally kept as JSONL rather than synlynk's internal log
    wrapper so a CLI schema change cannot silently regress cost capture.
    """
    raw_exec_output = (
        '{"schema_version":1,"record_type":"event",'
        '"payload_type":"run.lifecycle.started",'
        '"payload":{"kind":"run_started"}}\n'
        '{"schema_version":1,"record_type":"event",'
        '"payload_type":"model.completed",'
        '"payload":{"kind":"model_completed",'
        '"usage":{"input_tokens":1482,"cached_tokens":317,'
        '"output_tokens":96,"total_tokens":1895},'
        '"finish_reason":"stop"}}\n'
        '{"schema_version":1,"record_type":"event",'
        '"payload_type":"run.terminal.completed",'
        '"payload":{"kind":"run_terminal","terminal":"completed"}}\n'
    )

    counts = _extract_muse_structured(raw_exec_output)

    assert counts is not None
    assert counts.input_tokens == 1482
    assert counts.output_tokens == 96
    assert counts.cache_read_tokens == 317
    assert counts.basis == "structured_output"


def test_muse_probe_agent(monkeypatch):
    """Verify _probe_agent probes Meta Muse with mock CLI version output."""
    db = sqlite3.connect(":memory:")
    db.execute("""
        CREATE TABLE harness_records (
            harness_name TEXT PRIMARY KEY,
            installed_version TEXT,
            compliance_status TEXT,
            active_contract TEXT,
            active_flags TEXT,
            capability_hash TEXT,
            last_probe_at TEXT
        )
    """)
    db.execute("""
        CREATE TABLE harness_command_palette (
            harness_name TEXT,
            cli_version TEXT,
            command TEXT,
            command_type TEXT,
            help_text TEXT,
            first_seen_version TEXT,
            last_seen_version TEXT,
            PRIMARY KEY (harness_name, command)
        )
    """)
    db.commit()

    class FakeRun:
        stdout = "muse version 1.2.0 (meta-ai/muse)"
        stderr = ""
        returncode = 0

    monkeypatch.setattr("subprocess.run", lambda *a, **kw: FakeRun())
    monkeypatch.setattr("socket.create_connection", lambda *a, **kw: MagicMock(close=lambda: None))

    result = _probe_agent("muse", db, fast_path_ok=False, write_fence=False)
    assert result["version"] == "1.2.0"
    assert result["status"] == "ok"
    assert result["schema_issues"] == []

    # Check DB record
    row = db.execute("SELECT installed_version, compliance_status FROM harness_records WHERE harness_name='muse'").fetchone()
    assert row is not None
    assert row[0] == "1.2.0"
    assert row[1] == "ok"
