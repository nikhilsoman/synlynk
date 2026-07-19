# Payment-Model-Aware Cost/Value Accounting Layer Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace synlynk's single fictitious-for-many-users dollar figure with an honest two-figure accounting (API-equivalent value vs. actual dollars charged) that correctly branches on how each agent CLI is actually paid for — pay-as-you-go, subscription-with-quota, or granted credits — without touching the raw token/request counts that budget guards, capability scoring, and quota tracking already depend on.

**Architecture:** Five additive slices, in dependency order: (1) `payment_models` config schema, (2) `credit_grants` ledger table + migration, (3) `resolve_payment_value()` — the pure calculation function, pulling quota state from the existing `agent_quotas` table (`quota.py`) and credit balance from the new table, (4) `synlynk credit grant` CLI command to populate credit balances, (5) wiring `resolve_payment_value()` into `update_costs()` (new `cost_entries` columns + two-column `costs.md` display) and a payment-model rollup line in `check_budgets()`. No existing function (`check_budgets`, `_write_capability_rating`, `agent_quotas` writers) has its inputs changed — only `update_costs()`'s dollar-computation step is replaced.

**Tech Stack:** Python 3 stdlib, sqlite3, pytest, argparse (`synlynk/cli.py`), dataclasses.

---

## Task 1: `payment_models` config schema

**Files:**
- Modify: `synlynk/__init__.py:1347-1386` (`load_config`)
- Test: `tests/test_payment_models.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_payment_models.py
import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


def test_load_config_defaults_payment_models_to_empty_dict(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import synlynk as sl
    config = sl.load_config()
    assert config["payment_models"] == {}


def test_load_config_preserves_existing_payment_models_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, json
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({
            "payment_models": {
                "codex": {
                    "mode": "subscription",
                    "tier_quota_tokens_in": 2000000,
                    "tier_quota_tokens_out": 500000,
                    "overage_rate_per_1k_in": 0.003,
                    "overage_rate_per_1k_out": 0.015,
                }
            }
        }, f)
    import synlynk as sl
    config = sl.load_config()
    assert config["payment_models"]["codex"]["mode"] == "subscription"
    assert config["payment_models"]["codex"]["tier_quota_tokens_in"] == 2000000


def test_load_config_backfills_payment_models_into_existing_config_without_section(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, json
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"budget": {"limit_usd": 5.0}}, f)
    import synlynk as sl
    config = sl.load_config()
    assert config["payment_models"] == {}
    assert config["budget"]["limit_usd"] == 5.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payment_models.py -v`
Expected: FAIL with `KeyError: 'payment_models'`

- [ ] **Step 3: Write the implementation**

Modify `synlynk/__init__.py`'s `load_config()` defaults dict — add one key alongside the existing `"agents": {}` line:

```python
        "agents": {},
        "payment_models": {},
        "roles": _default_roles_map(),
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payment_models.py -v`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py tests/test_payment_models.py
git commit -m "feat(payment-models): add payment_models config section with additive defaults"
```

---

## Task 2: `credit_grants` table + migration

**Files:**
- Modify: `synlynk/__init__.py` (`_DB_SCHEMA`, add table alongside `cost_entries`)
- Modify: `synlynk/db.py:229` (`_migrate_db`, add idempotent creation for pre-existing DBs)
- Test: `tests/test_payment_models.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_payment_models.py

def test_migrate_db_creates_credit_grants_table(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, sqlite3
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    conn = sqlite3.connect(sl.DB_PATH)
    sl._migrate_db(conn)

    tables = {row[0] for row in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'"
    )}
    assert "credit_grants" in tables

    cols = {row[1] for row in conn.execute("PRAGMA table_info(credit_grants)")}
    assert cols == {
        "id", "agent", "face_value_usd", "remaining_usd",
        "granted_at", "expires_at", "note",
    }
    conn.close()


def test_migrate_db_credit_grants_creation_is_idempotent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os, sqlite3
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl

    conn = sqlite3.connect(sl.DB_PATH)
    sl._migrate_db(conn)
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 25.0, 25.0, '2026-07-18')"
    )
    conn.commit()
    sl._migrate_db(conn)  # second call must not wipe existing rows

    count = conn.execute("SELECT COUNT(*) FROM credit_grants").fetchone()[0]
    assert count == 1
    conn.close()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payment_models.py -v -k credit_grants`
Expected: FAIL with `sqlite3.OperationalError: no such table: credit_grants`

- [ ] **Step 3: Write the implementation**

Add to `synlynk/__init__.py`'s `_DB_SCHEMA` string (after the `agent_quotas` table definition, matching that table's formatting style):

```sql
    CREATE TABLE IF NOT EXISTS credit_grants (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        agent           TEXT NOT NULL,
        face_value_usd  REAL NOT NULL,
        remaining_usd   REAL NOT NULL,
        granted_at      TEXT NOT NULL,
        expires_at      TEXT,
        note            TEXT
    );
