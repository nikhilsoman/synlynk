<!-- generated - source of truth is state.db -->
---
decision_id: dec-f34a2f5f
topic: "Review and approve/reject the Companion v2 design (docs/superpowers/specs/2026-10-31-companion-v2-design.md, committed 5b857324): an at-the-fence personality/voice system that registers against the just-approved Configurability Framework (docs/superpowers/specs/2026-10-31-configurability-framework-design.md). Key mechanics: FeatureSpec registration with extra_name=None and default_enabled=False; a zero-call-site-change composition hook (companion.maybe_add_hint) injected inside render_task_fence() itself rather than at the 3 existing call sites; significance-tier gating (routine/notable/milestone) combined with a voice_density setting; stage (6-step acceptance ladder) and segment (4 developer types) each auto-inferred fresh from telemetry per call with user override, independent of theme; built-in IP-safe pastiche archetypes as Python dict literals plus BYO theme packs via discover_packs("companion"); hybrid template-default/remix-opt-in content generation restricted to milestone tier; and a domain_vocab word-substitution pass (longest-key-first, word-boundary, non-recursive) applied as the final step after composition. Evaluate: is the zero-call-site hook the right integration point or does it create hidden coupling/circular-import risk between fencing.py and companion.py; is computing stage/segment fresh from telemetry on every fence call (rather than caching) a performance or consistency concern; is the fail-open fallback-to-standard-theme-on-unknown-name consistent with the framework's stated fail-closed convention or a meaningful exception that needs to be flagged; and does the composition/vocabulary ordering (template-or-remix, then domain_vocab substitution) avoid edge cases like vocabulary terms colliding with remix-generated text."
date: 2026-10-31
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Review and approve/reject the Companion v2 design (docs/superpowers/specs/2026-10-31-companion-v2-design.md, committed 5b857324): an at-the-fence personality/voice system that registers against the just-approved Configurability Framework (docs/superpowers/specs/2026-10-31-configurability-framework-design.md). Key mechanics: FeatureSpec registration with extra_name=None and default_enabled=False; a zero-call-site-change composition hook (companion.maybe_add_hint) injected inside render_task_fence() itself rather than at the 3 existing call sites; significance-tier gating (routine/notable/milestone) combined with a voice_density setting; stage (6-step acceptance ladder) and segment (4 developer types) each auto-inferred fresh from telemetry per call with user override, independent of theme; built-in IP-safe pastiche archetypes as Python dict literals plus BYO theme packs via discover_packs("companion"); hybrid template-default/remix-opt-in content generation restricted to milestone tier; and a domain_vocab word-substitution pass (longest-key-first, word-boundary, non-recursive) applied as the final step after composition. Evaluate: is the zero-call-site hook the right integration point or does it create hidden coupling/circular-import risk between fencing.py and companion.py; is computing stage/segment fresh from telemetry on every fence call (rather than caching) a performance or consistency concern; is the fail-open fallback-to-standard-theme-on-unknown-name consistent with the framework's stated fail-closed convention or a meaningful exception that needs to be flagged; and does the composition/vocabulary ordering (template-or-remix, then domain_vocab substitution) avoid edge cases like vocabulary terms colliding with remix-generated text.

## Panel Inputs

### claude
[model=default; version=2.1.311 (Claude Code)]

## Analysis

**Hook placement (fencing.py importing companion.py):** The import is local (inside the function), which avoids a module-level circular import, but it still creates a runtime dependency from the generic fencing primitive onto a specific feature module. That's a layering inversion: `fencing.py` is infrastructure; `companion.py` is a feature built on top of it. The "zero call-site changes" win is real and valuable (dispatch.py x2, cli.py x1 untouched), but it comes at the cost of every fence render — even with Companion fully disabled — paying a module-import + `is_feature_enabled()` check. That's cheap today, but it sets a precedent: the next fence-consuming feature will be tempted to hook the same way, and `render_task_fence()` becomes a dumping ground for side-effecting callbacks. A thin seam (e.g., a `fence_hooks` list that features register into, which `fencing.py` iterates generically) would get the same zero-call-site benefit without fencing.py needing to know companion exists by name.

