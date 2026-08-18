# GH-Write Delivery Verification, Round 2 (#659 + #860) — Design

## Summary

The job-truth/gh-write consolidation work (`#701`, design spec `2026-08-15-job-truth-gh-write-consolidation-design.md`, shipped via PR `#978`) built a ground-truth-verification (GTV) mechanism — `gh_write_verified()` — that checks whether a `--requires-gh-write` job's declared GitHub effect actually landed, instead of trusting the job's self-reported exit status. It shipped Tasks 0–4 (schema, shared helper, `synlynk jobs` surfacing, a regression guard) and part of Task 5 (a CLI-routing instruction telling Codex to use `gh pr review`/`gh pr comment` instead of MCP tools). Tasks 6–8 (close `#331`/`#579`, retitle `#426`, close `#935`/`#701`) only partially ran — `#331`/`#579` are closed, but `#935`, `#701`, and `#426` are still open/stale.

Two gaps survived that shipped work, discovered by re-hitting `#659` live during this session (Grok job dispatched for PR `#1038`'s review reported `OK (exit 0)` with `stopReason: "cancelled"` in its own transcript — no review was ever posted):

1. **The CLI-routing mitigation is Codex-only.** `_format_prompt_for_agent()` only injects the "use `gh` CLI, not MCP tools" instruction inside the `agent == "codex"` branch. Grok, Agy, and any other agent get no such instruction. Since a 2026-08-09 decision (`dec-d90d14ad`) retired `#426`'s "route gh-write to Grok by default" policy in favor of ordinary capability-based routing (Codex excluded only on execution-capability grounds, tracked separately in `#865`), Grok and Agy are now the **default** targets for gh-write review tasks — this gap is on the live path, not an edge case.

2. **`gh_write_verified()` cannot express "a review/comment was posted."** It only supports `expect="closed"` and `expect="merged"` (exact-match on `gh <kind> view --json state`). `gh_write_target` is only ever built as `issue:<N>` (never `pr:<N>`, even though the parser already accepts it). A review-only dispatch has no verifiable target shape at all — this is the shared structural cause of both `#659` (false-positive: job says OK, write didn't land) and `#860` (false-negative: job says failed, write did land) for this specific effect type. Neither direction can be checked today because the check has no vocabulary for "reviewed"/"commented."

This design closes both gaps and reuses two pieces of infrastructure that postdate the original `#701` spec:

- **Role-scoped GitHub App identities** (`#859`, closed/verified): `--requires-gh-write` dispatches now run under `synlynk-<repo-slug>-<role>[bot]`, not the shared personal identity `#423` assumed. Verification can filter by actual author, not just timestamp.
- **`_reviewer_role_from_login()`** (`synlynk/events.py`, from the GOVERNS `review_submitted` event work, `#77`): already parses that bot-login pattern. This design reuses it rather than re-deriving role-from-login logic a second time.

## Non-goals (explicitly out of scope)

- **Root-causing the MCP connector's cancellation itself.** Unchanged from the original spec — still not diagnosed, still out of scope. This design only extends detection and routes around it, as before.
- **Using MCP tools for the verification check.** Considered and rejected: verification runs inside `synlynk`'s own Python reconciliation code (`_check_job_stall`, `_reconcile_daemon_jobs`), which has no MCP client — only a dispatched agent's own tool-loop has MCP access. `gh` CLI is the only viable transport for an orchestrator-side check.
- **Reusing `scan_local_events`/`_scan_pr_reviews`'s events-table as the verification source of truth.** Considered and rejected: that mechanism only runs on `workspace_agent.py`'s own poll cadence (not on-demand), so it isn't guaranteed fresh at the exact moment a stall-kill decision or terminal reconciliation needs an answer. This design calls `gh pr view` directly and synchronously instead, reusing only the author/role-parsing logic from `events.py`, not the table itself.
- **`#865`** (whether Codex's sandbox egress block to `api.github.com` is fixable) — real, related, explicitly deferred by its own panel review ("not urgent; do not block other dispatch-policy work on this"). Referenced from `#659`'s tracking comment, not solved here.
- **Extending `expect` beyond `closed`/`merged`/`review_posted`/`comment_posted`.** No other gh-write effect type has a documented failure history; YAGNI.

## Architecture

### 1. `synlynk/gh_verify.py` — extend `gh_write_verified()`

Add two new `expect` values that check a list field for a matching entry, instead of an exact scalar match:

```python
_LIST_EXPECT_FIELD = {
    "review_posted": "reviews",
    "comment_posted": "comments",
}
```

New signature: `gh_write_verified(target, expect, timeout=10, since=None, expect_author=None)`.

- `since`: ISO8601 string (the job's `started_at`). Required for `review_posted`/`comment_posted` — without a time floor, a review posted by a human days earlier would false-positive every future job on the same PR. If `since` is `None` for these two `expect` values, return `None` (unknown) rather than guessing.
- `expect_author`: optional GitHub login (the resolved role's bot login, e.g. `synlynk-synlynk-dev[bot]`). When provided, an entry must match both the time floor and the author. When `None` (host-auth fallback path, no role token resolved), fall back to time-floor-only — matches the precision already available under the pre-`#859` shared-identity assumption, so this is strictly no worse than before, and strictly better whenever a role token exists.

```python
def gh_write_verified(target, expect, timeout=10, since=None, expect_author=None):
    if not target:
        return None
    match = _TARGET_RE.match(target)
    if not match:
        return None
    kind, number = match.groups()
    subcommand = "issue" if kind == "issue" else "pr"

    if expect in _EXPECT_FIELD:
        field, expected_value = _EXPECT_FIELD[expect]
        cmd = ["gh", subcommand, "view", number, "--json", field]
    elif expect in _LIST_EXPECT_FIELD:
        if not since:
            return None
        field = _LIST_EXPECT_FIELD[expect]
        cmd = ["gh", subcommand, "view", number, "--json", field]
    else:
        return None

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
    except (subprocess.TimeoutExpired, FileNotFoundError, OSError):
        return None
    if result.returncode != 0:
        return None
    try:
        payload = json.loads(result.stdout)
    except (json.JSONDecodeError, ValueError):
        return None

    if expect in _EXPECT_FIELD:
        actual = payload.get(field)
        return None if actual is None else actual == expected_value

    entries = payload.get(field)
    if entries is None:
        return None
    since_dt = _parse_iso8601(since)
    if since_dt is None:
        return None
    for entry in entries:
        entry_time = entry.get("submittedAt") or entry.get("createdAt")
        entry_dt = _parse_iso8601(entry_time)
        if entry_dt is None or entry_dt < since_dt:
            continue
        if expect_author and (entry.get("author") or {}).get("login") != expect_author:
            continue
        return True
    return False
```

`_parse_iso8601` is a small new helper (`datetime.fromisoformat` with a `Z`-suffix normalization, since `gh`'s JSON timestamps use `Z` and `fromisoformat` pre-3.11 doesn't accept it directly — this repo's CI matrix includes 3.8/3.10/3.12 per the existing GitHub Actions config, so this must not assume 3.11+ parsing).

`reviews` entries already carry `author.login` (per `events.py:_scan_pr_reviews`, proven pattern); `comments` entries carry the same shape via `gh pr view --json comments`.

### 2. `synlynk/dispatch.py` — thread `since`/`expect_author` through

- `gh_write_target` construction (currently `synlynk/dispatch.py:2536-2538`, issue-only): extend to also build `pr:<N>` when the dispatch is a review/comment-type task. The existing `_TARGET_RE` in `gh_verify.py` already accepts `pr:` — no parser change needed, only the construction site. Add an explicit `gh_write_target_kind: str = "issue"` parameter to `dispatch_agent()` (default preserves current behavior) so callers doing PR-review dispatches pass `gh_write_target_kind="pr"` alongside `issue=<pr_number>`.
- Resolve the expected bot login once, alongside the existing `_resolve_dispatch_gh_token(role)` call in `_build_subprocess_env` (`synlynk/dispatch.py:438-480`): derive it from the same `app_config` already loaded there (`app_config.get("app_slug")` gives the App slug; the bot login is `f"{app_slug}[bot]"` per GitHub's convention — confirm exact shape against a live `.synlynk/github_apps/*.json` during implementation, since `app_slug` there may already include the `[bot]` suffix or not). Store it on the job dict as `expect_author` (flat-file) / a new `daemon_jobs.gh_write_author` column (sqlite), mirroring how `gh_write_target` is already persisted on both tracking mechanisms.
- Both call sites that already call `gh_write_verified`/`_apply_gh_write_verification` (`_check_job_stall` at `synlynk/dispatch.py:618-620`, `_reconcile_daemon_jobs`/`_apply_gh_write_verification` at `synlynk/jobs.py:2083-2096`) pass `since=job["started_at"]` and `expect_author=job.get("gh_write_author")` through. The `expect` value used for the check (currently hardcoded to `"closed"` in both call sites) needs to become data-driven — read from a new `gh_write_expect` field stored alongside `gh_write_target` at dispatch time (default `"closed"`, preserving current behavior for non-review dispatches; review/comment dispatches set it explicitly).

### 3. `_format_prompt_for_agent` — CLI-routing instruction for all agents

Move the `gh_write_instruction` block (`synlynk/dispatch.py:1078-1090`) out of the `if agent == "codex":` branch into a shared variable computed once at the top of the function (same content, same condition on `requires_gh_write`), and splice it into every agent branch's returned prompt (`codex`, `agy`, and the generic fallback branch — Grok uses the fallback branch per current code, confirm during implementation that no agent-specific branch already exists for `grok` that would need the same treatment).

### 4. Cheap audit: `task_type="review"` consistency

Before or alongside the above, grep every call site that dispatches a PR-review task (`grep -rn "task_type=.review." synlynk/`, plus any prompt-construction/plan-driven dispatch call sites that *should* be setting it but might not) and confirm they consistently pass `task_type="review"` so they get `review_stall_timeout_minutes` (90 min) rather than the generic `stall_timeout_minutes` (30 min) default. This is a verification/audit step, not a redesign — today's live recurrence was independently confirmed to be an in-agent cancellation (`stopReason: "cancelled"`), not a stall-timeout kill, so this is due diligence against a *different*, previously-unconfirmed failure class hiding in the same issue bucket, not a fix for `#659`/`#860` themselves.

### 5. Housekeeping (folds in the original plan's abandoned Tasks 6–8)

After the above ships and is independently verified end-to-end (dispatch a fresh review task with `--requires-gh-write`, confirm `gh_write_verified` correctly resolves `true`/`false` for the `review_posted` check against its real outcome):

- Close `#935` and `#701`, citing this work's PR and the verification job.
- Retitle `#426` to reflect the actual 2026-08-09 retirement decision (`project-docs/decisions/2026-08-09-should-synlynk-retire-its-standing-githu.md`) rather than leaving its stale "only Grok can do gh-write" framing — supersedes the retitle wording proposed in the original (unexecuted) Task 7.
- Add a comment to `#659` and `#860` referencing `#865` as the known-related, deliberately-deferred Codex-sandbox-egress question — not solved here, but no longer an unlinked loose end.
- `#659` and `#860` themselves stay open per the original disposition table's precedent (`#659`: "keep open, attach concrete next step") — this design is the next concrete step, not a closure; close them only once a subsequent live recurrence-free period confirms the fix holds, matching this repo's roadmap Definition of Done language ("no recurrence for one full release cycle").

## Data model changes

`daemon_jobs` (sqlite, `synlynk/db.py` migration block, same idempotent-`ALTER TABLE` pattern as the existing `requires_gh_write`/`gh_write_target`/`gh_write_verified` columns):

- `gh_write_author TEXT` — resolved bot login at dispatch time, or `NULL` if no role token was resolved (host-auth fallback).
- `gh_write_expect TEXT` — one of `closed`/`merged`/`review_posted`/`comment_posted`, defaults to `closed` for backward compatibility with existing non-review gh-write dispatches.

Flat-file job dict: same two new keys (`gh_write_author`, `gh_write_expect`), mirroring how `gh_write_target` is already dual-persisted.

## Testing

- `gh_write_verified()`: `review_posted`/`comment_posted` true when a matching entry exists at/after `since` — with and without `expect_author` set; false when only stale (before `since`) entries exist; false when entries exist after `since` but authored by someone else and `expect_author` is set; `None` when `since` is omitted for these two `expect` values; existing `closed`/`merged` behavior unchanged (regression).
- `_parse_iso8601`: handles `Z`-suffixed timestamps under Python 3.8 (this repo's CI floor) — write a direct unit test, don't rely on indirect coverage through `gh_write_verified`.
- `gh_write_target` construction: `pr:<N>` built when `gh_write_target_kind="pr"` passed to `dispatch_agent`; existing `issue:<N>` behavior unchanged when omitted (regression).
- `_build_subprocess_env`/dispatch: `gh_write_author` populated from `app_config` when a role token resolves; `None` under the host-auth fallback path (regression: existing fail-closed/allow-host-auth tests must still pass unchanged).
- `_format_prompt_for_agent`: the CLI-routing instruction now appears in the returned prompt for `agent="grok"` and `agent="agy"` (previously only `agent="codex"`), gated on `requires_gh_write=True`; absent when `requires_gh_write=False` for every agent (regression).
- `_check_job_stall` / `_apply_gh_write_verification`: pass through `since`/`expect_author`/`gh_write_expect` correctly; a `review_posted` job that's actually posted extends the stall timeout / doesn't get marked `succeeded_gh_write_failed`; one that hasn't, does.
- Regression guard (`tests/test_gh_write_guard.py`, already exists from `#978`): confirm it still passes unchanged — no new terminal-status-deciding function is introduced by this design, only the existing two are extended.
- Full suite (`pytest tests/ -x -q`) must stay green throughout.

## Rollout

Implementation routes to Codex via `synlynk dispatch` per this repo's capability table (Claude = PM/review/deploy only). No `--requires-gh-write` needed for the code/test tasks (Tasks 1–4 below are code-only). The housekeeping task (issue closes/retitle) is a separate `--requires-gh-write` dispatch to Grok/Agy, same pattern as the original plan.
