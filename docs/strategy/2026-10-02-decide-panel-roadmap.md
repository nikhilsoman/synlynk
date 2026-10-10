# Decide-Panel Synthesis: Architecture Roadmap, Surface Simplification, Broader Issues

Date: 2026-10-02
Input: [`docs/strategy/2026-10-02-five-pov-review.md`](./2026-10-02-five-pov-review.md)
Method: three `synlynk decide --panel claude,codex --record` panel runs, one per deliverable below. Each panel member (Claude, Codex) independently analyzed the relevant section(s) of the five-POV review and gave a 200–400 word position; a synthesis pass reconciled disagreements into one decision. Full per-member responses and synthesis text are preserved in the session record; this document carries the synthesized output plus editorial tightening for a single consolidated artifact.

**Process note:** the first panel run's `--record` output was silently overwritten by the second and third runs — all three topics shared an identical first-40-character prefix (`"Review docs/strategy/2026-10-02-five-...`), and `cmd_decide`'s slug generation (`project-docs/decisions/<date>-<40-char-slug>.md`) has no collision detection. Only the third run's decision record survived on disk; the first two were recovered from this session's captured stdout rather than from the written files. This is itself a new instance of the repo's known write-through blind-overwrite bug class (see `[[feedback_cost_log_regenerates_costs_md]]`) and is filed below as its own issue rather than silently worked around.

**Fidelity-patch note (2026-10-02, follow-up to the PR this doc first shipped in):** the first synthesis pass compressed the panel's raw per-harness responses more aggressively than it should have — three architecture items present in the original per-harness answers (a `HarnessAdapter` plugin registry for third-party harnesses, a CI release-version gate, and an explicit cold-start performance budget) were dropped entirely, and two more (the `dispatch_agent` pipeline shape, and containerized execution for untrusted harnesses) lost their specifics. This revision restores them from the session's captured per-harness output rather than re-running the panel.

---

## 1. Consolidated Architecture Roadmap (fastest practical execution)

Source: Architect POV (§2 of the five-POV review) — `dispatch.py` god-function, `viz.py` god-module, cost/token extraction fragility, write-through regen bugs, worktree proliferation, `state.db` scaling, CLI surface size.

