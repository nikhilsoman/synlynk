# synlynk Cold-Start Design

**Status:** Approved for planning
**Author:** Claude (PM), synthesized from a 4-round `synlynk decide` panel brainstorm with Nikhil as arbiter
**Panel inputs:** `project-docs/decisions/2026-08-08-synlynk-cold-start-problem-round-{1,2,3}-brain.md`, `project-docs/decisions/2026-08-09-synlynk-cold-start-problem-round-4-brain.md`

## Problem

synlynk has built substantial structure — goals, plans, specs, roadmap, telemetry, dispatch routing, quota tracking, review discipline — but none of it is reachable by a new user on their first interaction. synlynk has no model of what it should or could do until the user first asks a harness to do something; it is reactive, not proactive. Concretely:

1. A user starting a brand-new project gets no guided intent-capture — synlynk waits to be told what to build.
2. A user joining an existing project gets no onboarding — they read a README and skim `git log` themselves, exactly as they would without synlynk installed.
3. Even when a scan happens, its output is a document to read, not an action to take. A canon nobody acts on is not different, in effect, from no canon.

## Product framing (governs every decision below)

synlynk = "synaptic link" — the gap between neurons, biological or synthetic. Its purpose is making the transmission of intent and action possible across that gap: human → agent, and agent → agent. The test for every mechanism in this spec is not "does this produce good documentation" but **"does this close a specific intent-transmission gap"**. A cold-start flow that ends in a well-written file nobody acts on has failed regardless of the file's quality.

## Goals

- One real artifact on disk plus one actionable next command, in both the new-project and existing-project path, within roughly 60 seconds of first run.
- For existing repos: build genuine, verifiable, curated understanding — not a second scanner, a projection over data `synlynk scan --deep` already collects.
- Every cold-start and every progressive assessment ends by proposing concrete next actions the user is incentivized to take, routed through synlynk's existing goal/roadmap/dispatch machinery.
- Auto-infer everything that is read-only synthesis over local data; keep explicit consent gates only around actions with real external side effects (disk beyond the repo, auth, network egress, cost).

## Non-goals

- No new scanning engine — this is a curation/synthesis layer over `_scan_full_repo()` / `state.db` / `project-docs/source-map.md`.
- No automatic inference of cross-repo relationship *types* (api-call, shared-db, etc.) — that boundary is already shipped and fixed in `docs/superpowers/specs/2026-07-11-vizor-architect-map-v2-design.md` and is not reopened here.
- No wizard-style 20-question new-project interrogation — capped at 4 questions.
- No forced big-bang generation of every canon section in one pass.

## Command surface

`synlynk start` — new top-level cold-start entry point, distinct from `init` (lower-level bootstrap primitive `start` calls). `synlynk canon assess --section <name>` — progressive, independently re-runnable assessment of one canon section.

## Detection: new vs. existing

A cheap, sub-second triage runs unconditionally on `synlynk start`: git presence, commit count, manifest files, README presence. Combined with an always-on harness/auth env-probe (runs even for brand-new projects, decoupled from any deeper scan).

- **Confident new:** no `.git`, or `.git` with 0 commits, no manifest files, empty/near-empty tree.
- **Confident existing:** `.git` with commits, at least one manifest or README, non-trivial file count.
- **Ambiguous** (forked/cloned repo with no commits yet; empty repo with a stray README; monorepo where only one package is in scope): show a single one-line confirm, e.g. `"Looks like an existing project with no commits yet — is that right, or are we starting fresh? [existing/new]"`. No mode question is ever asked when detection is confident.

## New-project path

Exactly 4 questions: one-sentence goal, deliverable shape, solo/team, preferred implementer (if known). No canon is generated — there is nothing yet to document. Immediately writes `.synlynk/config.json` + seeded `roadmap.md` / `todo.md` / `memory.md`, then prints the generated roadmap plus one concrete next action (e.g. "run `synlynk launch` → Task 1"). No code is written before this confirmation step.

## Existing-project path ("warm start")

### Baseline (`synlynk start`)

1. Env-probe (harnesses, auth) — always, unconditional.
2. Shallow scan (stack, harnesses present, README, git depth) — prints a 5-8 line "here's what I found" summary within ~5 seconds.
3. Offers the deeper pass (`synlynk scan --deep`) with consent — this is the one consent gate that survives from round 1-3 for *local* deep scanning, distinct from the external-action gates below. (Codex dissented in round 4, arguing local deep-scan should also auto-run since it's non-destructive; the synthesis and the arbiter's read of prior rounds keep this gate for now — it is the most expensive local operation and worth one confirmation. Revisit if this friction proves unwarranted in practice.)
4. Writes `workspace-canon.md` at repo root with the baseline sections filled (Documentation Index, 3-claim receipt, skeleton for the deeper sections marked `not yet assessed`).
5. Asks one question: "what are you trying to do right now?" — routes the answer into roadmap seeding or a specific dispatched task.

