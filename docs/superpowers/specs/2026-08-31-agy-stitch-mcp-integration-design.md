# Design Spec: Agy Stitch MCP Integration (#573)

- **Issue:** #573 (Agy cannot call Stitch MCP tools (`mcp__stitch__*`) in headless dispatch)
- **Tracking Story:** `story-f51c7705`
- **Linked Goal:** `goal-a222b393`
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-08-31
- **Status:** Approved

---

## 1. Problem Statement & Root Cause Analysis

### 1.1 Symptoms
When dispatching headless design or screen-generation tasks to Agy (`synlynk dispatch agy`), attempts to call Stitch MCP tools failed or were reported as missing.

### 1.2 Root Cause Findings
Independent empirical investigation on the host environment revealed two distinct gaps:

1. **Configuration & Discovery Gap:**
   - Stitch was installed in `~/.gemini/extensions/Stitch/` using the Gemini CLI (`gemini extensions install https://github.com/gemini-cli-extensions/stitch`).
   - The Gemini CLI (`gemini`) reads extensions from `~/.gemini/extensions/`.
   - In contrast, `synlynk dispatch agy` invokes **Antigravity CLI (`agy`)**.
   - Antigravity CLI does **not** read `~/.gemini/extensions/`; it loads MCP servers exclusively from `~/.gemini/config/mcp_config.json` (or plugin-scoped `mcp_config.json`).
   - Prior to investigation, `~/.gemini/config/mcp_config.json` was 0 bytes empty. `agy mcp list` reported `No MCP servers configured.`

2. **Tool-Calling Paradigm Mismatch:**
   - In Anthropic Claude Code, MCP tools are flattened into global tools with prefix syntax: `mcp__<server>__<tool_name>` (e.g. `mcp__stitch__generate_screen_from_text`).
   - In Google Antigravity CLI (`agy`), MCP servers do not create flat `mcp__<server>__*` tools; instead, Antigravity provides the built-in meta-tool:
     ```json
     call_mcp_tool(server="stitch", tool="<tool_name>", arguments={...})
     ```
   - Dispatched prompts that asked Agy to invoke `mcp__stitch__*` caused model confusion because that exact tool name does not exist in Agy's tool declarations.

3. **Empirical Verification of Fix:**
   - Configuring `stitch` in `~/.gemini/config/mcp_config.json` via:
     ```bash
     agy mcp add --env GOOGLE_CLOUD_PROJECT=gen-lang-client-0187568210 stitch npx -y stitch-mcp@1.0.0
     ```
   - Testing live headless execution with `agy -p "Call the stitch tool list_projects via call_mcp_tool" --dangerously-skip-permissions` succeeded completely:
     - Verified Google Cloud ADC auth against project `gen-lang-client-0187568210`.
     - Successfully executed `list_projects` and returned 6 live projects from Stitch (`RxCC UX Redesign Framework`, `Vdowrx.ai SaaS Platform`, `Dashboard - Reframe AI`, `Dialify Corporate SPA`, `Dialify Website`, `AI Video Reframe`).

---

## 2. Architecture & Design

### 2.1 Configuration Diagnostics & Auto-Remediation (`synlynk/doctor.py`)
1. **TC-8: Stitch MCP Configuration Check:**
   - Define `_check_agy_stitch_mcp(mcp_config_path=None)`:
     - Inspects `~/.gemini/config/mcp_config.json`.
     - Validates that `"stitch"` is present in `mcpServers`, enabled, and configured with command `npx` and args containing `stitch-mcp`.
2. **`synlynk doctor --fix agy` Remediation:**
   - Extend `_build_agy_fix_plan()` to inspect both `settings.json` (TC-7 GitHub write rules) and `~/.gemini/config/mcp_config.json` (Stitch MCP server).
   - If `stitch` is missing from `mcp_config.json`, propose and apply the standard `stitch` configuration.

### 2.2 Preflight Validation (`synlynk/dispatch.py`)
- In `_preflight_dispatch()`:
  - If a dispatch explicitly requires `stitch` or `mcp` (`--requires stitch` or `--requires mcp`), check whether the required MCP server is configured in `~/.gemini/config/mcp_config.json` when `agent == "agy"`.
  - If missing, fail closed with `sentinel: "MCP_SERVER_MISSING"` pointing to `synlynk doctor --fix agy` or `agy mcp add`.

### 2.3 Prompt Adaptation Header (`synlynk/dispatch.py`)
- In `_format_prompt_for_agent()` for `agy`:
  - When the task text contains `stitch` or `mcp__stitch`, inject a directive:
    ```markdown
    ## Stitch MCP Tool Usage Note
    Stitch MCP tools on Agy are called via the built-in meta-tool:
    call_mcp_tool(server="stitch", tool="<tool_name>", arguments={...})
    Do not call `mcp__stitch__<tool_name>` directly.
    ```

### 2.4 Capability Baselines (`synlynk/_constants.py`)
- In `HARNESS_CAPABILITY_BASELINES["agy"]["network_deps"]["optional_endpoints"]`:
  - Add `"stitch.googleapis.com:443"`.

---

## 3. Testing Strategy
- `tests/test_doctor.py`: Unit tests for TC-8 Stitch MCP check and `synlynk doctor --fix agy` remediation.
- `tests/test_dispatch.py`: Unit tests for `--requires stitch` preflight gate and prompt adapter injection.
- Run full pytest suite across `test_synlynk.py`, `test_dispatch.py`, `test_doctor.py`, and `test_jobs.py`.
