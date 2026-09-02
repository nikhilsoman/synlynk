---
title: "Issue #937 — Making Review Dispatches Read-Only at the Repository Boundary"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 157
pr: "#1328"
merged: status open
---

## The Problem

A code review needs to read the checkout and may need to post findings on
GitHub, but it should not edit the PR files it is reviewing. Review dispatches
already selected a read-oriented role, yet caller-supplied write grants could
restore `write:src/` or `write:docs/`. Codex GitHub-write dispatches also used a
writable workspace sandbox.

## What This PR Shipped

Review permission resolution now strips every `write:*` capability after all
defaults and explicit grants are merged. Codex review jobs retain the network
capability needed for GitHub review submission while using a read-only
workspace sandbox. Non-review dispatch behavior is unchanged.

## What This Achieved on the Path to Autonomy

The review boundary is now enforced by dispatch policy and harness sandbox
selection, reducing the chance that an evaluator mutates the artifact it was
asked to assess.

## Strategic Note: The Goal at the End of This PR

Keep review, implementation, and publication capabilities distinct so every
automated action has the smallest filesystem authority needed for its job.
