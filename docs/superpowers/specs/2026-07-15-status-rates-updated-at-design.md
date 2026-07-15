# `synlynk status` — Surface `rates_updated_at` Design Spec

**Issue:** #259
**Closes:** epic #210 (final remaining item, alongside #258 which shipped as PR #264)
**Theme:** v0.12.0 Measurement Ledger Hardening

## Context

Fable's 2026-07-12 strategic review (`docs/strategy/2026-07-12-fable-deep-review-and-strategic-roadmap.md`, §6.3 Horizon 0 item 1) asked for `_MODEL_RATE_TABLE` to move out of code into an updatable data file "with a `rates_updated_at` shown in `status`." The data-file move shipped in Measurement Ledger Phase 1 (`.synlynk/model_rates.json`, PR #236). `synlynk/costs.py`'s `_load_model_rates()` already returns a dict containing a `rates_updated_at` key — a `"YYYY-MM-DD"` string when `synlynk init` seeded/updated the file (`synlynk/__init__.py:3408`), or `None` when no rate file exists and the loader falls back to `_HARDCODED_FALLBACK_RATES` (`synlynk/costs.py:289-306`). Nothing in `synlynk/status.py` reads or displays this field today — confirmed via `grep -rn "rates_updated_at" synlynk/*.py`, which matches only the two definition/seed sites, not `status.py`.

This closes epic #210's last remaining scope: every cost-relevant number the ecosystem surfaces should be either structurally sourced or visibly flagged when it isn't — a stale or never-updated rate table currently fails that bar silently.

## Scope

`synlynk/status.py` only: `cmd_status()` and `_format_status_terminal()`. No schema changes, no changes to `costs.py` (the loader and its return shape are already correct and unchanged). No changes to `synlynk init`'s seeding behavior.

## Design

### Data flow

`cmd_status()` (`synlynk/status.py:350`) currently loads `config`, `harness_rows`, `cycle_map`, `efficiency`, and `sentinels_active` before calling `_format_status_terminal()`. It gains one more load:

```python
from synlynk.costs import _load_model_rates
...
rates_updated_at = _load_model_rates().get("rates_updated_at")
```

This is passed through to `_format_status_terminal()` as a new keyword argument.

### `_format_status_terminal()` signature change

Current signature (`synlynk/status.py:282-289`):

```python
def _format_status_terminal(
    harness_rows: list,
    cycle_map: dict,
    efficiency_ratio: float,
    dispatch_mode: str,
    sentinels_active: int,
    json_output: bool = False,
) -> str:
```

New signature — one new keyword-only-by-convention parameter with a default, so the two existing direct-call tests (`test_format_status_terminal_structure`, `test_format_status_json_valid` in `tests/test_ecosystem_status.py`) that don't pass it keep working unchanged:

```python
def _format_status_terminal(
    harness_rows: list,
    cycle_map: dict,
    efficiency_ratio: float,
    dispatch_mode: str,
    sentinels_active: int,
    json_output: bool = False,
    rates_updated_at: Optional[str] = None,
) -> str:
```

(`Optional` is already imported in `status.py`'s typing imports — verify at implementation time; add the import if not.)

### JSON output

In the `if json_output:` branch (`synlynk/status.py:294-307`), add one top-level key to the `payload` dict, alongside `headless_efficiency`, `fleet`, etc.:

```python
payload = {
    "headless_efficiency": efficiency_ratio,
    "fleet": {...},
    "agents": {...},
    "cycle_capability": cycle_map,
    "capacity": TIER1_CAPACITY,
    "sentinels_active": sentinels_active,
    "rates_updated_at": rates_updated_at,
}
```

`rates_updated_at` serializes as the date string or JSON `null` — no special-casing needed, `json.dumps` handles `None` natively.

### Terminal output

Insert one new line immediately after the existing `BUDGET` line in the `lines` list (`synlynk/status.py:311-321`):

```python
lines = [
    f"SYNLYNK ECOSYSTEM STATUS  {ts}",
    "━" * 44,
    "",
    f"HEADLESS EFFICIENCY  {efficiency_ratio}×   headless dispatch baseline",
    "",
    f"FLEET   {attached}/{len(agents)} attached   mode: {dispatch_mode}",
    "BUDGET  limit tracked via .synlynk/config.json",
    _format_rates_line(rates_updated_at),
    "",
    f"{'AGENT SCORE':<14} {'ATTACH':>8}  {'COMPLETE':>9}  {'VERSION':>10}",
]
```

New small helper (keeps the conditional string out of the list literal):

```python
def _format_rates_line(rates_updated_at: Optional[str]) -> str:
    if rates_updated_at:
        return f"RATES   updated {rates_updated_at}"
    return "RATES   never updated ⚠ (hardcoded defaults)"
```

Rendered examples:
```
BUDGET  limit tracked via .synlynk/config.json
RATES   updated 2026-07-13
```
```
BUDGET  limit tracked via .synlynk/config.json
RATES   never updated ⚠ (hardcoded defaults)
```

## Testing

Two new tests in `tests/test_ecosystem_status.py`, placed next to the existing `test_format_status_terminal_structure` / `test_format_status_json_valid` pair:

1. **`test_format_status_terminal_shows_rates_updated_date`** — call `_format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0, rates_updated_at="2026-07-13")`, assert `"RATES   updated 2026-07-13"` appears in the output.
2. **`test_format_status_terminal_shows_rates_never_updated_warning`** — call `_format_status_terminal(rows, cycle_map, 4.2, "daily-grind", 0, rates_updated_at=None)` (or omit the kwarg to test the default), assert `"RATES   never updated ⚠ (hardcoded defaults)"` appears in the output.
3. **`test_format_status_json_includes_rates_updated_at`** — call `_format_status_terminal(rows, {}, 1.0, "eco", 2, json_output=True, rates_updated_at="2026-07-13")`, `json.loads` the result, assert `data["rates_updated_at"] == "2026-07-13"`.
4. **`test_cmd_status_json_output_reads_rates_from_file`** — extend the existing `test_cmd_status_json_output` pattern: write a `.synlynk/model_rates.json` fixture file (matching the shape from `tests/test_cost_ledger.py::test_load_model_rates_valid_file`, i.e. `{"unit": "usd_per_1k_tokens", "rates_updated_at": "2026-07-13", "models": {}, "billing_mode": {}}`) into `tmp_path`, call `cmd_status(db_conn=db, json_output=True)`, assert the returned JSON's `rates_updated_at` equals `"2026-07-13"`. A second variant with no rate file present asserts `data["rates_updated_at"] is None`.

No changes needed to the two pre-existing direct-call tests (`test_format_status_terminal_structure`, `test_format_status_json_valid`) — they'll continue to pass with the new parameter defaulting to `None`, which renders the "never updated" warning line / `null` JSON value harmlessly since neither test asserts on that specific line.

## Out of scope

- Any change to how `.synlynk/model_rates.json` is created, seeded, or updated (Phase 1, already shipped).
- Staleness thresholds (e.g., warning if the date is >90 days old) — the issue asks only for visibility of the value, not age-based alerting. Not requested, not building it (YAGNI).
- Vizor/HTML surfaces — this issue is scoped to `synlynk status` (terminal + `--json`) only, per the issue body.
