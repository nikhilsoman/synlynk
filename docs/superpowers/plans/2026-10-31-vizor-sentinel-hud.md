# Vizor Overview sentinel HUD Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. This repo executes via **`synlynk dispatch`**, not in-session `spawn_subagent`.

**Goal:** Group Overview sentinel alerts by pattern, refresh groups over SSE, and persist Ignore / Raise issue without rewriting `sentinel.md`.

**Architecture:** Project alerts with `load_workspace_sentinel_alerts`, then `group_workspace_sentinel_alerts` (acks applied). Overview renders groups + a collapsed Acked section. Daemon GET `/w/<slug>/api/sentinel` and SSE `event: sentinel` emit the grouped object. POST `/w/<slug>/api/sentinel/ack` and `…/issue` write `.synlynk/sentinel-acks.json` under the workspace `repo_path`. Every POST still hits the existing `authorize_local_request` at daemon `do_POST`. Investigate is clipboard-only.

**Tech Stack:** Python 3.10+, `http.server`, pytest, `synlynk/viz/overview.py`, `synlynk/viz/data.py`, `synlynk/vizor_daemon.py`, `synlynk/viz/server.py`.

**Spec:** `docs/superpowers/specs/2026-10-31-vizor-sentinel-hud-design.md`. Issue #2672. Goal `goal-e3840370`. Epic #2458.

**Harness:** Grok for PR1 (grouping + Overview + SSE). Codex for PR2 (sidecar IO, POST routes, gh raise). Reviewer harness+model must differ from implementer. qa merge is headless Agy (`gemini-3.8-flash-high`). Interpreter: `/opt/homebrew/bin/python3`. Trailer for the implementing harness. Worktree per PR from `origin/main` after this plan is on `main`. Do not bump VERSION, CHANGELOG, README, or tag. Do not retitle #2470. Do not close #2458. Do not bind `0.0.0.0`. Do not set `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH`. Do not call `_clear_sentinel_alerts` / `_rewrite_sentinel_alerts` / `compact_sentinel_alerts` from Vizor. Do not mutate live `~/.synlynk/workspaces/synlynk/state.db` or live `sentinel.md` in tests.

---

## Global constraints

- Writes: `/w/<slug>/api/*` only. Ack file: `os.path.join(str(ctx.repo_path), ".synlynk", "sentinel-acks.json")` — never the daemon cwd.
- Auth: existing `authorize_local_request` at top of daemon `do_POST`. Do not add a second compare in sentinel handlers.
- Ack ≠ parser `resolved`. `sentinel.md` is read-only from Vizor.
- Pattern ack expires when any member `last_seen` (else `ts`) is strictly after `last_seen_at_ack`.
- Collapse: group `count > 3` starts collapsed; 1–3 start expanded; Acked section starts collapsed.
- Raise issue: `synlynk gh --role support -- issue create …`. Host-auth env unset.
- Investigate: no POST, no shell, no reproduce command.

## Out of this plan

