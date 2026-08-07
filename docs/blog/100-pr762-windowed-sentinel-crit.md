---
title: "PR #762 — Windowed sentinel_crit: Stop Lifetime Logs from Keeping Ops RED"
date: 2026-08-07
series: "Building the OS for Multi-Agent Development"
post: 100
issue: 751
---

# Windowed `sentinel_crit` — Stop Lifetime Logs from Keeping Ops RED

## Broader goal (end of previous PR)

Platform ops nightly (#719) replaced fleet-only EOD with a cross-repo scoreboard. Hygiene and ops were deliberately split: a machine could be hygiene-GREEN while ops stayed RED on real multi-agent failures (LIVE issues, sentinel CRITICAL, bad job rates).

## What moved the goalpost

The first live nightlies reported **ops RED** with `sentinel_crit≈47–48` while open LIVE=0. A full triage showed the truth:

| Bucket | Count | Meaning |
|--------|------:|---------|
| REAL (≤48h) | 5 | Recent agy timeouts / stalls worth acting on |
| AGED (2–7d) | 12 | Preflight noise / already-done jobs |
| STALE (>7d) | 31 | July history — pure append-only log debt |

`sentinel.md` is an **append-only** alert log. L4 counted **every** CRITICAL/FLATLINE line in the file. Lifetime history is not an open incident. That made the scoreboard untrustworthy and drowned the five real lines.

## What this PR ships

1. **`count_sentinel_critical_lines`** — pure helper that returns `(windowed, lifetime, untimestamped)`.
2. **Window = report `--hours`** (override via `SYNLYNK_OPS_SENTINEL_HOURS`).
3. **Alert-bullet only** — requires `- [` so triage notes mentioning the word CRITICAL do not count.
4. **Untimestamped CRITICAL lines** count toward lifetime only (cannot flip ops RED).
5. **Signals payload** now includes:
   - `sentinel_critical_lines` (windowed — used for pass/findings)
   - `sentinel_critical_lines_lifetime`
   - `sentinel_critical_untimestamped`
   - `sentinel_window_hours`
6. Human report L4 line shows both windowed and lifetime.
7. Unit tests with a multi-month fixture (acceptance: 40 stale lines → windowed 0, no sentinel finding).
8. Docs note in `docs/brainstorm/fleet-operability/PLATFORM-OPS-NIGHTLY.md`.

## Related hygiene (not in this PR)

Same day ops triage archived STALE sentinels and reaped zombie `running` jobs; product follow-ups: #750 (agy timeout cluster), #752 (cost $0 gap), #753 (`jobs reap`).

## On the long arc

Autonomous multi-agent dispatch needs a scoreboard that is **actionable**, not historically noisy. Windowed L4 is a small correctness fix that makes nightly ops RED mean "something recent is wrong."

## New goalpost

- Nightly ops RED on sentinel only when **recent** severity alerts exceed threshold.
- Still open: auto-reap zombies (#753), agy timeout root cause (#750), cost capture gap (#752).
