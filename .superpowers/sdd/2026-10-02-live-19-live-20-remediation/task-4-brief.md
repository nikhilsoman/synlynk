# Task 4 Brief: Dual-Ledger Markdown Generation & Monthly Amortization Rollup (LIVE-20)

**Story ID:** `story-73e0a8e5`  
**Harness:** `agy` | **Role:** `implement`  
**Base Branch:** `fix/agy/live-19-live-20-remediation`  

## Objective
Update `synlynk/db.py::_generate_costs_md()` so `project-docs/costs.md` renders the dual ledger (actual amortized cost vs API equivalent value) while strictly preserving backwards-compatibility with `parse_costs_md()` and existing test fixtures. Add `synlynk cost billing` CLI command.

## Requirements
1. **TDD:** Create `tests/test_costs_dual_ledger_live20.py`:
   - Test 1: In `_generate_costs_md()`, when `payment_mode == 'subscription'`, the generated markdown row in `project-docs/costs.md` formats `Cost` as:
     `$X.XXXX [sub] (API: $Y.YYYY)`
     where `$X.XXXX` is `actual_usd` and `$Y.YYYY` is `api_equivalent_usd`.
   - Test 2: In `parse_costs_md()`, verify that rows with `$X.XXXX [sub] (API: $Y.YYYY)` are parsed cleanly without error and return `$X.XXXX` as the cost value.
   - Test 3: Verify the table header is preserved exactly:
     `| Date | Agent | Model | Tokens In | Tokens Out | Cost | Source | Story | Notes |`
   - Test 4: Verify an active monthly summary section is appended:
     `## Subscription Amortization & Dual-Ledger Summary`
     displaying monthly base fees, actual amortized spend, API equivalent value, and net savings.
   - Test 5: Verify `synlynk cost billing` outputs an ASCII table detailing the 4 harnesses, their subscription mode, monthly fees ($90 total), and projected tokens.
2. **Implementation:**
   - In `synlynk/db.py::_generate_costs_md()`:
     - Query selects `session_date, agent, model, input_tokens, output_tokens, total_cost_usd, cost_source, story_id, notes, api_equivalent_usd, actual_usd, payment_mode`.
     - Render subscription rows with `$X.XXXX [sub] (API: $Y.YYYY)` when `payment_mode == 'subscription'` and `actual_usd is not None`.
     - Append `## Subscription Amortization & Dual-Ledger Summary` section at the end of `costs.md`.
   - In `synlynk/costs.py`:
     - Add `cmd_cost_billing(args)` to print the billing summary.
   - In `synlynk/cli.py` & `synlynk/taxonomy.py`:
     - Register subcommand `cost billing` with help text "Show harness subscription billing and amortization configuration".
3. **Verification:**
   - Run `pytest tests/test_costs_dual_ledger_live20.py tests/test_payment_models.py tests/test_taxonomy.py tests/test_docs_sync.py` and ensure 100% pass.
