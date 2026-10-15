# Personal-Use Hosted Relay — Design Spec

**Status:** Draft, pending user review
**Issue:** gh:#2201 (distinct scope from gh:#1402, enterprise sync research)
**Date:** 2026-10-12

## Summary

Design a hosted-relay capability for Personal edition: a single user running multiple
devices (desktop, laptop, VPS) who wants (a) remote access to their synlynk workspace
when away from their primary machine, and (b) live awareness across devices of job
claims, state changes, and agent activity, without risking duplicated work when a
device was offline.

This explicitly extends to Team edition (hub as multi-collaborator sync) and
Enterprise edition (hub as a leadership observability/governance aggregation surface)
later — the Personal-edition design must not foreclose either, and should ideally be
the first real build of the architecture both tiers already assume.

## Non-Goals (explicitly out of scope for this spec)

- **Full multi-writer state.db reconciliation** (CRDTs, conflict-free merge of
  divergent local databases) — this is gh:#1402's research scope. This spec solves
  the narrower, more common problem (replay of missed events on reconnect) without
  requiring database-level merge.
- **Billing/entitlement implementation** — the spec notes where gating *hooks* go
  (account JWT claims checked by the managed hub), but implementing billing itself is
  separate work.
- **Team/Enterprise-specific features** (cross-workspace aggregation, per-person
  identity beyond "device" scoping) — the subject hierarchy and credential model are
  designed so these layer in additively later, but this spec covers Personal only.
- **File-sync/merge system for docs** — the doc-preview channel (below) is
  notification + best-effort preview only, never authoritative; git + GitHub remain
  the source of truth for anything requiring review or persistence.

## Architecture

Three logical pieces:

1. **Local broker (unchanged)** — today's `synlynk/relay.py` `RelayBroker`/
   `RelayServer`, running on `127.0.0.1:7432`. Intra-machine pub/sub, JSON-RPC
   commands, local `relay_events`/`relay_mailbox` persistence in the workspace
   `state.db`. Zero changes for users who never opt into a hub — this stays the free,
   always-available default, and the existing local P2P mesh peering
   (`relay peer add/list`) is untouched.

2. **Hub (new, opt-in)** — a NATS server: self-run (`synlynk relay hub init` wraps
   `nats-server` with Personal-edition defaults, ships as a Docker image / standalone
   binary) or managed at synlynk.com (`synlynk relay hub connect <workspace-token>`).
   This is the paid/optional add-on referenced in gh:#2201 — self-hosting it is free;
   a managed instance is the monetizable convenience. Subjects are scoped per
   workspace under `synlynk.<workspace_id>.*` so Team (more human members) and
   Enterprise (cross-workspace aggregation subjects) extend the same namespace
   without a redesign.

3. **Hub adapter (new, per device)** — a lightweight process alongside the local
   broker on each device. Holds that device's NATS credential, **dials outbound to
   the hub only** (never accepts inbound connections — avoids NAT traversal /
   port-forwarding entirely, which matters for laptops and home VPS instances without
   stable public IPs). Bridges local broker events onto the device's hub subjects and
   injects hub messages addressed to this device/workspace back into the local
   broker's subscriber queue. Existing local JSON-RPC methods remain the single API
   surface callers use — the adapter is invisible to anything already talking to the
   local broker.

A device with no hub adapter running behaves exactly as it does today — the hub is
purely additive.

## Topology Choice

Both hub-and-spoke (hub as central broker all devices connect to) and the existing
P2P mesh are supported; the hub is the opt-in paid add-on layered on top, not a
replacement for the mesh. Which a user runs is an environment-dependent setting, not
a forced choice.

## Subject Taxonomy

```
synlynk.<workspace_id>.job.<event_type>        # claims, status changes, completions
synlynk.<workspace_id>.agent.<harness>.<role>   # live per-agent activity/progress
synlynk.<workspace_id>.sentinel.<pattern>       # FLATLINE / SUCCESS_LOOP / QUOTA_EXHAUSTED-style alerts
synlynk.<workspace_id>.device.<device_id>       # direct device-targeted messages (steering, DMs)
synlynk.<workspace_id>.doc.<drafted|updated>    # doc/artifact preview notifications (see below)
synlynk.<workspace_id>.custom.<topic>           # user-defined, zero relay code changes to add one
```

