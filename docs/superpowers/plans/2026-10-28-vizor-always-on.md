---
title: "Vizor always-on plan"
date: 2026-10-28
status: Accepted
author: "Grok (Home Conductor)"
goal: "goal-e3840370"
epic: "#2650"
milestone: "unscheduled (after v0.26.6)"
arc: "platform"
issue: "#2650"
---

# Vizor always-on plan

Spec: `docs/superpowers/specs/2026-10-28-vizor-always-on-design.md`.

## Tasks

1. Guard `synlynk/__init__.py` so only the Vizor daemon and `vizor_ensure` skip product-root resolution and the legacy import fan-out.
2. Add the heartbeat `version` column and write it from `_remember_beat`.
3. Cap `daemon.log`. Add the stall thread in `run_forever`.
4. Make `install` rewrite daemon and ensure units. Add `ensure()` with a healthy no-op and a 3-strike / 10-minute backoff.
5. Add `synlynk viz --ensure` and `synlynk/vizor_ensure.py`.
6. Pass a Vizor URL hint into the dispatch, jobs, and exec fences without changing `render_task_fence`.
7. Tests cover the import guard, version migration, log cap, ensure no-op, ensure restart, backoff, fence hint, and the existing `run_forever` shutdown test.

## Verification

`pytest tests/test_vizor_daemon.py tests/test_vizor_heartbeats.py tests/test_vizor_daemon_stream.py tests/test_fencing.py tests/test_viz.py tests/test_project_root_hardening.py tests/test_four_point_attribution.py`

Do not load or kickstart the operator's real `com.synlynk.vizor-daemon` plist from tests. Do not bind port 33333.
