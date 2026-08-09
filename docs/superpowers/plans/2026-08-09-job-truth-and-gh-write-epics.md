# Epic plan: Job-status/cost truth + GH-write identity

**Date:** 2026-08-09  
**Status:** Plan only — implement after #832 (fresh `--base`)  
**Inputs:** Open-bug cluster review (40 bugs); nightly ops GREEN after reap/windowed sentinel

---

## Epic A — Job lifecycle + cost *completeness* (not pricing)

**Do not** implement as one mega-PR with GH-write or rate formulas.

### Scope map

| Root | Issues | Goal |
|------|--------|------|
| **A1 Status truth** | #701 (status half), #579, #331 | Terminal status matches process + git reality |
| **A2 Cost completeness** | #752 (+ #481/#329 surfaces later) | Every finished job that spent tokens has a cost row (or explicit `cost_missing`) |
| **A3 Analytics dims** | #740 | Real home vs headless on `dispatch_context` |
| **Out of epic A** | #787, #510 | Pricing *meaning* (flat-rate vs metered) — Epic C later |

### Already shipped (do not re-do)

- #753 `jobs reap` + auto-reap STALL/TIMEOUT  
- #751 windowed `sentinel_crit`  
- #835 context_mode/bytes (if merged)

### Sequence

1. **A1.1** — On STALL/TIMEOUT/exit: always write terminal status + summary (harden remaining paths #579/#331 GTV).  
2. **A1.2** — Ops finding: `running` + dead PID (should be 0 if #753 healthy).  
3. **A2.1** — Ops finding: jobs in window with no `cost_entries` (#752).  
4. **A2.2** — Close write gaps (which agents/paths skip `update_costs`).  
5. **A3** — Set `dispatch_context` to `home`|`headless` at enqueue/dispatch (#740).

### Exit criteria

- Hand-verify git less often: `synlynk jobs` / summaries trustworthy for done vs failed.  
- Nightly: fail_rate not dominated by zombies; cost total tracks job activity.  
- Can split success rate home vs headless.

### PR sizing

- PR A1: status GTV (tests with fake dead PID + files touched).  
- PR A2: cost completeness detect + fix top missing path.  
- PR A3: home/headless column fill.

**Retitle #701** body to point here and exclude GH-write (link Epic B).

---

## Epic B — GitHub-write identity under dispatch

**Process today is correct (route to Grok/Agy); product is not.**

### Scope map

| Layer | Issues | Goal |
|-------|--------|------|
| **B1 Identity** | #569, #426 | Role-scoped token injected for `--requires-gh-write`; no silent personal keyring |
| **B2 Sandbox** | #577 (Codex) | Hard-block or real allowlist; no silent fail |
| **B3 MCP/review** | #659, #714 | After B1; reduce cancel/flake |

### Sequence

1. **B1 design** — `synlynk identity` / App installation: per-role token, env for child only.  
2. **B1 implement** — When token present, set `GH_TOKEN` for job; when absent, **fail preflight** for GH-write (no strip-and-hope).  
3. **B2** — Codex: document permanent no-GH-write + route, or fix sandbox.  
4. **B3** — MCP review reliability with real identity.

### Exit criteria

- Dispatched review/merge jobs succeed without human `gh` from laptop.  
- `--requires-gh-write` without App token → hard fail with install instructions.  
- CLAUDE.md routing becomes backup, not primary control.

### PR sizing

- PR B0: design doc + preflight fail-closed without token.  
- PR B1: App token provisioning + injection.  
- PR B2/B3: children.

---

## Epic C — Cost *pricing* accuracy (later)

#787, #510, #382 — after A2 complete. Separate from “did we log.”

---

## Suggested calendar (indicative)

| Week | Focus |
|------|--------|
| 0 | **#832** fresh `--base` (this plan’s companion PR) |
| 1 | Epic A1 status GTV |
| 1–2 | Epic B0/B1 identity design + fail-closed |
| 2 | A2 cost completeness |
| 3 | A3 home/headless; B2/B3 as needed |
| later | Epic C rates |

---

## Standing process (until B1)

- GH-write → Grok/Agy; never assume Codex headless GH.  
- #423 COMMENT approve on shared identity.  
- Prefer verifying job outcome against git until A1 done.
