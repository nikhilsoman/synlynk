# Federated Quota Capture Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture each harness's real subscription-quota percent at task boundaries and from a daemon poller, store it in `quota_snapshots`, and let `synlynk quota federated` plus dispatch defaults see who has headroom.

**Architecture:** Migration 20 adds `quota_snapshots` beside `cost_entries`. `synlynk/quota_capture.py` owns the registry, the four parsers, the async boundary capture, the daemon poller, the staleness/calibrate fallback, and the federated read model. `exec_command` and `_settle_daemon_job_terminal` only schedule a daemon thread. `_infer_dispatch_defaults` consults weekly headroom when the caller did not pin a harness. `harness_quotas` and `cost_entries` stay the manual-calibration and dollar ledgers; this plan does not merge them.

**Tech Stack:** Python 3 stdlib, SQLite via the existing migration runner (`synlynk/migrations`, next version 20), pytest, the `herdr` CLI (`pane send-text` / `pane send-keys`).

**Spec:** `docs/superpowers/specs/2026-10-10-federated-quota-capture-design.md` (commit `a90722bd`).

## Locked decisions

These close gaps between two sentences in the spec. Implement them as written.

1. **`staleness_seconds` on a `task_boundary` row is SQL NULL.** The schema comment wins over the bullet that says `0`. Poller rows store the age, in whole seconds, of the underlying log event or CLI reading at capture time. CLI readings (`claude`, `agy`) store `0`. A row is fresh when `max(now - captured_at, staleness_seconds or 0) <= 1800` (2 × the 15-minute poll interval). Older than that is `unknown`, never 0% or 100%.
2. **Routing.** When `dispatch` did not receive an explicit harness, `prefer_harness_by_weekly_headroom` looks at the incumbent plus its policy fallbacks. A harness whose **5h** reading is `known` and `used_percent >= 100` is skipped. Among the rest, the harness with the lowest **known weekly** `used_percent` wins. Equal percents keep the incumbent. If nobody has a known weekly reading, return the incumbent and do not raise. Unknown is not treated as empty or full.
3. **Stale or missing snapshot falls through to `harness_quotas`.** `used_percent = used_tokens / limit_tokens * 100` for `unit='tokens'` and `quota_type` equal to the window. That row's source is `calibrate`. No calibrate row means `unknown`.
4. **Grok has no automated 5h row.** `has_5h_window: false` means the parser never emits `5h`. A manual `synlynk quota calibrate --window 5h` row still surfaces through decision 3.
5. **Codex 5h stays absent until a bucket with `window_minutes == 300` appears.** `secondary: null` writes no 5h row. `window_minutes == 10080` is weekly. Any other `window_minutes` is ignored.
6. **Agy collapses to one percent per window:** the max `used` across model-family blocks. The table is per harness, not per family. Claude's weekly percent is only the `Current week (all models)` block. `Current week (Sonnet only)` is ignored.
7. **Codex file selection.** Walk `~/.codex/sessions/**/rollout-*.jsonl` in descending mtime and stop at the first file that contains a `payload.rate_limits` object. Inside that file, keep the last such object. That is the rollout the task just wrote. Do not spawn a process.
8. **Grok pane refresh.** Only when `interactive_pane_id` is set and the newest `billing: fetched credits config` line is missing or older than 900 seconds. Commands, in order: `herdr pane send-text <pane_id> /usage`, then `herdr pane send-keys <pane_id> Enter`, then wait `GROK_REFRESH_WAIT_SECONDS` (2) and re-read the log. A null pane id never calls `herdr`. A failed `herdr` call is logged and the existing line, if any, is still recorded. This product call is not gated on `HERDR_ENV`; the daemon is not inside the pane it drives.
9. **Unregistered harnesses** (`muse`, anything absent from the registry) never get a capture row. Routing still will not raise. Their federated status is `unknown` unless a calibrate row exists.
10. **Registry file.** The shipped default lives in code and matches the spec's JSON, including `"has_5h_window": "unknown"` for Codex. `.synlynk/quota_capture.json`, when present, replaces entries by harness name. Absent harnesses are not captured. Do not put this map in `policy.json`.

## File map

| File | Responsibility |
|---|---|
| `synlynk/migrations/m0020_quota_snapshots.py` | Create `quota_snapshots` and its lookup index |
| `synlynk/migrations/runner.py` | Register migration 20 |
| `synlynk/quota_capture.py` | Registry, parsers, writer, staleness, boundary thread, poller, federated view, routing helper |
| `synlynk/dispatch.py` | Schedule capture at the end of `exec_command`; consult headroom in `_infer_dispatch_defaults` |
| `synlynk/jobs.py` | Schedule capture when `_settle_daemon_job_terminal` commits `done` |
| `synlynk/daemon.py` | Call `poll_once` from `SynlynkDaemon._run_loop` |
| `synlynk/cli.py` | `synlynk quota federated` |
| `synlynk/taxonomy.py` | Taxonomy leaf for the new command |
| `AI_INSTRUCTIONS.md` | Trigger phrase for the new command |
| `docs/reference/commands.md`, `README.md` | Regenerated command docs |
| `tests/test_federated_quota_capture.py` | All tests for this feature |
| `docs/blog/266-prTBD-federated-quota-capture.md` | Blog post written when the PR opens |

`synlynk/quota.py` is not modified. `cmd_quota` / `calibrate_and_update_quota` keep owning `harness_quotas`.

## Out of scope

Herdr-as-a-bundled-dependency, creating per-harness Herdr panes, and any change to `cost_entries` dollar accounting. With every `interactive_pane_id` left `null`, Grok's automated weekly refresh does not run and the federated view reports Grok weekly as `unknown` until a pane id is configured or someone calibrates.

---

### Task 1: `quota_snapshots` table

**Files:**
- Create: `synlynk/migrations/m0020_quota_snapshots.py`
- Modify: `synlynk/migrations/runner.py`
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Create `tests/test_federated_quota_capture.py`:

```python
import sqlite3

import pytest


def test_migration_0020_creates_quota_snapshots(tmp_path, monkeypatch):
    from synlynk.migrations import runner
    from synlynk.migrations.m0020_quota_snapshots import MIGRATION

    conn = sqlite3.connect(tmp_path / "state.db")
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA user_version = 19")
    conn.commit()
    monkeypatch.setattr(runner, "MIGRATIONS", [MIGRATION])

    runner.run_pending_migrations(conn)

    cols = {row[1]: row for row in conn.execute("PRAGMA table_info(quota_snapshots)")}
    assert set(cols) == {
        "id", "harness", "window", "used_percent", "resets_at",
        "captured_at", "source", "staleness_seconds", "job_id",
    }
    assert cols["harness"][3] == 1  # NOT NULL
    assert cols["used_percent"][3] == 1
    assert cols["resets_at"][3] == 0
    assert cols["staleness_seconds"][3] == 0
    assert cols["job_id"][3] == 0
    indexes = {
        row[1]
        for row in conn.execute("PRAGMA index_list(quota_snapshots)")
    }
    assert "idx_quota_snapshots_harness_window" in indexes
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20

    runner.run_pending_migrations(conn)
    assert conn.execute("PRAGMA user_version").fetchone()[0] == 20
    conn.close()


def test_runner_registry_includes_migration_20_in_order():
    from synlynk.migrations.runner import MIGRATIONS

    versions = [item.version for item in MIGRATIONS]
    assert versions == [16, 17, 18, 19, 20]
    assert MIGRATIONS[-1].name == "quota_snapshots"
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_migration_0020_creates_quota_snapshots tests/test_federated_quota_capture.py::test_runner_registry_includes_migration_20_in_order -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.migrations.m0020_quota_snapshots'`

- [ ] **Step 3: Write the minimal implementation**

Create `synlynk/migrations/m0020_quota_snapshots.py`:

```python
"""Migration 20: subscription-quota snapshots, separate from cost_entries."""
import sqlite3

from synlynk.migrations import Migration


def _up(conn: sqlite3.Connection) -> None:
    conn.execute(
        """CREATE TABLE IF NOT EXISTS quota_snapshots (
            id INTEGER PRIMARY KEY,
            harness TEXT NOT NULL,
            window TEXT NOT NULL,
            used_percent REAL NOT NULL,
            resets_at TEXT,
            captured_at TEXT NOT NULL,
            source TEXT NOT NULL,
            staleness_seconds INTEGER,
            job_id TEXT
        )"""
    )
    conn.execute(
        """CREATE INDEX IF NOT EXISTS idx_quota_snapshots_harness_window
           ON quota_snapshots(harness, window, captured_at, id)"""
    )


MIGRATION = Migration(version=20, name="quota_snapshots", up=_up)
```

In `synlynk/migrations/runner.py`, add the import next to `M0019` and append `M0020` to `MIGRATIONS`:

