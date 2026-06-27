# BS-8: Harness Capability Awareness + Loop-Native Dispatch
## Design Spec

**Date:** 2026-06-27  
**Session:** BS-8 (Nikhil + Claude)  
**Status:** Approved — ready for implementation planning  
**Target:** v0.10.1 (post dev-preview code freeze)

---

## Problem Statement

synlynk wraps AI harnesses (Claude, Codex, Agy, Grok) that ship new primitives every few weeks — new flags, slash commands (`/goal`, `/loop`), hook events, model versions, pricing. Currently synlynk has no mechanism to detect these changes, and dispatch/exec is single-shot with no loop controller, no objective injection, and no recovery path when an agent gets stuck.

Two subsystems address this:

1. **`synlynk probe`** — ambient capability drift detection with autonomous analysis + publishing pipeline
2. **Loop-native dispatch** — synlynk as loop controller with composite termination, `/goal`-equivalent objective injection, and stuck-triggered consult from the capability matrix

---

## Architecture

```
synlynk probe                         Loop-Native Dispatch
─────────────────────────────         ──────────────────────────────────────────
Run agent help/status/version         dispatch_agent() × N turns
         │                                       │
   Hash output, diff                    evaluate termination predicate
   against last snapshot                (exit code + done_criteria + verify_cmd)
         │                                       │
    Changed?                             not done + iterations < max?
         │                                       │
         ├─ Update .agents/<n>_probe.json         ├─ stuck? (exit repeat OR log pattern)
         ├─ Commit docs/harness-updates/ md       │     │
         ├─ Open GitHub issue (harness-cap)       │     └─ dispatch one-shot consult
         └─ Dispatch analysis agent               │          (best alt agent from cap matrix)
              write implications + usage          │          inject ## Expert Consult into
              methods into markdown, open PR      │          next turn context
                                                  └─ re-dispatch with enriched context
                                                       ## Dispatch Objective (goal)
                                                       ## Previous Turn Summary
                                                       ## Expert Consult (if triggered)
```

The two subsystems are **independent** — probe doesn't require loop-native and vice versa. They ship together as a coherent "synlynk stays current and runs longer" story.

---

## Subsystem 1: `synlynk probe`

### Probe Data Model

Each agent gets a snapshot file at `.agents/<name>_probe.json`:

```json
{
  "agent": "claude",
  "last_probed": "2026-06-27T10:00:00Z",
  "probe_hash": "sha256:abc123...",
  "raw_output": "...",
  "capabilities": {
    "flags": ["--print", "--output-format", "--dangerously-skip-permissions"],
    "slash_commands": ["/goal", "/loop", "/status", "/compact", "/clear"],
    "hook_events": ["PreToolUse", "PostToolUse", "Stop", "Notification"],
    "output_formats": ["text", "json", "stream-json"],
    "models": ["claude-opus-4-8", "claude-sonnet-4-6", "claude-haiku-4-5"]
  }
}
```

### Probe Commands Per Agent

| Agent | Probe commands |
|---|---|
| claude | `claude --help`, `claude /status` |
| codex | `codex --help`, `codex --version` |
| agy | `agy --help`, `agy --version` |
| grok | `grok --help`, `grok -v` |

All probe commands run with a 10s timeout. Failures are recorded as `"probe_error": "<message>"` — they do not abort the probe run for other agents.

### On-Change Pipeline

When the hash differs from the last snapshot:

1. **Update** `.agents/<name>_probe.json` with new snapshot + timestamp
2. **Commit** `docs/harness-updates/YYYY-MM-DD-<agent>-<slug>.md` with:
   - Raw diff (added/removed lines)
   - New capabilities detected
   - Placeholder sections for: Implications, Methods of Use, synlynk Integration Notes
3. **Open GitHub issue** tagged `harness-capability` with the diff summary and a link to the markdown file
4. **Dispatch analysis agent** — highest-scoring agent for `engg_domain=tooling` from capability matrix. The agent's task:
   - Fill Implications, Methods of Use, synlynk Integration Notes sections in the markdown
   - Propose whether any new flag/command should be adopted into `AGENT_CAPABILITY_BASELINES`
   - Open a PR with the completed analysis

