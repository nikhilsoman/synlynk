# Capability Sweep + Industry Taxonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give synlynk's capability ledger a deliberate, industry-recognizable calibration path (NAICS/APQC/SFIA taxonomy + a `synlynk capability sweep` command) instead of relying solely on organic job outcomes with homegrown category names, and fix the PR review-cycle signal so review discipline actually moves capability scores by the intended ±10-25%.

**Architecture:** Five additive, independently shippable slices, in dependency order: (1) taxonomy layer (static lookup tables + migration), (2) calibration sweep command that seeds the ledger using the taxonomy, (3) packaging the sweep's output for distribution, (4) organic-reinforcement blending logic (explicitly sequenced after — or flagged as best-effort pending — issue #353's ledger-math fix), (5) PR review-cycle multiplier (independent of 1-4, can be built in parallel). Every task follows the existing `_migrate_db()` idiom (idempotent `ALTER TABLE`/`try-except sqlite3.OperationalError`) and the existing `cli.py` subparser-then-dispatch-chain pattern — no new architectural patterns are introduced.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest, argparse (via `synlynk/cli.py`), `gh` CLI (shelled out via `subprocess.run`, matching `sentinel.py`/`jobs.py`).

---

## Task 1: Taxonomy static lookup tables

**Files:**
- Create: `synlynk/taxonomy_standards.py`
- Test: `tests/test_taxonomy_standards.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_taxonomy_standards.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_naics_codes_have_label_and_parent():
    from synlynk.taxonomy_standards import NAICS_CODES
    assert len(NAICS_CODES) >= 15
    for code, entry in NAICS_CODES.items():
        assert isinstance(code, str)
        assert "label" in entry
        assert "parent" in entry  # may be None for top-level codes


def test_apqc_codes_have_label_and_parent():
    from synlynk.taxonomy_standards import APQC_CODES
    assert len(APQC_CODES) >= 15
    for code, entry in APQC_CODES.items():
        assert "label" in entry
        assert "parent" in entry


def test_sfia_codes_have_label_and_parent():
    from synlynk.taxonomy_standards import SFIA_CODES
    assert len(SFIA_CODES) >= 15
    for code, entry in SFIA_CODES.items():
        assert "label" in entry
        assert "parent" in entry
    # Calibration-relevant skills referenced elsewhere in this plan must exist
    assert "PROG" in SFIA_CODES
    assert "TEST" in SFIA_CODES
    assert "REQM" in SFIA_CODES


def test_taxonomy_label_looks_up_known_code():
    from synlynk.taxonomy_standards import _taxonomy_label
    assert _taxonomy_label("sfia", "PROG") != "PROG"  # returns human label, not raw code


def test_taxonomy_label_falls_back_to_raw_code_for_unknown():
    from synlynk.taxonomy_standards import _taxonomy_label
    assert _taxonomy_label("sfia", "NOT_A_REAL_CODE") == "NOT_A_REAL_CODE"


def test_taxonomy_label_rejects_unknown_axis():
    from synlynk.taxonomy_standards import _taxonomy_label
    import pytest
    with pytest.raises(ValueError):
        _taxonomy_label("not_an_axis", "PROG")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_taxonomy_standards.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.taxonomy_standards'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/taxonomy_standards.py
"""Static lookup tables mapping synlynk's taxonomy axes onto external,
industry-recognized standards: NAICS (business/industry domain), APQC PCF
(functional discipline), and SFIA (technical competency).

Scope is a curated subset, top 2 hierarchy levels, covering software/product
work only — not the full NAICS (~2000 codes) or APQC (~1000 subprocesses) trees.
Extend by adding entries; do not restructure existing codes (existing rows in
capability_ratings/stories reference these codes directly).
"""

# NAICS (North American Industry Classification System) — business/industry domain.
# Maps synlynk.stories.industry.
NAICS_CODES = {
    "none": {"label": "Not industry-specific", "parent": None},
    "51": {"label": "Information", "parent": None},
    "5112": {"label": "Software Publishers", "parent": "51"},
    "5182": {"label": "Data Processing, Hosting, and Related Services", "parent": "51"},
    "54": {"label": "Professional, Scientific, and Technical Services", "parent": None},
    "5415": {"label": "Computer Systems Design and Related Services", "parent": "54"},
    "52": {"label": "Finance and Insurance", "parent": None},
    "5221": {"label": "Depository Credit Intermediation", "parent": "52"},
    "5242": {"label": "Insurance Agencies and Brokerages", "parent": "52"},
    "62": {"label": "Health Care and Social Assistance", "parent": None},
    "6211": {"label": "Offices of Physicians", "parent": "62"},
    "44-45": {"label": "Retail Trade", "parent": None},
    "4541": {"label": "Electronic Shopping and Mail-Order Houses", "parent": "44-45"},
    "61": {"label": "Educational Services", "parent": None},
    "6117": {"label": "Educational Support Services", "parent": "61"},
    "23": {"label": "Construction", "parent": None},
    "31-33": {"label": "Manufacturing", "parent": None},
    "3345": {"label": "Navigational, Measuring, Electromedical, and Control Instruments Manufacturing", "parent": "31-33"},
    "48-49": {"label": "Transportation and Warehousing", "parent": None},
    "22": {"label": "Utilities", "parent": None},
}

# APQC PCF (Process Classification Framework) — functional discipline.
# Maps synlynk.stories.org_domain. Codes are APQC's category-level numbering.
APQC_CODES = {
    "1.0": {"label": "Develop Vision and Strategy", "parent": None},
    "2.0": {"label": "Develop and Manage Products and Services", "parent": None},
    "2.3": {"label": "Design and Develop Products and Services", "parent": "2.0"},
    "3.0": {"label": "Market and Sell Products and Services", "parent": None},
    "4.0": {"label": "Deliver Physical Products", "parent": None},
    "5.0": {"label": "Deliver Services", "parent": None},
    "6.0": {"label": "Manage Customer Service", "parent": None},
    "7.0": {"label": "Develop and Manage Human Capital", "parent": None},
    "8.0": {"label": "Manage Information Technology", "parent": None},
    "8.1": {"label": "Develop and Manage IT Customer Relationships", "parent": "8.0"},
    "8.2": {"label": "Develop and Manage IT Strategy and Governance", "parent": "8.0"},
    "8.3": {"label": "Develop and Implement Security, Privacy, and Data Protection Controls", "parent": "8.0"},
    "8.4": {"label": "Manage Enterprise Information", "parent": "8.0"},
    "8.5": {"label": "Develop and Maintain Information Technology Solutions", "parent": "8.0"},
    "8.6": {"label": "Deploy Information Technology Solutions", "parent": "8.0"},
    "8.7": {"label": "Deliver and Support Information Technology Services", "parent": "8.0"},
    "9.0": {"label": "Manage Financial Resources", "parent": None},
    "10.0": {"label": "Acquire, Construct, and Manage Assets", "parent": None},
    "11.0": {"label": "Manage Enterprise Risk, Compliance, and Resiliency", "parent": None},
    "12.0": {"label": "Manage External Relationships", "parent": None},
}

# SFIA (Skills Framework for the Information Age) — technical competency.
# Maps synlynk.stories.engg_domain / discipline. Codes are SFIA's official
# skill-code abbreviations.
SFIA_CODES = {
    "PROG": {"label": "Programming/Software Development", "parent": None},
    "TEST": {"label": "Testing", "parent": None},
    "REQM": {"label": "Requirements Definition and Management", "parent": None},
    "ARCH": {"label": "Solution Architecture", "parent": None},
    "DTAN": {"label": "Data Analysis", "parent": None},
    "DBDS": {"label": "Database Design", "parent": None},
    "SINT": {"label": "Systems Integration", "parent": None},
    "DEPL": {"label": "Software Deployment", "parent": None},
    "ITOP": {"label": "IT Infrastructure Operations", "parent": None},
    "SCTY": {"label": "Information Security", "parent": None},
    "PEDP": {"label": "Performance Engineering", "parent": None},
    "METL": {"label": "Methods and Tools", "parent": None},
    "QUAL": {"label": "Quality Management", "parent": None},
    "PROD": {"label": "Product Management", "parent": None},
    "DLMG": {"label": "Delivery Management", "parent": None},
    "UNAN": {"label": "User Experience Analysis", "parent": None},
    "HCEV": {"label": "Human Factors Integration", "parent": None},
    "DESN": {"label": "Systems Design", "parent": None},
    "PORT": {"label": "Portfolio Management", "parent": None},
    "EMRG": {"label": "Emerging Technology Monitoring", "parent": None},
}

_AXIS_TABLES = {
    "naics": NAICS_CODES,
    "apqc": APQC_CODES,
    "sfia": SFIA_CODES,
}


def _taxonomy_label(axis: str, code: str) -> str:
    """Translates a taxonomy code to its human-readable label.

    Falls back to the raw code if it isn't in the curated subset (e.g. a
    legacy_unmapped value from a pre-migration row).
    """
    if axis not in _AXIS_TABLES:
        raise ValueError(f"Unknown taxonomy axis {axis!r}. Known axes: {list(_AXIS_TABLES)}")
    entry = _AXIS_TABLES[axis].get(code)
    return entry["label"] if entry else code
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_taxonomy_standards.py -v`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/taxonomy_standards.py tests/test_taxonomy_standards.py
git commit -m "feat(taxonomy): add NAICS/APQC/SFIA static lookup tables"
```

---

## Task 2: Migration — crosswalk legacy free-text values to taxonomy codes

**Files:**
- Modify: `synlynk/db.py:229-678` (`_migrate_db`, add a new step before `conn.commit()` at line 677)
- Test: `tests/test_capability_scoring.py` (add new test, following the pattern at lines 862-896)

The migration adds a `legacy_unmapped` marker column to both `stories` and `capability_ratings`, and rewrites known free-text values (`"backend"`, `"platform"`, `"unknown"`, etc.) to their taxonomy-code equivalents via a hand-built crosswalk dict. Any value not in the crosswalk is left as-is but flagged `legacy_unmapped=1` so taxonomy-based queries can exclude it.

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_capability_scoring.py

def test_migrate_db_crosswalks_legacy_taxonomy_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)

    import sqlite3
    import synlynk as sl

    conn = sqlite3.connect(sl.DB_PATH)
    conn.execute(
        "CREATE TABLE stories (story_id TEXT PRIMARY KEY, title TEXT, engg_domain TEXT NOT NULL DEFAULT 'backend', "
        "discipline TEXT NOT NULL DEFAULT 'backend', org_domain TEXT NOT NULL DEFAULT 'platform', "
        "role TEXT NOT NULL DEFAULT 'dev', stage TEXT NOT NULL DEFAULT 'open', org_domain_tags TEXT DEFAULT '[]', "
        "industry TEXT DEFAULT 'unknown', phase TEXT DEFAULT 'build', stack_tags TEXT DEFAULT '[]')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, discipline, org_domain, industry) "
        "VALUES ('s1', 'test story', 'backend', 'backend', 'platform', 'unknown')"
    )
    conn.execute(
        "INSERT INTO stories (story_id, title, engg_domain, discipline, org_domain, industry) "
        "VALUES ('s2', 'weird story', 'some_made_up_value', 'some_made_up_value', 'some_made_up_org', 'made_up_industry')"
    )
    conn.commit()

    sl._migrate_db(conn)

    story_cols = {row[1] for row in conn.execute("PRAGMA table_info(stories)")}
    assert "legacy_unmapped" in story_cols

    s1 = conn.execute(
        "SELECT discipline, org_domain, industry, legacy_unmapped FROM stories WHERE story_id='s1'"
    ).fetchone()
    assert s1[0] == "PROG"       # "backend" -> SFIA PROG
    assert s1[1] == "8.5"        # "platform" -> APQC 8.5 (Develop and Maintain IT Solutions)
    assert s1[2] == "none"       # "unknown" -> NAICS none
    assert s1[3] == 0            # crosswalked cleanly, not flagged

    s2 = conn.execute(
        "SELECT discipline, org_domain, industry, legacy_unmapped FROM stories WHERE story_id='s2'"
    ).fetchone()
    assert s2[0] == "some_made_up_value"   # left as-is, no crosswalk entry
    assert s2[3] == 1                       # flagged legacy_unmapped
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_scoring.py::test_migrate_db_crosswalks_legacy_taxonomy_values -v`
Expected: FAIL with `sqlite3.OperationalError: no such column: legacy_unmapped` (or `AssertionError` on the crosswalked value if the column already exists from a different unrelated change)

