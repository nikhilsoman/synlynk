# RCA: [LIVE-33] Onboarding dispatches before the workspace is published

**Date:** 2026-11-18
**Severity:** Sev2
**Status:** Root cause confirmed. Point fixes for the job id, one Claude profile, and premature reconcile have shipped. The publish-order bug, sovereign-runner discovery, and multi-identity quota federation have not.
**Tracking issue:** gh:#5363 (OPEN)
**Related:** gh:#5297 (job id, closed by #5303), gh:#5298 (Claude env passthrough, closed by #5303), gh:#5299 (reconcile-before-init, closed by #5303), gh:#5302 (FTUE epic, closed by the same PR), gh:#1990 (GOVERNS hard-fail, still a warning)

## Summary

An early adopter ran Synlynk's first-run wizard on a DGX Spark setup (LiteLLM in front of local models, more than one Claude config directory). He confirmed the built-in architecture review. The process spawned Claude, cut a worktree from `origin/main`, and stashed his dirty checkout **before** it wrote workspace config, context, or role files.

He then had three inconsistent views of the same repo at once: a job running against `origin/main`, a stash and tar of the tree he actually had, and a config write that landed only in the main checkout after the agent had started. The log line said `synlynk logs --job unknown`, so he could not follow the job. He opened `.synlynk/project-docs/memory.md` in the main checkout, which is the path the template names and not where a just-started worktree job writes.

#5303 fixed the dict key that printed `unknown`, passed one Claude profile's gateway variables into the child, and stopped `init` from reconciling jobs before a repo is initialized. The wizard still offers dispatch before publish. Onboarding still does not inventory a sovereign model server, and it still cannot see a second identity or add that identity's quota to a pool.

## Timeline

- **2026-11-12 / 2026-11-13, early-adopter session.** Wizard dispatch preview: agent `claude`, cycle Visualize, full context, ~2h, R 80K / W 8K / T 12. Prompt is the `arch-review` template (`synlynk/launch_templates.py`), workspace name `jitendra.agrawal`, stack Python and CI/CD, topology multi. He pressed enter.
- The preflight printed `capability gate degraded: repo artifacts present for gh-actions; no explicit --requires declaration` and `GOVERNS linkage missing — dispatch proceeding, but this will hard-fail once #1990 ships`. Both are non-blocking on this build. The launch screen calls `dispatch_agent` with `story_id=None` and no `--requires`.
- Worktree base resolved and verified against `origin/main` at `6c169e292b8d0cf822558d9a316589e6c3bf14b1`.
- The screen printed `▶ [unknown] claude dispatched` and `Log: synlynk logs --job unknown`. That string is `job.get("job_id")` against a dict whose key is `id`. `synlynk dispatch` already read `id`. The launch path did not. `dispatch_agent` had returned a dict, so the process was spawned. The suggested log command cannot find the job.
- Immediately after that line, the wizard's commit-on-complete ran, because the tree was dirty:
  - `.synlynk/backups/init-1794483517.tar.gz`
  - git stash `synlynk-init-safety-backup-1794483517`
  - `context.md` rewritten (50,919 characters)
  - workspace config `~/.synlynk/workspaces/jitendra.agrawal/config.json`
  - role fences written to `CLAUDE.md` and `AGENTS.md`
- The printed home path is `/Users/jitendra.agrawal`, a macOS home. The product failure does not depend on DGX OS. The Spark matters because that is the machine whose models and profiles onboarding failed to see.
- He opened `vi` on `.synlynk/project-docs/memory.md` in the checkout the wizard was using. The template tells the agent to append a section to that path inside the job worktree. The main checkout file is not the job's output, and on an unmigrated repo Synlynk's own memory file is `project-docs/memory.md`.
- **2026-11-15.** #5297, #5298, #5299, and epic #5302 were filed from this session. #5303 merged the same day and closed them. On current `origin/main` (`98606735`):
  - `synlynk/wizard.py` resolves `job.get("id") or job.get("job_id")`.
  - `HARNESS_CAPABILITY_BASELINES["claude"]["env_passthrough"]` includes `ANTHROPIC_BASE_URL`, `ANTHROPIC_AUTH_TOKEN`, `ANTHROPIC_API_KEY`, and `CLAUDE_CONFIG_DIR`.
  - `synlynk/cli.py` skips `_reconcile_jobs()` when the command is `init` and neither `.synlynk/config.json` nor `.synlynk/workspace.json` exists.
- **2026-11-18.** Re-read of `wizard_init` shows screen 6 still auto-launches, and the writes still happen after that call returns. `synlynk/launch.py` `dispatch_first_win_remediation` still reads only `job["job_id"]`. This RCA files the remainder as #5363.

