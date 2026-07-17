# Command Taxonomy, Maturity-Tiered Reveal, and Trigger Registry

**Date:** 2026-07-17
**Status:** Design approved, not yet planned/implemented
**Supersedes:** #262 (Surface consolidation: declare 5 daily commands, demote the rest)

---

## Why this exists

Issue #262 asked for something narrow: pick 5 daily commands, demote the rest from README/FTUE to reference docs. Working through it surfaced that the real command surface is much larger than the docs suggest — **~45 commands and subcommands** are registered in `synlynk/cli.py`, versus ~19 visible in `README.md`. A flat "top 5" list can't represent that gap honestly, because:

1. Not every command is meant for a human to type. Some exist purely for synlynk's own autopilots/hooks to invoke (`relay`, `checkpoint`, `daemon`, `instructions ack`, etc.) — these should never compete for a human's attention regardless of how experienced the user is.
2. What's "essential" changes as a user/repo matures. A brand-new repo needs `init`/`scan`; a repo with months of history needs `dispatch`/`jobs`. A single flat list can't represent that.
3. synlynk's product philosophy (stated directly by the founder during this design session): **"we live inside somebody else's home — we don't really have an interface ourselves."** The goal is not to build a command browser UI that users are asked to learn. The goal is to disappear into existing developer habits — surfacing the right verb at the right moment, mostly without the user needing to know the taxonomy exists at all.

This spec defines the data model that makes both of those things possible — command classification (Phase 1), the FTUE/README consolidation it enables (Phase 2, which retires #262), and a trigger registry so the right command gets reached for automatically, whether by a human talking to an agent or by a real git hook (Phase 3). Two follow-on phases (ambient ordinary-time HUD surfacing, and taxonomy-browsing UI inside `watch`/`viz`) are named but explicitly out of scope here — see "Out of scope."

---

## Section 1 — Data model

A new module, `synlynk/taxonomy.py`, holds a single source-of-truth registry: `COMMAND_TAXONOMY`, a list of per-command entries. Each entry carries independent tags — deliberately independent, because they answer different questions:

| Field | Question it answers | Values |
|---|---|---|
| `command` | What is it | e.g. `"dispatch"`, `"relay start"` |
| `governs_stage` | Which SDLC stage does this serve? (routing axis, used for trigger/hook wiring) | `goal \| open \| visualize \| execute \| release \| notify \| sustain` |
| `maturity_tier` | When in a user's journey should this ever surface? (reveal axis) | `0` (FTUE) \| `1` (Goal) \| `2` (Execute) \| `3` (Team/Enterprise) \| `"latent"` (never promoted — autopilot/hook only) |
| `prominence` | Within its tier, is this promoted or reference-only? | `"primary"` \| `"secondary"` \| `None` (latent commands have no prominence) |
| `orientation_gateway` | Is this one of the fixed orientation points, independent of tier? | `bool` — `true` only for `status`, `watch`, `viz` |
| `audience` | Who actually invokes this? | `"human"` \| `"pilot"` \| `"hook"` |
| `trigger_phrases` | Conversational phrases that should make an agent reach for this command | `list[str]`, empty for non-human-audience commands |
| `hook_event` | A real mechanical event that should fire this command, if one exists | `"pre-commit"` \| `"pre-push"` \| `None` |

Example entries:

```python
COMMAND_TAXONOMY = [
    {
        "command": "dispatch",
        "governs_stage": "execute",
        "maturity_tier": 2,
        "prominence": "primary",
        "orientation_gateway": False,
        "audience": "human",
        "trigger_phrases": ["let's build X", "can you implement...", "hand this to codex"],
        "hook_event": None,
    },
    {
        "command": "status",
        "governs_stage": "visualize",
        "maturity_tier": 0,
        "prominence": "primary",
        "orientation_gateway": True,   # available from Tier 0, never demoted as tier advances
        "audience": "human",
        "trigger_phrases": ["where are we", "what's the state of things"],
        "hook_event": None,
    },
    {
        "command": "relay start",
        "governs_stage": "execute",
        "maturity_tier": "latent",
        "prominence": None,
        "orientation_gateway": False,
        "audience": "hook",
        "trigger_phrases": [],
        "hook_event": None,
    },
    {
        "command": "instructions ack",
        "governs_stage": "sustain",
        "maturity_tier": "latent",
        "prominence": None,
        "orientation_gateway": False,
        "audience": "hook",
        "trigger_phrases": [],
        "hook_event": "pre-commit",
    },
]
```

This shape deliberately mirrors the existing `LAUNCH_TASK_TEMPLATES` structure in `synlynk/__init__.py` (which already has a `cycle` field using GOVERNS naming and a `trigger_condition` field) — same spirit, extended with the new tags this design adds.

### The orientation gateway

`status`, `watch`, and `viz` are not peers to `dispatch`/`schedule`/`release`. They are the fixed point a developer returns to after going down an implementation tunnel — `status` is synlynk telling you where things stand (text), `watch` and `viz` are the two live views (terminal and browser) most developers actually live in. All three:

- Are available from **Tier 0 onward** — never gated behind maturity, since the orientation layer should never need to be "unlocked"
- Are **never demoted** to secondary as the user's tier advances (every other `primary` command cycles to `secondary` once the user moves past the tier where it's freshest)
- Are the intended long-term home for taxonomy browsing (see "Out of scope" — Phase 5)