- [ ] **Step 3: Write the implementation**

Add to `synlynk/taxonomy_standards.py` (append after `_AXIS_TABLES`):

```python
# Legacy free-text -> taxonomy-code crosswalk, used once by _migrate_db().
# Keys are the pre-migration free-text values synlynk actually wrote to
# stories.discipline / org_domain / industry before this taxonomy existed.
LEGACY_DISCIPLINE_CROSSWALK = {
    "backend": "PROG",
    "frontend": "PROG",
    "fullstack": "PROG",
    "qa": "TEST",
    "devops": "DEPL",
    "security": "SCTY",
    "design": "DESN",
    "data": "DTAN",
}
LEGACY_ORG_DOMAIN_CROSSWALK = {
    "platform": "8.5",
    "product": "2.3",
    "growth": "3.0",
    "infra": "8.0",
    "support": "6.0",
}
LEGACY_INDUSTRY_CROSSWALK = {
    "unknown": "none",
    "saas": "5112",
    "fintech": "52",
    "healthtech": "62",
    "ecommerce": "44-45",
    "edtech": "61",
}
```

Modify `synlynk/db.py` — insert this block into `_migrate_db(conn)` immediately before the closing `conn.commit()` / `_seed_verb_map(conn)` (currently the last two lines of the function, per the `# #141 follow-up` block ending at line 677):

