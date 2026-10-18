# Local Pilot Prompt Contract — Implementation Plan

Spec: `docs/superpowers/specs/2026-10-17-local-pilot-prompt-contract-design.md`

## Objective

Ensure a valid, authenticated Local Pilot receipt suppresses the generic
story-level `## How to Verify` section, while ordinary implementation dispatches
continue to receive the existing verification instructions.

## Scope

- Change prompt assembly in `synlynk/dispatch.py` only after receipt validation
  has completed. Do not infer Local Pilot status from task wording or caller
  parameters that have not passed receipt verification.
- Keep `_verify_contract_for_story()` and normal dispatch semantics unchanged.
- Add dispatch-level regression coverage for a signed pilot receipt and a
  normal implementation dispatch. Where feasible, capture the actual prompt
  passed to the adapter/runner rather than testing only a helper predicate.
- Do not change runner permissions, pilot classes, model qualification,
  admission/share settings, or acceptance denominators.
- Keep both pilot runtime configurations disabled. Do not dispatch a pilot
  sample in this implementation task.

## Implementation steps

1. Inspect the full `dispatch_agent()` flow and existing prompt/adapter test
   fixtures to confirm receipt validation precedes prompt assembly.
2. Gate the generic verification-section generation on the absence of a
   verified Local Pilot receipt. Preserve compatibility with the existing
   `_verify_contract_for_story` call signatures and error behavior for normal
   dispatches.
3. Add tests proving that a valid signed pilot receipt produces no generic
   verification section, and that a normal story-linked implementation still
   gets it. Include a forged receipt regression if coverage does not already
   prove the prompt path cannot be reached with one.
4. Run the focused dispatch tests, then the full relevant test module and
   formatting/lint checks used by the repository for changed Python files.
5. Inspect the final diff, `git diff --check`, branch identity, and pilot
   configuration to verify no unrelated edits or enablement occurred.

## Acceptance criteria

- Valid Local Pilot receipt: final dispatch prompt contains no generic
  `## How to Verify` section and no generated pytest command.
- Normal implementation dispatch: current generic verification section remains
  present and unchanged.
- Forged/replayed receipt is rejected before prompt assembly and cannot bypass
  normal policy.
- Focused regression tests and repository checks pass, or any unrelated
  pre-existing failures are documented precisely.
- No pilot dispatch, production routing change, model/share change, GitHub
  write, or merge is performed as part of implementation.

## Risks and controls

- A broad condition could suppress useful verification for ordinary tasks;
  test the normal-dispatch path explicitly.
- A caller-supplied but invalid receipt must not suppress verification; keep
  the gate downstream of receipt authentication and admission validation.
- Prompt-level suppression does not authorize test execution. The Local Pilot
  runner's existing execution restrictions remain unchanged.
