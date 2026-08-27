<!-- generated - source of truth is state.db -->
---
decision_id: dec-ea34075c
topic: "Review docs/superpowers/specs/2026-08-19-gh-write-broker-design.md (GitHub-write broker design, resolves #865) from Grok's perspective as maintainer of the grok harness: feasibility of grok emitting gh_write_request.json and consuming gh_write_result.json under its own execution model, and whether grok is fit to run the broker process itself given the qa role's CI/CD/infra charter overlap. Flag any correctness, security, or feasibility problems."
date: 2026-08-19
panel: [grok]
status: approved
---

## Topic
Review docs/superpowers/specs/2026-08-19-gh-write-broker-design.md (GitHub-write broker design, resolves #865) from Grok's perspective as maintainer of the grok harness: feasibility of grok emitting gh_write_request.json and consuming gh_write_result.json under its own execution model, and whether grok is fit to run the broker process itself given the qa role's CI/CD/infra charter overlap. Flag any correctness, security, or feasibility problems.

## Panel Inputs

### grok
I'll review the GitHub-write broker design from the grok harness maintainer's perspective and start by reading the spec plus how grok currently executes jobs.The spec is clear on the request/result files; next I’ll check how grok actually runs jobs and where the qa role overlaps the broker.**Grok can emit and consume the request/result files. Grok must not run the broker.**

Grok is not Codex. Headless `grok --single` has `can_gh_write: true`, no `workspace-write` network cut, and Write/Read/Bash in the same turn. Writing `.synlynk/gh_write_request.json` is trivial. In default (post-turn) mode Grok never sees the result in-process, which matches today’s fire-and-forget dispatch. In elevated mode a bounded sleep-and-reread of `gh_write_result.json` is also in-model: this harness already loops on files and command output without sockets.

The hard grok-specific risk is the opposite of Codex’s: **we still have a live `gh`/MCP path.** #426 routed writes to Grok because they work. A prompt that says “write JSON instead” is not enforcement. If `GH_TOKEN` or the user keyring remains visible, Grok will keep calling `gh` and recreate #569 (wrong identity) and #659 (direct write). Once the broker ships, even `can_gh_write` harnesses need `gh`/GitHub MCP stripped from the job env. Codex gets that for free; Grok does not.

**Do not put Grok in the broker seat.** qa’s charter (CI/CD, IaC, deploy) and Grok’s infra routing explain who *implements* `gh_broker.py`. They do not justify an LLM hosting the trust boundary. The broker exists so merge/review/comment run *outside* agent judgment (§2 already rejected elevated-trust invocation). qa should keep CI truthful; the broker should *read* CI. qa must not also execute merges. That split is already in the roles doc (§5 merge = architect; §9 defers any qa merge amendment). Collapsing them would put a prompt-driven process on the same side of the token as the sandbox the design just emptied.

**Correctness holes to close before build:**

- **`extra_args` is an argv injection surface.** Allowlist keys per action. Never forward raw flags (`--repo`, `--body-file`, admin merge).
- **Authorize action × job role.** A `dev` Grok job emitting `merge` + `approve: true` must be rejected. Token = that job’s role, never a more privileged one.
- **One filename is not a queue.** Elevated “merge then close issue” will overwrite request/result. Need `request_id` and consume-on-read.
- **`gh pr checks` with “no checks reported” must fail-closed.** This repo also cannot use `gh pr merge --auto`.
- **#423 remains:** App-token `review --approve` on a same-identity PR still fails. Map that to the COMMENT-checklist path or a typed reject.
- Unregistered-worktree **ignore** looks like a hang to a 60s poller; treat timeout as reject.

**Position:** Approve the file protocol and host-side broker. Reject Grok (or any harness) as broker runtime. Treat “Grok stops calling `gh`” as a shipping requirement, not prompt hygiene. Do not start implementation until `extra_args`, role×action auth, and request-id consumption are specified.

## Synthesis
I'll read the GitHub-write broker spec and the grok harness execution model so the decision matches how Grok actually runs jobs.The spec matches the panel’s protocol picture. I’ll confirm the qa/merge charter and Grok’s live `gh` path so the decision doesn’t over-claim.**Approve the file protocol and a host-side broker. Do not let Grok (or any harness) run the broker. Do not start implementation until the spec closes the request-shape holes.**

Grok can emit `.synlynk/gh_write_request.json` and, in elevated mode, poll `.synlynk/gh_write_result.json`. Headless `grok --single` already has Write/Read/Bash in one turn, `can_gh_write: true`, and no Codex-style `workspace-write` network cut. Default (post-turn) mode never needs an in-process result — that matches today’s fire-and-forget dispatch. Elevated sleep-and-reread is also in-model: this harness already loops on files and command output without sockets. The request/result files are a fit for Grok’s execution model.

The Grok-specific risk is the opposite of Codex’s. #426 routed GitHub writes to Grok because they work. After the broker ships, a prompt that says “write JSON instead” is not enforcement. If `GH_TOKEN` or the user keyring stays visible, Grok will keep calling `gh` (or GitHub MCP) and recreate #569 (wrong identity) and #659 (direct write). Codex loses that path structurally. Grok does not. Shipping the broker therefore requires stripping `gh` and GitHub MCP from the job environment for every harness, including `can_gh_write` ones.

Do not put Grok in the broker seat. qa’s CI/CD/IaC/deploy charter and Grok’s infra routing explain who *implements* `gh_broker.py`. They do not justify an LLM hosting the trust boundary. The design already rejected elevated-trust invocation (§2): merge, review, and comment must run outside agent judgment. qa should keep CI truthful; the broker should *read* CI. qa must not also execute merges. Roles already split that: merge is architect (§5); any qa merge amendment is deferred (§9). Collapsing them would put a prompt-driven process on the same side of the token as the sandbox this design just emptied.

Correctness holes that must be specified before build:

| Gap | Why it blocks |
|---|---|
| `extra_args` as a raw map | Argv injection: `--repo`, `--body-file`, admin merge flags. Allowlist keys per action; never forward raw flags. |
| No action × job-role auth | A `dev` Grok job can emit `merge` + `approve: true`. Token must be that job’s role, never a more privileged one. |
| One filename is not a queue | Elevated “merge then close issue” overwrites request/result. Need `request_id` and consume-on-read. |
| `gh pr checks` with “no checks reported” | Must fail-closed. This repo also cannot use `gh pr merge --auto`. |
| #423 same-identity `review --approve` | App-token approve on a same-identity PR still fails. Map to the COMMENT-checklist path or a typed reject. |
| Unregistered-worktree **ignore** | A 60s poller sees a hang. Treat timeout as reject. |

Decision: Approve the request/result file protocol and a host-side, non-LLM `gh_broker.py` invoked by the dispatch daemon. Reject Grok — and any harness — as broker runtime. Treat “Grok stops calling `gh`” as a shipping requirement (env/MCP strip), not prompt hygiene. Hold implementation until `extra_args` is an allowlisted per-action map, the broker authorizes action × job role, and request/result files are consumed by `request_id` rather than a single overwriteable filename.

## Decision
Decision: Approve the request/result file protocol and a host-side, non-LLM `gh_broker.py` invoked by the dispatch daemon. Reject Grok — and any harness — as broker runtime. Treat “Grok stops calling `gh`” as a shipping requirement (env/MCP strip), not prompt hygiene. Hold implementation until `extra_args` is an allowlisted per-action map, the broker authorizes action × job role, and request/result files are consumed by `request_id` rather than a single overwriteable filename.

> Signatures: see 2026-08-19-review-docs-superpowers-specs-2026-08-19.json
