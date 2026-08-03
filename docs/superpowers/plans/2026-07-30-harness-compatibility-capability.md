# Harness Compatibility & Capability — Implementation Plan

**Status:** APPROVED spec, plan ready for dispatch.
**Spec:** `docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md` (PR #587, approved 2026-07-30)
**GOVERNS goal:** `goal-6ebfe9b5`
**Canon data source:** `docs/reference/harness-capability-matrix.md` — recheck before implementing any per-harness detail; it is the ground truth, not this plan's paraphrase of it.

---

## 0. Blocking-dependency check (do this before Phase 4 or 4b — not optional)

The spec hard-gates two things on external issues. Checked at plan-authoring time (2026-07-30):

| Dependency | Status (2026-07-30) | What it blocks |
|---|---|---|
| **#339** (baseline schema inconsistency) | **Closed** 2026-07-29 | — |
| **#578** (fix for #339, TC1/2/3/5) | **Open, unmerged** (`fix: Fix issue #339...`) | §2b/§4's "stale" and "actively failing" preflight branches |
| **#580** (follow-up correction to #578) | **Open, unmerged** | Same as above |
| **#419** (permission-denial telemetry misclassification) | **Open, no fix yet** | `UNVERIFIED_CAPABILITY` telemetry tag (§4 point 3) |

**Consequence for this plan, not just a footnote:** #578/#580 are unmerged right now. Per spec §1/§4, this means the preflight gate must **not** trust any literal TC1-5 pass/fail value today — every capability check must route through the "no-coverage" branch (§2b) regardless of what a stale/buggy probe result claims. Phase 4 below is scoped accordingly: build the full four-way branch structure, but the stale/failing branches are dead code paths (present, tested, but effectively unreachable) until #578/#580 land. Re-check #578/#580 status immediately before wiring Phase 4 into `dispatch_agent()` — if they've merged by then, un-gate the stale/failing branches as part of that same PR.

**#419 is a hard block on `UNVERIFIED_CAPABILITY`, not a soft one.** It has no fix yet, so its eventual taxonomy is unknown. Phase 4b (the tag itself) is not scheduled in this pass — it's tracked as a follow-up, gated on #419 landing first. Do not preemptively add the field "to be safe"; that's exactly the second-competing-top-level-field risk the spec calls out.

---

## 1. Phases

Each phase is one PR, one branch, one dispatch. Branch names follow `fix/<phase-slug>` or `feat/<phase-slug>` per repo convention. All are Python/CLI/tests work in `synlynk/` — routed to **Codex** per the Capability-Based Task Allocation table, except GitHub-write actions on each PR (review/merge), which route to **Grok only** per the GitHub write routing SOP.

### Phase 1 — Codex baseline fix: `--ask-for-approval`, not the legacy Codex approval-flag name
**Why first:** zero-risk, self-contained bugfix already fully specified by the canon doc; no dependency on anything else in this plan.
- File: `synlynk/_constants.py`, `AGENT_CAPABILITY_BASELINES` Codex entry.
- Change the approval-flag name and its enum values (`untrusted|on-request|never`) to match `docs/reference/harness-capability-matrix.md`'s Codex section.
- Grep the codebase for any other legacy Codex approval-flag references (dispatch.py flag construction, tests, docs) and fix those too — this was a baseline-data error, likely propagated wherever Codex approval flags are constructed.
- Test: unit test asserting the constructed Codex CLI args use `--ask-for-approval`, not the old flag.
- Dispatch: Codex, `--force-agent`, context-mode full.

### Phase 2 — Grok flag mapping in `_permissions_to_flags` (§2c)
**Why:** independent of the dependency-gated work; closes the actual `_permissions_to_flags` `[]` fallthrough that #338 and the spec's canon self-review both confirmed is real.
- File: `synlynk/dispatch.py`, `_permissions_to_flags`'s Grok branch.
- Map permission role → `--allow`/`--deny` and `--permission-mode`, per the flag surface confirmed in the canon doc's Grok section. Reserve `--yolo`/always-approve for genuinely broad grants, not the default per-job case (spec §2c recommendation).
- Do **not** touch `~/.grok/config.toml` in this phase — that's reserved for durable project-policy config, a separate concern from per-job dispatch-time flags (spec §2c, §2a).
- Test: unit tests covering each permission role → flag mapping, plus a regression test that the old unconditional `[]` fallthrough is gone.
- Dispatch: Codex.

### Phase 3 — Remediation audit log (§2a foundation)
**Why:** a hard prerequisite for Phase 4's `doctor --fix`, since every `--yes`-confirmed write must append to this log per the mandatory-audit-logging amendment.
- New append-only log — `.synlynk/remediation-log.json` or a `remediation_actions` table (match whatever storage pattern PR #542's DB-canonical state engine already established for `costs`/`memory`, don't reinvent a third pattern if the DB path is available), distinct from the rolling 100-entry telemetry log so entries are never pruned.
- Fields: timestamp, agent, target file, exact diff applied, operator who confirmed (or "non-interactive `--yes`" if headless).
- Write path only — no read/reporting UI in this phase (that's a natural fast-follow, not spec-required).
- Test: write an entry, assert it persists and isn't subject to the 100-entry rolling cap.
- Dispatch: Codex.

### Phase 4 — `synlynk doctor --fix agy` (§2a, Agy only)
**Why Agy only, not Codex too:** the spec explicitly blocks the Codex `config.toml` `[sandbox_workspace_write]` write-back path pending independent schema verification (§2a) — implementing it now would ship a write-back mechanism against an unconfirmed target. Agy's target (`~/.gemini/antigravity-cli/settings.json`) is confirmed.
- Depends on: Phase 3 (audit log).
- New `synlynk doctor --fix agy` subcommand: computes the exact JSON patch against `~/.gemini/antigravity-cli/settings.json` for the detected gap, prints the diff, writes only on `--yes` (or interactive confirm), appends to the Phase 3 audit log on every write regardless of interactive vs. headless confirmation.
- Runs pre-dispatch as a separate operator-invoked step, never auto-triggered by `dispatch_agent()` itself (spec §2a: Agy's remediation is pre-flight manifest seeding, not a runtime prompt).
- Explicitly out of scope for this phase: Codex's write-back (tracked as its own follow-up ticket, blocked on independently verifying `config.toml`'s actual schema — not just `--help` output); Claude's runtime propose-and-apply loop (Claude's failure mode is a loud, same-run error, so its remediation flow is a different shape — scope as a later phase if Nikhil wants it in this pass, not assumed here).
- Test: diff computation against a fixture `settings.json`, write-on-`--yes` behavior, audit log entry created on write.
- Dispatch: Codex.

### Phase 5 — `_scan_repo_requirements` (§2d)
**Why:** independent of the dependency-gated preflight work; can be built and tested standalone, then wired into Phase 6.
- New function in `probe.py` or `dispatch.py` (spec leaves exact home TBD — put it in `probe.py` alongside existing discovery functions, since it's a discovery primitive, not a dispatch-time decision): `_scan_repo_requirements(repo_path)` → returns a requirement set, e.g. `{"docker", "mcp", "gh-actions"}`, from presence checks only (`docker-compose.yml`/`Dockerfile`, `.mcp.json`, `.github/workflows/*`).
- **v1 is presence-only, never semantically blocking on its own** (spec amendment) — this function returns a signal, it does not make a block/degrade decision itself; that logic lives in Phase 6.
- Test: fixture repos with/without each artifact type, assert correct requirement set returned.
- Dispatch: Codex.

### Phase 6 — Preflight gate (§2b/§4)
**Why last among the core phases:** integrates Phases 3-5 and is where the #578/#580 gating from §0 actually matters.
- Depends on: Phase 3 (remediation log, for the block message's "run `doctor --fix`" pointer), Phase 5 (`_scan_repo_requirements`).
- New preflight step called from `dispatch_agent()` in `synlynk/dispatch.py`, before subprocess spawn:
  1. Look up the harness's last probe result and age.
  2. **Per §0: since #578/#580 are unmerged as of this plan, treat every probe result as no-coverage regardless of its literal value.** Structure the code so this is a single, obvious conditional (e.g. a `_probe_results_trustworthy()` gate) that flips cleanly once #578/#580 merge — not scattered special-casing.
  3. Run `_scan_repo_requirements(cwd)` (Phase 5).
  4. Determine required-vs-optional per capability from the job's role/dispatch declaration.
  5. Apply the four-way branch: stale → re-probe sync, timeout=fail (dead path until #578/#580 land, but implement and test it now so it's ready); failing → hard block (same); no-coverage+required → hard block (live path today); no-coverage+optional → degrade — **but do not add the `UNVERIFIED_CAPABILITY` tag yet (Phase 4b, blocked on #419)**; log/return the degrade decision without a telemetry field until that lands.
  6. Apply §2d's presence-vs-declared split for repo-artifact requirements: presence alone → degrade/tag only, never hard-block; hard-block reserved for a job that explicitly declares the need.
- **Declared-need mechanism (§7 open question #1, needs a decision here):** add a generic `--requires <capability>` dispatch flag (e.g. `--requires docker`, `--requires gh-write` — note `--requires-gh-write` already exists per #426's routing hint, so this may just be generalizing that existing pattern rather than inventing a new one; check `dispatch.py`'s existing flag before adding a parallel mechanism). Recommend this over role-inference for v1: explicit is auditable, inferred-from-role is another layer of "what does this job actually need" guessing this whole goal exists to eliminate.
- On block: structured failure (not a spawned job) with the exact remediation step from §2a inline (e.g. "run `synlynk doctor --fix agy` and review the diff").
- Test: one test per branch of the four-way split, one for the repo-artifact presence-vs-declared split, one confirming the #578/#580 gate gives no-coverage behavior in the current repo state.
- Dispatch: Codex.

### Phase 4b (tracked, not scheduled) — `UNVERIFIED_CAPABILITY` telemetry tag
**Blocked on #419.** Do not implement until #419's classification fix lands and its taxonomy is known. When it does: confirm with a direct read of #419's actual fix whether `UNVERIFIED_CAPABILITY` should be a value within #419's taxonomy or (only if #419 turns out unrelated) an additive telemetry field. File as a follow-up issue referencing this plan and spec §4 point 3 rather than letting it become an untracked TODO.

### Phase 7 (fast-follow, not core to the goal) — `synlynk/team.py:329` timeout configurability
Spec §7 open question #2. Make the hardcoded 120s `_run_agent_sync` timeout in `synlynk decide`'s panel query configurable (per-agent override, since Codex specifically needs more headroom for non-trivial prompts — canon doc: ~44K tokens / several minutes for a 5-section self-review). Low complexity, no dependency on Phases 1-6; can run any time, including in parallel with them.
- Dispatch: Codex.

---

## 2. Sequencing summary

```
Phase 1 (Codex flag fix)  ─┐
Phase 2 (Grok mapping)     ├─ independent, dispatch in parallel
Phase 7 (team.py timeout)  ─┘

Phase 3 (audit log) ──> Phase 4 (doctor --fix agy)

Phase 5 (repo scan) ──┐
                       ├──> Phase 6 (preflight gate, wires 3+5)
Phase 3 (audit log) ───┘        (also needs §0 dependency re-check
                                  immediately before merge)

Phase 4b — blocked on #419, tracked as follow-up, not dispatched now.
```

Phases 1, 2, and 7 have no dependencies on each other or on anything else — dispatch all three immediately and in parallel. Phase 3 must land before Phases 4 and 6. Phase 5 can run in parallel with Phase 3/4. Phase 6 is the integration point and should be the last core phase dispatched, with a fresh check of #578/#580's merge status immediately before it starts (not at plan-authoring time — this document will be stale on that specific fact by the time Phase 6 is reached).

## 3. PR / review discipline for this work

Every phase gets its own PR, one feature per branch (`fix/codex-approval-flag`, `feat/grok-flag-mapping`, `feat/remediation-audit-log`, `feat/doctor-fix-agy`, `feat/repo-requirement-scan`, `feat/dispatch-preflight-gate`, `chore/team-py-timeout-config`). Per PR Review Discipline: a non-authoring agent reviews and runs `synlynk pr check <pr#>`; GitHub write actions (review/merge) route to Grok per the GH write routing SOP, since Codex will be the author on most of these. Blog post per PR, in-branch, per the Blog Post Protocol — same as this design/planning pair got. Cost-log any native PM review work same as this session did for PR #587.

## 4. What this plan deliberately does not schedule

- Claude's own runtime propose-and-apply remediation flow (§2a) — Claude's failure mode is a loud, same-run error, and the spec treats it as "fits as-is," but no code phase above builds it. If Nikhil wants it built now rather than relying on the existing loud-error behavior being sufficient, add a Phase 4c.
- Codex's `config.toml` write-back — blocked on independent schema verification, not scheduled.
- Richer §2d requirement inference (parsing `.mcp.json` contents, distinguishing Docker-touching from Docker-needing jobs) — explicitly deferred in the spec to a follow-up once presence-only data shows the distinction matters.
- CI-scheduled probe re-runs (#112/#213/#332) — spec's Appendix notes this stays a separate, unaddressed gap; this plan's preflight re-probe is dispatch-time only.