## Root cause

Three separate gaps. The screenshot is gap 1. Gaps 2 and 3 are why a DGX Spark with a local gateway and several config directories still cannot complete onboarding even after #5303.

### 1. Publish happens after the first side effect

`wizard_init` treats "the human pressed a key on the cheat sheet" as permission to dispatch, and treats "dispatch returned" as permission to mutate the checkout.

```text
_wiz_screen_launch(..., auto_launch=True)
    cmd_launch_ftue()
        dispatch_agent(...)          # worktree, process, jobs record
# only then:
guard_dirty_worktree()               # tar + git stash of the dirty caller tree
write_workspace_config(...)
generate_structured_context(...)     # the 50,919-character context.md
upsert role fences into CLAUDE.md / AGENTS.md
```

`auto_launch_after_wizard` defaults to true. There is no published-generation marker. Dispatch, Vizor, and a human reading `CLAUDE.md` all observe whatever happens to be on disk. During the window above, that is an unpublished mix:

- The job's worktree is `origin/main` at the moment of `git worktree add`. It does not contain the context or the role text written afterwards, and it does not contain the uncommitted files the stash then hid.
- The stash runs only when `git status --porcelain` is non-empty. Init therefore deletes the caller's uncommitted work from the index and worktree as a side effect of finishing setup, after a job has already started.
- The safety tar walks the repo (skipping `.git`, `.worktrees`, `__pycache__`, and virtualenvs). On a large tree that is a long, visible mutation, not a private staging write.

`onboarding_sessions` has stages S1–S10, including `S6_DispatchDecide`. The wizard does not consult that stage before spawning. A reader cannot tell "onboarding in progress" from "this config is the one dispatch will use."

### 2. Onboarding discovery is a PATH search for frontier CLIs

`run_workspace_scan` records harnesses with `_detect_harnesses_on_path`. The name list is `claude`, `agy`, `codex`, `grok`, `gemini`, `aider`. Each hit is `shutil.which` plus `--version`. The scan does not call `probe_local_runtimes` or `discover_models`.

`probe_local_runtimes` (`synlynk/models.py`) is a later, separate probe. It asks:

- Ollama at `OLLAMA_HOST` or `127.0.0.1:11434` `/api/tags`
- oMLX at `OMLX_BASE_URL` or `127.0.0.1:8000`, plus weight files under `~/.omlx/models`
- an OpenAI-compatible URL only when `OPENAI_BASE_URL`, `SYNLYNK_LOCAL_AI_URL`, or `VLLM_BASE_URL` is already set

The FTUE test added in #5303 (`tests/test_provider_discovery_matrix.py`) exercises that function with a mocked socket. It does not run during `synlynk init` or `synlynk launch`. The architecture-review template still sets `"agent": "claude"`. A Spark whose only healthy server is NIM, vLLM, llama.cpp, or LiteLLM, and whose `claude` binary is absent or pointed at the wrong profile, gets no local candidate in the task picker.

Weights on disk are not a runner. The oMLX filesystem walk records a model id with no check that a server is up. A DGX box with a model cache and a stopped NIM process would look populated and would not serve.

### 3. One environment variable is not a set of identities

#5298 was a real bug: the Claude child env allowlist was empty, so `ANTHROPIC_BASE_URL` and `CLAUDE_CONFIG_DIR` died at the dispatch boundary. #5303 puts those four names on the allowlist and teaches the auth-path helper to honor `CLAUDE_CONFIG_DIR`. That is one profile, the one already selected in the parent process.

Nothing enumerates sibling directories (`~/.claude`, `~/.claude-*`, extra `CODEX_HOME` trees, a second Grok home). `quota_snapshots` is keyed by `harness` and `window` only (`m0020_quota_snapshots.py`). The federated-quota spec (`docs/superpowers/specs/2026-10-10-federated-quota-capture-design.md`) is also one snapshot per harness. Allocation cannot see that profile A is exhausted and profile B is empty, and it cannot pin a job to B.

Copying tokens from every profile into `state.db` would make this worse. Federation here means a registry of confirmed identities plus a per-job environment, not a merged credential.

`dispatch_first_win_remediation` in `synlynk/launch.py` still prints `job.get("job_id", "unknown")`. That is the #5297 bug on the first-win path, which #5303 did not edit. It is smaller than the three gaps above and should be fixed with the publish-gate change, not as a new design.

## Impact

