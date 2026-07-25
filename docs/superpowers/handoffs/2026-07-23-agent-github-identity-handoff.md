# Handoff: Per-Role GitHub Identity — synlynk

## Where this lives
- Repo: ~/dev/synlynk
- Worktree: .worktrees/chore+agent-github-identity-design
- Branch: chore/agent-github-identity-design (based on main at v0.13.0 + a few post-release docs commits — see commit list below)
- PR: **none opened yet**
- Plan: **none written yet**
- Status: spec-only, committed, clean working tree, nothing further has happened on this branch since.

## What this feature does
Every `synlynk dispatch`-originated `gh` operation (PR authorship, comments, reviews)
currently runs under the single ambient personal GitHub token of whoever owns the
machine — regardless of which agent (Agy/Grok/Codex/Claude) or which role (dev/qa/
pm/tpm/etc.) actually did the work. This spec designs a fix: **one GitHub App per
role** (not per agent CLI, not per model), provisioned once per project via the
GitHub App Manifest flow, minting short-lived installation tokens at dispatch time
so `rxcc-dev[bot]`, `rxcc-qa[bot]`, etc. show up as the real GitHub actor. Underlying
agent/model attribution (git commit `Co-Authored-By` trailer, `capability_ratings`
table) is untouched — this only changes who GitHub thinks did the work at the
PR/review/comment layer.

This directly fixes two concrete breakages documented in the spec's Context section:
1. **Self-approval is structurally impossible today.** GitHub blocks a PR author
   from approving their own PR by *identity*. Grok's `gh pr review --approve` on
   synlynk PR #417 failed with "Review can not approve your own pull request" even
   though Grok didn't author the PR — because GitHub sees `nikhilsoman` as both
   author and reviewer (single shared token).
2. **Review-based capability signals are unmeasurable.** The 2026-07-18
   capability-sweep-taxonomy spec's PR Review-Cycle Multiplier depends on
   `_extract_pr_review_cycles()` reading real `CHANGES_REQUESTED` review counts.
   With one shared identity, `reviewDecision` stays permanently empty on every
   dispatch-authored PR.

## Origin / decision trail
- Issue: [nikhilsoman/synlynk#423](https://github.com/nikhilsoman/synlynk/issues/423)
  (closed, unresolved) — documents the shared-token problem, confirmed via `gh api`
  against rxcc PR #983 (author, comments, reviews all resolved to `nikhilsoman` even
  though Agy did the work; only the git commit author was distinct).
- Issue #426 / the 2026-07-21 gh-write-capability-routing spec explicitly named and
  deferred this exact problem to "its own future spec" — this spec is that follow-up.
- Spec file: `docs/superpowers/specs/2026-07-23-agent-github-identity-design.md`
  (single commit, full content below — no plan doc exists yet).
- No multi-agent `synlynk decide --panel` review was run for this spec (unlike the
  GOVERNS lifecycle work, which had one recorded at
  `project-docs/decisions/2026-07-23-should-synlynk-formally-wire-every-user.md`).
  This spec was brainstormed and written up directly, single-pass.

