# Per-Role GitHub Identity — Design

## Context

Issue [#423](https://github.com/nikhilsoman/synlynk/issues/423) (closed, unresolved) documents that every `synlynk dispatch`-originated `gh` operation — PR authorship, PR comments, PR reviews — runs under the single ambient personal GitHub token of whoever owns the machine, regardless of which agent actually did the work. Confirmed directly via `gh api` on rxcc PR #983: author, both comments, and the (empty) reviews list all resolve to `nikhilsoman`, even though Agy performed the work. Only the git commit author (`synlynk-dispatch <noreply@synlynk.dev>`) is distinct — invisible at the PR/review/comment layer GitHub actually surfaces to humans and to its own APIs.

This breaks two things:
1. **Self-approval is structurally impossible.** GitHub blocks a PR author from approving their own PR by *identity*, not by token. Grok's `gh pr review --approve` on PR #417 failed with "Review can not approve your own pull request" despite Grok not having authored the PR — because GitHub sees `nikhilsoman` as both author and reviewer.
2. **Review-based capability signals are unmeasurable.** The 2026-07-18 capability-sweep-taxonomy spec's PR Review-Cycle Multiplier depends on `_extract_pr_review_cycles()` reading real `CHANGES_REQUESTED` review counts from the GitHub API. With one shared identity, `reviewDecision` stays permanently empty on every dispatch-authored PR — there is no real review signal to read.

Issue [#426](https://github.com/nikhilsoman/synlynk/issues/426) / the 2026-07-21 gh-write-capability-routing spec explicitly named and deferred this problem: "Issue #423 ... is a separate, independent problem ... deferred to its own future spec." This is that spec.

## What This Builds

### Identity model: one GitHub App per role, not per agent CLI

The unit of GitHub identity is a **role** (`pm`, `architect`, `tpm`, `dev`, `qa`, `designer`, and open-ended future roles — see Role Extensibility below) — not an agent CLI (Agy/Grok/Codex/Claude) and not a specific model. A role is the durable, directive-governed actor a project defines (its "canonical directive document" per the role's charter); the agent CLI + model that executes a given instance of that role is an interchangeable implementation detail, exactly as a human role can be filled by different people over time without the position's identity changing.

Concretely: `rxcc-pm[bot]`, `rxcc-tpm[bot]`, `rxcc-architect[bot]`, `rxcc-dev[bot]`, `rxcc-qa[bot]`, `rxcc-designer[bot]` are separate GitHub App installations on the `Dialify` org. Whichever underlying agent (Agy, Grok, Codex, Claude) is dispatched to execute a `dev`-role task authenticates as `rxcc-dev[bot]` when it opens the PR, posts a comment, or leaves a review. If Claude executes a `dev` task on Monday and Grok executes a `dev` task on Wednesday, both show up on GitHub as `rxcc-dev[bot]` — which is correct: from the repo's social-object history, it was the same *role* acting both times.

This choice was made deliberately over two alternatives considered during design:
- **Identity per agent CLI** (Agy/Grok/Codex/Claude, 4 identities) was the original framing, but loses role information entirely once two different autopilots share a backing model — e.g. a future PM-autopilot and TPM-autopilot both backed by Claude would be indistinguishable on GitHub as `claude-bot`.
- **Identity per (role, agent) pair** was rejected as unnecessary combinatorial expansion with no clear mechanism for "posting as two actors at once," and no consumer of that granularity — GitHub's UI and API only support one actor per PR/comment/review.

### Underlying agent/model attribution stays exactly where it is today

This design does **not** touch capability-scoring attribution. Which agent CLI and model version executed a given role-instance continues to be recorded exactly as it is today:
- The `Co-Authored-By` git commit trailer (e.g. `Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>`).
- The `agent` / `model_version` columns already present in `capability_baseline.json` / the `capability_ratings` table.

GitHub identity answers "who is the actor for review/authorship purposes" (role). Capability scoring answers "which model is good at this" (agent CLI + model). These are different questions at different layers and were never the same signal — separating them cleanly is a feature of this design, not a gap.

### Self-approval / non-authoring-review invariant, restated at the role level

The existing PR Review Discipline convention ("a non-authoring agent reviews") becomes, under this design, **"a non-authoring role reviews."** This is the correct level for the check to operate at: a `qa`-role review of a `dev`-role PR is a legitimate cross-check regardless of which underlying model executed either side. A role reviewing its own PR — even if a different underlying model happened to execute the review than wrote the code — is still correctly blocked as self-review, because from GitHub's (and a human reader's) perspective, it's the same actor.

### Provisioning: GitHub App Manifest flow, one-time per role

Each role's GitHub identity is a **GitHub App**, not a machine-user account — ruled out during design because per-agent machine users require email/mailbox provisioning (Google Workspace seat cost, ongoing account management overhead), which Apps don't need at all. Apps are free, are a first-class "Bot" actor type (the `dependabot[bot]` precedent already exists in-repo), and are provisioned via the App Manifest flow:

1. `synlynk identity init --role <name>` opens `https://github.com/settings/apps/new?state=<random>` pre-filled with a generated manifest (name `<project>-<role>`, minimal permissions: `contents:write`, `pull_requests:write`, `issues:write`; webhook disabled — this design has no inbound webhook consumer).
2. User clicks "Create GitHub App" (one click) — GitHub redirects to a local callback with a temporary `code`.
3. `synlynk` exchanges the code via `POST /app-manifests/{code}/conversions`, receiving `app_id`, a generated private key (PEM), and `client_id`. These are written to `.synlynk/github_apps/<role>.json` (private key `chmod 600`), gitignored.
4. User is shown an install link (`https://github.com/apps/<project>-<role>/installations/new`) and clicks to install on the `Dialify` org (second click), scoped to the target repo(s).
5. `synlynk identity init` confirms installation by checking `GET /app/installations` for a matching `app_id`, and marks the role as provisioned in `.synlynk/roles.yaml`.

Total human effort: two clicks per role, once. Steps 1–5 are identical regardless of which trigger initiated them (see Onboarding Integration below).

### Token minting: new `synlynk/github_app_auth.py`

GitHub Apps don't get a static token — they mint short-lived (~1hr) installation tokens on demand:

1. Sign a JWT with the App's private key (`app_id` as issuer, 10-minute expiry per GitHub's JWT requirements).
2. `POST /app/installations/{installation_id}/access_tokens` with the JWT as bearer auth → returns an installation access token.
3. Cache the token in memory (not on disk) keyed by role, keyed off its expiry; re-mint when a dispatched job needs `gh` access and the cached token is expired or absent.
4. The dispatched job's `gh`/git environment gets `GH_TOKEN=<installation token>` injected for that job's duration, scoped to whichever role the job is tagged with.

### Call-routing / attribution rule

At dispatch time, `dispatch_agent()` resolves the job's `role` (from story metadata — this already exists as the `role` dimension in the Capability Matrix taxonomy). Before invoking the underlying agent CLI:
- If `.synlynk/github_apps/<role>.json` exists (role has a provisioned identity) → mint an installation token for that role, inject as `GH_TOKEN` for the job's environment.
- If it doesn't exist (role not yet provisioned, or job has no role tag) → fall back to `synlynk-bot[bot]`, a single generic catch-all App provisioned the same way at `synlynk init` time, used only when no role-specific identity applies. This preserves *a* distinct bot identity (never falls back to the human's personal token) even for untagged ad hoc dispatch work.

