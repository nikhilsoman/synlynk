# Agent Dispatch Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the `synlynk agent init/list/show/edit/disable` CLI onboarding surface on top of the existing `synlynk/agent_store.py` storage layer, then wire the resulting `agent_id` into `dispatch_agent()` as a first-class routing/identity key so a workspace agent's tasks can be dispatched to any harness and correctly attributed via GitHub identity.

**Architecture:** Two layers, built bottom-up. Layer 1 (Tasks 1-4) adds two small storage functions to `agent_store.py` and a new `synlynk/agent_cli.py` module wired into `cli.py`, mirroring the existing `harness` subparser pattern. Layer 2 (Tasks 5-7) threads an optional `agent_id` through `dispatch_agent()`: it resolves the agent's org-chart role via `agent_store._agent_role()`, maps that role to a harness-selection role tag (`architect`/`builder`/`verifier` — the vocabulary `AGENT_CAPABILITY_BASELINES[...]["roles"]` already uses), and reuses the already-shipped `_resolve_dispatch_gh_write()`/`_role_for_story()` GitHub-identity machinery, generalized to accept an agent-derived role. A new `--as-agent` flag on `synlynk dispatch` makes the harness positional optional when agent-based auto-selection applies.

**Tech Stack:** Python 3 stdlib only, `argparse`, `sqlite3` (existing `_get_db()`), `pytest`.

---

## Design Decision: mapping org-chart roles to harness-selection roles

`agent_store.py`'s `role_slug` values (`dev`, `qa`, `pm`, `architect`, `tpm`, `designer`, `marketing`, `synlynk-bot` — the parent spec's 8-role org chart) are a **different vocabulary** from `AGENT_CAPABILITY_BASELINES[<harness>]["roles"]` (`architect`, `builder`, `verifier` — an execution-style tag `synlynk/_constants.py:44-207` already uses to say what kind of work a harness is good at). These are not the same "role" despite sharing a field name — a second instance of the Agent-vs-Harness naming collision (see spec §6). This plan does not rename either; it adds one small, explicit mapping table so harness auto-selection has a deterministic input:

```python
# synlynk/dispatch.py, near the top, after imports
_ORG_ROLE_TO_BASELINE_ROLE = {
    "dev": "builder",
    "qa": "verifier",
    "architect": "architect",
    "tpm": "architect",
    "pm": "architect",
    "designer": "builder",
    "marketing": "builder",
    "synlynk-bot": "builder",
}
```

Harness auto-selection for an `agent_id`-driven dispatch (no `story_id`, or `story_id` present but its own capability-score lookup returns nothing) picks the first harness in `sorted(CORE_FLEET)` whose `AGENT_CAPABILITY_BASELINES[harness]["roles"]` contains the mapped baseline role (and, if `requires_gh_write` is set, whose baseline also has `can_gh_write: True`). This is a static, deterministic fallback — it does not touch or replace the existing `_best_agent_for_story` DB-driven capability-scoring system, which stays exactly as-is and still wins whenever a `story_id` is present and yields a result (existing precedence, unchanged).

---

## Task 1: Storage layer additions — `set_agent_disabled` and `list_agents`

**Files:**
- Modify: `synlynk/agent_store.py`
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_store.py`:

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_store.py -k "list_agents or set_agent_disabled" -v`
Expected: FAIL with `AttributeError: module 'synlynk.agent_store' has no attribute 'list_agents'`

- [ ] **Step 3: Implement `list_agents` and `set_agent_disabled`**

In `synlynk/agent_store.py`, add after `resolve_agent_id` (after line 110, before `class RevisionConflictError`):

```python
def list_agents() -> list:
    """Return all registry entries (agent_id, aliases, disabled, created_at, history)."""
    return _load_registry()["agents"]


def set_agent_disabled(agent_id: str, actor: str) -> None:
    """Idempotently mark an agent disabled, appending a history event."""
    registry = _load_registry()
    for entry in registry["agents"]:
        if entry["agent_id"] == agent_id:
            if entry.get("disabled"):
                return
            entry["disabled"] = True
            entry["history"].append(
                {"event": "disabled", "at": _now_iso(), "actor": actor}
            )
            _write_json_atomic(_registry_path(), registry)
            return
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agent_store.py -k "list_agents or set_agent_disabled" -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat: add list_agents and set_agent_disabled to agent_store"
```

---

## Task 2: `synlynk/agent_cli.py` — init, list, show

