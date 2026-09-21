<!-- generated - source of truth is state.db -->
---
decision_id: dec-02d8709d
topic: "Cloudflare Tunnel as a full-duplex remote-access transport for synlynk Workspaces. Facts: cloudflared opens 4 outbound-only, post-quantum-encrypted connections to 2+ Cloudflare edge datacenters (port 7844) - no inbound ports ever opened on the origin. Quick Tunnels (trycloudflare.com) are zero-config, ephemeral, URL in ~3s, die with the process - good for previews/CI/agent workflows, not production. Named tunnels are 'remotely-managed': config (ingress rules, hostnames) stored on Cloudflare, managed via dashboard/API/Terraform (POST /accounts/{id}/cfd_tunnel), token-based - anyone holding the tunnel token can run it. Ingress rules route by hostname to local services; supports HTTP, WebSocket (http2Origin option), and raw TCP/L4 (e.g. SSH/RDP-style access), so genuinely full-duplex bidirectional streams are possible, not just request/response HTTP. Cloudflare Access sits in front as a Zero Trust auth layer, validates JWTs per-request, supports external identity providers including GitHub OAuth, and can gate access per-hostname/path with policies. Context: synlynk already has a W9 spec (hosted Vizor at synlynk.com/<product_slug>, GitHub OAuth, W4 member-token minting, a relay serving synced product state) and a W10 spec (Grok Bot phone client via remote MCP on that same relay), both blocked on W9 landing. Question for the panel: where does Cloudflare Tunnel actually fit in synlynk's remote-access strategy - as the literal transport underneath W9/W10's relay (tunneling the local daemon straight to a hostname instead of building a sync/relay layer), as a lower-risk interim/parallel path for local-workspace remote access before W9 ships, as a mechanism for something W9 doesn't cover (e.g. full-duplex live daemon control, SSH-style access to a specific worktree, exposing a local dispatch job's live output), or as the wrong tool entirely given synlynk's existing GitHub-App-based identity model? Give a concrete recommended approach, not just tradeoffs."
date: 2026-09-20
panel: [claude, codex]
status: approved
---

## Topic
Cloudflare Tunnel as a full-duplex remote-access transport for synlynk Workspaces. Facts: cloudflared opens 4 outbound-only, post-quantum-encrypted connections to 2+ Cloudflare edge datacenters (port 7844) - no inbound ports ever opened on the origin. Quick Tunnels (trycloudflare.com) are zero-config, ephemeral, URL in ~3s, die with the process - good for previews/CI/agent workflows, not production. Named tunnels are 'remotely-managed': config (ingress rules, hostnames) stored on Cloudflare, managed via dashboard/API/Terraform (POST /accounts/{id}/cfd_tunnel), token-based - anyone holding the tunnel token can run it. Ingress rules route by hostname to local services; supports HTTP, WebSocket (http2Origin option), and raw TCP/L4 (e.g. SSH/RDP-style access), so genuinely full-duplex bidirectional streams are possible, not just request/response HTTP. Cloudflare Access sits in front as a Zero Trust auth layer, validates JWTs per-request, supports external identity providers including GitHub OAuth, and can gate access per-hostname/path with policies. Context: synlynk already has a W9 spec (hosted Vizor at synlynk.com/<product_slug>, GitHub OAuth, W4 member-token minting, a relay serving synced product state) and a W10 spec (Grok Bot phone client via remote MCP on that same relay), both blocked on W9 landing. Question for the panel: where does Cloudflare Tunnel actually fit in synlynk's remote-access strategy - as the literal transport underneath W9/W10's relay (tunneling the local daemon straight to a hostname instead of building a sync/relay layer), as a lower-risk interim/parallel path for local-workspace remote access before W9 ships, as a mechanism for something W9 doesn't cover (e.g. full-duplex live daemon control, SSH-style access to a specific worktree, exposing a local dispatch job's live output), or as the wrong tool entirely given synlynk's existing GitHub-App-based identity model? Give a concrete recommended approach, not just tradeoffs.

## Panel Inputs

### claude
[model=default; version=2.1.274 (Claude Code)]