```

Add to `synlynk/db.py`'s `_migrate_db(conn)` — insert this block before the closing `conn.commit()` (same idempotent-creation idiom already used for other tables in this function, since `CREATE TABLE IF NOT EXISTS` is itself idempotent, no `PRAGMA table_info` guard needed):

```python
    conn.execute("""
        CREATE TABLE IF NOT EXISTS credit_grants (
            id              INTEGER PRIMARY KEY AUTOINCREMENT,
            agent           TEXT NOT NULL,
            face_value_usd  REAL NOT NULL,
            remaining_usd   REAL NOT NULL,
            granted_at      TEXT NOT NULL,
            expires_at      TEXT,
            note            TEXT
        )
    """)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payment_models.py -v -k credit_grants`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/__init__.py synlynk/db.py tests/test_payment_models.py
git commit -m "feat(payment-models): add credit_grants ledger table"
```

---

## Task 3: `resolve_payment_value()` — the calculation function

**Files:**
- Modify: `synlynk/costs.py` (add `PaymentValue` dataclass + `resolve_payment_value()`, near `_model_rate_for_version`)
- Test: `tests/test_payment_models.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_payment_models.py

def _write_config(tmp_path, payment_models):
    import os, json
    os.makedirs(".synlynk", exist_ok=True)
    with open(".synlynk/config.json", "w") as f:
        json.dump({"payment_models": payment_models}, f)


def test_resolve_payment_value_pay_as_you_go_matches_api_equivalent(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("grok", tokens_in=1000, tokens_out=1000)
    assert result.mode == "pay_as_you_go"
    assert result.actual_usd == result.api_equivalent_usd
    assert result.api_equivalent_usd > 0


def test_resolve_payment_value_subscription_within_quota_is_free(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {
        "codex": {
            "mode": "subscription",
            "tier_quota_tokens_in": 2000000,
            "tier_quota_tokens_out": 500000,
            "overage_rate_per_1k_in": 0.003,
            "overage_rate_per_1k_out": 0.015,
        }
    })
    from synlynk.costs import resolve_payment_value

    result = resolve_payment_value("codex", tokens_in=1000, tokens_out=500)
    assert result.mode == "subscription"
    assert result.actual_usd == 0.0
    assert result.api_equivalent_usd > 0
    assert result.quota_pct_used is not None
    assert result.quota_pct_used < 1.0


def test_resolve_payment_value_subscription_overage_bills_only_the_excess(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {
        "codex": {
            "mode": "subscription",
            "tier_quota_tokens_in": 1000,
            "tier_quota_tokens_out": 1000,
            "overage_rate_per_1k_in": 0.003,
            "overage_rate_per_1k_out": 0.015,
        }
    })
    import os
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.quota import _upsert_agent_quota
    # Simulate the cycle already having consumed 800 in / 800 out this window.
    _upsert_agent_quota(
        "codex", "monthly", limit_tokens=1000, used_tokens=800,
        model="unknown", unit="tokens",
    )
    from synlynk.costs import resolve_payment_value

    # This call's own 500 in / 500 out tokens push cumulative to 1300 in / 1300 out,
    # 300 over quota on each axis.
    result = resolve_payment_value("codex", tokens_in=500, tokens_out=500)
    assert result.mode == "subscription"
    expected_overage_usd = (300 / 1000 * 0.003) + (300 / 1000 * 0.015)
    assert abs(result.actual_usd - expected_overage_usd) < 0.0001
    assert result.quota_pct_used == 1.0


def test_resolve_payment_value_credit_grant_consumes_balance(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"agy": {"mode": "credit_grant"}})
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 25.0, 25.0, '2026-07-18')"
    )
    conn.commit()
    conn.close()

    from synlynk.costs import resolve_payment_value
    result = resolve_payment_value("agy", tokens_in=1000, tokens_out=1000)
    assert result.mode == "credit_grant"
    assert result.actual_usd == 0.0
    assert result.credit_remaining_usd is not None
    assert result.credit_remaining_usd < 25.0

    conn = sl._get_db()
    remaining = conn.execute(
        "SELECT remaining_usd FROM credit_grants WHERE agent='agy'"
    ).fetchone()[0]
    conn.close()
    assert remaining == result.credit_remaining_usd


def test_resolve_payment_value_credit_grant_falls_back_when_exhausted(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    _write_config(tmp_path, {"agy": {"mode": "credit_grant"}})
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 0.0001, 0.0001, '2026-07-18')"
    )
    conn.commit()
    conn.close()

    from synlynk.costs import resolve_payment_value
    result = resolve_payment_value("agy", tokens_in=1000, tokens_out=1000)
    assert result.mode == "credit_grant"
    assert result.actual_usd > 0.0  # overshoot billed at pay_as_you_go fallback
    assert result.credit_remaining_usd == 0.0


def test_resolve_payment_value_unconfigured_agent_defaults_pay_as_you_go(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.costs import resolve_payment_value
    result = resolve_payment_value("claude", tokens_in=100, tokens_out=100)
    assert result.mode == "pay_as_you_go"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payment_models.py -v -k resolve_payment_value`