Auto-adoption of capabilities into `AGENT_CAPABILITY_BASELINES` is **never automatic** — the analysis agent proposes, a human merges the PR. Breaking changes (removed flags, renamed commands) are flagged explicitly in the issue body.

### CLI

```bash
synlynk probe                  # probe all registered agents
synlynk probe claude           # probe one agent
synlynk probe --dry-run        # show diff, no commit / issue / dispatch
```

### Daemon Integration

`_probe_all_agents()` is added to the daemon's daily reconcile pass. Runs silently when no changes are detected. On any diff: fires the full pipeline (commit → issue → dispatch). No user action required.

### Doctor Integration

`_hc_probe_freshness()` added to `HEALTH_CHECKS`:
- **ok** — all agents probed within 7 days
- **warn** — any agent not probed in >7 days, or `.agents/<name>_probe.json` missing
- **fix** → `synlynk probe`

---

## Subsystem 2: Loop-Native Dispatch

### Loop Controller

New function `dispatch_loop(agent, story_id, max_iterations=5, verify_cmd=None)` wraps `dispatch_agent` in a controlled turn cycle:

```python
previous_job = None
for iteration in range(1, max_iterations + 1):
    context = _build_loop_context(story_id, iteration, max_iterations,
                                   previous_job, expert_advice)
    job = dispatch_agent(agent, task, story_id, loop_context=context,
                         loop_iteration=iteration, loop_root_job_id=root_job_id)
    wait_for_job(job)

    # Composite termination predicate
    exit_ok     = job["exit_code"] == 0
    criteria_ok = _eval_done_criteria(story_id, job["log"])
    verify_ok   = _run_verify_cmd(verify_cmd) if verify_cmd else True

    if exit_ok and criteria_ok and verify_ok:
        _mark_loop_done(root_job_id, reason="done", iteration=iteration)
        return job

    # Stuck detection — either signal triggers consult
    expert_advice = None
    if _is_stuck(job, previous_job):
        consult_agent = _best_agent_for_story(story_id, exclude=agent)
        if consult_agent:
            expert_advice = _run_consult(consult_agent, story_id, job)

    previous_job = job

_mark_loop_done(root_job_id, reason="max_iterations", iteration=max_iterations)
```

### Composite Termination Predicate

All three must pass for the loop to exit as done:

| Signal | Passes when |
|---|---|
| Exit code | `job["exit_code"] == 0` |
| Done criteria | `done_criteria` field on story matches patterns in job log (regex + keyword scan). LLM fallback: only if `verify_cmd` is provided AND fails — synlynk asks the working agent "did you complete `<done_criteria>`? answer yes/no" as a one-shot prompt. No LLM call if `verify_cmd` passes or no `verify_cmd` set. |
| Verify command | Optional shell command exits 0 (e.g. `pytest tests/ -q`, `gh pr list --head ...`) |

### Dispatch Objective Injection (`/goal` equivalent)

Every turn's context includes a `## Dispatch Objective` block — explicit, persistent goal framing equivalent to what `/goal` provides in interactive sessions:

```markdown
## Dispatch Objective
**Goal:** <story title>
**Done criteria:** <done_criteria from story>
**Iteration:** 2 of 5
**Status:** Previous turn did not meet done criteria. Continue.

## Previous Turn Summary
<last 50 lines of previous job log>

## Expert Consult
<consult agent response — only present if triggered this turn>
```

### Stuck Detection

Either signal triggers a consult before the next turn:

**Signal A — Exit code repeat:** Same non-zero exit code on 2 consecutive turns  
**Signal B — Log pattern repeat:** Same error string or exception class appearing in logs of 2 consecutive turns (scanned via existing sentinel pattern infrastructure)

Consult is **one per iteration** and **non-recursive** — the consult job always runs as `one_shot=True` and cannot itself trigger a consult.

### Consult Mechanism

```python
def _run_consult(consult_agent, story_id, stuck_job):
    prompt = (
        f"Agent is stuck on story '{story_id}' after {stuck_job['loop_iteration']} turns.\n"
        f"Last exit code: {stuck_job['exit_code']}\n"
        f"Last error pattern:\n{_extract_stuck_pattern(stuck_job['log'])}\n\n"
        "Identify the root cause and give one concrete next step the agent should take."
    )
    consult_job = dispatch_agent(consult_agent, prompt, one_shot=True)
    wait_for_job(consult_job)
    return read_log(consult_job)
```

