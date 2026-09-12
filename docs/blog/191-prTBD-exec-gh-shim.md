---
title: "191-prTBD-exec-gh-shim"
author: "synlynk team"
date: 2026-09-06
post: 191
pr: "—"
type: pr
series: "Building the OS for Multi-Agent Development"
tags: posts
version: "0.19.0"
---
# The `synlynk exec` GitHub CLI guard

`synlynk exec` now places a short-lived `gh` shim at the front of the child
process's `PATH`. This closes the remaining Hole B in #1436 without changing
the operator's login shell or intercepting ordinary `gh` commands.

The shim fails closed when neither a role App token nor the explicit
`SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH` opt-in is present. With either token
environment variable (`GH_TOKEN` or `GITHUB_TOKEN`) set, or with the opt-in,
it removes its own directory from `PATH`, finds the real `gh`, and `exec`s it.

This keeps role-scoped GitHub writes explicit through `synlynk gh --role` and
prevents a raw child `gh` from silently using the host `nikhilsoman` identity.