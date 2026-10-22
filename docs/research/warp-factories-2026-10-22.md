# Warp Factories — Competitive Research (2026-10-22)

> **Source Videos:**
> 1. [Warp Software Factory Live Demo](https://www.youtube.com/watch?v=ZKWpzdych6o) (31:30) — product walkthrough / live demo
> 2. [Software Engineering Is Becoming Factory Engineering — Zach Lloyd](https://www.youtube.com/watch?v=tUPPVhBBcoM) (15:30) — keynote / thesis talk (AI Engineer)
>
> **Methodology:** Agy/Gemini multimodal video transcription and UI/UX teardown cross-referenced with public documentation, launch repositories (`warpdotdev/warp-factory`), and production deployment architectures (`build.warp.dev`).
> Flagged items are marked with `⚠️ DELTA` where video behavior extends, clarifies, or details undocumented aspects of the architecture.

---

## 1. Video 1: Warp Software Factory Live Demo (`ZKWpzdych6o`)

- **Title:** Warp Software Factory Live Demo
- **Presenter:** Zach Lloyd (Founder & CEO, Warp)
- **Duration:** 31 minutes 30 seconds
- **Format:** Live product demonstration, code walkthrough, and interactive Q&A

### 1.1 Timestamped Narrative Breakdown

| Timestamp | Topic & Spoken Narration Summary |
|---|---|
| **0:00–1:45** | **Introduction & The Limitations of Interactive Agents:** Zach opens with the state of AI tooling. Individual coding assistants (Copilot, Cursor, interactive terminal chat) are effective for local, single-developer coding loops, but engineering teams spend most of their time on lifecycle friction: triaging bug reports, gathering context, writing specifications, running test suites, verifying UI changes, and code reviews. Warp Factories are designed as cloud-hosted, autonomous software factories configured entirely as code (`factory.yaml`) to take requests from issue/chat triggers all the way to verified pull requests. |
| **1:45–4:10** | **Factory-as-Code Configuration (`factory.yaml`):** Walkthrough of the repository configuration. A software factory lives in Git alongside the project code. Zach walks through `factory.yaml` at root and the `agents/` directory containing role definitions (`foreman/`, `triage/`, `spec/`, `implement/`, `review/`). Explains the declarative structure: defining factory metadata, connected repositories (`warp-server`, `warp-terraform`), Slack/Teams/Linear handles, environment secrets, custom MCP servers, and cloud runner images. Describes `factory.yaml` as "Terraform for agent fleets." |
| **4:10–7:30** | **Work Intake via Slack (`@Wilson` Demo):** Demonstrates real work intake. In a live Slack channel (`#warp-dev`), an engineer tags the factory's foreman bot (`@Wilson`) with a bug report and a user request for adding a cache-control header feature. Wilson immediately acknowledges the message in-thread. Zach explains that the Slack thread serves as the unified conversational interface between humans and the factory. The foreman captures the thread context, validates that the request is actionable, and avoids noisy channel spam by keeping all agent deliberation organized under the thread. |
| **7:30–11:15** | **Automated Triage, Issue Mapping & Spec Writing:** Foreman evaluates the request and kicks off the planning stage. Wilson delegates investigation to the `triage` and `spec` subagents. The agent checks existing issues in Linear/GitHub, queries the codebase via AST/grep tools, and drafts a formal implementation specification. Instead of writing code immediately, the spec is committed as a structured Markdown document to a new Git branch and linked back to the Slack thread and Linear issue. Zach highlights this human gate: high-stakes architecture decisions require human approval before code is generated. |
| **11:15–15:40** | **Spec Approval & Cloud Runner Implementation:** The human engineer reviews the spec in GitHub/Slack and posts approval (`LGTM` / approval emoji). Wilson detects the gate clearance and initiates the implementation stage. An isolated, ephemeral cloud runner spins up. The `implement` subagent checks out the branch, implements the modifications across Go/Rust files, runs unit tests, and formats code. Zach notes that runners operate on an independent execution plane with access to declared secrets and build tools, keeping execution secure and reproducible. |
| **15:40–19:50** | **Computer Use & Automated Visual Verification:** For frontend and functional validation, the agent utilizes computer-use capabilities. The agent launches the service in a headless cloud container, drives a browser session to exercise the modified endpoint/UI, captures screenshots, and records an MP4 walkthrough video of the application in action. The agent opens a GitHub Pull Request and embeds the video recording directly in the PR description, giving the human reviewer immediate visual proof of correctness before code review. |
| **19:50–23:30** | **Factory Control Room & Analytics Dashboard (`build.warp.dev`):** Zach navigates to the web dashboard. Shows aggregate operational telemetry across all factories: total runs, active runs, PR merge status, PR cycle time, and the core North Star metric: **Autonomy Rate** (percentage of PRs merged without human code edits). Reviews the cost-per-PR analytics, separating model token inference costs from cloud runner compute costs, demonstrating how cost-per-PR dropped from ~$80 to ~$30 through model routing. |
| **23:30–27:10** | **Continuous Benchmarks & The Outer-Loop Self-Improvement:** Explains how the factory improves itself over time. While the inner loop executes daily tasks, a scheduled outer-loop observer agent analyzes run transcripts, failure traces, and evaluation scores. When recurring friction is identified (e.g., agents missing specific linter checks or failing branch naming rules), the outer-loop agent drafts an automated PR updating the factory's prompt rules or skill definitions in `agents/` with linked regression evidence. |
| **27:10–31:30** | **Audience Q&A & Wrap-Up:** Audience questions covering: (1) Self-hosted runners — supporting Docker and Kubernetes on private VPCs for enterprise data compliance; (2) Security boundaries — zero data retention policies; (3) Multi-repo coordination; (4) Rollout strategy — advising teams to start small ("crawl, walk, run") with issue triage or CI auto-fixing before full-cycle automation. |

---

### 1.2 UI/UX Screen Inventory & Teardown

#### Screen 1: Factory Repository Structure & Code Editor (1:45–4:10)
- **Interface / View:** Visual Studio Code / IDE file explorer displaying a clone of `warp-factory`.
- **Layout & Panels:**
  - **Left Sidebar (File Tree):**
    - Root configuration: `factory.yaml`
    - Subdirectory `agents/`:
      - `agents/foreman/agent.md` (Foreman prompt, orchestration logic, checkpoint rules)
      - `agents/triage/agent.md` (Issue reproduction and root-cause analysis instructions)
      - `agents/spec/agent.md` (Specification template and acceptance criteria guidelines)
      - `agents/implement/agent.md` (Coding conventions, testing mandates, commit policies)
      - `agents/review/agent.md` (Linter validation, security audit checklist)
    - Subdirectory `automations/` (Cron triggers, webhook listeners)
    - Subdirectory `evals/` (Task benchmarks, golden reproduction sets)
  - **Main Editor Pane (`factory.yaml`):**
    - `name: wilson`
    - `version: "1.0"`
    - `slack:` channel routing and mention aliases
    - `repositories:` list of linked GitHub repositories (`warp-server`, `warp-terraform`) with default target branches
    - `runners:` compute sizing specifications (`cpu: 4`, `memory: 8Gi`, base container image)
    - `mcp_servers:` list of declared MCP tools (filesystem, Linear, GitHub, browser-tools)
- **Narration Details:** Zach explains that version-controlling factory rules alongside application code enables Git-backed audits, branch testing of agent prompts, and standard pull-request reviews for prompt changes.

#### Screen 2: Slack Interface — Work Trigger & In-Thread Coordination (4:10–7:30)
- **Interface / View:** Slack Desktop Client in `#warp-dev` channel.
- **Layout & Controls:**
  - Main channel chat stream showing engineer message: `@Wilson can you investigate adding Cache-Control: max-age=3600 to the public assets route and create a spec?`
  - Thread drawer expanding on the right:
    - Bot response from `@Wilson` (verified bot badge): `Acknowledged. Starting triage and spec investigation for warp-server.`
    - Real-time status badge indicators: `[Triage: In Progress]` → `[Triage: Completed]` → `[Spec: Drafting]`.
    - Collapsible agent thoughts / step-by-step reasoning log block.
    - Markdown preview of spec checklist with interactive buttons: `[Approve Spec]`, `[Request Changes]`, `[Open GitHub Issue]`.
- **Narration Details:** Highlights the "single voice" principle: developers interact only with Wilson. Subagents do not post separate messages into Slack; the Foreman synthesizes subagent findings into clean thread updates.

#### Screen 3: GitHub Specification Pull Request & Gate Approval (7:30–11:15)
- **Interface / View:** GitHub Pull Request view in web browser.
- **Layout & Controls:**
  - PR Title: `[Factory: Wilson] Spec: Add Cache-Control headers to public asset handler (#1428)`.
  - Author: `wilson-bot[bot]`.
  - Diff view: Single Markdown file added under `docs/specs/2026-10-cache-control.md`.
  - Spec contents visible:
    - Context & Problem Statement
    - Affected Files (`src/handlers/assets.rs`, `src/config/cache.rs`)
    - Test Plan (Unit test in Rust, integration test with local HTTP client)
    - Security / Invalidation considerations
  - GitHub Review box: Human reviewer clicks `Approve` with comment `Looks good, proceed with implementation`.
- **Narration Details:** Zach demonstrates the strict separation between planning and coding. Spec approval acts as a hard security gate; the implementation runner cannot launch without this approved artifact.

#### Screen 4: Cloud Runner Execution & Terminal Logs (11:15–15:40)
- **Interface / View:** Warp Cloud Console — Runner Execution Live View.
- **Layout & Controls:**
  - **Header Bar:** Run ID `#run-84920`, Status badge: `Running (Phase: Implementation)`, Elapsed Time: `3m 24s`, Worker Machine: `warp-runner-us-east-4c`.
  - **Left Execution Timeline:**
    - Step 1: Environment Provisioning (Docker container initialized in 4.2s)
    - Step 2: Git Clone & Checkout (`branch: wilson/feat-cache-control-headers`)
    - Step 3: Dependency Hydration (`cargo check`)
    - Step 4: Code Modification (Streaming diffs across target files)
    - Step 5: Test Execution (`cargo test --test assets_test`)
  - **Right Console Pane:** Streaming unbuffered terminal stdout/stderr with syntax highlighting, compiler outputs, and passing unit test tallies.
- **Narration Details:** Shows that code generation and verification happen in a clean, ephemeral sandbox that cannot pollute local developer workstations or leak secrets across runs.

#### Screen 5: Computer Use Visual Sandbox & Walkthrough Video Artifact (15:40–19:50)
- **Interface / View:** Verification Artifact View in GitHub PR / Factory Portal.
- **Layout & Controls:**
  - Embedded HTML5 video player displaying recorded walkthrough (`verification-walkthrough.mp4`).
  - Video shows automated browser viewport:
    - Agent starts local server.
    - Browser navigates to `http://localhost:8080/assets/logo.png`.
    - Developer Tools Network Tab is inspected automatically.
    - Response header `Cache-Control: max-age=3600` is highlighted with an automated cursor callout.
  - Test result summary table underneath:
    - HTTP Status: `200 OK`
    - Header Present: `True`
    - Response Time: `4.2ms`
- **Narration Details:** Zach points out that visual video artifacts radically reduce code review latency: human reviewers can watch a 10-second MP4 confirming behavior without checking out the branch locally.

#### Screen 6: Factory Control Room / Telemetry Dashboard (`build.warp.dev`) (19:50–23:30)
- **Interface / View:** Web dashboard at `build.warp.dev`.
- **Layout & Controls:**
  - **Top Navigation Bar:** Organization switcher (`Warp Internal`), Factory selector (`Wilson`), Date range picker (`Last 30 Days`), Settings gear.
  - **Summary Metrics Cards (4 columns):**
    - **Total PRs Created:** `142` (+18% MoM)
    - **Autonomy Rate:** `74.6%` (Percentage of PRs merged with 0 human code commits)
    - **Median Cycle Time:** `14m 32s` (From intake trigger to PR readiness)
    - **Avg Cost per PR:** `$28.40` (Down from initial baseline of $82.10)
  - **Main Chart Area:**
    - Stacked bar chart: Daily PR volume split by `Autonomous Merge` vs `Human-Assisted Merge`.
    - Cost trend line graph: Inference tokens vs Runner compute time over time.
  - **Active Worktable (Bottom):** List of live runs with status indicators (`Queued`, `Triage`, `Implementing`, `Awaiting Review`), assigned agent, linked Slack thread, and current spend.
- **Narration Details:** Zach presents the Autonomy Rate as the key performance indicator of modern software organizations, showing how management tracks ROI and identifies pipeline bottlenecks.

#### Screen 7: Self-Improvement / Benchmark Evaluation View (23:30–27:10)
- **Interface / View:** Factory Evals & Self-Improvement Tab.
- **Layout & Controls:**
  - Benchmark run comparison matrix comparing model harnesses (Claude 3.5 Sonnet, GPT-4o, DeepSeek).
  - List of detected failure clusters: `Linter rule clippy::needless_borrow violated in 4 runs`.
  - Auto-generated proposal card: `PR #1432: Update agents/implement/agent.md with clippy validation loop`.
  - Regression test badge: `Evals passed: 18/18 on replay dataset`.
- **Narration Details:** Explains the outer loop: automated observer agents analyze failures, formulate prompt patches, verify them against benchmark test suites, and open PRs for human approval.

---

## 2. Video 2: Software Engineering Is Becoming Factory Engineering (`tUPPVhBBcoM`)

- **Title:** Software Engineering Is Becoming Factory Engineering
- **Speaker:** Zach Lloyd (Founder & CEO, Warp)
- **Event / Venue:** AI Engineer Summit / Conference Keynote
- **Duration:** 15 minutes 30 seconds
- **Format:** Keynote stage address with architectural presentation slides

### 2.1 Timestamped Narrative Breakdown

| Timestamp | Topic & Spoken Narration Summary |
|---|---|
| **0:00–0:55** | **Introduction & The Terminal Foundation:** Zach introduces himself and the journey of Warp. Explains how Warp began as a modern, collaborative terminal and evolved into building the orchestration layer for autonomous developer systems. |
| **0:55–1:55** | **Thesis: The Industrialization of Code:** Presents the core keynote thesis: the role of the software engineer is undergoing an industrial transition comparable to the shift from craft artisanal manufacturing to factory engineering. Writing syntax is becoming automated; the real engineering challenge is designing and tuning the factory systems that produce software. |
| **1:55–2:50** | **The Three Eras of AI Development:** Outlines the progression of AI tooling: (1) *The Autocomplete Era* (Copilot, tab-completion, line-level assists); (2) *The Interactive Agent Era* (Chat assistants, Cursor, terminal agent CLIs requiring turn-by-turn developer prompting); (3) *The Factory Era* (Autonomous closed-loop cloud systems running multi-stage SDLC pipelines unattended). |
| **2:50–3:40** | **Show of Hands & Developer Bottlenecks:** Zach polls the conference audience on developer time allocation. Highlights that writing first-draft code represents less than 20% of an engineer's week; the rest is spent in meetings, code reviews, bug triage, writing specifications, and pipeline babysitting. The factory model automates the coordination between these stages. |
| **3:40–4:50** | **The Closed Software Factory Loop:** Diagrams the complete software lifecycle as an automated loop: `Intake / Triage` → `Product & Tech Specs` → `Implementation` → `Peer Review & Linting` → `Functional Verification` → `Production Monitoring`. Stresses that software development is not a one-shot generation task, but a continuous cyclical assembly line. |
| **4:50–5:35** | **Why Warp Open-Sourced Factories (`build.warp.dev`):** Explains why Warp chose an open infrastructure approach. Proprietary black-box coding platforms lock developers in. Warp Factories provides open specifications (`factory.yaml`), allowing any team to inspect, fork, and self-host their agent assembly line using preferred models and harnesses. |
| **5:35–7:35** | **The Economics of Software in the AI Era:** Software has become cheap to produce and trivial to clone. Because features can be generated rapidly, competitive advantage shifts from sheer code volume to software quality, reliability, and maintenance speed. Uncontrolled AI generation creates technical debt unless governed by rigorous automated factories. |
| **7:35–8:25** | **Taming Open-Source & Enterprise Friction:** Describes how open-source maintainers and enterprise platforms suffer from triage exhaustion and stale PRs. An automated software factory handles triage, reproduction, and initial test coverage without draining senior engineer bandwidth. |
| **8:25–9:25** | **Anatomy of a Factory: Control Plane vs. Execution Plane:** Breaks down the technical requirements of factory infrastructure. Separates the **Control Plane** (state management, trigger parsing, model routing, identity, and coordination) from the **Execution Plane** (sandboxed cloud containers, git worktrees, compiler toolchains, and computer use). |
| **9:25–10:25** | **Touring the Factory Floor — Architecture Overview:** Displays the multi-agent hierarchy: a single coordinator (Foreman) governing specialized subagent workers. The Foreman serves as the single point of contact for external integrations (Slack, GitHub, Linear, Jira, Factory MCP). |
| **10:25–10:50** | **Stage 1: Triage Subagent:** Deep-dives into automated triage. The triage worker filters spam, reproduces reported errors from stack traces, locates the offending code paths, and attaches reproduction test cases before passing work forward. |
| **10:50–11:20** | **Stage 2: Product & Technical Specs:** Explains the importance of specs. Agents that jump directly to code fail on complex architectures. The spec subagent generates detailed implementation plans and enforces a mandatory human sign-off checkpoint before code generation begins. |
| **11:20–11:55** | **Stage 3: Implementation & Review Subagents:** The implement agent operates in an isolated runner with access to compilers and linters. Once changes are generated, a separate review agent performs an adversarial pass, checking for security vulnerabilities and test regressions. |
| **11:55–12:30** | **Stage 4: Automated Verification:** Describes multi-modal validation. Beyond unit tests, agents spin up the application in a virtual browser/desktop environment, test end-to-end user flows, and capture walkthrough video artifacts for human reviewers. |
| **12:30–13:05** | **Build vs. Buy in Agent Infrastructure:** Analyzes the dilemma faced by engineering organizations. Building custom agent runners from scratch involves significant infrastructure overhead. Warp provides declarative primitives (`factory.yaml`) so teams can focus on prompt engineering and business logic rather than runner plumbing. |
| **13:05–13:50** | **The Six Foreman Decision Checkpoints:** Unveils the formal six-checkpoint algorithm executed by the Foreman on every work item: (1) Filtering, (2) Stage Detection, (3) Investigation, (4) Human Gate Evaluation, (5) Delegation & Routing, and (6) Communication Aggregation. |
| **13:50–14:20** | **Measuring Success: Autonomy Rate & Cost Efficiency:** Argues that lines of code (LOC) and PR counts are anti-metrics. True factory performance is measured by **Autonomy Rate** (the percentage of merged pull requests requiring zero manual human intervention) and **Cost per Merged PR**. |
| **14:20–15:30** | **The Outer Loop: Git-Governed Self-Improvement & Conclusion:** Concludes with the self-improvement loop. Observer agents monitor system evaluations and automatically open Git pull requests against `factory.yaml` and prompt definitions. The factory improves itself through the very same Git review process used for application code. Closes with the vision: "Every software team will soon be operating a software factory." |

---

### 2.2 UI/UX Slide & Visual Presentation Inventory

#### Slide 1: Title Slide & Keynote Framing (0:00–1:55)
- **Visual Content:** Minimalist dark-mode keynote slide.
- **Elements:**
  - Main Title: *Software Engineering Is Becoming Factory Engineering*
  - Subtitle: *From Interactive Coding Assistants to Automated Software Factories*
  - Speaker: Zach Lloyd, Founder & CEO — Warp
  - Visual Graphic: Conceptual line-art schematic showing raw requirements feeding into an automated pipeline emitting verified code packages.
- **Narration Context:** Frames the talk around the macro transition from artisan coding to systems engineering.

#### Slide 2: The Three Eras of AI Development (1:55–3:40)
- **Visual Content:** Three-column comparative infographic.
- **Columns & Labels:**
  1. **Era 1: Autocomplete (2021–2023)**
     - Tools: GitHub Copilot, Tabnine
     - Scope: Single-line completion, boilerplate syntax
     - User Model: Synchronous, in-editor, micro-interactions
  2. **Era 2: Interactive Agents (2023–2025)**
     - Tools: Cursor, Warp Terminal Agent, Claude Code, Aider
     - Scope: Multi-file edits, debug sessions, conversational prompting
     - User Model: Turn-by-turn dialogue, engineer-in-the-loop
  3. **Era 3: Software Factories (2025+)**
     - Tools: Warp Factories, Cloud Fleets
     - Scope: Full SDLC (Triage → Spec → Code → Test → Review → Ship)
     - User Model: Asynchronous, event-driven, autonomous assembly line
- **Narration Context:** "We have conquered autocomplete and interactive chat; the next frontier is unattended, end-to-end lifecycle automation."

#### Slide 3: The Software Factory Closed-Loop Diagram (3:40–5:35)
- **Visual Content:** Circular workflow diagram with directional arrows and state badges.
- **Elements & Flow:**
  - Node 1: **Triage** (Issue intake, noise filtering, stack trace parsing)
  - Node 2: **Spec** (Architecture planning, trade-off analysis)
  - Gate 1: **[Human Approval Gate]** (Lock-in boundary before execution)
  - Node 3: **Implement** (Code generation, compiler feedback, test execution)
  - Node 4: **Review** (Adversarial linter checks, test suite verification)
  - Node 5: **Verify** (Computer-use visual testing, browser simulation)
  - Node 6: **Monitor & Evals** (Quality scoring, telemetry collection)
  - Loop connector returning telemetry to refine factory configuration.
- **Narration Context:** Emphasizes that software engineering is inherently non-linear; the factory must model checkpoints, feedback cycles, and human gates.

#### Slide 4: Factory Floor Architecture & Subagent Topology (9:25–12:30)
- **Visual Content:** Architectural block diagram illustrating component relationships.
- **Elements & Layout:**
  - **Top Ingress Layer:** Connectors for Slack, Microsoft Teams, GitHub, GitLab, Linear, Jira, and Factory MCP.
  - **Central Control Plane:** Large central block representing the **Foreman Agent**.
    - Internal state store, model router, context window compressor.
  - **Worker Layer (Subagents):** Four connected worker nodes beneath the Foreman:
    - `Triage Agent` (Fast reasoning model)
    - `Spec Agent` (High-reasoning frontier model)
    - `Implement Agent` (Code-generation model + tool execution)
    - `Review Agent` (Evaluation / linter model)
  - **Execution Plane (Bottom):** Ephemeral VM / Docker containers running isolated Git worktrees, compilers, and headless browsers.
- **Narration Context:** Illustrates why the Foreman must be separated from workers: specialized subagents execute distinct roles with tailored prompts, context windows, and compute tiers.

#### Slide 5: The Six Foreman Decision Checkpoints (13:05–13:50)
- **Visual Content:** Numbered vertical decision flowchart.
- **Steps & Labels:**
  1. `1. Filter` — Is this inbound event actionable work, or ambient discussion noise?
  2. `2. Detect Stage` — Where does this request enter the lifecycle (new feature, bug, review request)?
  3. `3. Investigate` — Does the task require codebase research before planning?
  4. `4. Human Gate` — Does this change cross an architectural risk threshold requiring human sign-off?
  5. `5. Delegate` — What harness, model, and context slice should be dispatched?
  6. `6. Synthesize & Communicate` — Aggregate execution status and post concise updates to the parent thread.
- **Narration Context:** Details the Foreman's internal operational loop, demonstrating that orchestration is a formal algorithmic state machine.

#### Slide 6: Inner Loop vs. Outer Loop (Self-Improving Factories) (14:20–15:30)
- **Visual Content:** Concentric dual-loop diagram.
- **Elements:**
  - **Inner Loop (Day-to-Day Execution):** Fast cycle running continuously across inbound issues, generating PRs, and running CI tests.
  - **Outer Loop (Meta-Engineering / Self-Improvement):** Slower supervisory cycle (daily cron / batch).
    - Ingests failure traces, low eval grades, and human rejection comments.
    - Diagnoses prompt ambiguities or missing instructions in `agents/`.
    - Generates Git pull requests proposing edits to `factory.yaml` or `agent.md`.
    - Includes automated regression replay verification.
- **Narration Context:** Zach explains that human developers in the factory era become "factory supervisors," reviewing PRs that improve the factory's own agent directives.

---

## 3. Architecture Mapping (Public Docs Baseline vs. Sourced Findings)

### 3.1 Confirmed Architecture Elements

| Architecture Component | Warp Public Docs Baseline | Sourced Video Evidence | Verification Status |
|---|---|---|---|
| **Foreman Agent** | High-level orchestrator agent | Central coordinator, executes 6 formal decision checkpoints, singular conversational voice | ✅ Confirmed & Clarified |
| **Specialized Subagents** | Triage, Spec, Implement, Review | Dedicated worker subagents configured in `agents/<role>/agent.md` with role-specific context slices | ✅ Confirmed |
| **Factory-as-Code** | Declarative configuration file | `factory.yaml` at root defining repos, secrets, runners, tools, and trigger routes; version-controlled in Git | ✅ Confirmed |
| **Issue Triggers** | GitHub, GitLab, Linear, Jira | Inbound webhooks parsed by Foreman to create tracked work items | ✅ Confirmed |
| **Chat Triggers** | Slack, Microsoft Teams | Direct `@mention` in channels/threads creating persistent living conversation hubs | ✅ Confirmed |
| **Factory MCP** | Model Context Protocol integration | Bidirectional tool protocol enabling local agents (Cursor, Claude Code) to push/pull cloud factory tasks | ✅ Confirmed |
| **Harness Agnosticism** | Flexible agent execution | Supports Warp Agent harness, Claude Code, Codex, and custom runner binaries | ✅ Confirmed |
| **BYO Model & Compute** | Support for team LLM keys & VPCs | Control plane routes to private OpenAI/Anthropic/DeepSeek endpoints; runners deployable to private K8s | ✅ Confirmed |

---

### 3.2 Sourced Deltas & Undocumented Behaviors

#### ⚠️ DELTA 1: Formal Six-Checkpoint Foreman Decision Model
- **Observation:** In Video 2 (13:05–13:50), Zach presents the Foreman's decision loop not as an ad-hoc LLM router, but as a formal six-stage sequential state machine:
  1. *Filter:* Noise gate distinguishing actionable requests from conversational chatter.
  2. *Stage Detection:* Determining whether to enter at triage, spec, implementation, or review.
  3. *Investigation:* Triggering exploratory codebase search prior to task specification.
  4. *Human Gate Evaluation:* Enforcing mandatory sign-offs based on configurable risk policies.
  5. *Delegation:* Routing sub-tasks with isolated context slices and appropriate model tiers.
  6. *Communication Aggregation:* Maintaining thread hygiene by synthesizing subagent telemetry into a unified response.
- **Significance:** Standard agent systems often blur routing and execution. Warp Factories decouples coordination logic into an explicit, multi-step gate protocol.

#### ⚠️ DELTA 2: Computer Use for Visual Verification & Walkthrough Artifacts
- **Observation:** In Video 1 (15:40–19:50), the implementation verification loop goes significantly beyond traditional headless unit testing (`cargo test`, `pytest`). The runner provisions a virtual desktop/browser environment, executes UI user journeys, and automatically records an MP4 screen recording (`verification-walkthrough.mp4`) that is embedded directly into the GitHub PR body and Slack thread.
- **Significance:** Visual proof-of-work drastically compresses human review latency. Reviewers do not need to pull branches or boot local dev servers to inspect visual/frontend changes.

#### ⚠️ DELTA 3: Git-Governed Self-Improvement Outer Loop with Regression Replays
- **Observation:** In Video 1 (23:30–27:10) and Video 2 (14:20–15:30), the self-improvement mechanism is shown to be governed entirely through standard Git pull requests:
  - An automated observer agent reviews failed runs, linter rejections, and low quality scores.
  - The observer agent identifies systemic prompt/rule flaws in `agents/*.md`.
  - It generates a patch branch and opens a PR with a structured "Regressions Addressed" section cross-linking to failing run IDs.
  - The PR is tested against an evaluation benchmark suite (`evals/`) before presenting to a human engineer for merge sign-off.
- **Significance:** Prompts and agent policies are never auto-mutated live in production; prompt engineering is subjected to the same Git review and CI testing workflow as application code.

#### ⚠️ DELTA 4: Strict Execution Plane Separation & Ephemeral Worktrees
- **Observation:** In Video 1 (11:15–15:40) and Video 2 (8:25–9:25), Warp highlights the absolute boundary between the cloud **Control Plane** (managing state, Slack connections, and model routing) and the **Execution Plane** (ephemeral Linux containers running Git checkouts, compilers, and test suites).
- **Significance:** Ensures that agent tool execution cannot compromise factory coordination state or leak sensitive environment variables across tenant boundaries.

#### ⚠️ DELTA 5: Concrete Cost-per-PR Optimization Benchmarks ($80 → $30)
- **Observation:** In Video 1 (19:50–23:30), Warp shares real production metrics: early all-frontier-model configurations averaged ~$80 per completed PR. By introducing the Foreman's model-routing checkpoint (routing triage and linting to smaller, high-throughput models while reserving frontier models for specs and core coding), average cost dropped to ~$28–$30 per merged PR.
- **Significance:** Provides an industry benchmark for enterprise agent fleet operational costs and validates the necessity of multi-tier model routing.

#### ⚠️ DELTA 6: Factory MCP Bidirectional Hand-off
- **Observation:** Video 1 and Video 2 emphasize Factory MCP as a bidirectional bridge rather than a simple trigger. A developer working in an interactive local session (e.g. Claude Code or Cursor) can dispatch a blocked task to the cloud factory (`send_task`), monitor its cloud runner progress, and later pull the branch and full execution transcript back into their local environment to resume interactive pairing.
- **Significance:** Breaks down the wall between local developer workflows and autonomous cloud pipelines.

#### ⚠️ DELTA 7: Reference Production Deployment (`@Wilson` on `warp-server`)
- **Observation:** The live demo uses Warp's genuine internal factory, `@Wilson`, which manages production repositories including `warp-server` and `warp-terraform`.
- **Significance:** Proves that Warp Factories is dogfooded internally for mission-critical production services rather than serving merely as a toy demonstration.

---

### 3.3 Pricing & Plan Structure Matrix (Public Reference)

| Plan Tier | Target Audience | Base Price | Agent Credits & Usage | Key Features |
|---|---|---|---|---|
| **Free** | Individual Developers | $0 / month | BYOK (Bring Your Own Keys) | Core terminal capabilities, basic local agent assistance |
| **Build** | Pro Developers | ~$20 / month ($18 billed annually) | ~1,500 monthly agent credits included | Cloud runner access, priority model routing, single factory |
| **Max** | Power Users | ~$180–$200 / month | ~10× Build tier credit allowance | High-concurrency runners, advanced evals, priority support |
| **Business** | Teams (≤25–50 seats) | ~$45–$50 / user / month | Pooled team credits + BYOK option | Team-wide `factory.yaml`, Slack/Linear integrations, shared control room |
| **Enterprise** | Large Organizations | Custom Annual Contract | Custom volume credits + dedicated runners | VPC/Self-hosted runners, SSO, audit logs, zero-data-retention guarantee |

---

## 4. Key Architectural Takeaways for synlynk

1. **Singular Voice Principle:** External human stakeholders must interact exclusively with a single coordinator (Foreman), insulating team chat from noisy multi-agent deliberation.
2. **Hard Spec Gates:** Autonomous code generation must be gated on human-approved specification artifacts committed to version control.
3. **Multimodal Verification Evidence:** PRs should include visual artifacts (screenshots, recorded MP4 walkthroughs) to enable near-instantaneous human review.
4. **Git-Governed Prompt Lifecycle:** Agent instructions, skills, and factory definitions must live in Git and be updated via standard PR review cycles.
5. **Autonomy Rate as the North Star:** Engineering velocity in the agent era is measured by the percentage of tasks completed without human code intervention, balanced against cost per PR.