**Fresh stage/segment inference per call:** Computing from `.synlynk/telemetry.json` on every fence call is a correctness-over-performance choice, and it's the right one — telemetry files are small, reads are infrequent (fence cadence, not per-line), and caching risks exactly the staleness this design explicitly rejects for the FTUE-stage anti-pattern (no elapsed-time advancement). This is fine as designed; flag it only if telemetry file size grows unbounded later.

**Fail-open theme fallback:** This is a real, correctly-flagged exception to the framework's fail-closed convention, and the spec is honest about it ("availability, not security"). That reasoning holds — an unknown theme name degrading to `standard` output is not a security-relevant gate like the enable/disable Layer 2 check. Acceptable as a documented, narrow exception, not a violation.

**Composition/vocabulary ordering:** domain_vocab runs last, over already-composed text (template or remix), longest-key-first, word-boundary, non-recursive. This avoids the worst edge case (a short key pre-empting a longer one) but doesn't address vocabulary terms colliding with remix output that already contains the *replacement* text — a mild, low-stakes idempotency wrinkle (replacement happens to match another key), not a correctness bug, since non-recursion only prevents re-scanning the replacement itself.

## Recommendation

**Approve with one requested revision**: replace the name-specific `companion` import in `render_task_fence()` with a generic hook-registration seam, so fencing.py stays feature-agnostic. Everything else — tiering, stage/segment inference, fail-open fallback, vocab ordering — is sound and well-justified.

### agy
[model=default; version=1.4.12]

Last completed task: Companion v2 design spec (commit `5b857324`)
Next task from `todo.md`: Reconcile project-docs drift stranded in PR #2571 review worktree (PR #2572)

---

### Evaluation

1. **Integration Hook & Coupling:** Injecting `companion.maybe_add_hint()` inside [`render_task_fence()`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/synlynk/fencing.py) is the correct pragmatic choice. Mutating `data.hints` avoids altering call sites across `dispatch.py` and `cli.py`. Circular import risks are mitigated by the function-local import inside `render_task_fence()`, combined with `typing.TYPE_CHECKING` in [`synlynk/companion.py`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/synlynk/companion.py). An immediate `is_feature_enabled("companion")` check ensures zero overhead when disabled.

2. **Telemetry Recomputation & Performance:** Fence rendering occurs exclusively at harness task boundaries (cadence of tens of seconds to minutes), never in hot execution paths. Reading recent telemetry once per fence incurs sub-millisecond overhead. Computing stage and segment fresh guarantees dynamic responsiveness to user behavior shifts without the risk of stale cache synchronization bugs, while explicit user overrides short-circuit telemetry reads entirely.

3. **Fail-Open Fallback vs. Fail-Closed:** The Configurability Framework’s strict fail-closed convention applies to Layers 1 and 2 (feature presence and enablement). Companion’s Layer 3 fallback—reverting an unresolvable theme to `"standard"` with a one-time warning—is an availability safeguard, not an authorization bypass. Halting terminal rendering due to a missing community pack would disrupt core developer workflows; falling back to an IP-safe built-in archetype is a well-bounded, pragmatic presentation choice.

4. **Composition & Vocabulary Ordering:** Placing the `domain_vocab` pass as the terminal step (after template resolution or milestone remix) is architecturally sound. Its purpose is enforcing domain terminology across all output; executing it post-remix ensures LLM-generated phrasing complies with project lexicon. Edge cases are structurally mitigated by non-recursive scanning, regex word boundaries, and longest-key-first prioritization, preventing substring preemption or runaway substitution cycles.

### Recommendation

I **APPROVE** the Companion v2 design ([`docs/superpowers/specs/2026-10-31-companion-v2-design.md`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/docs/superpowers/specs/2026-10-31-companion-v2-design.md)). It faithfully adheres to the Configurability Framework, avoids call-site sprawl, confines generative costs to milestone tiers, and implements robust guardrails for theme and vocabulary extension.

### codex
[model=default; version=codex-cli 0.163.0]

The design is coherent and largely compatible with the Configurability Framework. The internal hook in `render_task_fence()` is a good compatibility point: it preserves all three call sites and guarantees every task fence receives identical Companion behavior. However, the local import does not eliminate architectural coupling; it hides a dependency from `fencing.py` to `companion.py`, and Companion depends on `FenceData` and fencing-related configuration. This creates a plausible circular-import hazard during feature bootstrap. The implementation should enforce a one-way boundary—ideally a narrow protocol or lazy, guarded callback—plus an import-cycle test. Companion must also remain a strict no-op if bootstrap or configuration is incomplete.

