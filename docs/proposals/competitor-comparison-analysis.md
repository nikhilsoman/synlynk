# synlynk: Comparative Analysis (Superpowers vs. GStack vs. synlynk)
**Date:** June 5, 2026  
**Status:** Evaluation Report / GTM Positioning  

---

## 1. Architectural & Feature Comparison

This section evaluates **Superpowers**, **GStack**, and **synlynk** across key developer-centric vectors.

| Vector of Interest | Superpowers (Local Skills Library) | GStack (Persona Framework) | synlynk (Context Switchboard) |
| :--- | :--- | :--- | :--- |
| **Core Value Proposition** | Runnable custom task plans and sub-agent automation within a specific repo. | Virtual engineering team structure (CEO, EM, QA, Reviewer) for Claude Code. | Multi-agent context switchboard, state continuity, and quota safety. |
| **State & Memory** | Local checklist directories (`.superpowers/brainstorm`) storing raw task files. | Short-term CLI history and session-scoped local context. | A durable, human-and-AI readable ledger (`project-docs/`) with dynamic snapshots. |
| **Tool / CLI Lock-in** | Locked into the specific agent shell running the superpowers skill. | Brittle integration. Heavily optimized for **Claude Code** and slash commands. | **Tool-Agnostic.** Seamlessly bridges Claude, Gemini, Codex, and Cursor. |
| **Multi-Agent Coordination** | Basic task division. Spawns simple sequential sub-agents. | Single-agent execution that shifts between virtual personas sequentially. | **Active Multi-Agent Orchestration** via shared event logs and Projects v2. |
| **Safety & Loop Control** | None. Runs plans continuously until execution exits. | Pre-configured shell command blocking (e.g., preventing `rm -rf`). | **Flatline Sentinel:** Heuristically detects and blocks infinite loop failures. |
| **Cost & Budget Auditing** | None. No awareness of token counts or financial spend. | None. Cost is tracked on the provider's billing dashboard. | **Budget Pulse:** Local cost tracking, request counting, and limit warnings. |
| **UI Ergonomics** | Raw CLI output and markdown files. | Interactive shell prompts and headless browser visual checks. | Rich **Terminal UI (TUI)** dashboard with panels for tasks, memory, and logs. |

---

## 2. Token & Cost Simulation Analysis

To evaluate efficiency, we model the execution of a common developer project: **A RESTful Todo API with JWT User Authentication and Database Persistence (CRUD + Auth).**

### Use Case Definitions:
1. **Small Implementation:** Adding a single validation schema or creating a database health check route (`GET /health`).
2. **Medium Implementation:** Implementing Password Hashing, JWT generation, login/signup endpoints, and auth middleware.
3. **Large Implementation:** Re-architecting the backend from a monolithic script into a clean-architecture model (Routers, Controllers, Services, Repositories), running DB migrations, and writing integration tests.

### Pricing Assumptions (Claude 3.5 Sonnet / Gemini 1.5 Pro Baseline):
* **Input Tokens:** $3.00 / Million ($0.000003 per token)
* **Output Tokens:** $15.00 / Million ($0.000015 per token)
* *Note: Assume an average of 800 output tokens generated per session execution.*

### Token Usage & Cost Comparison Matrix:

| Implementation Size | Metric | Superpowers | GStack | synlynk |
| :--- | :--- | :---: | :---: | :---: |
| **Small** | **Input Tokens** | 25,000 | 60,000 | **12,000** |
| (Task: `GET /health`) | **Output Tokens**| 800 | 1,200 | **600** |
| | **Estimated Cost** | $0.087 | $0.198 | **$0.045** |
| **Medium** | **Input Tokens** | 120,000 | 300,000 | **70,000** |
| (Task: JWT Auth Flows) | **Output Tokens**| 3,500 | 5,000 | **2,500** |
| | **Estimated Cost** | $0.4125 | $0.975 | **$0.2475** |
| **Large** | **Input Tokens** | 500,000 | 1,500,000 | **220,000** |
| (Task: Re-architecture) | **Output Tokens**| 12,000 | 18,000 | **8,000** |
| | **Estimated Cost** | $1.680 | $4.770 | **$0.780** |

### Why synlynk is Cost-Effective:
* **Context Compaction:** Both GStack and Superpowers pass massive directories of historical files and persona rules with every prompt. synlynk's watcher daemon dynamically prunes completed tasks and compresses historical devlogs, keeping context inputs thin.
* **No Redundant Roles:** GStack's multi-step persona loop (CEO $\rightarrow$ EM $\rightarrow$ QA) forces the LLM to read the entire codebase and instruction set multiple times in sequence, repeating input overhead. synlynk uses a single, focused session wrapper.

---

## 3. Key Advantages of synlynk

### A. Frictionless Onboarding vs. Heavy Tooling
* **Superpowers** requires maintaining complex local directories of executable markdown plans.
* **GStack** requires node installations, global CLI configurations, and setting up visual testing dependencies.
* **synlynk** installs instantly via a single `curl | bash` command with zero external Python dependencies, utilizing standard stdlib utilities already present on developers' machines.

### B. Workspace Autonomy vs. rigid Process Lock-in
* **GStack** forces developers to work through a rigid pipeline (Think $\rightarrow$ Plan $\rightarrow$ Build $\rightarrow$ Review $\rightarrow$ Test). This introduces significant friction for experienced developers who want to write code without approving multiple steps.
* **synlynk** runs silently in the background (`synlynk watch`). You write code, git commit, and run your CLI tools exactly as you always have; synlynk updates state and guards budgets without micro-managing your terminal actions.

### C. Multi-Repository Portability
* Both GStack and Superpowers are strictly bound to a single repository.
* synlynk operates as a **cross-repo coordination fabric**. By pointing multiple repositories to a single Projects v2 board, a developer coordinates actions across multiple microservices simultaneously.

---

## 4. Alternative Methods of Comparison

To demonstrate synlynk's advantages in GTM materials, consider these showcase strategies:
1. **The "Infinite Loop" Benchmark (Hallucination Test):**
   * Introduce a bug that causes standard CLI tools to fail compile checks. Run GStack, Superpowers, and synlynk.
   * *Result:* GStack and Superpowers will repeat the failing command until the token budget or human patience is exhausted. synlynk's **Flatline Sentinel** automatically flags three consecutive failures and interrupts the loop, demonstrating direct financial savings.
2. **The "Quota Swap" Live Demo:**
   * Run a development session where you exhaust your Anthropic API quota mid-way through a task.
   * *Result:* With GStack, your context state is trapped in Claude Code. With synlynk, you shut down Claude Code, open Gemini CLI or Cursor, and immediately resume work from the exact line where you left off, because your state was preserved in `.synlynk/context.md`.