### Re-running `start`

If `.synlynk/config.json` already exists: explicit `[y/N]` refresh prompt, never a silent re-wizard. Refusing leaves everything untouched; accepting re-runs baseline detection/env-probe and re-checks canon staleness (below) without re-asking the 4 new-project questions or re-running consent-gated deep scan unless explicitly requested via `canon assess`.

### Zero working harnesses

Env-probe reports failure state on-screen explicitly (which harnesses were checked, why each failed — no auth, not installed, etc.) and does not block the rest of `start`; scan and canon generation proceed using local-only capability (no harness dispatch offered until at least one harness is available).

## workspace-canon.md

Root-level, human-readable and human-editable Markdown. Not generated for brand-new projects. Carries provenance metadata: HEAD SHA + scan timestamp, per section (not just globally), so partial refreshes are traceable. Every claim carries a file:line citation and a confidence tag (`found` / `inferred`). A 3-claim receipt prints before the full canon on every generation/refresh, with an instant verify command, so a skeptical reader can confirm correctness in the first 60 seconds without reading the whole file.

### Canon becomes the documentation index

`workspace-canon.md` is the hub, not a novel document. Its first section is a `## Documentation Index` that auto-links `project-docs/` (roadmap, todo, memory, decisions), `docs/superpowers/specs/`, `docs/blog/`, and any other discovered docs directories — generated by walking known doc paths, not hand-maintained.

### Section: Retrospective Roadmap

Reconstructed from git/PR/decision history — a *historical* timeline of how the repo reached its current state (major merges, named releases, architectural pivots visible in commit/PR/decision metadata), not a future roadmap. This is distinct from and does not replace `project-docs/roadmap.md` (which stays forward-looking).

**Release tags as a primary timeline source:** when the repo has git tags, `git tag` (with annotated-tag dates via `git for-each-ref --sort=creatordate`) is scanned as a first-class signal alongside PR/decision history, not just commit messages. Tag *pattern* is auto-detected rather than assumed: semver (`vX.Y.Z` / `X.Y.Z`), CalVer, monorepo per-package tags (`<pkg>@X.Y.Z`), and untagged/no-release repos are all distinguished, since the shape of that pattern (or its absence) is itself part of "how this repo ships" and belongs in the retrospective narrative. GitHub Releases (`gh release list`, when the `gh` CLI is authenticated) are cross-referenced opportunistically to pull release notes onto the timeline; their absence is not an error — tags alone are sufficient.

### Section: Current State (active code only)

