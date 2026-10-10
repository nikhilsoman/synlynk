# PR #2029 GOVERNS attribution fix — superseded attempt

PR #2029 (governs_gate.py attribution fix) went through three Codex implementation
attempts before CI went fully green and the PR merged (squash commit `0f9740c`,
2026-10-05, merged by `app/synlynk-synlynk-qa`):

1. `job-187f4d70` — first attempt, regressions found by Grok review (`job-3690f7b6`)
2. `job-1fad5e08` — second attempt, abandoned mid-fix (uncommitted, never pushed);
   superseded by a redesigned third attempt before this diff was committed. Archived
   here per the Worktree Hygiene Protocol's archive-before-removal rule since it was
   genuinely unmerged work with no associated PR.
3. `job-17f7dcad` — third attempt, redesigned per explicit instruction to require
   explicit PR/issue linkage rather than shared `story_id` alone; this is what
   actually shipped in the merged PR.

`job-1fad5e08-second-attempt.diff` is the uncommitted working-tree diff from the
abandoned second attempt, preserved for reference only — it was never committed,
pushed, or reviewed, and does not represent the shipped fix.
