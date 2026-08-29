# Charter Corpus References

For each role below: what corpus (devlog entries, commit ranges, memory files) was
consulted to validate or update that role's charter content in `synlynk/agent_cli.py`'s
`SEED_CHARTERS`, and what (if anything) changed as a result. Use this to check future
charter edits against real evidence rather than plausible-sounding prose.

Excluded: `pm` (already grounded via PR #1196) and `synlynk-bot` (infra catch-all,
no meaningful corpus of independent decisions to mine).

## dev

**Sources consulted:** `project-docs/devlogs/nikhilsoman.md` entries from 2026-06-23
through 2026-08-25, especially the 2026-06-23 v0.9.3 delivery entry, the 2026-07-03
daily-driver and Vizor delivery entries, and the 2026-08-09 and 2026-08-24 dispatch
and verification entries; `project-docs/memory.md` sections "Roadmap Realignment",
"Agent Identity, Dispatch & Entitlements", and "Dispatch Reliability Fixes"; and
`git log --oneline --grep="dispatch\|implement\|codex\|grok\|agy" -i | head -60`.

**Findings:** The recorded implementation work is dispatch-triggered and assigned to
Codex, Agy, or Grok against approved plans or tickets. The corpus repeatedly records
implementers following task breakdowns, with verification and review handled as
separate stages; it does not show an autonomous dev loop or a dev identity
redesigning an approved architecture mid-task.

**Charter changes made:** None. The existing dispatch-only, plan-following,
implementation-stage text matches the corpus.

## qa

**Sources consulted:** `project-docs/devlogs/nikhilsoman.md` entries from 2026-06-23
through 2026-08-25, especially the 2026-06-23 non-authoring review record, the
2026-08-09 independent test/CI verification record, the 2026-08-22 QA completion
tracker and merge-gate records, and the 2026-08-24 full-suite baseline record;
`project-docs/memory.md` section "QA Completion Tracker + Merge-Restricted-Classes
Gate Mode"; and `git log --oneline --grep="qa\|test\|verify" -i | head -60`.

**Findings:** QA work is test- and verification-centered: suites are rerun directly,
CI and diffs are checked, and the reviewer distinguishes verification from merge.
The corpus records `qa_gate_mode=merge-restricted-classes` as permitting QA to merge
docs-only PRs, while harder classes remain restricted and branch protection is still
deferred. The charter therefore needed to describe policy-limited merge authority,
not unrestricted authority over every PR.

**Charter changes made:** Updated the Instructions, Authority & Escalation, and
Workflow Ownership body text to make verification and policy-defined merge-gate
ownership explicit, including the demonstrated docs-only boundary. Frontmatter was
unchanged.

## architect

**Sources consulted:** `project-docs/devlogs/nikhilsoman.md` entries from 2026-06-23
through 2026-08-25, especially the 2026-07-30 review/merge process record, the
2026-08-09 and 2026-08-24 records identifying Claude as the pm/reviewer and merge
actor, and the 2026-08-25 backlog-triage record; `project-docs/memory.md` sections
"QA Completion Tracker + Merge-Restricted-Classes Gate Mode", "Agent Identity,
Dispatch & Entitlements", and "Dispatch Reliability Fixes"; and `git log
--oneline --grep="review\|merge\|architect" -i | head -60`.

**Findings:** The corpus contains extensive architecture, spec, plan, review, and
merge activity, but records Claude operating in the pm/reviewer role as the actor.
It does not show a separately exercised architect identity running those workflows.
The architect charter should describe that provisioned role without implying a
track record or independent merge authority that the corpus does not support.

**Charter changes made:** Updated the Instructions, Authority & Escalation, and
Workflow Ownership body text to identify the role as provisioned-but-largely-
unexercised, and to defer review/merge authority to explicit policy and the assigned
non-authoring reviewer. Frontmatter was unchanged.