- The early adopter's uncommitted files left the worktree via stash while a review job ran against a different commit. Restoring them is a manual `git stash` operation he was not told to do.
- The agent he launched did not receive the 50,919-character context or the role block the wizard printed as success.
- `synlynk logs --job unknown` sent him to a command that cannot succeed on the build he was running. On current main the launch screen prints the real id. The first-win dispatcher does not.
- The findings, if the job finishes, land in the job worktree at the template path. The file he opened in the main checkout stays empty of that review. A later memory regenerate from `state.db` can overwrite a hand-written section in the generated file.
- On a sovereign box, onboarding reports the frontier CLIs it found on `PATH` and then offers a Claude task. The local server is invisible unless the operator already exported a base URL and then dispatched the local harness by hand.
- A second subscription or a second gateway profile cannot contribute quota. The operator must export the right directory before every command. A shared machine must not have that choice made by scanning every home directory unattended.

## Why the #5303 guardrails do not cover this

- The job-id change is a print fix. It does not move the write.
- The env allowlist forwards whatever the parent already set. It does not discover other config directories, and it does not record which identity a job used.
- Skipping reconcile on a fresh `init` stops one premature `.synlynk/` creation. `wizard_init` still creates backups, stashes, context, config, and role fences, and it still does that after dispatch.
- The provider-discovery test mocks `probe_local_runtimes`. The wizard never calls it.
- The onboarding stage machine is updated by `cmd_wizard_init` (the zero-config path), not by the interactive `wizard_init` that produced this transcript. Stage S6 is not a lock.

## Approaches

These are the changes #5363 should be implemented from. They are not a license to start coding before a spec for the runner catalog and the identity table is committed. The publish-gate reorder is a defect fix against the current wizard and can be specified briefly inside that same spec.

### A. No live files until publish

Goal: a concurrent reader never observes a half-written workspace, and dispatch cannot start on one.

1. Move `guard_dirty_worktree`, `write_workspace_config`, `generate_structured_context`, and the role-fence writes to **before** `_wiz_screen_launch`. Screen 6 then offers a task only after publish has returned.
2. Stop using `git stash` as the dirty-tree guard. Stash rewrites the caller's index. The tar, if kept, must be opt-in and must not be a precondition of dispatch. Synlynk-owned paths can be copied into the staging directory. The caller's uncommitted product files stay where they are.
3. Write the candidate workspace under `.synlynk/onboarding-staging/<session-id>/`, gitignored. The live names (`.synlynk/workspace.json`, `.synlynk/context.md`, instruction fences) are updated by one publish step: write a temp manifest, rename it into place, then write `.synlynk/onboarding-published` with the session id and a content hash. Readers treat a missing or mismatched marker as "not initialized."
4. `dispatch_agent` and `cmd_launch_ftue` check that marker first and return `onboarding_unpublished` when it is absent. They do not create a worktree in that case.
5. Interactive onboarding uses the same `onboarding_sessions` row the headless path already has. `S6_DispatchDecide` is unreachable until the published marker for that session exists. Abort deletes the staging directory and leaves the previous published generation untouched.
6. Fix `dispatch_first_win_remediation` to read `job.get("id") or job.get("job_id")`, and refuse to run while unpublished.

Acceptance: a test drives `wizard_init` with a dirty tree and a fake `dispatch_agent`. The fake is not called before the published marker exists. `git status` after a skipped launch shows the caller's pre-existing dirty files still dirty. Killing the process during staging leaves the previous published config byte-for-byte unchanged.

### B. Discover sovereign runners during onboarding

Goal: a machine with a healthy local server and no frontier CLI still gets a concrete harness and model list in the task picker.

