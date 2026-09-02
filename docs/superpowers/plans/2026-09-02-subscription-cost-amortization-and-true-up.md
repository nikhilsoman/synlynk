# Implementation Plan: Subscription Cost Amortization, Extra Usage, and End-of-Month True-Up

**Issue:** [#787](https://github.com/nikhilsoman/synlynk/issues/787)  
**Spec:** `docs/superpowers/specs/2026-09-02-subscription-cost-amortization-and-true-up-design.md`  
**Date:** 2026-09-02  

---

## Tasks

- [ ] **Task 1: Extend Harness Billing Configuration Schema**
  - Update `load_config()` in `synlynk/__init__.py` to support `harness_billing` structure (`payment_mode`, `monthly_base_fee_usd`, `projected_monthly_tokens`, `allow_extra_usage`, `extra_usage_cap_usd`).
  - Add unit tests in `tests/test_costs.py`.

- [ ] **Task 2: Implement Dynamic Subscription Amortization & Overage in `synlynk/costs.py`**
  - Update `resolve_payment_value()` and `_subscription_actual_usd()` to compute amortized rate from prior month throughput or projected volume.
  - Implement metered overage transition when `allow_extra_usage` is true and token threshold is exceeded.
  - Set `actual_usd = 0.0` for `payment_mode="zero_cost"` (`local` harness).

- [ ] **Task 3: Implement True-Up Reconciler CLI (`synlynk cost true-up`)**
  - Add `cmd_cost_true_up()` in `synlynk/costs.py` computing monthly variance $\Delta = \text{Total Billed} - \sum \text{actual\_usd}$ and writing a `true_up_reconciliation` row into `cost_entries`.
  - Expose CLI command `synlynk cost true-up` in `synlynk/__init__.py`.

- [ ] **Task 4: Update Documentation, Devlog, and Memory**
  - Add unit tests for all true-up and amortization cases in `tests/test_costs.py`.
  - Write blog post `docs/blog/161-pr1337-subscription-cost-amortization.md` and update `docs/blog/README.md`.
  - Update `project-docs/memory.md` and devlogs.
