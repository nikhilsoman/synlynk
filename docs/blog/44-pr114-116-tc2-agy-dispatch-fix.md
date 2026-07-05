---
title: "PRs #114–#116 — The TC-2 Agent Dispatch Fix Arc"
date: 2026-07-05
series: "Building the OS for Multi-Agent Development"
post: 44
pr: "#114–#116"
merged: 2026-07-05
---

## The Broader Goal at the End of the Previous PR

With the integration of ecosystem status in Vizor (PR #113), synlynk had a functional dashboard displaying fleet health and capabilities. However, as soon as this instrument panel was turned on, it revealed a critical failure: all dispatches to the `agy` agent were failing immediately at the preflight stage. 

The broader goal was to make agent dispatch reliable and self-healing when agent CLI tools drift. But when the drift detection gates were first activated, they didn't just warn us—they locked down the entire dispatch pipeline.

## Strategic Shifts in This PR

The "TC-2 Saga" represents a major milestone in synlynk's maturity: the harness is now **self-aware of its contracts**. 

Historically, if a vendor CLI changed its flags, synlynk would blindly invoke it, resulting in silent hangs or obscure stderr exits that required manual debugging. TC-2 (the CLI flag compliance check) was designed to catch this. But the saga proved that contract enforcement is a double-edged sword: a bug in the enforcement code itself can result in a false-positive lockout. 

Strategically, this arc forced us to build bypass paths (`--skip-preflight`), improve zombie process reclamation, and establish a multi-agent review process to resolve layered, multi-component bugs without breaking the main branch.

## The Arc Narrative: Three Layered Bugs

The issue was first reported by `Claude@rxcc` (a guest agent operating on the workspace), who noted that every attempt to dispatch work to `agy` failed during preflight. Investigating this led down a rabbit hole of three separate bugs layered on top of each other, requiring three distinct PRs to resolve:

### 1. The Preflight & Observability Gap (PR #114)
The first layer was a lack of visibility: when a preflight check failed, the job was aborted, but the command logs didn't cleanly explain why, and the process was left in a zombie state.
- **The Fix**: Appended `.summary` content to the end of `cmd_logs()` output so that failed preflight exits are immediately visible. Wired zombie job reconciliation into `cmd_jobs()` via `.exit` file checks to clean up orphaned PIDs. 
- **Preflight Gate**: Hooked the TC-2 check (`_run_tc2`) directly into the `_preflight_dispatch` pipeline to ensure invalid flags fail preflight *before* triggering network calls. Added the `--skip-preflight` bypass flag for emergency overrides.

### 2. Incorrect Flag Baselines (PR #115)
The second layer was that the baseline flags defined for `agy` in `_constants.py` did not match the installed binary (version 1.0.16).
- **The Fix**: Removed the non-existent `--output-format` and `--always-approve` flags. Moved `--dangerously-skip-permissions` out of the invalid flags list (since it is a valid flag), and added the required `--sandbox` flag. Ran `synlynk probe agy` to regenerate the harness configuration fence in `GEMINI.md`.

### 3. The Root Cause: Seeding `failed` with `invalid_flags` (PR #116)
The deepest layer was a logical error in the TC-2 validator itself inside `synlynk/probe.py`.
- **The Fix**: In `_run_tc2()`, the validator was initializing the list of failed flags as `failed = list(invalid_flags)`. However, `invalid_flags` are dispatch-time guards ("do not pass these flags to the CLI"), not flags that need to be supported by the CLI's `--help` menu. By seeding the list this way, any agent with defined invalid flags would *always* fail TC-2 validation. Changed this to initialize `failed = []`, so TC-2 only fails when required or valid flags are missing from the CLI help output.

## Test Approach

The fix arc was validated with a comprehensive test suite across three modules:
- Added 6 new integration tests in `tests/test_agy_dispatch_fix.py` covering preflight bypass, log summary appending, and zombie job cleanup.
- Updated the main test suite (`tests/test_synlynk.py`) to mock the TC-2 gate during network preflight testing (since TC-2 now runs first).
- Corrected the TC-2 validator tests in `tests/test_harness_compatibility.py` to assert that `invalid_flags` do not populate the `failed_flags` list.

## What This Achieved on the Path to Autonomy

The resolution of the TC-2 saga establishes a robust contract negotiation layer between the OS and guest agents:
1. **Self-Aware Contracts**: The harness can now successfully detect when an agent's command-line interface changes and block execution *before* a failure occurs, rather than crashing mid-job.
2. **Zombie Reclamation**: The scheduler automatically detects and reclaims zombie processes whose PIDs are dead but whose status remained "running" in the DB.
3. **Resilient Failure Paths**: By appending summaries to logs and offering a preflight bypass, human operators have the tools needed to debug and override the harness when automated gates fail.

## Strategic Note: The Goal at the End of This PR

With the dispatch loop stabilized and the agent fleet fully verified against its CLI contracts, the core execution engine is healthy. The next phase of the roadmap focuses on **agent collaboration and handoff protocols** (BS-12). We need to define how agents securely request permissions, share workspace state during multi-agent dispatches, and hand off tasks to one another without human intervention.
