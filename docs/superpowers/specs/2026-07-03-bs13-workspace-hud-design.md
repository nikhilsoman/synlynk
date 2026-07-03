# BS-13 Workspace HUD — Design Spec

**Date:** 2026-07-03  
**Status:** Approved — ready for implementation  
**Roadmap:** BS-13 (v0.11.0)  
**Author:** PM session (Claude) + Nikhil

---

## What it is

`synlynk watch` is a terminal-native HUD for monitoring the 6-cycle SDLC state of a workspace. It reads from `state.db` (always) and optionally enriches from the daemon HTTP API at `localhost:27471`. It has two modes:

- **`synlynk watch`** — ambient monitoring, 10s refresh, full B3 layout with tube-line sidebar
- **`synlynk watch --live`** — active job stream, 3s refresh, no sidebar, large job cards only

`synlynk watch` does **not** overlap with Vizor (`synlynk viz`). Vizor shows historical Gantt + tube map in the browser. The HUD shows live workspace state in the terminal. They are complementary, not redundant.

---

## Architecture

### New files

**`synlynk/hud.py`** — all HUD logic. Two classes:

| Class | Purpose |
|---|---|
| `JobSnapshot` | Data layer. Queries `state.db`, optionally enriches from daemon. Returns typed dicts. |
| `HUDRenderer` | Full ambient HUD. Renders B3 layout with platform health header, tube sidebar, cycle-filtered right panel. |
| `LiveRenderer` | Stripped-down `--live` view. No sidebar. Larger job cards with context progress bar. |

### Modified files

**`synlynk/cli.py`** — add `cmd_watch(args)` function. Parses `--live` flag, instantiates the correct renderer, runs the poll loop, handles `KeyboardInterrupt` cleanly (cursor restore + terminal reset).

### No new state.db tables

All data comes from the existing `jobs` table. No schema changes required.

### Renderer approach: buffered ANSI diff

Each tick renders the full frame into a string buffer. Diff against the previous frame's buffer. Only emit changed lines using ANSI cursor positioning (`\033[<row>;<col>H`). This avoids full-screen flicker without requiring a curses dependency.

---

## Data layer (`JobSnapshot`)

### Queries

```sql
-- Running/queued jobs (both modes)
SELECT agent, branch, cycle, status, started_at, cost_usd, tokens_in, tokens_out, context_pct
FROM jobs
WHERE status IN ('running', 'queued')
ORDER BY started_at DESC;

-- Recent history (right panel, ambient mode)
SELECT agent, branch, cycle, status, started_at, ended_at, cost_usd
FROM jobs
WHERE status = 'done'
ORDER BY ended_at DESC
LIMIT 5;
```

### Daemon enrichment (optional)

If `localhost:27471/status` responds within 500ms, merge its budget and agent-fleet data into the platform health panel. If the daemon is absent or slow, render immediately from `state.db`; daemon data merges on the next tick. Never block the render waiting for the daemon.

---

## Colour map

| Cycle | Colour | Hex |
|---|---|---|
| Dream | Purple | `#a371f7` |
| Plan | Blue | `#58a6ff` |
| Work | Orange | `#f0883e` |
| Ship | Green | `#3fb950` |
| Maintain | Yellow | `#d29922` |
| Engage | Teal | `#39d3bb` |

Active cycles render at full brightness. Idle cycles dim to ~35% opacity via ANSI 256-colour approximation.

---

## Layout: `synlynk watch` (ambient)

```
┌─ PLATFORM HEALTH ──────────────────────────────── [p] ─┐
│ ▶ PLATFORM  ✓ claude  ✓ agy  ✓ codex  ✓ grok  $8.40/$20 │
└────────────────────────────────────────────────────────┘
┌──── sidebar ────┬──── right panel (cycle-filtered) ────┐
│ synlynk         │ ◉ WORK — 2 running · $0.53 · 14.2k   │
│ ▌ Dream  ready  │                                       │
│ ▌ Plan   ready  │  [job cards for selected cycle]       │
│ ▌ Work ◀ 2 run  │                                       │
│ ▌ Ship   ready  │  ── READINESS ─────────────────────   │
│ ▌ Maintain idle │  codex ✓  agy ✓  claude —  grok —    │
│ ▌ Engage  idle  │                                       │
│                 │  ── RECENT ────────────────────────   │
│ [↑↓] [p] [q]   │  ✓ codex  feat/bs21  22m  $1.10  done │
└─────────────────┴────────────────────────────────────── ┘
```

