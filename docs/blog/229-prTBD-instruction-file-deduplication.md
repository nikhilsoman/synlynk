---
title: "R9 — One Canonical Instruction Protocol"
date: 2026-09-29
series: "Building the OS for Multi-Agent Development"
post: 229
pr: "1843"
issue: "story-025c857c"
status: draft
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, instructions, performance]
type: story
---
# R9 — One Canonical Instruction Protocol

## The Cost of Helpful Duplication

synlynk's four harness instruction files had gradually become copies of the same operating manual. Even though `_build_templates` assembled the text from shared Python blocks, `synlynk init` still wrote every block into `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `GROK.md`. Reading all of them at session start meant paying for the same protocol repeatedly.

## One Source, Four Adapters

R9 makes `AI_INSTRUCTIONS.md` the canonical home for the shared protocol: session lifecycle, dual-mode operation, worktree discipline, live-issue handling, four-document maintenance, GitHub Projects workflow, and the harness SOPs. Each tool-specific file now keeps its identity, attribution, branch prefix, and a short pointer to that canonical file.

The fenced synlynk markers remain unchanged. That preserves drift detection and lets existing repositories update their managed sections without losing surrounding content.

## What We Verify

Tests assert that every harness file retains its identity metadata, stays substantially smaller than the canonical file, and no longer carries duplicate shared sections. The canonical file is checked for the complete protocol, while initialization and instruction drift tests continue to exercise the same fenced update path.

Refs story-025c857c and goal-079e2f37.
