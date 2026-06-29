---
title: "Why We Need a Polyglot Harness"
date: 2026-06-09
series: "Building the OS for Multi-Agent Development"
post: 0
tags: posts
excerpt: "AI tools are not converging on one winner. They are diverging by design. The harness that runs them must speak all their dialects — or it isn't a harness at all."
---

The premise of synlynk is simple to state and surprisingly hard to argue against: you will not use one AI tool. You are not using one AI tool. You are already managing a small fleet.

And that fleet has no shared memory, no shared state, and no shared cost ledger. Every tool is an island.

---

## The Convergence Thesis Was Wrong

When the current generation of AI coding assistants launched, there was a reasonable bet that one would win. Google has the infra. Anthropic has the alignment story. OpenAI has the distribution. One of them would pull so far ahead that developers would standardize.

That did not happen. Instead, each model developed genuine, durable strengths:

- **Claude Code** excels at multi-file reasoning, long context, and architectural decisions. It is the agent you trust with your CLAUDE.md, your FHIR compliance logic, your Pulumi stacks.
- **Gemini CLI** is fast and cost-effective for high-volume file operations — scanning hundreds of files, generating UI variations, running batch transforms. Tasks where you want parallel throughput, not careful deliberation.
- **Codex (OpenAI)** provides a different perspective on testing and integration — its training data and world model diverge enough from Claude's that a Codex-generated test suite catches different failure classes.

This is not marketing copy. It is what falls out empirically when you run ~300 PRs through a trio of agents on a regulated medical software product and measure per-PR correctness, incident rate, and reviewer acceptance rate. The specialists are not equally good at everything — and that gap is reproducible and durable.

The convergence thesis was wrong because capability differentiation compounds. The more each model is trained on its own RLHF signal and deployment distribution, the more it diverges from the others in specific strengths. Multimodality, tool use, reasoning traces, context window size — each optimization exaggerates the specialization rather than erasing it.

**The correct bet is multi-model by default.** The wrong response is to build a single-model workflow and pretend.

---

## The Polyglot Problem

Using multiple AI tools is not the same as using one very capable tool multiple times. The problems compound:

**Context fragmentation.** Each tool has its own session. Claude Code knows your FHIR data model. Gemini does not. You switch to Gemini to draft some UI and it has no idea what `Patient.extension[0].url` means or that you have an embargo on the auth subsystem until the YC review. You re-explain. That re-explanation is not free — it costs tokens, time, and introduces error (you forget something you already told Claude).

**Decision amnesia.** You decided three weeks ago to use JioDLT instead of AWS SES for SMS in India. That decision lives in Claude's memory and in your CLAUDE.md. Gemini has never heard of JioDLT. It will happily suggest the AWS alternative.

**Cost invisibility.** You pay three separate bills. One to Anthropic, one to Google, one to OpenAI (or you run your own Codex). There is no single view of what a feature cost you across all three agents. No per-task cost attribution. No budget alarm that triggers when the feature branch runs long.

**Constraint drift.** You instruct Claude: "do not touch the payments module during the stability window." Claude obeys. You send a task to Gemini — it has no idea about the stability window. It happily refactors a component that touches the payments module. Now you have a conflict.

**Flatline blindness.** Claude can fail silently in a loop — retrying the same broken command, accumulating cost, making no progress. You are not watching. You do not know until you check 20 minutes later.

None of these are hypothetical. All of them happened, repeatedly, in the RxCC.me workgroup before synlynk existed.

---

## Why the Harness Must Be Polyglot

A harness that only supports Claude is not a harness — it is a Claude plugin.

The polyglot constraint is architectural, not a feature request. If the harness is implemented as a Claude-specific skill or an Anthropic API integration, it cannot propagate constraints to Gemini. It cannot collect costs from Codex. It cannot perform cold-start handoff to a new agent that has never seen your project.

**The harness must live outside all the tools.** It must operate at the layer beneath all of them — the OS layer.

What that means concretely:
- Context is stored in human-readable files (`project-docs/`), not in any model's memory API. Any tool can read them.
- Constraints are encoded in agent instruction files (`CLAUDE.md`, `GEMINI.md`, `AGENTS.md`), one per tool, all generated and maintained by the harness from a single source of truth.
- Costs are written to a ledger (`costs.md`) in a standard schema that any tool can read and any human can audit.
- Telemetry is structured JSON, tool-agnostic, readable by any downstream aggregator.
- The harness itself is a subprocess wrapper — `synlynk exec <cmd>` — which means it works with any CLI-addressable tool, now and in the future.

The single-file Python stdlib constraint is not an aesthetic choice. It is the implementation of the polyglot principle: a harness that requires pip dependencies, a specific runtime, or a cloud API is a harness that can fail or be unavailable when you switch tools. Zero dependencies means the harness is always there, regardless of what you are running underneath it.

---

## The OS Metaphor

The framing that crystallized in mid-2026 is: synlynk is the OS for multi-agent development.

Not a workflow tool. Not a context injector. The OS.

An OS manages processes (agent sessions), a filesystem (project state), IPC (agent-to-agent coordination), a scheduler (dispatch and routing), a shell (the CLI interface), and a security model (entitlements and sandboxing). Everything an OS does for programs, synlynk does for agents.

The implications cascade:

- **Kernel (v0.1–v0.3):** exec, telemetry, flatline, budget, project-docs ledger — the minimum viable process manager and state store.
- **Filesystem (v0.5):** SQLite WAL replacing flat files — consistent, queryable, concurrent-safe state.
- **IPC (v0.4–v0.6):** constraint propagation, job state machine, Architect→Build→Verify pipeline — agents communicating through a defined protocol rather than through the human.
- **Scheduler (v0.5–v0.7):** capability routing, daemon, async dispatch — assigning work to the right agent without human mediation.
- **Shell (v0.7–v0.9):** the `synlynk dispatch` interface, the review TUI — the human-facing control surface.
- **Ecosystem Interface (v0.8):** the Open Context Protocol and MCP server — any tool can subscribe to context, not just the ones synlynk knows about today.

This is not a metaphor chosen after the fact to make the roadmap sound grand. It is the shape that emerged from observing what broke in the RxCC.me workgroup and working backwards from the failure modes to the structural requirements.

---

## Where We Are and Where We Are Going

synlynk v0.3.0 is the kernel. The OS metaphor is aspirational but grounded: the architectural staircase from flat files through SQLite through HTTP context server through NATS leaf nodes is designed so that each step is independently useful and the path forward never requires a rewrite.

The eventual goal is **full autonomy**: a human describes an intent, the harness decomposes it into stories, routes each story to the appropriate agent, monitors execution, and surfaces the result for human review at the end — not in the middle. The human is the product owner and the merge gate, not the message-passing layer.

That autonomy is only possible through a polyglot harness. A single-model workflow cannot reach it because the model's specialization ceiling becomes the workflow's capability ceiling.

The posts in this series document the journey from kernel to OS, PR by PR.

---

*Next: [The Project That Built synlynk](./01-the-project-that-built-synlynk.md) — the RxCC.me hybrid workgroup, three cross-agent studies, and the failure modes that became the product requirements.*
