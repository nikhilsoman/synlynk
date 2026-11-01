<!-- generated - source of truth is state.db -->
---
decision_id: dec-eccd7214
topic: "Review and approve/reject the Herdr Customizations design (docs/superpowers/specs/2026-10-31-herdr-customizations-design.md, committed 14bfb40a): splits Herdr integration into a thin always-on synlynk-core half (synlynk herdr init/tab <epic>, FeatureSpec herdr_cockpit with extra_name=None since Herdr is an external binary not a pip dependency, default_enabled=False, 3-step resolution: disabled->hint, enabled-but-no-herdr->tmux/terminal fallback, enabled-and-herdr-live->delegate to linked plugin or fall back to raw pane-split sequence) and an optional external herdr-synlynk GitHub repo tagged herdr-plugin (installed independently via herdr plugin install, carrying pane-layout actions, a worktree.created event hook gated on a user setting, GitHub link handlers, and a sentinel.md-to-Herdr-toast notifier). Also adds a lightweight Client Surface Consistency convention (branding/framing/version-alignment, no shared code) covering this plugin and the existing unpublished VS Code/Open VSX extension (clients/vscode/), with explicit extraction-to-its-own-doc trigger once a 3rd surface exists. Evaluate: (1) does the three-independent-gates structure (herdr binary present + feature enabled + plugin linked) actually guarantee no Herdr-related behavior runs without explicit opt-in, or are there gaps (e.g. the tmux fallback itself, or the worktree.created event hook once the plugin is linked but before the user sets herdr_auto_tab_on_epic); (2) is delegating to a user-installed herdr-plugin.toml-based plugin via 'herdr plugin action invoke' a reasonable integration point or does it create a fragile contract (versioning, action-id stability) between synlynk core and an independently-versioned external plugin; (3) is deferring the plugin repo's own build entirely out of this spec's scope appropriate, or does core's fallback-to-raw-pane-sequence path effectively require designing that logic now anyway, making the split less clean than claimed; (4) is the Client Surface Consistency section the right scope for 2 data points, or premature."
date: 2026-10-31
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
Review and approve/reject the Herdr Customizations design (docs/superpowers/specs/2026-10-31-herdr-customizations-design.md, committed 14bfb40a): splits Herdr integration into a thin always-on synlynk-core half (synlynk herdr init/tab <epic>, FeatureSpec herdr_cockpit with extra_name=None since Herdr is an external binary not a pip dependency, default_enabled=False, 3-step resolution: disabled->hint, enabled-but-no-herdr->tmux/terminal fallback, enabled-and-herdr-live->delegate to linked plugin or fall back to raw pane-split sequence) and an optional external herdr-synlynk GitHub repo tagged herdr-plugin (installed independently via herdr plugin install, carrying pane-layout actions, a worktree.created event hook gated on a user setting, GitHub link handlers, and a sentinel.md-to-Herdr-toast notifier). Also adds a lightweight Client Surface Consistency convention (branding/framing/version-alignment, no shared code) covering this plugin and the existing unpublished VS Code/Open VSX extension (clients/vscode/), with explicit extraction-to-its-own-doc trigger once a 3rd surface exists. Evaluate: (1) does the three-independent-gates structure (herdr binary present + feature enabled + plugin linked) actually guarantee no Herdr-related behavior runs without explicit opt-in, or are there gaps (e.g. the tmux fallback itself, or the worktree.created event hook once the plugin is linked but before the user sets herdr_auto_tab_on_epic); (2) is delegating to a user-installed herdr-plugin.toml-based plugin via 'herdr plugin action invoke' a reasonable integration point or does it create a fragile contract (versioning, action-id stability) between synlynk core and an independently-versioned external plugin; (3) is deferring the plugin repo's own build entirely out of this spec's scope appropriate, or does core's fallback-to-raw-pane-sequence path effectively require designing that logic now anyway, making the split less clean than claimed; (4) is the Client Surface Consistency section the right scope for 2 data points, or premature.

## Panel Inputs

### claude
[model=default; version=2.1.311 (Claude Code)]

**Analysis**

1. **Opt-in guarantee:** The three gates are real and meaningfully independent, but two gaps exist. First, the tmux fallback (step 2) fires once the feature flag is on, even without Herdr present — that's intended behavior (an explicit roadmap requirement), not a leak, but the spec should say plainly that enabling `herdr_cockpit` is itself consent to *a* multiplexer/terminal action, not just to Herdr-specific ones. Second, and more real: once the plugin is linked, the `worktree.created` hook runs on every worktree creation regardless of `herdr_auto_tab_on_epic` — the hook script checks the setting before *acting* (suggesting a tab), but it still executes and reads `.synlynk/config.json` on every event. That's a negligible-but-nonzero "behavior runs without opt-in" gap; worth a one-line acknowledgment that the hook's presence isn't itself gated, only its effect is.

2. **Delegating via `herdr plugin action invoke <action-id>`:** reasonable as a first integration point, but it is a string-keyed contract with no declared versioning strategy. If `herdr-synlynk` renames or reshapes `tab-epic`, core's fallback path masks the break silently (falls through to raw pane sequence) rather than surfacing it — convenient for robustness, but means version skew is invisible until someone notices the richer behavior silently stopped firing. The spec should at least note that failure mode is accepted, not undiscovered.

