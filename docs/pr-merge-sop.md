# Pull request merge SOP

Before `gh pr merge`, the reviewer must run the merge oracle. Its JSON result
is the merge bit: merge only when `merge_allowed` is `true`.

CI and `qa-gate` are authoritative. Do not use `.synlynk/jobs.json` or a HUD
job status to decide whether a PR may merge; `failed_unverified` is not a
merge veto when the PR checks are green.
