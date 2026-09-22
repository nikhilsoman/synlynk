# Workspace identity W12 — Discord/Herdr full-duplex remote-access bridge

**Date:** 2026-09-22
**Status:** Approved in chat 2026-09-22 (Nikhil): full duplex is the v1 target (not phased read-only-first like W11); bridge mechanism is Herdr's pane API for v1 behind a small abstracted interface; access is workspace-member scoped via Discord-account linking to W4. Implementation is **out of scope** until this spec is on `main` and a plan exists.
**Issue:** [#1730](https://github.com/nikhilsoman/synlynk/issues/1730)
**Depends on:** [W4 — Members & dispatch](2026-09-17-workspace-identity-w4-members-dispatch-design.md) (member roster; §2 explicitly allows non-GitHub IdPs to "alias the same member," which is the pattern Discord linking uses)
**Related, not a dependency:** [W9 — Hosted Vizor](2026-09-17-workspace-identity-w9-hosted-vizor-design.md), [W10 — Grok Bot remote MCP surface](2026-09-20-grok-bot-remote-mcp-design.md), [W11 — Cloudflare Tunnel remote access](2026-09-21-cloudflare-tunnel-remote-access-design.md)
**External research:** Discord Gateway (WebSocket, bidirectional event stream, 120 gateway-commands/60s — applies to commands like heartbeat/presence, not message posting), Discord REST API (channel/message CRUD, 5 messages/5s per-channel rate limit, 4096-byte message cap), `MESSAGE_CONTENT` privileged intent (required to read message bodies outside DMs/mentions)
**Author:** Nikhil Soman (brainstorm with Claude, Home Conductor)

---

## 1. Problem

synlynk's remote-access surfaces so far are: W9 (always-on hosted relay, works with no machine online), W10 (Grok Bot as a phone-native conversational client of that same relay), and W11 (an opt-in tunnel for live, machine-local, full-duplex access to a running daemon). None of them give a mobile-first, chat-native way to sit inside a **specific live Herdr agent session** — steering it and reading its output from a phone, the way you'd watch and nudge a teammate's terminal from Slack.

Discord is a strong fit for that: free, mobile-native, already has a bidirectional Gateway/REST API, and per-channel scoping maps naturally onto per-session scoping. This spec designs that bridge: a synlynk-managed Discord server with one channel per live Herdr session, full-duplex from day one — the same recurring trust-boundary question as W10/W11 applies (Discord's own membership is never the real authorization gate).

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Duplex semantics | A message typed in the channel is delivered to the running Herdr pane **as a new prompt/turn** — the same as a human steering that session directly — not raw stdin, not restricted to slash commands only |
| Bridge mechanism | Built against **Herdr's own pane API** (`herdr pane run <pane-id> "<text>"` to inject; a pane output/log tail to stream) for v1, behind a small internal interface (`inject(session_id, text)` / `stream(session_id) -> events`) so a non-Herdr backend is a future swap, not a rewrite |
| Access model | **Workspace members only.** A Discord account must be linked to a W4 member before it can see or use any session's channel — Discord's own guild membership is coarse admission, never the real gate, exactly as Cloudflare Access is coarse admission in W11 |
| Channel scope & lifecycle | **One channel per live session** (not per-workspace-forever): created when a member first bridges a given Herdr pane, archived when that pane closes. The channel's lifecycle mirrors the pane's, not an independent policy |
| Phasing | **Full duplex is the v1 target**, not phased like W11. Rationale: injecting a prompt into an already-running, already-authorized Herdr session is not a privilege escalation — the session's own permissions already gate what it can do. There is no equivalent of W11's "dispatch = RCE" risk here |
| Relationship to W9/W10/W11 | None required in either direction. A fourth, independent remote-access surface — same "compose only where it structurally helps" principle already established between W9 and W10 |

## 3. Architecture

```
Discord mobile/desktop client
      │  native Discord protocol — no synlynk-specific mobile work needed
      ▼
Discord Gateway (WebSocket) ──MESSAGE_CREATE events──┐
Discord REST API ◄──message posting, channel mgmt────┤
      │                                              │
      ▼                                              │
synlynk Discord Bot process (new component)          │
  - Gateway listener: filters to the synlynk-managed  │
    guild, resolves channel -> session_id             │
  - Link-check: Discord user ID -> W4 member,          │
    fail-closed on no match                           │
  - REST poster: chunks (<=4096 bytes) and throttles   │
    output to the 5 msg/5s per-channel budget          │
      │                                              │
      ▼                                              │
Bridge interface (new, small, backend-agnostic):      │
  inject(session_id, text)                            │
  stream(session_id) -> async iterator of output events│
      │                                              │
      ▼                                              │
Herdr adapter (v1 implementation of the interface)    │
  - inject -> `herdr pane run <pane-id> "<text>"`      │
  - stream -> tail Herdr's pane output/log             │
```

- **One synlynk-managed Discord server (guild)**, not one guild per product — channels are the per-session unit, the guild is the shared container. Matches "preferably by running a Synlynk Discord server" from the original ask.
- **Discord-account linking** reuses W4's aliasing pattern (§2 of the W4 spec: non-GitHub IdPs "alias the same member," not a second roster): a `/link` slash command has the bot DM a short-lived code, which the member redeems via the existing GitHub-OAuth-backed web flow. An unlinked Discord account cannot see or use any workspace channel — Discord permissions on the guild are set to hide session channels from anyone without the linked role, and the bot's own authorization check is the enforced gate, not the Discord permission alone (defense in depth, same posture as W11's Cloudflare Access + daemon double-check).
- **Throttling**: Herdr pane output is coalesced into ≤4096-byte messages and rate-limited to the channel's 5-messages-per-5-seconds budget. Bursty output (e.g. a long build log) is batched rather than streamed line-by-line; output that would exceed a reasonable per-minute volume is truncated with a pointer to `synlynk logs` for the full record, rather than silently dropped or spamming the channel into the rate limit.
- **cloudflared/W11 parallel, not integration**: the bot process runs wherever the Herdr session runs (the operator's machine), the same "additive sidecar, not folded into the daemon binary" posture W11 established for `cloudflared`.

## 4. Cross-device usability contract

Discord supplies the client layout, but the bridge still needs an explicit
contract so mobile convenience does not turn into a second product surface and
desktop density does not become a requirement for basic operation.

- **One information architecture:** the session channel, message ordering,
  prompt semantics, link state, and authorization result are identical on
  mobile and desktop. A user can open a channel on one device and continue on
  the other without a mode switch or a different command vocabulary.
- **Mobile is the baseline flow:** a linked member must be able to select one
  live session, read the latest output, type a prompt, and see the result using
  a single channel view and the normal Discord composer. No action may depend
  on hover, right-click, drag-and-drop, a wide table, or simultaneous panes.
  Session names and the first line of status messages must remain recognizable
  when Discord truncates or wraps them on a narrow screen.
- **Desktop is progressive enhancement:** desktop users may keep the channel
  list visible, use Discord's split-pane behavior, or monitor multiple session
  channels, but those are navigation conveniences rather than additional
  bridge capabilities. Every action available in a desktop arrangement must
  remain available from the single-channel mobile flow.
- **Output is readable in both arrangements:** bridge messages use short,
  labelled chunks with stable session attribution; long output is summarized
  and linked to `synlynk logs` rather than relying on horizontal scrolling or
  an always-visible desktop-only transcript panel. Code/log formatting must
  degrade to ordinary wrapped text on mobile.
- **Responsive acceptance checks:** at narrow width, the primary path is
  `session -> latest output -> prompt -> acknowledgement`; at wide width, a
  user may add parallel channel monitoring without changing that path. A
  channel deep link, a reconnect, and a permission failure must produce the
  same visible state and next step on both device classes.

This resolves the mobile/desktop conflict by making mobile task completion the
compatibility floor and desktop parallelism an optional client enhancement. It
does not require synlynk to ship a custom responsive Discord UI.

## 5. Non-goals

- Building the bot process, the `/link` flow, the Herdr adapter, or the bridge interface's concrete code — that is the plan, not this spec.
- A Discord-hosted equivalent of `synlynk viz`'s board/organigram view. Channels are session-scoped chat, not a dashboard; anyone wanting the board view still uses `synlynk viz` or (once shipped) W9's hosted Vizor.
- Voice channels, threads-per-subtask, or any Discord feature beyond text channels + slash commands — YAGNI until a concrete need appears.
- Multi-guild or per-product-guild support — one shared synlynk guild is the v1 assumption.
- Replacing or depending on W9, W10, or W11 in either direction.
- Defining a new grant type in W4's schema — linking a Discord account to an existing W4 member is an identity alias, not a new permission; no new grant is introduced by this spec.

## 6. Sequencing

Not blocked on W9, W10, or W11 — it depends only on W4 (member roster, already specced) and Herdr's existing pane API (already documented and in use per CLAUDE.md's Herdr Workspace Protocol). Can move to `writing-plans` independently of the other three specs' timelines.
