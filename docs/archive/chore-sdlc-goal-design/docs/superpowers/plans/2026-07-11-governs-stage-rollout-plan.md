# GOVERNS Stage Rollout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the drifted six-value `CYCLES` vocabulary (`dream/plan/work/ship/maintain/engage`, already inconsistently spelled `design`/`build` in places) with the locked seven-stage GOVERNS model (`goal/open/visualize/execute/release/notify/sustain`) across `hud.py`, `LAUNCH_TASK_TEMPLATES`, `task_to_cycle`, the `init` roadmap template, `migrate`'s markdown parser, and Vizor's data payload.

**Architecture:** This is a rename-and-remap rollout, not new subsystems — five independently testable surfaces (HUD rendering, task-template metadata, agent-handoff routing, project-init scaffolding, Vizor viz data) each get their vocabulary swapped for the seven canonical keys, with a data migration step to clean up existing `cycle_capability` rows that still hold old/drifted values.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest. No new dependencies.

**Spec:** `docs/superpowers/specs/2026-07-11-business-goal-sdlc-model-design.md`, Part 2 ("The seven stages" table, line 86-94).

**The seven canonical keys** (letter → key → rationale, from the spec table):

| Key | Stage | Command | Scope |
|---|---|---|---|
| `goal` | Goal | `synlynk goal` | Product intent, outcome, success criterion, deadline |
| `open` | Open | `synlynk open` | Kick off a work session/branch scoped to a story |
| `visualize` | Visualize | `synlynk viz` | Map architecture/structure before building |
| `execute` | Execute | `synlynk exec`/`synlynk dispatch` | The build itself — agent-swarm dispatch |
| `release` | Release | `synlynk release` | Cut the release: gates + human sign-off |
| `notify` | Notify | (docs convention) | Market-facing release notes/blog/changelog for *this* release |
| `sustain` | Sustain | `synlynk repair`/`doctor`/`status` | Operational continuity (Maintain + Alert sub-modes) |

---

## Task 1: `hud.py` — rename `CYCLES` and `CYCLE_COLOURS`

**Files:**
- Modify: `synlynk/hud.py:13-22`
- Test: `tests/test_hud_cycles.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_hud_cycles.py
from synlynk.hud import CYCLES, CYCLE_COLOURS


def test_cycles_is_governs_seven_stages():
    assert CYCLES == ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]


def test_cycle_colours_covers_every_cycle():
    assert set(CYCLE_COLOURS.keys()) == set(CYCLES)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_hud_cycles.py -v`
Expected: FAIL — `assert ["dream", "plan", "work", "ship", "maintain", "engage"] == ["goal", ...]`

- [ ] **Step 3: Replace the definitions**

In `synlynk/hud.py`, replace lines 13-22:

```python
CYCLES = ["goal", "open", "visualize", "execute", "release", "notify", "sustain"]

CYCLE_COLOURS = {
    "goal": "\033[38;5;141m",
    "open": "\033[38;5;75m",
    "visualize": "\033[38;5;213m",
    "execute": "\033[38;5;208m",
    "release": "\033[38;5;71m",
    "notify": "\033[38;5;220m",
    "sustain": "\033[38;5;178m",
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_hud_cycles.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Update the default-cycle fallback string throughout `hud.py`**

`hud.py` has five call sites that default an unset job's cycle to the old `"work"` value: `cycle_summary()` (line ~152 `job.get("cycle", "work")`), `render_right_panel()`'s job loop (line ~404 `job.get("cycle", "work")`), and the matching literal in the status line at line ~410 (`job.get('cycle','work')`), plus the `filter` call in the top-of-file job lookup (line ~144 `job.get("cycle", "work") != cycle`). Replace every `"work"` default literal with `"execute"` (the GOVERNS key that owns the build/dispatch loop, matching the old `"work"` semantics). Use this command to find and confirm all sites before editing:

```bash
grep -n '"cycle", "work"\|cycle","work"' synlynk/hud.py
```

Edit each matched line, changing `"work"` to `"execute"`.

- [ ] **Step 6: Write a regression test for the default fallback**

```python
def test_cycle_summary_defaults_unset_job_to_execute(tmp_path, monkeypatch):
    import json
    from synlynk.hud import JobStore

    jobs_file = tmp_path / "jobs.json"
    jobs_file.write_text(json.dumps([{"status": "running", "agent": "codex", "task": "t"}]))
    store = JobStore(str(jobs_file))
    summary = store.cycle_summary()
    assert summary["execute"]["running"] == 1
