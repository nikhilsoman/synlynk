---
title: "Companion v2.1 Design: Ambient Multi-Channel Co-Pilot & Developer Engagement"
date: 2026-10-31
last_updated: 2026-11-03
status: draft
author: "Claude (Home Conductor) & AGY (Antigravity)"
goal: "goal-85656c82"
epic: "#2458"
milestone: "v0.28.0"
arc: "developer-experience"
depends_on: "docs/superpowers/specs/2026-10-31-configurability-framework-design.md"
related:
  - "docs/superpowers/specs/2026-09-22-discord-herdr-bridge-design.md"
  - "project-docs/decisions/2026-10-31-review-and-approve-reject-the-companion.md"
---

# Companion v2.1 Design: Ambient Multi-Channel Co-Pilot & Developer Engagement

## 1. Problem & Strategic Vision

"At-the-fence" communication — the moment a harness calls back into synlynk between tasks — originated as a plain cost block (`FenceData`/`render_task_fence()` in `synlynk/fencing.py`). Companion v2 registered this mechanism against the [Configurability Framework](2026-10-31-configurability-framework-design.md) to provide an optional, configurable "voice" addressing four developer segments (`novice`, `skeptic`, `accelerant`, `architect`) across an AI-adoption acceptance ladder.

However, modern developer workflows do not live solely in a single synchronous terminal buffer. Developers navigate across terminal emulators (CLI, Warp), web dashboards (Vizor), IDE environments (VS Code, Cursor), multi-session agent cockpits (Herdr), mobile apps, and asynchronous team communication hubs (Discord, Slack).

Under **`goal-85656c82`** (*"Developer Experience v1.0: Ambient, Ubiquitous Multi-Surface Co-Pilot & Governance"*), Companion evolves from a terminal-only cost hint into an **ambient, multi-channel co-pilot**. It delivers structured, high-signal, non-coercive guidance with contextual deep links into GitHub and Vizor, while serving as the unifying communication layer across CLI, IDE, Cockpit, Mobile, and Discord/Slack team environments across Personal, Team, and Enterprise editions.

---

## 2. Carried-Over Decisions (Settled & Preserved)

The following foundational decisions approved in the original Companion brainstorm and ratified in [dec-f34a2f5f](../../../project-docs/decisions/2026-10-31-review-and-approve-reject-the-companion.md) remain strictly locked:

1. **Stage and theme are independent axes.** `stage` (`onboarding | companionship | sounding_board | policy_maker | recruiter | champion`) is a relationship-ladder position; `theme` is a pure vocabulary/tone skin. Neither implies the other.
2. **Stage is auto-inferred from behavior, user-overridable.** Signals: command vocabulary, override-rate of suggested actions, frequency of manual intervention vs. accepting defaults. Never advanced purely on elapsed time. Explicit override in settings wins; absent an override, Companion infers dynamically from recent telemetry (`.synlynk/telemetry.json`).
3. **Stage/segment inference is pinned once per command invocation.** (DECIDE Panel 2026-10-31): Stage/segment inference is memoized for the duration of a single `synlynk <command>` process invocation to prevent voice inconsistency between estimation and completion fences.
4. **Developer segment sets entry point + skip rules, not just tone.** Segments (`novice | skeptic | accelerant | architect`) define progression skip rules (e.g. `skeptic` or `architect` skips `onboarding` directly to `sounding_board`; `accelerant` skips to `policy_maker`).
5. **Significance tiers gate content, not frequency.** Every fence renders (frequency is governed by existing cost-fence cadence); `routine | notable | milestone` controls attached voice density. `routine` receives short lines or empty hints depending on `voice_density`; `milestone` is the only tier eligible for `remix` mode.
6. **Built-in themes are generic pastiche archetypes, not franchise content.** No proprietary franchise names, trademarks, or copyrighted dialogue ship with synlynk. Community packs are pluggable at user discretion.
7. **Hybrid content generation.** Static template lookup tables are default (zero cost, deterministic). Opt-in `remix` mode is restricted to `milestone` tier and dispatched via existing harness-exec with full telemetry/cost logging.
8. **Decoupled FTUE.** Companion `stage` is strictly independent of `onboarding_state.py`'s 10-stage First-Time User Experience (FTUE) model.
9. **Layer-3 Fail-Open Theme Fallback.** (DECIDE Panel 2026-10-31): Unknown or unresolvable theme names fail-open to `"standard"` with repeated warnings on every affected invocation, preventing silent misconfigurations while maintaining service continuity.
10. **Domain Vocabulary Post-Substitution Scoping.** (DECIDE Panel 2026-10-31): Whole-word replacement applies only to static template lines. For `remix` mode, vocabulary constraints are injected directly into the LLM synthesis prompt to prevent corrupting model prose.

