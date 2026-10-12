# Config Decomposition Follow-Up (gh:#2147) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Migrate the 8 remaining `.synlynk/config.json` direct-reader call-sites (found by gh:#2101's post-plan review, filed as gh:#2147) to read from the correct split file, with legacy `config.json` fallback, so they stop silently regressing on any repo that has already run the gh:#2101 migration — including this repo itself.

**Architecture:** Every field touched by these 8 call-sites (`autonomy_mode`, `workspace_id`, `home_harness`, `goal_aliases`/`governs.goal_aliases`, `product_id`, `version_policy`) is absent from both `_BILLING_KEYS` and `_POLICY_MIGRATED_KEYS` in `synlynk/__init__.py`, so by `cmd_config_set()`'s own routing rule (`synlynk/__init__.py:1365-1380`, the `else` branch) every one of them is a **`workspace.json`** key. The existence-check call-sites (`github_app_auth.py`, `team.py` x2) are not field reads at all — they test "has this repo been synlynk-initialized," which must now mean "does `workspace.json` or legacy `config.json` exist," matching the exact precedent already set in Task 10 of the governing plan (`docs/superpowers/plans/2026-10-09-config-decomposition-plan.md:1058-1117`, `coldstart.py`'s init-detection fix).

**Tech Stack:** Python 3 stdlib (`json`, `os`, `pathlib`), pytest, `tmp_path`/`monkeypatch.chdir` fixtures — no new dependencies, matching the governing design spec's "no `jsonschema` dependency" constraint.

---

## Governing references

- Design (approved, do not re-litigate): `docs/superpowers/specs/2026-10-09-config-decomposition-design.md`
- Pattern template (mirror its step shape exactly): `docs/superpowers/plans/2026-10-09-config-decomposition-plan.md`, Tasks 5 (field-read pattern), 6 (test-rewrite pattern), 10 (existence-check pattern)
- Source issue: gh:#2147
- Key routing rule used throughout this plan: `synlynk/__init__.py:1365-1380` (`cmd_config_set`) — a key not in `_BILLING_KEYS` (`budget`, `harness_billing`, `payment_models`, `capability_sweep`) and not in `_POLICY_MIGRATED_KEYS` (`qa_gate_mode`, `roles`, `story_classification`, `sentinel`) is a `workspace.json` key.
- Existence-check idiom to reuse verbatim (already used twice in `synlynk/__init__.py:1452` and `:1570`): `".synlynk/workspace.json" if os.path.exists(".synlynk/workspace.json") else ".synlynk/config.json"`

All 8 tasks below are independent — no task depends on another's code changes, only on the shared idiom above. They may be executed in any order, including in parallel across dispatched workers.

---

## Task 1: `synlynk/autonomy.py:13` — `get_autonomy_mode()`/`set_autonomy_mode()`

**Files:**
- Modify: `synlynk/autonomy.py:11-13` (`_get_config_path`), and the read/write bodies of `get_autonomy_mode()`/`set_autonomy_mode()` that call it
- Test: `tests/test_autonomy_dial.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '1,60p' synlynk/autonomy.py`

Current `_get_config_path()`:

```python
def _get_config_path() -> str:
    return os.path.join(os.getcwd(), ".synlynk", "config.json")
```

Both `get_autonomy_mode()` and `set_autonomy_mode()` call `_get_config_path()` and then read/write the `autonomy_mode` key in whatever file it returns. Post-migration, `.synlynk/config.json` no longer exists (renamed to `config.json.bak`), so `get_autonomy_mode()` always falls through to its `return AutonomyMode.SUPERVISED` default, and `set_autonomy_mode()` writes a key nothing ever reads again.

- [ ] **Step 2: Write a new direct test for the updated read path**

Add to `tests/test_autonomy_dial.py`:

```python
def test_autonomy_mode_reads_from_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"autonomy_mode": "autonomous"}, f)
    from synlynk.autonomy import get_autonomy_mode, AutonomyMode
    assert get_autonomy_mode() == AutonomyMode.AUTONOMOUS


def test_autonomy_mode_falls_back_to_legacy_config_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/config.json", "w", encoding="utf-8") as f:
        json.dump({"autonomy_mode": "manual"}, f)
    from synlynk.autonomy import get_autonomy_mode, AutonomyMode
    assert get_autonomy_mode() == AutonomyMode.MANUAL
```

