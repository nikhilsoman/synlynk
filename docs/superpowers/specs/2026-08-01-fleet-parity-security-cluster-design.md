# Fleet-Parity Security Cluster — Design

**Status:** Draft, pending review
**Issues:** #348 (dispatched subprocess env leaks host secrets), #338 (permission enforcement is a no-op for some agents)
**Deferred to a follow-up spec:** #340, #342, #347 (reliability cluster — job silently fails/drifts but doesn't exceed granted scope)

## Background

The fleet-parity audit (issues #332/#338/#340/#342/#347/#348/#419/#461, tracked in project memory as queued after PR #587) split into two severity clusters. #332/#419/#461 were already fixed by PR #604 and have been closed directly (never used a GitHub closing keyword, so they'd stayed open). The remaining five split by whether the gap lets a dispatched agent **do more than it was granted** (security severity: #348, #338) versus **fail or drift without exceeding scope** (reliability severity: #340, #342, #347). This spec covers the security cluster only.

Two concrete gaps, both in `synlynk/dispatch.py`:

1. **#348 — every dispatched subprocess inherits the full parent environment.** `proc_env = os.environ.copy()` (line 1836) hands every dispatched CLI — including agents running under weaker trust assumptions — the operator's AWS keys, unrelated API tokens, and anything else sitting in the shell environment. There is no allowlist.
2. **#338 — `_permissions_to_flags()` cannot enforce restrictions for every agent.** Claude (`--allowedTools`), Codex (`--ask-for-approval untrusted`), and Grok (`_grok_permission_flags`, landed this session) have real per-permission CLI enforcement. Agy escalates to `--dangerously-skip-permissions` for any write/run permission but only *warns* (does not block) when dispatched with read-only permissions — a silent no-op that gives false confidence a restriction is in effect. Local (aider) has zero enforcement: no permission-shaped flag exists in its declared `valid_flags` at all.

## Decisions Locked In (from brainstorming)

- **Fail closed, not warn-and-proceed.** When an agent has no real mechanism to enforce a requested restriction, the dispatch must refuse to start rather than proceed with a warning. A silent no-op is worse than a loud refusal — it gives the illusion of a restriction that isn't there.
- **Tight allowlist, not a denylist.** The subprocess environment is built by allowlisting a minimal fixed set of vars plus each agent's own declared requirements — not by copying everything and stripping known-secret-shaped patterns. Deny-by-default is the safer default; a denylist only ever catches patterns someone thought to strip.
- **Local (aider): fail closed, no new enforcement mechanism.** aider's actual CLI may support a `--read <file>` flag for read-only file context (unverified in this environment — aider isn't installed here), but wiring that up requires testing against a real aider install. Out of scope for this spec; Local gets the same fail-closed treatment as any agent with no declared enforcement mechanism, and the `--read` investigation is logged as a follow-up.
- **Agy: no `--sandbox` investigation.** Agy's write-permission path is unchanged (still escalates to `--dangerously-skip-permissions` — there's no partial-write-scope flag to target restrictions at). Its read-only path changes from warn to fail-closed. `--sandbox`'s actual semantics aren't documented in this repo and investigating it is deferred.
- **#348's other suggested fixes ride along:** a generic secret-pattern redaction pass on captured stdout/stderr (today's `_redact_active_tokens()` only redacts synlynk's own minted GitHub App tokens), plus a `.gitignore` audit for job log directories. The audit is already resolved by inspection (see below) — no code change needed there.

## Architecture

Two new centralized functions in `synlynk/dispatch.py`, each with a single call site, mirroring the shape of the just-landed `_grok_permission_flags()`:

### 1. `_permissions_to_flags()` fails closed

Add a `PermissionEnforcementError(RuntimeError)` exception. Where the function currently prints a warning and returns `[]` (Agy read-only case) or falls through to a bare `return []` (Local, any permissions beyond none), it instead raises:

```python
class PermissionEnforcementError(RuntimeError):
    """Raised when an agent has no real mechanism to enforce requested permissions."""
```

