# Design: Full-Fleet Operability (Home + Headless Truth Gate)

**Date:** 2026-08-02  
**Status:** Approved — implementation plan `docs/superpowers/plans/2026-08-02-fleet-operability.md`  
**Brainstorm agenda:** `docs/brainstorm/fleet-operability/2026-08-02-agenda.md`  
**Decide panel:** `project-docs/decisions/2026-08-02-fleet-operability-deep-survey.md` (`dec-2f979483`)  
**Visuals:** `docs/brainstorm/fleet-operability/visuals/`  
**Companion session:** `.superpowers/brainstorm/51904-1785661849/` (local)

---

## 1. Problem

synlynk’s long-standing product claim is dual operability:

1. **Home harness** — a user can run synlynk from inside any supported interactive CLI (Claude / Codex / Agy / Grok / Aider).
2. **Headless fleet** — from any home, synlynk can reliably dispatch work to the other harnesses.

A multi-agent decide panel (2026-08-02) was **unanimous**: this is **not completely supported today**. The shared root cause is **completion theater / false-greens** — doctor, status, and job summaries report presence and exit codes without verified round-trips. Related open issues include #112, #330, #332, #338, #340, #342, #347, #426, #577, #579, #648 (partially mitigated).

We will not “fix fleet parity” as scattershot stories. We will define **Supported / Proven**, ship a **live-capable audit matrix**, fail-close truth signals, then invest in side-effects (GH-write + grants) only with matrix acceptance.

---

## 2. Goals

1. Define enforceable tiers: **Supported**, **Proven**, **Experimental**.
2. Ship `synlynk selftest --matrix` as the fleet truth gate (dry in CI; live budget-capped).
3. Fail-close doctor, state.db, and job completion signals so “green” is falsifiable.
4. Align product claims with a **Core 4** fleet (local out until green; codex builder-only until proven).
5. Sequence later work: GH-write + grants for Core 4 → native-harness go/no-go after first Proven week.

### Non-goals (this design)

- Implementing a native synlynk harness (strategy deferred).
- Implementing full GH-write or grants in Phase 1–2 (sequencing only; Phase 3 epic).
- Promoting `local` to Core without open + TC-1 + TC-3 + dry matrix green.
- Exhaustive per-issue fixes for every open harness bug (matrix will surface them as red cells).

---

## 3. Product model

### 3.1 Tiers

| Tier | Meaning | Enforced by |
|------|---------|-------------|
| **Supported** | Agent is Core 4; fail-closed doctor green; dry matrix green for required cells | `doctor` non-zero on FAIL; dry matrix in CI |
| **Proven** | Supported + live matrix cell green within **7 days** | `fleet_matrix_runs` freshness; `status` labels |
| **Experimental** | Not Core 4 (today: `local`) | Omitted from default `open` / `dispatch` help |

Docs, help text, and status UI **must never claim a higher tier than measured**.

### 3.2 Core fleet

| Agent | Membership | Claim limits |
|-------|------------|--------------|
| claude | Core 4 | Full home + headless (subject to matrix) |
| agy | Core 4 | Full home + headless; GH-write **not Proven** until Phase 3 |
| codex | Core 4 | **Builder-only** until TC-2 / #577 / #340 cells Proven — no claims for GH-write, package-install, or network-heavy sandbox |
| grok | Core 4 | Full home + headless (subject to matrix) |
| local (aider) | Experimental | Not in `synlynk open` / dispatch help until open allowlist + TC-1 + TC-3 + dry matrix green |

### 3.3 Hard freeze

Until **Phase 1** (S1–S3) merges:

- **Blocked:** new “fleet parity / harness compatibility” feature PRs.
- **Allowed:** stop-the-line bugs (broken dispatch, data loss, security, hard TC-2 crash).

After Phase 1, fleet freeze lifts for unrelated work; fleet-parity features still require dry matrix green in CI.

---

## 4. Matrix runner

### 4.1 CLI

