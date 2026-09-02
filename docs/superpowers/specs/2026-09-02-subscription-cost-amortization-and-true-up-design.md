# Design Spec: Subscription Cost Amortization, Extra Usage, and End-of-Month True-Up

**Issue:** [#787](https://github.com/nikhilsoman/synlynk/issues/787)  
**Date:** 2026-09-02  
**Status:** Approved  
**Author:** [@nikhilsoman], [@agy]  

---

## 1. Objective

Provide an accurate, dual-ledger cost engine in `synlynk/costs.py` that differentiates between:
1. **API Equivalent Value (`api_equivalent_usd`):** Standard commercial developer list-price cost for token volume.
2. **Realized Cash Outlay (`actual_usd`):** True marginal/amortized dollar spend accounting for fixed-fee subscription tiers, extra usage overages, zero-cost local inference, and end-of-month true-up reconciliation.

---

## 2. Architectural Design & Formulas

### A. Configuration Schema (`.synlynk/config.json`)

```json
{
  "harness_billing": {
    "claude": {
      "payment_mode": "subscription",
      "monthly_base_fee_usd": 20.00,
      "billing_cycle_day": 1,
      "projected_monthly_tokens": 10000000,
      "allow_extra_usage": true,
      "extra_usage_cap_usd": 50.00
    },
    "codex": {
      "payment_mode": "subscription",
      "monthly_base_fee_usd": 20.00,
      "billing_cycle_day": 1,
      "projected_monthly_tokens": 10000000
    },
    "agy": {
      "payment_mode": "pay_as_you_go"
    },
    "grok": {
      "payment_mode": "pay_as_you_go"
    },
    "local": {
      "payment_mode": "zero_cost"
    }
  }
}
```

### B. Projected Amortization Rate (During Month)

For harnesses in `subscription` mode:
- If prior month tokens $T_{\text{prior}} > 0$, set $T_{\text{projected}} = T_{\text{prior}}$; otherwise use `projected_monthly_tokens` from config (default $10\text{M}$ tokens).
- Effective token rate:
  $$\text{rate}_{\text{amortized}} = \frac{\text{monthly\_base\_fee\_usd}}{T_{\text{projected}} / 1000}$$
- Each job logs:
  - `api_equivalent_usd = (tokens_in / 1000 * rate_in) + (tokens_out / 1000 * rate_out)`
  - `actual_usd = (tokens_in + tokens_out) / 1000 * rate_amortized`
  - `cost_source = "amortized_subscription"`

### C. Extra Usage Tracking (Metered Overages)

When `allow_extra_usage = true`:
- If cumulative monthly tokens exceed base tier threshold ($T_{\text{projected}}$):
  - Tokens up to threshold bill at $\text{rate}_{\text{amortized}}$.
  - Tokens above threshold bill at metered pay-as-you-go rates.
  - Hard cap at `extra_usage_cap_usd`.

### D. End-of-Month True-Up Reconciler

At the close of the billing cycle (or when invoking `synlynk cost true-up`):
1. Query total `actual_usd` recorded in `cost_entries` for the billing month.
2. Determine total cash billed by provider:
   $$\text{Total Billed} = \text{monthly\_base\_fee\_usd} + \text{extra\_usage\_usd}$$
3. Compute True-Up Variance:
   $$\Delta = \text{Total Billed} - \sum \text{actual\_usd}$$
4. Insert reconciling row into `cost_entries`:
   - `job_id = None`
   - `cost_source = "true_up_reconciliation"`
   - `actual_usd = \Delta`
   - `api_equivalent_usd = 0.0`
   - `notes = "End-of-month subscription true-up reconciliation for YYYY-MM"`

---

## 3. Storage & CLI Updates

1. **`synlynk cost log` & `synlynk status`:**
   - Display dual cost summaries: *Actual Outlay* vs *API Equivalent Value*.
2. **`synlynk cost true-up`:**
   - New CLI verb to inspect or run true-up reconciliation.
3. **`project-docs/costs.md`:**
   - Appends monthly reconciled summaries.

---

## 4. Test Strategy

1. **Unit tests in `tests/test_costs.py`:**
   - Verify amortized rate calculation for subscription harnesses.
   - Verify transition to extra usage overage rates.
   - Verify true-up reconciliation math for under-usage and over-usage.
   - Verify zero-cost handling for `local` harness.
