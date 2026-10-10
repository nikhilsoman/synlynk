# CLI Surface Baseline Metrics

Captured: 2026-10-04T10:32:26Z (UTC)

This is the pre-UX-change baseline for gh:#1973 and the phase-1 gate in
`docs/strategy/2026-10-02-decide-panel-roadmap.md`.

## Dispatch flags

- Rolling telemetry source: `/Users/nikhilsoman/dev/synlynk/.synlynk/telemetry.json`
- Dispatch events observed: 42
- Events with explicit caller-flag telemetry: 0
- Legacy events without explicit caller-flag telemetry: 42
- Median explicit flags per dispatch: **Unavailable**

The legacy `dispatch` event shape records agent, job, story, context mode, and
context bytes, but not the flags entered by the caller. This report leaves the
median unavailable instead of treating missing data as zero. New CLI dispatches
now emit `dispatch_invocation` rows with `explicit_flags` and
`explicit_flag_count`; rerun the capture script after those rows accumulate to
replace this provisional value with a measured median.

## Dogfood onboarding run

| Started (UTC) | Init | Dispatch | Verified dispatch | Duration |
|---|---:|---:|---:|---:|
| 2026-10-04T10:32:26Z | 1 | not run | no | 1.859s |

The isolated clean-install simulation stopped during `init`, before dispatch,
so it is recorded as an unsuccessful onboarding attempt rather than claimed as
time to first verified dispatch. The runner is available for a real dogfood
run with a local harness command:

```sh
python3 scripts/capture_surface_baseline.py \
  --onboarding-repo /path/to/clean/repo \
  --dispatch-command 'python3 bin/synlynk.py dispatch codex --task "baseline probe"'
```

The script only marks a run verified when dispatch exits successfully and emits
the normal dispatched-job confirmation.