Expected: FAIL with `ImportError: cannot import name 'resolve_payment_value'`

- [ ] **Step 3: Write the implementation**

Add to `synlynk/costs.py` (near `_model_rate_for_version`, after its definition):

```python
from dataclasses import dataclass


@dataclass
class PaymentValue:
    api_equivalent_usd: float
    actual_usd: float
    mode: str
    quota_pct_used: Optional[float] = None
    credit_remaining_usd: Optional[float] = None


def _payment_model_config_for_agent(agent: str) -> dict:
    """Returns the agent's payment_models config entry, defaulting to
    pay_as_you_go for any agent not explicitly configured."""
    config = _pkg("load_config")()
    return config.get("payment_models", {}).get(agent, {"mode": "pay_as_you_go"})


def _subscription_actual_usd(agent: str, tokens_in: int, tokens_out: int,
                              pm_config: dict) -> tuple:
    """Returns (actual_usd, quota_pct_used) for subscription mode.

    Reads the agent's cumulative used_tokens from agent_quotas (monthly cycle,
    unit=tokens) BEFORE this call's tokens, adds this call's tokens, and bills
    only the portion of the combined total that exceeds the configured tier
    quota, at the configured overage rate. Cumulative tokens are tracked
    per-axis (in vs out) using the row's used_tokens field twice — once via a
    'tokens_in' quota_type-suffixed row and once via 'tokens_out' — since
    agent_quotas' schema tracks one used_tokens count per (agent, model,
    quota_type, unit) row, not a compound in/out pair.
    """
    from synlynk.quota import _upsert_agent_quota, _pkg as quota_pkg
    get_db = _pkg("_get_db")
    conn = get_db()
    try:
        row_in = conn.execute(
            "SELECT used_tokens FROM agent_quotas WHERE agent=? AND quota_type='monthly' "
            "AND unit='tokens' AND model='unknown'",
            (agent,),
        ).fetchone()
    finally:
        conn.close()
    prior_used_in = row_in[0] if row_in else 0

    tier_quota_in = pm_config["tier_quota_tokens_in"]
    tier_quota_out = pm_config["tier_quota_tokens_out"]
    overage_rate_in = pm_config["overage_rate_per_1k_in"]
    overage_rate_out = pm_config["overage_rate_per_1k_out"]

    cumulative_in = prior_used_in + tokens_in
    # Reuses the single used_tokens counter as a combined in+out proxy is not
    # accurate; store cumulative in and out as two independent rows instead.
    row_out = None
    conn = get_db()
    try:
        row_out = conn.execute(
            "SELECT used_tokens FROM agent_quotas WHERE agent=? AND quota_type='monthly' "
            "AND unit='tokens' AND model='out'",
            (agent,),
        ).fetchone()
    finally:
        conn.close()
    prior_used_out = row_out[0] if row_out else 0
    cumulative_out = prior_used_out + tokens_out

    over_in = max(0, cumulative_in - tier_quota_in)
    over_out = max(0, cumulative_out - tier_quota_out)
    actual_usd = (over_in / 1000 * overage_rate_in) + (over_out / 1000 * overage_rate_out)

    quota_pct_used = max(
        cumulative_in / tier_quota_in if tier_quota_in else 0.0,
        cumulative_out / tier_quota_out if tier_quota_out else 0.0,
    )
    quota_pct_used = min(quota_pct_used, 1.0) if quota_pct_used <= 1.0 else 1.0

    _upsert_agent_quota(agent, "monthly", limit_tokens=tier_quota_in,
                        used_tokens=cumulative_in, model="unknown", unit="tokens")
    _upsert_agent_quota(agent, "monthly", limit_tokens=tier_quota_out,
                        used_tokens=cumulative_out, model="out", unit="tokens")

    return actual_usd, quota_pct_used


def _credit_grant_actual_usd(agent: str, api_equivalent_usd: float) -> tuple:
    """Returns (actual_usd, credit_remaining_usd) for credit_grant mode.

    Consumes the oldest non-expired row with remaining_usd > 0 for this agent,
    oldest-first. If api_equivalent_usd exceeds the remaining balance, only
    the overshoot is billed at the pay_as_you_go fallback rate (the row's
    balance is fully drained to 0, not left negative).
    """
    conn = _pkg("_get_db")()
    try:
        row = conn.execute(
            "SELECT id, remaining_usd FROM credit_grants WHERE agent=? AND remaining_usd > 0 "
            "ORDER BY granted_at ASC LIMIT 1",
            (agent,),
        ).fetchone()
        if row is None:
            return api_equivalent_usd, 0.0

        row_id, remaining = row
        if api_equivalent_usd <= remaining:
            new_remaining = remaining - api_equivalent_usd
            conn.execute(
                "UPDATE credit_grants SET remaining_usd=? WHERE id=?",
                (new_remaining, row_id),
            )
            conn.commit()
            return 0.0, new_remaining
        else:
            overshoot = api_equivalent_usd - remaining
            conn.execute(
                "UPDATE credit_grants SET remaining_usd=0 WHERE id=?", (row_id,)
            )
            conn.commit()
            return overshoot, 0.0
    finally:
        conn.close()


def resolve_payment_value(agent: str, tokens_in: int, tokens_out: int) -> PaymentValue:
    """Computes both the API-equivalent dollar value (unchanged pay-as-you-go
    rate lookup) and the actual dollars charged, branching on the agent's
    configured payment_models mode. Defaults any unconfigured agent to
    pay_as_you_go using today's existing rate-table behavior."""
    pm_config = _payment_model_config_for_agent(agent)
    mode = pm_config.get("mode", "pay_as_you_go")

    model_version = extract_model_version("", agent=agent)
    rates = _model_rate_for_version(model_version, agent=agent)
    api_equivalent_usd = (tokens_in / 1000 * rates["input"]) + (tokens_out / 1000 * rates["output"])

    if mode == "pay_as_you_go":
        return PaymentValue(api_equivalent_usd=api_equivalent_usd,
                            actual_usd=api_equivalent_usd, mode=mode)

    if mode == "subscription":
        actual_usd, quota_pct_used = _subscription_actual_usd(
            agent, tokens_in, tokens_out, pm_config
        )
        return PaymentValue(api_equivalent_usd=api_equivalent_usd, actual_usd=actual_usd,
                            mode=mode, quota_pct_used=quota_pct_used)

    if mode == "credit_grant":
        actual_usd, credit_remaining_usd = _credit_grant_actual_usd(agent, api_equivalent_usd)
        return PaymentValue(api_equivalent_usd=api_equivalent_usd, actual_usd=actual_usd,
                            mode=mode, credit_remaining_usd=credit_remaining_usd)

    return PaymentValue(api_equivalent_usd=api_equivalent_usd,
                        actual_usd=api_equivalent_usd, mode="pay_as_you_go")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payment_models.py -v -k resolve_payment_value`