Fresh stage and segment inference per call is semantically correct: it avoids stale behavioral classifications and honors the “not persisted” decision. The likely cost is telemetry parsing and inference overhead on every fence, especially because fences are intentionally frequent. The spec should require bounded, read-only telemetry access and define a per-call snapshot so stage and segment are internally consistent. A short-lived cache could be considered later, but caching must not be introduced implicitly because it changes the stated semantics.

Unknown-theme fallback is a deliberate exception to the framework’s fail-closed enablement rule, and the distinction is defensible: it concerns content availability, not feature activation or security. Still, it should be explicitly labeled as a composition-layer exception, with deterministic warning behavior and tests ensuring unknown feature names/settings do not similarly become enabled.

The composition order is sound. Remix or template generation occurs first, then longest-key-first, word-boundary, non-recursive vocabulary substitution, so substitutions cannot be bypassed by remix output and replacement text cannot cascade. Remaining edge cases—case sensitivity, punctuation, and terms inside generated identifiers—should be specified in tests.

I recommend **approve with conditions**: add explicit import-boundary/cycle safeguards, bounded telemetry snapshot semantics, and a stronger statement distinguishing theme fallback from framework fail-closed behavior.

### grok
[model=default; version=grok 1.0.70 (f50904eaee6c) [stable]]

I'll read the Companion v2 spec and the Configurability Framework it registers against, then judge the hook, telemetry, fail-open, and vocabulary-ordering questions.Reject the spec as committed. The Companion v2 shape is right — opt-in `FeatureSpec`, `default_enabled=False`, `extra_name=None`, packs via `discover_packs("companion")` — but four mechanics need to be amended before implementation.

The zero-call-site hook is the wrong layer. `render_task_fence()` is a pure formatter. `maybe_add_hint()` would mutate `FenceData.hints`, read config and telemetry, and on milestone remix run harness-exec inside that formatter. A second render double-appends. Remix that itself emits a fence can re-enter the hook. A lazy `from synlynk import companion` probably avoids an import cycle, because `fencing.py` finishes initializing before `companion` imports `FenceData`, but `from synlynk import companion` also loads the package `__init__`, and the dependency still points the wrong way. Keep fencing pure. When features load, companion should register a hint callback that fencing already calls. Call sites stay unchanged, and fencing never names companion.

Fresh stage and segment inference is not a performance problem. `telemetry.json` is capped at about 100 rows, and fences run at task boundaries. The risk is consistency. The estimate fence and the complete fence in one command can disagree if telemetry is appended between them, and without hysteresis one atypical event flips `segment` and its skip table. Pin the inferred pair for that command. Do not persist a cache.

The unknown-theme fallback is a real exception to Layer 2, not a breach of it. Fail-closed governs enablement: a missing file, a missing entry, or a failed probe yields `default_enabled`, never a silent `True`. An unknown `theme` is a bad setting on a feature that is already on. Falling back to `"standard"` still speaks, and a one-time warning becomes a silent wrong voice. Validate names at `config set` against built-ins and discovered packs. At runtime, repeat the warning on every fence until the name resolves.

Vocabulary-after-compose is right for templates. Longest-key-first, word-boundary, non-recursive matching is sound, and keys must be `re.escape`d. It does not handle remix collisions. The model paraphrases past the keys, or it emits ordinary words (`run`, `will`, `cost`) that a flat table rewrites. Apply the table only to template lines. For remix, pass `domain_vocab` in the prompt as a constraint, and do not post-edit free text.

**Position: reject `5b857324` until those four amendments are in the design.** Callback registration instead of an import inside the renderer, inference pinned per command, unknown theme as an explicit Layer-3 exception with a loud fallback, and domain vocabulary kept off unconstrained remix prose. With those changes, approve.

## Synthesis
## Synthesis