Check `tests/test_autonomy_dial.py`'s top imports already include `os` and `json`; add them if missing.

- [ ] **Step 3: Run tests to verify the first one fails**

Run: `pytest tests/test_autonomy_dial.py -k workspace_json -v`
Expected: FAIL (reads `.synlynk/config.json`, which doesn't exist in the new test's fixture, so it falls back to the `SUPERVISED` default instead of `AUTONOMOUS`)

- [ ] **Step 4: Update `_get_config_path()`**

```python
def _get_config_path() -> str:
    workspace_path = os.path.join(os.getcwd(), ".synlynk", "workspace.json")
    if os.path.exists(workspace_path):
        return workspace_path
    return os.path.join(os.getcwd(), ".synlynk", "config.json")
```

No other change needed — `get_autonomy_mode()`/`set_autonomy_mode()` already just read/write whatever path this returns.

Sanity-check for other callers that might pass an explicit legacy path: `grep -rn "_get_config_path\|autonomy_mode" synlynk/ | grep -v test_` — confirm `autonomy.py` is the only module touching this key directly (per gh:#2147's own audit, `cli.py:3207` and `vizor_daemon.py:647` only call the public `get_autonomy_mode()` function, not the private path helper).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_autonomy_dial.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/autonomy.py tests/test_autonomy_dial.py
git commit -m "$(cat <<'EOF'
fix(autonomy): read autonomy_mode from workspace.json with legacy fallback

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 2: `synlynk/agent_store.py:15` — `_CONFIG_PATH` constant

**Files:**
- Modify: `synlynk/agent_store.py:15-32` (`_CONFIG_PATH`, `_load_raw_config`), and the two write call-sites at `synlynk/agent_store.py:97,103`
- Test: `tests/test_agent_store.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '1,110p' synlynk/agent_store.py`

```python
_CONFIG_PATH = os.path.join(".synlynk", "config.json")

def _load_raw_config() -> dict:
    if not os.path.exists(_CONFIG_PATH):
        return {}
    try:
        with open(_CONFIG_PATH) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
```

`get_workspace_id()` (`synlynk/agent_store.py:81-103`) reads `workspace_id` via `_load_raw_config()` and, on recovery/mint, writes it back via `_write_json_atomic(_CONFIG_PATH, config)` at both lines 97 and 103. `workspace_id` is a `workspace.json` key per the governing design (`docs/superpowers/specs/2026-10-09-config-decomposition-design.md:21-22`).

- [ ] **Step 2: Write a new direct test for the updated read/write path**

Add to `tests/test_agent_store.py`:

```python
def test_get_workspace_id_reads_from_workspace_json(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    wid = "11111111-2222-3333-4444-555555555555"
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"workspace_id": wid}, f)
    from synlynk.agent_store import get_workspace_id
    assert get_workspace_id() == wid


def test_get_workspace_id_mint_writes_to_workspace_json_not_legacy(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({}, f)
    from synlynk.agent_store import get_workspace_id
    minted = get_workspace_id()
    assert minted
    with open(".synlynk/workspace.json", encoding="utf-8") as f:
        saved = json.load(f)
    assert saved.get("workspace_id") == minted
    assert not os.path.exists(".synlynk/config.json")
```

Check the top of `tests/test_agent_store.py` already imports `os` and `json`; add them if missing.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_agent_store.py -k workspace_json -v`
Expected: FAIL — `get_workspace_id()` can't find `.synlynk/config.json`, so `test_get_workspace_id_reads_from_workspace_json` mints a fresh UUID instead of returning the fixture's `wid`, and `test_get_workspace_id_mint_writes_to_workspace_json_not_legacy` finds no `workspace_id` key written to `workspace.json` because it was written to a freshly created `.synlynk/config.json` instead.

- [ ] **Step 4: Update `_CONFIG_PATH`/`_load_raw_config`**

```python
def _config_path() -> str:
    workspace_path = os.path.join(".synlynk", "workspace.json")
    if os.path.exists(workspace_path):
        return workspace_path
    return os.path.join(".synlynk", "config.json")


def _load_raw_config() -> dict:
    path = _config_path()
    if not os.path.exists(path):
        return {}
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return {}
```

Remove the module-level `_CONFIG_PATH = os.path.join(".synlynk", "config.json")` constant and replace its two write call-sites in `get_workspace_id()`:

```python
            _write_json_atomic(_config_path(), config)
```

(both at the former lines 97 and 103).

Sanity-check for other callers: `grep -n "_CONFIG_PATH" synlynk/agent_store.py` should now return zero matches outside this file; `grep -rn "from synlynk.agent_store import _CONFIG_PATH\|agent_store\._CONFIG_PATH" synlynk/ tests/` should return nothing (confirms no external caller depends on the removed constant).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_agent_store.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/agent_store.py tests/test_agent_store.py
git commit -m "$(cat <<'EOF'
fix(agent_store): read/write workspace_id via workspace.json with legacy fallback

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 3: `synlynk/handover.py:159` — `execute_home_handover()`

**Files:**
- Modify: `synlynk/handover.py:148-165`
- Test: `tests/test_handover.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '148,170p' synlynk/handover.py`

```python
def execute_home_handover(
    target_harness: str,
    repo_path: Union[str, Path] = ".",
    force: bool = False,
) -> Dict[str, Any]:
    """Execute dynamic home harness switch with drain-to-boundary protocol."""
    from synlynk import _update_config, load_config
    from synlynk.context import detect_active_home_harness, generate_context

    repo = Path(repo_path).resolve()
    cfg_file = repo / ".synlynk" / "config.json"
    cfg = {}
    if cfg_file.exists():
        try:
            with open(cfg_file, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        except Exception:
            pass
    if not cfg:
        cfg = load_config() if callable(load_config) else {}

    current_home = cfg.get("home_harness") or detect_active_home_harness(cfg)
```

This function already imports `load_config` (the split-file-aware facade) but only falls back to it when the direct legacy-path read is empty/missing. Post-migration, `cfg_file.exists()` is `False` (config.json renamed to config.json.bak), so this is already hitting the `load_config()` fallback today — but the dead legacy-read block is exactly the kind of regression source gh:#2147 is flagging repo-wide, and it masks a real bug: if a **stale, already-migrated-away** `config.json` ever exists on disk (e.g. a half-finished migration or test fixture leftover) alongside a current `workspace.json`, this function would silently prefer the stale file's `home_harness` over the authoritative `workspace.json`.

- [ ] **Step 2: Write a new direct test for the updated read path**

Add to `tests/test_handover.py`:

```python
def test_execute_home_handover_prefers_load_config_over_stale_legacy_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    # Authoritative split file says "codex" is home.
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"home_harness": "codex"}, f)
    # Stale legacy file (e.g. leftover from before migration) says "claude".
    with open(".synlynk/config.json", "w", encoding="utf-8") as f:
        json.dump({"home_harness": "claude"}, f)
    from synlynk.handover import execute_home_handover
    result = execute_home_handover("codex", repo_path=str(tmp_path), force=True)
    assert result["current_home"] == "codex" or result.get("already_home") is True
