# Design Spec: Read-Only Repository Scope for Review Dispatches (#937)

- **Issue:** [#937](https://github.com/nikhilsoman/synlynk/issues/937)
- **Date:** 2026-09-02
- **Status:** APPROVED

## Context

Review jobs inspect PR files and may need GitHub access to publish a review.
They must not receive broad `write:src/` or `write:docs/` capabilities that let
the reviewing harness alter the checkout under review. Previously, explicit
grants could reintroduce those scopes after the `review` role was selected, and
Codex GitHub-write dispatches selected a writable workspace sandbox.

## Design

1. Add a `read_only` mode to effective permission resolution. When enabled,
   remove every `write:*` permission after defaults, grants, and revokes are
   combined. This makes the rule apply equally to role defaults and caller
   supplied grants.
2. Use that mode for `task_type="review"` dispatches. Reviews retain read,
   test, shell, and GitHub-network capabilities needed by the operation, but
   never receive broad repository write scopes.
3. For Codex reviews, force `-s read-only`. If GitHub network access is also
   required, use the read-only network sandbox configuration rather than the
   workspace-write configuration.

## Non-goals

This does not change permissions for implementation, test, refactor, or other
non-review task types. It also does not restrict the external GitHub review
submission itself; only the target repository filesystem remains read-only.

## Verification

Regression tests cover explicit write grants and Codex review dispatch flags.
Run `pytest tests/` plus the issue-specific `tests/test_agent_cli.py` selection.
