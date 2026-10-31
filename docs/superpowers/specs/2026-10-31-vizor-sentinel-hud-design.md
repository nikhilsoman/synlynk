---
title: "Vizor Overview sentinel HUD (Wave D / #2672)"
date: 2026-10-31
status: Accepted
author: "Grok (Home Conductor)"
goal: "goal-e3840370"
epic: "#2458"
milestone: "v0.26.7"
arc: "platform"
issue: "#2672"
parent_spec: "docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md"
---

# Vizor Overview — sentinel HUD (Wave D)

## Status

Accepted 2026-10-31 (Nikhil: "go ahead"). Product code follows the plan in `docs/superpowers/plans/2026-10-31-vizor-sentinel-hud.md`. This spec does not bump VERSION, does not edit CHANGELOG or README, and does not cut or retag a release.

v0.26.6 is **done** (tag `v0.26.6`, #2641 closed 2026-10-28). Waves A–C of the write-path edition are **on `main`** and tagged `v0.26.7` (`ec809e84`). This ticket is Wave D of that edition. Implementation PRs stay on GitHub milestone **v0.26.7** (#63) and leave VERSION at `0.26.7`. A later named cut is a separate ceremony.

Do not retitle #2470. Epic #2458 stays open.

**Tracking:** [#2672](https://github.com/nikhilsoman/synlynk/issues/2672) under [#2458](https://github.com/nikhilsoman/synlynk/issues/2458). Governing goal `goal-e3840370`. Parent edition spec: `docs/superpowers/specs/2026-10-31-v0.26.7-vizor-interactive-write-path-design.md` (Wave D row).

---

## 1. Decision

The Overview sentinel surface is a **grouped HUD with local ack/ignore and one GitHub raise path**. It is not a log editor.

1. Group active alerts by **pattern `code`** (`STALL_NO_OUTPUT`, `TOKEN_BLOAT`, …). Collapse groups with more than a handful of members. Expand lists individual alerts.
2. Every expanded row and every group header has **Inspect / Ignore / Raise issue / Investigate**. Investigate is copy-only.
3. Persist ack/ignore in a **dedicated per-workspace sidecar**. Do not rewrite `sentinel.md`. Do not mark an acked row `resolved` in the parser.
4. SSE `event: sentinel` refreshes **groups**, including the acked section. It does not flatten hundreds of alerts back into one button list.
5. GitHub writes use `synlynk gh --role support`. No `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH`. Bind stays `127.0.0.1`. Every POST still goes through the single `authorize_local_request` call site already at daemon `do_POST`.

This is the write-path the v0.26.6 read-only panel deferred, and the write the edition spec left out of Wave C.

---

## 2. What already shipped (do not regress)

| Piece | Where | Contract |
|---|---|---|
| Heartbeat + SSE + read-only inspect | `vizor_daemon.py`, `overview.py` | Inspection panel is read-only until this spec |
| Flat list, first 6 of `telemetry.sentinel_alerts` | `synlynk/viz/overview.py` | Replace with grouped HUD |
| Alert projection | `load_workspace_sentinel_alerts` in `synlynk/viz/data.py` | Keep field names; grouping consumes this shape |
| Parser | `_iter_sentinel_alerts` / `_parse_sentinel_alert` | Read-only from Vizor. `sentinel_clear` stays CLI |
| Daemon POST auth | `authorize_local_request` at top of `do_POST` | Single call site; fail closed |
| Workspace writes | `/w/<slug>/api/*` | No site-root POST |
| Write-route table | `synlynk/viz/write_routes.py` | Add sentinel rows; do not revive hidden Wave C CTAs |
| Notes sidecar precedent | `.synlynk/viz-notes.json` | Same class of store as the ack sidecar |
| Memorable ports | `MEMORABLE_VIZOR_PORTS` | Unchanged |

Live Overview today dumps the first six unstructured rows and, on SSE, rebuilds `.alerts-list` as one button per alert. On synlynk that is hundreds of `STALL_*` / `TOKEN_BLOAT` / `COST_INFLATION` lines.

---

## 3. Grouping model

### Key

Group key is `code` / `pattern` after `str(code).strip().upper()`. Empty or missing code is the group `UNPARSED` (legacy free-form bullets). Do not group on the raw line or on severity alone. A code that fires at both WARNING and CRITICAL is still one group; the header severity is the **worst** member (`CRITICAL` > `WARNING` > `INFO`).

### Header (collapsed)

| Field | Source |
|---|---|
| severity | worst member |
| pattern | group key |
| count | sum of `occurrences` (default 1) |
| first seen | min `first_seen` / `ts` |
| last seen | max `last_seen` / `ts` |

### Members (expanded)

Each member is one projected alert: severity, pattern, message, first_seen, last_seen, occurrences, raw_line, plus `identity` (see below). Cap **rendered** members at 50 per group with a “N more” note. The count on the header is the full sum.

### Collapse default

- Group `count > 3` starts collapsed.
- Groups of 1–3 start expanded.
- The **Acked** section starts collapsed as a whole.

### Identity

Reuse `_alert_identity` from `synlynk/sentinel.py`: `(normalized severity, upper code, collapsed message)`. Occurrence-level ack keys off that tuple plus workspace slug. Do not key off the write timestamp.

### Parser `resolved`

`resolved` remains what `load_workspace_sentinel_alerts` already computes (`[RESOLVED]` in the raw line, or code `RESOLVED`). **Ack is not resolved.** An acked still-firing pattern stays in the Acked section until the pattern goes quiet *or* it refires past the ack watermark.

---

## 4. Ack sidecar

Path: **`.synlynk/sentinel-acks.json`** under the **workspace `path_root`**, constant `SENTINEL_ACKS_PATH` next to `VIZ_NOTES_PATH`.

This is UI state, not GOVERNS truth. Do not put acks in `state.db` in this cut. Do not write `sentinel.md`. Do not call `_clear_sentinel_alerts`, `_rewrite_sentinel_alerts`, or `compact_sentinel_alerts` from Vizor handlers.

### Schema

```json
{
  "version": 1,
  "slug": "synlynk",
  "acks": [
    {
      "kind": "occurrence",
      "code": "STALL_NO_OUTPUT",
      "identity": ["WARNING", "STALL_NO_OUTPUT", "normalized message"],
      "acked_at": "2026-10-31T12:00:00Z",
      "last_seen_at_ack": "2026-10-31T11:58:00Z",
      "issue_url": null
    },
    {
      "kind": "pattern",
      "code": "TOKEN_BLOAT",
      "identity": null,
      "acked_at": "2026-10-31T12:01:00Z",
      "last_seen_at_ack": "2026-10-31T12:00:30Z",
      "issue_url": "https://github.com/nikhilsoman/synlynk/issues/NNNN"
    }
  ]
}
```

`kind`:

| kind | CTA | Hides |
|---|---|---|
| `occurrence` | Ignore on a member row | That identity only |
| `group` | Ack group (current members) | Every identity present in the group at ack time, until refire |
| `pattern` | Ignore this pattern until it fires again | The whole code, until refire |

**Group ack** writes `kind: "pattern"` (one row). The product copy may say “ack group”; the store does not need both `group` and `pattern` as distinct hide rules. If an implementation writes `kind: "group"` with an identity list, hide those identities until any member’s `last_seen` exceeds `last_seen_at_ack`. Prefer `pattern` for the header Ignore/ack control so 400 `STALL_NO_OUTPUT` rows become one sidecar record.

### Refire

A pattern ack **expires** when any active alert with that code has `last_seen` (else `ts`) **strictly after** `last_seen_at_ack`. The group returns to Active. The expired ack row stays in the file as history; the HUD ignores expired rows when classifying.

An occurrence ack expires the same way for that identity.

Acking synlynk does not ack any other slug. The daemon reads the sidecar from that workspace’s `path_root`. Missing file = no acks.

Write with the same replace-file discipline as notes (`VIZ_NOTES_PATH`). Create `.synlynk/` if needed. Corrupt JSON = empty ack set plus a single INFO-level log line; do not crash Overview.

---

## 5. CTAs

All four exist on **each expanded member** and on **each group header**.

| CTA | Where it runs | Effect |
|---|---|---|
| **Inspect** | Client | Existing read-only panel. Member: current fields. Group: header fields plus up to 5 sample messages. No write. |
| **Ignore** | `POST /w/<slug>/api/sentinel/ack` | Member → `kind: occurrence`. Header → `kind: pattern`. Hides from Active; does not delete log lines. |
| **Raise issue** | `POST /w/<slug>/api/sentinel/issue` | Opens one GitHub issue (role App `support`). Records `issue_url` on a pattern ack if the raise was at group scope, or on the occurrence ack if it was a member. |
| **Investigate** | Client clipboard | Copy a bounded JSON brief. **No POST. No shell. No “run this to reproduce”.** |

### Investigate brief (copy payload)

```json
{
  "slug": "synlynk",
  "code": "STALL_NO_OUTPUT",
  "severity": "WARNING",
  "count": 400,
  "first_seen": "...",
  "last_seen": "...",
  "sample_messages": ["…", "…"],
  "identities": [["WARNING", "STALL_NO_OUTPUT", "…"]],
  "job_ids": [],
  "agents": []
}
```

`job_ids` / `agents` are extracted from messages with the existing `_extract_sentinel_agent` helper and a conservative `job-[0-9a-f]+` scan. Cap arrays at 20. Never include a command line, `sentinel.md` path write, or a suggested `curl`.

### Raise issue

- Command shape: `synlynk gh --role support -- issue create --title … --body …`.
- Title: `[support] sentinel: <CODE> (n)` with `n` = group count (or 1 for a member).
- Body: workspace slug, code, severity, first/last seen, count, up to 20 sample `raw_line`s, Investigate JSON as a fenced block, link to #2672 only if useful as context — do not dump 647 lines.
- Labels: `live-issue` if the helper already uses it for sentinel; otherwise no extra labels beyond what `support` normally applies. Do not invent a new label in this cut.
- Host auth env is unset. Personal tokens stay off-limits.
- Failure (gh non-zero) returns HTTP 502 with `{ "ok": false, "error": "gh_failed" }`. Do not ack on failure.
- Success returns `{ "ok": true, "issue_url": "https://…" }` and upserts the sidecar `issue_url`.

One issue per raise click. Raising at group scope creates **one** issue for the pattern, not one per member.

---

## 6. HTTP and SSE

Workspace-relative only.

| Method | Path | Auth | Body / result |
|---|---|---|---|
| GET | `/w/<slug>/api/sentinel` | none (same as other GETs) | `{ "groups": [...], "acked": [...], "active_count": N, "acked_count": M }` |
| POST | `/w/<slug>/api/sentinel/ack` | `authorize_local_request` | `{ "scope": "occurrence" \| "pattern", "code": "...", "identity": [...]? }` → `{ "ok": true }` |
| POST | `/w/<slug>/api/sentinel/issue` | `authorize_local_request` | same scope fields → `{ "ok": true, "issue_url": "..." }` |

`scope: "occurrence"` requires `identity`. `scope: "pattern"` ignores `identity`.

`WRITE_ROUTES` gains:

```python
"sentinel/ack": "keep",
"sentinel/issue": "keep",
```

Investigate has no route.

### Overview first paint

Replace the first-6 flat dump with the grouped HUD. Embed a **grouped** snapshot in `#sentinel-snapshot` (groups + acked), not 647 raw alerts. Members inside the snapshot may be capped at 50 per group; GET `/w/<slug>/api/sentinel` is the full grouping.

Empty Active + empty Acked: keep the current empty treatment (no banner). Active count in the title is unacked active alerts (sum of group counts), not group cardinality.

Acked section heading: `Acked (k)` under the Active list, collapsed.

### SSE

`event: sentinel` payload **is the grouped object**, same shape as GET. The client replaces Active and Acked from `groups` / `acked`. It must not map `payload.alerts` into one button per item.

If a transitional payload still includes `alerts` for older tests, the Overview script prefers `groups` when present.

Heartbeat `event: heartbeat` is unchanged.

Relative stream URL stays `/w/<slug>/api/daemon/stream`.

---

## 7. Files

| File | Change |
|---|---|
| `synlynk/viz/overview.py` | Grouped HUD, CTAs, grouped snapshot, SSE consumer, Investigate copy |
| `synlynk/viz/data.py` | `group_workspace_sentinel_alerts(alerts, acks)`; load sidecar |
| `synlynk/viz/constants.py` | `SENTINEL_ACKS_PATH = ".synlynk/sentinel-acks.json"` |
| `synlynk/vizor_daemon.py` | GET grouped sentinel; POST ack/issue under `/w/<slug>/api/sentinel/*` (auth already at `do_POST`) |
| `synlynk/viz/write_routes.py` | Two `keep` rows |
| `synlynk/viz/server.py` | Optional: same routes on `VizorHandler` so a non-daemon serve does not 404; still authorize |
| `synlynk/sentinel.py` | **No writes from Vizor.** May import `_alert_identity` / `_extract_sentinel_agent` |
| tests | New `tests/test_viz_sentinel_hud.py` (and daemon route tests). Update Overview tests that assume six flat buttons / `payload.alerts` flatten |

Do not add a second auth compare in the sentinel handlers.

---

## 8. Tests

- Fixture with three codes and 20+ 10+ 2 members: Active shows 3 groups; the 20- and 10-member groups start collapsed; the 2-member group starts expanded.
- Header count is the sum of `occurrences`.
- Occurrence Ignore hides one identity; sibling members in that code remain Active; `sentinel.md` byte-identical.
- Pattern Ignore moves the group to Acked; `sentinel.md` unchanged.
- A new member with `last_seen` after `last_seen_at_ack` returns the pattern to Active.
- Ack file in workspace A is invisible to workspace B.
- POST without token → 401/403; no sidecar write.
- POST with token writes sidecar; GET grouping reflects it.
- SSE fixture payload has `groups` and the Overview script does not build one `.alert-item` per raw alert when `groups` is present.
- Investigate payload has no `shell`, `reproduce`, or `$ ` command line.
- Raise issue: mock `synlynk gh`; argv includes `--role` `support`; host-auth env absent; sidecar stores `issue_url`.
- `WRITE_ROUTES["sentinel/ack"] == "keep"` and `["sentinel/issue"] == "keep"`.
- Existing skinny / write-route / heartbeat tests stay green.

---

## 9. Out of scope

- Detector quality (#2500).
- Compacting or rewriting `sentinel.md` from Vizor. CLI `synlynk sentinel clear` stays CLI.
- Cross-workspace sentinel rollup.
- Ack table in `state.db`.
- Binding `0.0.0.0`, cookies, personal GitHub tokens.
- `viz --ensure` / daemon lifecycle / identity UI.
- VERSION / CHANGELOG / README / retag `v0.26.7`.
- Retitling #2470. Closing #2458.
- Wave E Jantt vendor. Wave F dive list. #4973 CPM.
- Efficiency / Observatory sentinel counts beyond what they already show.

---

## 10. Implementation split (after sign-off)

Plan file later: `docs/superpowers/plans/2026-10-31-vizor-sentinel-hud.md`. Dispatch via `synlynk dispatch` (no in-session product coding).

Suggested PRs:

1. **Grouping + SSE + Inspect** (read path; sidecar read as empty). Unblocks the 647-button Overview.
2. **Ack sidecar + Ignore + Raise issue + Investigate copy** (write path).

Grok owns Overview canvas/JS. Codex owns daemon routes and sidecar IO. qa merge is headless Agy (`gemini-3.8-flash-high`), reviewer harness+model different from the implementer. Architect review if the sidecar vs `state.db` choice is challenged.

---

## 11. Sign-off

Product code starts only after this file is signed off. The issue already named grouping, the four CTAs, group ack, dedicated store, per-slug isolation, SSE grouping, and “ack ≠ resolved”. This spec pins:

- sidecar path `.synlynk/sentinel-acks.json` (not `state.db`, not `sentinel.md`)
- collapse threshold `count > 3`
- pattern-ack refire = `last_seen` strictly after `last_seen_at_ack`
- Raise issue role `support`
- Investigate copy-only
- grouped SSE / GET shape
- no VERSION bump

Please review this file and say if you want changes before the implementation plan.
