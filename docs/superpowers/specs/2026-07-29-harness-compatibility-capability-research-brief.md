# Harness Compatibility & Capability — Research Brief
## Pre-Brainstorm Research Document

**Date:** 2026-07-29
**Author:** Claude (PM)
**Status:** Research complete — not yet brainstormed, not a design spec
**GOVERNS goal:** "Harness compatibility & capability" — `goal-6ebfe9b5` (see §7)
**Trigger:** A live dispatch incident — an Agy job ran ~72 minutes, took one 3-second turn, hit a shell "command" permission wall headless mode couldn't prompt for, was silently auto-denied, and gave up with nothing produced. A parallel Codex incident (sandbox blocking `gh` auth / Docker) surfaced the same class of gap on a different agent.

---

## 0. Why this brief exists

Nikhil asked for a deep research pass across four topics plus adjacent ones, expanding into a full audit of `synlynk doctor`, `synlynk selftest`, and environment discovery — headful vs. headless, per harness (Claude, Agy, Codex, Grok). Before scoping a brainstorm, I surveyed the repo for prior art. **Conclusion: this is not a greenfield problem.** There is substantial shipped infrastructure (`synlynk/doctor.py`, `synlynk/selftest.py`, `synlynk/probe.py`, `AGENT_CAPABILITY_BASELINES`) and a trail of specs that already named this exact failure class (BS-14, gh-write-capability-routing, agent-github-identity). What's missing is not discovery machinery — it's **closing the loop from discovered gap → automatic or human-escalated remediation**, and **doing it per-harness instead of per-incident**. That reframing should anchor the brainstorm.

---

## 1. Research thread: environment discovery deep dive

**Shipped today:**
- `synlynk/doctor.py` — `HEALTH_CHECKS` (10 static checks: python version, project init, docs dir, identity key/roles/file-perms, agent profiles via `_hc_agent_profiles`, instruction-file presence via `_hc_instruction_files`, model-rate freshness, version currency).
- `synlynk/probe.py` — dynamic per-harness discovery: version fingerprint → baseline lookup → live TC1–TC5 checks (headless-stdout contract, flag compliance, network reachability, verb-map/binary availability, SOP-section presence) against `AGENT_CAPABILITY_BASELINES`.
- Config discovery is read-only and per-harness inconsistent: Claude reads `~/.claude/settings.json` (`probe.py:809`); Codex reads `~/.codex/config.toml` (model fingerprint only); **Agy and Grok have no equivalent discovery path** for their local settings files.

**Gaps to research further:**
- Discovery finds *whether* a capability exists, but not *whether the local machine-level config grants it* — the Agy incident is exactly this: `~/.gemini/antigravity-cli/settings.json` allow-rules are known to exist as a concept (documented in `probe.py:58,61` SOP text) but there is no code path that reads, verifies, or writes them.
- No equivalent "settings.json" has been located for Codex. Its sandbox posture (`workspace-write`, network egress blocked to `api.github.com`) is fixed at invocation time (`-s workspace-write` in `AGENT_CAPABILITY_BASELINES["codex"]`) with an explicit comment warning against `--dangerously-bypass-approvals-and-sandbox` (full host access) — meaning there may be no narrower whitelist mechanism to discover, only a binary sandboxed/unsandboxed choice. **This needs a Codex-docs literature check, not just a repo grep** — first task for the brainstorm's research phase.
- Grok has no discovery path at all in `probe.py`/`dispatch.py` — it inherits Claude's harness instructions (per Nikhil's note), which explains why it *works* today, but means synlynk has no independent signal on Grok's actual local capability posture; that inheritance is assumed, not verified.

---

## 2. Research thread: harness capability discovery & testing — periodic review

**Shipped today:** TC1–TC5 live probes exist and run via `synlynk doctor`. Baselines live in `AGENT_CAPABILITY_BASELINES` (`synlynk/_constants.py`).

**Known holes (already filed, not yet fixed):**
- **#339** — doctor TC-1/2/3/5 silently no-op due to a baseline schema inconsistency. Two PRs in flight (**#578**, **#580**) fixing this now — the periodic-review mechanism has been broken and is only now being repaired.
- **#112 / #213** — dispatch does not preflight TC-2/TC-4 before handing work to an agent, and vendor probes "never run in CI" — meaning the periodic-review cadence has no automated trigger; it's manual (`synlynk doctor` invocation) rather than scheduled or CI-gated.
- No cadence policy exists yet (daily? per-release? on harness-version-bump?) for re-running probes as vendor CLIs update. Harness self-updates (Codex, Agy, Claude Code all ship silently) can invalidate a baseline without synlynk noticing until a job fails.

---

## 3. Research thread: third-party tool recognition/interop discovery (GitHub, Docker, skills, MCP)

