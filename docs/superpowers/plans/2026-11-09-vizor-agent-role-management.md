# Vizor Agent Role Management ("Agent Studio") Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**GOVERNS goal:** `goal-658aa384` — parent tracking issue: gh:#5185. Every dispatched task below must link this goal (`synlynk goal link <story_id> --goal goal-658aa384` once a story exists for the task, or `--story-id`/`--goal` on the dispatch call itself).

**Goal:** Close the Vizor role-management gap (dead "Edit Charter" button, no dispatchable `maintainer`, no FTUE role-provisioning flow, no unified capability inventory) by activating a 10-role taxonomy, replacing the dead charter UI with a real BAU editor and a 5-step FTUE wizard, and introducing a Capability Registry — while landing the four hosted-Team/Enterprise forward-compat seams (`workspace_id`, `identity_binding`, attributable/append-only audit, manifest provenance) and the four governance gates (audited writes, `capability_ratings` wiring, deprecation/revocation lifecycle, trust/dedup gate) from Phase 1 onward, per `docs/superpowers/specs/2026-11-09-vizor-agent-role-management-design.md` §3a/§3b/§6.

**Architecture:** Extends three existing subsystems rather than building parallel ones: `synlynk/agent_store.py`'s already-versioned, actor-attributed `propose_charter_revision`/`_write_versioned_file` mechanism gains an `actor_type` classification and a `workspace_id` stamp (no new audit table); `synlynk/charter_schema.py`'s `KNOWN_ROLES` enum and frontmatter parser gain `secops`/`infra-devops` and two new optional nested-dict fields (`identity_binding`, `policy_refs`); `synlynk/viz/server.py`'s existing-but-hidden `_handle_role_create` handler and `synlynk/viz/roles.py`'s dead UI become the real BAU editor and FTUE wizard, gated by `synlynk/viz/write_routes.py`. `capability_ratings` activation seeding follows the exact pattern already used for the `local` harness in `synlynk/local_agent_seed.py`.

**Tech Stack:** Python 3 stdlib only (no third-party deps — matches repo convention), SQLite (`state.db`, via `synlynk/db.py`/`db_schema.py`), hand-rolled YAML-subset frontmatter parser (`charter_schema.py`), stdlib `http.server`-based Vizor UI (`synlynk/viz/`), `pytest` for tests.

---

## Phase sequencing (from spec §6, re-ordered per §3a governance gates)

1. **Taxonomy activation + audited writes + capability_ratings wiring + §3b seams** (this plan's largest phase — the governance/forward-compat gates land here, not retrofitted later)
2. BAU charter editor (replace dead "Edit Charter" button)
3. Role lifecycle: deprecation/merge + GitHub App identity revocation
4. FTUE 5-step wizard
5. Native hook catalog (Capability Registry, native-code-hook source)
6. Capability Registry local source (harness-installed MCPs/Skills)
7. Trust/dedup gate (§3a.4) — a precondition for remote-connector ingestion and the upstream feature-request flow, both of which remain **out of scope** for this plan per spec §7 (filed as a follow-on once this gate exists)
8. TPM charter tool-use migration for GitHub sync — added per decide panel decision `2026-11-09-decide-panel-should-bidirectional-sync-w`; wraps `gh sync-roadmap` as a Capability Registry entry, migrates `tpm`'s charter into `agent_store`

---

# Phase 1: Taxonomy activation, audited writes, capability_ratings wiring, §3b seams

### Task 1: Add `secops` and `infra-devops` to the known-role enum

**Files:**
- Modify: `synlynk/charter_schema.py:11-13`
- Test: `tests/test_charter_schema.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_charter_schema.py`:

```python
def test_known_roles_includes_secops_and_infra_devops():
    from synlynk.charter_schema import KNOWN_ROLES
    assert "secops" in KNOWN_ROLES
    assert "infra-devops" in KNOWN_ROLES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_schema.py::test_known_roles_includes_secops_and_infra_devops -v`
Expected: FAIL — `assert "secops" in KNOWN_ROLES` is False

- [ ] **Step 3: Implement**

In `synlynk/charter_schema.py`, change:

```python
KNOWN_ROLES = (
    "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot", "maintainer",
)
```

to:

```python
KNOWN_ROLES = (
    "dev", "qa", "pm", "architect", "tpm", "designer", "marketing", "synlynk-bot", "maintainer",
    "secops", "infra-devops",
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_schema.py::test_known_roles_includes_secops_and_infra_devops -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/charter_schema.py tests/test_charter_schema.py
git commit -m "feat(charters): add secops and infra-devops to known-role enum"
```

---

### Task 2: Add `actor_type` classification and `workspace_id` stamp to charter revisions

This is the §3a.1/§3b.1/§3b.3 seam: every charter write already goes through `agent_store.propose_charter_revision` (versioned, attributable, append-only `charter.revisions.jsonl`). It is missing (a) a human/agent/service classification of `actor` and (b) an explicit `workspace_id` field on each revision entry, both required before a hosted multi-tenant Vizor can filter/audit at scale.

**Files:**
- Modify: `synlynk/agent_store.py:246-307` (`_write_versioned_file`, `propose_charter_revision`)
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_agent_store.py`:

```python
def test_propose_charter_revision_rejects_invalid_actor_type(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(tmp_path / "fake_home")))
    from synlynk import agent_store
    content = (
        "---\nschema_version: 1\nrole: dev\ndescription: \"x\"\n"
        "durability: dispatch-only\ntools: []\ncredentials: []\n---\n\n"
        "## Instructions\n\nDo work.\n\n## Authority & Escalation\n\nEscalate.\n\n"
        "## Workflow Ownership\n\nOwn it.\n"
    )
    with pytest.raises(ValueError, match="actor_type"):
        agent_store.propose_charter_revision(
            "dev-test", content, actor="someone", parent_revision=0, actor_type="robot"
        )


def test_propose_charter_revision_stamps_actor_type_and_workspace_id(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(tmp_path / "fake_home")))
    from synlynk import agent_store
    content = (
        "---\nschema_version: 1\nrole: dev\ndescription: \"x\"\n"
        "durability: dispatch-only\ntools: []\ncredentials: []\n---\n\n"
        "## Instructions\n\nDo work.\n\n## Authority & Escalation\n\nEscalate.\n\n"
        "## Workflow Ownership\n\nOwn it.\n"
    )
    agent_store.propose_charter_revision(
        "dev-test", content, actor="nikhil", parent_revision=0, actor_type="human"
    )
    base = agent_store.agent_store_path("dev-test")
    with open(f"{base}/charter.revisions.jsonl") as fh:
        entry = json.loads(fh.readline())
    assert entry["actor_type"] == "human"
    assert entry["workspace_id"] == agent_store.get_workspace_id()
```

Add `import json` and `import pytest` at the top of `tests/test_agent_store.py` if not already present (check first with `grep -n "^import" tests/test_agent_store.py`).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py -k "actor_type" -v`
Expected: FAIL — `propose_charter_revision() got an unexpected keyword argument 'actor_type'`

- [ ] **Step 3: Implement**

In `synlynk/agent_store.py`, change `_write_versioned_file`:

```python
def _write_versioned_file(
    file_path: str,
    revisions_path: str,
    content: str,
    actor: str,
    parent_revision: int,
    actor_type: str = "service",
) -> int:
    """Write a new revision of a single-file versioned artifact.

    Raises RevisionConflictError on stale parent_revision.
    """
    _, current_revision = _read_versioned_file(file_path, revisions_path)
    if parent_revision != current_revision:
        raise RevisionConflictError(
            f"parent_revision {parent_revision} does not match current head {current_revision}"
        )
    parent_hash = None
    if current_revision > 0:
        with open(file_path) as f:
            parent_hash = _content_hash(f.read())

    os.makedirs(os.path.dirname(file_path), exist_ok=True)
    with open(file_path, "w") as f:
        f.write(content)

    new_revision = current_revision + 1
    entry = {
        "revision": new_revision,
        "parent_hash": parent_hash,
        "content_hash": _content_hash(content),
        "actor": actor,
        "actor_type": actor_type,
        "workspace_id": get_workspace_id(),
        "timestamp": _now_iso(),
    }
    with open(revisions_path, "a") as f:
        f.write(json.dumps(entry) + "\n")
    return new_revision
```

And `propose_charter_revision`:

```python
_VALID_ACTOR_TYPES = ("human", "agent", "service")


def propose_charter_revision(
    agent_id: str, content: str, actor: str, parent_revision: int,
    actor_type: str = "service",
) -> int:
    """Write a new charter revision if parent_revision matches the current head.

    actor_type must be classifiable as 'human', 'agent', or 'service' (§3a.1/§3b.3
    audit-immutability seam) — no auto-approval logic is included; the gated
    mutability tier is out of scope.
    """
    if actor_type not in _VALID_ACTOR_TYPES:
        raise ValueError(
            f"actor_type {actor_type!r} must be one of {_VALID_ACTOR_TYPES}"
        )
    charter_schema.validate_charter(content)
    base = agent_store_path(agent_id)
    return _write_versioned_file(
        os.path.join(base, "charter.md"),
        os.path.join(base, "charter.revisions.jsonl"),
        content,
        actor,
        parent_revision,
        actor_type=actor_type,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py -k "actor_type" -v`
Expected: PASS (both tests)

- [ ] **Step 5: Run full agent_store + charters test suites to check for regressions**

Run: `pytest tests/test_agent_store.py tests/test_charters.py tests/test_autonomous_role_charters.py -v`
Expected: PASS — existing callers of `propose_charter_revision` (e.g. `tests/test_charters.py`'s `_register_charter` helper, `synlynk/charters.py`'s `sync_dispatch_routing`) omit `actor_type` and get the `"service"` default, so no existing call site breaks.

- [ ] **Step 6: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "feat(agent_store): classify charter-write actors and stamp workspace_id

