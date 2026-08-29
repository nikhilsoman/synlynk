# Codex Direct GitHub-Write Network Access via Config Override — Design

**Date:** 2026-08-29  
**Status:** Approved (directed by Nikhil Soman following live verification on #865/#1268)  
**Author:** Agy (Gemini)  
**Tracking Issues:** #865 (closed evaluation), #1268 (implementation scope)  

---

## 1. Motivation & Context

In synlynk's dispatch policy (`.synlynk/policy.json`), GitHub-write actions (PR review, PR comment, issue closure) have historically routed to Claude by default and Agy as fallback, with Codex excluded on the assumption that OpenAI Codex's `workspace-write` sandbox enforces an unbypassable, structural block on network egress to `api.github.com`.

On 2026-08-29, two empirical investigations clarified the actual ground truth:

1. **Attribution False Positive on PR #1258:**
   In `job-78d04989`, Codex patched `synlynk/daemon.py` and `synlynk/db.py` locally and exited 0. PR #1258 was then created by synlynk's host-level wrapper (`_maybe_open_worktree_pr` in `synlynk/jobs.py`), not by Codex inside the sandbox. Codex never attempted any network calls.
2. **Live Empirical Sandbox Probe:**
   Testing OpenAI Codex CLI (`v0.150.1`) on macOS Darwin arm64 under synlynk's exact invocation path (`codex exec - -s workspace-write`):
   - **Default:** `curl https://api.github.com` immediately fails with `curl: (6) Could not resolve host: api.github.com` (DNS/Seatbelt isolation).
   - **With Config Override (`-c sandbox_workspace_write.network_access=true`):** `curl https://api.github.com` cleanly succeeds (`HTTP/2 200`).

Issue #1268 originally proposed a complex **brokered file-based relay** (Codex writing action files into a local queue, watched by `synlynk daemon` which executes `gh` on its behalf). This design replaces that over-engineered relay with a **direct native configuration override**, achieving full fleet symmetry with minimal complexity.

---

## 2. Alternatives Considered

| Dimension | Option A: Brokered File Relay (#1268) | Option B: Direct Config Override (Selected) |
| :--- | :--- | :--- |
| **Complexity** | High: Custom file IPC, schema serialization, daemon watch loop, synchronous wait/poll loop in Codex, retry/timeout logic. | Minimal: ~5 lines in `synlynk/dispatch.py` passing `-c sandbox_workspace_write.network_access=true`. |
| **Model Alignment** | Poor: Forces Codex into proprietary JSON file queues, fighting its native pre-training on `gh` and `git` CLI tools. | Native: Codex executes standard `gh pr review`, `gh pr comment` commands. |
| **Operational Health** | Fragile: Dependent on daemon health. Daemon crashes or hangs freeze all review dispatches. | Robust: Stateless subprocess execution; no background daemon dependency. |
| **Fleet Symmetry** | Asymmetric: Claude, Agy, and Grok execute `gh` directly; only Codex would use a proxy relay. | Symmetric: All 4 harnesses share the exact same isolated execution environment contract (`_build_subprocess_env`). |

---

## 3. Security & Isolation Boundaries

Option B maintains strict isolation without relying on sandbox network denial:
1. **Process Environment Scrubbing:** `_build_subprocess_env()` in `synlynk/dispatch.py:505-566` strictly allowlists environment variables (`_ENV_ALLOWLIST_BASE`), purging personal GitHub tokens, SSH credentials, and ambient secrets.
2. **Role-Scoped GitHub App Token:** Only a short-lived (1-hour), role-scoped GitHub App token is injected as `GH_TOKEN` into an isolated `GH_CONFIG_DIR` temporary directory.
3. **Filesystem Confinement:** Codex remains strictly confined to its git worktree and `/tmp` via `-s workspace-write`.
4. **Preflight Policy Gates:** `check_authority()` in `synlynk/policy.py` validates role authority *before* dispatch, failing closed if the requested action is disallowed.

---

## 4. Architecture & Technical Specification

### 4.1 Permission Mapping in `synlynk/dispatch.py`

`synlynk/dispatch.py` already defines `_CODEX_NETWORK_PERMISSION = "run:install"` in `synlynk/_constants.py:43`.

When `requires_gh_write` is active (either passed explicitly as `--requires-gh-write` or inferred via `_task_requires_gh_write(task)`):
1. In `dispatch_agent()` (`synlynk/dispatch.py:2443-2448`):
   ```python
   effective_grants = list(grants or [])
   if requires_gh_write:
       if "run:shell" not in effective_grants:
           effective_grants.append("run:shell")
       if agent == "codex" and _CODEX_NETWORK_PERMISSION not in effective_grants:
           effective_grants.append(_CODEX_NETWORK_PERMISSION)
   ```
2. In `_permissions_to_flags("codex", permissions)` (`synlynk/dispatch.py:448-455`):
   Existing logic already appends `["-c", "sandbox_workspace_write.network_access=true"]` when `_CODEX_NETWORK_PERMISSION in (permissions or [])`. With `_CODEX_NETWORK_PERMISSION` included in effective grants, Codex automatically receives the config override.

### 4.2 Invariant Guarantees
- Non-gh-write dispatches (code editing, tests, documentation) without `run:install` continue to run with network access **disabled** by default.
- Dispatches requiring GitHub write capabilities receive network access and the isolated role-scoped `GH_TOKEN`.

---

## 5. Test Strategy (TDD)

1. **Unit Test in `tests/test_agent_cli.py` or `tests/test_synlynk.py`:**
   - Verify that `_permissions_to_flags("codex", ...)` continues to gate on `_CODEX_NETWORK_PERMISSION`.
   - Verify that `dispatch_agent()` includes `_CODEX_NETWORK_PERMISSION` in `permissions` and `-c sandbox_workspace_write.network_access=true` in Codex's CLI flags when `requires_gh_write=True`.
   - Verify that when `requires_gh_write=False` and `run:install` is absent, the network access flag is **not** present.
2. **End-to-End Live Verification:**
   - Execute a live headless dispatch with Codex on a task requiring GitHub write (`gh pr view` or test read/write) to confirm live execution succeeds without network denial.
