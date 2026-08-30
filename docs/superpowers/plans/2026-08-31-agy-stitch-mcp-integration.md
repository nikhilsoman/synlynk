# Implementation Plan: Agy Stitch MCP Integration (#573)

- **Tracking Story:** `story-f51c7705`
- **Linked Goal:** `goal-a222b393`
- **Author:** Agy (Gemini) [@agy]
- **Date:** 2026-08-31

---

## Proposed Changes

### 1. `synlynk/_constants.py`
- Add `"stitch.googleapis.com:443"` to `HARNESS_CAPABILITY_BASELINES["agy"]["network_deps"]["optional_endpoints"]`.

### 2. `synlynk/doctor.py`
- Implement `_check_agy_stitch_mcp(mcp_config_path: Optional[str] = None) -> dict`:
  - Validates `~/.gemini/config/mcp_config.json` contains a valid, enabled `stitch` server config.
- Update `_build_agy_fix_plan()` / `cmd_doctor_fix()`:
  - If `stitch` is missing or disabled in `mcp_config.json`, produce a remediation plan that configures:
    ```json
    {
      "mcpServers": {
        "stitch": {
          "command": "npx",
          "args": ["-y", "stitch-mcp@1.0.0"],
          "disabled": false,
          "env": {
            "GOOGLE_CLOUD_PROJECT": "gen-lang-client-0187568210"
          }
        }
      }
    }
    ```
- Wire `TC-8 agy-stitch-mcp-preflight` into `synlynk doctor` output under `agy`.

### 3. `synlynk/dispatch.py`
- In `_preflight_dispatch()`:
  - When `harness_name == "agy"` and (`"stitch"` in declared_requires or `"mcp"` in declared_requires):
    - Check `_check_agy_stitch_mcp()`.
    - If not passed and not `force_agent`, fail closed with `sentinel: "MCP_SERVER_MISSING"`.
- In `_format_prompt_for_agent()`:
  - For `agy`, if `"stitch"` or `"mcp__stitch"` is detected in `task`, prepend `## Stitch MCP Tool Usage Note` reminding the agent to invoke `call_mcp_tool(server="stitch", tool="<tool_name>", arguments={...})`.

### 4. Tests
- Add unit tests in `tests/test_doctor.py`:
  - `test_check_agy_stitch_mcp_ok()`
  - `test_check_agy_stitch_mcp_missing()`
  - `test_build_agy_fix_plan_includes_stitch_mcp()`
- Add unit tests in `tests/test_dispatch.py`:
  - `test_preflight_blocks_missing_stitch_mcp_when_required()`
  - `test_format_prompt_for_agy_injects_stitch_tool_hint()`
- Run full test suite.

---

## Verification Steps
1. `python -m pytest tests/test_doctor.py tests/test_dispatch.py -q`
2. `python -m pytest tests/test_synlynk.py -q` (all 499 tests)
3. Run `synlynk doctor` and confirm `TC-8 agy-stitch-mcp-preflight: ✓`.
