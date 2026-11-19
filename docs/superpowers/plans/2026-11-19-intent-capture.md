# Intent Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add one persistent intent-capture primitive shared by the CLI, Vizor, and TPM daemon polling, with semantic associations to roadmap and repository knowledge.

**Architecture:** `synlynk/intent.py` owns schema migration, capture/list operations, deterministic lexical association, and proposal-shaped outcomes. The CLI, Vizor HTTP route, and TPM wake cycle are thin adapters over that API; GitHub polling records free-text issue/comment intent while retaining external item IDs for idempotency.

**Tech Stack:** Python 3, SQLite, argparse, existing Vizor HTTP server, TPM GitHub role wrapper, pytest.

**Spec:** `docs/superpowers/specs/2026-11-13-intent-based-engineering-and-roadmap-drift-governance-design.md` Section 1

## Global Constraints

- Captures never directly create or mutate a goal; they persist a proposal for `/approve /revise /drop /prioritize /hold` ratification.
- Association checks goals, stories, roadmap phases, `.synlynk/docgraph.json`, and available Graphify/impact graph artifacts.
- Existing databases migrate lazily and supplied SQLite connections remain caller-owned.
- GitHub polling reuses the TPM wake cadence and must be idempotent without a separate poller.

## Review Focus

- Blank text is rejected without writing a row.
- Sparse/legacy databases and missing graph artifacts degrade to an orphan result rather than crashing.
- Repeated external GitHub events do not create duplicate captures.
- Caller-owned connections are not closed and their transaction remains usable.
- Vizor and CLI return the same persisted record shape as the Python primitive.

---

### Task 1: Persistent capture and semantic association

**Files:**
- Create: `synlynk/intent.py`
- Create: `tests/test_intent_capture.py`

**Interfaces:**
- Produces: `capture_intent(text, source='terminal', context=None, conn=None) -> dict`, `list_intents(conn=None) -> list[dict]`, and `poll_github_intents(conn=None) -> dict`.

- [ ] Write failing tests for persistence, matching goals/stories/roadmap, docgraph and impact artifacts, orphan fallback, validation, connection ownership, and external-event deduplication.
- [ ] Run `pytest -q tests/test_intent_capture.py` and confirm failures are caused by the missing module/API.
- [ ] Implement lazy `intent_captures` schema creation and deterministic token-overlap scoring across database and graph candidates; store context, associations, resolution, status, and external identity as JSON/text columns.
- [ ] Run `pytest -q tests/test_intent_capture.py` and confirm the primitive tests pass.

### Task 2: CLI adapters

**Files:**
- Modify: `synlynk/cli.py`
- Modify: `tests/test_intent_capture.py`

**Interfaces:**
- Consumes: Task 1 capture/list functions.
- Produces: `synlynk intent capture <text>` and `synlynk intent list`.

- [ ] Add failing parser/dispatch tests that capture prints the proposal record and list prints persisted captures.
- [ ] Run the focused tests and confirm the `intent` command is absent.
- [ ] Add the nested parser and thin command dispatch.
- [ ] Run the focused tests and confirm they pass.

### Task 3: Vizor and daemon/TPM adapters

**Files:**
- Modify: `synlynk/viz/write_routes.py`
- Modify: `synlynk/viz/server.py`
- Modify: `synlynk/tpm_sweep.py`
- Modify: `tests/test_intent_capture.py`

**Interfaces:**
- Consumes: Task 1 APIs.
- Produces: authenticated `POST /api/intent/capture` and a GitHub intent-poll result in each TPM wake cycle.

- [ ] Add failing tests for card-context capture, route classification, free-text issue/comment filtering, command-grammar exclusion, and wake-cycle polling.
- [ ] Run focused tests and verify the missing adapters cause the failures.
- [ ] Add the Vizor route/handler and call GitHub intent polling from the existing TPM wake cadence.
- [ ] Run `pytest -q tests/test_intent_capture.py` and the smallest affected Vizor/TPM test files.

### Task 4: Verification and commit

**Files:**
- Verify all files above.

- [ ] Run `pytest -q` on every added or modified test file, retaining only the last 30 lines in `.synlynk/logs/job-797a0db1-verify-1.log` if output exceeds 4000 characters.
- [ ] Run mutation review for missing persistence, wrong association target, duplicate external event, unauthenticated Vizor write, and daemon poll omission.
- [ ] Confirm `git branch --show-current` is not protected and inspect `git diff --check` plus `git status --short`.
- [ ] Commit with a conventional message and `Co-Authored-By: Codex <noreply@openai.com>`.
