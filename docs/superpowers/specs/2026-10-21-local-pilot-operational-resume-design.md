# Local Pilot Operational Resume Control Design

Date: 2026-10-21  
Status: Proposed; awaiting Nikhil Soman approval  
Parent epic: #2342  
Governing story: #2349  
Release home: v0.25.2 Fleet Capacity Recovery (#2465)

---

## 1. Intent

Correct the Local pilot re-baseline implementation so a past hard safety
failure remains permanent evidence and causes an immediate pause, but does not
make a later, explicitly approved recovery impossible. The correction adds a
dedicated operational-resume command. It records the recovery decision,
performs a fresh preflight, and enables only the existing 20% / one-concurrent
validation lane. It does not enable Local now.

This is a repair to the approved 2026-10-20 Local pilot re-baseline design,
not a new promotion path. The present configuration remains disabled until a
future operator deliberately invokes the command after implementation,
independent review, remediation, and fresh preflight.

## 2. Problem being corrected

`evaluate_rebaseline()` currently totals every failed safety verdict in the
append-only validation and expansion cohorts. That correctly pauses an active
pilot, but also means a historical failure can never be recovered from, even
when the original design requires a root-cause correction, independent
verification, and a fresh human resume decision.

Safety evidence must not be edited, deleted, or reclassified. Recovery needs
to be a separate, durable fact that names the exact point in the immutable
ledger from which future safety failures again block admission.

## 3. Decisions made

Nikhil selected:

1. an explicit CLI operational-resume record; and
2. atomic re-enablement at the existing 20% share and one-concurrent cap only
   after preflight passes.

The existing Synlynk decision signature is a signature by the host's local
Ed25519 identity key. It can make the record tamper-evident and identify the
local key, but it does **not** prove the human operator is Nikhil. This change
therefore enforces an interactive, explicit human approval ceremony; it must
not claim cryptographic Nikhil-only authorization. A future human-identity
provider or verified key registry would be a separate authorization project.

## 4. Command and authority boundary

Add `synlynk local pilot resume` as the only normal path that can turn the
pilot back on after a hard safety pause. The command must:

- require an interactive terminal, an explicit confirmation phrase, a
  non-empty remediation reference, and a non-empty independent-verification
  reference;
- refuse `--yes`, stdin piping, inherited shell defaults, or any invocation
  that cannot establish an interactive confirmation;
- display the exact current pause/failure state, qualified model, requested
  share (20%), concurrency (one), and preflight result before confirmation;
- sign the canonical approval payload with the existing local identity key;
  refuse to resume if that key is unavailable rather than creating an unsigned
  authority record;
- never accept a caller-provided `approved-by` value as proof of identity;
- refuse if any Local reservation is active or if any eligible preflight check
  fails; and
- never broaden task classes, model qualification, permissions, share, or
  concurrency.

The command is an operational control, not a dispatch mechanism. It creates
no Local job and it does not grant Local GitHub-write, review, deploy, daemon,
or general implementation authority.

## 5. Durable state and evaluation

Add an append-only `local_pilot_resume_authorizations` ledger table. Each event stores
an event ID, timestamp, canonical signed approval payload and digest, the
current disabled configuration fingerprint, remediation and independent-
verification references, and a safety watermark: the greatest immutable
`local_pilot_evidence` rowid visible when preflight passed. The row also
stores an activation state: `activating`, `active`, `revoked`, or `failed`,
with immutable activation/revocation timestamps and reasons.

Safety evidence stays in `local_pilot_evidence` and is never changed. Status
must report both:

- `historical_safety_failures`: every failed evidence row; and
- `active_epoch_safety_failures`: failed rows after the latest *active*
  resume watermark.

`evaluate_rebaseline()` must fail closed as follows:

- no active authorization after a historical safety failure ->
  `operational_resume_required`, no admission;
- a safety failure after an active authorization watermark ->
  `hard_safety_failure_requires_pause`, no admission;
- an active authorization with no later hard safety failure -> evaluate the
  normal validation/expansion quality rules at the fixed 20% cap, using only
  evidence after that authorization watermark.

The watermark creates a new evidence epoch. Every validation/expansion count,
including accepted, rejected, pending, and consecutive acceptance counts,
must be calculated only from the active epoch. A pre-incident four-of-five
validation result must never be combined with a post-recovery sample.

The status surface must show the latest authorization ID, activation state, watermark,
preflight receipt digest, current disabled/enabled configuration, and both
safety counters. It must never make an old failure disappear.

## 6. Preflight and atomic activation

The resume command runs the existing Local runtime checks and adds explicit
checks for: `enabled=false` before activation, exact 20% configuration target,
one-concurrent reservation availability, qualified Ornith model, a usable
Docker/Compose runner (rather than merely a compose file and `docker` on
`PATH`), required local endpoint/authentication health, a readable/migrated
pilot ledger, zero running Local jobs, and no pending Local evidence or
terminal-reconciliation debt.

Because SQLite and `.synlynk/workspace.json` cannot be one ACID transaction,
the command uses a recoverable two-phase state machine:

1. Write a signed `activating` authorization within a SQLite transaction with the
   immutable safety watermark and the successful preflight receipt.
2. Atomically replace the workspace configuration with `enabled=true`,
   `share=0.20`, and a one-concurrent control value through the owned config
   writer. Any write failure leaves the authorization non-active and admission
   blocked.
3. Re-check that no newer safety failure, Local job, or conflicting
   authorization exists, then mark that exact authorization `active` in a
   SQLite transaction. Admission requires both an active authorization and a
   matching enabled configuration.

If the process crashes between steps, admission remains fail-closed:
`activating` cannot route work. The next status/resume invocation must reconcile
the incomplete authorization: it may mark it `failed` if configuration is
disabled, and must require re-running preflight plus a fresh explicit human
confirmation before activation. The implementation must never infer approval
from a matching configuration file alone.

Existing automatic pause handling remains authoritative: it disables the
configuration first and revokes any active authorization in the same serialized
control flow. Any later safety failure is therefore unacknowledged, and a new
resume authorization is required.

## 7. Scope of related correction

Fix the Local frontier fallback call to retain the original `pr` argument.
This is a narrow, behavior-preserving context propagation repair discovered in
the final review. It belongs in the same corrective change because it is in
the Local rejection/recovery path, but it has no bearing on operational-resume
authority.

## 8. Required tests and acceptance evidence

The implementation must test:

1. a historical failure pauses immediately and is still displayed after a
   later successful resume;
2. an old failure blocks admission until a signed, active resume authorization;
3. a failure after the resume watermark pauses again and revokes the authorization
   for admission;
4. non-interactive, unconfirmed, unsigned, incomplete-reference, failed
   preflight, wrong-share, active-reservation, and unqualified/isolation
   attempts leave config disabled and do not activate an authorization;
5. successful preflight plus confirmation produces a signed event and enables
   exactly 20%/one-concurrent, with no dispatch produced;
6. every crash boundary (`activating`, config write, activation) remains
   fail-closed and is reconciled deterministically;
7. an active epoch resets all validation and expansion denominators, so no
   pre-incident quality result advances the recovered pilot;
8. immutable evidence and authorizations cannot be altered, deleted, or hidden
   by recovery records;
9. a pause racing a resume cannot leave an active authorization with an enabled
   configuration; and
10. a Local fallback preserves `pr` context.

The final review must verify the focused Local pilot, migration, dispatch, and
CLI tests, plus the corrected broad suite findings. No live Local work is
authorized merely by merging this change; the later operator invocation is the
separate operational-resume decision.

## 9. Non-goals

This amendment does not enable Local now, change its current disabled config,
add a verified Nikhil identity system, change the 20% share or one-concurrent
cap, expand eligible task classes, or grant any additional authority. It also
does not auto-resume after a safety event and does not permit historical safety
evidence to be overwritten.

