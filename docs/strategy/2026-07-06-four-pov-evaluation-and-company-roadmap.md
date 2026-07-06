# synlynk — Four-POV Evaluation & Company-Building Roadmap

**Date:** 2026-07-06
**Author:** Claude (PM role), commissioned by Nikhil
**Basis:** v0.11.0 state — ~19.7K LOC stdlib-only Python package, 868 tests, roadmap through v1.2 (enterprise, Q1 2027), strategy doc `synlynk-as-a-harness.md`

---

## POV 1 — A developer who uses AI coding tools

**Would I install this? If I run more than one agent CLI, probably yes. If I run one, probably not yet.**

The pains synlynk targets are real and I feel them daily: agents that loop silently and burn $40 before I notice (FLATLINE/stall sentinels), no cost visibility across tools, context that evaporates between sessions, and no way to know which of my CLIs is actually good at which kind of task. The sentinel layer is the standout — nothing in Claude Code, Codex, or Gemini CLI watches my agent *from the outside* and kills a 6-hour silent hang. The zero-dependency stdlib-only install is genuinely respectful of my machine.

What gives me pause as a user:

- **Surface area vs. daily habit.** The command surface is large (dispatch, jobs, watch, viz, status, probe, doctor, sync, relay, scan, story, score…). My honest first question is "what are the three commands I run every day?" The v0.10 FTUE wizard and launch cheat-sheet address this, but the tool currently reads as built for its builder's workflow.
- **Overlap anxiety.** Harnesses are absorbing this layer fast — Claude Code has subagents, hooks, OTel telemetry, and cost reporting natively. Anything synlynk does that my harness also does becomes friction. The durable value is precisely what a single vendor *won't* build: cross-vendor routing, comparison, and arbitration.
- **Trust in the numbers.** Costs come from regex-scraping stdout. When a vendor changes output format, my budget dashboard silently drifts wrong — worse than no dashboard.

**Verdict:** compelling for the multi-agent power user (a small but rapidly growing segment); the wedge features for everyone else are flatline detection and cost tracking, which should be extractable and near-zero-config (`flatline` standalone is the right instinct).

## POV 2 — Founder/exec leadership at an AI company

**The strategic bet is that the multi-vendor agent world persists and needs a neutral coordination layer. I think the bet is right; the current moat is thin; the durable asset is the data, not the wrapper.**

- **Layer analysis.** synlynk sits at the meta-harness/orchestration layer — the layer every model vendor wants to own downward from and every IDE wants to own upward into. Model vendors will not build genuinely neutral multi-vendor routing (conflict of interest), which is exactly why a Switzerland player can exist here — same structural logic as OpenRouter for inference or Terraform for clouds. But the seat is contested: LangGraph/CrewAI from the framework side, OpenHands/Dagger/e2b from the sandbox side, and ACP/Agent SDKs from the vendors themselves.
- **Moat audit.** Flag maps, verb maps, and stdout regexes are commoditizable and depreciate with every vendor release. The durable assets in the codebase are: (1) the capability ledger — longitudinal per-agent, per-domain performance data; (2) the sentinel pattern library — behavioral failure signatures of autonomous agents; (3) the cross-harness compliance matrix. These compound with usage; the wrappers don't. A company here is a *data and policy* company wearing a CLI costume.
- **The native-harness question** (the internal `synlynk-as-a-harness.md` proposal): going direct-to-API trades harness drift for direct competition with vendor harnesses, without their model access, their subsidized token economics, or their distribution. Wrong move. The right move is the middle path: migrate from stdout scraping to *structured programmatic interfaces* (headless JSON modes, Agent SDKs, ACP) — keep the vendors as the execution engines, own the coordination and measurement above them.
- **Economics framing.** "Eco mode," R/W/T budgets, and capacity gates are early moves toward **FinOps for AI agents** — cost-aware routing across heterogeneous models. As agent spend becomes a real line item (it already is at AI-native companies), the party that knows "which agent/model completes this class of task cheapest at acceptable quality" holds pricing-relevant information. That is a company. Semiconductor/infra relevance is nil and that's fine — this is a pure software/data layer.
- **Execution signal.** v0.1→v0.11 in ~6 weeks, 868 tests, disciplined release/blog cadence — the velocity is real. The risks are bus-factor-of-one and the depth of review behind agent-written code; both are financeable problems, not disqualifiers.

## POV 3 — Enterprise tech exec (adoption, utilization, governance, security)