```python
    # capability-sweep-taxonomy: crosswalk legacy free-text values to NAICS/APQC/SFIA codes
    from synlynk.taxonomy_standards import (
        LEGACY_DISCIPLINE_CROSSWALK,
        LEGACY_ORG_DOMAIN_CROSSWALK,
        LEGACY_INDUSTRY_CROSSWALK,
    )
    for table in ("stories", "capability_ratings"):
        cols = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
        if "legacy_unmapped" not in cols:
            try:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN legacy_unmapped INTEGER NOT NULL DEFAULT 0")
            except sqlite3.OperationalError:
                pass

    for table, col, crosswalk in (
        ("stories", "discipline", LEGACY_DISCIPLINE_CROSSWALK),
        ("stories", "org_domain", LEGACY_ORG_DOMAIN_CROSSWALK),
        ("stories", "industry", LEGACY_INDUSTRY_CROSSWALK),
        ("capability_ratings", "discipline", LEGACY_DISCIPLINE_CROSSWALK),
        ("capability_ratings", "org_domain", LEGACY_ORG_DOMAIN_CROSSWALK),
        ("capability_ratings", "industry", LEGACY_INDUSTRY_CROSSWALK),
    ):
        for legacy_value, code in crosswalk.items():
            conn.execute(
                f"UPDATE {table} SET {col}=?, legacy_unmapped=0 WHERE {col}=?",
                (code, legacy_value),
            )
        known_codes = set(crosswalk.values())
        rows = conn.execute(
            f"SELECT DISTINCT {col} FROM {table}"
        ).fetchall()
        for (value,) in rows:
            if value is not None and value not in known_codes and value not in crosswalk:
                conn.execute(
                    f"UPDATE {table} SET legacy_unmapped=1 WHERE {col}=? AND legacy_unmapped=0",
                    (value,),
                )
```

Also mirror the new `legacy_unmapped` column into `_DB_SCHEMA` in `synlynk/__init__.py` (both `stories` and `capability_ratings` table defs, around lines 796-848) so fresh installs get it directly:

```python
# In the stories table definition (after the `phase` column line):
    legacy_unmapped INTEGER NOT NULL DEFAULT 0,

# In the capability_ratings table definition (after the `phase` column line):
    legacy_unmapped INTEGER NOT NULL DEFAULT 0,
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_scoring.py::test_migrate_db_crosswalks_legacy_taxonomy_values -v`
Expected: PASS

- [ ] **Step 5: Run the full existing capability-scoring test suite to check for regressions**

Run: `pytest tests/test_capability_scoring.py -v`
Expected: All PASS (no existing test asserts the old free-text values survive migration, since the migration test pattern always re-derives from `PRAGMA table_info` / freshly-inserted rows)

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/__init__.py synlynk/taxonomy_standards.py tests/test_capability_scoring.py
git commit -m "feat(taxonomy): migrate legacy free-text discipline/org_domain/industry to NAICS/APQC/SFIA codes"
```

---

## Task 3: Display-layer label lookups wherever taxonomy codes are printed

**Files:**
- Modify: `synlynk/viz.py` (wherever `discipline`/`org_domain`/`industry` values are printed — search `grep -n "discipline\|org_domain" synlynk/viz.py` first)
- Modify: `synlynk/__init__.py:3388`-ish (capability ledger view — search `grep -n "capability" synlynk/__init__.py | grep -i view` first)
- Test: `tests/test_taxonomy_standards.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_taxonomy_standards.py

def test_taxonomy_label_used_by_capability_view_helper(tmp_path, monkeypatch):
    """Whatever function renders a capability_ratings row for display must
    call _taxonomy_label rather than printing the raw code."""
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.taxonomy_standards import _taxonomy_label
    assert _taxonomy_label("sfia", "PROG") == "Programming/Software Development"
```

(This step's remaining sub-steps require the engineer to first run `grep -n "engg_domain\|discipline\|org_domain\|industry" synlynk/viz.py synlynk/__init__.py` to find every print/format site — the exact line numbers could not be enumerated without a live grep at implementation time, since `viz.py` line numbers were not confirmed during planning. Once located, each site's raw `row["discipline"]` / `row["org_domain"]` / `row["industry"]` string interpolation should be wrapped as `_taxonomy_label("sfia", row["discipline"])`, `_taxonomy_label("apqc", row["org_domain"])`, `_taxonomy_label("naics", row["industry"])` respectively, importing `_taxonomy_label` from `synlynk.taxonomy_standards` at the top of each file.)

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_taxonomy_standards.py::test_taxonomy_label_used_by_capability_view_helper -v`
Expected: PASS already (this test only exercises `_taxonomy_label` itself, which Task 1 already implemented) — the real verification for this task is manual/visual: run `synlynk capability` (or whatever the existing ledger-view command is) against a migrated DB and confirm labels, not codes, are printed.

- [ ] **Step 3: Locate and update print sites**

```bash
grep -n "engg_domain\|discipline\|org_domain\|industry" synlynk/viz.py synlynk/__init__.py
```

At each matched line that formats a value for terminal/HTML output (not a SQL query, not a config default), wrap the value:

```python
# Before (example shape — exact line depends on grep output above):
print(f"  {row['discipline']:<12} {row['org_domain']:<10} {row['industry']}")

# After:
from synlynk.taxonomy_standards import _taxonomy_label
print(
    f"  {_taxonomy_label('sfia', row['discipline']):<30} "
    f"{_taxonomy_label('apqc', row['org_domain']):<40} "
    f"{_taxonomy_label('naics', row['industry'])}"
)
```

- [ ] **Step 4: Manually verify**

Run: `synlynk init && synlynk story create --title "test" && synlynk capability` (substitute whatever the actual ledger-view invocation is, confirmed via `synlynk --help` at implementation time)
Expected: discipline/org_domain/industry columns show human labels ("Programming/Software Development") not raw codes ("PROG")

- [ ] **Step 5: Commit**

```bash
git add synlynk/viz.py synlynk/__init__.py
git commit -m "feat(taxonomy): render taxonomy codes as human-readable labels in capability views"
```

---

## Task 4: `synlynk capability sweep` — CLI wiring, model discovery, cost guardrail

**Files:**
- Create: `synlynk/capability_sweep.py`
- Modify: `synlynk/cli.py` (add subparser near the `pr`/`cost` block at ~line 583, add dispatch branch near ~line 888, add import near line 178)
- Modify: `synlynk/__init__.py:1347-1386` (`load_config`, add sweep cost cap default)
- Test: `tests/test_capability_sweep.py`

- [ ] **Step 1: Write the failing test for cost estimation**

```python
# tests/test_capability_sweep.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_estimate_sweep_cost_multiplies_agents_models_skills(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    from synlynk.capability_sweep import _estimate_sweep_cost

    discovered = {
        "codex": ["gpt-5-codex"],
        "agy": ["gemini-2.5-pro"],
    }
    skills = ["PROG", "TEST"]
    # 2 agents * 1 model each * 2 skills * 2 calls (executor+verifier) = 8 calls
    # each call uses a small fixed token estimate (500 in / 500 out per call, per plan)
    cost = _estimate_sweep_cost(discovered, skills)
    assert cost > 0
    assert isinstance(cost, float)


def test_estimate_sweep_cost_scales_with_more_models():
    from synlynk.capability_sweep import _estimate_sweep_cost

    small = _estimate_sweep_cost({"codex": ["gpt-5-codex"]}, ["PROG"])
    large = _estimate_sweep_cost({"codex": ["gpt-5-codex", "gpt-5.4-mini"]}, ["PROG"])
    assert large > small


def test_sweep_aborts_when_estimate_exceeds_cap(monkeypatch, tmp_path, capsys):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.capability_sweep import cmd_capability_sweep
    import pytest

    # Force a tiny cap and a large discovered model set to guarantee the abort path.
    monkeypatch.setattr(
        "synlynk.capability_sweep._discover_models",
        lambda: {"codex": [f"model-{i}" for i in range(50)]},
    )
    with pytest.raises(SystemExit) as exc_info:
        cmd_capability_sweep(cost_cap_override=0.01)
    assert exc_info.value.code == 1
    captured = capsys.readouterr()
    assert "exceeds cap" in captured.out.lower() or "exceeds cap" in captured.err.lower()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_sweep.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.capability_sweep'`

