# Opt-In Anonymous Telemetry & FTUE Hardening Design

- **Date:** 2026-11-08
- **Author:** Agy (Gemini)
- **Status:** Draft / Pending Sign-Off
- **Scope:** Privacy-Preserving Observability, User-Selected Telemetry Topics, Global Capability & Cost Matrix Feed, FTUE Robustness

---

## 1. Intent & Context

### 1.1 The Post-Release Observability Gap
Synlynk is designed from the ground up as a **local-first, local-only** control plane. It operates directly against local git repositories, local SQLite databases (`state.db`), and local agent harnesses. Consequently, after the Developer Preview v0.29.0 release, maintainers have no empirical insight into:
- Whether users successfully make it from `pipx install synlynk` to their first completed merge.
- What percentage of users choose greenfield vs brownfield workflows.
- Which agent harnesses and model families are actively delivering value in the wild (Claude, Agy, Codex, Grok, OpenRouter, Local Ollama/MLX).
- Real-world task tokenomics, quota burn rates, and model capability drift across development stacks.
- Common failure points during FTUE (First Time User Experience), migration, or routine command execution.

### 1.2 Core Privacy & Sovereignty Constraints
Any telemetry solution in Synlynk **must** strictly adhere to the following non-negotiable architectural invariants:
1. **Strictly Opt-In (Default OFF):** Outbound network reporting is disabled by default. Synlynk will never phone home unless the user explicitly opts in during `synlynk init` or runs `synlynk telemetry enable`.
2. **Granular Topic Selection (User-Selected Domains):** Telemetry is not an all-or-nothing toggle. Users can select exact information domains (`lifecycle`, `tokenomics`, `capability`, `diagnostics`) they wish to share.
3. **Zero PII (Personally Identifiable Information):** No usernames, email addresses, git author strings, repository URLs, absolute file system paths, code contents, commit messages, or prompt text shall ever be collected or transmitted.
4. **No Heavy SDKs or Binary Dependencies:** Reporting must use Python standard library (`urllib.request`) only, adding 0KB of third-party package dependencies.
5. **Fire-and-Forget Resilience:** Telemetry pings must run in a background daemon thread or subprocess with a hard 1.0s timeout. Network drops, corporate proxies, firewall blocks, or offline airgapped environments must fail completely silently without impacting CLI performance or returning non-zero exit codes.
6. **Inspectable & Auditable:** Users can inspect the exact payload at any time via `synlynk telemetry inspect` or `synlynk telemetry test --dry-run`.

---

## 2. Granular Telemetry Domains & Topic Selection

Users can choose to report on any combination of four discrete telemetry topics:

| Topic | Description | Included Data | Excluded Data |
| :--- | :--- | :--- | :--- |
| **`lifecycle`** | FTUE and workspace lifecycle health | CLI command invoked (`init`, `status`, `pr check`, `migrate`, `upgrade`), lifecycle tier (`greenfield`, `brownfield`, `migrated`), OS platform, Python version, Synlynk version. | No file names, branch names, or project directories. |
| **`tokenomics`** | Cost, token burn, and quota efficiency | Plan tier, token budget limits, prompt/completion/cached token counts per task, estimated vs actual USD cost, quota burn-rate multiplier. | No prompt content, code diffs, or pricing secrets. |
| **`capability`** | Multi-model routing & dispatch outcomes | Detected harnesses (`claude`, `agy`, `codex`, `grok`, `local`), model IDs invoked (`claude-sonnet-4-6`, `gemini-2.5-pro`, `o3-mini`), task engg domain (`backend`, `frontend`, `testing`), dispatch success/retry/fallback rates. | No task descriptions, commit messages, or code tokens. |
| **`diagnostics`** | Error categories and failure classification | Normalized exception classes (`SqliteOperationalError`, `GitCalledProcessError`, `RateLimitError`, `ConfigNotFound`), exit code. | No file paths, stack traces, or command arguments. |

### 2.1 Configuration Schema
Stored in `~/.synlynk/config.json` (user global) with workspace-level override in `.synlynk/config.json`:
```json
{
  "telemetry": {
    "enabled": false,
    "anonymous_id": "c7f93a10-2b91-4d1a-85b4-93f8e1329a1b",
    "endpoint": "default",
    "topics": {
      "lifecycle": true,
      "tokenomics": true,
      "capability": true,
      "diagnostics": true
    }
  }
}
```

---

## 3. Global Cost & Capability Matrix Contribution

When `tokenomics` and `capability` topics are enabled, Synlynk emits anonymized task execution summaries that contribute to the Synaptic AI Capability Index and public model capability benchmarks:

### 3.1 Task Execution Event (`task_completed`)
Emitted at the completion of an agent dispatch or story execution:
```json
{
  "client_id": "c7f93a10-2b91-4d1a-85b4-93f8e1329a1b",
  "events": [
    {
      "name": "task_completed",
      "params": {
        "plan_type": "solo",
        "harness": "codex",
        "model_id": "o3-mini",
        "task_domain": "backend",
        "task_discipline": "platform",
        "token_quota_tier": "tier_1",
        "prompt_tokens": 14200,
        "completion_tokens": 850,
        "cached_tokens": 12100,
        "cost_estimated_usd": 0.042,
        "cost_actual_usd": 0.038,
        "cost_drift_percent": -9.5,
        "burn_rate_multiplier": 1.0,
        "duration_seconds": 18,
        "outcome": "success",
        "fallback_triggered": false,
        "synlynk_version": "0.29.0",
        "os_platform": "darwin"
      }
    }
  ]
}
```

