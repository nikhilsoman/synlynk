# Daemon lifecycle recovery (#1523)

The daemon lock file is a durable diagnostic artifact, while the advisory
`flock` is the source of truth for ownership.  The lock now records its owner
PID after acquisition.  A start attempt preserves a lock held by a live
process (and by a live daemon), but retries when the recorded owner is dead;
this makes service restarts recover from stale lifecycle metadata without
weakening mutual exclusion.

Daemon re-exec and installed services also retain the originating absolute
workspace as their working directory.  GitHub App configuration and token
cache paths therefore resolve against the same repository even when launchd,
systemd, cron, or a detached child supplies a different default cwd.