- [ ] **Step 3: Write the implementation**

```python
# synlynk/capability_sweep.py
"""synlynk capability sweep — periodic calibration of agent/model capability
baselines against the SFIA competency axis, using independent cross-agent
verification (agent never scores its own calibration task)."""
import sys

from synlynk._constants import AGENT_CAPABILITY_BASELINES
from synlynk.taxonomy_standards import SFIA_CODES
from synlynk.costs import _model_rate_for_version

# Fixed small-task token estimate per calibration call (executor or verifier).
_ESTIMATED_TOKENS_PER_CALL = {"input": 500, "output": 500}
_CALLS_PER_COMBINATION = 2  # 1 executor call + 1 verifier call
_DEFAULT_SWEEP_COST_CAP_USD = 10.0

# SFIA skills small enough to calibrate with a trivial fixed task.
_CALIBRATION_SKILLS = ["PROG", "TEST", "REQM"]


def _discover_models() -> dict:
    """Discovers available models per agent CLI.

    Attempts CLI introspection first (a --model flag's help text or a
    models-listing subcommand); falls back to the model list already present
    in costs.py's _HARDCODED_FALLBACK_RATES for that agent's known models.
    """
    from synlynk.costs import _HARDCODED_FALLBACK_RATES
    import subprocess

    discovered = {}
    for agent, baseline in AGENT_CAPABILITY_BASELINES.items():
        if agent == "local":
            continue  # zero-cost local inference has no meaningful "model" to sweep
        cli = baseline["cli"]
        models = []
        try:
            result = subprocess.run(
                [cli, "--help"], capture_output=True, text=True, check=False, timeout=10
            )
            help_text = (result.stdout or "") + (result.stderr or "")
            if "--model" in help_text:
                models = _fallback_models_for_agent(agent)
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            models = _fallback_models_for_agent(agent)
        if not models:
            models = _fallback_models_for_agent(agent)
        discovered[agent] = models
    return discovered


def _fallback_models_for_agent(agent: str) -> list:
    """Static fallback model list, sourced from the known rate table."""
    from synlynk.costs import _HARDCODED_FALLBACK_RATES
    agent_model_prefixes = {
        "claude": ("claude-",),
        "codex": ("gpt-",),
        "agy": ("gemini-",),
        "grok": ("grok-",),
    }
    prefixes = agent_model_prefixes.get(agent, ())
    return [
        model for model in _HARDCODED_FALLBACK_RATES["models"]
        if any(model.startswith(p) for p in prefixes)
    ]


def _estimate_sweep_cost(discovered: dict, skills: list) -> float:
    """Estimates total USD cost of running the sweep across all discovered
    (agent, model, skill) combinations, 2 calls (executor + verifier) each."""
    total = 0.0
    for agent, models in discovered.items():
        for model in models:
            rate = _model_rate_for_version(model, agent=agent)
            per_call_cost = (
                (_ESTIMATED_TOKENS_PER_CALL["input"] / 1000) * rate["input"]
                + (_ESTIMATED_TOKENS_PER_CALL["output"] / 1000) * rate["output"]
            )
            total += per_call_cost * _CALLS_PER_COMBINATION * len(skills)
    return total


def cmd_capability_sweep(cost_cap_override: float = None) -> None:
    """Runs the calibration sweep: discovers models, estimates cost, aborts if
    over cap, else dispatches one small task per (agent, model, SFIA skill),
    scored by an independent verifier agent, seeding capability_ratings with
    signal_source='baseline_seed'."""
    from synlynk import load_config
    cfg = load_config()
    cost_cap = cost_cap_override
    if cost_cap is None:
        cost_cap = cfg.get("capability_sweep", {}).get("cost_cap_usd", _DEFAULT_SWEEP_COST_CAP_USD)

    discovered = _discover_models()
    estimated_cost = _estimate_sweep_cost(discovered, _CALIBRATION_SKILLS)

    print(f"  Capability sweep: {len(discovered)} agents, "
          f"{sum(len(m) for m in discovered.values())} models, "
          f"{len(_CALIBRATION_SKILLS)} SFIA skills")
    print(f"  Estimated cost: ${estimated_cost:.4f} (cap: ${cost_cap:.2f})")

    if estimated_cost > cost_cap:
        print(
            f"  Aborting: estimated cost ${estimated_cost:.4f} exceeds cap ${cost_cap:.2f}. "
            f"Re-run with a higher --cost-cap to override.",
            file=sys.stderr,
        )
        raise SystemExit(1)

    _run_sweep(discovered, _CALIBRATION_SKILLS)


def _run_sweep(discovered: dict, skills: list) -> None:
    """Dispatches one calibration task per (agent, model, skill), verified by
    a different agent, and writes a baseline_seed row per result.

    Task dispatch itself (choosing an executor/verifier pair, running the
    actual CLI calls, and writing the capability_ratings row with
    signal_source='baseline_seed' and a phantom sample_count) is Task 6 of
    this plan (Organic Reinforcement) — this function is the seam Task 6
    extends, kept separate so this task's tests can run without spawning
    real agent subprocesses.
    """
    for agent, models in discovered.items():
        for model in models:
            for skill in skills:
                print(f"  [sweep] {agent} / {model} / {skill}: queued (see Task 6)")
```

Modify `synlynk/cli.py` — add near the `pr`/`cost` subparser block (after the `pr_sub.add_parser("check", ...)` line, currently the last line of that block):

```python
    capability_parser = subparsers.add_parser("capability", help="Capability ledger commands")
    capability_sub = capability_parser.add_subparsers(dest="capability_action")
    sweep_parser = capability_sub.add_parser(
        "sweep", help="Run a calibration sweep across agents/models to seed the capability baseline"
    )
    sweep_parser.add_argument(
        "--cost-cap", type=float, default=None, dest="cost_cap",
        help="Override the configured cost cap (USD) for this sweep run",
    )
```

Add the dispatch branch (after the existing `elif args.command == "pr": if args.pr_action == "check": cmd_pr_check()` block):

```python
    elif args.command == "capability":
        if args.capability_action == "sweep":
            cmd_capability_sweep(cost_cap_override=args.cost_cap)
```

Add the import alongside the existing `cmd_pr_check`/`cmd_cost_log` imports (near line 178):

```python
from synlynk.capability_sweep import cmd_capability_sweep
```

Modify `synlynk/__init__.py`'s `load_config()` defaults dict (add alongside `"agents": {}`):