Expected: PASS (6 tests)

- [ ] **Step 5: Commit**

```bash
git add synlynk/costs.py tests/test_payment_models.py
git commit -m "feat(payment-models): add resolve_payment_value for subscription/credit-grant/pay-as-you-go branching"
```

---

## Task 4: `synlynk credit grant` CLI command

**Files:**
- Modify: `synlynk/db.py` (add `cmd_credit_grant`, near `cmd_cost_log` at line 1602)
- Modify: `synlynk/cli.py` (subparser + dispatch chain)
- Test: `tests/test_payment_models.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_payment_models.py

def test_cmd_credit_grant_inserts_row(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    from synlynk.db import cmd_credit_grant

    cmd_credit_grant(agent="agy", amount=25.0, expires=None, note="Q3 promo credit")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT agent, face_value_usd, remaining_usd, note FROM credit_grants WHERE agent='agy'"
    ).fetchone()
    conn.close()
    assert row == ("agy", 25.0, 25.0, "Q3 promo credit")

    captured = capsys.readouterr()
    assert "25.00" in captured.out


def test_cmd_credit_grant_rejects_negative_amount(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    from synlynk.db import cmd_credit_grant
    import pytest
    with pytest.raises(ValueError):
        cmd_credit_grant(agent="agy", amount=-5.0, expires=None, note=None)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payment_models.py -v -k credit_grant_cli`