```

(If `JobStore` takes a different constructor signature than `(path)`, check `synlynk/hud.py`'s class definition above line 140 and adjust the call to match — the class wraps the jobs file path already referenced by `_load()` at line ~148.)

- [ ] **Step 7: Run full hud test suite**

Run: `pytest tests/test_hud_cycles.py -v`
Expected: PASS (3 tests)

- [ ] **Step 8: Commit**

```bash
git add synlynk/hud.py tests/test_hud_cycles.py
git commit -m "feat(hud): rename CYCLES/CYCLE_COLOURS to GOVERNS seven-stage keys"
```

---

## Task 2: `LAUNCH_TASK_TEMPLATES` — remap all 15 `"cycle"` values

**Files:**
- Modify: `synlynk/__init__.py` (15 exact lines below)
- Test: `tests/test_launch_templates.py` (new)

**Remap key** (id → old value → new value → rationale):

| Line | Template id | Old value | New value | Rationale |
|---|---|---|---|---|
| 114 | `arch-review` | `dream` | `visualize` | Architecture review = mapping structure (V scope) |
| 135 | `product-assessment` | `dream` | `goal` | Product-fit assessment = outcome/intent (G scope) |
| 154 | `lifecycle-setup` | `plan` | `open` | Session/workflow kickoff (O scope) |
| 177 | `add-tests` | `plan` | `execute` | Test-writing is part of the build loop (E scope) |
| 202 | `setup-ci` | `plan` | `execute` | CI pipeline is build infrastructure (E scope) |
| 222 | `docs-audit` | `design` (drift) | `notify` | Docs deliverable maps to Notify's documentation scope |
| 244 | `security-scan` | `dream` | `sustain` | Ongoing security posture = Sustain/Alert |
| 268 | `perf-baseline` | `dream` | `sustain` | Baseline for ongoing monitoring = Sustain/Maintain |
| 292 | `cross-repo-map` | `dream` | `visualize` | Cross-repo mapping = architecture visualization (V scope) |
| 313 | `type-safety` | `design` (drift) | `execute` | Type-safety work happens in the build loop (E scope) |
| 343 | `a11y-audit` | `design` (drift) | `release` | Accessibility gate belongs before shipping (R scope) |
| 367 | `db-schema-review` | `dream` | `visualize` | Schema review = architecture mapping (V scope) |
| 388 | `refactor-module` | `design` (drift) | `execute` | Refactoring is build-loop work (E scope) |
| 413 | `reduce-complexity` | `build` (drift) | `execute` | Already build-loop work; correcting the drifted key (E scope) |
| 436 | `fix-churn-debt` | `sustain` | `sustain` | Already correct — key unchanged |

- [ ] **Step 1: Write the failing test**

```python
# tests/test_launch_templates.py
from synlynk import LAUNCH_TASK_TEMPLATES
from synlynk.hud import CYCLES


def test_every_template_cycle_is_a_governs_key():
    bad = [(t["id"], t["cycle"]) for t in LAUNCH_TASK_TEMPLATES if t["cycle"] not in CYCLES]
    assert bad == []


def test_specific_template_remaps():
    by_id = {t["id"]: t["cycle"] for t in LAUNCH_TASK_TEMPLATES}
    assert by_id["arch-review"] == "visualize"
    assert by_id["product-assessment"] == "goal"
    assert by_id["lifecycle-setup"] == "open"
    assert by_id["docs-audit"] == "notify"
    assert by_id["a11y-audit"] == "release"
    assert by_id["reduce-complexity"] == "execute"
    assert by_id["fix-churn-debt"] == "sustain"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_launch_templates.py -v`
Expected: FAIL — `assert bad == []` (15 entries with old values)

- [ ] **Step 3: Edit each of the 15 `"cycle"` lines**

Use the Remap key table above. For each line number, replace the value in-place — e.g. line 114:

```python
        "cycle": "visualize",
