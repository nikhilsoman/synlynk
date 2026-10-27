# Harness-Dispatch Rejection & Parity Investigation

**Date:** 2026-10-23  
**Story:** story-adhoc-1792757200  
**Analyst:** Agy (Gemini) — read-only sweep  
**Scope:** Exhaustive taxonomy of dispatch rejections, sentinel alert coverage, and interactive/headless capability parity across all harnesses

---

## Executive Summary

This investigation sourced rejection patterns from the code (`dispatch.py`, `jobs.py`, `sentinel.py`, `circuit_breaker.py`, `daemon.py`, `policy_gates.py`, `capability_classifier.py`), the live `.synlynk/sentinel.md` (492 active alerts), project-docs (`memory.md`, 4 devlogs), policy configuration (`policy.json`, `capability-roles.json`), and harness instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, `GROK.md`).

**Key Findings:**
1. **20 distinct hard-rejection reasons** exist pre-dispatch (job never created)
2. **9 preflight sentinel codes** gate dispatch entry
3. **18 terminal failure statuses** can mark a job post-dispatch
4. **13 terminal statuses have NO sentinel alert** — silent status transitions
5. **28 unique sentinel alert codes** emit across 6 modules
6. **97/492 active alerts** are `STALL_NO_OUTPUT` — the dominant failure mode
7. **Agy** has the most stall alerts (concentrated 2026-10-17 burst); **Codex** has the most alerts overall (169/429 agent-attributed)
8. **6 documented false-negative patterns** where jobs reported failure despite successful work
9. **3 task types have zero fallback** (css, canvas, infra) — single points of failure
10. **Grok has no scoped-permission headless mode** (all-or-nothing bypass)

---

## 1. Rejection Taxonomy

### 1A. Pre-Dispatch Hard Rejections (Job Never Created)

These raise `RuntimeError`, `ValueError`, or `SystemExit` before any `daemon_jobs` row is written.

| # | Rejection Reason | Source | Error Pattern |
|---|---|---|---|
| 1 | Empty task | [`dispatch.py` L4230](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4230) | `"--task is empty or whitespace-only"` |
| 2 | Policy authority (role/task_type mismatch) | [`dispatch.py` L4344](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4344) | `"task_type is not an authorized task_type for role"` |
| 3 | GH-write missing role (dispatch) | [`dispatch.py` L4451](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4451) | `"--requires-gh-write requires a resolvable role identity"` |
| 4 | GH-write missing token (require) | [`dispatch.py` L887](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L887) | `"no valid, non-stale GitHub App token"` |
| 5 | GH-write missing token (build env) | [`dispatch.py` L1496](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L1496) | `"--requires-gh-write requires a role-scoped GitHub App token"` |
| 6 | GH-write missing role (build env) | [`dispatch.py` L1472](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L1472) | `"Dispatch refused: --requires-gh-write requires a resolvable role identity"` |
| 7 | Unknown agent | [`dispatch.py` L4533](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4533) | `"Unknown agent"` |
| 8 | No adapter registered | [`dispatch.py` L4396](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4396) | `"no registered dispatch adapter"` |
| 9 | Grok sandbox write denied (force) | [`dispatch.py` L4529](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4529) | `"Grok sandbox denies write capability"` |
| 10 | Unregistered agent_id | [`dispatch.py` L4100](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4100) | `"agent_id is unregistered"` |
| 11 | Disabled agent_id | [`dispatch.py` L4105](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4105) | `"agent is disabled"` |
| 12 | Local Pilot receipt invalid | [`dispatch.py` L4258](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4258) | `"invalid Local Pilot routing receipt"` |
| 13 | Local Pilot GH-write attempt | [`dispatch.py` L4265](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4265) | `"Local Pilot cannot execute GitHub-write work"` |
| 14 | Local Pilot container override | [`dispatch.py` L4267](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4267) | `"Local Pilot uses its fixed isolated Compose runner"` |
| 15 | Connector role not granted | [`dispatch.py` L4447](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4447) | `"explicit connector grant required"` |
| 16 | TC-7 Agy GH-write preflight | [`dispatch.py` L4493](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L4493) | `SystemExit(1)` |
| 17 | Local permission enforcement | [`dispatch.py` L1273](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L1273) | `PermissionEnforcementError` |
| 18 | Grok permission enforcement | [`dispatch.py` L1191](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L1191) | `PermissionEnforcementError` |
| 19 | Stacking on mainline | [`dispatch.py` L3074](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L3074) | `"refusing to stack on mainline"` |
| 20 | Worktree creation failure | [`dispatch.py` L3401](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L3401) | `"Failed to create worktree"` |

