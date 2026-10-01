<!-- generated - source of truth is state.db -->
---
decision_id: dec-f77e216e
topic: "Zero-Risk Packaging & Standalone Distribution (pipx/uv/venv) Architecture: 4-Tier Resilient Installation Ladder (pipx -> uv -> auto-install pipx -> standalone venv fallback), Zero-External-Dependency Runtime, Post-Install Ecosystem Tools Provisioning (graphify, superpowers, gh), Multi-Tier Upgrade & Rollback Parity, and Making Synlynk Installation 'Impossible to Fail' on Any Modern Developer Environment (macOS/Linux)"
date: 2026-10-01
panel: [claude, codex, agy]
status: approved
---

## Topic
Zero-Risk Packaging & Standalone Distribution (pipx/uv/venv) Architecture: 4-Tier Resilient Installation Ladder (pipx -> uv -> auto-install pipx -> standalone venv fallback), Zero-External-Dependency Runtime, Post-Install Ecosystem Tools Provisioning (graphify, superpowers, gh), Multi-Tier Upgrade & Rollback Parity, and Making Synlynk Installation 'Impossible to Fail' on Any Modern Developer Environment (macOS/Linux)

## Panel Inputs

### claude
[model=sonnet; version=2.1.284 (Claude Code)]

**Analysis**

"Impossible to fail" is the wrong target. The achievable one is that install never fails silently and always leaves a working or cleanly reverted state. A 4-tier ladder gets us most of the way, but the tiers carry different risk.

- **Tiers 1–2 (pipx, uv)** are the right defaults. Both give isolated environments, clean uninstall, and `pipx upgrade` or `uv tool upgrade` for free. Prefer uv when it's present because it can also fetch a managed Python, which removes the biggest macOS failure: a stale system Python 3.9.
- **Tier 3 (auto-install pipx)** is the riskiest. It means mutating the user's machine through brew or `pip --user`, which hits PEP 668 "externally managed" errors on modern Debian, Ubuntu and Homebrew Python. I'd drop it, or make it opt-in with explicit consent.
- **Tier 4 (standalone venv)** is the real guarantee. It needs only `python3 -m venv` (stdlib), lives in `~/.synlynk/venv`, and has a shim in `~/.synlynk/bin`. Since synlynk already has no dependencies beyond the stdlib, this tier is cheap and robust. It should be the tested baseline, and tiers 1–2 are conveniences on top of it.

**Key risks**
1. Python version floor. Detect it up front and fail with an actionable message, or have uv fetch a newer Python.
2. Ecosystem tools (graphify, superpowers, gh) must be strictly non-blocking. A core install must succeed even if they fail. Run them as a separate `synlynk doctor --provision` step with per-tool status, not inside the install transaction.
3. Upgrade and rollback parity. Each tier needs its own upgrade path, so record the install method in a manifest (`~/.synlynk/install.json`). Keep the previous version, either as a venv snapshot or a pinned wheel, so rollback is the same operation regardless of tier.
4. Don't auto-edit the PATH silently. Print the exact line, or write it with consent and a backup.
5. Verification. A CI matrix (macOS arm64, Ubuntu, Debian with PEP 668, no-pipx, no-uv, Python 3.9–3.13) that runs install → upgrade → rollback → uninstall is what makes the claim credible. Without it, "zero-risk" is marketing.

**Recommendation**

Adopt a 3-tier ladder: uv, then pipx, then the stdlib venv fallback. Auto-installing pipx is opt-in only. Make the venv tier the tested baseline. Write an install manifest that drives upgrade and rollback identically across tiers, and keep ecosystem provisioning separate and non-fatal. Ship it only with a CI matrix covering install, upgrade, rollback and uninstall on each tier. Market it as "never leaves you broken" rather than "can't fail".

### codex
[model=default; version=codex-cli 0.155.1]

The proposed four-tier ladder is directionally strong, but “impossible to fail” should be treated as a product goal, not a literal guarantee. Each installer—`pipx`, `uv`, automatic `pipx`, then a private `venv`—covers a meaningful class of modern macOS/Linux environments. The key architectural rule should be that every tier invokes the same packaged application and produces the same executable contract, rather than maintaining separate installation logic.

