# Strategic Analysis: synlynk as a Standalone Harness

**Date:** 2026-06-29  
**Author:** Agy (Gemini)  
**Status:** Brainstorm / Proposal  

---

## 1. Executive Summary

This document evaluates the strategic and architectural implications of transitioning **synlynk** from a meta-wrapper of external AI agent harnesses (such as `claude`, `codex`, and `grok` CLIs) to hosting its own native execution harness.

By direct API integration with LLM providers (Google Gemini, Anthropic, xAI, OpenAI) and executing a native tool loop, synlynk can eliminate harness drift, establish precise host sandboxing, and provide zero-latency state and context tracking.

---

## 2. Rationale for Transition

Currently, synlynk operates by spawning external CLIs as subprocesses:

```
synlynk CLI/TUI -> subprocess.Popen() -> Vendor CLI (claude/grok/codex) -> Model API
```

This meta-wrapping strategy has critical limitations:
1. **Harness Drift:** Vendor CLIs frequently release breaking updates, deprecate flags, and change command/slash syntaxes. Keeping [AGENT_CAPABILITY_BASELINES](file:///Users/nikhilsoman/dev/synlynk/synlynk/__init__.py#L455) aligned requires constant patching.
2. **Process Boundaries:** Because execution happens in a separate CLI process, synlynk has no turn-by-turn insight. It must write prompt files to disk and parse raw stdout/stderr logs post-completion to extract telemetry, tokens, and exit codes.
3. **Imprecise Sandboxing:** We are dependent on the security properties of the guest CLIs (e.g. Codex's `-s workspace-write`). We cannot easily enforce granular, path-specific read/write permissions or intercept network requests at the system level.
4. **Sub-optimal Context Injection:** We force context files (like `CLAUDE.md`, `GEMINI.md`, and `.cursorrules`) onto tools, which clutter the workspace and are prone to user or agent edits (drift).

---

## 3. Native Harness Architecture

A standalone harness architecture would connect directly to model APIs and control the execution loop locally:

```
synlynk CLI/TUI -> Native Loop Controller -> Model APIs (Google, Anthropic, xAI)
                         │
                         ├─> Native System Tools (PTY Terminal, File Ops, Search)
                         └─> Sandbox & Permission Gatekeeper
```

### Key Components to Build

1. **Loop Controller & Turn Manager:** A state machine executing a standard `Thought -> Tool Call -> Tool Execution -> Tool Output` loop. Allows direct meta/milestone/story goal injection into system prompts and on-the-fly context compaction.
2. **Model API Client Gateway:** A structured gateway wrapping model endpoints (Vertex/Gemini, Anthropic Messages API, OpenAI-compatible APIs) with streaming, structured tool-call (function-calling) parsing, and token/rate limit tracking.
3. **Native Tool Suite:** A set of atomic system tools exposed to the model:
   - File Operations: `read_file`, `write_file`, `replace_file_content`, `list_dir`, `grep_search`.
   - Terminal Execution: A process wrapper running commands inside an interactive PTY to support interactive prompts (`npm install`, interactive Git, etc.).
4. **Permissions & Sandbox Gatekeeper:** A policy engine intercepting tool calls. Allows configuring path-level write locks (e.g., locking config directories) and interactive terminal command approvals inside the synlynk TUI or shell prompt.
5. **MCP (Model Context Protocol) Host:** Enables connecting to external tool servers (databases, browser automation, search engines) out-of-the-box, keeping the core synlynk repository lightweight.
6. **Context Compaction Engine:** An algorithmic summarizer that condenses older messages once conversation history crosses context threshold limits (e.g., 70% of model window).

---

## 4. Comparison of Run Environments

| Dimension | Wrapper Mode (synlynk Today) | Native Harness Mode (synlynk Go-It-Alone) | Other Harnesses (Claude Code, Cursor, etc.) |
| :--- | :--- | :--- | :--- |
| **Model Connection** | Process pipe; no direct API connection. | Direct HTTPS/WebSocket streams to API endpoints. | Direct API connections. |
| **OS Interface** | Spawns child processes. | Direct OS calls, custom PTY manager. | Uses interactive PTY (`node-pty`). |
| **Tool Calling** | Implicit. Prompts tell agent how to use tools. | Explicit. Uses model-native JSON schemas. | Standard JSON-schema function calling. |
| **Permissions** | Pre-exec gates or guest constraints. | In-loop, granular path and command ACLs. | Coarse-grained host access or containerization. |
| **Loop Control** | Single-shot process execution. | Loop controller (`dispatch_loop`) controls turns. | Session-scoped loop, no multi-session context. |

---

## 5. Transition Path (Dual-Mode Execution)

We do not need to rewrite the entire tool overnight. We propose a staged rollout:

*   **Phase 1 (v0.10.x - v1.0.0): Coexistence.** Build `synlynk-agent` as a native runner option, default disabled. If API keys are present, developers can opt-in to native execution; otherwise, synlynk continues to spawn external CLIs.
*   **Phase 2 (v1.0.0+): Native Primacy.** Promote the native runner to primary execution model. Retain wrappers only as fallback interfaces or legacy compatibility wrappers. Update the Capability Ledger scoring to track model APIs and domain competence instead of CLI wrappers.