### 3.2 Value Delivered to the Community & Platform
- **Empirical Model Efficiency:** Proves actual token-to-outcome efficiency across real-world tasks rather than artificial synthetic benchmarks.
- **Dynamic Burn-Rate Calibration:** Calibrates default cost and burn-rate weights across model families (Claude 3.5 Sonnet vs Gemini 2.5 Pro vs Grok 3 vs Local models).
- **Fallback Intelligence:** Identifies common harness failure patterns and optimizes automatic retry and fallback routing rules.

---

## 4. Empirical FTUE Hardening Findings (OrbStack Ubuntu 24.04 Run)

During pristine end-to-end user scenario testing on an isolated Ubuntu 24.04 VM (`synlynk-preview` on OrbStack), three concrete user friction points were discovered and logged as routine tracking issues:

### 4.1 Bug 1: `synlynk status` on Fresh Repo (`sqlite3.OperationalError`) <!-- id:story-142f3886 -->
- **Observed Behavior:** In a fresh repository where `synlynk init` has not yet touched SQLite, or when running `status` before any state-mutating command, `_get_db(read_only=True)` opens SQLite with URI `?mode=ro`. In SQLite, `mode=ro` crashes (`sqlite3.OperationalError: unable to open database file`) if the file does not exist on disk.
- **Root Cause:** `synlynk/cli.py` opens `read_only=True` without checking if `DB_PATH` exists on disk.
- **Assigned Ticket:** `story-142f3886` (`Fix synlynk status OperationalError when state.db missing on fresh repo`).
- **Fix:** In `_get_db()`, if `read_only=True` and `not os.path.exists(db_path)`, return a transient empty in-memory or newly initialized database instance rather than crashing.

### 4.2 Bug 2: `synlynk migrate` Crash on Untracked `project-docs/` (Exit Code 128) <!-- id:story-f9471e24 -->
- **Observed Behavior:** When migrating a repo where `project-docs/` was created but not yet committed to the git index, `synlynk migrate` executes `subprocess.run(["git", "rm", "--cached", "-r", "--quiet", raw_docs_dir], check=True)`. Git exits with code 128 (`fatal: pathspec 'project-docs' did not match any files`), aborting the migration and triggering rollback.
- **Root Cause:** Unconditional `check=True` assuming `project-docs/` is already tracked in the git index.
- **Assigned Ticket:** `story-f9471e24` (`Guard git rm cached in synlynk migrate against untracked project-docs`).
- **Fix:** Check `git ls-files --error-unmatch project-docs` first, or run `git rm --cached` with `check=False` so untracked directories do not abort migration.

### 4.3 Bug 3: `.synlynk/instructions.json` Working Tree Timestamp Churn <!-- id:story-3e8f9412 -->
- **Observed Behavior:** Every time an instruction check or `synlynk pr check` runs, `_write_instruction_manifest()` unconditionally overwrites `"generated_at"` and `"last_checked"` with current ISO timestamps. This marks `.synlynk/instructions.json` as dirty in `git status`, blocking subsequent branch checkouts and merges (`error: Your local changes would be overwritten by checkout`).
- **Root Cause:** Manifest write is unconditional regardless of whether file SHAs changed.
- **Assigned Ticket:** `story-3e8f9412` (`Prevent instructions.json timestamp churn when SHAs unchanged`).
- **Fix:** Skip disk write if the loaded manifest's SHAs and synlynk version match the computed values exactly.

---

## 5. CLI UX & Commands

```bash
# Inspection and Status
synlynk telemetry status               # Shows: [Telemetry: DISABLED (Opt-in only)]
synlynk telemetry inspect              # Displays exact JSON payload structure
synlynk telemetry test --dry-run        # Validates transport & schema locally

# Granular Enablement
synlynk telemetry enable               # Enables all topics with confirmation
synlynk telemetry enable --topics lifecycle,tokenomics,capability
synlynk telemetry configure            # Interactive checklist prompt for topics
synlynk telemetry disable              # Disables all outbound telemetry

# Anonymity Management
synlynk telemetry rotate-id            # Generates fresh cryptographic UUIDv4
```

### 5.1 Interactive `synlynk init` Prompt
During `synlynk init` interactive wizard:
```
✦ Help improve Synlynk?
  Synlynk is local-first. You can optionally share anonymous statistics to help improve routing and model capabilities.
  [1] Opt-in to all topics (lifecycle, tokenomics, capability benchmarks, errors)
  [2] Select specific topics
  [3] Opt-out completely (Default [Enter])
Select [1/2/3]: 3
```
In non-interactive or `--auto-defaults` mode, telemetry is **strictly disabled by default**.

---

## 6. Network Transport Specification

```python
def send_telemetry_event(event_name: str, topic: str, params: dict) -> None:
    """Non-blocking, fire-and-forget anonymous telemetry beacon."""
    if not is_telemetry_topic_enabled(topic):
        return

    def _worker():
        try:
            payload = _build_payload(event_name, params)
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                _get_endpoint_url(),
                data=data,
                headers={"Content-Type": "application/json", "User-Agent": f"synlynk/{VERSION}"},
            )
            with urllib.request.urlopen(req, timeout=1.0) as resp:
                pass
        except Exception:
            # Completely silent failure
            pass

    threading.Thread(target=_worker, daemon=True).start()
```

---

## 7. Autonomous Execution Plan

1. **FTUE Gaps:** Dispatched to relevant role agents as routine operational backlog stories (`story-142f3886`, `story-f9471e24`, `story-3e8f9412`).
2. **Telemetry Implementation Plan:** Upon sign-off of this spec, author implementation plan in `docs/superpowers/plans/2026-11-08-opt-in-telemetry.md`.
3. **Build & Verification:**
   - Unit tests in `tests/test_telemetry.py` (contract tests, PII sanitizer assertions, topic filtering, timeout verification).
   - End-to-end verification in OrbStack `synlynk-preview` VM.
