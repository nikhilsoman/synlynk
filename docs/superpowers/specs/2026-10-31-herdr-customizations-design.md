# Herdr Customizations — Design Specification

**Date:** 2026-10-31
**Status:** Draft, pending DECIDE panel review
**Relates to:** `docs/superpowers/specs/2026-09-14-synlynk-cockpit-herdr-orchestration.md` (predecessor — component split superseded below), `docs/superpowers/specs/2026-10-31-configurability-framework-design.md` (registration), `project-docs/roadmap.md` v0.26.8 ("`synlynk herdr tab <epic>`... graceful fallback to spawning a tmux/terminal window when `HERDR_ENV != 1`")

## 1. Problem

v0.26.8 calls for launching each epic in a dedicated Herdr tab with an isolated 4-pane cockpit, with a tmux/terminal fallback when Herdr isn't the active environment. The Sept-14 predecessor doc already specified the pane mechanics (`synlynk herdr init`, `synlynk dispatch --pane`) but assumed Herdr as the only possible backend and did not address packaging or opt-in.

Terminal and multiplexer choice is highly personal. This feature must not impose any Herdr-related dependency, process, or behavior on a user who hasn't explicitly opted in — not even indirectly through `pip install synlynk` pulling in Herdr-flavored code paths that run by default.

Research into Herdr's actual extension surface (its `herdr-plugin.toml` manifest system — `[[actions]]`, `[[events]]`, `[[panes]]`, `[[link_handlers]]` — and its community marketplace of GitHub repos tagged `herdr-plugin`) changes what's possible here: the richer "body" synlynk could have inside Herdr doesn't need to live inside synlynk's own pip package at all.

## 2. Two-artifact split

- **Core** (ships inside the `synlynk` pip package): `synlynk/cockpit.py` + the `synlynk herdr` CLI group (`init`, `tab <epic>`). Zero new dependencies. Does nothing unless explicitly enabled.
- **Plugin** (`herdr-synlynk`, a separate GitHub repository tagged `herdr-plugin`, installed independently via `herdr plugin install synlynk-dev/herdr-synlynk`): carries the richer pane-layout actions, an event hook, link handlers, and a sentinel-alert notifier. Never touches synlynk's pip install surface.

This split is what makes the opt-in requirement structural rather than a policy promise: three independent gates must all be true before any Herdr-specific behavior runs — (a) the `herdr` binary is installed by the user, (b) the `herdr_cockpit` feature is explicitly enabled in synlynk's own settings, (c) for the richer version, the plugin has been separately `herdr plugin install`'d. No terminal/multiplexer opinion is baked into a bare `pip install synlynk`.

**Precision on what these gates actually cover (DECIDE panel, 2026-10-31):** the tmux/terminal fallback in Section 3 *is* gated behind `herdr_cockpit` being enabled — a user who never enables the feature never gets a spawned terminal window either, so this is consented-to multiplexer behavior, not a leak. The one real gap is on the plugin side: once `herdr-synlynk` is linked, its `worktree.created` event hook (Section 4) *executes* unconditionally the moment a worktree is created — only its *effect* (suggesting a cockpit tab) is gated by `herdr_auto_tab_on_epic`. The hook always runs, reads `.synlynk/config.json`, and must fail closed (no suggestion, no error surfaced to the user) on missing or malformed config, rather than assuming the setting is present.

## 3. Core side — Configurability Framework registration, CLI, fallback

```python
FeatureSpec(
    name="herdr_cockpit",
    extra_name=None,
    import_probe=lambda: True,
    default_enabled=False,
)
```

`extra_name=None` because there is no non-stdlib Python dependency to gate — Herdr is an external CLI binary, not a pip package. The Configurability Framework's Layer 1 is scoped to dependency *presence*, not code stripping (an explicit Framework non-goal), so inventing a fake extra here would misuse Layer 1's semantics rather than honor the opt-in requirement. Presence of the `herdr` binary itself is checked at call time via `shutil.which("herdr")`, not at import time — a missing binary is never a reason to block synlynk from loading.

Settings: `herdr_pane_layout` (string, default `"4pane"` — room for future presets), `herdr_auto_tab_on_epic` (bool, default `false` — epic-start auto-launch stays opt-in even when the feature itself is enabled).

`synlynk herdr init` / `synlynk herdr tab <epic>` resolve in this order:

1. **Feature disabled** → print the one-line enable hint, exit 0. (Fail-closed, consistent with the Framework's convention.)
2. **Feature enabled, but `HERDR_ENV != 1` or `herdr` missing** → **tmux/terminal fallback**: spawn a plain `tmux new-session` (or OS terminal window) running the same conductor command, with no pane orchestration. This is the roadmap's explicit requirement. It is a degraded path, not a parallel backend — it never attempts multi-pane layout.
3. **Feature enabled, Herdr live** → check `herdr plugin list` for `synlynk.cockpit` linked.
   - If linked: delegate via `herdr plugin action invoke synlynk.cockpit.tab-epic --arg epic=<epic>`.
   - If not linked: fall back to the raw `herdr pane split`/`herdr pane run` sequence from the Sept-14 doc, directly from `cockpit.py`. **This is intentional duplication, not deferred scope** (DECIDE panel, 2026-10-31): `cockpit.py`'s raw pane-sequence path reimplements the same `apply-4pane`/`tab-epic` logic the plugin's actions provide, so that `herdr_cockpit` is fully usable without ever installing the plugin. The plugin is an enhancement layer (events, link handlers, notifier), not core's only path to a working cockpit.

**Plugin contract hardening (DECIDE panel, 2026-10-31):** `herdr plugin action invoke` is an unversioned, string-keyed contract against an independently-versioned external repo — core must not assume `synlynk.cockpit.tab-epic` exists or behaves as expected just because `herdr plugin list` shows it linked. Before delegating, core checks a minimal compatibility marker (an `interface_version` the plugin's manifest or a dedicated `synlynk.cockpit.version` action reports) against a version core knows how to speak to. On a missing/mismatched version, or on the invoke call itself failing, core falls through to its own raw pane-sequence path and logs a one-line notice naming the mismatch — this fallback is a named, documented behavior, not a silent catch-all.

## 4. Plugin side — `herdr-synlynk` repository

`herdr-plugin.toml` sketch:

- `id = "synlynk.cockpit"`
- `[[actions]]`: `apply-4pane` (applies the Sept-14 4-pane split to the current tab), `tab-epic` (opens a new tab named `synlynk/<project>`, applies the split, labels panes per the existing Herdr Workspace Protocol naming convention).
- `[[events]] on = "worktree.created"`: a hook script that reads `.synlynk/config.json` for `herdr_auto_tab_on_epic`. If and only if that setting is `true`, it *suggests* (never force-opens) a cockpit tab for the new worktree. The hook itself — not the manifest — is responsible for checking this setting, since the Herdr event system has no native concept of a downstream tool's own config.
- `[[link_handlers]]`: routes GitHub issue/PR URLs appearing in pane output through the existing `~/.synlynk/gh-shim`.
- A notifier action that tails `.synlynk/sentinel.md` and raises a Herdr toast/pane on new `FLATLINE`/`QUOTA_EXHAUSTED` alerts, closing the gap where these alerts currently require a human to notice the file.

The plugin repo is planned and built as its own small project once this spec and the core half are approved — it does not block the Design → Plan → Build gate for synlynk core itself.

## 5. Client Surface Consistency

synlynk now has two independent marketplace-style distribution surfaces for thin client integrations: the Herdr plugin marketplace (this doc) and the VS Code Marketplace + Open VSX Registry (`clients/vscode/`, spec'd in `docs/superpowers/specs/2026-10-18-vscode-extension-design.md`, built, CI-wired for both registries, not yet published — roadmap v0.27.0, target 2026-11-01). A third (e.g. a JetBrains or other IDE plugin) is plausible per the harness-independence thread (gh:#2126).

Rather than build shared tooling for two data points, this establishes a lightweight **convention**, not code, that both surfaces follow:

- **Branding:** consistent icon derived from the same source asset as `clients/vscode/media/synlynk-icon.svg`; consistent naming pattern per registry convention (e.g. `synlynk-vscode` on the VS Code/Open VSX side, where `synlynk-<surface>` is the house style; `herdr-synlynk` on the Herdr marketplace side, where Herdr's own `herdr-<provider>` convention takes precedence — both still read unambiguously as synlynk's) (fixed per DECIDE panel, 2026-10-31: the prior wording implied a single `synlynk-<surface>` pattern inconsistent with `herdr-synlynk` itself); consistent publisher/owner identity (`synlynk` where the registry allows a reserved publisher name, `synlynk-dev` as the GitHub org otherwise).
- **Framing:** every listing's description states the same "thin client, zero required production dependencies, shells out to the local `synlynk` CLI" framing — this is true of both the VS Code extension and the Herdr plugin, and should read the same way in both.
- **Version alignment:** each surface's published version tracks the synlynk Named Release it ships alongside, noted in that surface's own changelog, not synced as a hard version-number match (the two will drift — a plugin bugfix doesn't need a synlynk core bump and vice versa).
- **Extraction trigger:** when a third client surface is specced, extract this section into its own `docs/superpowers/specs/<date>-client-surface-conventions.md` and have all three surfaces' specs reference it instead of repeating it inline.

## 6. Testing

Core: mock `shutil.which`, `HERDR_ENV`, and feature-enabled state; cover the 2×2×2 matrix (feature enabled/disabled × herdr present/absent × plugin linked/unlinked) and assert the correct one of {hint, tmux fallback, plugin delegate, raw pane sequence} fires. `herdr_auto_tab_on_epic` defaulting to `false` even when `herdr_cockpit` is enabled is its own explicit test case. Additional cases per the DECIDE panel (2026-10-31): plugin-linked-but-version-mismatched falls through to the raw pane sequence with a logged notice, not a silent no-op; and plugin-linked-but-invoke-raises behaves identically.

Plugin repo: own test suite (manifest validation, action scripts), out of scope for this document beyond noting it exists, with one exception the panel flagged as core-relevant: the `worktree.created` hook's fail-closed behavior on missing/malformed `.synlynk/config.json` (hook executes, reads config, finds nothing usable, suggests nothing — no error surfaced) must be tested, since the hook always runs once linked regardless of `herdr_auto_tab_on_epic`.

## 7. Out of scope

Pane-layout presets beyond `4pane`; the notifier's exact toast API (depends on Herdr's socket API, to be nailed down when the plugin repo is actually built); auto-detection of multiplexers other than Herdr (the tmux fallback here is strictly "no cockpit," never a second orchestrated backend); the cross-surface convention's eventual extraction document (deferred until a third surface exists, per Section 5).