3. **Deferring the plugin build:** appropriate in principle, but partly fictional in practice — Section 3's fallback path (raw `herdr pane split`/`pane run` sequence) *is* the plugin's `apply-4pane` logic, just inlined into core instead of the plugin. Core isn't escaping that design work, it's duplicating it. That's a reasonable transitional seam (keeps core usable pre-plugin) but the doc should name it as duplication-by-design, not as scope avoidance.

4. **Client Surface Consistency section:** fine as a lightweight convention with an explicit extraction trigger — this is the right amount of ceremony for two data points, and the trigger condition is well-defined.

**Position:** Approve, with two small required edits before merge: (a) explicitly state that the `worktree.created` hook executes unconditionally once linked and only its *effect* is gated by `herdr_auto_tab_on_epic`, and (b) note the raw pane-split fallback is intentionally duplicative of the plugin's `apply-4pane` action, not independent of it. Neither blocks the design's soundness; both are one-sentence clarifications.

### agy
[model=default; version=1.4.12]

**Last completed task:** Roadmap v0.26.1: Workspace-agent operations  
**Next task:** Reconcile project-docs drift stranded in PR #2571 review worktree (PR #2572)

---

### Evaluation of Herdr Customizations Design (`14bfb40a`)

1. **Gate Integrity & Opt-In Guarantees:** The three-gate model (`herdr` CLI present, `herdr_cockpit=true`, plugin linked) successfully guarantees that no Herdr-specific behavior runs uninvited. With `default_enabled=False`, bare `pip install synlynk` environments remain completely untouched. The tmux/terminal fallback executes only upon explicit user invocation of `synlynk herdr tab` when the feature is enabled, fulfilling intended graceful degradation rather than an unprompted action. Furthermore, the plugin's `worktree.created` hook operates purely as an advisory suggestion and requires explicit opt-in via `herdr_auto_tab_on_epic=true`.
2. **Plugin Delegation Contract:** Invoking `synlynk.cockpit.tab-epic` via `herdr plugin action invoke` is an idiomatic integration pattern for Herdr. While external action IDs can theoretically drift, the contract is insulated from fragility because synlynk core checks `herdr plugin list` and provides an automatic fallback to raw CLI commands (`herdr pane split/run`) if the plugin is absent or fails.
3. **Core vs. Plugin Scope Split:** Deferring the external `herdr-synlynk` repository build does not compromise the design. Core's raw fallback implementation relies on the established Sept-14 pane mechanics implemented directly within [`synlynk/cockpit.py`](file:///Users/nikhilsoman/dev/synlynk/.claude/worktrees/docs+claude+synlynk-com-platform-vision/synlynk/cockpit.py). Because core remains completely self-sufficient with raw pane commands, the external plugin remains an optional enhancement layer rather than a hidden dependency.
4. **Client Surface Consistency Scope:** Section 5 strikes the appropriate balance. Rather than introducing premature shared code or premature abstraction for only two distribution points (Herdr and VS Code), it establishes operational conventions (branding, framing, release-aligned versioning) and explicitly defers formal extraction until a third surface emerges (Rule of Three).

### Recommendation

**Approve.** The design cleanly decouples optional Herdr GUI and event integration from core CLI primitives, strictly preserves zero-dependency and fail-closed defaults for synlynk, and provides robust fallbacks across all execution gates.

### codex
[model=default; version=codex-cli 0.163.0]

The design is directionally sound, but the three-gate claim is slightly overstated. The gates prevent Herdr behavior in an unconfigured `synlynk` install: the feature defaults off, the binary is checked at call time, and plugin delegation requires an independently linked plugin. The tmux/terminal fallback is still behavior, but it occurs only after the user enables `herdr_cockpit`; it should be documented as an explicit consequence of enabling the feature, not as proof that no fallback runs without opt-in. The `worktree.created` hook is acceptably guarded by `herdr_auto_tab_on_epic=false`, but the contract should require the hook to fail closed when config is absent, malformed, or unreadable, and clarify whether merely linking a plugin authorizes event execution.

`herdr plugin action invoke` is a reasonable boundary, especially because it avoids a Python dependency and keeps richer behavior external. However, action IDs and argument shapes become an API contract. Core should specify a plugin compatibility/version check, stable namespaced action IDs, defined exit/error behavior, and fallback rules for unsupported plugin versions. Otherwise upgrades can silently break cockpit launch.

Deferring the plugin repository’s build is appropriate, but the raw pane sequence is not entirely “just fallback”: core now owns a second Herdr integration implementation and its compatibility surface. The spec should either define that sequence minimally as a tested compatibility baseline or narrow core to delegation plus a deliberately limited fallback.

The Client Surface Consistency section is acceptable at this stage because it is explicitly a convention, not shared infrastructure, and has a clear extraction trigger. It should remain lightweight and avoid implying governance or synchronized releases that do not yet exist.

