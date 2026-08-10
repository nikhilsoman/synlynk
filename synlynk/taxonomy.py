"""Single source of truth for synlynk's command surface."""

import argparse


def iter_leaf_commands(parser: argparse.ArgumentParser, prefix: tuple = ()):
    """Yield every invocable command path from an argparse tree."""
    subparsers_actions = [
        action for action in parser._actions
        if isinstance(action, argparse._SubParsersAction)
    ]
    own_args = [
        action for action in parser._actions
        if not isinstance(action, argparse._SubParsersAction)
        and not isinstance(action, argparse._HelpAction)
    ]

    if not subparsers_actions:
        if prefix:
            yield " ".join(prefix)
        return

    if own_args and prefix:
        yield " ".join(prefix)

    for action in subparsers_actions:
        for name, subparser in action.choices.items():
            if getattr(subparser, "_synlynk_skip_taxonomy", False):
                continue
            yield from iter_leaf_commands(subparser, prefix + (name,))


COMMAND_TAXONOMY = [
    # --- Tier 0: FTUE ---
    {"command": "init", "governs_stage": "open", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["set up synlynk here", "get started with synlynk"], "hook_event": None},
    {"command": "start", "governs_stage": "open", "maturity_tier": 0, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["start a new project", "is this a new or existing project"], "hook_event": None},
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
    {"command": "config nudges", "governs_stage": "open", "maturity_tier": 0, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["control workspace-agent nudges"], "hook_event": None},

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
    {"command": "story done", "governs_stage": "goal", "maturity_tier": 1, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["mark this story done"], "hook_event": None},
    {"command": "roadmap add", "governs_stage": "sustain", "maturity_tier": 1, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["add a roadmap arc", "add a roadmap phase"], "hook_event": None},
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
    {"command": "backfill-capability-ratings", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["backfill capability ratings", "repair missing story ids"], "hook_event": None},
    {"command": "jobs", "governs_stage": "execute", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["what's still running", "check on that job"], "hook_event": None},
    {"command": "jobs handoff", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["hand this stalled job to another agent"], "hook_event": None},
    {"command": "jobs reap", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": [
         "reap zombie jobs",
         "clear dead running jobs",
         "jobs stuck running with dead pid",
     ], "hook_event": None},
    {"command": "schedule", "governs_stage": "execute", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["batch these up", "run this fleet-wide"], "hook_event": None},
    {"command": "release", "governs_stage": "release", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["cut a release", "ship v0.x.0"], "hook_event": None},
    {"command": "pr check", "governs_stage": "release", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["is this PR's model version attested"], "hook_event": None},
    {"command": "ops report", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "primary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": [
         "platform ops report",
         "how is the multi-agent fleet across all repos",
         "cross-repo jobs and costs last day",
         "nightly ops rollup",
     ], "hook_event": None},
    {"command": "doctor", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["run a health check", "is synlynk set up correctly"], "hook_event": None},
    {"command": "probe", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["probe this endpoint"],
     "hook_event": None},
    {"command": "worktree audit", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["audit stale worktrees", "classify worktree safety"], "hook_event": None},
    {"command": "worktree clean", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["clean up stale worktrees", "remove safe worktrees"], "hook_event": None},
    {"command": "exec", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["run claude directly with context"], "hook_event": None},
    {"command": "tui", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["launch the terminal ui", "open the curses dashboard"], "hook_event": None},
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
    {"command": "credit grant", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["grant a credit balance", "record a credit grant"], "hook_event": None},
    {"command": "quota", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["show agent quota headroom"], "hook_event": None},
    {"command": "capability sweep", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human",
     "trigger_phrases": ["run a capability sweep", "seed capability baselines"], "hook_event": None},
    {"command": "run --trio", "governs_stage": "execute", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["run the trio protocol"],
     "hook_event": None},
    {"command": "local doctor", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["is the local oMLX agent reachable"],
     "hook_event": None},
    {"command": "upgrade", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["upgrade synlynk"],
     "hook_event": None},
    {"command": "rollback", "governs_stage": "sustain", "maturity_tier": 2, "prominence": "secondary",
     "orientation_gateway": False, "audience": "human", "trigger_phrases": ["roll back the last change"],
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
    {"command": "identity list", "governs_stage": "sustain", "maturity_tier": "latent", "prominence": None,
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
    return [entry for entry in COMMAND_TAXONOMY if entry["maturity_tier"] == tier]


def entries_up_to_tier(tier: int) -> list:
    return [
        entry for entry in COMMAND_TAXONOMY
        if isinstance(entry["maturity_tier"], int) and entry["maturity_tier"] <= tier
    ]
