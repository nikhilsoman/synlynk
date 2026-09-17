# Workspace identity W9 — Hosted Vizor (Teams / Enterprise)

**Date:** 2026-09-17  
**Status:** Approved in chat 2026-09-17 (Nikhil): path tenant `synlynk.com/<product_slug>`; GitHub OAuth named; Google/Apple/Microsoft stub; relay as first origin/cache; **entire Vizor, not a subset**. Implementation is **out of scope** until this spec is on `main`, W4 exists, and a plan exists.  
**Issue:** [#914](https://github.com/nikhilsoman/synlynk/issues/914)  
**Depends on:** W3 (board + all local Vizor surfaces), W4 (human members)  
**Author:** Nikhil Soman (brainstorm with Grok, Home Conductor)

---

## 1. Problem

Local `synlynk viz` (loopback) is the dogfood surface. Teams and Enterprise need the **same** workspace in a browser without SSH to Nikhil’s laptop: a teammate at hitchock or an agency Partner opens the product Vizor, sees organigram + board + jobs, with human OAuth.

This is **not** a marketing landing page and **not** a stripped “status lite.” If a tab, action, or panel exists in local Vizor, it exists on hosted Vizor.

No hosted code in this docs PR. **#914 stays OPEN.**

---

## 2. Decision (locked)

| Topic | Choice |
|:---|:---|
| URL (this spec) | `https://synlynk.com/<product_slug>` |
| Subdomain later | `<product_slug>.synlynk.com` when cookie isolation needs it — not blocking |
| Origin | Relay caches/serves generated Vizor or a small API over **synced** product state (W4) |
| Auth | **GitHub OAuth** required for hosted humans. Google / Apple / Microsoft = same IdP protocol, **stub** |
| Who logs in | **Human members** (W4). Agent types do not get Vizor logins |
| Surface parity | **Entire Vizor** — every local element, not a subset |
| Solo | Unchanged: loopback `synlynk viz`, no hosted account required |

---

## 3. Entirety (non-negotiable)

Hosted Vizor **includes**, as they exist locally then and as W3/W8 add them:

- Shell, nav, all tabs
- Gantt, Board, User Journeys, Architect Map, Effort & Cost, Efficiency, Observatory
- Organigram (W8) — onboard, expand types, home/reach, tracker connect
- Onboarding / roles / readiness
- Sticky notes / annotate → context
- Dispatch-adjacent views that Vizor already exposes (job drawer, live polling)
- Product filters (`repo_id`, type id)

**Forbidden:** a hosted “read-only executive dashboard” that omits organigram, Board writes, Observatory, or onboarding. If a local write is unsafe on the web (e.g. open a local worktree), hosted exposes the **equivalent** (deep-link, copy path, “open on agent machine”) — it does not drop the feature silently.

Local loopback may stay unauthenticated for the operator. Hosted is always OAuth.

---

## 4. Auth and tenancy

- GitHub OAuth identity **maps to a W4 member** of that `product_slug`. No membership → 404/403, not a leaked graph.
- Google / Apple / Microsoft: same member mapping when implemented; unknown IdP fail-closed.
- Session cookies scoped to the path tenant until subdomain migration.
- Agent PEMs and connector `secret` files are **never** sent to the browser. Hosted API uses W4 token minting (approach C), not downloading PEMs.

---

## 5. Data path

Hosted does not become a second `state.db`. Relay/API reads the **product** graph (W2) after W4 sync (member machines / daemon). Cache is a projection (HTML/JSON), invalidate on graph change. Conflict: product `state.db` wins (same as W6 policy).

---

## 6. Non-goals (W9)

- Implementing relay hosting, OAuth apps, wildcard DNS
- Building Google/Apple/Microsoft IdP in this epic
- Replacing local Vizor
- Closing #914

---

## 7. Success

- A W4 member opens `https://synlynk.com/hitchcock`, GitHub OAuth, and gets the **same tab set** as `synlynk viz` on a hitchock checkout (Board, organigram, Observatory, Map, …).
- A non-member cannot see hitchock’s graph.
- `https://synlynk.com/vdowrx` is a different tenant.
- Local `synlynk viz` on synlynk still works with no synlynk.com account.

---

## 8. Test plan (when implemented; not this PR)

- Unit: path tenant routing; unknown IdP fail-closed; non-member 403; parity checklist = local Vizor route list ⊆ hosted routes.
- No live OAuth in unit tests.
