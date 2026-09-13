# Safe Fleet Parity Migration Playbook

## 1. Executive Summary & Core Invariants

This playbook governs the declarative, non-destructive adoption of Synlynk across existing and early-adopter repositories in the multi-agent fleet. It ensures operational parity with zero disruption to existing development workflows.

### Non-Negotiable Invariants
1. **Sacred User Domain Invariant:** Content outside explicit `<!-- synlynk:start -->` and `<!-- synlynk:harness -->` directive fences must never be modified, truncated, or overwritten. 100% of user instructions, architectural decisions, and custom conventions are preserved.
2. **Worktree-First Isolation Invariant:** Remediation and migration work must never dirty or commit to the active branch (`main`, `master`, or feature branches). All changes execute in an isolated shadow worktree (`.worktrees/synlynk-parity-check`).
3. **Stack-Aware Policy Invariant:** Never impose Python branch-protection matrix rules or CI assumptions onto Node, Go, or Rust repositories. Test commands and quality gates must match the repository's native package manager and runtime.
4. **Recursive Ignore Hygiene:** Monorepo subpackages (`apps/`, `packages/`, `infra/`) must not leak nested `.synlynk/` operational files into `git status`. Recursive `**/.synlynk/*` rules must protect state while tracking core policy and configuration.

---

## 2. Standard 8-Step Migration Checklist

Every target repository must advance sequentially through these 8 gates:

```
[ Gate 1: Preflight Audit & Dry-Run ]
                │
[ Gate 2: Shadow Worktree Creation ]
                │
[ Gate 3: Directive AST Fencing ]
                │
[ Gate 4: Config & Policy Provisioning ]
                │
[ Gate 5: Recursive .gitignore Hardening ]
                │
[ Gate 6: Worktree Verification & Tests ]
                │
[ Gate 7: Worktree Commit & PR Submission ]
                │
[ Gate 8: QA Review, Merge & Worktree Cleanup ]
```

### Gate 1: Preflight Audit & Dry-Run
- [ ] Inspect git branch and clean state: `git status --porcelain`.
- [ ] Run dry-run parity analysis:
  ```bash
  synlynk heal --parity --dry-run
  ```
- [ ] Verify detected stack (`language`, `package_manager`, `test_cmd`) matches repo reality.
- [ ] Review gaps identified (e.g. missing fences, missing `policy.json`, missing `roles.yaml`, un-fenced directive files).

### Gate 2: Shadow Worktree Creation
- [ ] Ensure `.worktrees/synlynk-parity-check` is initialized on branch `feat/agy/synlynk-adoption-parity`.
- [ ] Confirm the primary working tree is completely untouched.

### Gate 3: Directive AST Fencing
- [ ] Parse `CLAUDE.md`, `GEMINI.md`, `AGENTS.md`, and `GROK.md`.
- [ ] Verify that all user-authored headers and custom domain rules remain preceding the `<!-- synlynk:start -->` fence.
- [ ] Inject canonical start block (`<!-- synlynk:start version="0.20.0" tool="..." -->`) and modern SOP harness block (`<!-- synlynk:harness ... -->`).

### Gate 4: Stack-Aware Config & Policy Provisioning
- [ ] Verify `.synlynk/config.json` declares all 4 core harnesses (`claude`, `codex`, `agy`, `grok`) in `workgroup_agents`.
- [ ] Generate `.synlynk/policy.json` with native test commands (e.g., `npm test` / `pnpm test` for Node, `go test ./...` for Go, `pytest` for Python).
- [ ] Seed canonical `.synlynk/roles.yaml` defining 6 standard roles (`pm`, `tpm`, `qa`, `dev`, `architect`, `marketing`).
- [ ] Seed `.agents/` profiles (`claude.json`, `agy.json`, `codex.json`, `grok.json`).

### Gate 5: Recursive `.gitignore` Hardening
- [ ] Verify `.gitignore` contains:
  ```gitignore
  **/.synlynk/*
  !**/.synlynk/config.json
  !**/.synlynk/policy.json
  !**/.synlynk/roles.yaml
  !**/.synlynk/instructions.json
  !**/.synlynk/model_rates.json
  !**/.synlynk/project-docs/
  ```

### Gate 6: Worktree Verification & Tests
- [ ] Run diagnostic inside worktree:
  ```bash
  synlynk doctor
  ```
  Assert: `✓ fleet_parity: Directives fenced, workgroup roster complete, and policy authority active`.
- [ ] Run native repository tests inside the worktree (e.g. `npm test`, `pnpm test`, `pytest`).

### Gate 7: Worktree Commit & PR Submission
- [ ] Commit changes inside `.worktrees/synlynk-parity-check` with proper trailer:
  ```
  Co-Authored-By: AGY <noreply@antigravity.dev>
  ```
- [ ] Push feature branch:
  ```bash
  git push origin feat/agy/synlynk-adoption-parity
  ```
- [ ] Open Pull Request:
  ```bash
  synlynk gh --role dev -- pr create --fill
  ```

### Gate 8: QA Review, Merge & Worktree Cleanup
- [ ] Verify CI checks are green on the PR.
- [ ] Run `synlynk pr check` from the checked-out worktree.
- [ ] Submit QA review and merge:
  ```bash
  synlynk gh --role qa -- pr review <PR> --approve --body "QA Gate Verified"
  synlynk gh --role qa -- pr merge <PR> --squash --delete-branch
  ```
- [ ] Remove shadow worktree:
  ```bash
  git worktree remove .worktrees/synlynk-parity-check
  ```

---

## 3. In-Browser Workspace Agent Role Provisioning (`synlynk viz`)

Once baseline parity is merged, autonomous execution requires role-scoped identities to prevent PR self-approval collisions (#423).

### 1-Click Provisioning Steps
1. Launch Vizor in the target workspace:
   ```bash
   synlynk viz
   ```
2. Open the browser to:
   ```
   http://localhost:27472/onboarding/roles
   ```
3. For each unconfigured role (`pm`, `tpm`, `qa`, `dev`, `architect`, `marketing`), click **"Provision with GitHub"**.
4. GitHub opens with a pre-configured GitHub App Manifest:
   - App Name: `synlynk-<role>-<repo_name>`
   - Permissions: Scoped read/write for issues, PRs, and contents; checks & statuses write for `qa`/`dev`.
   - Callback: `http://localhost:27472/auth/callback?role=<role>`
5. Click **"Create GitHub App"**; GitHub redirects back to Vizor with an authorization code.
6. Vizor exchanges the code for credentials, writes `<role>.app.json` and `<role>.private-key.pem` with `0o600` permissions into `.synlynk/github_apps/<role>/`, and mints an initial role token.
7. Observe the Live 4-Point Readiness Matrix updating automatically to `PASS` across all vectors.

---

## 4. Fleet Rollout Matrix & Tracking

| Repository | Stack | Preflight Status | Parity Branch / PR | Verification | Status |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **`rxcc`** | Node / TS (pnpm) | Audited | Pending Worktree Run | Doctor `PASS` | Gate 1 Ready |
| **`cc-videoreframing`** | Python (pip) | Gaps identified | `feat/agy/synlynk-adoption-parity` | Doctor `PASS` | Gate 6 Verified |
| **`playblazer-ng`** | Python (pip) | Gaps identified | `feat/agy/synlynk-adoption-parity` | Doctor `PASS` | Gate 6 Verified |
| **`hitchcock`** | Python (pip) | Gaps identified | `feat/agy/synlynk-adoption-parity` | Doctor `PASS` | Gate 6 Verified |