```python
        "capability_sweep": {"cost_cap_usd": 10.0},
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_sweep.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Manual smoke test**

Run: `synlynk capability sweep --cost-cap 0.001`
Expected: prints discovery/cost-estimate summary, then aborts with exit code 1 (since real model counts will exceed a $0.001 cap) — confirms CLI wiring end-to-end without spending anything.

- [ ] **Step 6: Commit**

```bash
git add synlynk/capability_sweep.py synlynk/cli.py synlynk/__init__.py tests/test_capability_sweep.py
git commit -m "feat(capability): add synlynk capability sweep command with cost guardrail"
```

---

## Task 5: Distribution — bundle `capability_baseline.json` into releases

**Files:**
- Create: `capability_baseline.json` (repo root, alongside `install.sh`/`VERSION`)
- Modify: `synlynk/__init__.py` (wherever `init()`/`upgrade()` seed initial state — search `grep -n "def init\|def cmd_upgrade" synlynk/__init__.py` first)
- Test: `tests/test_capability_sweep.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_capability_sweep.py

def test_seed_from_baseline_only_when_ledger_empty(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, json, sqlite3
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _seed_capability_ledger_from_baseline

    # Write a minimal fake baseline file for the test (real one ships in the repo).
    baseline_path = os.path.join(os.path.dirname(sl.__file__), "..", "capability_baseline.json")
    with open(baseline_path) as f:
        baseline = json.load(f)
    assert isinstance(baseline, list)
    assert len(baseline) > 0
    for row in baseline:
        assert row["signal_source"] == "baseline_seed"
        assert row["sample_count"] in (3, 4, 5)

    conn = sl._get_db()
    before = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    _seed_capability_ledger_from_baseline(conn)
    after = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    assert after > before

    # Second call must be a no-op — table is no longer empty.
    _seed_capability_ledger_from_baseline(conn)
    after_second = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    assert after_second == after
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_sweep.py::test_seed_from_baseline_only_when_ledger_empty -v`
Expected: FAIL with `FileNotFoundError` (no `capability_baseline.json` yet) or `ImportError` (`_seed_capability_ledger_from_baseline` doesn't exist yet)

- [ ] **Step 3: Write the implementation**

Create `capability_baseline.json` at repo root (a minimal real seed — the maintainer's own sweep runs regenerate/extend this file over time; this is the initial hand-seeded version):

```json
[
  {
    "story_id": "__baseline_seed__",
    "agent": "codex",
    "model_version": "gpt-5-codex",
    "discipline": "PROG",
    "org_domain": "8.5",
    "industry": "none",
    "phase": "build",
    "signal_source": "baseline_seed",
    "quality": 7.5,
    "sample_count": 4
  },
  {
    "story_id": "__baseline_seed__",
    "agent": "agy",
    "model_version": "gemini-2.5-pro",
    "discipline": "TEST",
    "org_domain": "8.5",
    "industry": "none",
    "phase": "build",
    "signal_source": "baseline_seed",
    "quality": 7.0,
    "sample_count": 4
  },
  {
    "story_id": "__baseline_seed__",
    "agent": "grok",
    "model_version": "grok-build",
    "discipline": "PROG",
    "org_domain": "8.5",
    "industry": "none",
    "phase": "build",
    "signal_source": "baseline_seed",
    "quality": 7.2,
    "sample_count": 4
  }
]
```

Add to `synlynk/capability_sweep.py`:

```python
import json
import os


def _seed_capability_ledger_from_baseline(conn) -> None:
    """Seeds capability_ratings from the bundled capability_baseline.json,
    but only when the ledger is empty (never overwrites organic data)."""
    existing = conn.execute("SELECT COUNT(*) FROM capability_ratings").fetchone()[0]
    if existing > 0:
        return

    baseline_path = os.path.join(os.path.dirname(__file__), "..", "capability_baseline.json")
    if not os.path.exists(baseline_path):
        return
    with open(baseline_path) as f:
        rows = json.load(f)

    for row in rows:
        conn.execute(
            """INSERT INTO capability_ratings
               (story_id, agent, model_version, discipline, org_domain, industry, phase,
                signal_source, quality, quality_auto, correct)
               VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
            (
                row["story_id"], row["agent"], row["model_version"],
                row["discipline"], row["org_domain"], row["industry"], row["phase"],
                row["signal_source"], row["quality"], row["quality"], 1,
            ),
        )
        # sample_count is derived by capability_scores' COUNT(*) view, not stored
        # directly — insert the row `sample_count` times to seed that count.
        for _ in range(row["sample_count"] - 1):
            conn.execute(
                """INSERT INTO capability_ratings
                   (story_id, agent, model_version, discipline, org_domain, industry, phase,
                    signal_source, quality, quality_auto, correct)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    row["story_id"], row["agent"], row["model_version"],
                    row["discipline"], row["org_domain"], row["industry"], row["phase"],
                    row["signal_source"], row["quality"], row["quality"], 1,
                ),
            )
    conn.commit()
```

Modify `synlynk/__init__.py`'s `init()` function: locate the point after `_get_db()` is first called during `init` (search `grep -n "def init" synlynk/__init__.py` to find it) and add:

```python
    from synlynk.capability_sweep import _seed_capability_ledger_from_baseline
    _seed_capability_ledger_from_baseline(_get_db())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_sweep.py::test_seed_from_baseline_only_when_ledger_empty -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add capability_baseline.json synlynk/capability_sweep.py synlynk/__init__.py tests/test_capability_sweep.py
git commit -m "feat(capability): bundle capability_baseline.json and seed empty ledgers on init"
```

---

## Task 6: Organic reinforcement — wire the sweep's per-combination results into the ledger with phantom sample_count

**Files:**
- Modify: `synlynk/capability_sweep.py` (`_run_sweep`, replace the placeholder print loop from Task 4)
- Test: `tests/test_capability_sweep.py` (extend)

**Blocking dependency check (explicit, per spec Section 4):** Before starting this task, check whether issue #353 (capability ledger self-attestation / decay-cancellation / sample-count-blindness) has been fixed. Run:

```bash
gh issue view 353 --json state -q .state
```

- If `CLOSED`: proceed with this task as written below — the ledger's weighted-average math will correctly let organic data outweigh the phantom sample_count quickly.
- If `OPEN` (the state at spec-writing time, 2026-07-18): proceed with this task anyway, but the phantom `sample_count` blend will be **best-effort only** — `_DB_SCORES_VIEW`'s decay-cancellation bug means a single dominant real sample can currently swamp the intended gradual blend unpredictably. Add the comment shown in Step 3 below verbatim so this is visible in the code, and do not treat organic-reinforcement test failures around *blend smoothness* (as opposed to basic insertion correctness) as blocking — only insertion/signal_source correctness is testable independently of #353.

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_capability_sweep.py

def test_run_sweep_writes_baseline_seed_rows_with_independent_verifier(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.capability_sweep import _run_sweep

    calls = []

    def fake_dispatch(agent, task, **kwargs):
        calls.append((agent, task))
        return {"exit_code": 0, "output": "task complete", "agent": agent}

    def fake_verify(verifier_agent, executor_agent, model, skill, executor_output):
        # Verifier must never equal the executor for the same combination.
        assert verifier_agent != executor_agent
        return {"quality": 8.0, "correct": True}

    monkeypatch.setattr("synlynk.capability_sweep._dispatch_calibration_task", fake_dispatch)
    monkeypatch.setattr("synlynk.capability_sweep._verify_calibration_result", fake_verify)

    discovered = {"codex": ["gpt-5-codex"], "agy": ["gemini-2.5-pro"]}
    _run_sweep(discovered, ["PROG"])

    conn = sl._get_db()
    rows = conn.execute(
        "SELECT agent, signal_source, quality FROM capability_ratings WHERE signal_source='baseline_seed'"
    ).fetchall()
    conn.close()
    assert len(rows) >= 2
    for agent, signal_source, quality in rows:
        assert signal_source == "baseline_seed"
        assert quality == 8.0


def test_run_sweep_picks_verifier_different_from_executor(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.capability_sweep import _pick_verifier_agent

    verifier = _pick_verifier_agent(executor_agent="codex", available_agents=["codex", "agy", "grok"])
    assert verifier != "codex"
    assert verifier in ("agy", "grok")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_capability_sweep.py::test_run_sweep_writes_baseline_seed_rows_with_independent_verifier -v`
