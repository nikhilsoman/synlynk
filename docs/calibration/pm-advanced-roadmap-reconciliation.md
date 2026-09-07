# Roadmap Section: Reconciling Throughput vs. Trustworthiness

**Role:** PM calibration draft (advanced / general scenario)  
**Status:** Draft for stakeholder review — not committed to the live product roadmap  
**Conflict under reconciliation:** Stakeholder A prioritizes *feature throughput and autonomous coverage*; Stakeholder B prioritizes *execution trustworthiness and zero silent failure*.

---

## Stakeholder positions (as stated)

| Stakeholder | Priority | Success signal they will accept | Risk they refuse |
|---|---|---|---|
| **A — Growth / Autonomy** | Expand what agents can do unattended (more roles, more surfaces, more parallel jobs) | Weekly increase in closed stories and Named-Release-ready clusters | Roadmap that "pauses shipping to polish plumbing" |
| **B — Reliability / Truth** | Make every dispatch outcome verifiable (receipts, job-truth, gh-write attestation, merge authority) | No Sev1/Sev2 LIVE recurrence across a full release cycle; `jobs --all` stays clean | Shipping features on an unreliable execution floor |

These are not aesthetic preferences. They collide on the same scarce resources: harness quota, review bandwidth, and the human approval gate.

---

## Reconciliation thesis

**Ship autonomy on a trust floor, not instead of one.**

Throughput is allowed to grow only inside bands where trustworthiness gates are green. When a trust gate turns red, throughput work is preempted — not negotiated away in chat. Conversely, trust work that does not unlock measurable autonomy capacity is deferred.

This converts a zero-sum argument ("features vs. reliability") into a sequenced dependency: **trustworthiness is the enabling constraint for sustainable throughput**.

---

## Roadmap arc: `vNext — Throughput-on-Trust`

### Phase T0 — Trust floor (blocking; 1–2 weeks)

Must complete before any net-new autonomy surface area lands.

| Item | Owner role | Acceptance |
|---|---|---|
| Job-truth + gh-write attestation remains green on the default review path | qa / codex | `synlynk jobs` and PR gate agree with GitHub ground truth for open/review/close |
| Task + instruction receipt protocol enforced on every dispatch | tpm | Missing/mismatched receipts → terminal `task_delivery_failed`, never silent OK |
| Merge authority check before merge | qa | Non-authorized merge attempts fail closed |

**Stakeholder B gets:** hard stop on silent failure.  
**Stakeholder A gets:** a clear, short critical path after which expansion unblocks — not an open-ended reliability rewrite.

### Phase T1 — Throughput expansion (gated; 2–4 weeks)

Unlocked only while T0 acceptance stays green for one full release cycle slice.

| Item | Owner role | Acceptance |
|---|---|---|
| Parallel ready-story sweep under TPM durable loop | tpm | ≥N independent stories advanced unattended without manual re-prompt |
| Capability-calibration traffic at stratified holdback rates | pm / architect | Ledger updates; no auto-reroute without PM-gated proposal |
| Next product surface from backlog (e.g. visualization BS-6) | designer / grok | Spec → plan → build sequence intact; no bypass of brainstorm-first |

**Stakeholder A gets:** concrete autonomy and product expansion.  
**Stakeholder B gets:** expansion that is auto-paused if T0 regressions reappear (fail-closed demotion, same pattern as gh-write safety).

### Phase T2 — Compounding loop (ongoing)

| Item | Purpose |
|---|---|
| Named Release when a themed cluster of ≥3 related PRs lands | Converts throughput into communicable progress without waiting for a mega-release |
| Competitive sweep → research tickets → decide rounds | Keeps growth intentional rather than opportunistic feature sprawl |
| Worktree/job hygiene on every merge | Prevents autonomy from creating stale-state debt that looks like "progress" |

---

## Decision rules (how future collisions resolve)

1. **If T0 is red:** queue T1 work; do not start new autonomy surfaces. Escalate to human authority only for exceptions that waive a trust gate.
2. **If T0 is green and quota is scarce:** prefer T1 items that increase *verified completed stories per dollar*, not raw dispatch count.
3. **If A and B disagree on a single ticket:** classify the ticket as *trust-enabling* (counts toward T0) or *throughput-consuming* (counts toward T1). Mixed tickets must be split.
4. **Major decisions** (spec approval, budget/release sign-off, charter changes) still block for `human_authority_role` — PM drafts and sequences; PM does not silently commit the human.

---

## What we will not do

- Expand headless fleet surface area while job-truth or receipt verification is regressing.
- Pause all product work indefinitely for speculative reliability rewrites with no acceptance metrics.
- Auto-repoint dispatch policy from a single calibration sample (requires N≥5 same-direction observations + PM proposal).

---

## Success criteria for this reconciliation

| Horizon | Metric |
|---|---|
| 2 weeks | T0 acceptance green; zero silent OK on dead/mismatched receipt jobs |
| 1 Named Release | ≥1 T1 product/autonomy cluster shipped with T0 still green |
| 1 release cycle | No Sev1 LIVE recurrence attributable to unverified job status or gh-write false success |

---

## One-line pitch

**Autonomy scales only on verified ground — grow the floor, then grow the fleet.**
