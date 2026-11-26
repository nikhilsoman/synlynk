# FTUE Review-Gate Identity Matrix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only testbed scenario that drives `_cross_harness_review_verdict()` through six identity shapes (3 existing team identities + 3 new solo/edge identities), reproducing gh:#5355 as a deterministic failing assertion for solo-harness-account workspaces — without fixing #5355 itself.

**Architecture:** Three new identity fixtures go in `synlynk/testbed/identities.py` as a `SOLO_AND_EDGE_IDENTITIES` dict, kept separate from `STANDARD_IDENTITIES` so existing VM-based scenarios are untouched. A new `ScenarioRunner.run_review_gate_matrix(conn)` method in `synlynk/testbed/scenarios.py` takes an already-open `sqlite3.Connection`, seeds `cost_entries` rows for six (implementer, reviewer) pairings, calls `_cross_harness_review_verdict(conn, pr_number)` for each, and returns one `ScenarioResult` per pairing. This needs no VM, network, or GitHub mock, matching `run_state_db_wal_soak`'s existing no-VM precedent. Test wiring in `tests/test_ftue_vm_acceptance.py` seeds an isolated `state.db` via the existing `project_dir`/`isolated_db` pytest fixtures, runs the scenario, and asserts the matrix's expected pass/fail shape.

**Design resolution (spec ambiguity, resolved here):** The approved spec's §3.2 step 2 says to seed "the same identity" as reviewer for every identity in the matrix, but §3.3/§5 expects the three existing team identities (alice/bob/charlie) to **pass**. Self-pairing always fails in current code (harness+model trivially equals itself), so a literal same-identity-as-reviewer pairing for alice/bob/charlie would also fail, contradicting §5's table. This plan resolves the ambiguity the way the spec's own intent implies: team identities, which have other team members with distinct harness/model accounts, are paired with a *different* teammate as reviewer (the realistic case — proving the matrix also captures the known-good shape, not just blanket failures). Solo/edge identities (`solo_claude`, `gateway_poweruser`, `ci_headless`), which have no second identity available, are paired with themselves — the literal #5355 condition.

**Tech Stack:** Python 3 stdlib, `sqlite3`, `pytest`. No new dependencies.

---

### Task 1: Add solo/edge identity fixtures

**Files:**
- Modify: `synlynk/testbed/identities.py`

- [ ] **Step 1: Append `SOLO_AND_EDGE_IDENTITIES` after `STANDARD_IDENTITIES`**

Add this block immediately after the closing `}` of `STANDARD_IDENTITIES` (currently ending at line 61) and before `def get_identity_for_node`:

```python
SOLO_AND_EDGE_IDENTITIES: Dict[str, SyntheticIdentity] = {
    "solo_claude": SyntheticIdentity(
        username="dana",
        email="dana@test.synlynk",
        role="dev",
        harness="claude",
        model_tier="pro",
        model="claude-opus-4-6",
        api_keys={
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY", "mock-anthropic-key-testbed"),
        },
    ),
    "gateway_poweruser": SyntheticIdentity(
        username="erin",
        email="erin@test.synlynk",
        role="dev",
        harness="claude",
        model_tier="pro",
        model="claude-opus-4-6-gateway",
        api_keys={
            "ANTHROPIC_BASE_URL": os.environ.get("ANTHROPIC_BASE_URL", "https://mock-gateway.test.synlynk"),
            "ANTHROPIC_AUTH_TOKEN": os.environ.get("ANTHROPIC_AUTH_TOKEN", "mock-gateway-token-testbed"),
            "CLAUDE_CONFIG_DIR": os.environ.get("CLAUDE_CONFIG_DIR", "/tmp/mock-claude-config-testbed"),
        },
    ),
    "ci_headless": SyntheticIdentity(
        username="ci-bot",
        email="ci-bot@test.synlynk",
        role="dev",
        harness="codex",
        model_tier="fast",
        model="gpt-5.3-codex-headless",
        api_keys={
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY", "mock-openai-key-testbed"),
        },
    ),
}
```

