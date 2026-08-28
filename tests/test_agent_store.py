import json
import os
import pytest


def _valid_charter(marker: str) -> str:
    return (
        "---\n"
        "schema_version: 1\n"
        "role: dev\n"
        f'description: "{marker}"\n'
        "durability: dispatch-only\n"
        "tools: []\n"
        "credentials: []\n"
        "---\n"
        "\n"
        "## Instructions\n"
        f"\n{marker} instructions body.\n"
        "\n"
        "## Authority & Escalation\n"
        "\nEscalates per policy.\n"
        "\n"
        "## Workflow Ownership\n"
        "\nOwns nothing in particular for this test.\n"
    )


def test_get_workspace_id_mints_and_persists(project_dir):
    from synlynk.agent_store import get_workspace_id

    workspace_id = get_workspace_id()
    assert workspace_id
    with open(".synlynk/config.json") as f:
        config = json.load(f)
    assert config["workspace_id"] == workspace_id


def test_get_workspace_id_idempotent(project_dir):
    from synlynk.agent_store import get_workspace_id

    first = get_workspace_id()
    second = get_workspace_id()
    assert first == second


def test_get_workspace_id_never_overwrites_existing_value(project_dir):
    from synlynk.agent_store import get_workspace_id

    with open(".synlynk/config.json") as f:
        config = json.load(f)
    config["workspace_id"] = "pre-existing-id"
    with open(".synlynk/config.json", "w") as f:
        json.dump(config, f)

    assert get_workspace_id() == "pre-existing-id"


