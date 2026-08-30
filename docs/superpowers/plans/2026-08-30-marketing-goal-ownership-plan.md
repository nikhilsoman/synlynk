# Marketing Goal Ownership Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give the marketing role standing, autonomous ownership of the readership-growth outcome (`goal-0c4e96ff`) by (1) documenting that ownership in the marketing charter, and (2) fixing the TPM sweep so ready stories tagged `role="marketing"` actually dispatch to the correct harness (Agy) instead of being silently misrouted to Codex.

**Architecture:** Two independent, additive changes. First, a charter text edit (`synlynk/agent_cli.py`) plus its evidence-log addendum (`docs/charters/corpus-references.md`) — pure documentation, no runtime behavior. Second, a policy + dispatch fix: add a `"marketing"` entry to the `agent_roles` table in `synlynk/policy.py`'s `DEFAULT_WORKSPACE_POLICY`, then change `synlynk/tpm_sweep.py::run_sweep_pass()` to resolve the dispatch harness from that table (keyed by the story's `role`) instead of hardcoding `"codex"`. This is a strictly broader fix than the literal design-spec text anticipated — today `tpm_sweep.py` has **zero** role-based harness routing for *any* role, not just marketing, so the fix generalizes correctly rather than special-casing marketing.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest (existing `isolated_db`/`project_dir` fixtures in `tests/conftest.py`).

---

### Task 1: Add `marketing` to the policy's `agent_roles` table

**Files:**
- Modify: `synlynk/policy.py:53-58`
- Test: `tests/test_policy.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_policy.py`:

```python
def test_agent_roles_includes_marketing_harness_agy(tmp_path, monkeypatch):
    from synlynk.policy import load_policy

    monkeypatch.setenv("HOME", str(tmp_path))
    policy = load_policy(repo_path=str(tmp_path))
    assert policy["agent_roles"]["marketing"] == {
        "default_harness": "agy",
        "scope": ["content", "blog", "comms"],
    }
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_policy.py::test_agent_roles_includes_marketing_harness_agy -v`
Expected: FAIL with `KeyError: 'marketing'`

- [ ] **Step 3: Add the marketing entry**

In `synlynk/policy.py`, the `agent_roles` dict currently reads (lines 53-58):

```python
        "agent_roles": {
            "pm": {"default_harness": "claude", "scope": ["roadmap", "review", "deploy", "brainstorm"]},
            "qa": {"default_harness": "claude", "scope": ["review", "merge"]},
            "dev": {"default_harness": "codex", "scope": ["implement", "test"]},
            "architect": {"default_harness": "claude", "scope": ["roadmap", "brainstorm"]},
        },
```

Change it to:

```python
        "agent_roles": {
            "pm": {"default_harness": "claude", "scope": ["roadmap", "review", "deploy", "brainstorm"]},
            "qa": {"default_harness": "claude", "scope": ["review", "merge"]},
            "dev": {"default_harness": "codex", "scope": ["implement", "test"]},
            "architect": {"default_harness": "claude", "scope": ["roadmap", "brainstorm"]},
            "marketing": {"default_harness": "agy", "scope": ["content", "blog", "comms"]},
        },
```

This matches the capability-routing table already documented in `CLAUDE.md` (Agy = implement/test/css/templates/content/subpages) and the marketing charter's existing "routed to Agy" language — it was simply never encoded in the machine-readable policy table.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_policy.py::test_agent_roles_includes_marketing_harness_agy -v`
Expected: PASS

- [ ] **Step 5: Run full policy test suite to check for regressions**

Run: `python3 -m pytest tests/test_policy.py tests/test_policy_cli.py -v`
Expected: All PASS (no existing test asserts the exact contents of `agent_roles`, only specific keys like `pm`/`architect`, so this is additive-safe)

- [ ] **Step 6: Commit**

```bash
git add synlynk/policy.py tests/test_policy.py
git commit -m "feat: add marketing role to agent_roles harness routing table"
```

---

### Task 2: Route TPM sweep dispatches by role instead of hardcoding codex

**Files:**
- Modify: `synlynk/tpm_sweep.py:1-86`
- Test: `tests/test_tpm_sweep.py`

**Context:** `run_sweep_pass()` currently calls `dispatch_agent("codex", ...)` unconditionally for every ready story regardless of `story["role"]`. This means a `role="marketing"` story would be dispatched to Codex, contradicting the marketing charter and `CLAUDE.md`'s own routing table. Task 1 added the lookup table (`policy["agent_roles"][role]["default_harness"]`); this task wires it in.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_tpm_sweep.py`:

