# Synlynk Platform Diagnostics & Troubleshooting Guide

> **Scope:** Onboarding failure diagnosis, prerequisite auditing, common recovery workflows, and automated self-healing for Synlynk Developer Preview (`v0.27.x`).

---

## 1. System Prerequisite Matrix

Before initializing or running Synlynk, ensure your host environment satisfies the baseline requirements:

| Component | Minimum Version | Recommended | Notes |
| :--- | :--- | :--- | :--- |
| **Python** | 3.10+ | 3.12 / 3.14 | Zero external runtime dependencies; stdlib only (`sqlite3`, `json`, `subprocess`). |
| **Git** | 2.38+ | 2.45+ | Required for worktree management (`git worktree add/remove`). |
| **GitHub CLI (`gh`)** | 2.40+ | Latest | Authenticated with `gh auth login` for PR and issue tracking. |
| **Node.js** *(Optional)* | 18+ | 20+ / 24+ | Only needed if building/packaging the VS Code extension (`clients/vscode`). |

### Core Agent Harnesses
Synlynk orchestrates across five supported harnesses:
* **Claude Code (`claude`):** Recommended for PM, architecture review, and non-author QA verification.
* **OpenAI Codex (`codex`):** Recommended for backend logic, CLI plumbing, and TDD implementations.
* **AntiGravity (`agy`):** Recommended for frontend layouts, CSS architecture, and documentation.
* **xAI Grok (`grok`):** Recommended for high-volume canvas, scripts, and infrastructure.
* **Meta Muse (`muse`):** Low-privilege specialist harness for exploratory tasks.

---

## 2. Automated Self-Healing (`synlynk doctor --fix`)

Synlynk includes 30+ automated health checks. If an environment anomaly is detected, running `synlynk doctor` will diagnose the root cause and provide automated remediation:

```bash
# Run full diagnostic suite
synlynk doctor

# Automatically remediate detected issues
synlynk doctor --fix
```

### Key Automated Remediation Targets:
1. **CLI PATH Precedence:**
   - *Fault:* `_hc_cli_entrypoint_health` fails due to another binary or broken alias shadowing `synlynk`.
   - *Fix:* `synlynk doctor --fix cli` re-audits PATH precedence and ensures the canonical entry point is active.
2. **Missing Workspace Ledger:**
   - *Fault:* `_hc_project_init` fails because `.synlynk/config.json` or `state.db` is missing.
   - *Fix:* `synlynk init --auto-defaults` re-initializes workspace metadata without overwriting existing repository files.
3. **Stale Task Leases:**
   - *Fault:* `_hc_task_leases_integrity` detects orphaned lease records from interrupted sessions.
   - *Fix:* `synlynk doctor --fix leases` releases stale locks and reclaims undispatched stories.
4. **Identity & Role Keys:**
   - *Fault:* `_hc_identity_roles` detects unmapped or unverified agent keys.
   - *Fix:* `synlynk doctor --fix identity` generates cryptographic Ed25519 signatures and syncs role directives.

---

## 3. Common Error Codes & Recovery Workflows

### 3.1 `StateRegistryError: canonical path mismatch`
- **Symptom:** `StateRegistryError: canonical path mismatch for 'synlynk'`.
- **Cause:** A transient or isolated test database was initialized in a subdirectory, diverging from the canonical SQLite database at `~/.synlynk/workspaces/<slug>/state.db`.
- **Remediation:**
  ```bash
  # Recover and re-register canonical ledger
  SYNLYNK_ALLOW_REGISTRY_RECOVERY=1 synlynk state register --slug synlynk --path ~/.synlynk/workspaces/synlynk/state.db
  ```

### 3.2 `Operation not permitted: index.lock`
- **Symptom:** `fatal: Unable to create '.git/.../index.lock': Operation not permitted`.
- **Cause:** Sandboxed process attempting to modify Git repository metadata or concurrent operations holding a dead lock file.
- **Remediation:**
  ```bash
  # Remove dead index lock files if no active git processes exist
  find .git -name "*.lock" -delete
  ```

### 3.3 `qa merge gate is red: CI status undeterminable`
- **Symptom:** `[PR CHECK BLOCKED] qa gate is red: CI status undeterminable`.
- **Cause:** Pull request checks have not completed yet on GitHub Actions or PR branch is behind `main`.
- **Remediation:**
  ```bash
  # Update branch from origin/main
  gh pr update-branch <pr-number>
  
  # Wait for CI matrix to turn green, then re-run check
  synlynk pr check
  ```

### 3.4 Worktree Leases & Safe Cleanup
- **Symptom:** Multiple feature worktrees left behind after merged PRs.
- **Remediation:**
  ```bash
  # Safely audit and prune merged worktrees without touching active work
  synlynk worktree clean --apply
  ```