This is a pure environment-injection change at dispatch time — no change to how the underlying agent CLI itself calls `gh` (it already just uses whatever `GH_TOKEN`/`gh auth` context is in its environment).

### Role Extensibility (domain-adaptivity)

Role identity provisioning reads from a project-level role list — `.synlynk/roles.yaml`, the same store `synlynk role add <name>` already writes to — not a hardcoded enum. `capability-matrix-taxonomy.md`'s 6-value `role` enum (architect/dev/pm/tpm/qa/designer) is today's software-project default, not a ceiling: a synthetic-film project's roles might be `director`/`screenwriter`/`editor`/`colorist`; a research project's might be `pi`/`analyst`/`peer-reviewer`. Provisioning treats every entry in `.synlynk/roles.yaml` identically regardless of domain — `synlynk identity init --role <name>` doesn't validate `<name>` against any fixed list.

This spec does not attempt to make GOVERNS stages themselves domain-adaptive (a bigger, separate taxonomy question tracked as a deferred team/enterprise idea) — only that this identity layer doesn't assume software-dev roles are the universe, so it doesn't have to be revisited when that broader work happens.

### Onboarding / upgrade integration

Two entry points trigger role-identity provisioning, both funneling into the same `synlynk identity init --role <name>` mechanism from the 2026-06-07 identity-dispatch spec (which already covers Ed25519 bootstrap at `synlynk init` / `synlynk profile probe`):