This reuses the exact `SyntheticIdentity` dataclass already defined at the top of the file (`username, email, role, harness, model_tier, model, api_keys`) — no structural changes.

- [ ] **Step 2: Verify the module still imports cleanly**

Run: `python3 -c "from synlynk.testbed.identities import SOLO_AND_EDGE_IDENTITIES, STANDARD_IDENTITIES; print(sorted(SOLO_AND_EDGE_IDENTITIES)); print(sorted(STANDARD_IDENTITIES))"`
Expected: `['ci_headless', 'gateway_poweruser', 'solo_claude']` then `['node-1', 'node-2', 'node-3']` — no traceback.

- [ ] **Step 3: Commit**

```bash
git add synlynk/testbed/identities.py
git commit -m "feat(testbed): add solo/edge identity fixtures for review-gate matrix"
```

---

### Task 2: Add `run_review_gate_matrix` scenario

**Files:**
- Modify: `synlynk/testbed/scenarios.py`

- [ ] **Step 1: Add the method to `ScenarioRunner`**

Add this method to the `ScenarioRunner` class in `synlynk/testbed/scenarios.py`, immediately after `run_state_db_wal_soak` (which currently ends the file at line 128):

```python
    def run_review_gate_matrix(self, conn) -> List[ScenarioResult]:
        """Local (no VM) matrix proving which identity shapes satisfy cross-harness review.

        Team identities are paired with a distinct teammate reviewer (the realistic
        case); solo/edge identities are paired with themselves, since that is the
        literal gh:#5355 condition — one harness account, no second identity to
        review with. Caller is responsible for cwd (policy.json lookup) and for
        passing an already-migrated connection, matching
        synlynk.db._cross_harness_review_verdict's own contract.
        """
        from synlynk.db import _cross_harness_review_verdict
        from synlynk.testbed.identities import STANDARD_IDENTITIES, SOLO_AND_EDGE_IDENTITIES

        alice = STANDARD_IDENTITIES["node-1"]
        bob = STANDARD_IDENTITIES["node-2"]
        charlie = STANDARD_IDENTITIES["node-3"]
        solo_claude = SOLO_AND_EDGE_IDENTITIES["solo_claude"]
        gateway_poweruser = SOLO_AND_EDGE_IDENTITIES["gateway_poweruser"]
        ci_headless = SOLO_AND_EDGE_IDENTITIES["ci_headless"]

        pairings = [
            (9001, alice, charlie),
            (9002, bob, charlie),
            (9003, charlie, alice),
            (9004, solo_claude, solo_claude),
            (9005, gateway_poweruser, gateway_poweruser),
            (9006, ci_headless, ci_headless),
        ]

        results: List[ScenarioResult] = []
        for pr_number, implementer, reviewer in pairings:
            start_t = time.time()
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                ("2026-11-21", implementer.harness, implementer.harness, implementer.model, "test", pr_number),
            )
            conn.execute(
                "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number, agent_role) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("2026-11-21", reviewer.harness, reviewer.harness, reviewer.model, "test", pr_number, "qa"),
            )
            conn.commit()
            ok, message = _cross_harness_review_verdict(conn, pr_number)
            duration = time.time() - start_t
            results.append(ScenarioResult(
                name=f"review_gate_matrix:{implementer.username}",
                status="PASSED" if ok else "FAILED",
                duration_seconds=duration,
                details=message,
            ))
        return results
```

