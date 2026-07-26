---
decision_id: dec-ba21be09
topic: "Should synlynk implement per-role GitHub App identity as designed in docs/superpowers/specs/2026-07-23-agent-github-identity-design.md and planned in docs/superpowers/plans/2026-07-24-agent-github-identity-design.md? This touches auth/security-adjacent surface: GitHub App private keys stored at .synlynk/github_apps/<role>.pem (chmod 600, gitignored), RS256 JWT signing done by shelling out to the system openssl binary (no Python crypto dependency), short-lived installation tokens minted via the GitHub API and cached in-memory, and injecting a role-scoped GH_TOKEN into dispatched agents' subprocess environment at dispatch time. Evaluate: (1) is the openssl-subprocess-signing approach for RS256 safe and sound, or does it introduce risks a Python crypto library would avoid; (2) is storing App private keys as plaintext .pem files on disk (even chmod 600, gitignored) an acceptable risk for a local dev tool, or does it need stronger protection; (3) is injecting GH_TOKEN into subprocess env for dispatched CLI agents (which may log their env or pass it to sub-processes) a meaningful token-leakage risk, and if so what mitigation is needed; (4) should this ship as planned, need revision before implementation, or need a narrower first slice; (5) is dispatching this implementation to Codex (per the Capability-Based Task Allocation table) appropriate given the security sensitivity, or does auth-adjacent code warrant different review handling before merge."
date: 2026-07-25
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Should synlynk implement per-role GitHub App identity as designed in docs/superpowers/specs/2026-07-23-agent-github-identity-design.md and planned in docs/superpowers/plans/2026-07-24-agent-github-identity-design.md? This touches auth/security-adjacent surface: GitHub App private keys stored at .synlynk/github_apps/<role>.pem (chmod 600, gitignored), RS256 JWT signing done by shelling out to the system openssl binary (no Python crypto dependency), short-lived installation tokens minted via the GitHub API and cached in-memory, and injecting a role-scoped GH_TOKEN into dispatched agents' subprocess environment at dispatch time. Evaluate: (1) is the openssl-subprocess-signing approach for RS256 safe and sound, or does it introduce risks a Python crypto library would avoid; (2) is storing App private keys as plaintext .pem files on disk (even chmod 600, gitignored) an acceptable risk for a local dev tool, or does it need stronger protection; (3) is injecting GH_TOKEN into subprocess env for dispatched CLI agents (which may log their env or pass it to sub-processes) a meaningful token-leakage risk, and if so what mitigation is needed; (4) should this ship as planned, need revision before implementation, or need a narrower first slice; (5) is dispatching this implementation to Codex (per the Capability-Based Task Allocation table) appropriate given the security sensitivity, or does auth-adjacent code warrant different review handling before merge.

## Panel Inputs

### claude
This is a decision-panel analysis task, not implementation work, so no skill applies here — I'll give my assessment directly.

**1. openssl-subprocess-signing for RS256:** Sound. Shelling out to `openssl dgst -sha256 -sign` for RS256 is a well-worn pattern (used by many CI/CD tools issuing GitHub App JWTs) and avoids adding `cryptography`/`PyJWT` as a dependency, consistent with synlynk's stdlib-only design. The risk isn't cryptographic — it's operational: private key material touches disk paths, error messages, and process argv/env if not handled carefully. Ensure the key is passed via stdin or a temp file with restricted perms, never as a CLI argument (visible in `ps`), and that openssl's stderr on failure doesn't leak key contents.

**2. Plaintext .pem on disk, chmod 600, gitignored:** Acceptable for a local dev tool. This matches how `~/.ssh/id_rsa` and most local credential stores work. The floor is: verify gitignore actually catches it (test with `git check-ignore`), verify chmod 600 is enforced at write time not just assumed, and confirm it's excluded from any backup/sync tooling (iCloud, dotfiles). No need for OS keychain integration at this stage — that's over-engineering for v1.

