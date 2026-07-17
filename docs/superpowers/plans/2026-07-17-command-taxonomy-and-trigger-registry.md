# Command Taxonomy, Maturity-Tiered Reveal, and Trigger Registry — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Give every one of synlynk's 58 registered commands a single source-of-truth classification (GOVERNS stage, maturity tier, prominence, audience, trigger phrases), then use that classification to narrow the README/FTUE/launch-picker surface and to drive a two-mode trigger registry (agent-context phrases + real git hooks) — closing out issue #262 and design spec `docs/superpowers/specs/2026-07-17-command-taxonomy-and-trigger-registry-design.md` (PR #303).

**Architecture:** A new `synlynk/taxonomy.py` module holds `COMMAND_TAXONOMY`, a flat list of dict entries — one per leaf command as registered in `synlynk/cli.py`. A coverage test walks the actual argparse tree (via a small parser-introspection helper) and asserts every leaf has an entry, so the taxonomy can never silently drift from the real CLI surface — the same discipline that fixed issue #263's stale GOVERNS vocabulary. Everything downstream (README generation, FTUE wizard, launch picker, trigger registry) reads from `COMMAND_TAXONOMY` rather than maintaining a second copy.

**Tech Stack:** Python 3 stdlib only (`argparse`, `json`), pytest, existing `synlynk/instructions.py` fencing mechanism, existing pre-commit hook install pattern from `synlynk init`.

---

## File structure

| File | Responsibility |
|---|---|
| `synlynk/cli.py` | Modify: extract parser construction out of `main()` into a standalone `build_parser()` so it can be introspected without running the CLI |
| `synlynk/taxonomy.py` | Create: `COMMAND_TAXONOMY` data + `iter_leaf_commands(parser)` introspection helper + `get_entry(command)` / `entries_for_tier(tier)` lookup helpers |
| `tests/test_taxonomy.py` | Create: coverage test (taxonomy ⟷ real CLI surface), schema test, tier-lookup tests |
| `scripts/generate_command_docs.py` | Create: regenerates `docs/reference/commands.md` and the README command table from `COMMAND_TAXONOMY` |
| `docs/reference/commands.md` | Create (generated): full reference of every command, all tiers |
| `README.md` | Modify: command section replaced with generated Tier 0 + gateway summary, pointing to `docs/reference/commands.md` for the rest |
| `tests/test_docs_sync.py` | Create: regenerate-and-diff test that fails if README/reference docs drift from `COMMAND_TAXONOMY` |
| `synlynk/__init__.py` | Modify: `wizard_init()` FTUE cheat-sheet and `LAUNCH_TASK_TEMPLATES` sourced from `COMMAND_TAXONOMY` instead of separate hardcoded lists |
| `synlynk/instructions.py` | Modify: inject a tier-scoped trigger-phrase sub-section inside existing `synlynk:start/end` fencing; add pre-commit hook installer for `instructions ack` |
| `tests/test_instructions.py` | Modify: add tier-scoping test, hook-install test |

---

## Task 1: Extract `build_parser()` from `main()`

**Files:**
- Modify: `synlynk/cli.py:137-612` (the `main()` function)
- Test: `tests/test_cli_parser.py`

Today `synlynk/cli.py`'s `main()` builds the entire argparse tree inline and immediately calls `parser.parse_args()` on the real `sys.argv`, then dispatches. There's no way to get a `parser` object in a test without invoking the live CLI. This task splits parser construction into its own function so Task 2's coverage test can introspect it safely.

- [ ] **Step 1: Write the failing test**

```python
# tests/test_cli_parser.py
import argparse
from synlynk.cli import build_parser


def test_build_parser_returns_argument_parser():
    parser = build_parser()
    assert isinstance(parser, argparse.ArgumentParser)


def test_build_parser_has_known_top_level_commands():
    parser = build_parser()
    subparsers_action = next(
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    )
    assert "init" in subparsers_action.choices
    assert "dispatch" in subparsers_action.choices
    assert "viz" in subparsers_action.choices
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_cli_parser.py -v`
Expected: FAIL with `ImportError: cannot import name 'build_parser' from 'synlynk.cli'`

- [ ] **Step 3: Extract `build_parser()`**

In `synlynk/cli.py`, `main()` currently reads (abbreviated):

