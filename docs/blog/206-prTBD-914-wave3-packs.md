---
title: "Wave 3 — Industry packs for workspace identity"
author: "Nikhil Soman"
date: 2026-09-18
post: 206
pr: TBD
series: "Workspace identity"
tags: [identity, packs, cli]
---

# Wave 3 — Industry packs for workspace identity

Wave 3 keeps the W5 type registry small while making its canonical set product
aware. Software projects retain the existing defaults, while studio and agency
workspaces can seed their own stable type IDs and human-facing labels.

Pack files are JSON bodies kept under `.yaml` names so synlynk stays
dependency-free. The registry validates `type create --kind` against the union
of shipped pack kinds, while unknown kinds continue to fail closed.

The new `synlynk type seed --pack <id>` command makes pack selection explicit.
`identity init --pack <id>` uses the same seed path for an empty product store;
without a pack it remains software-product-compatible.
