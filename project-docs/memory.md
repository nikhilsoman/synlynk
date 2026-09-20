# synlynk Memory

## Project Overview
- **Name:** synlynk
- **Description:** <img src="docs/img/logo/lockup.svg" alt="synlynk — keep your AI tools in sync" height="80"> </p>
- **Languages:** Python
- **Directories:** agents, bin, docs, examples, project-docs, scripts, synlynk, synlynk.egg-info, test_archive, test_context_output, tests, website, worktrees

## Decisions
- **Tripartite Model Routing:** Decoupled agent role charter (`--role`), sandbox harness (`codex`/`agy`/`claude`/`grok`), and model intelligence tiering (`--model-tier fast|pro|reasoning`) with AST blast-radius cost routing. [@codex, @agy]
- **Sovereign Multi-Home Protocol:** Dynamic drain-to-boundary pipeline handover using predictive quota runways to preempt mid-task rate limit failures. [@agy]
- **Vizor World View Extractor:** Implemented Concentric Radar SVG visualization and dual projection toggles (Radar vs Sequence Flow) for workspace proximity mapping. [@grok, @agy]
- **Deep Brownfield & Magic PR Engine:** Automated brownfield test/linter/runtime discovery (`synlynk init --brownfield`) and zero-touch AST remediation (`synlynk heal --magic`). [@codex]
- **PM Radar & Architect Watchdog:** Added Ring 3 (Ecosystem & Competitor Frontier) opportunity extraction (`synlynk pm sweep --radar`) and SPOF/memory health checks in `synlynk doctor`. [@claude, @codex, @agy]
- **Frontier QA Testbed & Enterprise Compliance Boundaries:** Co-located compliance and isolated testbed inside monorepo; established explicit extraction criteria for future sister swarm orchestrator. Bound testbed execution and Ed25519 cryptographic attestation receipts to QA Agent charter. [@agy, @claude, @codex]


## Architecture
- `state.db` remains the single point of mutation and source of truth across all 4 project documentation projections.
- Dual-track Git parity policy: every release commit is atomically synchronized across `main`, `staging`, and `unstable`.
