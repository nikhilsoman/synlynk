# Charter Content & Structure Design

Date: 2026-08-27
Status: Approved (design), pending implementation plan
Related: `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` (org chart, 8 roles),
`docs/superpowers/specs/2026-08-27-charter-authority-design.md` (PR #1193 — injection mechanism, harness-agnosticism,
human-authority-role reassignment; this spec is scoped to charter *content/structure*, not injection)

## 1. Motivation

Workspace agent charters exist for all 7 provisioned roles (pm, architect, tpm, dev, qa, designer, marketing —
`synlynk-bot` is an infra identity, not a role, and is out of scope) but have no enforced structure. Two concrete
problems surfaced while reviewing them this session:

1. **Inconsistent depth.** The built-in `SEED_CHARTERS` defaults in `synlynk/agent_cli.py` ranged from 33 to 373
   characters — most roles had a one-sentence placeholder (`dev`: *"Implementation — writes the code."*) while `pm`
   had substantially richer content (a weekly competitive-intelligence sweep, a capability/marketing-gap comparison
   doc, feature-proposal escalation). This session's provisioning pass upgraded all 7 to consistent, richer prose
   (now at charter revision 2), but in doing so `pm`'s replacement text **lost** the competitive-intelligence-sweep
   specificity that its original seed had, even though it gained other content (Named Release ownership, an explicit
   authority line). This is a content regression, not just a formatting one.
2. **No enforceable shape.** Charters are single free-text markdown blobs (`agent_store.py`: `read_charter` /
   `propose_charter_revision`, content-hash-versioned). Nothing checks that a charter actually covers the concerns a
   good charter needs — durability model, tool/credential access, escalation rules, workflow-stage ownership. A
   charter could be edited down to nothing and no code would notice.