## Commits on the branch (in order)
1. `1c6fe53` fix(viz): keep --serve alive — pre-existing, unrelated, part of v0.13.0 lineage
2. `646f0d5` release: v0.13.0 — Discoverability & Accounting — release commit, branch base
3. `c6d104b` docs: archive unmerged docs from stale branches before removal (#444)
4. `60a8e5d` docs: recover uncommitted cost log, decision record, and job-lifecycle spec (#447)
5. `eb345fa` **docs: design spec for per-role GitHub App identity (#423)** — the only
   commit specific to this feature. Adds
   `docs/superpowers/specs/2026-07-23-agent-github-identity-design.md` in full (see
   below). No code, no tests, no plan.

(Commits 3–4 are shared ancestry from the branch being cut post-v0.13.0, not part of
this feature's work — listed only so the branch's base state is unambiguous.)

## Full spec content (as committed, verbatim — reproduce this file if starting fresh)

### Context
Issue #423 documents that every `synlynk dispatch`-originated `gh` operation runs
under the single ambient personal GitHub token, confirmed via `gh api` on rxcc PR
#983. This breaks (1) self-approval being structurally impossible by identity, not
token — Grok's approve on PR #417 failed despite not authoring it — and (2)
review-based capability signals being unmeasurable since `reviewDecision` stays
empty with one shared identity. Issue #426 / the 2026-07-21 gh-write-capability
-routing spec deferred this exact problem to its own future spec; this is that spec.

### What This Builds

**Identity model: one GitHub App per role, not per agent CLI.** The unit of GitHub
identity is a *role* (`pm`, `architect`, `tpm`, `dev`, `qa`, `designer`, and
open-ended future roles) — not an agent CLI (Agy/Grok/Codex/Claude) and not a
specific model. Concretely: `rxcc-pm[bot]`, `rxcc-tpm[bot]`, `rxcc-architect[bot]`,
`rxcc-dev[bot]`, `rxcc-qa[bot]`, `rxcc-designer[bot]` are separate GitHub App
installations on the `Dialify` org. Whichever underlying agent executes a `dev`-role
task authenticates as `rxcc-dev[bot]`. Two alternatives were considered and rejected:
*identity per agent CLI* (loses role information once two autopilots share a backing
model), and *identity per (role, agent) pair* (unnecessary combinatorial expansion,
no consumer of that granularity — GitHub only supports one actor per PR/comment
/review).

**Underlying agent/model attribution stays exactly where it is today** — the git
commit `Co-Authored-By` trailer and the `agent`/`model_version` columns in
`capability_baseline.json`/`capability_ratings` are unaffected. GitHub identity
answers "who is the actor for review/authorship purposes" (role); capability scoring
answers "which model is good at this" (agent CLI + model) — different questions at
different layers.

**Self-approval invariant, restated at the role level:** the existing PR Review
Discipline convention ("a non-authoring agent reviews") becomes "a non-authoring
*role* reviews." A `qa`-role review of a `dev`-role PR is a legitimate cross-check
regardless of underlying model; a role reviewing its own PR is still correctly
blocked as self-review.

**Provisioning: GitHub App Manifest flow, one-time per role.** GitHub Apps (not
machine-user accounts — those need email/mailbox provisioning overhead Apps don't).
Flow: `synlynk identity init --role <name>` opens a pre-filled
`github.com/settings/apps/new?state=...` manifest (name `<project>-<role>`,
permissions `contents:write`, `pull_requests:write`, `issues:write`, webhook
disabled) → user clicks "Create GitHub App" → synlynk exchanges the returned `code`
via `POST /app-manifests/{code}/conversions` for `app_id`/private key
(PEM)/`client_id`, written to `.synlynk/github_apps/<role>.json` (private key
`chmod 600`, gitignored) → user clicks an install link to install on the org →
`synlynk identity init` confirms via `GET /app/installations` and marks the role
provisioned in `.synlynk/roles.yaml`. Total human effort: two clicks per role, once.

**Token minting: new `synlynk/github_app_auth.py`.** GitHub Apps mint short-lived
(~1hr) installation tokens on demand: sign a JWT with the App's private key
(10-minute expiry), `POST /app/installations/{id}/access_tokens` with the JWT as
bearer auth, cache the token in memory (not on disk) keyed by role and expiry,
re-mint on expiry/absence. The dispatched job's environment gets
`GH_TOKEN=<installation token>` injected for that job's duration.

**Call-routing / attribution rule:** at dispatch time, `dispatch_agent()` resolves
the job's `role` from story metadata (already exists as the `role` dimension in the
Capability Matrix taxonomy). If `.synlynk/github_apps/<role>.json` exists, mint and
inject that role's token; otherwise fall back to `synlynk-bot[bot]`, a single
generic catch-all App provisioned at `synlynk init` time — never falls back to the
human's personal token. Pure environment-injection change at dispatch time; no
change to how the underlying CLI calls `gh`.

**Role Extensibility (domain-adaptivity):** provisioning reads from
`.synlynk/roles.yaml` (the same store `synlynk role add <name>` writes to), not a
hardcoded enum. The 6-value `role` enum in capability-matrix-taxonomy.md is today's
software-project default, not a ceiling — a film project's roles might be
`director`/`screenwriter`/`editor`/`colorist`. This spec does not attempt to make
GOVERNS stages themselves domain-adaptive (a bigger, separate, deferred taxonomy
question — see memory `project-capability-taxonomy-enterprise-seed`) — only ensures
this identity layer doesn't assume software-dev roles are the universe.

**Onboarding / upgrade integration:** two entry points, both funneling into
`synlynk identity init --role <name>` (from the 2026-06-07 identity-dispatch spec,
which already covers Ed25519 bootstrap at `synlynk init`/`synlynk profile probe`):
- `synlynk init` (new project): after Ed25519 bootstrap, prompt "which roles will
  this project use?" (default starter set `dev`, `qa`, editable), run the App
  Manifest flow once per declared role before `init` completes.
- `synlynk upgrade` (existing project, or gaining a new role later): diffs
  `.synlynk/roles.yaml` against `.synlynk/github_apps/` and runs provisioning only
  for roles missing an identity.

### Non-Goals
- **Mode B (managed/hosted identities)** — a `synlynk.com`-hosted mode
  pre-owning canonical Apps and forwarding role-scoped email aliases (e.g.
  `pm.nikhilsoman@synlynk.com`) via SES, removing the two-click local step —
  explicitly deferred; depends on unbuilt Tokq cloud infra (same deferral point as
  multi-project identity in the 2026-06-07 spec). Nothing in this design's data
  model precludes a future Mode B populating the same files via a hosted API instead.
- **GOVERNS-stage domain-adaptivity** — separate, larger, deferred team/enterprise
  taxonomy question; this spec only avoids hardcoding assumptions that would block it.
- **Retroactive identity assignment** — already-posted PRs/comments/reviews under
  the human's personal identity (e.g. rxcc PR #983) are not rewritten.
- **Sandboxing or entitlement enforcement changes** — the existing Role entitlement
  layer (3.2 of the 2026-06-07 spec — what an actor is *allowed* to do) is
  unchanged; this spec only changes *which actor* GitHub sees.
- **Webhook-driven automation** — the Apps provisioned here have no webhook
  configured; pure auth/identity mechanism for outbound calls, not an event source.

### Data Flow
```
synlynk init / synlynk upgrade
  → read/prompt .synlynk/roles.yaml
  → for each role missing .synlynk/github_apps/<role>.json:
      → App Manifest flow (2 clicks) → app_id, private key, client_id
      → write .synlynk/github_apps/<role>.json (gitignored, chmod 600)
      → confirm installation on org

synlynk dispatch (job tagged with role=<role>)
  → dispatch_agent() resolves role from story metadata
  → github_app_auth.get_installation_token(role)
      → cache hit (unexpired) → return cached token
      → cache miss/expired → sign JWT with .synlynk/github_apps/<role>.json's private key
                            → POST /app/installations/{id}/access_tokens
                            → cache + return token
  → inject GH_TOKEN=<token> into dispatched agent's environment
  → underlying agent CLI (Agy/Grok/Codex/Claude) runs gh/git commands,
    authenticated as <project>-<role>[bot]
  → commit trailer still records real agent + model (unchanged from today)
```

### Data Model
`.synlynk/roles.yaml` (new, project-local, **committed** — role names are project
config, not secrets):
```yaml
roles:
  - dev
  - qa
  - pm
  - tpm
```

`.synlynk/github_apps/<role>.json` (new, one per provisioned role, **gitignored**):
```json
{
  "role": "dev",
  "app_id": "123456",
  "client_id": "Iv1.abc123",
  "app_slug": "rxcc-dev",
  "installation_id": "78901234",
  "private_key_path": ".synlynk/github_apps/dev.pem"
}
```
Private key stored as a sibling `.pem` file (`chmod 600`), not inlined in the JSON.

`.synlynk/github_apps/synlynk-bot.json` — the generic catch-all identity, same
shape, provisioned once at `synlynk init` regardless of role list, fallback for
untagged jobs.

No changes to any existing SQL schema (`capability_ratings`, `stories`, `jobs`).

### CLI Surface (new/changed)
- `synlynk identity init --role <name>` — runs the App Manifest provisioning flow
  for one role. Idempotent: no-ops with a message if the role's JSON already exists.
- `synlynk role add <name>` (existing) — now also prompts "provision a GitHub
  identity for this role now?" (default yes), calls `identity init --role <name>`
  if accepted.
- `synlynk upgrade` (existing) — gains a role-identity-diff step per Onboarding
  Integration above.
- `synlynk identity list` — new; lists all provisioned role identities and their
  installation status (queries `GET /app/installations` per role, flags revoked ones).

### Rollout (as specced, not yet started)
1. Ship `github_app_auth.py` + `.synlynk/roles.yaml` / `.synlynk/github_apps/` data
   model, with `synlynk identity init --role` as a standalone command (no automatic
   triggering yet).
2. Manually provision `rxcc-dev[bot]`, `rxcc-qa[bot]`, `rxcc-pm[bot]`,
   `rxcc-tpm[bot]` (rxcc's current active roles) on the `Dialify` org as a
   real-world validation pass — confirm a dispatched job can open a PR and a
   different role can post a real `--approve` review GitHub accepts (the actual
   #423 failure mode, now testable).
3. Wire the `dispatch_agent()` call-routing change (token injection by role) behind
   the existing role-tagging story metadata — no new tagging mechanism needed.
4. Wire `synlynk init` / `synlynk upgrade` triggers last, once the manual flow
   (steps 1–3) is confirmed working end-to-end on rxcc.
5. Once real review data exists, revisit `_extract_pr_review_cycles()`
   (`sentinel.py:219-247`) to confirm it now reads a non-empty `reviewDecision` on
   dispatch-authored PRs — the original motivation from the 2026-07-18
   capability-sweep spec.

### Future Work
- **Mode B / Tokq-hosted managed identities** — see Non-Goals.
- **GOVERNS-stage domain-adaptivity** — see memory `project-capability-taxonomy-enterprise-seed`.
- **Cross-project role identity reuse** — today each project provisions its own App
  per role even if the same human runs multiple projects with the same role names;
  deferred to the Tokq identity layer, consistent with the 2026-06-07 spec's deferral.

## Implementation status
**Nothing beyond the spec exists.** No plan file, no PR, no code, no tests, no
`.synlynk/roles.yaml`, no `github_app_auth.py`. Working tree is clean on
`chore/agent-github-identity-design`.

## ⚠️ Process note — carried over from the GOVERNS lifecycle work
The sibling GOVERNS-lifecycle-checkpoint feature (PR #464, merged) was implemented
by dispatching to generic Claude subagents via `subagent-driven-development`, which
violated the standing global "Default Agent Role" policy (Claude = PM/roadmap/
brainstorming/review/deployments only; all implementation must route through
`synlynk dispatch` to Agy/Grok/Codex). That was caught post-hoc and left as-is for
that PR, but **any future work on this branch (writing the plan, then
implementing) must route implementation tasks through `synlynk dispatch --story <N>
--context-mode task`, not generic Claude subagents** — even if reaching for
`subagent-driven-development` or `executing-plans` feels natural. See memory
`feedback-skill-vs-standing-policy` for the full incident writeup.

## Immediate next step (if picking this back up)
1. Invoke `superpowers:writing-plans` against the spec above to produce
   `docs/superpowers/plans/2026-07-23-agent-github-identity-design.md` (or a later
   date if resumed after today).
2. Per the process note above, execution must go through `synlynk dispatch`, not
   the `subagent-driven-development` skill's built-in generic-subagent dispatch —
   flag this explicitly to whichever session picks this up, before execution starts.
3. No panel decision (`synlynk decide --panel`) has been run on this spec. Consider
   whether one is warranted before committing to implementation, given this touches
   auth/security-adjacent surface (GitHub App private keys, token minting) — higher
   blast radius than the GOVERNS lifecycle work's advisory-text-only change.