Consult agent selection: `_best_agent_for_story(story_id, exclude=current_agent)` — highest capability scorer for the story's domain coordinate, excluding the agent currently working the task (different perspective is the point).

### Forward Compatibility: Consult as an Advisory Protocol

**Design constraint for v1.0+ team/enterprise mode:**

Consult is not AI-to-AI only. The consult target is any advisory participant — AI agent, specific model, or human team member. The same mechanism that today dispatches Claude to advise Codex will, in team mode, be able to dispatch a consult to a human via `synlynk notify` or a human-in-the-loop approval step.

The consult interface is:
- **Trigger:** any agent (human or AI) running in a loop
- **Advisor:** any registered participant (AI agent, named human, role)
- **Response:** text that gets injected into the `## Expert Consult` block

In v1.0+, `synlynk consult <participant> <story_id>` becomes a standalone command. Advisors can be addressed by role (`role:architect`), by agent name (`claude`), or by GitHub username (`@nikhilsoman`).

### Job Chain Tracking

New fields on every loop job stored in jobs.json:

| Field | Description |
|---|---|
| `loop_iteration` | Which turn this is (1-based) |
| `loop_root_job_id` | First job in the chain (same across all turns) |
| `loop_terminate_reason` | `"done"` \| `"max_iterations"` \| `"error_abort"` |
| `consult_job_id` | Job ID of the consult job if triggered this turn, else `""` |
| `one_shot` | `true` for consult jobs — marks them as non-loopable |

### CLI

```bash
# Loop dispatch
synlynk dispatch claude story-abc123 --loop
synlynk dispatch claude story-abc123 --loop --max-iterations 8
synlynk dispatch claude story-abc123 --loop --verify-cmd "pytest tests/ -q"

# View loop chain
synlynk jobs --loop              # shows root + all turns + consult jobs per chain
```

---

## What This Does NOT Build (YAGNI)

- **Auto-patching `AGENT_CAPABILITY_BASELINES`** in code from probe — analysis agent proposes, human merges
- **Recursive consult** — consult is always one-shot, never triggers another consult
- **LLM-only done_criteria eval** — exit code + regex first; LLM is fallback only when verify_cmd also fails
- **Parallel fan-out dispatch** — independent story parallelism is a separate epic
- **Human consult delivery** (email/Slack) — v1.0+ once team mode ships

---

## Testing Approach

| Test | How |
|---|---|
| Probe diff detected | Mock `--help` output change; assert hash mismatch triggers commit + issue + dispatch |
| Probe no change | Same output twice; assert no side effects |
| `--dry-run` | Diff printed; nothing written, no issue opened |
| Doctor probe_freshness warn | Set `last_probed` >7 days ago; assert warn |
| Loop exits on first success | Mock exit 0 + passing verify_cmd; assert stops at iteration 1 |
| Loop re-dispatches on failure | Mock exit 1; assert iteration 2 dispatched with objective block |
| Stuck detection — exit code | Same non-zero exit × 2; assert consult dispatched |
| Stuck detection — log pattern | Same error string × 2; assert consult dispatched |
| Consult non-recursive | Consult job has `one_shot=True`; assert it never triggers another consult |
| Consult injected into context | Assert `## Expert Consult` present in next turn's prompt file |
| Max iterations cap | Loop exits with `"max_iterations"` reason after N turns |
| Job chain fields consistent | `loop_root_job_id` same across all turns in a chain |
| Verify cmd failure keeps loop going | verify_cmd exits 1; assert re-dispatch even if exit_code is 0 |

---

## Release Slot

**v0.10.1** — immediately after v0.10.0 dev preview ships. `synlynk probe` is the most immediately useful (catches harness drift before it breaks dispatches). Loop-native dispatch follows as v0.10.1's headline feature.

Stories to create in state.db:
- `story-bs8-probe` — `synlynk probe` + probe data model + daemon integration + doctor check
- `story-bs8-loop` — `dispatch_loop()` + objective injection + job chain tracking
- `story-bs8-consult` — stuck detection + `_run_consult()` + `## Expert Consult` injection