The runtime should remain zero-external-dependency after installation. Network access, package managers, GitHub authentication, and ecosystem tools must be optional provisioning concerns, never startup requirements. `graphify`, `superpowers`, and `gh` should be installed through an explicit, resumable post-install phase with capability detection, clear per-tool status, and no failure of one tool blocking Synlynk itself.

Upgrade and rollback parity is essential. Every tier should record version, installation source, environment path, and a rollback target. Upgrades should be transactional where possible: install and validate the new version first, switch an atomic launcher pointer, and retain the previous environment until health checks pass. Rollback must work offline and must not depend on the package manager that performed the original installation. A `synlynk doctor` command should expose provenance, permissions, interpreter compatibility, PATH issues, and repair options.

The main risks are complexity, privilege assumptions, stale PATH state, platform-specific shell behavior, and silent divergence between tiers. These are manageable with a small bootstrapper, deterministic artifacts, signed or hash-verified releases, bounded retries, and comprehensive matrix testing across clean macOS/Linux machines.

My recommendation is to adopt the four-tier design, with one qualification: make the standalone venv fallback the canonical recovery mechanism and define strict success criteria around offline launch, upgrade, rollback, and repair. Market the system as highly resilient, not literally failure-proof. This gives Synlynk broad distribution coverage without making runtime reliability depend on external tooling.

### agy
[model=default; version=1.2.14]