```python
def test_run_sweep_pass_routes_marketing_role_to_agy(isolated_db, project_dir):
    story_id = cmd_story_create(title="write blog post", story_id="story-5", role="marketing")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-5", "agent": "agy"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    mock_dispatch.assert_called_once()
    called_harness = mock_dispatch.call_args[0][0]
    assert called_harness == "agy"


def test_run_sweep_pass_routes_dev_role_to_codex(isolated_db, project_dir):
    story_id = cmd_story_create(title="fix bug", story_id="story-6", role="dev")
    cmd_story_ready(story_id)
    with patch("synlynk.tpm_sweep.check_authority") as mock_auth, \
            patch("synlynk.tpm_sweep.dispatch_agent") as mock_dispatch:
        mock_auth.return_value = MagicMock(allowed=True, requires_approval=False)
        mock_dispatch.return_value = {"id": "job-6", "agent": "codex"}
        summary = run_sweep_pass()
    assert summary["advanced"] == 1
    called_harness = mock_dispatch.call_args[0][0]
    assert called_harness == "codex"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_tpm_sweep.py::test_run_sweep_pass_routes_marketing_role_to_agy tests/test_tpm_sweep.py::test_run_sweep_pass_routes_dev_role_to_codex -v`
Expected: `test_run_sweep_pass_routes_marketing_role_to_agy` FAILS (`called_harness == "codex"`, not `"agy"`); `test_run_sweep_pass_routes_dev_role_to_codex` PASSES already (codex is the current hardcoded value, this test just guards against regressing it)

- [ ] **Step 3: Implement role-based harness resolution**

Replace the full contents of `synlynk/tpm_sweep.py` with:

```python
"""Run one policy-gated autonomous TPM sweep pass."""
from __future__ import annotations

import os
from typing import Dict

from synlynk.approval_gate import raise_approval_ticket
from synlynk.db import _find_ticket, _insert_ticket, _mark_ticket_consumed
from synlynk.dispatch import dispatch_agent
from synlynk.events import emit_awaiting_approval
from synlynk.policy import check_authority, load_policy

_FALLBACK_HARNESS = "codex"


def _ready_stories() -> list:
    from synlynk.db import _get_db

    conn = _get_db()
    try:
        rows = conn.execute(
            "SELECT story_id, title, role FROM stories WHERE readiness='ready' "
            "AND NOT EXISTS (SELECT 1 FROM daemon_jobs dj "
            "WHERE dj.story_id=stories.story_id "
            "AND dj.status IN ('queued','running','done'))"
        ).fetchall()
        return [
            {"story_id": row[0], "title": row[1], "role": row[2] or "dev"}
            for row in rows
        ]
    finally:
        conn.close()


def _resolve_harness(role: str, repo_path: str) -> str:
    """Look up the default dispatch harness for a story's role.

    Falls back to codex (the pre-existing hardcoded behavior) for any role
    with no entry in policy["agent_roles"], so unmapped roles keep working
    exactly as before this change.
    """
    policy = load_policy(repo_path=repo_path)
    role_entry = policy.get("agent_roles", {}).get(role)
    if role_entry and role_entry.get("default_harness"):
        return role_entry["default_harness"]
    return _FALLBACK_HARNESS


def run_sweep_pass(assignee: str = "nikhilsoman") -> Dict[str, int]:
    """Dispatch each ready, undispatched story after checking policy authority."""
    summary = {"advanced": 0, "parked": 0, "failed": 0}
    repo_path = os.getcwd()

    for story in _ready_stories():
        authority = check_authority(
            "task_dispatch:implement",
            role=story["role"],
            repo_path=repo_path,
        )
        if not authority.allowed:
            summary["failed"] += 1
            continue

        if authority.requires_approval:
            action = "task_dispatch:implement"
            resolved_ticket = _find_ticket(story["story_id"], action, "resolved")
            if resolved_ticket:
                _mark_ticket_consumed(resolved_ticket["id"])
                # Fall through to dispatch below, same as an allowed authority.
            else:
                if not _find_ticket(story["story_id"], action, "open"):
                    emit_awaiting_approval(
                        story["story_id"],
                        action,
                        authority.reason,
                    )
                    issue_url = raise_approval_ticket(
                        story_id=story["story_id"],
                        action=action,
                        reason=authority.reason,
                        assignee=assignee,
                        context=f"Story: {story['title']}",
                    )
                    if issue_url:
                        _insert_ticket(story["story_id"], action, issue_url)
                summary["parked"] += 1
                continue

        try:
            harness = _resolve_harness(story["role"], repo_path)
            dispatch_agent(
                harness,
                story["title"],
                story_id=story["story_id"],
                task_type="implement",
                context_mode="full",
                role=story["role"],
            )
            summary["advanced"] += 1
        except Exception:
            summary["failed"] += 1

    return summary
```

The only behavioral changes from the original: a new `_resolve_harness()` helper, and the `dispatch_agent(...)` call's first argument changes from the literal `"codex"` to `harness`. Everything else (approval-ticket handling, `_ready_stories()` query, summary counters) is unchanged.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_tpm_sweep.py -v`
Expected: All PASS, including both new tests and the five pre-existing tests (which all use `mock_dispatch.return_value = {"id": ..., "agent": "codex"}` for `role=None`-defaulting-to-`"dev"` stories, which still resolves to `"codex"` via `_FALLBACK_HARNESS`)

- [ ] **Step 5: Commit**

```bash
git add synlynk/tpm_sweep.py tests/test_tpm_sweep.py
git commit -m "fix: route TPM sweep dispatches by role instead of hardcoding codex"
```

