# Synlynk in 10 minutes

This is the shortest path from an empty checkout to a verified task result.

## 1. Install (2 minutes)

```bash
pipx install git+https://github.com/nikhilsoman/synlynk
```

From a checkout, use `python3 bin/synlynk.py` in place of `synlynk`.

## 2. Initialize the project (2 minutes)

Run this from the repository you want Synlynk to coordinate:

```bash
synlynk init
```

Initialization creates the shared project context used by every execution
backend. An Agent is the accountable role (for example `dev` or `qa`); a
Harness is the tool that executes that role (for example Codex or Claude).
See the [glossary](glossary-agent-vs-harness.md) when choosing either one.

## 3. Send one task (3 minutes)

```bash
synlynk dispatch --task "Add a focused test for the next small behavior change"
```

Synlynk selects the available role and harness defaults, creates an isolated
worktree, and records the job. Add explicit overrides when you need them:

```bash
synlynk dispatch codex --task "Run the targeted test and fix the failure"
```

## 4. Verify the outcome (3 minutes)

```bash
synlynk jobs
synlynk status
```

Inspect the job details and its worktree before reviewing or merging the
change. For the next task, use the [how-tos](how-to/README.md). For every
available command, use the [generated command reference](reference/commands.md).