(test names above don't include "cli" — run the whole file instead)
Run: `pytest tests/test_payment_models.py -v -k cmd_credit_grant`
Expected: FAIL with `ImportError: cannot import name 'cmd_credit_grant'`

- [ ] **Step 3: Write the implementation**

Add to `synlynk/db.py`, immediately after `cmd_cost_log` (before `def cmd_pr_check():`):

```python
def cmd_credit_grant(agent: str, amount: float, expires: str = None, note: str = None) -> None:
    """Records a new credit grant for an agent — a stated face-value balance
    to be consumed against future api_equivalent_usd charges."""
    from synlynk import _GREEN, _RESET, _get_db
    import time

    if amount < 0:
        raise ValueError("amount must be non-negative")

    granted_at = time.strftime("%Y-%m-%d %H:%M")
    conn = _get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at, expires_at, note) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (agent, amount, amount, granted_at, expires, note),
    )
    conn.commit()
    conn.close()
    print(f"  {_GREEN}✓{_RESET} Credit grant recorded for {agent}: ${amount:.2f}"
          + (f" (expires {expires})" if expires else ""))
```

Modify `synlynk/cli.py` — add a subparser near the `cost`/`pr` block:

```python
    credit_parser = subparsers.add_parser("credit", help="Credit grant ledger commands")
    credit_sub = credit_parser.add_subparsers(dest="credit_action")
    grant_parser = credit_sub.add_parser("grant", help="Record a credit grant for an agent")
    grant_parser.add_argument("--agent", required=True, help="Agent name (e.g. agy, codex)")
    grant_parser.add_argument("--amount", type=float, required=True, help="Face-value USD amount granted")
    grant_parser.add_argument("--expires", default=None, help="ISO8601 expiry date, optional")
    grant_parser.add_argument("--note", default=None, help="Free-text note")
```

Add the dispatch branch:

```python
    elif args.command == "credit":
        if args.credit_action == "grant":
            cmd_credit_grant(agent=args.agent, amount=args.amount, expires=args.expires, note=args.note)
```

Add the import alongside `cmd_cost_log`:

```python
from synlynk.db import cmd_credit_grant
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payment_models.py -v -k cmd_credit_grant`
Expected: PASS (2 tests)

- [ ] **Step 5: Manual smoke test**

Run: `synlynk init && synlynk credit grant --agent agy --amount 25 --note "test grant"`
Expected: prints `✓ Credit grant recorded for agy: $25.00`

- [ ] **Step 6: Commit**

```bash
git add synlynk/db.py synlynk/cli.py tests/test_payment_models.py
git commit -m "feat(payment-models): add synlynk credit grant CLI command"
```

---

## Task 5: Wire `resolve_payment_value()` into `update_costs()` and `costs.md` display

**Files:**
- Modify: `synlynk/costs.py:421-494` (`update_costs`)
- Modify: `synlynk/db.py:439-456, 500+` (`cost_entries` schema — add `api_equivalent_usd`, `actual_usd`, `payment_mode` columns) and `_insert_cost_row` (accept the new fields)
- Modify: `synlynk/db.py`'s `_migrate_db` (idempotent column add for pre-existing DBs)
- Test: `tests/test_payment_models.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_payment_models.py

def test_update_costs_writes_actual_and_api_equivalent_columns(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    sl.init()

    _write_config(tmp_path, {
        "codex": {
            "mode": "subscription",
            "tier_quota_tokens_in": 1000000,
            "tier_quota_tokens_out": 1000000,
            "overage_rate_per_1k_in": 0.003,
            "overage_rate_per_1k_out": 0.015,
        }
    })

    sl.update_costs("codex exec", in_tokens=1000, out_tokens=1000, duration=1.0, agent="codex")

    conn = sl._get_db()
    row = conn.execute(
        "SELECT api_equivalent_usd, actual_usd, payment_mode FROM cost_entries "
        "ORDER BY id DESC LIMIT 1"
    ).fetchone()
    conn.close()
    api_equiv, actual, mode = row
    assert api_equiv > 0
    assert actual == 0.0  # well within the 1M-token tier quota
    assert mode == "subscription"


def test_costs_md_shows_two_dollar_columns_for_subscription_row(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    sl.init()

    _write_config(tmp_path, {
        "codex": {
            "mode": "subscription",
            "tier_quota_tokens_in": 1000000,
            "tier_quota_tokens_out": 1000000,
            "overage_rate_per_1k_in": 0.003,
            "overage_rate_per_1k_out": 0.015,
        }
    })
    sl.update_costs("codex exec", in_tokens=1000, out_tokens=1000, duration=1.0, agent="codex")

    costs_file = os.path.join(sl._synlynk_project_docs_dir(), "costs.md")
    with open(costs_file) as f:
        content = f.read()
    assert "[in-quota]" in content
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payment_models.py -v -k "update_costs_writes or costs_md_shows"`
Expected: FAIL with `sqlite3.OperationalError: no such column: api_equivalent_usd`

- [ ] **Step 3: Write the implementation**

Add the three new columns to `synlynk/db.py`'s `cost_entries` DDL (both the `CREATE TABLE IF NOT EXISTS cost_entries` block at line ~439 and the post-rename `CREATE TABLE cost_entries` block at line ~500 — this table has a legacy rename-and-recreate path for old DBs, both definitions must match):

```sql
            total_cost_usd    REAL,
            api_equivalent_usd REAL,
            actual_usd        REAL,
            payment_mode      TEXT,
            notes             TEXT,
```

Add a migration step in `_migrate_db(conn)` for DBs that already have `cost_entries` without these columns (same idiom as the existing `cost_cols` block at line ~486):

```python
    cost_cols = {row[1] for row in conn.execute("PRAGMA table_info(cost_entries)")}
    for col in ("api_equivalent_usd", "actual_usd", "payment_mode"):
        if col not in cost_cols:
            typedef = "TEXT" if col == "payment_mode" else "REAL"
            try:
                conn.execute(f"ALTER TABLE cost_entries ADD COLUMN {col} {typedef}")
            except sqlite3.OperationalError:
                pass
```

Modify `_insert_cost_row` in `synlynk/db.py:690` — add the three new optional parameters and include them in the INSERT:

```python
def _insert_cost_row(
    session_date: str,
    agent: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cost_source: str,
    total_cost_usd: float,
    notes: str = None,
    story_id: str = None,
    epic_id: int = None,
    phase_id: int = None,
    estimate_basis: str = None,
    job_id: str = None,
    api_equivalent_usd: float = None,
    actual_usd: float = None,
    payment_mode: str = None,
) -> None:
    """Insert or update a cost_entries row through the single sanctioned path."""
    from synlynk import _get_db

    if cost_source not in _VALID_COST_SOURCES:
        raise ValueError(
            f"Invalid cost_source: {cost_source!r}, must be one of {_VALID_COST_SOURCES}"
        )

    conn = _get_db()
    try:
        conn.execute(
            """INSERT INTO cost_entries
               (session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                story_id, epic_id, phase_id, total_cost_usd, notes, cost_source,
                estimate_basis, job_id, api_equivalent_usd, actual_usd, payment_mode)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                session_date, agent, model, input_tokens, output_tokens, cache_read_tokens,
                story_id, epic_id, phase_id, total_cost_usd, notes, cost_source,
                estimate_basis, job_id, api_equivalent_usd, actual_usd, payment_mode,
            ),
        )
        conn.commit()
    finally:
        conn.close()
```

(Note: this replaces the existing job_id-update-vs-insert branch shown in the current file at `db.py:690+` with a plain insert-only path for this plan's tests — if the engineer implementing this finds the existing function already has an `UPDATE ... WHERE job_id=?` branch for idempotent re-runs, preserve that branch and add the three new columns to both the `UPDATE SET` list and the `INSERT` column list, rather than deleting the existing update-on-conflict behavior.)

Modify `synlynk/costs.py`'s `update_costs()` — replace the existing single-rate cost computation block with a call to `resolve_payment_value`:

```python
    rates = _model_rate_for_version(model_version, agent=agent_name)
    cache_read_tokens = 0 if cache_read_tokens is None else cache_read_tokens

    payment_value = resolve_payment_value(agent_name, in_tokens, out_tokens)
    est_cost = payment_value.api_equivalent_usd + (cache_read_tokens / 1000 * rates["cache_read"])
    actual_usd = payment_value.actual_usd + (cache_read_tokens / 1000 * rates["cache_read"]
                                              if payment_value.mode == "pay_as_you_go" else 0.0)

    short_cmd = (command[:20] + '...') if len(command) > 20 else command
    ts = time.strftime('%Y-%m-%d %H:%M')
    if suspicious_token_count:
        flag = "[est?] "
    else:
        flag = "" if cost_source == "actual" else ("[legacy] " if cost_source == "legacy_unknown" else "[est] ")

    if payment_value.mode == "subscription":
        mode_tag = "[in-quota]" if actual_usd == 0.0 else "[overage]"
    elif payment_value.mode == "credit_grant":
        mode_tag = "[credit]"
    else:
        mode_tag = ""
    actual_display = f"${actual_usd:.4f} {mode_tag}".strip()

    entry = (f"| {ts} | {agent_name} | 1 | {in_tokens}/{out_tokens} "
             f"| {flag}${est_cost:.4f} | {actual_display} | exec: {short_cmd} |\n")
```

Add the import at the top of the block that already imports `_insert_cost_row` from `synlynk.db`:

```python
    from synlynk.db import _insert_cost_row
```

(already present — no change needed there) and pass the new fields through the existing `_insert_cost_row(...)` call inside `update_costs()`:

```python
        _insert_cost_row(
            session_date=ts, agent=agent_name, model=model_version,
            input_tokens=in_tokens, output_tokens=out_tokens, cache_read_tokens=cache_read_tokens,
            cost_source=cost_source, estimate_basis=estimate_basis, total_cost_usd=est_cost,
            notes=f"exec: {short_cmd}", story_id=story_id, epic_id=epic_id, phase_id=phase_id,
            job_id=job_id,
            api_equivalent_usd=payment_value.api_equivalent_usd,
            actual_usd=actual_usd,
            payment_mode=payment_value.mode,
        )
```

Add the `resolve_payment_value` import at the top of `synlynk/costs.py` if it isn't already module-local (it's defined in the same file per Task 3, so no import statement needed — it's just called directly).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payment_models.py -v -k "update_costs_writes or costs_md_shows"`
Expected: PASS (2 tests)

- [ ] **Step 5: Run full cost test suite for regressions**

Run: `pytest tests/ -v -k cost`
Expected: All PASS. If any existing test asserts the exact old `costs.md` row format (5 columns), update it to expect the new 6-column format (`| date | agent | reqs | tokens | api-equiv | actual | note |`) — this is an intentional, spec-mandated format change (Section 4), not a regression.

- [ ] **Step 6: Commit**

```bash
git add synlynk/costs.py synlynk/db.py tests/test_payment_models.py
git commit -m "feat(payment-models): wire resolve_payment_value into update_costs, add two-column costs.md display"
```

---

## Task 6: Payment-model rollup line in `check_budgets()`

**Files:**
- Modify: `synlynk/costs.py:532-574` (`check_budgets`)
- Test: `tests/test_payment_models.py` (extend)

- [ ] **Step 1: Write the failing test**

```python
# Add to tests/test_payment_models.py

def test_check_budgets_prints_payment_model_rollup(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    import os
    os.makedirs(".synlynk", exist_ok=True)
    import synlynk as sl
    sl.init()

    _write_config(tmp_path, {
        "codex": {
            "mode": "subscription",
            "tier_quota_tokens_in": 1000000,
            "tier_quota_tokens_out": 1000000,
            "overage_rate_per_1k_in": 0.003,
            "overage_rate_per_1k_out": 0.015,
        },
        "agy": {"mode": "credit_grant"},
    })
    conn = sl._get_db()
    conn.execute(
        "INSERT INTO credit_grants (agent, face_value_usd, remaining_usd, granted_at) "
        "VALUES ('agy', 25.0, 14.20, '2026-07-18')"
    )
    conn.commit()
    conn.close()

    sl.update_costs("codex exec", in_tokens=1000, out_tokens=1000, duration=1.0, agent="codex")

    sl.check_budgets()
    captured = capsys.readouterr()
    assert "Payment Models" in captured.out
    assert "codex" in captured.out
    assert "subscription" in captured.out
    assert "agy" in captured.out
    assert "14.20" in captured.out
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_payment_models.py -v -k check_budgets_prints_payment_model_rollup`
Expected: FAIL with `AssertionError: assert 'Payment Models' in ''`

- [ ] **Step 3: Write the implementation**

Modify `synlynk/costs.py`'s `check_budgets()` — append this block at the end of the function, after the existing failed-job placeholder print:

```python
def check_budgets() -> None:
    """Warns if cumulative spend from costs.md approaches config limits."""
    config = _pkg("load_config")()
    limit_usd = config["budget"]["limit_usd"]
    limit_reqs = config["budget"]["limit_requests"]
    total_usd, _ = _pkg("parse_costs_md")()

    # Request count from telemetry exec events
    total_reqs = 0
    telemetry_file = ".synlynk/telemetry.json"
    if os.path.exists(telemetry_file):
        try:
            with open(telemetry_file) as f:
                data = json.load(f)
            total_reqs = sum(1 for e in data if e.get("type") == "exec")
        except (json.JSONDecodeError, IOError):
            pass

    if total_usd >= limit_usd:
        print(f"\n🛑 [Budget Alert] CRITICAL: Spent ${total_usd:.2f} / ${limit_usd:.2f}.")
    elif total_usd >= limit_usd * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of cost budget (${total_usd:.2f} / ${limit_usd:.2f}).")

    if total_reqs >= limit_reqs:
        print(f"\n🛑 [Budget Alert] CRITICAL: {total_reqs} / {limit_reqs} request limit.")
    elif total_reqs >= limit_reqs * 0.8:
        print(f"\n⚠️  [Budget Warning] 80% of request limit ({total_reqs} / {limit_reqs}).")

    conn = _pkg("_get_db")()
    try:
        failed_row = conn.execute(
            "SELECT COUNT(*), COALESCE(SUM(total_cost_usd), 0) FROM cost_entries "
            "WHERE cost_source = 'estimated_tshirt' AND estimate_basis = 'fixed_default' "
            "AND notes LIKE '%failed job%'"
        ).fetchone()
        payment_rows = conn.execute(
            "SELECT agent, payment_mode, actual_usd FROM cost_entries "
            "WHERE payment_mode IS NOT NULL ORDER BY id"
        ).fetchall()
    finally:
        conn.close()
    failed_count, failed_usd = failed_row
    if failed_count:
        print(
            f"  ℹ️  {failed_count} failed-job placeholder estimates, ${failed_usd:.2f} "
            "(not blended into the spend total above)"
        )

    if payment_rows:
        payment_models_config = config.get("payment_models", {})
        seen_agents = {}
        for agent, mode, actual in payment_rows:
            seen_agents[agent] = (mode, actual)  # last-seen row per agent wins (most current state)

        print("\n  Payment Models")
        for agent, (mode, actual) in seen_agents.items():
            if mode == "subscription":
                conn = _pkg("_get_db")()
                try:
                    row = conn.execute(
                        "SELECT limit_tokens, used_tokens FROM agent_quotas "
                        "WHERE agent=? AND quota_type='monthly' AND unit='tokens' AND model='unknown'",
                        (agent,),
                    ).fetchone()
                finally:
                    conn.close()
                pct = int(100 * row[1] / row[0]) if row and row[0] else 0
                print(f"    {agent:<8}[subscription]  quota: {pct}% used this cycle (${actual:.2f} marginal)")
            elif mode == "credit_grant":
                conn = _pkg("_get_db")()
                try:
                    grant_row = conn.execute(
                        "SELECT remaining_usd, face_value_usd FROM credit_grants "
                        "WHERE agent=? ORDER BY granted_at DESC LIMIT 1",
                        (agent,),
                    ).fetchone()
                finally:
                    conn.close()
                if grant_row:
                    remaining, face_value = grant_row
                    print(f"    {agent:<8}[credit_grant]  balance: ${remaining:.2f} remaining of ${face_value:.2f} granted")
            else:
                print(f"    {agent:<8}[pay_as_you_go] ${actual:.2f} this run")
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_payment_models.py -v -k check_budgets_prints_payment_model_rollup`
Expected: PASS

- [ ] **Step 5: Run full test suite for regressions**

Run: `pytest tests/ -v -k "budget or cost"`
Expected: All PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/costs.py tests/test_payment_models.py
git commit -m "feat(payment-models): add per-agent payment-model rollup to Budget Pulse output"
```

---

## Self-Review Notes

**Spec coverage:**
- Section 1 (Config schema) → Task 1.
- Section 2 (Value calculation, `PaymentValue`/`resolve_payment_value`) → Task 3, covering all three modes plus the unconfigured-agent default.
- Section 3 (Credit grants ledger + `synlynk credit grant`) → Task 2 (table), Task 4 (CLI command), and the oldest-first consumption + fallback-on-exhaustion logic in Task 3's `_credit_grant_actual_usd`.
- Section 4 (Display — two `costs.md` columns + Budget Pulse rollup) → Task 5 (columns), Task 6 (rollup line).
- Schema Changes Summary → `credit_grants` (Task 2), `payment_models` config (Task 1), `costs.md` two columns (Task 5), `synlynk credit grant` (Task 4) — all covered.
- Out of Scope items are not implemented: no ROI/efficiency comparison command, no automatic overage-rate detection (Task 3 always uses the user-configured flat rate from `payment_models` config), no backfill/migration of historical `costs.md` rows (Task 5's new columns are additive — old rows keep their original 5-column shape; only new rows get 6 columns, exactly as Section 4 specifies "applies going forward only"), and `check_budgets()`/`_write_capability_rating`/`agent_quotas` internals are read from (in Task 3 and Task 6) but never restructured — their existing writers and raw-count contracts are untouched.

**Placeholder scan:** No TBD/TODO markers. Task 5's Step 3 includes an explicit disclosed caveat about `_insert_cost_row`'s possible pre-existing `UPDATE ... WHERE job_id=?` branch (this plan's source excerpt showed the branch starting but was not fully re-verified against the exact current file state at planning time) with a concrete instruction for what to do if found, rather than silently assuming one shape.

**Type consistency:** `PaymentValue` (dataclass with `api_equivalent_usd`, `actual_usd`, `mode`, `quota_pct_used`, `credit_remaining_usd`) is defined once in Task 3 and referenced with identical field names in every later task. `resolve_payment_value(agent, tokens_in, tokens_out)` signature is consistent between its Task 3 definition and its Task 5 call site inside `update_costs()`. `cmd_credit_grant(agent, amount, expires, note)` signature matches between Task 4's definition and its CLI dispatch call in `cli.py`.

**Sequencing:** Task 1 and Task 2 are independent and can run in parallel. Task 3 depends on Task 1 (config) and Task 2 (`credit_grants` table). Task 4 depends on Task 2. Task 5 depends on Task 3. Task 6 depends on Task 5 (reads `cost_entries.payment_mode`, populated there).
