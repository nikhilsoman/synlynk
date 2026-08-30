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

## tpm

**Sources consulted:** `project-docs/devlogs/nikhilsoman.md` in full, especially
the 2026-06-23 TPM Agent design entry, the 2026-08-23 autonomous-loop/release
entry, and the 2026-08-24 ticket-driven approval auto-resume entry;
`project-docs/memory.md` in full, especially "State DB & Agentic PM",
"Agent Identity, Dispatch & Entitlements", and "QA Completion Tracker +
Merge-Restricted-Classes Gate Mode"; `synlynk/tpm_sweep.py` and the related
`git log --oneline --grep="tpm\|sweep\|dispatch\|ticket" -i | head -60` history.

**Findings:** The live TPM implementation scans ready stories that have no
queued, running, or completed daemon job; checks policy authority; creates or
reuses approval tickets when dispatch is blocked; and consumes resolved ticket
state before dispatching. The 2026-08-24 record confirms this three-way
no-ticket/open/resolved flow and its durable event-scanner writeback. This is a
tasking and lifecycle-enforcement loop, not technical-plan authorship.

**Charter changes made:** Updated the Instructions, Authority & Escalation, and
Workflow Ownership body text to describe the implemented ready-story,
policy-gate, approval-ticket, and daemon-job behavior precisely. Frontmatter was
unchanged.

## designer

**Sources consulted:** `project-docs/devlogs/nikhilsoman.md` in full, especially
the 2026-06-28 BS-5 website scaffold entry, the 2026-06-29 website polish and
merge entry, and the 2026-08-09 user-facing guide and journey-map verification
entries; `project-docs/memory.md` in full, especially "Roadmap Realignment" and
"Agent Identity, Dispatch & Entitlements"; `git log --oneline
--grep="blog\|marketing\|designer\|css\|ui" -i | head -60`.

**Findings:** The corpus contains concrete UI, CSS, template, website, and
visual-verification work performed by Grok and Agy, including the BS-5 site
scaffold and Agy template/subpage work. It does not reliably identify any of
that work as executed under a `role=designer` charter; the role remains a
provisioned dispatch-only destination routed to Agy.

**Charter changes made:** None. The existing body already states the supported
UI/UX scope, dispatch-only durability, Agy routing, and information-architecture
escalation without claiming a designer track record. Frontmatter was unchanged.

## marketing

**Sources consulted:** `project-docs/devlogs/nikhilsoman.md` in full, especially
the 2026-06-28/29 website and blog work, the 2026-08-09 guide and release
bookkeeping entries, and the 2026-08-24 release/blog entry;
`project-docs/memory.md` in full, especially "Roadmap Realignment",
"Positioning", and the resolved "Blog Post Protocol" note; `docs/blog/README.md`
and its series index; `git log --oneline
--grep="blog\|marketing\|designer\|css\|ui" -i | head -60`.

**Findings:** The repository has a substantial blog and public-website corpus,
but the records attribute individual posts and content tasks to different
harnesses or direct PM work, not consistently to a `role=marketing` charter.
The corpus therefore supports marketing as an explicit dispatch-only comms
function, with the blog README/template as its content contract, but does not
support the stronger claim that marketing writes every PR's blog post.

**Charter changes made:** Updated the Instructions body to make comms work
explicitly dispatch-triggered and conditional on an approved technical summary,
and removed the unsupported universal "every PR" claim. Frontmatter was
unchanged.

### 2026-08-30 addendum: goal-0c4e96ff ownership

**Sources consulted:** `docs/superpowers/specs/2026-08-30-marketing-goal-ownership-design.md`
(approved design spec, PR #1294), `goal-0c4e96ff` story linkage (22 stories,
18 primary / 4 secondary via `goal_contributions`).

**Findings:** Unlike the original charter's Blog/Comms scope (evidenced by
actual PR history), this addition is a forward-looking, explicitly-approved
standing responsibility rather than a corpus-evidenced pattern — the readership
metrics needed to eventually evidence it are tracked as a prerequisite story
(`story-33ab504a`), not yet instrumented.

**Charter changes made:** Added one sentence to `## Workflow Ownership`
naming `goal-0c4e96ff` ownership, dispatched via the TPM sweep's role-based
routing (`synlynk/tpm_sweep.py`, Task 2 of this plan) rather than per-PR.
No change to `durability`, `Authority & Escalation`, or `Instructions`.
