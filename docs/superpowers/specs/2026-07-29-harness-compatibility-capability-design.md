# Harness Compatibility & Capability — Design Spec

**Status: DRAFT — pending Nikhil review, not approved.**

**Date:** 2026-07-29
**Author:** Claude (PM), produced headless via `synlynk dispatch` in non-interactive mode
**GOVERNS goal:** `goal-6ebfe9b5` — "Every dispatched harness either succeeds at a granted capability headless, or fails loud with a specific, operator-actionable remediation step"
**Input:** `docs/superpowers/specs/2026-07-29-harness-compatibility-capability-research-brief.md`
**Process note:** This spec was produced without the interactive brainstorming loop (no Visual Companion offer, no one-at-a-time clarifying questions, no live approval gate) per explicit dispatch instructions — this is itself a dispatched job with no human available mid-session. Assumptions are stated inline and collected in §7. Two prior dispatch attempts at this exact task failed for reasons documented in §6 (case study) — this attempt follows the corrected headless-safe procedure from the second attempt.

---

## 1. Problem framing (carried from the brief)

Per the brief, this is not a discovery-machinery gap — `doctor.py`, `probe.py`, and `AGENT_CAPABILITY_BASELINES` already do a reasonable job of finding out what a harness *can* do. The gap is that **nothing closes the loop**: when a gap is found, there is no write-back, no dispatch-time gate, and one harness (Grok) doesn't even translate computed permissions into anything at all. This design covers the two gaps the brief identifies as having no existing spec — remediation/write-back and preflight gating — plus two adjacent questions the brief flagged as needing an explicit decision (Grok's no-op, and repo-artifact-driven discovery).

**Explicitly out of scope** (linked as related, not re-scoped here):
- **#423 / agent-github-identity-design.md** — shared GitHub identity blocking self-approval. Separate track, already spec'd.
- **#339 / #578 / #580** — baseline schema drift breaking TC1/2/3/5. In flight on its own PRs; this design assumes that work lands and probe results become reliable again, but does not re-litigate it.
- **#344** (instruction-file cross-contamination) and **#343** (missing root AGENTS.md) — noted in the brief as adjacent but not part of this design's four focus questions.

---

## 2. Design questions and recommendations

### 2a. Remediation / write-back when a capability gap is detected

