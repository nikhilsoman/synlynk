---
title: "Issue #1837 - Scheduled Workflows Follow the Harness CLI"
date: 2026-09-28
series: "Building the OS for Multi-Agent Development"
post: 227
issue: "#1837"
pr: 1842
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, workflows, reliability]
type: issue
---
# Scheduled Workflows Follow the Harness CLI

Issue #1837 fixes two scheduled workflows that still called the retired
`synlynk agent run` command. Both now use `synlynk harness run` with the
existing `.agents/support.json` and `.agents/workspace-lifecycle-nudge.json`
profiles.

The Support Engineer workflow also skips cleanly, with an explicit message,
when `ANTHROPIC_API_KEY` is not configured. This keeps scheduled CI honest:
missing credentials are reported as a skipped integration rather than replaced
with a fake secret.

## What This Achieved on the Path to Autonomy

Automation now follows the current CLI vocabulary, and each scheduled target
is backed by a checked-in runtime profile.