```

Check `tests/test_handover.py`'s imports already include `os`/`json`; check the existing `test_execute_home_handover_drain_flow` test (line 59) for the exact shape `execute_home_handover()`'s return dict takes and adjust the assertion to match that real shape rather than guessing — read it with `sed -n '59,97p' tests/test_handover.py` before finalizing this assertion.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_handover.py -k stale_legacy -v`
Expected: FAIL — the direct legacy read finds `.synlynk/config.json` present and non-empty, so `cfg["home_harness"]` resolves to the stale `"claude"` instead of `load_config()`'s `"codex"`.

- [ ] **Step 4: Update `execute_home_handover()`**

Remove the direct legacy-file read block entirely and call `load_config()` unconditionally — it already merges `workspace.json`/`billing.json`/`policy.json` with legacy `config.json` fallback internally, so re-implementing that fallback here is exactly the duplicated logic gh:#2147 is asking to remove:

```python
def execute_home_handover(
    target_harness: str,
    repo_path: Union[str, Path] = ".",
    force: bool = False,
) -> Dict[str, Any]:
    """Execute dynamic home harness switch with drain-to-boundary protocol."""
    from synlynk import _update_config, load_config
    from synlynk.context import detect_active_home_harness, generate_context

    repo = Path(repo_path).resolve()
    cfg = load_config() if callable(load_config) else {}

    current_home = cfg.get("home_harness") or detect_active_home_harness(cfg)
```

