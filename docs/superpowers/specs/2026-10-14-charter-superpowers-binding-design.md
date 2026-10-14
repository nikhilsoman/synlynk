# Charter Superpowers-Skill Binding Design

Date: 2026-10-14
Status: Draft, pending review
Related: gh:#2305 (tracking issue), `docs/superpowers/specs/2026-08-27-charter-content-structure-design.md`
(frontmatter schema this design extends), `docs/superpowers/specs/2026-08-27-charter-authority-design.md`
(injection mechanism this design reuses unchanged)

## 1. Motivation

synlynk's charter system governs *who* does work (role, mandate, authority, escalation triggers) but has no
mechanism for *how* work gets done — specifically, which superpowers skills (`test-driven-development`,
`systematic-debugging`, `brainstorming`, etc.) a dispatched agent is expected to invoke for a given task. An
interactive home session gets this discipline for free via the `using-superpowers` SessionStart hook, which
explicitly forces skill invocation ("if 1% chance a skill might apply, you must invoke it"). A dispatched headless
job (Codex/Grok/Agy) gets no equivalent signal at all. This is the "item 5" gap identified in the 2026-10-14
master-plan recap, filed as gh:#2305.

## 2. Current State (confirmed by direct code inspection, 2026-10-14)

Two disconnected "charter" concepts exist:

1. **`AgentCharter` dataclass** (`synlynk/charters.py:14`) — JSON-backed (`.synlynk/charters/<role>.json`), used only
   by `detect_charter_divergence`/`cmd_charters_adapt` (capability-drift detection). **Never read by
   `dispatch.py`** — confirmed via `grep -n "load_charter\|AgentCharter" synlynk/dispatch.py` returning zero hits.
   This path has no bearing on what a dispatched job actually receives.
2. **Agent-store markdown charters** (`agent_store.py` + `charter_schema.py`) — these ARE injected into a
   dispatched job's context via `charter_injection.render_charter_section()`, called from `dispatch.py:2417-2423`.
   Per the 2026-08-27 content-structure design, their frontmatter schema has a required set of keys
   (`schema_version`, `role`, `description`, `durability`, `tools`, `credentials`) plus an optional,
   unenforced `skills:` key. Today `skills:` is populated only by `adapt_charters_for_installed_tools()`
   (`charters.py:181`) for two hardcoded external tools (`graphify`, `testbed`) via the `TOOL_ROLE_SKILLS` map —
   never for general superpowers skills. Confirmed via repo-wide grep for `"skills"` across `synlynk/*.py`: the
   only other references are read-only display code (`agent_cli.py` prints the synced list; `scan.py`/`wizard.py`
   handle an unrelated per-repo tool-detection "skills" concept).
3. Even where `skills:` is populated, `render_charter_section` renders the full charter `content` string verbatim
   (confirmed in `charter_injection.py:44-48`) — a `skills:` frontmatter list appears as **inert YAML text** in the
   dispatched context. Nothing tells the harness those skills are binding, let alone *why* or *when* to invoke
   them. There is no equivalent of the `using-superpowers` skill's forcing language anywhere in the charter
   rendering path.

Net effect: charters currently express zero behavioral-discipline binding. A `dev`-role dispatched job has no
charter-level nudge toward `test-driven-development`; a `qa`-role job has none toward `systematic-debugging`.

## 3. Decision

### 3.1 Extend the existing `skills:` frontmatter key — don't add a new one

`charter_schema.py`'s frontmatter parser already round-trips a `skills:` list (used today for tool-derived
skills). This design reuses that same key for superpowers skills rather than inventing e.g. `superpowers:` or
`bound_skills:` — one list, two sources feeding it (tool-detection, role-default), merged the same way
`adapt_charters_for_installed_tools` already merges `existing_skills` with `active_role_skills`.

### 3.2 New static role→skills mapping: `ROLE_SUPERPOWERS_SKILLS`

Add to `synlynk/charters.py`, alongside the existing `TOOL_ROLE_SKILLS` map:

```python
ROLE_SUPERPOWERS_SKILLS: dict[str, list[str]] = {
    "dev": ["test-driven-development", "systematic-debugging"],
    "builder": ["test-driven-development", "systematic-debugging"],
    "qa": ["systematic-debugging"],
    "verifier": ["systematic-debugging"],
    "architect": ["brainstorming"],
    "pm": ["brainstorming"],
    "tpm": ["brainstorming"],
}
```

This is a starting mapping based on each role's documented mandate (dev/builder write and debug code; qa/verifier
debug failures; architect/pm/tpm own the Brainstorm-First Policy's design stage) — not exhaustive, and expected to
grow via the same living-charter-drift mechanism `charters.py` already has for capability baselines. Roles not
listed get an empty list (no behavior change from today).

`adapt_charters_for_installed_tools` (`charters.py:181`) gains one more merge source alongside
`active_role_skills` (tool-derived): `ROLE_SUPERPOWERS_SKILLS.get(role, [])`. Both existing merge/dedup logic
(lines 215-218, 256-259) already handle a plain list union — no new control flow needed, just one more list fed
into the same `for s in ... : if s not in desired_skills: desired_skills.append(s)` loop.