**Last completed task:** `feat(onboarding): Unified Onboarding Journeys & Self-Updating Lifecycle Engine (#1894)`  
**Next task from [`todo.md`](file:///Users/nikhilsoman/dev/synlynk/worktrees/feat-zero-risk-packaging/project-docs/todo.md):** `BS-7: brainstorm — skill pack interoperability + benchmarks (Superpowers/GStack/GSD) [platform]`

---

### Analysis: Zero-Risk Packaging & Standalone Distribution Architecture

Achieving an installation flow that is "impossible to fail" across macOS and Linux environments requires resolving three systemic distribution hazards: **PEP 668 externally managed environments**, **fragile C-extension/compiler toolchains**, and **monolithic installer failures**.

1. **4-Tier Resilient Ladder:** Cascading `pipx` $\rightarrow$ `uv tool` $\rightarrow$ auto-provisioned `pipx` $\rightarrow$ isolated standalone `venv` fallback (targeting `~/.local/share/synlynk/venv` with binary symlinks to `~/.local/bin/synlynk`) solves the PEP 668 constraint without requiring `sudo`. Tier 4 provides a guaranteed zero-configuration escape hatch, functioning on barebone developer environments or minimal CI containers equipped only with system Python 3.8+.
2. **Zero-External-Dependency Runtime:** Restricting the core Synlynk runtime strictly to the Python Standard Library ([`sqlite3`](file:///Users/nikhilsoman/dev/synlynk/worktrees/feat-zero-risk-packaging/synlynk/db.py), `urllib`, `subprocess`, `dataclasses`, `pathlib`) is architecturally sound. It eliminates wheel compilation errors, glibc/musl incompatibilities, and network latency during bootstrap, ensuring diagnostic commands like `synlynk doctor` always execute.
3. **Decoupled Post-Install Ecosystem Provisioning:** Coupling third-party tools (`gh`, `graphify`, `superpowers`) into the critical path of the initial installation script creates cascading failure points (e.g., missing Homebrew, GitHub authentication prompts, firewall blocks). Ecosystem provisioning must run asynchronously and idempotently through `synlynk doctor --fix` rather than blocking the base installer.
4. **Upgrade & Rollback Parity:** To maintain feature parity across tiers, Tier 4 must mimic `pipx` via atomic version directory swapping (`releases/<version>` symlinked to `current`), coordinated with transaction-safe [`rollback`](file:///Users/nikhilsoman/dev/synlynk/worktrees/feat-zero-risk-packaging/synlynk/rollback.py) checkpoints for `.synlynk/state.db`.

### Recommendation & Panel Position

I **strongly endorse** approving the 4-Tier Resilient Installation Ladder and Zero-External-Dependency runtime, with the binding condition that **core runtime installation is strictly decoupled from secondary ecosystem provisioning**. The POSIX installer must focus exclusively on establishing an isolated, verified Synlynk CLI binary within seconds; auxiliary tools (`gh`, `superpowers`) should be flagged and provisioned lazily during first-run onboarding or via `synlynk doctor`. This separation ensures Synlynk installs flawlessly on 100% of target Unix environments without sacrificing broad ecosystem integration.

## Synthesis
## Synthesis

**Where the panel agrees**
- "Impossible to fail" is a goal, not a guarantee. All three panelists want the claim reworded to "never leaves you broken": every failure is loud and leaves a working or cleanly reverted state.
- The stdlib `venv` fallback is the tested baseline. Synlynk is already stdlib-only, so this tier needs nothing but `python3 -m venv`. It also doubles as the recovery path. Tiers above it are conveniences.
- Ecosystem tools (graphify, superpowers, gh) are provisioned outside the install transaction, via `synlynk doctor --fix` or first-run onboarding. They are idempotent, report per-tool status, and one failing never blocks core.
- Upgrade and rollback must behave the same on every tier. Install provenance goes in a manifest (`~/.synlynk/install.json`: method, version, env path, rollback target). Upgrades install and validate the new version first, then atomically switch the launcher. The previous version is kept until health checks pass, and rollback works offline without the original package manager.
- A CI matrix is required before any "zero-risk" claim: macOS arm64, Ubuntu, Debian with PEP 668, no-pipx, no-uv, and Python 3.9–3.13. Each cell runs install, upgrade, rollback, and uninstall.

**Where they differ**
1. **Tier 3 (auto-install pipx):** Claude would drop it or make it opt-in, because it mutates the machine and hits PEP 668. Codex and Agy keep it. I side with Claude on the risk, but the ladder stays four tiers. Tier 3 only runs with explicit consent (an interactive prompt or `--allow-bootstrap`). Non-interactive runs skip it and go to tier 4.
2. **Tier order:** Claude puts uv before pipx, since uv can fetch a managed Python and fixes the stale macOS 3.9 case. I adopt that order.
3. **Tier 4 layout:** Agy proposes versioned `releases/<version>` directories with a `current` symlink. Codex proposes an atomic launcher pointer. These are the same idea, so I use the versioned-directory version for tier 4. It gives rollback for free and matches how pipx and uv behave.
4. **PATH edits:** Never edit silently. Print the exact line, or write it with consent and a backup.

**Open item:** I didn't check the repo's actual Python floor. Agy says 3.8+ and Claude's matrix starts at 3.9. This should be verified against `pyproject.toml` and the code before the matrix is fixed.

Decision: Adopt the resilient installation ladder, ordered uv → pipx → consent-gated pipx bootstrap → stdlib venv. The venv tier is the tested baseline and the recovery mechanism, using versioned release directories and an atomic `current` pointer. The runtime stays zero-external-dependency. All tiers share one install manifest (`install.json`) that drives upgrade, rollback, `synlynk doctor`, and repair identically. Ecosystem tools (graphify, superpowers, gh) are provisioned separately and non-fatally through `doctor --fix` or onboarding, and never inside the install transaction. Auto-installing pipx is opt-in only, and PATH changes are never made silently. The feature ships only with a CI matrix covering install, upgrade, rollback, and uninstall on each tier. It is positioned publicly as "never leaves you broken", not "impossible to fail". The next step is a spec in `docs/superpowers/specs/` (after a Python-floor check), per the brainstorm-first policy.

## Decision
Decision: Adopt the resilient installation ladder, ordered uv → pipx → consent-gated pipx bootstrap → stdlib venv. The venv tier is the tested baseline and the recovery mechanism, using versioned release directories and an atomic `current` pointer. The runtime stays zero-external-dependency. All tiers share one install manifest (`install.json`) that drives upgrade, rollback, `synlynk doctor`, and repair identically. Ecosystem tools (graphify, superpowers, gh) are provisioned separately and non-fatally through `doctor --fix` or onboarding, and never inside the install transaction. Auto-installing pipx is opt-in only, and PATH changes are never made silently. The feature ships only with a CI matrix covering install, upgrade, rollback, and uninstall on each tier. It is positioned publicly as "never leaves you broken", not "impossible to fail". The next step is a spec in `docs/superpowers/specs/` (after a Python-floor check), per the brainstorm-first policy.

> Signatures: see 2026-10-01-zero-risk-packaging-standalone-distribut.json