```python
def main() -> None:
    from synlynk import (...)
    from synlynk.status import cmd_status as cmd_ecosystem_status
    from synlynk.viz import cmd_viz
    from synlynk.scheduler import cmd_schedule
    _reconcile_jobs()
    parser = argparse.ArgumentParser(
        description="synlynk: The Universal Context Switchboard for AI Devs"
    )
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", ...)
    # ... ~400 lines of subparsers.add_parser(...) calls ...
    viz_parser = subparsers.add_parser("viz", ...)
    viz_parser.add_argument(...)

    args = parser.parse_args()

    if args.command == "init":
        ...
```

Change it to:

```python
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="synlynk: The Universal Context Switchboard for AI Devs"
    )
    parser.add_argument("--version", action="version", version=f"synlynk {VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    init_parser = subparsers.add_parser("init", ...)
    # ... same ~400 lines, unchanged ...
    viz_parser = subparsers.add_parser("viz", ...)
    viz_parser.add_argument(...)

    return parser


def main() -> None:
    from synlynk import (...)
    from synlynk.status import cmd_status as cmd_ecosystem_status
    from synlynk.viz import cmd_viz
    from synlynk.scheduler import cmd_schedule
    _reconcile_jobs()
    parser = build_parser()
    args = parser.parse_args()

    if args.command == "init":
        ...
```

`VERSION` is only used inside `build_parser()` now (for `--version`), so move `from synlynk import VERSION` (just that one name) to module level in `cli.py`, or keep it as a local import at the top of `build_parser()` — either works, but it must no longer live only inside the deferred import block in `main()`, since `build_parser()` needs it independently of `main()`'s other imports. The dispatch `if args.command == ...` chain in `main()` is untouched — only the parser-building block moves.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_cli_parser.py -v`
Expected: PASS

- [ ] **Step 5: Run the full existing test suite to confirm no regression**

Run: `pytest tests/ -x -q`
Expected: PASS, same pass/skip count as before this change (this is a pure refactor — no behavior change)

- [ ] **Step 6: Commit**

```bash
git add synlynk/cli.py tests/test_cli_parser.py
git commit -m "refactor: extract build_parser() from main() for testability"
```

---

## Task 2: `synlynk/taxonomy.py` — schema, introspection helper, and coverage test

**Files:**
- Create: `synlynk/taxonomy.py`
- Test: `tests/test_taxonomy.py`

- [ ] **Step 1: Write the failing coverage test**

```python
# tests/test_taxonomy.py
import argparse
from synlynk.cli import build_parser
from synlynk.taxonomy import COMMAND_TAXONOMY, iter_leaf_commands

REQUIRED_KEYS = {
    "command", "governs_stage", "maturity_tier", "prominence",
    "orientation_gateway", "audience", "trigger_phrases", "hook_event",
}
VALID_STAGES = {"goal", "open", "visualize", "execute", "release", "notify", "sustain"}
VALID_TIERS = {0, 1, 2, 3, "latent"}
VALID_PROMINENCE = {"primary", "secondary", None}
VALID_AUDIENCE = {"human", "pilot", "hook"}


def test_every_entry_has_required_keys():
    for entry in COMMAND_TAXONOMY:
        assert REQUIRED_KEYS <= entry.keys(), f"{entry.get('command')} missing keys"


def test_every_entry_has_valid_field_values():
    for entry in COMMAND_TAXONOMY:
        assert entry["governs_stage"] in VALID_STAGES, entry["command"]
        assert entry["maturity_tier"] in VALID_TIERS, entry["command"]
        assert entry["prominence"] in VALID_PROMINENCE, entry["command"]
        assert entry["audience"] in VALID_AUDIENCE, entry["command"]
        assert isinstance(entry["trigger_phrases"], list), entry["command"]
        if entry["audience"] != "human":
            assert entry["trigger_phrases"] == [], entry["command"]


def test_no_duplicate_commands():
    commands = [e["command"] for e in COMMAND_TAXONOMY]
    assert len(commands) == len(set(commands))


def test_taxonomy_matches_real_cli_surface():
    parser = build_parser()
    real_commands = set(iter_leaf_commands(parser))
    taxonomy_commands = {e["command"] for e in COMMAND_TAXONOMY}
    missing_from_taxonomy = real_commands - taxonomy_commands
    stale_in_taxonomy = taxonomy_commands - real_commands
    assert not missing_from_taxonomy, f"cli.py commands with no taxonomy entry: {missing_from_taxonomy}"
    assert not stale_in_taxonomy, f"taxonomy entries for commands no longer in cli.py: {stale_in_taxonomy}"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_taxonomy.py -v`