The concrete targets are now confirmed (correcting the brief's uncertainty about whether Codex has any narrower write-back target than a binary sandboxed/unsandboxed switch):

- **Agy**: `~/.gemini/antigravity-cli/settings.json` — allow-rule list, referenced today only as SOP text in `probe.py:58,61`, never read or written by code.
- **Codex**: `~/.codex/config.toml` `[sandbox_workspace_write]` table, with `network_access` (bool) and `writable_roots` (array) keys. This is a real, narrower target — not merely the `-s workspace-write` / `--dangerously-bypass-approvals-and-sandbox` binary choice the brief initially assumed. `probe.py` already has a working pattern for scoped TOML reads (`_read_toml_string_value`, used for the `model` key at `probe.py:794-798`); it needs a write-side counterpart and a table-aware (not just top-level-key) read.

**Options:**

1. **Fully automatic write-back.** Probe detects a gap and writes the fix immediately, no confirmation. Fastest path to "self-healing," but a synlynk process autonomously widening its own sandbox/permission boundary (e.g. adding a `writable_roots` entry or an Agy allow-rule) with no human ever having approved that specific scope is a security regression, not a fix — it recreates exactly the kind of silent, unaccountable permission change the goal is trying to eliminate on the other side.
2. **Propose-and-apply with an explicit confirm step.** synlynk computes the exact diff (JSON patch for Agy's settings.json, TOML table patch for Codex's config.toml), shows it via `synlynk doctor --fix <agent>`, and only writes when the operator passes `--yes` (or confirms in an interactive session). Nothing is ever written silently; every write has a human-reviewed diff behind it, once.
3. **Detect-and-escalate only, no write path at all.** synlynk never touches another tool's config file; it only emits the exact remediation snippet (the JSON/TOML block to paste) for the operator to apply by hand.

**Recommendation: Option 2**, uniformly across Agy and Codex. Reasoning: these are both security-boundary files (permission allow-rules, sandbox writable roots / network access), not cosmetic config — Option 1's "just fix it" is the wrong default for boundary-widening changes even in a system whose explicit goal is more autonomy, because the failure mode of a bad auto-write (agent given broader access than intended, silently) is worse than the failure mode this goal is trying to close (agent denied and idle, loudly reported). Option 3 is strictly worse than Option 2 for zero additional safety — a computed, reviewable diff costs nothing over a remediation snippet and removes a manual transcription step that is itself an error source. `--fix` becomes the single write-back entry point for both harnesses; the diff format differs (JSON merge-patch vs. TOML table patch) but the confirm-then-write contract is identical.

Narrowing/repair changes (e.g., restoring a baseline-schema-conformant value that drifted due to #339-class bugs, not a scope change) could in principle be auto-applied without confirmation, but this design does not special-case that distinction — it adds a second code path for a marginal win and the brief did not surface evidence that repair-vs-widen misclassification is itself a live risk. If it becomes one, split it out as a follow-up.

### 2b. Preflight gating at dispatch time

**Options:**

1. **Hard block.** Dispatch refuses outright if the relevant probe result is stale or failing for the capability the job's role requires.
2. **Degrade-and-fail-fast.** Dispatch proceeds with a reduced capability set; if the job then hits a real denial, it should fail within its first turn (not the incident's 72 minutes), and be classified correctly (closing #419) rather than reported as OK.
3. **Warn-and-proceed.** Print an operator-visible warning but dispatch with the full requested permission set regardless — closest to current behavior, just louder.

**Recommendation: none of these alone — branch on *why* the probe result is unusable**, because "stale" and "failing" are different failure classes with different correct responses:

- **Stale** (probe result older than a cadence threshold, or the harness binary/version fingerprint has changed since the last probe) → **re-probe synchronously before dispatch.** TC1-5 are fast, targeted checks; paying that cost once at dispatch time is far cheaper than a 72-minute idle job, and it turns "we don't know" into a fresh, trustworthy "yes/no" before deciding whether to block.
- **Actively failing** for the specific capability the job's role requires (e.g. job needs `write:github`, the last probe shows GitHub-write capability broken for this harness) → **hard block (Option 1).** This is the direct fix for the reported incident class: instead of a 3-second wasted turn followed by 72 minutes of silence, dispatch never starts and the operator gets the exact remediation step from §2a inline in the block message.
- **No probe coverage exists at all** for the capability class in question (today's actual state for Grok's permission-to-flag translation — there's nothing to be stale or failing, it was never wired) → **degrade-and-fail-fast (Option 2)**, with the job explicitly tagged `UNVERIFIED_CAPABILITY` in telemetry so that if it fails, #419's corrected classification catches it as a real denial rather than a false OK.

This is a three-way branch, not a single policy, because collapsing it into "always block" would false-positive-block on cheap-to-refresh staleness, and collapsing it into "always degrade" would keep shipping the exact 72-minute-idle failure mode for known-broken capabilities that a synchronous check would have caught immediately.

### 2c. Grok's permission no-op (#338) vs. formalizing instruction-inheritance

**Options:**

1. **Give Grok its own real flag mapping** in `_permissions_to_flags`, mirroring the Claude/Codex treatment.
2. **Formalize the inheritance fallback explicitly** — document that Grok relies on Claude-authored harness instructions rather than CLI flags for permission enforcement, and change `_permissions_to_flags`'s Grok branch from a silent `return []` to a return value that signals "enforced via instruction-inheritance, not flags" so downstream code (and telemetry) can tell the difference between "no permissions needed" and "no flag mechanism exists."
3. **Hybrid:** do (2) now, and file a separate, narrowly-scoped research ticket to determine whether Grok's CLI actually exposes any permission/sandbox flags at all (the brief confirms this has never been investigated — `probe.py`/`dispatch.py` have zero Grok-specific discovery today).

**Recommendation: Option 3.** Jumping straight to Option 1 would mean building a flag-translation layer against a CLI surface nobody has confirmed exists — the brief is explicit that "Grok has no discovery path at all," so its actual flag surface is an open question, not a known gap to close. Option 2 alone is the safe, honest fix for the *silent* part of the no-op (turns an invisible `[]` into a documented, telemetry-visible fallback) but leaves the underlying question — does Grok have real flags we're just not using? — unanswered indefinitely. The hybrid closes the "silent no-op is indistinguishable from success" bug immediately (this is the same *class* of bug the Agy incident found, per the brief, just not yet triggered) while deferring the "build Grok's real mapping" work to a scoped follow-up that starts with the missing research, not a guess.

### 2d. Repo-artifact-driven job-requirement discovery as a second probe pass

**Options:**

1. **Single unified pass** — fold repo-artifact scanning (Docker, MCP, GH requirements of *this* job) into the same `doctor`/`probe` invocation that does harness-capability discovery.
2. **Two independent passes, gated together at dispatch time** — harness-capability probing stays as-is (periodic, cached, a property of the agent's local environment); a new lightweight repo-artifact scan runs per-job at dispatch time against the specific target repo, and dispatch gates on the logical AND of both signals.
3. **Defer entirely** — separate future spec, no design commitment here.

**Recommendation: Option 2.** Harness capability (what can this agent do) and job requirements (what does this repo need) vary on different timescales and different keys — harness capability is slow-changing and per-agent (cacheable across many jobs, expensive to re-probe since it invokes the CLI); repo requirements are per-job and per-repo (must be freshly evaluated every dispatch, since a repo can gain a `docker-compose.yml` or `.mcp.json` between one job and the next, and re-scanning repo artifacts is cheap — file existence checks, no subprocess). Merging them into one pass forces a bad tradeoff: either re-run the expensive harness probe on every dispatch (wasteful) or let repo-artifact data go stale between dispatches (defeats the purpose). This also matches the codebase's existing separation of concerns — `doctor` as periodic environment health, `dispatch` as per-job orchestration — rather than introducing a new hybrid concept.

This is scoped as: **a new lightweight scan function** (name TBD in the implementation plan, e.g. `_scan_repo_requirements(repo_path)`) that checks for `docker-compose.yml`/`Dockerfile`, `.mcp.json`, and `.github/workflows/*` presence, returning a requirement set (`{"docker", "mcp", "gh-actions"}` or similar) — gated against the harness's probed capabilities at dispatch time, same block/degrade logic as §2b applied to the intersection.

---

## 3. Architecture

```
                    ┌─────────────────────────┐
                    │  synlynk doctor --fix   │   (2a: write-back)
                    │  <agent>                │
                    │  - compute diff          │
                    │  - show diff             │
                    │  - write on --yes only   │
                    └───────────┬─────────────┘
                                │ writes
                    ┌───────────▼─────────────┐
        reads       │ ~/.gemini/.../settings  │
   ┌────────────────│ .json (Agy)             │
   │                │ ~/.codex/config.toml    │
   │                │ [sandbox_workspace_write]│
   │                │ (Codex)                 │
   │                └─────────────────────────┘
   │
┌──▼──────────────┐      ┌──────────────────────┐
│ probe.py         │      │ _scan_repo_requirements│  (2d: new)
│ TC1-5 + config   │      │ (repo_path) → set      │
│ discovery        │      └──────────┬───────────┘
└──────┬───────────┘                 │
       │ capability result           │ requirement set
       │ (fresh / stale / failing /  │
       │  no-coverage)                │
       ▼                              ▼
┌─────────────────────────────────────────────┐
│ dispatch.py: preflight gate (2b)             │
│  stale      → re-probe sync, then re-check   │
│  failing    → hard block, emit remediation   │
│  no-coverage→ dispatch, tag UNVERIFIED_CAPABILITY (2c: Grok) │
│  gate on AND(harness-capable, repo-requires)  │
└──────────────────┬────────────────────────────┘
                    │
             ┌──────▼──────┐
             │ job runs, or │
             │ blocked with │
             │ remediation  │
             └─────────────┘
```

---

## 4. Data flow

1. **At dispatch time**, `dispatch_agent()` calls `_resolve_dispatch_permissions()` (unchanged) then, before spawning the subprocess, calls a new preflight step:
   - Look up the harness's last probe result and its age.
   - Run `_scan_repo_requirements(cwd)` against the target repo.
   - Apply the §2b three-way branch per required capability.
2. **On block**, the dispatch call returns a structured failure (not a spawned job) carrying the exact remediation step — for Agy/Codex config gaps, this is literally "run `synlynk doctor --fix <agent>` and review the diff."
3. **On degrade**, the job is tagged `UNVERIFIED_CAPABILITY` in the telemetry record at spawn time (new field, additive to the existing telemetry schema — no migration needed since telemetry already tolerates missing/added keys per its rolling-100-entries JSON log).
4. **`synlynk doctor --fix <agent>`** is a separate, operator-invoked command (never auto-triggered by dispatch) that reads the current gap (from the last probe run), computes the diff against the target config file, prints it, and writes only when `--yes` is passed.

---

## 5. Error handling / escalation UX

Per the brief's §5.8, some gaps genuinely cannot be closed by a file write — e.g. if Agy's headless mode itself has no allow-rule concept for a given permission at all (not just "not yet granted" but "not expressible"), or if a Codex sandbox restriction is enforced above the config-file layer. For these:

- The preflight block message must distinguish **"fixable — run `synlynk doctor --fix`"** from **"not self-fixable — operator must do X interactively once"** (e.g., Agy's settings.json is confirmed to support this case: an operator must have already confirmed scoped allow-rules once locally, per the existing SOP text in `probe.py:58,61`, before headless dispatch can work at all — this design's `--fix` writes the file, but the *first* Agy job to actually exercise a newly-granted permission may still need a one-time interactive confirmation inside Agy itself, outside synlynk's control).
- This is exactly the shape of both case-study incidents below: a process assumed a human would be available to respond to something, headless mode had no way to satisfy that, and the original failure was silent/slow rather than an immediate, specific "here's what a human needs to do" message.

---

## 6. Case study: this dispatch's own predecessors as evidence

Both prior attempts at running *this exact brainstorm dispatch* independently reproduced the class of failure this goal targets, giving direct, first-party evidence for §5.8's escalation-path argument:

- **job-a58018b8** — hit `PERMISSION_DENIED` because the brainstorming skill's Visual Companion offer and its one-at-a-time clarifying-question loop are both designed around an interactive human being present to respond. In headless dispatch, there was no one to respond, and the job blocked waiting for a reply that could never come. This is functionally identical to the Agy incident that motivated the whole goal: a permission/interaction gate that works correctly headful silently (or in this case, not-so-silently — but still unproductively) fails headless instead of either succeeding or failing loud with a specific remediation ("run this in an interactive session, not via dispatch"). It is supporting evidence for exactly the escalation-path gap named in the brief's §5.8: the correct behavior here isn't auto-remediation (a dispatched job cannot consent to a Visual Companion or answer clarifying questions on a human's behalf) but a fast, specific, operator-actionable failure — which the first attempt did not produce.
- **job-3b0fb176** — corrected the interactive-loop problem (skipped Visual Companion, stated assumptions inline, skipped the approval-wait loop) and got all the way through research, including independently confirming the Codex `config.toml` `[sandbox_workspace_write]` correction folded into §2a of this spec — but then failed on a transient "API Error: Connection closed mid-response" while writing the spec. This is **not** a capability/permission gap in the sense this goal targets (it's an infra/connection reliability blip, not a discovered-but-unhandled permission wall) — noted here only as a caveat: closing the headless-adherence gap (which job-3b0fb176 did correctly) does not by itself guarantee a dispatched job completes; execution-reliability tail risk is a separate, orthogonal concern this design does not attempt to address.

This attempt (job-a7eb31f5) follows job-3b0fb176's corrected procedure directly.

---

## 7. Open Questions for Nikhil

Because this spec was produced without a live clarifying-question loop, the following are assumptions made inline above, flagged here for explicit confirmation or correction:

1. **§2a scope-widening confirmation UX**: assumed CLI-flag confirmation (`--yes`) is sufficient for both Agy and Codex write-backs, with no additional audit trail requirement. If these config writes should also be logged somewhere durable (e.g. a remediation-actions log distinct from telemetry), that's an addition to scope.
2. **§2b staleness threshold**: no cadence number is proposed here (the brief's §2 also flags "no cadence policy exists yet" as an open gap). This design assumes a re-probe-on-stale policy but does not pick a number of days / version-bump trigger — that belongs in the implementation plan, but Nikhil should confirm the *policy* (re-probe on stale, don't just block) before it's picked.
3. **§2c Grok research ticket**: assumed this should be filed as a new, separate, narrowly-scoped issue (not folded into this goal's implementation plan) once this spec is approved — confirm that's the right sequencing rather than including a Grok-flag-discovery research task directly in this design's plan.
4. **§2d scan scope**: assumed Docker/MCP/GH-Actions file-presence checks are sufficient for a first version of `_scan_repo_requirements` (no deeper content inspection, e.g. parsing `.mcp.json` for which specific MCP servers are declared). Confirm whether presence-only is enough for v1 or whether the gate needs to be requirement-specific from the start.
5. **Telemetry schema change** (`UNVERIFIED_CAPABILITY` tag): assumed additive/backward-compatible given telemetry already tolerates schema drift across its rolling 100-entry log; not verified against #419's in-flight fix for classification, since that issue's own resolution approach wasn't read in detail here — worth cross-checking before implementation to avoid two changes fighting over the same telemetry field.

---

## Appendix: related, not re-scoped here

- #423 / `2026-07-23-agent-github-identity-design.md` — shared GitHub identity / self-approval structural gap.
- #339, #578, #580 — doctor baseline schema drift (assumed resolved as a prerequisite, not re-litigated).
- #344 — instruction-file cross-contamination between harness instruction files.
- #343 — synlynk's own repo missing root `AGENTS.md`.
- #419 — permission-denied telemetry misclassification (this design's `UNVERIFIED_CAPABILITY` tag interacts with it; see Open Question 5).
- #112 / #213 / #332 — no CI cadence for probe re-runs (this design's preflight re-probe-on-stale is dispatch-time, not CI-scheduled; CI cadence remains a separate, unaddressed gap).