```text
synlynk selftest --matrix
synlynk selftest --matrix --live
synlynk selftest --matrix --live --budget 10
```

| Mode | Behaviour |
|------|-----------|
| Default / CI | **Dry** only — no model API spend |
| `--live` | Tier-2 live cells; hard budget stop (default **$10** per weekly window) |
| Mid-budget abort | Remaining cells marked incomplete (not green) |

### 4.2 Grid

- **Rows (home):** claude, agy, codex, grok  
- **Dry columns:** status, doctor, dispatch-dry, jobs, logs, pr-check (contract), cost (schema/read), story list  
- **Live columns:** trivial headless dispatch to each Core 4 target  

### 4.3 Tiers

| Tier | Name | Phase | Cost |
|------|------|-------|------|
| 1 | Dry / contract | Phase 1 (S3) | Free |
| 2 | Live trivial | Phase 2 (S4) | ≤ $10/week |
| 3 | Live git-only | Future (not in S1–S4) | Budget TBD at plan time |
| 4 | Live GH-write | Phase 3 epic | Budget TBD with GH-write plan |

### 4.4 Storage

New table `fleet_matrix_runs` in the **canonical** project `state.db`:

| Column | Purpose |
|--------|---------|
| run_id | Run identity |
| tier | 1–4 |
| home | Home harness |
| cell | Verb or target key |
| status | green / red / incomplete / na |
| detail | Short machine-readable reason |
| cost_usd | Live cell cost |
| ts | Timestamp |

Proven freshness: last green live cell `ts` within 7 days for that home×target (or home×verb as defined per cell type).

### 4.5 Cell assertions

A cell is **red** if any apply:

- Non-zero process exit where success was required  
- Terminal job status is UNKNOWN (or equivalent ambiguous)  
- Missing instruction file for the agent under test  
- Nested product `state.db` under `worktrees/`  
- Live cell without cost ledger evidence (or explicit zero-cost marker)  
- Argv / flag contract mismatch (dry)

**N/A (not red):** Codex GH-write / package-install cells while builder-only label is active.

---

## 5. Truth signals

### 5.1 Doctor severity

| Check | Severity |
|-------|----------|
| Missing instruction file for a Core 4 agent | **FAIL** |
| Nested worktree product `state.db` | **FAIL** |
| TC-2 flag failures | **FAIL** |
| TC-3 required endpoint unreachable | **FAIL** |
| CLI version skew vs baseline | WARN |
| TC-5 SOP missing sections | WARN |

Any FAIL ⇒ doctor non-zero exit ⇒ agent not Supported.

### 5.2 Canonical state.db

- Product ledger path remains `~/.synlynk/projects/<key>/state.db` (key = MD5 of git-common-dir root).  
- **Refuse** creating/using a nested product ledger under job worktrees (error, not silent success).  
- #650 fallback to empty local DB when `$HOME` is unwritable: keep warn + local empty DB; **not** Proven ledger; doctor may still FAIL if stale nested files exist from old jobs.

### 5.3 Completion / UNKNOWN (#579)

- `jobs` and completion banners **never** show UNKNOWN as final status.  
- In-flight: “reconciling…”.  
- After reconciliation timeout: `FAILED_UNVERIFIED` + reason.  
- Matrix live requires reconciled terminal (OK or FAILED_*), never UNKNOWN.  
- Keep existing guard: do not overwrite a terminal summary with empty/ambiguous reconciler writes.

### 5.4 Dispatch preflight (#112)

- Dispatch to a Core 4 target: if doctor FAIL for that agent → **block** unless `--force-agent` (explicit warning).

---

## 6. Architecture (Phase 1–2)

```
synlynk selftest --matrix [--live]
        │
        ├─► dry cells ──► baselines + doctor TCs + fs checks ──► fleet_matrix_runs
        │
        └─► live cells ──► dispatch_agent (trivial) ──► reconcile job
                              │                              │
                              └─ budget remaining? ──► stop ─┘
        │
        ▼
synlynk status ── reads last green ts ── Supported / Proven labels
synlynk doctor ── FAIL-closed checks ── non-zero if unsupported
```