```python
from synlynk.migrations.m0020_quota_snapshots import MIGRATION as M0020

MIGRATIONS: list[Migration] = [M0016, M0017, M0018, M0019, M0020]
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_migration_0020_creates_quota_snapshots tests/test_federated_quota_capture.py::test_runner_registry_includes_migration_20_in_order -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/migrations/m0020_quota_snapshots.py synlynk/migrations/runner.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: add quota_snapshots table

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 2: Capture registry

**Files:**
- Create: `synlynk/quota_capture.py`
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Append to `tests/test_federated_quota_capture.py`:

```python
def test_default_registry_matches_the_spec():
    from synlynk.quota_capture import DEFAULT_POLL_INTERVAL_SECONDS, load_registry

    registry = load_registry(repo_path="/nonexistent/quota-capture-repo")
    assert DEFAULT_POLL_INTERVAL_SECONDS == 900
    assert registry["claude"]["cli_usage_cmd"] == 'claude -p "/usage" --output-format text'
    assert registry["claude"]["log_scrape"] is None
    assert registry["claude"]["has_5h_window"] is True
    assert registry["claude"]["interactive_pane_id"] is None
    assert registry["agy"]["cli_usage_cmd"] == 'agy -p "/usage" --output-format text'
    assert registry["agy"]["has_5h_window"] is True
    assert registry["codex"]["cli_usage_cmd"] is None
    assert registry["codex"]["log_scrape"] == {
        "path": "~/.codex/sessions/**/*.jsonl",
        "jq_filter": ".payload.rate_limits",
    }
    assert registry["codex"]["has_5h_window"] == "unknown"
    assert registry["grok"]["cli_usage_cmd"] is None
    assert registry["grok"]["has_5h_window"] is False
    assert registry["grok"]["log_scrape"]["path"] == "~/.grok/logs/unified.jsonl"
    assert registry["grok"]["log_scrape"]["jq_filter"] == 'select(.msg == "billing: fetched credits config")'
    assert "muse" not in registry


def test_repo_overlay_replaces_one_harness(tmp_path):
    from synlynk.quota_capture import load_registry

    syn = tmp_path / ".synlynk"
    syn.mkdir()
    (syn / "quota_capture.json").write_text(
        '{"grok": {"cli_usage_cmd": null, "log_scrape": {"path": "~/.grok/logs/unified.jsonl",'
        ' "jq_filter": "select(.msg == \\"billing: fetched credits config\\")"},'
        ' "has_5h_window": false, "interactive_pane_id": "pane-grok"}}'
    )
    registry = load_registry(repo_path=str(tmp_path))
    assert registry["grok"]["interactive_pane_id"] == "pane-grok"
    assert registry["claude"]["cli_usage_cmd"].startswith("claude ")
    assert "muse" not in registry
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_default_registry_matches_the_spec tests/test_federated_quota_capture.py::test_repo_overlay_replaces_one_harness -v`

Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.quota_capture'`

- [ ] **Step 3: Write the minimal implementation**

Create `synlynk/quota_capture.py`:

```python
"""Subscription-quota capture. Dollars stay in cost_entries."""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

logger = logging.getLogger("synlynk.quota_capture")

DEFAULT_POLL_INTERVAL_SECONDS = 900
STALENESS_MULTIPLIER = 2
GROK_REFRESH_WAIT_SECONDS = 2.0

DEFAULT_REGISTRY: dict[str, dict] = {
    "claude": {
        "cli_usage_cmd": 'claude -p "/usage" --output-format text',
        "log_scrape": None,
        "has_5h_window": True,
        "interactive_pane_id": None,
    },
    "agy": {
        "cli_usage_cmd": 'agy -p "/usage" --output-format text',
        "log_scrape": None,
        "has_5h_window": True,
        "interactive_pane_id": None,
    },
    "codex": {
        "cli_usage_cmd": None,
        "log_scrape": {
            "path": "~/.codex/sessions/**/*.jsonl",
            "jq_filter": ".payload.rate_limits",
        },
        "has_5h_window": "unknown",
        "interactive_pane_id": None,
    },
    "grok": {
        "cli_usage_cmd": None,
        "log_scrape": {
            "path": "~/.grok/logs/unified.jsonl",
            "jq_filter": 'select(.msg == "billing: fetched credits config")',
        },
        "has_5h_window": False,
        "interactive_pane_id": None,
    },
}


def load_registry(repo_path: str | None = None) -> dict[str, dict]:
    """Return the spec default, with a per-harness replace from quota_capture.json."""
    registry = json.loads(json.dumps(DEFAULT_REGISTRY))
    root = Path(repo_path) if repo_path is not None else Path.cwd()
    overlay_path = root / ".synlynk" / "quota_capture.json"
    if not overlay_path.is_file():
        return registry
    try:
        overlay = json.loads(overlay_path.read_text())
    except (OSError, json.JSONDecodeError):
        logger.exception("ignoring unreadable quota capture overlay %s", overlay_path)
        return registry
    if not isinstance(overlay, dict):
        return registry
    for harness, entry in overlay.items():
        if harness == "poll_interval_seconds" or not isinstance(entry, dict):
            continue
        registry[harness] = entry
    return registry
```

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_default_registry_matches_the_spec tests/test_federated_quota_capture.py::test_repo_overlay_replaces_one_harness -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: add the per-harness quota capture registry

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 3: Per-harness parsers

**Files:**
- Modify: `synlynk/quota_capture.py`
- Test: `tests/test_federated_quota_capture.py`

Samples below are the live shapes from 2026-10-10: Codex `payload.rate_limits` in `~/.codex/sessions/2026/10/10/rollout-2026-10-10T11-46-03-01a12474-48bc-7a42-ac42-d35ec1ddcbd7.jsonl`, and a Grok `unified.jsonl` billing line (`creditUsagePercent` 22.0 in the live file; the spec's research sample was 21.0 — the fixture uses 21.0 as the spec recorded, with the live object shape). Claude headings are the strings in the Claude Code binary: `Current session`, `Current week (all models)`, `Current week (Sonnet only)`.

- [ ] **Step 1: Write the failing test**

Append:

```python
CLAUDE_USAGE = """\
Current session
12% used
Resets 4:30pm (America/Los_Angeles)

Current week (all models)
98% used
Resets 2026-10-12T15:30:00Z

Current week (Sonnet only)
40% used
Resets 2026-10-12T15:30:00Z
"""

AGY_USAGE = """\
Gemini 3 Pro
Current session
8% used

Current week
15% used

Claude
Current session
3% used

Current week
22% used
"""

CODEX_RATE_LIMITS = {
    "plan_type": "plus",
    "primary": {"used_percent": 14.0, "window_minutes": 10080, "resets_at": 1791953738},
    "secondary": None,
}

GROK_BILLING = {
    "ts": "2026-10-10T07:04:04.780Z",
    "src": "shell",
    "lvl": "info",
    "msg": "billing: fetched credits config",
    "ctx": {
        "config": {
            "creditUsagePercent": 21.0,
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "start": "2026-10-07T03:27:47.938919+00:00",
                "end": "2026-10-14T03:27:47.938919+00:00",
            },
        }
    },
}


def test_parse_claude_usage_text_keeps_session_and_all_models_week():
    from synlynk.quota_capture import parse_claude_usage_text

    readings = {item.window: item for item in parse_claude_usage_text(CLAUDE_USAGE)}
    assert set(readings) == {"5h", "weekly"}
    assert readings["5h"].used_percent == 12.0
    assert readings["5h"].resets_at is None
    assert readings["weekly"].used_percent == 98.0
    assert readings["weekly"].resets_at == "2026-10-12T15:30:00Z"


def test_parse_agy_usage_text_uses_the_max_family_percent():
    from synlynk.quota_capture import parse_agy_usage_text

    readings = {item.window: item for item in parse_agy_usage_text(AGY_USAGE)}
    assert readings["5h"].used_percent == 8.0
    assert readings["weekly"].used_percent == 22.0


def test_parse_codex_rate_limits_weekly_only_when_secondary_is_null():
    from synlynk.quota_capture import parse_codex_rate_limits

    readings = parse_codex_rate_limits(CODEX_RATE_LIMITS, observed_at="2026-10-10T06:16:10.058Z")
    assert len(readings) == 1
    assert readings[0].window == "weekly"
    assert readings[0].used_percent == 14.0
    assert readings[0].resets_at == "2026-10-14T04:55:38Z"
    assert readings[0].observed_at == "2026-10-10T06:16:10.058Z"


def test_parse_codex_rate_limits_maps_300_minutes_to_5h():
    from synlynk.quota_capture import parse_codex_rate_limits

    payload = {
        "primary": {"used_percent": 14.0, "window_minutes": 10080, "resets_at": 1791953738},
        "secondary": {"used_percent": 40.0, "window_minutes": 300, "resets_at": 1791400000},
    }
    windows = {item.window: item.used_percent for item in parse_codex_rate_limits(payload, "2026-10-10T00:00:00Z")}
    assert windows == {"weekly": 14.0, "5h": 40.0}


def test_parse_codex_ignores_unknown_window_minutes():
    from synlynk.quota_capture import parse_codex_rate_limits

    payload = {"primary": {"used_percent": 5.0, "window_minutes": 60, "resets_at": 1}, "secondary": None}
    assert parse_codex_rate_limits(payload, "2026-10-10T00:00:00Z") == []


def test_parse_grok_billing_line_is_weekly_only():
    from synlynk.quota_capture import parse_grok_billing_line

    readings = parse_grok_billing_line(GROK_BILLING)
    assert len(readings) == 1
    assert readings[0].window == "weekly"
    assert readings[0].used_percent == 21.0
    assert readings[0].resets_at == "2026-10-14T03:27:47.938919+00:00"
    assert readings[0].observed_at == "2026-10-10T07:04:04.780Z"
    assert parse_grok_billing_line({"msg": "something else"}) == []
```

`1791953738` UTC formats as `2026-10-14T04:55:38Z`. That string is already the assertion above.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_parse_claude_usage_text_keeps_session_and_all_models_week tests/test_federated_quota_capture.py::test_parse_agy_usage_text_uses_the_max_family_percent tests/test_federated_quota_capture.py::test_parse_codex_rate_limits_weekly_only_when_secondary_is_null tests/test_federated_quota_capture.py::test_parse_codex_rate_limits_maps_300_minutes_to_5h tests/test_federated_quota_capture.py::test_parse_codex_ignores_unknown_window_minutes tests/test_federated_quota_capture.py::test_parse_grok_billing_line_is_weekly_only -v`

Expected: FAIL with `ImportError: cannot import name 'parse_claude_usage_text'`

- [ ] **Step 3: Write the minimal implementation**

Append to `synlynk/quota_capture.py`:

```python
import re
from dataclasses import dataclass
from datetime import datetime, timezone

_PERCENT_USED = re.compile(r"^\s*(\d+(?:\.\d+)?)%\s*used\s*$", re.IGNORECASE)
_ISO_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})")