Separately, `docs/superpowers/specs/2026-08-27-charter-authority-design.md` (merged via PR #1193) resolved *how and
when* charter content gets surfaced to a dispatched harness (inject via the shared `generate_context()` path, keyed
off a reassignable `human_authority_role` pointer rather than hardcoded to `pm`/Claude). That spec explicitly did not
address what should be *inside* a charter — this spec fills that gap. The authority spec's injection mechanism reads
charter content as an opaque string; nothing in this design requires changes to that mechanism, only to the content
it reads.

## 2. Current State (as of 2026-08-27)

- 7 agents provisioned, all at charter revision 2 (dev/qa/architect provisioned 2026-08-26; pm/tpm/designer/marketing
  provisioned 2026-08-27 this session).
- Charter storage: `~/.synlynk/workspaces/<workspace_id>/agents/<agent_id>/charter.md`, revisioned via
  `charter.revisions.jsonl` (revision, parent_hash, content_hash, actor, timestamp) — per-machine, not per-repo.
- A separate thin YAML projection exists per agent at `.synlynk/agents/<agent_id>.yaml` (in-repo, git-tracked):
  `agent_id`, `workspace_id`, `role`, `overrides.capability_grants`. Written by
  `agent_store.regenerate_agent_projection()`, called only from `agent_cli.py`'s `init`/`edit` handlers.
- **`overrides.capability_grants` is written but never read anywhere in the codebase** — confirmed via grep across
  `dispatch.py` and `agent_cli.py`. It is currently a dead placeholder for an enforcement mechanism that was never
  built. This means retiring the projection file carries no runtime risk today.
- `read_charter`/`propose_charter_revision` treat charter content as an opaque string for hashing/diffing purposes —
  adding YAML frontmatter to that string requires no change to the versioning mechanism itself, only to what writes
  and validates the string's shape.
- `.synlynk/policy.json` already holds the authoritative capability+cost-matrix routing table
  (`overrides.dev_authority.task_allocation`), keyed by task type, with `harness` + `fallback` per entry. Only `dev`
  has a populated entry today.

## 3. Precedent Studied

Before designing a synlynk-specific schema, existing portable agent-definition conventions were reviewed directly
(not from memory) to avoid inventing something bespoke:

- **GitHub Copilot custom agents** (`.github/agents/*.agent.md`, found locally under a VS Code extension's source):
  YAML frontmatter limited to `name`, `description`, `tools: [...]` — followed by a fully freeform markdown body
  (philosophy, process, checklists, output format, "don't be afraid to" sections, high-risk file tables). No
  enforced structure inside the body beyond whatever `##` headers the author chose.
- **Claude Code subagent definitions**: same shape — `name`, `description`, `tools`, optional `model` in frontmatter;
  freeform markdown body.
- **superpowers `SKILL.md`**: minimal frontmatter (`name`, `description` only), freeform body.

The common pattern: **minimal structured frontmatter for metadata that needs to be parsed/matched by tooling
(name, description, tool access), freeform markdown for everything a human or LLM just needs to read.** This design
adopts that pattern, extended with a `credentials` field (a synlynk-specific need not present in the precedents
studied, since none of them model cross-harness credential scoping) and three *required* (but not rigidly
sub-structured) body sections, per the explicit ask: "first and second level structure needs to be machine readable
and enforceable... some amount of prose within a section is fine."

## 4. Decision

### 4.1 File structure: merge frontmatter into `charter.md`

`charter.md` becomes YAML frontmatter + markdown body, in one file — not a separate structured file plus a prose
file. The existing `.synlynk/agents/<agent_id>.yaml` projection is retired; its three meaningful fields
(`agent_id`, `workspace_id`, `role`) become redundant with frontmatter's `role` field plus the registry's own
`agent_id`/`workspace_id` tracking, and `capability_grants` is superseded by frontmatter's `tools`/`credentials`
fields (see 4.2). No other code depends on the projection file's existence (confirmed above), so retiring it is
non-breaking.

This keeps a charter portable as a single file — a harness or human reading `charter.md` alone gets the complete
picture, matching the `.agent.md` convention's design intent.

### 4.2 Frontmatter schema (required, enforced)

```yaml
schema_version: 1
role: pm                    # required; must be one of the 7 provisioned roles
description: "..."           # required; one-line summary, mirrors .agent.md's description field
durability: durable | session-only | dispatch-only   # required; matches the durability model from
                                                        # the 2026-08-09 org-chart spec §2
tools: []                    # required (empty list allowed); capability/tool names this role is granted
credentials: []               # required (empty list allowed); named credential/token references this role
                              # may access — the reference name only, never the secret value itself
dispatch_routing:            # optional; see 4.4 — machine-generated, never hand-edited
  <task_type>: {harness: ..., fallback: [...]}
```

`schema_version` exists so a future structural change can be migrated deliberately rather than silently
reinterpreted.

### 4.3 Required body sections (enforced presence, not enforced content)

Three `##` headers must be present and non-empty. Content beneath each is free prose — no further sub-structure is
enforced, per the explicit instruction that rigid prose requirements make charters "too rigid":

- `## Instructions` — the day-to-day behavioral prose. This is what most of today's revision-2 charters already are.
- `## Authority & Escalation` — what this role decides unilaterally vs. what it must escalate to whoever currently
  holds `human_authority_role` (per the merged authority spec). Every charter must say this explicitly rather than
  leaving it implicit.
- `## Workflow Ownership` — which stage(s) of the end-to-end workflow (from the 2026-08-09 spec §5) this role owns.

Roles may add further `##` sections beyond these three with no restriction — this is the "extensible and expandable"
requirement. A role-specific section (e.g. `qa`'s Support Engineer operational notes, `marketing`'s blog-post
handoff protocol) is exactly the kind of content that belongs here rather than being forced into one of the three
required sections.

### 4.4 `dispatch_routing` is generated, never hand-authored

`.synlynk/policy.json`'s `task_allocation` table is the single source of truth for harness routing (per the
authority spec's Q2 direction). If `dispatch_routing` in a charter's frontmatter were hand-edited, it would
inevitably drift from `policy.json`. Instead:

- `dispatch_routing` is present in frontmatter only for roles that have a `task_allocation` entry in `policy.json`
  (today: `dev` only).
- It is written exclusively by a sync step (extending the existing `regenerate_agent_projection`-style write path,
  now targeting `charter.md`'s frontmatter block instead of the retired projection file) whenever `policy.json`
  changes for that role.
- Any manual edit to `dispatch_routing` in a charter is not itself invalid per the validator (the validator checks
  shape, not provenance) but is expected to be overwritten on the next sync — this is a documentation note for
  implementation, not a new enforcement rule, since building drift-detection for this one field is out of scope (see
  §7).

### 4.5 Enforcement

A validator runs wherever a charter is written — inline in `propose_charter_revision`'s call path, invoked from
`agent_cli.py`'s `edit` handler (and `init`, for newly seeded charters). It checks:

1. Frontmatter parses as valid YAML.
2. Required keys present (`schema_version`, `role`, `description`, `durability`, `tools`, `credentials`) with
   correct types (`role` matches a known role; `durability` matches the enum; `tools`/`credentials` are lists).
3. The three required `##` headers are present in the body and each has at least one non-whitespace line of content
   beneath it before the next `##` header or end of file.

A revision that fails validation is rejected before being written — the same rejection point `RevisionConflictError`
already uses for a parent-revision mismatch, so this fits the existing error-handling shape rather than adding a
new one.

Enforcement is turned on immediately (no warning-only period) — there are only 7 charters today, and the only
current editor of charter content is this session (via `agent edit`), so there's no external workflow to break by
requiring the schema from day one.

### 4.6 Migration of the 7 existing charters

Each of the 7 gets a new revision (rev 3) that adds frontmatter and restructures existing prose into the three
required sections. This is a content-authoring task, not a mechanical transform — done per-role as part of
implementation, not drafted in full here. One exception is called out explicitly because it's a correction, not just
a reformat: **`pm`'s rewrite must restore the lost competitive-intelligence-sweep / capability-gap-doc /
feature-proposal-escalation content from its original seed, merged alongside revision 2's additions (Named Release
ownership, the "never commits the human to something they haven't seen" authority line) rather than choosing one
version over the other.**

## 5. Error Handling

- Invalid frontmatter YAML → reject with a parse error pointing at the offending line, same UX pattern as other
  synlynk config-file parse failures.
- Missing required frontmatter key → reject listing every missing key at once (not one-at-a-time), so a fix pass
  doesn't require multiple round-trips.
- Missing or empty required `##` section → reject naming the missing section(s).
- `role` value that doesn't match a known provisioned role → reject (prevents typo'd role drift).

## 6. Testing

- Unit tests for the validator: valid charter passes; each of the four rejection categories in §5 is independently
  triggered and produces the expected error; `dispatch_routing` presence/absence doesn't affect validation pass/fail
  either way (it's optional and unchecked in content).
- A test asserting all 7 post-migration charters (once rewritten) pass validation — a regression guard so a future
  hand-edit can't silently drop a required section.
- A test asserting `.synlynk/agents/<agent_id>.yaml` is no longer written by `agent init`/`edit` (projection
  retirement).

## 7. Out of Scope

- Actually authoring the 7 migrated charter bodies — implementation work, follow-on from this spec.
- Building the `dispatch_routing` sync step's drift detection (flagged in §4.4) — the sync-writes-on-policy-change
  path is in scope; detecting/warning on stale hand-edited `dispatch_routing` is not.
- Any change to the authority spec's injection mechanism (`generate_context()`, `human_authority_role`) — that
  mechanism is unchanged; it continues to read charter content as an opaque string, and this design does not require
  it to parse frontmatter specially.
- Extending `tools`/`credentials` frontmatter fields into an actual runtime-enforced capability system (i.e., a
  harness being technically prevented from using a tool not listed) — this design only requires the fields exist and
  validate; wiring them into runtime enforcement is future work, same status `capability_grants` has held since it
  was introduced (declared, not enforced).

## 8. Dependencies / Sequencing

- Independent of the authority spec's Q1/Q4 implementation (charter injection into dispatch) — that can land before,
  after, or in parallel with this design's implementation. Q2 (the `pm`/`architect` capability-matrix routing
  amendment) does interact with §4.4: once `pm`/`architect` gain `policy.json` `task_allocation` entries, their
  charters will start carrying a generated `dispatch_routing` block too.
- No dependency on GitHub issue #1194 (decision-record write-path bug) or PR #1195 (record recovery) — unrelated
  threads from earlier in this session.