- **`synlynk init` (new project):** after the existing Ed25519 identity bootstrap, prompt "which roles will this project use?" — default to a starter set (`dev`, `qa` at minimum; more if the project's domain is known), editable. Run the App Manifest flow (Provisioning, above) once per declared role before `init` completes.
- **`synlynk upgrade` (existing project on an older synlynk version, or gaining a new role later):** diffs `.synlynk/roles.yaml` against `.synlynk/github_apps/` and runs the provisioning flow for any role missing an identity. This means adding a role after initial setup (e.g. bolting `marketing-intern` onto a project that started with just `dev`/`qa`) only provisions the new role — it does not re-run the full flow for roles already provisioned.

Both entry points reuse the identical underlying step sequence; onboarding and upgrade are just two different callers of the same one-time-per-role operation.

## Non-Goals

- **Mode B (managed/hosted identities)** — a `synlynk.com`-hosted mode where synlynk pre-owns canonical Apps and forwards role-scoped email aliases (e.g. `pm.nikhilsoman@synlynk.com`) via SES, removing even the two-click self-hosted provisioning step — is explicitly deferred. It depends on unbuilt Tokq cloud infrastructure (the same layer multi-project identity is already deferred to per the 2026-06-07 spec) and is noted here only as a future extension point: nothing in this design's data model (`.synlynk/roles.yaml`, `.synlynk/github_apps/<role>.json`) precludes a future Mode B from populating the same files via a hosted provisioning API instead of the local App Manifest flow.
- **GOVERNS-stage domain-adaptivity** — making the 7-stage lifecycle itself pluggable per domain/industry is a separate, larger taxonomy question, tracked as deferred team/enterprise work. This spec only ensures role identity doesn't hardcode assumptions that would block it later.
- **Retroactive identity assignment** — PRs/comments/reviews already posted under the human's personal identity (e.g. rxcc PR #983) are not rewritten or re-attributed. This design only changes behavior going forward.
- **Sandboxing or entitlement enforcement changes** — this spec is purely about *which actor* GitHub sees; the existing Role entitlement layer (3.2 of the 2026-06-07 spec — what an actor is *allowed* to do, e.g. "merge to main always requires approval") is unchanged and continues to apply on top of whichever identity is now correctly attributed.
- **Webhook-driven automation** — the GitHub Apps provisioned here have no webhook configured; they are used purely as an auth/identity mechanism for outbound `gh`/API calls, not as an event source.

## Data Flow

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

## Data Model

**`.synlynk/roles.yaml`** (new, project-local, committed to repo — role names are project config, not secrets):
```yaml
roles:
  - dev
  - qa
  - pm
  - tpm
```

**`.synlynk/github_apps/<role>.json`** (new, one file per provisioned role, gitignored):
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
Private key stored as a sibling `.pem` file (`chmod 600`), not inlined in the JSON, so the JSON itself can be more loosely handled if ever needed for debugging without exposing the key.

**`.synlynk/github_apps/synlynk-bot.json`** — the generic catch-all identity, same shape as above, provisioned once at `synlynk init` regardless of role list, used as fallback for untagged jobs.

No changes to any existing SQL schema (`capability_ratings`, `stories`, `jobs`) — role/agent/model attribution columns there are unaffected.

## CLI Surface (new/changed)

- `synlynk identity init --role <name>` — runs the App Manifest provisioning flow for one role. Idempotent: no-ops with a message if `.synlynk/github_apps/<name>.json` already exists.
- `synlynk role add <name>` (existing command) — now also prompts "provision a GitHub identity for this role now?" (default yes) and calls `identity init --role <name>` if accepted.
- `synlynk upgrade` (existing command) — gains a role-identity-diff step as described in Onboarding/Upgrade Integration.
- `synlynk identity list` — new, lists all provisioned role identities and their installation status (queries `GET /app/installations` per role to confirm still-installed, flags any revoked).

## Rollout

1. Ship `github_app_auth.py` + `.synlynk/roles.yaml` / `.synlynk/github_apps/` data model, with `synlynk identity init --role` as a standalone command (no automatic triggering yet).
2. Manually provision `rxcc-dev[bot]`, `rxcc-qa[bot]`, `rxcc-pm[bot]`, `rxcc-tpm[bot]` (rxcc's current active roles) on `Dialify` org as a real-world validation pass — confirm a dispatched job can open a PR and a different role can post a real `--approve` review that GitHub accepts (the actual failure mode from #423, now testable).
3. Wire the `dispatch_agent()` call-routing change (token injection by role) behind the existing role-tagging story metadata — no new tagging mechanism needed, this already exists.
4. Wire `synlynk init` / `synlynk upgrade` triggers last, once the manual flow (steps 1–3) is confirmed working end-to-end on rxcc.
5. Once real review data exists, revisit `_extract_pr_review_cycles()` (`sentinel.py:219-247`) to confirm it now reads a non-empty `reviewDecision` on dispatch-authored PRs — this was previously unmeasurable and is the original motivation from the 2026-07-18 capability-sweep spec.

## Future Work

- **Mode B / Tokq-hosted managed identities** (see Non-Goals) — once Tokq cloud infrastructure exists, offer a hosted alternative to the local App Manifest flow, with `agent.owner@synlynk.com`-style SES-forwarded email aliases per role for human-readable audit trail, removing the two-click local setup entirely.
- **GOVERNS-stage domain-adaptivity** — pluggable lifecycle stages per domain/industry, tracked separately as team/enterprise-tier work (see memory: `project-capability-taxonomy-enterprise-seed`).
- **Cross-project role identity reuse** — today each project provisions its own App per role even if the same human runs multiple projects with the same role names; multi-project identity sharing is deferred to the Tokq identity layer, consistent with the existing deferral in the 2026-06-07 spec.
