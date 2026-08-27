# Charter Authority — Surfacing Mechanism, Harness-Agnosticism, and Role-Portability — Design

**Date:** 2026-08-27
**Status:** Approved (pending final user sign-off on this written doc)
**Author:** Claude (pm), brainstormed with Nikhil Soman; resolved via `synlynk decide --panel claude,agy,codex,grok --record` (agy timed out, 3/4 quorum)
**Decision record:** `project-docs/decisions/2026-08-27-charter-authority-surfacing-mechanism-ha.md`

## 1. Motivation

The 2026-08-27 audit of the two-imperatives roadmap found that workspace agent charters (`synlynk agent init/edit`, shipped in Phase 1) exist for all 8 org-chart roles but are **activated as identity records only** — `read_charter()` is called from `agent_cli.py` (the `agent show` command) and nowhere else. Grepping the dispatch path confirms `dispatch.py` consults `agent_store.list_agents()` for `--as-agent` role resolution and `capability_grants` overrides, but never calls `read_charter()`. A charter currently has zero effect on what a dispatched harness does.

Reviewing `pm`'s charter specifically surfaced a second, deeper structural question: the 2026-08-09 agent-roles-charters spec (§3.1) hardcodes `pm` and `architect` as "Claude only — not delegated out." That carve-out means charter injection can't be solved uniformly across all 8 roles without first deciding whether `pm`/`architect` stay permanently pinned to one harness. The user extended this further: the "represents the human" authority itself is currently welded to the `pm` role label, but should be a reassignable attribute — both because harness capability is expected to shift (Claude's current edge over Agy/Grok/Codex is real but not permanent, and synlynk may build its own harness), and because different users may prefer to drive synlynk through a different role's interaction style.

This design resolves four linked questions, decided via a `synlynk decide` panel (claude, codex, grok — agy returned no output):

1. Where/how does a role's charter actually reach the harness executing that role's work?
2. Should the hardcoded "pm/architect = Claude only" carve-out (2026-08-09 spec §3.1) be retired?
3. Should "represents the human" be decoupled from the `pm` role label and made reassignable?
4. How must charter injection be designed so it works for whichever role currently holds that authority, not hardcoded to `pm`?

## 2. Decision

**Q1 — Injection mechanism: Option C.** Route `pm` and `architect` through the same `synlynk dispatch` path as `dev`/`qa`/`designer`/`marketing`, and have that path inject the resolved role's active charter into dispatch context through the same code path `generate_context()` (`synlynk/context.py:233`) already assembles memory/roadmap context through — not a second, parallel injector.

Rejected alternatives:
- **Option A** (render the charter into CLAUDE.md's synlynk-owned harness fence): permanently binds `pm`/`architect` behavior to Claude's fence specifically. It would not travel to Agy/Grok/Codex or a future synlynk-built harness, and directly fights Q2's retirement of the Claude-only carve-out.
- **Option B** (explicit session-start pull, e.g. `synlynk agent whoami`): opt-in discipline that gets skipped in practice. Useful as an inspection/debug command, not as the activation mechanism.

**Gap to close in the same change:** native IDE sessions that never pass through `synlynk dispatch` or `synlynk exec` won't receive charter injection either under Option C. Close this by routing those sessions through `synlynk exec` too — not a third, parallel mechanism.

**Q2 — Retire the Claude-only carve-out: yes, as an amendment to the locked 2026-06-28 decision (issue #79), not a reversal of it.** #79's rationale ("keep Claude's context clean for PM decisions; implementers have purpose-built tooling") correctly matched capability to accountability at the time — it does not argue Claude must remain the only PM-capable harness forever. Move `pm` and `architect` into `.synlynk/policy.json`'s existing `dev_authority.task_allocation` table, using the same capability+cost-matrix routing every other role already uses, with Claude as the current default entry (its edge today is real). Any re-ranking away from that default still requires the same evidence discipline the Harness Capability Reassessment Protocol already enforces — no blind swap on a hunch.

**This amends a locked decision and requires explicit human sign-off before implementation.** (Obtained 2026-08-27 — see §7.)

**Q3 — Decouple "represents the human" from the `pm` label: yes.** Add a reassignable config pointer, `human_authority_role`, to `.synlynk/policy.json`, following the existing pattern of `merge_authority`/`release_authority` in that same file. Reassignment goes through the existing human-approval-gated flow — never a silent config edit, never agent self-reassignment. Charter *revision* changes a role's behavioral content; this pointer changes *which role holds an attribute* — a deliberately separate axis, so charter prose is not overloaded to also carry authority assignment. Default value: `pm`.

**This is a new governance primitive and requires explicit human sign-off before implementation.** (Obtained 2026-08-27 — see §7.)

**Q4 — Portable injection design.** The injector (Q1's shared dispatch/`exec` code path) must resolve `human_authority_role` from `.synlynk/policy.json` first, then load *that* role's charter through the shared context builder — it must never branch on `role == pm`. If the pointer is reassigned, the very next session picks up the new role's charter with zero code change. Dispatch should record the resolved role, charter revision, and harness used for each invocation, for traceability.

## 3. Dependency Ordering

- **Q4 is blocked on Q3** — the `human_authority_role` pointer must exist in `.synlynk/policy.json` before the injector can resolve it.
- **Q1's choice of Option C is what makes Q2 and Q4 coherent** — choosing Option A would re-hardcode Claude into the fence mechanism and directly contradict Q2's retirement of the Claude-only carve-out.
- **Recommended build sequence:**
  1. Q3's config pointer (`human_authority_role` in `.synlynk/policy.json`) — small, mechanical, no behavior change on its own.
  2. Q2's policy-table migration (`pm`/`architect` into `task_allocation`) — the amendment PR, reviewed against the sign-off obtained in §7.
  3. Q1 + Q4 land together as one PR: shared dispatch/`exec` charter injection, keyed off the Q3 pointer, closing the native-IDE-session gap via `synlynk exec`.

## 4. Schema Changes

`.synlynk/policy.json` gains one new top-level override, alongside the existing `merge_authority`/`release_authority` pattern:

```json
"human_authority_role": {
  "role": "pm",
  "requires_human_approval": true
}
```

`dev_authority.task_allocation` gains entries for the task-types `pm`/`architect` currently perform outside the existing `review`/`gh_write` entries — e.g. `brainstorm`, `pm`, `architecture-review` — mapped to `claude` as default `harness` with an empty or minimal `fallback` list initially, consistent with how `css`/`templates`/`content`/`subpages` are scoped to `agy` alone today. Exact task-type naming is an implementation-time decision, not fixed by this design.

## 5. Error Handling

- If `human_authority_role` is unset or missing from `.synlynk/policy.json`, the injector defaults to `pm` (matching today's implicit behavior) rather than failing.
- If the pointer names a role with no registered agent (`agent_store.list_agents()` has no matching `role_slug`), injection must fail loudly (visible error, not silent fallback) — an unset authority role is a configuration error, not a normal state.
- Charter injection failures (missing charter file, revision-store read error) must not silently produce an empty-charter dispatch; surface the failure the same way other dispatch preflight failures already surface today.

## 6. Testing

- Unit coverage for the injector resolving `human_authority_role` correctly for both the default (`pm`) and a reassigned value, without any `role == pm` branch existing in the code path.
- Regression test asserting `dispatch.py`'s context assembly includes charter content end-to-end for at least one Claude-only-today role (`pm` or `architect`) once Q2 lands.
- A reassignment test: moving `human_authority_role` to a different role and confirming the next dispatch picks up that role's charter with no code change required.
- `synlynk exec` coverage confirming native-IDE-session charter injection matches dispatch's injection (same code path, not divergent behavior).

## 7. Sign-Off Record

Per §2, Q2 and Q3 each amend or create governance primitives and required explicit human sign-off before implementation, per this design's own dependency ordering. Nikhil approved both in-session on 2026-08-27: "yes, approve both — write the spec." This satisfies the sign-off gate for both Q2 (amending issue #79) and Q3 (the new `human_authority_role` primitive); no further approval gate blocks moving this design to a plan.

## 8. Related Findings (Out of Scope for This Spec, Filed Separately)

Two issues surfaced during this brainstorm that are adjacent but not part of this design's scope:

1. **`pm`'s seed charter was overwritten.** `synlynk/agent_cli.py::SEED_CHARTERS["pm"]` ships a richer, more specific default (weekly competitive-intelligence sweep, capability/marketing-gap doc, feature-proposal escalation) than the generic spec-§2 prose written into `pm`'s charter during the 2026-08-27 role-provisioning pass (revision 2). These should be reconciled — likely merged, not replaced — as part of the Q1/Q4 implementation PR's charter content pass, since that PR will already be touching every role's charter content to align with the new authority model.
2. **`synlynk decide --record` writes to a gitignored path.** Verified during this session: the 2026-08-27 charter-authority decision recorded via `--record` landed in `.synlynk/project-docs/decisions/`, which `.gitignore` excludes — not the tracked `project-docs/decisions/` at repo root where 44+ prior decision records live (including the #79/#914-adjacent decisions this spec builds on). The file was manually copied into the tracked location to avoid losing it. This is a distinct bug from #1191 (same general area — local vs. tracked project-docs paths going out of sync) and should be filed and fixed on its own.

## 9. Out of Scope for This Spec

- Implementing any of Q1–Q4 — this document is the design; implementation is a separate plan per the Design → Plan → Build sequence.
- Exact task-type naming for the `dev_authority.task_allocation` entries added under Q2 (§4) — an implementation-time detail.
- Reconciling `pm`'s overwritten seed charter (§8.1) — a content fix, not an architecture decision, bundled into the implementation PR instead.
- Fixing `synlynk decide --record`'s gitignored write path (§8.2) — filed as a separate issue.
- Any further reassignment of authorities beyond `human_authority_role` (e.g. splitting "conversational principal" from "named-release sign-off" into separately reassignable authorities) — Grok's panel input raised this as a future possibility; not adopted here, no consensus was sought on it.
