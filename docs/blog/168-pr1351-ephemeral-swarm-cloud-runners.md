# PR #1351 - Ephemeral Swarm Cloud Runners

Synlynk's swarm engine now has a small, explicit contract for ephemeral
execution. A runner driver provisions isolated compute, streams telemetry,
collects a receipt, and destroys the runner. The local driver makes this
contract testable on a laptop; the Fly.io driver maps it to Machines v2 and
starts a watchdog for every machine.

The manager keeps lifecycle records in SQLite, so `synlynk swarm status` is
useful even after a CLI process exits. `synlynk swarm dispatch` fans out a
batch, while `synlynk swarm destroy --all` is the emergency cleanup command.
Progress is emitted as `runner_progress` relay events, giving the existing
watch and relay surfaces a common stream without coupling them to a provider.

This is intentionally a foundation: Kubernetes and Hetzner drivers can be
added without changing the CLI or the master-side lifecycle ledger.
