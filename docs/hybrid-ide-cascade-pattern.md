# Hybrid Pattern: synlynk Protocols + Native IDE Cascades

**Status:** Supported  
**Applicable to:** Agents running inside IDE environments with native cascade tools (Antigravity/Gemini, Cursor, Copilot Chat, etc.)  
**First documented:** 2026-06-27 — based on Agy session on rxcc project

---

## Problem

synlynk's `dispatch` command launches agent CLIs as shell subprocesses. In sandboxed IDE environments, running arbitrary shell commands requires explicit user permission prompts, and IDE-native cascade tools (e.g. `invoke_subagent` in Antigravity) offer pre-authorized execution that avoids this friction.

The question agents asked: _"Can I use native cascades for execution while still maintaining synlynk protocols?"_

The answer is: **yes, explicitly supported.**

---

## The Pattern

Use synlynk for **state and context tracking**. Use native IDE cascades for **execution**.

```
┌─────────────────────────────────────────────────────────┐
│  synlynk handles:            IDE cascade handles:        │
│  • .synlynk/context.md       • Spawning the subagent     │
│  • .synlynk/jobs.json        • Tool use permissions       │
│  • .synlynk/logs/<job>.log   • Sandbox isolation          │
│  • .synlynk/telemetry.json   • Real-time streaming        │
│  • project-docs/ state       • Multi-file edits           │
└─────────────────────────────────────────────────────────┘
```

---

## How Agents Should Apply This

### 1. Before dispatching — write the job entry manually

When using `invoke_subagent` (or equivalent) instead of `synlynk dispatch`, manually register the job so `synlynk jobs` and `synlynk status` stay accurate:

```python
# Pseudocode — adapt to your IDE's file write tool
job_id = "job-" + sha256(task + timestamp)[:8]

# Write prompt
write(".synlynk/prompts/{job_id}.md", task_prompt)

# Register in jobs.json
jobs = read_json(".synlynk/jobs.json")
jobs.append({
    "id": job_id,
    "agent": "codex",
    "story_id": story_id,
    "task": task_summary,
    "status": "running",
    "started_at": now_iso(),
    "pid": None,           # no OS PID for cascade subagents
    "log_file": f".synlynk/logs/{job_id}.log"
})
write_json(".synlynk/jobs.json", jobs)
```

### 2. During execution — stream output to the log file

As the cascaded subagent produces output, append it to the log file:

```
.synlynk/logs/<job_id>.log
```

This lets `synlynk logs --job <job_id>` work normally and keeps the telemetry pipeline intact.

### 3. After completion — close the job entry

```python
# Update jobs.json with final status
job["status"] = "done"          # or "failed"
job["exit_code"] = 0
job["ended_at"] = now_iso()
write_json(".synlynk/jobs.json", jobs)

# Write exit sentinel (matches native dispatch convention)
write(f".synlynk/logs/{job_id}.log.exit", "0")
```

### 4. Context still flows through synlynk

Before launching the cascade, call:
```bash
synlynk context generate   # or let synlynk exec do it
```

This ensures `.synlynk/context.md` is fresh and the subagent gets the same context it would receive from a native `synlynk dispatch`.

---

## What Still Goes Through synlynk CLI

Even in hybrid mode, these synlynk CLI commands should run directly — they don't hit shell permission friction because they're non-destructive reads:

| Command | Purpose |
|---|---|
| `synlynk status` | Agent + project health snapshot |
| `synlynk jobs` | Job queue visibility |
| `synlynk logs --job <id>` | Tail log for any job |
| `synlynk context generate` | Refresh `.synlynk/context.md` |
| `synlynk score` | Capability scoring |
| `synlynk doctor` | Onboarding health check |

For write operations (`synlynk dispatch`, `synlynk exec`) — use the native cascade path + manual job registration described above.

---

## What synlynk Doesn't Mind

- Jobs registered without OS PIDs (`"pid": null`)
- Log files written by cascade tools instead of shell redirects
- Gaps in telemetry if a session was short
- Mixing native dispatch (for capable environments) and cascade dispatch (for sandboxed ones) across agents in the same workgroup

synlynk reads state from files, not from process monitoring. As long as the files are written correctly, all reporting commands (`synlynk jobs`, `synlynk status`, `synlynk logs`) work identically.

---

## Precedent

This pattern was first identified in a Gemini/Agy session on the rxcc project (2026-06-27), where Agy:

1. Noted it had used `invoke_subagent` instead of `synlynk dispatch` 
2. Manually wrote job state, prompt, and log files into `.synlynk/`
3. Verified `synlynk jobs` and `synlynk status` reflected the completed work
4. Formally acknowledged synlynk protocols and committed to the hybrid approach going forward

Agy's assessment of the pros/cons is in `docs/synlynk-gemini-human-agent-hybrid-workgroup-study.md`.

---

## Future Work

- `synlynk jobs register` CLI command — let agents register a cascade job from one line rather than manually editing `jobs.json`
- `synlynk jobs complete <id> --exit-code 0` — close a job from the CLI
- Telemetry bridge hook — IDE extensions could call these after each cascade completion automatically