`load_config()` is already called relative to the process's current working directory, same as the removed direct read was relative to `repo`. Check whether any caller of `execute_home_handover()` passes a `repo_path` that differs from `os.getcwd()`: `grep -rn "execute_home_handover(" synlynk/ tests/`. If a caller does rely on a non-cwd `repo_path`, keep `os.chdir`-free correctness by reading via the same `Path`-based idiom instead, matching `load_workspace()`'s own flat/cwd-relative convention documented in the design spec's Precedence section — but do not add this complexity unless the grep shows a real caller needing it.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_handover.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/handover.py tests/test_handover.py
git commit -m "$(cat <<'EOF'
fix(handover): stop duplicating load_config()'s legacy-fallback logic

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 4: `synlynk/github_app_auth.py:27` — `_default_apps_dir()`

**Files:**
- Modify: `synlynk/github_app_auth.py:23-33`
- Test: `tests/test_github_app_auth.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '23,35p' synlynk/github_app_auth.py`

```python
def _default_apps_dir() -> str:
    """Return the shared GitHub App directory for the current repository."""
    try:
        if not os.path.isfile(os.path.join(".synlynk", "config.json")):
            return os.path.join(".synlynk", "github_apps")
        from synlynk.product_store import resolve_github_apps_dir
        return str(resolve_github_apps_dir("."))
    except Exception:
        return os.path.join(".synlynk", "github_apps")
```

This is the exact bug named in gh:#2147: the existence-check gate (`not os.path.isfile(".synlynk/config.json")`) decides whether to even call the already-migration-aware `resolve_github_apps_dir()` (`synlynk/product_store.py:261-290`, confirmed split-file-aware via `identity_slug_from_config`). Post-migration, this gate is always `True` (config.json renamed to config.json.bak), so it always falls back to the legacy `github_apps` dir even on a fully migrated, fully configured repo — same failure class as gh:#1160 / `worktree-github-apps-gap`.

- [ ] **Step 2: Write a new direct test for the updated gate**

Add to `tests/test_github_app_auth.py`:

```python
def test_default_apps_dir_resolves_via_product_store_after_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"identity_slug": "test-product"}, f)
    from synlynk.github_app_auth import _default_apps_dir
    result = _default_apps_dir()
    # Must not silently fall back to the bare legacy dir once the repo is configured.
    assert result != os.path.join(".synlynk", "github_apps")
```

Check `tests/test_github_app_auth.py`'s imports already include `os`/`json`; add if missing.

- [ ] **Step 3: Run test to verify it fails**

Run: `pytest tests/test_github_app_auth.py -k resolves_via_product_store -v`
Expected: FAIL — `_default_apps_dir()` returns the bare `.synlynk/github_apps` fallback because `.synlynk/config.json` doesn't exist in the fixture.

- [ ] **Step 4: Update `_default_apps_dir()`**

```python
def _default_apps_dir() -> str:
    """Return the shared GitHub App directory for the current repository."""
    try:
        configured = (
            os.path.isfile(os.path.join(".synlynk", "workspace.json"))
            or os.path.isfile(os.path.join(".synlynk", "config.json"))
        )
        if not configured:
            return os.path.join(".synlynk", "github_apps")
        from synlynk.product_store import resolve_github_apps_dir
        return str(resolve_github_apps_dir("."))
    except Exception:
        # Preserve the historical behavior outside a repository or when the
        # daemon module cannot resolve the repository context.
        return os.path.join(".synlynk", "github_apps")
```

Sanity-check for other callers duplicating this exact gate: `grep -rn 'isfile.*config\.json\|isfile.*workspace\.json' synlynk/ | grep -v test_`. If `team.py`'s two sites (Task 7 below) duplicate the same two-file check, that duplication is expected and intentional — each site stays a plain inline check rather than a shared helper, per the governing design's own choice not to introduce new shared abstractions beyond `load_config()`/`load_workspace()`/`load_billing()`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_github_app_auth.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/github_app_auth.py tests/test_github_app_auth.py
git commit -m "$(cat <<'EOF'
fix(github_app_auth): detect repo configuration via workspace.json or legacy config.json

Refs gh:#2147, gh:#2101, gh:#1160

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 5: `synlynk/governs_engine.py:37` — `_config_aliases()`

**Files:**
- Modify: `synlynk/governs_engine.py:35-50`
- Test: `tests/test_governs_engine_tenancy.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '35,55p' synlynk/governs_engine.py`

```python
def _config_aliases(repo_root: Optional[str] = None) -> dict[str, list[str]]:
    path = os.path.join(_workspace_root(repo_root), ".synlynk", "config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}

    raw = config.get("goal_aliases", config.get("governs", {}).get("goal_aliases", {}))
    ...
```

