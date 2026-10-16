# CLI Core/Packs Split — Design Spec

**gh:#1927** — "Roadmap: CLI core/packs split — ~15-command core, rest become optional packs (architecture #8)"

## Glossary (read this first — "pack" is overloaded)

synlynk already uses "pack" for two unrelated concepts. This design adds a third, deliberately, as the
seed of a broader extension-point system:

| Term | Meaning | Status |
|---|---|---|
| `synlynk pack` (singular, existing) | `synlynk/pack.py` — AST-based context-pack generator for feeding a task's relevant code into a dispatch prompt | Unrelated. Unchanged by this design. |
| `synlynk/packs/*.yaml` (existing) | Fleet role-template bundles (`studio.yaml`, `agency.yaml`, `software-product.yaml`) — defines role types like director/production/qa for a fleet | Unrelated today. May later become an instance of the new contract (see Future Work, `synlynk.packs.agent`). Unchanged by this design. |
| **`synlynk packs`** (plural, new) | The new extension-point mechanism this spec defines: discoverable, optionally-loaded command bundles (Vizor, marketing, media, mesh, relay, swarm) | **New. This design.** |

Going forward, "pack" with no qualifier means the new plural concept. The two existing singular/YAML
uses are called out explicitly whenever there's ambiguity.

## Context

