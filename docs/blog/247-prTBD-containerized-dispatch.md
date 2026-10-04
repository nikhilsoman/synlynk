---
title: "gh:#1925 Part 2 — An opt-in container for an untrusted harness"
date: 2026-10-04
series: "Building the OS for Multi-Agent Development"
post: 247
pr: "TBD"
issue: "1925"
status: published
author: "synlynk team"
version: "0.25.0-dev"
tags: [posts, dispatch, security, docker]
type: story
---

## The broader goal at the end of the previous PR

Part 1 of gh:#1925 made Grok's permission bypass explicit. `--dangerously-skip-permissions` is no longer an implicit default, and `HARNESS_CAPABILITY_BASELINES` leaves `required_flags` empty. The worktree still isolated only git state. The harness process kept the host's network and filesystem.

## Strategic shifts in this PR

The decide panel (`dec-ff9a9005`) approved the design with two required changes, both folded into the spec before implementation. Bridge networking is not described as a network sandbox: the container can open outbound and LAN connections, which is how a harness reaches its model API. Domain-filtered egress stays in #1392 and #1393. A `GH_TOKEN` from the existing `--requires-gh-write` opt-in is inside the container and can be used over that network. The parity test must prove the fake `docker` ran. Matching logs alone would also pass a bug that ran `sh -c` on the host.

`docker/Dockerfile.sovereign` stays the local oMLX image. A Mac arm64 host binary cannot run inside a Linux container, so the harness CLI has to already be on `PATH` in the image the operator names.

## What this PR ships

`synlynk dispatch --container-image <ref>` is the switch. No image means the host subprocess, unchanged. No current harness gained a `container_image` baseline.

`synlynk/container_exec.py` rewrites the existing `sh -c` spawn into `docker run`. The worktree and, for a linked worktree, its git dir and common git dir are bind-mounted at the same absolute paths. The root is read-only, capabilities are dropped, the user is the operator's uid and gid, and `HOME` and `TMPDIR` are `/tmp`. `PATH`, `SHELL`, and `SSH_AUTH_SOCK` are not passed in. If `docker` is missing, or the client exits before the inner shell writes an exit file, the job fails. It does not fail over to a host harness.

`docker/Dockerfile.runner` is `debian:bookworm-slim` plus git, CA certificates, and `stub-harness`. CI builds it and does not push it.

## Tests

Twelve tests cover the argv contract, linked-worktree mounts, a broken git link, log and token parity through a fake `docker`, a missing `docker`, a dead client with no failover, and the CLI flag. A local `docker build` of the runner image ran `stub-harness` and wrote `stub-marker` in the mounted directory.

## On the way to autonomous dispatch

An untrusted harness can now be opted into a container without moving Claude, Codex, Agy, Grok, Muse, or local off the host. The plugin registry for OpenCode, Aider, and Goose is still a separate change.

## The new goalpost

The next trust slice is egress. Bridge mode is an open network. #1392 and #1393 are where a default-deny or domain-filtered network would live. This PR does not close them.
