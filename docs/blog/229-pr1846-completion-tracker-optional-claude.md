---
title: "Completion Tracking Without an Installed Claude CLI"
date: 2026-09-29
series: "Building the OS for Multi-Agent Development"
post: 229
issue: "#1846"
pr: "TBD"
author: "synlynk team"
version: "0.23.0-dev"
tags: [posts, reliability, testing]
type: pr
---
# Completion Tracking Without an Installed Claude CLI

The post-merge completion tracker asks the Claude CLI for a semantic verdict. That check is intentionally non-blocking, but the tracker still crashed when it ran on a GitHub Actions runner where the optional `claude` binary was not installed.

The tracker now treats a missing Claude executable like any other unavailable verdict input and returns `None`. The lifecycle nudge can continue, and a later scan can retry when the environment provides the dependency.

A regression test monkeypatches `subprocess.run` to raise `FileNotFoundError` for the Claude invocation and verifies that the tracker fails soft instead of propagating the exception.