gh:#2147 notes this has zero callers repo-wide currently (confirm with `grep -rn "_config_aliases(" synlynk/ tests/`), so this is dead-on-arrival rather than an active regression — still worth fixing so it's correct whenever a caller is added, per the issue's own framing ("lower urgency, but dead-on-arrival"). `goal_aliases` is not in `_BILLING_KEYS` or `_POLICY_MIGRATED_KEYS`, so per the routing rule it belongs in `workspace.json`.

- [ ] **Step 2: Write a new direct test for the updated read path**

Add to `tests/test_governs_engine_tenancy.py`:

```python
def test_config_aliases_reads_from_workspace_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "workspace.json", "w", encoding="utf-8") as f:
        json.dump({"goal_aliases": {"goal-1": ["alias-a", "alias-b"]}}, f)
    from synlynk.governs_engine import _config_aliases
    result = _config_aliases(repo_root=str(tmp_path))
    assert result == {"goal-1": ["alias-a", "alias-b"]}


def test_config_aliases_falls_back_to_legacy_config_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "config.json", "w", encoding="utf-8") as f:
        json.dump({"goal_aliases": {"goal-2": ["alias-c"]}}, f)
    from synlynk.governs_engine import _config_aliases
    result = _config_aliases(repo_root=str(tmp_path))
    assert result == {"goal-2": ["alias-c"]}
```

Check `tests/test_governs_engine_tenancy.py`'s imports already include `os`/`json`; add if missing.

- [ ] **Step 3: Run tests to verify the first one fails**

Run: `pytest tests/test_governs_engine_tenancy.py -k config_aliases -v`
Expected: FAIL on `test_config_aliases_reads_from_workspace_json` — the function only reads `.synlynk/config.json`, which doesn't exist in that fixture, so it returns `{}` instead of the seeded aliases.

- [ ] **Step 4: Update `_config_aliases()`**

```python
def _config_aliases(repo_root: Optional[str] = None) -> dict[str, list[str]]:
    root = _workspace_root(repo_root)
    workspace_path = os.path.join(root, ".synlynk", "workspace.json")
    path = workspace_path if os.path.isfile(workspace_path) else os.path.join(root, ".synlynk", "config.json")
    try:
        with open(path, encoding="utf-8") as fh:
            config = json.load(fh)
    except (OSError, ValueError, TypeError):
        return {}

    raw = config.get("goal_aliases", config.get("governs", {}).get("goal_aliases", {}))
```

