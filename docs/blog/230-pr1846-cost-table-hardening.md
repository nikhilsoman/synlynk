---
title: "Issue #1846 — Keeping the Cost Ledger a Valid Markdown Table"
date: 2026-09-29
series: "Building the OS for Multi-Agent Development"
post: 230
pr: "TBD"
issue: "1846"
status: draft
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, reliability, costs]
type: story
---
# Keeping the Cost Ledger a Valid Markdown Table

The cost ledger is stored canonically in SQLite and rendered into `costs.md` for humans and tools. That projection has to remain structurally valid even when historical text is messy. A model label or note containing a newline used to create a new physical line; a literal pipe then changed the apparent column count for the row and every reader after it.

The generator now treats free-text model and notes values as Markdown cells: line breaks become spaces and literal pipes are escaped. The regression test seeds both hazards and confirms that the following row still remains a complete table row.

We also made one bounded pass through `extract_model_version`, `update_costs`, and `cmd_cost_log`, plus their immediate callers. That review did not identify a defensible path that would turn an exception string or traceback fragment into a model value. The historical producer of the corrupted value remains an open question; this change therefore hardens the projection without claiming an unverified root-cause fix.

Refs issue #1846.