Note: the implementer row deliberately omits the `agent_role` column (defaults to `NULL`, which `_native_cost_entry_identity`'s `COALESCE(agent_role, '') NOT IN ('qa')` filter treats as a non-reviewer row) — this exactly mirrors the existing pattern in `tests/test_agent_cli.py`'s `test_pr_check_accepts_native_reviewer_cost_entry`. Do not pass `implementer.role` into this column: `charlie.role` is `"qa"`, and tagging charlie's *implementer* row with `agent_role="qa"` would make `_native_cost_entry_identity(reviewer=False)` exclude it, breaking pairing `(9003, charlie, alice)`.

- [ ] **Step 2: Verify the method is importable and runs against a scratch db**

Run:
```bash
python3 -c "
import sqlite3, tempfile, os
os.environ['SYNLYNK_ALLOW_CWD_FALLBACK'] = '1'
import synlynk
with tempfile.TemporaryDirectory() as tmp:
    os.makedirs(os.path.join(tmp, '.synlynk'), exist_ok=True)
    with open(os.path.join(tmp, '.synlynk', 'policy.json'), 'w') as fh:
        fh.write('{\"overrides\": {\"merge_authority\": {\"cross_harness_review_required\": true}}}')
    os.chdir(tmp)
    conn = synlynk._get_db(os.path.join(tmp, 'state.db'))
    import synlynk.db as db
    db._pr_closing_issue_numbers = lambda _pr: []
    db._pr_head_branch = lambda _pr: 'feat/scratch'
    from synlynk.testbed.scenarios import ScenarioRunner
    results = ScenarioRunner().run_review_gate_matrix(conn)
    for r in results:
        print(r.name, r.status, r.details)
"
```
Expected output (order matches `pairings`):
```
review_gate_matrix:alice PASSED implementation codex / gpt-4o-mini (native cost record) reviewed by grok / grok-3 (native cost record)
review_gate_matrix:bob PASSED implementation agy / gemini-1.5-pro (native cost record) reviewed by grok / grok-3 (native cost record)
review_gate_matrix:charlie PASSED implementation grok / grok-3 (native cost record) reviewed by codex / gpt-4o-mini (native cost record)
review_gate_matrix:dana FAILED implementing and reviewing jobs use the same harness+model (claude / claude-opus-4-6)
review_gate_matrix:erin FAILED implementing and reviewing jobs use the same harness+model (claude / claude-opus-4-6-gateway)
review_gate_matrix:ci-bot FAILED implementing and reviewing jobs use the same harness+model (codex / gpt-5.3-codex-headless)
```
If any status doesn't match, re-check the pairing table and the `agent_role` columns against Step 1 before continuing.

- [ ] **Step 3: Commit**

```bash
git add synlynk/testbed/scenarios.py
git commit -m "feat(testbed): add run_review_gate_matrix local scenario"
```

---

### Task 3: Test wiring in `tests/test_ftue_vm_acceptance.py`

**Files:**
- Modify: `tests/test_ftue_vm_acceptance.py`
- Reuses (not modified): `project_dir` and `isolated_db` autouse fixtures in `tests/conftest.py`

- [ ] **Step 1: Add imports and a local policy-enabling helper**

Add to the top of `tests/test_ftue_vm_acceptance.py`, after the existing `from synlynk.testbed.driver import ...` import:

```python
import json

from synlynk.testbed.scenarios import ScenarioRunner


def _enable_enforce_policy(project_dir, monkeypatch, mode="enforce"):
    import synlynk.db as db

    policy_path = project_dir / ".synlynk" / "policy.json"
    policy_path.parent.mkdir(parents=True, exist_ok=True)
    policy_path.write_text(json.dumps({
        "overrides": {
            "merge_authority": {
                "cross_harness_review_required": True,
                "cross_harness_review_required_mode": mode,
            }
        }
    }))
    monkeypatch.chdir(project_dir)
    monkeypatch.setattr(db, "_pr_closing_issue_numbers", lambda _pr: [])
    monkeypatch.setattr(db, "_pr_head_branch", lambda _pr: "feat/review-gate-matrix")
```

This mirrors `tests/test_agent_cli.py`'s existing `_enable_cross_harness_policy` helper exactly (same policy.json shape, same two `_pr_closing_issue_numbers`/`_pr_head_branch` stubs to avoid real `gh` subprocess calls), with `cross_harness_review_required_mode` added since this test also exercises the observe/enforce gate layer in Step 3 below.

- [ ] **Step 2: Write the matrix scenario test**

Add this test function to `tests/test_ftue_vm_acceptance.py`:

```python
def test_review_gate_matrix_reproduces_solo_harness_gap(project_dir, monkeypatch):
    """gh:#5355 — solo-harness/gateway/headless identities fail cross-harness review
    with no carve-out, while team identities with a distinct teammate pass."""
    import synlynk

    _enable_enforce_policy(project_dir, monkeypatch)
    conn = synlynk._get_db()

    results = ScenarioRunner().run_review_gate_matrix(conn)

    by_name = {r.name: r for r in results}
    assert by_name["review_gate_matrix:alice"].status == "PASSED"
    assert by_name["review_gate_matrix:bob"].status == "PASSED"
    assert by_name["review_gate_matrix:charlie"].status == "PASSED"

    assert by_name["review_gate_matrix:dana"].status == "FAILED"
    assert "same harness+model" in by_name["review_gate_matrix:dana"].details
    assert by_name["review_gate_matrix:erin"].status == "FAILED"
    assert "same harness+model" in by_name["review_gate_matrix:erin"].details

    # ci_headless's outcome is reported, not pre-judged (spec §3.3/§5) — surfaced
    # for human review rather than asserted on, since current code treats every
    # self-paired identity the same way regardless of whether it's human or bot.
    print(f"ci_headless verdict: {by_name['review_gate_matrix:ci-bot'].status} "
          f"— {by_name['review_gate_matrix:ci-bot'].details}")

    conn.close()
```

- [ ] **Step 3: Run it to verify it currently fails the right way**

Run: `pytest tests/test_ftue_vm_acceptance.py::test_review_gate_matrix_reproduces_solo_harness_gap -v`
Expected: PASS. (The test asserts the *bug's* presence — `dana`/`erin` are asserted `FAILED`, which is the correct, expected-red-state behavior per spec §3.3. The pytest test itself should go green, confirming the scenario faithfully reproduces gh:#5355.)

If this pytest run instead errors or the `dana`/`erin` assertions don't match, do not change the assertions to make it pass — re-check Task 2's pairing table and `_cross_harness_review_verdict`'s current behavior in `synlynk/db.py:372-446` first; a change there means the gap may already be fixed or the matrix is wired wrong.

- [ ] **Step 4: Write the mode-parametrized gate test**

Add this test function, which exercises the `observe`/`enforce` mode layer (`synlynk/policy_gates.py`) on top of the raw verdict, per spec §3.2 step 4:

```python
@pytest.mark.parametrize("mode,expected_should_block", [("observe", False), ("enforce", True)])
def test_cross_harness_gate_mode_blocks_only_in_enforce(project_dir, monkeypatch, mode, expected_should_block):
    """The raw verdict always fails for a solo identity; only enforce mode blocks on it."""
    import synlynk
    import synlynk.db as db
    from synlynk.policy_gates import _evaluate_gate, classify_cross_harness_verdict
    from synlynk.testbed.identities import SOLO_AND_EDGE_IDENTITIES

    _enable_enforce_policy(project_dir, monkeypatch, mode=mode)
    conn = synlynk._get_db()
    solo_claude = SOLO_AND_EDGE_IDENTITIES["solo_claude"]
    pr_number = 9100
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-11-21", solo_claude.harness, solo_claude.harness, solo_claude.model, "test", pr_number),
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, model, cost_source, pr_number, agent_role) "
        "VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-11-21", solo_claude.harness, solo_claude.harness, solo_claude.model, "test", pr_number, "qa"),
    )
    conn.commit()

    ok, message = db._cross_harness_review_verdict(conn, pr_number)
    assert not ok

    evaluation = _evaluate_gate(
        conn, pr_number=pr_number, gate="cross_harness_review",
        mode_key="cross_harness_review_required_mode", policy_section="merge_authority",
        verdict=classify_cross_harness_verdict(ok, message),
    )

    assert evaluation.verdict == "warn"
    assert evaluation.should_block is expected_should_block
    conn.close()
```

- [ ] **Step 5: Run both new tests**

Run: `pytest tests/test_ftue_vm_acceptance.py -v -k "review_gate_matrix or cross_harness_gate_mode"`
Expected: 3 tests pass (`test_review_gate_matrix_reproduces_solo_harness_gap`, and the two parametrized cases of `test_cross_harness_gate_mode_blocks_only_in_enforce`).

- [ ] **Step 6: Run the full file to confirm no regressions**

Run: `pytest tests/test_ftue_vm_acceptance.py -v`
Expected: all 5 tests pass (the 2 pre-existing + 3 new), none skipped except possibly `test_live_orb_ftue_e2e` if `orbctl` isn't running locally (pre-existing `skipif`, unrelated to this change).

- [ ] **Step 7: Commit**

```bash
git add tests/test_ftue_vm_acceptance.py
git commit -m "test(ftue): add review-gate identity matrix reproducing gh:#5355"
```

---

### Task 4: Update blog post and roadmap note (project housekeeping)

**Files:**
- Create: `docs/blog/` entry per this project's Blog Post Protocol — **superseded**: per CLAUDE.md's "Multi-Task & Multi-Goal Series Tracking Protocol" (point 4), the per-PR blog stub convention is retired; post a conversational status rollup on gh:#5355 instead once the PR is open.
- No `project-docs/roadmap.md` edit needed — `roadmap.md` is no longer git-tracked (state.db is sole authority per gh:#2653); this plan has no roadmap-arc implications since it's test-only infrastructure.

- [ ] **Step 1: No action required before PR open**

This task exists only to flag, not to execute: once a PR is opened for this plan's commits, post a status-rollup comment on gh:#5355 (the parent tracking issue) summarizing that a reproducing regression test now exists, per the Multi-Task & Multi-Goal Series Tracking Protocol. This is a PR-time action, not a plan-execution step — do not create a `docs/blog/` file for this change.

---

## Self-Review Notes (writing-plans skill)

**Spec coverage:**
- §3.1 (new identity fixtures) → Task 1.
- §3.2 steps 1-3 (seed rows, call verdict directly) → Task 2.
- §3.2 step 4 (parameterize over observe/enforce) → Task 3 Step 4 (separate test, since `_cross_harness_review_verdict` itself has no mode parameter — mode only affects `_evaluate_gate`, a distinct function in `synlynk/policy_gates.py`).
- §3.3 (expected red-state result) → Task 3 Step 2 assertions.
- §3.4 (test wiring, not gated behind `_is_orbctl_available()`) → Task 3 (confirmed: neither new test function has the `@pytest.mark.skipif(not _is_orbctl_available(), ...)` decorator used by `test_live_orb_ftue_e2e`).
- §4 (out of scope: fixing #5355, re-running full journey, GitHub mock) → not addressed by any task, by design.
- §5 (verification matrix) → Task 3 Step 2's exact per-identity assertions.
- §6 (rollout: spec → plan → PR → follow-up fix PR) → this plan is step 2; Task 4 flags the step-3 PR action without executing it.

**Placeholder scan:** no TBD/TODO markers; every code step shows complete, runnable code; every "Run:" step shows the exact command and exact expected output, derived directly from the fixture data defined in Task 1 (harness/model pairs) and the assertion-message formats verified in `tests/test_agent_cli.py`.

**Type/signature consistency:** `run_review_gate_matrix(self, conn) -> List[ScenarioResult]` is used identically in Task 2 (definition) and Task 3 (call sites). `ScenarioResult(name, status, duration_seconds, details, invariants=None)` matches the existing dataclass in `synlynk/testbed/scenarios.py:13-19` — no new fields introduced. `_evaluate_gate`'s keyword arguments (`pr_number`, `gate`, `mode_key`, `policy_section`, `verdict`) match the verified production call site at `synlynk/db.py:6075-6080` exactly.

---

## Execution Handoff

**Plan complete and saved to `docs/superpowers/plans/2026-11-21-ftue-review-gate-identity-matrix.md`. Two execution options:**

**1. Subagent-Driven (recommended)** — I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** — Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