**Sidebar** (B3 tube-line): Each cycle gets a 3px vertical colour bar on its left edge. Selected cycle gets a tinted background row and `◀` indicator. Arrow keys navigate cycles.

**Platform health header** (collapsible): Collapsed = one line showing agent fleet checkmarks + budget. `[p]` expands to show: agent fleet grid (2×2, version + trust-check), budget bar (daily + weekly), harness compliance (last probe + DRIFT sentinel count). Workspace dims to 40% opacity while expanded.

**Right panel — active cycle selected:**
- Running job cards (colour-bordered left edge matching cycle colour)
- Each card: agent name, branch, cycle tag, duration, tokens, cost, context % progress bar
- Readiness section: which agents are configured for this cycle
- Recent history: last 2–5 completed jobs in this cycle

**Right panel — idle cycle selected:**
- "no active jobs in this cycle" placeholder (dashed border)
- Readiness section with `synlynk launch <cycle>` hint
- Recent history for this cycle

---

## Layout: `synlynk watch --live`

No sidebar. No cycle navigation. Shows only actively running jobs regardless of cycle.

```
◉ synlynk watch --live          3s refresh  [q]quit [r]refresh [a]all

┌─ codex ──────────────────────────────────────── $0.42 ─┐
│ feat/bs20-deep-scan                                     │
│ cycle: work  ·  4m 12s  ·  10.1k tok  ·  38 req        │
│ ████████████░░░░░░░░  62% context used                  │
└────────────────────────────────────────────────────────┘

┌─ agy ────────────────────────────────────────── $0.11 ─┐
│ docs/blog-post                                          │
│ cycle: work  ·  1m 30s  ·  4.1k tok  ·  12 req         │
│ ███░░░░░░░░░░░░░░░░░  18% context used                  │
└────────────────────────────────────────────────────────┘

no other active jobs · [a] show all cycles · synlynk watch for full HUD

2 running · $0.53 · 14.2k tok          refreshed 1s ago
```

`[a]` switches the query to include all statuses (for spotting queued/stalled jobs).

---

## Refresh strategy

| Mode | Interval | Query scope |
|---|---|---|
| `synlynk watch` | 10s | running + queued + recent 5 |
| `synlynk watch --live` | 3s | running + queued only |
| `[r]` force | immediate | same as active mode |

Status line always shows "refreshed Ns ago" as an integer. Never "just now".

---

## Key bindings

| Key | Effect |
|---|---|
| `↑` / `↓` | Navigate cycles (ambient mode only) |
| `[p]` | Toggle platform health accordion |
| `[r]` | Force immediate refresh |
| `[1]` | Toggle compact job rows (one line per job) |
| `[a]` | `--live` only: show all cycles |
| `[q]` | Clean exit (cursor restore + terminal reset) |

No mouse support.

---

## Error states

| Condition | Behaviour |
|---|---|
| `state.db` missing | Full-screen error: `✗ state.db not found — run synlynk scan first`. No partial render. |
| Schema version mismatch | Warning banner: `⚠ schema vN expected, got vM — run synlynk migrate`. HUD renders with available columns. |
| No jobs anywhere | Right panel: `all cycles idle · $X.XX spent today`. All sidebar cycles dim. Not an error. |
| Daemon absent | Silently falls back to `state.db`. Budget/harness lines in platform health show `—`. |
| Daemon slow (>500ms) | Render from `state.db` immediately. Daemon data merges on next tick. |
| Terminal < 80 cols | Auto-compact mode. Below 60 cols: drops sidebar, falls back to horizontal cycle bar. |

---

## Out of scope

- Vizor overlap: no browser dashboard, no Gantt, no historical visualisation
- `synlynk status --platform`: its output is absorbed into the platform health header; the standalone command is unchanged
- Writing to `state.db`: HUD is read-only
- Daemon management: HUD does not start, stop, or restart the daemon

---

## Implementation notes for agents

- Use `select` or `poll` for keyboard input, not `getch()` with blocking — allows the refresh ticker and keypress to share the same loop
- Restore terminal state (`stty sane` equivalent) on any exit path including exceptions
- ANSI colour codes: use 256-colour `\033[38;5;<n>m` for closest match to hex values above; true-colour `\033[38;2;<r>;<g>;<b>m` where supported
- `synlynk/hud.py` must have zero imports outside Python stdlib — no curses, no blessed, no rich