@dataclass(frozen=True)
class WindowReading:
    window: str
    used_percent: float
    resets_at: str | None
    observed_at: str


def _resets_from_line(line: str) -> str | None:
    match = _ISO_STAMP.search(line)
    return match.group(0) if match else None


def _parse_headed_usage(text: str, *, collapse_max: bool, weekly_requires_all_models: bool) -> list[WindowReading]:
    current: str | None = None
    found: dict[str, WindowReading] = {}
    pending_resets: dict[str, str | None] = {}
    for raw in text.splitlines():
        line = raw.strip()
        lowered = line.lower()
        if lowered.startswith("current session"):
            current = "5h"
            continue
        if lowered.startswith("current week"):
            if weekly_requires_all_models and "all models" not in lowered:
                current = None
            else:
                current = "weekly"
            continue
        if current is None:
            continue
        percent = _PERCENT_USED.match(line)
        if percent:
            used = float(percent.group(1))
            reading = WindowReading(current, used, pending_resets.get(current), "")
            previous = found.get(current)
            if previous is None or (collapse_max and used >= previous.used_percent) or not collapse_max:
                found[current] = reading
            continue
        if lowered.startswith("resets"):
            stamp = _resets_from_line(line)
            pending_resets[current] = stamp
            if current in found and stamp:
                prev = found[current]
                found[current] = WindowReading(prev.window, prev.used_percent, stamp, prev.observed_at)
    return list(found.values())


def parse_claude_usage_text(text: str) -> list[WindowReading]:
    return _parse_headed_usage(text, collapse_max=False, weekly_requires_all_models=True)


def parse_agy_usage_text(text: str) -> list[WindowReading]:
    return _parse_headed_usage(text, collapse_max=True, weekly_requires_all_models=False)


def _unix_to_iso(value: object) -> str | None:
    if not isinstance(value, (int, float)):
        return None
    return datetime.fromtimestamp(int(value), tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_codex_rate_limits(rate_limits: dict, observed_at: str) -> list[WindowReading]:
    readings: list[WindowReading] = []
    if not isinstance(rate_limits, dict):
        return readings
    for bucket_name in ("primary", "secondary"):
        bucket = rate_limits.get(bucket_name)
        if not isinstance(bucket, dict):
            continue
        minutes = bucket.get("window_minutes")
        if minutes == 10080:
            window = "weekly"
        elif minutes == 300:
            window = "5h"
        else:
            continue
        used = bucket.get("used_percent")
        if used is None:
            continue
        readings.append(
            WindowReading(window, float(used), _unix_to_iso(bucket.get("resets_at")), observed_at)
        )
    return readings


def parse_grok_billing_line(obj: dict) -> list[WindowReading]:
    if not isinstance(obj, dict) or obj.get("msg") != "billing: fetched credits config":
        return []
    config = (obj.get("ctx") or {}).get("config") or {}
    period = config.get("currentPeriod") or {}
    if period.get("type") != "USAGE_PERIOD_TYPE_WEEKLY":
        return []
    used = config.get("creditUsagePercent")
    observed = obj.get("ts")
    if used is None or not isinstance(observed, str):
        return []
    end = period.get("end")
    resets = end if isinstance(end, str) else None
    return [WindowReading("weekly", float(used), resets, observed)]
```

The Claude parser must attach a reset stamp that appears on the line **after** the percent. The loop above stores `Resets` onto an already-seen window. Confirm Task 3's Claude test passes with that order (`98% used` then `Resets 2026-10-12T15:30:00Z`). The 5h block's reset line has no ISO stamp, so `resets_at` stays `None`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k parse -v`

Expected: PASS for every `test_parse_*` test.

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: parse claude, agy, codex, and grok quota readings

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 4: Snapshots, staleness, and the federated read model

**Files:**
- Modify: `synlynk/quota_capture.py`
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def _snapshots_db():
    conn = sqlite3.connect(":memory:")
    conn.row_factory = sqlite3.Row
    from synlynk.migrations.m0020_quota_snapshots import MIGRATION
    MIGRATION.up(conn)
    conn.execute(
        """CREATE TABLE harness_quotas (
            id INTEGER PRIMARY KEY,
            harness TEXT NOT NULL,
            track TEXT NOT NULL DEFAULT 'default',
            model TEXT NOT NULL DEFAULT 'unknown',
            quota_type TEXT NOT NULL,
            unit TEXT NOT NULL DEFAULT 'tokens',
            limit_tokens INTEGER NOT NULL,
            used_tokens INTEGER NOT NULL DEFAULT 0,
            reset_at TEXT,
            updated_at TEXT
        )"""
    )
    conn.execute(
        """CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY,
            session_date TEXT NOT NULL,
            agent TEXT,
            harness TEXT,
            total_cost_usd REAL,
            cost_source TEXT NOT NULL
        )"""
    )
    return conn


def test_task_boundary_insert_stores_null_staleness_and_job_id():
    from synlynk.quota_capture import WindowReading, insert_snapshots

    conn = _snapshots_db()
    count = insert_snapshots(
        conn,
        "claude",
        [WindowReading("weekly", 98.0, "2026-10-12T15:30:00Z", "2026-10-10T00:00:00Z"),
         WindowReading("5h", 12.0, None, "2026-10-10T00:00:00Z")],
        source="task_boundary",
        job_id="job-1",
        captured_at="2026-10-10T01:00:00+00:00",
        staleness_by_window={"weekly": 999, "5h": 999},
    )
    conn.commit()
    assert count == 2
    rows = conn.execute(
        "SELECT window, used_percent, source, staleness_seconds, job_id FROM quota_snapshots ORDER BY window"
    ).fetchall()
    assert rows[0]["window"] == "5h"
    assert rows[0]["staleness_seconds"] is None
    assert rows[0]["job_id"] == "job-1"
    assert rows[1]["window"] == "weekly"
    assert rows[1]["used_percent"] == 98.0
    assert rows[1]["source"] == "task_boundary"


def test_stale_snapshot_is_unknown_until_calibrate_fallback():
    from datetime import datetime, timezone
    from synlynk.quota_capture import insert_snapshots, window_status, WindowReading

    conn = _snapshots_db()
    insert_snapshots(
        conn, "claude",
        [WindowReading("weekly", 10.0, None, "2026-10-01T00:00:00Z")],
        source="poller", job_id=None,
        captured_at="2026-10-01T00:00:00+00:00",
        staleness_by_window={"weekly": 0},
    )
    now = datetime(2026, 10, 10, tzinfo=timezone.utc)
    status = window_status(conn, "claude", "weekly", now=now)
    assert status["state"] == "unknown"
    assert status["reason"] == "stale"
    assert status["used_percent"] is None

    conn.execute(
        "INSERT INTO harness_quotas (harness, quota_type, unit, limit_tokens, used_tokens, updated_at)"
        " VALUES ('claude', 'weekly', 'tokens', 100, 40, '2026-10-09T00:00:00Z')"
    )
    fallback = window_status(conn, "claude", "weekly", now=now)
    assert fallback == {
        "state": "known",
        "used_percent": 40.0,
        "reason": None,
        "source": "calibrate",
        "resets_at": None,
        "captured_at": None,
    }


def test_fresh_poller_row_with_old_log_age_is_unknown():
    from datetime import datetime, timezone
    from synlynk.quota_capture import insert_snapshots, window_status, WindowReading

    conn = _snapshots_db()
    insert_snapshots(
        conn, "codex",
        [WindowReading("weekly", 14.0, None, "2026-10-01T00:00:00Z")],
        source="poller", job_id=None,
        captured_at="2026-10-10T00:00:00+00:00",
        staleness_by_window={"weekly": 90000},
    )
    status = window_status(conn, "codex", "weekly", now=datetime(2026, 10, 10, 0, 0, tzinfo=timezone.utc))
    assert status["state"] == "unknown"
    assert status["reason"] == "stale"


def test_missing_snapshot_is_unknown_not_zero():
    from datetime import datetime, timezone
    from synlynk.quota_capture import window_status

    conn = _snapshots_db()
    status = window_status(conn, "grok", "5h", now=datetime(2026, 10, 10, tzinfo=timezone.utc))
    assert status["state"] == "unknown"
    assert status["used_percent"] is None
    assert status["reason"] == "missing"


def test_federated_rows_include_registry_gaps_and_seven_day_cost():
    from datetime import datetime, timezone
    from synlynk.quota_capture import federated_rows, insert_snapshots, WindowReading

    conn = _snapshots_db()
    insert_snapshots(
        conn, "claude",
        [WindowReading("weekly", 98.0, "2026-10-12T15:30:00Z", "2026-10-10T00:00:00Z")],
        source="task_boundary", job_id="job-9",
        captured_at="2026-10-10T00:30:00+00:00",
        staleness_by_window={},
    )
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, harness, total_cost_usd, cost_source)"
        " VALUES ('2026-10-09', 'claude', 'claude', 4.5, 'actual'),"
        "        ('2026-10-01', 'claude', 'claude', 100, 'actual')"
    )
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    rows = {(row["harness"], row["window"]): row for row in federated_rows(conn, now=now)}
    assert rows[("claude", "weekly")]["state"] == "known"
    assert rows[("claude", "weekly")]["used_percent"] == 98.0
    assert rows[("claude", "weekly")]["cost_7d_usd"] == 4.5
    assert rows[("claude", "5h")]["state"] == "unknown"
    assert rows[("grok", "weekly")]["state"] == "unknown"
    assert rows[("grok", "5h")]["state"] == "unknown"
    assert rows[("codex", "5h")]["state"] == "unknown"
    assert ("muse", "weekly") not in rows


