<!-- generated - source of truth is state.db -->
---
decision_id: dec-db39a676
topic: "Slot synlynk-native-skill (goal-483f99a3, issue #5371) as roadmap arc v0.39.0, ahead of the held v0.39.0-v0.43.0 release-proposal queue -- extracted from the roadmap composition/prioritization decide panel (dec-fcec4295, gh:#5372) specifically to close the ARC_NO_DECISION gate for this goal. Same panel inputs and synthesis as dec-fcec4295; this record exists to carry the explicit goal_id link dec-fcec4295 itself did not carry (it resolved to goal-bfc37035/Harness Parity via text-match heuristic instead)."
date: 2026-11-18
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Slot synlynk-native-skill (goal-483f99a3, issue #5371) as roadmap arc v0.39.0, ahead of the held v0.39.0-v0.43.0 release-proposal queue -- extracted from the roadmap composition/prioritization decide panel (dec-fcec4295, gh:#5372) specifically to close the ARC_NO_DECISION gate for this goal. Same panel inputs and synthesis as dec-fcec4295; this record exists to carry the explicit goal_id link dec-fcec4295 itself did not carry (it resolved to goal-bfc37035/Harness Parity via text-match heuristic instead).

## Panel Inputs

### claude
[model=sonnet; version=2.1.327 (Claude Code)]

**Analysis**

The two gaps are different in kind. Gap 1 (the 10-match truncation in `mine_specs_and_decisions()`) is a plain bug. It silently drops data and has no design rationale, so it should be fixed outright. Gap 2 (`target_count=5`) is a design heuristic that has hardened into a de facto invariant. Every ticket from v0.36.1 through v0.38.2 has exactly five stories, so the cap is the only thing shaping releases. A flat cap over a mixed top-15 pool optimizes for similar-sized releases, not for coherent ones. It also splits goals, which works against the "one-sentence pitch" rule in the Named Release Policy.

**Goal-aware packaging: yes, with guardrails.**
- If a goal has N ready stories, cluster by `goal_id` first and fill the release from that goal. Only fall back to thematic clustering for leftovers or orphan stories.
- Don't leave it fully uncapped. Use a soft ceiling, for example 12–15 stories or a cost/token estimate. Beyond that, split along plan-phase boundaries, not arbitrary count. A 24-task goal should become 2–3 phase-aligned releases, each with a real pitch. An uncapped 24-story release would be unreviewable and would make rollback and `pr check` coarse.
- Keep the cap as the default for mixed pools. Goal-awareness should be additive, so existing behavior doesn't regress.
- Separately fix the mining truncation so plans over 10 tasks aren't silently under-mined. Add a test that mines a 24-task plan and expects 24 items.

**Sequencing.** Yes, synlynk-native-skill should get its own slot ahead of v0.39.0+. Three reasons:
1. It is the only initiative with a committed spec, a committed plan, and GOVERNS-linked stories. Everything from v0.39.0 to v0.43.0 is provisional and unspecced. Under Brainstorm-First, that work can't be dispatched yet anyway.
2. It absorbs the superpowers ceremonies and closes #5367. That removes an external dependency from every later release's workflow, so it is infrastructure for the queue and not just another item in it.
3. It exercises the goal-aware packager, so it gives a real test of the fix.

I'd leave v0.38.2 (Harness Parity Phase 3) where it is, since it is open and in flight, and slot the skill as v0.38.3 (or v0.39.0, if it ships as a named theme). Split it by plan phase.

**Provisional proposals.** Don't merge them. The themes are genuinely distinct (Hetzner, Edge Routing, Ambient Co-Pilot, Sovereign Silicon, Intent-Based Engineering, Cloud Wedge Shell). Instead, renumber them down by one slot and treat them as unspecced placeholders. Re-run the packager after the goal-aware fix, because some of them may have been fragmented by the cap and could consolidate on their own.

**Position:** Make the packager goal-aware with a soft ceiling of about 12–15 stories and phase-boundary splitting. Fix the mining truncation as a separate bug. Slot synlynk-native-skill immediately after v0.38.2, split by phase. Shift v0.39.0–v0.43.0 down one slot without merging them, and re-package them after the fix lands.

### agy
[model=default; version=1.5.11]

**Last completed task:** Created goal-483f99a3, 24 GOVERNS-linked stories, and issue #5371 for the [synlynk-native-skill plan](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+claude+harness-parity-redesign/docs/superpowers/plans/2026-11-18-synlynk-native-skill.md).  
**Next task from [todo.md](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/chore+claude+harness-parity-redesign/project-docs/todo.md):** Harness Parity Corrective Redesign: Live Routing + Manifest Mechanics (`story-e1b2c9d7`).

---

### Analysis & Recommendations

**1. Transition to Goal-Aware Release Packaging**  
The hard ceiling of `target_count=5` across a mixed candidate pool shatters cohesive architectural initiatives into arbitrary micro-releases, multiplying verification overhead and blurring milestone intent. `package_next_release_proposal()` must become **goal-aware**: whenever candidates share an active `goal_id`, the packaging engine should sweep all ready stories under that goal into a single coherent release proposal uncapped. The flat 5-story ceiling should be retained strictly as a batching guardrail for unparented maintenance chores and ad-hoc backlog tickets.

**2. Audit & Consolidation of Provisional Queue (v0.39.0–v0.43.0)**  
The 7 held release proposals (spanning Hetzner Swarm, Edge Routing Oracle, DevEx, Sovereign Silicon, Intent-Based Engineering, and NATS Wedge) are heavily fragmented artifacts of this 5-story ceiling. Because each proposal was truncated from larger strategic tracks, they represent split pieces rather than standalone value deliveries. These provisional milestones should be collapsed and re-clustered by their parent goal definitions, consolidating multiple 5-ticket fragments back into cohesive, full-scope milestone proposals.

**3. Prioritization of `synlynk-native-skill`**  
The 24-task `synlynk-native-skill` initiative establishes the universal harness-native skill tree and cross-agent instruction sync mechanisms. This is foundational runtime substrate that directly unifies harness interactions across Claude, Codex, Agy, and Grok. Deferring or splitting this goal behind downstream feature epics forces future initiatives to build against a legacy, fragmented instruction protocol.

---

### Position
I recommend updating `package_next_release_proposal()` to package goal-governed stories uncapped by default, collapsing the artificially fragmented v0.39.0–v0.43.0 provisional proposals into their true consolidated goal scopes, and scheduling the unified 24-task `synlynk-native-skill` goal as **v0.39.0** immediately following the completion of v0.38.x.

### codex
[model=default; version=codex-cli 0.169.1]

The two findings are systemic packaging defects, not isolated data-quality issues. The 10-line mining limit makes backlog state incomplete; the five-story thematic cap then converts that incomplete state into misleading release boundaries. Roadmap decisions made from the current proposals should therefore be treated as provisional until both mechanisms are corrected and the queue is re-mined.

`target_count=5` should become goal-aware. When ready stories share a validated `goal_id`, the packager should include the full goal, uncapped, subject to practical safeguards such as release-size limits, dependency validity, and an explicit split only at a goal boundary. For mixed candidate pools, the existing cap can remain as a fallback. This preserves coherent delivery while preventing one oversized or malformed goal from monopolizing a release indefinitely.

The synlynk-native-skill goal is materially different from the queued thematic initiatives: it is already defined as a 24-task, manually validated unit, and the manual workaround demonstrates that the current roadmap does not represent it reliably. It should receive a dedicated release slot, preferably v0.39.0 if v0.38.2 is already in active release handling. A v0.38.x slot is justified only if the branch is still open for a compatible corrective release and the goal’s work is genuinely release-ready; it should not be forced into a patch release merely to preserve chronology.

The later v0.39.0-v0.43.0 proposals should be regenerated after the fixes, then resequenced by dependency, readiness, and strategic value. They should not be merged solely because the old cap split them; merge only genuinely overlapping goals. My position: implement goal-aware uncapped packaging, re-mine and repackage the queue, reserve synlynk-native-skill its own v0.39.0-class slot, and defer final ordering of subsequent provisional releases until that recomputation is complete.

### grok
[model=default; version=grok 1.0.77 (50ca579fa996) [stable]]

I'll ground the recommendation in how mining and release packaging actually cap stories, then look at the held v0.38–v0.43 queue against the new 24-task goal.The two gaps compound. Mining keeps only the first 10 checkbox lines and the first 10 `### Task N:` headers per file, so a 24-task plan never becomes one backlog. Packaging then takes a mixed top-15 and keeps at most five stories, even when they share a `goal_id`. The release theme is chosen from the next roadmap arc for that version, not from the stories. Clustering prefers one goal and drops the rest; the next sweep rethemes the remainder under a different arc. That is how one initiative gets smeared across Harness Parity, Hetzner, Edge Routing, and the later titles. The hand-built `goal-483f99a3` plus #5371 is the right shape: one goal, the full task set, one tracking issue.

Make packaging goal-aware, not uncapped. Pick the winning goal first. Ship only that goal's ready stories, and do not backfill from other goals to hit a count. Derive the theme from the goal. A 24-story goal is a program: use a phase-sized ceiling (about one plan phase, ~12 stories) and emit an explicit same-theme continuation for the overflow. Remove the silent 10-line mine slice, and stop filing mined rows under the default backlog goal. Widen the candidate pool from "15 mixed" to "all ready stories of the winning goal," or the cap just moves upstream.

Do not place all 24 native-skill tasks ahead of v0.39.0–v0.43.0, and do not merge those provisional themes. Hetzner, edge routing, sovereign silicon, and the NATS wedge are different arcs; the cap made their story lists untrustworthy, not their titles. Audit each held proposal by `goal_id`, pull split slices back into one theme with a part-2 ticket, and strip cross-goal filler. Keep v0.38.2 if its stories are actually Harness Parity Phase 3. Reserve v0.39.0 for native-skill stage 0 (tree, manifests, SessionStart, one harness loading the skill) and the remainder as v0.39.x on the same goal. That sits after parity and before Ambient Co-Pilot and Intent-Based Engineering. Leave the infra arcs queued, but stop letting them absorb this goal. Treat v0.40–v0.43 membership as suspect until recomputed.

**Position:** Replace the flat five-story cap with single-goal packaging, a phase-sized ceiling, and same-theme continuations. Give synlynk-native-skill its own v0.39 slot in two cuts. Repair split goals in the held queue; do not merge unrelated themes or jump that queue with all 24 tasks.

## Synthesis
**Where the four panelists agree**
- The mining truncation is a plain bug. It has no design rationale and should be fixed on its own, with a test that mines a 24-task plan and expects 24 items.
- The flat `target_count=5` over a mixed top-15 pool should become goal-aware. Stories that share a `goal_id` should be packaged together, and the flat cap stays only as the fallback for orphan or maintenance stories.
- synlynk-native-skill should get its own slot ahead of the provisional v0.39.0–v0.43.0 proposals. It is the only initiative with a committed spec, a committed plan and GOVERNS-linked stories. It also removes the superpowers dependency (#5367), which every later release would otherwise inherit.
- v0.38.2 (Harness Parity Phase 3) is in flight and stays as it is.
- The held queue's story lists can't be trusted until it is recomputed after the fixes.

**Where they split, and how I resolved it**
- **Uncapped vs. bounded.** Agy and Codex want the cap removed for goal-governed packaging. Claude and Grok want a ceiling of about 12–15 stories, or one plan phase, with overflow split at phase boundaries. I side with bounded. A 24-story release can't be reviewed, rolled back or checked with `pr check` in any useful way, and it breaks the one-sentence-pitch rule. Cutting at phase boundaries keeps each part coherent.
- **Merge or keep the provisional proposals.** Agy wants them collapsed. Claude, Codex and Grok say the themes are genuinely distinct and shouldn't be merged. I side with the majority. Merge a fragment back only when its stories share a `goal_id`. Never merge across themes.
- **Slot number.** Claude suggested v0.38.3 or v0.39.0, and the other three said v0.39.0. I choose v0.39.0. It's a named feature cluster, not a patch, and v0.38.x stays reserved for Harness Parity.

**Root cause (from Grok).** The release theme comes from the next roadmap arc for that version, not from the stories. The packager keeps one goal's stories up to the cap and drops the rest. The next sweep then files the leftovers under a different arc. That is how one initiative ends up spread across unrelated themes. Making the cap goal-aware fixes the count, but the theme also has to be derived from the winning goal.

**Order of work**
1. Fix the mining truncation as its own bug, with the 24-task test.
2. Make packaging goal-aware. Pick the winning goal first and ship only its ready stories, with no cross-goal backfill. Derive the theme from the goal, and use a phase-sized ceiling of about 12 stories. Overflow becomes a same-theme continuation ticket.
3. Cut native-skill as v0.39.0 (tree, manifests, SessionStart, one harness loading the skill) and v0.39.x for the rest, on goal-483f99a3. It doesn't need the packager fix to ship, since the goal and stories already exist.
4. Re-mine and re-package the held v0.40–v0.43 queue by `goal_id`. Repair split goals, strip cross-goal filler, and then finalize the order by dependency, readiness and strategic value.

**Decision:** Make `package_next_release_proposal()` goal-aware. It will package one goal's ready stories together, derive the theme from that goal, and use a phase-sized ceiling of about 12 stories, with overflow as a same-theme continuation. The flat 5-story cap stays only for orphan stories. Fix the 10-match mining truncation separately as a plain bug. Give synlynk-native-skill its own v0.39.0 slot, split by plan phase, right after v0.38.2 and ahead of the other provisional releases. Don't merge the provisional themes. Re-mine and re-package the held v0.40–v0.43 queue by `goal_id`, merge only fragments of the same goal, and finalize their order after that recomputation.

## Decision
Decision: Give synlynk-native-skill its own v0.39.0 slot, split by plan phase, right after v0.38.2 and ahead of the other provisional releases (which shift v0.39.0-v0.43.0 -> v0.40.0-v0.44.0 to make room). Panel: claude, agy, codex, grok (2026-11-18, same panel as dec-fcec4295).

> Signatures: see 2026-11-18-slot-synlynk-native-skill-goal-483f99a3.json