Detector quality (#2500). CLI `sentinel clear`. Cross-workspace rollup. `state.db` ack table. Wave E/F. #4973. Named-release cut.

## File map

| File | Role |
|---|---|
| `synlynk/viz/constants.py` | Add `SENTINEL_ACKS_PATH = ".synlynk/sentinel-acks.json"` |
| `synlynk/viz/__init__.py` | Re-export `SENTINEL_ACKS_PATH` if `VIZ_NOTES_PATH` is re-exported |
| `synlynk/viz/data.py` | `load_sentinel_acks`, `save_sentinel_ack`, `group_workspace_sentinel_alerts`, `investigate_brief` |
| `synlynk/viz/overview.py` | Grouped HUD, Inspect, later CTAs, grouped `#sentinel-snapshot`, SSE prefers `groups` |
| `synlynk/viz/server.py` | `serve_daemon_stream` emits grouped sentinel; optional handler routes |
| `synlynk/vizor_daemon.py` | GET `api/sentinel`; POST `api/sentinel/ack` and `api/sentinel/issue` |
| `synlynk/viz/write_routes.py` | `"sentinel/ack": "keep"`, `"sentinel/issue": "keep"` |
| `tests/test_viz_sentinel_hud.py` | **Create.** Grouping, ack, refire, slug isolation, Investigate shape |
| `tests/test_vizor_daemon_stream.py` | SSE `groups`; keep Overview inspect fields |
| `tests/test_viz_write_path_table.py` | Allow the two new keep routes in `required` |

---

## PR 1 — Grouping + SSE + Inspect (#2672)

Worktree: `feat/grok/vizor-sentinel-hud-groups` from `origin/main`. Harness: Grok. `--task-type canvas`. `--role dev`. `--requires-gh-write` `--gh-write-expect pr_open`. No Ignore/Raise POST in this PR. Overview stays without `fetch(` so `test_overview_inspection_is_read_only` can keep `assert "fetch(" not in inline` until PR2.

### Task 1: Grouping helper

**Files:**
- Modify: `synlynk/viz/constants.py`
- Modify: `synlynk/viz/data.py`
- Create: `tests/test_viz_sentinel_hud.py`

- [ ] **Step 1: Write the failing tests**

```python
from synlynk.viz.constants import SENTINEL_ACKS_PATH
from synlynk.viz.data import group_workspace_sentinel_alerts


def _alert(code, n=1, *, severity="WARNING", message="stall", last="2026-10-31 12:00:00 UTC", first=None):
    return {
        "severity": severity,
        "pattern": code,
        "message": message,
        "ts": last,
        "raw_line": f"- [{severity}] [{last}] {code}: {message}",
        "occurrences": n,
        "first_seen": first or last,
        "last_seen": last,
        "resolved": False,
    }


def test_sentinel_acks_path():
    assert SENTINEL_ACKS_PATH == ".synlynk/sentinel-acks.json"


def test_groups_by_code_and_collapse_default():
    alerts = (
        [_alert("STALL_NO_OUTPUT", message=f"job {i}") for i in range(20)]
        + [_alert("TOKEN_BLOAT", message=f"tok {i}") for i in range(10)]
        + [_alert("COST_INFLATION", message="a"), _alert("COST_INFLATION", message="b")]
    )
    hud = group_workspace_sentinel_alerts(alerts, {"version": 1, "acks": []})
    by_code = {g["code"]: g for g in hud["groups"]}
    assert set(by_code) == {"STALL_NO_OUTPUT", "TOKEN_BLOAT", "COST_INFLATION"}
    assert by_code["STALL_NO_OUTPUT"]["count"] == 20
    assert by_code["STALL_NO_OUTPUT"]["collapsed"] is True
    assert by_code["TOKEN_BLOAT"]["collapsed"] is True
    assert by_code["COST_INFLATION"]["collapsed"] is False
    assert hud["active_count"] == 32
    assert hud["acked"] == []
    assert hud["acked_count"] == 0


def test_worst_severity_and_member_cap():
    alerts = [_alert("X", severity="WARNING", message=f"m{i}") for i in range(55)]
    alerts[0]["severity"] = "CRITICAL"
    hud = group_workspace_sentinel_alerts(alerts, {"acks": []})
    group = hud["groups"][0]
    assert group["severity"] == "CRITICAL"
    assert group["count"] == 55
    assert len(group["members"]) == 50
    assert group["hidden_member_count"] == 5


def test_empty_code_is_unparsed():
    hud = group_workspace_sentinel_alerts([_alert("")], {"acks": []})
    assert hud["groups"][0]["code"] == "UNPARSED"


def test_resolved_alerts_are_dropped():
    alerts = [_alert("X"), {**_alert("Y"), "resolved": True}]
    hud = group_workspace_sentinel_alerts(alerts, {"acks": []})
    assert [g["code"] for g in hud["groups"]] == ["X"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_viz_sentinel_hud.py -q`
Expected: FAIL (import / missing function).

- [ ] **Step 3: Implement grouping**

Add to `synlynk/viz/constants.py`:

```python
SENTINEL_ACKS_PATH = ".synlynk/sentinel-acks.json"
```

If `synlynk/viz/__init__.py` re-exports `VIZ_NOTES_PATH`, re-export `SENTINEL_ACKS_PATH` the same way.

Add to `synlynk/viz/data.py` (after `load_workspace_sentinel_alerts`):

```python
_SEV_RANK = {"CRITICAL": 3, "CRIT": 3, "WARNING": 2, "WARN": 2, "INFO": 1}


def _code_key(alert: dict) -> str:
    code = str(alert.get("pattern") or alert.get("code") or "").strip().upper()
    return code or "UNPARSED"


def _last_seen(alert: dict) -> str:
    return str(alert.get("last_seen") or alert.get("ts") or "")


def group_workspace_sentinel_alerts(alerts, acks=None, *, member_cap: int = 50) -> dict:
    """Split projected alerts into Active groups and Acked groups.

    ``acks`` is the sidecar object ``{"version": 1, "acks": [...]}`` or ``{}``.
    Occurrence / pattern hide rules are applied here so Overview and SSE share one shape.
    """
    from synlynk.sentinel import _alert_identity

    acks = acks or {}
    ack_rows = list(acks.get("acks") or [])
    active_alerts = [a for a in (alerts or []) if not a.get("resolved")]
    buckets = {}
    for alert in active_alerts:
        key = _code_key(alert)
        bucket = buckets.setdefault(key, [])
        bucket.append(alert)

    def _hidden(alert, code):
        identity = list(_alert_identity({
            "severity": alert.get("severity"),
            "code": code if code != "UNPARSED" else "",
            "message": alert.get("message") or "",
        }))
        last = _last_seen(alert)
        for row in ack_rows:
            kind = row.get("kind")
            if kind == "occurrence" and list(row.get("identity") or []) == identity:
                watermark = str(row.get("last_seen_at_ack") or "")
                if not last or last <= watermark:
                    return True
            if kind in ("pattern", "group") and str(row.get("code") or "").upper() == code:
                watermark = str(row.get("last_seen_at_ack") or "")
                if not last or last <= watermark:
                    return True
        return False

    def _pack(code, members, collapsed_default):
        count = sum(int(m.get("occurrences") or 1) for m in members)
        firsts = [m.get("first_seen") or m.get("ts") or "" for m in members]
        lasts = [_last_seen(m) for m in members]
        worst = max(members, key=lambda m: _SEV_RANK.get(str(m.get("severity") or "").upper(), 0))
        shown = members[:member_cap]
        return {
            "code": code,
            "severity": str(worst.get("severity") or "WARNING").upper(),
            "count": count,
            "first_seen": min((x for x in firsts if x), default=""),
            "last_seen": max((x for x in lasts if x), default=""),
            "collapsed": bool(collapsed_default if collapsed_default is not None else count > 3),
            "members": shown,
            "hidden_member_count": max(0, len(members) - len(shown)),
        }

    groups = []
    acked = []
    for code, members in buckets.items():
        visible = [m for m in members if not _hidden(m, code)]
        hidden = [m for m in members if _hidden(m, code)]
        if visible:
            packed = _pack(code, visible, None)
            packed["collapsed"] = packed["count"] > 3
            groups.append(packed)
        if hidden and not visible:
            packed = _pack(code, hidden, True)
            packed["collapsed"] = True
            acked.append(packed)
    groups.sort(key=lambda g: (-_SEV_RANK.get(g["severity"], 0), -g["count"], g["code"]))
    acked.sort(key=lambda g: g["code"])
    return {
        "groups": groups,
        "acked": acked,
        "active_count": sum(g["count"] for g in groups),
        "acked_count": sum(g["count"] for g in acked),
    }
```

Callers set `collapsed` after `_pack`. Do not use walrus assignment.

- [ ] **Step 4: Run tests**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_viz_sentinel_hud.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz/constants.py synlynk/viz/data.py synlynk/viz/__init__.py tests/test_viz_sentinel_hud.py
git commit -m "feat: group Vizor sentinel alerts by pattern"
```

Trailer: `Co-Authored-By: Grok <noreply@x.ai>` (or Codex if Codex implements).

### Task 2: Overview grouped HUD

**Files:**
- Modify: `synlynk/viz/overview.py` (alert loop ~12–57, snapshot JS ~404–496)
- Test: `tests/test_viz_sentinel_hud.py`, `tests/test_vizor_daemon_stream.py`

- [ ] **Step 1: Write failing tests**

```python
from synlynk.viz.overview import generate_overview_html


def test_overview_renders_groups_not_six_flat_rows():
    alerts = []
    for i in range(20):
        alerts.append({
            "severity": "WARNING",
            "pattern": "STALL_NO_OUTPUT",
            "message": f"stall {i}",
            "ts": "2026-10-31",
            "resolved": False,
            "raw_line": f"stall {i}",
            "occurrences": 1,
            "first_seen": "2026-10-01",
            "last_seen": "2026-10-31",
        })
    alerts.append({
        "severity": "CRITICAL",
        "pattern": "VIZOR_DAEMON_DOWN",
        "message": "bind failed",
        "ts": "2026-10-31",
        "resolved": False,
        "raw_line": "raw sentinel line",
        "occurrences": 4,
        "first_seen": "2026-10-27 01:00:00 UTC",
        "last_seen": "2026-10-28 02:00:00 UTC",
    })
    html = generate_overview_html({
        "workspace": {"name": "acme", "updated_at": "2026-10-31"},
        "telemetry": {"sentinel_alerts": alerts},
        "goals": [], "dreams": [], "jobs": [],
    }, 33333)
    assert "Active Sentinel Alerts (24)" in html
    assert 'data-sentinel-group="STALL_NO_OUTPUT"' in html
    assert 'data-sentinel-group="VIZOR_DAEMON_DOWN"' in html
    assert "Acked (" in html
    snapshot = html.split('id="sentinel-snapshot">', 1)[1].split("</script>", 1)[0]
    assert '"groups"' in snapshot
    assert "payload.alerts" not in html.split("addEventListener('sentinel'", 1)[1].split("source.onerror", 1)[0] or "payload.groups" in html
```

Keep `test_overview_inspection_is_read_only` green: still include inspect panel, `raw sentinel line`, no `method="post"`, no `/api/sentinel/clear`, no `>Run<`, no `fetch(` in the Overview script this PR.

- [ ] **Step 2: Run to see fail**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_viz_sentinel_hud.py::test_overview_renders_groups_not_six_flat_rows tests/test_vizor_daemon_stream.py::test_overview_inspection_is_read_only -q`

- [ ] **Step 3: Rewrite the Overview banner**

Replace the `sentinel_alerts[:6]` button dump with:

1. `hud = group_workspace_sentinel_alerts(unresolved, data.get("sentinel_acks") or {})`
2. Title uses `hud["active_count"]`.
3. Each Active group is a `<details>` (`open` when not `collapsed`) with `data-sentinel-group="{code}"`. Summary: severity pill, code, count, first seen, last seen. Body: member buttons `data-alert-index` still opening Inspect (`renderPanel`).
4. Acked section: `<details class="sentinel-acked">` closed, heading `Acked ({acked_count})`.
5. `#sentinel-snapshot` JSON is the **hud object** (groups + acked + counts), not a flat list. Keep `<` → `\u003c`.
6. SSE handler: `const hud = payload.groups ? payload : {groups: [], acked: [], active_count: 0, acked_count: 0};` then rebuild the grouped DOM. Do not `payload.alerts.map` into `.alerts-list` when `payload.groups` exists.
7. Inspect `renderPanel` looks up a member by walking `hud.groups` / `hud.acked` members, or keep a flat `members` index in the snapshot for inspect.

Member buttons stay `type="button"` with existing `.alert-item` classes.

- [ ] **Step 4: Tests pass**

Run: `/opt/homebrew/bin/python3 -m pytest tests/test_viz_sentinel_hud.py tests/test_vizor_daemon_stream.py tests/test_viz_nav.py tests/test_viz_nav_restructure.py tests/test_sentinel_noop_alert.py tests/test_viz_circuit_breaker.py -q`

- [ ] **Step 5: Commit**

```bash
git commit -m "feat: render Overview sentinel HUD as grouped details"
```

### Task 3: GET `/w/<slug>/api/sentinel` + grouped SSE

**Files:**
- Modify: `synlynk/viz/server.py` `serve_daemon_stream` (~820–868)
- Modify: `synlynk/vizor_daemon.py` `api/` branch (~877)
- Test: `tests/test_vizor_daemon_stream.py`, `tests/test_viz_sentinel_hud.py`

- [ ] **Step 1: Failing tests**

Extend `test_workspace_stream_emits_sentinel_from_repo` to parse the `event: sentinel` JSON and assert `"groups"` in the payload and `"VIZOR_DAEMON_DOWN"` appears under `groups` (still may include `alerts` for compatibility).

Add a daemon GET test (mirror stream fixture registry): `GET /w/acme/api/sentinel` returns 200 JSON with `groups`.

- [ ] **Step 2: Implement**

In `serve_daemon_stream`, after loading alerts:

```python
from synlynk.viz.data import group_workspace_sentinel_alerts, load_sentinel_acks
from synlynk.viz.constants import SENTINEL_ACKS_PATH

alerts = load_workspace_sentinel_alerts(sentinel_path, active_only=True)
acks_path = os.path.join(str(repo_path), SENTINEL_ACKS_PATH)
hud = group_workspace_sentinel_alerts(alerts, load_sentinel_acks(acks_path))
emit("sentinel", hud)
```

`load_sentinel_acks` in this PR may return `{"version": 1, "acks": []}` on missing/corrupt file (implement it now; write comes in PR2).

In `vizor_daemon.py` next to `api/note`:

```python
if api_route == "sentinel" and self.command == "GET":
    from synlynk.viz.data import (
        load_workspace_sentinel_alerts,
        load_sentinel_acks,
        group_workspace_sentinel_alerts,
    )
    from synlynk.viz.constants import SENTINEL_ACKS_PATH
    sentinel_path = os.path.join(str(ctx.repo_path), ".synlynk", "sentinel.md")
    acks_path = os.path.join(str(ctx.repo_path), SENTINEL_ACKS_PATH)
    hud = group_workspace_sentinel_alerts(
        load_workspace_sentinel_alerts(sentinel_path, active_only=True),
        load_sentinel_acks(acks_path),
    )
    body = json.dumps(hud).encode("utf-8")
    ...
```

- [ ] **Step 3: Tests pass + commit**

```bash
git commit -m "feat: emit grouped sentinel HUD on SSE and GET api/sentinel"
```

Open PR against `main`, body links #2672. Do not merge from the implementer job.

---

## PR 2 — Ack sidecar + Ignore + Raise issue + Investigate (#2672)

Worktree: `feat/codex/vizor-sentinel-hud-writes` from `origin/main` (after PR1 merge). Harness: Codex. `--task-type cli-plumbing`. `--role dev`. `--requires-gh-write` `--gh-write-expect pr_open`.

### Task 4: Sidecar read/write + occurrence/pattern hide

**Files:**
- Modify: `synlynk/viz/data.py`
- Test: `tests/test_viz_sentinel_hud.py`

- [ ] **Step 1: Tests**

```python
import json
from synlynk.viz.data import (
    load_sentinel_acks,
    save_sentinel_ack,
    group_workspace_sentinel_alerts,
)


def test_load_missing_acks_is_empty(tmp_path):
    assert load_sentinel_acks(str(tmp_path / "missing.json"))["acks"] == []


def test_corrupt_acks_are_empty(tmp_path):
    path = tmp_path / "sentinel-acks.json"
    path.write_text("{not json")
    assert load_sentinel_acks(str(path))["acks"] == []


def test_occurrence_ack_hides_one_identity(tmp_path):
    alerts = [_alert("STALL_NO_OUTPUT", message="job a"), _alert("STALL_NO_OUTPUT", message="job b")]
    path = tmp_path / "acks.json"
    from synlynk.sentinel import _alert_identity
    ident = list(_alert_identity({"severity": "WARNING", "code": "STALL_NO_OUTPUT", "message": "job a"}))
    save_sentinel_ack(str(path), {
        "kind": "occurrence",
        "code": "STALL_NO_OUTPUT",
        "identity": ident,
        "acked_at": "2026-10-31T12:00:00Z",
        "last_seen_at_ack": "2026-10-31 12:00:00 UTC",
        "issue_url": None,
    }, slug="acme")
    hud = group_workspace_sentinel_alerts(alerts, load_sentinel_acks(str(path)))
    assert hud["groups"][0]["count"] == 1
    assert hud["groups"][0]["members"][0]["message"] == "job b"
    original = tmp_path / "sentinel.md"
    original.write_text("untouched\n")
    # grouping must not write sentinel.md — caller never opened it


def test_pattern_ack_moves_group_until_refire():
    alerts = [_alert("TOKEN_BLOAT", last="2026-10-31 12:00:00 UTC")]
    acks = {"acks": [{
        "kind": "pattern",
        "code": "TOKEN_BLOAT",
        "identity": None,
        "acked_at": "2026-10-31T12:00:00Z",
        "last_seen_at_ack": "2026-10-31 12:00:00 UTC",
        "issue_url": None,
    }]}
    hud = group_workspace_sentinel_alerts(alerts, acks)
    assert hud["groups"] == []
    assert hud["acked"][0]["code"] == "TOKEN_BLOAT"
    later = [_alert("TOKEN_BLOAT", last="2026-10-31 12:05:00 UTC")]
    hud2 = group_workspace_sentinel_alerts(later, acks)
    assert hud2["groups"][0]["code"] == "TOKEN_BLOAT"
    assert hud2["acked"] == []


def test_acks_are_per_file(tmp_path):
    a = tmp_path / "a.json"
    b = tmp_path / "b.json"
    save_sentinel_ack(str(a), {
        "kind": "pattern", "code": "X", "identity": None,
        "acked_at": "t", "last_seen_at_ack": "t", "issue_url": None,
    }, slug="one")
    assert load_sentinel_acks(str(b))["acks"] == []
    assert load_sentinel_acks(str(a))["slug"] == "one"
```

`save_sentinel_ack(path, row, slug=)` upserts into `acks` (occurrence: match identity; pattern: match code+kind), writes `version: 1`.

- [ ] **Step 2: Implement + pytest pass + commit**

```bash
git commit -m "feat: persist Vizor sentinel acks in workspace sidecar"
```

Never write `sentinel.md` from these functions.

### Task 5: POST ack + POST issue

**Files:**
- Modify: `synlynk/vizor_daemon.py`
- Modify: `synlynk/viz/write_routes.py`
- Modify: `tests/test_viz_write_path_table.py` (`required` adds `"sentinel/ack"`, `"sentinel/issue"`)
- Test: `tests/test_viz_sentinel_hud.py`

- [ ] **Step 1: Tests**

Use the same `HTTPServer` + `build_workspace_routing_handler` pattern as `tests/test_vizor_daemon_stream.py`. Registry workspace `acme` with a repo that has `.synlynk/sentinel.md`.

1. `POST /w/acme/api/sentinel/ack` without token → 401 or 403; sidecar absent.
2. With `X-Synlynk-Token` matching `ensure_local_token()`, body `{"scope":"pattern","code":"VIZOR_DAEMON_DOWN"}` → 200 `{"ok": true}` and sidecar contains that pattern.
3. `GET /w/acme/api/sentinel` then shows the group under `acked`.
4. `POST /w/acme/api/sentinel/issue` with token: monkeypatch a helper `raise_sentinel_issue(slug, hud_group)` that you add in `data.py` to call `synlynk gh --role support -- issue create --title … --body …` via `subprocess.run`. Assert argv contains `--role` and `support`, env does not contain `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH`. Fake return `https://github.com/nikhilsoman/synlynk/issues/1`. Response has `issue_url`. Sidecar stores it.
5. `WRITE_ROUTES["sentinel/ack"] == "keep"` and `["sentinel/issue"] == "keep"`.

Issue title: `[support] sentinel: <CODE> (n)`. Body: slug, code, severity, first/last, count, up to 20 `raw_line`s. Cap. Do not dump unbounded lines.

`raise_sentinel_issue` must not set host-auth. Use `synlynk.gh_cli` if a wrapper already exists; otherwise `subprocess.run` on the `synlynk` binary with `--role support`.

- [ ] **Step 2: Daemon routes**

After the GET `sentinel` branch, handle:

- `api_route == "sentinel/ack"` POST: parse JSON, `scope` in `{occurrence, pattern}`, require `identity` for occurrence, `save_sentinel_ack` under `ctx.repo_path`, 200.
- `api_route == "sentinel/issue"` POST: build group from current alerts, call `raise_sentinel_issue`, on failure 502 `{"ok": false, "error": "gh_failed"}` and **do not ack**. On success save ack with `issue_url`.

Auth is already at `do_POST`. Do not re-compare the token.

- [ ] **Step 3: Commit**

```bash
git commit -m "feat: ack and raise Vizor sentinel issues via workspace API"
```

### Task 6: Overview CTAs + Investigate copy

**Files:**
- Modify: `synlynk/viz/overview.py`
- Test: `tests/test_viz_sentinel_hud.py`

- [ ] **Step 1: Tests**

```python
def test_overview_ctas_and_investigate_copy():
    html = generate_overview_html({...one group...}, 33333)
    assert "Ignore" in html
    assert "Raise issue" in html
    assert "Investigate" in html
    assert "Inspect" in html
    assert "api/sentinel/ack" in html
    assert "api/sentinel/issue" in html
    assert "fetch('/" not in html  # no site-root
    assert "navigator.clipboard" in html
    assert "reproduce" not in html.lower()
    inline = html.split("<script>", 1)[-1]
    assert "shell" not in inline.lower()
```

Add `investigate_brief(slug, group) -> dict` in `data.py` as specified (cap 20). Unit-test it has no `shell` key.

PR2 **does** add `fetch('api/sentinel/ack'` relative. Update `test_overview_inspection_is_read_only`: drop `assert "fetch(" not in inline`. Keep no `/api/sentinel/clear`, no `>Run<`, no `method="post"` form (fetch is fine). Keep inspect fields.

- [ ] **Step 2: Wire buttons**

Group header and each member: Inspect (existing panel), Ignore, Raise issue, Investigate.

Relative URLs: `api/sentinel/ack` and `api/sentinel/issue` (same pattern as Gantt `api/note`). Send `X-Synlynk-Token` the same way other Vizor writes already send it (copy the Gantt note fetch header helper if present; if Overview has no token helper, read ` synlynk/viz/gantt.py` `fetch('api/note'` and match it).

Investigate: `navigator.clipboard.writeText(JSON.stringify(brief, null, 2))`. Brief built in JS from the snapshot group, matching `investigate_brief`.

After successful Ignore/Raise, `GET api/sentinel` or rebuild from response — simplest: `location.reload()` is acceptable; prefer applying returned hud if the POST returns it.

- [ ] **Step 3: Full pytest subset + commit + PR**

```bash
/opt/homebrew/bin/python3 -m pytest tests/test_viz_sentinel_hud.py tests/test_vizor_daemon_stream.py tests/test_viz_write_path_table.py tests/test_vizor_write_routes.py tests/test_viz_nav.py -q
git commit -m "feat: Overview sentinel Ignore, Raise issue, and Investigate copy"
```

Open PR, link #2672. Do not merge from the implementer job.

---

## Spec coverage

| Spec section | Task |
|---|---|
| Group by code, collapse `count > 3` | 1, 2 |
| Inspect | 2 (existing panel) |
| SSE grouped | 3 |
| GET `/w/<slug>/api/sentinel` | 3 |
| Sidecar path, corrupt=empty, per-slug | 4 |
| Occurrence / pattern ack, refire | 4, 5 |
| Raise issue role support | 5 |
| Investigate copy-only | 6 |
| WRITE_ROUTES keep | 5 |
| No sentinel.md rewrite, no VERSION | all |
| authorize_local_request single site | 5 |

---

## Dispatch (conductor)

1. Land this plan + accepted spec (docs PR) on `main` via qa merge.
2. Grok PR1 from `origin/main`.
3. After PR1 merge: Codex PR2.
4. qa Agy `gemini-3.8-flash-high` merges each product PR. Architect reviews if sidecar-vs-`state.db` is challenged.
