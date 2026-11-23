# Decision Record: dec-e89c42fa

**Topic:** Comprehensive Architectural Assessment of Synlynk Modular Ecosystem (5 Standalone Packages): Modularity, Synlynk Integration, Standalone Extensibility, Publishing Strategy, and Technical Hardening  
**Date:** 2026-11-23  
**Panel:** Claude Sonnet (Chair), Agy (Gemini), Codex, Grok  
**Status:** Approved & Ratified  

---

## 1. Executive Summary & Authoritative Decision

```
Decision:
Ratify the architecture for the Synlynk Modular Ecosystem suite of 5 standalone packages:
1. Enforce strict zero-leakage modularity (AST import-linter in CI preventing any package from importing synlynk).
2. Establish a unified bridge facade in `synlynk/ecosystem/` for clean core integration.
3. Standardize a 4-tier configuration ladder (CLI > ENV > Project JSON > Global JSON) with published JSON Schemas.
4. Adopt an Apache-2.0 PyPI publishing strategy under the Synlynk Ecosystem brand with a unified interactive documentation portal.
5. Apply technical hardening across all 5 packages: pre-compiled slot-optimized pricing tables, streaming generator iterators for circuit-breaking, OS flock concurrency for worktree leasing, and universal test fixture kits for transcript parsing.
```

---

## 2. Deep Review Against Key Focus Areas

### 1. Ensuring Modularity & Boundary Invariants
* **The Problem:** Subpackages developed inside a monorepo often accidentally import utility helpers or database handles from the parent repository, corrupting their standalone portability.
* **The Invariant:**
  - Every package in `packages/<name>/` must have its own standalone `pyproject.toml`, isolated dependencies, and dedicated test suite.
  - **CI Enforcement:** An automated AST import-scanner runs on every pull request to guarantee:
    ```python
    def test_zero_synlynk_imports():
        for py_file in package_source_files:
            tree = ast.parse(py_file.read_text())
            for node in ast.walk(tree):
                if isinstance(node, (ast.Import, ast.ImportFrom)):
                    assert not node.module.startswith("synlynk")
    ```

### 2. Efficient Integration into Synlynk Core
* **The Problem:** If synlynk callers across 50+ files directly depend on volatile subpackage APIs, upgrading a standalone package causes wide blast-radius refactors.
* **The Solution — The Bridge Facade (`synlynk/ecosystem/`):**
  Synlynk introduces a structured internal bridge:
  - `synlynk/ecosystem/pricing.py` wraps `tokenprice`.
  - `synlynk/ecosystem/transcripts.py` wraps `tokentrail`.
  - `synlynk/ecosystem/worktrees.py` wraps `worktree-lease`.
  - `synlynk/ecosystem/probing.py` wraps `harness-spec`.
  - `synlynk/ecosystem/circuit_breakers.py` wraps `token-breaker`.
  Existing synlynk subsystems (`synlynk/costs.py`, `synlynk/worktree.py`, `synlynk/jobs.py`) consume the bridge facade, guaranteeing zero coupling between synlynk's `state.db` schemas and the standalone libraries.
* **Monorepo Dependency Management:**
  Use `uv workspaces` with local editable path dependencies during active development (`tokentrail = { path = "packages/tokentrail", editable = true }`).

### 3. Configurability, Extensibility & Clear Scope as Standalone Packages
Every package adheres to a deterministic, predictable 4-tier configuration resolution ladder:
```
Tier 1: Explicit CLI flags (e.g., --config, --provider, --max-cost)
   │
Tier 2: Environment variables (e.g., TOKENTRAIL_CONFIG, TOKENPRICE_PROVIDER)
   │
Tier 3: Project-local config file (e.g., ./.tokentrail.json, ./.wtlease.json)
   │
Tier 4: Global user config file (e.g., ~/.config/tokentrail/config.json)
```
* **Extensibility via Schemas:** Every package publishes an open `config.schema.json` that IDEs (VSCode, Cursor) and automated validators use to provide schema autocompletion.

### 4. Strategy for Independent Publishing as Synlynk Ecosystem Suite
* **License:** Apache-2.0 across all 5 packages to maximize developer adoption, enterprise compliance, and community goodwill.
* **PyPI Naming Strategy:**
  - Dual registration on PyPI: Clean names (`tokenprice`, `tokentrail`, `worktree-lease`, `harness-spec`, `token-breaker`) accompanied by synlynk-namespaced aliases (`synlynk-tokenprice`, etc.).
* **Top-of-Funnel Marketing & Web Portal:**
  - Build an interactive web utility on `synlynk.com/ecosystem` (or `ecosystem.synlynk.dev`).
  - Embed `tokenprice` and `tokentrail` directly into the browser using WebAssembly / Pyodide. Developers can drag and drop a Claude Code or Agy transcript file into the browser and instantly get a beautiful, verified cost and token breakdown without installing anything.
  - This positions Synlynk as the premier authority on autonomous agent FinOps and developer infrastructure.

### 5. Technical Hardening & Specific Advice per Package

| Package | Specific Hardening Directives |
|---|---|
| **`tokenprice`** | Use `__slots__` on all data classes for sub-millisecond execution in 10k req/sec gateway proxies. Add support for custom pricing override URLs. |
| **`tokentrail`** | Ship `tokentrail.testing` containing anonymized transcript streams from Claude Code, Agy, and Codex CLI to serve as an industry-standard test fixture kit. |
| **`worktree-lease`** | Use OS-level atomic file locking (`fcntl.flock` on Unix, `msvcrt` on Windows). Support detached HEAD checkouts and provide `--dry-run` on prune. |
| **`harness-spec`** | Distinguish between passive probing (`--version`) and active execution. Provide strict sandbox isolation level verification. |
| **`token-breaker`** | Implement dual supervisor modes: Process-level OS PID watcher AND Python streaming generator iterator middleware. |