Rationale for splitting by category rather than one firehose subject:

- **Independent retention budgets per category.** `job.*` and `sentinel.*` are
  low-frequency, high-value — generous retention. `agent.*` activity chatter is
  high-frequency and mostly only useful live — a smaller/shorter-retention stream so
  it can't crowd out events that matter. `custom.*` gets a sane configurable default
  per topic since volume is unknown ahead of time.
- **Wildcard subscriptions come free from NATS** subject matching
  (`synlynk.<ws>.job.>`, `synlynk.<ws>.sentinel.>`, etc.) — no custom filtering code.
- **User-controlled subscription settings per device**: `synlynk relay subscribe
  <pattern>` / `unsubscribe`, backed by `.synlynk/relay-subscriptions.json`, lets a
  device tune what actually bridges into its local broker (e.g. a thin client
  subscribes to `job.>` + `sentinel.>` only; the main desktop subscribes to
  everything including `agent.>`). Default posture: every device subscribes to
  everything (opt-out), since Personal edition is single-user and the volume
  concern is addressed by per-category retention, not per-device filtering.
- **Custom topics are a reserved namespace, not a feature to build** — any script or
  future integration picks a `custom.<topic>` string and publishes/subscribes with
  no relay-side schema change.

Existing RPC methods remap onto this hierarchy via a routing-layer addition (method →
subject), with no breaking change to method names:

| RPC method | Subject |
|---|---|
| `relay.send_message` / `broadcast` | `job.*` or `custom.*` depending on caller intent |
| `relay.inject_steering` | `device.<id>.steering` |
| `relay.request_review` | `job.review_requested` |
| `relay.runner_progress` | `agent.<harness>.progress` |

## Credentials & Device Registration

- Each device's hub adapter holds a NATS **nkey keypair + JWT**, scoped to that
  device's own subjects plus the shared workspace subjects — never account-wide
  access. This is what makes revocation per-device.
- **Bootstrap:** `synlynk relay hub init` (self-hosted) or `synlynk relay hub connect
  <workspace-token>` (managed) establishes the workspace's trust-root account key —
  the key that signs device JWTs.
- **Adding a device:** `synlynk relay device add <name>`, run from an
  already-trusted device (or the hub admin, for first bootstrap), mints a new nkey +
  JWT and writes the credential file locally (e.g. `~/.synlynk/relay/<device_id>.
  creds`). Self-hosted: updates the local `nats-server` resolver config. Managed: API
  call to synlynk.com.
- **Revoking a device:** `synlynk relay device revoke <device_id>` pushes that
  device's nkey onto the hub's deny list. Effective immediately; no other device's
  credential is touched.
- This credential shape (device JWT under a workspace account) is what Team edition
  extends: a "person" credential is the same JWT shape with a different subject
  scope, added under the same workspace account — not a new credential system.

## Durability & Replay

