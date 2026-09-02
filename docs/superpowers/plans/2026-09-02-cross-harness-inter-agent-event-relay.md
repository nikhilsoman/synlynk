# Implementation Plan: Cross-Harness Inter-Agent Event Relay (synlynk relay)

**Spec:** `docs/superpowers/specs/2026-09-02-cross-harness-inter-agent-event-relay-design.md`  
**Issue:** [#1339](https://github.com/nikhilsoman/synlynk/issues/1339)  
**Goal:** `goal-ef42902a` (Networked Messaging across Workspace > User > Agent > Process hierarchy)  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Event Schema & Serialization Engine (`synlynk/events.py`)**
  - Implement `EventEnvelope`, `ActorIdentifier` (`workspace_id`, `member_id`, `agent_role`, `harness`, `job_id`), and event types (`agent_started`, `task_progress`, `artifact_published`, `review_requested`, `steering_injected`, `agent_completed`).
  - Add SQLite persistence helpers in `synlynk/db.py` (`relay_events` and `relay_mailbox` tables).
  - Add unit tests in `tests/test_events.py`.

- [ ] **Task 2: Lightweight Relay Server & JSON-RPC Dispatcher (`synlynk/relay.py`)**
  - Implement standard library `http.server.ThreadingHTTPServer` with `GET /events` (SSE broadcasting) and `POST /rpc` (JSON-RPC 2.0 handler).
  - Implement RPC methods: `relay.send_message`, `relay.inject_steering`, `relay.request_review`, `relay.broadcast`.
  - Support thread-safe subscriber queues with automatic dead-client pruning.
  - Add unit tests in `tests/test_relay.py`.

- [ ] **Task 3: Relay CLI Commands & Real-Time Watcher**
  - Register CLI commands in `synlynk/cli.py` and `synlynk/taxonomy.py`:
    - `synlynk relay start [--port 7432] [--daemon]`
    - `synlynk relay status`
    - `synlynk relay send --to-agent <role> --message <text>`
    - `synlynk relay tail`
  - Upgrade `synlynk watch` to subscribe to the local `/events` SSE stream.
  - Update `docs/reference/commands.md` via `scripts/generate_command_docs.py`.

- [ ] **Task 4: Harness Adapter Hooks & Cross-Agent Messaging Bridge**
  - Connect Agy `send_message` tool hook to relay client.
  - Add MCP relay tool adapter for Claude harness.
  - Add non-interactive background event listener for Codex / Grok workers.

- [ ] **Task 5: Documentation, Blog Post, and Full Suite Verification**
  - Add integration tests simulating cross-agent steering and review requests in `tests/test_relay_e2e.py`.
  - Author blog post `docs/blog/165-pr1348-cross-harness-event-relay.md` and index in `docs/blog/README.md`.
  - Update `project-docs/memory.md` and devlogs. Ensure all pytest tests pass.