**Files:**
- Create: `synlynk/agent_cli.py`
- Test: Create `tests/test_agent_cli.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_agent_cli.py`:

```python
import os

import pytest


SEED_ROLES = ["dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot"]


def test_cmd_agent_init_creates_registry_entry_and_charter(project_dir):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")

    agents = agent_store.list_agents()
    assert len(agents) == 1
    assert agents[0]["agent_id"] == agent_id
    assert {"kind": "role_slug", "value": "dev"} in agents[0]["aliases"]

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 1
    assert content == agent_cli.SEED_CHARTERS["dev"]


def test_cmd_agent_init_writes_projection_with_empty_capability_grants(project_dir):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("qa")

    projection_path = os.path.join(".synlynk", "agents", f"{agent_id}.yaml")
    with open(projection_path) as f:
        rendered = f.read()
    assert "capability_grants: {}" in rendered


def test_cmd_agent_init_rejects_duplicate_role(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_init("dev")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "already has an agent" in captured.err or "already has an agent" in captured.out


def test_cmd_agent_list_empty(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_list()
    captured = capsys.readouterr()
    assert "No agents registered" in captured.out


def test_cmd_agent_list_shows_all_agents(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    agent_cli.cmd_agent_init("qa")
    capsys.readouterr()

    agent_cli.cmd_agent_list()
    captured = capsys.readouterr()
    assert "dev" in captured.out
    assert "qa" in captured.out
    assert "active" in captured.out


def test_cmd_agent_show_resolves_by_full_id(project_dir, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_show(agent_id)
    captured = capsys.readouterr()
    assert agent_id in captured.out
    assert "dev" in captured.out


def test_cmd_agent_show_resolves_by_alias(project_dir, capsys):
    from synlynk import agent_cli

    agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_show("dev")
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cmd_agent_show_unresolvable_exits_1(project_dir, capsys):
    from synlynk import agent_cli

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_show("nonexistent")
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "No agent found matching" in captured.err or "No agent found matching" in captured.out
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_cli.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.agent_cli'`

- [ ] **Step 3: Implement `synlynk/agent_cli.py` (init, list, show, resolve helper)**

Create `synlynk/agent_cli.py`:

```python
"""CLI handlers for `synlynk agent init/list/show/edit/disable`.

Onboarding surface layered on top of synlynk/agent_store.py's storage
functions (PR #988). See docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md.
"""
import sys
import uuid

from synlynk import agent_store

SEED_CHARTERS = {
    "dev": "Implementation — writes the code.",
    "qa": "Quality assurance — tests and verifies work.",
    "pm": "Program management — roadmap, brainstorming, issue triage.",
    "architect": "System design — architecture and technical direction.",
    "tpm": "Technical program management — cross-cutting coordination, GOVERNS integration.",
    "designer": "Design — visual and interaction design.",
    "marketing": "Marketing — external communication and positioning.",
    "synlynk-bot": "Catch-all workspace automation identity.",
}

ROLES = list(SEED_CHARTERS)


def _resolve_or_exit(id_or_alias: str) -> str:
    agents = agent_store.list_agents()
    for entry in agents:
        if entry["agent_id"] == id_or_alias:
            return id_or_alias
    resolved = agent_store.resolve_agent_id(id_or_alias)
    if resolved:
        return resolved
    print(f"No agent found matching '{id_or_alias}'.", file=sys.stderr)
    raise SystemExit(1)


def cmd_agent_init(role: str) -> str:
    for entry in agent_store.list_agents():
        for alias in entry["aliases"]:
            if alias["kind"] == "role_slug" and alias["value"] == role:
                print(
                    f"Role '{role}' already has an agent ({entry['agent_id']}). "
                    "Only one agent per role is supported.",
                    file=sys.stderr,
                )
                raise SystemExit(1)

    agent_id = str(uuid.uuid4())
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(
        agent_id, SEED_CHARTERS[role], actor="cli", parent_revision=0
    )
    agent_store.regenerate_agent_projection(
        agent_id, repo_overrides={"capability_grants": {}}
    )
    print(f"Created agent {agent_id} (role: {role})")
    return agent_id


def cmd_agent_list() -> None:
    agents = agent_store.list_agents()
    if not agents:
        print("No agents registered. Run `synlynk agent init <role>` to create one.")
        return
    print(f"{'AGENT_ID':<38}{'ROLE':<13}{'STATUS':<11}CREATED_AT")
    for entry in agents:
        role = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), "?"
        )
        status = "disabled" if entry.get("disabled") else "active"
        print(f"{entry['agent_id']:<38}{role:<13}{status:<11}{entry['created_at']}")


def cmd_agent_show(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    role = next(
        (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), "?"
    )
    status = "disabled" if entry.get("disabled") else "active"
    content, revision = agent_store.read_charter(agent_id)

    print(f"agent_id:   {agent_id}")
    print(f"role:       {role}")
    print(f"status:     {status}")
    print(f"created_at: {entry['created_at']}")
    print("history:")
    for event in entry["history"]:
        print(f"  {event}")
    print(f"charter (revision {revision}):")
    print(content)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agent_cli.py -v`
