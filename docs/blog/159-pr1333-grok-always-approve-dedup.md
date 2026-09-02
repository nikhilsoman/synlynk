---
title: "PR #1333 — Deduplicating Grok's Boolean Dispatch Flags"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 159
pr: "#1333"
merged: status open
---

## The Broader Goal at the End of the Previous PR

The previous fleet-parity work made Grok a first-class dispatch target, but
headless execution still depended on a precise composition of baseline and
permission-derived CLI flags.

## Strategic Shifts in This PR (if any)

No strategic shift was required. This is a reliability hardening change at the
dispatch boundary.

## What This PR Shipped

Issue #1327 exposed that Grok could receive `--always-approve` twice: once from
its required baseline flags and once from permission translation for shell or
test execution. The launch then failed before the task started.

Dispatch now performs stable deduplication for known boolean CLI flags after
all baseline, override, permission, and harness-specific flags are assembled.
Repeatable options and option/value pairs remain unchanged. Regression tests
cover both the actual Grok launch command and the focused helper behavior.

## What This Achieved on the Path to Autonomy

Permission policy can now be composed from multiple sources without turning a
valid headless Grok dispatch into an invalid command line. This makes automatic
task allocation more resilient to overlapping defaults and grants.

## Strategic Note: The Goal at the End of This PR

With duplicate boolean options normalized centrally, future fleet parity work
can add harness defaults and permission translations independently while
keeping the final launch contract valid.

## Related Docs

- Design Spec: `docs/superpowers/specs/2026-09-02-grok-always-approve-dedup-design.md`
- Implementation Plan: `docs/superpowers/plans/2026-09-02-grok-always-approve-dedup.md`