**The vocabulary is exactly right and ahead of most of the market; the enforcement is not there yet. I'd engage as a design partner, not a buyer.**

What resonates immediately: role-based capability tiers per agent, per-task permission grant/revoke, budget gates that block dispatch, an audit trail of every invocation, compliance checks (`doctor`), and cost rollups per agent and per project. This is precisely the "agent sprawl" governance story CIOs are being asked for in 2026, and almost nobody selling AI coding tools speaks it.

What my security team would flag in week one:

1. **Advisory vs. enforced controls.** Permission translation maps to `--allowedTools` (real) for Claude but to a `## Permissions` context header for Agy — i.e., *instructions to the model*. Prompt-level controls are not controls. Enterprise readiness requires an enforcement plane: OS sandboxing, container isolation, network egress policy — independent of agent cooperation.
2. **No identity or central management.** State is per-repo SQLite; there's no SSO/SCIM, no RBAC tied to corporate identity, no central policy distribution, no org-wide visibility. (Planned v1.1/v1.2 — the plan is correct, it just doesn't exist yet.)
3. **Supply chain.** Single maintainer, `install.sh`, no signed releases, no SBOM, no SOC2 story. Ed25519 signing exists in the codebase — pointed at agent attestations, not yet at release artifacts.
4. **Local services.** The daemon HTTP server (localhost:27471), relay broker, and Vizor (localhost:8721) need an authn story before any multi-user deployment.

**Verdict:** the primitives (tiers, gates, sentinels, signed ledger) are the right foundation and the roadmap sequences the missing planes correctly, but Q1 2027 for enterprise is aggressive. Track it; pilot the local tool with an innovation team; buy when the enforcement + management planes ship.

## POV 4 — AI systems architect / principal engineer

**Sound local-first architecture with one honest structural liability (the scraping layer) and one avoidable one (monolith remnants). Several defensible IP candidates — but the blog series is racing the patent clock.**

