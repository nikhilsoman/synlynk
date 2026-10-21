# Local Harness Pilot Re-baseline Operations

This runbook governs the disabled-by-default Local pilot re-baseline. It is
associated with parent epic #2342 and governing story #2349. The canonical
SQLite ledger is the source of truth for cohort evidence; generated roadmap or
todo files do not change pilot state.

## Status and safe interpretation

Use `synlynk local pilot status --json` for machine-readable state or
`synlynk local pilot status` for the concise operator view. The command is
read-only: it neither enables Local nor dispatches work. It reports every
historical safety failure as well as failures in the current authorized epoch,
the latest authorization ID/state/watermark, and whether the enabled runtime
still matches its signed 20%/one-concurrent target.

Read the three denominators separately:

- Historical evidence is the preserved 8/12 record. It is context only and is
  never added to either re-baseline denominator.
- Validation is accepted tasks out of 5. All five independently accepted,
  low-risk samples are required before expansion evidence can begin.
- Expansion evidence is consecutive accepted tasks out of 10. A quality
  rejection resets this count to zero but retains the 20% cap; a safety failure
  pauses the pilot immediately.

The status output also reports the fixed 20% cap, one-job concurrency boundary,
the qualified Ornith model, enabled/paused state and reason, and whether the
ledger is eligible to make a 35% proposal. Endpoint, credentials, model
qualification, isolated-runner, and reservation disagreements appear as
operational mismatches. These values are statuses only: the command never
prints a credential, authorization header, or secret-bearing response.

## Approval gates

1. **Design approval:** Nikhil approved the re-baseline design and its narrow
   read-only boundary.
2. **Operational-resume approval:** after committed implementation,
   independent review, and a fresh reconciliation of endpoint, credentials,
   model qualification, isolated runner, and reservations, only Nikhil's later operational-resume approval authorizes live samples.
3. **Expansion approval:** ten consecutive accepted expansion samples make a
   35% proposal eligible for Nikhil's decision. A 35% proposal is never automatic;
   without that decision the 20% cap remains in force.

Merging the implementation branch leaves `local_pilot.enabled` disabled, so no live work is authorized by code merge alone.

## Operational-resume ceremony and recovery

The only normal re-enable path is `synlynk local pilot resume --remediation-ref
<reference> --verification-ref <reference>`. It requires an interactive input
and output terminal plus the exact typed confirmation. `--yes`, redirected
input, inherited shell defaults, and blank audit references are not approval.
Before prompting, Synlynk displays the current pause/failure state, selected
qualified Ornith model, fixed 20%/one-concurrent target, and the complete
preflight receipt.

The local host Ed25519 key signs the durable authorization record and makes it
tamper-evident; it is not proof that a particular human is Nikhil. The command
requires the human ceremony above and never accepts a caller-supplied
`approved-by` value as identity proof. Preflight requires a disabled exact
target configuration, qualified live Ornith model, usable isolated
Docker/Compose runner, endpoint/authentication health, readable migrated
ledger, no Local reservation, and no reconciliation debt. It creates no Local
job or dispatch.

Activation is staged: `activating` authorization, atomic config replacement,
then `active` authorization after a fresh check. `activating`, `failed`, and
`revoked` records never admit work. If status or a later resume finds a
stranded `activating` record, it terminalizes it as failed and disables Local;
a matching config file alone never restores authority. A safety pause revokes
the active authorization before disabling config. Dispatch therefore requires
both the enabled exact runtime and a matching active signed authorization; any
uncertainty or drift goes to the selected frontier fallback.

The control lock serializes that staged activation, a safety pause, and the
final Local reservation/runner launch. Immediately before taking the sole
slot, dispatch reads the active signed authority, epoch safety state, exact
workspace runtime, local-agent one-concurrent setting, and signed
preflight-selected model again. A changed, revoked, or merely differently
qualified model is refused before a Local reservation or runner is created.

## Evidence and tracking procedure

For every cohort result, safety pause, operational-resume decision, or 35%
proposal decision:

1. Capture the canonical ledger status and the relevant signed admission and
   runner receipt, preserving exact scope, model, and reviewer evidence.
2. Attach a concise summary and links to the evidence on #2342 and #2349.
   Include related PR or incident links where applicable.
3. For a pause, record the safety reason separately from any answer-quality
   verdict and leave Local disabled until root-cause correction and independent
   verification are complete.
4. For a resume request, attach the fresh operational reconciliation and wait
   for Nikhil's explicit operational-resume approval before admitting any live
   sample.
5. For an expansion request, attach the ten-sample consecutive-acceptance
   evidence and wait for Nikhil's explicit expansion decision; do not change
   allocation based on proposal eligibility alone.

This procedure does not grant GitHub, deploy, review, merge, daemon, host-Aider,
or promotion authority to Local or its factual reviewer.
