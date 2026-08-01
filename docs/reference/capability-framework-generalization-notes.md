# Capability Framework — Generalization Notes (v2 signals)

**Status:** Living notes, not a spec. Seeded 2026-07-31 during the Harness Capability Drift & Regression Classification brainstorm (`docs/superpowers/specs/2026-07-31-harness-capability-drift-regression-classification-design.md`).

Purpose: collect directional signals for applying the probe → classify → matrix pattern (built for AI-harness compatibility) to other concerns, without committing any of them to a spec until they're actually needed. Add a bullet when a signal comes up; don't feel obligated to act on anything here.

## Signals collected so far

- **Community capability feed.** The harness-capability-matrix data (which CLI version of Claude/Agy/Grok/Codex supports which capability) is the same fact for every synlynk install — re-probing it independently per user is redundant. A read-only, opt-in, hosted snapshot that installs pull to pre-seed/cross-check local probes could reduce that redundancy. Explicitly *not* the same thing as centralizing regression classification or smoke tests (those are repo-specific and require local credentials/context to mean anything) — this would be data-only, no accounts, no service the rest of synlynk depends on.

- **Notification/engagement layer on top of a future feed.** Raised alongside the capability-feed idea: email signup for capability-drift alerts, GitHub-star-based community engagement. This is a product/growth decision, not a technical extension of the probe/classify/matrix pattern — noted here so it isn't lost, but it doesn't belong in any harness-compatibility spec.

- **MCP server / IDE integration compatibility.** Open question: as synlynk's surface grows beyond wrapping CLI harnesses (e.g. if it starts talking to MCP servers or IDE extensions directly), does the same probe/classify/matrix pattern apply there too? Not evaluated yet — just flagged as a plausible future application of the same architecture.

## Non-signal (explicitly considered and rejected)

- **Synlynk-run centralized service for regression classification or smoke tests.** Rejected during the 2026-07-31 brainstorm — would require holding user GitHub credentials or testing something too generic to catch repo-specific regressions. See the Discussion section of the design doc above for full reasoning. Not expected to be revisited unless the project's local-first constraint itself changes.