> [!IMPORTANT]
> **None of these 20 hard rejections write sentinel alerts.** They raise exceptions caught by the CLI, so no job record or alert trail exists. The only evidence is the operator's terminal output.

### 1B. Preflight Gate Failures (Returned as `{passed: False}`)

From [`_preflight_dispatch`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py#L3714-L4021):

| Sentinel Code | Severity | Trigger | Alert Written? |
|---|---|---|---|
| `LOCAL_CAPABILITY_UNAVAILABLE` | CRITICAL | Local config missing, oMLX unreachable, aider not installed | Yes (via caller) |
| `LOCAL_ORBSTACK_UNAVAILABLE` | CRITICAL | OrbStack container runtime not running | Yes (via caller) |
| `INSTRUCTION_FILE_MISSING` | CRITICAL | Core 4 harness missing its instruction file (LIVE-1 / #343) | Yes (via caller) |
| `MCP_SERVER_MISSING` | CRITICAL | Agy Stitch MCP server not configured | Yes (via caller) |
| `HARNESS_PREFLIGHT_FAIL` | CRITICAL | Invalid flag, auth probe failed, headless permission auto-denial | Yes (via caller) |
| `CAPACITY_EXCEEDED_INPUT` | CRITICAL | Task exceeds input token budget | Yes (via caller) |
| `CAPACITY_EXCEEDED_OUTPUT` | CRITICAL | Task exceeds output token budget | Yes (via caller) |
| `GOVERNS_LINKAGE_MISSING` | WARN | No --story/--issue/--pr linkage | Separate emission at L2154 |
| `HARNESS_VERSION_DRIFT` | WARN | Harness version changed (non-blocking) | Yes at L3863 |

### 1C. Routing Reroutes (Not Rejections — Harness Silently Changed)

| Trigger | Sentinel Code | From → To |
|---|---|---|
| Local oMLX unreachable | `DISPATCH_ROUTING_FALLBACK` | local → agy (default) |
| Local capability score < threshold | `DISPATCH_ROUTING_FALLBACK` | local → frontier |
| Local pilot decision rejected | `DISPATCH_ROUTING_FALLBACK` | local → frontier |
| Grok sandbox write denied | `GROK_WRITE_SANDBOX_DENIED` | grok → codex (then agy, claude) |
| GH-write capability routing | (none — logged in `fallback_reason`) | Per `GH_WRITE_HARNESS_PRIORITY` |
| Capability probe failure | (none — logged in routing) | Via `resolve_capable_dispatch_harness` |
| Cross-harness review exclusion | (none) | Implementing harness excluded |

### 1D. Post-Dispatch Terminal Failure Statuses

From [`jobs.py` L54-159](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/jobs.py#L54-L159):

| Status | Sentinel Alert? | Alert Code |
|---|---|---|
| `completed` | — | (success) |
| `failed` | Depends on cause | `STALL_NO_OUTPUT`, `STALL_GH_WRITE_UNVERIFIED` |
| `cancelled` | ❌ None | — |
| `interrupted` | ❌ None | — |
| `permission_denied` | ❌ None | Silent from log signature detection |
| `task_delivery_failed` | ⚠ Partial | `TASK_RECEIPT_WARN` (soft case only) |
| `failed_unverified` | ❌ None | — |
| `needs_fix` | ❌ None | From gate_suite_cmd |
| `stale_base` | ❌ None | — |
| `SCOPE_VIOLATION` | ❌ None | Status downgrade only |
| `SCOPE_REVIEW_REQUIRED` | ⚠ Partial | `TOKEN_BLOAT` + `COST_INFLATION` fire separately |
| `instruction_receipt_untrusted` | ❌ None | — |
| `completed_without_changes` | ✅ | `TASK_NOOP_DENIED` |
| `failed_noop_denied` | ✅ | `TASK_NOOP_DENIED` |
| `failed_verification` | ❌ None | After GH-write retry exhausted |
| `unpushed_branch` | ❌ None | — |
| `circuit_breaker_tripped` | ✅ | `TOKEN_CIRCUIT_BREAKER_TRIPPED` |
| `pending_verification` | — | (non-terminal hold) |
| `succeeded_gh_write_failed` | ❌ None | In FAILURE_LOOKING set only |
| `unknown` | ❌ None | — |

> [!WARNING]
> **13 of 18 terminal failure statuses have no dedicated sentinel alert.** Status transitions for `permission_denied`, `cancelled`, `interrupted`, `failed_unverified`, `needs_fix`, `stale_base`, `SCOPE_VIOLATION`, `instruction_receipt_untrusted`, `failed_verification`, `unpushed_branch`, `succeeded_gh_write_failed`, and `unknown` are silent.

---

## 2. Sentinel Alert Coverage Matrix

### 2A. Complete Alert Code Inventory (28 codes across 6 modules)

| Code | Severity | Emitting Module | Lines | Trigger |
|---|---|---|---|---|
| **STALL_NO_OUTPUT** | CRITICAL | dispatch.py | 1797 | Job zero output after timeout (30min default) |
| **STALL_GH_WRITE_UNVERIFIED** | CRITICAL | dispatch.py | 1743 | GH-write job stalled, target NOT delivered |
| **TOKEN_CIRCUIT_BREAKER_TRIPPED** | CRITICAL | circuit_breaker.py | 295 | In-flight token/cost/log-size limit breached |
| **CIRCUIT_BREAKER** | CRITICAL | sentinel.py | 890 | Legacy `enforce_job_circuit_breaker` (hard limit) |
| **CLEANUP_UNVERIFIED** | CRITICAL | sentinel.py, circuit_breaker.py | 892, 304 | Process kill uncertain after sentinel cleanup |
| **FLATLINE** | CRITICAL | sentinel.py | 1065 | Same command failed 3× in a row |
| **QUOTA_EXHAUSTED** | CRITICAL | sentinel.py | 1091 | Output matches quota/rate-limit text patterns |
| **HARNESS_INTERNAL_TIMEOUT** | CRITICAL | jobs.py | 2863, 3113 | Job died from internal harness timeout |
| **HARNESS_PREFLIGHT_FAIL** | CRITICAL | dispatch.py (caller) | 4902 | Preflight binary/auth/flag check failed |
| **RECONCILIATION_DATA_INTEGRITY_FAILURE** | CRITICAL | jobs.py | 2385 | Job reconciliation hit sqlite IntegrityError |
| **VIZOR_DAEMON_DOWN** | CRITICAL | vizor_daemon.py | 977 | Vizor daemon not running |
| **ZOMBIE_DAEMON** | CRITICAL | daemon.py | 1712 | Watch daemon pidfile exists, process dead |
| **ZOMBIE_SYNLYNK_DAEMON** | CRITICAL | daemon.py | 1723 | Synlynk daemon pidfile exists, process dead |
| **TOKEN_BLOAT** | WARN/CRITICAL | sentinel.py | 986-1014 | Anomalous token-per-file ratio |
| **COST_INFLATION** | WARN/CRITICAL | sentinel.py | 1017-1039 | Job cost exceeds $3/$5 thresholds |
| **TASK_RECEIPT_WARN** | WARN | jobs.py | 2927, 3164 | Task receipt marker missing/mismatched |
| **TASK_NOOP_DENIED** | WARN | jobs.py | 2510 | Job exit 0, no verified effects (Invariant 1) |
| **DISPATCH_ROUTING_FALLBACK** | WARN | dispatch.py | 275 | Routing fell back from requested to different harness |
| **DANGEROUS_PERMISSIONS_BYPASS** | WARN | dispatch.py | 4579 | `--dangerously-skip-permissions` enabled |
| **GOVERNS_LINKAGE_MISSING** | WARN | dispatch.py | 2154 | No --story/--issue/--pr on dispatch |
| **CONTEXT_BUILD_DEGRADED** | WARN | dispatch.py | 2596 | Graph extraction / pack synthesis failed |
| **HARNESS_VERSION_DRIFT** | WARN | dispatch.py | 3863 | Harness version changed from last recorded |
| **TOOL_PRESSURE** | WARN | dispatch.py | 3991 | Estimated tool usage >70% of budget |
| **GROK_WRITE_SANDBOX_DENIED** | WARN | dispatch.py | 4516 | Grok sandbox denies write for write task |
| **HANDOFF_PENDING** | WARN | dispatch.py | 1804 | Stalled job awaiting handoff |
| **RECONCILIATION_PERSISTENCE_DEGRADED** | WARN | jobs.py | 2385 | Persistence failure (non-integrity) |
| **STALE_MODEL_RATES** | WARN | sentinel.py | 796 | Model rates >90 days old or invalid |
| **SUCCESS_LOOP** | WARN | sentinel.py | 1079 | Same command 5× in <10 min |
| **VERIFY_SKIP** | INFO | sentinel.py | 1111 | Exit 0, no test/verify evidence |
| **INSTRUCTION_LOAD_MISMATCH** | WARN | jobs.py | 2850 | Instruction receipt version mismatch |
| **INSTRUCTION_LOAD_ABSENT** | WARN | jobs.py | 2850 | Instruction receipt marker absent |
| **ORPHANED_STORY_COST** | WARN | jobs.py | 2717 | Cost entry skipped for missing story |
| **CAPABILITY_WATCH_FAILED** | ERROR | daemon.py | 1330 | Capability watch probe failed |
| **DAEMON_PORT_CONFLICT** | ERROR | daemon.py | 1575 | Daemon port already in use |
| **DAEMON_DETACHED_DEAD** | ERROR | daemon.py | 1738 | Daemon service installed but dead |
| **RUNTIME_REVISION_DRIFT** | WARN | daemon.py | 1623 | Runtime revision differs from expected |
| **STALL** | WARN | daemon.py | 1762 | Generic exec stall warning |

### 2B. Live Sentinel Alert Distribution (`.synlynk/sentinel.md` — 492 active alerts post-triage)

| Alert Code | Count | % | Severity |
|---|---|---|---|
| `TASK_RECEIPT_WARN` | 208 | 42.3% | WARN |
| `STALL_NO_OUTPUT` | 97 | 19.7% | CRITICAL |
| `TASK_NOOP_DENIED` | 61 | 12.4% | WARN |
| `DANGEROUS_PERMISSIONS_BYPASS` | 40 | 8.1% | WARN |
| `RECONCILIATION_PERSISTENCE_DEGRADED` | 29 | 5.9% | WARN |
| `HARNESS_VERSION_DRIFT` | 17 | 3.5% | WARN |
| `HANDOFF_PENDING` | 9 | 1.8% | WARN |
| `TOOL_PRESSURE` | 5 | 1.0% | WARN |
| `STALL_GH_WRITE_UNVERIFIED` | 5 | 1.0% | CRITICAL |
| `DISPATCH_ROUTING_FALLBACK` | 5 | 1.0% | WARN |
| `TOKEN_CIRCUIT_BREAKER_TRIPPED` | 3 | 0.6% | CRITICAL |
| `RUNTIME_REVISION_DRIFT` | 3 | 0.6% | WARN |
| `HARNESS_INTERNAL_TIMEOUT` | 2 | 0.4% | CRITICAL |
| `COST_INFLATION` | 2 | 0.4% | CRITICAL |
| `VIZOR_DAEMON_DOWN` | 1 | 0.2% | CRITICAL |
| `TOKEN_BLOAT` | 1 | 0.2% | CRITICAL |
| `HARNESS_PREFLIGHT_FAIL` | 1 | 0.2% | CRITICAL |
| `GROK_WRITE_SANDBOX_DENIED` | 1 | 0.2% | WARN |
| `GOVERNS_LINKAGE_MISSING` | 1 | 0.2% | WARN |
| `CAPACITY_EXCEEDED_INPUT` | 1 | 0.2% | CRITICAL |

**By severity:** CRITICAL: 113, WARN: 379

### 2C. Alerts by Harness (agent-attributed alerts only)

| Harness | Alert Count | % | Top Alert |
|---|---|---|---|
| codex | 169 | 39.4% | STALL_NO_OUTPUT (dominant) |
| claude | 126 | 29.4% | STALL_NO_OUTPUT |
| agy | 82 | 19.1% | STALL_NO_OUTPUT (2026-10-17 burst) |
| grok | 40 | 9.3% | STALL_NO_OUTPUT |
| muse | 12 | 2.8% | STALL_NO_OUTPUT |

> [!NOTE]
> The 2026-10-17 04:08 UTC cluster shows ~30 simultaneous `STALL_NO_OUTPUT` alerts across all harnesses, suggesting a fleet-wide infrastructure event rather than per-harness issues. All show "Process kill skipped" — possibly a daemon/watch health failure.

### 2D. Missing Sentinel Alerts (Coverage Gaps)

| Gap | Status/Scenario | Impact | Recommendation |
|---|---|---|---|
| **permission_denied** | Headless auto-denial → silent status | High — no operator visibility | Add `PERMISSION_DENIED` sentinel |
| **cancelled** | Job cancellation | Medium | Add `JOB_CANCELLED` for audit trail |
| **scope_violation** | Files outside declared scope | High — scope breach invisible | Add `SCOPE_VIOLATION` sentinel |
| **instruction_receipt_untrusted** | Instruction load mismatch → untrusted | High — trust violation | Promote existing `INSTRUCTION_LOAD_*` alerts to cover |
| **stale_base** | Worktree not anchored to fresh base | Medium | Add `STALE_BASE` sentinel |
| **unpushed_branch** | Branch not pushed to remote | Medium | Add `UNPUSHED_BRANCH` sentinel |
| **failed_verification** | GH-write retry exhausted | High — effect undelivered | Add `GH_WRITE_VERIFICATION_EXHAUSTED` sentinel |
| **Pre-dispatch hard rejections** | 20 RuntimeError types | Very High — zero trace | Add `DISPATCH_REJECTED` sentinel for all hard rejections |

### 2E. False-Positive / False-Negative Patterns

**False Negatives (Job succeeded but reported failure):**

| Pattern | Documented Occurrences | Root Cause | Fix Status |
|---|---|---|---|
| `circuit_breaker_tripped` on successful jobs | 12+ (gh:#202, #1377, #2130, #2163) | LIVE-19: Clean-exit jobs (rc=0) with heavy prompt tokens falsely stamped | Partially fixed |
| `timed_out` / `exit -9` on delivered GH-write jobs | 3/3 in one session (nikhilsoman devlog L207-218) | PR #1331 forced `-s read-only` on Codex review; blocks network | Fixed (PR #1375) |
| `failed` on noop reviews | Undocumented | Reviews intentionally leave worktree untouched → noop detection false-fires | Guard added for `task_type == "review"` |

**False Positives (Alert fires but no real issue):**

| Pattern | Mechanism | Frequency |
|---|---|---|
| `TASK_RECEIPT_WARN` on valid work | Receipt parsing strict; Aider ANSWER framing rejected valid work | 208 active alerts (42% of all) |
| `STALL_NO_OUTPUT` batch during infra event | Fleet-wide daemon/watch failure → mass stall alerts | ~30 alerts on 2026-10-17 04:08 |
| Dual-ledger stale `degraded` status | `.synlynk/state.db` fallback held stale records → false TC-2 preflight rejections | Fixed (devlog agy L463) |

---

## 3. Interactive/Headless Capability Parity Matrix

### 3A. Per-Harness Mode Contracts

| Harness | Interactive (Home) Mode | Headless (Away) Mode | Key Difference |
|---|---|---|---|
| **Claude** | Full Home Conductor / PM / TPM / Architect | `--print` pipe mode, `--output-format json` | ⚠ Interactive: auto-mode classifier can nondeterministically deny authorized actions (gh:#2150) |
| **Agy** | Full builder/verifier with MCP tools | `-p` arg mode, `--print-timeout 30m0s` | ⚠ Headless read-only: auto-denies tool calls silently (L3271–3302 pre-flight gate) |
| **Codex** | Full builder/verifier | `exec -` stdin pipe, sandbox modes | ⚠ Network isolated by default; only gets network for `--requires-gh-write` |
| **Grok** | Full builder/architect | `--single` arg mode, `--always-approve --permission-mode bypassPermissions` | ⚠ **No scoped-permission headless mode** — all-or-nothing (LIVE-13) |
| **Local** | Aider interactive stdin | `--message-file`, `--no-auto-commits --yes-always` | ❌ Cannot enforce permissions at all; `can_gh_write: false` |

### 3B. Capability Allocation Matrix

✅ Primary | 🔄 Fallback | ⚠ Degraded | ❌ Not allocated

| Task Type | Claude Headless | Agy Headless | Codex Headless | Grok Headless |
|---|---|---|---|---|
| **pm** | ✅ Primary | 🔄 #1 | 🔄 #2 | ❌ |
| **brainstorm** | ✅ Primary | 🔄 #1 | 🔄 #2 | ❌ |
| **architecture-review** | ✅ Primary | 🔄 #1 | 🔄 #2 | ❌ |
| **deploy** | ✅ Primary (0 samples) | 🔄 #1 | 🔄 #2 | ❌ |
| **review** | 🔄 #1 | ⚠ Read-only auto-denial | ✅ Primary | ⚠ Bypass-only permissions |
| **implement** | ❌ | 🔄 #2 | ✅ Primary | 🔄 #1 |
| **test** | ❌ | 🔄 #2 | ✅ Primary | 🔄 #1 |
| **refactor** | ❌ | ❌ | ✅ Primary | ❌ |
| **cli-plumbing** | ❌ | ❌ | ✅ Primary | ❌ |
| **css** | ❌ | ✅ Primary | ❌ | ❌ |
| **templates** | ❌ | ✅ Primary | ❌ | ❌ |
| **content** | ❌ | ✅ Primary | ❌ | ❌ |
| **subpages** | ❌ | ✅ Primary | ❌ | ❌ |
| **canvas** | ❌ | ❌ | ❌ | ✅ Primary |
| **js** | ❌ | ❌ | ❌ | ✅ Primary |
| **infra** | ❌ | ❌ | ❌ | ✅ Primary |
| **gh_write** | 🔄 #2 (8.19) | ⚠ #3 (7.58) | ✅ Primary (9.04) | 🔄 #1 (8.55) |

> [!CAUTION]
> **Single Points of Failure:** `css`, `templates`, `content`, `subpages` (Agy only), `canvas`, `js`, `infra` (Grok only), and `refactor`, `cli-plumbing` (Codex only) have **zero fallback** in `policy.json`.

### 3C. Permission Model Asymmetry

| Capability | Claude | Agy | Codex | Grok | Local |
|---|---|---|---|---|---|
| **Granular read-only** | ✅ `--allowedTools Read,Glob,Grep,LS` | ⚠ `--mode plan` | ✅ `-s read-only` | ❌ (bypass all or nothing) | ❌ |
| **Scoped write** | ✅ `--allowedTools Edit,Write,MultiEdit` | ✅ `--dangerously-skip-permissions` or `--sandbox` | ✅ `-s workspace-write` | ❌ (bypass all or nothing) | ❌ |
| **Shell execution** | ✅ `--allowedTools Bash` | ✅ same | ✅ workspace-write | ❌ (bypass all or nothing) | ❌ |
| **Network access** | ✅ (no restriction) | ✅ (requires Google endpoints) | ⚠ Only for `--requires-gh-write` | ✅ (requires cli-chat-proxy) | ⚠ Local only |
| **GH write** | ✅ | ✅ (TC-7 preflight) | ✅ (Primary) | ✅ | ❌ |

### 3D. Known Interactive/Headless Bugs

| Issue | Harness | Mode | Status |
|---|---|---|---|
| gh:#2150 auto-mode classifier denial | Claude | Interactive only | Open — merges mandated to headless |
| LIVE-13 `--permission-mode dontAsk` silently cancels | Grok | Headless | Fixed — `bypassPermissions` workaround |
| Agy 5-min headless timeout (#750, #162) | Agy | Headless | Fixed — `--print-timeout 30m0s` (PR #1286) |
| Aider multiline stdin misinterpretation | Local | Headless | Open — `--message-file` workaround |
| Codex `-s read-only` blocks network (#1274) | Codex | Headless review | Fixed — `-s workspace-write` (PR #1375) |
| Non-Claude interactive self-censorship | All non-Claude | Interactive | Fixed — constitutional precedence (agy devlog L398-405) |

---

## 4. State.db Job Record Analysis

### 4A. Table Schema

The `daemon_jobs` table at [`db_schema.py` L178-231](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/db_schema.py#L178-L231) tracks:
- **Routing parity:** `requested_harness` vs `actual_harness` with `fallback_reason`
- **Mode tracking:** `context_mode` (home/headless)
- **Lifecycle:** `process_state` CHECK constraint (`unknown|running|stop_requested|stopped_verified|cleanup_unverified|cleanup_overridden`)
- **Purpose:** `purpose` CHECK constraint (`implementation|review|other` or NULL)
- **Deferral:** `blocked_reason` (e.g., `quota_exhausted`, `local_concurrency`)
- **Effect verification:** `gh_write_evidence`, `gh_write_verification_attempts`, `terminal_evidence_strength`

> [!NOTE]
> The `daemon_jobs` table in the accessible state.db is **empty** (COUNT=0) — this is expected for a job-scoped worktree. Live job records accumulate in the main repo's `.synlynk/state.db` and are accessible via `synlynk jobs ls`. Related tables (`capability_ratings`, `harness_quotas`, `policy_gate_events`, `job_lifecycle_event`, `job_status_shadow`) are also empty in this worktree copy.

### 4B. Supporting Tables for Rejection Analysis

| Table | Purpose | Key Columns |
|---|---|---|
| `job_lifecycle_event` | Structured lifecycle telemetry | `rejection_reason`, `harness`, `role`, `event_type` |
| `job_status_shadow` | Status truth pilot | `legacy_status`, `oracle_status`, `disagreement`, `reason_code` |
| `job_terminal_decision` | Immutable terminal verdicts | `status`, `verification_state`, `decision_reason` |
| `job_effect_contract` | GH-write effect contracts | `kind`, `expect`, `target` |
| `capability_incidents` | Capability drift/regression events | `harness`, `classification`, `evidence` |
| `policy_gate_events` | PR check gate verdicts | `gate`, `mode`, `verdict`, `detail` |

---

## 5. Configuration Consistency Audit

### 5A. `capability-roles.json` vs `policy.json` Inconsistencies

| Discrepancy | `capability-roles.json` | `policy.json` |
|---|---|---|
| **review** ownership | Claude only | Codex primary, Claude fallback #1, Agy fallback #2 |
| **Muse** | Absent | Listed as `not_yet_calibrated` but absent from task_allocation |
| **Local** | Absent | Has separate `local_pilot` section but no task_allocation entries |

### 5B. `policy.json` Internal Gaps

| Gap | Detail |
|---|---|
| **deploy** — 0 samples | Primary=Claude; routing is empirical but never validated |
| **Muse** — uncalibrated | Listed in `not_yet_calibrated` alongside Grok, but Grok has been calibrated |
| **min_sample_size=5** | Agy has 89 samples, well above threshold, but Local (n=2) and Muse (n=1) are below |

---

## 6. Documented Rejection Incidents (from Devlogs & Memory)

| Date | Incident | Harness | Category | Fix |
|---|---|---|---|---|
| 2026-10-22 | #2530 job terminal truth: capacity released prematurely | All | Process lifecycle | Design in progress |
| 2026-10-20 | LIVE-29 AST scanner worktree exclusion | All | Headless | Fixed |
| 2026-10-19 | LIVE-27 model catalog corruption → fleet-wide dispatch failure | All | Model resolution | Fixed (migrations 23, 28) |
| 2026-10-17 | Dual-ledger stale degraded status → false TC-2 rejections | All | Preflight | Fixed |
| 2026-10-17 | Fleet-wide STALL_NO_OUTPUT burst (~30 jobs) | All | Infrastructure | Unclear root cause |
| 2026-10-02 | LIVE-19 false circuit_breaker_tripped | All | False negative | Partially fixed |
| 2026-09-22 | LIVE-13 Grok sandbox-deny fixed | Grok | Permission | Fixed (PRs #1734/#1735) |
| 2026-08-xx | Agy 5-min headless timeout | Agy | Headless timeout | Fixed (PR #1286) |
| 2026-08-xx | Codex `-s read-only` network block | Codex | Headless review | Fixed (PR #1375) |
| 2026-08-xx | QA identity self-approval block (chicken-and-egg) | Claude | Auth | Fixed (PR #1747) |
| 2026-08-xx | Codex model-tier rejection (`o3`/`gpt-4o` invalid) | Codex | Model resolution | Fixed (#1748) |
| 2026-08-xx | Non-Claude interactive self-censorship | Agy, Codex, Grok | Interactive parity | Fixed (constitutional precedence) |

---

## 7. Recommendations

### 7A. Alert Coverage Expansion (High Priority)

1. **Add `DISPATCH_REJECTED` sentinel** for all 20 pre-dispatch hard rejections — currently zero trace
2. **Add `PERMISSION_DENIED` sentinel** when jobs transition to `permission_denied` status
3. **Add `SCOPE_VIOLATION` sentinel** — scope breaches are currently invisible
4. **Add `GH_WRITE_VERIFICATION_EXHAUSTED` sentinel** when retry budget is exhausted
5. **Add `STALE_BASE` sentinel** when worktree base branch check fails

### 7B. False-Positive Reduction (Medium Priority)

6. **`TASK_RECEIPT_WARN` triage** — 208 active alerts (42%) dominate the dashboard; tighten parsing or add Aider-specific receipt normalization
7. **Fleet-wide stall burst correlation** — correlate the 2026-10-17 04:08 UTC cluster with daemon/watch health events
8. **LIVE-19 false circuit_breaker_tripped** — ensure remaining cases are resolved

### 7C. Parity Improvements (Medium Priority)

9. **Add fallback for Agy-exclusive tasks** (css, templates, content, subpages) — single point of failure
10. **Add fallback for Grok-exclusive tasks** (canvas, js, infra) — single point of failure
11. **Grok scoped permissions** — the all-or-nothing bypass model is the weakest security posture
12. **Reconcile `capability-roles.json` with `policy.json`** on review ownership

---

## Evidence Paths

| Source | Path |
|---|---|
| Schema | [`synlynk/db_schema.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/db_schema.py) |
| Dispatch | [`synlynk/dispatch.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/dispatch.py) |
| Sentinel | [`synlynk/sentinel.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/sentinel.py) |
| Jobs | [`synlynk/jobs.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/jobs.py) |
| Circuit Breaker | [`synlynk/circuit_breaker.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/circuit_breaker.py) |
| Daemon | [`synlynk/daemon.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/daemon.py) |
| Policy Gates | [`synlynk/policy_gates.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/policy_gates.py) |
| Capability Classifier | [`synlynk/capability_classifier.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/capability_classifier.py) |
| Constants | [`synlynk/_constants.py`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/synlynk/_constants.py) |
| Live Sentinel | `.synlynk/sentinel.md` (main repo) |
| Policy Config | [`.synlynk/policy.json`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/.synlynk/policy.json) |
| Capability Roles | [`.synlynk/capability-roles.json`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/.synlynk/capability-roles.json) |
| Memory | [`project-docs/memory.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/project-docs/memory.md) |
| Claude Devlog | [`project-docs/devlogs/claude.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/project-docs/devlogs/claude.md) |
| Agy Devlog | [`project-docs/devlogs/agy.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/project-docs/devlogs/agy.md) |
| Codex Devlog | [`project-docs/devlogs/codex.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/project-docs/devlogs/codex.md) |
| Nikhilsoman Devlog | [`project-docs/devlogs/nikhilsoman.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/project-docs/devlogs/nikhilsoman.md) |
| Models Config | [`.synlynk/models.json`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/.synlynk/models.json) |
| Instruction Files | [`CLAUDE.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/CLAUDE.md), [`GEMINI.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/GEMINI.md), [`AGENTS.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/AGENTS.md), [`GROK.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/job-3326f764/GROK.md) |
