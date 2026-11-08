# Opt-In Anonymous Telemetry & FTUE Hardening Design

- **Date:** 2026-11-08
- **Author:** Agy (Gemini)
- **Status:** Draft / Pending Sign-Off
- **Scope:** Privacy-Preserving Observability, FTUE Robustness, Post-Release Verification

---

## 1. Intent & Context

### 1.1 The Post-Release Observability Gap
Synlynk is designed from the ground up as a **local-first, local-only** control plane. It operates directly against local git repositories, local SQLite databases (`state.db`), and local agent harnesses. Consequently, after the Developer Preview v0.29.0 release, maintainers have no empirical insight into:
- Whether users successfully make it from `pipx install synlynk` to their first completed merge.
- What percentage of users choose greenfield vs brownfield workflows.
- Which agent harnesses are detected and active in the wild (Claude, Agy, Codex, Grok, OpenRouter).
- Common failure points during FTUE (First Time User Experience), migration, or routine command execution.

### 1.2 Core Privacy & Sovereignty Constraints
Any telemetry solution in Synlynk **must** strictly adhere to the following non-negotiable architectural invariants:
1. **Strictly Opt-In (Default OFF):** Outbound network reporting is disabled by default. Synlynk will never phone home unless the user explicitly opts in during `synlynk init` or runs `synlynk telemetry enable`.
2. **Zero PII (Personally Identifiable Information):** No usernames, email addresses, git author strings, repository URLs, absolute file system paths, code contents, commit messages, or prompt text shall ever be collected or transmitted.
3. **No Heavy SDKs or Binary Dependencies:** Reporting must use Python standard library (`urllib.request`) only, adding 0KB of third-party package dependencies.
4. **Fire-and-Forget Resilience:** Telemetry pings must run in a background daemon thread or subprocess with a hard 1.0s timeout. Network drops, corporate proxies, firewall blocks, or offline airgapped environments must fail completely silently without impacting CLI performance or returning non-zero exit codes.
5. **Inspectable & Auditable:** Users can inspect the exact payload at any time via `synlynk telemetry inspect` or `synlynk telemetry test --dry-run`.

---

## 2. Empirical FTUE Hardening Findings (OrbStack Ubuntu 24.04 Run)

During pristine end-to-end user scenario testing on an isolated Ubuntu 24.04 VM (`synlynk-preview` on OrbStack), three concrete user friction points were discovered:

### 2.1 Bug 1: `synlynk status` on Fresh Repo (`sqlite3.OperationalError`)
- **Observed Behavior:** In a fresh repository where `synlynk init` has not yet populated or touched SQLite, or when running `status` before any state-mutating command, `_get_db(read_only=True)` opens SQLite with URI `?mode=ro`. In SQLite, `mode=ro` crashes (`sqlite3.OperationalError: unable to open database file`) if the file does not exist.
- **Root Cause:** `synlynk/cli.py` opens `read_only=True` without checking if `DB_PATH` exists on disk.
- **Fix:** In `_get_db()`, if `read_only=True` and `not os.path.exists(db_path)`, return a transient empty in-memory or newly initialized database instance rather than crashing.

### 2.2 Bug 2: `synlynk migrate` Crash on Untracked `project-docs/` (Exit Code 128)
- **Observed Behavior:** When migrating a repo where `project-docs/` was created but not yet committed to the git index, `synlynk migrate` executes `subprocess.run(["git", "rm", "--cached", "-r", "--quiet", raw_docs_dir], check=True)`. Git exits with code 128 (`fatal: pathspec 'project-docs' did not match any files`), aborting the migration and triggering rollback.
- **Root Cause:** Unconditional `check=True` assuming `project-docs/` is already tracked in the git index.
- **Fix:** Check `git ls-files --error-unmatch project-docs` first, or run `git rm --cached` with `check=False` so untracked directories do not abort migration.

### 2.3 Bug 3: `.synlynk/instructions.json` Working Tree Timestamp Churn
- **Observed Behavior:** Every time an instruction check or `synlynk pr check` runs, `_write_instruction_manifest()` unconditionally overwrites `"generated_at"` and `"last_checked"` with current ISO timestamps. This marks `.synlynk/instructions.json` as dirty in `git status`, blocking subsequent branch checkouts and merges (`error: Your local changes would be overwritten by checkout`).
- **Root Cause:** Manifest write is unconditional regardless of whether file SHAs changed.
- **Fix:** Skip disk write if the loaded manifest's SHAs and synlynk version match the computed values exactly.

