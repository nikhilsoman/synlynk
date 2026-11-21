# [LIVE-34] `github_sync_map` stale vs live GitHub milestones; `sync-roadmap` can silently corrupt them

- **Issue:** gh:#5443
- **Severity:** Sev1 (correctness bug that would silently corrupt live, public GitHub Milestone data)
- **Status:** No corruption occurred — caught before any write succeeded. Root cause of the drift not yet fully confirmed.
- **Date:** 2026-11-21

## Timeline

1. While closing out gh:#5434/PR #5440 (fix for `story_arc_version()` milestone resolution), ran `synlynk gh sync-roadmap --help` intending to see usage before invoking the real backfill for 15 plan-task stories under goal `goal-e03d2671` (v0.39.2, gh:#1993).
2. `--help` was **not** intercepted as a help flag. `synlynk/cli.py`'s `gh` command branch special-cases `gh_args[0] == "sync-roadmap"` and only checks membership of `"--dry-run"` / `"--backfill"` in the remaining `gh_args` — any other token, including `--help`, is silently ignored. This caused a real, full invocation of `cmd_sync_roadmap(dry_run=False, backfill=False, ...)`.
3. `cmd_sync_roadmap` iterates all 10 `is_milestone_eligible=1` `roadmap_arcs` rows in ascending `id` order and calls `gh_sync.sync_arc()` for each, which unconditionally PATCHes the milestone number recorded in `github_sync_map` with the arc's current title/state/description.
4. The first arc processed (`id=2`, `version='v0.26.10'`) is mapped to GitHub milestone **#21**. The PATCH attempted to set title=`v0.26.10`, state=`closed`. GitHub rejected it with **HTTP 422 Validation Failed**, raising `RuntimeError` and aborting the loop before any further arc was processed.
5. Investigating the 422 revealed milestone **#21** is *actually*, live on GitHub, titled `"0.39.2"` and **open** — not `v0.26.10` at all. A second spot-check on `roadmap_arcs.id=10` (`version='v0.39.2'`, mapped to milestone **#29**) found #29 is live-titled `"v0.9.2"` and **closed**, created and closed in the same second on 2026-10-30 — also completely inconsistent with the map.
6. Had the 422 not occurred, the real production GitHub repo's `"0.39.2"` milestone (#21) would have been overwritten with `v0.26.10`'s content and closed; v0.39.2's real content would never have reached milestone #29 (it's an unrelated, already-closed, differently-versioned milestone).

## Root cause

**Confirmed:**
- `cmd_sync_roadmap`'s lack of real flag parsing let `--help` silently fall through to a full, live, non-dry-run invocation (`synlynk/cli.py:2748-2760`).
- `sync_arc()` (`synlynk/gh_sync.py:156-199`) performs a live PATCH against whatever milestone number is recorded in `github_sync_map`, with no step that compares the milestone's current live title/content against what the map expects before overwriting it.
- `github_sync_map.last_synced_at` for the `entity_id='2' → github_number=21` row is `2026-11-20 04:04:37`, exactly matching milestone #21's live `updated_at`. A write genuinely landed there on that date — but the content now live (title `"0.39.2"`) doesn't match what `_arc_sync_fields()` should have sent for arc 2 (`title = roadmap_arcs.version = "v0.26.10"`).

**Not yet confirmed (needs `systematic-debugging` treatment, filed as follow-up in gh:#5443):**
- Whether `github_sync_map`'s `entity_id → github_number` assignment for arc 2 vs arc 10 was swapped or reassigned at some point after 2026-11-20's write, or whether the write on that date actually originated from a different arc/code path than today's `sync_arc()` logic.
- Whether this is the same class of bug as the separately-fixed `goals.arc_version` typo found during the gh:#5434 investigation (`'0.39.2'` stored without its leading `v`) — i.e., whether `roadmap_arcs.version` strings were also in a transient bad state around 2026-11-20 that happened to coincide with a sync.
- A structural anomaly in the same table — two distinct `entity_id`s (`1` and `74`) both mapped to `github_number=66` — was found but not investigated for cause.

## Impact

None realized. The only live write attempted (arc 2 → milestone #21) was rejected by GitHub's own validation (422) before any content changed. No milestone was corrupted. The backfill of the 15 plan-task stories (the original gh:#5434 motivation) was not run and remains pending until this is fixed.

## Why it wasn't caught by the 100% GOVERNS/review gates

This was a local, interactive-session mistake (a flag typo), not a dispatched/reviewed job — it happened during direct, ad hoc exploration of command usage after PR #5440 had already merged, outside any dispatch or PR review flow. No gate in the Hardened PR Review Policy applies to local, non-dispatched command invocations.

## Action items

1. **(gh:#5443, item 3)** Make `cli.py`'s `gh sync-roadmap` argument handling reject/ignore unrecognized flags explicitly instead of silently running the full real sync — at minimum, route `-h`/`--help` to real usage text instead of falling through.
2. **(gh:#5443, item 2)** Add a pre-PATCH guard in `sync_arc()`: fetch the target milestone's current title before writing, and abort+warn (don't silently overwrite) if it doesn't match what `github_sync_map`'s `content_hash` / last-known state expects.
3. **(gh:#5443, item 1)** Root-cause the actual drift for the arc 2/10 ↔ milestone 21/29 mapping specifically, using `systematic-debugging` — don't guess further without evidence.
4. **(gh:#5443, item 4)** Resolve the `entity_id` 1/74 → `github_number=66` collision.
5. Re-attempt the original goal — running `synlynk gh sync-roadmap --backfill` for real to attach the 15 plan-task stories to the v0.39.2 milestone — only after items 1–2 land, since the command remains unsafe to run against production in its current form.

## Prevention

Treat any CLI subcommand that performs live, non-idempotent external writes (GitHub API PATCH/POST/DELETE) as requiring genuine argparse-level flag validation and a pre-write diff/confirm step, not ad hoc membership checks against a raw trailing arg list. This is the same class of risk the Hardened PR Review Policy's merge-authority gating exists to prevent for dispatched work — it does not yet have an equivalent guard for ad hoc interactive invocations of destructive sync commands.
