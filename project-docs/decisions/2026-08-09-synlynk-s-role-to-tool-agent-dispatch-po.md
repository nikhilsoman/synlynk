---
decision_id: dec-195a5deb
topic: "synlynk's role-to-tool-agent dispatch policy (as being designed in the 2026-08-09 agent-roles-and-charters spec) currently hard-wires which tool-agent (Claude/Agy/Grok/Codex) handles which task type per role, based on today's known capability fit. Problem: a purely hard-wired policy means we'd never detect if a harness/model degrades over time (regression, rate-limit-induced quality drop, deprecated model) or improves (new model version, better tool support) -- we'd keep routing to yesterday's best-fit agent forever. capability_sweep.py already exists and does periodic SFIA-tagged calibration (PROG/TEST/REQM skills, discrete sweep runs, cost-capped) but is not currently wired into live dispatch decisions or continuously kept current. Design a concrete mechanism for: (1) reserving a small percentage of real dispatched tasks as calibration/exploration traffic -- e.g. occasionally routing a task to a normally-non-preferred agent, or to a different model/effort-level within the same harness, purely to measure whether the hard-wired preference is still correct; (2) how to size that percentage (tradeoff: too low = slow to detect drift, too high = wastes cost/quality on suboptimal routing for real work); (3) how results feed back into updating the dispatch policy (automatic re-ranking vs. surfaced to pm/architect for a decision); (4) how this differs from / integrates with capability_sweep.py's existing periodic sweep mechanism -- is holdback-based live calibration a replacement, a complement, or should sweep be retired in favor of it; (5) how to keep this 'current' over time -- what's the actual recurring trigger (cron via tpm's durable loop? every N dispatches? every new model release?). Give a concrete recommended design, not just principles."
date: 2026-08-09
panel: [claude, agy, codex]
status: approved
---

## Topic
synlynk's role-to-tool-agent dispatch policy (as being designed in the 2026-08-09 agent-roles-and-charters spec) currently hard-wires which tool-agent (Claude/Agy/Grok/Codex) handles which task type per role, based on today's known capability fit. Problem: a purely hard-wired policy means we'd never detect if a harness/model degrades over time (regression, rate-limit-induced quality drop, deprecated model) or improves (new model version, better tool support) -- we'd keep routing to yesterday's best-fit agent forever. capability_sweep.py already exists and does periodic SFIA-tagged calibration (PROG/TEST/REQM skills, discrete sweep runs, cost-capped) but is not currently wired into live dispatch decisions or continuously kept current. Design a concrete mechanism for: (1) reserving a small percentage of real dispatched tasks as calibration/exploration traffic -- e.g. occasionally routing a task to a normally-non-preferred agent, or to a different model/effort-level within the same harness, purely to measure whether the hard-wired preference is still correct; (2) how to size that percentage (tradeoff: too low = slow to detect drift, too high = wastes cost/quality on suboptimal routing for real work); (3) how results feed back into updating the dispatch policy (automatic re-ranking vs. surfaced to pm/architect for a decision); (4) how this differs from / integrates with capability_sweep.py's existing periodic sweep mechanism -- is holdback-based live calibration a replacement, a complement, or should sweep be retired in favor of it; (5) how to keep this 'current' over time -- what's the actual recurring trigger (cron via tpm's durable loop? every N dispatches? every new model release?). Give a concrete recommended design, not just principles.

## Panel Inputs

### claude
This is a decision-panel analysis task, not implementation — no skill needed.

## Analysis

**Sizing (2-3):** Fix at ~10% of dispatched tasks as calibration traffic, scoped only to tasks where a failure is cheap to detect and revert (non-`--requires-gh-write`, non-critical-path). Use Thompson sampling / epsilon-decreasing rather than a flat rate: start at 15% for any role-agent pairing with <20 historical sweep observations (cold start needs signal fast), decay to 5% once a pairing has 50+ consistent observations, and only escalate back up if `capability_sweep.py`'s periodic score or live-calibration variance exceeds a threshold (drift alarm). This avoids the false choice between "always 10%" and manual tuning — the rate itself responds to confidence, which is the actual variable that matters.