---

## 3. Opt-In Anonymous Telemetry Architecture

### 3.1 Configuration & Consent Storage
Consent is stored in the global user configuration `~/.synlynk/config.json` with workspace-level override support in `.synlynk/config.json`:
```json
{
  "telemetry": {
    "enabled": false,
    "anonymous_id": "c7f93a10-2b91-4d1a-85b4-93f8e1329a1b",
    "endpoint": "default"
  }
}
```

### 3.2 Anonymous Identifier Generation
At first run (or upon first opt-in), Synlynk generates a cryptographic random UUIDv4 (`uuid.uuid4()`) and saves it to `~/.synlynk/telemetry_id`.
- The ID contains no entropy derived from MAC address, IP, hostname, or username.
- Users can regenerate their ID at any time with `synlynk telemetry rotate-id`.

### 3.3 Event Schema (Google Analytics 4 Measurement Protocol & OTLP JSON)
The default outbound sink is GA4 Measurement Protocol HTTP POST:
- **Endpoint:** `https://www.google-analytics.com/mp/collect?api_secret={SECRET}&measurement_id={ID}`
- **Payload Structure:**
```json
{
  "client_id": "c7f93a10-2b91-4d1a-85b4-93f8e1329a1b",
  "non_personalized_ads": true,
  "events": [
    {
      "name": "cli_command",
      "params": {
        "command": "init",
        "subcommand": "brownfield",
        "synlynk_version": "0.29.0",
        "python_version": "3.12",
        "os_platform": "linux",
        "os_arch": "arm64",
        "install_method": "pipx",
        "harnesses_detected": "claude,agy",
        "outcome": "success",
        "duration_bucket": "1_5s"
      }
    }
  ]
}
```

### 3.4 Key Tracked Events
1. `cli_command`: Emitted at command completion for top-level commands (`init`, `status`, `dispatch`, `migrate`, `upgrade`, `pr check`, `story`, `goal`).
2. `ftue_completed`: Emitted when `synlynk init` successfully completes, recording whether the repo was `greenfield` or `brownfield`.
3. `command_error`: Emitted when an unhandled exception occurs, containing only the normalized exception class name (e.g. `SqliteOperationalError`, `GitCalledProcessError`, `ConfigNotFound`), with no tracebacks, file paths, or error messages.

### 3.5 Network Transport Specification
```python
def send_telemetry_event(event_name: str, params: dict) -> None:
    """Non-blocking, fire-and-forget anonymous telemetry beacon."""
    if not is_telemetry_enabled():
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

## 4. CLI UX & Commands

```
synlynk telemetry status       # Shows: [Telemetry: DISABLED (Opt-in only)]
synlynk telemetry enable       # Enables anonymous telemetry
synlynk telemetry disable      # Disables anonymous telemetry
synlynk telemetry inspect      # Prints sample JSON payload that would be sent
synlynk telemetry test --dry-run # Validates configuration without sending
```

During `synlynk init` interactive flow:
```
✦ Help improve Synlynk?
  Send anonymous, non-PII usage statistics (command names, errors, version)?
  [y/N]: N
```
In `--auto-defaults` or non-interactive mode, telemetry is **always defaulted to OFF**.

---

## 5. Verification Plan

### 5.1 Unit & Contract Tests
- `tests/test_telemetry.py`:
  - Assert telemetry is disabled by default.
  - Assert zero network calls when disabled.
  - Assert payload validator rejects any string containing `@`, `/home/`, `/Users/`, or git URLs.
  - Assert thread timeout does not hang CLI.
  - Assert `synlynk telemetry enable / disable / inspect` modifies config correctly.

### 5.2 OrbStack VM Verification
- Run inside `synlynk-preview` VM:
  1. Test `synlynk status` on an empty directory before init (verify no `OperationalError`).
  2. Test `synlynk migrate` with untracked `project-docs/` (verify no exit code 128).
  3. Test `synlynk instructions status` followed by git checkout (verify no dirty working tree).
  4. Test `synlynk telemetry inspect` and `synlynk telemetry test --dry-run`.