**Position: Cloudflare Tunnel should not be the transport under W9/W10. It should ship as a separate, opt-in "direct-to-my-machine" lane for live daemon access, which W9 doesn't cover.**

**Why not the W9/W10 relay transport**
- W9's core value is synced product state that stays reachable when the laptop is closed. A tunnel only works while the origin is online, so it can't replace the relay for a phone client like W10.
- The tunnel token is a bearer secret. Hosted Team/Enterprise would need per-member tunnels, or synlynk-owned tunnels to every user's machine. That means secret distribution, Cloudflare account and ToS exposure, and a hard vendor dependency on the critical path.
- Cloudflare Access identifies a GitHub *user*. synlynk's model is a GitHub App plus W4 member tokens. These would be two parallel authorization systems unless they are explicitly bridged.

**Where it does fit**
Three things W9 doesn't cover are natural tunnel workloads:
1. Live job output streaming (WebSocket or SSE from the local daemon).
2. Full-duplex daemon control.
3. Shell access to a specific worktree, through TCP ingress.

These are inherently machine-local and real-time. Syncing them through a relay would be the wrong shape.

**Concrete approach**
1. Add `synlynk tunnel up`, opt-in, and bring-your-own Cloudflare account. It creates a named tunnel via the API and one hostname per project. Nothing changes for users who never run it.
2. Put Cloudflare Access in front with the GitHub IdP. The daemon validates `Cf-Access-Jwt-Assertion` itself and checks the GitHub login against the project's member list. Bridging Access identity to the existing identity model in the daemon avoids a second one.
3. Phase 1 is read-only: `synlynk viz` plus job log streaming. This works as an interim remote view before W9 lands, with no relay dependency.
4. Phase 2 is dispatch or shell, and only after W4 token scopes exist to gate it. Exposing agent dispatch is effectively remote code execution, so it needs per-action authorization, not just "authenticated via Access."
5. Use Quick Tunnels only for unauthenticated ephemeral previews, such as CI or demo Vizor. Never expose the daemon that way, because the URL would be the only secret.

**Sequencing**
The tunnel lane is not on W9's critical path. It can start now, and W9 and W10 stay unblocked and unchanged. Later, W9's relay could optionally treat a live tunnel as a "hot path" for real-time data when the machine is online, but that's an optimization, not a dependency.

**Bottom line:** Use Cloudflare Tunnel for live, machine-local, full-duplex access, read-only first, with Access JWTs bridged to member tokens. Don't use it as the sync or relay layer, and don't let it replace W9.

### codex
[model=default; version=codex-cli 0.154.0]

Cloudflare Tunnel should be treated as a transport primitive, not as a replacement for synlynk’s W9 relay or identity model. It solves secure reachability: a local daemon can publish HTTP, WebSocket, or raw TCP services without inbound firewall exposure. W9 solves a broader product problem: hosted Vizor, synchronized product state, GitHub OAuth, member-token minting, and multi-user access. A tunnel alone provides none of that state, tenancy, lifecycle, or audit model.

Using Tunnel literally underneath W9/W10 would therefore be the wrong architecture. It would couple the hosted relay to an individual operator’s local process, complicate availability and scaling, and risk making Cloudflare tunnel tokens an implicit synlynk credential. W10’s remote MCP client should continue to target the W9 relay, where GitHub-App identity and W4-style member tokens can authorize actions consistently.

The strongest fit is a lower-risk parallel path for “reach my live workspace” workflows while W9 remains blocked: named tunnels for durable, explicitly provisioned workspaces; Quick Tunnels for previews, CI, and ephemeral agent sessions. A thin synlynk-side broker or CLI could provision a tunnel, register its hostname and capabilities, and place Cloudflare Access in front. Access can use GitHub OAuth for coarse admission, while synlynk still performs fine-grained authorization and workspace/job scoping. Never treat possession of a tunnel token as user identity.

This also covers capabilities W9 does not need to expose publicly: a full-duplex daemon-control WebSocket, SSH-style access to one worktree, or live output from a dispatch job. Those should be opt-in, short-lived, auditable sessions, ideally with per-session hostnames or routes and automatic teardown.