(rest of the function body unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_governs_engine_tenancy.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/governs_engine.py tests/test_governs_engine_tenancy.py
git commit -m "$(cat <<'EOF'
fix(governs_engine): read goal_aliases from workspace.json with legacy fallback

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 6: `synlynk/state_registry.py:114` — `product_identity()`

**Files:**
- Modify: `synlynk/state_registry.py:110-125`
- Test: `tests/test_state_registry.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '110,126p' synlynk/state_registry.py`

```python
def product_identity(slug: str, repo_path: str = ".") -> str:
    """Return configured or registered product identity without mutating state."""
    try:
        config = json.loads((Path(repo_path) / ".synlynk" / "config.json").read_text())
    except (OSError, json.JSONDecodeError):
        config = {}
    configured = config.get("product_id")
    ...
```

Called from `synlynk/__init__.py:500` and `state_repair.py` (x4 sites, per gh:#2147's audit — confirm with `grep -rn "product_identity(" synlynk/`). `product_id` is not in `_BILLING_KEYS`/`_POLICY_MIGRATED_KEYS`, so it is a `workspace.json` key.

- [ ] **Step 2: Write a new direct test for the updated read path**

Add to `tests/test_state_registry.py`:

```python
def test_product_identity_reads_configured_id_from_workspace_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "workspace.json", "w", encoding="utf-8") as f:
        json.dump({"product_id": "configured-product-xyz"}, f)
    from synlynk.state_registry import product_identity
    assert product_identity("some-slug", repo_path=str(tmp_path)) == "configured-product-xyz"


def test_product_identity_falls_back_to_legacy_config_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "config.json", "w", encoding="utf-8") as f:
        json.dump({"product_id": "legacy-product-abc"}, f)
    from synlynk.state_registry import product_identity
    assert product_identity("some-slug", repo_path=str(tmp_path)) == "legacy-product-abc"
```

Check `tests/test_state_registry.py`'s imports already include `os`/`json`; add if missing. These tests exercise only the "explicitly configured `product_id`" branch — they intentionally do not seed the registry file, so if `configured` is falsy the function would fall through to registry/legacy-UUID logic and the assertion would fail loudly rather than silently passing for the wrong reason.

- [ ] **Step 3: Run tests to verify the first one fails**

Run: `pytest tests/test_state_registry.py -k product_identity_reads_configured -v`
Expected: FAIL — reads `.synlynk/config.json`, which doesn't exist in the fixture, so `configured` is `None` and the function falls through to the registry/legacy-UUID path instead of returning `"configured-product-xyz"`.

- [ ] **Step 4: Update `product_identity()`**

```python
def product_identity(slug: str, repo_path: str = ".") -> str:
    """Return configured or registered product identity without mutating state."""
    repo = Path(repo_path)
    workspace_file = repo / ".synlynk" / "workspace.json"
    config_file = workspace_file if workspace_file.is_file() else repo / ".synlynk" / "config.json"
    try:
        config = json.loads(config_file.read_text())
    except (OSError, json.JSONDecodeError):
        config = {}
    configured = config.get("product_id")
```

(rest of the function body unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_state_registry.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/state_registry.py tests/test_state_registry.py
git commit -m "$(cat <<'EOF'
fix(state_registry): read product_id from workspace.json with legacy fallback

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 7: `synlynk/team.py:271,1139` — `_write_role_app_paths()` and `ensure_type_for_identity_init()`

**Files:**
- Modify: `synlynk/team.py:269-276` (`_write_role_app_paths`), `synlynk/team.py:1134-1143` (`ensure_type_for_identity_init`)
- Test: `tests/test_team.py`

- [ ] **Step 1: Read current implementation**

Run: `sed -n '269,276p' synlynk/team.py && sed -n '1134,1144p' synlynk/team.py`

```python
def _write_role_app_paths(role: str) -> tuple[Path, Path, Path]:
    from synlynk.product_store import write_apps_dir_for_init
    if (Path(".synlynk") / "config.json").is_file():
        app_dir = write_apps_dir_for_init(".")
    else:
        app_dir = Path(".synlynk") / "github_apps"
    slug = _role_slug(role)
    return app_dir, app_dir / f"{slug}.json", app_dir / f"{slug}.pem"
```

```python
def ensure_type_for_identity_init(type_id: str, pack_id: str = "software-product") -> None:
    from synlynk.product_store import identity_slug_from_config, types_yaml_path
    from synlynk.types_registry import load_types, seed_canonical_types
    slug = identity_slug_from_config(".")
    if not (Path(".synlynk") / "config.json").is_file():
        return
    types = load_types(slug)
    ...
```

Both are the same "is this repo initialized" existence-check gate as Task 4's `github_app_auth.py` bug and the governing plan's Task 10 `coldstart.py` precedent: post-migration, `Path(".synlynk") / "config.json"` never exists, so `_write_role_app_paths()` always thinks the repo is unconfigured (writes to the bare fallback dir instead of calling `write_apps_dir_for_init`), and `ensure_type_for_identity_init()` always returns early, silently skipping type seeding/validation on a fully configured repo.

- [ ] **Step 2: Write new direct tests for both updated gates**

Add to `tests/test_team.py`:

```python
def test_write_role_app_paths_uses_product_store_after_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"identity_slug": "test-product"}, f)
    from synlynk.team import _write_role_app_paths
    app_dir, app_json, app_pem = _write_role_app_paths("dev")
    # Must not silently fall back to the bare legacy dir once the repo is configured.
    assert str(app_dir) != os.path.join(".synlynk", "github_apps")


def test_ensure_type_for_identity_init_does_not_skip_after_migration(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk")
    with open(".synlynk/workspace.json", "w", encoding="utf-8") as f:
        json.dump({"identity_slug": "test-product"}, f)
    from synlynk.team import ensure_type_for_identity_init, UnknownType
    # Must reach the type-lookup logic (and raise UnknownType for a bogus
    # type) instead of returning silently because it thinks the repo is
    # unconfigured.
    with pytest.raises(UnknownType):
        ensure_type_for_identity_init("definitely-not-a-real-type")
```

Check `tests/test_team.py`'s imports already include `os`/`json`/`pytest`; add if missing. Confirm `UnknownType` is importable from `synlynk.team` (defined at `synlynk/team.py:1130` per the earlier read) before finalizing this assertion — if `seed_canonical_types`/`load_types` would need additional fixture setup to reach the `UnknownType` branch cleanly in a fresh `tmp_path` (e.g. a missing pack definition), adjust the assertion to whatever the function's actual first failure mode is in an empty fixture, verified by running the test once manually with `-s` and reading the traceback, rather than guessing further.

- [ ] **Step 3: Run tests to verify they fail**

Run: `pytest tests/test_team.py -k "write_role_app_paths_uses_product_store or ensure_type_for_identity_init_does_not_skip" -v`
Expected: FAIL — both gates see no `.synlynk/config.json` and take their "unconfigured" branch instead of the configured one.

- [ ] **Step 4: Update both functions**

```python
def _write_role_app_paths(role: str) -> tuple[Path, Path, Path]:
    from synlynk.product_store import write_apps_dir_for_init
    configured = (
        (Path(".synlynk") / "workspace.json").is_file()
        or (Path(".synlynk") / "config.json").is_file()
    )
    if configured:
        app_dir = write_apps_dir_for_init(".")
    else:
        app_dir = Path(".synlynk") / "github_apps"
    slug = _role_slug(role)
    return app_dir, app_dir / f"{slug}.json", app_dir / f"{slug}.pem"
```

```python
def ensure_type_for_identity_init(type_id: str, pack_id: str = "software-product") -> None:
    from synlynk.product_store import identity_slug_from_config, types_yaml_path
    from synlynk.types_registry import load_types, seed_canonical_types
    slug = identity_slug_from_config(".")
    configured = (
        (Path(".synlynk") / "workspace.json").is_file()
        or (Path(".synlynk") / "config.json").is_file()
    )
    if not configured:
        return
    types = load_types(slug)
```

(rest of each function body unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_team.py -v`
Expected: all passed

- [ ] **Step 6: Commit**

```bash
git add synlynk/team.py tests/test_team.py
git commit -m "$(cat <<'EOF'
fix(team): detect repo configuration via workspace.json or legacy config.json

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Task 8: `synlynk/version_policy.py:23` — `check_version_policy()`

**Files:**
- Modify: `synlynk/version_policy.py:20-30`
- Test: `tests/test_version_policy.py` (new file — none exists today)

- [ ] **Step 1: Read current implementation**

Run: `sed -n '1,45p' synlynk/version_policy.py`

```python
def check_version_policy(repo_dir: str, current_version: str) -> Tuple[bool, str]:
    """Check whether ``current_version`` meets a repository's minimum version."""

    config_path = Path(repo_dir) / ".synlynk" / "config.json"
    if not config_path.is_file():
        return True, "No version policy defined"

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, "Invalid config"

    policy = config.get("version_policy", {}) if isinstance(config, dict) else {}
```

`version_policy` is not in `_BILLING_KEYS`/`_POLICY_MIGRATED_KEYS`, so per the routing rule it is a `workspace.json` key, despite its name sounding policy-flavored — the governing design's `policy.json` split is scoped to exactly `qa_gate_mode`, `roles`, `story_classification`, `sentinel` (design spec lines 43-48); `version_policy` was not one of the four keys moved there, and does not get special treatment.

No `tests/test_version_policy.py` exists yet; create it.

- [ ] **Step 2: Write a new test file with both the positive and fallback cases**

Create `tests/test_version_policy.py`:

```python
import json
import os

from synlynk.version_policy import check_version_policy


def test_check_version_policy_reads_min_version_from_workspace_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "workspace.json", "w", encoding="utf-8") as f:
        json.dump({"version_policy": {"min_version": "0.20.0"}}, f)
    ok, reason = check_version_policy(str(tmp_path), "0.10.0")
    assert ok is False
    assert "0.20.0" in reason


def test_check_version_policy_falls_back_to_legacy_config_json(tmp_path):
    os.makedirs(tmp_path / ".synlynk")
    with open(tmp_path / ".synlynk" / "config.json", "w", encoding="utf-8") as f:
        json.dump({"version_policy": {"min_version": "0.15.0"}}, f)
    ok, reason = check_version_policy(str(tmp_path), "0.30.0")
    assert ok is True


def test_check_version_policy_no_files_present(tmp_path):
    ok, reason = check_version_policy(str(tmp_path), "1.0.0")
    assert ok is True
    assert reason == "No version policy defined"
```

- [ ] **Step 3: Run tests to verify the first one fails**

Run: `pytest tests/test_version_policy.py -v`
Expected: `test_check_version_policy_reads_min_version_from_workspace_json` FAILS — `config_path` only checks `.synlynk/config.json`, which doesn't exist in that fixture, so it returns `(True, "No version policy defined")` instead of rejecting `0.10.0` against `min_version 0.20.0`. The other two tests pass already (no change in behavior for the legacy-only and no-file cases), confirming the new test correctly isolates the regression.

- [ ] **Step 4: Update `check_version_policy()`**

```python
def check_version_policy(repo_dir: str, current_version: str) -> Tuple[bool, str]:
    """Check whether ``current_version`` meets a repository's minimum version."""

    repo = Path(repo_dir)
    workspace_path = repo / ".synlynk" / "workspace.json"
    config_path = workspace_path if workspace_path.is_file() else repo / ".synlynk" / "config.json"
    if not config_path.is_file():
        return True, "No version policy defined"

    try:
        config = json.loads(config_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return True, "Invalid config"

    policy = config.get("version_policy", {}) if isinstance(config, dict) else {}
```

(rest of the function body unchanged).

- [ ] **Step 5: Run tests to verify they pass**

Run: `pytest tests/test_version_policy.py -v`
Expected: all passed (3/3)

- [ ] **Step 6: Commit**

```bash
git add synlynk/version_policy.py tests/test_version_policy.py
git commit -m "$(cat <<'EOF'
fix(version_policy): read version_policy from workspace.json with legacy fallback

Refs gh:#2147, gh:#2101

Co-Authored-By: Claude Sonnet 5 <noreply@anthropic.com>
Claude-Session: https://claude.ai/code/session_0167ERumamwnBGV98mN3gXMQ
EOF
)"
```

---

## Self-Review

**Spec coverage:** All 8 bullets from gh:#2147's own enumerated list are covered one-to-one by Tasks 1-8 (`team.py`'s two line numbers, 271 and 1139, are combined into Task 7 since both are the identical existence-check bug in the same file — matches how the issue itself grouped them under one bullet). `status.py:398`'s cosmetic string is explicitly out of scope per the issue and is not a task here.

**Placeholder scan:** No "TBD"/"TODO"/"add appropriate X" patterns. Every step shows real before/after code. Task 7, Step 2 has one explicit judgment-call note (how to reach `ensure_type_for_identity_init`'s `UnknownType` branch in a bare fixture) rather than a guessed assertion — this is flagged as a verify-once-and-adjust step, not an unresolved placeholder, consistent with how the governing plan's own Task 10 handles the same kind of fixture-dependent uncertainty.

**Type consistency:** `_config_path()`/`_default_apps_dir()`/`_get_config_path()` naming matches each file's pre-existing private-helper convention (no cross-task naming collisions — each is a module-private function in a different module). The `workspace.json`-or-`config.json` idiom is applied identically across all 8 tasks, matching the two existing precedents in `synlynk/__init__.py:1452,1570` and the governing plan's Task 10.

**Full regression run:** after all 8 tasks land, run the complete suite once (not just the touched test files) before opening the PR: `pytest -x -q`.

---

## Execution Handoff

Per this project's Default Agent Role policy, implementation should be dispatched via `synlynk dispatch` rather than executed by Claude directly — this is routine, mechanical, pattern-following migration work (each task mirrors an already-established, already-reviewed pattern from the gh:#2101 plan), not PM/review/deploy work. Per gh:#2147's own suggested routing and the repo's capability-based task allocation table, dispatch to **Codex** (fallback: Grok) with `--task-type implement`, one dispatch per task or a small batch of 2-3 tasks per dispatch given their independence and small size — avoid a single dispatch covering all 8, since any one task's review-cycle rework would otherwise block the other 7.

Link `story-84912225` is specific to the cost-inflation investigation (gh:#1937/#2219) and is **not** the right GOVERNS story for this work — before dispatching, create or locate the correct story/goal for gh:#2147 itself (`synlynk story list` / `synlynk story create`) so the Hardened PR Review Policy's 100% GOVERNS-adherence requirement is met, and link that story (not story-84912225) on each dispatch.

Per the Hardened PR Review Policy, the reviewer must differ from Codex in both harness and model (e.g. Grok) and the reviewer's own dispatch performs the merge.
