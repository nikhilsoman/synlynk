# Task 3 Brief: Quad-Harness Subscription Configuration & `harness_billing` Seed (LIVE-20)

**Story ID:** `story-741f9192`  
**Harness:** `codex` | **Role:** `implement`  
**Base Branch:** `fix/agy/live-19-live-20-remediation`  

## Objective
Wire the user's real quad-harness subscription billing structure into `.synlynk/config.json`, ensure default config bootstrapping initializes it properly, and verify `_payment_model_config_for_agent()` resolves all 4 harnesses to subscription mode.

## Requirements
1. **TDD:** Create `tests/test_harness_billing_config.py`:
   - Test 1: Verify `.synlynk/config.json`'s `harness_billing` block resolves all 4 harnesses:
     - `claude`: `mode: "subscription"`, `monthly_base_fee_usd: 20.0`
     - `codex`: `mode: "subscription"`, `monthly_base_fee_usd: 20.0`
     - `agy`: `mode: "subscription"`, `monthly_base_fee_usd: 20.0`
     - `grok`: `mode: "subscription"`, `monthly_base_fee_usd: 30.0`
     - Total baseline subscription = $90.00/month.
   - Test 2: In `synlynk.costs::_payment_model_config_for_agent()`, verify each harness returns `mode: "subscription"` and the configured base fee.
   - Test 3: In `synlynk.costs::resolve_payment_value()`, verify that a job dispatch on any of the 4 harnesses computes amortized `actual_usd` distinct from `api_equivalent_usd` under subscription mode.
2. **Implementation:**
   - Update `.synlynk/config.json` with the quad-harness subscription structure.
   - In `synlynk/__init__.py::_default_config()`, ensure defaults seed `harness_billing` cleanly if empty.
3. **Verification:**
   - Run `pytest tests/test_harness_billing_config.py tests/test_payment_models.py` and ensure 100% pass.