---

## 3. Companion Topics & 4-Part Message Anatomy

Companion communicates across four discrete operational topics. Regardless of the topic or channel, every companion communication conforms to a strict **4-part message anatomy**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│ [Signal]     Domain classification badge, severity, and intent tag          │
│ [Context]    Compact, factual summary of current state or state delta       │
│ [Nudge]      Actionable, non-coercive next step or command                  │
│ [Deep Links] Direct clickable anchors to GitHub entities, Vizor, or IDE     │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 3.1 Topic Taxonomy

| Topic | Primary Domain | Typical Triggers | Example Signal |
|:---|:---|:---|:---|
| **1. Governance & Phase Ceremonies** | SDLC, phase gates, PR reviews, merge policy, compliance | Goal phase shifts, unapproved specs, PR author collision, review required | `[GOV:GATE]`, `[GOV:REVIEW]`, `[GOV:AUDIT]` |
| **2. Cost, Quota & Budget Awareness** | Spend tracking, token drift, quota exhaustion, burn rate | Milestone cost exceeded, high burn-rate multiplier, tier budget alert | `[COST:DRIFT]`, `[COST:WARN]`, `[COST:SAVINGS]` |
| **3. Agent Orchestration & Health** | Multi-harness dispatch, tool failures, fallback routing, test regressions | Harness PTY failure, sandboxed command blocked, dispatch queue backlog | `[DISPATCH:ROUTING]`, `[DISPATCH:ALERT]`, `[HEALTH:DEGRADED]` |
| **4. Workflow Acceleration & DevEx** | Stale worktrees, shortcut aliases, doc sync, PR closing ceremony | Hanging worktrees (>48h), unlinked tasks, uncommitted specs, release cut | `[DEVEX:NUDGE]`, `[DEVEX:CLEANUP]`, `[DEVEX:TIP]` |

### 3.2 Anatomy Schema & Concrete Topic Examples

#### Topic 1: Governance & Phase Ceremonies
- **`[Signal]`**: `[GOV:GATE:REVIEW_REQUIRED]` (Severity: Warning)
- **`[Context]`**: `PR #5050 touches protected core packaging without non-author qa signoff.`
- **`[Nudge]`**: `Dispatch review to qa role before attempting merge.`
- **`[Deep Links]`**: `[PR #5050](https://github.com/nikhilsoman/synlynk/pull/5050) · [Vizor Governance](http://localhost:4200/governs#dec-f34a2f5f)`

#### Topic 2: Cost, Quota & Budget Awareness
- **`[Signal]`**: `[COST:DRIFT:EXCEEDS_ESTIMATE]` (Severity: Notice)
- **`[Context]`**: `Task job-836e13a4 consumed $0.42 (estimate was $0.15; +180% drift via Claude-3.5-Sonnet).`
- **`[Nudge]`**: `Consider routing verification-only followups to Grok or Agy.`
- **`[Deep Links]`**: `[Cost Log](http://localhost:4200/observatory#costs) · [Harness Benchmark](http://localhost:4200/observatory#capability-ratings)`

#### Topic 3: Agent Orchestration & Dispatch Health
- **`[Signal]`**: `[DISPATCH:SANDBOX:FALLBACK]` (Severity: Warning)
- **`[Context]`**: `Codex task blocked by git index lock in sandboxed worktree.`
- **`[Nudge]`**: `Re-dispatch with BypassSandbox: true or prune dead lockfiles.`
- **`[Deep Links]`**: `[Failed Task #2180](http://localhost:4200/inbox#task-2180) · [GitHub Issue #5049](https://github.com/nikhilsoman/synlynk/issues/5049)`

#### Topic 4: Workflow Acceleration & DevEx Nudges
- **`[Signal]`**: `[DEVEX:CLEANUP:STALE_WORKTREE]` (Severity: Info)
- **`[Context]`**: `Worktree .worktrees/feat-legacy-auth has had no commits for 14 days.`
- **`[Nudge]`**: `Run synlynk worktree prune to reclaim 1.2 GB disk space.`
- **`[Deep Links]`**: `[Active Worktrees](http://localhost:4200/observatory#worktrees)`

---

## 4. Contextual Deep Links Engine

A major gap in static CLI tips is the friction required to inspect the underlying artifact. Companion v2.1 introduces the **Contextual Deep Links Engine**, dynamically resolving canonical entity references to web, local dashboard, and editor URLs.

