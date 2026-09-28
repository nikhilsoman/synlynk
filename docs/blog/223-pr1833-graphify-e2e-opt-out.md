---
title: "Issue #1833 — Keeping Dispatch E2E Tests Focused"
date: 2026-09-28
series: "Building the OS for Multi-Agent Development"
post: 223
issue: "#1833"
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, testing, performance]
pr: "TBD"
type: issue
---
# Keeping Dispatch E2E Tests Focused

The dispatch end-to-end test was paying the cost of a full Graphify AST extraction in every CLI subprocess. That work is valuable in production, but it is unrelated to proving that a job is created successfully.

Issue #1833 adds a narrow `SYNLYNK_SKIP_GRAPHIFY_EXTRACT=1` opt-out. The shared E2E CLI fixture sets it for subprocesses, while unit tests still verify both paths: the opt-out returns immediately, and the default path continues to install/run Graphify and process its result.

This keeps the black-box test focused on dispatch behavior without weakening production behavior or the dedicated extraction tests.
