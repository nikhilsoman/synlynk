# Plan: Intent-Based Product Development (IBPD) Engine (Track 4 / v0.36.0)

**Date:** 2026-11-14
**Spec:** `docs/superpowers/specs/2026-11-13-intent-based-product-development-design.md`
**Issue:** #5247 (Master Roadmap Epic)
**Branch:** `feat/v0.36.0-ibpd-engine`

---

## 1. Goal

Implement the Intent-Based Product Development (IBPD) Engine representing Master Roadmap Phase 3 (Self-Serve Tiered Delivery Ladder: Tier 1 Self-Serve, Tier 2 Assisted Self-Serve, Tier 3 Fully Managed), integrated into synlynk's Editions registry as `hosted` capabilities, with CLI commands, state introspection, and rigorous automated tests.

---

## 2. Tasks

### Task 1: Core IBPD Domain & Primitives (`synlynk/ibpd.py`)
- Define `DeliveryTier` dataclass / enum (`Tier 1 — Self-Serve`, `Tier 2 — Assisted Self-Serve`, `Tier 3 — Fully Managed`).
- Define `IBPDDeliveryLadder` containing metadata for each tier:
  - Who drives (`Customer` vs `Customer (review/approval only)`)
  - Who executes (`Customer own fleet` vs `Customer fleet + synlynk playbooks` vs `Synlynk operator fleet`)
  - Revenue / commercial model (`Subscription`, `Professional services / decide panel`, `Outcome-based / retainer`)
  - Cost bearer classification (`core` for Tier 1, `hosted` for Tiers 2 and 3 per Editions spec)
- Define engagement contract validation (`EngagementContract`, `validate_engagement_contract`, `evaluate_tier_requirements`).
- Implement `get_ibpd_status(conn=None)` inspecting current workspace configuration, GOVERNS enforcement status, and active delivery tier.

### Task 2: Edition Registry Linkage (`synlynk/editions.py`)
- Register `ibpd_tier2_assisted` and `ibpd_tier3_managed` in the Editions capability registry (`CAPABILITIES`) with `category: "hosted"`.
- Implement capability checks verifying edition entitlement and gating.

### Task 3: CLI Subsystem & Taxonomy (`synlynk/cli.py` & `synlynk/taxonomy.py`)
- Add `ibpd` CLI subparser to `synlynk/cli.py`:
  - `synlynk ibpd status [--json]`
  - `synlynk ibpd tiers [--json]`
  - `synlynk ibpd quote --tier <1|2|3> [--repo <path>] [--stories <n>] [--json]`
- Update command taxonomy in `synlynk/taxonomy.py` (`ibpd status`, `ibpd tiers`, `ibpd quote`).

### Task 4: Comprehensive Test Suite (`tests/test_ibpd.py`)
- Unit tests for all tiers, metadata, trust ladder progression, and editions binding.
- CLI tests verifying `synlynk ibpd status`, `synlynk ibpd tiers`, and `synlynk ibpd quote`.
- Contract validation tests ensuring Tier 3 enforces synlynk GOVERNS policy and personal-token prohibition.

### Task 5: Version Bump & Release Documentation
- Bump `VERSION` to `0.36.0`.
- Document `v0.36.0` in `CHANGELOG.md`.
- Regenerate commands documentation (`scripts/generate_command_docs.py`).
- Verify `release --check-docs` passes.
- Open PR, run QA review approval, verify all CI checks, and merge.