### 4.1 Data Contract (`CompanionLink`)

```python
from dataclasses import dataclass
from typing import Optional, Literal

ChannelSurface = Literal["github", "vizor", "ide", "herdr", "discord", "slack", "custom"]

@dataclass(frozen=True)
class CompanionLink:
    label: str                          # Human-readable anchor text (e.g. "PR #5050")
    surface: ChannelSurface             # Target ecosystem
    url: str                            # Fully-qualified HTTPS or custom URI scheme
    entity_type: Optional[str] = None   # "issue" | "pr" | "decision" | "goal" | "task" | "file"
    entity_id: Optional[str] = None     # "#5050", "dec-f34a2f5f", "story-690e6184"
    anchor: Optional[str] = None        # HTML fragment / DOM anchor
```

### 4.2 Resolvers

1. **GitHub Link Resolver (`resolve_github_link`)**:
   - Inspects `git remote get-url origin` to extract owner and repository.
   - Resolves issues: `https://github.com/{owner}/{repo}/issues/{id}`
   - Resolves PRs: `https://github.com/{owner}/{repo}/pull/{id}`
   - Resolves filtered searches: `https://github.com/{owner}/{repo}/issues?q={query}` (e.g. `is:open+label:role:pm`)
   - Resolves Actions runs: `https://github.com/{owner}/{repo}/actions/runs/{run_id}`
   - Resolves Commits: `https://github.com/{owner}/{repo}/commit/{sha}`

2. **Vizor Link Resolver (`resolve_vizor_link`)**:
   - Detects local Vizor server (`http://localhost:4200` or configured port) or Hosted Vizor URL (W9).
   - Resolves top-level views: `/overview`, `/observatory`, `/governs`, `/inbox`.
   - Resolves deep anchor fragments:
     - Decisions: `/governs#{decision_id}` (e.g. `/governs#dec-f34a2f5f`)
     - Goals: `/observatory#{goal_id}` (e.g. `/observatory#goal-85656c82`)
     - Stories / Tasks: `/inbox#{story_id}` (e.g. `/inbox#story-1a8afcc1`)

3. **IDE Editor Resolver (`resolve_ide_link`)**:
   - Emits editor protocol URIs: `vscode://file/{absolute_path}:{line}` or `cursor://file/{absolute_path}:{line}`.

4. **Terminal Hyperlink Emission (OSC 8)**:
   - For CLI output supporting standard ANSI OSC 8 escapes, links render as clickable text without cluttering the screen with raw URLs:
     `\x1b]8;;https://github.com/nikhilsoman/synlynk/pull/5050\x1b\\PR #5050\x1b]8;;\x1b\\`
   - Fallback for non-TTY or non-supporting terminals gracefully prints: `PR #5050 (https://...)`.

---

## 5. Multi-Channel Presentation Surfaces & Placement Providers

Companion operates across multiple user-facing surfaces. A pluggable renderer architecture translates the canonical `CompanionMessage` into channel-native UI paradigms:

```python
@dataclass
class CompanionMessage:
    topic: str                          # "governance" | "cost" | "dispatch" | "devex"
    tier: str                           # "routine" | "notable" | "milestone"
    signal: str                         # e.g. "GOV:GATE:REVIEW_REQUIRED"
    context: str                        # Factual statement
    nudge: str                          # Recommended action
    links: list[CompanionLink]          # Structured deep links
    theme: str                          # Active theme archetype
    stage: str                          # Inferred or configured stage
```

### 5.1 UX Surface Matrix

