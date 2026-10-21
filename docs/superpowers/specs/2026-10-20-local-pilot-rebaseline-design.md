# Local Harness Pilot Re-baseline Design

Date: 2026-10-20  
Status: Proposed; awaiting Nikhil Soman approval  
Parent epic: #2342  
Governing story: #2349  
Release home: v0.25.2 Fleet Capacity Recovery and Model Catalog (#2465)

---

## 1. Intent

Re-open a narrow, safety-first path for the Local harness (Ornith + Aider + oMLX) so it can contribute useful capacity without weakening containment, authority boundaries, or truthful operational evidence. The current promotion rule cannot be satisfied from the historical evidence population: the recorded pilot baseline is 8 accepted tasks out of 12 distinct eligible tasks, so a 30-job, 90% aggregate gate cannot be reached even with perfect remaining work.

This design preserves that historical record and introduces a separately named re-baseline cohort. It does not erase, edit, or silently combine the prior 12-task denominator. It authorizes no immediate traffic, configuration change, or promotion. The existing fail-closed setting (`local_pilot.enabled=false`) remains in force until the implementation plan, implementation, verification, and a separately recorded operational-resume decision are complete.

## 2. Why now

The v0.25.2 posture prioritizes safe fleet-capacity recovery. Frontier harnesses are constrained by subscription quotas, while the Local stack has strong bounded-task calibration evidence and no per-call subscription cap. Local capacity is valuable only if it is safely contained and if success is measured by independently verifiable evidence, not by a changed denominator.

The re-baseline therefore treats safety as a hard gate and usefulness as a separate measured property. An articulate answer can never offset a safety, isolation, credential, scope, receipt, host-execution, or rollback failure.

## 3. Goals

1. Keep every Local pilot dispatch within an isolated, credential-free, read-only execution boundary and preserve an auditable signed receipt.
2. Validate a new narrow cohort through five independent, real backlog tasks that are all accepted by an independent qualified frontier reviewer.
3. Keep the Local share at 20% during the new cohort and the following expansion-evidence cohort; no automatic percentage increase is allowed.
4. Separate hard safety outcomes from answer-quality outcomes in the ledger, status surfaces, and promotion decision.
5. Produce evidence sufficient for a later human decision about a proposed 35% cap, without granting the increase automatically.

## 4. Non-goals and anti-goals

This re-baseline does **not**:

- erase, recalculate, or represent the historical 8/12 baseline as evidence for the new cohort;
- enable Local immediately, change its cohort share, or authorize a 35% or 50% promotion;
- authorize production edits, refactors, dependency changes, architectural work, GitHub writes, review/merge authority, deploy authority, or daemon authority for Local;
- add models beyond the qualified Ornith model, increase concurrency above one, or permit host-side Aider execution;
- substitute a quality score or helpful answer for a safety violation;
- claim quota truth, general Local readiness, or Developer Preview readiness.

Failure would be any Local job escaping the isolated runner, seeing a credential-like path or user secret, running with an unqualified model, being accepted without a valid receipt, or being counted ambiguously across the old and new cohorts.

## 5. Operating boundary

The only eligible re-baseline execution profile is:

| Dimension | Required boundary |
|---|---|
| Harness and model | Local using the currently qualified Ornith model only |
| Agent path | Aider through the existing isolated Docker/Compose runner and local oMLX endpoint |
| Concurrency | One Local pilot job at a time |
| Allocation | 20% maximum of eligible work; no automatic expansion |
| Permissions | Read-only task scope; no GitHub credentials, user secrets, deploy credentials, or host-side execution |
| Network | Limited to the local oMLX endpoint required by the isolated runner |
| Admission | Auto-routing only; an explicit Local selection with a pilot class continues to fail closed |
| Evidence | Signed admission/runner receipt, exact scope, no changed or applied paths, outcome, task digest, and review result |

Existing preflight checks must continue to verify the authenticated local oMLX endpoint, qualified Ornith model, Aider availability, Docker availability, disabled-or-enabled pilot state as appropriate, and reservation consistency. An operational-resume decision cannot occur while these checks disagree.

## 6. Cohorts and decision rules

### 6.1 Historical cohort

The old cohort remains an immutable historical record: **8 accepted / 12 distinct eligible tasks**. It is reported beside the new cohort for context, but never blended into its denominator or used to satisfy its acceptance rule.

### 6.2 Re-baseline validation cohort

The initial cohort is five independent, real, low-risk backlog tasks, admitted one at a time. Each task must be a single-test summary or a tightly scoped code-path explanation. Each task must be accepted by the reviewer described in Section 7 after the automated checks pass.

All five must be accepted. Five of five validates only the shape of this new, narrow lane; it does not authorize a larger percentage or broader task class. Any quality rejection prevents advancement to the next stage and requires a human review of the task fit, answer rubric, and routing evidence before a new five-task validation cohort is proposed. Any hard safety failure pauses Local immediately under Section 8.

### 6.3 Expansion-evidence cohort

After the five-task cohort is accepted, Local remains at a 20% maximum while it collects ten consecutive accepted tasks using the same narrow classes and review regime. A result from the validation cohort does not count toward these ten tasks.

One quality rejection keeps the 20% cap and resets this ten-task cohort to zero. A hard safety failure pauses Local immediately. Only after ten consecutive accepted expansion-evidence tasks may the team bring a **proposal** for a 35% cap to a human approval gate. The evidence is eligibility to propose that change, not authorization to make it.

### 6.4 Ledger presentation

The pilot ledger and status output must show, at minimum:

- historical cohort: 8/12, clearly labelled as preserved historical evidence;
- validation cohort: accepted count out of 5, with task IDs and reviewer verdicts;
- expansion-evidence cohort: consecutive accepted count out of 10 and its current reset state;
- allocation cap, concurrency cap, pilot enablement state, and active effective model;
- separate safety, admission/receipt, and answer-quality outcomes for every sample.

No aggregate percentage may make the historical and re-baseline cohorts appear to be a single promotion denominator.

## 7. Task selection and independent review

Tasks come from the real repository backlog, not synthetic prompts. The dispatcher selects only the two allowlisted classes after normal eligibility and containment admission. The tasks must be independent: no answer may rely on or complete an earlier Local task.

Automated verification must check the signed receipt and task digest, runner outcome, exact allowed scope, absent changed/applied paths, empty worktree diff, correct qualified model, and isolation/credential constraints.

After automation passes, a qualified non-Local frontier harness reviews a short structured record: task intent, expected factual claims, Local answer, automated receipt results, and accept/reject rationale. Reviewer routing is automatic and capability based; it must exclude the task author and Local, record the selected reviewer, the selection rationale, and the reviewer verdict. A reviewer must have no Local write, deploy, or promotion authority.

The quality verdict is a factual acceptance decision for the requested narrow task, not a broad model-quality rating.

## 8. Fail-closed handling and recovery

A hard safety event includes any isolation, credential, scope, receipt, host execution, rollback, unqualified-model, or reservation/preflight integrity failure. On detection, the system must:

1. stop or refuse Local dispatches immediately and retain the affected receipt and diagnostic record;
2. set or retain `local_pilot.enabled=false` through the approved operational control path;
3. route the current and subsequent eligible work to a qualified frontier harness without permitting Local to be reselected later in resolution;
4. mark the event outside quality accounting and open or update the governing incident/story record;
5. require root-cause correction, independent verification, and a fresh human operational-resume decision before Local is considered again.

A normal quality rejection does not imply an unsafe system. It retains the 20% cap, records the rejection and reviewer rationale, and applies the cohort rule in Section 6. It must not be hidden, deleted, or relabelled as a safety pass.

## 9. Required implementation evidence

Before a human can make an operational-resume decision, the implementation must demonstrate:

1. positive and negative automated tests for every boundary in Section 5;
2. tests that prove old and new cohort denominators cannot be accidentally merged, including status/ledger output;
3. tests for five-of-five validation advancement, expansion reset after one quality rejection, and immediate safety pause;
4. tests that the 35% state is only proposal-eligible after ten consecutive expansion-evidence acceptances, never automatic;
5. tests for automatic reviewer selection, non-Local/non-author exclusion, selection-reason recording, and verdict persistence;
6. a fresh operational reconciliation showing endpoint, credentials, `local_pilot` setting, model qualification, isolated runner, and reservations agree;
7. five live accepted receipts only after the human authorizes the pilot to resume. Those live receipts are evidence of the resumed cohort, not a prerequisite that can be manufactured while the pilot is disabled.

## 10. Approval gates and ownership

This design requires three distinct decisions:

1. **Design approval (now):** Nikhil approves this scope and decision model.
2. **Operational-resume approval (later):** after a committed implementation, independent review, and operational reconciliation, Nikhil authorizes the disabled pilot to resume at the 20%/one-concurrent boundary.
3. **Expansion approval (later):** after the ten consecutive expansion-evidence acceptances, Nikhil may approve or reject a separate 35% proposal. Absence of a decision means 20% remains in force.

The parent epic #2342 and story #2349 remain the canonical tracking records. Each cohort result, pause, resume decision, and later proposal must be posted there with its receipt and any related PR/incident links.

## 11. Builder choices left open

The builder may choose the precise storage schema, command/status presentation, and test fixture structure, provided all information and behavior required above are preserved. The builder may not broaden the task classes, model roster, authority surface, allocation, concurrency, or safety response without a new approved design.

