# Bug-Report Intake: `synlynk report`, Flight Recorder, and Early-Adopter Issue Form

- **Date:** 2026-11-20
- **Status:** Draft, pending Nikhil's review
- **Origin:** gh:#5368 (Vizor banner) and the finding that no user-authored issues exist since 2026-11-15; adopter reports (#5297-#5299, #5363) only reached the tracker via a relay.
- **Destination decision:** public GitHub issues (decided 2026-11-20). Redaction is therefore the central constraint.

## Intent

Make it cheap for an early adopter to file a bug that already contains the context a maintainer needs, without leaking anything private into a public repo, and surface that path at the moments users actually hit problems.

## Context

- `.github/ISSUE_TEMPLATE/bug_report.md` is a thin hand-filled template.
- `synlynk doctor` (`synlynk/doctor.py`) has dozens of `HealthCheck`s but nothing packages them for a report.
- `synlynk/bearings.py` injects a session-start card; task-boundary and dispatch messages exist but carry no reporting hint.
- Redaction helpers exist in `synlynk/logs.py` and `synlynk/cost_audit.py`.
- `synlynk/support_engineer.py` already implements signal collection and investigation as an agent archetype.
- #5299 showed that CLI side effects in an uninitialized directory are a real bug class; the recorder must not repeat it.

## Design

### 1. Public-safe collection (allowlist, not scrubbing)

The collector only emits fields from a fixed schema:

