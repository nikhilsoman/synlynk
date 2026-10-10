<!-- generated - source of truth is state.db -->
---
decision_id: dec-19555009
topic: "Review docs/reviews/2026-10-05-three-lens-strategic-review.md (VC/M&A/Engineer three-lens strategic review of synlynk). Assess its recommendations and Cross-Lens Top 7 Opportunities (Part 4) and P0/P1/P2 fix list (3.5) for validity. Then map each surviving recommendation onto the existing Five-Track Code-Adjacency Plan (docs/superpowers/plans/2026-10-04-five-track-code-adjacency-plan.md: Track 1 Dispatch/Harness gh:#1985, Track 2 CLI Surface/Taxonomy gh:#1986, Track 3 Data/Display Layer gh:#1987, Track 4 Trust & Positioning Copy gh:#1988, Track 5 Go-to-Market gh:#1989) — identify which opportunities are NEW (not yet covered by any open issue/story in those tracks) vs. which are already tracked. Output a ranked list of concrete new opportunities to fold into the roadmap, each tagged with the Track it belongs to (or 'new Track 6' if none fit), and flag any recommendation you think is wrong or not worth pursuing."
date: 2026-10-06
panel: [claude, codex, grok]
status: approved
---

## Topic
Review docs/reviews/2026-10-05-three-lens-strategic-review.md (VC/M&A/Engineer three-lens strategic review of synlynk). Assess its recommendations and Cross-Lens Top 7 Opportunities (Part 4) and P0/P1/P2 fix list (3.5) for validity. Then map each surviving recommendation onto the existing Five-Track Code-Adjacency Plan (docs/superpowers/plans/2026-10-04-five-track-code-adjacency-plan.md: Track 1 Dispatch/Harness gh:#1985, Track 2 CLI Surface/Taxonomy gh:#1986, Track 3 Data/Display Layer gh:#1987, Track 4 Trust & Positioning Copy gh:#1988, Track 5 Go-to-Market gh:#1989) — identify which opportunities are NEW (not yet covered by any open issue/story in those tracks) vs. which are already tracked. Output a ranked list of concrete new opportunities to fold into the roadmap, each tagged with the Track it belongs to (or 'new Track 6' if none fit), and flag any recommendation you think is wrong or not worth pursuing.

## Panel Inputs

### claude
[model=default; version=2.1.289 (Claude Code)]

## Panel Assessment: Three-Lens Review vs. Five-Track Plan

**Validity of the review's core claims:** The P0 list holds up — empirical routing being suspended while `README`/`policy.json` contradict each other is real and already tracked (gh:#1926, #1993, both Track 3/1). P0-3 (audit log) maps to #1992 (Track 1), already open. P1 items mostly map cleanly too: P1-3 GOVERNS → #1990 (Track 1, now in Wave 2), P1-5 adapter conformance → partially covered by #1963's scope-enforcement work but no dedicated conformance-suite issue exists yet. P1-1/P1-2 (config schema validation, config decomposition) are genuinely **not tracked anywhere** in the five tracks.

**Cross-Lens Top 7 — new vs. tracked:**
1. Prove/kill routing thesis → tracked (#1926, #1993, Track 3/1).
3. Finish strangler/harden adapters → partially tracked (#1963), but "single dispatch path" and conformance tests are not a standalone issue — **new, Track 1**.
4. Close governance loop → tracked (#1990, #1991, #1992).
2. VS Code extension/distribution surface → **NEW, no Track fits** → **new Track 6 (Distribution Surface)**.
5. Ledger-as-standalone-product → **NEW**, speculative productization, not engineering — belongs with Track 5 (GTM) as a future item, not urgent.
6. Productize local/sovereign (MLX one-click) → **NEW**, Track 1-adjacent (dispatch.py has `_preflight_local_silent`) but could be Track 6.
7. Narrative/pricing/demo video → overlaps #1978/#1982 (Track 4/5) — mostly tracked, pricing page is genuinely new (Track 5).

**Ranked new opportunities to fold in:**
1. **Adapter conformance test suite** (P1-5) — Track 1, concrete, cheap, high trust payoff.
2. **Config schema validation + decomposition** (P1-1/P1-2) — Track 1/3 boundary, file it against whichever module ends up owning `.synlynk/config.json`.
3. **VS Code/GitHub App thin client** (P2-1, Opportunity #2) — new Track 6, biggest leverage per the VC lens but large scope; needs its own spec, not a quick dispatch.
4. **SQLite fleet-scale soak test** (P1-4) — Track 3, pairs naturally with #1926 consolidation work already in flight.
5. **Pricing page + 2-min demo video** (Opportunity #7) — Track 5, cheap, should ride along with #1982.

**What I'd reject:** the M&A "$3–8M acqui-hire" framing and VC "pass/seed" verdict are not actionable engineering recommendations — they're market commentary for Nikhil, not roadmap items, and shouldn't generate issues. Also skeptical of "ledger as standalone product" (Opportunity #5) — it's a pivot-shaped bet with no validated demand signal; I'd defer it rather than fold it into any track now.

My position: fold in items 1, 2, and 4 above as new issues against Track 1/3 immediately (small, well-scoped, clearly code-adjacent); open a **new Track 6 (Distribution Surface)** epic for the VS Code/GitHub App work since it has zero current home and is the single highest-leverage gap the review identifies; defer the ledger-productization and pricing-page items to Nikhil's GTM judgment rather than auto-queuing them for dispatch.

### codex
[model=default; version=codex-cli 0.160.0]

The review’s strongest recommendations are the ones tied to observable product claims and reliability evidence. Its P0/P1 labels are too broad for the current roadmap: several items are already tracked, and “blockers before any external diligence” overstates the case for work like config decomposition. The M&A price range and venture-scale claims are hypotheses, not engineering findings, and should not drive prioritization without customer evidence.

**New opportunities to consider, ranked:**

1. **Adapter conformance suite — Track 1.** Valuable and concrete: verify receipt markers, cost attribution, and timeout behavior across adapters. The plan tracks dispatch enforcement and capability reporting, but does not list this test suite.
2. **Standalone cost and capability observability — new Track 6.** This is a meaningful product experiment beyond the Track 3 data/display work. Validate demand before building a separate product or claiming a data moat.
3. **VS Code extension or GitHub App distribution — Track 5.** The plan has GTM and benchmark work, but no extension or app delivery story. Start with one thin, measurable distribution experiment rather than committing to both surfaces.
4. **Pricing and willingness-to-pay test — Track 5.** Add a pricing experiment to the design-partner work; a pricing page alone is not evidence of demand.
5. **RBAC for merge/governance authority — Track 1.** The plan tracks GOVERNS enforcement and host-auth auditing, but not role-based access controls. Scope this only if target customers require it.

**Already tracked:** routing evidence and consolidation (#1926, #1993); GOVERNS and host-auth audit (#1990, #1992); local/sovereign roster (#1984); and GTM benchmarks, design partners, and competitive positioning (#1980–#1983). The adapter strangler itself is not explicit in the five-track table, so confirm whether an open issue covers it before treating it as tracked. SQLite fleet-scale testing is also absent, but should follow evidence of concurrent-writer demand.

**Position:** Fold the adapter conformance suite and focused distribution/pricing experiments into existing tracks; explore standalone observability and RBAC only behind customer validation. Defer a hosted relay and external benchmark wiring until a concrete team pilot or routing dataset justifies them.

### grok
[model=default; version=grok 1.0.44 (5b807183dd79) [stable]]

I'll read the three-lens review and the five-track plan, then check which recommendations already have open issues before ranking anything new.The plan is from October 4. I'll check whether those issues are still open and whether the review's claims match the code.The review's one load-bearing finding is right, and several of its "blockers" are already done. README still says Synlynk "routes tasks to the best available harness using a live capability ledger," while `.synlynk/policy.json` has `capability_policy.mode=empirical` with `suspended_since: 2026-10-04`. That contradiction is the only claim that moves both the venture and the engineering verdict. Proving it is already the roadmap: shard consolidation is #1926 (Track 3), `synlynk capability report` is #1993 (Track 1), and the public proof artifact is #1980 (Track 5). What is missing is the interim copy fix.

P0-3 and P1-3 are stale. #1992 (host-auth audit log) and #1990 (GOVERNS hard-fail) closed on 2026-10-05; #1991 closed with them. `doctor.py` and `status.py` already surface `gh_host_auth` events. The review also understates `dispatch.py` (thousands of lines, `dispatch_agent` near line 3105, not ~1.2k). `LegacyAdapter` is still on the dispatch path, so the strangler note is real, but it is an internal correctness item, not a diligence blocker.

**New work worth filing, in order:**

1. **Track 4.** Replace the "live capability ledger / best harness" sentence in the README and site with interim-default language until #1993 has at least five samples per harness and task type. #1978 shipped positioning and left this claim in place.
2. **Track 1.** One issue: adapter conformance (task-receipt SHA-256, cost attribution, timeout) and a single registry dispatch path, retiring `LegacyAdapter` as a second route.
3. **Track 1.** Make local preflight fail closed. `_preflight_local_silent()` still swallows a missing MLX/OrbStack setup.
4. **Track 2.** Have `synlynk doctor` validate `.synlynk/config.json` and `policy.json` against a schema. Doctor currently checks that the files exist.

**Do not pursue:** a standalone costs product (opportunity 5) — `state.db` is local and the cost bugs are already Track 3; a public pricing page before #1981 design partners and a measured router; splitting `config.json` (P1-2); RBAC, SOC2, hosted relay, and a 20–50-writer SQLite soak (P1-4, P2-3). Those reopen an enterprise plane this roadmap already set aside, for a user base that is still one maintainer. A VS Code extension plus GitHub App (opportunity 2) is a real distribution gap and a new product. Park it. It does not belong on Tracks 1–5 until the routing sentence is true, and it should not become a Track 6.

Keep the five tracks. Add the four items above. Treat the review's seed conditions — extension, paid pilots, SWE-bench — as a venture memo, not as this roadmap.

## Synthesis
## Synthesis

All three panelists agree on the load-bearing finding: the routing-capability contradiction (README's "live capability ledger" claim vs. `policy.json`'s `suspended_since: 2026-10-04`) is real, and the work to resolve it empirically is already tracked — shard consolidation (#1926), `synlynk capability report` (#1993), and public proof (#1980). Grok adds the one piece the others missed: the *interim copy fix* for that contradiction isn't tracked anywhere yet, and is cheap enough to do immediately rather than wait for #1993's five-sample bar. That's the single highest-leverage, lowest-cost item across all three reviews.

On P0-3/P1-3 (host-auth audit log, GOVERNS hard-fail): Claude and Codex call these "tracked," Grok claims they're already *closed* (#1990/#1991/#1992, 2026-10-05). Grok's claim is more specific and consistent with the visible commit history (PRs #2046/#2047/#2050 landing 2026-10-05/06), so I weight it higher — these are done, not open work to re-file.

There's real convergence on four concrete, code-adjacent gaps none of the five tracks currently cover:
- Adapter conformance suite (receipt/cost/timeout verification across harnesses, retiring `LegacyAdapter` as a parallel dispatch path) — all three flag this, Track 1.
- `_preflight_local_silent()` swallowing missing MLX/OrbStack setup instead of failing closed — Grok's concrete bug find, Track 1.
- Config/policy schema validation via `synlynk doctor` — all three raise some version of this; Grok's framing (doctor validates, doesn't just check existence) is the most scoped, Track 2.
- README/site capability-routing language overstating the suspended router — Grok's addition, Track 4, directly closes the review's own headline finding's external-facing half.

Where the panel splits is Track 6 / VS Code extension and the broader productization ideas (ledger-as-product, pricing page, RBAC/SOC2/hosted relay, fleet-scale soak). Claude wants a new Track 6 for distribution; Codex is lukewarm (fold into Track 5 as one bounded experiment); Grok flatly rejects creating a sixth track and says park the extension idea entirely, and rejects RBAC/SOC2/hosted-relay/soak-test work outright as reopening an enterprise plane for a single-maintainer project. Grok's position is better matched to the project's actual state (one maintainer, router itself unproven) — building distribution or enterprise-trust surface before the core routing claim is empirically true is sequencing error. The M&A valuation range and VC pass/seed verdict are explicitly non-actionable market commentary per all three, correctly excluded from the roadmap.

**Decision:** Keep the five-track structure unchanged — do not open a new Track 6. Fold in four new issues now: (1) Track 1 — adapter conformance test suite + retire the `LegacyAdapter` dual dispatch path, (2) Track 1 — fix `_preflight_local_silent()` to fail closed, (3) Track 2 — add schema validation of `.synlynk/config.json`/`policy.json` to `synlynk doctor`, (4) Track 4 — correct the README/site "live capability ledger / best harness" language to reflect the suspended, interim-default routing state until #1993 clears its sample-size bar. Treat P0-3/P1-3 as already resolved (#1990/#1991/#1992) rather than re-filing. Defer the VS Code extension/GitHub App idea, ledger-as-standalone-product, pricing page, and any RBAC/SOC2/hosted-relay/fleet-scale-soak work indefinitely — note them in the review doc as parked future options contingent on #1993 proving the router and #1981 landing design partners, but do not queue them for dispatch. Reject the M&A valuation and VC verdict outright as non-engineering commentary with no roadmap action.

## Decision
**Decision:** Keep the five-track structure unchanged — do not open a new Track 6. Fold in four new issues now: (1) Track 1 — adapter conformance test suite + retire the `LegacyAdapter` dual dispatch path, (2) Track 1 — fix `_preflight_local_silent()` to fail closed, (3) Track 2 — add schema validation of `.synlynk/config.json`/`policy.json` to `synlynk doctor`, (4) Track 4 — correct the README/site "live capability ledger / best harness" language to reflect the suspended, interim-default routing state until #1993 clears its sample-size bar. Treat P0-3/P1-3 as already resolved (#1990/#1991/#1992) rather than re-filing. Defer the VS Code extension/GitHub App idea, ledger-as-standalone-product, pricing page, and any RBAC/SOC2/hosted-relay/fleet-scale-soak work indefinitely — note them in the review doc as parked future options contingent on #1993 proving the router and #1981 landing design partners, but do not queue them for dispatch. Reject the M&A valuation and VC verdict outright as non-engineering commentary with no roadmap action.

> Signatures: see 2026-10-06-review-docs-reviews-2026-10-05-three-len.json
