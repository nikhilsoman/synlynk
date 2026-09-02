---
title: "Cross-Harness Event Relay"
date: 2026-09-02
---

# Cross-Harness Event Relay

Agents increasingly work across harnesses, but disk polling makes progress and
handoffs slow to observe. This change adds `synlynk relay`: a small local
ThreadingHTTPServer with an SSE event stream and JSON-RPC 2.0 control endpoint.

Events use a typed `EventEnvelope` with a stable `ActorIdentifier`, so a
message can identify its workspace, member, role, harness, and job. Relay
events are persisted in SQLite, while point-to-point messages also enter a
recipient mailbox for later delivery.

The first CLI surface is intentionally small: `relay start`, `status`, `send`,
and `tail`. The standard-library implementation keeps the relay easy to run in
headless workers and easy to test with an ephemeral port.