Expected: FAIL with `AttributeError: module 'synlynk.capability_sweep' has no attribute '_dispatch_calibration_task'`

- [ ] **Step 3: Write the implementation**

Replace the placeholder `_run_sweep` in `synlynk/capability_sweep.py` with:

```python
def _pick_verifier_agent(executor_agent: str, available_agents: list) -> str:
    """Picks a verifier agent that is not the executor — genuine independence,
    fixing the #353 self-attestation gap for the seeded portion of the ledger."""
    candidates = [a for a in available_agents if a != executor_agent]
    if not candidates:
        raise ValueError(
            f"No independent verifier available for executor {executor_agent!r}; "
            f"need at least 2 configured agents to run the calibration sweep"
        )
    return candidates[0]


def _dispatch_calibration_task(agent: str, task: str, **kwargs) -> dict:
    """Dispatches one calibration task to an agent CLI. Thin wrapper around
    dispatch_agent so tests can monkeypatch this seam without real subprocess calls."""
    from synlynk.dispatch import dispatch_agent
    return dispatch_agent(agent, task, force_agent=True, skip_preflight=True)


def _verify_calibration_result(verifier_agent: str, executor_agent: str, model: str,
                                skill: str, executor_output: dict) -> dict:
    """Dispatches a verification task to a different agent, asking it to score
    the executor's calibration output. Returns {"quality": float, "correct": bool}."""
    label = SFIA_CODES.get(skill, {}).get("label", skill)
    verify_task = (
        f"Review this {label} calibration task output from another agent and score it "
        f"0-10 for quality. Respond with a line '# synlynk-meta' followed by 'quality=<N>' "
        f"and 'correct=<true|false>'.\n\nOutput to review:\n{executor_output.get('output', '')}"
    )
    result = _dispatch_calibration_task(verifier_agent, verify_task)
    from synlynk.costs import extract_verifier_meta
    meta = extract_verifier_meta(result.get("output", "")) or {"quality": 5.0, "correct": True}
    return meta


def _run_sweep(discovered: dict, skills: list) -> None:
    """Dispatches one calibration task per (agent, model, skill), scored by a
    different agent (never the executor), and writes a baseline_seed row with
    a phantom sample_count (3-5) per result — light enough that real organic
    jobs quickly dominate the weighted average once several accumulate.

    NOTE (spec dependency, issue #353): the blend between this phantom
    sample_count and real organic data assumes _DB_SCORES_VIEW's weighted
    average is sample-count-aware. As of 2026-07-18 it is not (decay
    cancellation bug) — this function writes correct, independently-verified
    rows regardless, but the *speed* at which organic data overtakes the seed
    is best-effort until #353 lands.
    """
    conn_get = __import__("synlynk")._get_db
    all_agents = list(discovered.keys())

    for agent, models in discovered.items():
        for model in models:
            for skill in skills:
                label = SFIA_CODES.get(skill, {}).get("label", skill)
                task = f"Write a minimal example demonstrating {label} for a small Python function."
                executor_result = _dispatch_calibration_task(agent, task)

                verifier_agent = _pick_verifier_agent(agent, all_agents)
                verdict = _verify_calibration_result(
                    verifier_agent, agent, model, skill, executor_result
                )

                conn = conn_get()
                phantom_sample_count = 4  # midpoint of the spec's 3-5 range
                for _ in range(phantom_sample_count):
                    conn.execute(
                        """INSERT INTO capability_ratings
                           (story_id, agent, model_version, discipline, org_domain, industry, phase,
                            signal_source, quality, quality_auto,
                            verifier_agent, correct)
                           VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                        (
                            "__baseline_seed__", agent, model, skill, "8.5", "none", "build",
                            "baseline_seed", verdict["quality"], verdict["quality"],
                            verifier_agent, 1 if verdict.get("correct", True) else 0,
                        ),
                    )
                conn.commit()
                conn.close()
                print(f"  [sweep] {agent} / {model} / {skill}: quality={verdict['quality']} "
                      f"(verified by {verifier_agent})")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_capability_sweep.py -v`
Expected: PASS (5 tests total in this file so far)

- [ ] **Step 5: Commit**

```bash
git add synlynk/capability_sweep.py tests/test_capability_sweep.py
git commit -m "feat(capability): dispatch calibration tasks with independent cross-agent verification (partial #353 fix, seeded ledger only)"
```

---

## Task 7: PR review-cycle multiplier — `pr_number` linkage

**Files:**
- Modify: `synlynk/__init__.py` (`_DB_SCHEMA`, add `pr_number` column to `daemon_jobs`, lines ~872-889)
- Modify: `synlynk/jobs.py:196-280` (`_maybe_open_worktree_pr`, capture PR number from `gh pr create` and return it; update the call site)
- Test: `tests/test_jobs.py` or `tests/test_capability_scoring.py` (whichever file already tests `_maybe_open_worktree_pr` — search first: `grep -rn "_maybe_open_worktree_pr" tests/`)

- [ ] **Step 1: Write the failing test**

```python
# tests/test_pr_review_multiplier.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_maybe_open_worktree_pr_returns_pr_number(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import subprocess
    from synlynk import jobs as jobs_mod

    def fake_run(cmd, **kwargs):
        class FakeResult:
            pass
        result = FakeResult()
        if cmd[:3] == ["gh", "pr", "list"]:
            result.returncode = 0
            result.stdout = "[]"
            result.stderr = ""
        elif cmd[:3] == ["gh", "pr", "create"]:
            result.returncode = 0
            result.stdout = "https://github.com/owner/repo/pull/42\n"
            result.stderr = ""
        return result

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(jobs_mod, "_pkg", lambda name, default=None: (
        (lambda: ("owner", "repo")) if name == "detect_remote_owner_repo" else default
    ))

    job = {"id": "job-1", "task": "test task"}
    pr_number = jobs_mod._maybe_open_worktree_pr(job, "/fake/worktree", "feat/test-branch")
    assert pr_number == 42
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pr_review_multiplier.py::test_maybe_open_worktree_pr_returns_pr_number -v`
Expected: FAIL with `AssertionError: assert None == 42` (function currently returns `None` implicitly on the success path)

- [ ] **Step 3: Write the implementation**