| Surface | Presentation Format | Placement Location | Interactivity / Capabilities |
|:---|:---|:---|:---|
| **synlynk CLI** | Bordered fence hint or post-command footer | Terminal STDOUT (`FenceData.hints`) | ANSI colors, OSC 8 clickable hyperlinks, compact 2-line rendering |
| **Vizor HUD / Web** | Ambient companion ticker & notification drawer | Bottom-right floating card / top bar ticker | Rich HTML/CSS, expandable drawer, 1-click action triggers (`Approve Gate`, `Rerun Doctor`) |
| **VS Code / Cursor** | Status bar widget & Webview sidebar panel | Bottom Status Bar (`synlynk: [GOV]`) + Secondary Window / Panel | Hover tooltips, click to open Companion Side Panel, CodeLens hints in `GEMINI.md` / `AGENTS.md` |
| **Warp Terminal** | Smart completion block & inline markdown cards | Block action bar & post-execution fence | Markdown formatting, inline parameter chips, native Warp action buttons |
| **Herdr Cockpit** | Pane status footer & broadcast notification | Live Herdr session pane footer / top bar | Real-time agent status streaming, cross-pane broadcast alerts |
| **Mobile App / PWA** | Push notification & swipeable cards | Mobile OS Notification Center + Activity feed | 1-tap remote approval chips (`Approve`, `Reject`, `Pause Session`) |
| **Slack** | Block Kit message with interactive buttons | Configured alert channels / bot DMs | Color-coded severity attachments, interactive button components |
| **Discord** | Rich Embeds with ActionRow buttons | Session-scoped channels (Team) or bot DM (Personal) | Embed fields for Context/Nudge, URL buttons for deep links, slash commands |
| **MCP Agent Hook** | Structured JSON tool return / resource | Agent LLM Context Window (`companion://current`) | Enables active coding agents to read ambient state or emit companion events |
| **GitHub PR / Issue** | Markdown comment / collapsible block | PR status comments or Check Run summaries | Collapsible `<details>` fence block with markdown deep links |

### 5.2 Pluggable Channel Provider Interface

```python
class CompanionRenderer(Protocol):
    def render_cli(self, msg: CompanionMessage) -> str: ...
    def render_vizor_json(self, msg: CompanionMessage) -> dict: ...
    def render_vscode(self, msg: CompanionMessage) -> dict: ...
    def render_discord_embed(self, msg: CompanionMessage) -> dict: ...
    def render_slack_blocks(self, msg: CompanionMessage) -> list[dict]: ...
    def render_github_markdown(self, msg: CompanionMessage) -> str: ...
    def render_mcp_resource(self, msg: CompanionMessage) -> dict: ...
```

---

## 6. Discord Remote-Access Bridge Across Editions

The Discord/Herdr full-duplex remote-access bridge specced in [2026-09-22-discord-herdr-bridge-design.md](2026-09-22-discord-herdr-bridge-design.md) is consolidated directly into Companion v2.1 under **`goal-85656c82`**. This establishes Discord as the primary conversational chat surface for remote companion interactions across all three distribution tiers:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                       Common Goal: goal-85656c82                            │
│           (Ambient Multi-Surface Co-Pilot & Developer Engagement)           │
├──────────────────────────────┬──────────────────────────────┬───────────────┤
│       Personal Edition       │         Team Edition         │  Enterprise   │
├──────────────────────────────┼──────────────────────────────┼───────────────┤
│ • 1-Developer Private Bot    │ • Shared Workspace Guild     │ • Dedicated   │
│ • Direct DM / Webhook Relay  │ • 1 Channel per Herdr Pane   │   Cluster GW  │
│ • Push Alerts on Milestones  │ • W4 IdP Account Linking     │ • SAML / SSO  │
│ • Mobile Slash Steering:     │ • Full-Duplex Team Steering  │ • Multi-Tenant│
│   /approve, /dispatch        │ • Cross-Agent Broadcasts     │ • Audit Logs  │
└──────────────────────────────┴──────────────────────────────┴───────────────┘
```

### 6.1 Edition Tiering

1. **Personal Edition (Single Developer / Solo Operator)**:
   - **Target**: Individual engineers working locally across CLI, Herdr, and mobile.
   - **Topology**: Lightweight bot daemon connected via WebSocket Gateway (`goal-f4ce526a`). Delivers milestone alerts, cost drift warnings, and fence notifications to a private channel or DM.
   - **Interactions**: Simple slash commands (`/approve #pr`, `/dispatch <task>`, `/status`, `/kill <task>`). Zero external infrastructure required.

2. **Team Edition (Shared Engineering Guild)**:
   - **Target**: Small-to-medium engineering teams collaborating across multi-agent workflows.
   - **Topology**: Shared Synlynk Discord Guild. Auto-provisions temporary channels dynamically mirrored 1:1 to live Herdr agent sessions (lifecycle matches pane creation and close).
   - **Identity & Access**: Enforces W4 member roster linking (`/link` slash command with GitHub OAuth verification). Role-based visibility hides session channels from non-members.
   - **Interactions**: Team members can inspect streaming output, review companion signals, and inject steering prompts into active agents directly from Discord desktop or mobile.

3. **Enterprise Edition (Multi-Tenant Org & Compliance)**:
   - **Target**: Large enterprise organizations with strict governance, audit, and security requirements.
   - **Topology**: Dedicated private Discord or Slack enterprise gateway with high-availability NATS message brokers (`goal-ef42902a`, `goal-d8cb407d`).
   - **Governance & Audit**:
     - Strict SAML / Okta / Azure AD SSO mapping to W4 enterprise identities.
     - Multi-tenant workspace routing ensuring zero data leakage across departmental tenants.
     - Tamper-evident, cryptographically signed audit logs for every command, prompt injection, and gate approval.
     - Hard enforcement of `.synlynk/policy.json` merge authority and gate policies prior to command dispatch.