**Recommendation: approve with revisions.** Require fail-closed event-hook semantics, an explicit plugin compatibility/version contract, and a clearer boundary around the raw pane fallback before implementation begins.

### grok
[model=default; version=grok 1.0.70 (f50904eaee6c) [stable]]

I'll read the Herdr customizations spec and the surrounding feature-resolution code so the four review questions are grounded in what the design actually commits to.The opt-in story holds for core and fails as stated for the plugin. `herdr_cockpit` with `default_enabled=False`, and a disabled path that only prints a hint, means a bare `pip install` runs no cockpit. The claim that three gates must all be true overreaches. Gate (a) is a router: with the feature on and Herdr absent, step 2 still spawns tmux or an OS terminal. That matches the v0.26.8 roadmap and is behavior the user requested by enabling the feature, but it is multiplexer behavior under a Herdr-named flag. Gate (c) is optional by design: the unlinked path runs `herdr pane split` from `cockpit.py`. On the plugin side the gates invert. Once `herdr plugin install` links `synlynk.cockpit`, Herdr invokes the `worktree.created` hook, the GitHub link handlers, and the sentinel notifier without reading `features.json`. The hook consults only `herdr_auto_tab_on_epic`. A false setting stops the suggestion, but the hook still runs, and a true setting can suggest a tab while `herdr_cockpit` is off. "Suggests" is undefined.

`herdr plugin action invoke synlynk.cockpit.tab-epic` is the right seam. It is Herdr's own extension surface, and core stays free of a plugin Python import. It is also an unpinned contract. Action ids, the `--arg` shape, and `herdr plugin list` parsing can drift, because section 5 says the two versions drift on purpose. Invoke failure has no specified recovery. The spec should name a stable action-id list, an interface version core checks, and a fall-through to the raw pane sequence when invoke fails.

Deferring the plugin repository is appropriate. Deferring the pane sequence is not. Step 3's unlinked path implements that sequence inside core, and the 2026-09-14 spec already designs the 2×2 layout. The plugin's `apply-4pane` and `tab-epic` would be a second copy. Own the layout in `cockpit.py` now, and limit the plugin to ambient behavior: the event hook, link handlers, and the sentinel notifier. That is the split the resolution order actually implements.

Section 5 is the right weight: a convention, no shared package, and extraction only when a third surface is specced. Fix the naming example. `synlynk-<surface>` and `herdr-synlynk` do not match.

**Approve with those amendments.** Core opt-in is real. The plugin must check `herdr_cockpit` and no-op the hook unless that flag and `herdr_auto_tab_on_epic` are both true. Pin the action contract and the invoke fallback. Keep client consistency as prose.

## Synthesis
Decision: Approve the design, with revisions required before implementation (not merge of the spec itself, which may already be committed as a proposal). All four panelists converge on the same substantive shape: the architectural split (thin core + optional plugin) is sound and the opt-in defaults are real, but the spec currently overstates how clean and gap-free the three-gate story is, and three concrete fixes must land before build starts:

1. **Gate precision.** The "no Herdr behavior without opt-in" claim needs qualification, not retraction. The tmux/terminal fallback is correctly gated behind `herdr_cockpit` being enabled — that's consented-to multiplexer behavior, not a leak, but the doc should say so explicitly rather than implying only Herdr-specific actions are gated. The real gap is on the plugin side: once `herdr-synlynk` is linked, its `worktree.created` hook executes unconditionally (reads config, checks `herdr_auto_tab_on_epic`) — only its *effect* is gated, not its execution. Spec must state this plainly and require the hook fail closed on missing/malformed config.

2. **Plugin contract hardening.** `herdr plugin action invoke` is the right seam (keeps core free of a plugin dependency), but it's currently an unversioned, string-keyed contract. Add a minimal compatibility check (interface version, stable namespaced action IDs) and an explicit, documented fallback/error path when invoke fails or drifts — silent fall-through to raw pane sequence on a version mismatch must be a named, accepted behavior, not an undiscovered one.

3. **Name the fallback duplication honestly.** Core's raw pane-split fallback is not merely "deferred scope" — it's a second implementation of the plugin's `apply-4pane`/`tab-epic` logic, inlined into `cockpit.py`. The spec should reframe this as intentional duplication for core self-sufficiency, not as proof the split avoided designing that logic.

Section 5 (Client Surface Consistency) is approved as-is — right-sized convention for two data points, with a sound extraction trigger; only the `synlynk-<surface>` naming example (inconsistent with `herdr-synlynk`) needs a one-line fix.

None of this blocks approval — all four reviewers land on approve/approve-with-revisions, and the required edits are documentation/precision fixes, not redesigns.

## Decision
Decision: Approve the design, with revisions required before implementation (not merge of the spec itself, which may already be committed as a proposal). All four panelists converge on the same substantive shape: the architectural split (thin core + optional plugin) is sound and the opt-in defaults are real, but the spec currently overstates how clean and gap-free the three-gate story is, and three concrete fixes must land before build starts:

> Signatures: see 2026-10-31-review-and-approve-reject-the-herdr-cust.json
