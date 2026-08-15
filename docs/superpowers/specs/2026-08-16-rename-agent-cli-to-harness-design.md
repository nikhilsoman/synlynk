# Rename `synlynk agent` CLI group to `synlynk harness` — Design

**Status:** Approved (via `synlynk decide --panel claude,agy,codex,grok --record`, see `project-docs/decisions/2026-08-16-synlynk-s-cli-has-a-naming-collision-syn.md`)
**Author:** Claude (PM/design role)
**Scope:** Standalone `chore/rename-agent-cli-to-harness` PR, shipped ahead of Task #97 (Phase 1 agent-roles-charters CLI)

## 1. Problem

`docs/glossary-agent-vs-harness.md` already defines the project's terminology:

- **Agent** — a persistent role identity with a charter (pm, architect, tpm, dev, designer, qa, marketing, synlynk-bot, and now workspace agents backed by `synlynk/agent_store.py` from PR #988).
- **Harness** — a swappable execution backend (Claude, Agy, Grok, Codex, local) that runs a dispatched task.

The CLI does not follow this split. `synlynk/cli.py` defines a top-level `agent` subcommand group (lines 467–481) whose four actions — `add`, `configure`, `run`, `list` — all mean *harness*, not *agent*:

```python
agent_parser = subparsers.add_parser("agent", help="Manage and run autopilot agents")
agent_sub = agent_parser.add_subparsers(dest="agent_action")
agent_add_parser = agent_sub.add_parser("add", help="Retrofit an on-PATH agent into this project")
agent_add_parser.add_argument("name", help="Agent binary name on PATH")
agent_configure_parser = agent_sub.add_parser("configure", help="Interactively write .agents/<name>.json context profile")
agent_configure_parser.add_argument("name", help="Agent name: claude, agy, codex, grok")
agent_run_parser = agent_sub.add_parser("run", help="Run a named agent once")
agent_run_parser.add_argument("name", help="Agent name (matches .agents/<name>.json)")
agent_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="Collect signals and print findings; no dispatch/issue/PR")
agent_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron", help="Install local crontab entry for this agent")
agent_sub.add_parser("list", help="List .agents/ configs and last run status")
```

Dispatch logic (lines 1297–1311):

```python
elif args.command == "agent":
    action = getattr(args, "agent_action", None)
    if action == "add":
        cmd_agent_add(args.name)
    elif action == "configure":
        cmd_agent_configure(args.name)
    elif action == "run":
        cmd_agent_run(
            args.name,
            dry_run=getattr(args, "dry_run", False),
            install_cron=getattr(args, "install_cron", False),
        )
    elif action == "list":
        cmd_agent_list()
    else:
        help_parsers.get("agent", parser).print_help()
```

`add`/`configure`/`run`/`list` retrofit an on-PATH CLI binary (claude/agy/codex/grok) into a project, write `.agents/<name>.json` context profiles, and run the Support Engineer's signal-collection loop against `.agents/` configs. Every one of these is harness/execution-backend management, matching the glossary's "Harness" definition exactly.

Task #97 needs to add `synlynk agent init/list/show/edit/disable` for the new durable role-identity records backed by `synlynk/agent_store.py` (workspace-level charter/memory/SoR storage, `register_agent()`, `regenerate_agent_projection()`). Building that on top of the existing `agent` group would collide: `synlynk agent list` would need to mean two unrelated things (list `.agents/*.json` harness configs vs. list registered role-identity agents), and `synlynk agent run <name>` (Support Engineer signal loop) has no analogue in the new group at all.

## 2. Decision

Per the unanimous 4-panel `synlynk decide` outcome:

1. Rename `synlynk agent add/configure/run/list` → `synlynk harness add/configure/run/list`, as a small, scoped, pre-1.0 breaking change.
2. **Carve-out:** `synlynk agent run support` stays under `agent`, not `harness`. The Support Engineer (`support`) is already a durable role-identity agent per the design (its config lives at `.agents/support.json` but the *thing being run* is an Agent, not a harness-config action). It becomes `synlynk agent run support` once Task #97 builds the new `agent` group; until Task #97 lands, `cmd_agent_run("support", ...)` keeps working exactly as today but is invoked via the new `harness run support` spelling like every other name — the carve-out is a naming reservation for Task #97 to claim, not new behavior this PR must build. This PR does not need to implement `agent run support`; it only needs to avoid taking the `agent` top-level verb so Task #97 can claim it cleanly.
3. Reserve the bare `synlynk agent` verb, unused after this rename, for Task #97's new `init/list/show/edit/disable` subcommands.

### Out of scope (explicitly, not silently dropped)

The following existing uses of the word "agent" in `synlynk/cli.py` are **not** renamed by this PR, because they don't collide with the new `agent` namespace — they're separate parts of the argparse tree and the decide panel's decision was scoped to the `agent add/configure/run/list` group specifically:

- `synlynk dispatch <agent> --task ...` (cli.py:576–579) — positional arg named `agent`, choices from `AGENT_CAPABILITY_BASELINES`.
- `synlynk open <agent>` (cli.py:702) — positional arg named `agent`, choices from `CORE_FLEET`.
- `synlynk probe --agent <name>` / `cmd_probe(agent=...)` (cli.py:1274, 1387).
- `synlynk quota --agent <name>` (cli.py:1113 preview, feeding `cmd_quota(agent=...)`).
- `synlynk configure agent <name>` (cli.py:410–424, dispatch at cli.py:1421-onward) — configures a harness's dispatch flags/env/network deps. Confusingly named today but it's a *sibling* command (`configure agent`, not `agent configure`) with no parser-level collision against the new `agent` group, and renaming it would touch a different, unrelated part of the tree. Left as a known follow-up, not blocking.

Renaming these is a much larger blast radius (every dispatch/probe/quota script that passes `--agent` or a positional agent name) and was not part of what the decide panel scoped or what actually collides with Task #97. If a future spec wants to extend the harness rename to these, that's a separate decision.

## 3. Implementation

### 3.1 Files touched

- `synlynk/cli.py` — rename the `agent` subparser group (lines 467–481) to `harness`; rename dispatch block (lines 1297–1311) to match; rename the four import names' call sites (not the underlying function names — see 3.2); update `help_parsers` registration (`"agent": agent_parser` at line ~881) to `"harness": harness_parser`.
- No changes needed to `synlynk/__init__.py` (`cmd_agent_configure`, `cmd_agent_add`) or `synlynk/support_engineer.py` (`cmd_agent_run`, `cmd_agent_list`) — see 3.2 for why function names stay as-is.
- No changes needed to `README.md` or `SYNLYNK_GUIDE.md` — grepped for `synlynk agent add/configure/run/list`, no hits. The only "agent" reference in README.md is a historical changelog line (`v0.8.0 | Support Engineer Agent...`), which is a record of what shipped and must not be edited.

### 3.2 Why function names (`cmd_agent_*`) don't change

`cmd_agent_add`, `cmd_agent_configure`, `cmd_agent_run`, `cmd_agent_list` are Python function names in `synlynk/__init__.py` and `synlynk/support_engineer.py`, imported into `cli.py` in two places (the `build_parser()` import block at cli.py:139–154, and the `main()` import block at cli.py:927–943). Renaming these functions to `cmd_harness_add` etc. would touch two more files and their existing docstrings/tests for no CLI-visible benefit — the rename that matters is the **CLI verb** (`synlynk agent add` → `synlynk harness add`), not the internal Python identifier. This PR only changes the argparse subparser name (`"agent"` → `"harness"`) and the `args.command == "agent"` dispatch check (`== "harness"`); the imported function names and their call sites (`cmd_agent_add(args.name)` etc.) stay exactly as they are today.

This mirrors how `cmd_agent_configure` already differs from the CLI verb `configure agent` — this codebase already tolerates internal function names not lexically matching their CLI surface, so there's no new inconsistency introduced.

### 3.3 Exact changes to `synlynk/cli.py`

**A. Subparser block (replaces lines 467–481):**

```python
harness_parser = subparsers.add_parser("harness", help="Manage and run autopilot harnesses")
harness_sub = harness_parser.add_subparsers(dest="harness_action")
harness_add_parser = harness_sub.add_parser("add", help="Retrofit an on-PATH harness into this project")
harness_add_parser.add_argument("name", help="Harness binary name on PATH")
harness_configure_parser = harness_sub.add_parser("configure", help="Interactively write .agents/<name>.json context profile")
harness_configure_parser.add_argument("name", help="Harness name: claude, agy, codex, grok")
harness_run_parser = harness_sub.add_parser("run", help="Run a named harness once")
harness_run_parser.add_argument("name", help="Harness name (matches .agents/<name>.json)")
harness_run_parser.add_argument("--dry-run", action="store_true", dest="dry_run", help="Collect signals and print findings; no dispatch/issue/PR")
harness_run_parser.add_argument("--install-cron", action="store_true", dest="install_cron", help="Install local crontab entry for this harness")
harness_sub.add_parser("list", help="List .agents/ configs and last run status")
```

Note: the on-disk config directory stays `.agents/` (e.g. `.agents/claude.json`) — that's storage layout, not CLI surface, and is out of scope for this rename. Only the CLI verb and argparse `dest` names change (`agent_action` → `harness_action`).

**B. `help_parsers` registration (replaces the `"agent": agent_parser,` line found near cli.py:881):**

```python
"harness": harness_parser,
```

**C. Dispatch block (replaces lines 1297–1311):**

```python
elif args.command == "harness":
    action = getattr(args, "harness_action", None)
    if action == "add":
        cmd_agent_add(args.name)
    elif action == "configure":
        cmd_agent_configure(args.name)
    elif action == "run":
        cmd_agent_run(
            args.name,
            dry_run=getattr(args, "dry_run", False),
            install_cron=getattr(args, "install_cron", False),
        )
    elif action == "list":
        cmd_agent_list()
    else:
        help_parsers.get("harness", parser).print_help()
```

No other files change. The four `cmd_agent_*` imports at cli.py:139–154 and cli.py:927–943 stay byte-for-byte identical — only their call sites' surrounding dispatch block moves under the `"harness"` command check.

### 3.4 Tests

Search the test suite for the current CLI surface before writing new assertions:

```bash
grep -rn "\"agent\", \"add\"\|\"agent\", \"configure\"\|\"agent\", \"run\"\|\"agent\", \"list\"\|args.command == .agent.\|agent_action" tests/
```

Any test invoking `build_parser().parse_args(["agent", "add", ...])` (or similar for configure/run/list) must be updated to `["harness", "add", ...]` etc. Any test asserting on `args.agent_action` must be updated to `args.harness_action`. New/updated tests should cover:

- `build_parser().parse_args(["harness", "add", "claude"])` → `args.command == "harness"`, `args.harness_action == "add"`, `args.name == "claude"`.
- `build_parser().parse_args(["harness", "run", "claude", "--dry-run"])` → `args.dry_run is True`.
- `build_parser().parse_args(["agent", ...])` now fails argparse (unknown command) or falls through to whatever `agent` verb exists after this PR (there should be none yet — Task #97 adds it later) — assert `SystemExit` is raised, matching argparse's behavior for an unrecognized subcommand.
- `help_parsers["harness"]` exists and `help_parsers.get("agent")` is `None` (or raises `KeyError` per the dict's existing access pattern) post-rename.

### 3.5 Non-goals

- No change to `.agents/<name>.json` file format, location, or the `AGENT_CAPABILITY_BASELINES` constant name.
- No change to `dispatch`/`open`/`probe`/`quota`/`configure agent`'s use of "agent" (see §2 Out of scope).
- No implementation of the new `synlynk agent init/list/show/edit/disable` commands — that's Task #97, blocked on this PR merging first so the `agent` verb is free to claim.
- No change to `cmd_agent_run`'s Support Engineer signal-collection logic in `synlynk/support_engineer.py` — behavior is identical, only reachable via `synlynk harness run <name>` instead of `synlynk agent run <name>`.

## 4. Rollout

Pre-1.0, no deprecation shim. `synlynk agent add/configure/run/list` simply stop resolving (argparse reports unknown command) the moment this PR merges; `synlynk harness add/configure/run/list` take over immediately. This matches the decide panel's framing of it as "a small scoped pre-1.0 breaking change" — synlynk has no external users depending on a stable CLI contract yet, and the fix is a straight positional rename with no migration state to carry.