This means `synlynk charters adapt` — the existing command, no new CLI surface — picks up superpowers-skill
binding immediately once this ships, the same way it already picks up tool-derived skills.

### 3.3 Render bound skills with enforcement language, not bare YAML

Today, `skills:` only ever reaches the dispatched harness as part of the raw frontmatter block inside
`content` (`render_charter_section` renders the full charter string verbatim). This design adds a rendering step
in `render_charter_section` (`charter_injection.py`): after resolving `content`, parse the `skills:` frontmatter
key via `charter_schema.split_frontmatter`/`parse_frontmatter` (already-existing functions, no new parser), and if
non-empty, append a short explicit section:

```
## Bound Skills (required)

This role's charter binds the following skills for this dispatch. If your harness supports an
equivalent skill/tool-loading mechanism, invoke it before proceeding — these are required, not optional,
for tasks they apply to:
- test-driven-development
- systematic-debugging
```

This mirrors the forcing language already proven effective in Claude's own `using-superpowers` skill, phrased
harness-agnostically (not every harness has a `Skill` tool) so a Codex/Grok/Agy job gets the instruction as plain
directive prose it can act on however its own tool surface allows.

### 3.4 Fate of the dead `AgentCharter`/`load_charter` JSON path

Out of primary scope for this design. `charters.py`'s `AgentCharter` dataclass and `load_charter()` remain used
only by drift-detection (`detect_charter_divergence`/`cmd_charters_adapt`'s non-adapt-tooling half) — unaffected
by this design, since §3.2's new mapping lives in the *same file* but feeds the *markdown* charter path (via
`adapt_charters_for_installed_tools`), not the JSON dataclass path. No change to `AgentCharter` itself is proposed
here. Documenting this as a known, separate piece of dead-weight-with-respect-to-dispatch is useful context for a
reader of this spec, but reconciling or deprecating it is a separate follow-up, not blocking this work.

## 4. Error Handling

- A role not present in `ROLE_SUPERPOWERS_SKILLS` behaves exactly as today (empty list, no `## Bound Skills`
  section rendered) — no new failure mode.
- If a charter has no registered agent for a role (the existing `adapt_charters_for_installed_tools` fallback
  path to `SEED_CHARTERS`), the new skills still merge into the fallback's `desired_skills` the same way tool-
  derived skills already do (`charters.py:256-259`) — no special-casing needed.
- If `render_charter_section`'s frontmatter parse fails (malformed YAML), fail the same way the existing
  `charter_schema` validator already does elsewhere — don't silently swallow a parse error and omit the section;
  surface it through the same error path `propose_charter_revision`/`agent_cli.py edit` already use (per the
  2026-08-27 design's §5 Error Handling precedent).

## 5. Testing

- Unit test: `ROLE_SUPERPOWERS_SKILLS["dev"]` merges into `adapt_charters_for_installed_tools()`'s output
  alongside any active tool-derived skills, with no duplicates.
- Unit test: a role absent from `ROLE_SUPERPOWERS_SKILLS` (e.g. `designer`, `marketing`) is unaffected — output
  skills list unchanged from today's tool-only behavior.
- Unit test: `render_charter_section()` for a charter with a non-empty `skills:` frontmatter list includes the
  literal string `## Bound Skills` in its returned markdown; for an empty/absent `skills:` list, it does not.
- Integration-shaped test (synthetic charter fixture, no live dispatch): feed a charter with
  `skills:\n  - test-driven-development` through `render_charter_section` and assert the exact bound-skills
  section text appears verbatim in the rendered context, matching the template in §3.3.

## 6. Out of Scope

- Reconciling or deprecating the dead `AgentCharter`/`load_charter` JSON path (§3.4) — flagged, not fixed here.
- Building a generic harness-side mechanism that *verifies* a dispatched job actually invoked a bound skill
  (e.g. parsing job output for evidence of skill use) — this design only gets the binding into the dispatched
  context as a directive; enforcement-by-detection is future work, same declared-not-enforced status
  `tools`/`credentials` frontmatter fields already have per the 2026-08-27 design's §7.
- Expanding `ROLE_SUPERPOWERS_SKILLS` beyond the starting mapping in §3.2 — expected to evolve via normal PR
  review, not frozen by this spec.
- Any change to `charter_injection.py`'s resolution of *which* role's charter gets injected
  (`resolve_role_charter`/`human_authority_role`) — unchanged, this design only changes what's appended to the
  rendered section once a charter is already resolved.

## 7. Dependencies / Sequencing

- Depends on the 2026-08-27 charter-content-structure design already being implemented (it is — `skills:` key,
  `charter_schema` parse/split functions, and `adapt_charters_for_installed_tools`'s merge logic all exist today).
- No dependency on gh:#2294/PR #2301/#2303 (pytest verbosity shim) or gh:#2302/#2304 (unrelated side-findings from
  the same session) — independent thread.
- Independent of item 6 (auto-upgrade/bundled deps) and item 7 (Vizor revival) from the same master-plan recap —
  no shared code path.