**Feedback loop (3):** Never auto-repoint the hard-wired policy from a single calibration result — one bad Grok run during a rate-limit window shouldn't silently demote Grok for a month. Route results into `capability_sweep.py`'s existing SFIA-tagged scoring, and require N≥5 calibration results in the same direction before the delta crosses a "propose re-rank" threshold. At that point, surface a structured diff (task type, current preferred agent, challenger, score gap, sample size) to Claude/PM for a go/no-go — same discipline as the Design→Plan→Build gate already in this repo, not silent automation. Auto-apply only for a narrow case: safety regression (challenger scoring near-zero repeatedly) triggers immediate fail-closed demotion, mirroring the fail-closed pattern already used in `--requires-gh-write` (#569).

**Relationship to sweep (4):** Complement, not replacement. Sweep tests synthetic SFIA tasks cheaply and broadly (good for coverage of skills rarely dispatched live); live holdback tests real task distribution and real prompt shapes sweep can't synthesize. Keep both — sweep catches capability gaps before they hit production tasks, holdback catches distribution-specific and cost/rate-limit-induced drift sweep won't see. Feed both into one shared scoring table keyed by (role, task-type, SFIA skill).

**Trigger (5):** Not cron-only. Three triggers: (a) every N=200 live dispatches, recompute holdback statistics; (b) sweep runs on its existing periodic cadence, independently; (c) event-triggered re-sweep on new model version release (manual flag, since that's not detectable automatically) — this is the one place a human/PM signal is required, everything else can run on tpm's durable loop.

**Position:** Ship holdback-based live calibration as a complement to `capability_sweep.py`, wired into dispatch now, with confidence-adaptive sampling (15%→5%) and PM-gated re-ranking except for fail-closed safety regressions.

### agy
**Last completed task:** Initialized session for dispatch policy architectural review.
**Next task from `todo.md`:** Deliver concrete recommendation for live holdback calibration & `capability_sweep.py` integration.

---

### Recommended Architecture: Hybrid Exploration & Sweep Framework

1. **Live Exploration Mechanism ($\epsilon$-Greedy Routing):**
   Implement an $\epsilon$-greedy interceptor in the dispatch layer. While 95% of live tasks follow the hard-wired matrix, **5% of real production tasks** are randomly assigned to non-preferred agents or alternate model/effort configs sharing the same SFIA tag (PROG/TEST/REQM). Outcome metrics (test pass rate, execution time, token cost, lint score) are logged asynchronously.

2. **Traffic Sizing Strategy:**
   - **Default:** **5% baseline holdback**, which provides sufficient statistical confidence ($\sim 100+$ samples/month per role) without risking project delivery.
   - **Dynamic Scaling:** Automatically scale down to **2%** when budget cap limits trigger, and burst to **10%** for 72 hours following any major model/harness release.

3. **Policy Feedback & Governance:**
   Use a **hybrid automated PR gate**. Telemetry continuously updates performance confidence intervals. When an alternate agent beats the incumbent by $\ge 15\%$ composite quality score or $\ge 30\%$ cost efficiency over $\ge 30$ executions, the system automatically opens a PR to update the `agent-roles-and-charters` dispatch policy matrix for PM/architect review. Intra-harness effort-level changes auto-promote once thresholds are met.

4. **Integration with `capability_sweep.py`:**
   Live holdback is a **complement**, not a replacement. `capability_sweep.py` provides synthetic, reproducible prior benchmarks when onboarding new models or roles in isolation. Live holdback continuously validates these priors against production complexity, rate limits, and actual codebase degradation.

5. **Recurring Trigger & Freshness:**
   - **Event-driven:** Webhook trigger on new model/SDK releases to run an immediate targeted `capability_sweep.py` run and reset baseline priors.
   - **Time-driven:** A weekly cron managed via TPM's durable loop that executes `capability_sweep.py` and reconciles live holdback telemetry into policy update proposals.

**Final Position:** I position firmly in favor of a **complementary dual-engine model**: maintaining `capability_sweep.py` for synthetic baseline calibration while deploying a **5% adaptive live holdback** for continuous real-world drift detection. Automated PR proposals preserve human architectural oversight while ensuring dispatch routing never stalls on outdated assumptions.

### codex
Use a stratified exploration holdback layered over the hard-wired policy. For each eligible dispatch, compute the normal `(role, task-type) -> agent/model/effort` choice, then assign a deterministic random bucket. In the exploration bucket, route to an approved alternative—normally the runner-up agent, or another model/effort level within the preferred harness. Record policy version, task strata, chosen arm, cost, latency, exit status, verification results, reviewer score, and subsequent rework.

Start at 5% of eligible traffic, with a floor of at least 10 observations per `(role, task-type, arm)` per rolling 30-day window. Use 2% for expensive/high-risk tasks and up to 10% for cheap, reversible work or cells with stale/uncertain data. Never explore tasks requiring unavailable permissions, security-sensitive production changes, or agents failing current compatibility gates. If volume is low, the system should trigger targeted calibration rather than waiting indefinitely for random samples.

Results should update a capability ledger, not directly rewrite the charter. Re-ranking can be automatic only when an alternative has adequate sample size, a statistically meaningful quality advantage, no safety/verification regression, and a cost/latency improvement or accepted tradeoff. Apply changes as a versioned policy overlay with a canary period, rollback threshold, and audit record. Otherwise, surface a recommendation to the PM/architect with the evidence and proposed diff; human approval remains required for role-charter changes.

This complements `capability_sweep.py`. The sweep is controlled, repeatable, SFIA-tagged, cross-agent verified, and useful for cold-start, new models, and sparse task classes. Live holdback measures performance on actual repository context and operational conditions, including rate limits and harness regressions. Retire neither: run the sweep after model/harness releases and monthly as a broad baseline; use live traffic continuously to keep rankings current.

The recurring trigger should be both event- and volume-based: TPM’s durable loop runs a daily freshness check, launches a sweep when any model/CLI version changes or a cell is older than 30 days, and evaluates holdback results every 100 completed dispatches. My recommendation is a 5% stratified live holdback plus the existing monthly/event-triggered sweep, with automatic ranking only under confidence gates and PM/architect approval for charter-level changes.

## Synthesis
## Synthesis

All three panelists converge on the same shape: a small, confidence-adaptive live holdback layered on the hard-wired policy, feeding a scored ledger that gates re-ranking through PM approval except for fail-closed safety demotions, running alongside (not replacing) `capability_sweep.py`. The disagreements are in the numbers and mechanics — worth resolving explicitly rather than averaging.

**Sizing.** Codex's stratified approach is the most operationally sound: a flat percentage ignores that risk profile varies wildly across task types. Adopt Codex's structure — 2% for expensive/high-risk/`--requires-gh-write` tasks, 10% for cheap/reversible work, 5% as the default — but adopt Claude's confidence-adaptive overlay on top of the strata: start each `(role, task-type, arm)` cell at the upper end of its band until it has ≥10 observations in a rolling 30-day window (matches Codex's floor), then decay toward the lower end once a cell has 50+ consistent observations. This gives fast cold-start signal without permanently taxing well-established pairings.

**Feedback loop.** Reject Agy's auto-PR-on-threshold design — a 15%-quality or 30%-cost delta auto-opening a policy PR is too aggressive given this repo's own Design→Plan→Build gate and the non-authoring-review discipline already in force; it also risks the same self-authored-approval problem #423 flags for GitHub writes. Use Codex's versioned-overlay model: results accumulate in a capability ledger, automatic re-ranking is permitted *only* for a canaried overlay with rollback threshold and audit record when sample size, quality margin, and no safety/verification regression are all satisfied — otherwise it's a surfaced recommendation with evidence + diff to Claude/PM, exactly as Claude's response specifies. The one universal auto-action across all three inputs is fail-closed demotion on repeated near-zero challenger scores — keep that, mirroring the `--requires-gh-write` fail-closed precedent (#569).

**Relationship to sweep.** Unanimous: complement, not replacement. Sweep = synthetic, reproducible, SFIA-tagged, good for cold-start and rarely-dispatched skills. Holdback = real task distribution, real prompt shapes, real rate-limit/cost conditions sweep can't synthesize. Both write into one shared ledger keyed by `(role, task-type, SFIA skill)`.

**Trigger.** Merge Claude's and Codex's trigger sets — they're compatible, not competing: (a) volume-based reconciliation every 100–200 completed dispatches via TPM's durable loop, (b) sweep on its existing independent periodic cadence, (c) event-triggered re-sweep + reset of priors on new model/harness version release (human-flagged, since version changes aren't self-detecting), (d) a daily freshness check that forces a targeted sweep if any ledger cell has gone stale (>30 days without an observation) — Codex's addition, which covers the gap where low-traffic role/task cells might never accumulate enough live samples on their own.

**Decision:** Ship live holdback calibration as a complement to `capability_sweep.py`, wired directly into `synlynk dispatch`. Use stratified sampling rates (2% high-risk / 5% default / 10% cheap-reversible), confidence-adaptive within each stratum (start high until ≥10 observations/30-day window, decay after ≥50 consistent observations). Both sweep and holdback write into one shared capability ledger keyed by `(role, task-type, SFIA skill)`. Re-ranking proposals require ≥N=5-10 same-direction observations and are shipped as a versioned, canaried policy overlay with rollback threshold and audit trail, surfaced to Claude/PM for approval — never silently auto-applied — except for fail-closed safety demotion on repeated near-zero challenger scores, which applies immediately and automatically. Recurring currency is maintained via TPM's durable loop on three triggers: volume-based reconciliation (every ~100-200 dispatches), sweep's existing independent cadence, and event-triggered re-sweep on model/harness version changes, plus a daily staleness check that force-sweeps any ledger cell untouched for 30+ days.

## Decision
**Decision:** Ship live holdback calibration as a complement to `capability_sweep.py`, wired directly into `synlynk dispatch`. Use stratified sampling rates (2% high-risk / 5% default / 10% cheap-reversible), confidence-adaptive within each stratum (start high until ≥10 observations/30-day window, decay after ≥50 consistent observations). Both sweep and holdback write into one shared capability ledger keyed by `(role, task-type, SFIA skill)`. Re-ranking proposals require ≥N=5-10 same-direction observations and are shipped as a versioned, canaried policy overlay with rollback threshold and audit trail, surfaced to Claude/PM for approval — never silently auto-applied — except for fail-closed safety demotion on repeated near-zero challenger scores, which applies immediately and automatically. Recurring currency is maintained via TPM's durable loop on three triggers: volume-based reconciliation (every ~100-200 dispatches), sweep's existing independent cadence, and event-triggered re-sweep on model/harness version changes, plus a daily staleness check that force-sweeps any ledger cell untouched for 30+ days.

> Signatures: see 2026-08-09-synlynk-s-role-to-tool-agent-dispatch-po.json