- **Agy:** if `permissions` is non-empty and `set(permissions) <= {"read:*"}` (today's warn branch), raise instead of warning. The write/run branch (escalate to `--dangerously-skip-permissions`) is unchanged — that's real enforcement, just coarse-grained.
- **Local:** if `permissions` is non-empty (anything beyond an empty list — Local currently has zero permission-aware flags), raise. An empty permission list (no restriction requested) is a no-op, same as today.
- **Claude / Codex / Grok:** unchanged — all three have real per-permission enforcement already.

The caller (the main dispatch function, around where `_permissions_to_flags()` is currently invoked) lets `PermissionEnforcementError` propagate — dispatch fails before any subprocess spawns, with a message naming the agent and the unenforceable permissions.

### 2. `_build_subprocess_env()` replaces the unconditional `os.environ.copy()`

```python
_ENV_ALLOWLIST_BASE = [
    "PATH", "HOME", "LANG", "LC_ALL", "TERM", "TMPDIR",
    "USER", "SHELL", "SSH_AUTH_SOCK",
    "GIT_AUTHOR_NAME", "GIT_AUTHOR_EMAIL",
    "GIT_COMMITTER_NAME", "GIT_COMMITTER_EMAIL",
    "GIT_SSH_COMMAND",
]

def _build_subprocess_env(agent: str, overrides: dict, requires_gh_write: bool, story_id: str) -> dict:
    """Build a minimal, allowlisted environment for a dispatched subprocess."""
    baselines = AGENT_CAPABILITY_BASELINES.get(agent, {})
    allowed = set(_ENV_ALLOWLIST_BASE) | set(baselines.get("env_passthrough", []))

    proc_env = {k: v for k, v in os.environ.items() if k in allowed}
    proc_env.update(overrides.get("env", {}))

    for var in baselines.get("headless_contract", {}).get("env_vars_required", []):
        if "=" in var:
            k, v = var.split("=", 1)
            proc_env[k] = v

    if requires_gh_write:
        gh_token = _resolve_dispatch_gh_token(_role_for_story(story_id) or "dev")
        if gh_token:
            proc_env["GH_TOKEN"] = gh_token
        else:
            proc_env.pop("GH_TOKEN", None)
            proc_env.pop("GITHUB_TOKEN", None)
            print(
                "  ⚠ no role-scoped GitHub token available for this --requires-gh-write "
                "dispatch — stripping any inherited GH_TOKEN/GITHUB_TOKEN so the job cannot "
                "silently fall back to a personal credential; GitHub write actions in this "
                "job will fail until a role App is provisioned (see `synlynk identity init`).",
                file=sys.stderr,
            )
    return proc_env
```

This preserves the existing GH_TOKEN stripping/injection logic verbatim — only the base environment construction changes, from "copy everything" to "allowlist, then layer on required/override vars." The call site (`dispatch.py:1836-1856`) becomes a single call:

```python
proc_env = _build_subprocess_env(agent, overrides, requires_gh_write, story_id)
```

**New `AGENT_CAPABILITY_BASELINES` field: `env_passthrough`.** Each agent baseline gains an `env_passthrough: []` key (empty list default) naming any additional env vars that specific agent's CLI genuinely needs beyond the fixed base set — e.g., an API-key env var if a given CLI reads auth from the environment rather than a login file. **This spec does not populate real values for any agent** — the actual auth mechanism per CLI (env var vs. OAuth file vs. keychain) needs to be confirmed per agent during implementation, since getting this wrong either leaks a var that should've been stripped or breaks an agent's auth. The implementation plan includes one task per agent: confirm its real auth dependency (read CLI docs / test invocation), and add to `env_passthrough` only if genuinely required. If a task's investigation can't confirm a dependency, `env_passthrough` stays empty for that agent — better to fail visibly (auth error) than reintroduce a broad leak.

### 3. Generic secret redaction on captured output

Extend `synlynk/__init__.py`'s existing `_redact_active_tokens()` call sites (lines 2317/2320, where captured job output is printed/logged) with a second pass, `_redact_secret_patterns(text)`, applied after the existing token-specific redaction:

```python
_SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),           # GitHub PAT
    re.compile(r"gh[oprsu]_[A-Za-z0-9]{36}"),     # GitHub OAuth/App/refresh/server tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),               # AWS access key ID
    re.compile(r"sk-[A-Za-z0-9]{20,}"),            # OpenAI-style secret key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),   # Slack token
]

def _redact_secret_patterns(text: str) -> str:
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[REDACTED]", text)
    return text
```

Applied wherever `_redact_active_tokens()` is currently called on captured stdout/stderr before it's printed or persisted (job logs, telemetry). This is pattern-based and necessarily incomplete (it can't catch arbitrary high-entropy secrets with no recognizable prefix) — it closes the gap for the common, recognizable credential shapes, same tier of coverage as the tight env allowlist is meant to prevent from ever reaching the subprocess in the first place. The env allowlist is the primary defense; this redaction pass is defense-in-depth for the case where a secret still ends up in captured output some other way (e.g., echoed by the dispatched agent itself).

