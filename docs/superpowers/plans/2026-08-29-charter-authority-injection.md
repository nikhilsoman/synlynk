# Charter Authority Injection Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give workspace agent charters actual behavioral authority by (1) adding a reassignable `human_authority_role` pointer to policy, (2) moving `pm`/`architect` into the same capability-routed `task_allocation` table every other role uses, and (3) injecting the resolved role's charter into the context every `synlynk dispatch` and `synlynk exec` invocation actually receives.

**Architecture:** Three sequential, independently-shippable changes per the approved design (`docs/superpowers/specs/2026-08-27-charter-authority-design.md`, §3): a policy schema addition, a policy-table migration, then a single injector wired into the one context-assembly function (`generate_context()` in `synlynk/context.py`) that both `dispatch_agent()` and `exec_command()` already call. No new parallel injection path.

**Tech Stack:** Python 3 stdlib, pytest, existing `synlynk/policy.py`, `synlynk/agent_store.py`, `synlynk/context.py`, `synlynk/dispatch.py`.

---

## File Structure

- Modify `synlynk/policy.py` — add `human_authority_role` to `DEFAULT_WORKSPACE_POLICY["defaults"]`, add a `get_human_authority_role()` accessor, move `pm`/`architect` task-types into `dev_authority.task_allocation`.
- Modify `.synlynk/policy.json` (this repo's own override) — mirror the same `task_allocation` additions so this repo's dispatch behavior actually changes, not just the library default.
- Create `synlynk/charter_injection.py` — the injector: resolves `human_authority_role`, loads that role's registered agent, reads its charter via `agent_store.read_charter()`, and renders a `## Role Charter` section. Kept as its own module (not stuffed into `context.py`, which is already large) with one clear entry point: `render_charter_section(repo_path: str) -> str`.
- Modify `synlynk/context.py:generate_context()` — call `charter_injection.render_charter_section()` and write its output into the assembled context, guarded so a missing/failed charter read surfaces loudly rather than silently producing an empty section (per spec §5).
- Test: `tests/test_policy.py` — human_authority_role default/override coverage.
- Test: `tests/test_charter_injection.py` — new file, the injector's resolution and error-handling logic.
- Test: `tests/test_context.py` — assert `generate_context()` output includes charter content end-to-end (create this file if it doesn't already exist — check first).
- Test: `tests/test_dispatch.py` — add a regression case confirming a `pm`/`architect` dispatch resolves through `task_allocation` like any other role.

---

## Task 1: `human_authority_role` policy primitive

**Files:**
- Modify: `synlynk/policy.py`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write the failing test for the default value**

Add to `tests/test_policy.py`:

```python
def test_load_policy_defaults_human_authority_role_to_pm(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    assert policy["human_authority_role"] == {"role": "pm", "requires_human_approval": True}


def test_get_human_authority_role_reads_pointer(tmp_path, monkeypatch):
    from synlynk.policy import get_human_authority_role

    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    assert get_human_authority_role(repo_path=str(repo)) == "pm"


def test_get_human_authority_role_reads_repo_override(tmp_path, monkeypatch):
    from synlynk.policy import get_human_authority_role

    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo_policy_path = repo / ".synlynk" / "policy.json"
    _write_json(repo_policy_path, {
        "schema_version": 1,
        "repo_id": "test",
        "overrides": {
            "human_authority_role": {"role": "architect", "requires_human_approval": True},
        },
    })
    assert get_human_authority_role(repo_path=str(repo)) == "architect"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_policy.py -k human_authority -v`
Expected: FAIL — `KeyError: 'human_authority_role'` and `ImportError: cannot import name 'get_human_authority_role'`

- [ ] **Step 3: Add the pointer to the default policy and the accessor**

In `synlynk/policy.py`, inside `DEFAULT_WORKSPACE_POLICY["defaults"]` (alongside `merge_authority`/`release_authority`), add:

```python
        "human_authority_role": {"role": "pm", "requires_human_approval": True},
```

Then add a new function, placed after `load_policy()`:

```python
def get_human_authority_role(repo_path: str, workspace_name: str = "default") -> str:
    """Return the role slug currently holding 'represents the human' authority.

    Defaults to 'pm' if unset (matching pre-existing implicit behavior), per
    spec error-handling §5 (docs/superpowers/specs/2026-08-27-charter-authority-design.md).
    """
    policy = load_policy(repo_path=repo_path, workspace_name=workspace_name)
    pointer = policy.get("human_authority_role") or {}
    return pointer.get("role") or "pm"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_policy.py -v`
Expected: PASS (all tests in the file, including pre-existing ones — confirms no regression to the merge-rule behavior)

- [ ] **Step 5: Commit**

```bash
git add synlynk/policy.py tests/test_policy.py
git commit -m "feat: add human_authority_role policy pointer (#1201)"
```

---

## Task 2: Migrate `pm`/`architect` into `task_allocation`

**Files:**
- Modify: `synlynk/policy.py`
- Modify: `.synlynk/policy.json`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_policy.py`:

```python
def test_task_allocation_covers_pm_and_architect_task_types(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    policy = load_policy(repo_path=str(repo), workspace_name="default")
    table = policy["dev_authority"]["task_allocation"]
    assert table["pm"]["harness"] == "claude"
    assert table["brainstorm"]["harness"] == "claude"
    assert table["architecture-review"]["harness"] == "claude"


def test_check_authority_task_dispatch_pm_allowed(tmp_path, monkeypatch):
    from synlynk.policy import check_authority

    monkeypatch.setenv("HOME", str(tmp_path))
    repo = tmp_path / "repo"
    repo.mkdir()
    result = check_authority("task_dispatch:pm", role="pm", repo_path=str(repo))
    assert result.allowed
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_policy.py -k "task_allocation_covers or task_dispatch_pm" -v`
Expected: FAIL — `KeyError: 'pm'`

- [ ] **Step 3: Add the new task-types to `DEFAULT_WORKSPACE_POLICY`**

In `synlynk/policy.py`, inside `dev_authority.task_allocation` (both the module-level default and mirroring what's in this repo's own `.synlynk/policy.json`), add:

```python
                "pm": {"harness": "claude", "fallback": []},
                "brainstorm": {"harness": "claude", "fallback": []},
                "architecture-review": {"harness": "claude", "fallback": []},
```

Per spec §4: minimal/empty fallback list initially, consistent with how `css`/`templates`/`content`/`subpages` are scoped to `agy` alone today. Do **not** touch `agent_roles` (`pm`/`architect` entries there stay — that dict is a display/default-harness convenience, not the authority gate; `dev_authority.task_allocation` is what `check_authority("task_dispatch:...")` actually reads).

- [ ] **Step 4: Mirror the same entries in this repo's own policy override**

Edit `.synlynk/policy.json` — add the same three keys to `overrides.dev_authority.task_allocation`:

```json
        "pm": {"harness": "claude", "fallback": []},
        "brainstorm": {"harness": "claude", "fallback": []},
        "architecture-review": {"harness": "claude", "fallback": []}
```

(Recall `load_policy()`'s merge rule: a repo override REPLACES the whole `dev_authority` object one level deep, not a recursive merge — so this repo's `.synlynk/policy.json` needs the full existing table plus these three, not just the three alone. Confirm by re-reading the file before editing; don't drop the pre-existing 14 entries.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_policy.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/policy.py .synlynk/policy.json tests/test_policy.py
git commit -m "feat: route pm/architect through task_allocation, retiring Claude-only carve-out (#1201, amends #79)"
```

---

## Task 3: Charter injector module

**Files:**
- Create: `synlynk/charter_injection.py`
- Test: `tests/test_charter_injection.py`

- [ ] **Step 1: Write the failing tests**

Create `tests/test_charter_injection.py`:

```python
import pytest

from synlynk import agent_store
from synlynk.charter_injection import render_charter_section, CharterInjectionError


def _register_pm_with_charter(repo_dir, monkeypatch, content="# PM Charter\n\nDo PM things.\n"):
    monkeypatch.chdir(repo_dir)
    agent_id = "pm-primary"
    agent_store.register_agent(agent_id, [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(agent_id, content, actor="test", parent_revision=0)
    return agent_id


def test_render_charter_section_includes_resolved_role_charter(project_dir, tmp_path, monkeypatch):
    _register_pm_with_charter(project_dir, monkeypatch)
    section = render_charter_section(repo_path=str(project_dir))
    assert "## Role Charter" in section
    assert "Do PM things." in section
    assert "pm" in section


def test_render_charter_section_resolves_reassigned_role(project_dir, tmp_path, monkeypatch):
    import json
    monkeypatch.chdir(project_dir)
    agent_store.register_agent("architect-primary", [{"kind": "role_slug", "value": "architect"}])
    agent_store.propose_charter_revision(
        "architect-primary", "# Architect Charter\n\nDesign things.\n", actor="test", parent_revision=0,
    )
    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.write_text(json.dumps({
        "schema_version": 1,
        "repo_id": "test",
        "overrides": {
            "human_authority_role": {"role": "architect", "requires_human_approval": True},
        },
    }))
    section = render_charter_section(repo_path=str(project_dir))
    assert "Design things." in section


def test_render_charter_section_raises_loudly_when_no_agent_registered(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    with pytest.raises(CharterInjectionError, match="no registered agent"):
        render_charter_section(repo_path=str(project_dir))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_charter_injection.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.charter_injection'`

- [ ] **Step 3: Implement the injector**

Create `synlynk/charter_injection.py`:

```python
"""Resolves the current human_authority_role and surfaces its charter into
dispatch/exec context. See docs/superpowers/specs/2026-08-27-charter-authority-design.md.

Never branches on role == "pm" — the resolved role is read from policy, and
whichever role currently holds human_authority_role is treated identically.
"""
from synlynk import agent_store
from synlynk.policy import get_human_authority_role


class CharterInjectionError(Exception):
    """Raised when the resolved authority role has no charter to inject.

    Per spec §5: an unset/unregistered authority role is a configuration
    error, not a normal state — callers must not silently swallow this into
    an empty charter section.
    """


def _find_agent_for_role(role: str):
    for entry in agent_store.list_agents():
        role_slug = next(
            (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
        )
        if role_slug == role and not entry.get("disabled"):
            return entry
    return None


def render_charter_section(repo_path: str) -> str:
    """Return a '## Role Charter' Markdown section for the resolved
    human_authority_role, or raise CharterInjectionError.
    """
    role = get_human_authority_role(repo_path=repo_path)
    entry = _find_agent_for_role(role)
    if entry is None:
        raise CharterInjectionError(
            f"human_authority_role is {role!r} but no registered agent has "
            f"role_slug {role!r} (see agent_store.list_agents()) — an unset "
            f"authority role is a configuration error, not a normal state."
        )
    content, revision = agent_store.read_charter(entry["agent_id"])
    if not content.strip():
        raise CharterInjectionError(
            f"role {role!r} (agent_id {entry['agent_id']!r}) has no charter content "
            f"(revision {revision}) — charter injection failures must not silently "
            f"produce an empty section."
        )
    return (
        f"## Role Charter ({role}, revision {revision})\n\n"
        f"{content.strip()}\n\n---\n\n"
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_charter_injection.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_injection.py tests/test_charter_injection.py
git commit -m "feat: add charter_injection module resolving human_authority_role to charter content (#1201)"
```

---

## Task 4: Wire the injector into `generate_context()`

**Files:**
- Modify: `synlynk/context.py` (function `generate_context`, `synlynk/context.py:233`)
- Test: `tests/test_context.py` (create if it doesn't exist — run `ls tests/test_context.py` first to check)

- [ ] **Step 1: Check whether `tests/test_context.py` already exists**

Run: `ls tests/test_context.py`

If it exists, read it fully before adding to it (append in its existing style). If it doesn't exist, create it fresh in Step 2.

- [ ] **Step 2: Write the failing test**

Add (or create the file with) this test:

```python
import os

from synlynk import agent_store
from synlynk.context import generate_context


def test_generate_context_includes_resolved_role_charter(project_dir, tmp_path, monkeypatch):
    monkeypatch.chdir(project_dir)
    agent_store.register_agent("pm-primary", [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        "pm-primary", "# PM Charter\n\nDo PM things.\n", actor="test", parent_revision=0,
    )
    context_text = generate_context(scope="full", out_path=str(project_dir / ".synlynk" / "context.md"))
    assert "## Role Charter" in context_text
    assert "Do PM things." in context_text


def test_generate_context_raises_when_authority_role_unregistered(project_dir, tmp_path, monkeypatch):
    import pytest
    from synlynk.charter_injection import CharterInjectionError

    monkeypatch.chdir(project_dir)
    with pytest.raises(CharterInjectionError):
        generate_context(scope="full", out_path=str(project_dir / ".synlynk" / "context.md"))
```

Note: `project_dir` is the existing fixture in `tests/conftest.py` — it chdirs into a tmp repo with `project-docs/` and `.synlynk/` already created, so `agent_store` calls resolve their workspace correctly.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_context.py -k role_charter -v`
Expected: FAIL — first test fails because the section is missing; second test fails because no exception is raised yet (charter injection isn't wired in, so nothing raises)

- [ ] **Step 4: Wire the injector into `generate_context()`**

In `synlynk/context.py`, inside `generate_context()` (the non-DB branch — the function already early-returns to `_generate_context_from_db` when migrated, so add this in the flat-file path only, matching where `_is_migrated()` is False), add near the top of the `with open(context_file, "w") as out:` block, right after the `Generated:` line is written and before the sentinel-alerts section:

```python
        from synlynk.charter_injection import render_charter_section
        out.write(render_charter_section(repo_path=os.getcwd()))
```

This intentionally lets `CharterInjectionError` propagate — per spec §5, charter injection failures must surface loudly, not be swallowed into an empty section. Do not wrap this in a `try/except`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_context.py -v`
Expected: PASS

- [ ] **Step 6: Run the full context and dispatch test suites to check for regressions**

Run: `python3 -m pytest tests/test_context.py tests/test_dispatch.py tests/test_charter_injection.py tests/test_policy.py tests/test_agent_store.py -v`
Expected: PASS. If any pre-existing `test_dispatch.py` test asserts on `generate_context()` output without first registering a `pm`-role agent in its fixture, it will now fail with `CharterInjectionError` — that is a real gap the test needs to close (register a minimal pm agent + charter in that test's setup), not a reason to add a silent fallback in the injector.

- [ ] **Step 7: Commit**

```bash
git add synlynk/context.py tests/test_context.py
git commit -m "feat: inject resolved role's charter into generate_context() output (#1201)"
```

---

## Task 5: Confirm `synlynk exec` (native IDE sessions) gets the same injection

**Files:**
- Read: `synlynk/dispatch.py:2909` (`exec_command`)
- Test: `tests/test_dispatch.py`

- [ ] **Step 1: Confirm `exec_command()` already calls the shared `generate_context()`**

Run: `grep -n "generate_context" synlynk/dispatch.py`

Per the earlier repo scan, `exec_command()` (around `synlynk/dispatch.py:2929`) calls `generate_context()` directly (no scope/out_path args, full-context default) — the same function Task 4 modified. If this is confirmed, no code change is needed here: the injection is already live for native sessions once Task 4 lands, closing the spec's "native-IDE-session gap" (§2, Q1) for free.

- [ ] **Step 2: Write a regression test asserting this**

Add to `tests/test_dispatch.py` (find the existing test class/module structure first and match its fixture style):

```python
def test_exec_command_context_includes_charter(project_dir, tmp_path, monkeypatch, capsys):
    from synlynk import agent_store
    from synlynk.dispatch import exec_command

    monkeypatch.chdir(project_dir)
    agent_store.register_agent("pm-primary", [{"kind": "role_slug", "value": "pm"}])
    agent_store.propose_charter_revision(
        "pm-primary", "# PM Charter\n\nDo PM things.\n", actor="test", parent_revision=0,
    )
    monkeypatch.setattr("synlynk.dispatch.subprocess.run", lambda *a, **kw: type("R", (), {"returncode": 0, "stdout": "", "stderr": ""})())
    exec_command(["echo", "hi"])
    context_text = (project_dir / ".synlynk" / "context.md").read_text()
    assert "## Role Charter" in context_text
```

Adjust the `subprocess.run` monkeypatch target/shape to match however `exec_command()` actually invokes the subprocess — read the function body at `synlynk/dispatch.py:2909` first and mirror an existing `test_dispatch.py` test that already exercises `exec_command()`, rather than guessing the mock shape blind.

- [ ] **Step 3: Run test to verify it passes**

Run: `python3 -m pytest tests/test_dispatch.py -k exec_command_context_includes_charter -v`
Expected: PASS

- [ ] **Step 4: Commit**

```bash
git add tests/test_dispatch.py
git commit -m "test: confirm synlynk exec inherits charter injection via shared generate_context() (#1201)"
```

---

## Task 6: Update the design's flagged follow-on — reconcile pm's seed charter

**Files:**
- Read: `synlynk/agent_cli.py` (`SEED_CHARTERS["pm"]`)
- Modify: whichever charter content file/mechanism currently holds `pm`'s revision-2 charter (check via `synlynk agent show pm` or `agent_store.read_charter()` for the currently-registered pm agent in this repo's own workspace)

- [ ] **Step 1: Compare the two charter texts**

Run: `python3 -c "from synlynk.agent_cli import SEED_CHARTERS; print(SEED_CHARTERS['pm'])"` and separately dump the currently-live pm charter (`synlynk agent show pm` from repo root, or read the file `agent_store.agent_store_path(<pm-agent-id>)/charter.md` for this repo's registered pm agent).

- [ ] **Step 2: Merge, don't replace**

Per spec §8.1, the live revision-2 charter (generic spec-derived prose) should be merged with the richer `SEED_CHARTERS["pm"]` content (weekly competitive-intel sweep, capability/marketing-gap doc, feature-proposal escalation) — the seed content should not be silently dropped. Write the merged Markdown.

- [ ] **Step 3: Propose the revision**

Use `agent_store.propose_charter_revision()` (or the `synlynk agent edit pm <path>` CLI, if available in this repo's installed version) with the merged content, `parent_revision` matching the current head.

- [ ] **Step 4: Commit**

```bash
git add -A
git commit -m "fix: reconcile pm charter's overwritten seed content per spec §8.1 (#1201)"
```

---

## Self-Review Notes (for whoever executes this plan)

- **Do not** add a `try/except` around `render_charter_section()` anywhere in the dispatch/context path — spec §5 is explicit that missing-charter failures must surface loudly. If a test seems to want a silent fallback, that test's fixture is missing agent registration, not the production code missing error handling.
- **Do not** branch on `role == "pm"` anywhere in `charter_injection.py` or its call site — the whole point of Q4 is that reassigning `human_authority_role` requires zero code change.
- Tasks 1–2 (`policy.py` + `.synlynk/policy.json`) can land as one PR per the spec's step 1+2, or be split further — they have no interdependency with Tasks 3–5. Tasks 3–5 depend on Task 1 (the `human_authority_role` pointer must exist before the injector can resolve it — spec §3).
- Task 6 is content cleanup flagged in the spec as "bundled into the implementation PR" (§8.1) — fine to fold into whichever PR lands Task 4, or ship as a fast-follow; it has no code dependency on Tasks 1–5.
- This plan does not cover spec §8.2 (`synlynk decide --record` writing to a gitignored path) — that is explicitly filed as a separate issue per the spec's own scope note.
