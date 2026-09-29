---
title: "R14 — One Migration Helper for Daemon Job Schemas"
author: "Nikhil Soman"
date: 2026-09-29
series: "Building the OS for Multi-Agent Development"
post: 205
pr: "TBD"
version: "0.23.0-dev"
tags: [database, dispatch, maintenance]
status: open
---

# 205 — One Migration Helper for Daemon Job Schemas

Legacy daemon databases are a compatibility surface, but compatibility code should not multiply every time a column is added. R14 (story 1194) consolidates six near-identical lazy migrations into one helper that reads `daemon_jobs` once and adds any missing columns from a caller-provided definition map.

The dispatch and reconciler paths now retain their existing column-specific context while sharing the same no-op behavior for absent tables, existing columns, and transient migration errors. The vestigial `schema_version` table was also retired after a repository-wide search found no reads or writes against it; unrelated JSON and YAML `schema_version` metadata remains unchanged.

The result is a smaller migration surface that is easier to extend without creating another ad-hoc helper.