All four reviewers agree the core shape of the design — opt-in `FeatureSpec` registration, `default_enabled=False`, tiered significance gating, pack discovery via `discover_packs("companion")`, and the milestone-only remix restriction — is sound and correctly registers against the Configurability Framework. Where they diverge is on four specific mechanics, and on three of those four, a majority (3 of 4) converge on the same fix:

**1. Hook placement (fencing.py → companion.py).** Claude, Codex, and Grok independently flag the same issue: a function-local import avoids a *module-load-time* circular import, but it still gives the generic `fencing.py` primitive a named, hardcoded dependency on a specific feature. Grok adds a concrete failure mode (double-append on re-render, re-entrancy if remix output itself triggers a fence). Only Agy is satisfied with the import-as-is. **Majority verdict: replace the named import with a generic hook-registration seam** — fencing.py exposes a callback list/registry that features register into at load time; it never needs to know "companion" exists by name. This preserves the zero-call-site-change win without the layering inversion.

**2. Fresh stage/segment inference per call.** Claude and Agy call this a non-issue (telemetry is small, reads are infrequent, caching would reintroduce the staleness problem the design explicitly rejects). Codex wants a defined "bounded snapshot" semantic. Grok raises the sharpest, most concrete concern: two fences within the *same command* (e.g., an estimate fence and a completion fence) can read telemetry at different points and infer different stage/segment, producing visibly inconsistent voice within one command's output. This is a real consistency bug, not a performance worry. **Adopt Grok's fix: pin the inferred stage/segment once per command invocation**, not per individual fence call — still computed fresh each command, never persisted across commands.

**3. Fail-open theme fallback.** Unanimous: falling back to `standard` on an unresolvable theme name is a legitimate, narrow exception to the framework's fail-closed convention (it's a content-availability concern, not a security/enablement gate), and it's fine as a concept. The gap all reviewers converge toward is documentation and UX: the spec should **explicitly label this as a named Layer-3 exception** (not just note it in passing), and the warning should repeat on each affected call rather than fire once and go silent, so a persistently-misconfigured theme name doesn't quietly produce the wrong voice indefinitely.

**4. Composition/vocabulary ordering.** Claude, Agy, and Codex find the longest-key-first, word-boundary, non-recursive, post-compose ordering sound, flagging only minor edge cases (case sensitivity, punctuation) to cover in tests. Grok identifies a distinct and more substantive gap: applying `domain_vocab` as a blind post-substitution pass over milestone-tier *remix* output risks rewriting ordinary LLM-generated prose words that happen to collide with vocab keys, since remix text — unlike template text — isn't under the design's control. **Adopt this fix: restrict post-hoc `domain_vocab` substitution to template-generated lines; for remix output, pass `domain_vocab` as a generation constraint in the prompt instead of editing the free-form text afterward.**

None of these four fixes require re-brainstorming the design from scratch — they're bounded amendments to an otherwise-approved spec, which is why 3 of 4 reviewers landed on approve (two with conditions) rather than reject.

**Decision: Approve `docs/superpowers/specs/2026-10-31-companion-v2-design.md` (5b857324) conditional on four spec amendments before implementation begins — (1) a generic fence-hook registration seam replacing the named `companion` import in `render_task_fence()`, (2) stage/segment inference pinned once per command rather than per individual fence call, (3) the unknown-theme fallback explicitly documented as a named Layer-3 fail-closed exception with a repeating (not one-time) warning, and (4) `domain_vocab` substitution restricted to template-generated text, with remix output constrained via the generation prompt instead of post-edited.** File these as required revisions to the spec; re-review is not needed once they're folded in — proceed to planning/build after the spec is updated.

## Decision
**Decision: Approve `docs/superpowers/specs/2026-10-31-companion-v2-design.md` (5b857324) conditional on four spec amendments before implementation begins — (1) a generic fence-hook registration seam replacing the named `companion` import in `render_task_fence()`, (2) stage/segment inference pinned once per command rather than per individual fence call, (3) the unknown-theme fallback explicitly documented as a named Layer-3 fail-closed exception with a repeating (not one-time) warning, and (4) `domain_vocab` substitution restricted to template-generated text, with remix output constrained via the generation prompt instead of post-edited.** File these as required revisions to the spec; re-review is not needed once they're folded in — proceed to planning/build after the spec is updated.

> Signatures: see 2026-10-31-review-and-approve-reject-the-companion.json