1. The onboarding scan calls `probe_local_runtimes` in addition to the PATH search. Results go into the staging record from approach A, not into the live catalog, until publish.
2. Add a runner catalog with an explicit health check (`GET /v1/models` or the server's own tags endpoint) and a null check when nothing is listening:

   | Runner | Default probe | Notes |
   |---|---|---|
   | Ollama | `127.0.0.1:11434/api/tags` | already implemented |
   | oMLX | `127.0.0.1:8000/v1/models` | filesystem weights are evidence of a cache, not of a server |
   | vLLM / OpenAI-compatible | `VLLM_BASE_URL` or `:8000/v1/models` | |
   | LiteLLM | `:4000/v1/models` | the DGX gateway case from #5298 |
   | llama.cpp | `:8080/v1/models` | |
   | NIM | OpenAI-compatible port, plus a DGX signal (`nvidia-smi`, `/etc/dgx-release`) | do not assume `~/.omlx` or a macOS home |

3. An operator-declared endpoint file is allowed (`SYNLYNK_LOCAL_AI_URL` and a staging-only list). A URL the operator did not set and that is not loopback is not probed.
4. A healthy runner is a `local` harness candidate with the model ids the server returned. The architecture-review template's pinned `agent: claude` becomes "authenticated home harness, else the healthy local runner." If neither exists, the picker says so and does not dispatch Claude.
5. `synlynk doctor` prints the runner, the endpoint, and the model ids after publish. A refused connection is a named miss, not an empty harness list.

Acceptance: with only a mock LiteLLM on `127.0.0.1:4000` and no `claude` binary, the launch picker offers `local` and names the mock model ids. With the port closed, it offers neither a fake model nor a Claude task.

### C. Federate identities, do not merge tokens

Goal: several confirmed profiles for one harness contribute separate quota, and a job records which profile it ran as.

1. Discovery lists profile roots. Candidates: `~/.claude` and directories the operator names, `CLAUDE_CONFIG_DIR` if set, `~/.codex` and `CODEX_HOME`, the Grok home the quota scraper already tails. Read account labels the CLIs already print (email, plan name). Do not read or copy API keys, `auth.json`, or session tokens into `state.db` or the staging manifest. Store the path and a hash of the path.
2. An identity is ineligible until the operator confirms it on the onboarding screen. A shared DGX must not spend a lab-mate's login because their home directory was readable.
3. Add `identity_id` to `quota_snapshots` (new migration). Capture stays per the existing federated-quota spec, plus the identity. Missing or stale snapshots stay "unknown," never 0% or 100%.
4. Headroom for a harness is the sum of remaining quota across its confirmed identities. Routing picks one identity and sets only that job's environment (`CLAUDE_CONFIG_DIR`, `CODEX_HOME`, or the gateway URL that profile uses). The allowlist from #5303 is how the chosen value reaches the child. Other profiles' variables are not exported.
5. The job row stores `identity_id`. Cost and quota views can group by it. There is no combined API key.

Acceptance: two fixture Claude config directories, one reported full and one reported empty, produce two identities after confirmation. A dispatch selects the empty one, the child environment contains that directory and not the other, and `state.db` contains no secret from either profile.

## Corrective actions he can take now

These do not require a new Synlynk build except where noted.

1. **Do not confirm the wizard's first task.** On the task picker, press `s`. That returns before `dispatch_agent`. The wizard then writes config, context, and roles. Pressing enter on the preview is what cut the worktree.
2. **If he already dispatched,** run `synlynk jobs` in that repo. On a build that contains #5303 the launch line itself prints `job-…`. On the build in the screenshot, `jobs.json` has the real `id` and `synlynk logs --job unknown` will not. Follow the real id.
3. **Recover the stash before assuming files were lost.** `git stash list` should show `synlynk-init-safety-backup-1794483517`. Inspect with `git stash show` and pop only if that diff is the work he wants back. The tar at `.synlynk/backups/init-1794483517.tar.gz` is the other copy. The review job, if it is still running, is based on `origin/main` at `6c169e292b8d` and will not pick up the popped files.
4. **Upgrade to a build that contains #5303,** then start the shell with the one profile he wants:

   - `CLAUDE_CONFIG_DIR` for the LiteLLM profile or the direct Anthropic profile
   - `ANTHROPIC_BASE_URL` and `ANTHROPIC_API_KEY` or `ANTHROPIC_AUTH_TOKEN` when that profile is the gateway

   Synlynk will pass those four through to a Claude child. It will not switch profiles mid-session, and it will not see a second directory he did not export.
5. **Point at the Spark server explicitly** with `OPENAI_BASE_URL` or `SYNLYNK_LOCAL_AI_URL` if he wants `probe_local_runtimes` / a local dispatch to see it. The wizard's architecture-review task still selects Claude. A local-runner job is a separate `synlynk dispatch` to the local harness after publish.
6. **Read the review from the job worktree,** not from the `vi` session on the main checkout. The template path is `.synlynk/project-docs/memory.md` inside that worktree. Expect it only after the job finishes.

## Prevention

- The publish marker is the only signal dispatch trusts. A green "workspace config" line printed after a job id is not success.
- Onboarding tests must use a dirty fixture repo and assert both "no stash" and "no `dispatch_agent` call before the marker." The current FTUE tests check the job-id string and a mocked socket. They do not execute `wizard_init`'s order.
- Runner discovery and identity confirmation are part of the staging record. Publishing an empty harness list when a local server is healthy is a failed onboarding, not a quiet default to Claude.
- Identity rows store paths and quota. A test greps the staging manifest and `state.db` for the fixture token and fails if it appears.

## Resolution status

#5363 is open. #5297, #5298, and #5299 are closed and stay closed. This document is not a closure record. Implementation waits on a spec that covers the publish marker, the runner catalog, and the `identity_id` migration, then a plan. The early-adopter workarounds above are safe to send as-is.
