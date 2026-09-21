# W12 — A Channel Is a Pane

**PR:** [#1731](https://github.com/nikhilsoman/synlynk/pull/1731)
**Date:** 2026-09-22

## Where things stood

W9, W10, and W11 had just staked out three non-overlapping remote-access surfaces: an always-on hosted relay, a phone-native conversational client on top of it, and an opt-in tunnel for live, machine-local, full-duplex access to a running daemon. Between them they covered "always available" and "live control of a machine" — but nothing yet covered "sit inside one specific running agent session, from a phone, in a chat app people already have open all day."

## What moved the goalpost

That gap is what Discord was explored against. Unlike W11's dispatch/shell phase, injecting a prompt into an already-running, already-authorized Herdr session isn't a privilege escalation — the session's own permissions already gate what it can do. That let this spec skip W11's read-only-first phasing and design full duplex as the v1 target directly: a Discord channel that mirrors one live Herdr pane, both directions, from day one.

## What this PR ships

`docs/superpowers/specs/2026-09-22-discord-herdr-bridge-design.md` (W12). It locks:

- **One synlynk-managed Discord server, one channel per live Herdr session** — not per-workspace-forever. A channel is created when a member first bridges a pane and archived when that pane closes; the channel's lifecycle mirrors the pane's own lifecycle rather than an independent policy.
- **Full duplex from day one.** Typing in the channel injects a new prompt/turn into the running pane, exactly as if a human were steering that session directly — not raw stdin, not slash-commands-only.
- **Herdr's pane API for v1, behind a small abstracted interface** (`inject(session_id, text)` / `stream(session_id) -> events`). This is Approach C from three considered: build directly against Herdr now, but leave a documented seam so a non-Herdr backend is a future swap rather than a rewrite — cheaper than building a decoupled synlynk-native primitive today, without permanently welding the design to Herdr.
- **Workspace-member-scoped access.** A Discord account must be linked to a W4 member via a `/link` flow before it can see or use any session's channel — Discord's own guild membership is coarse admission, never the real gate, the same trust-boundary discipline as W10's policy.json and W11's daemon-side JWT check. The linking pattern itself isn't new: W4 §2 already allows non-GitHub IdPs to "alias the same member," so Discord slots into an existing seam rather than requiring a new grant type.
- **Throttling designed against real constraints**, not assumed ones: research surfaced that Discord's gateway rate limit (120 commands/60s) governs commands like heartbeats, not message posting — the actual binding constraint for streaming Herdr output is the REST API's 5-messages-per-5-seconds-per-channel limit and the 4096-byte message cap, so the spec calls for coalescing/batching pane output rather than naive line-by-line posting.

No visuals were used — every open question (duplex semantics, bridge mechanism, access model, phasing) was a text/architectural choice, not a visual one.

## Where this leaves the long arc

The remote-access strategy now has four distinct surfaces, each answering a question the others structurally can't: W9 (always-on hosted view), W10 (phone-native conversational client on that relay), W11 (live full-duplex access to a running machine), and W12 (live full-duplex access to one specific running agent session, from a chat app). None of them quietly duplicates another's auth or sync work — the same discipline that shaped W9→W10 and W9/W10→W11 held here too.

## New goalpost

W12 is unblocked — it depends only on W4 (already specced) and Herdr's existing pane API (already in production use), so it can move to `writing-plans` independently of W9/W10/W11's timelines. The four-surface remote-access map is now complete at the design level; the next arc is deciding build order across W10/W11/W12's implementation plans.
