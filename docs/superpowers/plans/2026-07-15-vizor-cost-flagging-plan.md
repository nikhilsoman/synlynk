# Vizor Effort & Cost Tab: Flag Estimated vs. Actual Cost Rows — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Vizor Effort & Cost tab visually distinguish structurally-measured ("actual") cost rows from heuristically-estimated ones, closing epic #210's last remaining scope (spec: `docs/superpowers/specs/2026-07-15-vizor-cost-flagging-design.md`).

**Architecture:** Two independent layers change in `synlynk/viz.py`. (1) The data layer — `generate_viz_data()` — starts reading the `cost_source` column already present on `cost_entries` (added in Measurement Ledger Phase 1) and splits `by_agent`/`by_stage`/dream cost totals into actual/estimated sub-amounts. (2) The rendering layer — `generate_effort_html()` and its `render_bar_chart()` helper — consumes that split to add a 5th "~Estimated" summary card and render a faded second bar segment for any row with non-actual spend.

**Tech Stack:** Python 3 stdlib (`sqlite3`, f-strings for HTML/SVG generation), pytest for tests. No new dependencies.

**Naming note (read before starting):** This codebase already uses "actual"/"est" to mean *actual spend vs. budgeted target* (e.g. `story["cost_actual"]`, `dream["cost_est"]`). This plan introduces a *different* axis — actual spend vs. budgeted target say nothing about whether the observed dollar figure was structurally measured or heuristically estimated. To avoid colliding with the existing vocabulary, every new field/variable in this plan uses the word **"estimated" only for the provenance axis** (`cost_source != "actual"`), and existing `cost_actual`/`cost_est` fields keep their current meaning and current values — they are not being narrowed to exclude non-actual-provenance rows. Where a new field is a *subset* of an existing "actual" total (e.g. `story["cost_prov_estimated"]` is a portion of `story["cost_actual"]`), that relationship is called out explicitly in the task.

---

### Task 1: Data layer — split cost aggregates by provenance

**Files:**
- Modify: `synlynk/viz.py:401-402` (by_agent/by_stage init), `synlynk/viz.py:334-342` (`_dream_cost_actual`, renamed), `synlynk/viz.py:417-419` (SQL query), `synlynk/viz.py:429-438` (story dict init), `synlynk/viz.py:442-456` (cost_rows loop + agents total_usd), `synlynk/viz.py:515-541` (stage/dream aggregation), `synlynk/viz.py:558-562` (final `data["costs"]` assembly), `synlynk/viz.py:159` (`_base_data()` default costs shape)
- Test: `tests/test_viz.py`

- [ ] **Step 1: Add `cost_source` column to the test fixture**

Open `tests/test_viz.py`. In `make_test_db()` (lines 4-35), the `cost_entries` table is missing the `cost_source` column that exists on real (post-Phase-1-migration) databases. Add it with a default so the existing single INSERT keeps working unchanged:

```python
def make_test_db(path: str):
    conn = sqlite3.connect(path)
    conn.executescript("""
        CREATE TABLE roadmap_arcs (
            id INTEGER PRIMARY KEY, version TEXT UNIQUE, title TEXT,
            status TEXT DEFAULT 'active', target_date TEXT, notes TEXT
        );
        CREATE TABLE roadmap_phases (
            id INTEGER PRIMARY KEY, arc_version TEXT, phase_title TEXT,
            status TEXT DEFAULT 'planned', priority TEXT, story_id TEXT, notes TEXT
        );
        CREATE TABLE stories (
            id INTEGER PRIMARY KEY, story_id TEXT UNIQUE, title TEXT,
            status TEXT DEFAULT 'open', phase TEXT DEFAULT 'build',
            estimated_tokens INTEGER, created_at TEXT
        );
        CREATE TABLE cost_entries (
            id INTEGER PRIMARY KEY, session_date TEXT, agent TEXT,
            model TEXT, input_tokens INTEGER, output_tokens INTEGER,
            cache_read_tokens INTEGER, total_cost_usd REAL, notes TEXT,
            cost_source TEXT DEFAULT 'actual'
        );
        INSERT INTO roadmap_arcs (version, title, status) VALUES ('v0.11.0', 'Retention Layer', 'active');
        INSERT INTO roadmap_phases (arc_version, phase_title, status, notes)
            VALUES ('v0.11.0', 'Plan', 'done', '[agent:codex]'),
                   ('v0.11.0', 'Build', 'active', '[agent:agy,codex]');
        INSERT INTO stories (story_id, title, status, phase, estimated_tokens)
            VALUES ('story-bs21-shell', 'Shell layout', 'done', 'build', 60000);
        INSERT INTO cost_entries (session_date, agent, total_cost_usd, notes, cost_source)
            VALUES ('2026-07-01', 'agy', 1.20, 'story-bs21-shell', 'actual');
    """)
    conn.commit()
    return conn
```

