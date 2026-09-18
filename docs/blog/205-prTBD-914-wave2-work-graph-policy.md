---
title: "Wave 2 — One product graph and policy authority"
author: "Nikhil Soman"
date: 2026-09-18
pr: "#1649"
version: "0.21.0"
tags: [workspace, identity, policy]
---

# Wave 2 — One product graph and policy authority

Wave 2 of #914 moves synlynk's graph to the product store at
`~/.synlynk/workspaces/<identity_slug>/state.db`. Legacy databases are copied
once, never overwritten, and pytest continues to use isolated databases.

The same product boundary now owns policy. A repository policy may provide
local settings, but merge and connector authority come from the product policy.
Merge checks resolve known type IDs: only canonical `qa` types can merge, while
unknown IDs retain the legacy string check for compatibility.

Stories keep a nullable `repo_id`, and jobs and costs keep a nullable `type_id`,
so one product graph can relate work without pretending that constituent repos
are the same codebase.
