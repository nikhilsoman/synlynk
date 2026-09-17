---
title: "Wave 1 — Product-Scoped GitHub Apps and Types"
date: 2026-09-17
series: "Building the OS for Multi-Agent Development"
post: 204
pr: "#TBD"
status: open
---

## The Broader Goal at the End of the Previous PR

W0 defined workspace identity vocabulary and the W1-W9 implementation sequence. The next goal was to make a product's durable GitHub identity survive clones and worktrees.

## Strategic Shifts in This PR

The App and PEM home is now keyed by `identity_slug` under `~/.synlynk/workspaces/`, while legacy repo material remains readable for migration. Product types are recorded beside that store, without moving `state.db` or distributing PEMs.

## What This PR Shipped

Wave 1 adds absolute product path resolution, product-first App lookup, one-shot legacy copying, fail-closed duplicate App initialization, product-store doctor checks, and a dependency-free canonical `software-product` type registry. `synlynk type create` creates a specialist type without contacting GitHub, and canonical identity initialization seeds the registry first.

## Brainstorm Visuals Used

None.

## What This Achieved on the Path to Autonomy

Dispatch and token minting no longer depend on a worktree-relative PEM path. A second clone of the same product reuses the durable type identity instead of silently minting another App.

## Strategic Note: The Goal at the End of This PR

Wave 1 is stacked on #1647 and advances #914 without closing it. The next goal is to land the product work graph and policy layers in later waves.