**Partially covered, narrowly:**
- GitHub write-action capability is the most mature sub-case here, via `synlynk probe`'s SOP text and **#426** / the 2026-07-21 `gh-write-capability-routing-design.md` spec (routes GitHub writes to Grok by default, `--requires-gh-write` flag).
- Docker and MCP discovery from repo artifacts: **not found anywhere in the codebase.** No grep hit for Docker sandbox detection, MCP server enumeration, or skills-catalog cross-referencing as a *discovery* input (as opposed to synlynk's own use of skills). This is a genuine gap, not a shipped-and-hidden feature.
- "Discovery from repo artifacts" (e.g., detecting a `.mcp.json`, `docker-compose.yml`, `.github/workflows/*` and inferring what a harness will need access to before dispatch) is not implemented — today's discovery is harness-introspection only (probe the CLI), not repo-introspection (probe the job's actual requirements).

**This is a good candidate for a distinct sub-topic** in the brainstorm: discovery should arguably run in both directions — "what can this harness do" (shipped) and "what will this job need" (missing) — and gate dispatch on the intersection.

---

## 4. Research thread: feature/command adherence per harness, headful vs. headless

**Shipped:** TC2 (flag compliance via `--help` scrape) and the command-taxonomy/trigger-registry design (`2026-07-17-command-taxonomy-and-trigger-registry-design.md`, approved but not yet planned/implemented) are the closest existing coverage.

