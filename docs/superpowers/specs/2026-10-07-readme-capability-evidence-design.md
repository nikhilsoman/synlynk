# README Capability Evidence Copy Design

## Status

Draft for Nikhil's approval. No implementation plan or copy change should be made until this spec is committed and approved.

## Problem

The README describes capability-aware harness allocation but does not state the evidence threshold or make clear that the current allocation remains an interim default until enough merged work exists for the relevant task type. Readers can interpret the copy as a measured claim that the available evidence does not support.

## Goals

- Make the README accurately describe the current routing policy.
- State that empirical allocation requires at least five completed, merged jobs for the specific harness and task type.
- State that the existing policy remains the interim allocation when that threshold is not met.
- Link readers to the policy evidence that defines the threshold and current behavior.
- Keep the correction limited to README claims; the policy and measurement implementation are tracked separately by #1993.

## Proposed README wording

> Synlynk uses empirical harness allocation only after a harness has at least five completed, merged jobs for the relevant task type. Until then, routing follows the documented interim policy. See the [empirical capability policy](docs/blog/244-chore-empirical-capability-policy.md) and [routing policy](.synlynk/policy.json).

The implementation should place this text next to the README's existing harness allocation description and remove any nearby wording that implies a mature per-task capability ledger already exists. Do not add claims about sample counts or winning harnesses without current report evidence.

## Scope

- Inspect README text and linked README-level product copy for statements that imply empirical routing is already proven.
- Update only the affected copy and evidence links.
- Do not change routing behavior, policy thresholds, capability reports, or site content unless an equivalent claim is found there and included in the approved implementation plan.

## Acceptance criteria

- README copy states the five completed-and-merged job minimum per harness and task type.
- README copy says the documented interim policy applies below that threshold.
- The evidence links resolve to the maintained policy documentation and `.synlynk/policy.json`.
- No adjacent README wording overstates the current empirical evidence.

## Verification

- Review the rendered Markdown and verify relative links resolve from the repository root.
- Search README and linked product copy for remaining claims that imply empirical routing is already proven.
- No behavior tests are needed because this is documentation-only.

## Dependencies

- #2098
- The empirical evidence rules in `docs/blog/244-chore-empirical-capability-policy.md` and `.synlynk/policy.json`
