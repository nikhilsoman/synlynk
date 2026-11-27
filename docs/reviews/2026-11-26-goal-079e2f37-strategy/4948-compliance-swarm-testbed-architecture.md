# #4948 — Compliance, swarm, and testbed architecture

## Question

Decide whether compliance, swarm management, and the acceptance/soak testbed should extend the monorepo or move into a dedicated sister project.

## Verdict

**Derived from the recorded synthesis.** Keep compliance and the commit-pinned acceptance testbed in the monorepo, but isolate the testbed from default CI, installation, release artifacts, credentials, and the compliance-audited surface. Defer extraction until the swarm module requires a non-stdlib dependency or an independent release cadence, and only after the state and status contracts are versioned.

## Findings

### Recorded panel synthesis (verbatim)

> ## Synthesis
>
> **Where the panel agrees.** All three want a hard boundary between compliance-scoped code and experimental code. All three want shared contracts and an explicit path for graduating or extracting things. The disagreement is only about timing and location: claude says extend the monorepo behind boundaries, while agy and codex say start a sister repo now.
>
> **Why I'm not going with the 2-to-1 majority.**
>
> - **The testbed isn't frontier agent research.** agy's and codex's arguments assume it is: speculative API privileges, "unsafe-to-production experiments", volatile tool definitions. The committed spec (`2026-09-20-automated-acceptance-testbed-design.md`) describes OrbStack VMs and Docker running acceptance and multi-node soak tests against the CLI. A test rig has to be pinned to the exact commit under test, and a sister repo makes that harder, not easier.
> - **Their mechanism doesn't exist yet.** Both proposals lean on "versioned, immutable packages" and "contract-verified promotion gates". synlynk is a single stdlib-only file with no package boundary. The `state.db` schema and the `synlynk status --json` contract are still moving. A sister repo now means a second release train, more Workspace Map edges and a second blog and PR cycle. It would sit on contracts we can't yet version, and the fleet is already strained by stacked-PR proliferation and worktree cleanup.
> - **The compliance argument cuts the other way for identity and audit.** Attribution, `policy.json`, merge authority and the `state.db` audit trail (W2-T1.4 just landed) must live next to the thing they audit. Splitting them out creates the drift that makes an audit fail.
> - **The one valid worry is compliance scope creep.** The `conn.commit()` incident, where CI went from 90s to 32 minutes, shows why soak workloads must not share the default path. That calls for isolation inside the repo, not a separate repo.
>
> **What we take from agy and codex.** The testbed and any swarm experiments get their own directory, an opt-in entry point and a nightly or manual trigger. They are excluded from the default CI path and from the `install.sh` and release artifact. They use separate credentials, and their code does not enter the compliance-audited surface. Anything promoted from the testbed into core goes through the normal PR and review gates.
>
> **Swarm control plane.** It stays a bounded module behind a versioned interface. `synlynk swarm dispatch` remains the thin client. The heavy orchestration side is the only real candidate for extraction.
>
> Decision: Extend the synlynk monorepo instead of creating a dedicated sister swarm project now. Compliance (identity, audit, policy, merge authority) stays in core alongside `state.db` and `policy.json`. The acceptance and soak testbed goes in an isolated, opt-in directory that is version-locked to the CLI commit under test. That directory is kept out of default CI and out of shipped artifacts, and uses separate credentials. The swarm control plane is built as a bounded module behind a versioned interface. Extraction into a sister project is deferred and governed by two explicit criteria, which the testbed spec must record: the swarm module needs a non-stdlib dependency, or it must ship on a different release cadence from the CLI. Meeting either trigger reopens this decision, and no extraction happens before the `state.db` schema and `status --json` contract are versioned.
>
> If you want this recorded, I can run `synlynk decide` and add the extraction criteria to the testbed spec. That spec currently has uncommitted changes on `main`, so that work would go on a branch.

## Recommended follow-ups

- **New ticket: No. Proposed title:** “Record testbed isolation and extraction triggers in the accepted testbed spec.” Update the existing spec/issue rather than duplicate it.
- **New ticket: Yes. Proposed title:** “Exclude testbed and swarm experiments from default CI and release artifacts.”
- **New ticket: Yes. Proposed title:** “Version state.db and status JSON contracts before swarm extraction.”

## Sources

- [GitHub issue #4948](https://github.com/nikhilsoman/synlynk/issues/4948)
- `docs/superpowers/specs/2026-09-20-automated-acceptance-testbed-design.md`
- `docs/reviews/2026-10-16-frontier-lab-architecture-review.md`
