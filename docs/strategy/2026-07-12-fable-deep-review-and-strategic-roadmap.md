# synlynk — Deep Review & 3–5 Year Strategic Roadmap

**Date:** 2026-07-12
**Author:** Fable (deep review), commissioned by Nikhil
**Basis:** v0.11.0 worktree state — 25 modules / 22,392 source LOC, 976 passing tests / 15,321 test LOC (verified by running the suite, not cited from docs), local-agent spec + plan (2026-07-12, unimplemented), market research via live web search
**Supersedes:** `docs/strategy/2026-07-06-four-pov-evaluation-and-company-roadmap.md` (Step 6 reviews and replaces its roadmap)

---

## Step 1 — Market Review (now → 3 years out)

### 1.1 The layer synlynk sits in, and who else is standing on it

The "polyglot coding-agent harness" layer — tools that wrap, route between, and account for multiple AI coding CLIs — went from near-empty in mid-2025 to visibly crowded by mid-2026. The players cluster into five groups:

**a) Vendor-native orchestration (the absorption front).** Claude Code now ships subagents with per-agent context windows, tool permissions, and model selection; June 2026 added *Dynamic Workflows* (a lead agent fanning out tens-to-hundreds of parallel subagents) and grader-driven revision loops, plus hierarchical agent spawning three levels deep. Commentators describe this explicitly as "Anthropic absorbing a layer of infrastructure that used to be your problem" ([MindStudio](https://www.mindstudio.ai/blog/code-with-claude-2026-new-agent-features), [Developers Digest](https://www.developersdigest.tech/blog/claude-code-agent-teams-subagents-2026), [eesel](https://www.eesel.ai/blog/claude-code-multiple-agent-systems-complete-2026-guide)). The prior 4-POV doc predicted this absorption; it is happening faster than that doc implied. Crucially, though, everything absorbed so far is *intra-vendor*: Claude orchestrating Claudes.

**b) Third-party multi-CLI orchestrators (synlynk's direct competitors).** This is the crowded shelf:
- **Composio's agent-orchestrator** — fleets of parallel coding agents (Claude Code, Codex, Aider, OpenCode), *each in its own git worktree*, with autonomous CI-fix/merge-conflict/review handling ([GitHub](https://github.com/ComposioHQ/agent-orchestrator)). Feature-for-feature this is the closest overlap with synlynk's dispatch/worktree/jobs machinery.
- **Microsoft Conductor** — MIT-licensed deterministic YAML-defined multi-agent workflows (May 2026) ([Microsoft OSS blog](https://opensource.microsoft.com/blog/2026/05/14/conductor-deterministic-orchestration-for-multi-agent-ai-workflows/)). A big-company entrant legitimizes the category and commoditizes the workflow-DAG part of it.
- **bernstein, agent-kanban, agentbox, Shipyard** — deterministic orchestration, leader-worker kanban with cryptographic agent identity, sandboxed parallel execution across local Docker/cloud VMs, respectively ([Augment's survey](https://www.augmentcode.com/tools/open-source-agent-orchestrators), [awesome-agent-orchestrators](https://github.com/andyrewlee/awesome-agent-orchestrators)).
- The **wshobson/agents** multi-harness plugin marketplace (92 plugins, 199 agents across Claude Code/Codex/Cursor/OpenCode/Copilot/Gemini CLI) shows the "cross-harness compatibility" problem is now a recognized ecosystem, not a niche.
- The dominant published pattern is architect→executor→reviewer trios with worktree isolation ([Addy Osmani](https://addyosmani.com/blog/code-agent-orchestra/)) — i.e., synlynk's Trio Protocol is now conventional wisdom, not differentiation.

**c) Proxy/routing layers.** **CliGate** intercepts Claude Code/Codex/Gemini CLI traffic at the protocol level and routes it to cloud providers *or local Ollama models transparently* — the harness never knows the model changed ([Nimbalyst survey](https://nimbalyst.com/blog/best-local-first-ai-coding-tools-2026/)). This is an architecturally different answer to the same question synlynk answers with agent-level dispatch: CliGate swaps the *inference* under one harness; synlynk swaps the *agent* per task. One layer up, **OpenRouter** is the proof the neutral-routing thesis funds: ~$50M annualized revenue (Mar 2026), $113M Series B at ~$1.3B led by CapitalG with Google/Nvidia/ServiceNow/Snowflake/Databricks strategic money, 25T tokens/week — explicitly pitched as routing + governance + billing + observability becoming "a control-plane and data advantage" ([Sacra](https://sacra.com/c/openrouter/), [New Market Pitch](https://newmarketpitch.com/blogs/news/openrouter-series-b-analysis)).

**d) Cost/telemetry observability.** The FinOps-for-AI space is validated and busy: 98% of FinOps practitioners now manage AI spend; a review of 127 enterprise agentic implementations found 73% went over budget, some by >2.4×; Gartner pegs agentic workloads at 5–30× the tokens of chatbots ([Beri](https://www.beri.net/article/ai-finops-2026-73-percent-blow-budget-cfo-fix), [Vantage](https://www.vantage.sh/blog/finops-for-ai-token-costs)). Tooling spans enterprise FinOps platforms (Finout, CloudZero), LLM-native tracers (Langfuse, Helicone, Portkey, LangSmith, Braintrust, Datadog LLM Obs). Two relevant gaps practitioners report: attribution breaks down across multi-agent chains, and "no commercial tool yet delivers granular token + LLM + GPU monitoring at enterprise scale" (FinOps Foundation, via [Finout](https://www.finout.io/blog/best-ai-cost-observability-tools-in-2026)). Nobody in that list does *coding-agent-CLI-level* cost attribution from the outside, which is synlynk's exact seat.

**e) Local/on-device inference (relevant to the 5th-agent bet).** The trend is strong and Apple is actively feeding it: MLX shows 21–87% higher throughput than llama.cpp across Qwen3-0.6B→Nemotron-30B (~525 tok/s peak on M4 Max); WWDC 2026 opened the Foundation Models framework to any backend and shipped `MLXLanguageModel`, making ~4,800 mlx-community models drop-in ([Apple ML Research](https://machinelearning.apple.com/research/exploring-llms-mlx-m5), [WWDC26](https://developer.apple.com/videos/play/wwdc2026/232/), [arXiv comparative study](https://arxiv.org/html/2601.19139v2)). On the workflow side, the published consensus pattern is *hybrid*: local models take file reads, small edits, boilerplate — "maybe 60–70% of a typical coding session" — while cloud frontier models take debugging and architecture, "dropping the API bill to a few dollars a day instead of $20–50" ([Nimbalyst](https://nimbalyst.com/blog/best-local-first-ai-coding-tools-2026/), [Sebastian Raschka](https://magazine.sebastianraschka.com/p/using-local-coding-agents)). Cline, Continue, Goose, CliGate, and Ollama's `launch` integration for Claude Code/Codex/OpenCode all support this hybrid out of the box. **oMLX itself checks out** as described in the spec: real, active, Apache-2.0, native Swift menubar app, OpenAI *and* Anthropic-compatible endpoints, continuous batching, two-tier RAM/SSD KV cache ([jundot/omlx](https://github.com/jundot/omlx), [omlx.ai](https://omlx.ai/)) — but young and single-maintainer, as the spec admits.

### 1.2 Where the layer is going, 1–3 years

1. **Intra-vendor orchestration is already absorbed; cross-vendor arbitration will not be.** Anthropic's Dynamic Workflows kills the "I wrap one CLI in parallel" product category. But no vendor will build genuinely neutral routing that concludes "send this task to a competitor" — the same structural logic that made OpenRouter investable at the inference layer. The durable seat is *measurement and arbitration across vendors*, not workflow plumbing.
2. **Consolidation at the routing layer, fragmentation at the harness layer.** Expect more coding CLIs (every model vendor plus OSS: OpenCode, Aider, Goose), which *increases* the value of a neutral coordination layer, while orchestration frameworks consolidate around a few winners (Conductor-style deterministic DAGs, Composio-style fleets). A shakeout among the ~9+ open-source orchestrators is likely within 18 months; most are <1 year old and single-purpose.
3. **Hybrid local/cloud routing becomes table stakes by 2027.** With Apple shipping the substrate, Ollama shipping the integrations, and the 60–70% offload pattern already folklore, "can route cheap tasks to a local model" will be an expected checkbox in every serious harness within 12–18 months. The differentiation window is *now*, and it is not the routing itself but *measured quality-parity arbitration* (knowing when local output is actually good enough — nobody does this empirically per task class yet).
4. **Money is flowing to governance/monitoring, not wrappers.** 2026 financing has shifted from "what agents can do" to "whether agents can be monitored, governed, secured, and recovered when they fail" ([New Market Pitch](https://newmarketpitch.com/blogs/news/agentic-ai-funding-trends)); Sycamore raised a $65M seed for an autonomous-enterprise-AI OS. Capital is concentrated: infrastructure platforms get the vast majority, thin wrappers get nothing.

### 1.3 Sizing — what's sourceable and what isn't

Honest position: **there is no credible direct market-size figure for "polyglot coding-agent harnesses."** The category is too new and too entangled with adjacent ones. What is sourceable:
- OpenRouter: ~$50M annualized revenue, ~$1.3B valuation, 5%-of-inference-spend take rate — the best comparable for what a neutral routing layer monetizes at ([Sacra](https://sacra.com/c/openrouter/)).
- 67% of enterprises already process ~1B tokens/month; agentic workloads run 5–30× chatbot token volumes (Gartner via [Vantage](https://www.vantage.sh/blog/finops-for-ai-token-costs)).
- 73%-over-budget on agentic implementations is a demand signal for exactly the cost-governance product synlynk gestures at.

What is genuinely unknown/extrapolated: how much of coding-agent spend flows through *third-party* coordination layers vs. vendor-native ones (no data found); whether enterprises will pay for coding-agent governance separately from their existing FinOps/observability vendors (no pricing comparables found at this layer); the durability of per-seat pricing when agents outnumber humans. I flag these rather than invent numbers.

---

## Step 2 — Promoter/Adversary POVs

### 2.1 Promoter / bull case — "the only party measuring the market it routes"

The strongest honest argument for synlynk succeeding:

**The structural seat is real and just got a $1.3B comp.** OpenRouter proved investors will fund a neutral routing layer whose moat is traffic data, at the *inference* layer. The same logic applies one layer up, at the *agent* layer, and it is harder for vendors to attack: Anthropic can absorb Claude-orchestrating-Claude, but a routing layer whose value is "we know Codex beats Claude on your Django migrations at a third of the cost, and we can prove it from your own history" is structurally unbuildable by any vendor. synlynk already has the three primitives this company needs, working, in production on its own development: (1) a longitudinal, Ed25519-signable capability ledger keyed on a real task taxonomy; (2) a 3-stage capability→quota→cost router that consumes that ledger (`jobs.py:376`, `scheduler.py`); (3) an external behavioral sentinel layer (FLATLINE, SUCCESS_LOOP, QUOTA_EXHAUSTED, stall→SIGKILL→handoff) that no vendor harness offers *about itself*.

**The demand signal is precise, current, and unserved at this altitude.** 73% of enterprise agentic implementations blow budget; FinOps practitioners explicitly report no tool gives granular agent-level attribution. Langfuse/Helicone instrument *your app's* LLM calls; Finout ingests *bills*. Nobody sits outside heterogeneous coding CLIs, attributing spend per task, per agent, per capability coordinate. synlynk's `agent_quotas` + telemetry + costs pipeline is aimed at exactly the reported gap.

**The local agent completes the economic story at the perfect moment.** Once a $0 agent is in the fleet, the router's cost tie-break becomes an automatic savings engine, and the capability ledger becomes the *only* dataset anywhere that empirically answers "which task classes can a 7–9B local model handle at quality parity with frontier models?" That dataset compounds with usage; the hybrid-routing folklore ("60–70% of a session could be local") is currently vibes — synlynk can make it measured. This is the OpenRouter data-flywheel argument, applied to the local-vs-cloud boundary before anyone else has instrumented it.

**Execution velocity is demonstrated, and the meta-story is the demo.** v0.1→v0.11 in ~7 weeks; a 976-test suite that passes clean in 3.5 minutes; a monolith regression caught and reversed with a CI guardrail within days (§3). The product develops itself through its own dispatch pipeline under a locked PM/implementer role split — the strongest sales asset is the working demonstration that one person plus a routed agent fleet ships like a team.

**Eight-to-eighteen-month window, and the wedge is cheap to reach.** "Trustworthy cross-agent cost numbers + automatic local offload with quality proof" is shippable by a solo founder on the existing codebase. None of the funded competitors (Composio, Conductor) are building the measurement layer; they're building execution plumbing, which is commoditizing fastest.

### 2.2 Adversary / bear case — "a feature shelf, not a company, racing three absorptions at once"

The strongest honest argument for failure:

**The category's oxygen is being consumed from three directions simultaneously.** From above: Claude Code's Dynamic Workflows already does fan-out, grading, and hierarchical delegation natively — every month, more of synlynk's dispatch surface is a worse duplicate of what the harness does better with subsidized tokens. From below: CliGate-style transparent proxies deliver hybrid local/cloud routing *without asking the developer to change agents*, which is a strictly lower-friction wedge than "adopt my dispatch CLI, tag your tasks along four dimensions, and let my scheduler pick." From the side: Microsoft shipping Conductor for free, MIT-licensed, kills pricing power for workflow orchestration. What's left — cross-vendor measurement — presumes people *run* multiple agent CLIs seriously. If Claude Code follows the Cursor trajectory and takes 80%+ of serious usage, "polyglot" is a hobbyist niche and the Switzerland position guards an empty border.

**The capability-ledger moat requires scale synlynk has no path to.** The flywheel argument assumes many users generating ratings across shared task coordinates. Current reality: N=1 user, per-repo SQLite, no telemetry consent framework, no shared ledger, and a fresh install starts cold (the router literally returns `None` with no capability data — `jobs.py:376`). OpenRouter's data advantage came from sitting in the request path of 8M+ users; synlynk is a local CLI a developer must choose, configure, and keep using through its 20+ command surface. The moat is real *only after* distribution, and distribution is the unsolved problem — there is no PyPI/Homebrew presence yet and zero external users referenced anywhere in the repo.

**The numbers the pitch rests on are not yet trustworthy — and the codebase knows it.** Cost tracking regex-scrapes stdout with an 80/20 split heuristic when only totals are found (`costs.py:35–75`); the rate table hardcodes seven models and silently applies a default paid rate to anything unknown (`costs.py:137–149`); `gemini-2.5-pro` is priced at $0.0 across the board. A FinOps product whose unit economics come from brittle regexes over vendor stdout, one CLI release away from silent drift, will lose the only thing it sells — trust — the first time a customer audits a number. The 2026-07-06 doc flagged this ("Epic 1 before revenue"); five weeks later the structured-interface migration hasn't started, but a 5th agent has been specced.

**Solo-founder physics.** The repo shows a pattern: brilliant velocity, then regression under its own speed — `__init__.py` was modularized to ~1.5K lines on 2026-07-01 and grew back to 10.8K lines by 2026-07-12 before pass 2 re-extracted it. One person cannot simultaneously do GTM, enterprise enforcement planes, SOC2, a data network, *and* keep four vendor adapters current against monthly CLI releases. Meanwhile 48+ public blog posts of implementation detail are prior art against the IP candidates, and the EU grace period never existed.

**The local agent, as specced, weakens the story it's supposed to strengthen.** It dispatches a *single chat completion* to a 7–9B model and prints the text (§3.4, §5.1) — it cannot edit files, run tests, or produce the verify signals the capability ledger feeds on. Shipping it as-planned creates an agent that "completes" jobs producing no diffs, polluting the very dataset that is supposed to be the moat, while competitors (Ollama launch, CliGate) deliver *actually agentic* local coding today by keeping the harness and swapping the model. The bear reads this as the project optimizing for its own roadmap narrative over user-observable capability.

**Synthesis (where I actually land):** the bear is right about sequencing and the bull is right about the seat. The failure mode is not "wrong thesis" but "measurement layer never hardened because feature surface kept growing." The bull case only survives if trustworthy numbers and distribution precede everything else — which drives Steps 5 and 6.

---

## Step 3 — Architectural & Code Review (actual codebase)

All numbers below were measured in this worktree on 2026-07-12, not quoted from prior docs. The 2026-07-06 doc's "868 tests / ~19.7K LOC" is stale: current state is **22,392 source LOC across 25 modules**, **15,321 test LOC**, and **976 tests, all passing in 3m28s** (`pytest tests/ -q`: `976 passed in 207.67s`).

### 3.1 The `__init__.py` extraction: regressed, then genuinely fixed — with a guardrail

The prior doc said the extraction "should continue"; what actually happened is more instructive. Pass 1 (2026-07-01) got `__init__.py` to ~1.5K lines; by 2026-07-12 it had regrown to **10,818 lines** because new feature work landed directly into it (documented candidly in `docs/superpowers/specs/2026-07-12-init-remodularization-design.md`). Pass 2 (commit `8caa638`, merged #180) extracted 11 modules — `wizard.py`, `scan.py`, `instructions.py`, `daemon.py`, `jobs.py`, `quota.py`, `context.py`, `costs.py`, `support_engineer.py`, `team.py`, `doctor.py` — bringing `__init__.py` to **3,406 lines / 53 top-level defs**, and added a CI guardrail failing the build at 4,000 lines (`.github/workflows/test.yml:19–24`). The duplicate `_generate_context_from_db` latent bug flagged in that design was fixed (single definition at `synlynk/context.py:143`).

Assessment: the refactor is real and the guardrail is the right lesson ("no guardrail existed to prevent this regrowth" — their words). Still above the ~1,900–2,200L target; the remaining monolith remnants are the DB schema block (`__init__.py:769–931`), `cmd_release` (~line 2489, ~470L), `cmd_status` + platform-health printers (~2964+), and the verb-map/launch-template tables. None urgent. **`viz.py` remains 4,623 lines of Python with 327 embedded HTML/CSS/script fragments** — the "extract to template assets" recommendation from the prior doc has not been acted on and stands.

### 3.2 Test suite: better than the count suggests, with two real gaps

Depth is genuinely good for the stage, not just numerically: an autouse per-test isolated SQLite fixture and an autouse worktree stub with an explicit opt-out into a *real* git repo fixture (`tests/conftest.py:9–41`); a true black-box E2E tier that shells out to `bin/synlynk.py` with zero imports or monkeypatching (`tests/test_e2e.py:1–16`, marked `e2e`); dedicated regression files for past incidents (`test_agy_dispatch_fix.py`, `test_cycle_migration.py`); and re-export contract tests guarding the modularization (`tests/test_modularise.py`). Mock density is high (~1,876 mock/patch references) but appropriately layered rather than a mock swamp.

The two gaps that matter: **(1) No coverage instrumentation** — 976 tests with unknown branch coverage is a count, not a depth claim; nothing in `pytest.ini` or CI measures it. **(2) The vendor-contract tests (probe TC-1…TC-5) never run against real CLIs in CI** — the compatibility layer most likely to break (verb maps, flag specs, stdout formats in `_constants.py:44–106`) is validated only against fixtures. The prior doc's "nightly CI contract tests against latest vendor CLI releases" (Epic 1) remains unbuilt.

### 3.3 The scraping liability: confirmed, and now measurably load-bearing

POV-4's concern is verified in code and is worse than "fragile parsing" — it feeds pricing:
- `extract_tokens()` tries 5 regex families against captured stdout, then falls back to splitting a bare "Total tokens: N" **80/20 input/output by assumption** (`synlynk/costs.py:35–75`). A vendor format change doesn't error; it silently degrades to the heuristic or zeros.
- `_MODEL_RATE_TABLE` hardcodes 7 model rates; **any unrecognized `model_version` silently bills at `_DEFAULT_MODEL_RATE`** ($3/$15 per MTok shape), and `gemini-2.5-pro` is hardcoded to $0.0 (`costs.py:136–149`). So an unknown model is *charged* a guessed rate and a known one is *free* — both wrong in ways a paying customer would notice.
- Model identity itself is tiered scraping: a `# synlynk-meta` header regex, else agent profile, else config default, else `"unknown"` (`costs.py:77–105`) — and capability ratings key on this (`jobs.py:199–246`), so scores fragment across `model_version='unknown'` rows when the header is absent.

The mitigation instinct in the codebase is right (preflight harness-version-drift detection at `dispatch.py:470–525`, probe/doctor contract machinery), but the strategic fix — structured JSON output modes per vendor — hasn't begun. Notably, the local-agent plan's runner accidentally proves the pattern: it gets token counts from a JSON response body and *prints them in a scrapeable line* to avoid touching `costs.py` (plan, Task Group 1) — structured data deliberately down-converted to the fragile format for compatibility. That's the tail wagging the dog.

### 3.4 Independent findings (not in the prior doc)

1. **Two divergent dispatch paths.** `dispatch_agent()` (`dispatch.py:635+`) does the full ritual: preflight, permission→flag translation, harness overrides, per-job git worktree, context sizing. But the daemon/scheduler queue path `_dispatch_ready_jobs()` (`jobs.py:694–790`) builds its own command from only `cli + non_interactive_flags` and spawns it — **no `dispatch_flags`, no permission translation, no preflight, and no worktree creation visible in that path**; queued jobs appear to run in the daemon's cwd with up to `max_parallel=4` concurrent agents. Whatever the intended semantics, two half-copies of dispatch is where behavior will silently fork (e.g., Claude dispatched via the queue lacks `--dangerously-skip-permissions`, so it will stall on tool approval — the exact failure class sentinels exist to catch). This also matters for the local-agent plan (§5).
2. **Taxonomy/router drift.** `docs/reference/capability-matrix-taxonomy.md` mandates 4 dimensions (org_domain, discipline, role, stage) "so the scheduler can precisely match tasks." The actual candidate query filters on `engg_domain / org_domain / industry / phase` and falls back to `(engg_domain, phase)` (`jobs.py:344–375`) — **discipline, role, and stage are recorded but never used for routing**. The documented contract and the shipped router disagree; either the query or the doc needs to move. This directly affects where the local agent's seeds must live (§5.5).
3. **Score view semantics.** `capability_scores` applies 0.85/week exponential decay to *both* numerator and denominator (`__init__.py:910–930`), so a single ancient rating keeps its full face value forever (decay only reweights *between* ratings). Combined with sample-count-blind ranking in `_capability_candidates_for_story`, one lucky rating from March can outrank ten mediocre recent ones from a rival agent. Fine at N=1 usage; wrong shape for the "signed, game-resistant ledger" ambition.
4. **Fleet scheduler is well-built.** `scheduler.py` is the newest module and the best-engineered: in-batch headroom decrementing, retry caps, failed-agent exclusion with sole-candidate exception, dry-run by construction with a separate `_enqueue_plan` writer. Degraded-quota semantics are explicitly documented and mirrored between single (`jobs.py:376+`) and batch paths. This is the quality bar the rest should meet.
5. **Security posture unchanged since the prior review**: Claude dispatch still defaults to `--dangerously-skip-permissions` (`_constants.py:48`), Codex is properly sandboxed with a well-commented `workspace-write` choice (`_constants.py:56–63`), Agy/Grok permissions remain prompt-advisory. The enforcement-plane gap stands as described in the 4-POV doc.

**Overall:** structure is markedly healthier than five weeks ago and the test discipline is real. The two liabilities that block commercialization are unchanged and both sit in the same place: the numbers pipeline (scraping + hardcoded rates) and the duplicated dispatch path.

---

## Step 4 — Value of the "Local Agent" Addition in Market Context

**Verdict: strategically right, twelve months before it's table stakes — but only if it ships as a measured-arbitrage feature, not a checkbox. As currently planned it is half of each.**

### 4.1 Table stakes soon — the checkbox part is not differentiation

Hybrid local/cloud is already the published best-practice workflow (Step 1e): Ollama's `launch` integration points Claude Code/Codex/OpenCode at local models today; CliGate does transparent protocol-level local routing; Cline/Continue/Goose ship the hybrid pattern out of the box; Apple is making the substrate free and fast (MLX, `MLXLanguageModel`, ~4,800 drop-in models). By 2027, "can use a local model" will be an expected checkbox in anything that calls itself an agent harness. If synlynk's local agent amounts to "we can also send a prompt to localhost:8080," it arrives at parity with tools that already do this with less friction, and it's a distraction.

### 4.2 The wedge nobody else has: routed, measured, quality-gated offload

What no competitor does — and what synlynk's existing machinery makes almost free — is answer *empirically, per task class, when the local model is good enough*:

- CliGate and Ollama-launch route by **static human configuration** ("point boilerplate at the 7B"). The user guesses the boundary.
- synlynk's capability→quota→cost router (`jobs.py:376`, `scheduler.py`) routes by **accumulated quality ratings at $0 marginal cost tie-break** — the boundary is *learned and auditable*. The conservative-seeding rollout in the spec (start narrow at docs/testing, widen as real `capability_ratings` accrue) is exactly the right mechanism, and it needed no new gating code, which validates the architecture.
- The resulting dataset — frontier-vs-local quality deltas across a real task taxonomy, with verify signals and rework counts attached — is the local-inference version of the capability-intelligence moat (prior doc's Epic 6), and the hybrid-routing folklore ("60–70% of a session could be local") currently has **zero empirical instrumentation anywhere in the market**. First mover on measurement here owns the reference numbers.

There's a second-order strategic effect: a $0 agent makes synlynk's cost dashboard *actionable* instead of observational. "You spent $41 this week" is a report; "the router saved you $23 this week by sending 47 granular tasks local at ≥0.95 quality parity" is a product. That sentence is the single best marketing asset available to this project, and only the local agent unlocks it.

### 4.3 Does it dilute? The honest risks

1. **It deepens the bear's sequencing critique.** The scraping/rates pipeline (§3.3) — the thing revenue depends on — remains unhardened while a 5th agent ships. Mitigation: the local agent is also the *first structured-telemetry agent* (usage from a JSON body, rates knowably $0), so ship it explicitly as the Epic-1 pattern-setter, not instead of Epic 1.
2. **As specced, it can't yet earn the ratings that widen its envelope.** A single-shot chat completion produces text in a log, not diffs in a worktree — the verify/test/rework signals the ledger feeds on will read empty (§5.1). Without fixing that, the "self-widening envelope" is a flywheel with no torque.
3. **Apple-only v1 narrows the audience** — acceptable (the dev base is Mac-heavy, and §5.4 shows the v1 is accidentally runtime-agnostic anyway), but the *positioning* should be "local agent," never "MLX agent."
4. **Vendor counter-move exists but is constrained:** Anthropic/OpenAI will not route work to a model that produces them no revenue; Gemini CLI or an OSS harness might. The neutral player is structurally the right owner of the local/cloud boundary — same Switzerland logic as Step 1.2.

**Net:** wedge, not distraction — conditional on §5's fixes. It is the one feature in the current roadmap that simultaneously strengthens the economic story, the data moat, and the neutrality positioning, and it expires as differentiation in roughly a year.

---

## Step 5 — Recommendations on the Local-Agent Spec & Plan

The spec (`docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md`) and plan (`docs/superpowers/plans/2026-07-12-local-agent-mlx-driver.md`) are unusually concrete — pinned code, exact line anchors, TDD steps. Verified against the real codebase, the line anchors check out (`dispatch.py:635/651/730-733`, `costs.py:137-145` all match). The recommendations below are ordered by severity.

### 5.1 BLOCKER — the runner is a text generator, not an agent. Fix the contract or the architecture.

`local_agent_runner.py` sends one `/v1/chat/completions` request and prints the response (plan, Task Group 1 Step 6). It cannot read files, edit files, run tests, or commit. Yet the spec claims "everything downstream (worktree creation, verify, job summary) is unchanged" — downstream *runs*, but on an untouched worktree: verify finds no diff, `_extract_auto_signals`/test-pass-rate/build-success come back empty, and `_write_capability_rating` (`jobs.py:199`) records hollow ratings. The self-widening envelope — the whole rollout mechanism — has no torque, and worse, jobs will look "done" while producing nothing, polluting the ledger the strategy depends on (§4.2).

Two acceptable resolutions, in order of preference:
1. **v1: an explicit artifact-writer contract.** The dispatch prompt for `local` instructs "output the complete contents of file X"; the runner (or a small post-step in the dispatch path) writes the response body to the target path inside the job worktree before exit. Seeds then legitimately cover full-file-rewrite tasks (docs pages, single test files). This is honest, small, and makes verify/capability signals real.
2. **v2 fast-follow: drive an agentic OSS harness against the local endpoint** — e.g. Codex CLI's OSS-provider mode or OpenCode pointed at oMLX's OpenAI-compatible endpoint. Then `local` is a real coding agent (tool use, edits, tests) and reuses the *existing* CLI-subprocess dispatch machinery even more faithfully than the runner does. This is what CliGate/Ollama-launch users already get; it's the market-parity form of the feature.

Either way, delete or qualify the "unchanged downstream" sentence in the spec — as written it's the document's one materially false claim.

### 5.2 HIGH — the concurrency guard only guards one of the two dispatch paths

The plan adds `_local_concurrency_exceeded()` inside `dispatch_agent()` (Task Group 2 Step 8). But fleet-scheduled jobs launch through `_dispatch_ready_jobs()` (`jobs.py:694–790`), which never calls `dispatch_agent()` — so `synlynk schedule --execute` or the daemon can happily start N concurrent local jobs on one GPU, which is precisely the scenario the guard exists for. Fix: enforce the cap inside `_dispatch_ready_jobs()`'s launch loop (skip local candidates when at cap, leave them queued for the next tick) *and* keep the `dispatch_agent()` check. Also change the `dispatch_agent()` behavior from `raise RuntimeError` to a clean "queued/busy" outcome — at-capacity is a normal transient state, not an error; a raise will surface as a failed dispatch in interactive use and, if it ever reaches the scheduler path, would burn one of the story's `MAX_STORY_RETRIES = 2` attempts (`scheduler.py:14`). The plan's *decision* to use a `daemon_jobs` COUNT rather than a synthetic `agent_quotas` row is correct — quotas model time-windowed spend, concurrency is instantaneous state — keep that; just fix placement and failure mode.

### 5.3 HIGH — model identity: without it, the $0 guarantee silently breaks

The runner prints `prompt_tokens/completion_tokens` (matching `extract_tokens()` pattern 5) but **no model identity**. `extract_model_version()` (`costs.py:77–105`) will fall through to `"unknown"` unless a `# synlynk-meta model_version=…` header is present, and `_model_rate_for_version("unknown")` returns the *default paid rate* (`costs.py:136–149`) — so local jobs get billed ~$3/$15 per MTok in the cost ledger, violating the spec's "true $0" decision, and capability ratings fragment under `model_version='unknown'` instead of accruing to the roster model. Two-line fix with a test: the runner's output must end with `# synlynk-meta model_version=<roster id>` (Tier 1 header) alongside the token line. Additionally, make the zero-cost guarantee **agent-level, not model-id-level**: the plan's three hardcoded `_MODEL_RATE_TABLE` entries break the moment a user edits `.agents/local.json` to add a fourth model (it would silently re-price at the default paid rate). A `driver=="http"`/agent=="local" → rate 0.0 override is one conditional and can't drift.

### 5.4 MEDIUM — the plan quietly dropped the spec's preflight; restore it at the scheduling layer

The spec's flow starts with `_preflight_local()` (GET `/v1/models`, fail fast). The plan's runner-refinement moved endpoint-down discovery to job runtime — a clean *failure*, but now a fleet batch scheduled while oMLX is down produces a failed job per story, each burning one of two retries and feeding FLATLINE-adjacent noise into sentinels. Restore a cheap reachability check in two places: `_compute_schedule_plan()` treats `local` as quota-exhausted when the endpoint is down (one HTTP call per batch, cached), and `dispatch_agent()` preflights before spawning. The health-check helper already exists in the plan (`_health_check`) — this is wiring, not new code.

### 5.5 MEDIUM — seed where the router actually looks, and integration-test the seam

Per §3.4(2), candidate filtering uses `engg_domain/org_domain/industry/phase` (`jobs.py:344–375`) — *not* discipline/stage, which the spec's Capability Envelope section reasons in. The plan's `STARTER_WHITELIST` happens to set `engg_domain=docs/testing` so it works, but by accident of column duplication, and the plan's test fixtures use a *hand-rolled schema that drifts from the real one* (a `goal_id` column on stories that doesn't exist in `_DB_SCHEMA`, `__init__.py:772–790`). Add the one test that matters and is currently missing: seed into a real `_get_db()` database and assert `_best_agent_for_story()` returns `local` for a matching story and does *not* for a non-matching one. Also: seeding only-inside-`local doctor` (Task Group 2 Step 5) means a user who skips doctor gets a router that never picks local and a feature that looks dead — seed idempotently on first `local` dispatch as well.

### 5.6 MEDIUM — timeouts and stall-sentinel interplay need one real-hardware data point

`_chat_completion(timeout=300)` is hardcoded. A 9B model on a 16GB machine, fed a full `--context-mode full` prompt (context.md can be large), can plausibly exceed 300s; conversely, long silent local inference may trip stall detection tuned for chatty cloud CLIs. Make the timeout a `local.json` key, default `context_mode` to `task` for local dispatches, and make Task Group 3's real-hardware run explicitly record tokens/sec and P95 latency so the stall thresholds and the 16GB-baseline risk (spec's Open Risks) get numbers instead of vibes.

### 5.7 SCOPE WIN — v1 is already cross-platform; say so and cut the "future llama.cpp driver"

The "driver" is an OpenAI-compatible HTTP client plus a config endpoint. Ollama, llama-server, and LM Studio all speak the same protocol — a Linux user pointing `endpoint` at `http://127.0.0.1:11434/v1` gets the entire feature today with zero code change. The spec's non-goal ("Linux/Windows is a future driver, most likely llama.cpp") over-scopes future work that mostly doesn't exist: reframe as "any OpenAI-compatible local server works via config; oMLX is the documented/tested happy path on Apple Silicon." Bonus: a Linux CI runner with Ollama + a ~1B model could exercise the real-inference tier cheaply, giving the `local_hardware` tests a home in CI after all.

### 5.8 Keep as-is

The 4-PR sequence; two-tier mocked/real testing with the `local_hardware` marker and CI `-m "not local_hardware"` exclusion; conservative capability seeding with `SEED_QUALITY=0.6` (sits inside the 0.15 cost-tie-break gap of a 0.6–0.75 incumbent — the intended behavior); no new gating mechanism; `.agents/local.json` roster-as-config; stdlib-only `urllib` client; the thin-client mitigation for oMLX's youth (verified: oMLX is real, active, Apache-2.0, but ~5 months old and single-maintainer — the thin client is the right insurance). One small addition: commit `.agents/local.json` (worktree subprocesses resolve it relative to cwd — an uncommitted config would vanish inside job worktrees; `.agents/support.json` is already tracked, follow suit).

---

## Step 6 — New 3–5 Year Strategic Roadmap (supersedes 2026-07-06)

### 6.1 Audit of the 2026-07-06 doc — what held, what aged

**Held up (keep):** The vendor-absorption risk call — absorption arrived even faster than written (Claude Code Dynamic Workflows, June 2026). The Switzerland thesis — OpenRouter's $113M Series B at $1.3B is external validation that neutral routing layers monetize on data. "A data and policy company wearing a CLI costume" remains the single best sentence about this project. The rejection of the native-harness pivot — still correct, now permanently so. The "Epic 1 before revenue" scraping warning — verified in code (§3.3), unresolved, and more urgent. The monolith concern — regressed to 10.8K lines and was re-fixed with a CI guardrail; the *lesson* (guardrails, not intentions) generalizes.

**Aged out or wrong (change):**
1. **Local inference was the doc's blind spot.** It appears nowhere, yet it is the biggest strategic development of the five weeks since: Apple shipping the substrate, hybrid-offload becoming folklore, CliGate/Ollama shipping the plumbing. The doc's FinOps framing ("track the spend") missed the stronger move: *eliminate* spend via measured local offload, and own the boundary data.
2. **Competitive crowding was underestimated.** Composio's fleet orchestrator, Microsoft Conductor, agentbox et al. commoditized dispatch/worktree plumbing within weeks. Everything in synlynk that executes tasks is now table stakes; only what *measures and arbitrates* is defensible.
3. **The Epic sequence was too enterprise-linear.** SSO/SCIM/SOC2 planning for a product with zero external users was ceremony. The binding constraint is distribution, and the old roadmap deferred it behind three engineering epics.
4. **License ambiguity is already resolved by the code:** `pyproject.toml` declares MIT. Stop revisiting Apache-2.0; keep MIT, add the CLA, move on.
5. **The patent-clock advice is now mostly moot** — 50+ public posts later, defensive publication *is* the strategy for everything already disclosed. Decide once: file nothing, publish deliberately, keep the blog cadence as a content moat instead of treating it as an IP leak.
6. Stale numbers throughout (fixed in this doc's header).

### 6.2 Identity — one decisive sentence

**synlynk is the measurement and arbitration layer for heterogeneous coding agents: it knows which agent — cloud or local — should do each unit of work, proves it from your own history, and shows you the money.** It is not a harness, not a workflow engine, and not an agent vendor. Everything below either feeds that sentence or gets cut.

### 6.3 The roadmap

#### Horizon 0 — Prove the numbers (now → Oct 2026, pre-GA)

The gate for this horizon: *every number synlynk displays is either structurally sourced or visibly labeled as an estimate.* No GA, no users, no revenue talk before this.

1. **Structured Integration Layer** (old Epic 1, unchanged in intent, now with a pattern-setter): per-agent adapters consuming `claude -p --output-format stream-json`, Codex headless JSON, Gemini structured mode — regex scraping demoted to fallback, and fallback-derived rows *flagged as estimated* in costs.md and Vizor. Kill the 80/20 total-split heuristic as a silent default (`costs.py:70–75`). Move `_MODEL_RATE_TABLE` out of code into an updatable data file with a `rates_updated_at` shown in `status`; fix the `gemini-2.5-pro: $0` lie.
2. **Local agent, shipped per Step 5**: artifact-writer v1 → agentic-OSS-harness v2, model-identity header, agent-level $0 guarantee, guard in both dispatch paths, scheduler-level preflight. Crown it with the **Savings Ledger**: "router sent N tasks local this week at ≥X% measured quality parity — $Y saved." This line is the product's headline metric from now on.
3. **Unify the two dispatch paths** (§3.4.1): one launch function used by interactive dispatch and the daemon queue — worktrees, flags, preflight identical. This is a correctness debt that compounds with every new agent.
4. **Surface consolidation:** declare the five daily commands (`dispatch`, `schedule`, `status`, `jobs`, `doctor`); everything else demoted from README/FTUE to reference docs. `viz.py` template extraction is parked unless it blocks something.

**Explicit kills, permanent:** the native-harness direction (`synlynk-as-a-harness.md` marked historical); any 6th agent before v1.1; all enterprise-plane work (SSO, SOC2, RBAC); new visualization surfaces.

#### Horizon 1 — Distribution or die (Q4 2026 → mid-2027)

The old roadmap treated distribution as an epilogue to engineering. Inverted: H1 is *only* about users.

1. **v1.0 GA:** PyPI + Homebrew, signed releases + SBOM, docs site. Positioning is the Savings Ledger, not the feature list: *"the coding-agent router that pays for itself."*
2. **The Benchmark Asset:** publish the first empirical local-vs-frontier quality-parity dataset by task class, from synlynk's own telemetry (own dogfood + opt-in early users). Nobody has these numbers (§4.2); the goal is that every "should I run a local coding model?" conversation in 2027 cites synlynk's data. This replaces the old BS-7 benchmark narrative and is the single highest-leverage marketing artifact available.
3. **Opt-in anonymized telemetry** designed in at GA (consent-first) — the H3 flywheel's intake. `flatline` and `git-drift` standalones ship as top-of-funnel.
4. **The honest gate, named now:** if by mid-2027 synlynk has fewer than ~500 weekly-active installs with D30 retention above ~25%, the thesis-honest conclusion is that this is a *tool, not a company* — continue as sustainable OSS with the data asset kept clean for an acqui-conversation, and do not raise. If the gate passes, H2 proceeds and the seed raise happens on that evidence. Writing the gate down today is the discipline the last roadmap lacked.

#### Horizon 2 — Sell the boundary (mid-2027 → end 2028) — *conditional on the H1 gate*

1. **Team control plane** (hosted + self-hostable, NATS as planned): shared capability ledger, team budgets, policy distribution, team Savings Ledger. 5–10 design partners before pricing.
2. **Pricing follows the router, not the seat.** The natural model for an arbitration layer is OpenRouter's, not Jira's: a percentage of *managed/optimized* spend (or a flat platform fee + savings-share). Per-seat pricing ages badly in a world where agents outnumber humans. Run both with design partners; expect the %-of-spend model to win.
3. **Enforcement plane ships in OSS first** (unchanged from the prior doc, re-affirmed): sandboxing around dispatched agents, authn on daemon/relay/Vizor, secrets redaction. It makes the free product safer and every enterprise conversation possible — but it *follows* paying-team demand rather than preceding all revenue.
4. **Seed raise + 2–3 founding engineers** here, on H1 traction. Bus-factor-of-one ends in this horizon or the company ambition does.

#### Horizon 3 — The capability intelligence network (2029 → 2031)

The durable asset compounds: anonymized cross-org routing intelligence — which agent/model/local-tier completes which task class at what cost and quality, model-release regression alerts within hours, routing recommendations as an API. Two honest endgames, both wins:
- **(a) Independent:** the OpenRouter of coding agents — the neutral arbitration layer every multi-vendor engineering org runs, monetizing a slice of routed spend and the intelligence API. Optimize for this.
- **(b) Acquired:** by a FinOps platform (Finout/CloudZero class), an observability vendor (Datadog class), or a neutral router (OpenRouter itself) — what's bought is the longitudinal cross-vendor + local/cloud boundary dataset and the routing engine on top. Keep this path live at zero cost by keeping the ledger schema clean, signed, and exportable — which is already the design.

**What would falsify the thesis (monitor, don't hedge):** (1) a single vendor consolidates >80% of serious coding-agent usage → "polyglot" becomes a niche; watch quarterly. (2) local models reach such complete parity that arbitration is trivial → the quota/fleet/sentinel layer remains but the intelligence premium shrinks. (3) vendors ship genuinely neutral cross-vendor routing → structurally unlikely (conflict of interest), and the strongest reason to believe the seat stays open.

### 6.4 Top risks, restated for this roadmap

| # | Risk | Change vs. 2026-07-06 | Mitigation |
|---|------|----------------------|------------|
| 1 | Scraping fragility poisons trust | **Worse** — verified in code, still unfixed, now feeds pricing | H0 item 1 is the roadmap's hard gate |
| 2 | Vendor absorption | **Realized** for intra-vendor orchestration; cross-vendor seat still open | Retreat fully to measurement/arbitration; stop competing on execution plumbing |
| 3 | Distribution never happens | **Newly named** — the prior doc's silent assumption | H1 is distribution-only, with a written kill/continue gate |
| 4 | Local-agent ships hollow (no diffs, hollow ratings) | **New** | Step 5.1 blocker resolved before merge |
| 5 | Solo velocity regression (monolith pattern) | Mitigated once via CI guardrail | Generalize: every architectural invariant gets a CI check, not a doc note |

### 6.5 The one-sentence pitch for the next release

*"synlynk v1.0 routes your coding tasks across Claude, Codex, Gemini, Grok — and your own Mac — using your project's own quality history, and shows you exactly what it saved you."*

---

*End of review. Written by Fable (deep review), 2026-07-12, commissioned by Nikhil. This document supersedes `2026-07-06-four-pov-evaluation-and-company-roadmap.md` as the operative strategy document.*