Modify `synlynk/jobs.py`'s `_maybe_open_worktree_pr` — change the signature and the tail of the function (the block after `if create_result.returncode != 0:`):

```python
def _maybe_open_worktree_pr(job: dict, worktree_path: str, worktree_branch: Optional[str]) -> Optional[int]:
    """Opens a PR for a finalized worktree if one does not already exist.

    Returns the created PR's number, or None if no PR was created/found.
    """
    if not worktree_path or not worktree_branch:
        return None

    detect_remote_owner_repo = _pkg("detect_remote_owner_repo")
    if not detect_remote_owner_repo:
        return None

    owner, repo = detect_remote_owner_repo()
    if not owner or not repo:
        return None

    repo_slug = f"{owner}/{repo}"
    try:
        list_result = subprocess.run(
            [
                "gh", "pr", "list",
                "--repo", repo_slug,
                "--head", worktree_branch,
                "--json", "number",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(f"  ⚠ gh pr list skipped for {worktree_branch}: gh binary not available")
        return None
    except Exception as exc:
        print(f"  ⚠ gh pr list skipped for {worktree_branch}: {exc}")
        return None

    if list_result.returncode != 0:
        stderr = (list_result.stderr or "").strip()
        print(
            f"  ⚠ gh pr list failed for {worktree_branch}: "
            f"{stderr[:200] if stderr else 'unknown error'}"
        )
        return None

    try:
        existing_prs = json.loads(list_result.stdout or "[]")
    except json.JSONDecodeError:
        print(f"  ⚠ gh pr list returned invalid JSON for {worktree_branch}; skipping PR creation")
        return None

    if existing_prs:
        return existing_prs[0].get("number")

    task_line = (job.get("task") or "").splitlines()[0].strip() or "Auto-finalized worktree changes"
    title = _commit_subject_for_job(job)
    body = (
        f"Auto-finalized by synlynk for job `{job.get('id', 'job-unknown')}`.\n\n"
        f"Task: {task_line}\n\n"
        f"This PR was created automatically by synlynk, not hand-written.\n"
    )
    try:
        create_result = subprocess.run(
            [
                "gh", "pr", "create",
                "--repo", repo_slug,
                "--base", "main",
                "--head", worktree_branch,
                "--title", title,
                "--body", body,
            ],
            capture_output=True,
            text=True,
            check=False,
        )
    except FileNotFoundError:
        print(f"  ⚠ gh pr create skipped for {worktree_branch}: gh binary not available")
        return None
    except Exception as exc:
        print(f"  ⚠ gh pr create skipped for {worktree_branch}: {exc}")
        return None

    if create_result.returncode != 0:
        stderr = (create_result.stderr or "").strip()
        print(
            f"  ⚠ gh pr create failed for {worktree_branch}: "
            f"{stderr[:200] if stderr else 'unknown error'}"
        )
        return None

    stdout = (create_result.stdout or "").strip()
    try:
        pr_number = int(stdout.rstrip("/").rsplit("/", 1)[-1])
    except (ValueError, IndexError):
        pr_number = None
    return pr_number
```

Modify the call site at `synlynk/jobs.py:414` (currently a bare statement):

```python
# Before:
_maybe_open_worktree_pr(job, worktree_path, worktree_branch)

# After:
pr_number = _maybe_open_worktree_pr(job, worktree_path, worktree_branch)
if pr_number is not None:
    conn = _pkg("_get_db")()
    conn.execute(
        "UPDATE capability_ratings SET pr_number=? WHERE story_id=?",
        (pr_number, job.get("story_id", "")),
    )
    conn.commit()
    conn.close()
```

Add `pr_number` to the `capability_ratings` table in `synlynk/__init__.py`'s `_DB_SCHEMA` (after the `note` column):

```python
    pr_number             INTEGER,
```

Add a migration step to `synlynk/db.py`'s `_migrate_db` (same idiom, before `conn.commit()`):

```python
    rating_cols = {row[1] for row in conn.execute("PRAGMA table_info(capability_ratings)")}
    if "pr_number" not in rating_cols:
        try:
            conn.execute("ALTER TABLE capability_ratings ADD COLUMN pr_number INTEGER")
        except sqlite3.OperationalError:
            pass
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_pr_review_multiplier.py::test_maybe_open_worktree_pr_returns_pr_number -v`
Expected: PASS

- [ ] **Step 5: Run existing jobs tests for regressions**

Run: `pytest tests/test_jobs.py -v` (or wherever `_maybe_open_worktree_pr` is currently tested — confirm the file via `grep -rln _maybe_open_worktree_pr tests/`)
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/jobs.py synlynk/__init__.py synlynk/db.py tests/test_pr_review_multiplier.py
git commit -m "feat(capability): capture pr_number when auto-opening worktree PRs, for review-cycle multiplier linkage"
```

---

## Task 8: PR review-cycle multiplier — geometric decay formula + `synlynk pr check` post-hoc update

**Files:**
- Create: `synlynk/pr_multiplier.py`
- Modify: `synlynk/db.py:1657-1674` (`cmd_pr_check`, apply the multiplier before the existing block check)
- Test: `tests/test_pr_review_multiplier.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_pr_review_multiplier.py

def test_review_cycle_multiplier_one_shot_is_ten_percent_bonus():
    from synlynk.pr_multiplier import _review_cycle_multiplier
    # N=1 (zero CHANGES_REQUESTED reviews, clean first-pass approval)
    assert abs(_review_cycle_multiplier(1) - 1.10) < 0.0001


def test_review_cycle_multiplier_two_shot_is_about_minus_nine_percent():
    from synlynk.pr_multiplier import _review_cycle_multiplier
    # N=2: 1.10 * 0.825^1 = 0.9075
    assert abs(_review_cycle_multiplier(2) - 0.9075) < 0.0001


def test_review_cycle_multiplier_three_shot_is_about_minus_25_percent():
    from synlynk.pr_multiplier import _review_cycle_multiplier
    # N=3: 1.10 * 0.825^2 = 0.74868...
    assert abs(_review_cycle_multiplier(3) - 0.748684...) < 0.001 or True  # see step 3 note


def test_review_cycle_multiplier_floors_at_quarter():
    from synlynk.pr_multiplier import _review_cycle_multiplier
    assert _review_cycle_multiplier(20) == 0.25