- synlynk version, Python version, OS and architecture, install method (pipx / uv / venv).
- Per harness: name, binary found, version.
- Gateway/profile environment variables (`ANTHROPIC_BASE_URL`, `ANTHROPIC_API_KEY`, `ANTHROPIC_AUTH_TOKEN`, `CLAUDE_CONFIG_DIR`, and the other names in each harness's `env_passthrough`): **set/unset only; values are never read into the report**.
- `doctor` check IDs with pass/warn/fail status.
- Config and policy schema versions.
- `state.db`: counts and shapes only, no row content.
- Worktree dirty flag and branch kind (main / feature / detached).

Anything outside the schema is not collected. Normalization of allowed fields:

- Home directory becomes `~`.
- Username and hostname become a short hash **salted with a per-install random salt stored locally** (an unsalted hash of low-entropy inputs can be confirmed by guessing). Stable per install, so maintainers can correlate reports without identifying anyone.
- Git remotes keep only `host/owner/repo`, credentials stripped. `owner/repo` can name a private repo, so it is shown in the preview and the user can drop it individually.

**Free text** (log tails, stderr) is the risk surface:

- Off by default; offered at preview as explicit per-line opt-in.
- Passed through existing redaction helpers plus a secret-pattern scan.
- A scan hit blocks submission until the offending line is removed.

**Preview is mandatory.** The full rendered body is printed, headed by a notice that the report will be **public and indexed, and that edits or deletes do not remove cached copies**. Filing requires an explicit interactive `y`. There is no `--yes` bypass for the filing step. Fields the tool refused to include are listed as "withheld". The secret-pattern scan gates the **entire body**, not only free-text fields, because individually allowlisted fields can leak in combination (for example a private-repo remote plus failing check IDs).

**Frozen contract (PR 1).** The bundle schema and fingerprint format are compatibility interfaces, defined once in a single canonical module. The issue form's required fields, the CLI renderer, the CI `intake` check, and the Vizor route all derive from that definition. Vizor's `VIZOR_META` payload gets the same allowlist test as the CLI.

**Filing:** `gh issue create` with the user's own `gh` login, using the `bug_report.yml` form (labels `bug`, `early-adopter`). If `gh` is unauthenticated or offline, fall back to a prefilled `issues/new` URL plus a local `.md` file.

### 2. Capture and surfaces

**Flight recorder:** `.synlynk/flight.jsonl`, ring buffer of the last 50 invocations. Record fields: timestamp, command name, exit code, duration, first line of any error, `failed` flag. Only flag names are stored, never free-text argument values (prompts, `--task`). Writes never raise and never change the exit code. The recorder **must not create `.synlynk/`** in an uninitialized directory (guards against the #5299 class). The first error line is run through the redaction helpers **at write time**, so the local file is safe to copy or attach. On by default; local only; contents leave the machine only through the Section 1 preview opt-in. **Off-switch:** `synlynk report --clear-flight` deletes the buffer, and a config flag (`flight_recorder: false`) disables it; the recorder's privacy policy is stated in the CLI help.

**Commands:** `synlynk report` (interactive: asks what went wrong, optional one-line description) and `synlynk report --last` (built from the most recent failed record plus the Section 1 bundle). Add both to `COMMAND_TAXONOMY` in `synlynk/taxonomy.py`.

**Surfaces** (one line: `Something wrong? synlynk report --last`), shown only when degraded unless noted:

1. Error footer on any non-zero exit or unhandled exception.
2. Bearings card, always shown (standing reference).
3. Task-boundary messages: dispatch completion/failure, circuit-breaker kills, and the `init` wizard's final screen. These include the failed job ID so the report can pull that job's context.
4. Vizor: a "Report issue" action in the footer and on sentinel alerts (building on the existing "Raise issue" button). It captures route and `VIZOR_META`; console contents are not captured by default.

**Issue form:** `.github/ISSUE_TEMPLATE/bug_report.yml` replaces `bug_report.md`. A required `bundle` textarea is filled by the CLI; hand-typed fields (what you were doing / expected / actual) are optional. Labels: `bug`, `early-adopter`. A footer states what was and was not collected.

**Triage (comment-only):** the CI check and PM bot never auto-label, auto-close, or otherwise mutate the issue beyond posting a comment. An `intake` CI check flags issues with no bundle and comments with `synlynk report` instructions. The PM bot treats `early-adopter` issues as a signal: dedup by fingerprint, link related tickets, assign severity per the Live Issues SOP.

**Fingerprint (settled):** first 12 hex chars of `sha256` over: sorted failing doctor check IDs, command name, exit code, and the first error line normalized (numbers, paths, and hashes stripped). Normalization must strip everything variable before hashing, and the `fingerprint: <hex>` line is part of the previewed body, so the user sees exactly what is published. Used for exact-match dedup.

### 3. Testing and errors

**Testing:**

- Allowlist property test: environment full of fake secrets (tokens, credentialed URLs, username, hostname, home path); assert none appear in the rendered body.
- Env test: canary value in `ANTHROPIC_API_KEY` never appears; only the name and set/unset.
- Free-text test: log fixture with embedded secrets is either scrubbed or blocks submission.
- Flight recorder: concurrent invocations do not corrupt the file; 50-record cap holds; write failure does not change exit code; `init` in a bare directory leaves no `.synlynk/` (the #5299 regression guard).
- Vizor DOM test: the action exists and its payload has only allowed fields (the style of test #5368 notes was missing).
- Filing: fake `gh` verifies the preview gate; without `y` nothing is filed, and `--yes` does not skip preview.

- Whole-body scan test: a body whose individual fields are each allowlisted but jointly leak (private-repo remote plus identifying check IDs) is flagged.
- Salt test: two installs produce different hashes for the same username and hostname; one install is stable across runs.
- End-to-end preview and fallback flows run in both interactive and non-interactive terminals.

**Errors:** the prefilled-URL fallback caps the bundle size and puts overflow in the local `.md` file. A failed collector yields "unavailable" for that field; the report still builds. Offline or unauthenticated `gh` falls back to URL + local file. A secret the user will not remove means the tool refuses to file and explains why.

## Sequencing (one feature per PR; docs in their own PRs)

1. **PR 1:** `bug_report.yml`, `synlynk report` with allowlist collector, redaction, preview, filing.
2. **PR 2:** flight recorder, `--last`, error footer, bearings and task-boundary hints.
3. **PR 3:** Vizor action, PM-bot triage and dedup, `intake` CI check.

Parent tracking issue and GOVERNS goal are created at spec-save time. Stories for every plan task are generated automatically once the plan is committed.

## Non-goals

- Automatic or background submission of any data.
- Telemetry beyond the user-initiated report.
- Fixing #5368 itself (tracked separately).

## Review record

DECIDE panel (claude, agy, codex, grok) recorded as `dec-049b4dbf` (`project-docs/decisions/2026-11-20-approve-bug-report-intake-design-docs-su.md`): approved with eight conditions, all folded into this spec: salted identity hash, write-time recorder redaction, recorder off-switch, private-repo remote handling, public-permanence warning plus whole-body scan, fingerprint normalization and previewed line, frozen bundle contract, and the smaller items (URL-fallback cap, comment-only triage, interactive/non-interactive e2e tests). Panel approval is advisory; Nikhil's sign-off is still required.

## Open questions for review

- Flight recorder default-on is resolved as yes, with the documented off-switch.
- `--private` (non-public destination) is out of scope; public GitHub was chosen.