**Gap — this is the core of the reported incident class:**
- `_permissions_to_flags` (`synlynk/dispatch.py:148-173`) is the single chokepoint translating synlynk's internal permission grants into actual CLI flags, and it is **inconsistent per agent today**:
  - **agy**: fixed by PR #417/#475 (was the unconditional-empty-list bug reported in the incident — already resolved on `main`, contrary to what the live incident log suggested; worth confirming the incident job ran against a stale binary/deploy).
  - **claude**: maps through `_PERMISSION_TO_TOOL_MAP` into `--allowedTools` — the most complete mapping.
  - **codex**: binary only (`--approval-policy untrusted` or nothing) — no fine-grained tool-level mapping exists or is possible given the sandbox model.
  - **grok**: falls through to `return []` — permissions computed by `_resolve_dispatch_permissions` are never translated into a Grok flag at all. This is the same *class* of bug the Agy incident found, still live, just not yet triggered into a visible failure (possibly because Grok inherits Claude's instructions and rarely needs fine-grained grants).
- **#338** names this directly: "role-based permission/grants system is a no-op for Agy, Grok, and Local dispatch" — filed, open, unscoped to a PR yet.
- **#419** — permission-denied jobs are misclassified as OK in telemetry. This means the exact failure mode from the incident (job runs, does nothing, silently denied) may not even be visible in `synlynk status`/cost tracking today — a monitoring gap layered on top of the permission gap.
- Headful vs. headless is not a variable synlynk currently models explicitly anywhere in `dispatch.py` or `probe.py` — TC1's "headless-stdout contract" check is the closest, but there's no discovery of *what changes* about a harness's tool-permission behavior between interactive/headful and dispatched/headless invocation (which is precisely where the Agy incident's gap lived: the CLI's permission gate exists and works headful, but "cannot prompt" headless and silently denies instead of erroring loud).

---

## 5. Suggested adjacent topics (not in the original four, but load-bearing)

1. **Config write-back / auto-remediation, not just discovery.** Every mechanism found above is read-only. When doctor/probe finds a gap (e.g., Agy's settings.json missing an allow-rule), nothing writes the fix. Given Nikhil's ask to "fix this and maintain it autonomously in the long run," this is probably the single most important adjacent topic — discovery without remediation just produces better-labeled failures.
2. **Failure-mode classification & alerting for permission/sandbox denials specifically.** #419 (permission-denied misclassified as OK) means this class of failure is currently invisible in telemetry. A silently-denied-then-idle job and a genuinely-successful-but-quiet job look the same today. Needs its own signal, not folded into generic FLATLINE/stall detection.
3. **Preflight gating at dispatch time, not just periodic review.** #112/#213/#332 — TC2/TC4 aren't checked before a job is handed to an agent. A goal here should probably require: no dispatch to a harness whose last probe is stale or failing for the specific capability the job needs.
4. **Instruction-file hygiene / cross-contamination.** #344 — GEMINI.md leaking a Codex-only flag into Agy's harness contract. If synlynk generates/merges instruction files across harnesses, drift between them is itself a capability-adherence bug, distinct from the runtime permission gap but caused by the same "per-harness config is under-modeled" root issue.
5. **GitHub identity infrastructure.** #423 / `2026-07-23-agent-github-identity-design.md` — shared `nikhilsoman` identity across all dispatched agents means even a capability-correct agent (Grok) fails self-approval structurally. This is adjacent, already has its own spec in flight, and should be referenced/linked from the new goal rather than re-scoped under it.
6. **CI parity for vendor probes.** Probes "never run in CI" per #112/#213 — meaning capability regressions from vendor CLI updates are only caught live, in production dispatch, which is exactly how the Agy and Codex incidents were discovered. Moving probe execution into CI (or a scheduled job) is a maintenance-cadence topic distinct from the probes' content.
7. **Dogfooding gap.** #343 — synlynk's own repo is missing `AGENTS.md` at root, meaning Codex dispatches against synlynk's own codebase are missing the exact instruction file the whole system is meant to guarantee. Cheap, concrete, and a good canary for whether the eventual fix actually self-applies.
8. **Escalation path when auto-remediation isn't possible.** Some gaps (Agy's settings.json) require a human to run an interactive approval once, locally, before headless dispatch can work — this can't be automated away. The goal needs an explicit "detected, cannot self-fix, notify operator with the exact remediation step" path, not just pass/fail probe output.

---

## 6. Consolidated gap map (by root cause, not by symptom)

| Root cause | Evidence | Status |
|---|---|---|
| Permission grants computed but not wired to CLI flags, per-agent inconsistent | dispatch.py:148-173; #338 | Agy fixed (#417/#475); Codex structurally limited; **Grok still a no-op** |
| Local machine-level harness config (settings.json equivalents) is invisible to synlynk | probe.py:58,61 SOP text only, no code | Not started — no read or write path for Agy/Codex-equivalent config |
| No repo-artifact-driven discovery of job requirements (Docker/MCP/GH) | grep: no hits | Not started |
| Probe/doctor results not gating dispatch | #112, #213, #332 | Not started |
| Permission-denied failures invisible in telemetry | #419 | Not started |
| No remediation write-back when a gap is found | all of the above | Not started — this is the load-bearing missing piece |
| Baseline schema drift breaking TC1/2/3/5 silently | #339 | **In flight** (#578, #580) |
| Instruction-file cross-contamination between harnesses | #344 | Filed, open |
| Shared GitHub identity blocks self-approval | #423, agent-github-identity-design.md | **Spec'd, separate track — link, don't duplicate** |
| No CI cadence for probe re-runs | #112, #213 | Not started |
| synlynk's own repo missing AGENTS.md | #343 | Filed, open, trivial |

---

## 7. GOVERNS goal framing

Per the Business Goal layer (BS-8, `synlynk goal` — implemented in `synlynk/db.py`), this should be filed as:

- **Outcome:** Every dispatched harness (Claude, Agy, Codex, Grok) either succeeds at a granted capability headless, or fails loud with a specific, operator-actionable remediation step — never silently idles or gets misreported as OK.
- **Criterion:** Zero permission/sandbox-caused silent-idle dispatch failures over a trailing 30-day window, measured via corrected telemetry classification (closing #419).
- **Deadline:** Ongoing (Sustain-lane goal, not a single-release Dream) — this is exactly the kind of cross-cutting operational goal the Business Goal layer was designed for, distinct from version-arc feature work.
- Filed as `goal-6ebfe9b5` via `synlynk goal create`.
- Existing Dreams/epics that should link under it as secondary contributions (not re-parented): the in-flight #578/#580 (doctor baseline parity), #426/gh-write-capability-routing, #423/agent-github-identity — these stay on their own tracks but should carry a `goal_contributions` link to the new goal per the BS-8 data model.

---

## 8. Proposed brainstorm scope (for the next session)

Recommend the brainstorm focus on **§5.1 (remediation/write-back) and §5.3 (preflight gating)** as the primary design questions — those are the two gaps with no existing spec at all, versus most of the discovery/detection machinery which is either shipped or already has an owner. Suggested opening questions:

1. For each harness, is remediation even possible without a human in the loop (Agy's settings.json needs one-time interactive approval) — and if not, what does the "detected but can't self-fix, escalate to operator" UX look like in `synlynk status`/HUD?
2. Should preflight gating block dispatch outright on a stale/failing probe, or dispatch with a downgraded capability set and let the job fail fast? (Trade-off: false-positive blocking vs. wasted 72-minute idle jobs like the incident.)
3. Where does repo-artifact-driven discovery (Docker/MCP/GH requirements of *this job*) intersect with harness-capability discovery (what *this agent* can do) — one probe pass or two independent signals gated together at dispatch time?
4. Is Grok's "inherits Claude's harness instructions" behavior something to formalize (explicit fallback-to-Claude-profile mechanism) or something to close (give Grok its own real profile)?

---

## Appendix: source citations

Full detail behind every claim above is in the Explore-agent research pass that produced this brief (doctor.py:302-341, selftest.py:1226, dispatch.py:63,130,148-173,1104-1144, probe.py:58-796, _constants.py:52-65). Issues referenced: #112, #162, #213, #332, #338, #339, #340, #343, #344, #419, #423, #426, #569, #577, #578, #580, #581. Specs referenced: BS-8 harness-capability-awareness-loop-dispatch (2026-06-27), BS-14 harness-compatibility (2026-06-30), capability-matrix-hardening (2026-07-11), capability-sweep-taxonomy (2026-07-18), command-taxonomy-and-trigger-registry (2026-07-17), live-command-selftest (2026-07-17, shipped as PR #328 + follow-ons), dispatch-job-comms-fence (2026-07-17), gh-write-capability-routing (2026-07-21), agent-github-identity (2026-07-23), governs-lifecycle-engagement (2026-07-23).