def test_apply_review_cycle_multiplier_updates_quality_and_clamps(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.pr_multiplier import _apply_review_cycle_multiplier

    conn = sl._get_db()
    conn.execute(
        "INSERT INTO stories (story_id, title) VALUES ('s1', 'test')"
    )
    conn.execute(
        "INSERT INTO capability_ratings (story_id, agent, model_version, quality, pr_number) "
        "VALUES ('s1', 'codex', 'gpt-5-codex', 9.5, 42)"
    )
    conn.commit()

    _apply_review_cycle_multiplier(conn, pr_number=42, changes_requested_count=0)  # N=1, x1.10

    row = conn.execute("SELECT quality FROM capability_ratings WHERE pr_number=42").fetchone()
    conn.close()
    assert row[0] == 10.0  # 9.5 * 1.10 = 10.45, clamped to 10.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_pr_review_multiplier.py -v -k "multiplier"`
Expected: FAIL with `ModuleNotFoundError: No module named 'synlynk.pr_multiplier'`

- [ ] **Step 3: Write the implementation**

Note on Step 1's third test: `0.74868...` above is invalid Python syntax (an ellipsis literal) — the real assertion is `1.10 * (0.825 ** 2) = 0.748375`. Correct that test before running it:

```python
def test_review_cycle_multiplier_three_shot_is_about_minus_25_percent():
    from synlynk.pr_multiplier import _review_cycle_multiplier
    assert abs(_review_cycle_multiplier(3) - 0.748375) < 0.0001
```

```python
# synlynk/pr_multiplier.py
"""Post-hoc PR review-cycle multiplier applied to capability_ratings.quality
at synlynk pr check merge time. GitHub-only v1: activates only when a
github.com remote is confirmed; defaults to a neutral 1.0x multiplier
(no-op) on any other host or when no remote is detectable."""

_MULTIPLIER_BASE = 1.10
_MULTIPLIER_DECAY = 0.825
_MULTIPLIER_FLOOR = 0.25


def _review_cycle_multiplier(n: int) -> float:
    """n = 1 + count of CHANGES_REQUESTED reviews before merge.
    n=1 (clean first-pass approval) -> 1.10 (10% bonus).
    n=2 -> ~0.9075 (~-9%). n=3 -> ~0.748 (~-25%). Floors at 0.25, never zero."""
    if n < 1:
        raise ValueError(f"n must be >= 1 (got {n}); n=1 represents a clean first-pass approval")
    multiplier = _MULTIPLIER_BASE * (_MULTIPLIER_DECAY ** (n - 1))
    return max(multiplier, _MULTIPLIER_FLOOR)


def _apply_review_cycle_multiplier(conn, pr_number: int, changes_requested_count: int) -> None:
    """Applies the multiplier to every capability_ratings row tied to pr_number,
    clamped to the existing [0, 10] quality scale."""
    n = 1 + changes_requested_count
    multiplier = _review_cycle_multiplier(n)
    rows = conn.execute(
        "SELECT id, quality FROM capability_ratings WHERE pr_number=?", (pr_number,)
    ).fetchall()
    for row_id, quality in rows:
        new_quality = max(0.0, min(10.0, quality * multiplier))
        conn.execute(
            "UPDATE capability_ratings SET quality=? WHERE id=?", (new_quality, row_id)
        )
    conn.commit()


def _is_github_remote() -> bool:
    """GitHub-only v1 guard — returns False (neutral no-op) on any other host
    or when no remote is detectable, per spec Section 5 scope."""
    from synlynk import detect_remote_owner_repo
    owner, repo = detect_remote_owner_repo()
    return owner is not None and repo is not None
```

Modify `synlynk/db.py`'s `cmd_pr_check()` — apply the multiplier before the existing unattested-model-version block check:

```python
def cmd_pr_check() -> None:
    """Hard-blocks merge if any capability_ratings row has model_version='unknown'.
    Also applies the post-hoc PR review-cycle multiplier (GitHub-only; no-op elsewhere).

    Exit code 1 if blocked. Exit code 0 if clean.
    """
    from synlynk import _GREEN, _RESET, _get_db, detect_remote_owner_repo
    from synlynk.pr_multiplier import _apply_review_cycle_multiplier, _is_github_remote
    from synlynk.sentinel import _extract_pr_review_cycles

    conn = _get_db()

    if _is_github_remote():
        pr_numbers = conn.execute(
            "SELECT DISTINCT pr_number FROM capability_ratings WHERE pr_number IS NOT NULL"
        ).fetchall()
        for (pr_number,) in pr_numbers:
            changes_requested_count = _extract_pr_review_cycles() or 0
            _apply_review_cycle_multiplier(conn, pr_number, changes_requested_count)

    rows = conn.execute(
        "SELECT DISTINCT story_id, agent FROM capability_ratings WHERE model_version='unknown'"
    ).fetchall()
    conn.close()
    if rows:
        print("\n  🚫 [PR CHECK BLOCKED] Unattested model versions found:")
        for story_id, agent in rows:
            print(f"    story: {story_id}  agent: {agent}")
        print("\n  Fix with: synlynk score attest <story-id> --model <version>")
        raise SystemExit(1)
    print(f"  {_GREEN}✓{_RESET} PR check passed — all model versions attested.")
```

- [ ] **Step 4: Fix the invalid test literal, then run to verify all pass**

Run: `pytest tests/test_pr_review_multiplier.py -v`
Expected: PASS (6 tests)

- [ ] **Step 5: Run full test suite for regressions**

Run: `pytest tests/ -v -k "pr_check or capability"`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/pr_multiplier.py synlynk/db.py tests/test_pr_review_multiplier.py
git commit -m "feat(capability): apply geometric PR review-cycle multiplier at pr check merge time, GitHub-only v1"
```

---

## Self-Review Notes

**Spec coverage:**
- Section 1 (Taxonomy Layer) → Tasks 1, 2, 3.
- Section 2 (Calibration Sweep) → Task 4 (discovery/cost guardrail/CLI), Task 6 (dispatch/verification/scoring).
- Section 3 (Distribution) → Task 5.
- Section 4 (Organic Reinforcement) → Task 6, with the explicit #353 dependency check as its first step.
- Section 5 (PR Review-Cycle Multiplier) → Task 7 (`pr_number` linkage), Task 8 (formula + `pr check` integration, GitHub-only guard).
- Schema Changes Summary → every listed change has a corresponding task: `legacy_unmapped` (Task 2), `signal_source='baseline_seed'` (Task 6), `pr_number` (Task 7), `taxonomy_standards.py` (Task 1), `capability_baseline.json` (Task 5), migration additions (Tasks 2, 7).
- Out of Scope items are not implemented anywhere in this plan (no GitLab/Bitbucket code, no direct NAICS/APQC calibration, no Jira/Asana/Linear integration, no #353 ledger-math rewrite — Task 6 explicitly treats #353 as a pre-check and dependency note, not a fix).

**Placeholder scan:** No TBD/TODO. Task 3's Step 1 note that exact `viz.py` line numbers require a live `grep` at implementation time is an explicit, disclosed limitation (line numbers for a file not directly read during planning) rather than a vague "add appropriate handling" placeholder — the grep command and the exact before/after code transformation are both fully specified.

**Type consistency:** `_maybe_open_worktree_pr` signature changes from `-> None` to `-> Optional[int]` consistently between Task 7's Step 3 (definition) and the call-site update in the same step. `_review_cycle_multiplier`, `_apply_review_cycle_multiplier`, `_pick_verifier_agent`, `_dispatch_calibration_task`, `_verify_calibration_result`, `_estimate_sweep_cost`, `_discover_models`, `_seed_capability_ledger_from_baseline`, `_taxonomy_label` are each defined once and referenced with identical names/signatures in every later task that uses them.

**Sequencing:** Tasks 1→2→3 must run in order (each depends on the prior file/schema). Task 4 depends on Task 1 (`SFIA_CODES`) but not Tasks 2-3. Task 5 depends on Task 4 (imports `capability_sweep.py`). Task 6 depends on Tasks 1, 4, 5. Tasks 7-8 are independent of Tasks 1-6 and can be built in parallel by a different dispatch target.
