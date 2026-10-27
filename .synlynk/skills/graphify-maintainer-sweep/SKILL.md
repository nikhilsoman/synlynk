---
name: graphify-maintainer-sweep
description: Refresh the code graph after a merge, report orphan symbols, and record non-blocking mesh contract drift.
---

# Graphify Maintainer Sweep

## Charter Mandate & Overview
- **Primary Role:** `maintainer`
- **Mission:** Keep the code graph, warm traversal cache, and federated mesh current after merges, and report dead symbols without rewriting the ledger markdown.

## Available Tools & CLI Commands
- `synlynk maintainer sweep --refresh-graph`: Rebuild the graph for HEAD, rewrite the traversal cache, and rebuild `.synlynk/mesh.json` when the workspace lists two or more repos. Contract drift emits `MESH_CONTRACT_DRIFT` and still exits 0 when extract succeeds.
- `synlynk heal --cycles`: Report circular imports and file refactoring stories.
- `synlynk heal --orphans`: Report functions and classes with in-degree 0, excluding entrypoint chains, test files, and dunder names. Add `--stories` to file stories without editing `project-docs/todo.md`.
- `synlynk doctor`: Check that `graphify` is on PATH. Install only with `synlynk doctor --fix graphify`.

## Execution Protocol
1. Run `synlynk maintainer sweep` first and read the dry plan.
2. Run `synlynk maintainer sweep --refresh-graph` after a merged PR.
3. Run `synlynk heal --orphans` and file stories only when the report names a symbol worth tracking.
4. Run `synlynk doctor` when the graphify check fails. Do not install during a plain doctor run.

## Safety
Do not drop `--code-only`. Do not add document nodes to the code graph. Do not delete source files from an orphan report.
