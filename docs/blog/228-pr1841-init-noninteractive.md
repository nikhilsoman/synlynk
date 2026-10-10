---
title: "R8 — Making synlynk init safe for CI"
date: 2026-09-28
series: "Building the OS for Multi-Agent Development"
post: 228
pr: "1841"
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts]
type: pr
---
# 227: Making `synlynk init` safe for CI

## Why this PR

Project initialization is often the first command run by a bootstrap script or a headless agent. The old `synlynk init` wizard could pause forever waiting for input, even when there was no terminal attached.

## What changed

`synlynk init --yes` and `synlynk init --non-interactive` now select safe defaults without calling `input()`. A non-terminal standard input is treated the same way, so CI jobs can invoke plain `synlynk init` safely. The command reports the selected defaults: no optional enrichment, an empty collaborator field, and the inferred industry (or its empty fallback).

Interactive terminal sessions keep the existing prompts and behavior.

## Verification

The test suite covers closed-stdin subprocess execution, the no-input-call guarantee, parser aliases, and the unchanged terminal flow.
