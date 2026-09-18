---
title: "Wave 5 — Local Vizor Board over the product graph"
author: "Nikhil Soman"
date: 2026-09-18
pr: "TBD"
version: "0.21.0"
tags: [workspace, identity, vizor, board]
---

# Wave 5 — Local Vizor Board over the product graph

Wave 5 adds a local Vizor Board over the product-scoped `state.db`. Cards can
be filtered by repository, type, and goal, and status changes write directly
to that product graph. Stored GitHub and Linear-style pointers become safe
deep-links; unknown tracker surfaces stay non-clickable until an adapter
exists.

The Board is deliberately local. GitHub Projects is not the source of truth,
no tracker SDK is contacted, and hosted Vizor remains the later W9 slice.
