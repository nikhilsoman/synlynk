# Repo Adoption Playbook — folding a repo's docs into synlynk

> **For agentic workers:** REQUIRED SUB-SKILL: use `superpowers:subagent-driven-development`
> (recommended) or `superpowers:executing-plans` to run this task-by-task. This is a
> docs-safety/ops migration, not a code feature — steps are exact commands and
> verification checks rather than test-driven code changes, but the same "no
> placeholders, run and verify each step" discipline applies.

**Goal:** Safely fold a target repo's pre-synlynk documentation into synlynk's
`state.db` schema via the five recognized file patterns (`memory.md`, `roadmap.md`,
`costs.md`, `devlogs/*.md`, `todo.md`), while permanently protecting every other
narrative document (RCAs, plans, research, strategy, reports, brainstorm) as
git-tracked content that lives outside anything `synlynk migrate` will touch.

**Architecture:** synlynk's `_migrate_import()` (in the installed `db.py`) only reads
exactly five path patterns inside `docs_dir`. Everything else in `docs_dir` gets
silently untracked (`git rm --cached -r docs_dir` + `.gitignore` append) by the real
(non-dry-run) `migrate` command, with no import path back into `state.db`. Most repos
adopting synlynk will have the *legacy* equivalents of the five schema files living in
inconsistent locations/names (e.g. `docs/Roadmap.md` vs `project-docs/roadmap.md`,
`docs/Backlog.md` vs `project-docs/todo.md`, a flat `docs/devlog.md` vs the expected
`devlogs/<author>.md` directory), and these must be reconciled into the exact
names/format the parser expects *before* migration — while everything outside those
five patterns must be confirmed to already live outside `docs_dir` and left untouched.