---

### Task 3: Marketing charter edit — Workflow Ownership addition

**Files:**
- Modify: `synlynk/agent_cli.py` (the `SEED_CHARTERS["marketing"]` entry)
- Test: none (documentation/text content; existing charter-schema validation tests must still pass)

- [ ] **Step 1: Locate the current marketing charter entry**

`SEED_CHARTERS["marketing"]` is a Python string literal at `synlynk/agent_cli.py:154-175`. Its last two lines (174-175) are:

```python
        "## Workflow Ownership\n\n"
        "Owns the Blog/Comms pass of the Named Release stage.\n"
    ),
```

- [ ] **Step 2: Edit the Workflow Ownership section**

Replace those two lines (`synlynk/agent_cli.py:173-175`) with:

```python
        "## Workflow Ownership\n\n"
        "Owns the Blog/Comms pass of the Named Release stage. Also owns the\n"
        "standing readership-growth outcome tracked as goal-0c4e96ff (book\n"
        "manuscript + blog series), fed by stories the PM links to that goal —\n"
        "dispatched automatically per the TPM sweep's role-based routing (see\n"
        "synlynk/tpm_sweep.py), not on every PR.\n"
    ),
```

Leave `schema_version`, `role`, `description`, `durability`, `tools`, `credentials` frontmatter (lines 155-162) and the `## Instructions` / `## Authority & Escalation` sections (lines 163-172) completely unchanged — the design spec (`docs/superpowers/specs/2026-08-30-marketing-goal-ownership-design.md`) explicitly scopes this to a Workflow Ownership addition only, with no change to `durability` (stays `dispatch-only`) or to marketing's authority.

- [ ] **Step 3: Validate charter schema still parses**

Run: `python3 -m pytest tests/test_charter_schema.py -v` (or the closest-matching existing charter validation test file — run `grep -rl "SEED_CHARTERS\|charter_schema" tests/` first if the exact filename differs)
Expected: All PASS — confirms the edited charter text still satisfies `REQUIRED_SECTIONS`/`REQUIRED_FRONTMATTER_KEYS` parsing in `synlynk/charter_schema.py`

- [ ] **Step 4: Commit**

```bash
git add synlynk/agent_cli.py
git commit -m "docs: extend marketing charter with goal-0c4e96ff ownership"
```

---

### Task 4: Corpus-references addendum for the charter change

**Files:**
- Modify: `docs/charters/corpus-references.md` (marketing section)

- [ ] **Step 1: Read the existing marketing section's format**

Run: `grep -n "^## marketing\|^### marketing" docs/charters/corpus-references.md` to find the section, and read it in full to match its existing "Sources consulted / Findings / Charter changes made" structure.

- [ ] **Step 2: Append an addendum entry**

Add a new dated sub-entry under the marketing section (do not remove or edit the existing entry — this is an addendum, not a rewrite):

```markdown
### 2026-08-30 addendum: goal-0c4e96ff ownership

**Sources consulted:** `docs/superpowers/specs/2026-08-30-marketing-goal-ownership-design.md`
(approved design spec, PR #1294), `goal-0c4e96ff` story linkage (22 stories,
18 primary / 4 secondary via `goal_contributions`).

**Findings:** Unlike the original charter's Blog/Comms scope (evidenced by
actual PR history), this addition is a forward-looking, explicitly-approved
standing responsibility rather than a corpus-evidenced pattern — the readership
metrics needed to eventually evidence it are tracked as a prerequisite story
(`story-33ab504a`), not yet instrumented.

**Charter changes made:** Added one sentence to `## Workflow Ownership`
naming `goal-0c4e96ff` ownership, dispatched via the TPM sweep's role-based
routing (`synlynk/tpm_sweep.py`, Task 2 of this plan) rather than per-PR.
No change to `durability`, `Authority & Escalation`, or `Instructions`.
```

- [ ] **Step 3: Commit**

```bash
git add docs/charters/corpus-references.md
git commit -m "docs: log corpus-references addendum for marketing goal ownership"
```

---

## Self-Review Notes

- **Spec coverage:** Design spec's three "Changes" items are covered — Change 1 (charter edit) → Task 3+4; Change 2 (TPM sweep extension) → Task 1+2, generalized to fix the pre-existing zero-role-routing gap rather than a marketing-only special case, per the corrected understanding of `tpm_sweep.py`'s actual current behavior. Change 3 (backlog process — no code) requires no task.
- **Goal-linkage eligibility:** No SQL change to `_ready_stories()` was needed — it already selects any `readiness='ready'` story regardless of `goal_id`/`goal_contributions`, so goal-`0c4e96ff`-linked marketing stories are already eligible for sweep once marked ready. The actual gap was purely the harness-routing one fixed in Task 2.
- **Placeholder scan:** No TBD/TODO markers; all code blocks are complete, no elisions.
- **Type consistency:** `_resolve_harness(role: str, repo_path: str) -> str` signature matches its single call site in `run_sweep_pass()`; `dispatch_agent`'s first positional arg (`agent: str`) matches `harness`.
