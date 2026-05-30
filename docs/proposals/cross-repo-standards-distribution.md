# Proposal: Cross-Repo Standards Distribution Mechanism

**From:** Claude Sonnet 4.6 (rxcc session, 2026-05-30)  
**To:** Synlynk inbox — for Synlynk to design, build, and distribute  
**Status:** Proposal only — no implementation attempted from rxcc  
**Related:** `rxcc-wow-observations.md` (the problem context)

---

## The Problem

A solo engineer working with 3 agents across 4+ repos has no mechanism to:

1. **Propagate a standard** decided in one repo to all other repos without manually editing every `CLAUDE.md` and `GEMINI.md`
2. **Share live cross-repo state** (what each agent is working on, which branches are active) so agents in one repo don't step on work happening in another
3. **Collect observations** from each repo and synthesise them into protocol without the collecting repo writing the protocol (boundary violation)
4. **Onboard a new repo** into the workgroup with a consistent set of behavioural contracts for all agents

The specific failure this caused in rxcc (S-037): Claude had no way to know Gemini was mid-commit on a branch, pushed to it, and caused a 30-minute recovery. A live WIP signal accessible to all agents would have prevented this.

---

## What Is Needed (Not How to Build It)

### 1. An Observations Inbox

A designated place where each repo deposits observations, discovered failure modes, and proposed improvements — without writing any cross-repo protocol itself. Repos write observations. Synlynk reads them and decides what to standardise.

The `rxcc-wow-observations.md` file in this directory is an example of an inbox item. The mechanism for how Synlynk processes the inbox and decides what to standardise is entirely Synlynk's design.

### 2. A Standards Distribution Mechanism

Once Synlynk derives a standard from observations, it needs to reach every agent in every repo automatically — not via copy-paste, not via manual edits to each repo's instruction file. The distribution must be:

- **Automatic:** When the standard changes, all repos see the update on the next agent session without manual intervention
- **Agent-scoped:** Claude gets Claude standards, Gemini gets Gemini standards, Codex gets Codex standards
- **Hierarchical:** Global standards (apply everywhere) + repo-specific overrides (where a repo legitimately differs)
- **Auditable:** An agent in repo X should be able to see which standards it's operating under and where they came from

The right distribution layer is probably somewhere in the local machine environment (dotfiles, `~/.synlynk/`, or similar) since that's already the shared substrate for all repos on a given machine. But Synlynk should decide the exact mechanism.

### 3. A Live Cross-Repo State Signal

Agents in one repo need visibility into what agents in other repos are currently doing. Minimum needed:

- Which branches are active per repo, and which agent owns them
- Which issues have work-in-progress (agent has started, hasn't opened PR yet)
- Any cross-repo dependencies (repo A's feature depends on repo B's PR)

This state needs to be injected into an agent's context before it starts work, not looked up reactively. The current `synlynk exec` context injection is the right place for this. The missing piece is the state store and the mechanism for agents to update it when they start/finish work.

### 4. A Repo Onboarding Bootstrap

When a new repo joins the workgroup, there needs to be a checklist and a command that:

- Creates the minimum required file structure (agent instruction files, CI workflows, docs structure)
- Applies the current global standards (not a snapshot — the live standards, so the repo stays current)
- Registers the repo in whatever cross-repo coordination mechanism Synlynk uses

This should be a single command, not a manual process.

---

## Claude's Additional Observations for Synlynk's Design

*These are inputs, not prescriptions. Synlynk decides how to act on them.*

**On the inbox pattern:** The observations-then-protocol separation is important. When an agent writes an observation, it should not simultaneously propose the implementation. The implementation is Synlynk's domain. If this distinction isn't enforced in the inbox format, agents will start writing protocols for other repos, which is exactly the boundary violation the inbox exists to prevent. Consider a template or schema for inbox items that separates "what broke" from "how to fix it" — and explicitly reserves "how to fix it" for Synlynk.

**On standards staleness:** Standards derived from observations become stale as repos evolve. A standard about ECS deployment derived from an rxcc observation in May 2026 may be wrong for a Lambda-based repo onboarded in September 2026. The distribution mechanism needs a versioning or freshness signal so agents know when a standard might not apply to their context.

**On agent asymmetry:** Claude has persistent cross-session memory (the `~/.claude/projects/` structure). Gemini and Codex don't — each session is cold. Any cross-repo coordination mechanism needs to account for this asymmetry. Standards that rely on agents "remembering" what they were told last session will work for Claude and fail for Gemini. The distribution mechanism must inject standards fresh into every session, not rely on memory.

**On the cost of coordination overhead:** The rxcc session that generated these observations cost real time and money — estimated 45+ minutes of session time and multiple $ in API costs, just on the CI cascade and agent boundary recovery. The value of the coordination mechanism is proportional to how much of this overhead it eliminates. If the mechanism itself requires significant manual maintenance (editing config files, running sync commands, resolving conflicts), the net benefit may be negative. The bar for "Synlynk solution" should be: zero manual steps for an agent session to pick up current standards and live cross-repo state.

**On the multi-machine problem:** The rxcc workgroup currently runs on a single machine. If the engineer works across machines (e.g., laptop + desktop), the cross-repo state store needs to be accessible from both. Local files work for single-machine; cloud-backed state (or a git repo as state store) works for multi-machine. Synlynk may want to design for multi-machine from the start even if the initial implementation is local-only.

---

## What This Proposal Does Not Attempt

- No implementation details for Synlynk internals
- No edits to dotfiles or global CLAUDE.md from this repo
- No schema or file format decisions for the standards distribution layer
- No commands or scripts

Those are all Synlynk's decisions to make with full context in its own session.

---

*Deposited from rxcc session S-037, 2026-05-30. Ready for Synlynk to process when context allows.*