Expected: PASS (8 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_cli.py tests/test_agent_cli.py
git commit -m "feat: add agent_cli init/list/show handlers"
```

---

## Task 3: `synlynk/agent_cli.py` — edit, disable

**Files:**
- Modify: `synlynk/agent_cli.py`
- Test: Modify `tests/test_agent_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_cli.py`:

```python
def test_cmd_agent_edit_updates_charter(project_dir, tmp_path, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    charter_file = tmp_path / "new_charter.md"
    charter_file.write_text("Implementation — writes the code, reviews own PRs.")

    agent_cli.cmd_agent_edit(agent_id, str(charter_file))

    content, revision = agent_store.read_charter(agent_id)
    assert revision == 2
    assert content == "Implementation — writes the code, reviews own PRs."


def test_cmd_agent_edit_stdin(project_dir, monkeypatch, capsys):
    import io
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    monkeypatch.setattr("sys.stdin", io.StringIO("New charter from stdin."))
    agent_cli.cmd_agent_edit(agent_id, "-")

    content, revision = agent_store.read_charter(agent_id)
    assert content == "New charter from stdin."
    assert revision == 2


def test_cmd_agent_edit_stale_revision_exits_1(project_dir, tmp_path, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()
    # Simulate a concurrent edit bumping the revision underneath us.
    agent_store.propose_charter_revision(
        agent_id, "concurrent edit", actor="other", parent_revision=1
    )

    charter_file = tmp_path / "stale.md"
    charter_file.write_text("stale content")

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_edit(agent_id, str(charter_file))
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "updated by someone else" in captured.err or "updated by someone else" in captured.out


def test_cmd_agent_disable_sets_flag(project_dir, capsys):
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_disable(agent_id)

    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    assert entry["disabled"] is True


def test_cmd_agent_disable_idempotent(project_dir, capsys):
    from synlynk import agent_cli

    agent_id = agent_cli.cmd_agent_init("dev")
    capsys.readouterr()

    agent_cli.cmd_agent_disable(agent_id)
    capsys.readouterr()
    agent_cli.cmd_agent_disable(agent_id)
    captured = capsys.readouterr()
    assert "already disabled" in captured.out


def test_cmd_agent_disable_unresolvable_exits_1(project_dir, capsys):
    from synlynk import agent_cli

    with pytest.raises(SystemExit) as exc_info:
        agent_cli.cmd_agent_disable("nonexistent")
    assert exc_info.value.code == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_cli.py -k "edit or disable" -v`
Expected: FAIL with `AttributeError: module 'synlynk.agent_cli' has no attribute 'cmd_agent_edit'`

- [ ] **Step 3: Implement `cmd_agent_edit` and `cmd_agent_disable`**

Append to `synlynk/agent_cli.py`:

```python
def cmd_agent_edit(id_or_alias: str, charter_path: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    if charter_path == "-":
        new_content = sys.stdin.read()
    else:
        with open(charter_path) as f:
            new_content = f.read()

    _, parent_revision = agent_store.read_charter(agent_id)
    try:
        new_revision = agent_store.propose_charter_revision(
            agent_id, new_content, actor="cli", parent_revision=parent_revision
        )
    except agent_store.RevisionConflictError:
        print(
            "Charter was updated by someone else since you last viewed it. "
            f"Run `synlynk agent show {agent_id}` and retry.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    agent_store.regenerate_agent_projection(agent_id, repo_overrides={"capability_grants": {}})
    print(f"Updated charter for {agent_id} (revision {new_revision})")


def cmd_agent_disable(id_or_alias: str) -> None:
    agent_id = _resolve_or_exit(id_or_alias)
    entry = next(a for a in agent_store.list_agents() if a["agent_id"] == agent_id)
    if entry.get("disabled"):
        print(f"Agent {agent_id} is already disabled.")
        return
    agent_store.set_agent_disabled(agent_id, actor="cli")
    print(f"Disabled agent {agent_id}.")
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_agent_cli.py -v`
Expected: PASS (14 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_cli.py tests/test_agent_cli.py
git commit -m "feat: add agent_cli edit/disable handlers"
```

---

## Task 4: Wire `agent` subparser into `synlynk/cli.py`

**Files:**
- Modify: `synlynk/cli.py`
- Test: Modify `tests/test_agent_cli.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_cli.py`:

```python
def test_cli_agent_init_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    captured = capsys.readouterr()
    assert "Created agent" in captured.out


def test_cli_agent_init_rejects_unknown_role(project_dir):
    from synlynk.cli import main

    with pytest.raises(SystemExit):
        main(["agent", "init", "not-a-real-role"])


def test_cli_agent_list_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    capsys.readouterr()
    main(["agent", "list"])
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cli_agent_show_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    capsys.readouterr()
    main(["agent", "show", "dev"])
    captured = capsys.readouterr()
    assert "dev" in captured.out


def test_cli_agent_disable_route(project_dir, capsys):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    capsys.readouterr()
    main(["agent", "disable", "dev"])
    captured = capsys.readouterr()
    assert "Disabled agent" in captured.out


def test_cli_agent_edit_requires_charter_flag(project_dir):
    from synlynk.cli import main

    main(["agent", "init", "dev"])
    with pytest.raises(SystemExit):
        main(["agent", "edit", "dev"])
```

Check how `synlynk/cli.py` exposes its entry point before writing these (some repos call it `main`, others `run`). Run:

```bash
grep -n "^def main\|^def run\|if __name__" synlynk/cli.py
```

Use whichever name that grep reveals in place of `main` above (the plan assumes `main(argv: list) -> None` exists based on the `harness`/`dispatch` subparsers already routing through it at `synlynk/cli.py:1101` — confirm the exact signature before writing Step 1's test calls).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_cli.py -k "test_cli_agent" -v`
Expected: FAIL — `agent` is not a recognized subcommand (argparse `SystemExit` with "invalid choice", or similar)

- [ ] **Step 3: Add the `agent` subparser**

In `synlynk/cli.py`, add immediately after the `harness` subparser block (after line 481, before the `exec_parser` block at line 483):

```python
    agent_parser = subparsers.add_parser("agent", help="Manage workspace agents (roles/charters)")
    agent_sub = agent_parser.add_subparsers(dest="agent_action")

    agent_init_parser = agent_sub.add_parser("init", help="Create a new workspace agent for a role")
    agent_init_parser.add_argument("role", choices=[
        "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot",
    ], help="Org-chart role for this agent")

    agent_sub.add_parser("list", help="List all registered workspace agents")

    agent_show_parser = agent_sub.add_parser("show", help="Show one agent's details and charter")
    agent_show_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")

    agent_edit_parser = agent_sub.add_parser("edit", help="Propose a new charter revision")
    agent_edit_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")
    agent_edit_parser.add_argument("--charter", required=True,
        help="Path to new charter content, or '-' to read from stdin")

    agent_disable_parser = agent_sub.add_parser("disable", help="Disable a workspace agent")
    agent_disable_parser.add_argument("id_or_alias", help="Agent ID or alias (e.g. role slug)")
```

- [ ] **Step 4: Add the dispatch block**

In `synlynk/cli.py`, add immediately after the `elif args.command == "dispatch":` block ends (after line 1101's block — locate the next `elif args.command ==` line after it and insert before that line):

```python
    elif args.command == "agent":
        from synlynk import agent_cli
        if args.agent_action == "init":
            agent_cli.cmd_agent_init(args.role)
        elif args.agent_action == "list":
            agent_cli.cmd_agent_list()
        elif args.agent_action == "show":
            agent_cli.cmd_agent_show(args.id_or_alias)
        elif args.agent_action == "edit":
            agent_cli.cmd_agent_edit(args.id_or_alias, args.charter)
        elif args.agent_action == "disable":
            agent_cli.cmd_agent_disable(args.id_or_alias)
        else:
            agent_parser.print_help()
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agent_cli.py -v`
Expected: PASS (20 tests)

- [ ] **Step 6: Run the full suite to check for regressions**

Run: `pytest -q`
Expected: all prior tests still pass, plus the 20 new ones

- [ ] **Step 7: Commit**

```bash
git checkout -- GEMINI.md 2>/dev/null || true
git add synlynk/cli.py tests/test_agent_cli.py
git commit -m "feat: wire agent subparser into cli.py"
```

---

## Task 5: `dispatch_agent()` gains `agent_id` — role resolution and error handling

**Files:**
- Modify: `synlynk/dispatch.py:1931-1963` (function signature and top of body)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dispatch.py`:

```python
def test_dispatch_agent_with_unregistered_agent_id_raises(project_dir):
    import synlynk as sl

    with pytest.raises(ValueError, match="unregistered"):
        sl.dispatch_agent(
            "codex", "do work", agent_id="nonexistent-id", force_agent=True, context_mode="none",
        )


def test_dispatch_agent_with_disabled_agent_id_raises(project_dir):
    import synlynk as sl
    from synlynk import agent_cli, agent_store

    agent_id = agent_cli.cmd_agent_init("dev")
    agent_store.set_agent_disabled(agent_id, actor="test")

    with pytest.raises(ValueError, match="disabled"):
        sl.dispatch_agent(
            "codex", "do work", agent_id=agent_id, force_agent=True, context_mode="none",
        )
```

Check whether `pytest` is already imported at the top of `tests/test_dispatch.py`:

```bash
head -20 tests/test_dispatch.py
```

If `import pytest` is missing, add it.

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k "agent_id" -v`
Expected: FAIL with `TypeError: dispatch_agent() got an unexpected keyword argument 'agent_id'`

- [ ] **Step 3: Add `agent_id` parameter and role resolution**

In `synlynk/dispatch.py`, modify the `dispatch_agent` signature (line 1931) to add `agent_id: str = None`:

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   agent_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   task_type: str = None,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None) -> dict:
```

Immediately after the `if not task or not task.strip():` guard (after line 1949's `)`), insert:

```python
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry is None:
            raise ValueError(
                f"agent_id {agent_id!r} is unregistered — cannot dispatch. "
                f"Run `synlynk agent list` to see registered agents."
            )
        if entry.get("disabled"):
            raise ValueError(
                f"agent {agent_id!r} is disabled — cannot dispatch. "
                f"Use `synlynk agent show {agent_id}` to check status."
            )
        resolved_agent_role = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -k "agent_id" -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: dispatch_agent resolves and validates agent_id"
```

---

## Task 6: Harness auto-selection and GitHub identity resolution from `agent_id`

**Files:**
- Modify: `synlynk/dispatch.py` (near top-level constants, the `if story_id and not force_agent:` block at ~1957-1963, and `_build_subprocess_env`/its call site at 385-434 and 2406)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_dispatch.py`:

```python
def test_dispatch_agent_id_auto_selects_harness_by_mapped_role(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    agent_id = agent_cli.cmd_agent_init("qa")  # qa -> "verifier" -> agy

    job = sl.dispatch_agent(
        "claude", "run the test suite", agent_id=agent_id,
        force_agent=False, context_mode="none",
    )

    assert job["agent"] == "agy"


def test_dispatch_agent_id_takes_precedence_over_story_id_for_gh_token_role(project_dir, monkeypatch):
    import synlynk as sl
    import synlynk.dispatch as dispatch_mod
    from synlynk import agent_cli

    class FakeProc:
        pid = 1

    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: FakeProc())
    monkeypatch.setattr(sl, "_preflight_dispatch", lambda agent_name, dispatch_flags, db_conn=None, _task_hint="": {"passed": True, "sentinel": None, "reason": None})

    captured_roles = []
    monkeypatch.setattr(
        dispatch_mod, "_resolve_dispatch_gh_token",
        lambda role: captured_roles.append(role) or "test-gh-token",
    )

    agent_id = agent_cli.cmd_agent_init("dev")

    sl.dispatch_agent(
        "grok", "review and merge PR #500", agent_id=agent_id, story_id="story-with-different-role",
        context_mode="none", requires_gh_write=True, force_agent=True,
    )

    assert captured_roles == ["dev"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_dispatch.py -k "auto_selects_harness or takes_precedence" -v`
Expected: FAIL — `test_dispatch_agent_id_auto_selects_harness_by_mapped_role` fails because `job["agent"]` is `"claude"` (no auto-selection happened); `test_dispatch_agent_id_takes_precedence_over_story_id_for_gh_token_role` fails because `captured_roles` is `[]` or contains the story's role, not `["dev"]`

- [ ] **Step 3: Add the org-role mapping and harness auto-selection**

In `synlynk/dispatch.py`, add the mapping table near the top of the file, immediately after the `from synlynk._constants import AGENT_CAPABILITY_BASELINES` import (line 18):

```python
_ORG_ROLE_TO_BASELINE_ROLE = {
    "dev": "builder",
    "qa": "verifier",
    "architect": "architect",
    "tpm": "architect",
    "pm": "architect",
    "designer": "builder",
    "marketing": "builder",
    "synlynk-bot": "builder",
}


def _harness_for_org_role(org_role: str, baselines_map: dict, requires_gh_write: bool = False):
    """Deterministic fallback harness selection for agent_id-driven dispatch.

    Picks the first harness (alphabetical) whose declared baseline "roles"
    (architect/builder/verifier — a different vocabulary than org-chart
    roles, see docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md §6)
    includes the mapped tag for this org role. Does not consult the
    story_id-based capability_scores DB table — that stays story_id-only.
    """
    baseline_role = _ORG_ROLE_TO_BASELINE_ROLE.get(org_role)
    if not baseline_role:
        return None
    for name in sorted(baselines_map):
        baseline = baselines_map[name]
        if baseline_role not in baseline.get("roles", []):
            continue
        if requires_gh_write and not baseline.get("can_gh_write", False):
            continue
        return name
    return None
```

Modify the existing block at lines 1957-1963 (the block right after the `resolved_agent_role` resolution added in Task 5):

```python
    if story_id and not force_agent:
        best_agent = _pkg("_best_agent_for_story")
        if best_agent:
            best = best_agent(story_id)
            if best and best in baselines_map:
                agent = best
    if resolved_agent_role and not force_agent and not (story_id and agent != agent):
        # Only fall back to agent_id-based selection if story_id routing (above)
        # didn't already pick something — story_id result always wins when present.
        if not story_id or agent not in baselines_map:
            picked = _harness_for_org_role(resolved_agent_role, baselines_map, requires_gh_write)
            if picked:
                agent = picked
```

Wait — that conditional is convoluted. Replace the whole block (both the existing `if story_id and not force_agent:` block and your new addition) with this single clean version instead:

```python
    if not force_agent:
        picked = None
        if story_id:
            best_agent = _pkg("_best_agent_for_story")
            if best_agent:
                best = best_agent(story_id)
                if best and best in baselines_map:
                    picked = best
        if picked is None and resolved_agent_role:
            picked = _harness_for_org_role(resolved_agent_role, baselines_map, requires_gh_write)
        if picked:
            agent = picked
```

This preserves existing behavior exactly when `agent_id` is not passed (picked stays `None` unless `story_id` routing succeeds, identical to today), and only engages `_harness_for_org_role` as a fallback when `story_id` routing didn't produce a pick.

- [ ] **Step 4: Thread agent-derived role into GitHub token resolution**

In `synlynk/dispatch.py`, modify `_build_subprocess_env`'s signature (line 385) to accept the resolved agent role:

```python
def _build_subprocess_env(agent: str, overrides: dict, requires_gh_write: bool, story_id: str, agent_role: str = None) -> dict:
```

Modify the role resolution inside it (line 410):

```python
    if requires_gh_write:
        role = agent_role or _role_for_story(story_id) or "dev"
        gh_token = _resolve_dispatch_gh_token(role)
```

Update the call site at line 2406:

```python
    proc_env = _build_subprocess_env(agent, overrides, requires_gh_write, story_id, agent_role=resolved_agent_role)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_dispatch.py -k "auto_selects_harness or takes_precedence" -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Run the full dispatch test file to check for regressions**

Run: `pytest tests/test_dispatch.py -v`
Expected: all tests pass, including the pre-existing `test_dispatch_agent_requires_gh_write_true_capable_agent_unchanged` and other story_id-based gh-write tests — confirms `agent_role=None` default preserves old behavior

- [ ] **Step 7: Commit**

```bash
git add synlynk/dispatch.py tests/test_dispatch.py
git commit -m "feat: dispatch_agent auto-selects harness and gh identity from agent_id"
```

---

## Task 7: `--as-agent` flag on `synlynk dispatch` CLI

**Files:**
- Modify: `synlynk/cli.py:576-639` (dispatch_parser block) and `synlynk/cli.py:1101-1150` (dispatch handler block)
- Test: `tests/test_dispatch.py` or `tests/test_agent_cli.py` (CLI-route test — place alongside the other `test_cli_agent_*` tests in `tests/test_agent_cli.py` from Task 4, since it's testing agent-CLI-facing behavior)

- [ ] **Step 1: Write the failing tests**

Append to `tests/test_agent_cli.py`:

```python
def test_cli_dispatch_as_agent_resolves_alias(project_dir, monkeypatch, capsys):
    from synlynk.cli import main
    import synlynk.dispatch as dispatch_mod

    main(["agent", "init", "dev"])
    capsys.readouterr()

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["agent"] = agent
        captured["agent_id"] = kwargs.get("agent_id")
        return {"id": "job-1", "pid": 1, "agent": agent}

    monkeypatch.setattr(dispatch_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr("synlynk.cli.dispatch_agent", fake_dispatch_agent)

    main(["dispatch", "codex", "--task", "do work", "--as-agent", "dev"])

    assert captured["agent"] == "codex"
    assert captured["agent_id"] is not None


def test_cli_dispatch_as_agent_unresolvable_exits_1(project_dir):
    from synlynk.cli import main

    with pytest.raises(SystemExit) as exc_info:
        main(["dispatch", "codex", "--task", "do work", "--as-agent", "nonexistent"])
    assert exc_info.value.code == 1


def test_cli_dispatch_as_agent_without_explicit_harness(project_dir, monkeypatch, capsys):
    from synlynk.cli import main
    import synlynk.dispatch as dispatch_mod

    main(["agent", "init", "dev"])
    capsys.readouterr()

    captured = {}

    def fake_dispatch_agent(agent, task, **kwargs):
        captured["agent"] = agent
        return {"id": "job-1", "pid": 1, "agent": agent}

    monkeypatch.setattr(dispatch_mod, "dispatch_agent", fake_dispatch_agent)
    monkeypatch.setattr("synlynk.cli.dispatch_agent", fake_dispatch_agent)

    main(["dispatch", "--task", "do work", "--as-agent", "dev"])

    assert "agent" in captured
```

Check the exact import path `synlynk.cli` uses for `dispatch_agent` before finalizing the `monkeypatch.setattr` targets:

```bash
grep -n "^from synlynk.dispatch import\|^import synlynk.dispatch" synlynk/cli.py
```

Adjust the `monkeypatch.setattr("synlynk.cli.dispatch_agent", ...)` line to match whatever name `cli.py` actually binds `dispatch_agent` to in its own module namespace (it's likely `from synlynk.dispatch import dispatch_agent`, in which case that setattr target is correct as written).

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_agent_cli.py -k "as_agent" -v`
Expected: FAIL — `error: unrecognized arguments: --as-agent`

- [ ] **Step 3: Make the `agent` positional optional and add `--as-agent`**

In `synlynk/cli.py`, modify the `dispatch_parser.add_argument("agent", ...)` block (lines 579-581):

```python
    dispatch_parser.add_argument("agent",
        nargs="?", default=None,
        choices=known_agents,
        help=f"Agent name: {', '.join(known_agents)}. Optional when --as-agent triggers auto-selection.")
```

Add a new argument, placed after the `--session` argument block (after line 638):

```python
    dispatch_parser.add_argument(
        "--as-agent",
        dest="as_agent",
        default=None,
        help="Dispatch as this workspace agent (ID or role alias). Resolves GitHub identity "
             "and, if the harness positional is omitted, auto-selects a harness by role fit.",
    )
```

- [ ] **Step 4: Resolve `--as-agent` in the dispatch handler**

In `synlynk/cli.py`, modify the `elif args.command == "dispatch":` block. Immediately after the `try:` (after line 1102), insert:

```python
            resolved_agent_id = None
            if getattr(args, "as_agent", None):
                from synlynk import agent_cli
                resolved_agent_id = agent_cli._resolve_or_exit(args.as_agent)
            if not args.agent and not resolved_agent_id:
                dispatch_parser.error("the following arguments are required: agent (unless --as-agent is given)")
```

Modify the `dispatch_agent(...)` call (line 1129) to pass `agent_id` and to fall back to a placeholder harness name when `args.agent` is `None` (auto-selection inside `dispatch_agent` — Task 6 — will overwrite it before use, but the parameter itself is positional and must be a string of a known harness for `AGENT_CAPABILITY_BASELINES` membership checks to not immediately fail; use the first known agent as a safe placeholder since auto-selection runs before the `if agent not in baselines_map` guard):

```python
            job = dispatch_agent(args.agent or known_agents[0], args.task, story_id=args.story_id,
                                 agent_id=resolved_agent_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 requires_gh_write=getattr(args, "requires_gh_write", False),
                                 task_type=getattr(args, "task_type", None),
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 scope_paths=getattr(args, "scope_paths", []),
                                 session_id=getattr(args, "session_id", None))
```

Also update the print line right after (line 1148) since `args.agent` may now be `None`:

```python
            print(f"  {_GREEN}▶{_RESET} [{job['id']}] {job['agent']} dispatched  PID {job['pid']}")
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agent_cli.py -k "as_agent" -v`
Expected: PASS (3 tests)

- [ ] **Step 6: Run the full suite**

Run: `pytest -q`
Expected: all tests pass (existing suite + all new tests from Tasks 1-7)

- [ ] **Step 7: Manual CLI smoke test**

```bash
cd /tmp && mkdir -p synlynk-smoke && cd synlynk-smoke && git init -q
python3 /Users/nikhilsoman/dev/synlynk/.worktrees/feat-agent-roles-phase1-cli/bin/synlynk.py agent init dev
python3 /Users/nikhilsoman/dev/synlynk/.worktrees/feat-agent-roles-phase1-cli/bin/synlynk.py agent list
python3 /Users/nikhilsoman/dev/synlynk/.worktrees/feat-agent-roles-phase1-cli/bin/synlynk.py agent show dev
python3 /Users/nikhilsoman/dev/synlynk/.worktrees/feat-agent-roles-phase1-cli/bin/synlynk.py dispatch --help
```

Expected: `agent init` prints `Created agent <uuid> (role: dev)`; `agent list` shows one row; `agent show dev` prints charter; `dispatch --help` shows both the (now optional) `agent` positional and the new `--as-agent` flag.

- [ ] **Step 8: Commit**

```bash
git checkout -- GEMINI.md 2>/dev/null || true
git add synlynk/cli.py tests/test_agent_cli.py
git commit -m "feat: add --as-agent flag to synlynk dispatch"
```

---

## Task 8: Final full-suite verification

**Files:** None (verification only)

- [ ] **Step 1: Run the full test suite**

Run: `pytest -q`
Expected: all tests pass, 0 failures (baseline was 1988 passed, 2 skipped before this plan — expect that count plus this plan's ~29 new tests, all passing)

- [ ] **Step 2: Discard any stray GEMINI.md modification**

```bash
git status --short
git checkout -- GEMINI.md 2>/dev/null || true
```

(Known recurring side effect of running pytest in this repo — see standing memory `gemini-md-stale-revert-884.md`.)

- [ ] **Step 3: Confirm no other unintended changes**

```bash
git status --short
```

Expected: clean working tree (everything already committed in Tasks 1-7).

---

## Self-Review Notes

**Spec coverage:** §3 (CLI surface) → Tasks 2-4. §4 (storage changes) → Task 1. §5.1 (agent_id as dispatch key, harness auto-selection, GitHub identity) → Tasks 5-6. §5.2 (`--as-agent` CLI flag) → Task 7. §5.3 (parallel fan-out) → no code required, confirmed in spec itself as "no new orchestration primitive," nothing to implement. §5.4 (unmediated tool/mode access) → no code required, confirmed as a deliberate non-restriction. §6 (naming-collision documentation) → addressed via the `_ORG_ROLE_TO_BASELINE_ROLE` design-decision section at the top of this plan and its docstring in `_harness_for_org_role`. §7 (error handling table) → Task 5 (unregistered/disabled agent_id) and Task 4 (CLI-level errors, inherited directly from the superseded spec's already-implemented error paths). §8 (testing) → all test names in Tasks 1-7 correspond to the spec's §8 bullet list.

**Placeholder scan:** no TBD/TODO; the one open item (confirming `cli.py`'s exact `main`/`dispatch_agent` import binding before finalizing a `monkeypatch.setattr` target in Tasks 4 and 7) is a verification step with an explicit grep command and fallback instruction, not a content placeholder — the test bodies themselves are complete.

**Type consistency:** `agent_id` parameter name and `resolved_agent_role`/`agent_role` variable names are used consistently across Task 5's signature change, Task 6's `_build_subprocess_env` change, and Task 7's CLI wiring. `SEED_CHARTERS`/`ROLES` in `agent_cli.py` (Task 2) match the 8-role `choices=` list in the Task 4 `cli.py` subparser.
