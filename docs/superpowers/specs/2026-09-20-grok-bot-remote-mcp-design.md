# Grok Bot remote MCP surface (W10)

**Date:** 2026-09-20
**Status:** Approved in chat 2026-09-20 (Nikhil). **Blocked on W9** — implementation does not start until W9 (hosted Vizor) is on `main` and its own plan exists. This spec exists so W10 can be picked up immediately once that dependency clears.
**Depends on:** [W9 — Hosted Vizor](2026-09-17-workspace-identity-w9-hosted-vizor-design.md) (relay, GitHub OAuth, W4 member-token minting), [W4 — Members & dispatch](2026-09-17-workspace-identity-w4-members-dispatch-design.md)
**Author:** Nikhil Soman (brainstorm with Claude, Home Conductor)

---

## 1. Problem

Grok Bot (xAI/Cursor, beta) is a persistent cloud agent reachable from a phone, and its only integration path into a third-party system is a **remote MCP connector** — it cannot reach a local/loopback MCP server. That constraint decides the shape of this spec: any synlynk integration has to be hosted, not something that runs on Nikhil's laptop.

W9 already commits to standing up a hosted relay (`synlynk.com/<product_slug>`) with GitHub OAuth and W4 member-token minting, serving the same product state Vizor uses locally. W10 is the plan to expose a **remote MCP endpoint** on that same relay, so Grok Bot becomes a conversational, phone-native front end to a synlynk Workspace — a second consumer of W9's infrastructure, not a parallel remote-access stack.

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| Transport | Remote MCP endpoint at `synlynk.com/<product_slug>/mcp`, hosted on the W9 relay — no new backend service |
| Auth | Same GitHub OAuth + W4 member-token minting as hosted Vizor. Grok Bot's connector auth flow maps to a W4 member exactly as a browser session does |
| Authority | The MCP layer is a thin transport. Every write tool call is enforced by the **same** `policy.json`/`merge_authority` gates as the CLI — Grok Bot is just another caller, never a bypass |
| Scope of this spec | Approach A only (the MCP surface itself). **Approach B (a Marketplace "Bot" template bundling instructions/skills/routines on top of this MCP surface) is planned but explicitly out of scope here** — a follow-on spec once A ships |
| Local path | None. Grok Bot cannot reach loopback MCP, so this is hosted-only by construction; solo/local-only workspaces are unaffected |

## 3. Tool surface (v1)

A deliberately small set, each mapped 1:1 to something hosted Vizor already does server-side — nothing gets a capability Vizor doesn't already expose:

| Tool | Kind | Maps to |
|:---|:---|:---|
| `status` | read | Fleet/job/PR status summary |
| `jobs_list` / `job_get` | read | Dispatch history + detail |
| `pr_check` | read | A PR's review/merge-gate state |
| `dispatch` | write | Trigger a dispatch job |
| `decide` | write | Approve/merge/reject at a gate |

## 4. Trust boundary (open decision, deferred to rollout)

Grok Bot's own permission model is prompt-based — natural-language rules plus a review agent, not code-enforced. It **cannot** be relied on as the real gate; §2's "Authority" row is the locked constraint (`policy.json` is always the actual gate, regardless of what Grok Bot's reviewer allows).

What's left open, to decide at rollout rather than in this design: whether `dispatch`/`decide` ship enabled from day one, or the surface starts read-only (`status`/`jobs_list`/`job_get`/`pr_check` only) with writes flipped on later via a workspace-level feature flag once there's real-world confidence. Recommendation: ship with the flag present and defaulted **off** for writes, so the plumbing exists but blast radius stays operator-controlled while the integration is new.

## 5. Auth and tenancy detail

- Grok Bot's Custom Connector auth flow completes GitHub OAuth the same way a hosted Vizor browser session does; the relay maps the resulting identity to a W4 member of that `product_slug`.
- No membership → the MCP endpoint refuses the tool call, same fail-closed behavior as hosted Vizor's 404/403 on an unmapped identity.
- No PEM or connector `secret` material is ever sent to Grok Bot. Write tools use W4 token minting (the same approach hosted Vizor uses), not exporting credentials.

## 6. Non-goals (this spec)

- Implementing the MCP endpoint, tool handlers, or feature flag — that's the plan, not this doc.
- The Marketplace Bot template (Approach B) — follow-on spec once A ships.
- Any local/loopback MCP path.
- Resolving the §4 read/write rollout question — deferred to rollout, not locked here.

## 7. Sequencing

W10 cannot start until:
1. W9 (hosted Vizor: relay, GitHub OAuth, synced product state) is on `main`, and
2. W9 has its own implementation plan (per W9's own "implementation out of scope until plan exists" gate).

Once both clear, this spec is ready to move straight to `writing-plans` without further brainstorming — the open item in §4 is the only thing that needs a decision at that point, not a re-derivation of the architecture.
