<!-- generated - source of truth is state.db -->
---
decision_id: dec-264bd6e3
topic: "How should Synlynk fix role-scoped GitHub egress for a Codex home conductor (gh:#2096) given that codex-cli 0.163.0 ignores file sandbox_mode?"
date: 2026-10-22
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
How should Synlynk fix role-scoped GitHub egress for a Codex home conductor (gh:#2096) given that codex-cli 0.163.0 ignores file sandbox_mode?

## Panel Inputs

### claude
Member transcript was not retained. `synlynk decide` without `--record` prints only the synthesis. Word count from that run is below. The panel was convened 2026-10-22 from the Grok home-conductor session and was not run again for this record.

328 words.

### agy
Member transcript was not retained. `synlynk decide` without `--record` prints only the synthesis. Word count from that run is below. The panel was convened 2026-10-22 from the Grok home-conductor session and was not run again for this record.

370 words.

### codex
Member transcript was not retained. `synlynk decide` without `--record` prints only the synthesis. Word count from that run is below. The panel was convened 2026-10-22 from the Grok home-conductor session and was not run again for this record.

293 words.

### grok
Member transcript was not retained. `synlynk decide` without `--record` prints only the synthesis. Word count from that run is below. The panel was convened 2026-10-22 from the Grok home-conductor session and was not run again for this record.

414 words.

### conductor
Conductor correction, recorded with the panel text and not part of the synthesis: on codex-cli 0.163.0 the tested proxy schema is `[features.network_proxy]` `enabled = true` and `domains = { "api.github.com" = "allow", "github.com" = "allow" }`. The key `features.network_proxy.allowed_domains` was not tested. The `-c` profile was proven with `codex sandbox`, not with an interactive `codex` session. The recorder stores status `approved` for every decision row; this panel authorized a design spec only.

## Synthesis
Decision: Adopt launch-time explicit `-c` overrides as the fix for role-scoped GitHub egress on the Codex home conductor — start the interactive `codex` process (Synlynk's home-conductor launch path, not `codex sandbox` and not `config.toml`) with `sandbox_mode=workspace-write`, `approval_policy=on-request`, `sandbox_workspace_write.network_access=true`, `features.network_proxy.enabled=true`, and `features.network_proxy.allowed_domains=["api.github.com","github.com"]`, with no `writable_roots`. This is the only profile verified to survive the confirmed upstream gap (openai/codex#36448: `codex sandbox` silently ignores file `sandbox_mode`, so `config.toml`-only persistence is not viable on 0.163.0). Treat the inner dispatched `codex exec` path, review workers' `writable_roots=[]`, and the canonical state-db's fail-closed non-writable behavior as unchanged and out of scope. Before any code change: (1) retest this exact flag set against the real interactive `codex`/`codex exec` TUI path (not `codex sandbox`), since fact 4 only proves it against the `sandbox` subcommand; (2) test the untested domains (`codeload.github.com`, `uploads.github.com`, `objects.githubusercontent.com`) needed for real GitHub operations beyond API reads; (3) validate token-free via the established checks (`synlynk gh --role pm issue view 2096` succeeds, `curl -I https://example.com` gets proxy 403, raw TCP to `1.1.1.1:443` and localhost bind both fail). The next step is design-only: write a spec in `docs/superpowers/specs/` defining the home-conductor launch argv contract, explicit non-goals (no danger-full-access, no personal token/host-auth opt-in, no state-dir writable root, review workers unchanged), and this verification matrix — committed and signed off before any implementation ticket is opened. Per-command approved escalation (panelists' "approach 1/2" variants) is the acceptable fallback procedure while that spec is pending, not a competing long-term fix. No implementation is authorized by this decision.

## Decision
Decision: Adopt launch-time explicit `-c` overrides as the fix for role-scoped GitHub egress on the Codex home conductor — start the interactive `codex` process (Synlynk's home-conductor launch path, not `codex sandbox` and not `config.toml`) with `sandbox_mode=workspace-write`, `approval_policy=on-request`, `sandbox_workspace_write.network_access=true`, `features.network_proxy.enabled=true`, and `features.network_proxy.allowed_domains=["api.github.com","github.com"]`, with no `writable_roots`. This is the only profile verified to survive the confirmed upstream gap (openai/codex#36448: `codex sandbox` silently ignores file `sandbox_mode`, so `config.toml`-only persistence is not viable on 0.163.0). Treat the inner dispatched `codex exec` path, review workers' `writable_roots=[]`, and the canonical state-db's fail-closed non-writable behavior as unchanged and out of scope. Before any code change: (1) retest this exact flag set against the real interactive `codex`/`codex exec` TUI path (not `codex sandbox`), since fact 4 only proves it against the `sandbox` subcommand; (2) test the untested domains (`codeload.github.com`, `uploads.github.com`, `objects.githubusercontent.com`) needed for real GitHub operations beyond API reads; (3) validate token-free via the established checks (`synlynk gh --role pm issue view 2096` succeeds, `curl -I https://example.com` gets proxy 403, raw TCP to `1.1.1.1:443` and localhost bind both fail). The next step is design-only: write a spec in `docs/superpowers/specs/` defining the home-conductor launch argv contract, explicit non-goals (no danger-full-access, no personal token/host-auth opt-in, no state-dir writable root, review workers unchanged), and this verification matrix — committed and signed off before any implementation ticket is opened. Per-command approved escalation (panelists' "approach 1/2" variants) is the acceptable fallback procedure while that spec is pending, not a competing long-term fix. No implementation is authorized by this decision.

Conductor correction, recorded with the panel text and not part of the synthesis: on codex-cli 0.163.0 the tested proxy schema is `[features.network_proxy]` `enabled = true` and `domains = { "api.github.com" = "allow", "github.com" = "allow" }`. The key `features.network_proxy.allowed_domains` was not tested. The `-c` profile was proven with `codex sandbox`, not with an interactive `codex` session. The recorder stores status `approved` for every decision row; this panel authorized a design spec only.

> Signatures: see 2026-10-22-how-should-synlynk-fix-role-scoped-githu.json
