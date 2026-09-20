# W10 — A Phone Can Talk to a synlynk Workspace, Once Hosted Vizor Exists

**PR:** TBD
**Date:** 2026-09-20

## Where things stood

The #914 workspace-identity arc (W0–W9) had just locked its last piece: W9, hosted Vizor. The plan there is `synlynk.com/<product_slug>` — a relay serving the same organigram, board, and job state that local `synlynk viz` shows, gated by GitHub OAuth and W4 member-token minting. The stated goal at the end of W9 was narrow and firm: give a teammate or an agency Partner a browser window onto a workspace without SSH to Nikhil's laptop. Nothing about phones, nothing about chat.

## What moved the goalpost

Grok Bot — xAI's persistent cloud agent, reachable from a macOS/iOS/Android app — turned out to have exactly one integration path into a third-party system: a **remote MCP connector**. Not local, not loopback — it only speaks to an MCP server reachable over the public internet. That's a hard constraint, and it happens to line up with something synlynk was already going to build: a hosted relay with real auth. The question this PR answers is whether "remote access to a Workspace" should mean two things being built (a web HUD and a phone bot, separately) or one relay with two consumers.

## What this PR ships

Nothing executable — this is a spec, `docs/superpowers/specs/2026-09-20-grok-bot-remote-mcp-design.md`, tracked as **W10**. It locks:

- **Transport**: a remote MCP endpoint (`synlynk.com/<product_slug>/mcp`) on the *same* W9 relay — no second backend.
- **Auth**: the same GitHub OAuth + W4 member-token minting hosted Vizor already needs. Grok Bot's connector auth maps to a W4 member exactly like a browser session does.
- **Authority**: the MCP layer is a thin transport. `dispatch` and `decide` still pass through `policy.json`/`merge_authority` server-side — Grok Bot's own prompt-based permission model (natural-language rules + a review agent, not code-enforced) is never treated as the real gate.
- **Tool surface (v1)**: `status`, `jobs_list`, `job_get`, `pr_check` (read), `dispatch`, `decide` (write) — each mapped 1:1 to something hosted Vizor already does, so nothing new gets exposed.
- **Scope discipline**: the Marketplace "Bot" template (packaging this MCP surface as a shareable, pre-wired bot) is explicitly deferred — a follow-on spec, not built here.

One thing deliberately left open: whether writes ship enabled on day one or the surface launches read-only with a feature flag for `dispatch`/`decide`, flipped on after real-world confidence. That's a rollout call, not an architecture call, so it's flagged rather than decided.

No brainstorm visuals were used for this one — the questions were architectural (transport, auth, authority), not visual, so the session stayed text-only per the brainstorming skill's own guidance on when a visual companion earns its keep.

## Where this leaves the long arc

The long arc is a harness-agnostic Home Conductor — Claude, Codex, Agy, Grok all get equal home/away airtime, and now potentially a *device* dimension too: the same conductor role reachable from a laptop or a phone, against one source of truth. W10 doesn't add a new source of truth; it makes sure a second client of the existing one doesn't turn into a second implementation of it.

## New goalpost

W10 is locked and blocked on W9 landing on `main` with its own plan. The moment that dependency clears, W10 moves straight to `writing-plans` — the only decision waiting is the read/write rollout flag in §4, not a re-litigation of the design.
