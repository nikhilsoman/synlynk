# Platform ops nightly (replaces fleet-only EOD)

**Status:** Implemented on `feat/platform-ops-nightly`  
**CLI:** `synlynk ops report [--hours 24] [--json]`  
**Support Engineer:** signal type `platform_ops` in `.agents/support.json`

## Why

Fleet EOD (matrix/doctor/TIER) was hygiene-only and single-repo. It could be all-green while LIVE issues, unknown jobs, and orphan costs burned money across repos.

## What it covers (nine gaps)

| # | Gap | Layer |
|---|-----|--------|
| 1 | Single-repo only | Cross `~/dev/*` + `~/.synlynk/projects/*` |
| 2 | No job outcomes | L1 status mix, unknown/fail rates |
| 3 | Live smoke ≠ real work | L1 jobs separate from L6 smoke cells |
| 4 | Doctor presence checks | L0 matrix + L1 outcomes (not TC-2 alone) |
| 5 | No GH-write lane | L3 heuristics + can_gh_write list |
| 6 | No LIVE/sentinel feed | L4 open `live-issue` + **windowed** sentinel CRITICAL (#751) |
| 7 | No cost rollup | L2 cost_entries + orphan rate |
| 8 | Worktree debt ignored | L5 counts |
| 9 | Soft pass criteria | Scoreboard splits **hygiene** vs **ops** |

Exit code **1** when **ops=RED** (even if hygiene is GREEN).

## L4 sentinel window (#751)

`sentinel.md` is **append-only**. L4 does **not** count the full file history.

| Signal key | Meaning |
|------------|---------|
| `sentinel_critical_lines` | CRITICAL / FLATLINE / QUOTA_EXHAUSTED bullets with timestamp in the last **N hours** (default = report `--hours`) |
| `sentinel_critical_lines_lifetime` | Same severity tokens, all ages (diagnostic only) |
| `sentinel_critical_untimestamped` | Severity bullets with no parseable timestamp (excluded from windowed) |
| `sentinel_window_hours` | Window actually used |

Override window independently of job/cost hours: `SYNLYNK_OPS_SENTINEL_HOURS=48`.

Threshold for signals.pass / finding: **windowed** count `< 5` (unchanged). STALE July history alone cannot keep ops RED.

## Commands

```bash
# Full environment report (this machine)
python3 -m synlynk ops report --hours 24

# JSON for tooling
python3 -m synlynk ops report --hours 72 --json

# Support Engineer dry-run (includes platform_ops signal)
python3 -m synlynk agent run support --dry-run

# Support Engineer live (files issues / may dispatch fixes — HITL)
python3 -m synlynk agent run support
```

## Support Engineer status

| Item | Status |
|------|--------|
| Code | `synlynk/support_engineer.py` — **shipped** (v0.8.0) |
| Config | `.agents/support.json` |
| Last run (this repo) | historically **never run** until wired |
| GHA | `.github/workflows/support-engineer.yml` every 6h on main (needs secrets) |
| Local cron | `synlynk agent run support --install-cron` (every 6h) |

**Wiring:** `platform_ops` is now the **first** signal so Support Engineer becomes a **platform** consumer of the same rollup the nightly uses.

## Nightly schedule

Grok Build durable daily task runs `synlynk ops report --hours 24` and posts the scoreboard (not the old fleet-only checklist).
