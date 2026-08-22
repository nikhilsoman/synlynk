# gh-write Identity Hardening (Phase 1 Closeout) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the three gaps surfaced by this session's live gh-write dispatch tests (§3.1–3.3 of the approved design) so Phase 1 of the full-autonomy roadmap can be marked done: correct harness routing defaults, auto-imply the `run:shell` grant for gh-write dispatches, and fail closed instead of silently defaulting to the `dev` identity when no role is resolvable.

**Architecture:** All three changes live in `synlynk/dispatch.py` (plus the `can_gh_write` data correction in `synlynk/_constants.py`, a new `--role` CLI flag in `synlynk/cli.py`, and the two hardcoded copies of the #426 routing sentence in `synlynk/probe.py`). No new files, no new subsystems — this is a data-correction + fail-closed-validation pass over existing, already-read machinery.

**Tech Stack:** Python 3 stdlib, pytest, argparse (existing `synlynk` CLI conventions).

---

### Task 1: Correct `can_gh_write` baselines in `synlynk/_constants.py`

**Files:**
- Modify: `synlynk/_constants.py:113` (agy), `synlynk/_constants.py:147` (grok)
- Test: `tests/test_synlynk.py` (new test, place near the existing `HARNESS_CAPABILITY_BASELINES` role-coverage test around line 460)

- [ ] **Step 1: Write the failing test**

```python
def test_can_gh_write_baselines_match_live_verified_reality():
    from synlynk._constants import HARNESS_CAPABILITY_BASELINES

    assert HARNESS_CAPABILITY_BASELINES["claude"]["can_gh_write"] is True
    assert HARNESS_CAPABILITY_BASELINES["agy"]["can_gh_write"] is True
    assert HARNESS_CAPABILITY_BASELINES["grok"]["can_gh_write"] is False
    assert HARNESS_CAPABILITY_BASELINES["codex"]["can_gh_write"] is False
    assert HARNESS_CAPABILITY_BASELINES["local"]["can_gh_write"] is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py -k test_can_gh_write_baselines_match_live_verified_reality -v`
Expected: FAIL — `agy` asserts `True` but is currently `False`; `grok` asserts `False` but is currently `True`.

- [ ] **Step 3: Correct the two stale values**

In `synlynk/_constants.py`, inside the `"agy": {` block (currently line 111-113):

```python
    "agy": {
        "cli": "agy",
        "can_gh_write": True,
```

(was `False` — corrected per `job-488c152f`, live-verified 2026-08-22, post TC-7 fix in PR #1107.)

Inside the `"grok": {` block (currently line 145-147):

```python
    "grok": {
        "cli": "grok",
        "can_gh_write": False,
```

(was `True` — corrected per `job-3e428904`, live-verified failure: Grok's dispatch sandbox denies `bash` entirely, confirmed via `git diff origin/main` showing zero real change despite a misleading "OK, exit 0" job status.)

Do not change `claude`, `codex`, or `local` — their values already match observed reality.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py -k test_can_gh_write_baselines_match_live_verified_reality -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add synlynk/_constants.py tests/test_synlynk.py
git commit -m "fix(constants): correct can_gh_write baselines for agy/grok (#423)"
```

---

### Task 2: Prefer `claude` over `agy` for gh-write in `_harness_for_org_role`

**Context:** `synlynk/dispatch.py:32-53` (`_harness_for_org_role`) currently iterates `sorted(n for n in baselines_map if n in CORE_FLEET)` — alphabetical order (`agy, claude, codex, grok`). For a non-gh-write dispatch this is fine and must stay unchanged. For a gh-write dispatch, alphabetical order picks `agy` before `claude`, which is the wrong default per the spec (`claude` primary, `agy` fallback — claude was faster, cheaper, and hit zero preflight bugs in this session's live test). This task changes iteration order **only when `requires_gh_write=True`**.

There is a second, separate reroute path in `dispatch_agent` (`synlynk/dispatch.py:2168-2191`, the `capable_agents[0]` fallback) that relies on `HARNESS_CAPABILITY_BASELINES`' literal dict insertion order (`claude, codex, agy, grok, local`). That path already self-corrects to prefer `claude` then `agy` purely from Task 1's data fix — no code change needed there. This task only touches `_harness_for_org_role`.

**Files:**
- Modify: `synlynk/dispatch.py:32-53`
- Test: `tests/test_synlynk.py` (new test, place near `test_resolve_dispatch_permissions_returns_role_defaults` around line 463)

- [ ] **Step 1: Write the failing test**

```python
def test_harness_for_org_role_prefers_claude_over_agy_for_gh_write():
    from synlynk.dispatch import _harness_for_org_role

    baselines_map = {
        "agy": {"roles": ["builder"], "can_gh_write": True},
        "claude": {"roles": ["builder"], "can_gh_write": True},
        "codex": {"roles": ["builder"], "can_gh_write": False},
        "grok": {"roles": ["builder"], "can_gh_write": False},
    }
    picked = _harness_for_org_role("dev", baselines_map, requires_gh_write=True)
    assert picked == "claude"


def test_harness_for_org_role_falls_back_to_agy_when_claude_unavailable():
    from synlynk.dispatch import _harness_for_org_role

    baselines_map = {
        "agy": {"roles": ["builder"], "can_gh_write": True},
        "codex": {"roles": ["builder"], "can_gh_write": False},
        "grok": {"roles": ["builder"], "can_gh_write": False},
    }
    picked = _harness_for_org_role("dev", baselines_map, requires_gh_write=True)
    assert picked == "agy"


def test_harness_for_org_role_stays_alphabetical_when_gh_write_not_required():
    from synlynk.dispatch import _harness_for_org_role

    baselines_map = {
        "agy": {"roles": ["builder"], "can_gh_write": True},
        "claude": {"roles": ["builder"], "can_gh_write": True},
    }
    picked = _harness_for_org_role("dev", baselines_map, requires_gh_write=False)
    assert picked == "agy"
```

- [ ] **Step 2: Run tests to verify the gh-write-preference ones fail**

Run: `python3 -m pytest tests/test_synlynk.py -k "test_harness_for_org_role_prefers_claude_over_agy_for_gh_write or test_harness_for_org_role_falls_back_to_agy_when_claude_unavailable" -v`
Expected: FAIL — both currently return `"agy"` (alphabetically first), not the claude-first order the gh-write tests expect.

Run: `python3 -m pytest tests/test_synlynk.py -k test_harness_for_org_role_stays_alphabetical_when_gh_write_not_required -v`
Expected: PASS already (this behavior is unchanged) — confirms the baseline before your edit.

- [ ] **Step 3: Implement a gh-write-specific priority order**

Replace `synlynk/dispatch.py:32-53` (the full `_harness_for_org_role` function) with:

```python
_GH_WRITE_HARNESS_PRIORITY = ("claude", "agy")


def _harness_for_org_role(org_role: str, baselines_map: dict, requires_gh_write: bool = False):
    """Deterministic fallback harness selection for agent_id-driven dispatch.

    Picks the first harness whose declared baseline "roles" (architect/
    builder/verifier — a different vocabulary than org-chart roles, see
    docs/superpowers/specs/2026-08-16-agent-dispatch-integration-design.md
    §6) includes the mapped tag for this org role. Does not consult the
    story_id-based capability_scores DB table — that stays story_id-only.

    When requires_gh_write is set, candidates are tried in the fixed
    priority order claude -> agy first (live-verified 2026-08-23, see
    docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md),
    then any remaining CORE_FLEET members alphabetically. Non-gh-write
    selection is untouched: plain alphabetical order over CORE_FLEET.
    """
    baseline_role = _ORG_ROLE_TO_BASELINE_ROLE.get(org_role)
    if not baseline_role:
        return None
    from synlynk._constants import CORE_FLEET

    candidates = [n for n in baselines_map if n in CORE_FLEET]
    if requires_gh_write:
        ordered = [n for n in _GH_WRITE_HARNESS_PRIORITY if n in candidates]
        ordered += sorted(n for n in candidates if n not in _GH_WRITE_HARNESS_PRIORITY)
    else:
        ordered = sorted(candidates)

    for name in ordered:
        baseline = baselines_map[name]
        if baseline_role not in baseline.get("roles", []):
            continue
        if requires_gh_write and not baseline.get("can_gh_write", False):
            continue
        return name
    return None
```

- [ ] **Step 4: Run all three tests to verify they pass**

Run: `python3 -m pytest tests/test_synlynk.py -k "test_harness_for_org_role" -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Run the full dispatch test module to catch regressions**

Run: `python3 -m pytest tests/test_synlynk.py -k "harness_for_org_role or resolve_dispatch_harness" -v`
Expected: PASS — no existing test asserted alphabetical order for the gh-write case (confirm by reading output; if something unexpected fails, read that test before proceeding — do not silently adjust its assertion to match new behavior without understanding why it existed).

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_synlynk.py
git commit -m "fix(dispatch): prefer claude over agy for gh-write harness selection (#423)"
```

---

### Task 3: Correct the #426 routing sentence in both `probe.py` SOP sources

**Context:** The routing sentence in the repo's checked-in `CLAUDE.md` is auto-generated from two hardcoded template strings in `synlynk/probe.py` — `_CAPABILITY_ALLOCATION_SOP` (line 67, static template, used for repos without repo-specific role config) and `_repair_capability_allocation_sop` (line 1028, dynamic generator, used when `.synlynk/config.json` has a `roles` mapping). Both currently contain the identical stale sentence: `"**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**...."`. Editing only the checked-in `CLAUDE.md` by hand would be silently overwritten the next time `synlynk roles --fix` runs — both generator sources must be corrected for the fix to stick.

**Files:**
- Modify: `synlynk/probe.py:67`
- Modify: `synlynk/probe.py:1028`
- Test: `tests/test_synlynk.py` (new test, place near other probe/SOP tests — see `test_run_tc5_missing_file_reports_all_headers` around line 104)

- [ ] **Step 1: Write the failing test**

```python
def test_capability_allocation_sop_routes_gh_write_to_claude_not_grok():
    from synlynk.probe import _CAPABILITY_ALLOCATION_SOP, _repair_capability_allocation_sop

    assert "claude by default" in _CAPABILITY_ALLOCATION_SOP
    assert "Route any task that requires GitHub write actions to **Grok by default**" not in _CAPABILITY_ALLOCATION_SOP

    repaired = _repair_capability_allocation_sop({"roles": {}})
    assert "claude by default" in repaired
    assert "Route any task that requires GitHub write actions to **Grok by default**" not in repaired
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m pytest tests/test_synlynk.py -k test_capability_allocation_sop_routes_gh_write_to_claude_not_grok -v`
Expected: FAIL — both strings still contain the old "Grok by default" sentence.

- [ ] **Step 3: Replace the sentence in both locations**

In `synlynk/probe.py`, find this exact line at line 67 (inside the `_CAPABILITY_ALLOCATION_SOP` triple-quoted string):

```
**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**. Agy headless can complete `gh pr review`, `gh pr comment`, and `gh pr merge` writes when the machine-local `~/.gemini/antigravity-cli/settings.json` already contains scoped `command(gh pr review)`, `command(gh pr comment)`, and `command(gh pr merge)` allow-rules; that precondition is operator-confirmed, not reliably verifiable mid-task. Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically, but do not treat it as a hard identity guarantee yet: the token-stripping fallback does not prevent `gh` from using a locally logged-in personal keyring identity when no role-scoped GitHub App token is available (#569).
```

Replace it (in-place, same line) with:

```
**GitHub write routing (#426):** Route any task that requires GitHub write actions to **claude by default, Agy as fallback** (live-verified 2026-08-23; see `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`). Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic "OK, exit 0" job status — do not trust job-status alone for Grok gh-write attempts). Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569).
```

At line 1028 (inside `_repair_capability_allocation_sop`, the same sentence appears as a Python string literal — note it is followed by a trailing `",` since it's a list/join element, not a bare triple-quoted block). Find:

```python
        "**GitHub write routing (#426):** Route any task that requires GitHub write actions to **Grok by default**. Agy headless can complete `gh pr review`, `gh pr comment`, and `gh pr merge` writes when the machine-local `~/.gemini/antigravity-cli/settings.json` already contains scoped `command(gh pr review)`, `command(gh pr comment)`, and `command(gh pr merge)` allow-rules; that precondition is operator-confirmed, not reliably verifiable mid-task. Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically, but do not treat it as a hard identity guarantee yet: the token-stripping fallback does not prevent `gh` from using a locally logged-in personal keyring identity when no role-scoped GitHub App token is available (#569).",
```

Replace it with:

```python
        "**GitHub write routing (#426):** Route any task that requires GitHub write actions to **claude by default, Agy as fallback** (live-verified 2026-08-23; see `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`). Grok's dispatch sandbox denies `bash` execution entirely in this environment (confirmed via `git diff origin/main` showing a total silent no-op despite a generic \"OK, exit 0\" job status — do not trust job-status alone for Grok gh-write attempts). Codex's `workspace-write` sandbox blocks network egress to `api.github.com` by design. Pass `--requires-gh-write` on synlynk dispatch to enforce the routing hint automatically; it now also auto-implies the `run:shell` permission grant and fails closed with a `RuntimeError` if no role is resolvable via `--as-agent`, `--story`, or `--role` (#569).",
```

(Note the escaped `\"OK, exit 0\"` — this line is a double-quoted Python string literal, unlike the triple-quoted block at line 67, so inner double quotes must be escaped.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m pytest tests/test_synlynk.py -k test_capability_allocation_sop_routes_gh_write_to_claude_not_grok -v`
Expected: PASS

- [ ] **Step 5: Regenerate the checked-in `CLAUDE.md` so it matches the new generator output**

Run: `python3 -m synlynk roles --fix`
Then verify the routing sentence in the actual file changed:

Run: `grep -n "GitHub write routing" CLAUDE.md`
Expected: the output line now contains `"claude by default, Agy as fallback"`, not `"Grok by default"`.

If `synlynk roles --fix` reports no changes needed or errors, read `synlynk/probe.py`'s `_repair_sops_only` (imported in `synlynk/__init__.py`) to understand why the repair didn't apply before proceeding — do not hand-edit `CLAUDE.md` directly, since that edit would not survive the next `--fix` run.

- [ ] **Step 6: Commit**

```bash
git add synlynk/probe.py CLAUDE.md tests/test_synlynk.py
git commit -m "docs(probe): correct #426 gh-write routing SOP to claude/agy, not grok"
```

---

### Task 4: `--requires-gh-write` auto-implies `run:shell`

**Context:** `synlynk/dispatch.py:2316-2330` is where `role_list`, `permissions`, and `flags` are assembled for a dispatch, immediately before `_permissions_to_flags(agent, permissions)` is called. This task adds `"run:shell"` into the `grants` list before `_resolve_dispatch_permissions(...)` is called, whenever `requires_gh_write=True`. This must happen unconditionally — not only for `task_type == "review"` — since any gh-write dispatch needs shell access to invoke `gh`, and must land before the agy `PermissionEnforcementError` read-only-only check inside `_permissions_to_flags` runs (that check reads the final `permissions` list, so injecting into `grants` before `_resolve_dispatch_permissions` builds `permissions` satisfies this).

**Files:**
- Modify: `synlynk/dispatch.py:2118-2136` (function signature — confirm `grants` is already a parameter; it is) and `synlynk/dispatch.py:2326-2330` (call site)
- Test: `tests/test_synlynk.py` (new tests, place near `test_resolve_dispatch_permissions_grant_expands` around line 471)

- [ ] **Step 1: Write the failing tests**

```python
def test_dispatch_agent_gh_write_auto_implies_run_shell(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_permissions_to_flags(agent, permissions):
        captured["agent"] = agent
        captured["permissions"] = list(permissions)
        return []

    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", fake_permissions_to_flags)
    monkeypatch.setattr(dispatch_mod, "_build_subprocess_env", lambda *a, **kw: {})
    monkeypatch.setattr(
        dispatch_mod,
        "_dispatch_capability_preflight",
        lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: types.SimpleNamespace(pid=1))

    dispatch_mod.dispatch_agent(
        "claude", "do a review #123", task_type="review",
        requires_gh_write=True, force_agent=True, role="qa",
        context_mode="none",
    )

    assert "run:shell" in captured["permissions"]


def test_dispatch_agent_non_gh_write_does_not_add_run_shell(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_permissions_to_flags(agent, permissions):
        captured["permissions"] = list(permissions)
        return []

    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", fake_permissions_to_flags)
    monkeypatch.setattr(dispatch_mod, "_build_subprocess_env", lambda *a, **kw: {})
    monkeypatch.setattr(
        dispatch_mod,
        "_dispatch_capability_preflight",
        lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: types.SimpleNamespace(pid=1))

    dispatch_mod.dispatch_agent(
        "claude", "implement a small fix", task_type="implement",
        requires_gh_write=False, force_agent=True,
        context_mode="none",
    )

    assert "run:shell" not in captured["permissions"]
```

Note: `types` (stdlib) and `isolated_db` fixture are already used elsewhere in this file (see `test_run_tc4_skips_flag_only_command_templates` and `test_dispatch_agent_injects_agy_permissions_header` at line 571) — reuse them, don't reimplement.

- [ ] **Step 2: Run tests to verify the first one fails**

Run: `python3 -m pytest tests/test_synlynk.py -k "test_dispatch_agent_gh_write_auto_implies_run_shell or test_dispatch_agent_non_gh_write_does_not_add_run_shell" -v`
Expected: `test_dispatch_agent_gh_write_auto_implies_run_shell` FAILs (`run:shell` not in captured permissions yet); `test_dispatch_agent_non_gh_write_does_not_add_run_shell` may already PASS (confirms it as a regression guard, not new behavior).

If `role="qa"` in the first test causes a different failure (e.g. `dispatch_agent()` doesn't yet accept a `role` kwarg), that's expected — Task 5 adds that parameter. Reorder: implement Task 5's `role` parameter addition first if pytest collection fails outright due to an unexpected-keyword TypeError, otherwise proceed; both tasks touch the same function signature and are safe to land in either order as long as both are complete before the full suite is expected to pass. This plan lists them in the order that reads most naturally, not a strict dependency order.

- [ ] **Step 3: Implement the auto-imply**

In `synlynk/dispatch.py`, at the permission/flags assembly block (currently lines 2326-2330):

```python
        role_list = (cfg.get("roles", {}) or {}).get(agent, [])
        if task_type == "review":
            role_list = ["review"]
        permissions = _resolve_dispatch_permissions(agent, role_list=role_list, grants=grants, revokes=revokes)
        flags = flags + _permissions_to_flags(agent, permissions)
```

Replace with:

```python
        role_list = (cfg.get("roles", {}) or {}).get(agent, [])
        if task_type == "review":
            role_list = ["review"]
        effective_grants = list(grants or [])
        if requires_gh_write and "run:shell" not in effective_grants:
            effective_grants.append("run:shell")
        permissions = _resolve_dispatch_permissions(agent, role_list=role_list, grants=effective_grants, revokes=revokes)
        flags = flags + _permissions_to_flags(agent, permissions)
```

- [ ] **Step 4: Run both tests to verify they pass**

Run: `python3 -m pytest tests/test_synlynk.py -k "test_dispatch_agent_gh_write_auto_implies_run_shell or test_dispatch_agent_non_gh_write_does_not_add_run_shell" -v`
Expected: PASS (2 passed) — once Task 5's `role` parameter also lands.

- [ ] **Step 5: Run the existing agy-permissions-header test to confirm no regression**

Run: `python3 -m pytest tests/test_synlynk.py -k test_dispatch_agent_injects_agy_permissions_header -v`
Expected: PASS unchanged (that test does not set `requires_gh_write`, so it must see identical behavior to before).

- [ ] **Step 6: Commit**

```bash
git add synlynk/dispatch.py tests/test_synlynk.py
git commit -m "feat(dispatch): auto-imply run:shell permission for --requires-gh-write"
```

---

### Task 5: Add `--role` flag and fail-closed role resolution for gh-write

**Context:** Two fallback sites in `synlynk/dispatch.py` currently default an unresolvable role to `"dev"` for gh-write dispatches: `_build_subprocess_env` (line 487, `role = agent_role or _role_for_story(story_id) or "dev"`) and the main `dispatch_agent` flow's `gh_write_role` computation (line 2624, same pattern). Per spec §3.3, when `requires_gh_write=True`, this silent default must become a fail-closed `RuntimeError`, mirroring the error class/style `_resolve_dispatch_gh_token` already raises (line 505-512) for "no token provisioned." A new `--role <role>` CLI flag becomes a third resolution source alongside `--as-agent` and `--story`-with-tagged-role, for the ad-hoc/manual dispatch case (like this session's own live tests) that has neither a registered agent nor a story.

**Files:**
- Modify: `synlynk/dispatch.py:2118-2136` (add `role` parameter to `dispatch_agent` signature)
- Modify: `synlynk/dispatch.py:2151-2160` (resolve `role` param into `resolved_agent_role`, add fail-closed check)
- Modify: `synlynk/dispatch.py:462-513` (`_build_subprocess_env` — remove `or "dev"` fallback, raise on unresolvable role)
- Modify: `synlynk/dispatch.py:2617-2626` (drop the now-redundant `or "dev"` in `gh_write_role`)
- Modify: `synlynk/cli.py:675-681` (add `--role` argparse flag) and `synlynk/cli.py:1212-1227` (thread `role=getattr(args, "role", None)` into the `dispatch_agent(...)` call)
- Test: `tests/test_synlynk.py` (new tests, place near Task 4's tests)

- [ ] **Step 1: Write the failing tests**

```python
def test_dispatch_agent_gh_write_raises_without_resolvable_role(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(
        dispatch_mod,
        "_dispatch_capability_preflight",
        lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None},
    )

    with pytest.raises(RuntimeError, match="--requires-gh-write"):
        dispatch_mod.dispatch_agent(
            "claude", "post a comment on PR #1", task_type="review",
            requires_gh_write=True, force_agent=True,
            context_mode="none",
        )


def test_dispatch_agent_gh_write_resolves_explicit_role_flag(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk.dispatch as dispatch_mod

    captured = {}

    def fake_build_env(agent, overrides, requires_gh_write, story_id, agent_role=None):
        captured["agent_role"] = agent_role
        return {}

    monkeypatch.setattr(dispatch_mod, "_build_subprocess_env", fake_build_env)
    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", lambda agent, permissions: [])
    monkeypatch.setattr(
        dispatch_mod,
        "_dispatch_capability_preflight",
        lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: types.SimpleNamespace(pid=1))

    dispatch_mod.dispatch_agent(
        "claude", "post a comment on PR #1", task_type="review",
        requires_gh_write=True, force_agent=True, role="qa",
        context_mode="none",
    )

    assert captured["agent_role"] == "qa"


def test_dispatch_agent_non_gh_write_still_defaults_role_to_dev(tmp_path, isolated_db, monkeypatch):
    monkeypatch.chdir(tmp_path)
    os.makedirs(".synlynk/state", exist_ok=True)
    import synlynk.dispatch as dispatch_mod

    monkeypatch.setattr(dispatch_mod, "_permissions_to_flags", lambda agent, permissions: [])
    monkeypatch.setattr(
        dispatch_mod,
        "_dispatch_capability_preflight",
        lambda *a, **kw: {"passed": True, "sentinel": None, "reason": None},
    )
    monkeypatch.setattr(dispatch_mod.subprocess, "Popen", lambda *a, **kw: types.SimpleNamespace(pid=1))

    # requires_gh_write=False: no role resolution, no fail-closed check, no exception.
    job = dispatch_mod.dispatch_agent(
        "claude", "implement a small fix", task_type="implement",
        requires_gh_write=False, force_agent=True,
        context_mode="none",
    )
    assert job["agent"] == "claude"


def test_build_subprocess_env_raises_without_resolvable_role():
    from synlynk.dispatch import _build_subprocess_env

    with pytest.raises(RuntimeError, match="--requires-gh-write"):
        _build_subprocess_env("claude", {}, requires_gh_write=True, story_id=None, agent_role=None)


def test_build_subprocess_env_dev_default_unchanged_when_gh_write_not_required(monkeypatch, tmp_path):
    from synlynk.dispatch import _build_subprocess_env

    monkeypatch.chdir(tmp_path)
    # No GH_TOKEN env vars are injected, and no exception is raised, when
    # requires_gh_write is False -- the "dev" default path is untouched.
    env = _build_subprocess_env("claude", {}, requires_gh_write=False, story_id=None, agent_role=None)
    assert "GH_TOKEN" not in env
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python3 -m pytest tests/test_synlynk.py -k "gh_write_raises_without_resolvable_role or gh_write_resolves_explicit_role_flag or non_gh_write_still_defaults_role_to_dev or build_subprocess_env_raises_without_resolvable_role or build_subprocess_env_dev_default_unchanged" -v`
Expected: the two `raises_without_resolvable_role` tests FAIL (no exception currently raised — role silently defaults to `"dev"`); `gh_write_resolves_explicit_role_flag` FAILs with a `TypeError: dispatch_agent() got an unexpected keyword argument 'role'`; the two "unchanged" tests should already PASS (confirming current default behavior as a baseline before the edit).

- [ ] **Step 3: Add the `role` parameter and fail-closed check to `dispatch_agent`**

In `synlynk/dispatch.py`, change the `dispatch_agent` signature (currently lines 2118-2136):

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   agent_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   static_baseline: bool = False,
                   task_type: str = None,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None,
                   gh_write_target_kind: str = "issue",
                   model: str = None) -> dict:
```

Add a `role: str = None` parameter (append after `model`):

```python
def dispatch_agent(agent: str, task: str, story_id: str = None,
                   agent_id: str = None,
                   force_agent: bool = False,
                   context_mode: str = None,
                   cycle: str = "work",
                   skip_preflight: bool = False,
                   requires_gh_write: bool = False,
                   static_baseline: bool = False,
                   task_type: str = None,
                   requires: list = None,
                   grants: list = None,
                   revokes: list = None,
                   job_id: str = None,
                   issue: int = None,
                   base: str = None,
                   scope_paths: list = None,
                   session_id: str = None,
                   gh_write_target_kind: str = "issue",
                   model: str = None,
                   role: str = None) -> dict:
```

Then, in the body (currently lines 2151-2160):

```python
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry:
            resolved_agent_role = next(
                (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
            )
```

Replace with (adds the `--role` flag as a resolution source, plus the story-tagged-role source, plus the fail-closed raise — all only under `requires_gh_write`):

```python
    resolved_agent_role = None
    if agent_id:
        from synlynk import agent_store
        entry = next(
            (a for a in agent_store.list_agents() if a["agent_id"] == agent_id), None
        )
        if entry:
            resolved_agent_role = next(
                (a["value"] for a in entry["aliases"] if a["kind"] == "role_slug"), None
            )
    resolved_agent_role = role or resolved_agent_role
    if requires_gh_write and not resolved_agent_role:
        resolved_agent_role = _role_for_story(story_id)
    if requires_gh_write and not resolved_agent_role:
        raise RuntimeError(
            "Dispatch refused: --requires-gh-write requires a resolvable role identity, "
            "but none was provided. Pass --role <role>, or dispatch via --as-agent "
            "<registered-agent-id> or --story <id> with a role-tagged story. Refusing to "
            "silently default to the 'dev' identity for a GitHub-write dispatch (see #423, #569)."
        )
```

- [ ] **Step 4: Remove the `or "dev"` fallback in `_build_subprocess_env` and raise instead**

In `synlynk/dispatch.py`, change (currently lines 486-512):

```python
    if requires_gh_write:
        role = agent_role or _role_for_story(story_id) or "dev"
        gh_token = _resolve_dispatch_gh_token(role)
```

Replace with:

```python
    if requires_gh_write:
        role = agent_role or _role_for_story(story_id)
        if not role:
            raise RuntimeError(
                "Dispatch refused: --requires-gh-write requires a resolvable role identity "
                "(agent_role or a story-tagged role), but none was provided. Pass --role "
                "<role> to dispatch, or use --as-agent/--story with a role-tagged entry. "
                "Refusing to default to 'dev' for a GitHub-write dispatch (see #423, #569)."
            )
        gh_token = _resolve_dispatch_gh_token(role)
```

Everything below this (`proc_env.pop(...)`, the `if gh_token:` / `elif _gh_write_allow_host_auth():` / `else:` block) stays exactly as-is — only the role-resolution line and the new guard above it change.

- [ ] **Step 5: Simplify the redundant `gh_write_role` fallback**

In `synlynk/dispatch.py`, change (currently line 2624):

```python
        gh_write_role = resolved_agent_role or _role_for_story(story_id) or "dev"
```

Replace with:

```python
        gh_write_role = resolved_agent_role or _role_for_story(story_id)
```

(By this point in `dispatch_agent`, when `requires_gh_write` is true, Step 3's fail-closed check has already guaranteed `resolved_agent_role` is set or the function has already raised — so `"dev"` is unreachable dead code here. Leaving the bare `or` without a final default is intentional: if this is ever reached with both `None` in some future refactor, `_resolve_dispatch_gh_bot_login(None)` will do a harmless attribute-safe lookup miss and return `None`, not silently mint a `dev`-identity token.)

- [ ] **Step 6: Add the `--role` CLI flag**

In `synlynk/cli.py`, after the existing `--as-agent` argument block (currently lines 675-681):

```python
    dispatch_parser.add_argument(
        "--as-agent",
        dest="as_agent",
        default=None,
        help="Dispatch as this workspace agent (ID or role alias). Resolves GitHub identity "
             "and, if the harness positional is omitted, auto-selects a harness by role fit.",
    )
```

Add:

```python
    dispatch_parser.add_argument(
        "--role",
        dest="role",
        default=None,
        help="Explicit role identity for this dispatch (e.g. qa, dev, architect). Required "
             "for --requires-gh-write dispatches that have no --as-agent or role-tagged "
             "--story to resolve a role from (#423, #569).",
    )
```

- [ ] **Step 7: Thread the flag into the `dispatch_agent(...)` call**

In `synlynk/cli.py`, change the `dispatch_agent(...)` call (currently lines 1212-1227):

```python
            job = dispatch_agent(args.agent or known_agents[0], args.task, story_id=args.story_id,
                                 agent_id=resolved_agent_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 static_baseline=getattr(args, "static_baseline", False),
                                 requires_gh_write=_effective_requires_gh_write,
                                 task_type=getattr(args, "task_type", None),
                                 gh_write_target_kind=_resolved_gh_write_target_kind,
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 scope_paths=getattr(args, "scope_paths", []),
                                 session_id=getattr(args, "session_id", None))
```

Add `role=getattr(args, "role", None),` (any position among the kwargs; append at the end for a minimal diff):

```python
            job = dispatch_agent(args.agent or known_agents[0], args.task, story_id=args.story_id,
                                 agent_id=resolved_agent_id,
                                 force_agent=getattr(args, "force_agent", False),
                                 static_baseline=getattr(args, "static_baseline", False),
                                 requires_gh_write=_effective_requires_gh_write,
                                 task_type=getattr(args, "task_type", None),
                                 gh_write_target_kind=_resolved_gh_write_target_kind,
                                 requires=getattr(args, "requires", []),
                                 context_mode=getattr(args, "context_mode", "task"),
                                 skip_preflight=getattr(args, "skip_preflight", False),
                                 base=getattr(args, "base", None),
                                 grants=getattr(args, "grant", []),
                                 revokes=getattr(args, "revoke", []),
                                 issue=getattr(args, "issue", None),
                                 scope_paths=getattr(args, "scope_paths", []),
                                 session_id=getattr(args, "session_id", None),
                                 role=getattr(args, "role", None))
```

- [ ] **Step 8: Run all Task 5 tests to verify they pass**

Run: `python3 -m pytest tests/test_synlynk.py -k "gh_write_raises_without_resolvable_role or gh_write_resolves_explicit_role_flag or non_gh_write_still_defaults_role_to_dev or build_subprocess_env_raises_without_resolvable_role or build_subprocess_env_dev_default_unchanged" -v`
Expected: PASS (5 passed)

- [ ] **Step 9: Run Task 4's tests again to confirm the `role="qa"` kwarg now resolves correctly**

Run: `python3 -m pytest tests/test_synlynk.py -k "test_dispatch_agent_gh_write_auto_implies_run_shell or test_dispatch_agent_non_gh_write_does_not_add_run_shell" -v`
Expected: PASS (2 passed) — this confirms Task 4's test, which passed `role="qa"`, now actually exercises the new parameter rather than silently ignoring an unrecognized kwarg.

- [ ] **Step 10: Run the full existing dispatch test suite to check for regressions**

Run: `python3 -m pytest tests/test_synlynk.py -v 2>&1 | tail -60`
Expected: all tests pass. Pay particular attention to any test invoking `dispatch_agent(...)` with `requires_gh_write=True` and no `--as-agent`/`--story`/`--role` equivalent — such a test will now raise where it previously silently defaulted to `"dev"`. If any existing test fails this way, read it to determine whether it was implicitly relying on the old silent-default behavior (in which case, update it to pass an explicit `role=` or `story_id=` matching a tagged role, per spec §3.3 — this is the intended breaking change) or whether it's an unrelated regression (in which case, stop and investigate before proceeding).

- [ ] **Step 11: Commit**

```bash
git add synlynk/dispatch.py synlynk/cli.py tests/test_synlynk.py
git commit -m "feat(dispatch): fail closed on unresolvable role for --requires-gh-write, add --role flag"
```

---

### Task 6: Full suite run, self-review, and plan-vs-spec coverage check

**Files:** none (verification only)

- [ ] **Step 1: Run the complete test suite**

Run: `python3 -m pytest tests/ -v 2>&1 | tail -80`
Expected: all tests pass, zero failures, zero errors.

- [ ] **Step 2: Confirm spec §3.1–3.3 and §4 coverage**

Cross-check against `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`:
- §3.1 (harness default correction + CLAUDE.md text) → Tasks 1, 2, 3.
- §3.2 (`run:shell` auto-imply) → Task 4.
- §3.3 (fail-closed role resolution + `--role` flag) → Task 5.
- §4's four test scenarios → covered by Task 4's two tests (run:shell auto-imply, non-gh-write unaffected) and Task 5's tests (no-role raises, `--role qa` resolves) plus Task 2's three tests (claude-first, agy-fallback, non-gh-write alphabetical unchanged).

- [ ] **Step 3: Push the branch**

```bash
git push -u origin docs/gh-write-identity-hardening-design
```

- [ ] **Step 4: Open the PR bundling spec + plan + implementation**

```bash
gh pr create --title "fix(dispatch): gh-write identity hardening — Phase 1 closeout (#423)" --body "$(cat <<'EOF'
## Summary
- Corrects `can_gh_write` baselines (agy False→True, grok True→False) per this session's live-tested dispatch results (job-488c152f, job-a7ab9a0c, job-3e428904)
- Prefers `claude` over `agy` for gh-write harness auto-selection; corrects the #426 routing SOP in both `probe.py` generator sources and the regenerated `CLAUDE.md`
- `--requires-gh-write` now auto-implies the `run:shell` permission grant
- gh-write dispatches now fail closed with a `RuntimeError` instead of silently defaulting to the `dev` role identity; adds a new `--role <role>` dispatch flag as an explicit resolution source

## Test plan
- [ ] `python3 -m pytest tests/ -v` — full suite green
- [ ] `grep -n "GitHub write routing" CLAUDE.md` shows the corrected claude/agy sentence
- [ ] Manual smoke: `python3 -m synlynk dispatch claude --requires-gh-write --role qa --task "..." --dry-run` resolves without error; the same command without `--role`/`--as-agent`/`--story` raises the new fail-closed RuntimeError

Includes: `docs/superpowers/specs/2026-08-23-gh-write-identity-hardening-design.md`, `docs/superpowers/plans/2026-08-23-gh-write-identity-hardening.md`

Relates to #423, #569, #426. Tracking issue for the gh-write broker revival (Phase 1b): #1109.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
EOF
)"
```

- [ ] **Step 5: Note the Cost Capture Protocol and Blog Post Protocol obligations**

Per project CLAUDE.md, before merge: confirm all implementer-stage work in this PR was dispatched via `synlynk dispatch` (auto-captured) and log any native/PM-session cost via `synlynk cost log`. Draft the corresponding blog post in `docs/blog/` in this same branch before or immediately after opening the PR, per the Blog Post Protocol — describing the two live-test harness comparisons (Agy vs claude), the TC-7 bug found along the way, and this hardening pass as the concrete outcome.