```

Repeat for all 15 lines listed in the table (114, 135, 154, 177, 202, 222, 244, 268, 292, 313, 343, 367, 388, 413, 436), using the exact `New value` column for each.

- [ ] **Step 4: Update the `lifecycle-setup` prompt text's own vocabulary**

In `synlynk/__init__.py`, inside the `lifecycle-setup` template's `prompt_template` (currently lines 157-166), replace this line:

```python
            "For each story, assign a cycle phase (dream/design/plan/build/ship/sustain) "
```

with:

```python
            "For each story, assign a cycle phase (goal/open/visualize/execute/release/notify/sustain) "
```

Also update the template's `title` (line 152, currently `"Set up 6-cycle workflow for this repo"`) and `description` (line 153, currently `"Initialise lifecycle tracking in state.db. Label open stories by cycle."`) to say **7-cycle** instead of **6-cycle**:

```python
        "title": "Set up 7-stage GOVERNS workflow for this repo",
        "description": "Initialise GOVERNS lifecycle tracking in state.db. Label open stories by stage.",
```

- [ ] **Step 5: Run test to verify it passes**

Run: `pytest tests/test_launch_templates.py -v`
Expected: PASS (2 tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_launch_templates.py
git commit -m "feat(templates): remap LAUNCH_TASK_TEMPLATES cycle values to GOVERNS keys"
```

---

## Task 3: `task_to_cycle` map in `_recommend_handoff_agent`

**Files:**
- Modify: `synlynk/__init__.py:5539-5548`
- Test: `tests/test_handoff_cycle_map.py` (new)

**Remap key:**

| Task type | Old value | New value | Rationale |
|---|---|---|---|
| `implement` | `work` | `execute` | Build loop |
| `review` | `engage` (orphaned — no longer exists) | `execute` | Code review is a checkpoint inside the build/dispatch loop (E scope: "human tech-lead greenlights") |
| `plan` | `plan` | `open` | Session/approach kickoff (O scope) |
| `debug` | `maintain` | `sustain` | Operational continuity, Sustain/Alert sub-mode |
| `test` | `maintain` | `execute` | Test-writing/running is part of the build loop |
| `docs` | `maintain` | `notify` | Docs deliverable maps to Notify's documentation scope |
| `default` | `work` | `execute` | Build loop is the default assumption |

- [ ] **Step 1: Write the failing test**

```python
# tests/test_handoff_cycle_map.py
from synlynk import _recommend_handoff_agent


def test_task_to_cycle_uses_governs_keys(monkeypatch):
    import synlynk
    captured = {}

    class FakeConn:
        def execute(self, query, params):
            captured["cycle"] = params[0]
            class R:
                def fetchall(self):
                    return []
            return R()

    monkeypatch.setattr(
        "synlynk.status._classify_task_type", lambda prompt: "review", raising=False
    )
    _recommend_handoff_agent("review this PR", "codex", FakeConn())
    assert captured["cycle"] == "execute"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_handoff_cycle_map.py -v`
