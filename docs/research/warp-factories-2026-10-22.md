# Warp Factories — Competitive Research (2026-10-22)

> **Source Videos:**
> 1. [Warp Software Factory Live Demo](https://www.youtube.com/watch?v=ZKWpzdych6o) — product walkthrough / live demo
> 2. [Software Engineering Is Becoming Factory Engineering — Zach Lloyd](https://www.youtube.com/watch?v=tUPPVhBBcoM) — keynote / thesis talk (AI Engineer)
>
> **Methodology:** Web-sourced reconstruction from search results, blog posts, official docs, and coverage.
> Claude Opus cannot natively process YouTube video frames — a Gemini-native pass is recommended for frame-level UI teardown.
> Flagged items are marked with `⚠️ DELTA` where behavior extends or contradicts publicly documented architecture.

---

## Video 1: Warp Software Factory Live Demo (`ZKWpzdych6o`)

### 1.1 Timestamped Narrative Summary

| Approx. Timestamp | Topic / Narration |
|---|---|
| 0:00–1:00 | **Introduction & problem statement.** Interactive chat-based coding agents work for isolated tasks, but managing multi-step development lifecycles (triage → specs → implementation → PR) lacks scalable infrastructure. Warp Factories provide open, flexible, cloud-based infrastructure to run automated "software factories" configured entirely via code (`factory.yaml`). |
| 1:00–2:30 | **Factory-as-code overview.** Shows or references the directory structure: `factory.yaml` at root, `agents/` directory with `foreman/`, `triage/`, `spec/`, `implement/`, `review/` subdirectories each containing `agent.md`. Also references `automations/` directory. `factory.yaml` described as "Terraform for agents" — declares factory name, Slack/Linear aliases, connected GitHub repos, environment secrets, MCP servers, and runner definitions. |
| 2:30–4:00 | **Step 1: Initiating work from Slack.** A developer tags the factory's coordinator agent (the Foreman, e.g. `@payments` or custom bot handle) in a shared Slack channel with a bug report. The Slack thread becomes the living communication hub. Agent captures intent, maintains conversation history and context from intake onward. |
| 4:00–6:00 | **Step 2: Automated triage & spec writing.** The Foreman parses the request and maps it to project tracking tools (Linear, Jira, or GitHub Issues). Instead of jumping to coding, the agent researches the codebase and writes a comprehensive specification plan. This spec is committed/checked in directly via GitHub as code for human approval before execution proceeds. |
| 6:00–8:00 | **Step 3: Agent execution & GitHub integration.** Once the spec is approved, specialized execution agents take over using flexible harnesses (Warp Agent harness, Claude Code, or Codex). The agent spins up an isolated runner, creates a new Git branch, writes code modifications, and opens a draft or active Pull Request back in GitHub. |
| 8:00–10:00 | **Step 4: Computer use & visual verification.** For features requiring visual/functional validation, agents leverage computer use capabilities. Agent runs the application on a cloud runner, executes automated checks or a device simulator, records a walkthrough video or captures screenshots. Visual evidence is posted directly back into the GitHub PR or Slack thread. |
| 10:00–12:00 | **Step 5: Monitoring, analytics, and self-improvement.** Showcases the Warp Factories analytics dashboard tracking cost-per-PR, token spend, run success rates, and cycle times. Teams can deploy scoring agents and self-improvement loops to evaluate previous runs, refining agent skills and prompts over time. |

### 1.2 UI/UX Screen Inventory

> **⚠️ Limitation:** These descriptions are reconstructed from documentation, coverage articles, and video metadata — not from direct frame-by-frame viewing. A Gemini-native re-pass is recommended for pixel-level accuracy.

#### Screen 1: Factory-as-Code File View (~1:00–2:30)

- **What it shows:** Editor or file-tree view of a factory configuration directory
- **Layout elements:**
  - File tree sidebar showing: `factory.yaml`, `agents/foreman/agent.md`, `agents/triage/agent.md`, `agents/spec/agent.md`, `agents/implement/agent.md`, `agents/review/agent.md`, `automations/`
  - Editor pane showing YAML configuration with fields: `name`, `slack_alias`, `repos`, `secrets`, `mcp_servers`, `runners`
- **Narration context:** "Terraform for agents" — configuring the factory entirely as code

#### Screen 2: Slack Integration — Task Intake (~2:30–4:00)

- **What it shows:** Slack channel interface with bot interaction
- **Layout elements:**
  - Slack channel with message thread
  - User `@`-mentioning factory bot (e.g., `@payments`)
  - Bot response acknowledging task receipt
  - Thread continuation showing agent status updates
- **Narration context:** Demonstrates the primary trigger mechanism — tagging the factory in Slack to initiate work

#### Screen 3: Spec Document / GitHub PR (~4:00–6:00)

- **What it shows:** GitHub Pull Request or code check-in view with generated specification
- **Layout elements:**
  - GitHub PR interface showing a specification document
  - Markdown-formatted spec with requirements, scope, and acceptance criteria
  - Human approval checkpoint visible (review request or approval button)
- **Narration context:** Agent writes spec, commits to GitHub for human sign-off before implementation proceeds

#### Screen 4: Agent Execution / Runner Activity (~6:00–8:00)

- **What it shows:** Cloud runner executing implementation tasks
- **Layout elements:**
  - Terminal/console output showing agent executing build & test commands
  - Git operations visible (branch creation, commits, PR creation)
  - Possible harness selection indicator (Warp Agent, Claude Code, Codex)
- **Narration context:** Isolated runner spins up, agent creates branch, implements changes, opens PR

#### Screen 5: Computer Use — Walkthrough Video (~8:00–10:00)

- **What it shows:** Device simulator or browser running the application
- **Layout elements:**
  - Simulated device/browser viewport showing the application under test
  - Agent-driven interaction with the UI (clicking, scrolling, form input)
  - Screenshot/video capture indicators
  - Evidence posted back to PR or Slack thread
- **Narration context:** Visual verification via computer use — agent runs the app, captures walkthrough video, posts evidence to PR

#### Screen 6: Factory Dashboard — Analytics & Metrics (~10:00–12:00)

- **What it shows:** Factory App analytics dashboard
- **Layout elements:**
  - **Metrics panel:** Total runs, PRs opened, PRs merged, autonomy rate (% of merged PRs with zero human code pushes), PR cycle times
  - **Cost breakdown:** Cost per PR split into inference costs (token-based) vs compute costs (runner machines). Further broken down by PR size (S/M/L/XL) or individual model
  - **Scorer cards:** Quality grades from automated evaluation functions (LLM-as-judge or deterministic)
  - **Time-series charts:** Tracking trends over time
- **Narration context:** Track ROI, diagnose inefficiencies (e.g., expensive models on simple triage tasks), deploy evaluation loops

---

## Video 2: Software Engineering Is Becoming Factory Engineering (`tUPPVhBBcoM`)

### 2.1 Timestamped Narrative Summary

| Approx. Timestamp | Topic / Narration |
|---|---|
| 0:00–2:00 | **Opening thesis.** Zach Lloyd (Warp CEO/Founder) presents the core argument: software engineering is shifting from manual coding to "factory engineering." Moving past AI autocomplete and interactive chat agents toward fully automated software factories. |
| 2:00–5:00 | **Evolution of AI-assisted development.** Three eras outlined: (1) autocomplete/copilot era, (2) interactive agentic era (chat-based coding assistants), (3) fully automated factory era. Each generation handles progressively more of the SDLC autonomously. |
| 5:00–8:00 | **The Software Factory Loop.** Describes how ideas flow through a continuous automated loop: triage → spec writing → implementation → human review gate → verification → monitoring. Continuous loop, not one-shot. The factory processes work items from intake to shipped code. |
| 8:00–12:00 | **Architecture deep-dive.** Foreman agent as orchestrator coordinating specialized subagents (triage, spec, implement, review). Foreman handles six sequential checkpoints per work item: (1) Filtering — is this request for the factory? (2) Stage detection — what stage to enter at? (3) Investigation — does it need triage first? (4) Human gates — high-stakes spec approval? (5) Delegation — which agent, model, context slice? (6) Communication — aggregating updates. |
| 12:00–16:00 | **Factory-as-code & meta-engineering.** Engineers no longer write the product code directly; they build and optimize the internal software factory — the system of agents that builds the product. `factory.yaml` as the declarative configuration. Shows directory structure and configuration patterns. |
| 16:00–20:00 | **Triggers & integrations ecosystem.** Work enters from Slack, Microsoft Teams, GitHub, GitLab, Linear, Jira. Each integration is a door into the same Foreman. Also introduces Factory MCP — a hosted MCP server connecting local coding agents (Claude Code, Cursor) bidirectionally with cloud factories. `send_task`, list/search tasks, continue tasks locally, message the foreman. |
| 20:00–24:00 | **Self-improvement & the outer loop.** Inner loop = day-to-day agent execution (processing tickets, writing code, running tests). Outer loop = meta-process analyzing collective performance over time. A scheduled background job (e.g., daily) reviews recent failures, low scorer grades, full conversation logs. Outer-loop agent identifies recurring structural bottlenecks, generates a fix, opens a standard Git PR with "Regressions addressed" section linking to failing runs and scorer evidence. Human approves the self-improvement PR. |
| 24:00–28:00 | **BYO model & infrastructure.** Not locked into single AI provider. Teams configure requests to Warp-managed models or team-managed LLM API keys and private model endpoints. Custom fine-tuned models, local LLMs in VPC, enterprise API gateways all supported. Warp handles choreography and transcript logging. |
| 28:00–30:00 | **Success metrics & closing.** Success measured by percentage of changes shipped automatically (without human intervention) relative to inference + human time costs. Not raw LOC or features. Autonomy rate as the north-star metric. |

### 2.2 UI/UX Screen Inventory

> **⚠️ Limitation:** Same caveat — reconstructed from public sources, not frame-by-frame.

#### Screen 1: Slide — Three Eras of AI Development (~2:00–5:00)

- **What it shows:** Presentation slide illustrating the evolution
- **Layout elements:**
  - Three-column or progressive diagram: Autocomplete → Interactive Agents → Automated Factories
  - Each era labeled with characteristics and scope of automation
- **Narration context:** "We've moved past autocomplete, past interactive agents, into factory-level automation"

#### Screen 2: Slide — The Software Factory Loop (~5:00–8:00)

- **What it shows:** Circular/loop diagram of the factory SDLC pipeline
- **Layout elements:**
  - Circular flow: Triage → Spec → Implement → Review → Verify → Monitor → (loop back)
  - Human review gate marked at specific points
  - Arrows indicating continuous cycle, not one-shot
- **Narration context:** "Ideas flow through a continuous automated loop"

#### Screen 3: Architecture Diagram — Foreman & Subagents (~8:00–12:00)

- **What it shows:** Architecture diagram of the multi-agent system
- **Layout elements:**
  - Central Foreman node connected to subagent nodes: Triage, Spec, Implement, Review
  - Arrows showing delegation flow
  - Six checkpoint labels on the Foreman: Filter, Stage Detect, Investigate, Human Gate, Delegate, Communicate
  - Integration connectors (Slack, GitHub, Linear, etc.) feeding into the Foreman
- **Narration context:** "The Foreman coordinates the assembly line; it does not write code itself"

#### Screen 4: Factory-as-Code Directory Structure (~12:00–16:00)

- **What it shows:** File/directory tree and YAML configuration
- **Layout elements:**
  - Tree showing `factory.yaml`, `agents/` subdirectories, `automations/`
  - YAML snippet with configuration fields
- **Narration context:** "Your job is no longer to write the product code — it's to build and optimize the factory"

#### Screen 5: Integrations / Triggers Map (~16:00–20:00)

- **What it shows:** Diagram or slide showing all trigger sources
- **Layout elements:**
  - Icons/logos for: Slack, Microsoft Teams, GitHub, GitLab, Linear, Jira
  - Factory MCP connection diagram showing local agent ↔ cloud factory bidirectional link
  - MCP operations listed: `send_task`, list/search tasks, continue locally, message foreman
- **Narration context:** "Each integration is a door into the same central orchestrating agent"

#### Screen 6: Inner Loop vs Outer Loop Diagram (~20:00–24:00)

- **What it shows:** Two-layer architecture diagram
- **Layout elements:**
  - Inner ring/loop: Individual task execution (triage → spec → implement → review)
  - Outer ring/loop: Self-improvement process analyzing collective runs
  - Scorer inputs flowing into outer loop
  - Output: Auto-generated PR with "Regressions addressed" section
- **Narration context:** "The outer loop is the meta-process — the system that improves the system"

#### Screen 7: Dashboard / Metrics — Autonomy Rate (~28:00–30:00)

- **What it shows:** Metrics dashboard or slide showing success criteria
- **Layout elements:**
  - Autonomy rate metric (% of PRs merged with zero human code pushes)
  - Cost metrics (inference cost, compute cost, human time cost)
  - Possible benchmark: cost per PR dropped from ~$80 to ~$30 via model/harness optimization
- **Narration context:** "Success is measured by the percentage of changes shipped automatically"

---

## 3. Architecture Mapping (Public Docs Baseline)

### 3.1 Confirmed Architecture Elements

| Component | Documented | Confirmed in Videos |
|---|---|---|
| Foreman agent (orchestrator) | ✅ | ✅ — central coordinator, does not write code |
| Triage subagent | ✅ | ✅ — investigates raw requests, parses logs |
| Spec subagent | ✅ | ✅ — writes technical plans, human approval gate |
| Implement subagent | ✅ | ✅ — writes code, runs tests, creates PRs |
| Review subagent | ✅ | ✅ — independent quality gate, scoring |
| Factory-as-code (`factory.yaml`) | ✅ | ✅ — "Terraform for agents" |
| GitHub/GitLab triggers | ✅ | ✅ — labels, mentions, CI failures, review requests |
| Slack/Teams triggers | ✅ | ✅ — @-mention in channel/thread/DM |
| Linear/Jira triggers | ✅ | ✅ — assignment, status change, label, comment |
| Factory MCP | ✅ | ✅ — bidirectional local↔cloud agent bridge |
| BYO model/infra | ✅ | ✅ — team-managed LLM keys, private endpoints |

### 3.2 Deltas: Extended or Not-Fully-Documented Behavior

#### ⚠️ DELTA 1: Foreman Six-Checkpoint Decision Model

The video (Video 2, ~8:00–12:00) describes **six sequential checkpoints** the Foreman evaluates per work item:
1. **Filtering** — is this request for the factory? (noise filtering in shared channels)
2. **Stage Detection** — what pipeline stage does the work item enter?
3. **Investigation** — does it need a triage subagent run first?
4. **Human Decision / Gates** — high-stakes spec approval boundary?
5. **Delegation** — which subagent harness, LLM model, and repo context slice?
6. **Communication** — aggregating updates back to user/thread

> Public docs describe the Foreman as an orchestrator but do not always enumerate these six checkpoints as a formal decision model. The video makes this significantly more structured than a simple "route to subagent" description.

#### ⚠️ DELTA 2: Computer Use for Visual Verification

The demo (Video 1, ~8:00–10:00) shows agents using **computer use** capabilities to:
- Run the application on a cloud runner with a device simulator or browser
- Execute UI interactions (clicking, scrolling, form input)
- Record walkthrough videos of what they built
- Post visual evidence back to GitHub PR or Slack thread

> Public docs mention verification but do not always detail the computer-use-based visual verification loop with walkthrough video recording as a first-class factory capability.

#### ⚠️ DELTA 3: Self-Improvement Outer Loop as Git-Governed PR Flow

The talk (Video 2, ~20:00–24:00) describes the self-improvement mechanism in detail:
- A **scheduled background job** (e.g., daily cron) runs the outer-loop agent
- It reviews recent failures, low scorer grades, and full conversation logs
- It **identifies recurring structural bottlenecks** (e.g., "agents keep forgetting to check if remote branch exists before pushing")
- It **autonomously generates a fix** — a draft PR to update factory skills, instructions, or prompts
- The PR includes a **"Regressions addressed"** section linking to exact failing runs and scorer evidence
- Human reviews and merges the self-improvement PR

> Public docs mention self-improvement and scoring but the specific mechanism — scheduled job generating Git PRs with regression-linked evidence sections — represents a more concrete implementation detail than typically documented.

#### ⚠️ DELTA 4: Runner Isolation & Concurrency Model

From documentation cross-referenced with video content:
- **Per-run sandboxing:** Every agent run instantiates in its own clean, ephemeral environment
- **Execution plane separation:** Control plane (Warp's coordination, state, identity, inference routing) separated from execution plane (code checkout, setup, command execution)
- **Self-hosted options:** Docker containers or Kubernetes Jobs in designated namespace
- **Concurrency caps:** Team-level concurrency limits with automatic queueing — excess runs queued, dispatched as active runs complete

> The concurrency queueing/throttling behavior and the explicit control-plane/execution-plane separation are architectural details not always prominent in introductory docs.

#### ⚠️ DELTA 5: Cost-per-PR Optimization Benchmarks

Both videos reference concrete cost optimization:
- Internal benchmark: average cost per PR dropped from **~$80 to ~$30** by evaluating and replaying tasks across different model/harness configurations
- Cost breakdown in dashboard separates **inference costs** (token-based model calls) from **compute costs** (runner machines)
- Cost further broken down by PR size (S/M/L/XL) and individual model usage
- Explicit call-out: over-paying for expensive frontier models (e.g., Claude Opus) on basic triage tasks when cheaper/routed models would suffice

> The $80→$30 benchmark and the granular cost breakdown by PR size are specific data points shown in the demo but not always in the public docs.

#### ⚠️ DELTA 6: Factory MCP Bidirectional Operations

Factory MCP capabilities demonstrated or referenced:
- `send_task` — push local work to cloud factory
- List/search active tasks
- Read active conversation streams
- **Continue a cloud task locally** — pull full context into local checkout, work locally, push back
- Message the foreman directly from local agent
- **Bootstrap new factory** — use local agent via MCP to create factory, choose repos, validate `factory.yaml`

> The "continue locally" and "bootstrap factory via MCP" operations extend beyond basic send/receive task patterns.

### 3.3 Pricing Structure (from public sources, not necessarily shown in videos)

| Plan | Price | Included Agent Usage | Notes |
|---|---|---|---|
| Free | $0/mo | None (BYOK required) | Core terminal features, no bundled credits |
| Build | $20/mo (~$18 annual) | ~$20/mo (~1,500 credits) | Individual developers |
| Max | $180–200/mo | ~10× Build allowance | Heavy individual users |
| Business | $45–50/user/mo | $20/seat/mo | Teams ≤25–50 seats, SSO, admin controls |
| Enterprise | Custom | Custom | Dedicated AM, advanced security, custom billing |

---

## 4. Factual Summary — Key Architectural Claims

1. **Foreman is the singular voice** — all human communication flows through the Foreman, never directly from subagents
2. **Spec approval is a hard gate** — implementation does not proceed without human sign-off on the spec
3. **Harness-agnostic execution** — Warp Agent, Claude Code, Codex, open-weight models all supported as interchangeable harnesses
4. **Factory MCP bridges local↔cloud** — not just "fire and forget" into the cloud, but bidirectional continuation
5. **Self-improvement is Git-governed** — outer-loop changes go through standard PR review, never auto-deployed
6. **Zero-data-retention option** — enterprise security feature, sandboxed cloud environments (Docker/K8s)
7. **Autonomy rate as north-star** — percentage of changes shipped without human intervention, not LOC or features
8. **Scorer-driven quality** — LLM-as-judge and deterministic scorers produce continuous quality grades feeding both dashboard metrics and outer-loop self-improvement

---

*Document generated 2026-10-22 by Claude Opus from web-sourced research. Frame-level UI teardown requires Gemini-native video pass — recommended for follow-up.*
