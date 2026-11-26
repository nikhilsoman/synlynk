# #4931 — Non-architecture concerns from the five-POV review

## Question

Identify the distinct non-architecture concerns in the Developer, Founder, VC, and AI-influencer sections and propose concrete responses.

## Verdict

**Derived from the recorded synthesis.** Public launch should remain gated on coherent positioning, safe permission defaults, verified outcomes, and a shared routing-proof asset. Demand proof should come from a time-bounded design-partner program, while competitive comparisons, incident evidence, and limited partnerships support distribution without expanding into inference billing.

## Findings

### Recorded panel synthesis (verbatim)

> **Where the panel agrees**
>
> - **Positioning:** both say the product has no single sentence. Adopt one: "Synlynk is a neutral control plane that routes coding tasks across AI vendors and local models, then proves the result." Use it in the README hero, the `init` banner, release notes and the homepage. Retire "Sovereign Silicon" and "Hybrid Workgroup" from user-facing text.
> - **Trust defaults:** skip-permissions as the default, the six-file `init` footprint, false job statuses and the 8.3 GB of local state would all sink a launch thread. Make permissions opt-in, make a minimal `init` the default, ship retention and cleanup controls, and attach verified evidence to job outcomes.
> - **Proof of demand:** there is no external usage, no paying customer and no routing-win number. Run a 90-day design-partner program of 10–20 weekly-active teams and aim to convert at least one to paid. Define the ICP as small teams already paying for two or more coding agents.
> - **Moat and absorption risk:** frontier labs and OpenClaw can copy dispatch. Claim the parts labs can't build: cross-vendor arbitration, governance, identity and outcome history. Treat integrations as distribution, not competition.
> - **Content:** the story is the AI-run operating model (831 PRs, 21 incidents), not the CLI. Hold tutorial content until onboarding is tight.
>
> **Where they differ**
>
> - **Competitive matrix:** Codex wants a published comparison against Conductor, Composio, claude-squad and Dynamic Workflows. Claude didn't propose one. It is cheap and answers the "why not X" objection, so I'd include it.
> - **Agent-authorship framing:** Claude wants a pinned launch comment that leads with "agent-written" as the demo, linked to the RCA archive. Codex doesn't address it. I'd include it, since the thread will raise it anyway.
> - **Partnerships:** Claude proposes concrete moves (an OpenClaw skill, a Hermes-class local tier, an OpenRouter fallback partnership). Codex only says to set boundaries. I'd take both. Stay out of inference billing, publish a privacy-safe anonymized-outcomes schema, and pursue the OpenClaw skill and OpenRouter fallback as low-cost distribution.
> - **Launch timing:** Claude says to recruit partners before any HN/PH launch. Codex allows a focused launch once identity, defaults and measurement are fixed. The two are compatible. Gate any public launch on the trust fixes, and keep partners first.
>
> **Sequence**
>
> 1. Fix the positioning sentence and the skip-permissions default, since both would sink a launch thread.
> 2. Build one routing-proof report (`route --report`) and a 5-way benchmark kit. This serves the developer hook, the VC data-moat question and the influencer's strongest format at once.
> 3. Recruit design partners and track weekly-active use, task success, cost savings and the job-status correctness rate.
> 4. Pitch the documentary and head-to-head formats (the LIVE-17 write-up, a Vizor clip) now. Hold the tutorial vlog.
>
> Decision: Hold the public launch until the positioning sentence is adopted and skip-permissions is opt-in, then build the routing-proof report and 5-way benchmark kit as the shared asset for developer, VC and influencer audiences. Run a 90-day design-partner program of 10–20 teams with one paid conversion as the evidence bar, and carry the launch with the benchmark and incident-documentary stories. Hold tutorial content, and take the OpenClaw skill and OpenRouter fallback partnership as cheap distribution while avoiding inference billing. I haven't written this up as a decision record. The two untracked `project-decisions/…five-pov` files already in the worktree are the panel's artifacts, so tell me if you want this recorded there.

## Recommended follow-ups

- **New ticket: Yes. Proposed title:** “Enforce public-launch trust and positioning gates.”
- **New ticket: Yes. Proposed title:** “Build route report and five-harness benchmark kit.”
- **New ticket: Yes. Proposed title:** “Run a 90-day multi-harness design-partner program.”
- **New ticket: Yes. Proposed title:** “Publish a cross-vendor competitive matrix and incident-evidence launch package.”
- **New ticket: Yes. Proposed title:** “Evaluate OpenClaw skill and OpenRouter fallback distribution partnerships.”

## Sources

- [GitHub issue #4931](https://github.com/nikhilsoman/synlynk/issues/4931)
- `docs/strategy/2026-10-02-five-pov-review.md`