This is the only edit to `make_test_db()`. Every existing test that calls it (`test_generate_viz_data_structure`, `test_dreams_populated`) is unaffected — they don't assert on `by_agent`/`by_stage` values.

- [ ] **Step 2: Write the failing tests for the actual/estimated split**

Add these three tests to `tests/test_viz.py`, after `test_dreams_populated` (after line 166):

```python
def test_generate_viz_data_splits_cost_source_by_agent(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = make_test_db(db_path)
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, total_cost_usd, notes, cost_source) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-07-02", "agy", 2.50, "story-bs21-shell", "estimated_token_rate"),
    )
    conn.commit()
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    by_agent = data["costs"]["by_agent"]
    assert by_agent["agy"]["actual"] == pytest.approx(1.20)
    assert by_agent["agy"]["estimated"] == pytest.approx(2.50)
    assert data["costs"]["total_usd"] == pytest.approx(3.70)
    assert data["costs"]["total_usd_estimated"] == pytest.approx(2.50)


def test_generate_viz_data_null_cost_source_counts_as_estimated(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = make_test_db(db_path)
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, total_cost_usd, notes, cost_source) "
        "VALUES (?, ?, ?, ?, NULL)",
        ("2026-07-02", "codex", 4.00, "story-bs21-shell"),
    )
    conn.commit()
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    by_agent = data["costs"]["by_agent"]
    assert by_agent["codex"]["actual"] == pytest.approx(0.0)
    assert by_agent["codex"]["estimated"] == pytest.approx(4.00)


def test_dream_cost_total_estimated_split(tmp_path, monkeypatch):
    db_path = str(tmp_path / "state.db")
    conn = make_test_db(db_path)
    conn.execute(
        "INSERT INTO cost_entries (session_date, agent, total_cost_usd, notes, cost_source) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-07-02", "codex", 3.00, "v0.11.0 story-bs21-shell", "estimated_tshirt"),
    )
    conn.commit()
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({}, f)

    from synlynk.viz import generate_viz_data
    with patch("synlynk.viz._get_db") as mock_db:
        mock_db.return_value = sqlite3.connect(db_path)
        data = generate_viz_data()

    dream = data["dreams"][0]
    assert dream["cost_total"] == pytest.approx(3.00)
    assert dream["cost_total_estimated"] == pytest.approx(3.00)
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_viz.py -v -k "cost_source or estimated_split"`
Expected: FAIL — `by_agent["agy"]` is a float (`1.20` or similar), not a dict, so `by_agent["agy"]["actual"]` raises `TypeError: 'float' object is not subscriptable`. The dream test fails with `KeyError: 'cost_total_estimated'`.

- [ ] **Step 4: Rename and extend `_dream_cost_actual` to return the actual/estimated split**

In `synlynk/viz.py`, replace the function at lines 334-342:

```python
    def _dream_cost_actual(conn, dream_id: str) -> float:
        try:
            row = conn.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0) FROM cost_entries WHERE notes LIKE ?",
                (f"%{dream_id}%",),
            ).fetchone()
        except Exception:
            return 0.0
        return float(row[0] or 0.0) if row else 0.0
```

with:

```python
    def _dream_cost_breakdown(conn, dream_id: str) -> tuple:
        """Returns (total, prov_estimated) for cost_entries whose notes reference this dream.

        `total` keeps the pre-existing meaning (sum of all matching rows, any provenance).
        `prov_estimated` is the subset of `total` whose cost_source != 'actual'.
        """
        try:
            rows = conn.execute(
                "SELECT COALESCE(SUM(total_cost_usd), 0), cost_source FROM cost_entries "
                "WHERE notes LIKE ? GROUP BY cost_source",
                (f"%{dream_id}%",),
            ).fetchall()
        except Exception:
            return 0.0, 0.0
        total = 0.0
        prov_estimated = 0.0
        for amount, cost_source in rows:
            amount = float(amount or 0.0)
            total += amount
            if cost_source != "actual":
                prov_estimated += amount
        return total, prov_estimated
```

- [ ] **Step 5: Extend the SQL query to select `cost_source`**

Replace lines 417-419:

```python
        cost_rows = conn.execute(
            "SELECT session_date, agent, total_cost_usd, notes FROM cost_entries ORDER BY id"
        ).fetchall()
```

with:

