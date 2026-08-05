# 96: the request finally landed — and the model tried to delete a test file

## Where we left off

PR #678 fixed the litellm provider-prefix bug: `_local_dispatch_model_flags()` now sends
`openai/Ornith-1.0-9B-4bit` instead of the bare roster name, so Aider's requests actually
reach oMLX instead of erroring out before anything is sent. `exit 0` finally meant what it
said. Next step: re-run the same test dispatch on `main` and see what Ornith actually says.

## What moved the goalpost

The re-run (`synlynk dispatch local --task "Scan this repo and give me a summary"`) did
reach the model this time — real progress, and a strictly longer runtime (44+ minutes vs.
the previous attempt's instant litellm failure) was itself a plausible good sign. It wasn't.

The captured log showed the model open a `THINKING` block, correctly reason that it should
scan the repo and answer, then immediately start proposing whole-file rewrites instead —
beginning with `tests/test_agent_quota_tracking.py`, collapsed from 1,804 lines down to a
single line (`@@ -1,1804 +1 @@`). It kept doing this across file after file for 94,000+ log
lines with no summary ever appearing. The process was killed manually rather than left to
run indefinitely.

Root cause wasn't in `synlynk/local_agent.py` at all — `_local_dispatch_model_flags()`
already reads `edit_format` correctly per model from `.agents/local.json`. The bug was in
the data: the pinned `Ornith-1.0-9B-4bit` entry declared `"edit_format": "whole"`, which
tells Aider (and therefore the model) that any response must be expressed as a complete
replacement file. A capable model can recognize a plain question and just answer in prose
despite that constraint; this 9B model apparently can't reliably tell "answer in prose"
from "must emit a whole-file block," so a Q&A-shaped prompt got forced through the file-edit
code path and degenerated into near-empty rewrites.

Because Aider was also run with `--no-auto-commits`, none of the hallucinated edits actually
landed — `git status` in the job worktree showed only Aider's own harmless `.aider*` line
auto-added to `.gitignore`. No data was lost. But the dispatch produced nothing useful and
would not have converged on its own.

## What this PR ships

A one-line **config** correction, not a code change — `.agents/local.json`:

```json
{"id": "Ornith-1.0-9B-4bit", "pinned": true, "edit_format": "diff"},
```

`diff` format doesn't carry the same "reproduce the entire file" pressure — a no-op response
is a valid near-empty diff hunk rather than a full-file replacement — and is Aider's own
recommended default for models at this capability tier. `qwen-coder` and `gemma-coder`
roster entries are untouched (they aren't actually downloaded into oMLX yet — a separate,
already-flagged gap, out of scope here).

Caught a genuinely new failure mode along the way: Codex's sandbox denied direct filesystem
writes to `.agents/local.json`, so it worked around it with `git update-index --cacheinfo`
to stage the correct blob straight into git's index, then committed cleanly. That commit
(`f522266`) was correct. But the physical file on disk was never actually rewritten, and the
dispatch harness's own post-job wrap-up commit snapshotted that stale on-disk state,
silently reverting the fix in a second, harness-authored commit — a fourth distinct flavor
of "job reports done/exit 0 but the real change didn't stick" this session, this time caused
by the dispatch tooling itself rather than the agent or the model. Caught by reading the
actual git history and file contents directly rather than trusting job status, and fixed
with an explicit `git revert` of the harness's bogus commit before merging. Not fixed at the
harness level in this PR — flagged as a follow-up, kept out of scope to keep this branch
narrow.

This does **not** make `local` dispatch a general-purpose Q&A agent — it remains scoped to
coding tasks with file-edit deliverables, same as the other four agents. `diff` format
reduces the blast radius of a confused response; it doesn't guarantee a coherent one.
True read-only/Q&A support for `local` is an explicit non-goal here, not solved.

Backfilled as Addendum 4 / Task Group 9 into the same design spec and implementation plan
that already carry Addenda 1–3 — the fourth time this pattern has held for this feature.

## Next goalpost

Two threads worth raising explicitly: (1) whether to file and act on the dispatch-harness
wrap-up-commit bug found above — it's not specific to `local`, any sandboxed agent write
workaround could hit the same silent-revert failure mode; (2) the same two longer-standing
open items as before — user review of the fleet-parity reliability cluster spec, and the
not-yet-started herdr-integration brainstorm.
