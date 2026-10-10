# Synlynk documentation

Use the path that matches what you are trying to do:

- [10-minute quickstart](quickstart.md) — install Synlynk, initialize a repo, run one task, and verify the result.
- [Task-oriented how-tos](how-to/README.md) — focused recipes for setup, dispatch, and inspecting work.
- [Command reference](reference/commands.md) — the complete CLI catalog, generated from `COMMAND_TAXONOMY`.
- [Agent vs harness glossary](glossary-agent-vs-harness.md) — the short answer to who owns work and which tool executes it.

The command reference is generated; edit `synlynk/taxonomy.py` and run
`python3 scripts/generate_command_docs.py` when the CLI surface changes.