**Origin:** This playbook is a generalized extraction of the plan executed for
`cc-videoreframing` (`chore/synlynk-adoption-migration`, PR #80, 2026-08-01/02). It
folds in every gap found during that execution's two-stage subagent review and the
post-merge conflict/re-review cycle — see "Lessons baked into this version" below.

**Tech Stack:** synlynk (any version — confirm with `synlynk --version` and re-verify
parser behavior per Task 2/4 Step 1, since parser regexes can change between
releases), git, the target repo's existing docs layout.

---

## Fill in before starting

Replace these placeholders throughout — do not guess, derive each from the target repo:

| Placeholder | How to derive it |
|---|---|
| `{REPO}` | Repo name, e.g. `cc-videoreframing` |
| `{DOCS_DIR}` | The repo's synlynk `docs_dir` (check `.synlynk/config.json`'s `project_docs_dir`, default `project-docs`) |
| `{LEGACY_ROADMAP}` | Repo's pre-synlynk roadmap file, e.g. `docs/Roadmap.md` (may not exist — some repos have no roadmap doc) |
| `{LEGACY_BACKLOG}` | Repo's pre-synlynk backlog file, e.g. `docs/Backlog.md` (may not exist) |
| `{LEGACY_DEVLOG}` | Repo's pre-synlynk devlog file(s) — may be a single flat file, or already per-author |
| `{AUTHOR}` | git username for the devlog author, e.g. `git config user.name` |
| `{BRANCH}` | `chore/synlynk-adoption-migration` (keep this name unless the repo's branch-naming convention requires otherwise) |
| `{TAG}` | `pre-synlynk-migrate-{REPO}-YYYYMMDD` — **resolve this once with `git tag -l "pre-synlynk-migrate*"` after Task 0 and reuse the literal string everywhere below.** Never re-evaluate `$(date +%Y%m%d)` in a later task — if the plan spans a session/day boundary the reconstructed tag name won't match the one actually created. |

---

## Known current-state facts to gather before writing Task 2+ (do this first, don't assume)

Run this recon and write down the actual answers — every later task depends on them:

```bash
synlynk --version
grep -n "_migrate_import\|_parse_roadmap_md\|_parse_devlog_file" -A 5 \
  "$(python3 -c 'import synlynk, os; print(os.path.dirname(synlynk.__file__))')"/db.py 2>&1 | head -20
cat .synlynk/config.json 2>/dev/null | grep -i docs_dir
find {DOCS_DIR} -type f
git status --porcelain
synlynk doctor 2>&1
```

Confirm, in writing, before proceeding:
- Which of the five schema files already exist in `{DOCS_DIR}` in usable form vs. broken/stubbed vs. absent entirely (absent is fine — don't fabricate a `costs.md` if there's no legacy cost tracking; a missing schema file just means that import count will be 0, which is expected, not an error).
- Where each legacy equivalent actually lives, and whether its name/format already matches what the installed parser expects (read the parser functions directly — don't trust the CLI's `--help` text or any prior playbook's description of the format, since parser regexes can change between synlynk versions).
- Every narrative-content path (RCAs, plans, research, strategy, reports, brainstorm dirs) that must stay **outside** `{DOCS_DIR}` and untouched by migration.
- Exactly what `synlynk doctor` currently flags for this repo (missing SOP sections, missing role fences, etc.) — you'll address the SOP gaps in Task 7 and should not duplicate content that's already there under a different heading.
- Working-tree cleanliness — anything dirty or untracked that predates this work needs an explicit keep/revert/stash decision in Task 1, not silent inclusion in migration commits.

---

## Task 0: Pre-flight safety snapshot

**Files:** none modified — this is a pure git operation.

- [ ] **Step 1: Confirm current branch and create the working branch**

```bash
git branch --show-current
git checkout -b {BRANCH}
```

- [ ] **Step 2: Tag the pre-migration snapshot and resolve the literal tag name**

```bash
git tag pre-synlynk-migrate-{REPO}-$(date +%Y%m%d)
git tag -l "pre-synlynk-migrate*"
```
Copy the exact tag string this prints — that's `{TAG}` for every step below, used
literally, not re-evaluated.

- [ ] **Step 3: Push the tag now, not at the end**

```bash
git push origin {TAG}
```
**Lesson from cc-videoreframing:** the tag was created but not pushed until a
post-merge review caught it — until pushed, it's not a durable safety net; if the
local machine/checkout is lost, so is the rollback point. Push it here, immediately,
before any destructive step runs.

---

## Task 1: Working-tree triage

**Files:**
- Modify: `.gitignore`
- Decide: any pre-existing dirty/untracked state unrelated to this migration

- [ ] **Step 1: Inspect and resolve unrelated dirty state**

```bash
git status --porcelain
```
For anything unrelated to this migration: revert it (`git checkout --`) if incidental,
or stash it out (`git stash push -m "<reason>" -- <path>`) if intentional in-progress
work you don't want mixed into this branch's commits.

- [ ] **Step 2: Decide `.synlynk/` operational-state tracking policy**

Some subpaths under `.synlynk/` are per-job ephemera (regenerated, no value in git);
others are repo configuration (should be committed). Add the ephemera to
`.gitignore`, anchored to root-only unless you specifically intend to match nested
paths too:

```bash
cat >> .gitignore <<'EOF'

# synlynk operational state (ephemeral, regenerated per job)
/.synlynk/logs/
/.synlynk/contexts/
/.synlynk/jobs.json
/.synlynk/telemetry.json
/.synlynk/sentinel.md
/.synlynk/scan-meta.json
/.synlynk/prompts/
EOF
```

**⚠️ Lesson from cc-videoreframing (real bug, caught in review):** do **not** write
an unanchored `{DOCS_DIR}/` line here or in Task 8. An unanchored pattern like
`project-docs/` matches *any* path segment with that name — including
`.synlynk/project-docs/`, which is the backup copy `synlynk migrate` creates in Task 8
specifically to preserve pre-migration content. An unanchored rule silently untracks
that backup too, leaving the migrated content unrecoverable from git if local
`~/.synlynk` state is ever lost. Always anchor: `/{DOCS_DIR}/`, not `{DOCS_DIR}/`.
Verify with `git check-ignore -v .synlynk/{DOCS_DIR}/memory.md` — it must report
**not ignored**.

Do **not** gitignore `.synlynk/config.json`, `.synlynk/instructions.json`,
`.synlynk/model_rates.json`, or the generated agent instruction files
(`AGENTS.md`, `GEMINI.md`, `GROK.md`, `.github/copilot-instructions.md`, etc.) —
these are repo configuration, not per-job ephemera, and should be committed.

- [ ] **Step 3: Stage, verify, commit**

```bash
git add .gitignore AGENTS.md GEMINI.md GROK.md .github/copilot-instructions.md \
  .synlynk/config.json .synlynk/instructions.json .synlynk/model_rates.json
git status
```
Expected: only intended files staged; per-job ephemera no longer appears as untracked.

```bash
git commit -m "chore: track synlynk agent instruction files, ignore per-job operational state"
```

---

## Task 2: Fix/create `{DOCS_DIR}/roadmap.md` from `{LEGACY_ROADMAP}`

Skip this task entirely if the repo has no legacy roadmap doc — do not fabricate one.

**Files:**
- Modify: `{DOCS_DIR}/roadmap.md`
- Read: `{LEGACY_ROADMAP}`

- [ ] **Step 1: Confirm current state of the target file** (may be broken/stubbed/absent)

- [ ] **Step 2: Read the parser's actual expected format from the installed source**

```bash
grep -n "_parse_roadmap_md" -A 40 \
  "$(python3 -c 'import synlynk, os; print(os.path.dirname(synlynk.__file__))')"/db.py
```
Confirm what heading/status markup it expects for `roadmap_arcs` (version headers) and
`roadmap_phases` (phase headers with status/priority). Use what the function actually
parses — do not guess or reuse a format description from a different synlynk version.

- [ ] **Step 3: Rewrite, content-preserving**

Read `{LEGACY_ROADMAP}` in full, then write `{DOCS_DIR}/roadmap.md` with the same
substantive content reformatted to match Step 2's structure. Every phase/decision in
the legacy file must appear in the new one.

**⚠️ Lesson from cc-videoreframing (real fabrication, caught in spec review):** if the
legacy doc's actual priority scheme doesn't map cleanly onto whatever the parser
extracts (e.g. it extracts priority from literal `(P0)`/`(P1)` substrings but the
legacy doc uses emoji/heading severity instead), **do not invent priority tags to make
the reformat "look complete."** The parser will import fabricated tags as
indistinguishable-from-real database values — this is a data-integrity risk, not a
cosmetic one. Only include a priority tag where the legacy source actually states one.

**If you invent placeholder version numbers** (e.g. because the legacy doc has no
version scheme but the parser requires `## vX.Y` arc headers), **disclose this
explicitly in the file itself** — a bolded note stating the version numbers are
synthetic sequence identifiers for the parser's format requirement only, not real
releases. A structural-mirroring explanation alone is not sufficient disclosure; say
plainly that the numbers themselves are non-semantic.

- [ ] **Step 4: Verify via dry-run import count**

```bash
synlynk migrate --dry-run 2>&1 | grep -i roadmap
```
Non-zero counts matching the number of phases in the legacy doc. A non-empty source
that imports 0 rows should fail loudly — if it doesn't, treat that as suspicious and
double check the reformat actually matches the parser, not just visually similar to it.

- [ ] **Step 5: Commit**

---

## Task 3: Reconcile `{DOCS_DIR}/todo.md` with `{LEGACY_BACKLOG}`

Skip if no legacy backlog doc exists.

**Files:** Read: `{LEGACY_BACKLOG}`, `{DOCS_DIR}/todo.md`. Create: one
`synlynk story create` call per unmigrated backlog item.

- [ ] **Step 1: Diff what's already represented** — cross-reference existing story
stubs in `todo.md` against every item in the legacy backlog; list unrepresented items.

- [ ] **Step 2: Create a story per unrepresented item**

`todo.md`'s parser only syncs GH issue numbers onto *existing* stories — it does not
bulk-import backlog text. Check `synlynk story create --help` for the current valid
flags before writing calls — **do not assume flag values from a prior repo's
playbook**. In particular, verify the valid `--stage` values live-run
(`synlynk story create --help` or read the source's stage enum) rather than guessing
a value like `backlog` that may not be a recognized stage in this synlynk version.

```bash
synlynk story create --title "<exact backlog item title>" --engg <area> --stage <valid-stage>
```

For each item you deliberately skip (already deployed, superseded, deferred pending a
business trigger, etc.), record the skip reason precisely — don't characterize a
concretely-planned, deferred item as "speculative" just because it isn't being created
now.

- [ ] **Step 3: Verify** `todo.md` reflects the full backlog via `synlynk checkpoint`.

- [ ] **Step 4: Commit.**

---

## Task 4: Build `{DOCS_DIR}/devlogs/{AUTHOR}.md` from `{LEGACY_DEVLOG}`

Skip if no legacy devlog exists or it's already in the correct per-author format.

**Files:** Create: `{DOCS_DIR}/devlogs/{AUTHOR}.md`. Read: `{LEGACY_DEVLOG}`.

- [ ] **Step 1: Read the parser's expected per-entry format from installed source**

```bash
grep -n "_parse_devlog_file" -A 30 \
  "$(python3 -c 'import synlynk, os; print(os.path.dirname(synlynk.__file__))')"/db.py
```
Confirm the exact heading pattern for `entry_date` / `session_title` (commonly a
strict `## YYYY-MM-DD [— title]` heading — headings that don't conform, like date
ranges or narrative prefixes, need an explicit, disclosed derived date, not a silent
guess).

- [ ] **Step 2: Split the flat file, preserving every entry**

If any original heading doesn't conform to the required pattern, keep a disclosure
block in the new file listing exactly which entries were reformatted and what their
original heading text was — and make sure that disclosure's own claims are internally
consistent (right count, accurate description of what's verbatim vs. paraphrased).
**Lesson from cc-videoreframing:** a first-pass disclosure claimed "verbatim
preserved" for entries that only carried a paraphrased range description — if you
can't defend a claim like "preserved verbatim," point to the source-of-truth table
instead of asserting it in prose.

- [ ] **Step 3: Verify via dry-run import count** — `devlog_entries` count matches
the number of dated entries in the legacy file.

- [ ] **Step 4: Commit.**

---

## Task 5: Confirm `{DOCS_DIR}/memory.md` canonical source and flag stale pointers

**Files:** Read only — any CLAUDE.md/AGENTS.md pointer fix happens in Task 7.

- [ ] **Step 1:** Confirm `{DOCS_DIR}/memory.md` is real, current, non-stub content.

- [ ] **Step 2:** If the repo also has a root-level `MEMORY.md` or similar
architecture-reference doc, confirm it's a genuinely distinct document (code/module
map) rather than a duplicate of the session-log memory file — leave it untouched if so.

- [ ] **Step 3:** Note any stale external memory-path pointers in CLAUDE.md/AGENTS.md
for the Task 7 fix — don't fix them here.

---

## Task 6: Verify non-schema narrative content stays outside `{DOCS_DIR}`

**Files:** verification only, no changes.

- [ ] **Step 1: Re-list `{DOCS_DIR}` contents right before migrating**

```bash
find {DOCS_DIR} -type f
```
Expected: only the recognized schema files (some may legitimately be absent). If
anything else appears, stop and handle it explicitly before Task 8 runs
`git rm --cached -r {DOCS_DIR}`.

- [ ] **Step 2: Confirm every narrative-content path identified in recon is outside `{DOCS_DIR}`**

```bash
for p in <list every path from your recon>; do
  echo -n "$p: "; [ -e "$p" ] && echo "present, outside {DOCS_DIR}" || echo "MISSING — investigate"
done
```

---

## Task 7: Archive superseded legacy files and reconcile CLAUDE.md/AGENTS.md

**Files:**
- Move: `{LEGACY_ROADMAP}`, `{LEGACY_BACKLOG}`, `{LEGACY_DEVLOG}` → `docs/archive/pre-synlynk-migration/`
- Modify: `CLAUDE.md` (and any other agent instruction files with equivalent doc-maintenance sections)

- [ ] **Step 1: Archive with `git mv`** (preserves history, stays tracked — never `rm` + re-add)

```bash
mkdir -p docs/archive/pre-synlynk-migration
git mv {LEGACY_ROADMAP} docs/archive/pre-synlynk-migration/
git mv {LEGACY_BACKLOG} docs/archive/pre-synlynk-migration/
git mv {LEGACY_DEVLOG} docs/archive/pre-synlynk-migration/
```

- [ ] **Step 2: Update doc-maintenance sections, and add doctor's flagged SOP sections**

Before writing anything about synlynk's write convention (e.g. "writes go through
synlynk automatically, don't hand-edit" vs. "append directly, then run
`synlynk checkpoint`"), **verify the actual convention by reading synlynk's own
generated session-protocol instructions** (`synlynk/instructions.py` or equivalent in
the installed package) rather than assuming — the two conventions produce opposite
guidance and getting it backwards will mislead every future agent session.

⚠️ **Lesson from cc-videoreframing (confirmed, not hypothetical — see Lesson #9
below):** as of this writing, `synlynk checkpoint` does **not** re-import
`{DOCS_DIR}/memory.md` or `{DOCS_DIR}/devlogs/*.md` edits into `state.db` — it only
archives resolved `todo.md` lines and refreshes context. Do not write CLAUDE.md
wording that says hand-edits get "synced" by `checkpoint` (the original
cc-videoreframing plan did, and it was wrong). Correct wording: these files are a
one-time write-through snapshot from the last `migrate`, and post-migrate hand-edits
to them are local-only reference until synlynk#645 lands — they carry no automatic
durability guarantee. Check that issue's status before writing this section; if it's
closed, verify the fix actually re-syncs before reverting to the "checkpoint syncs"
wording.

For each SOP section `synlynk doctor` flags as missing: check whether equivalent
content already exists under a different heading before adding a new section wholesale
— point the new heading at the existing content rather than duplicating it. If a
required heading name overlaps with an existing organizational policy (e.g. a global
CLAUDE.md convention with a similarly-named section), make sure the new section's
*content* actually matches what that policy means — a matching heading with
mismatched content is worse than a missing section.

Double check the result doesn't self-contradict older sections of the same file — e.g.
don't mark a memory path "superseded, don't edit" in one section while another section
just below still instructs active writes to that same path.

- [ ] **Step 3: Verify `synlynk doctor` / `synlynk instructions status`** show the
SOP warnings resolved or reduced.

- [ ] **Step 4: Commit.**

---

## Task 8: Migrate — dry-run, verify, then real migrate

**Files:** `state.db` (created/written), `{DOCS_DIR}` (rewritten as write-through
mirror by `migrate`), `.gitignore` (migrate appends to it).

- [ ] **Step 1: Full dry-run, read completely**

```bash
synlynk migrate --dry-run 2>&1 | tee /tmp/synlynk-migrate-dryrun.txt
```
Confirm per-file counts match what was verified in Tasks 2–4. A 0 count for a schema
file with no legacy source is expected, not an error.

- [ ] **Step 2: Re-run Task 6's file-by-file check immediately before the real migrate**

- [ ] **Step 3: Pause here for explicit human authorization before running the real
(non-dry-run) `migrate`.** This is the one irreversible step in the whole plan —
present exactly what it will do (untrack `{DOCS_DIR}`, append to `.gitignore`, copy a
backup to `.synlynk/{DOCS_DIR}/`) and the safety nets already in place (pushed tag from
Task 0, unpushed branch) and wait for a clear go-ahead.

- [ ] **Step 4: Run the real migrate**

```bash
synlynk migrate 2>&1 | tee /tmp/synlynk-migrate-real.txt
```

- [ ] **Step 5: Immediately check what happened to git tracking**

```bash
git status
git diff --stat {TAG} -- .
cat .gitignore | tail -5
```
Confirm nothing outside `{DOCS_DIR}` changed except `CLAUDE.md`, `.gitignore`, and the
Task 7 archived files.

**Immediately also check the backup copy is actually trackable, not swallowed:**
```bash
git check-ignore -v .synlynk/{DOCS_DIR}/memory.md   # must report NOT ignored
find .synlynk/{DOCS_DIR} -type f
git add .synlynk/{DOCS_DIR}
git commit -m "fix: track migrate's backup copy of {DOCS_DIR} as git-recoverable"
```
If this reports the backup as ignored, re-check Task 1's anchoring — the whole point
of this step is that pre-migration content stays recoverable from git even if local
`~/.synlynk` state and the pushed tag are both somehow unavailable.

---

## Task 9: Post-migration verification

**Files:** verification only.

- [ ] **Step 1: Confirm the tag still resolves and diff against it**

```bash
git show {TAG}:CLAUDE.md > /tmp/claude-before.md
diff /tmp/claude-before.md CLAUDE.md
```
Expected: only the intentional Task 7 edits — nothing unintended.

- [ ] **Step 2: Confirm every narrative-content path from Task 6 is untouched**

```bash
for p in <same list as Task 6 Step 2> docs/archive/pre-synlynk-migration; do
  git diff {TAG} -- "$p" | head -5
done
```
No output for any path except the archive dir, which should show the archived files
present with history preserved (`git log --follow docs/archive/pre-synlynk-migration/<file>`).

- [ ] **Step 3: Spot-check regeneration**

```bash
synlynk checkpoint 2>&1 | tail -20
cat {DOCS_DIR}/todo.md | head -10
cat {DOCS_DIR}/roadmap.md | head -10
```
Both should regenerate real content sourced from `state.db`, not stale stub content.

- [ ] **Step 4: Final doctor pass** — no `git rm --cached` or destructive warnings; SOP
warnings resolved or reduced per Task 7. (Unrelated pre-existing warnings — e.g. a
local dev-server network check, a role-fence gap on an agent file this plan didn't
touch — are fine to leave as separate follow-up items, not blockers for this plan.)

---

## Task 10: Report and stop — get explicit approval before pushing

- [ ] **Step 1:** Summarize for the human: import counts, files archived (with
`git log --follow` confirmation), CLAUDE.md diff confirmation, narrative-path
untouched confirmation, tag pushed confirmation.

- [ ] **Step 2:** Do **not** push or open a PR without explicit approval — per
standard git-workflow discipline, no branch goes to `origin` without a checkpoint.

---

## Task 11: Before merging — rebase/merge against `main` explicitly, don't assume a clean fast-forward

Multi-task migrations like this one can take long enough in wall-clock time that
`main` moves during execution — especially if legacy docs this plan renames
(`{LEGACY_ROADMAP}`, `{LEGACY_BACKLOG}`, `{LEGACY_DEVLOG}`) are still being actively
edited by other work landing on `main` in parallel.

- [ ] **Step 1:** Before merging, check `git log origin/{BRANCH}..origin/main
--oneline`. If non-empty, do not merge blind — inspect whether any of those commits
touch the files this plan renamed.

- [ ] **Step 2:** If they do, merge `main` into the branch locally first
(`git merge origin/main --no-commit --no-ff`) and **explicitly verify** — don't just
trust a clean auto-merge — that git's rename detection correctly folded the new
content from `main` into the archived path, rather than silently discarding it. Diff
the tail of the archived file against `main`'s version of the original path to confirm
the new content actually landed:
```bash
git show origin/main:{LEGACY_ROADMAP} | tail -30 > /tmp/main-tail.txt
tail -30 docs/archive/pre-synlynk-migration/<archived-name> > /tmp/ours-tail.txt
diff /tmp/main-tail.txt /tmp/ours-tail.txt
```

- [ ] **Step 3:** Check the repo's actual allowed merge method before running
`gh pr merge` — `gh api repos/{owner}/{repo} --jq '{squash: .allow_squash_merge, merge:
.allow_merge_commit, rebase: .allow_rebase_merge}'`. Don't assume merge-commit is
allowed; many repos are squash-only and the merge command will fail if you guess wrong.

---

## Lessons baked into this version (from the `cc-videoreframing` execution)

These were all real findings, not hypothetical risks — keep this list updated as the
playbook gets reused on more repos:

1. **Fabricated priority tags**: an implementer subagent invented `(P0)` tags not
   present in the source doc to "complete" a reformat where the parser extracts
   priority from literal substrings. Caught only because a spec-compliance reviewer
   diffed content line-by-line instead of trusting the report. → Task 2 Step 3.
2. **Unanchored gitignore rule swallowing the migrate backup**: `project-docs/`
   (unanchored) matched `.synlynk/project-docs/` too, silently untracking the one
   local recovery copy `migrate` creates. Caught by an independent PR review, not by
   the original two-stage review cycle — the original reviewers weren't specifically
   looking for this. → Task 1 Step 2, Task 8 Step 5.
3. **Rollback tag created but never pushed**: existed only locally until a later
   review pass caught it — not a durable safety net until pushed. → Task 0 Step 3.
4. **Self-contradictory CLAUDE.md edits**: new "superseded, don't hand-edit" wording
   for a legacy path directly contradicted active-write instructions for that same
   path a few sections below. → Task 7 Step 2.
5. **Heading-name collision with an org-wide policy**: a new required SOP section's
   name matched an existing global policy's section name closely enough that
   `synlynk doctor` was almost certainly checking for the real policy's content — but
   the section written didn't actually reference it. → Task 7 Step 2.
6. **Review-agent GitHub connector failures**: a dispatched review agent (Codex) twice
   had its review/comment submission cancelled by the GitHub MCP connector and could
   only report findings in its job log, not on the PR — the findings were still valid
   and had to be relayed manually. Don't assume "job completed OK" means "review
   landed on the PR" — check the actual PR for the comment/review before treating a
   dispatch as done.
7. **`main` moved during a multi-day migration**: 4 unrelated commits landed on
   `main`, including one editing the exact legacy files this plan renamed. Git's
   rename-aware merge handled it correctly, but that had to be explicitly verified by
   diffing tails, not assumed. → Task 11.
8. **Assumed merge-commit was allowed**: `gh pr merge --merge` failed because the repo
   only allows squash merges — wasted a round trip that a one-line `gh api` check
   would have avoided. → Task 11 Step 3.
9. **`synlynk checkpoint` does not sync `{DOCS_DIR}` file edits back into `state.db`**:
   confirmed by reading the installed package source (`checkpoint()` only archives
   `todo.md`'s `[x]` lines into the devlog *file* and refreshes context; the only
   writers of `memory_entries`/`devlog_entries` anywhere in the codebase are inside
   `migrate()` itself). Post-migration hand-edits to `{DOCS_DIR}/memory.md` and
   `{DOCS_DIR}/devlogs/*.md` are real but **local-only and one-way** — they never make
   it back into the DB of record, and the gitignored files carry no durability
   guarantee beyond the machine they were written on. Filed as
   [synlynk#645](https://github.com/nikhilsoman/synlynk/issues/645); until that's
   fixed, do not write CLAUDE.md wording implying `checkpoint` "syncs" these files —
   see Task 7 Step 2.
