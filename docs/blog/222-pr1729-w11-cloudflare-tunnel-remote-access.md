---
title: "PR #1729 — W11: Cloudflare Tunnel remote access"
date: 2026-09-21
series: "Building the OS for Multi-Agent Development"
post: 222
pr: "#1729"
status: open
author: "synlynk team"
version: "0.20.0"
tags: [posts]
type: pr
---

# W11 — What a Tunnel Is For, and What It Isn't

**PR:** [#1729](https://github.com/nikhilsoman/synlynk/pull/1729)
**Date:** 2026-09-21

## Where things stood

W10 had just landed as a spec: Grok Bot as a phone-native conversational client on top of W9's hosted-Vizor relay. Both W9 and W10 share one property — they're designed to work whether or not any machine is actually turned on, because they're backed by synced state, not a live connection to a laptop.

## What moved the goalpost

That same property is also a gap: neither W9 nor W10 can show you a dispatch job's output *as it streams*, or give you a real-time control channel to a daemon that's running right now. That's a genuinely different problem — full-duplex, machine-local, only meaningful while the origin is up — and it's the one Cloudflare Tunnel was explored against. Rather than brainstorm straight into a design, this one went through `synlynk decide` first: a two-member panel (Claude, Codex — Agy hit a headless permission denial, Grok's usage balance was exhausted) converged independently on the same shape, which made the follow-on brainstorm fast.

## What this PR ships

`docs/superpowers/specs/2026-09-21-cloudflare-tunnel-remote-access-design.md` (W11), plus the `synlynk decide` record it was built from. It locks:

- **Cloudflare Tunnel is not the transport under W9/W10.** A tunnel only exists while the origin is online, and its token is a bearer secret that would create a second identity system next to the GitHub App/W4 tokens synlynk already has. It's a separate, opt-in `synlynk tunnel` lane instead.
- **Workspace members, not solo-only** — Cloudflare Access + GitHub OAuth is coarse admission; the daemon independently maps the authenticated login to the W4 member roster before serving anything.
- **Named tunnels only.** Quick Tunnels are explicitly ruled out for the daemon — an ephemeral URL with no Access layer in front would be the only secret.
- **Phase 1 (this spec's build target): read-only** — `synlynk viz` and job-log streaming over the tunnel, enforced structurally (a read-only router on the tunnel-facing listener, not a convention). Doubles as an interim remote-access story before W9 ships.
- **Phase 2 (designed now, built later): dispatch and shell access**, explicitly scoped as remote code execution — grant-gated (not just roster-gated), short-lived per-session routes minted the same way W4 mints installation tokens, worktree-scoped shell sessions, fully attributed in the audit trail. Implementation waits on W4's write-scope grants; the authorization contract doesn't.

No visuals were used — the questions (transport boundary, audience, phasing) were architectural, not visual.

## Where this leaves the long arc

The remote-access strategy now has three distinct, non-overlapping surfaces instead of one generic "remote access" bucket: W9 (always-on hosted view), W10 (phone-native conversational client on that same relay), and W11 (live full-duplex access to a running machine). Each has a reason to exist that the others don't cover, and none of them quietly duplicates another's auth or sync work.

## New goalpost

W11 is unblocked — Phase 1 can move to `writing-plans` independently of W9's timeline. Phase 2 stays architecture-only until W4 defines write-scope grants, at which point this spec is the contract, not a re-brainstorm.