### Full command classification

The complete classification of all ~45 currently-registered commands (derived from `synlynk/cli.py`'s `add_parser()` calls) is maintained as the initial contents of `COMMAND_TAXONOMY` at implementation time, not duplicated here as a second source of truth. Summary by tier:

| Tier | Count | Primary examples | Secondary examples |
|---|---|---|---|
| 0 — FTUE | 8 | `init`, `scan`, `join` | `migrate`, `agent add/configure/list`, `config set` |
| 1 — Goal | 8 | `decide`, `goal *`, `story *`, `open`, `launch` | — |
| 2 — Execute | 16 | `dispatch`, `jobs`, `schedule`, `release`, `pr` | `doctor`, `probe`, `exec`, `logs`, `shell`, `sentinel *`, `cost log`, `run --trio`, `local doctor`, `upgrade` |
| 3 — Team/Enterprise | 4 | `team status`, `sync` | `score *`, `roles` |
| Gateway (tier-independent) | 3 | `status`, `watch`, `viz` | — |
| Latent (autopilot/hook) | 9 | — | `relay *`, `checkpoint`, `daemon`, `identity init`, `repair`, `exit`, `instructions *` |

Notes on two deliberate calls:
- `doctor` is classified **secondary**, not primary, despite appearing in Fable's original "5 daily commands" proposal — it's a periodic health check, not a daily-driver verb. Flagged for revisit if this doesn't match real usage once telemetry exists.
- Tier 2 has 8 primary commands, larger than the founder's own stated daily habit (`dispatch` + `jobs`). Deliberately left at 8 rather than narrowed further — the intent is that **context (Phase 4, out of scope here) does the narrowing at display time**, not a smaller static list.

---

## Section 2 — FTUE / README consolidation (retires #262)

- **README** restructures around the orientation gateway plus the current-tier primary set: a "Start here" block leads with `init`/`scan` (Tier 0), with `status`/`watch`/`viz` framed as "run any time to see where you are." Every other command moves to a new `docs/reference/commands.md`, **generated from `COMMAND_TAXONOMY`**, not hand-maintained.
- **FTUE wizard** (`synlynk init --wizard`) launch cheat-sheet screen only surfaces Tier 0 `primary` commands, plus a one-line pointer to the orientation gateway.
- **`synlynk launch`** picker (Tier 1) only shows Tier 1 `primary` commands as task templates — consistent with today's `LAUNCH_TASK_TEMPLATES` behavior, now driven by the same taxonomy instead of a separate hardcoded list.
- A generation script (invoked in CI) asserts `README.md`'s command table and `docs/reference/commands.md` stay in sync with `COMMAND_TAXONOMY` — this directly prevents the class of bug #263 just fixed (three/four hand-written, silently-diverging vocabularies) from recurring in the command-docs surface.

---

## Section 3 — Trigger registry

Two independent delivery mechanisms, sharing the same `trigger_phrases` / `hook_event` fields defined in Section 1.

**Agent-context injection.** Reuses the existing `synlynk:start/end` fencing mechanism already implemented in `synlynk/instructions.py` (built for the BS-7 skill-pack coexistence work). A new sub-section inside that fence lists `trigger_phrases → command` pairs — but **scoped to the current repo's maturity tier**, not the full 45-command set. A Tier 0 repo's injected context only contains Tier 0 + gateway phrases; as the repo's tier advances (tracked via existing state.db signals), the injected phrase set grows. This keeps `CLAUDE.md`/`AGENTS.md` lean and matches the "abstract away complexity" principle directly — the agent only ever sees phrases relevant to where this particular user actually is.

**Real hooks.** Only commands with a genuine mechanical event get an actual git hook — most human-audience commands (`dispatch`, `story create`) stay phrase-only, since there's no clean mechanical trigger for "I want to delegate this," it's inherently conversational. Where a real event exists, `hook_event` names it (`"pre-commit"`, `"pre-push"`). `synlynk/instructions.py`'s existing drift-detection logic is effectively already a proto-hook for the `instructions status/diff/update/ack` latent bucket; this phase formalizes it as an installed pre-commit hook, following the same `synlynk init`-installs-hooks pattern already planned for the (separate, still-unbuilt) `git-drift` tool.

---

## Section 4 — Testing

- **Coverage test:** every command registered via `add_parser()` in `synlynk/cli.py` has a corresponding `COMMAND_TAXONOMY` entry. Fails loudly if a new command ships unclassified — the same discipline #263 established for stage vocabulary, one level up.
- **Docs-sync test:** generated `README.md` command table and `docs/reference/commands.md` match current `COMMAND_TAXONOMY` output byte-for-byte (regenerate-and-diff, not hand assertions).
- **Tier-scoping test:** agent-context injection for a Tier 0 fixture repo contains only Tier 0 + gateway trigger phrases; a Tier 2 fixture repo contains the superset up through Tier 2.
- **Hook-install test:** extends existing `instructions.py` drift tests to cover the new pre-commit hook installation path triggered by `synlynk init`.

---

## Out of scope (named follow-on work, not built here)

1. **Ambient HUD surfacing** — git-state + job-state-driven "what's relevant right now" rendering inside `watch`/`viz`. This spec defines the taxonomy that surfacing will eventually read from; the context-aware rendering logic itself is a separate spec.
2. **Taxonomy-browsing UI inside `watch`/`viz`** — Section 2 retires the *need* for a standalone reference-map command by moving detail to generated docs, but building an actual interactive drill-down view into `watch`/`viz` is follow-on work.
3. **Tier 3 (Team/Enterprise) command set growth** — this spec classifies what exists today; new paid-tier commands get taxonomy entries when Epic 4/5 (Team Control Plane, Governance Pack) actually ship commands.
4. **Maturity-tier detection logic** — this spec assumes a signal already exists (state.db job history + git activity, partially present via the BS-20 scan-delta work) to determine which tier a given repo is in. Formalizing/hardening that detector is assumed infrastructure, not built fresh here — flagged explicitly so it isn't silently assumed away during planning.

---

## Sources consolidated

- Issue #262 (surface consolidation, superseded by this spec)
- `docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md` (Horizon 0 item 4, origin of the "5 daily commands" framing)
- `docs/superpowers/specs/2026-07-16-gtm-checklist-agenda.md` (GTM item 4 — trigger hardening; GTM item 5 — onboarding hardening)
- `docs/superpowers/specs/2026-06-27-bs7-skill-pack-interoperability-design.md` (`synlynk:start/end` fencing mechanism, reused here)
- `synlynk/__init__.py` `LAUNCH_TASK_TEMPLATES` / `CORE_TEMPLATE_IDS` (existing precedent for this data shape)
- `synlynk/cli.py` (full command inventory, ~45 commands/subcommands as of 2026-07-17)
- `docs/superpowers/specs/2026-07-17-adoption-priority-stack-rank.md` (item 4 — surface consolidation — and item 6 — GTM item 4 triggers — both folded into this spec)
