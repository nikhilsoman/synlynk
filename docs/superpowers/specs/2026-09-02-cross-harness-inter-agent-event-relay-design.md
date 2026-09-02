# Design Spec: Cross-Harness Inter-Agent Event Relay Protocol (synlynk relay)

**Date:** 2026-09-02  
**Status:** In Review  
**Issue:** [#1339](https://github.com/nikhilsoman/synlynk/issues/1339)  
**Authors:** [@nikhilsoman], [@agy], [@codex]  
**Relates to:** `goal-ef42902a`, #1326  

---

## 1. Objective & Scope

Define a lightweight, low-latency **Cross-Harness Inter-Agent Event Relay** (`synlynk relay`) to replace asynchronous disk polling with real-time streaming event broadcast and point-to-point subagent messaging.

---

## 2. Protocol Architecture

```
 ┌──────────────────────┐         HTTP POST JSON-RPC          ┌──────────────────────┐
 │    Leader Agent      │────────────────────────────────────▶│   synlynk relay      │
 │    (e.g. Agy)        │◀────────────────────────────────────│   In-Process / SSE   │
 └──────────────────────┘         SSE /events Stream          └──────────┬───────────┘
                                                                         │
                                              ┌──────────────────────────┴──────────────────────────┐
                                              ▼                                                     ▼
                                   ┌──────────────────────┐                              ┌──────────────────────┐
                                   │    Worker Agent 1    │                              │    Worker Agent 2    │
                                   │    (e.g. Codex)      │                              │    (e.g. Grok)       │
                                   └──────────────────────┘                              └──────────────────────┘
```

### A. Transport & Interfaces
1. **Server-Sent Events (`GET /events`):**
   - Unidirectional, low-overhead event streaming for progress tracking, artifact notifications, and live status logs.
2. **JSON-RPC (`POST /rpc`):**
   - Bi-directional messaging:
     - `relay.send_message(target_agent_id, message, payload)`
     - `relay.request_review(pr_url, diff_summary)`
     - `relay.inject_steering(job_id, prompt_delta)`
     - `relay.broadcast(topic, payload)`

### B. Standard Event Schema (`synlynk/events.py`)
```json
{
  "event_id": "evt-7a91bf02",
  "timestamp": "2026-09-02T12:00:00Z",
  "sender": {
    "agent_role": "architect",
    "harness": "agy",
    "job_id": "job-9c597160"
  },
  "recipient": {
    "agent_role": "dev",
    "harness": "codex",
    "job_id": "job-a24af5b3"
  },
  "event_type": "artifact_published",
  "payload": {
    "artifact_type": "diff_patch",
    "file_paths": ["synlynk/sentinel.py"],
    "summary": "Token bloat sentinel guard implementation ready for review."
  }
}
```

### C. Harness Integration & Adapter Hooks
- **Claude:** MCP server exposing `relay_send` / `relay_listen` tools.
- **Agy:** Antigravity SDK native subagent messaging hook (`send_message`).
- **Codex / Grok:** Non-interactive event listener background worker reading from relay socket.

---

## 3. Test & Verification Plan
- Concurrent pub/sub throughput and delivery verification tests in `tests/test_relay.py`.
- Mock cross-harness handshake test between simulated Agy lead and Codex worker.
