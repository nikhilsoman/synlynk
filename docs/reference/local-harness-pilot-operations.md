# Local Harness Pilot Re-baseline Operations

This runbook governs the disabled-by-default Local pilot re-baseline. It is
associated with parent epic #2342 and governing story #2349. The canonical
SQLite ledger is the source of truth for cohort evidence; generated roadmap or
todo files do not change pilot state.

## Status and safe interpretation

Use `synlynk local pilot status --json` for machine-readable state or
`synlynk local pilot status` for the concise operator view. The command is
read-only: it neither enables Local nor dispatches work.

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