**Active** = reachable from known entrypoints (mirroring `_scan_full_repo()`'s existing symbol graph) **OR** touched in the last 50 non-merge commits. This reachable-OR-recent-50-commits rule remains the baseline definition and the only one used for untagged repos.

**When release tags exist, they sharpen this definition rather than replace it:** code shipped at or before the latest tag is the *released baseline*; commits since the latest tag are *in-flight* and flagged as such in the active-code narrative (e.g. "N commits ahead of vX.Y.Z, not yet released") rather than silently folded into "current state" as if already shipped. This distinction is additive metadata on top of the existing active/dormant split, not a third bucket — tagged-and-active code is still active, it is simply also labeled with its release status. Code matching neither the reachability nor recency condition is not dropped from the canon — it is listed in a separate `Dormant` subsection, so nothing silently disappears, but the primary "what does this repo do today" narrative only describes the active set.

### Sections: Functional map (HLD), Data map (LLD), Infra view, Operational view, UX/UI view

Five further curated projections over existing scan data plus targeted new signal extraction:
- **Functional map**: major subsystems and their functional relationships, derived from module/package boundaries and call-graph clustering already available from the deep scan.
- **Data map**: schemas, storage boundaries, what persists where — derived from migration files, ORM models, schema definitions found during scan.
- **Infra view**: environments the product actually runs in (dev/CI/prod/etc.) — derived from CI config files, Dockerfiles, IaC (Pulumi/Terraform) definitions found in the repo, not assumed.
- **Operational view**: logs/metrics *actually instrumented* — derived from real logging/telemetry call sites found by the scan (e.g. `log_telemetry()`, structured logging calls), never aspirational monitoring that isn't wired up.
- **UX/UI view**: for a traditional app, screens/flows; for a CLI/tool product like synlynk itself, this means command surface + any HUD (Vizor) — adapted sensibly per what the repo actually is, not forced into a web-app template.

Each of these is optional and separately assessable, not part of the mandatory baseline.

## Progressive assessment mechanism

`synlynk canon assess --section <index|history|active|functional|data|infra|ops|ux|all>`. `synlynk start` runs only the cheap baseline (index + 3-claim receipt + skeleton). Each heavier section is independently runnable, idempotent (safe to re-run), stamped with its own `assessed_at` timestamp + HEAD SHA + confidence, and preserves any hand-edited `## Human notes` subsections on re-run (never silently overwritten). This is what lets the canon reach "professionally managed" depth without one slow big-bang pass, and what lets a user or a dispatched harness fill it out incrementally as a real, incentivized activity in its own right (see Goals Ledger below).

## Cross-repo references

Unchanged from round 3, reaffirmed in round 4: candidate sibling references (name/path/import mentions of another repo) are always logged for free into a "Found references" section — detection only, never relationship-type classification (that boundary stays with Vizor's Architect Map v2 spec, out of scope indefinitely). Promoting a reference to `.synlynk/vizor-workspace-map.json` as an untyped/pending edge requires an explicit `[y/N]` prompt. Cloning a missing sibling repo requires a separate explicit prompt (disk + potentially auth + cost — an external action). One-hop only: a cloned sibling is not itself auto-scanned or auto-recursed into without its own explicit `start`/`scan`.

**Monorepo:** one root canon with per-package sections.
**Multi-repo siblings** (synlynk's own actual setup — rxcc, cc-videoreframing, playblazer-ng, synlynk): one canon per repo, cross-linked only via each repo's Found-references section and Vizor's manually-maintained edge file. No merged multi-repo canon file.

## Consent boundary

**Local inference — zero prompts, always runs:** canon writes/refreshes, Found-references detection, active-code-set inference, functional/data/infra/ops/UX section generation, goal proposal generation. All of this is read-only synthesis over data already on disk; none of it is destructive, so none of it waits for permission.

**External action — stays consent-gated:** `synlynk scan --deep` itself (first run per repo — the most expensive local operation, one confirmation), cloning a missing sibling repo (disk + auth + cost), promoting a Found-reference to a typed/pending Vizor edge (this is a claim about repo relationships an external map will surface to other tooling).

This is the line all four panelists converged on in round 4: *local inference vs. external action*, not *docs vs. everything*. It fully answers requirement 10 from the R4 agenda (auto-infer, don't ask permission, because it's non-destructive) while explicitly preserving round 3's clone-consent decision rather than silently overriding it.

## Canon staleness

Each canon section carries HEAD SHA + timestamp. Staleness is checked the same way `_check_upstream_divergence` already gates on git state: on next relevant `synlynk` invocation, compare stored per-section HEAD SHA against current `git rev-parse HEAD`. A stale section is flagged with a warning banner inline in the canon output (not a silent background refresh, not a blocking prompt) — the user sees which sections are stale and can re-run `canon assess --section <name>` explicitly.

## Goals ledger — closing every scan with an action

Every `start` run and every `canon assess` run ends by emitting a gaps ledger: unfilled/stale canon sections, stale TODOs discovered during scan, unresolved cross-repo Found-references, and any explicit gaps the deep scan surfaces (dead code with no owner, missing tests on active paths, etc.). From this ledger, synlynk proposes 3-5 concrete goals, each rendered on screen as:

```
Goal: <one-line outcome>
Evidence: <why this surfaced — e.g. "3 Found-references to cc-videoreframing, none resolved">
Agenda: <2-3 bullet brainstorm agenda for this goal>
Accept? [y/N] → seeds a pre-scoped roadmap.md/todo.md entry, offers `synlynk dispatch` directly
```

Accepting a goal is the actual success state of a cold-start run — not "the user read the canon." This is the concrete mechanism answering the R4 reframe: canon discovery is not a solitary output, it is the on-ramp to an action a user is now incentivized to take.

## Testing approach (for the implementation plan to expand)

- Unit tests for detection heuristics (confident-new / confident-existing / ambiguous) against synthetic repo fixtures (varying commit counts, manifest presence, empty dirs).
- Unit tests for the active-code classifier (reachable-OR-recent-50-commits) against a fixture repo with known reachable, known dormant, and known recently-touched-but-unreachable files.
- Unit tests for tag-pattern detection (semver, CalVer, monorepo `<pkg>@X.Y.Z`, untagged) and for in-flight-vs-released labeling against a fixture repo with tagged commits followed by unreleased commits.
- Integration tests for `canon assess --section X` idempotency: run twice, confirm hand-edited `## Human notes` subsections survive, confirm `assessed_at`/HEAD SHA update correctly.
- Integration tests for the consent boundary: confirm zero prompts on pure local generation paths, confirm exactly one prompt on deep-scan-first-run / clone / edge-promotion paths.
- No live harness calls in tests — unit + integration against tmp git repos / tmp sqlite only, consistent with existing test conventions in this codebase.

## Open items deferred out of this spec

- Exact wording/UX polish of every on-screen prompt — left to implementation, following the tone established in the examples above.
- Whether the deep-scan consent gate should eventually be removed for local-only analysis (Codex's round-4 dissent) — noted above, not resolved here; revisit after baseline ships if the friction proves real.
