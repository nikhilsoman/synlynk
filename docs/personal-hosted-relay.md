# Personal hosted relay

The optional hub bridges local relay events through a self-hosted NATS server.
The ordinary `synlynk relay start` command remains local-only. Install the
`synlynk[hub]` extra on each participating device and install `nats-server` on
the hub host. The core CLI does not require either dependency.

## Set up the hub

```sh
synlynk relay hub init --workspace-id personal --config-dir ~/.synlynk/relay
synlynk relay device add desktop --workspace-id personal --config-dir ~/.synlynk/relay
synlynk relay device add laptop --workspace-id personal --config-dir ~/.synlynk/relay
nats-server -c ~/.synlynk/relay/nats.conf
```

Initialization defaults to loopback. For remote access, configure `--listen`
and `--url` for your private network, or use an authenticated tunnel to the
loopback listener. The generated configuration uses bearer secrets as native
NATS user/password credentials and does not configure TLS automatically.
Use TLS or a private tunnel when carrying credentials over an untrusted network.

Keep `devices.json` on the administrator host: it contains all device secrets.
Copy only the intended device's printed `.creds` file through a secure channel
to that device and keep it mode 0600. From the device's workspace, run:

```sh
synlynk relay start --hub --credential-file /path/to/laptop.creds \
  --workspace-id personal --hub-url nats://127.0.0.1:4222
```

Use the reachable private or tunneled hub URL in place of the example URL.
On the administrator host, `--device-id <minted-id> --config-dir <directory>`
can be used instead of `--credential-file` and `--workspace-id`.
Hub bridging currently runs in the foreground; `--hub --daemon` is rejected.

## Subscriptions and revocation

```sh
synlynk relay subscribe 'job.>'
synlynk relay subscribe 'sentinel.>'
synlynk relay unsubscribe 'job.>'
synlynk relay device revoke <device-id> --workspace-id personal
nats-server --signal reload=<server-pid>
```

Subscription settings belong to the current workspace. A missing settings file
means all subjects; an empty list means none. Restart the bridge after changing
subscriptions. Excluded events are acknowledged and skipped, so adding a filter
later does not restore previously skipped events.

Adding or revoking a device regenerates authorization configuration. Reload the
running NATS server to apply it. A local revocation message alone does not prove
that live server access has ended.

## Local verification

Local integration coverage uses isolated device processes and databases, exported
device credentials, and a real authenticated JetStream server. Install
`nats-server` (for example, `brew install nats-server`) and put it on `PATH`, then
run from an environment with the `synlynk[hub]` extra and pytest installed:

```sh
python -m pytest tests/test_relay_hub_integration.py tests/test_relay_hub.py \
  tests/test_relay_hub_onboarding.py tests/test_relay.py tests/test_relay_p2p.py \
  tests/test_governs_relay_events.py -v
```

The integration module skips when either optional dependency is absent. It
checks cross-device delivery, durable replay after device restart, persistent
deduplication, independent category cursors, retention gaps, subscription filters,
and credential rejection after a real server configuration reload. All servers
bind loopback on dynamic ports; no managed hub is contacted.

## Current limits

JetStream retains independent category streams and resumes durable device cursors.
Retention gaps emit a local `sync_gap_detected` event. Replayed events are
deduplicated against local persistence. This does not reconcile independent
workspace databases or merge files. The adapter has no application-level
outbound retry queue; reconnect/backoff and hub-aware status remain follow-up work.

`relay hub connect` stores private managed-service settings only. This release
does not provision or connect a managed service and does not implement billing
or entitlement enforcement.