No new network services. Extends existing selftest + doctor + jobs reconciliation.

---

## 7. Implementation phases (≤5 stories)

### Phase 1 — Truth gate MVP (hard freeze)

| ID | Story | Outcome |
|----|--------|---------|
| **S1** | Doctor fail-closed + Core 4 / local help alignment | FAIL on instruction, nested DB, TC-2, TC-3; help lists Core 4 only |
| **S2** | State refuse + UNKNOWN ban | Nested product ledger errors; jobs never terminal UNKNOWN |
| **S3** | `selftest --matrix` dry + storage + status labels | CI can run dry matrix; Supported labels dry-only |

### Phase 2 — Live proof

| ID | Story | Outcome |
|----|--------|---------|
| **S4** | `--live` matrix + $10/week budget + Proven freshness | Weekly/manual live; Proven ≤7d |

### Phase 3 — Later epic (new design/plan)

| ID | Story | Outcome |
|----|--------|---------|
| **S5** | Core 4 GH-write + grants | After first Proven week; matrix is acceptance gate |

Then: **native harness go/no-go** brainstorm (not a story in this backlog).

---

## 8. Testing strategy

| Layer | Coverage |
|-------|----------|
| Unit | Doctor severity classification; nested DB detection; UNKNOWN→FAILED_UNVERIFIED; matrix cell status rules; budget abort |
| Integration | Dry matrix full green on fixture repo; live matrix with mocked agent subprocesses |
| Live (ops) | Manual/weekly `selftest --matrix --live` with real CLIs, budget 10 |

---

## 9. Decisions log (brainstorm)

| # | Decision |
|---|----------|
| D1 | Tiered Supported / Proven (not binary CLI-on-PATH) |
| D2 | Proven freshness = 7 days |
| D3 | Core 4 product claim; local experimental until green |
| D4 | Hard freeze until matrix Phase 1 lands |
| D5 | Runner = `synlynk selftest --matrix` |
| D6 | Live budget = $10/week |
| D7 | Codex builder-only until relevant cells Proven |
| D8 | Doctor FAIL set: instruction, nested DB, TC-2, TC-3 |
| D9 | Ban UNKNOWN as terminal display |
| D10 | Nested product state.db = hard refuse |
| D11 | Invest in full Core 4 GH-write (not permanent claude/grok-only) |
| D12 | Implement grants for all Core 4 (Phase 3) |
| D13 | Order: matrix → GH-write+grants → native go/no-go |
| D14 | Defer native go/no-go until first Proven week |
| D15 | One operability spec, phased stories |

---

## 10. Open questions for plan author (not blockers)

1. Exact schema DDL placement (`synlynk/db.py` migrations vs `_migrate_db` in `__init__.py`) — follow existing table patterns.  
2. Whether dry matrix runs in default `selftest` (no flags) or only with `--matrix` (recommend **only `--matrix`** to keep default selftest fast).  
3. Weekly live trigger: docs-only vs cron/daemon hook (Phase 2 plan may choose docs-only first).

---

## 11. Success criteria

This design is successful when:

1. CI runs dry matrix and fails on Core 4 contract regressions.  
2. Doctor FAIL set matches §5.1; Core 4 help no longer lists local as peer.  
3. UNKNOWN is never a terminal job display.  
4. Nested product state.db cannot silently become the ledger.  
5. After S4, `status` can show Proven for cells green within 7 days.  
6. No new fleet-parity feature merges without matrix-backed claims.

---

## 12. References

- Agenda: `docs/brainstorm/fleet-operability/2026-08-02-agenda.md`  
- Decide record: `project-docs/decisions/2026-08-02-fleet-operability-deep-survey.md`  
- Strategy (deferred): `docs/strategy/synlynk-as-a-harness.md`  
- Prior harness work: `docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md`  
- Issues: #112 #330 #332 #338 #340 #342 #347 #426 #577 #579 #648  