Expected: FAIL — `assert 'engage' == 'execute'` (or an AttributeError if `synlynk.status._classify_task_type` isn't monkeypatchable exactly this way — if so, adjust the import path in the test to match the actual `try/except` import at the top of `_recommend_handoff_agent`, which does `from synlynk.status import _classify_task_type`)

- [ ] **Step 3: Replace the `task_to_cycle` dict**

In `synlynk/__init__.py`, replace lines 5539-5548:

```python
    task_to_cycle = {
        "implement": "execute",
        "review": "execute",
        "plan": "open",
        "debug": "sustain",
        "test": "execute",
        "docs": "notify",
        "default": "execute",
    }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_handoff_cycle_map.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_handoff_cycle_map.py
git commit -m "feat(dispatch): remap task_to_cycle to GOVERNS keys, resolve orphaned 'engage'"
```

---

## Task 4: `cycle_capability` data cleanup migration

**Files:**
- Modify: `synlynk/db.py` (`_migrate_db`, alongside the existing `DELETE FROM cycle_capability WHERE cycle IN (...)` precedent)
- Test: `tests/test_goals.py` or a new `tests/test_cycle_migration.py`

**Files:**
- Modify: `synlynk/db.py:119-144` region (find the existing precedent line via `grep -n "DELETE FROM cycle_capability" synlynk/db.py`)
- Test: `tests/test_cycle_migration.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cycle_migration.py
from synlynk import _get_db


def test_migrate_remaps_old_cycle_values_in_cycle_capability():
    conn = _get_db()
    conn.execute(
        "INSERT INTO cycle_capability (agent_name, cycle, support, verb_count, full_count, partial_count) "
        "VALUES ('codex', 'work', 'full', 3, 3, 0)"
    )
    conn.execute(
        "INSERT INTO cycle_capability (agent_name, cycle, support, verb_count, full_count, partial_count) "
        "VALUES ('codex', 'ship', 'full', 2, 2, 0)"
    )
    conn.commit()
    conn.close()

    # re-open to re-trigger _migrate_db
    conn = _get_db()
    rows = {r[0] for r in conn.execute("SELECT DISTINCT cycle FROM cycle_capability").fetchall()}
    conn.close()
    assert rows == {"execute", "release"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cycle_migration.py -v`
Expected: FAIL — `assert {'work', 'ship'} == {'execute', 'release'}`

- [ ] **Step 3: Add the remap migration**

In `synlynk/db.py`, `_migrate_db()`, immediately after the existing `"DELETE FROM cycle_capability WHERE cycle IN ('design','build','sustain')"` line (find it via `grep -n "cycle_capability WHERE cycle" synlynk/db.py`), add:

```python
    cycle_remap = {
        "dream": "goal", "design": "visualize", "plan": "open",
        "work": "execute", "build": "execute", "ship": "release",
        "maintain": "sustain", "engage": "execute",
    }
    for old, new in cycle_remap.items():
        conn.execute(
            "UPDATE cycle_capability SET cycle=? WHERE cycle=?", (new, old)
        )
```

Note: this UPDATE-based remap supersedes the older DELETE-based cleanup for the `design`/`build`/`sustain` drift values — those now get correctly remapped instead of deleted (`design`→`visualize`, `build`→`execute`; `sustain` needs no change since it's already a valid GOVERNS key). Leave the existing DELETE line in place above this block; running DELETE first then this UPDATE is harmless since DELETE removes only exact-drift rows that this loop's keys also cover — the DELETE becomes a no-op given this migration runs after it, but removing the historical DELETE line is out of scope for this plan to avoid touching unrelated migration history.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cycle_migration.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests, including Task 1-3's new tests and pre-existing suite)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py tests/test_cycle_migration.py
git commit -m "feat(migrate): remap legacy cycle_capability values to GOVERNS keys"
```

---

## Task 5: `init` roadmap template — add `## Business Goals` section

**Files:**
- Modify: `synlynk/__init__.py:4452-4465` (`fallback_roadmap` f-string, inside the scaffold function above line 4440)
- Test: `tests/test_init_business_goals.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_init_business_goals.py
def test_fallback_roadmap_includes_business_goals_section():
    import synlynk
    import inspect
    src = inspect.getsource(synlynk)
    assert "## Business Goals" in src
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_init_business_goals.py -v`
Expected: FAIL — `assert "## Business Goals" in src`

- [ ] **Step 3: Add the section to `fallback_roadmap`**

In `synlynk/__init__.py`, the `fallback_roadmap` f-string currently reads (lines 4452-4461):

```python
    fallback_roadmap = f"""\
# {name} Roadmap
{caveat}
**Positioning:** [Describe what {name} is building toward]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
| v0.1.0 | Initial release | ✅ Shipped | — |
| v0.2.0 | [Next milestone] | 🔜 Next | — |

## Recent work (from git history — {commit_count} commits, {langs})
{recent_work}
"""
```

Replace it with (adding the new section between the version table and "Recent work"):

```python
    fallback_roadmap = f"""\
# {name} Roadmap
{caveat}
**Positioning:** [Describe what {name} is building toward]

## Business Goals
[Define outcomes here with `synlynk goal create --outcome "..." --criterion "..."`.
Each arc below can be tagged `<!-- goal:goal-xxxxxxxx -->` to link it to a goal.]

| Version | Theme | Status | Target |
| :--- | :--- | :--- | :--- |
| v0.1.0 | Initial release | ✅ Shipped | — |
| v0.2.0 | [Next milestone] | 🔜 Next | — |

## Recent work (from git history — {commit_count} commits, {langs})
{recent_work}
"""
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_init_business_goals.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_init_business_goals.py
git commit -m "feat(init): add Business Goals section to fallback roadmap.md template"
```

---

## Task 6: `migrate` — parse `<!-- goal:G -->` tags on roadmap arcs

**Files:**
- Modify: `synlynk/db.py:34-56` (`_parse_roadmap_md`)
- Test: `tests/test_goal_tag_parsing.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_goal_tag_parsing.py
from synlynk.db import _parse_roadmap_md


def test_parse_roadmap_md_extracts_goal_tag():
    content = "## v0.11.0 - Agent Ecosystem <!-- goal:goal-a1b2c3d4 -->\n- Ship the thing\n"
    arcs, phases = _parse_roadmap_md(content)
    assert arcs[0]["goal_id"] == "goal-a1b2c3d4"


def test_parse_roadmap_md_goal_id_none_when_untagged():
    content = "## v0.10.0 - Untagged\n- Ship the thing\n"
    arcs, phases = _parse_roadmap_md(content)
    assert arcs[0]["goal_id"] is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_goal_tag_parsing.py -v`
Expected: FAIL — `KeyError: 'goal_id'`

- [ ] **Step 3: Extend `_parse_roadmap_md`**

In `synlynk/db.py`, replace the arc-header branch (lines 36-43):

```python
def _parse_roadmap_md(content: str) -> tuple:
    arcs, phases, current_arc = [], [], None
    for line in content.splitlines():
        arc_m = re.match(r'^## (v[\d.]+[\w.-]*)\s*[-—]?\s*(.*)', line)
        if arc_m:
            version = arc_m.group(1).strip()
            title = arc_m.group(2).strip() or None
            goal_m = re.search(r'<!--\s*goal:(\S+)\s*-->', line)
            goal_id = goal_m.group(1) if goal_m else None
            if title:
                title = re.sub(r'<!--\s*goal:\S+\s*-->', '', title).strip() or None
            status = ('shipped' if ('✅' in line or 'shipped' in line.lower()) else
                      'in_progress' if ('🚧' in line or 'in progress' in line.lower()) else 'planned')
            current_arc = {'version': version, 'title': title, 'status': status, 'goal_id': goal_id}
            arcs.append(current_arc)
            continue
```

(The rest of the function — the `phase_m` branch below — is unchanged.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_goal_tag_parsing.py -v`
Expected: PASS (2 tests)

- [ ] **Step 5: Run the full test suite to catch any callers of `_parse_roadmap_md`'s arc dict shape**

Run: `pytest tests/ -v -k "roadmap or migrate"`
Expected: PASS — if any pre-existing test asserts an exact dict shape without `goal_id`, update that assertion to include `'goal_id': None` for untagged fixtures. Check `grep -rn "_parse_roadmap_md\|arcs\[0\]" tests/` for call sites first.

- [ ] **Step 6: Wire `goal_id` into the DB import (`_migrate_import` / `cmd_migrate`)**

Run `grep -n "arcs, phases = _parse_roadmap_md\|INSERT INTO roadmap_arcs" synlynk/db.py` to find the import call site (around line 381) and the `INSERT INTO roadmap_arcs` statement. Add `goal_id` to the INSERT's column list and values tuple, reading `arc.get('goal_id')` from each parsed arc dict, so imported arcs carry their goal link into the `goal_id` column added in the BS-8 plan (Task 2 of `2026-07-11-bs8-goal-hierarchy-plan.md`). Write a test asserting the imported row's `goal_id` column matches the tagged value, following the existing import-test pattern in `tests/` (grep for `cmd_migrate` in `tests/` to find the closest existing test to extend).

- [ ] **Step 7: Commit**

```bash
git add synlynk/db.py tests/test_goal_tag_parsing.py
git commit -m "feat(migrate): parse goal tags on roadmap arcs and wire into roadmap_arcs.goal_id"
```

---

## Task 7: Vizor — nest `goals` above `dreams` in `viz.py` payload

**Files:**
- Modify: `synlynk/viz.py:82-100` (`generate_viz_data`)
- Test: `tests/test_viz_goals.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_viz_goals.py
from synlynk.viz import generate_viz_data


def test_viz_data_includes_goals_key():
    data = generate_viz_data()
    assert "goals" in data
    assert isinstance(data["goals"], list)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_viz_goals.py -v`
Expected: FAIL — `assert "goals" in data`

- [ ] **Step 3: Add the `goals` key and query**

In `synlynk/viz.py`, `generate_viz_data()` (starts line 82), find the line initializing `"dreams": []` (line 98) inside the default/empty-state dict, and add a `"goals": []` sibling key immediately before it. Then find where `dreams = []` is populated for real (line 407) and `data["dreams"] = dreams` is assigned (line 462) — immediately before that assignment, add:

```python
    conn = _get_db()
    goal_rows = conn.execute(
        "SELECT goal_id, outcome, criterion, deadline, status FROM goals WHERE status='active' "
        "ORDER BY created_at DESC"
    ).fetchall()
    conn.close()
    goals = [
        {"id": r[0], "outcome": r[1], "criterion": r[2], "deadline": r[3], "status": r[4]}
        for r in goal_rows
    ]
    data["goals"] = goals
```

(Place this directly before the existing `data["dreams"] = dreams` line so both keys are set together.)

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_viz_goals.py -v`
Expected: PASS

- [ ] **Step 5: Run the full test suite**

Run: `pytest tests/ -v`
Expected: PASS (all tests)

- [ ] **Step 6: Commit**

```bash
git add synlynk/viz.py tests/test_viz_goals.py
git commit -m "feat(viz): surface active Business Goals in Vizor data payload"
```

**Note — front-end rendering out of scope:** This task wires the `goals` array into the JSON payload consumed by `synlynk/viz.py`'s embedded JS (`window.VIZOR_DATA`). Rendering a "Goals" panel above the existing dream tube-map UI (the `renderDream`/`dreams.map(renderDream)` JS at lines ~1218-1223) is a front-end change involving the embedded HTML/JS template — per this project's role split, that implementation is a separate dispatch to Agy (CSS/templates owner), not part of this backend-focused plan. Flag it as a follow-up dispatch task once this plan merges.

---

## Self-Review Notes

- **Spec coverage:** All three "Open Items for Implementation Planning" from the design spec are addressed — `LAUNCH_TASK_TEMPLATES` remap (Task 2), `task_to_cycle` remap with the orphaned `"review": "engage"` resolved (Task 3), and BS-8 is the separate companion plan. The Part 3 rollout mechanics (init/migrate/Vizor/HUD) are covered by Tasks 1, 4, 5, 6, 7. The `abstraction-level dev/team/enterprise mapping` sub-section of Part 3 is **not** implemented here — it describes a config/gating concern (`.synlynk/config.json` mode field), not a vocabulary rename, and is out of scope for a stage-renaming plan; flagged as a follow-up plan.
- **Placeholder scan:** none found — every step has real code grounded in lines read directly from the current `synlynk/hud.py`, `synlynk/__init__.py`, `synlynk/db.py`, and `synlynk/viz.py`.
- **Type/signature consistency:** `CYCLES`/`CYCLE_COLOURS` keys used identically across Tasks 1, 2, 3, 7. `cycle_capability.cycle` values from Task 4 match the same seven keys asserted in Task 1's test.
- **Judgment calls made during planning (not left as open items, but worth surfacing to the user):** the exact per-template remap in Task 2 and the `"review"→"execute"` resolution in Task 3 are reasoned inferences from each template's `id`/`title` and the spec's stage-scope descriptions, not values pulled from an explicit existing mapping. Worth a quick human skim before dispatch, since a domain expert may weight a couple of these differently (e.g., `setup-ci` could arguably sit in `release` instead of `execute`).
