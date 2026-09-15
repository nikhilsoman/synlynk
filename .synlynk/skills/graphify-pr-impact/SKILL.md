---
name: graphify-pr-impact
description: Analyze PR git diffs to map modified symbols, calculate upstream caller blast radii, verify test coverage attestation, and enforce merge gates.
---

# Graphify PR Impact

## Charter Mandate & Overview
- **Primary Role:** `verifier` / `qa`
- **Supported Harnesses:** Codex (default), Claude / Agy (fallbacks)
- **Mission:** Guard system reliability, determine exact blast radii of code modifications, verify regression test coverage for all transitive callers, and enforce automated merge gates.

Code review must not rely on guesswork or superficial line inspections. The Verifier uses the Graphify knowledge graph substrate to compute the deterministic blast radius of pull requests in <0.5 seconds, mapping modified symbols directly to their upstream callers and test suites.

---

## Available Tools & CLI Commands

### MCP Tools (`graphify-mcp`)
- `get_pr_impact(pr_number: int | str)`: Resolves all AST symbols touched in the PR's unified git diff, traverses the directed call graph to identify all 1st-order and 2nd-order upstream callers, and lists the affected source files and modules.
- `shortest_path(source: str, target: str)`: Computes the shortest directed dependency or invocation path between two symbols, revealing coupling chains and unintended transitive side-effects.

### Companion CLI Commands
- `synlynk impact <symbol|file>`: Calculates the blast radius for a given symbol or file, printing upstream callers, downstream callees, and mapped test files.
- `synlynk pr check --impact-attested`: Checks that 100% of symbols modified in the PR branch have executed test coverage verifying their behavior and callers.
- `synlynk pr gate-status`: Evaluates all required merge gates, including QA sign-off and impact attestation.

---

## Execution Protocol

### Step 1: Ingest PR Diff & Resolve Touched Symbols
When assigned to review or verify a pull request:
1. Fetch the PR context or execute from within the PR worktree:
   ```bash
   synlynk pr check
   ```
2. Query `get_pr_impact(pr_number)` via MCP or invoke:
   ```bash
   synlynk impact $(git diff --name-only origin/main...HEAD)
   ```
3. Extract the mathematical set of all modified, deleted, or introduced AST symbols (functions, methods, classes, types).

### Step 2: Compute Upstream Caller Blast Radius
1. Inspect the caller tree returned by `get_pr_impact`:
   - Categorize affected callers by module and critical path (e.g. Ingress, Ledger/State, Authentication, CLI).
   - Flag any unintended blast radius where a localized utility change reaches cross-domain orchestration components.
2. If unexpected coupling is observed, run `shortest_path(source, target)` to explain the exact call sequence causing the leakage.

### Step 3: Test Coverage Attestation
1. Compare the affected caller list against the test suite:
   - Identify which caller sites have direct unit or integration test coverage.
   - Verify that test cases exercised in the PR branch cover all modified public interface signatures and edge cases.
2. Run the impact-attested verification gate:
   ```bash
   synlynk pr check --impact-attested
   ```
3. If test coverage is incomplete for any impacted upstream caller:
   - **Reject / Request Changes:** Post review comment with the specific uncovered call paths.
   - Mandate test addition before merge.

### Step 4: Verification Gate Sign-Off
1. Once all tests pass and blast-radius coverage is 100% attested:
   - Execute formal QA approval per session review discipline (`gh pr review --approve` or QA approval comment).
   - Log review receipt and proceed with merge if authorized.

---

## Safety & Governance Guardrails
1. **Context Window Protection:** Impact payloads are capped at 2,000 tokens using tiered depth limits. Focus on 1st-order callers and summarize deep transitive leaves.
2. **Deterministic Fallback:** If Graphify indexing is unavailable, fall back to git diff inspection and full test suite execution (`pytest tests/ -v`).
3. **Impartial Verification:** Verifier agents must never approve their own authored code. Dispatches must maintain strict separation of duties.
