---
title: "Wave 4: add a repository without minting another identity"
author: "Nikhil Soman"
date: 2026-09-18
pr: "#1651"
version: "0.21.0"
tags: [workspace, identity, repositories]
---

# Wave 4: add a repository without minting another identity

Wave 4 adds `synlynk workspace add-repo [<nwo>]` for product-scoped workspaces.

The command records the clone's `repo_id`, updates canonical product App JSON
reach, and writes a small `repos.json` ledger. Specialist Apps remain unchanged
unless they already list the repository. It never calls GitHub's installation
API: an operator still selects the repository in the GitHub App install UI.

Runtime checks now fail closed when a configured clone has no `identity_slug`,
and `synlynk doctor` reports missing specialist App material and invalid merge
authority types.
