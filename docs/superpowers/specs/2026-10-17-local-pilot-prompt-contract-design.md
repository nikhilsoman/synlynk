# Local Pilot Prompt Contract — Design

Status: approved by Nikhil on 2026-10-18.

## Problem

The Local Pilot admits bounded tasks such as `test_summary` and other scoped
read-only summaries. Dispatch prompt construction currently appends a generic
`## How to Verify` section whenever a story is present and the repository has a
`tests/` directory. That section asks the agent to run pytest, and may include
multiple test files unrelated to the assigned read-only summary.

Evidence from the 20% Ornith pilot:

- `job-c1c71753` was explicitly instructed to summarize one test in two bullets,
  not execute tests, and not modify files. Its prompt nevertheless included a
  generated multi-suite pytest command. The answer added that command and
  claimed it was “now running” verification. The runner receipt records
  `completed_read_only`, exit 0, no changed/applied paths, and the worktree diff
  is empty; no pytest process remained. The answer was not accepted.
- `job-9d8b210f` also received the generated verification section but returned
  the requested two-bullet summary. This shows inconsistent behavior, not a
  guaranteed side effect.
- `synlynk/dispatch.py` calls `_verify_contract_for_story()` for story-linked
  tasks without checking whether a verified Local Pilot receipt is present.

The generic verification contract is useful for implementation work, but it
conflicts with task-specific read-only scope and reduces pilot answer
reliability. The conflict is visible in the persisted dispatch prompt, not
merely inferred from the model response.

The fixed Local Pilot runner already distinguishes permissions: summary and
diagnosis classes are passed as Aider `--read` paths; documentation and
mechanical edit classes are passed as `--file` paths. It also disables
auto-tests and shell-command suggestions. None of the six current classes
grants a general-purpose pytest command, so the generic verifier is outside
their current execution contract.

## Goals

- Keep read-only Local Pilot tasks read-only in both the task and generated
  prompt contract.
- Prevent broad or guessed pytest commands from being injected into pilot
  prompts that are not authorized to execute tests.
- Preserve the existing verification contract for ordinary implementation
  dispatches.
- Make the pilot class / explicit verification capability—not a guess from
  task wording—the source of prompt policy.
- Preserve the isolated runner receipt and changed-path checks as the evidence
  for bounded pilot execution.

## Non-goals

- Changing the local model allowlist, dispatch percentage, or model-selection
  behavior.
- Giving Aider a shell or test-execution capability in this change.
- Reclassifying pilot samples or changing acceptance thresholds/denominators.
- Changing normal developer dispatch verification behavior.

## Design options

1. **Suppress generic verification for every Local Pilot dispatch.** Simple and
   fail-closed; pilot receipts remain the runner-level execution evidence.
   Editing classes would need a separately authorized verification workflow.
2. **Make verification class-aware.** Suppress command-oriented verification
   for read-only classes, and allow it only for classes with explicit, bounded
   verification authority. This is more expressive but requires a precise
   capability contract for edit and diagnosis tasks.
3. **Only change the appended section’s wording.** Tell the model to ignore
   pytest instructions for read-only tasks. This is small but leaves
   contradictory instructions in the same prompt and relies on model
   precedence; it is not recommended.

## Approved direction

Prefer option 1 for the current pilot: when an authenticated Local Pilot
receipt is present, omit the generic `## How to Verify` section for all six
current pilot classes. Keep the existing normal-dispatch behavior unchanged.
Bounded test execution is a separate future capability, not part of the six
current pilot classes. `test_diagnosis` means analyzing existing logs/results;
it does not authorize running or rerunning tests. If test execution is to be
part of the local pilot, add an explicit class/capability with a bounded
command allowlist, timeout, output receipt, and isolation contract before
enabling it. Do not imply that capability through the generic implementation
verifier.

This uses dispatch's already-verified Local Pilot receipt and its
`pilot_class`; it does not infer read-only authority from free-form task text.
No prompt text should suggest running tests unless an explicitly authorized
test-execution capability is introduced.

## Acceptance criteria

- A pilot prompt built with a valid Local Pilot receipt contains the exact task
  and task-receipt digest but no generic pytest command or “How to Verify”
  section.
- A normal implementation dispatch still receives the existing
  `## How to Verify` section.
- Regression tests cover the boundary using a valid pilot receipt and verify
  that normal dispatch behavior is unchanged.
- A bounded isolated `test_summary` sample returns only the requested summary,
  does not claim to execute tests, and has no changes outside the receipt.
- Receipt, task digest, scope, and empty diff are independently checked before
  counting a sample.
- No local-pilot share increase is included; keep at 20% or disabled until the
  existing gate is satisfied.

## Deferred decisions

- A possible future `test_execution` class needs a separate design covering
  command allowlists, scope, timeout, network, and output receipts.
- Pilot status reporting remains subject to the available approved tracking
  mechanism; this prompt-contract change performs no GitHub writes.

## Approval record

Nikhil approved the two choices above with “go ahead” on 2026-10-18. This
committed spec is the prerequisite for a separate implementation plan.