```python
        cost_rows = conn.execute(
            "SELECT session_date, agent, total_cost_usd, notes, cost_source FROM cost_entries ORDER BY id"
        ).fetchall()
```

- [ ] **Step 6: Change `by_agent`/`by_stage` init to actual/estimated dicts**

Replace lines 401-402:

```python
    by_agent = {name: 0.0 for name in ("claude", "agy", "codex", "grok")}
    by_stage = {name: 0.0 for name in ("design", "plan", "build", "ship", "sustain")}
```

with:

```python
    by_agent = {name: {"actual": 0.0, "estimated": 0.0} for name in ("claude", "agy", "codex", "grok")}
    by_stage = {name: {"actual": 0.0, "estimated": 0.0} for name in ("design", "plan", "build", "ship", "sustain")}
```

- [ ] **Step 7: Add `cost_prov_estimated` to the story dict**

In the story-dict construction loop (lines 429-438), add one field. Replace:

```python
    for story_id, title, status, phase, estimated_tokens in story_rows:
        story = {
            "id": story_id,
            "name": title or "",
            "agent": phase or "",
            "status": status or "open",
            "cost_est": _story_cost_est(estimated_tokens),
            "cost_actual": 0.0,
            "note": data["notes"].get(story_id) if isinstance(data["notes"], dict) else None,
        }
```

with:

```python
    for story_id, title, status, phase, estimated_tokens in story_rows:
        story = {
            "id": story_id,
            "name": title or "",
            "agent": phase or "",
            "status": status or "open",
            "cost_est": _story_cost_est(estimated_tokens),
            "cost_actual": 0.0,
            "cost_prov_estimated": 0.0,
            "note": data["notes"].get(story_id) if isinstance(data["notes"], dict) else None,
        }
```

Note: `cost_prov_estimated` is a *subset* of `cost_actual` (both accumulate together in Step 8), not a separate bucket — `cost_actual` keeps summing every matching row regardless of provenance, exactly as it does today.

- [ ] **Step 8: Update the cost_rows loop to classify by `cost_source`**

Replace lines 442-448:

```python
    for row in cost_rows:
        agent = row[1] or ""
        amount = float(row[2] or 0.0)
        notes = row[3] or ""
        if agent:
            by_agent.setdefault(agent, 0.0)
            by_agent[agent] += amount
            agents.setdefault(agent, _empty_agent_bucket())
        for story_id, story in stories_by_id.items():
            if story_id and story_id in notes:
                story["cost_actual"] += amount
```

with:

```python
    for row in cost_rows:
        agent = row[1] or ""
        amount = float(row[2] or 0.0)
        notes = row[3] or ""
        cost_source = row[4] or ""
        bucket_key = "actual" if cost_source == "actual" else "estimated"
        if agent:
            by_agent.setdefault(agent, {"actual": 0.0, "estimated": 0.0})
            by_agent[agent][bucket_key] += amount
            agents.setdefault(agent, _empty_agent_bucket())
        for story_id, story in stories_by_id.items():
            if story_id and story_id in notes:
                story["cost_actual"] += amount
                if cost_source != "actual":
                    story["cost_prov_estimated"] += amount
```

- [ ] **Step 9: Fix `agents[agent]["total_usd"]` to read from the new dict shape**

Replace lines 454-456:

```python
    for agent in list(by_agent):
        agents.setdefault(agent, _empty_agent_bucket())
        agents[agent]["total_usd"] = float(by_agent.get(agent, 0.0))
```

with:

```python
    for agent in list(by_agent):
        agents.setdefault(agent, _empty_agent_bucket())
        bucket = by_agent.get(agent) or {"actual": 0.0, "estimated": 0.0}
        agents[agent]["total_usd"] = float(bucket.get("actual", 0.0)) + float(bucket.get("estimated", 0.0))
```

- [ ] **Step 10: Split `by_stage` accumulation and dream cost totals**

Replace lines 515-519:

```python
            stage_cost_actual = sum(float(task["cost_actual"] or 0.0) for task in deduped_tasks)
            stage_cost_est = sum(float(task["cost_est"] or 0.0) for task in deduped_tasks) or None
            dream_tasks_cost_actual += stage_cost_actual
            if stage_cost_est is not None:
                dream_tasks_cost_est += stage_cost_est
```

with:

```python
            stage_cost_actual = sum(float(task["cost_actual"] or 0.0) for task in deduped_tasks)
            stage_cost_prov_estimated = sum(float(task["cost_prov_estimated"] or 0.0) for task in deduped_tasks)
            stage_cost_est = sum(float(task["cost_est"] or 0.0) for task in deduped_tasks) or None
            dream_tasks_cost_actual += stage_cost_actual
            if stage_cost_est is not None:
                dream_tasks_cost_est += stage_cost_est
```