def test_agent_store_path_under_workspace_home(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    workspace_id = agent_store.get_workspace_id()
    path = agent_store.agent_store_path("dev-primary")
    assert path == str(fake_home / ".synlynk" / "workspaces" / workspace_id / "agents" / "dev-primary")


def test_register_and_resolve_agent(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent(
        "dev-primary",
        aliases=[
            {"kind": "role_slug", "value": "dev"},
            {"kind": "github_app_slug", "value": "synlynk-dev[bot]"},
        ],
    )

    assert agent_store.resolve_agent_id("dev") == "dev-primary"
    assert agent_store.resolve_agent_id("synlynk-dev[bot]") == "dev-primary"
    assert agent_store.resolve_agent_id("unregistered-alias") is None


def test_register_agent_rejects_duplicate_agent_id(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    try:
        agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev2"}])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_register_agent_rejects_duplicate_alias_across_agents(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    try:
        agent_store.register_agent("dev-secondary", aliases=[{"kind": "role_slug", "value": "dev"}])
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_read_charter_missing_returns_empty(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    content, revision = agent_store.read_charter("dev-primary")
    assert content == ""
    assert revision == 0


def test_propose_charter_revision_writes_and_reads_back(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    charter_v1 = _valid_charter("Charter v1")
    new_revision = agent_store.propose_charter_revision(
        "dev-primary", charter_v1, actor="human:nikhilsoman", parent_revision=0
    )
    assert new_revision == 1

    content, revision = agent_store.read_charter("dev-primary")
    assert content == charter_v1
    assert revision == 1


def test_propose_charter_revision_rejects_invalid_content(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store, charter_schema

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    with pytest.raises(charter_schema.CharterValidationError):
        agent_store.propose_charter_revision(
            "dev-primary", "not a valid charter", actor="human:nikhilsoman", parent_revision=0
        )


def test_propose_charter_revision_stale_parent_raises_conflict(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    try:
        agent_store.propose_charter_revision(
            "dev-primary", _valid_charter("Charter v2 stale"), actor="human:nikhilsoman", parent_revision=0
        )
        assert False, "expected agent_store.RevisionConflictError"
    except agent_store.RevisionConflictError:
        pass


def test_sync_dispatch_routing_populates_block_for_dev(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("dev-primary", aliases=[{"kind": "role_slug", "value": "dev"}])
    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v1"), actor="human:nikhilsoman", parent_revision=0
    )

    new_revision = agent_store.sync_dispatch_routing("dev-primary", "dev", actor="cli")
    assert new_revision == 2

    content, revision = agent_store.read_charter("dev-primary")
    assert revision == 2
    assert "dispatch_routing:" in content
    assert "harness: codex" in content


def test_sync_dispatch_routing_is_noop_for_role_without_task_allocation(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.register_agent("qa-primary", aliases=[{"kind": "role_slug", "value": "qa"}])
    charter_v1 = _valid_charter("QA charter v1").replace("role: dev", "role: qa")
    agent_store.propose_charter_revision(
        "qa-primary", charter_v1, actor="human:nikhilsoman", parent_revision=0
    )

    unchanged_revision = agent_store.sync_dispatch_routing("qa-primary", "qa", actor="cli")
    assert unchanged_revision == 1

    content, revision = agent_store.read_charter("qa-primary")
    assert revision == 1
    assert "dispatch_routing" not in content


def test_charter_revisions_jsonl_provenance_chain(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store
    import json as _json

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Charter v2"), actor="agent:dev-primary", parent_revision=1
    )

    revisions_path = os.path.join(
        agent_store.agent_store_path("dev-primary"), "charter.revisions.jsonl"
    )
    lines = [_json.loads(line) for line in open(revisions_path) if line.strip()]
    assert len(lines) == 2
    assert lines[0]["revision"] == 1
    assert lines[0]["parent_hash"] is None
    assert lines[1]["revision"] == 2
    assert lines[1]["parent_hash"] == lines[0]["content_hash"]
    assert lines[1]["actor"] == "agent:dev-primary"


def test_read_entry_missing_returns_empty(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    content, revision = agent_store.read_entry("dev-primary", "memory", "onboarding-notes")
    assert content == ""
    assert revision == 0


def test_propose_entry_revision_writes_and_reads_back(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    new_revision = agent_store.propose_entry_revision(
        "dev-primary", "memory", "onboarding-notes", "notes v1",
        actor="agent:dev-primary", parent_revision=0,
    )
    assert new_revision == 1

    content, revision = agent_store.read_entry("dev-primary", "memory", "onboarding-notes")
    assert content == "notes v1"
    assert revision == 1


def test_entries_in_same_category_have_independent_revision_counters(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-a", "a v1", actor="agent:dev-primary", parent_revision=0
    )
    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-b", "b v1", actor="agent:dev-primary", parent_revision=0
    )
    _, rev_a = agent_store.read_entry("dev-primary", "memory", "entry-a")
    _, rev_b = agent_store.read_entry("dev-primary", "memory", "entry-b")
    assert rev_a == 1
    assert rev_b == 1


def test_memory_and_sor_categories_share_one_revisions_file_each(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store
    import json as _json

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-a", "a v1", actor="agent:dev-primary", parent_revision=0
    )
    agent_store.propose_entry_revision(
        "dev-primary", "memory", "entry-b", "b v1", actor="agent:dev-primary", parent_revision=0
    )

    revisions_path = os.path.join(agent_store.agent_store_path("dev-primary"), "memory", "revisions.jsonl")
    lines = [_json.loads(line) for line in open(revisions_path) if line.strip()]
    assert {line["entry"] for line in lines} == {"entry-a", "entry-b"}


def test_statements_of_record_category(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    agent_store.propose_entry_revision(
        "dev-primary", "statements-of-record", "2026-08-15-decision", "decided X",
        actor="human:nikhilsoman", parent_revision=0,
    )
    content, revision = agent_store.read_entry(
        "dev-primary", "statements-of-record", "2026-08-15-decision"
    )
    assert content == "decided X"
    assert revision == 1


def test_full_flow_canonical_content_lives_only_in_workspace_store(project_dir, tmp_path, monkeypatch):
    from synlynk import agent_store

    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr(os.path, "expanduser", lambda p: p.replace("~", str(fake_home)))

    workspace_id = agent_store.get_workspace_id()
    assert workspace_id

    agent_store.register_agent(
        "dev-primary",
        aliases=[
            {"kind": "role_slug", "value": "dev"},
            {"kind": "github_app_slug", "value": "synlynk-dev[bot]"},
        ],
    )
    assert agent_store.resolve_agent_id("dev") == "dev-primary"

    rev1 = agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v1"), actor="human:nikhilsoman", parent_revision=0
    )
    assert rev1 == 1
    rev2 = agent_store.propose_charter_revision(
        "dev-primary", _valid_charter("Dev charter v2 expanded scope"), actor="agent:dev-primary", parent_revision=1
    )
    assert rev2 == 2

    content, revision = agent_store.read_charter("dev-primary")
    assert content == _valid_charter("Dev charter v2 expanded scope")
    assert revision == 2

    canonical_charter_path = os.path.join(
        agent_store.agent_store_path("dev-primary"), "charter.md"
    )
    assert str(fake_home) in canonical_charter_path
    with open(canonical_charter_path) as f:
        assert "Dev charter v2" in f.read()


def test_list_agents_empty(project_dir):
    from synlynk import agent_store

    assert agent_store.list_agents() == []


def test_list_agents_returns_registered_entries(project_dir):
    from synlynk import agent_store

    agent_store.register_agent("agent-1", [{"kind": "role_slug", "value": "dev"}])
    agent_store.register_agent("agent-2", [{"kind": "role_slug", "value": "qa"}])

    agents = agent_store.list_agents()
    ids = {a["agent_id"] for a in agents}
    assert ids == {"agent-1", "agent-2"}


def test_set_agent_disabled_marks_entry_and_appends_history(project_dir):
    from synlynk import agent_store

    agent_store.register_agent("agent-1", [{"kind": "role_slug", "value": "dev"}])
    agent_store.set_agent_disabled("agent-1", actor="cli")

    agents = agent_store.list_agents()
    entry = next(a for a in agents if a["agent_id"] == "agent-1")
    assert entry["disabled"] is True
    assert entry["history"][-1]["event"] == "disabled"
    assert entry["history"][-1]["actor"] == "cli"


def test_set_agent_disabled_is_idempotent(project_dir):
    from synlynk import agent_store

    agent_store.register_agent("agent-1", [{"kind": "role_slug", "value": "dev"}])
    agent_store.set_agent_disabled("agent-1", actor="cli")
    history_len_after_first = len(agent_store.list_agents()[0]["history"])

    agent_store.set_agent_disabled("agent-1", actor="cli")
    agents = agent_store.list_agents()
    assert len(agents[0]["history"]) == history_len_after_first
    assert agents[0]["disabled"] is True