---

## 7. Framework Registration & Configuration

Companion v2.1 maintains strict backward compatibility with the [Configurability Framework](2026-10-31-configurability-framework-design.md).

### 7.1 Settings Schema

Registered via `synlynk.features.registry.register_feature`:

| Key | Type | Default | Description |
|:---|:---|:---|:---|
| `stage` | enum or `null` | `null` (auto-infer) | `onboarding \| companionship \| sounding_board \| policy_maker \| recruiter \| champion` |
| `theme` | string | `"standard"` | Built-in archetype name or discovered pack name |
| `voice_density` | enum | `"full"` | `full \| low \| off` |
| `remix` | enum | `"off"` | `off \| milestone_only` |
| `segment` | enum or `null` | `null` (auto-infer) | `novice \| skeptic \| accelerant \| architect` |
| `domain_vocab` | object | `{}` | Key-value string replacement mapping for template lines |
| `channels` | list[string] | `["cli"]` | Active surfaces: `cli`, `vizor`, `vscode`, `discord`, `slack`, `herdr` |
| `deep_links` | boolean | `true` | Enable contextual deep-link generation for GitHub & Vizor |
| `discord_edition` | enum | `"personal"` | `personal \| team \| enterprise \| off` |

### 7.2 Configuration CLI Commands

```bash
# Enable/disable feature
synlynk config feature companion enable|disable

# Configure core attributes
synlynk config feature companion set theme stoic_mentor
synlynk config feature companion set voice_density low
synlynk config feature companion set discord_edition team

# Manage channel enablement
synlynk config feature companion channels add vizor vscode discord
synlynk config feature companion channels list

# Manage domain vocabulary substitutions
synlynk config feature companion vocab set story campaign
synlynk config feature companion vocab list
synlynk config feature companion vocab remove story
```

---

## 8. Compatibility & Invariants

1. **Non-Breaking Fencing Contract**: `fencing.py` continues to invoke registered contributors via `_HINT_CONTRIBUTORS`. If Companion is disabled or has no hints to offer, `render_task_fence()` behavior is completely untouched.
2. **Zero Runtime Overhead when Disabled**: If `companion.enabled == false`, the contributor callback executes a single boolean check and returns immediately.
3. **No Circular Imports**: `fencing.py` never imports `synlynk.companion`. Registration occurs at feature bootstrap time in `synlynk/companion.py`.
4. **Deterministic Static Defaults**: Static templates require zero network calls, zero LLM tokens, and execute in under 1ms.
5. **Safe Fail-Open on Content Gaps**: Unrecognized theme names fallback to `"standard"` with persistent warnings, never crashing the CLI or task pipeline.

---

## 9. Testing & Verification Plan

1. **Unit Tests**:
   - `tests/test_companion_topics.py`: Verifies all 4 topics produce valid messages adhering to the 4-part anatomy (`[Signal]`, `[Context]`, `[Nudge]`, `[Deep Links]`).
   - `tests/test_companion_deep_links.py`: Tests `resolve_github_link` and `resolve_vizor_link` against remote URLs and local entity IDs; tests OSC 8 ANSI escape sequence rendering.
   - `tests/test_companion_renderers.py`: Tests formatting across CLI, Vizor JSON, VS Code, Discord Embed, and GitHub markdown.
   - `tests/test_companion_discord_bridge.py`: Tests Personal vs Team vs Enterprise channel provisioning, W4 identity check, and rate-limiting throttling logic.
2. **Regression & Invariant Tests**:
   - `tests/test_fencing_hint_contributors.py`: Asserts `fencing.py` has no named imports of `companion`.
   - `tests/test_companion_pinning.py`: Verifies stage and segment inference remains pinned per command invocation.
3. **End-to-End Verification**:
   - Test CLI fence output with deep links enabled and disabled.
   - Test Discord mock bot receiving Companion events and posting formatted embeds with action buttons.

---

## 10. Out of Scope

- Implementing the Discord bot daemon, Herdr IPC adapters, or VS Code extension UI (reserved for implementation phase).
- Redesigning the FTUE onboarding journey in `onboarding_state.py`.
- Creating proprietary franchise theme packs.
- Third-party chat networks outside Discord and Slack.
