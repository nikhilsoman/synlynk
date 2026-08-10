# Glossary: Agent vs Harness

synlynk uses two related but distinct terms. Getting them right matters because the design spec at
`docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` builds an entire dispatch
and calibration model on the distinction.

## Agent

An **Agent** is a persistent identity: a role, a charter, and (per the design spec's §10 roadmap)
eventually memory and access grants of its own. Agents are *what* work happens under and *who* is
accountable for it.

synlynk's 8 Agents (defined in the design spec's §2) are:

| Agent | Charter |
|---|---|
| pm | Represents the human user; owns major decisions and Named Release sign-off |
| architect | Owns Spec + Plan; does PR review and holds merge authority |
| tpm | Tasking, tracking, and reporting |
| dev | Implementation |
| designer | UI/UX |
| qa | Test coverage, CI/CD, IaC, deployments |
| marketing | End-user-facing comms, including every PR's blog post |
| synlynk-bot | Shared automation identity for durable Agents' scheduled writes (not itself a role) |

Each Agent has a GitHub App identity (provisioned under issue #859), so its actions attribute to the
Agent, not to whichever Harness happened to execute them.

## Harness

A **Harness** is a swappable *execution backend* — the AI CLI tool that actually runs a dispatched
task. synlynk's harnesses today are:

- Claude
- Agy (Gemini)
- Grok
- Codex
- local

Harnesses have no charter and no standing accountability of their own — they're selected per-task by
capability fit (see the design spec's §3, "Role → Tool-Agent Dispatch Policy"). The same Agent's work
(e.g. `dev`) can be executed by different Harnesses on different tasks.

## Why the distinction matters

Before issue #859, synlynk had no Agent identity layer — every GitHub write from every Harness
attributed to one shared personal identity (issue #569). Conflating "Agent" and "Harness" in
docs/config made it easy to write policy (like issue #426's "route GitHub writes to Grok by default")
that was really compensating for a missing Agent-identity layer, not a real Harness-capability
constraint. The design spec's §3.2 retires that policy now that Agent identity is real.

**Rule of thumb:** if you're asking "who is accountable for this and what's their charter," you mean
Agent. If you're asking "which AI CLI tool should execute this," you mean Harness.

## Related docs

- `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` — full Agent role design,
  dispatch policy, and the Phase 0-4 roadmap this glossary is Phase 0 of.
- `CLAUDE.md`'s "Terminology: Agent vs Harness" section — the short in-repo pointer to this doc.