Expected: FAIL with `ImportError: cannot import name 'COMMAND_TAXONOMY' from 'synlynk.taxonomy'` (module doesn't exist yet)

- [ ] **Step 3: Write `iter_leaf_commands()`**

```python
# synlynk/taxonomy.py
"""Single source of truth for synlynk's command surface: GOVERNS stage,
maturity tier, prominence, audience, and trigger phrases for every
command registered in synlynk/cli.py's build_parser()."""

import argparse


def iter_leaf_commands(parser: argparse.ArgumentParser, prefix: tuple = ()):
    """Yield dotted-space command paths (e.g. 'story create') for every
    invocable command in an argparse tree.

    A parser is a leaf if it has no subparsers action. A parser with a
    subparsers action is ALSO yielded as its own leaf if it defines any
    argument of its own beyond --help and the subparsers action itself
    (e.g. 'jobs' takes --all directly AND has a 'jobs handoff' subcommand,
    so both 'jobs' and 'jobs handoff' are real, separately-invocable
    commands)."""
    subparsers_actions = [
        a for a in parser._actions if isinstance(a, argparse._SubParsersAction)
    ]
    own_args = [
        a for a in parser._actions
        if not isinstance(a, argparse._SubParsersAction)
        and not isinstance(a, argparse._HelpAction)
    ]

    if not subparsers_actions:
        if prefix:
            yield " ".join(prefix)
        return

    if own_args and prefix:
        yield " ".join(prefix)

    for action in subparsers_actions:
        for name, subparser in action.choices.items():
            yield from iter_leaf_commands(subparser, prefix + (name,))
```

- [ ] **Step 4: Run test to verify the coverage assertion now fails meaningfully (not on import)**

Run: `pytest tests/test_taxonomy.py::test_taxonomy_matches_real_cli_surface -v`
Expected: FAIL with `AssertionError: cli.py commands with no taxonomy entry: {...58 commands...}` (confirms `iter_leaf_commands` works — now populate the data)

- [ ] **Step 5: Populate `COMMAND_TAXONOMY`**

Append to `synlynk/taxonomy.py`:

```python
COMMAND_TAXONOMY = [
    # --- Tier 0: FTUE ---
    {"command": "init", "governs_stage": "open", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["set up synlynk here", "get started with synlynk"], "hook_event": None},
    {"command": "scan", "governs_stage": "open", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["scan this repo", "inventory this codebase"], "hook_event": None},
    {"command": "join", "governs_stage": "open", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["add me to this project", "onboard me"], "hook_event": None},
    {"command": "migrate", "governs_stage": "sustain", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["migrate the old config", "upgrade project-docs layout"], "hook_event": None},
    {"command": "configure agent", "governs_stage": "open", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["configure the codex harness", "override dispatch flags for grok"], "hook_event": None},
    {"command": "agent add", "governs_stage": "open", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["add this agent binary", "retrofit an agent onto this project"], "hook_event": None},
    {"command": "agent configure", "governs_stage": "open", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["write this agent's context profile"], "hook_event": None},
    {"command": "agent list", "governs_stage": "open", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["what agents are configured", "list our agents"], "hook_event": None},
    {"command": "config set", "governs_stage": "open", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["set this config key"], "hook_event": None},

    # --- Tier 1: Goal ---
    {"command": "decide", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["let's decide on X", "record this decision"], "hook_event": None},
    {"command": "goal create", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["create a new goal", "start a business goal for X"], "hook_event": None},
    {"command": "goal list", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["what goals are active", "list our goals"], "hook_event": None},
    {"command": "goal link", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["link this story to the goal", "attach this to goal X"], "hook_event": None},
    {"command": "goal status", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["how close is this goal", "goal completion rollup"], "hook_event": None},
    {"command": "story create", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["create a story for X", "write up this piece of work"], "hook_event": None},
    {"command": "story list", "governs_stage": "goal", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["what stories do we have", "list open stories"], "hook_event": None},
    {"command": "story ready", "governs_stage": "goal", "maturity_tier": 1, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["mark this story ready"], "hook_event": None},
    {"command": "story draft", "governs_stage": "goal", "maturity_tier": 1, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["revert this story to draft"], "hook_event": None},
    {"command": "open", "governs_stage": "open", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["open the workspace", "open this project"], "hook_event": None},
    {"command": "launch", "governs_stage": "open", "maturity_tier": 1, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["what should I do next", "give me a task to launch"], "hook_event": None},
    {"command": "roles", "governs_stage": "open", "maturity_tier": 1, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["who has what role on this project"], "hook_event": None},

    # --- Tier 2: Execute ---
    {"command": "dispatch", "governs_stage": "execute", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["let's build X", "can you implement...", "hand this to codex"], "hook_event": None},
    {"command": "jobs", "governs_stage": "execute", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["what's still running", "check on that job"], "hook_event": None},
    {"command": "jobs handoff", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["hand this stalled job to another agent"], "hook_event": None},
    {"command": "schedule", "governs_stage": "execute", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["batch these up", "run this fleet-wide"], "hook_event": None},
    {"command": "release", "governs_stage": "release", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["cut a release", "ship v0.x.0"], "hook_event": None},
    {"command": "pr check", "governs_stage": "release", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["is this PR's model version attested"], "hook_event": None},
    {"command": "doctor", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["run a health check", "is synlynk set up correctly"], "hook_event": None},
    {"command": "probe", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["probe this endpoint"],
     "hook_event": None},
    {"command": "exec", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["run claude directly with context"], "hook_event": None},
    {"command": "logs", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["tail that job's logs"],
     "hook_event": None},
    {"command": "shell", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["drop me into that job's shell"],
     "hook_event": None},
    {"command": "sentinel list", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["what sentinel alerts are active"],
     "hook_event": None},
    {"command": "sentinel clear", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["clear that sentinel alert"],
     "hook_event": None},
    {"command": "cost log", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["log this manual session's cost"], "hook_event": None},
    {"command": "run --trio", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["run the trio protocol"],
     "hook_event": None},
    {"command": "local doctor", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["is the local oMLX agent reachable"],
     "hook_event": None},
    {"command": "upgrade", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["upgrade synlynk"],
     "hook_event": None},

    # --- Tier 3: Team/Enterprise ---
    {"command": "team status", "governs_stage": "notify", "maturity_tier": 3, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["show the team digest", "who's working on what"], "hook_event": None},
    {"command": "sync", "governs_stage": "sustain", "maturity_tier": 3, "prominence": "primary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["sync team state"],
     "hook_event": None},
    {"command": "score add", "governs_stage": "sustain", "maturity_tier": 3, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["rate this agent's output"],
     "hook_event": None},
    {"command": "score list", "governs_stage": "sustain", "maturity_tier": 3, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["show capability scores"],
     "hook_event": None},
    {"command": "score attest", "governs_stage": "sustain", "maturity_tier": 3, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["attest this model version"],
     "hook_event": None},

    # --- Orientation gateway (tier-independent) ---
    {"command": "status", "governs_stage": "visualize", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": True, "audience": "human",
     "trigger_phrases": ["where are we", "what's the state of things"], "hook_event": None},
    {"command": "watch", "governs_stage": "visualize", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": True, "audience": "human",
     "trigger_phrases": ["show me the live HUD", "watch the workspace"], "hook_event": None},
    {"command": "viz", "governs_stage": "visualize", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": True, "audience": "human",
     "trigger_phrases": ["open the dashboard", "show me the browser view"], "hook_event": None},

    # --- Latent (autopilot/hook, never promoted to humans) ---
    {"command": "relay start", "governs_stage": "execute", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": None},
    {"command": "relay broadcast", "governs_stage": "execute", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": None},
    {"command": "checkpoint", "governs_stage": "execute", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "pilot", "trigger_phrases": [], "hook_event": None},
    {"command": "daemon", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": None},
    {"command": "identity init", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "pilot", "trigger_phrases": [], "hook_event": None},
    {"command": "repair", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "pilot", "trigger_phrases": [], "hook_event": None},
    {"command": "exit", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "pilot", "trigger_phrases": [], "hook_event": None},
    {"command": "agent run", "governs_stage": "execute", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "pilot", "trigger_phrases": [], "hook_event": None},
    {"command": "instructions status", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": None},
    {"command": "instructions diff", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": None},
    {"command": "instructions update", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": None},
    {"command": "instructions ack", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
     "orientation_gateway": False, "audience": "hook", "trigger_phrases": [], "hook_event": "pre-commit"},
]


def get_entry(command: str) -> dict:
    for entry in COMMAND_TAXONOMY:
        if entry["command"] == command:
            return entry
    raise KeyError(f"no COMMAND_TAXONOMY entry for {command!r}")


def entries_for_tier(tier) -> list:
    return [e for e in COMMAND_TAXONOMY if e["maturity_tier"] == tier]


def entries_up_to_tier(tier: int) -> list:
    """Every entry visible to a repo currently at the given numeric tier:
    that tier and below, plus the always-on orientation gateway."""
    return [
        e for e in COMMAND_TAXONOMY
        if e["orientation_gateway"]
        or (isinstance(e["maturity_tier"], int) and e["maturity_tier"] <= tier)
    ]
```

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_taxonomy.py -v`
Expected: PASS, all 5 tests (if `test_taxonomy_matches_real_cli_surface` still fails, diff its error output against `iter_leaf_commands(build_parser())` to find the discrepancy — do not delete or weaken the test to make it pass)

- [ ] **Step 7: Commit**

```bash
git add synlynk/taxonomy.py tests/test_taxonomy.py
git commit -m "feat: add COMMAND_TAXONOMY covering all 58 registered commands"
```

---

## Task 3: Docs generation — `docs/reference/commands.md` + README sync

**Files:**
- Create: `scripts/generate_command_docs.py`
- Create (generated output): `docs/reference/commands.md`
- Modify: `README.md`
- Test: `tests/test_docs_sync.py`

- [ ] **Step 1: Write the failing docs-sync test**

```python
# tests/test_docs_sync.py
import subprocess
import sys


def test_generated_reference_doc_matches_taxonomy(tmp_path):
    from scripts.generate_command_docs import render_reference_doc
    with open("docs/reference/commands.md") as f:
        committed = f.read()
    assert render_reference_doc() == committed, (
        "docs/reference/commands.md is stale — run "
        "`python3 scripts/generate_command_docs.py` and commit the result"
    )


def test_generated_readme_section_matches_taxonomy():
    from scripts.generate_command_docs import render_readme_section
    with open("README.md") as f:
        readme = f.read()
    assert render_readme_section() in readme, (
        "README.md's command section is stale — run "
        "`python3 scripts/generate_command_docs.py` and commit the result"
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_docs_sync.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.generate_command_docs'`

- [ ] **Step 3: Write the generator**

```python
# scripts/generate_command_docs.py
"""Regenerates docs/reference/commands.md and README.md's command table
from synlynk.taxonomy.COMMAND_TAXONOMY. Run after any taxonomy change:

    python3 scripts/generate_command_docs.py
"""
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from synlynk.taxonomy import COMMAND_TAXONOMY, entries_for_tier

TIER_LABELS = {
    0: "Tier 0 — First-Time Setup",
    1: "Tier 1 — Goal",
    2: "Tier 2 — Execute",
    3: "Tier 3 — Team / Enterprise",
    "latent": "Latent — Autopilot & Hooks Only",
}

README_START = "<!-- commands:start -->"
README_END = "<!-- commands:end -->"


def render_reference_doc() -> str:
    lines = ["# Command Reference", "",
             "Generated from `synlynk/taxonomy.py`. Do not edit by hand — run "
             "`python3 scripts/generate_command_docs.py`.", ""]
    gateway = [e for e in COMMAND_TAXONOMY if e["orientation_gateway"]]
    lines.append("## Orientation gateway (always available)")
    lines.append("")
    for e in gateway:
        lines.append(f"- `{e['command']}` — {e['governs_stage']}")
    lines.append("")
    for tier in (0, 1, 2, 3, "latent"):
        entries = [e for e in entries_for_tier(tier) if not e["orientation_gateway"]]
        if not entries:
            continue
        lines.append(f"## {TIER_LABELS[tier]}")
        lines.append("")
        for e in entries:
            prom = f" ({e['prominence']})" if e["prominence"] else ""
            lines.append(f"- `{e['command']}`{prom} — {e['governs_stage']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def render_readme_section() -> str:
    lines = [README_START, ""]
    lines.append("**Start here:**")
    lines.append("")
    for e in COMMAND_TAXONOMY:
        if e["maturity_tier"] == 0 and (e["prominence"] == "primary" or e["orientation_gateway"]):
            lines.append(f"- `synlynk {e['command']}`")
    lines.append("")
    lines.append("Full command reference: [docs/reference/commands.md](docs/reference/commands.md)")
    lines.append("")
    lines.append(README_END)
    return "\n".join(lines)


def main():
    Path("docs/reference").mkdir(parents=True, exist_ok=True)
    Path("docs/reference/commands.md").write_text(render_reference_doc())

    readme_path = Path("README.md")
    readme = readme_path.read_text()
    section = render_readme_section()
    pattern = re.compile(
        re.escape(README_START) + r".*?" + re.escape(README_END), re.DOTALL
    )
    if pattern.search(readme):
        readme = pattern.sub(section, readme)
    else:
        raise RuntimeError(
            f"README.md is missing {README_START}/{README_END} markers — "
            "add them once around the command section, then re-run this script"
        )
    readme_path.write_text(readme)
    print("Regenerated docs/reference/commands.md and README.md command section.")


if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Add the marker pair to README.md**

Find the current command-listing section in `README.md` (the ~19-command list referenced in the design spec) and replace it with:

```markdown
<!-- commands:start -->
<!-- commands:end -->
```

(placeholder — Step 5 fills it in by running the generator)

- [ ] **Step 5: Run the generator to produce the real files**

Run: `python3 scripts/generate_command_docs.py`
Expected output: `Regenerated docs/reference/commands.md and README.md command section.`

- [ ] **Step 6: Run test to verify it passes**

Run: `pytest tests/test_docs_sync.py -v`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add scripts/generate_command_docs.py docs/reference/commands.md README.md tests/test_docs_sync.py
git commit -m "feat: generate command reference docs from COMMAND_TAXONOMY"
```

---

## Task 4: FTUE wizard + `synlynk launch` picker consolidation

**Files:**
- Modify: `synlynk/__init__.py` (`wizard_init()` cheat-sheet screen, `LAUNCH_TASK_TEMPLATES`)
- Test: `tests/test_launch.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_launch.py (add to existing file)
from synlynk.taxonomy import entries_for_tier
from synlynk import LAUNCH_TASK_TEMPLATES


def test_launch_templates_only_cover_tier1_primary_commands():
    tier1_primary_commands = {
        e["command"] for e in entries_for_tier(1) if e["prominence"] == "primary"
    }
    template_commands = {t["id"] for t in LAUNCH_TASK_TEMPLATES}
    # every template must correspond to a Tier 1 primary command's launch flow
    assert template_commands <= tier1_primary_commands | {
        t["id"] for t in LAUNCH_TASK_TEMPLATES if t["id"] in CORE_TEMPLATE_IDS
    }
```

Note: adapt this assertion once you've read the current `LAUNCH_TASK_TEMPLATES`/`CORE_TEMPLATE_IDS` shape in `synlynk/__init__.py:302-` — the exact `id` values (e.g. `"arch-review"`) don't map 1:1 to taxonomy `command` strings today. The concrete fix in Step 2 is what reconciles this; write whichever assertion form matches after reading that code, but it must assert something enforceable (not just `True`).

- [ ] **Step 2: Run test, confirm it fails or errors against current code**

Run: `pytest tests/test_launch.py -v`
Expected: FAIL (either import error on `CORE_TEMPLATE_IDS` if not exported, or assertion failure) — read the actual failure to guide Step 3

- [ ] **Step 3: Read current `wizard_init()` and `LAUNCH_TASK_TEMPLATES`, then reconcile**

Read `synlynk/__init__.py` around `wizard_init()` and `LAUNCH_TASK_TEMPLATES` (line ~307+) in full before editing. Update `wizard_init()`'s cheat-sheet print block to iterate `entries_for_tier(0)` (primary only) plus the three `orientation_gateway` entries from `synlynk.taxonomy`, instead of any hardcoded command list. Update `LAUNCH_TASK_TEMPLATES` construction (or the code that filters it for display) to only include templates whose underlying command is Tier 1 `primary` per `COMMAND_TAXONOMY`.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_launch.py -v`
Expected: PASS

- [ ] **Step 5: Run full suite**

Run: `pytest tests/ -x -q`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add synlynk/__init__.py tests/test_launch.py
git commit -m "feat: drive FTUE wizard and launch picker from COMMAND_TAXONOMY"
```

---

## Task 5: Trigger registry — agent-context injection (tier-scoped)

**Files:**
- Modify: `synlynk/instructions.py` (extend `synlynk:start/end` fencing content generation)
- Test: `tests/test_instructions.py`

Read `synlynk/instructions.py`'s existing fencing generation code in full before starting (the functions that build the `synlynk:start`/`synlynk:end` block content) — this task adds a new sub-section to that existing content, it does not replace the fencing mechanism.

- [ ] **Step 1: Write the failing tier-scoping test**

```python
# tests/test_instructions.py (add to existing file)
from synlynk.instructions import render_trigger_phrase_section


def test_tier0_fixture_only_gets_tier0_and_gateway_phrases():
    section = render_trigger_phrase_section(current_tier=0)
    assert "let's build X" not in section  # dispatch is Tier 2
    assert "set up synlynk here" in section  # init is Tier 0
    assert "where are we" in section  # status is gateway, always included


def test_tier2_fixture_gets_tier0_through_tier2_phrases():
    section = render_trigger_phrase_section(current_tier=2)
    assert "let's build X" in section  # dispatch is Tier 2, now included
    assert "set up synlynk here" in section  # Tier 0 still included
    assert "rate this agent's output" not in section  # score add is Tier 3, not yet
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_instructions.py -v`
Expected: FAIL with `ImportError: cannot import name 'render_trigger_phrase_section'`

- [ ] **Step 3: Implement `render_trigger_phrase_section()`**

```python
# synlynk/instructions.py (add near the other fencing-content builder functions)
from synlynk.taxonomy import entries_up_to_tier


def render_trigger_phrase_section(current_tier: int) -> str:
    """Build the trigger-phrase sub-section injected inside the
    synlynk:start/end fence, scoped to the repo's current maturity tier
    so the injected context stays proportional to what the user actually
    needs (see docs/superpowers/specs/2026-07-17-command-taxonomy-and-trigger-registry-design.md,
    Section 3)."""
    entries = [
        e for e in entries_up_to_tier(current_tier)
        if e["audience"] == "human" and e["trigger_phrases"]
    ]
    lines = ["## When the user says one of these, reach for the matching command:", ""]
    for e in entries:
        phrases = ", ".join(f'"{p}"' for p in e["trigger_phrases"])
        lines.append(f"- {phrases} → `synlynk {e['command']}`")
    return "\n".join(lines)
```

Wire this function's output into whatever function currently assembles the full `synlynk:start`...`synlynk:end` block content, appending it as a new sub-section. The repo's `current_tier` should come from the same state.db signal the FTUE/launch consolidation (Task 4) reads — locate that signal in the existing code (do not invent a new one; if none exists yet, that's a pre-existing gap flagged in the design spec's "Out of scope" item 4, and this task should default `current_tier` to `2` rather than block on building tier-detection from scratch).

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_instructions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/instructions.py tests/test_instructions.py
git commit -m "feat: tier-scoped trigger phrases in synlynk:start/end fencing"
```

---

## Task 6: Trigger registry — real pre-commit hook for `instructions ack`

**Files:**
- Modify: `synlynk/instructions.py` (hook installer)
- Modify: `synlynk/__init__.py` (`init()` — call the hook installer, following the existing pattern used for other `synlynk init`-installed hooks)
- Test: `tests/test_instructions.py`

- [ ] **Step 1: Write the failing hook-install test**

```python
# tests/test_instructions.py (add to existing file)
import os
import stat
from synlynk.instructions import install_pre_commit_hook


def test_install_pre_commit_hook_writes_executable_hook(tmp_path):
    git_dir = tmp_path / ".git" / "hooks"
    git_dir.mkdir(parents=True)
    install_pre_commit_hook(repo_root=tmp_path)
    hook_path = git_dir / "pre-commit"
    assert hook_path.exists()
    mode = hook_path.stat().st_mode
    assert mode & stat.S_IXUSR, "pre-commit hook must be executable"
    assert "synlynk instructions ack" in hook_path.read_text()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_instructions.py::test_install_pre_commit_hook_writes_executable_hook -v`
Expected: FAIL with `ImportError: cannot import name 'install_pre_commit_hook'`

- [ ] **Step 3: Implement `install_pre_commit_hook()`**

```python
# synlynk/instructions.py
import os
import stat
from pathlib import Path

HOOK_SCRIPT = """#!/bin/sh
# Installed by synlynk init — checks instruction-file drift before commit.
synlynk instructions ack --pre-commit || exit 1
"""


def install_pre_commit_hook(repo_root: Path) -> None:
    hook_path = Path(repo_root) / ".git" / "hooks" / "pre-commit"
    if hook_path.exists() and "synlynk instructions ack" in hook_path.read_text():
        return  # already installed, idempotent
    existing = hook_path.read_text() if hook_path.exists() else ""
    if existing and not existing.startswith("#!"):
        raise RuntimeError(f"unexpected pre-commit hook content at {hook_path}, not overwriting")
    hook_path.write_text(existing + ("\n" if existing else "") + HOOK_SCRIPT
                          if existing else HOOK_SCRIPT)
    hook_path.chmod(hook_path.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
```

`cmd_instructions_ack` (already implemented per the existing `instructions ack` CLI command) needs a `--pre-commit` flag that makes it exit non-zero on unacknowledged drift instead of just printing status — check its current signature in `synlynk/__init__.py` and add the flag if it isn't already there; this is a small, additive change to an existing function, not a rewrite.

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_instructions.py::test_install_pre_commit_hook_writes_executable_hook -v`
Expected: PASS

- [ ] **Step 5: Wire into `init()`**

In `synlynk/__init__.py`'s `init()` function, add a call to `install_pre_commit_hook(repo_root=Path.cwd())` (import `from synlynk.instructions import install_pre_commit_hook` at the top of the function or module, matching the existing import style in that file) alongside the other one-time setup `init()` already performs.

- [ ] **Step 6: Run full suite**

Run: `pytest tests/ -x -q`
Expected: PASS

- [ ] **Step 7: Commit**

```bash
git add synlynk/instructions.py synlynk/__init__.py tests/test_instructions.py
git commit -m "feat: install pre-commit hook for instructions ack on synlynk init"
```

---

## Self-review notes

- **Spec coverage:** Section 1 (data model) → Tasks 1–2. Section 2 (FTUE/README consolidation) → Tasks 3–4. Section 3 (trigger registry, both halves) → Tasks 5–6. Section 4 (testing) → each task's own test is the coverage, docs-sync, tier-scoping, and hook-install tests named explicitly in that section. Out-of-scope items (ambient HUD, taxonomy-browsing UI, Tier 3 growth, maturity-tier detection) are correctly not tasked here — Task 5 explicitly defaults to a fixed tier rather than building tier-detection, per the spec's own scope boundary.
- **Placeholder scan:** No TBD/TODO left unresolved. Task 4 Step 1's test is intentionally left for the implementer to finalize against the real current shape of `LAUNCH_TASK_TEMPLATES` (which this plan's author has not read line-by-line) — flagged explicitly as a read-before-edit step rather than papered over with a fake passing assertion.
- **Type/name consistency:** `COMMAND_TAXONOMY`, `iter_leaf_commands`, `get_entry`, `entries_for_tier`, `entries_up_to_tier` are defined once in Task 2 and reused with identical names in Tasks 3, 4, and 5 — no renames across tasks.

---

## Execution handoff

Each task above is scoped to be dispatched independently to Agy/Grok/Codex via `synlynk dispatch`, per this project's PM/implementer split — Claude reviews the resulting PRs and merges, but does not run these tasks itself. Suggested dispatch order: Task 1 → Task 2 → {Task 3, Task 4 in parallel, both depend only on Task 2} → {Task 5, Task 6 in parallel, both depend only on Task 2}.