Live-event-only was the initial framing, but was revised after review: losing events
while offline creates real risk of duplicate work claims across devices. NATS
**JetStream** provides durable, replayable per-subject streams, which solves this
without requiring full state.db reconciliation (that remains `(B)`/#1402 scope):

- Each workspace gets a JetStream stream per subject category (not one shared
  counter), each with its own retention budget:
  - `job.*`, `sentinel.*`: generous retention — default **cap at 50,000 events OR 1
    year, whichever is hit first** (configurable in hub config / managed-tier
    settings).
  - `agent.*`: much smaller/shorter default (e.g. last 2,000 events or 48h) — live
    activity chatter, not meant to be a durable record.
  - `custom.*`: sane configurable default per topic.
- On adapter connect/reconnect: a **durable consumer** tracks "last delivered
  sequence number" per device, so reconnecting resumes exactly where that device
  left off. Idempotency on replay is already available via `event_id` +
  `INSERT OR IGNORE` in the existing local broker's persistence.
- **Conflict resolution is explicitly not the relay's job.** Replaying "device X
  claimed story-Y at 14:02" before another device starts work lets *existing*
  job-claim logic refuse/warn on a second claim. The relay's only responsibility is
  guaranteeing that claim event isn't lost — not merging divergent state.
- If offline longer than the retention window, the gap is **detected and surfaced
  explicitly** ("sync gap — events older than retention were missed"), not silently
  resumed as if nothing was missed.

## Doc/Artifact Preview Channel

Specs and plans live in a device-local worktree before they're committed/pushed,
which is invisible to other devices/collaborators. Rather than build a second
file-sync system (risking an unscoped re-opening of the state-reconciliation
problem), this is handled as a narrow, explicitly-non-authoritative preview channel:

- `doc.drafted` / `doc.updated` fires when a tracked path changes locally, scoped to
  `docs/superpowers/specs/**`, `docs/superpowers/plans/**`, `docs/brainstorm/**` (the
  paths the brainstorming/writing-plans skills already write to).
- Payload: path, branch, local commit SHA if committed, and — only for files under a
  size threshold (specs/plans are small markdown, well under NATS's ~1MB default
  message cap) — the raw file content, delivered best-effort.
- Receiving devices get a **read-only preview copy** (e.g. written to
  `.synlynk/relay/previews/<device_id>/<path>`), clearly labeled as a preview, not
  merged into the receiving device's own worktree. No conflict resolution.
- Anything needing actual multi-person review or sign-off uses the existing,
  better-suited mechanism: push a draft branch and open a draft PR or attach to a
  tracking GitHub issue. A pushed `doc.drafted` event can *link* to that (branch/
  issue URL) rather than trying to carry review-quality delivery over the relay.

## Deployment & Feature Gating

- **Self-hosted:** `synlynk relay hub init` wraps `nats-server` with Personal-edition
  defaults, shipped as a Docker image / standalone binary. No account, no billing, no
  gating — everything described above, for free, forever.
- **Managed (synlynk.com):** `synlynk relay hub connect <workspace-token>`. Gating
  lives at the hub level, not the wire protocol — the managed hub additionally
  enforces entitlements (device count limits, future Team/Enterprise-only subjects)
  by checking the account JWT's claims before accepting a connection. The adapter and
  hub protocol are otherwise identical between self-hosted and managed, so Team/
  Enterprise features are additive policy on the same substrate, not a fork.

## Error Handling

1. **Adapter can't reach hub** (network down, hub unreachable): local broker
   continues unaffected; adapter retries with backoff; emits a local
   `relay.hub_disconnected` event so Vizor/CLI can surface "not synced" status.
2. **Hub rejects credential** (revoked/expired): adapter fails closed, same
   local-degraded-mode behavior, with a clear CLI error (`synlynk relay status`
   shows "credential revoked", not a generic timeout).
3. **Replay gap exceeds retention**: adapter detects its last-seen sequence predates
   the stream's earliest retained message and surfaces an explicit sync-gap marker
   rather than silently resuming.

## Testing

- Unit tests for the adapter's bridge logic (local↔hub translation) using a fake
  NATS client.
- Integration test spinning up a real embedded `nats-server` plus two local brokers
  to verify end-to-end replay-on-reconnect and device revocation.
- No live synlynk.com managed-hub testing in this spec's scope — that's
  infra/deployment, not relay-protocol correctness.

## Forward Compatibility (Team / Enterprise)

- **Team:** more identities (people, not just devices) under the same workspace
  account, same JWT shape, same subject hierarchy — no redesign.
- **Enterprise:** cross-workspace aggregation subjects under a higher-level
  namespace, consumed by an org-level Vizor view (per the existing
  `vizor-strategic-position` memory's NATS-gate direction) — this spec's choice of
  NATS as the hub transport is what makes that extension possible without a
  migration.
- **`(B)` state reconciliation:** if/when gh:#1402's research lands, it plugs in
  as an additional durable-stream consumer pattern on the same subjects — the
  subject hierarchy and JetStream durability designed here are the intended
  extension point, not something to re-architect around later.
