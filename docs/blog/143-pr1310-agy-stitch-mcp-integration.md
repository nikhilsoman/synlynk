---
title: "PR #1310 — Fleet Parity: Agy Stitch MCP Integration, Diagnostics, and Prompt Guidance"
date: 2026-08-31
series: "Building the OS for Multi-Agent Development"
post: 143
pr: "#1310"
issue: "#573"
status: merged
---

# PR #1310 — Fleet Parity: Agy Stitch MCP Integration, Diagnostics, and Prompt Guidance

## The Broader Goal at the End of the Previous PR

PR #1309 closed issue #347, completing the entire original fleet parity cluster (#332, #338, #340, #342, #347, #348, #419, #461). Next on the roadmap was issue #573: investigating and resolving why Agy (Google Antigravity CLI) was reported unable to invoke Stitch MCP tools in headless dispatches.

## What Was Missing & The Real Root Cause

1. **Configuration Gap:** Stitch had been installed via the Gemini CLI extension installer (`gemini extensions install https://github.com/gemini-cli-extensions/stitch`), which placed extension metadata under `~/.gemini/extensions/Stitch/`. But `synlynk dispatch agy` invokes the Antigravity CLI (`agy`), which does not read `~/.gemini/extensions/`. Antigravity loads MCP servers exclusively from `~/.gemini/config/mcp_config.json`, which was empty.
2. **Tool Invocation Paradigm Mismatch:** Prompts assumed the Claude Code convention of flat, prefixed tool names (`mcp__stitch__*`). In Antigravity CLI, MCP tools are invoked through the built-in meta-tool `call_mcp_tool(server="stitch", tool="<tool_name>", arguments={...})`.
3. **Live Verification:** Once `stitch` was added to `~/.gemini/config/mcp_config.json` (`npx -y stitch-mcp@1.0.0` with project `gen-lang-client-0187568210`), live headless dispatch verified that `call_mcp_tool` executed without permission prompts, successfully returning live Stitch projects.

## What Shipped

1. **Capability Baseline Update:** Added `stitch.googleapis.com:443` to optional network endpoints for Agy in `synlynk/_constants.py`.
2. **TC-8 Doctor Preflight:** Added `_run_tc8()` in `synlynk/doctor.py` asserting that `~/.gemini/config/mcp_config.json` has an active, enabled `stitch` server configuration.
3. **Doctor Auto-Remediation:** Added `_build_agy_stitch_fix_plan()` to `synlynk doctor --fix agy` for one-command remediation.
4. **Dispatch Preflight & Prompt Adaptation:**
   - Enforced `--requires stitch` / `--requires mcp` checks in `synlynk/dispatch.py:_preflight_dispatch()`.
   - Injected the `## Stitch MCP Tool Usage Note` reminding Agy to invoke `call_mcp_tool` whenever Stitch is referenced.
5. **Tests:** Added comprehensive unit tests in `tests/test_synlynk.py` and `tests/test_dispatch.py`. All 504 tests pass.