### 4. `.gitignore` audit — resolved by inspection, no code change

Job logs are written to `<job_worktree>/.synlynk/logs/<job_id>.log` (`dispatch.py:1682-1689`). The repo's root `.gitignore` already has `.synlynk/*` ignored, with only `!.synlynk/roles.yaml` and `!.synlynk/capability-roles.json` excepted — neither matches the `logs/` subdirectory. Since job worktrees share the repo's root `.gitignore` (git worktrees use the same ignore rules as the main checkout), job logs are already excluded from any commit. This finding is recorded here rather than actioned as a task.

## Data Flow / Error Handling

- A restrictive-permission dispatch to Local, or a read-only dispatch to Agy, now raises `PermissionEnforcementError` **before** `_build_subprocess_env()` runs and before any worktree/subprocess work begins — the failure is immediate and cheap, not a wasted dispatch.
- The env allowlist change is purely additive-restrictive: it cannot cause a previously-failing dispatch to newly succeed, only the reverse (an agent that silently depended on an unlisted env var will now fail loudly, e.g. with an auth error). This is treated as a feature, not a regression to work around — a silent env dependency was itself a latent version of the #348 gap. Per-agent `env_passthrough` investigation during implementation is how legitimate dependencies get whitelisted rather than papered over.
- Redaction is best-effort and applied at the output layer, not the execution layer — it does not change what the subprocess can access (the allowlist does that), only what makes it into logs/telemetry/printed output.

## Testing

- `_permissions_to_flags()`: parametrized tests asserting `PermissionEnforcementError` is raised for Local with any non-empty permission set, and for Agy with a read-only-only permission set; assert existing Claude/Codex/Grok/Agy-write behavior is unchanged (regression coverage for the pre-existing branches).
- `_build_subprocess_env()`: test that an unlisted var (e.g. a fake `AWS_SECRET_ACCESS_KEY` injected into `os.environ` via monkeypatch) does not appear in the returned dict; test that `PATH`/`HOME` always appear; test `env_passthrough` vars from a baseline are included; test GH_TOKEN injection/stripping behavior is preserved exactly (reuse/adapt existing tests for the current inline logic).
- `_redact_secret_patterns()`: one test per pattern (feed a synthetic matching string, assert `[REDACTED]` in output and the literal secret is not); one test asserting normal non-secret-shaped text passes through unchanged.
- Full existing dispatch test suite must stay green — the env/permission changes touch a shared code path used by every dispatch, so regression risk is broad; run the full suite, not just new tests, before merging.

## Out of Scope (this spec)

- Reliability cluster (#340/#342/#347) — separate follow-up spec.
- Local/aider real file-scoping via `--read` (needs a real aider install to verify) — follow-up.
- Agy `--sandbox` investigation — follow-up.
- Populating real `env_passthrough` values beyond what implementation-time per-agent investigation confirms — if no dependency is found, the field stays empty; this spec does not mandate exhaustive CLI-docs research per agent, only enough to avoid an obvious auth break.
