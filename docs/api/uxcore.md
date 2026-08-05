# uxcore — Synlynk's shared UX library

`synlynk.uxcore` is the shared data/write/RBAC layer behind Synlynk's TUI and
Vizor web HUD. It is a stable, documented Python library contract — import it
directly from the same process/venv as your synlynk install. There is no
network/HTTP API for out-of-process consumers in 1.0.

## Reads

- `get_fleet_state() -> dict[str, AgentBucket]`
- `get_jobs() -> list[JobRun]`
- `get_costs() -> Costs`
- `get_gantt_data() -> list[Dream]`

All reads return frozen dataclasses, never raw dicts. They raise `UxCoreError`
on I/O/DB failure — never a bare exception from `sqlite3`/`json`.

## Writes

- `dispatch(agent: str, task: str, actor: Actor | None = None, **flags) -> WriteResult`
- `approve_pr(pr_number: int, actor: Actor | None = None) -> WriteResult`
- `kill_job(job_id: str, actor: Actor | None = None) -> WriteResult`

`WriteResult(ok: bool, message: str, job_id: str | None)`. A permission denial
and a runtime failure have the same shape (`ok=False`) — check `message` for
which happened. Every write appends a structured event to `.synlynk/events.jsonl`.

## Actor and capabilities

```python
from synlynk import uxcore

actor = uxcore.DEFAULT_ACTOR  # LocalActor, role=Role.OWNER, in 1.0
caps = uxcore.list_capabilities(actor)
# [Capability(name='approve_pr', enabled=True), Capability(name='dispatch', enabled=True), ...]
```

Render/hide UI elements from `list_capabilities()` rather than hardcoding your
own permission checks — this is the same manifest both the TUI and Vizor use.

## Feature flags

`FeatureFlags.is_enabled(flag: str, tier: str) -> bool` reads a static
`features` block from `.synlynk/config.json`. Orthogonal to RBAC: flags gate
whether a deployment tier has a feature at all, RBAC gates whether a specific
actor can use it.

## Subscribing to events

```python
for event in uxcore.subscribe(event_types=["dispatch_complete", "pr_approved", "job_failed"]):
    print(event.action, event.result)
```

`subscribe()` reads all matching events currently in `.synlynk/events.jsonl`.
It is a one-shot read, not a live tail — poll it on an interval if you want
near-live updates (see `synlynk/notifiers/slack.py` for a reference consumer).

## Writing your own BYOUX consumer

A BYOUX ("bring your own UX") consumer is any script that imports
`synlynk.uxcore` and builds its own presentation on top — a custom dashboard,
a terminal-multiplexer pane layout, a notifier. `synlynk/notifiers/slack.py`
is the reference implementation: read `uxcore.subscribe()`, format for your
target surface, done. Nothing in `uxcore` assumes who's calling it beyond the
`Actor` you pass in.
