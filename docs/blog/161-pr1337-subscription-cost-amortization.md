---
title: "PR #1337 - Subscription Cost Amortization and True-Up"
date: 2026-09-02
series: "Building the OS for Multi-Agent Development"
post: 161
pr: "#1337"
merged: status: open
---

## The Broader Goal at the End of the Previous PR

The cost ledger needed to distinguish the commercial value of tokens from the
cash actually spent on a harness plan.

## What This PR Shipped

Issue #787 adds `harness_billing` configuration for subscription, metered, and
zero-cost harnesses. Subscription calls amortize a monthly base fee over
projected or prior-month throughput, while optional extra usage is charged at
the model's metered rates and bounded by a configured cap. Local inference
records zero realized cash outlay while retaining API-equivalent value.

The new `synlynk cost true-up` command reconciles a billing month against the
recorded ledger and writes an auditable `true_up_reconciliation` row. Unit
tests cover configuration defaults, amortization, local zero-cost behavior,
and under-usage reconciliation.

## What This Achieved on the Path to Autonomy

Dispatch economics can now be evaluated using realized cash outlay without
losing the comparable API-equivalent benchmark, making harness selection and
monthly budgeting more trustworthy.

## Strategic Note: The Goal at the End of This PR

The ledger is now ready to compare planned subscription economics with actual
provider invoices at the end of each billing cycle.
