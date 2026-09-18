---
title: "PR #1179 - Capability Reassessment Gets a Durable Cadence"
author: "Nikhil Soman"
date: 2026-09-18
pr: "#1179"
version: "0.21.0"
tags: [capability, cadence]
---

# PR #1179 - Capability Reassessment Gets a Durable Cadence

The harness baseline is useful only while it is kept current. This change makes
the existing `synlynk capability sweep` command part of a durable operational
loop: state.db records the last successful sweep and the dispatch count at that
point, while `synlynk doctor` and `synlynk status` warn after 25 jobs or 30 days.

The cadence check is deliberately observational. It does not run live probes or
re-rate harnesses from CI. A maintainer explicitly runs the paid calibration
sweep, and only a completed sweep advances the recorded timestamp.

Verification covers the never-run, under-threshold, and over-threshold cases
with focused pytest runs. This closes the recurring reassessment gap tracked by
#1179 while preserving the existing cost guardrail and independent verification
flow of the sweep itself.