My recommendation is to adopt Cloudflare Tunnel as an experimental/parallel remote-workspace transport, not as W9/W10’s foundational relay. Ship it first for privileged developer and agent workflows, with Access plus synlynk authorization layered above it; keep W9 as the canonical shared state, identity, and MCP control plane.

## Synthesis
## Synthesis

**Where the panel agrees**
- Cloudflare Tunnel is not the transport under the W9/W10 relay.
  - A tunnel only works while the origin machine is online. W10's phone client and W9's hosted Vizor need synced state that survives a closed laptop.
  - A tunnel token is a bearer secret. Making it an implicit synlynk credential would create a second identity system next to the GitHub App and W4 member tokens.
  - It would also put a vendor dependency on W9's critical path.
- It is the right tool for machine-local, real-time, full-duplex workloads that W9 doesn't cover: live job output, daemon control over WebSocket, and shell access to one worktree.
- It ships as an opt-in, bring-your-own-Cloudflare-account lane. W9 and W10 stay unblocked and unchanged.
- Cloudflare Access with GitHub OAuth is only coarse admission. Fine-grained authorization stays inside synlynk.
- Quick Tunnels are for ephemeral previews and CI only, never for the daemon, because the URL would be the only secret.

**Where they differ, and how I resolved it**
- Claude proposed a specific staging: read-only first, then dispatch or shell only after W4 scopes exist. Codex proposed short-lived, per-session, auditable routes with automatic teardown. These are compatible.
  - Adopt both: read-only comes first, and any write or exec capability uses short-lived per-session routes.
- Claude put the JWT check in the daemon, bridging the Access identity to the project member list. Codex framed the enforcement point as a thin synlynk-side broker. These come to the same thing.
  - Adopt the daemon-side check for v1. Don't add a broker until there is a second consumer.

**Sequencing**
1. Write a spec first, per the brainstorm-first policy. It should cover `synlynk tunnel up`, hostname-per-project, the Access JWT validation contract, and a threat model.
2. Phase 1 is read-only: `synlynk viz` and job log streaming. This doubles as an interim remote view before W9 lands.
3. Phase 2 is dispatch and shell access. It is gated on W4 token scopes and per-action authorization, because exposing dispatch is effectively remote code execution.
4. Later, W9's relay may optionally use a live tunnel as a hot path for real-time data. That is an optimization, not a dependency.

Decision: Adopt Cloudflare Tunnel as an opt-in, bring-your-own-account `synlynk tunnel` lane for live, machine-local, full-duplex access to the local daemon. That means job output streaming first, then daemon control and worktree shell access. Cloudflare Access (GitHub IdP) provides coarse admission, and the daemon validates the `Cf-Access-Jwt-Assertion` and maps the GitHub login to the project member list. It ships read-only first, and write or exec capabilities wait for W4 token scopes and use short-lived, auditable, per-session routes. It will not be the transport under the W9/W10 relay, will not replace W9's sync, identity, or MCP control plane, and will not use Quick Tunnels for the daemon. The next step is a design spec in `docs/superpowers/specs/` for Nikhil's sign-off before any implementation is dispatched.

## Decision
Decision: Adopt Cloudflare Tunnel as an opt-in, bring-your-own-account `synlynk tunnel` lane for live, machine-local, full-duplex access to the local daemon. That means job output streaming first, then daemon control and worktree shell access. Cloudflare Access (GitHub IdP) provides coarse admission, and the daemon validates the `Cf-Access-Jwt-Assertion` and maps the GitHub login to the project member list. It ships read-only first, and write or exec capabilities wait for W4 token scopes and use short-lived, auditable, per-session routes. It will not be the transport under the W9/W10 relay, will not replace W9's sync, identity, or MCP control plane, and will not use Quick Tunnels for the daemon. The next step is a design spec in `docs/superpowers/specs/` for Nikhil's sign-off before any implementation is dispatched.

> Signatures: see 2026-09-20-cloudflare-tunnel-as-a-full-duplex-remot.json