def test_format_federated_text_names_unknown_grok():
    from synlynk.quota_capture import format_federated_text

    text = format_federated_text([
        {"harness": "grok", "window": "weekly", "state": "unknown", "used_percent": None,
         "source": None, "resets_at": None, "captured_at": None, "cost_7d_usd": 0.0, "reason": "missing"},
    ])
    assert "grok" in text
    assert "weekly" in text
    assert "unknown" in text
    assert "0%" not in text
    assert "100%" not in text
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k "insert or stale or missing_snapshot or federated_rows or format_federated" -v`

Expected: FAIL with `ImportError: cannot import name 'insert_snapshots'`

- [ ] **Step 3: Write the minimal implementation**

Append to `synlynk/quota_capture.py`:

```python
def insert_snapshots(
    conn,
    harness: str,
    readings: list[WindowReading],
    *,
    source: str,
    job_id: str | None,
    captured_at: str,
    staleness_by_window: dict[str, int],
) -> int:
    by_window: dict[str, WindowReading] = {}
    for reading in readings:
        if reading.window not in {"5h", "weekly"}:
            continue
        by_window[reading.window] = reading
    for window, reading in by_window.items():
        staleness = None if source == "task_boundary" else int(staleness_by_window.get(window, 0))
        conn.execute(
            """INSERT INTO quota_snapshots
               (harness, window, used_percent, resets_at, captured_at, source, staleness_seconds, job_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (harness, window, reading.used_percent, reading.resets_at, captured_at, source, staleness, job_id),
        )
    return len(by_window)


def _parse_iso(value: str) -> datetime:
    text = value.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(text)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def effective_age_seconds(row, now: datetime) -> float:
    captured = _parse_iso(row["captured_at"])
    age = (now - captured).total_seconds()
    extra = row["staleness_seconds"]
    if extra is None:
        return max(0.0, age)
    return max(0.0, age, float(extra))


def _latest_snapshot(conn, harness: str, window: str):
    try:
        return conn.execute(
            """SELECT harness, window, used_percent, resets_at, captured_at, source, staleness_seconds, job_id
                 FROM quota_snapshots
                WHERE lower(harness) = lower(?) AND window = ?
                ORDER BY captured_at DESC, id DESC
                LIMIT 1""",
            (harness, window),
        ).fetchone()
    except Exception:
        return None


def _calibrate_percent(conn, harness: str, window: str) -> float | None:
    try:
        row = conn.execute(
            """SELECT used_tokens, limit_tokens FROM harness_quotas
                WHERE lower(harness) = lower(?) AND quota_type = ? AND unit = 'tokens'
                  AND limit_tokens > 0
                ORDER BY updated_at DESC
                LIMIT 1""",
            (harness, window),
        ).fetchone()
    except Exception:
        return None
    if row is None:
        return None
    return (float(row["used_tokens"]) / float(row["limit_tokens"])) * 100.0


def window_status(conn, harness: str, window: str, *, now: datetime, registry: dict | None = None) -> dict:
    threshold = DEFAULT_POLL_INTERVAL_SECONDS * STALENESS_MULTIPLIER
    row = _latest_snapshot(conn, harness, window)
    if row is not None and effective_age_seconds(row, now) <= threshold:
        return {
            "state": "known",
            "used_percent": float(row["used_percent"]),
            "reason": None,
            "source": row["source"],
            "resets_at": row["resets_at"],
            "captured_at": row["captured_at"],
        }
    calibrated = _calibrate_percent(conn, harness, window)
    if calibrated is not None:
        return {
            "state": "known",
            "used_percent": calibrated,
            "reason": None,
            "source": "calibrate",
            "resets_at": None,
            "captured_at": None,
        }
    reason = "stale" if row is not None else "missing"
    return {
        "state": "unknown",
        "used_percent": None,
        "reason": reason,
        "source": None,
        "resets_at": None,
        "captured_at": None,
    }


def weekly_cost_usd(conn, harness: str, *, now: datetime) -> float:
    start = (now.date()).isoformat()
    # 7 calendar days inclusive of `now`'s date, exclusive of the day 7 days prior.
    from datetime import timedelta
    cutoff = (now.date() - timedelta(days=6)).isoformat()
    try:
        row = conn.execute(
            """SELECT COALESCE(SUM(total_cost_usd), 0)
                 FROM cost_entries
                WHERE session_date >= ?
                  AND (lower(COALESCE(harness, agent)) = lower(?))""",
            (cutoff, harness),
        ).fetchone()
    except Exception:
        return 0.0
    if row is None or row[0] is None:
        return 0.0
    return float(row[0])


def federated_rows(conn, *, now: datetime | None = None, registry: dict | None = None) -> list[dict]:
    now = now or datetime.now(timezone.utc)
    registry = registry if registry is not None else load_registry()
    rows = []
    for harness in registry:
        cost = weekly_cost_usd(conn, harness, now=now)
        for window in ("weekly", "5h"):
            status = window_status(conn, harness, window, now=now, registry=registry)
            rows.append({
                "harness": harness,
                "window": window,
                "state": status["state"],
                "used_percent": status["used_percent"],
                "source": status["source"],
                "resets_at": status["resets_at"],
                "captured_at": status["captured_at"],
                "cost_7d_usd": cost,
                "reason": status["reason"],
            })
    return rows


def format_federated_text(rows: list[dict]) -> str:
    lines = ["harness  window  status   used_percent  source  cost_7d_usd  captured_at"]
    for row in rows:
        used = "—" if row["used_percent"] is None else f"{row['used_percent']:.1f}"
        source = row["source"] or "—"
        captured = row["captured_at"] or "—"
        lines.append(
            f"{row['harness']:<8} {row['window']:<7} {row['state']:<8} {used:<13} {source:<7} "
            f"{row['cost_7d_usd']:<11.2f} {captured}"
        )
    return "\n".join(lines)
```

Move `from datetime import timedelta` to the module imports instead of importing it inside `weekly_cost_usd`. Delete the inline import after adding `timedelta` to the existing `datetime` import.

The cost test's `now` is 2026-10-10, so the cutoff date is 2026-10-04. The 2026-10-09 row counts. The 2026-10-01 row does not. `cost_7d_usd == 4.5`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k "insert or stale or missing_snapshot or federated or format_federated" -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: read federated quota with a staleness fallback

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 5: Non-blocking boundary capture

**Files:**
- Modify: `synlynk/quota_capture.py`
- Modify: `synlynk/dispatch.py` (the final `return exit_code` of `exec_command`, currently just after the sentinel/drift block)
- Modify: `synlynk/jobs.py` (`_settle_daemon_job_terminal`, immediately before `return settled`)
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_boundary_capture_returns_before_the_slow_write(monkeypatch):
    import threading
    import time
    from synlynk.quota_capture import schedule_boundary_capture

    started = threading.Event()
    release = threading.Event()
    wrote = {}

    def slow_capture(harness, **kwargs):
        started.set()
        assert release.wait(2)
        wrote["harness"] = harness
        wrote["job_id"] = kwargs.get("job_id")
        wrote["source"] = kwargs.get("source")
        return 1

    monkeypatch.setattr("synlynk.quota_capture.capture_harness", slow_capture)
    monkeypatch.setattr("synlynk.quota_capture._open_db", lambda: None)

    started_at = time.perf_counter()
    thread = schedule_boundary_capture("codex", "job-77")
    elapsed = time.perf_counter() - started_at
    assert elapsed < 0.2
    assert started.wait(1)
    assert wrote == {}
    release.set()
    thread.join(2)
    assert not thread.is_alive()
    assert wrote == {"harness": "codex", "job_id": "job-77", "source": "task_boundary"}


def test_capture_harness_skips_an_unregistered_name():
    from synlynk.quota_capture import capture_harness

    class ExplodingConn:
        def execute(self, *args, **kwargs):
            raise AssertionError("unregistered harness must not write")

    assert capture_harness("muse", source="task_boundary", job_id=None, conn=ExplodingConn()) == 0


def test_exec_finished_schedules_only_registered_binaries(monkeypatch):
    from synlynk.quota_capture import on_exec_finished

    scheduled = []
    monkeypatch.setattr(
        "synlynk.quota_capture.schedule_boundary_capture",
        lambda harness, job_id: scheduled.append((harness, job_id)) or None,
    )
    on_exec_finished(["/usr/local/bin/claude", "-p", "hello"])
    on_exec_finished(["gemini", "-p", "hello"])
    on_exec_finished(["muse", "-p", "hello"])
    assert scheduled == [("claude", None), ("agy", None)]


def test_job_terminal_schedules_only_done_registered_jobs(monkeypatch):
    from synlynk.quota_capture import on_job_terminal

    scheduled = []
    monkeypatch.setattr(
        "synlynk.quota_capture.schedule_boundary_capture",
        lambda harness, job_id: scheduled.append((harness, job_id)),
    )
    on_job_terminal("codex", "job-1", "done")
    on_job_terminal("codex", "job-2", "failed")
    on_job_terminal("muse", "job-3", "done")
    assert scheduled == [("codex", "job-1")]


def test_note_exec_return_schedules_and_preserves_exit_code(monkeypatch):
    from synlynk.quota_capture import note_exec_return

    calls = []

    def boom(cmd):
        calls.append(list(cmd))
        raise RuntimeError("capture must not change the exit code")

    monkeypatch.setattr("synlynk.quota_capture.on_exec_finished", boom)
    assert note_exec_return(["claude", "-p", "hi"], exit_code=7) == 7
    assert calls == [["claude", "-p", "hi"]]


def test_note_job_settled_schedules_when_done(monkeypatch):
    from synlynk.quota_capture import note_job_settled

    calls = []
    monkeypatch.setattr(
        "synlynk.quota_capture.on_job_terminal",
        lambda harness, job_id, status: calls.append((harness, job_id, status)),
    )
    note_job_settled(settled=True, harness="grok", job_id="job-5", status="done")
    note_job_settled(settled=False, harness="grok", job_id="job-6", status="done")
    note_job_settled(settled=True, harness="grok", job_id="job-7", status="failed")
    assert calls == [("grok", "job-5", "done")]
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k "boundary_capture or unregistered or exec_finished or job_terminal or note_exec or note_job" -v`

Expected: FAIL with `ImportError: cannot import name 'schedule_boundary_capture'`

- [ ] **Step 3: Write the minimal implementation**

Append to `synlynk/quota_capture.py`:

```python
import shlex
import subprocess
import threading

def _open_db():
    from synlynk.db import _get_db
    return _get_db()


def _default_runner(argv: list[str], timeout: float) -> str:
    proc = subprocess.run(argv, capture_output=True, text=True, timeout=timeout, check=False)
    if proc.returncode != 0:
        raise RuntimeError(proc.stderr.strip() or f"exit {proc.returncode}")
    return proc.stdout


def _now_iso(now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    return current.astimezone(timezone.utc).isoformat()


def _reading_age_seconds(observed_at: str, now: datetime) -> int:
    try:
        observed = _parse_iso(observed_at)
    except ValueError:
        return 0
    return max(0, int((now - observed).total_seconds()))


def capture_cli_text(command: str, *, runner=None, timeout: float = 20) -> str:
    run = runner or _default_runner
    return run(shlex.split(command), timeout)


def _newest_codex_rate_limits(sessions_root: Path) -> tuple[dict, str] | None:
    if not sessions_root.is_dir():
        return None
    files = sorted(sessions_root.rglob("rollout-*.jsonl"), key=lambda path: path.stat().st_mtime, reverse=True)
    for path in files:
        last_payload = None
        last_ts = None
        try:
            lines = path.read_text(errors="replace").splitlines()
        except OSError:
            logger.exception("codex quota log unreadable: %s", path)
            continue
        for line in lines:
            line = line.strip()
            if not line or "rate_limits" not in line:
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                continue
            payload = obj.get("payload") if isinstance(obj, dict) else None
            rate_limits = payload.get("rate_limits") if isinstance(payload, dict) else None
            if isinstance(rate_limits, dict):
                last_payload = rate_limits
                last_ts = obj.get("timestamp")
        if last_payload is not None:
            observed = last_ts if isinstance(last_ts, str) else _now_iso()
            return last_payload, observed
    return None


def _newest_grok_billing(log_path: Path) -> dict | None:
    if not log_path.is_file():
        return None
    last = None
    try:
        lines = log_path.read_text(errors="replace").splitlines()
    except OSError:
        logger.exception("grok quota log unreadable: %s", log_path)
        return None
    for line in lines:
        if "billing: fetched credits config" not in line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            continue
        if isinstance(obj, dict) and obj.get("msg") == "billing: fetched credits config":
            last = obj
    return last


def capture_harness(
    harness: str,
    *,
    source: str,
    job_id: str | None,
    conn,
    registry: dict | None = None,
    now: datetime | None = None,
    runner=None,
) -> int:
    registry = registry if registry is not None else load_registry()
    name = (harness or "").strip().lower()
    if name == "gemini":
        name = "agy"
    entry = registry.get(name)
    if entry is None or conn is None:
        return 0
    if entry.get("has_5h_window") is False and entry.get("cli_usage_cmd") is None and not entry.get("log_scrape"):
        return 0
    current = now or datetime.now(timezone.utc)
    readings: list[WindowReading] = []
    staleness: dict[str, int] = {}
    try:
        if entry.get("cli_usage_cmd"):
            text = capture_cli_text(entry["cli_usage_cmd"], runner=runner)
            if name == "agy":
                readings = parse_agy_usage_text(text)
            else:
                readings = parse_claude_usage_text(text)
            staleness = {item.window: 0 for item in readings}
        elif name == "codex":
            scrape = entry.get("log_scrape") or {}
            configured = os.path.expanduser(scrape.get("path") or "")
            if "**" in configured:
                root = Path(configured.split("**")[0]).expanduser()
            elif configured:
                root = Path(configured).expanduser()
            else:
                root = Path(os.path.expanduser("~/.codex/sessions"))
            found = _newest_codex_rate_limits(root)
            if found is None:
                return 0
            payload, observed = found
            readings = parse_codex_rate_limits(payload, observed)
            age = _reading_age_seconds(observed, current)
            staleness = {item.window: age for item in readings}
        elif name == "grok":
            scrape = entry.get("log_scrape") or {}
            log_path = Path(os.path.expanduser(scrape.get("path") or "~/.grok/logs/unified.jsonl"))
            obj = _newest_grok_billing(log_path)
            if obj is None:
                return 0
            readings = parse_grok_billing_line(obj)
            if readings:
                age = _reading_age_seconds(readings[0].observed_at, current)
                staleness = {item.window: age for item in readings}
        else:
            return 0
    except Exception:
        logger.exception("quota capture failed for %s", name)
        return 0
    if entry.get("has_5h_window") is False:
        readings = [item for item in readings if item.window != "5h"]
    if not readings:
        return 0
    return insert_snapshots(
        conn,
        name,
        readings,
        source=source,
        job_id=job_id,
        captured_at=_now_iso(current),
        staleness_by_window=staleness,
    )


def schedule_boundary_capture(harness: str, job_id: str | None) -> threading.Thread:
    def _run() -> None:
        conn = None
        try:
            conn = _open_db()
            capture_harness(harness, source="task_boundary", job_id=job_id, conn=conn)
            if conn is not None:
                conn.commit()
        except Exception:
            logger.exception("boundary quota capture failed for %s", harness)
        finally:
            if conn is not None:
                conn.close()

    thread = threading.Thread(target=_run, name=f"quota-boundary-{harness}", daemon=True)
    thread.start()
    return thread


def _normalize_harness_name(harness: str) -> str:
    name = os.path.basename(str(harness or "")).strip().lower()
    if name == "gemini":
        return "agy"
    return name


def on_exec_finished(cmd_args: list) -> None:
    if not cmd_args:
        return
    name = _normalize_harness_name(cmd_args[0])
    if name not in load_registry():
        return
    schedule_boundary_capture(name, None)


def on_job_terminal(harness: str, job_id: str, status: str) -> None:
    if status != "done":
        return
    name = _normalize_harness_name(harness)
    if name not in load_registry():
        return
    schedule_boundary_capture(name, job_id)


def note_exec_return(cmd_args: list, exit_code: int) -> int:
    try:
        on_exec_finished(cmd_args)
    except Exception:
        logger.exception("quota boundary schedule failed")
    return exit_code


def note_job_settled(*, settled: bool, harness: str | None, job_id: str, status: str) -> None:
    if not settled or not harness or status != "done":
        return
    try:
        on_job_terminal(harness, job_id, status)
    except Exception:
        logger.exception("quota boundary schedule failed for job %s", job_id)
```

The boundary test monkeypatches `_open_db` to return `None` and replaces `capture_harness`. The thread still calls `_open_db` first, then the patched `capture_harness`, which ignores `conn`. A temp Codex sessions directory is the `log_scrape.path` value with no `**`; `capture_harness` passes that path straight to `_newest_codex_rate_limits`.

In `synlynk/dispatch.py`, import is local so a quota failure cannot import-cycle at module load. Immediately before the final `return exit_code` in `exec_command`:

```python
    from synlynk.quota_capture import note_exec_return
    return note_exec_return(cmd_args, exit_code)
```

Delete the old bare `return exit_code` that this replaces. Do not wrap the early `return 1` paths (empty argv, pre-exec gate). Those did not run a harness.

In `synlynk/jobs.py`, inside `_settle_daemon_job_terminal`, the function already has `conn`, `job_id`, `status`, and `settled`. Before `return settled`, load the harness from the row (the argument list does not include it):

```python
    if settled:
        try:
            agent_row = conn.execute(
                "SELECT agent FROM daemon_jobs WHERE job_id=?",
                (job_id,),
            ).fetchone()
            agent_name = agent_row[0] if agent_row else None
        except Exception:
            agent_name = None
        from synlynk.quota_capture import note_job_settled
        note_job_settled(settled=True, harness=agent_name, job_id=job_id, status=status)
    return settled
```

`note_job_settled` only schedules when `status == "done"`. A missing `daemon_jobs` table in a fixture hits the `except` and passes `harness=None`, which schedules nothing.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k "boundary_capture or unregistered or exec_finished or job_terminal or note_exec or note_job" -v`

Expected: PASS. `test_boundary_capture_returns_before_the_slow_write` must show the call returned before `release.set()`.

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py synlynk/dispatch.py synlynk/jobs.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: capture quota asynchronously after exec and dispatch

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 6: Daemon poller and the Grok Herdr refresh

**Files:**
- Modify: `synlynk/quota_capture.py`
- Modify: `synlynk/daemon.py` (`SynlynkDaemon._run_loop`, the `while True` body that already calls `_reconcile_daemon_jobs`)
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def _grok_registry(log_path: str, pane_id):
    return {
        "grok": {
            "cli_usage_cmd": None,
            "log_scrape": {
                "path": log_path,
                "jq_filter": 'select(.msg == "billing: fetched credits config")',
            },
            "has_5h_window": False,
            "interactive_pane_id": pane_id,
        }
    }


def _grok_line(ts: str, percent: float) -> str:
    return json.dumps({
        "ts": ts,
        "msg": "billing: fetched credits config",
        "ctx": {"config": {
            "creditUsagePercent": percent,
            "currentPeriod": {
                "type": "USAGE_PERIOD_TYPE_WEEKLY",
                "end": "2026-10-14T03:27:47.938919+00:00",
            },
        }},
    })


def test_grok_poller_sends_usage_only_when_the_log_line_is_stale(tmp_path):
    import json
    from datetime import datetime, timezone
    from synlynk.quota_capture import poll_once

    log_path = tmp_path / "unified.jsonl"
    log_path.write_text(_grok_line("2026-10-10T00:00:00Z", 21.0) + "\n")
    calls = []

    def runner(argv, timeout):
        calls.append(argv)
        if argv[2] == "send-keys":
            with log_path.open("a") as handle:
                handle.write(_grok_line("2026-10-10T01:00:00Z", 22.0) + "\n")
        return ""

    conn = _snapshots_db()
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    written = poll_once(
        conn=conn,
        registry=_grok_registry(str(log_path), "pane-grok"),
        now=now,
        runner=runner,
        sleeper=lambda seconds: None,
    )
    assert calls == [
        ["herdr", "pane", "send-text", "pane-grok", "/usage"],
        ["herdr", "pane", "send-keys", "pane-grok", "Enter"],
    ]
    assert written == 1
    row = conn.execute("SELECT used_percent, source, staleness_seconds FROM quota_snapshots").fetchone()
    assert row["used_percent"] == 22.0
    assert row["source"] == "poller"
    assert row["staleness_seconds"] == 0


def test_grok_poller_does_not_refresh_a_fresh_line(tmp_path):
    from datetime import datetime, timezone
    from synlynk.quota_capture import poll_once

    log_path = tmp_path / "unified.jsonl"
    log_path.write_text(_grok_line("2026-10-10T00:50:00Z", 21.0) + "\n")
    calls = []
    conn = _snapshots_db()
    written = poll_once(
        conn=conn,
        registry=_grok_registry(str(log_path), "pane-grok"),
        now=datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc),
        runner=lambda argv, timeout: calls.append(argv),
        sleeper=lambda seconds: None,
    )
    assert calls == []
    assert written == 1
    row = conn.execute("SELECT used_percent, staleness_seconds FROM quota_snapshots").fetchone()
    assert row["used_percent"] == 21.0
    assert row["staleness_seconds"] == 600


def test_grok_poller_without_a_pane_does_not_call_herdr(tmp_path):
    from datetime import datetime, timezone
    from synlynk.quota_capture import poll_once

    log_path = tmp_path / "unified.jsonl"
    log_path.write_text(_grok_line("2026-10-09T00:00:00Z", 21.0) + "\n")
    calls = []
    conn = _snapshots_db()
    poll_once(
        conn=conn,
        registry=_grok_registry(str(log_path), None),
        now=datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc),
        runner=lambda argv, timeout: calls.append(argv),
        sleeper=lambda seconds: None,
    )
    assert calls == []


def test_claude_poller_runs_the_registry_command(tmp_path):
    from datetime import datetime, timezone
    from synlynk.quota_capture import poll_once

    seen = []

    def runner(argv, timeout):
        seen.append(argv)
        return "Current session\n4% used\n\nCurrent week (all models)\n10% used\n"

    conn = _snapshots_db()
    written = poll_once(
        conn=conn,
        registry={"claude": {
            "cli_usage_cmd": 'claude -p "/usage" --output-format text',
            "log_scrape": None,
            "has_5h_window": True,
            "interactive_pane_id": None,
        }},
        now=datetime(2026, 10, 10, tzinfo=timezone.utc),
        runner=runner,
        sleeper=lambda seconds: None,
    )
    assert seen == [["claude", "-p", "/usage", "--output-format", "text"]]
    assert written == 2
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k poller -v`

Expected: FAIL with `ImportError: cannot import name 'poll_once'`

- [ ] **Step 3: Write the minimal implementation**

Append to `synlynk/quota_capture.py`:

```python
def refresh_grok_pane(pane_id: str, *, runner=None, sleeper=None) -> None:
    run = runner or _default_runner
    pause = sleeper or time.sleep
    run(["herdr", "pane", "send-text", pane_id, "/usage"], 10)
    run(["herdr", "pane", "send-keys", pane_id, "Enter"], 10)
    pause(GROK_REFRESH_WAIT_SECONDS)


def _grok_line_age(obj: dict | None, now: datetime) -> float | None:
    if obj is None:
        return None
    readings = parse_grok_billing_line(obj)
    if not readings:
        return None
    return float(_reading_age_seconds(readings[0].observed_at, now))


def poll_once(
    *,
    conn=None,
    registry: dict | None = None,
    now: datetime | None = None,
    runner=None,
    sleeper=None,
) -> int:
    owns_conn = conn is None
    if owns_conn:
        conn = _open_db()
    current = now or datetime.now(timezone.utc)
    registry = registry if registry is not None else load_registry()
    written = 0
    try:
        for harness, entry in registry.items():
            try:
                if harness == "grok":
                    scrape = entry.get("log_scrape") or {}
                    log_path = Path(os.path.expanduser(scrape.get("path") or "~/.grok/logs/unified.jsonl"))
                    existing = _newest_grok_billing(log_path)
                    age = _grok_line_age(existing, current)
                    pane_id = entry.get("interactive_pane_id")
                    if pane_id and (age is None or age > DEFAULT_POLL_INTERVAL_SECONDS):
                        try:
                            refresh_grok_pane(pane_id, runner=runner, sleeper=sleeper)
                        except Exception:
                            logger.exception("grok pane refresh failed for %s", pane_id)
                    written += capture_harness(
                        harness, source="poller", job_id=None, conn=conn,
                        registry=registry, now=current, runner=runner,
                    )
                else:
                    written += capture_harness(
                        harness, source="poller", job_id=None, conn=conn,
                        registry=registry, now=current, runner=runner,
                    )
            except Exception:
                logger.exception("quota poll failed for %s", harness)
        if owns_conn and conn is not None:
            conn.commit()
        elif conn is not None:
            conn.commit()
    finally:
        if owns_conn and conn is not None:
            conn.close()
    return written
```

Add `import time` next to the other imports.

`capture_harness` for Grok re-reads the log after `refresh_grok_pane` appends the new line. The fresh-line test's observed timestamp is 10 minutes before `now`, so `staleness_seconds` is 600 and no Herdr call is made. The stale test's first line is 3600 seconds old, so both Herdr commands run, and the appended line is exactly `now`, so staleness is 0.

In `synlynk/daemon.py`, inside `SynlynkDaemon._run_loop`, after `last_token_refresh = time.time()` and before `while True`, add:

```python
        last_quota_poll = 0.0
```

Inside the loop, after the `last_token_refresh` update at the bottom of the loop, add:

```python
            if time.time() - last_quota_poll >= 900:
                try:
                    from synlynk.quota_capture import poll_once
                    poll_once()
                except Exception:
                    _traceback.print_exc()
                last_quota_poll = time.time()
```

Use `900` here, the same value as `DEFAULT_POLL_INTERVAL_SECONDS`. Importing the constant at the top of `daemon.py` is also fine: `from synlynk.quota_capture import DEFAULT_POLL_INTERVAL_SECONDS, poll_once` must not run at daemon import if that import cycle is heavy. Keep the import inside the loop body, and compare against the literal `900`.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k poller -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py synlynk/daemon.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: poll harness quota and refresh Grok through Herdr

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 7: `synlynk quota federated`

**Files:**
- Modify: `synlynk/quota_capture.py`
- Modify: `synlynk/cli.py` (quota subparsers around the `calibrate` parser, and the `args.command == "quota"` branch)
- Modify: `synlynk/taxonomy.py` (the `quota calibrate` entry)
- Modify: `AI_INSTRUCTIONS.md` (the trigger line for `synlynk quota calibrate`)
- Modify: `docs/reference/commands.md` and `README.md` via `scripts/generate_command_docs.py`
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_quota_federated_json_prints_unknown_without_raising(monkeypatch, capsys):
    from synlynk.quota_capture import cmd_quota_federated

    monkeypatch.setattr(
        "synlynk.quota_capture.federated_rows",
        lambda conn, now=None, registry=None: [{
            "harness": "grok",
            "window": "weekly",
            "state": "unknown",
            "used_percent": None,
            "source": None,
            "resets_at": None,
            "captured_at": None,
            "cost_7d_usd": 0.0,
            "reason": "missing",
        }],
    )
    monkeypatch.setattr("synlynk.quota_capture._open_db", lambda: object())
    cmd_quota_federated(json_output=True)
    payload = json.loads(capsys.readouterr().out)
    assert payload[0]["harness"] == "grok"
    assert payload[0]["state"] == "unknown"
    assert payload[0]["used_percent"] is None


def test_taxonomy_and_parser_both_have_quota_federated():
    from synlynk.cli import build_parser
    from synlynk.taxonomy import COMMAND_TAXONOMY, iter_leaf_commands

    parser = build_parser()
    assert "quota federated" in set(iter_leaf_commands(parser))
    assert "quota federated" in {entry["command"] for entry in COMMAND_TAXONOMY}
```

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_quota_federated_json_prints_unknown_without_raising tests/test_federated_quota_capture.py::test_taxonomy_and_parser_both_have_quota_federated -v`

Expected: FAIL with `ImportError: cannot import name 'cmd_quota_federated'`, then FAIL because `quota federated` is absent from the parser.

- [ ] **Step 3: Write the minimal implementation**

Append to `synlynk/quota_capture.py`:

```python
def cmd_quota_federated(json_output: bool = False) -> None:
    conn = _open_db()
    try:
        rows = federated_rows(conn)
    finally:
        if conn is not None:
            conn.close()
    if json_output:
        print(json.dumps(rows, indent=2))
    else:
        print(format_federated_text(rows))
```

In `synlynk/cli.py`, immediately after the `calibrate_parser` block (after its `--json` argument), add:

```python
    federated_parser = quota_sub.add_parser(
        "federated",
        help="Show the latest subscription-quota percent per harness and window, plus 7-day dollar burn",
    )
    federated_parser.add_argument(
        "--json",
        action="store_true",
        dest="json_output",
        help="Emit machine-readable JSON",
    )
```

In the `elif args.command == "quota":` branch, before `elif action == "calibrate":`, add:

```python
        elif action == "federated":
            from synlynk.quota_capture import cmd_quota_federated
            cmd_quota_federated(json_output=getattr(args, "json_output", False))
```

In `synlynk/taxonomy.py`, immediately after the `quota calibrate` dict, add:

```python
    {"command": "quota federated", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["show federated quota", "which harness has quota headroom"], "hook_event": None},
```

In `AI_INSTRUCTIONS.md`, immediately after the `synlynk quota calibrate` trigger line, add:

```markdown
- "show federated quota", "which harness has quota headroom" -> `synlynk quota federated`
```

Regenerate the command docs:

Run: `python3 scripts/generate_command_docs.py`

Expected: `docs/reference/commands.md` and the `<!-- commands:start -->` block in `README.md` now contain `` `synlynk quota federated` ``.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py::test_quota_federated_json_prints_unknown_without_raising tests/test_federated_quota_capture.py::test_taxonomy_and_parser_both_have_quota_federated tests/test_docs_sync.py tests/test_taxonomy.py::test_taxonomy_matches_real_cli_surface -v`

Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py synlynk/cli.py synlynk/taxonomy.py AI_INSTRUCTIONS.md docs/reference/commands.md README.md tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: add synlynk quota federated

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 8: Dispatch uses weekly headroom

**Files:**
- Modify: `synlynk/quota_capture.py`
- Modify: `synlynk/dispatch.py` (`_infer_dispatch_defaults`, after `inferred_agent` is chosen and before the `return`)
- Test: `tests/test_federated_quota_capture.py`

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_routing_prefers_the_known_weekly_reading_with_headroom():
    from datetime import datetime, timezone
    from synlynk.quota_capture import insert_snapshots, prefer_harness_by_weekly_headroom, WindowReading

    conn = _snapshots_db()
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    captured = "2026-10-10T00:50:00+00:00"
    insert_snapshots(
        conn, "claude", [WindowReading("weekly", 98.0, None, captured)],
        source="task_boundary", job_id="job-c", captured_at=captured, staleness_by_window={},
    )
    insert_snapshots(
        conn, "codex", [WindowReading("weekly", 14.0, None, captured)],
        source="task_boundary", job_id="job-x", captured_at=captured, staleness_by_window={},
    )
    choice = prefer_harness_by_weekly_headroom("claude", ["codex", "agy"], conn=conn, now=now)
    assert choice == "codex"


def test_routing_does_not_treat_unknown_as_free_capacity():
    from datetime import datetime, timezone
    from synlynk.quota_capture import insert_snapshots, prefer_harness_by_weekly_headroom, WindowReading

    conn = _snapshots_db()
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    insert_snapshots(
        conn, "codex", [WindowReading("weekly", 14.0, None, "2026-10-10T00:50:00Z")],
        source="task_boundary", job_id=None, captured_at="2026-10-10T00:50:00+00:00", staleness_by_window={},
    )
    # Grok has no snapshot. It must not beat a known Codex reading, and it must
    # not be invented as 0%. Claude is unknown too, so the only known weekly
    # reading wins even though Claude is the incumbent.
    choice = prefer_harness_by_weekly_headroom("claude", ["grok", "codex"], conn=conn, now=now)
    assert choice == "codex"


def test_routing_keeps_incumbent_when_every_reading_is_unknown():
    from datetime import datetime, timezone
    from synlynk.quota_capture import prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    choice = prefer_harness_by_weekly_headroom(
        "claude", ["muse"], conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    assert choice == "claude"


def test_routing_skips_a_full_5h_window():
    from datetime import datetime, timezone
    from synlynk.quota_capture import insert_snapshots, prefer_harness_by_weekly_headroom, WindowReading

    conn = _snapshots_db()
    captured = "2026-10-10T00:50:00+00:00"
    now = datetime(2026, 10, 10, 1, 0, tzinfo=timezone.utc)
    insert_snapshots(
        conn, "codex",
        [WindowReading("weekly", 14.0, None, captured), WindowReading("5h", 100.0, None, captured)],
        source="task_boundary", job_id=None, captured_at=captured, staleness_by_window={},
    )
    insert_snapshots(
        conn, "claude", [WindowReading("weekly", 98.0, None, captured)],
        source="task_boundary", job_id=None, captured_at=captured, staleness_by_window={},
    )
    choice = prefer_harness_by_weekly_headroom("claude", ["codex"], conn=conn, now=now)
    assert choice == "claude"


def test_routing_uses_calibrate_when_the_snapshot_is_stale():
    from datetime import datetime, timezone
    from synlynk.quota_capture import insert_snapshots, prefer_harness_by_weekly_headroom, WindowReading

    conn = _snapshots_db()
    insert_snapshots(
        conn, "claude", [WindowReading("weekly", 98.0, None, "2026-10-01T00:00:00Z")],
        source="poller", job_id=None, captured_at="2026-10-01T00:00:00+00:00",
        staleness_by_window={"weekly": 0},
    )
    conn.execute(
        "INSERT INTO harness_quotas (harness, quota_type, unit, limit_tokens, used_tokens, updated_at)"
        " VALUES ('agy', 'weekly', 'tokens', 100, 10, '2026-10-09')"
    )
    choice = prefer_harness_by_weekly_headroom(
        "claude", ["agy"], conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    )
    assert choice == "agy"


def test_infer_dispatch_defaults_calls_headroom_when_the_harness_is_unpinned(monkeypatch):
    from synlynk.dispatch import _infer_dispatch_defaults

    monkeypatch.setattr(
        "synlynk.quota_capture.prefer_harness_by_weekly_headroom",
        lambda incumbent, fallbacks, conn, now=None, registry=None: "agy",
    )
    preview = _infer_dispatch_defaults("implement the quota view", task_type="implement", agent=None)
    assert preview["harness"] == "agy"


def test_infer_dispatch_defaults_does_not_override_an_explicit_harness(monkeypatch):
    from synlynk.dispatch import _infer_dispatch_defaults

    def explode(*args, **kwargs):
        raise AssertionError("explicit harness must skip quota routing")

    monkeypatch.setattr("synlynk.quota_capture.prefer_harness_by_weekly_headroom", explode)
    preview = _infer_dispatch_defaults(
        "implement the quota view", task_type="implement", agent="codex",
    )
    assert preview["harness"] == "codex"
```

The two `_infer_dispatch_defaults` tests need the same policy setup as `tests/test_dispatch_preview.py` if the real policy file is not what the test assumes. Copy that test's `tmp_path` policy write and `monkeypatch.chdir(tmp_path)` into both tests, with:

```json
{"schema_version": 1, "repo_id": "test", "capability_policy": {}, "overrides": {"dev_authority": {"task_allocation": {"implement": {"harness": "claude", "fallback": ["agy", "codex"]}}}}}
```

Also patch `synlynk.capability.ranked_harness_for_task` to return `None` so empirical promotion does not run ahead of the quota hook. The unpinned test then expects the quota hook to replace `claude` with `agy`.

- [ ] **Step 2: Run the test to verify it fails**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k "routing or infer_dispatch_defaults" -v`

Expected: FAIL with `ImportError: cannot import name 'prefer_harness_by_weekly_headroom'`

- [ ] **Step 3: Write the minimal implementation**

Append to `synlynk/quota_capture.py`:

```python
def prefer_harness_by_weekly_headroom(
    incumbent: str,
    fallbacks: list[str],
    conn,
    now: datetime | None = None,
    registry: dict | None = None,
) -> str:
    current = now or datetime.now(timezone.utc)
    registry = registry if registry is not None else load_registry()
    order = [incumbent]
    for name in fallbacks:
        if name and name not in order:
            order.append(name)
    eligible: list[tuple[float, int, str]] = []
    for index, harness in enumerate(order):
        try:
            five = window_status(conn, harness, "5h", now=current, registry=registry)
            weekly = window_status(conn, harness, "weekly", now=current, registry=registry)
        except Exception:
            logger.exception("quota routing skipped %s", harness)
            continue
        if five["state"] == "known" and five["used_percent"] is not None and five["used_percent"] >= 100:
            continue
        if weekly["state"] != "known" or weekly["used_percent"] is None:
            continue
        tie = 0 if harness == incumbent else 1
        eligible.append((float(weekly["used_percent"]), tie, harness))
    if not eligible:
        return incumbent
    eligible.sort()
    return eligible[0][2]
```

In `_infer_dispatch_defaults`, after `inferred_agent` is assigned and before `config = _pkg("load_config")`, add:

```python
    if agent is None and inferred_agent:
        pool = []
        for name in [default_harness, *list(fallback_list), inferred_agent]:
            if name and name not in pool:
                pool.append(name)
        try:
            from synlynk.quota_capture import prefer_harness_by_weekly_headroom
            qconn = _pkg("_get_db")()
            try:
                inferred_agent = prefer_harness_by_weekly_headroom(
                    inferred_agent,
                    [name for name in pool if name != inferred_agent],
                    conn=qconn,
                )
            finally:
                qconn.close()
        except Exception:
            pass
```

`_pkg("_get_db")` may return the function. Call it: `get_db = _pkg("_get_db"); qconn = get_db()`. If `_pkg` returns `None`, the `get_db()` line raises and the `except` keeps the incumbent. Do not let this block dispatch.

An explicit `agent=` argument skips the block because `agent is None` is false. `force` is not involved.

- [ ] **Step 4: Run the test to verify it passes**

Run: `python3 -m pytest tests/test_federated_quota_capture.py -k "routing or infer_dispatch_defaults" tests/test_dispatch_preview.py -v`

Expected: PASS, including the existing preview test. That test's harness stays `grok` because every weekly reading on the empty pytest database is unknown, so the helper returns the incumbent.

- [ ] **Step 5: Commit**

```bash
git add synlynk/quota_capture.py synlynk/dispatch.py tests/test_federated_quota_capture.py
git commit -m "$(cat <<'EOF'
feat: route unpinned dispatch toward weekly quota headroom

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

---

### Task 9: Regression sweep and the blog post

**Files:**
- Test: `tests/test_federated_quota_capture.py`
- Create: `docs/blog/266-prTBD-federated-quota-capture.md`
- Modify: `docs/blog/README.md` (prepend one index row)

- [ ] **Step 1: Write the failing regression test**

Append:

```python
def test_unregistered_harness_never_writes_and_routing_does_not_raise(tmp_path):
    from datetime import datetime, timezone
    from synlynk.quota_capture import capture_harness, prefer_harness_by_weekly_headroom

    conn = _snapshots_db()
    assert capture_harness("muse", source="poller", job_id=None, conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc)) == 0
    assert conn.execute("SELECT COUNT(*) FROM quota_snapshots").fetchone()[0] == 0
    assert prefer_harness_by_weekly_headroom(
        "claude", ["muse"], conn=conn, now=datetime(2026, 10, 10, tzinfo=timezone.utc),
    ) == "claude"
```

This test passes as soon as Tasks 5 and 8 are in. Run it. If it fails, fix the writer or the router. Do not weaken the assertion.

- [ ] **Step 2: Run the feature tests and the dispatch preview**

Run: `python3 -m pytest tests/test_federated_quota_capture.py tests/test_dispatch_preview.py tests/test_docs_sync.py tests/test_taxonomy.py::test_taxonomy_matches_real_cli_surface -v`

Expected: PASS

- [ ] **Step 3: Write the blog post**

When `gh pr create` returns a number, rename `266-prTBD-federated-quota-capture.md` to `266-pr<NUMBER>-federated-quota-capture.md` and use that name in the index. Until then, create the file with this body:

```markdown
# 266 — Federated quota capture

## Where the last PR left the goal

synlynk could price a job in `cost_entries` and could store a hand-entered ceiling in `harness_quotas`. It could not see which subscription was actually near its weekly limit, so PM and review work kept landing on whichever harness was home.

## What moved

The home harness hit 98% of its weekly quota during roadmap work. Allocation has to read the provider's own percent, not a local token estimate. Open-source usage tools were checked and rejected because they label their figures as API-equivalent estimates.

## What this PR ships

`quota_snapshots` (migration 20) stores `harness`, `window` (`5h` or `weekly`), `used_percent`, `resets_at`, `captured_at`, `source` (`task_boundary` or `poller`), `staleness_seconds`, and `job_id`. The registry in `synlynk/quota_capture.py` maps Claude and Agy to `cli -p "/usage" --output-format text`, Codex to the newest `payload.rate_limits` object under `~/.codex/sessions`, and Grok to `billing: fetched credits config` in `~/.grok/logs/unified.jsonl`. Boundary capture runs on a daemon thread after `exec_command` and after a dispatch job settles `done`. The daemon poller runs every 15 minutes. For Grok it sends `/usage` and Enter into `interactive_pane_id` only when that id is set and the log line is older than 15 minutes. `synlynk quota federated` prints the latest row per harness and window next to a 7-day `cost_entries` sum. A reading older than 30 minutes, or a missing reading, is `unknown`. Unknown falls back to `synlynk quota calibrate` data in `harness_quotas`. Unpinned dispatch then prefers the known weekly reading with the most room, and skips a harness whose known 5h reading is at least 100%.

## Brainstorm

No new brainstorm visuals. The approved spec is `docs/superpowers/specs/2026-10-10-federated-quota-capture-design.md`.

## On the way to autonomous dispatch

The fleet can now see subscription headroom the same way it already sees dollar burn. Grok stays `unknown` until a standing Herdr pane id is registered. That pane setup is a separate design.

## The new goalpost

Per-harness persistent Herdr panes, so Grok's weekly percent refreshes without a manual calibrate, and Herdr's place as a synlynk dependency gets its own spec.
```

Prepend this row to the index table in `docs/blog/README.md`, above the current first row:

```markdown
| [266](./266-prTBD-federated-quota-capture.md) | Federated subscription-quota capture | TBD | 2026-10-10 |
```

Replace `prTBD` and the `TBD` link column after the PR number exists.

- [ ] **Step 4: Commit**

```bash
git add tests/test_federated_quota_capture.py docs/blog/266-prTBD-federated-quota-capture.md docs/blog/README.md
git commit -m "$(cat <<'EOF'
docs: record federated quota capture

Co-Authored-By: Grok <noreply@x.ai>
EOF
)"
```

If the regression test was already committed in Task 8, stage only the blog files.

---

## Spec coverage

| Spec requirement | Task |
|---|---|
| `quota_snapshots` columns, free-text harness, nullable resets/job/staleness | Task 1 |
| Registry JSON for claude, agy, codex, grok, including Codex `has_5h_window: "unknown"` | Task 2 |
| Absent harness writes no row | Tasks 5 and 9 |
| Claude/Agy CLI parse, Codex log scrape, Grok JSONL parse, real samples | Task 3 |
| Boundary capture async, `source=task_boundary`, null staleness, job id, failures do not block | Task 5 |
| Poller every 15 minutes, `source=poller`, staleness is the reading's age | Tasks 4 and 6 |
| Grok `herdr pane send-text` + Enter only when the pane id is set and the line is stale | Task 6 |
| Null pane id leaves Grok unknown | Tasks 4 and 6 |
| `synlynk quota federated` beside 7-day dollar burn | Tasks 4 and 7 |
| Stale means unknown, not 0%; calibrate fallback; missing matches unknown | Task 4 |
| Dispatch consults the view before keeping the default harness | Task 8 |
| Codex 5h unknown until a 300-minute bucket exists; Grok 5h never auto-captured | Tasks 3 and 4 |
| Herdr-as-a-bundled-dependency deferred | Out of scope |

## Self-review

- Placeholder scan: the only deferred token is `prTBD` in the blog filename, replaced when `gh pr create` returns a number.
- Type names used throughout: `WindowReading`, `load_registry`, `insert_snapshots`, `window_status`, `federated_rows`, `capture_harness`, `schedule_boundary_capture`, `poll_once`, `prefer_harness_by_weekly_headroom`, `note_exec_return`, `note_job_settled`.
- `staleness_seconds` is NULL for `task_boundary` in Task 4's insert and Task 5's tests. Poller rows pass the log age.
