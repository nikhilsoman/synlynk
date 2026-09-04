# PR #1352 - Zero-Risk Onboarding & Instant First-Win Experience

Early adopters evaluating multi-agent development tools face an understandable trust barrier: handing control of an existing repository to autonomous tooling carries the risk of overwritten uncommitted work, unwanted config churn, or silent state pollution. PR #1352 eliminates this friction with a non-destructive safety guard and delivers an immediate "First Win" demonstration within two minutes of onboarding.

### 1. Non-Destructive Dirty-Tree Safety Guard
Before writing any workspace configuration, context files, or agent charters, `synlynk.wizard:guard_dirty_worktree()` probes the repository state via `git status --porcelain`. If any uncommitted modifications or untracked files are detected:
- The full tree state is archived into a safety tarball at `.synlynk/backups/init-<timestamp>.tar.gz`.
- A dedicated git stash entry (`synlynk-init-safety-backup-<timestamp>`) is created while preserving backup artifacts.
- Zero developer data is ever overwritten or lost, allowing one-command rollbacks.

### 2. Streamlined Zero-Config Workspace Initialization (<5s)
`cmd_wizard_init()` orchestrates an instant onboarding flow that completes in less than five seconds:
- **Harness Auto-Probe:** Detects installed CLI harnesses (`claude`, `codex`, `agy`, `grok`, `local`) on `$PATH`.
- **Codebase Stack Fingerprinting:** Detects repository languages, frameworks, test suites, and package managers without manual prompts.
- **8 Standard Agent Charters:** Instantly provisions standard workspace agent charters (`dev`, `qa`, `pm`, `architect`, `tpm`, `designer`, `marketing`, `synlynk-bot`) in `.synlynk/agents/` and registers durable agent identities in `agent_store`.
- **Automated Backlog Ingestion:** Automatically invokes `synlynk backlog ingest --sync-github`, synchronizing open issues directly into `state.db`.

### 3. "First Win" Diagnostic Auto-Remediation PR (<2m)
Through `synlynk.launch`, onboarding diagnoses the repository's highest-confidence low-hanging improvement—such as missing `.gitignore` hygiene rules, test coverage gaps, or documentation voids. The user is prompted for a 1-click confirmation to dispatch an automated fix:
- Executes in an isolated worktree.
- Runs local verification test suites.
- Dispatches via `--requires-gh-write` to open a clean GitHub PR with a descriptive summary in under two minutes.

### Verification
- `tests/test_onboarding_safety.py`: Validates clean vs. dirty tree detection, tar.gz safety backups, git stash persistence, `<5s` charter provisioning, and First-Win finding/dispatch mechanics.
- `tests/test_agent_cli.py`: Verified with `pytest tests/test_agent_cli.py -k 'featonboarding_implement_zerorisk_dirty_' -v`.
