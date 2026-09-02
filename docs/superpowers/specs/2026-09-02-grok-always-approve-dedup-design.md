# Design: Deduplicate Boolean CLI Flags During Dispatch

Date: 2026-09-02
Issue: #1327

## Problem

Grok declares `--always-approve` as a required dispatch flag. Permission
translation also emits that flag when the resolved permissions include shell
or test execution. The current assembly path concatenates both sources,
producing `--always-approve --always-approve`; Grok rejects the duplicated
boolean option before launching the task.

## Decision

Deduplicate known boolean CLI flags after baseline, override, permission, and
harness-specific flags have been assembled. Deduplication is stable: the first
occurrence remains in its original position and later occurrences are removed.
Only boolean flags are eligible. Repeatable option/value pairs such as
`--allow <rule>` and `--output-format <format>` remain untouched because their
repetition can carry meaning or a distinct value.

The final normalization applies to every harness so future combinations of
static and permission-derived flags receive the same protection. Grok’s
`--always-approve` case is the regression target.

## Verification

- Unit coverage asserts that a Grok dispatch assembled with the required
  baseline flag and shell-derived permission flag contains exactly one
  `--always-approve`.
- Run `pytest tests/test_agent_cli.py -k 'fixdispatch_deduplicate_boolean_cli_flag' -v`.
- Run the full `pytest tests/` suite.

## Non-goals

- Changing Grok permission semantics or its baseline declaration.
- Deduplicating repeatable flags or rewriting option/value ordering.