Replace lines 533-534:

```python
            if phase_key.lower() in by_stage:
                by_stage[phase_key.lower()] += stage_cost_actual
```

with:

```python
            if phase_key.lower() in by_stage:
                by_stage[phase_key.lower()]["estimated"] += stage_cost_prov_estimated
                by_stage[phase_key.lower()]["actual"] += (stage_cost_actual - stage_cost_prov_estimated)
```

Replace lines 535-543:

```python
        dream_cost_actual = _dream_cost_actual(conn, dream_id)
        dreams.append({
            "id": dream_id,
            "name": dream_name or "",
            "status": dream_status or "planned",
            "cost_total": float(dream_cost_actual),
            "cost_est": dream_tasks_cost_est or None,
            "stages": dream_stages,
        })
```

with:

```python
        dream_cost_total, dream_cost_prov_estimated = _dream_cost_breakdown(conn, dream_id)
        dreams.append({
            "id": dream_id,
            "name": dream_name or "",
            "status": dream_status or "planned",
            "cost_total": float(dream_cost_total),
            "cost_total_estimated": float(dream_cost_prov_estimated),
            "cost_est": dream_tasks_cost_est or None,
            "stages": dream_stages,
        })
```

- [ ] **Step 11: Add `total_usd_estimated` to the final `data["costs"]` assembly**

Replace lines 558-562:

```python
    data["costs"] = {
        "total_usd": float(sum(float(row[2] or 0.0) for row in cost_rows)),
        "by_agent": by_agent,
        "by_stage": by_stage,
    }
```

with:

```python
    data["costs"] = {
        "total_usd": float(sum(float(row[2] or 0.0) for row in cost_rows)),
        "total_usd_estimated": float(
            sum(float(row[2] or 0.0) for row in cost_rows if (row[4] or "") != "actual")
        ),
        "by_agent": by_agent,
        "by_stage": by_stage,
    }
```

- [ ] **Step 12: Update `_base_data()`'s default costs shape for consistency**

At `synlynk/viz.py:159`, replace:

```python
            "costs": {"total_usd": 0.0, "by_agent": {}, "by_stage": {}},
```

with:

```python
            "costs": {"total_usd": 0.0, "total_usd_estimated": 0.0, "by_agent": {}, "by_stage": {}},
```

- [ ] **Step 13: Run the tests to verify they pass**

Run: `python3 -m pytest tests/test_viz.py -v -k "cost_source or estimated_split"`
Expected: PASS (3 passed)

- [ ] **Step 14: Run the full existing test_viz.py suite to check for regressions**

Run: `python3 -m pytest tests/test_viz.py -v`
Expected: All tests pass. `test_generate_viz_data_structure`, `test_dreams_populated`, `test_graceful_degradation_no_db`, `test_generate_viz_data_includes_file_tree` must still be green — none of them assert on `by_agent`/`by_stage` value shapes, so the dict-vs-float change doesn't break them. `test_generate_effort_html_renders_svg_charts` and `test_generate_effort_html_empty_state` are addressed in Task 2, not this task — do not modify `generate_effort_html` in this task.

- [ ] **Step 15: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): split cost aggregates by actual vs. estimated provenance"
```

---

### Task 2: Rendering — summary card and stacked bar segments

**Files:**
- Modify: `synlynk/viz.py:2503-2921` (`generate_effort_html`, includes `render_bar_chart`, summary cards, row builders, label/color functions, CSS, subtitle)
- Test: `tests/test_viz.py`

This task depends on Task 1 being complete (needs `total_usd_estimated`, `by_agent`/`by_stage` dict shape, and dream `cost_total_estimated` to already exist in the data layer).

- [ ] **Step 1: Write the failing tests**

Add these two tests to `tests/test_viz.py`, after `test_generate_effort_html_empty_state` (after line 252):

```python
def test_generate_effort_html_flags_estimated_rows(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_effort_html

    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [
            {
                "id": "d1", "name": "Dream One", "status": "active",
                "cost_total": 120.0, "cost_total_estimated": 20.0, "cost_est": 100.0,
            },
        ],
        "costs": {
            "total_usd": 120.0,
            "total_usd_estimated": 20.0,
            "by_agent": {
                "claude": {"actual": 100.0, "estimated": 20.0},
                "agy": {"actual": 0.0, "estimated": 0.0},
            },
            "by_stage": {"build": {"actual": 100.0, "estimated": 20.0}},
        },
        "agents": {},
        "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [],
        "workspace_map": {"edges": [], "edge_types": {}},
        "notes": {},
    }

    html = generate_effort_html(data, port=8721)

    assert "~Estimated" in html
    assert "$20.00 (17%)" in html
    assert "(est: $20.00)" in html
    assert 'fill-opacity="0.4"' in html


