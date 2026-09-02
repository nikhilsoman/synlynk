# Design Spec: Autonomous Cadence-Breaker Resilience & Self-Healing Engine

**Date:** 2026-09-02  
**Status:** In Review  
**Authors:** [@nikhilsoman], [@agy], [@codex], [@claude]  
**Relates to:** #1073, #1327, #1303, #937, #1198  

---

## 1. Objective & Scope

Establish automated self-healing mechanisms and guard positions across the Synlynk daemon and workspace agents to eliminate the 5 primary **Cadence Breakers** that halt 24/7 autonomous loop execution.

---

## 2. The 5 Cadence Breakers & Self-Healing Architecture

```
                               ┌──────────────────────────────────────────────┐
                               │           SELF-HEALING CONTROL LOOP          │
                               └──────────────────────┬───────────────────────┘
                                                      │
         ┌──────────────────────────────┬─────────────┴────────────────┬──────────────────────────────┐
         ▼                              ▼                              ▼                              ▼
 ┌───────────────┐              ┌───────────────┐              ┌───────────────┐              ┌───────────────┐
 │ Markdown-Auto │              │ Token Bloat   │              │ Harness CLI   │              │ Zombie PID    │
 │ Rebaser       │              │ Killer        │              │ Failover      │              │ SRE Reaper    │
 ├───────────────┤              ├───────────────┤              ├───────────────┤              ├───────────────┤
 │ Resolves PR   │              │ Kills stalled │              │ Re-queues to  │              │ Cleans leaked │
 │ table/append  │              │ loops at $5 / │              │ backup on     │              │ locks & stale │
 │ conflicts     │              │ 500k tokens   │              │ startup crash │              │ worktrees     │
 └───────────────┘              └───────────────┘              └───────────────┘              └───────────────┘
```

### A. Markdown Table & Append-Only Conflict Auto-Rebaser
- **Problem:** When concurrent dispatches finish, squash merges to `main` produce trivial git conflicts in `docs/blog/README.md`, `project-docs/memory.md`, or `docs/reference/commands.md`.
- **Self-Healing Mechanism (`synlynk/rebase.py`):**
  - Detects if merge conflicts on a PR branch are purely in structured markdown tables or append-only memory entries.
  - Automatically merges `origin/main`, parses conflicting table blocks, interleaves rows chronologically by PR number, commits with `merge: auto-rebase markdown index`, and proceeds to merge.

### B. Monotonic Token Bloat & Runaway Stall Circuit Breaker
- **Problem:** Subagents in `--context-mode full` stall in internal wait loops (e.g. incident `job-cf837848` burning $5.26 on 0 files).
- **Self-Healing Mechanism (`synlynk/sentinel.py`):**
  - Live job monitor checks active processes every 30s.
  - If cumulative tokens $\ge 500\text{k}$ with 0 files touched OR accumulated cost $\ge \$5.00$:
    - Issues `SIGTERM` to subagent process.
    - Captures process stack trace and logs incident in `state.db`.
    - Resets story to `stalled_aborted` and releases worktree lock.

### C. Harness Option Failure & Startup Failover
- **Problem:** CLI option incompatibilities (e.g. duplicate flags, sandbox permissions) crash the primary harness on launch with non-zero exit.
- **Self-Healing Mechanism (`synlynk/dispatch.py`):**
  - If harness exits non-zero within 10s of launch without modifying files:
    - Logs diagnostic failure in `state.db`.
    - Automatically routes task to secondary harness in the capability matrix (e.g., Codex $\rightarrow$ Agy $\rightarrow$ Claude).

### D. Zombie PID & Leaked Worktree SRE Reaper
- **Problem:** Aborted terminal sessions or killed OS processes leave leaked `.worktrees/job-*` directories and stale locks in `daemon_jobs`.
- **Self-Healing Mechanism (`synlynk/jobs.py` & `synlynk daemon`):**
  - Heartbeat reaper sweeps `daemon_jobs` every 60 seconds.
  - Any job where PID is dead in the OS process table and status is still `running` is marked `killed_zombie`.
  - Automatically runs `git worktree remove --force` and unlinks stale locks.

### E. GitHub API Rate-Limit & Token Expiry Buffer
- **Problem:** Secondary rate limits (HTTP 403) or expired GitHub App tokens stall remote operations.
- **Self-Healing Mechanism (`synlynk/team.py`):**
  - Staged SQLite mutation buffer: all GitHub API writes queue locally in `state.db`.
  - On 403 or rate-limit response, the daemon backs off exponentially with random jitter and automatically re-generates App installation tokens from the App private key.

---

## 3. Test & Verification Strategy
- Synthetic conflict injection test in `tests/test_rebase.py`.
- Automated mock process timeout and SIGTERM killer test in `tests/test_sentinel.py`.
- Crash failover routing test in `tests/test_dispatch.py`.
- Stale PID reaper test in `tests/test_jobs.py`.