| # | Item | Effort | Depends on | Risk if deferred |
|---|---|---|---|---|
| 1 | **State + worktree GC** — `synlynk gc`, a size budget, and a worktree retention policy (relates to #1831) | S | none | Medium–high. `state.db` shards and stale worktrees (97+ observed in this repo today) grow silently with no bound. |
| 2 | **Regen-bug guard** — diff `costs.md`/`memory.md`/decision-record slugs against `origin/main` (or existing files) before writing, plus round-trip tests | S | none — ship alongside #1 in one PR | High. Data loss has already happened three times this session alone (costs.md x2, memory.md x1, decision-record slug collision x1). |
| 3 | **Structured telemetry as the completion oracle** — adopt `--output-format json` for Claude/Codex dispatch, keep stdout-scraping only as a fallback, and feed `verify_effects` from structured data | S–M | land #2 first (touches the same cost-ledger write path) | High. Stdout scraping is the root cause of the recurring false-status / sentinel-pattern incidents (#1377, #1826). |
| 4 | **Split `viz.py` into a domain-scoped package**, consuming the existing `status --json` seam | M | none — runs in parallel with the rest | Low today; rises as the module keeps growing (11.6K lines). |
| 5 | **`dispatch_agent` decomposition** — rebuild it as a pipeline (`resolve → authorize → prepare_worktree → spawn → observe → finalize`) around a typed `DispatchRequest` dataclass that replaces the current ~1000-line/27-parameter function's kwargs. Define a `HarnessAdapter` protocol — one class per harness implementing `build_cmd()`, `parse_events()` (structured), `permissions()`, `detect_quota()`, and `models()` — and move every `if agent == "claude"/"codex"/"agy"/"grok"` branch into an adapter, loaded via a plugin registry so third-party harnesses (OpenCode, Aider, Goose) can be added without further branching. Write characterization tests first. | M–L | #3, plus characterization tests before any refactor | Medium. Every future dispatch change gets slower and riskier the longer this is deferred, but nothing is actively broken. |
| 6 | **Safe-by-default execution** — flip `--dangerously-skip-permissions` from implicit default to an explicit opt-in, default to scoped permission profiles, and run untrusted or third-party harnesses inside containers (the existing `Dockerfile.sovereign` work is a starting point, not yet wired into dispatch). The CLI-default flip overlaps with the broader-issues plan's opt-in-permissions fix (§3) — land that flag change once, from whichever PR gets there first; this row additionally covers the containerization piece, which §3 does not. | S–M (flag default) / M (containerized execution) | none | Medium–high. Unsafe-by-default execution is a credible launch-blocking trust objection (see §3) independent of any architecture concern. |
| 7 | **`state.db` consolidation** — single workspace-owner DB, DAO + unit-of-work transactions, migrations; SQLite canonical, Markdown becomes a verified generated export (not a second source of truth) | L | #2 and #5 | Medium. Lock-cascade risk (per the #1205 32-minute CI incident) persists until this lands. |
| 8 | **CLI core/packs split** — target a core of roughly 15 commands (`init`, `dispatch`, `jobs`, `logs`, `review`, `merge`, `status`, `cost`, `route`, `local`, `doctor`, …) at an estimated 15–20K LOC, moving Vizor, marketing, media, mesh, relay, release-marketing, and swarm out into optional packs/plugins (155-command taxonomy → small core + packs) | L | #4, #5, usage telemetry, and a product decision | Medium, as ongoing maintenance drag — not urgent, and overlaps with the simplification plan in §2 below. |
| 9 | **CI release gate** — make `release --check-docs` a required CI check rather than a manual pre-release step, and generate the version from one single source of truth instead of three independently-edited files | S | none | Medium. Version drift has already happened live — `VERSION`, the README badge, and the CHANGELOG currently disagree (#1914) — and recurs silently without an enforced gate. |
| 10 | **Performance** — lazy-import per command (building on the existing `_lazy`/`_FAST_CLI` start), benchmark cold start, and set an explicit budget, e.g. <150ms for `jobs` and `status` | S–M | none — runs in parallel with the rest | Low–medium today; rises as the core/packs split (#8) adds more import surface to manage. |

**Sequencing decision:** Ship #1+#2 together as one PR first — they stop active data loss and unbounded disk growth with the least risk. #3 follows immediately after (shares the cost-ledger write path with #2). #4, #9, and #10 all run in parallel at any point — none of the three has a dependency on, or blocks, anything else in this list, so land them opportunistically alongside whichever other PR is already open. #6's permission-default flip is cheap and should land early in parallel too (it shares a CLI flag change with the broader-issues plan); its containerization half can wait. #5 is gated on #3 plus characterization tests, since it is the single riskiest change in the list. #7 and #8 wait until the seams from #3–#6 exist; #8 additionally needs real usage data, which the metrics in §2 below start collecting. Per the locked role split, implementation of #1–#10 routes to Codex/Grok via `synlynk dispatch`; Claude's role is PM/review/deploy only.

---

## 2. Surface Simplification Plan (no capability removed or changed)

Source: Developer POV (§1) + Architect POV CLI-surface commentary (§2) — ~155 commands in `synlynk/taxonomy.py`, multi-file `init` footprint, dispatch-flag complexity, role/harness concept overload.

**Principle both panelists converged on:** add a facade over the existing surface; remove nothing. The panel flagged its own evidence gap — neither member re-verified the 155-command count or current taxonomy tiers against the live file before answering, so re-confirming both is step 0 below.

### Where the panel agreed
- A **tiered `--help`** built directly from the existing `COMMAND_TAXONOMY` (`help` shows a short core list; `help --all` and `help <group>` show the rest) — pure read-side change, zero behavior change.
- A **guided first-run path** that detects installed harnesses, asks at most one question, and ends in a verified first dispatch.
- **Smart defaults for `dispatch`** (role, harness, worktree, permission profile inferred from task text/`policy.json`/story), with flags remaining the full override path — nothing stops working.
- **Docs reorganized by user journey**, with the command reference auto-generated from the taxonomy (never hand-maintained) plus a short role-vs-harness glossary.
- **Capture before/after metrics** before any change merges, not after.

### Where they differed, and the resolution
| Issue | Claude's position | Codex's position | Resolution |
|---|---|---|---|
| Entry command name | `start` | `quickstart` | Ship `quickstart`, alias `start` (check both against `COMMAND_TAXONOMY` for collisions first) |
| New group verbs (`work`/`review`/`setup`/`admin`) | not proposed | aliases over existing commands | Defer — tiered help likely captures most of the benefit with zero new naming surface; revisit only if metrics show it's insufficient |
| Dispatch inference UX | one-line preview (`→ dev/codex, worktree X`) | `--advanced`/interactive prompt | Use the one-line preview — cheapest, and it teaches the role-vs-harness split by example; add `--advanced` only if the preview proves insufficient |
| Role/harness concept | one sentence everywhere, harness detail only under `--verbose` | a glossary | Do both |

### Phased plan
1. **Baseline, before any merge.** Timestamped dogfood onboarding runs; count explicit flags used across recent real `dispatch` invocations.
2. **Tiered help.** Core tier ≈ 8 commands: `init`/`quickstart`, `dispatch`, `status`, `jobs`, `decide`, `pr check`, `exec`, `doctor`. Then Workflow tier, then Advanced/Admin tier. Every existing invocation keeps working unchanged.
3. **`synlynk quickstart`** (aliased `start`) — writes a manifest pointing to the generated instruction files, so a new user isn't handed all of them unexplained on day 1.
4. **Dispatch defaults + preview** — infer role/harness/worktree/permission profile, show the one-line inference before running.
5. **Docs restructure** — 10-minute quickstart, task-oriented how-tos, taxonomy-generated reference. Extend the existing `release --check-docs` `commands` check to cover the new reference doc.

### Metrics (capture baseline before step 2 ships)
1. **Time to first verified dispatch** from a clean install — target under 10 minutes.
2. **Onboarding completion rate** — share of `init`/`quickstart` runs reaching a first merged job or a green `status`; track 7-day repeat use of the core workflow.
3. **Median explicit flags per `dispatch` call** — a drop indicates the defaults are doing their job.
4. **Command-surface concentration** — share of real invocations covered by the top 10 commands, and the count of distinct commands a new user touches in week 1.
5. **Help-seeking load** — `--help`/`doctor` calls per session, plus onboarding-labeled issues per release.
6. **Guardrail:** advanced-command usage by existing power users must not drop. A drop means the facade is hiding capability rather than abstracting it — the explicit failure condition the user asked to avoid.

---

## 3. Broader Five-POV Issues: Remediation Plan

Source: Developer (§1), Founder-reaction ×3 (§3), VC Analyst (§4), AI Influencer (§5).

### Where the panel agreed
- **No single positioning sentence exists.** Adopt one and use it everywhere user-facing (README hero, `init` banner, release notes, any future site): *"Synlynk is a neutral control plane that routes coding tasks across AI vendors and local models, then proves the result."* Retire internal-sounding phrases ("Sovereign Silicon", "Hybrid Workgroup") from user-facing copy.
- **Current trust defaults would sink a launch thread:** `--dangerously-skip-permissions` as a default, the multi-file `init` footprint, confirmed false job-status incidents, and unbounded local state (8.3 GB+ shards, per `[[stray-local-state-db]]`) are all credible first-comment objections on HN/PH. Fix: make skip-permissions opt-in, make `init` minimal by default, ship the GC/retention controls from Roadmap item #1 above, and attach verified evidence (not self-reported status) to every job outcome.
- **No external proof of demand** — no outside users, no paying customer, no routing-win number to cite. Run a 90-day design-partner program (10–20 weekly-active teams), with "at least one paid conversion" as the evidence bar. ICP: small teams already paying for 2+ coding agents.
- **Moat/absorption risk is real** — frontier labs or OpenClaw-class competitors can copy the dispatch mechanic itself. Claim what's harder to copy: cross-vendor arbitration, governance, identity, and outcome history — not the CLI surface.
- **The real story is the operating model, not the tool** — 831+ PRs and 21+ documented incidents run through this exact multi-agent process is the differentiated narrative; hold tutorial-style content until onboarding (§2 above) is actually tight enough to survive a cold viewer.

### Where they differed, and the resolution
| Topic | Claude | Codex | Resolution |
|---|---|---|---|
| Competitive matrix | not proposed | publish a comparison vs. Conductor, Composio, claude-squad, Dynamic Workflows | Include it — cheap to produce, directly answers the "why not X" objection every one of the five POVs raises in some form |
| Agent-authorship framing | pin a launch comment leading with "agent-written," linked to the RCA archive | not addressed | Include it — the thread will raise this unprompted regardless |
| Partnerships | concrete moves: an OpenClaw skill, a Hermes-class local tier, an OpenRouter fallback partnership | only "set boundaries," no concrete moves | Take both — stay out of inference billing, publish a privacy-safe anonymized-outcomes schema, pursue the OpenClaw skill + OpenRouter fallback as low-cost distribution |
| Launch timing | recruit partners before any HN/PH launch | a focused launch is fine once identity/defaults/measurement are fixed | Compatible, not contradictory — gate any public launch on the trust fixes (above), keep partner recruitment running in parallel and ahead of the actual launch date |

### Sequence
1. Fix the positioning sentence and flip skip-permissions to opt-in — both are launch-thread-sinking issues and are cheap to fix immediately.
2. Build one routing-proof report (`route --report`) and a 5-way benchmark kit — this single artifact serves the Developer hook, the VC data-moat question, and the Influencer's strongest content format simultaneously.
3. Recruit design partners; track weekly-active use, task success rate, cost savings, and job-status correctness rate (ties directly to Roadmap item #3 above).
4. Pitch documentary/head-to-head content formats now (the LIVE-17 incident write-up, a Vizor walkthrough clip); hold the tutorial-style vlog until onboarding is tight.

---

## Cross-cutting note

Roadmap item #3 (structured telemetry) and the broader-issues "job-status correctness rate" metric are the same underlying fix viewed from two POVs — land it once, report it in both places. Similarly, Roadmap item #8 (CLI core/packs split) and the Surface Simplification Plan's phased rollout are sequenced as the same initiative: the simplification plan's steps 1–4 are the near-term, low-risk version of #8, and #8 itself is deferred specifically until this plan's metrics exist to justify it. Roadmap item #6's permission-default flip (opt-in skip-permissions) is the same change as the broader-issues plan's "flip skip-permissions to opt-in" action — land it from one PR, not two.

## New issue filed from this panel

A new write-through blind-overwrite bug was discovered running the panel itself: `cmd_decide`'s `--record` path builds its output filename from a 40-character slug of the topic string with no collision check, so two decide runs in the same day sharing a long common topic prefix silently overwrite each other's decision record. Filed as its own GitHub issue (see PR description / issue tracker) rather than worked around quietly, per this repo's standing practice for this bug class.