def test_generate_effort_html_no_estimate_suffix_when_fully_actual(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from synlynk.viz import generate_effort_html

    data = {
        "workspace": {"name": "test", "updated_at": "2026-07-03T10:00:00Z", "repos": []},
        "dreams": [
            {
                "id": "d1", "name": "Dream One", "status": "active",
                "cost_total": 120.0, "cost_total_estimated": 0.0, "cost_est": 100.0,
            },
        ],
        "costs": {
            "total_usd": 120.0,
            "total_usd_estimated": 0.0,
            "by_agent": {"claude": {"actual": 120.0, "estimated": 0.0}},
            "by_stage": {"build": {"actual": 120.0, "estimated": 0.0}},
        },
        "agents": {},
        "telemetry": {"recent": [], "sentinel_alerts": []},
        "journeys": [],
        "workspace_map": {"edges": [], "edge_types": {}},
        "notes": {},
    }

    html = generate_effort_html(data, port=8721)

    assert "(est:" not in html
    assert "~Estimated" in html
    assert "$0.00 (0%)" in html
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_viz.py -v -k "flags_estimated_rows or no_estimate_suffix"`
Expected: FAIL — `"~Estimated" in html` is `False` (card doesn't exist yet).

- [ ] **Step 3: Extract `total_usd_estimated` and add the `_bucket_total` helper**

In `synlynk/viz.py`, locate the top of `generate_effort_html` (around line 2503-2510):

```python
def generate_effort_html(data: dict, port: int) -> str:
    costs = data.get("costs") or {}
    dreams = list(data.get("dreams") or [])
    by_agent = dict(costs.get("by_agent") or {})
    by_stage = dict(costs.get("by_stage") or {})
    total_usd = float(costs.get("total_usd") or 0.0)

    data_json = _viz_json(data)
```

Replace with:

```python
def generate_effort_html(data: dict, port: int) -> str:
    costs = data.get("costs") or {}
    dreams = list(data.get("dreams") or [])
    by_agent = dict(costs.get("by_agent") or {})
    by_stage = dict(costs.get("by_stage") or {})
    total_usd = float(costs.get("total_usd") or 0.0)
    total_usd_estimated = float(costs.get("total_usd_estimated") or 0.0)

    def _bucket_total(bucket) -> float:
        if isinstance(bucket, dict):
            return float(bucket.get("actual", 0.0)) + float(bucket.get("estimated", 0.0))
        return float(bucket or 0.0)

    def _bucket_estimated(bucket) -> float:
        if isinstance(bucket, dict):
            return float(bucket.get("estimated", 0.0))
        return 0.0

    data_json = _viz_json(data)
```

(`_bucket_total`/`_bucket_estimated` accept both the new `{"actual", "estimated"}` dict shape and a plain float, so any caller still passing the old flat-float shape — e.g. the pre-existing `test_generate_effort_html_renders_svg_charts` test — keeps working unchanged.)

This is inside the `total_usd == 0` early-return branch's *outer* scope (the function has an `if total_usd == 0: return ...` a few lines later) — `total_usd_estimated` and the two helpers must be defined before that early return so they're in scope for the rest of the function. Since the early-return path doesn't use them, that's fine; just make sure the edit lands above the `if total_usd == 0:` line, not below it.

- [ ] **Step 4: Add the "~Estimated" summary card**

Locate `build_summary_cards()` (lines 2601-2611):

```python
    def build_summary_cards() -> str:
        cards = [
            ("Total Spend", _fmt_usd(total_usd)),
            ("Dreams In Flight", str(dreams_in_flight)),
            ("Over Budget", str(over_budget)),
            ("Top Agent", _svg_text(top_agent)),
        ]
        return "".join(
            f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>'
            for label, value in cards
        )
```

Replace with:

```python
    def build_summary_cards() -> str:
        est_pct = (total_usd_estimated / total_usd * 100.0) if total_usd else 0.0
        cards = [
            ("Total Spend", _fmt_usd(total_usd)),
            ("Dreams In Flight", str(dreams_in_flight)),
            ("Over Budget", str(over_budget)),
            ("Top Agent", _svg_text(top_agent)),
            ("~Estimated", f"{_fmt_usd(total_usd_estimated)} ({_fmt_pct(est_pct)})"),
        ]
        return "".join(
            f'<div class="stat"><span>{label}</span><strong>{value}</strong></div>'
            for label, value in cards
        )
```

- [ ] **Step 5: Fix `top_agent` to use `_bucket_total`**

Replace line 2599:

```python
    top_agent = max(by_agent.items(), key=lambda item: float(item[1] or 0.0))[0] if by_agent else "—"
```

with:

```python
    top_agent = max(by_agent.items(), key=lambda item: _bucket_total(item[1]))[0] if by_agent else "—"
```

- [ ] **Step 6: Add the `estimated_key` parameter to `render_bar_chart` and draw the second segment**

Replace the full `render_bar_chart` function (lines 2613-2643):

```python
    def render_bar_chart(rows, title, value_key, color_fn, label_fn, empty_text, max_value=None) -> str:
        rows = list(rows)
        row_count = max(len(rows), 1)
        svg_height = 54 + row_count * 30
        max_value = max_value or max([float(row.get(value_key) or 0.0) for row in rows] + [0.0]) or 1.0
        svg_rows = []
        if rows:
            for idx, row in enumerate(rows):
                value = float(row.get(value_key) or 0.0)
                y = 18 + idx * 30
                width = (value / max_value) * 380 if max_value else 0.0
                bar_color = color_fn(row, value)
                label = label_fn(row, value)
                svg_rows.append(
                    f'<text x="0" y="{y + 7}" class="y-label">{_svg_text(row.get("label") or row.get("name") or row.get("key") or "")}</text>'
                    f'<rect x="110" y="{y}" width="{width:.2f}" height="18" rx="9" fill="{bar_color}"></rect>'
                    f'<text x="495" y="{y + 7}" text-anchor="end" class="value-label">{_svg_text(label)}</text>'
                )
        else:
            svg_rows.append(f'<text x="250" y="42" text-anchor="middle" class="empty-label">{_svg_text(empty_text)}</text>')

        return f"""
        <section class="panel">
          <div class="panel-head">
            <h2>{_svg_text(title)}</h2>
          </div>
          <svg viewBox="0 0 500 {svg_height}" aria-label="{_svg_text(title)}">
            {''.join(svg_rows)}
          </svg>
        </section>
        """
```

with:

```python
    def render_bar_chart(rows, title, value_key, color_fn, label_fn, empty_text, max_value=None, estimated_key=None) -> str:
        rows = list(rows)
        row_count = max(len(rows), 1)
        svg_height = 54 + row_count * 30
        max_value = max_value or max([float(row.get(value_key) or 0.0) for row in rows] + [0.0]) or 1.0
        svg_rows = []
        if rows:
            for idx, row in enumerate(rows):
                value = float(row.get(value_key) or 0.0)
                estimated_val = float(row.get(estimated_key) or 0.0) if estimated_key else 0.0
                actual_val = max(value - estimated_val, 0.0)
                y = 18 + idx * 30
                bar_color = color_fn(row, value)
                label = label_fn(row, value)
                actual_width = (actual_val / max_value) * 380 if max_value else 0.0
                bar_svg = f'<rect x="110" y="{y}" width="{actual_width:.2f}" height="18" rx="9" fill="{bar_color}"></rect>'
                if estimated_val > 0:
                    est_width = (estimated_val / max_value) * 380 if max_value else 0.0
                    bar_svg += (
                        f'<rect x="{110 + actual_width:.2f}" y="{y}" width="{est_width:.2f}" '
                        f'height="18" fill="{bar_color}" fill-opacity="0.4"></rect>'
                    )
                svg_rows.append(
                    f'<text x="0" y="{y + 7}" class="y-label">{_svg_text(row.get("label") or row.get("name") or row.get("key") or "")}</text>'
                    f'{bar_svg}'
                    f'<text x="495" y="{y + 7}" text-anchor="end" class="value-label">{_svg_text(label)}</text>'
                )
        else:
            svg_rows.append(f'<text x="250" y="42" text-anchor="middle" class="empty-label">{_svg_text(empty_text)}</text>')

        return f"""
        <section class="panel">
          <div class="panel-head">
            <h2>{_svg_text(title)}</h2>
          </div>
          <svg viewBox="0 0 500 {svg_height}" aria-label="{_svg_text(title)}">
            {''.join(svg_rows)}
          </svg>
        </section>
        """
```

- [ ] **Step 7: Add `estimated` to `dream_rows`, `agent_rows`, `stage_rows`**

Replace lines 2645-2666:

```python
    dream_rows = [
        {
            "label": dream.get("name") or dream.get("id") or "Unnamed dream",
            "name": dream.get("name") or dream.get("id") or "Unnamed dream",
            "value": float(dream.get("cost_total") or 0.0),
            "cost_est": dream.get("cost_est"),
            "cost_total": float(dream.get("cost_total") or 0.0),
        }
        for dream in dreams_sorted
    ]

    agent_rows = [
        {"label": agent, "name": agent, "value": float(spend or 0.0), "spend": float(spend or 0.0)}
        for agent, spend in sorted(by_agent.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
        if float(spend or 0.0) > 0
    ]

    stage_rows = [
        {"label": stage, "name": stage, "value": float(spend or 0.0), "spend": float(spend or 0.0)}
        for stage, spend in sorted(by_stage.items(), key=lambda item: float(item[1] or 0.0), reverse=True)
        if float(spend or 0.0) > 0
    ]
```

with:

```python
    dream_rows = [
        {
            "label": dream.get("name") or dream.get("id") or "Unnamed dream",
            "name": dream.get("name") or dream.get("id") or "Unnamed dream",
            "value": float(dream.get("cost_total") or 0.0),
            "estimated": float(dream.get("cost_total_estimated") or 0.0),
            "cost_est": dream.get("cost_est"),
            "cost_total": float(dream.get("cost_total") or 0.0),
        }
        for dream in dreams_sorted
    ]

    agent_rows = []
    for agent, bucket in sorted(by_agent.items(), key=lambda item: _bucket_total(item[1]), reverse=True):
        total = _bucket_total(bucket)
        if total <= 0:
            continue
        agent_rows.append({
            "label": agent, "name": agent, "value": total, "spend": total,
            "estimated": _bucket_estimated(bucket),
        })

    stage_rows = []
    for stage, bucket in sorted(by_stage.items(), key=lambda item: _bucket_total(item[1]), reverse=True):
        total = _bucket_total(bucket)
        if total <= 0:
            continue
        stage_rows.append({
            "label": stage, "name": stage, "value": total, "spend": total,
            "estimated": _bucket_estimated(bucket),
        })
```

- [ ] **Step 8: Add the `(est: $Y.YY)` suffix to `dream_label`, `agent_label`, `stage_label`**

Replace lines 2674-2695:

```python
    def dream_label(row, value):
        est = row.get("cost_est")
        if est is None:
            return _fmt_usd(value)
        return f"{_fmt_usd(value)} / est {_fmt_usd(est)}"

    def agent_color(row, value):
        agent = (row.get("label") or "").strip().lower()
        return {
            "claude": "#0d9e87",
            "agy": "#3b7dd8",
            "codex": "#1a9e5c",
            "grok": "#888888",
        }.get(agent, "#0d9e87")

    def agent_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        return f"{_fmt_usd(value)} ({_fmt_pct(pct)})"

    def stage_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        return f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
```

with:

```python
    def dream_label(row, value):
        est = row.get("cost_est")
        prov_estimated = row.get("estimated") or 0.0
        base = _fmt_usd(value)
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        if est is None:
            return base
        return f"{base} / est {_fmt_usd(est)}"

    def agent_color(row, value):
        agent = (row.get("label") or "").strip().lower()
        return {
            "claude": "#0d9e87",
            "agy": "#3b7dd8",
            "codex": "#1a9e5c",
            "grok": "#888888",
        }.get(agent, "#0d9e87")

    def agent_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        base = f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
        prov_estimated = row.get("estimated") or 0.0
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        return base

    def stage_label(row, value):
        pct = (value / total_usd * 100.0) if total_usd else 0.0
        base = f"{_fmt_usd(value)} ({_fmt_pct(pct)})"
        prov_estimated = row.get("estimated") or 0.0
        if prov_estimated > 0:
            base = f"{base} (est: {_fmt_usd(prov_estimated)})"
        return base
```

(`dream_color` at line 2668-2672 is unchanged — it only compares `value` against the budget `cost_est`, unaffected by provenance.)

- [ ] **Step 9: Pass `estimated_key="estimated"` at the three `render_bar_chart` call sites**

Replace lines 2833-2857:

```python
    {render_bar_chart(
        dream_rows,
        "By Dream",
        "value",
        dream_color,
        dream_label,
        "No dreams found",
        max_dream_cost,
    )}
    {render_bar_chart(
        agent_rows,
        "By Agent",
        "value",
        agent_color,
        agent_label,
        "No agent spend yet",
    )}
    {render_bar_chart(
        stage_rows,
        "By Stage",
        "value",
        stage_color,
        stage_label,
        "No stage spend yet",
    )}
```

with:

```python
    {render_bar_chart(
        dream_rows,
        "By Dream",
        "value",
        dream_color,
        dream_label,
        "No dreams found",
        max_dream_cost,
        estimated_key="estimated",
    )}
    {render_bar_chart(
        agent_rows,
        "By Agent",
        "value",
        agent_color,
        agent_label,
        "No agent spend yet",
        estimated_key="estimated",
    )}
    {render_bar_chart(
        stage_rows,
        "By Stage",
        "value",
        stage_color,
        stage_label,
        "No stage spend yet",
        estimated_key="estimated",
    )}
```

- [ ] **Step 10: Widen the summary grid to 5 columns and add the legend line**

Replace lines 2766-2772:

```python
    .subtle {{ color: var(--muted); margin-top: 6px; font-size: 14px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
```

with:

```python
    .subtle {{ color: var(--muted); margin-top: 6px; font-size: 14px; }}
    .summary {{
      display: grid;
      grid-template-columns: repeat(5, minmax(0, 1fr));
      gap: 14px;
      margin-bottom: 18px;
    }}
```

Replace lines 2813-2815:

```python
    @media (max-width: 980px) {{
      .summary {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }}
    }}
```

with:

```python
    @media (max-width: 980px) {{
      .summary {{ grid-template-columns: repeat(3, minmax(0, 1fr)); }}
    }}
```

Then locate the subtitle line (near line 2829):

```python
        <div class="subtle">Workspace spend, dream overruns, and agent allocation at a glance.</div>
```

Replace with:

```python
        <div class="subtle">Workspace spend, dream overruns, and agent allocation at a glance. Faded segments indicate estimated (non-structural) cost.</div>
```

- [ ] **Step 11: Run tests to verify they pass**

Run: `python3 -m pytest tests/test_viz.py -v -k "flags_estimated_rows or no_estimate_suffix"`
Expected: PASS (2 passed)

- [ ] **Step 12: Run the full test_viz.py suite to check for regressions**

Run: `python3 -m pytest tests/test_viz.py -v`
Expected: All tests pass, including `test_generate_effort_html_renders_svg_charts` (old flat-float `by_agent`/`by_stage` shape, verifies `_bucket_total`/`_bucket_estimated` backward compatibility) and `test_generate_effort_html_empty_state`.

- [ ] **Step 13: Commit**

```bash
git add synlynk/viz.py tests/test_viz.py
git commit -m "feat(viz): flag estimated cost rows in Effort & Cost tab (summary card + bar segments)"
```

---

### Task 3: Final regression and review (Claude, not dispatched)

This task is verification-only, performed directly by Claude (PM/reviewer role) in the `chore/vizor-cost-flagging-design` worktree after Tasks 1 and 2 have each been dispatched, verified, and cherry-picked onto this branch — mirroring Task 3 of the prior four adapter plans.

- [ ] **Step 1: Run the full test suite**

Run: `python3 -m pytest tests/test_viz.py tests/test_cost_ledger.py -v`
Expected: All tests pass. `test_cost_ledger.py` is included because Task 1 reads the `cost_source` column that Phase 1's ledger tests also exercise — confirms no cross-module regression.

- [ ] **Step 2: Manually inspect the generated HTML for a populated dataset**

```bash
python3 -c "
from synlynk.viz import generate_effort_html
data = {
    'workspace': {'name': 'test', 'updated_at': '2026-07-15T00:00:00Z', 'repos': []},
    'dreams': [{'id': 'd1', 'name': 'Test Arc', 'status': 'active', 'cost_total': 50.0, 'cost_total_estimated': 15.0, 'cost_est': 40.0}],
    'costs': {
        'total_usd': 50.0, 'total_usd_estimated': 15.0,
        'by_agent': {'claude': {'actual': 35.0, 'estimated': 15.0}},
        'by_stage': {'build': {'actual': 35.0, 'estimated': 15.0}},
    },
    'agents': {}, 'telemetry': {'recent': [], 'sentinel_alerts': []}, 'journeys': [],
    'workspace_map': {'edges': [], 'edge_types': {}}, 'notes': {},
}
html = generate_effort_html(data, port=8721)
assert 'fill-opacity=\"0.4\"' in html
assert '~Estimated' in html
print('OK — estimated segment and summary card present')
"
```

Expected output: `OK — estimated segment and summary card present`, no traceback.

- [ ] **Step 3: Confirm no other `by_agent`/`by_stage` consumers were missed**

```bash
grep -n "by_agent\[" synlynk/viz.py
grep -n "by_stage\[" synlynk/viz.py
```

Expected: only the lines touched in Task 1 (init, cost_rows loop, `by_stage[phase_key.lower()]` accumulation) — no stray consumer elsewhere in the file still treating these as flat floats.
