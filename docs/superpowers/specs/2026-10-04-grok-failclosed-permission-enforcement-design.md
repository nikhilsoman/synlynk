# Design: Grok Fail-Closed Permission Enforcement (gh:#1925, part 1)

**Status:** Approved by Nikhil (conversational design), pending written-spec review
**Date:** 2026-10-04
**Scope:** Part 1 of gh:#1925 ("Safe-by-default execution") only. Part 2 (containerized
execution for untrusted/third-party harnesses) is deliberately out of scope here and will
get its own future spec/issue.

## Problem

Grok is the only core-fleet harness whose dispatch path **unconditionally** injects a full
permission bypass (`--always-approve` plus `--permission-mode bypassPermissions`), regardless
of the `skip_permissions` parameter that correctly gates the same decision for Claude, Agy,
and Codex. Today this happens in two places:

1. `synlynk/_constants.py` — Grok's `HARNESS_CAPABILITY_BASELINES` entry sets
   `dispatch_flags.required_flags = ["--always-approve"]` unconditionally (Claude/Agy's
   equivalent entries are `[]`, i.e. properly opt-in).
2. `synlynk/dispatch.py`'s `_grok_permission_flags(permissions)` — returns the bypass flags
   whenever `permissions` is non-empty, with no `skip_permissions` gate at all (the function
   doesn't even accept that parameter).

This is a real, silent unsafe-by-default gap matching gh:#1925's framing: a caller that
requests scoped permissions for Grok gets a full bypass instead, with no error, no warning,
and no way to opt out.

However, this isn't simply an oversight to delete. `docs/rca/2026-09-22-LIVE-13-grok-headless-dispatch-permission-bypass.md`
root-caused *why* the bypass became unconditional: Grok's CLI (v1.0.30) has no working
non-bypass headless mode. Under `--permission-mode dontAsk`, Grok's internal shell AST
splitter and risk classifier (`bash_command_splitting.rs`, `exec_risk.rs`) silently cancel
compound shell/file-mutation tool calls (`stopReason: "cancelled"`), and sometimes return a
conversational refusal with exit code 0 — a false-success silent no-op. PR #1279/#599 made
`--always-approve` + `--permission-mode bypassPermissions` unconditional specifically to stop
dispatches from silently doing nothing while reporting success. Naively flipping this back to
scoped/opt-in permissions would reopen LIVE-13.

## Goals

- Make the Grok bypass **structurally explicit and gated in code**, not implicit in a shared
  baseline table, so a reader/auditor can see it's a deliberate, named exception rather than
  a missed case.
- Provide a real fail-closed path (mirroring the `local` adapter's `PermissionEnforcementError`)
  for the case where a caller explicitly declines the bypass for Grok — today impossible,
  going forward an explicit `skip_permissions=False` refusal.
- Preserve every existing caller's behavior. No existing CLI invocation, auto-routing path, or
  test should need to change to keep working.

## Non-goals

- Containerized/sandboxed execution for Grok or any other harness (gh:#1925 part 2).
- Giving Grok a real scoped-permission mode — its CLI doesn't support one today. This design
  only makes the *absence* of one explicit and intentional, not fixed.
- Changing user-facing CLI flags (`--dangerously-skip-permissions` in `cli.py` is untouched).

## Approach

Mirror the `local` adapter's pattern: `translate_permissions`/`_grok_permission_flags` raises
`PermissionEnforcementError` when permissions are requested and the caller has not opted into
the bypass, instead of silently granting it. Unlike `local` (which can *never* enforce
permissions and therefore always raises), Grok's version is **gated by `skip_permissions`**:
when `True`, it returns the bypass flags unchanged (today's behavior); when `False` and
permissions are requested, it raises.

Because no caller passes `skip_permissions=True` for Grok today, `dispatch_agent()` itself
auto-supplies it internally the moment it resolves `agent == "grok"` — so every existing
caller keeps working exactly as before, and the new fail-closed path only fires if some future
caller explicitly passes `skip_permissions=False` for a Grok dispatch that requests
permissions (which cannot happen today, but is now a real, named outcome instead of an
impossible-to-reach branch).

## Components touched

### 1. `synlynk/_constants.py`

Remove the unconditional `"--always-approve"` from Grok's baseline `dispatch_flags.required_flags`
(this currently forces the bypass even in code paths that read the baseline directly without
going through `_permissions_to_flags`/`_grok_permission_flags` at all). After this change,
Grok's `required_flags` is `[]`, matching Claude/Agy, and the bypass is only ever added by the
explicit, gated logic in `_dispatch_flags_for_agent()` described below.

### 2. `synlynk/dispatch.py`

- **`_grok_permission_flags(permissions, skip_permissions=False)`** gains the
  `skip_permissions` parameter. Behavior:
  - If `permissions` is empty: return `[]` (unchanged).
  - If `permissions` is non-empty and `skip_permissions=True`: return
    `["--always-approve", "--permission-mode", "bypassPermissions"]` (unchanged from today).
  - If `permissions` is non-empty and `skip_permissions=False`: raise
    `PermissionEnforcementError` (the existing class already defined at `dispatch.py:713`),
    with a message explaining Grok has no scoped-permission mode and the bypass was declined.
- **`_permissions_to_flags(agent, permissions, read_only=False, skip_permissions=False)`**'s
  `grok` branch passes `skip_permissions` through to `_grok_permission_flags` (today it calls
  it with no `skip_permissions` awareness at all).
- **`_dispatch_flags_for_agent(agent, skip_permissions=False)`**: the existing
  `skip_permissions`-gated append set (currently `{"claude", "agy"}`, the set of agents for
  which `--dangerously-skip-permissions` is appended when `skip_permissions=True`) gains
  `"grok"`. This is what replaces the old unconditional `required_flags` entry removed in
  step 1 — the flag now only gets added through this explicit, named gate.
- **`dispatch_agent(...)`**: immediately after the function resolves the final `agent` value
  (before any permission-flag logic runs), add:

  ```python
  if agent == "grok" and not skip_permissions:
      # Grok's CLI has no working non-bypass headless mode (LIVE-13:
      # docs/rca/2026-09-22-LIVE-13-grok-headless-dispatch-permission-bypass.md).
      # Auto-opt-in here (rather than requiring every caller to pass
      # --dangerously-skip-permissions) so existing Grok dispatch workflows keep
      # working unchanged after gh:#1925 part 1 made the bypass gated instead of
      # unconditional. See docs/superpowers/specs/2026-10-04-grok-failclosed-permission-enforcement-design.md.
      skip_permissions = True
  ```

  This is the one piece of genuinely new logic in this design — everything else is moving an
  existing implicit default behind an explicit, named gate.

### 3. `synlynk/harness_adapters/grok.py`

This adapter is not yet live — `get_adapter()` is called in `dispatch_agent()` only for
later-stage use (`classify_failure`/`parse_output`); command-building and permission
translation still run through the legacy `dispatch.py` functions above. But
`GrokAdapter.translate_permissions()` currently duplicates the exact same unconditional-bypass
bug, and leaving it unfixed would silently reintroduce the bug the moment a future pipeline
cutover (gh:#1924 follow-on) starts using it for real. Update it to match:

```python
def translate_permissions(self, permissions: list, read_only: bool, skip_permissions: bool = False) -> list:
    permission_set = {perm for perm in (permissions or []) if perm}
    if not permission_set:
        return []
    if not skip_permissions:
        raise PermissionEnforcementError(
            "grok has no scoped-permission headless mode (LIVE-13); "
            "the bypass was declined by passing skip_permissions=False. "
            "Pass skip_permissions=True to proceed with --always-approve "
            "--permission-mode bypassPermissions."
        )
    return ["--always-approve", "--permission-mode", "bypassPermissions"]
```

`PermissionEnforcementError` is imported from `synlynk.harness_adapters.local` (where it's
already defined) rather than redefined — this is the first adapter besides `local` to need it,
so this design also moves the class to `synlynk/harness_adapters/base.py` and has both
`local.py` and `grok.py` import it from there, eliminating the pre-existing duplicate
class-identity split between `dispatch.py:713`'s `PermissionEnforcementError` and
`harness_adapters/local.py:8`'s separate class of the same name. (The `dispatch.py` copy stays
as-is; this only consolidates the two `harness_adapters/*.py` copies into one.)

### 4. `synlynk/harness_adapters/request.py` and `base.py`

- `DispatchRequest` (a frozen dataclass) gains `skip_permissions: bool = False` — additive,
  default-valued, so no existing construction site breaks.
- The `HarnessAdapter` `Protocol` in `base.py` gains `skip_permissions: bool = False` to its
  `translate_permissions` signature. Other adapters (`claude.py`, `codex.py`, `agy.py`,
  `local.py`) ignore the new parameter except `local.py`, which already raises unconditionally
  regardless of its value (unaffected — `local` has no bypass to gate).

## Testing

- Update `test_grok_permission_flags_emits_always_approve_when_shell_or_tests_granted`
  (`tests/test_dispatch.py:1918`) to call `_grok_permission_flags(..., skip_permissions=True)`
  explicitly, since that's now required to reach the bypass branch.
- Add `test_grok_permission_flags_raises_when_not_skipped`: asserts
  `_grok_permission_flags(["shell"], skip_permissions=False)` raises
  `PermissionEnforcementError`.
- Add `test_grok_permission_flags_empty_permissions_never_raises`: asserts
  `_grok_permission_flags([], skip_permissions=False) == []` (no permissions requested means
  nothing to enforce, regardless of the flag).
- Add a `dispatch_agent()`-level test, `test_grok_dispatch_auto_skips_permissions_by_default`:
  dispatch a Grok job with permissions requested and no explicit `skip_permissions` argument;
  assert it succeeds and the resulting command includes the bypass flags (confirming the
  internal auto-opt-in keeps today's callers working unchanged).
- Add `test_grok_adapter_translate_permissions_raises_when_not_skipped` and
  `test_grok_adapter_translate_permissions_bypasses_when_skipped` mirroring the legacy tests,
  against `GrokAdapter.translate_permissions` directly.
- Add `test_local_and_grok_adapters_share_permission_enforcement_error_class`: asserts
  `harness_adapters.local.PermissionEnforcementError is harness_adapters.grok.PermissionEnforcementError`
  is `harness_adapters.base.PermissionEnforcementError` (confirms the consolidation in
  component 3 actually happened, not just a second same-named class).
- Existing `test_grok_dispatch_deduplicates_boolean_permission_and_baseline_flags`
  (`tests/test_dispatch.py:1934`) must still pass unchanged — it exercises the boolean-flag
  dedup logic, which is untouched by this design.

## Out of scope (tracked separately)

Containerized execution for untrusted/third-party harnesses (gh:#1925 part 2) — the real
long-term fix for "Grok needs real sandboxing, not just an honest flag" — stays a future spec.
`docker/Dockerfile.sovereign` already exists as groundwork but is not wired into dispatch; this
design does not touch it.