Architecture roadmap item #8 (`docs/strategy/2026-10-02-decide-panel-roadmap.md` §1, row 8) calls for
splitting the CLI into a ~15-command, 15-20K LOC core, with the rest moved to optional packs. The
issue's own text gates this on adoption metrics existing first; that gate was explicitly waived by the
project owner on 2026-10-10 (single-operator dogfood repo; the instrumentation needed to compute the
metrics — `onboarding_sessions`, CLI-invocation logging — doesn't exist or is empty).

Investigation during brainstorming found two facts that reshape the usual rationale for this kind of
split:

1. **Zero third-party runtime dependencies** (`pyproject.toml`: `dependencies = []`, pure stdlib). The
   typical "isolate heavy deps" motivation for a packs split doesn't apply.
2. **Cold-start lazy-importing is already shipped** (gh:#1929) — `cli.py` only imports stdlib at module
   scope; every domain module is imported inside its handler function. The typical "reduce import cost"
   motivation is already mostly captured.

The actual motivation, confirmed with the project owner: **lay groundwork for a future plugin
ecosystem**, not install-footprint or cold-start reduction. The owner's long-term vision for "packs"
spans ten categories far broader than CLI commands (new harness/model backends, IDE/terminal
integrations, workflow templates, workspace-agent charters, domain tool integrations, RAG/context data
bundles, Tokq context/work packs, infra-as-code templates, security packs). Several of those depend on
subsystems that don't exist yet (Tokq) or are unrelated engineering efforts (new harness backends). Per
the brainstorming rule to decompose oversized requests, **this spec scopes to one generic contract plus
one fully-built instance** — CLI-command packs, which is what gh:#1927 literally asks for — and defers
the other nine categories to a roadmap note.

Authorship scope: **us only, for now.** This design does not build sandboxing, a pack registry/manifest,
or version-compatibility pinning for untrusted third-party pack code. It builds a real, stable discovery
contract (entry points) so third-party authorship isn't foreclosed later, but the only packs that exist
after this work are ones we write ourselves.

## The Pack contract

A minimal protocol, generic enough to host all ten future categories without redesign:

```python
# synlynk/extensions.py (new module)

from typing import Protocol, Any

class Pack(Protocol):
    name: str
    pack_type: str  # "cli" today; "harness", "workflow", "agent", ... later

    def register(self, target: Any) -> None:
        """Register this pack's capabilities onto `target`.

        `target`'s type depends on `pack_type`: for "cli" packs, an
        argparse subparsers object. Future pack types define their own
        target shape when they're built.
        """
        ...
```

Discovery uses Python's standard `importlib.metadata.entry_points`, namespaced per pack type:

```python
from importlib.metadata import entry_points

def discover_packs(pack_type: str) -> list[Pack]:
    return [ep.load() for ep in entry_points(group=f"synlynk.packs.{pack_type}")]
```

Namespacing by `pack_type` (`synlynk.packs.cli`, later `synlynk.packs.harness`, `synlynk.packs.workflow`,
etc.) is the one design decision made now specifically so future categories slot into the same contract
without touching this module.

## Scope: CLI-command packs only

This spec implements `pack_type="cli"` only.

**Core stays hardcoded in `cli.py`** — the ~15-20 commands the roadmap names as core (`init`, `dispatch`,
`jobs`, `logs`, `review`, `merge`, `status`, `cost`, `route`, `local`, `doctor`, plus a handful more
identified during the classification pass below). These are registered exactly as today: direct
`add_parser` calls, no discovery indirection. Core commands are the synlynk team's own, always-installed,
never-optional surface.

**Six named subsystems become the first CLI packs**: Vizor, marketing, media, mesh, relay, swarm (~4,800
LOC total, per issue). Each becomes a `synlynk/packs_cli/<name>.py` module exposing a `Pack`-conforming
object, registered via `pyproject.toml`:

```toml
[project.entry-points."synlynk.packs.cli"]
vizor = "synlynk.packs_cli.vizor:pack"
marketing = "synlynk.packs_cli.marketing:pack"
media = "synlynk.packs_cli.media:pack"
mesh = "synlynk.packs_cli.mesh:pack"
relay = "synlynk.packs_cli.relay:pack"
swarm = "synlynk.packs_cli.swarm:pack"
```

`cli.py`'s subparser-building code replaces its direct imports/registration of these six subsystems with
a `discover_packs("cli")` loop that calls `.register(subparsers)` on each. Everything still ships in the
single `synlynk` wheel — entry points declared in the same package's `pyproject.toml`, not separate
distributions. The benefit delivered now is the discovery contract and decoupling `cli.py` from needing
direct knowledge of every pack module, not a smaller install. Separate distributable packages (true
install-footprint reduction) is a distinct future step, intentionally not taken here — the cost (release
pipeline, versioning matrix, multi-package CI) isn't justified without actual external demand.

**New CLI surface:** `synlynk packs list` (shows registered packs, their `pack_type`, and the commands
each contributes) and `synlynk packs info <name>` (shows a pack's source module and registered command
names). No enable/disable mechanism in this pass — all discovered packs are always active, matching
today's behavior where all code ships and runs unconditionally. Enable/disable is natural future work
once there's a reason to want a pack off (see Future Work).

## Classifying the remaining LOC

The issue's six named subsystems total ~4,800 LOC. The package is ~89,700 LOC across 229 files, and the
roadmap's core target is 15-20K LOC — meaning roughly 65-70K LOC beyond the six named subsystems needs a
classification decision this spec does not make module-by-module. Doing that by hand across 229 files in
a design doc would produce exactly the kind of stale, unreviewed table this project's own memory warns
against (hand-authored capability/routing tables going stale — see the Empirical Capability Assessment
Policy's rationale for distrusting hand-curated classification).

Instead, this spec fixes the **methodology**, and treats full classification as implementation-plan work:

- A module is a **core dependency** if at least one of the ~15-20 core commands directly imports it, or
  it implements infrastructure that core commands rely on regardless of pack boundaries (state.db access,
  policy enforcement, dispatch orchestration, cost tracking, the taxonomy/help system).
- A module is a **pack candidate** if no core command depends on it and its only callers are commands
  outside the core list.
- Modules that are candidates but don't cleanly fit one of the six named subsystems get grouped into new
  packs by cohesion (what calls what), not forced into an existing pack just to avoid creating a seventh.

The actual run of this classification — a static import-graph pass over all 229 files proposing a
core/pack assignment, followed by human review of the proposal — is Task 1 of the implementation plan,
not performed here. This spec's job is the mechanism; the plan's job is applying it.

## Compatibility

Zero user-facing behavior change. Every existing command name, flag, and output stays identical — this
is an internal registration-mechanism refactor. `pip install synlynk` still installs the entire package.
Existing scripts, CI jobs, and docs that invoke `synlynk <command>` are unaffected, including for the six
subsystems moving to the new pack mechanism.

## Testing

- Unit tests for `discover_packs()` and the `Pack` protocol, using mocked `entry_points()` results (no
  real package installation needed in tests).
- One integration test registering a minimal fake pack via a test-local entry point and confirming its
  command surfaces correctly through `cli.py`'s parser.
- Regression tests confirming each of the six named packs (Vizor, marketing, media, mesh, relay, swarm)
  still registers and its commands still run correctly after migration off direct imports.

## Future work (not designed here)

The owner's broader vision names nine more pack categories. Each becomes a future `synlynk.packs.<type>`
entry-point group under the same `Pack` contract, designed and built separately when its underlying
subsystem is ready — not speculatively designed now:

| Future `pack_type` | Category | Notes |
|---|---|---|
| `harness` | New harness/model backends | New execution backend, not a CLI command bundle |
| `environment` | IDE/terminal integrations (Herdr-style multiplexers) | |
| `workflow` | Industry/domain workflow templates | |
| `agent` | Workspace-agent packs with their own charters | Likely eventual consolidation point with existing `synlynk/packs/*.yaml` fleet templates |
| `tool` | Domain-specific 3rd-party tool/library integrations | Likely eventual consolidation point with existing `synlynk/addon.py` `ADDON_BUNDLES` |
| `data` | RAG/context data bundles | |
| `tokq_context` | Tokq context packs | Blocked on Tokq itself existing (not yet built, per project memory `tokq-bridge.md`) |
| `tokq_work` | Tokq work packs (remote task execution on other synlynk users' environments) | Blocked on Tokq; also a distinct security/trust-boundary design problem (executing on someone else's environment) |
| `infra` | GPU/CPU/IaC templates | |
| `security` | Security packs | |

Also deferred: enable/disable of individual packs, separate-distribution packaging (`synlynk-vizor` as
its own pip package), and any sandboxing/manifest/version-pinning needed once third parties actually
author packs. None of these are needed for the CLI-command-pack instance this spec builds, and building
them now would be speculative.
