# End-to-End FTUE & Onboarding Deep Dive: Isolated VM Testbed, Provider Discovery & Full Vizor Audit — Design Spec

**Date:** 2026-11-15  
**Status:** In Review (Nikhil Soman)  
**Parent Issue:** [#5302](https://github.com/nikhilsoman/synlynk/issues/5302)  
**Associated Issues:** [#5297](https://github.com/nikhilsoman/synlynk/issues/5297) (FTUE wizard unknown job ID), [#5298](https://github.com/nikhilsoman/synlynk/issues/5298) (Claude LiteLLM/gateway env passthrough), [#5299](https://github.com/nikhilsoman/synlynk/issues/5299) (Premature `.synlynk/` creation on init), [#5287](https://github.com/nikhilsoman/synlynk/issues/5287) (Roadmap Studio Vizor UI)  

---

## 1. Executive Summary & Intent

Adopting synlynk as a daily multi-agent control plane depends entirely on the first 10 minutes of developer interaction:
1. Installing the CLI cleanly without dependency conflicts.
2. Auto-discovering available intelligence (Frontier CLIs, local servers, custom LiteLLM/DGX gateways).
3. Initializing a repository without false "already initialized" errors.
4. Executing a guided first dispatch with a verified job ID and immediate streaming logs.
5. Opening Vizor to an interactive, 100% functional visual control plane.

Recent early-adopter feedback on non-standard setups (e.g. an NVIDIA DGX Spark with LiteLLM proxying to local models) surfaced three critical papercuts (#5297, #5298, #5299). Rather than patching these as fragmented point fixes, this design establishes an **automated, repeatable, clean-slate Linux VM testbed** using synlynk's native `OrbDriver` ([synlynk/testbed/driver.py](file:///Users/nikhilsoman/dev/synlynk/synlynk/testbed/driver.py)). It validates the complete end-to-end FTUE journey against clean Ubuntu 24.04 environments, mock provider matrices, and automated headless Vizor browser sweeps.

---

## 2. Competitive & State-of-the-Art Analysis

A survey of contemporary developer control planes and agentic environments informs our architectural requirements:

| Platform | Strengths | Pitfalls & Failure Modes | Key Takeaway for Synlynk |
|:---|:---|:---|:---|
| **Cursor / Windsurf** | Seamless shell environment inheritance; instant connectivity test on API keys. | Hardcodes cloud endpoints; clumsy custom proxy configuration. | Provide explicit gateway environment passthrough (`ANTHROPIC_BASE_URL`, `OPENAI_BASE_URL`) out of the box. |
| **Continue.dev** | Dynamic local port scanning (`localhost:11434` for Ollama, `:8000` for vLLM, `:1234` for LM Studio). | Silent degradation when local daemon crashes without clear diagnostics. | Combine dynamic socket/port discovery with actionable `synlynk doctor` remediation hints. |
| **Claude Code / Agy** | Interactive terminal OAuth and guided wizard; persistent context packs. | Shell environment variable stripping; context-window runaway on large monorepos. | Ensure subprocess environment allowlists retain proxy configuration and JIT context compaction prevents token bloat. |
| **OrbStack / Docker** | Single-binary installation; zero-configuration background daemon management. | Locking race conditions and stray PID locks. | Ensure lock acquisition is strictly lazy and informational commands (`init --dry-run`) are 100% side-effect-free. |

---

## 3. Four-Pillar Architectural Specification

```
┌─────────────────────────────────────────────────────────────────────────────────────────────────┐
│                           FTUE END-TO-END VALIDATION ARCHITECTURE                               │
└─────────────────────────────────────────────────────────────────────────────────────────────────┘
                                                 │
         ┌───────────────────┬───────────────────┴───────────────────┬───────────────────┐
         ▼                   ▼                                       ▼                   ▼
┌─────────────────┐ ┌─────────────────┐                     ┌─────────────────┐ ┌─────────────────┐
│   PILLAR 1:     │ │   PILLAR 2:     │                     │   PILLAR 3:     │ │   PILLAR 4:     │
│  INSTALLATION   │ │ MODEL & HARNESS │                     │ REPO COLDSTART  │ │ VIZOR FULL VIEW │
│   & RUNTIME     │ │  AUTO-DISCOVERY │                     │   & WIZARD LAUNCH│ │  BROWSER AUDIT  │
├─────────────────┤ ├─────────────────┤                     ├─────────────────┤ ├─────────────────┤
│ • Clean VM Boot │ │ • CLI Binaries  │                     │ • Hermetic Dry- │ │ • 100% Working  │
│   (Ubuntu 24.04)│ │   (Claude, Codex│                     │   Run (Zero Disk│ │   Pages & Routes│
│ • pipx, uv &    │ │   Agy, Grok,    │                     │   Side Effects) │ │ • No 404s, Zero │
│   venv ladder   │ │   Muse)         │                     │ • Canonical Init│ │   Stale Caches  │
│ • Zero-external │ │ • Gateway Routes│                     │   Markers (.cfg)│ │ • Responsive HUD│
│   dependency    │ │   (LiteLLM,     │                     │ • Verified Job  │ │ • Dynamic Gantt,│
│   runtime check │ │   OpenRouter)   │                     │   ID in Wizard  │ │   Tube, Roadmap │
│                 │ │ • Local Silicon │                     │ • First Win SOP │ │   Studio Views  │
│                 │ │   (Ollama, oMLX)│                     │                 │                 │
└─────────────────┘ └─────────────────┘                     └─────────────────┘ └─────────────────┘
```

---

### Pillar 1: Clean-Slate Packaging & Installation Ladder

The installation lifecycle must be completely resilient across developer environments:
1. **Isolated VM Spin-up:**
   - Provision an ephemeral Ubuntu 24.04 (Noble) VM using `synlynk.testbed.driver.OrbDriver`.
   - The VM starts with zero pre-existing Python site-packages, zero existing git configurations, and no `~/.synlynk` state.
2. **Four-Tier Packaging Ladder:**
   - **Tier 1 (`pipx`):** Hermetic wheel build `python3 -m build --wheel` followed by `pipx install dist/synlynk-*.whl`.
   - **Tier 2 (`uv`):** `uv tool install dist/synlynk-*.whl`.
   - **Tier 3 (Automated Standalone venv):** Fallback installation script creating a dedicated `~/.synlynk/venv` wrapper.
   - **Tier 4 (Direct Pip):** Traditional `pip install` inside a virtual environment.
3. **Verification Contract:**
   - `synlynk --version` exits code 0 and reports the exact package version.
   - `synlynk doctor` passes core system integrity checks with zero missing binary or import errors.

---

### Pillar 2: Universal Model & Harness Discovery Engine

Synlynk must discover and configure all available execution intelligence automatically without manual config hacking.

#### 1. Discovery Subsystem Matrix
- **Frontier CLI Binaries:** Probing `PATH` for `claude`, `codex`, `agy`, `grok`, and `muse`.
- **Managed Gateway Routes:** Scanning for local or remote proxies (LiteLLM on `:4000`, OpenRouter, vLLM on `:8000`, generic OpenAI-compatible servers).
- **Local Sovereign Models:** Scanning standard sockets and HTTP ports (`localhost:11434` for Ollama, Apple MLX sockets).

#### 2. Resolving Issue #5298 (Subprocess Environment Passthrough)
Subprocesses spawned via `dispatch_agent()` must retain proxy and gateway configuration:
- In `synlynk/_constants.py`, update `HARNESS_CAPABILITY_BASELINES["claude"]["env_passthrough"]`:
  ```python
  "env_passthrough": [
      "ANTHROPIC_BASE_URL",
      "ANTHROPIC_AUTH_TOKEN",
      "ANTHROPIC_API_KEY",
      "CLAUDE_CONFIG_DIR",
  ],
  ```
- In `synlynk/probe_binding.py:_auth_config_path`, respect custom config directories:
  ```python
  claude_dir = os.environ.get("CLAUDE_CONFIG_DIR")
  auth_paths = {
      "claude": Path(claude_dir) / ".claude.json" if claude_dir else home / ".claude.json",
      ...
  }
  ```

#### 3. Mock Provider Test Suite
Inside the test VM, a lightweight mock background server (`tests/testbed_mocks/gateway_mock.py`) simulates:
- An Anthropic-compatible gateway on `http://127.0.0.1:4000`.
- An Ollama-compatible endpoint on `http://127.0.0.1:11434`.
- Mock executable binaries for `claude`, `codex`, `agy`, and `muse`.
- Automated test verifies that `synlynk probe` and `synlynk discover` correctly identify each provider and report active capabilities.

---

### Pillar 3: Coldstart, Init & Wizard First-Win Integrity

#### 1. Resolving Issue #5299 (Premature `.synlynk/` Creation on `init`)
- **Lazy Job Reconciliation:** In `synlynk/cli.py`, `_reconcile_jobs()` must be skipped when `args.command == "init"` or when `.synlynk/` does not yet exist.
- **Canonical Marker Check:** Replace bare directory existence checks (`os.path.exists(".synlynk")`) with checks for canonical initialization artifacts:
  ```python
  def is_repo_initialized(cwd: str = ".") -> bool:
      cfg = os.path.join(cwd, ".synlynk", "config.json")
      ws = os.path.join(cwd, ".synlynk", "workspace.json")
      return os.path.exists(cfg) or os.path.exists(ws)
  ```
- **Hermetic `--dry-run`:** Guard all file operations so running `synlynk init --dry-run` on a clean repository creates zero files and zero directories on disk.
- **Instruction Default Model:** Update `synlynk/instructions.py:704` to generate templates with current default `claude-sonnet-5` (retiring stale `claude-sonnet-4-6`).

#### 2. Resolving Issue #5297 (FTUE Wizard Job ID Resolution)
- In `synlynk/wizard.py:226`, resolve the dictionary key defensively:
  ```python
  job_id = (job.get("id") or job.get("job_id") or "unknown") if isinstance(job, dict) else "dispatched"
  print(f"\n  {_GREEN}▶{_RESET} [{job_id}] {chosen['agent']} dispatched\n"
        f"  {_DIM}Log: synlynk logs --job {job_id}{_RESET}\n")
  ```
- Verify that running `synlynk launch` in the test VM prints a valid `job-xxxxxxxx` ID and that `synlynk logs --job <id>` successfully connects to the log stream.

---

### Pillar 4: Full-Surface Vizor Visual & Interactive Audit

Once initialized, Vizor must run reliably in the clean VM without 404s, broken styles, or JavaScript exceptions.

#### 1. Automated Route Crawling Suite
An automated test script (`tests/test_vizor_e2e_audit.py`) starts the Vizor daemon on port 8765 (`synlynk viz --port 8765 --no-browser`) and audits every endpoint:
- **Routes Audited:**
  1. `/` (Overview & Session Bearings Card)
  2. `/roadmap` (Roadmap Studio & TPM Visual Proposals, [#5287](https://github.com/nikhilsoman/synlynk/issues/5287))
  3. `/gantt` (Interactive Execution Schedule)
  4. `/tube` (Tube Line Journey Map)
  5. `/radar` (Capability & Efficiency Radar)
  6. `/graphify` (Knowledge Graph Explorer)
  7. `/kanban` (Story Flow Board)
  8. `/health` (Doctor Pulse & Invariant Monitor)
- **Assertions:**
  - Status 200 on all primary routes.
  - Zero 404s on linked static assets (`/static/css/*.css`, `/static/js/*.js`, SVG icons, fonts).
  - Valid Content-Type (`text/html`, `application/json`, `text/css`, `image/svg+xml`).
  - Active WebSocket/SSE connection to `/events` streaming live job updates upon dispatch.
  - Viewports test: 1280px desktop, 768px tablet, 375px mobile responsiveness without layout blowout.

---

## 4. Implementation & Acceptance Contracts

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                              ACCEPTANCE TEST SUITE MATRIX                              │
├───────────────────────┬──────────────────────────────────┬─────────────────────────────┤
│ Test Module           │ Target Functionality             │ Success Verification Gate   │
├───────────────────────┼──────────────────────────────────┼─────────────────────────────┤
│ test_packaging_vm.py  │ pipx / uv / venv install ladder  │ Clean exit 0 in fresh VM    │
│ test_discovery_vm.py  │ Provider probing & env allowlist │ LiteLLM & CLIs auto-detected│
│ test_coldstart_vm.py  │ Hermetic init & dry-run          │ Zero stray files; no false  │
│                       │                                  │ "already initialized" errors│
│ test_wizard_vm.py     │ synlynk launch first-win dispatch│ Real job ID printed & logged│
│ test_vizor_audit.py   │ Full visual route sweep          │ 0 404s, 0 JS errors, 8 views│
└───────────────────────┴──────────────────────────────────┴─────────────────────────────┘
```

---

## 5. Review & Sign-Off

- **Author:** Agy (AI Partner / Mode A Conductor)
- **Reviewer:** Nikhil Soman (Architect / Owner)
- **Next Step:** Commit this design spec to branch `feat/agy/ftue-onboarding-vm-testbed-spec`, submit PR, and await Nikhil's sign-off before drafting the companion implementation plan.
