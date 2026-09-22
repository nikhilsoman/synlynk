# Workspace identity W11 — Cloudflare Tunnel full-duplex remote access

**Date:** 2026-09-21
**Status:** Approved in chat 2026-09-21 (Nikhil): workspace-member scope (not solo-only); Phase 2 architecture designed now, implementation deferred to W4 write-scopes. Implementation is **out of scope** until this spec is on `main` and a plan exists.
**Issue:** [#1728](https://github.com/nikhilsoman/synlynk/issues/1728)
**Depends on:** [W4 — Members & dispatch](2026-09-17-workspace-identity-w4-members-dispatch-design.md) (member roster, grants, token minting — Phase 2 only), [W1 — Install & secrets](2026-09-16-workspace-identity-w1-install-secrets-design.md) (PEM-less members, connector-secret handling pattern)
**Related, not a dependency:** [W9 — Hosted Vizor](2026-09-17-workspace-identity-w9-hosted-vizor-design.md), [W10 — Grok Bot remote MCP surface](2026-09-20-grok-bot-remote-mcp-design.md)
**Decision record:** [`project-docs/decisions/2026-09-20-cloudflare-tunnel-as-a-full-duplex-remot.md`](../../../project-docs/decisions/2026-09-20-cloudflare-tunnel-as-a-full-duplex-remot.md) (`synlynk decide`, panel: claude, codex)
**Author:** Nikhil Soman (brainstorm with Claude, Home Conductor)

---

## 1. Problem

W9 gives a workspace a hosted, always-available view (`synlynk.com/<product_slug>`) backed by synced state — it works whether or not any machine is on. W10 puts a phone-native conversational client on top of that same relay. Neither covers a different, real need: **live, machine-local, full-duplex access to a daemon that is actually running right now** — streaming a dispatch job's output as it happens, opening a real-time control channel to the daemon, or getting a shell into a specific worktree. That only exists while the machine is up, which is exactly what W9/W10 are designed *not* to depend on.

Cloudflare Tunnel (`cloudflared`) was explored as a candidate transport for this: outbound-only, no inbound firewall ports, WebSocket and raw TCP support (genuinely full-duplex, not just request/response HTTP), and Cloudflare Access as a Zero Trust layer in front with GitHub OAuth support. The `synlynk decide` panel (2026-09-20, Claude + Codex; Agy and Grok were unavailable that run) converged on where it fits — this spec formalizes that decision into a buildable design.

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Role | An **opt-in, bring-your-own-Cloudflare-account** `synlynk tunnel` lane for live machine-local access. Not the transport under W9/W10's relay |
| Why not under W9/W10 | A tunnel only exists while the origin is online; W9/W10 need state that survives a closed laptop. A tunnel token is a bearer secret — treating it as an implicit synlynk credential would create a second identity system next to the GitHub App/W4 tokens |
| v1 audience | **Workspace members (W4)**, not solo-only. Cloudflare Access + GitHub OAuth is coarse admission; the daemon maps the authenticated GitHub login to the W4 member roster for actual authorization |
| Tunnel type | Named (remotely-managed) tunnel only. **Quick Tunnels are never used for the daemon** — the ephemeral URL would be the only secret, with no Access layer in front of it |
| Phasing | **Phase 1 (this spec's implementation target): read-only.** `synlynk viz` and job-log streaming over the tunnel. **Phase 2 (designed here, built later): dispatch and shell access**, gated on W4 write-scopes that don't fully exist yet |
| Enforcement | Cloudflare Access validates the `Cf-Access-Jwt-Assertion` at the edge (coarse gate: is this a known GitHub identity at all). The **daemon** independently validates that JWT and maps the login to a W4 member + grant before serving any route. Access is never the sole gate |
| Relationship to W9 | None required. W9's relay **may later** use a live tunnel as an optional real-time hot path — that is a future optimization, never a dependency in either direction |

## 3. Architecture

```
Phone / browser
      │  HTTPS/WSS
      ▼
Cloudflare Access (GitHub OAuth app, JWT issuance)
      │  Cf-Access-Jwt-Assertion header
      ▼
Cloudflare edge (named tunnel, hostname-per-product: <product_slug>.tunnel.synlynk.com)
      │  outbound-only cloudflared connection (4x, 2+ datacenters, port 7844)
      ▼
cloudflared (runs alongside the synlynk daemon on the member's/operator's machine)
      │  loopback
      ▼
synlynk daemon — validates JWT, maps login → W4 member + grant, serves route
```

- **Hostname per product**, not per member: `<product_slug>.tunnel.synlynk.com`. Ingress rules route to the local daemon's existing HTTP/WS surface (the one `synlynk viz` already serves on loopback — this exposes it, it does not duplicate it).
- **Tunnel credentials** (the tunnel token) are treated like any other connector secret per W1's pattern: never committed, never handed to a member, held only by whoever runs `synlynk tunnel up` (the machine's operator). A member gets *access through* the tunnel via Cloudflare Access + their GitHub identity; they never see the tunnel token itself.
- **cloudflared is a sidecar process**, started/stopped by `synlynk tunnel up|down|status`, not folded into the daemon binary. If `cloudflared` is absent or the tunnel is down, the daemon's loopback behavior (`synlynk viz` locally) is entirely unaffected — this is strictly additive.

## 4. Phase 1 — read-only (implementation target of this spec's plan)

Scope: `synlynk viz` (organigram/board/jobs, same as loopback) and job-log streaming (`job_get`-style live tail), served over the tunnel to any authenticated W4 member.

- Daemon adds a middleware: extract `Cf-Access-Jwt-Assertion`, verify against Cloudflare's published JWKS for the Access application, extract the GitHub login claim, look up that login in the product's W4 member roster. No match → 403, same fail-closed behavior as W9's hosted Vizor.
- No write routes are mounted in Phase 1. This is enforced at the route-registration level (a read-only router is mounted on the tunnel-facing listener), not by convention — the same class of mistake W9 explicitly guards against ("hosted read-only executive dashboard" is forbidden there because it's a silent feature drop; here the read-only restriction is the opposite — a deliberate, structural limit, not an oversight).
- This phase also functions as an **interim remote-access story before W9 ships**, for anyone who wants live visibility into a running workspace today.

## 5. Phase 2 — dispatch and shell access (designed now, built after W4 write-scopes land)

Scope: triggering a dispatch job and opening a shell into a specific worktree, both from the tunnel-facing surface. This is explicitly remote code execution, so the authorization contract is designed now while Phase 1's plumbing is fresh, even though nothing here is implemented until W4 defines write-scoped grants.

- **Grant-gated, not roster-gated.** Phase 1's "is this login a W4 member" check is necessary but not sufficient for Phase 2 — the member must additionally hold a specific grant (e.g. a `tunnel_dispatch` or `tunnel_shell` grant, following W4 §2's existing grant model) before the daemon serves a write route.
- **Short-lived, per-session, auditable routes.** Each dispatch or shell session mints a scoped, time-bounded route/token at request time (matching W4's "minter returns installation token for that type" pattern, not a standing credential) and tears it down when the session ends or after an idle timeout — no long-lived exec channel sits open.
- **Shell access is worktree-scoped**, not machine-scoped: a session binds to one worktree path at mint time and cannot be redirected to another without a fresh grant check.
- **Every action is attributed and logged** the same way a `synlynk dispatch` invocation is today (telemetry, not a silent side channel) — a tunnel-originated dispatch is indistinguishable in the audit trail from a CLI-originated one, just tagged with its origin.
- Non-goal of Phase 2 as designed here: it does not define the W4 grant schema itself (that's W4's own surface to extend) — it only specifies what the tunnel-facing daemon requires from that schema once it exists.

## 6. Non-goals

- Building `synlynk tunnel up/down/status`, the JWT-validation middleware, or any route — that's the plan, not this doc.
- Defining the W4 grant schema for `tunnel_dispatch`/`tunnel_shell` — Phase 2 only specifies the contract it needs; the schema itself belongs to W4.
- Using Cloudflare Tunnel as a replacement for W9's sync/relay/MCP control plane, or as the transport under it.
- Quick Tunnels for anything other than possible future CI/preview use — never for the daemon.
- Team/Enterprise billing or Cloudflare-account provisioning tooling — bring-your-own-account is a v1 assumption, not something synlynk manages for the user.

## 7. Sequencing

Unlike W10, **W11 is not blocked on W9.** Phase 1 can be planned and built independently, and doubles as an interim capability while W9 is still in progress. Phase 2 remains architecture-only until W4's write-scope grants exist, at which point it moves to `writing-plans` without further brainstorming — this spec is the design contract for that later work.