- **Scalability:** SQLite-WAL job store + launchd/systemd daemon + SSE relay is the correct local/workgroup-scale architecture — no accidental distributed system. The team/enterprise jump needs a real control plane; NATS (already named in the plan) is a reasonable choice. The clean `status --json` contract as Vizor's sole data feed is good discipline that will pay off at the server transition.
- **Availability:** stall detection → SIGKILL → `HANDOFF_PENDING` → cross-agent handoff with context transfer is a genuinely thoughtful local resilience loop. Nothing needs HA until the server exists.
- **Efficiency:** stdlib-only is a real engineering constraint honored for 19.7K lines — install-anywhere with zero dependency hell. Preflight capacity gates (R/W/T, TOOL_PRESSURE) put backpressure *before* spend, which is the right place.
- **Maintainability:** 868 tests / ~12.7K test LOC is strong for the stage. Concerns: `__init__.py` still ~10K lines post-modularization (the extraction should continue until it's orchestration-only); `viz.py` is 4.5K lines of HTML/CSS/JS inside Python strings (extract to template assets); and the harness verb-map/palette tables institutionalize a permanent stdout-compatibility treadmill. The probe/doctor contract-test approach (TC-1–TC-5) is the correct mitigation — the strategic fix is migrating each adapter to structured interfaces as vendors stabilize them.
- **IP filing candidates** (ranked by defensibility × distance from prior art):
  1. **Behavioral sentinel detection for autonomous coding agents** — classifying failure modes (FLATLINE, SUCCESS_LOOP, STALL_NO_OUTPUT, QUOTA_EXHAUSTED) from external telemetry without agent cooperation, with automated intervention.
  2. **Cross-harness permission translation** — a capability-tier policy compiled to heterogeneous enforcement primitives (`--allowedTools`, approval policies, sandbox profiles) per target harness.
  3. **Stalled-job handoff protocol between heterogeneous agents** — sentinel-triggered transfer with context file, handoff notes, and lineage (`previous_agents`).
  4. **Game-resistant signed capability ledger** — Ed25519-attested, sample-capped per-agent capability scoring.
  5. **Preflight capacity gating** — R/W/T budget arbitration across an agent fleet.
  - **Caveat:** 48 public blog posts documenting implementation detail are self-published prior art. The US 1-year grace period is running on everything already posted; there is no grace period in the EU. If filing matters, provisionals on items 1–3 should precede further detailed disclosure; defensive publication is the honest alternative for the rest given the open-source core.

---

## Company-Building Roadmap

**Structure: open-core.** The individual engineer's tool stays a public, permissively-licensed project forever — it is the funnel, the community, and the recruiting surface. The company sells coordination, governance, and intelligence for teams and orgs.

```
OSS (public, free forever)              Commercial (the company)
─────────────────────────              ─────────────────────────
synlynk CLI · sentinels · dispatch     Sync server / team control plane
local Vizor · budgets · capability     Org policy + enforcement plane
ledger (local) · probe/doctor          SSO/SCIM · RBAC · audit export
flatline & git-drift standalones       Fleet analytics · capability intelligence
```

### Epic 0 — Legal & structural foundation *(now, before v1.0 GA)*
Incorporate. Choose licenses **before** GA: Apache-2.0 for the core (adoption-maximizing), commercial license for the server. **Introduce a CLA immediately** — without it, external contributions poison the ability to relicense or dual-license later. Trademark "synlynk." File provisionals on sentinel detection, permission translation, and handoff (POV-4 items 1–3) before publishing further implementation detail.

### Epic 1 — Structured Integration Layer *(pre-GA, highest technical priority)*
Replace stdout scraping with structured interfaces per agent: `claude -p --output-format stream-json` / Agent SDK, Codex headless JSON, Gemini CLI structured mode, ACP where offered. Nightly CI contract tests against latest vendor CLI releases; probe/doctor becomes the certification suite. *This de-risks the foundation every commercial promise sits on — cost numbers and telemetry must be trustworthy before anyone pays for them.*

### Epic 2 — GA & Distribution (v1.0)
PyPI + Homebrew, signed releases + SBOM, docs site, the BS-7 benchmark narrative and `flatline`/`git-drift` standalone utilities as launch assets. Add **opt-in anonymized telemetry** — the capability-intelligence flywheel (Epic 6) needs data consent designed in from day one. Success metric: weekly-active installs and D30 retention, not stars.

### Epic 3 — Enforcement Plane *(the enterprise credibility gate)*
Permissions move from advisory to enforced: OS-level sandboxing (Seatbelt/Landlock/containers) around dispatched agents, filesystem ACLs, network egress allowlists, secrets redaction in context injection, authn on all local services (daemon, relay, Vizor). Ships in OSS core — it makes the free product safer *and* makes every enterprise conversation possible.

### Epic 4 — Team Control Plane *(first paid product, ~v1.1)*
Hosted + self-hostable sync server (NATS): shared capability ledger, team budgets with owner-set limits, team Vizor, Slack/GitHub notifications, shared handoff queues. **Run 5–10 design partners before pricing.** Per-seat pricing; the buyer is an engineering manager whose agent spend became a budget line.

### Epic 5 — Governance & Compliance Pack *(enterprise, ~v1.2)*
SSO/SCIM, RBAC on corporate identity, policy-as-code distributed from the control plane, immutable audit export (SIEM-friendly), air-gapped self-host, SOC2 Type I → II. Sell utilization + governance as one motion: the same telemetry that enforces policy shows the CFO the ROI of agent spend.

### Epic 6 — Capability Intelligence *(the durable moat, post-v1.2)*
Anonymized cross-org benchmarks: which model/harness completes which task class at what cost and quality. Routing recommendations, model-release regression alerts, spend optimization. This is the asset competitors cannot copy by reading the code.

### Sequencing & funding
E0+E1 immediately (weeks); E2 on the existing Sep 2026 GA target; E3 through Q4 2026; E4 design partners Q4 2026 → paid Q1 2027; E5 realistically H2 2027 (SOC2 wants a real team); E6 grows as data accrues. Bootstrappable through E3; E4/E5 (server, compliance, 2–3 founding engineers) is the natural seed-raise moment, with OSS traction as the evidence.

### Top risks
1. **Vendor absorption** — harnesses natively add multi-agent orchestration. *Mitigation: neutrality + cross-vendor data; a vendor can copy features, not the Switzerland position.*
2. **Scraping fragility poisons trust** — one bad cost number ends a paid relationship. *Mitigation: Epic 1 before revenue.*
3. **Governance theater accusation** — selling "control" that is prompt-advisory. *Mitigation: Epic 3 before enterprise conversations; never market beyond enforcement reality.*
4. **Solo velocity as ceiling** — one founder + agents ships a v1, not a SOC2 company. *Mitigation: the seed hire plan in E4/E5.*