**3. GH_TOKEN in subprocess env:** This is the real risk. Dispatched CLI agents (Claude, Gemini, Codex, Grok) may echo env vars in error dumps, pass env to further subprocesses, or in worst case a compromised/malicious prompt could exfiltrate `$GH_TOKEN`. Mitigation: mint tokens with the narrowest possible installation scope/permissions per role, keep TTL short (GitHub installation tokens already expire in 1hr — don't extend), and never log full env in synlynk's own telemetry capture. Consider scrubbing `GH_TOKEN` from any captured stdout/stderr before writing to `.synlynk/telemetry.json`.

**4. Ship as planned or narrower slice:** Narrower first slice. Ship with one role (e.g., Grok, since it already owns GitHub writes) before generalizing to all four — validates token scoping and leak-scrubbing against real dispatch behavior before multiplying the attack surface.

**5. Dispatch to Codex vs. different handling:** Codex can implement it, but this is exactly the "auth-adjacent" case that warrants deviation from default routing — require Claude (not another implementer) to do the security review pass before merge, beyond the standard non-authoring-reviewer rule.

**Recommendation:** Proceed, but narrow the first slice to one role and require an explicit security-focused review round on top of standard PR review before merge.

### codex
The design is directionally sound, but I would not ship it exactly as planned.

1. `openssl` subprocess signing is acceptable for a local dev tool, but it is not as clean as an in-process crypto library. The main added risks are PATH/binary trust, platform variance, and weaker error handling boundaries. It is not inherently unsafe if you call the binary directly with an argv list, verify failures strictly, and treat the local host as trusted. See the plan’s architecture note on `openssl` signing and stdlib-only constraints in [the plan](file:///Users/nikhilsoman/dev/synlynk/.worktrees/chore+agent-github-identity-design/docs/superpowers/plans/2026-07-24-agent-github-identity-design.md#L9).

2. Storing GitHub App private keys as plaintext `.pem` files with `chmod 600` and gitignore is a reasonable local-dev compromise, not strong protection. It is acceptable only if the threat model is “single-user workstation, local compromise is already game over.” If these keys ever matter beyond that, they should move to OS-backed secret storage or an encrypted-at-rest scheme. The spec’s current file layout is explicit about this risk surface in [the design](file:///Users/nikhilsoman/dev/synlynk/.worktrees/chore+agent-github-identity-design/docs/superpowers/specs/2026-07-23-agent-github-identity-design.md#L41).

3. Injecting `GH_TOKEN` into dispatched subprocess environments is a real leakage risk. Anything that prints env vars, spawns child processes, writes crash dumps, or gets inspected by the same user can exfiltrate it. Mitigation needs to be explicit: keep tokens short-lived, repo-scoped, and injected only into the minimal process boundary; redact env dumps; avoid broad debug logging; and prefer a narrow `gh` wrapper over exposing the token to the whole agent runtime. The design currently proposes broad env injection at dispatch time ([spec](file:///Users/nikhilsoman/dev/synlynk/.worktrees/chore+agent-github-identity-design/docs/superpowers/specs/2026-07-23-agent-github-identity-design.md#L60)).

4. Recommendation: revise before implementation, and start with a narrower first slice. I would ship token minting and manual provisioning first, but not full automatic env injection across all dispatched agents.

5. Dispatching the implementation to Codex is appropriate for the Python/CLI/test work in the routing table, but auth-adjacent code should get a stricter review path before merge. In other words: Codex can build it; a separate security-minded review should bless the threat model and the token-handling details before it lands. The repo’s own routing policy assigns Python/CLI/tests to Codex in [CLAUDE.md](file:///Users/nikhilsoman/dev/synlynk/.worktrees/chore+agent-github-identity-design/CLAUDE.md#L143).  

My position: proceed, but only as a revised, narrower implementation with explicit security review gates.

### grok
I'll review the design and plan docs first, then answer the five evaluation points with a clear recommendation.## Decision panel: per-role GitHub App identity

### (1) openssl subprocess RS256
Sound for a **stdlib-only** CLI. `openssl dgst -sha256 -sign` with list argv (no shell) is a well-understood RS256 path; the crypto itself is not weaker than `cryptography` if the binary is the real OpenSSL. Risks a Python library would reduce: **PATH hijack**, surprising LibreSSL/old OpenSSL behavior, and messier error surfaces. Mitigations to add before merge: resolve a fixed openssl path (`shutil.which` + prefer `/usr/bin/openssl`), refuse non-absolute/out-of-tree `private_key_path`, and `synlynk doctor` checks for openssl + key perms. Do **not** add a crypto dependency just for this.

### (2) Plaintext `.pem` on disk
**Acceptable for a local single-user tool.** Matches gh App keys, deploy keys, and SSH practice: `chmod 600` + gitignore. OS keychain/secret-store would help shared machines or exfil via backup, but is out of scope and platform-heavy. Require: write-time `0o600`, doctor warn if not, never log PEM contents, document that App keys = full installation authority (revoke = re-provision).

### (3) `GH_TOKEN` in agent env
**Meaningful but bounded.** Agents can dump env, log, or spawn children. Mitigations already partial: ~1h installation tokens + minimal App perms. Tighten further: inject only when the job needs GitHub write (align with `--requires-gh-write`); scrub token-shaped strings from telemetry/captured stdout; never persist tokens to disk (in-memory cache only, as planned). Short TTL makes env leakage far better than ambient PATs today.

### (4) Ship / revise / slice
**Ship the design; implement as the plan’s staged rollout**, with the small hygiene items above as blocking review comments—not a redesign. First slice: `github_app_auth` + `identity init --role` + manual rxcc smoke (dev open PR, qa real approve). Wire default dispatch injection and init/upgrade only after that pass.

### (5) Codex vs review handling
**Codex implementation is appropriate** (Python/CLI/tests). Auth-adjacent code does **not** move implementation off Codex, but **does** require elevated merge review: checklist on key path, gitignore, openssl invocation, env injection scope, and telemetry scrubbing—plus human/Claude security pass before merge, not only the #423 COMMENT-approve fallback.

**Position:** Proceed as designed and planned, with a **narrow first slice** and **minor security hygiene** (absolute openssl, path confinement, conditional GH_TOKEN, scrubbing, doctor checks). Codex builds; heightened security review gates merge. This is the right fix for #423 without Mode B or secret-store complexity.

## Synthesis
This is a synthesis task on a completed decision panel, not creative/implementation work — no skill applies here.

All three inputs converge on the same shape: proceed, but narrower and with tighter review gates. Synthesizing:

**On the four technical questions**, there's no real disagreement — openssl subprocess signing is sound for a stdlib-only tool (risk is operational: argv exposure, PATH trust, error leakage, not cryptographic weakness); plaintext chmod-600 gitignored `.pem` is an acceptable local-dev tradeoff matching existing SSH/deploy-key norms; `GH_TOKEN` env injection is the one genuine risk surface and needs scrubbing from telemetry/logs plus scoping injection to only jobs that actually need GitHub writes, not all dispatched agents by default.

**On sequencing**, all three explicitly reject "ship as fully planned" in favor of a narrower first slice — token minting + one role (Claude/Grok favor starting with the role that already owns GitHub writes) validated end-to-end before generalizing to all four roles and full auto-injection at every dispatch.

**On routing**, all three agree Codex remains the correct implementer per the capability table, but all three also agree this doesn't get the standard review path — it needs an explicit security-focused pass (beyond the standard non-authoring-reviewer + COMMENT-approve fallback from #423) before merge.

Decision: Proceed with the per-role GitHub App identity design, but revise the rollout to a narrower first slice — implement JWT signing, token minting/caching, and manual provisioning for a single role first (the role that already performs GitHub writes), with `GH_TOKEN` injection scoped only to jobs that declare a GitHub-write need (e.g. via `--requires-gh-write`) rather than injected into every dispatched agent's environment by default. Before that slice merges, add the hygiene items called out across all three reviews: resolve openssl via an absolute/verified path (no bare PATH lookup), pass the private key via file/stdin never as an argv string, enforce 0o600 at write time with a doctor-style check, verify gitignore actually excludes `.synlynk/github_apps/`, and scrub token-shaped strings from anything synlynk captures into telemetry or logs. Codex implements per the existing Python/CLI routing, but this PR requires an additional explicit security-focused review pass (Claude, on top of the standard non-authoring-reviewer rule) covering the threat model and token-handling details specifically, before the standard PR check/merge process applies. Only after this first-role slice is validated in real dispatch use should injection be generalized to all roles and made default at dispatch time.

## Decision
Decision: Proceed with the per-role GitHub App identity design, but revise the rollout to a narrower first slice — implement JWT signing, token minting/caching, and manual provisioning for a single role first (the role that already performs GitHub writes), with `GH_TOKEN` injection scoped only to jobs that declare a GitHub-write need (e.g. via `--requires-gh-write`) rather than injected into every dispatched agent's environment by default. Before that slice merges, add the hygiene items called out across all three reviews: resolve openssl via an absolute/verified path (no bare PATH lookup), pass the private key via file/stdin never as an argv string, enforce 0o600 at write time with a doctor-style check, verify gitignore actually excludes `.synlynk/github_apps/`, and scrub token-shaped strings from anything synlynk captures into telemetry or logs. Codex implements per the existing Python/CLI routing, but this PR requires an additional explicit security-focused review pass (Claude, on top of the standard non-authoring-reviewer rule) covering the threat model and token-handling details specifically, before the standard PR check/merge process applies. Only after this first-role slice is validated in real dispatch use should injection be generalized to all roles and made default at dispatch time.

> Signatures: see 2026-07-25-should-synlynk-implement-per-role-github.json