Additive seam from the 2026-11-09 decide-panel re-run (spec §3b.1/.3):
every charter revision now carries actor_type (human/agent/service) and
workspace_id, laying the ground for a hosted Vizor to filter/audit by
tenant without a later migration. Existing callers default to
actor_type='service' — zero behavioral change."
```

---

### Task 3: Update existing charter-writing call sites to pass the real `actor_type`

**Files:**
- Modify: `synlynk/viz/server.py:619` (`_handle_role_create`)
- Modify: `synlynk/charters.py` (`sync_dispatch_routing`'s call into `propose_charter_revision` — already passes through `agent_store.propose_charter_revision`, no change needed there since it's a deterministic sync, default `"service"` is correct)
- Test: `tests/test_viz_roles.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_viz_roles.py`:

```python
def test_handle_role_create_stamps_human_actor_type(monkeypatch):
    from synlynk import agent_store

    calls = {}
    monkeypatch.setattr(agent_store, "list_agents", lambda: [])
    monkeypatch.setattr(agent_store, "register_agent", lambda agent_id, aliases: None)
    monkeypatch.setattr(
        agent_store, "propose_charter_revision",
        lambda *args, **kwargs: calls.update(kwargs) or 1,
    )
    VizorHandler.__new__(VizorHandler)._handle_role_create({"role": "security-auditor", "durability": "durable"})
    assert calls.get("actor_type") == "human"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py::test_handle_role_create_stamps_human_actor_type -v`
Expected: FAIL — `calls.get("actor_type")` is `None`

- [ ] **Step 3: Implement**

In `synlynk/viz/server.py`, change the final line of `_handle_role_create` (currently line 619):

```python
        agent_store.propose_charter_revision(agent_id, charter, actor="vizor", parent_revision=0)
```

to:

```python
        agent_store.propose_charter_revision(
            agent_id, charter, actor="vizor", parent_revision=0, actor_type="human",
        )
```

(A Vizor UI action is always a human operator clicking through the browser — there is no autonomous agent path through this handler.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py::test_handle_role_create_stamps_human_actor_type -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/server.py tests/test_viz_roles.py
git commit -m "feat(viz): stamp human actor_type on Vizor-initiated charter writes"
```

---

### Task 4: Add `workspace_id` and `identity_binding` frontmatter fields to new charter templates

