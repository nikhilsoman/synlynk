# synlynk-dist — Archive

**Archived:** 2026-05-26  
**Originally created:** 2026-05-16 in `pbmr/synlynk-dist/`  
**Version:** v1.1.0 (bash-era, pre-CLI)

## What this is

This directory contains the original "Pulse / synlynk" distribution package — a bash-script installer and a `SYNLYNK_GUIDE.md` designed to be pasted into AI system prompts. It predates synlynk becoming a first-class Python CLI repo.

At the time, synlynk was a manual protocol:
- `install.sh` bootstrapped `project-docs/` structure via interactive shell script
- `SYNLYNK_GUIDE.md` was copied into AI tool custom instructions or system prompts
- No CLI binary existed — the AI tool was instructed to maintain docs manually
- `GEMINI.md` was a minimal 2-line guideline, not the full session protocol
- The config used `version: "1.1.0"` — an internal version predating the public 0.x series

## Why archived

synlynk became a standalone Python CLI starting with v0.1.0 (2026-05-14). The bash-era installer and guide-as-system-prompt approach was superseded by:
- `synlynk init` — creates project structure + AI instruction files
- `synlynk exec <cmd>` — wraps AI CLIs with context injection
- Full `CLAUDE.md`, `GEMINI.md`, and (upcoming) `AGENTS.md` templates with complete session protocol

## Historical context

The pbmr (Playblazer) project used this distribution to set up its `project-docs/` directory in team mode. The project-docs there remain operational but are not CLI-managed.

## Reference

For the current install and usage, see:
- `../../../README.md` — current synlynk docs
- `../../../install.sh` — current installer
- `../../../bin/synlynk.py` — CLI source