The existing hand-rolled frontmatter parser (`charter_schema.py`'s `parse_frontmatter`) already supports a nested `key:\n  subkey: value` block as a dict (lines 81-89) — `identity_binding` needs no new parsing code, only new charter content and validation-tolerance (unknown frontmatter keys are already ignored by `validate_charter`, so this is purely additive).

**Files:**
- Modify: `synlynk/agent_cli.py` (`SEED_CHARTERS` dict) — add `"secops"` and `"infra-devops"` entries
- Test: `tests/test_charter_schema.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_charter_schema.py`:

```python
def test_seed_charter_secops_has_identity_binding_and_workspace_id():
    from synlynk.agent_cli import SEED_CHARTERS
    from synlynk.charter_schema import parse_frontmatter, split_frontmatter

    content = SEED_CHARTERS["secops"]
    frontmatter_text, _ = split_frontmatter(content)
    data = parse_frontmatter(frontmatter_text)
    assert data["workspace_id"] == "local"
    assert data["identity_binding"] == {"provider": "github_app", "subject": "secops"}
    assert data["policy_refs"] == {}


def test_seed_charter_infra_devops_has_identity_binding_and_workspace_id():
    from synlynk.agent_cli import SEED_CHARTERS
    from synlynk.charter_schema import parse_frontmatter, split_frontmatter

    content = SEED_CHARTERS["infra-devops"]
    frontmatter_text, _ = split_frontmatter(content)
    data = parse_frontmatter(frontmatter_text)
    assert data["workspace_id"] == "local"
    assert data["identity_binding"] == {"provider": "github_app", "subject": "infra-devops"}
    assert data["policy_refs"] == {}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_charter_schema.py -k "secops or infra_devops" -v`
Expected: FAIL — `KeyError: 'secops'` (no such key in `SEED_CHARTERS` yet)

- [ ] **Step 3: Implement**

In `synlynk/agent_cli.py`, add two new entries to the `SEED_CHARTERS` dict (after the existing `"qa"` entry, matching its exact structural style):

```python
    "secops": (
        "---\n"
        "schema_version: 1\n"
        "role: secops\n"
        'description: "Security operations — cross-cutting review veto and DLP policy ownership."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "workspace_id: local\n"
        "identity_binding:\n"
        "  provider: github_app\n"
        "  subject: secops\n"
        "policy_refs: {}\n"
        "---\n\n"
        "## Instructions\n\n"
        "Security operations: reviews changes that touch credentials, secret handling,\n"
        "third-party connector ingestion, or data egress. Owns the DLP policy this\n"
        "workspace's charters reference by id via `policy_refs.dlp` — the policy\n"
        "document itself is a separate, not-yet-built policy-enforcement-point\n"
        "artifact (spec §3b design-now-build-later); this charter only references it.\n\n"
        "## Authority & Escalation\n\n"
        "Holds cross-cutting veto authority over any PR or dispatch that matches a\n"
        "secops-relevant trigger (secret scanning hit, new remote connector, credential\n"
        "scope change) — may block merge unilaterally. Escalates to whoever holds\n"
        "`human_authority_role` before approving an exception to its own veto.\n\n"
        "## Workflow Ownership\n\n"
        "Owns the secops review gate across all roles' PR-lifecycle enforcement.\n"
    ),
    "infra-devops": (
        "---\n"
        "schema_version: 1\n"
        "role: infra-devops\n"
        'description: "Infrastructure & DevOps — runtime/pipeline health and deploy execution."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "workspace_id: local\n"
        "identity_binding:\n"
        "  provider: github_app\n"
        "  subject: infra-devops\n"
        "policy_refs: {}\n"
        "---\n\n"
        "## Instructions\n\n"
        "Infrastructure and DevOps: owns runtime/pipeline health monitoring and deploy\n"
        "execution. References this workspace's infra policy (preferred cloud providers,\n"
        "VPC/network configuration, IAM) by id via `policy_refs.infra` — the policy\n"
        "document itself is a separate, not-yet-built schema (spec §3b\n"
        "design-now-build-later), expected once Horizon 3's cloud swarm runners land.\n\n"
        "## Authority & Escalation\n\n"
        "Decides deploy timing and rollback unilaterally within an approved release.\n"
        "Escalates to whoever holds `human_authority_role` before provisioning new\n"
        "cloud infrastructure outside the referenced infra policy's bounds.\n\n"
        "## Workflow Ownership\n\n"
        "Owns runtime/pipeline health and the deploy-execution stage of the\n"
        "end-to-end workflow.\n"
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_charter_schema.py -k "secops or infra_devops" -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_cli.py tests/test_charter_schema.py
git commit -m "feat(charters): seed secops and infra-devops charters with identity_binding/policy_refs"
```

---

### Task 5: Register `secops` and `infra-devops` as real dispatchable agents

**Files:**
- Create: `synlynk/role_activation.py`
- Test: `tests/test_role_activation.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_role_activation.py`:

```python
import json

import pytest


def _fake_home(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(fake_home)))


def test_activate_role_registers_agent_and_writes_charter(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import agent_store, role_activation

    role_activation.activate_role("secops", actor="nikhil", actor_type="human")

    agent_ids = [e["agent_id"] for e in agent_store.list_agents()]
    assert "secops" in agent_ids
    charter, revision = agent_store.read_charter("secops")
    assert "role: secops" in charter
    assert revision == 1


def test_activate_role_is_idempotent(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import role_activation

    role_activation.activate_role("secops", actor="nikhil", actor_type="human")
    role_activation.activate_role("secops", actor="nikhil", actor_type="human")

    from synlynk import agent_store
    agent_ids = [e["agent_id"] for e in agent_store.list_agents()]
    assert agent_ids.count("secops") == 1


def test_activate_role_rejects_unknown_role(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import role_activation

    with pytest.raises(ValueError, match="no seed charter"):
        role_activation.activate_role("not-a-real-role", actor="nikhil", actor_type="human")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_activation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.role_activation'`

- [ ] **Step 3: Implement**

Create `synlynk/role_activation.py`:

```python
"""Activates a known role as a real, dispatchable agent: registers it in the
agent_store registry and writes its first charter revision.

Idempotent — calling activate_role() for an already-registered role_slug is
a no-op. Does not provision a GitHub App identity; call
synlynk identity init --role <role> separately (Phase 1 Task 6 wires this
into the same CLI command this module's caller uses).
"""
from synlynk import agent_store


def activate_role(role: str, actor: str, actor_type: str = "human") -> str:
    """Register `role` as a dispatchable agent and write its seed charter.

    Returns the agent_id (same as `role` for activated roles — no suffix,
    unlike Vizor's ad-hoc _handle_role_create which mints a random one).
    Raises ValueError if `role` has no entry in agent_cli.SEED_CHARTERS.
    """
    from synlynk.agent_cli import SEED_CHARTERS

    existing_ids = {e["agent_id"] for e in agent_store.list_agents()}
    if role in existing_ids:
        return role

    seed = SEED_CHARTERS.get(role)
    if not seed:
        raise ValueError(f"no seed charter for role {role!r}; add one to agent_cli.SEED_CHARTERS first")

    agent_store.register_agent(role, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(
        role, seed, actor=actor, parent_revision=0, actor_type=actor_type,
    )
    return role
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_activation.py -v`
Expected: PASS (all three tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/role_activation.py tests/test_role_activation.py
git commit -m "feat: add role_activation.activate_role for registering real dispatchable agents"
```

---

### Task 6: Promote `maintainer` to a dispatchable agent with the same mechanism

`maintainer` already has a full charter in `synlynk/charters.py`'s `DEFAULT_ROLE_CHARTERS` (mandate, `autonomous_authorities`, `escalation_triggers`, `wake_cycle_sop`) but is absent from `agent_store.list_agents()` — this is the exact gap the spec's §1 names. Promoting it means giving it a markdown charter (via `agent_cli.SEED_CHARTERS`, matching the other roles' format) rather than leaving it JSON-only, since `agent_store`/`charter_schema` only understand the markdown format.

**Files:**
- Modify: `synlynk/agent_cli.py` (`SEED_CHARTERS` — add `"maintainer"` entry)
- Test: `tests/test_role_activation.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_role_activation.py`:

```python
def test_activate_maintainer_role(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    from synlynk import agent_store, role_activation

    role_activation.activate_role("maintainer", actor="nikhil", actor_type="human")

    charter, _ = agent_store.read_charter("maintainer")
    assert "worktree_cleanup" in charter
    assert "release_cut" in charter
    assert "identity_binding" in charter
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_activation.py::test_activate_maintainer_role -v`
Expected: FAIL — `ValueError: no seed charter for role 'maintainer'`

- [ ] **Step 3: Implement**

Add to `synlynk/agent_cli.py`'s `SEED_CHARTERS` dict, transcribing the mandate/authorities/triggers already present in `synlynk/charters.py`'s `DEFAULT_ROLE_CHARTERS["maintainer"]` into the markdown format the other seeds use:

```python
    "maintainer": (
        "---\n"
        "schema_version: 1\n"
        "role: maintainer\n"
        'description: "Repository and workspace substrate hygiene."\n'
        "durability: durable\n"
        "tools: []\n"
        "credentials: []\n"
        "workspace_id: local\n"
        "identity_binding:\n"
        "  provider: github_app\n"
        "  subject: maintainer\n"
        "autonomous_authorities:\n"
        "  - worktree_cleanup\n"
        "  - policy_sync\n"
        "  - sentinel_triage\n"
        "  - release_cut\n"
        "escalation_triggers:\n"
        "  - invariant_violation_detected\n"
        "  - budget_exceeded\n"
        "  - irreversible_action_required\n"
        "  - database_corruption_detected\n"
        "---\n\n"
        "## Instructions\n\n"
        "Maintain repository and workspace substrate hygiene: prune merged worktrees,\n"
        "reconcile policy drift, triage sentinel alerts, and monitor database\n"
        "integrity. Wake-cycle SOP: (1) worktree cleanup via\n"
        "`synlynk worktree clean --apply`; (2) sentinel triage via\n"
        "`synlynk maintainer triage`, archiving alerts older than 7 days; (3) verify\n"
        "state.db WAL checkpointing and foreign-key integrity; (4) check\n"
        "`.synlynk/policy.json` and role charters for schema drift, notify pm on\n"
        "discrepancy.\n\n"
        "## Authority & Escalation\n\n"
        "Decides worktree cleanup, policy sync, and sentinel triage unilaterally.\n"
        "`release_cut` and other irreversible actions escalate to whoever holds\n"
        "`human_authority_role` until the governing dispatch contract for that\n"
        "authority is built (tracked as a spec §8 open item — this charter states\n"
        "the authority, it does not yet grant an unsupervised code path to it).\n\n"
        "## Workflow Ownership\n\n"
        "Owns worktree hygiene, sentinel alert triage, and state.db integrity\n"
        "monitoring across the workspace.\n"
    ),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_activation.py::test_activate_maintainer_role -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/agent_cli.py tests/test_role_activation.py
git commit -m "feat(charters): seed maintainer's markdown charter so it can be activated

Transcribes the existing DEFAULT_ROLE_CHARTERS['maintainer'] JSON charter's
mandate/authorities/triggers into the markdown+frontmatter format
agent_store/charter_schema require for a real dispatchable registration.
release_cut stays escalation-gated — no unsupervised code path exists for
it yet; promoting the identity does not silently grant the authority."
```

---

### Task 7: Wire `synlynk agent activate` CLI command to `role_activation.activate_role` + GitHub App provisioning

**Files:**
- Modify: `synlynk/cli.py` (add `agent activate` subcommand near the existing `agent` subparsers)
- Test: `tests/test_role_activation.py`

- [ ] **Step 1: Find the existing `agent` subparser group**

Run: `grep -n 'add_parser("agent"' synlynk/cli.py`

Confirm there is an `agent_sub = agent_parser.add_subparsers(...)` block (the same one `agent_configure_parser` in Task structure context belongs to, per the earlier grounding read of `synlynk/cli.py:905-911`).

- [ ] **Step 2: Write the failing test**

Add to `tests/test_role_activation.py`:

```python
def test_cli_agent_activate_calls_role_activation(tmp_path, monkeypatch, capsys):
    _fake_home(tmp_path, monkeypatch)
    import sys
    from synlynk import cli

    monkeypatch.setattr(sys, "argv", ["synlynk", "agent", "activate", "secops"])
    cli.main()

    from synlynk import agent_store
    agent_ids = [e["agent_id"] for e in agent_store.list_agents()]
    assert "secops" in agent_ids
```

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_role_activation.py::test_cli_agent_activate_calls_role_activation -v`
Expected: FAIL — `SystemExit` (argparse rejects unknown subcommand `activate`) or similar

- [ ] **Step 4: Implement**

In `synlynk/cli.py`, locate the `agent` subparser block (search for `agent_configure_parser = agent_sub.add_parser` to find the right `agent_sub` variable name) and add immediately after it:

```python
    agent_activate_parser = agent_sub.add_parser(
        "activate", help="Register a known role as a real dispatchable agent"
    )
    agent_activate_parser.add_argument("role")
```

Then find the dispatch block for `elif args.command == "agent":` and add a branch (matching the existing `elif args.agent_action == "configure":` style found nearby):

```python
        elif args.agent_action == "activate":
            from synlynk.role_activation import activate_role
            from synlynk.attribution import current_actor_identity  # existing 3-tier attribution helper

            actor, actor_type = current_actor_identity()
            agent_id = activate_role(args.role, actor=actor, actor_type=actor_type)
            print(f"  activated role '{agent_id}' as a dispatchable agent")
            print(f"  provision its GitHub App identity with: synlynk identity init --role {agent_id}")
```

If `synlynk.attribution` has no `current_actor_identity()` helper (check with `grep -n "^def " synlynk/attribution.py`), use the simpler, always-correct fallback instead — a CLI invocation is always a human at the keyboard:

```python
        elif args.agent_action == "activate":
            from synlynk.role_activation import activate_role
            import getpass

            agent_id = activate_role(args.role, actor=getpass.getuser(), actor_type="human")
            print(f"  activated role '{agent_id}' as a dispatchable agent")
            print(f"  provision its GitHub App identity with: synlynk identity init --role {agent_id}")
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_role_activation.py::test_cli_agent_activate_calls_role_activation -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_role_activation.py
git commit -m "feat(cli): add 'synlynk agent activate <role>' command"
```

---

### Task 8: Seed `capability_ratings` for every newly activated role at activation time (§3a.2)

Follows the exact pattern `synlynk/local_agent_seed.py` already establishes for the `local` harness: one synthetic calibration story + one `capability_ratings` row per starter task-type coordinate, `signal_source='seed'`, idempotent via `INSERT OR IGNORE`/`WHERE NOT EXISTS`.

**Files:**
- Create: `synlynk/role_activation_seed.py`
- Modify: `synlynk/role_activation.py` (call the seeder from `activate_role`)
- Test: `tests/test_role_activation.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_role_activation.py`:

```python
def test_activate_role_seeds_capability_ratings(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    import sqlite3
    from synlynk import db, role_activation

    conn = db.get_connection()
    role_activation.activate_role("secops", actor="nikhil", actor_type="human")

    rows = conn.execute(
        "SELECT COUNT(*) FROM capability_ratings WHERE agent='secops' AND signal_source='seed'"
    ).fetchone()
    assert rows[0] > 0
```

(If `synlynk.db` has no bare `get_connection()` — check with `grep -n "^def get_connection\|^def connect" synlynk/db.py` — use whichever existing accessor `tests/test_agent_store.py` or `tests/test_charters.py` already use to reach `state.db` in a temp-chdir'd test, and substitute that call here instead.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_activation.py::test_activate_role_seeds_capability_ratings -v`
Expected: FAIL — `rows[0] > 0` is False (0 rows seeded)

- [ ] **Step 3: Implement**

Create `synlynk/role_activation_seed.py`, modeled directly on `synlynk/local_agent_seed.py`:

```python
"""Seeds a starter capability_ratings bucket for a newly activated role,
per spec §3a.2 ('every activated role gets a capability_ratings task-type
bucket at activation, not after the fact'). Mirrors local_agent_seed.py's
pattern: one synthetic calibration story + one capability_ratings row per
starter coordinate, idempotent, signal_source='seed'.
"""

MODEL_VERSION = "role-activation-seed-1.0"

# (discipline, org_domain, stage, engg_domain, industry, phase, estimated_tokens)
# per role — a narrow starter envelope matching each role's §2 mandate, not
# a claim of measured capability. Real job completions widen it over time
# via the normal capability-rating write path, same as local_agent_seed.py.
ROLE_STARTER_COORDINATES = {
    "secops": [
        ("security", "platform", "execute", "security", "unknown", "build", 1000),
    ],
    "infra-devops": [
        ("infra", "platform", "execute", "infra", "unknown", "build", 1200),
    ],
    "maintainer": [
        ("platform", "platform", "execute", "platform", "unknown", "build", 600),
    ],
}

SEED_QUALITY = 0.6


def seed_role_capability_envelope(conn, role: str) -> None:
    """Idempotently seed capability_ratings for `role`. No-op if role is unknown."""
    coordinates = ROLE_STARTER_COORDINATES.get(role)
    if not coordinates:
        return
    owns_transaction = not conn.in_transaction
    if owns_transaction:
        conn.execute("BEGIN IMMEDIATE")
    try:
        for i, (discipline, org_domain, stage, engg_domain, industry, phase,
                est_tokens) in enumerate(coordinates):
            story_id = f"{role}-activation-seed-{i:02d}"
            conn.execute(
                "INSERT OR IGNORE INTO stories "
                "(story_id, engg_domain, org_domain, industry, phase, estimated_tokens) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (story_id, engg_domain, org_domain, industry, phase, est_tokens),
            )
            conn.execute(
                "INSERT INTO capability_ratings (story_id, agent, model_version, "
                "split_model, engg_domain, discipline, org_domain, role, stage, "
                "industry, phase, signal_source, quality) "
                "SELECT ?, ?, ?, 0, ?, ?, ?, ?, ?, ?, ?, 'seed', ? "
                "WHERE NOT EXISTS (SELECT 1 FROM capability_ratings "
                "WHERE story_id=? AND agent=? AND signal_source='seed')",
                (story_id, role, MODEL_VERSION, engg_domain, discipline, org_domain,
                 role, stage, industry, phase, SEED_QUALITY, story_id, role),
            )
        if owns_transaction:
            conn.commit()
    except Exception:
        if owns_transaction:
            conn.rollback()
        raise
```

Update `synlynk/role_activation.py`'s `activate_role` to call it:

```python
def activate_role(role: str, actor: str, actor_type: str = "human") -> str:
    """..."""
    from synlynk.agent_cli import SEED_CHARTERS
    from synlynk import db
    from synlynk.role_activation_seed import seed_role_capability_envelope

    existing_ids = {e["agent_id"] for e in agent_store.list_agents()}
    if role in existing_ids:
        return role

    seed = SEED_CHARTERS.get(role)
    if not seed:
        raise ValueError(f"no seed charter for role {role!r}; add one to agent_cli.SEED_CHARTERS first")

    agent_store.register_agent(role, [{"kind": "role_slug", "value": role}])
    agent_store.propose_charter_revision(
        role, seed, actor=actor, parent_revision=0, actor_type=actor_type,
    )
    seed_role_capability_envelope(db.get_connection(), role)
    return role
```

(Replace `db.get_connection()` with whatever the Task 8 Step 1 grep found to be the real accessor, keeping the same call shape.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_activation.py::test_activate_role_seeds_capability_ratings -v`
Expected: PASS

- [ ] **Step 5: Run the full Phase 1 test surface together**

Run: `pytest tests/test_charter_schema.py tests/test_agent_store.py tests/test_charters.py tests/test_viz_roles.py tests/test_role_activation.py -v`
Expected: PASS, 0 failures

- [ ] **Step 6: Commit**

```bash
git add synlynk/role_activation_seed.py synlynk/role_activation.py tests/test_role_activation.py
git commit -m "feat: seed capability_ratings for every role at activation time (spec §3a.2)

No activated role goes unmeasured from day one — mirrors the existing
local_agent_seed.py pattern (synthetic calibration story + seed-quality
capability_ratings row), so routing never falls back to a hand-authored
lock for a role that simply hasn't run a real job yet."
```

---

Phase 1 complete. `secops`, `infra-devops`, and `maintainer` are now real dispatchable agents with charters carrying `workspace_id`/`identity_binding`/`policy_refs`, every charter write is actor-type-classified and workspace-stamped, and every one has a `capability_ratings` starter bucket. GitHub App identity provisioning (`synlynk identity init --role <role>`) is a separate, already-existing command — Task 7's printed hint points the operator at it; this plan does not re-implement identity provisioning, which `synlynk/team.py:cmd_identity_init_role` already does in full.

---

# Phase 2: BAU charter editor (replace the dead "Edit Charter" button)

### Task 9: Add a charter-update Vizor route and handler

**Files:**
- Modify: `synlynk/viz/write_routes.py`
- Modify: `synlynk/viz/server.py` (add `_handle_charter_update`, `_handle_charter_update_request`, register the route)
- Test: `tests/test_viz_roles.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_viz_roles.py`:

```python
def test_handle_charter_update_writes_new_revision(monkeypatch):
    from synlynk import agent_store

    calls = {}
    monkeypatch.setattr(agent_store, "read_charter", lambda agent_id: (
        "---\nschema_version: 1\nrole: secops\ndescription: \"x\"\n"
        "durability: durable\ntools: []\ncredentials: []\n---\n\n"
        "## Instructions\n\nOld mandate.\n\n## Authority & Escalation\n\nOld.\n\n"
        "## Workflow Ownership\n\nOld.\n",
        1,
    ))
    monkeypatch.setattr(
        agent_store, "propose_charter_revision",
        lambda *args, **kwargs: calls.update(kwargs) or 2,
    )
    result = VizorHandler.__new__(VizorHandler)._handle_charter_update({
        "agent_id": "secops", "parent_revision": 1,
        "mandate": "New mandate text.",
    })
    assert result["ok"] is True
    assert result["revision"] == 2
    assert calls.get("actor_type") == "human"


def test_handle_charter_update_conflict_on_stale_revision(monkeypatch):
    from synlynk import agent_store

    monkeypatch.setattr(agent_store, "read_charter", lambda agent_id: ("---\nrole: secops\n---\n\n## Instructions\n\nx\n", 3))

    def _raise(*args, **kwargs):
        raise agent_store.RevisionConflictError("stale")
    monkeypatch.setattr(agent_store, "propose_charter_revision", _raise)

    result = VizorHandler.__new__(VizorHandler)._handle_charter_update({
        "agent_id": "secops", "parent_revision": 1, "mandate": "New mandate.",
    })
    assert result["ok"] is False
    assert "conflict" in result["error"].lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py -k charter_update -v`
Expected: FAIL — `AttributeError: 'VizorHandler' object has no attribute '_handle_charter_update'`

- [ ] **Step 3: Implement**

In `synlynk/viz/write_routes.py`, change:

```python
    "roles/create": "hide",
```

to:

```python
    "roles/create": "keep",
    "roles/charter/update": "keep",
```

In `synlynk/viz/server.py`, add after `_handle_role_create_request` (after line 633):

```python
    def _handle_charter_update(self, payload: dict) -> dict:
        """Apply an edited field onto an existing charter and write a new revision.

        Only the free-text body sections the BAU editor exposes (mandate ->
        Instructions section body) are supported in this first cut; structural
        frontmatter fields (role, durability) are not editable here — that
        remains a CLI-only / role-lifecycle (Phase 3) operation.
        """
        from synlynk import agent_store

        agent_id = str(payload.get("agent_id") or "").strip()
        if not agent_id:
            return {"ok": False, "error": "agent_id required"}
        try:
            parent_revision = int(payload.get("parent_revision"))
        except (TypeError, ValueError):
            return {"ok": False, "error": "parent_revision must be an integer"}
        mandate = str(payload.get("mandate") or "").strip()
        if not mandate:
            return {"ok": False, "error": "mandate must not be empty"}

        content, current_revision = agent_store.read_charter(agent_id)
        if current_revision != parent_revision:
            return {
                "ok": False,
                "error": f"conflict: charter has moved to revision {current_revision}, "
                         f"reload before editing",
            }

        header = "## Instructions"
        if header not in content:
            return {"ok": False, "error": "charter has no Instructions section to update"}
        before, _, after = content.partition(header)
        next_header_idx = after.find("\n## ")
        rest = after[next_header_idx:] if next_header_idx != -1 else ""
        new_content = f"{before}{header}\n\n{mandate}\n{rest}"

        try:
            new_revision = agent_store.propose_charter_revision(
                agent_id, new_content, actor="vizor", parent_revision=parent_revision,
                actor_type="human",
            )
        except agent_store.RevisionConflictError as exc:
            return {"ok": False, "error": f"conflict: {exc}"}
        return {"ok": True, "revision": new_revision}

    def _handle_charter_update_request(self):
        try:
            payload = self._read_json_body()
        except (json.JSONDecodeError, TypeError, ValueError):
            self.send_error(400, "Invalid JSON")
            return
        try:
            result = self._handle_charter_update(payload)
        except Exception as exc:
            self.send_error(500, str(exc))
            return
        self._send_json_ok(result)
```

Then register the route by adding `"/roles/charter/update"` to the `valid_paths` tuple (currently line 264) and adding a dispatch branch next to `elif clean_path == "/roles/create":` (currently lines 285-286):

```python
        elif clean_path == "/roles/charter/update":
            self._handle_charter_update_request()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py -k charter_update -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/write_routes.py synlynk/viz/server.py tests/test_viz_roles.py
git commit -m "feat(viz): add /roles/charter/update route for the BAU charter editor"
```

---

### Task 10: Replace the dead "Edit Charter" button with a working editor drawer

**Files:**
- Modify: `synlynk/viz/roles.py`
- Test: `tests/test_viz_roles.py`

- [ ] **Step 1: Write the failing test**

Replace the existing `test_generate_roles_html_has_synlynk_identity_note_without_create_form` test in `tests/test_viz_roles.py` (it currently asserts the editor does NOT exist — that assertion is exactly what Phase 2 invalidates) with:

```python
def test_generate_roles_html_renders_working_charter_editor():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert 'data-agent-id="pm-primary"' in rendered
    assert "/roles/charter/update" in rendered
    assert "<textarea" in rendered
```

Keep `test_handler_handle_role_create` as-is (Phase 1/pre-existing `roles/create` behavior is unchanged by this task).

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py::test_generate_roles_html_renders_working_charter_editor -v`
Expected: FAIL — no `<textarea` present, no `/roles/charter/update` string in output

- [ ] **Step 3: Implement**

In `synlynk/viz/roles.py`, replace the dead button line:

```python
          <button class="edit" data-agent-id="{html.escape(str(agent.get('agent_id') or ''))}">Edit Charter</button>
```

with a button that opens an inline editor drawer per-card, plus the drawer markup itself (a `<details>`/`<form>` pair keeps this dependency-free, consistent with the file's existing no-JS-framework style):

```python
          <details class="edit-charter">
            <summary>Edit Charter</summary>
            <form class="charter-edit-form" data-agent-id="{html.escape(str(agent.get('agent_id') or ''))}"
                  data-revision="{int(agent.get('charter_revision') or 0)}"
                  onsubmit="return window.__submitCharterEdit(event)">
              <label>Mandate (Instructions section)
                <textarea name="mandate" rows="4">{html.escape(str(agent.get('charter_excerpt') or ''))}</textarea>
              </label>
              <button type="submit" class="primary">Save revision</button>
              <span class="save-status" aria-live="polite"></span>
            </form>
          </details>
```

Then, immediately before the closing `{live}</body>` in the returned f-string, add a small inline script implementing `window.__submitCharterEdit` (no framework, matches the file's plain-JS `_live_js(port)` convention already in use):

```python
<script>
window.__submitCharterEdit = function(ev) {{
  ev.preventDefault();
  const form = ev.target;
  const status = form.querySelector(".save-status");
  const body = {{
    agent_id: form.dataset.agentId,
    parent_revision: parseInt(form.dataset.revision, 10),
    mandate: form.mandate.value,
  }};
  status.textContent = "saving...";
  fetch("/roles/charter/update", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body),
  }}).then(r => r.json()).then(result => {{
    if (result.ok) {{
      status.textContent = "saved (rev " + result.revision + ") — reload to see it live";
      form.dataset.revision = result.revision;
    }} else {{
      status.textContent = "error: " + result.error;
    }}
  }}).catch(() => {{ status.textContent = "network error"; }});
  return false;
}};
</script>
```

Add matching CSS to the existing `<style>` block (append, don't restructure the existing rules):

```css
.edit-charter{{margin-top:12px}}.edit-charter summary{{cursor:pointer;color:var(--accent);font-weight:700}}
.charter-edit-form{{display:grid;gap:8px;margin-top:10px}}.charter-edit-form textarea{{border:1px solid var(--line);border-radius:7px;padding:8px;font:inherit}}
.save-status{{font-size:11px;color:var(--muted)}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py -v`
Expected: PASS, all tests (including the pre-existing `test_generate_roles_html_renders_active_agents` and `test_handler_handle_role_create`)

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/roles.py tests/test_viz_roles.py
git commit -m "feat(viz): replace dead Edit Charter button with a working BAU editor drawer"
```

---

### Task 11: Remove the stale "stays on the CLI" text and tag Enforced vs. Guidance authorities

**Files:**
- Modify: `synlynk/viz/roles.py`
- Modify: `synlynk/viz/data.py:523-567` (`_load_workspace_agents` — surface `autonomous_authorities` with Enforced/Guidance tags)
- Test: `tests/test_viz_roles.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_viz_roles.py`:

```python
def test_generate_roles_html_no_longer_claims_cli_only_provisioning():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert "stays on the CLI" not in rendered


def test_generate_roles_html_tags_enforced_authority():
    data = _roles_data()
    data["workspace_agents"][0]["autonomous_authorities"] = [
        {"name": "worktree_cleanup", "enforced": True},
        {"name": "author_blog", "enforced": False},
    ]
    rendered = generate_roles_html(data, 8721)
    assert "Enforced" in rendered
    assert "Guidance" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py -k "cli_only or tags_enforced" -v`
Expected: FAIL on both — the stale string is still present, and no authority markup exists yet

- [ ] **Step 3: Implement**

In `synlynk/viz/roles.py`, change the drawer line:

```python
<section class="drawer" id="provision"><h2>Onboard Workspace Role</h2><p>Role provisioning stays on the CLI (<code>synlynk identity</code>).</p></section>
```

to:

```python
<section class="drawer" id="provision"><h2>Onboard Workspace Role</h2><p>Use the 5-step wizard below, or <code>synlynk agent activate &lt;role&gt;</code> + <code>synlynk identity init --role &lt;role&gt;</code> from the CLI.</p></section>
```

(The FTUE wizard markup itself is Phase 4's task — this task only removes the now-false claim.)

Add an authority-tagging helper and use it in the card loop. In the `cards.append(...)` block, before the `cards.append` call, add:

```python
        authorities = agent.get("autonomous_authorities") or []
        authority_html = "".join(
            f'<span class="authority {"enforced" if (a.get("enforced") if isinstance(a, dict) else False) else "guidance"}">'
            f'{html.escape(a.get("name", "") if isinstance(a, dict) else str(a))} '
            f'<small>{"Enforced" if (a.get("enforced") if isinstance(a, dict) else False) else "Guidance"}</small></span>'
            for a in authorities
        )
```

and insert `{authority_html}` into the card markup, just before the closing `</article>`:

```python
          <div class="authorities">{authority_html}</div>
        </article>""")
```

Add matching CSS:

```css
.authorities{{display:flex;flex-wrap:wrap;gap:6px;margin-top:10px}}.authority{{font-size:11px;border-radius:99px;padding:4px 8px;background:var(--accent-bg);color:#087462}}
.authority.guidance{{background:#f1f0ea;color:#8a7a3a}}.authority small{{font-weight:700;margin-left:3px}}
```

In `synlynk/viz/data.py`'s `_load_workspace_agents` (lines 523-567), add `autonomous_authorities` to the projected dict. The function already parses `metadata` from frontmatter but `autonomous_authorities` is a *body-adjacent* list key the parser already returns as a plain list (see `charter_schema.parse_frontmatter`'s list-key handling) — not yet tagged Enforced/Guidance, which requires a static lookup table since no per-authority "has a real code hook" registry exists yet. Add a conservative static set matching the spec's §3 Enforced examples (`worktree_cleanup`, `release_cut`, `policy_sync`, `approve_priority`) and mark everything else Guidance:

```python
_ENFORCED_AUTHORITIES = {"worktree_cleanup", "release_cut", "policy_sync", "approve_priority"}
```

(module-level constant, placed above `_load_workspace_agents`), then inside the function, after computing `harnesses`:

```python
            raw_authorities = metadata.get("autonomous_authorities") or []
            authorities = [
                {"name": a, "enforced": a in _ENFORCED_AUTHORITIES}
                for a in (raw_authorities if isinstance(raw_authorities, list) else [])
            ]
```

and add `"autonomous_authorities": authorities,` to the `projected.append({...})` dict.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py -v`
Expected: PASS, all tests

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/roles.py synlynk/viz/data.py tests/test_viz_roles.py
git commit -m "feat(viz): remove stale CLI-only claim, tag charter authorities Enforced/Guidance"
```

---

# Phase 3: Role lifecycle — deprecation/merge + GitHub App identity revocation

### Task 12: Add `synlynk identity revoke --role <role>`

No revocation path exists today (`grep -rn "revoke" synlynk/team.py synlynk/cli.py` turns up only the unrelated NATS relay-device revoke). GitHub does not let an installation token delete or suspend its own App — that requires the App-owner's web session — so this command does the part that is actually achievable headlessly: remove the local credential material, disable the agent record, and print the manual GitHub-side step.

**Files:**
- Modify: `synlynk/team.py` (add `cmd_identity_revoke`)
- Modify: `synlynk/cli.py` (wire `identity revoke` subcommand — the `identity_sub` parser from the earlier grounding read at `synlynk/cli.py:910-934`)
- Test: `tests/test_identity_list.py` (closest existing test file covering identity listing/status; add revocation tests alongside)

- [ ] **Step 1: Write the failing test**

Add to `tests/test_identity_list.py` (check its existing imports/fixtures first with `sed -n '1,20p' tests/test_identity_list.py` and match its style):

```python
def test_identity_revoke_removes_app_files_and_disables_agent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    fake_home = tmp_path / "fake_home"
    monkeypatch.setattr("os.path.expanduser", lambda p: p.replace("~", str(fake_home)))
    from synlynk import agent_store, team
    from synlynk.identity_roles import write_declared_roles
    from synlynk.product_store import resolve_github_apps_dir

    agent_store.register_agent("secops", [{"kind": "role_slug", "value": "secops"}])
    write_declared_roles(["secops"])
    apps_dir = resolve_github_apps_dir(".")
    apps_dir.mkdir(parents=True, exist_ok=True)
    (apps_dir / "secops.json").write_text("{}")
    (apps_dir / "secops.pem").write_text("fake-key")

    team.cmd_identity_revoke("secops", actor="nikhil")

    assert not (apps_dir / "secops.json").exists()
    assert not (apps_dir / "secops.pem").exists()
    from synlynk.identity_roles import load_declared_roles
    assert "secops" not in load_declared_roles()
    entries = [e for e in agent_store.list_agents() if e["agent_id"] == "secops"]
    assert entries[0]["disabled"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_identity_list.py::test_identity_revoke_removes_app_files_and_disables_agent -v`
Expected: FAIL — `AttributeError: module 'synlynk.team' has no attribute 'cmd_identity_revoke'`

- [ ] **Step 3: Implement**

In `synlynk/team.py`, add after `cmd_identity_list`:

```python
def cmd_identity_revoke(role: str, actor: str) -> None:
    """Revoke a role's local GitHub App credential material and disable its agent record.

    Does NOT delete or suspend the GitHub App installation itself — that
    requires the App owner's authenticated web session, which an
    installation token cannot grant itself. Prints the manual follow-up step.
    """
    from synlynk.product_store import resolve_github_apps_dir
    from synlynk.identity_roles import load_declared_roles, write_declared_roles
    from synlynk import agent_store

    apps_dir = resolve_github_apps_dir(".")
    json_path = apps_dir / f"{role}.json"
    pem_path = apps_dir / f"{role}.pem"
    app_slug = None
    if json_path.exists():
        try:
            app_slug = json.loads(json_path.read_text()).get("app_slug")
        except (json.JSONDecodeError, OSError):
            pass
        json_path.unlink()
    if pem_path.exists():
        pem_path.unlink()

    declared = load_declared_roles()
    if role in declared:
        write_declared_roles([r for r in declared if r != role])

    agent_store.set_agent_disabled(role, actor=actor)

    print(f"  revoked local credential material for role '{role}'")
    if app_slug:
        print(f"  manual step required: suspend or delete the GitHub App '{app_slug}' "
              f"at https://github.com/settings/apps/{app_slug} (installation tokens cannot "
              f"self-revoke)")
    else:
        print("  no GitHub App was provisioned for this role locally")
```

In `synlynk/cli.py`, add a subparser next to `identity_sub.add_parser("list", ...)` (found at the earlier grounding read's line 933):

```python
    identity_revoke_parser = identity_sub.add_parser("revoke", help="Revoke a role's local GitHub App credential material")
    identity_revoke_parser.add_argument("--role", required=True)
```

and a dispatch branch in the `elif args.command == "identity":` block, next to `elif action == "list":`:

```python
        elif action == "revoke":
            import getpass
            from synlynk.team import cmd_identity_revoke
            cmd_identity_revoke(args.role, actor=getpass.getuser())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_identity_list.py::test_identity_revoke_removes_app_files_and_disables_agent -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/team.py synlynk/cli.py tests/test_identity_list.py
git commit -m "feat(identity): add 'synlynk identity revoke --role' for role deprecation lifecycle (spec §3a.3)"
```

---

### Task 13: Add `synlynk agent deprecate <role>` wrapping disablement + identity revocation in one step

**Files:**
- Modify: `synlynk/cli.py` (add `agent deprecate` subcommand)
- Test: `tests/test_role_activation.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_role_activation.py`:

```python
def test_cli_agent_deprecate_disables_and_revokes(tmp_path, monkeypatch):
    _fake_home(tmp_path, monkeypatch)
    import sys
    from synlynk import agent_store, cli

    monkeypatch.setattr(sys, "argv", ["synlynk", "agent", "activate", "secops"])
    cli.main()
    monkeypatch.setattr(sys, "argv", ["synlynk", "agent", "deprecate", "secops"])
    cli.main()

    entries = [e for e in agent_store.list_agents() if e["agent_id"] == "secops"]
    assert entries[0]["disabled"] is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_role_activation.py::test_cli_agent_deprecate_disables_and_revokes -v`
Expected: FAIL — argparse rejects unknown subcommand `deprecate`

- [ ] **Step 3: Implement**

In `synlynk/cli.py`, next to the `agent_activate_parser` added in Task 7:

```python
    agent_deprecate_parser = agent_sub.add_parser(
        "deprecate", help="Disable a role's agent record and revoke its GitHub App identity"
    )
    agent_deprecate_parser.add_argument("role")
```

and in the `elif args.command == "agent":` dispatch block, next to the `activate` branch:

```python
        elif args.agent_action == "deprecate":
            import getpass
            from synlynk.team import cmd_identity_revoke
            cmd_identity_revoke(args.role, actor=getpass.getuser())
            print(f"  deprecated role '{args.role}'")
```

(`cmd_identity_revoke` already disables the agent record via `agent_store.set_agent_disabled` — Task 12 — so no separate disable call is needed here.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_role_activation.py::test_cli_agent_deprecate_disables_and_revokes -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/cli.py tests/test_role_activation.py
git commit -m "feat(cli): add 'synlynk agent deprecate <role>' one-step lifecycle command"
```

---

# Phase 4: FTUE 5-step wizard

### Task 14: Add the FTUE wizard route and step-sequencing handler

The spec's §5 defines 5 steps: pick function family -> customize fields -> escalation/veto scope -> provision identity -> review & activate. Steps 1-3 and 5 are pure form state collected client-side and submitted once; step 4 (GitHub App manifest provisioning) is an external OAuth-flow redirect that cannot run inside a JSON POST handler the way `_handle_role_create` does — `cmd_identity_init_role` opens a browser and blocks on a local callback server. The wizard therefore submits steps 1-3+5 as one `_handle_role_create` call (already built in Phase 1/pre-existing), then surfaces the `synlynk identity init --role <role>` command as the manual step-4 action, consistent with Task 12's finding that App provisioning fundamentally requires a human browser session.

**Files:**
- Modify: `synlynk/viz/roles.py` (add wizard markup + JS to the `<section class="drawer">`)
- Test: `tests/test_viz_roles.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_viz_roles.py`:

```python
def test_generate_roles_html_renders_ftue_wizard_steps():
    rendered = generate_roles_html(_roles_data(), 8721)
    assert 'data-step="1"' in rendered
    assert 'data-step="4"' in rendered
    assert "synlynk identity init --role" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py::test_generate_roles_html_renders_ftue_wizard_steps -v`
Expected: FAIL — no `data-step` markup exists yet

- [ ] **Step 3: Implement**

Replace the drawer section (as last modified in Task 11) with a step-sequenced wizard:

```python
<section class="drawer" id="provision"><h2>Onboard Workspace Role</h2>
<div class="wizard" id="ftue-wizard">
  <ol class="steps">
    <li data-step="1" class="active">1. Function family</li>
    <li data-step="2">2. Fields</li>
    <li data-step="3">3. Escalation scope</li>
    <li data-step="4">4. Identity</li>
    <li data-step="5">5. Review</li>
  </ol>
  <form id="ftue-form" onsubmit="return window.__submitFtue(event)">
    <div data-panel="1">
      <label>Function family
        <select name="role">
          <option value="dev">dev — delivery</option>
          <option value="qa">qa — quality/trust</option>
          <option value="secops">secops — quality/trust</option>
          <option value="maintainer">maintainer — platform</option>
          <option value="infra-devops">infra-devops — platform</option>
          <option value="designer">designer — experience</option>
          <option value="marketing">marketing — experience</option>
        </select>
      </label>
      <button type="button" onclick="window.__ftueNext(1)">Next</button>
    </div>
    <div data-panel="2" hidden>
      <label>Mandate (free text)<textarea name="mandate" rows="3"></textarea></label>
      <label>Durability
        <select name="durability"><option value="durable">durable</option><option value="dispatch-only">dispatch-only</option><option value="session-only">session-only</option></select>
      </label>
      <button type="button" onclick="window.__ftueNext(2)">Next</button>
    </div>
    <div data-panel="3" hidden>
      <p>Escalation triggers and veto scope are refined after activation, in the
         BAU charter editor above — this step confirms you understand the role
         activates with its taxonomy default scope (spec §2).</p>
      <button type="button" onclick="window.__ftueNext(3)">Next</button>
    </div>
    <div data-panel="4" hidden>
      <p>After activation, provision this role's GitHub App identity from a
         terminal (requires a browser for GitHub's manifest flow — cannot run
         inside Vizor):</p>
      <pre id="ftue-identity-cmd">synlynk identity init --role &lt;role&gt;</pre>
      <button type="button" onclick="window.__ftueNext(4)">Next</button>
    </div>
    <div data-panel="5" hidden>
      <p>Review your selections, then activate.</p>
      <button type="submit" class="primary">Activate role</button>
    </div>
  </form>
  <p class="wizard-status" aria-live="polite"></p>
</div>
</section>
```

Add the wizard script alongside the charter-edit script added in Task 10:

```python
<script>
window.__ftueNext = function(fromStep) {{
  document.querySelector('[data-panel="' + fromStep + '"]').hidden = true;
  document.querySelector('[data-panel="' + (fromStep + 1) + '"]').hidden = false;
  document.querySelectorAll(".steps li").forEach(li => li.classList.remove("active"));
  document.querySelector('[data-step="' + (fromStep + 1) + '"]').classList.add("active");
  if (fromStep + 1 === 4) {{
    const role = document.querySelector('[name="role"]').value;
    document.getElementById("ftue-identity-cmd").textContent = "synlynk identity init --role " + role;
  }}
}};
window.__submitFtue = function(ev) {{
  ev.preventDefault();
  const form = ev.target;
  const status = document.querySelector(".wizard-status");
  const body = {{
    role: form.role.value,
    durability: form.durability.value,
    mandate: form.mandate.value,
  }};
  status.textContent = "activating...";
  fetch("/roles/create", {{
    method: "POST",
    headers: {{"Content-Type": "application/json"}},
    body: JSON.stringify(body),
  }}).then(r => r.json()).then(result => {{
    status.textContent = result.ok
      ? "activated as " + result.agent_id + " — reload to see it in Living Charters"
      : "error: " + result.error;
  }}).catch(() => {{ status.textContent = "network error"; }});
  return false;
}};
</script>
```

Add matching CSS:

```css
.wizard .steps{{list-style:none;display:flex;gap:10px;padding:0;margin:0 0 16px;font-size:12px;color:#7fa8a3}}
.wizard .steps li.active{{color:#3de0c0;font-weight:700}}
.wizard [data-panel]{{display:grid;gap:10px}}.wizard pre{{background:#0c2225;padding:10px;border-radius:7px;color:#9ef5df}}
.wizard-status{{font-size:11px;color:#b7d4ce}}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py -v`
Expected: PASS, all tests

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/roles.py tests/test_viz_roles.py
git commit -m "feat(viz): add 5-step FTUE role-provisioning wizard"
```

---

# Phase 5: Native hook catalog (Capability Registry — native-code-hook source)

### Task 15: Define the Capability Registry manifest shape and a native-hook loader

**Files:**
- Create: `synlynk/capability_registry.py`
- Create: `.synlynk/capability_registry/native/` (manifest JSON files)
- Test: `tests/test_capability_registry.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_capability_registry.py`:

```python
import json

import pytest


def test_load_native_capabilities_reads_manifest(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry_dir = tmp_path / ".synlynk" / "capability_registry" / "native"
    registry_dir.mkdir(parents=True)
    manifest = {
        "capability_id": "worktree-clean",
        "name": "worktree_cleanup",
        "source": "native",
        "description": "Removes merged/stale worktrees and their branches.",
        "purpose": "Keep the repo's worktree set from accumulating stale entries.",
        "scope": "filesystem:worktrees,git:branches",
        "auth": {"type": "none"},
        "enforced_hook": "synlynk.cli:cmd_worktree_clean",
        "harness_compat": "any",
        "workspace_id": "local",
        "owner": "synlynk-core",
        "version": "1.0.0",
    }
    (registry_dir / "worktree-clean.json").write_text(json.dumps(manifest))

    from synlynk import capability_registry
    caps = capability_registry.load_native_capabilities()

    assert len(caps) == 1
    assert caps[0]["capability_id"] == "worktree-clean"
    assert caps[0]["enforced_hook"] == "synlynk.cli:cmd_worktree_clean"


def test_load_native_capabilities_rejects_manifest_missing_required_fields(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry_dir = tmp_path / ".synlynk" / "capability_registry" / "native"
    registry_dir.mkdir(parents=True)
    (registry_dir / "broken.json").write_text(json.dumps({"capability_id": "broken"}))

    from synlynk import capability_registry
    with pytest.raises(ValueError, match="missing required"):
        capability_registry.load_native_capabilities()


def test_load_native_capabilities_empty_dir_returns_empty_list(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk import capability_registry
    assert capability_registry.load_native_capabilities() == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_registry.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.capability_registry'`

- [ ] **Step 3: Implement**

Create `synlynk/capability_registry.py`:

```python
"""Capability Registry: a unified manifest shape for native code hooks,
local-harness-installed MCPs/Skills, and (held pending spec §3a.4/Phase 7)
remote third-party connectors. See spec §4.

This module implements only the native-hook source (Phase 5). Local-harness
and remote sources are separate modules (capability_registry_local.py,
Phase 6; remote ingestion stays out of scope per spec §7 until the Phase 7
trust/dedup gate lands).
"""
import json
import os

NATIVE_REGISTRY_DIR = os.path.join(".synlynk", "capability_registry", "native")

REQUIRED_MANIFEST_FIELDS = (
    "capability_id", "name", "source", "description", "purpose", "scope",
    "auth", "harness_compat", "workspace_id", "owner", "version",
)


def _validate_manifest(manifest: dict, path: str) -> None:
    missing = [f for f in REQUIRED_MANIFEST_FIELDS if f not in manifest]
    if missing:
        raise ValueError(f"{path}: missing required manifest field(s): {', '.join(missing)}")


def load_native_capabilities() -> list:
    """Load and validate every native-hook manifest under NATIVE_REGISTRY_DIR.

    Returns [] if the directory does not exist (no native capabilities
    registered yet — not an error).
    """
    if not os.path.isdir(NATIVE_REGISTRY_DIR):
        return []
    capabilities = []
    for name in sorted(os.listdir(NATIVE_REGISTRY_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(NATIVE_REGISTRY_DIR, name)
        with open(path) as fh:
            manifest = json.load(fh)
        _validate_manifest(manifest, path)
        capabilities.append(manifest)
    return capabilities
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_registry.py -v`
Expected: PASS, all three tests

- [ ] **Step 5: Seed the registry with the first real native-hook manifest**

Create `.synlynk/capability_registry/native/.gitkeep`-style real entry — `worktree-cleanup.json` documenting the actual `synlynk worktree clean` hook used throughout this repo's own Worktree Hygiene Protocol (CLAUDE.md):

Create `.synlynk/capability_registry/native/worktree-cleanup.json`:

```json
{
  "capability_id": "worktree-cleanup",
  "name": "worktree_cleanup",
  "source": "native",
  "description": "Removes merged/stale git worktrees and prunes their local branches.",
  "purpose": "Prevent stale worktree/branch accumulation after PR merge.",
  "scope": "filesystem:worktrees,git:branches",
  "auth": {"type": "none"},
  "enforced_hook": "synlynk.cli:cmd_worktree_clean",
  "harness_compat": "any",
  "workspace_id": "local",
  "owner": "synlynk-core",
  "version": "1.0.0"
}
```

(Verify the real dispatch target name first: `grep -n "cmd_worktree_clean\|def cmd.*worktree.*clean" synlynk/cli.py` — use whatever function name that grep actually returns in place of `cmd_worktree_clean` above if it differs.)

- [ ] **Step 6: Run the registry test against the real seeded manifest**

Run: `cd /Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+vizor-agent-role-management-spec && python3 -c "from synlynk import capability_registry; print(capability_registry.load_native_capabilities())"`
Expected: prints a one-item list containing the `worktree-cleanup` manifest, with no exception

- [ ] **Step 7: Commit**

```bash
git add synlynk/capability_registry.py tests/test_capability_registry.py .synlynk/capability_registry/native/worktree-cleanup.json
git commit -m "feat: add Capability Registry native-hook source (spec §4/§5)"
```

---

# Phase 6: Capability Registry local source (harness-installed MCPs/Skills)

### Task 16: Extend the registry loader to project `harness_bindings`-scoped local capabilities

**Files:**
- Modify: `synlynk/capability_registry.py`
- Test: `tests/test_capability_registry.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_capability_registry.py`:

```python
def test_load_local_capabilities_scoped_by_harness_bindings(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    registry_dir = tmp_path / ".synlynk" / "capability_registry" / "local"
    registry_dir.mkdir(parents=True)
    manifest = {
        "capability_id": "stitch-ui-driver",
        "name": "generate_screen_from_text",
        "source": "local_harness",
        "description": "Generates a UI screen mockup from a text prompt via the Stitch MCP server.",
        "purpose": "Design-stage mockup generation.",
        "scope": "mcp:stitch",
        "auth": {"type": "mcp_server", "server": "stitch"},
        "enforced_hook": None,
        "harness_compat": ["claude"],
        "workspace_id": "local",
        "owner": "designer",
        "version": "1.0.0",
    }
    (registry_dir / "stitch-ui-driver.json").write_text(json.dumps(manifest))

    from synlynk import capability_registry
    caps = capability_registry.load_local_capabilities(harness="claude")
    assert len(caps) == 1
    caps_other = capability_registry.load_local_capabilities(harness="grok")
    assert caps_other == []
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_registry.py::test_load_local_capabilities_scoped_by_harness_bindings -v`
Expected: FAIL — `AttributeError: module 'synlynk.capability_registry' has no attribute 'load_local_capabilities'`

- [ ] **Step 3: Implement**

In `synlynk/capability_registry.py`, add:

```python
LOCAL_REGISTRY_DIR = os.path.join(".synlynk", "capability_registry", "local")


def load_local_capabilities(harness: str = None) -> list:
    """Load local_harness-source manifests, optionally filtered to those whose
    harness_compat includes `harness` (or is the literal string "any").
    """
    if not os.path.isdir(LOCAL_REGISTRY_DIR):
        return []
    capabilities = []
    for name in sorted(os.listdir(LOCAL_REGISTRY_DIR)):
        if not name.endswith(".json"):
            continue
        path = os.path.join(LOCAL_REGISTRY_DIR, name)
        with open(path) as fh:
            manifest = json.load(fh)
        _validate_manifest(manifest, path)
        compat = manifest.get("harness_compat")
        if harness is not None and compat != "any" and harness not in (compat or []):
            continue
        capabilities.append(manifest)
    return capabilities
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_registry.py -v`
Expected: PASS, all tests

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_registry.py tests/test_capability_registry.py
git commit -m "feat: add Capability Registry local-harness source, scoped by harness_bindings (spec §4a)

Models tool-specific capabilities (e.g. Stitch) as harness_bindings-scoped
Capability Registry entries attached to stable functional roles, per the
2026-11-09 decide panel's rejection of tool-named role primitives (spec §4a)."
```

---

### Task 17: Wire the BAU editor's "Attach existing capability" control to the registry

**Files:**
- Modify: `synlynk/viz/roles.py`
- Modify: `synlynk/viz/data.py` (expose registry capabilities to the template)
- Test: `tests/test_viz_roles.py`

- [ ] **Step 1: Write the failing test**

Add to `tests/test_viz_roles.py`:

```python
def test_generate_roles_html_lists_attachable_capabilities():
    data = _roles_data()
    data["capability_registry"] = [
        {"capability_id": "worktree-cleanup", "name": "worktree_cleanup", "source": "native"},
    ]
    rendered = generate_roles_html(data, 8721)
    assert "worktree-cleanup" in rendered
    assert "Attach" in rendered
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_roles.py::test_generate_roles_html_lists_attachable_capabilities -v`
Expected: FAIL — no "Attach" control present

- [ ] **Step 3: Implement**

In `synlynk/viz/roles.py`, inside the charter-edit `<details>` block added in Task 10, add a capability picker right after the `<textarea>` label and before the submit button:

```python
              <label>Attach existing capability
                <select name="capability_id">
                  <option value="">— none —</option>
                  {"".join(f'<option value="{html.escape(c.get("capability_id",""))}">{html.escape(c.get("capability_id",""))} ({html.escape(c.get("source",""))})</option>' for c in (data.get("capability_registry") or []))}
                </select>
              </label>
```

(`data` is already the function's top-level parameter — no new argument needed, since `generate_roles_html(data, port)` already receives the full Vizor data dict; only the new `capability_registry` key is new.)

In `synlynk/viz/data.py`, wherever the top-level data dict assembled for Vizor is built (search `grep -n "workspace_agents.*:" synlynk/viz/data.py` to find the surrounding dict-construction site), add:

```python
    from synlynk import capability_registry
    try:
        native_caps = capability_registry.load_native_capabilities()
    except ValueError:
        native_caps = []
    try:
        local_caps = capability_registry.load_local_capabilities()
    except ValueError:
        local_caps = []
```

and include `"capability_registry": native_caps + local_caps,` as a new key in that same dict literal.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_roles.py -v`
Expected: PASS, all tests

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/roles.py synlynk/viz/data.py tests/test_viz_roles.py
git commit -m "feat(viz): wire BAU editor's capability picker to the Capability Registry"
```

---

# Phase 7: Trust/dedup gate (§3a.4) — precondition, not remote ingestion itself

Per spec §7, remote-connector ingestion (Zapier MCP/Composio/Smithery) and the upstream GitHub feature-request flow are explicitly **out of scope** for this plan. This phase builds only the gate gh:#2139's stale-closure lesson requires before either of those can ship — a follow-on ticket (filed in Task 19) carries the actual remote-ingestion work.

### Task 18: Add a dedup-check gate for any future upstream issue-filing path

**Files:**
- Create: `synlynk/upstream_dedup_gate.py`
- Test: `tests/test_upstream_dedup_gate.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_upstream_dedup_gate.py`:

```python
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
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_upstream_dedup_gate.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'synlynk.upstream_dedup_gate'`

- [ ] **Step 3: Implement**

Create `synlynk/upstream_dedup_gate.py`:

```python
"""Dedup/trust gate required (spec §3a.4) before any upstream GitHub
feature-request flow or remote Capability Registry ingestion ships.
References gh:#2139's lesson: a stale "closed via PR" claim in project
memory/roadmap text turned out to be wrong (issue was actually still open)
because nothing re-checked upstream state before treating it as resolved.

This module provides only the dedup check itself — the issue-filing and
remote-manifest-ingestion flows that will call it remain out of scope for
this plan (spec §7); they are a follow-on once this gate exists and is
wired in.
"""


def _search_issues(query: str) -> list:
    """Search this repo's GitHub issues for `query`. Real implementation
    delegates to the existing mcp__plugin_github_github__search_issues tool
    or `gh issue list --search`, whichever the caller's environment provides
    — left as an injection point so tests can stub it without a live GitHub
    call. Not implemented as a direct network call here, by design: this
    module must stay testable without GitHub credentials.
    """
    raise NotImplementedError(
        "wire this to a real search (gh issue list --search <query> --json number,title,state, "
        "or the github MCP server's search_issues tool) in the caller that has that access"
    )


def check_dedup(proposed_title_or_summary: str) -> dict:
    """Return {'has_candidate_duplicate': bool, 'candidates': [...]} for
    open issues that might already cover `proposed_title_or_summary`.

    Only open issues count as candidate duplicates — a closed issue is not
    evidence the work is done (gh:#2139's exact failure mode).
    """
    results = _search_issues(proposed_title_or_summary)
    open_candidates = [r for r in results if r.get("state") == "open"]
    return {
        "has_candidate_duplicate": bool(open_candidates),
        "candidates": open_candidates,
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_upstream_dedup_gate.py -v`
Expected: PASS, all three tests

- [ ] **Step 5: Commit**

```bash
git add synlynk/upstream_dedup_gate.py tests/test_upstream_dedup_gate.py
git commit -m "feat: add upstream dedup/trust gate scaffold required before remote ingestion ships (spec §3a.4)

Does not implement the upstream feature-request flow or remote Capability
Registry ingestion themselves — both remain explicitly out of scope per
spec §7 until this gate is wired into a real caller. Guards against the
gh:#2139 failure mode: a closed issue is never treated as evidence the
underlying work is actually done."
```

### Task 19: File the follow-on ticket for remote ingestion + upstream feature-request flow

- [ ] **Step 1: Confirm Phase 1-7 of this plan are merged**, then file a GitHub issue (not a code task) titled "Remote Capability Registry ingestion + upstream feature-request flow (spec §7 follow-on)" that:
  - Links this plan and the design spec
  - States the precondition met: `synlynk.upstream_dedup_gate.check_dedup` exists and is unit-tested
  - States the work still needed: wire `check_dedup` into a real issue-filing path (`_search_issues`'s `NotImplementedError` needs a live `gh`/MCP-backed implementation), build the Zapier MCP/Composio/Smithery remote-manifest ingestion loader (parallel to `capability_registry.py`'s `load_native_capabilities`/`load_local_capabilities`, but reading from a remote source and requiring the `owner`/`scope`/`version` provenance fields spec §3b.4 already requires on every manifest)
  - Is labeled per this project's live-issue/feature-tracking conventions (not a `live-issue` label — this is planned forward work, not an incident)

This step has no code and is not part of the TDD task sequence above — it is the explicit scope boundary the spec's §7 draws, made concrete as a trackable follow-on rather than silently dropped.

---

# Phase 8: TPM charter tool-use migration for GitHub sync

Added per `project-docs/decisions/2026-11-09-decide-panel-should-bidirectional-sync-w.md` — "external-system-touching, judgment-bearing functionality is agent-role tool-use via the Capability Registry; local control-plane mechanics stay native." `synlynk gh sync-roadmap` (`synlynk/gh_sync_cli.py:cmd_sync_roadmap`) is today a native CLI command with no charter authority behind it. This phase wraps the existing function as a `native_code` Capability Registry entry and grants `tpm` the authority to invoke it, without touching `cmd_sync_roadmap`'s own logic. Depends on Task 2/3 (`propose_charter_revision`'s `actor_type` param) and Task 15 (`capability_registry.py`) already being in place.

### Task 20: Wrap `gh sync-roadmap` as a Capability Registry entry, grant `tpm` the authority, migrate `tpm.json` into `agent_store`

**Files:**
- Create: `.synlynk/capability_registry/native/gh-sync-roadmap.json`
- Modify: `.synlynk/charters/tpm.json` (add `autonomous_authorities` entry + `capability_refs`)
- Modify: `synlynk/role_activation.py` or a one-off migration call (migrate `tpm` into `agent_store`)
- Test: `tests/test_capability_registry.py`, `tests/test_agent_store.py`

- [ ] **Step 1: Write the failing test for the new manifest**

Add to `tests/test_capability_registry.py`:

```python
def test_load_native_capabilities_includes_gh_sync_roadmap():
    from synlynk import capability_registry
    caps = capability_registry.load_native_capabilities()
    ids = {c["capability_id"] for c in caps}
    assert "gh-sync-roadmap" in ids
    entry = next(c for c in caps if c["capability_id"] == "gh-sync-roadmap")
    assert entry["enforced_hook"] == "synlynk.gh_sync_cli:cmd_sync_roadmap"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_registry.py::test_load_native_capabilities_includes_gh_sync_roadmap -v`
Expected: FAIL — `AssertionError` (no `gh-sync-roadmap` entry on disk yet)

- [ ] **Step 3: Create the manifest**

Create `.synlynk/capability_registry/native/gh-sync-roadmap.json`:

```json
{
  "capability_id": "gh-sync-roadmap",
  "name": "gh_sync_roadmap",
  "source": "native",
  "description": "Projects state.db GOVERNS goals/stories to GitHub Milestones/Issues (one-way today; bidirectional sync is a separate, deferred follow-on).",
  "purpose": "Keep GitHub's shareable projection of roadmap state in sync with state.db, the sole authority, without hand-edited roadmap.md/todo.md.",
  "scope": "network:github,state.db:goals,state.db:stories",
  "auth": {"type": "github_app"},
  "enforced_hook": "synlynk.gh_sync_cli:cmd_sync_roadmap",
  "harness_compat": "any",
  "workspace_id": "local",
  "owner": "synlynk-core",
  "version": "1.0.0"
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_registry.py::test_load_native_capabilities_includes_gh_sync_roadmap -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for tpm's new authority**

Add to `tests/test_agent_store.py`:

```python
def test_tpm_charter_has_gh_sync_authority():
    import json
    with open(".synlynk/charters/tpm.json") as fh:
        charter = json.load(fh)
    assert "sync_external_tracker" in charter["autonomous_authorities"]
    assert "gh-sync-roadmap" in charter.get("capability_refs", [])
```

- [ ] **Step 6: Run test to verify it fails**

Run: `pytest tests/test_agent_store.py::test_tpm_charter_has_gh_sync_authority -v`
Expected: FAIL — `KeyError`/`AssertionError` (authority and `capability_refs` don't exist yet)

- [ ] **Step 7: Update `tpm.json`**

Edit `.synlynk/charters/tpm.json`'s `autonomous_authorities` list to add `"sync_external_tracker"`, add a new top-level `"capability_refs": ["gh-sync-roadmap"]` field, and extend `wake_cycle_sop` with a new step:

```json
"7. Tracker Sync: Invoke the `gh-sync-roadmap` capability (synlynk.gh_sync_cli:cmd_sync_roadmap) to project state.db goal/story state to GitHub as the shareable read-only view, after sweep execution."
```

- [ ] **Step 8: Run test to verify it passes**

Run: `pytest tests/test_agent_store.py::test_tpm_charter_has_gh_sync_authority -v`
Expected: PASS

- [ ] **Step 9: Migrate `tpm` into `agent_store`**

`agent_store.read_charter('tpm')` currently returns empty content at revision 0 — `tpm` has never been registered into the versioned markdown system every other role in this plan uses. Run once, interactively or as a migration script:

```python
from synlynk import agent_store
import json

with open(".synlynk/charters/tpm.json") as fh:
    tpm_charter = json.load(fh)

if "tpm" not in {e["agent_id"] for e in agent_store.list_agents()}:
    agent_store.register_agent("tpm", [{"kind": "role_slug", "value": "tpm"}])

agent_store.propose_charter_revision(
    "tpm", tpm_charter, actor="nikhil", parent_revision=0, actor_type="human",
)
```

- [ ] **Step 10: Verify the migration**

Run: `python3 -c "from synlynk import agent_store; content, rev = agent_store.read_charter('tpm'); print(rev); assert rev >= 1"`
Expected: prints `1` (or higher), no `AssertionError`

- [ ] **Step 11: Run the full affected test surface together**

Run: `pytest tests/test_capability_registry.py tests/test_agent_store.py tests/test_charters.py -v`
Expected: PASS, 0 failures

- [ ] **Step 12: Commit**

```bash
git add .synlynk/capability_registry/native/gh-sync-roadmap.json .synlynk/charters/tpm.json tests/test_capability_registry.py tests/test_agent_store.py
git commit -m "feat: wrap gh sync-roadmap as a tpm-owned Capability Registry entry

Per decide-panel decision 2026-11-09-decide-panel-should-bidirectional-sync-w:
external-system-touching, judgment-bearing functionality becomes agent-role
tool-use via the Capability Registry rather than a bare native CLI command.
Wraps the existing cmd_sync_roadmap unchanged; migrates tpm's charter into
agent_store so it gets audited writes like every other role in this plan.

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>"
```

- [ ] **Step 13: File the follow-on stories under `goal-658aa384`**

Not code — per the decide panel's `[defer-safely]` items, file two GitHub issues (not implemented in this plan):
1. "Bidirectional GitHub sync (conflict resolution, idempotency, webhook/polling semantics) — tpm capability follow-on" — linked to `goal-658aa384`, blocked on a concrete trigger (no work starts until one exists).
2. "Linear/Jira/Asana/Slack connectors via Composio/Smithery — tpm/role tool-use follow-ons" — linked to `goal-658aa384`, gated by Phase 7/Task 18's trust/dedup gate before any ingestion work starts.

---

## Self-Review

**Spec coverage check (against `docs/superpowers/specs/2026-11-09-vizor-agent-role-management-design.md`):**
- §1 Problem (dead button, maintainer gap) -> Tasks 6, 9, 10 ✓
- §2 Taxonomy (secops, infra-devops, maintainer promotion) -> Tasks 1, 4, 5, 6 ✓
- §3 Enforced/Guidance tagging -> Task 11 ✓
- §3a.1 audited charter writes -> Task 2 ✓
- §3a.2 capability_ratings wiring from day one -> Task 8 ✓
- §3a.3 deprecation/merge lifecycle + GitHub App revocation -> Tasks 12, 13 ✓
- §3a.4 trust/dedup gate -> Task 18 ✓ (gate only; ingestion itself correctly deferred, Task 19)
- §3b.1 `workspace_id` seam -> Task 2 (audit entries), Task 4 (charter frontmatter), Task 15 (registry manifests) ✓
- §3b.2 `identity_binding` seam -> Task 4 ✓
- §3b.3 immutable/attributable audit -> Task 2 ✓
- §3b.4 manifest provenance (`owner`/`scope`/`version`) -> Task 15's `REQUIRED_MANIFEST_FIELDS` ✓
- §3b design-now-build-later (`policy_refs`) -> Task 4 ✓ (reference shape only, no PEP pipeline built — correctly matches spec)
- §3b defer-safely (SSO/SAML/SCIM/LDAP, hosted service) -> correctly absent from this plan, no task needed
- §4 Capability Registry (native/local/remote) -> Tasks 15, 16 (remote: Task 18/19, gated) ✓
- §4a tool-specific roles rejected, modeled as `harness_bindings` -> Task 16 ✓
- §5 BAU editor + FTUE wizard -> Tasks 9, 10, 11, 14, 17 ✓
- §6 phase sequencing -> this plan's Phase 1-7 structure mirrors it exactly, governance gates front-loaded into Phase 1 ✓
- §7 out of scope (hosted service, DLP/infra PEP pipelines, remote ingestion) -> correctly not built; Task 19 files the one legitimate follow-on ✓
- §8 open items -> explicitly not resolved by this plan (they are marked open in the spec itself for a reason); Task 12's GitHub-App-self-revocation limitation and Task 18's `NotImplementedError` injection point are the concrete manifestations of those open items surfacing in code, handled honestly rather than papered over
- Decide panel `2026-11-09-decide-panel-should-bidirectional-sync-w` (not in the original spec, added post-approval per Nikhil's explicit request) -> Task 20 wraps `gh sync-roadmap` as a Capability Registry entry and migrates `tpm` into `agent_store`; the panel's two `[defer-safely]` items (bidirectional sync, Linear/Jira/Asana/Slack connectors) are correctly filed as follow-on stories in Task 20 Step 13, not built here ✓

**Placeholder scan:** No TBD/TODO strings. The one `NotImplementedError` (Task 18's `_search_issues`) is not a placeholder for missing plan content — it is the documented, deliberate seam the spec's own Phase 7 gating requires (dedup-check logic is real and tested; only the live GitHub network call, which needs credentials no test should depend on, is left as an injection point, exactly as `tests/test_upstream_dedup_gate.py` demonstrates by stubbing it).

**Type/signature consistency check:**
- `activate_role(role, actor, actor_type="human")` — same signature used in Tasks 5, 6, 7, 8
- `propose_charter_revision(agent_id, content, actor, parent_revision, actor_type="service")` — same signature used in Tasks 2, 3, 5, 9, 20
- `load_native_capabilities()` / `load_local_capabilities(harness=None)` — same names used in Tasks 15, 16, 17
- `cmd_identity_revoke(role, actor)` — same signature used in Tasks 12, 13
- `REQUIRED_MANIFEST_FIELDS` tuple defined once in Task 15, referenced (not redefined) in Task 16

No gaps found requiring an added task.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-11-09-vizor-agent-role-management.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
