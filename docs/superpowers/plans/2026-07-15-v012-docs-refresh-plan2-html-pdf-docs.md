# v0.12.0 Docs Refresh — Plan 2: Canonical HTML/PDF Doc Bundles Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the 3 hand-authored, self-contained HTML doc bundles (Quick Start Guide, Command Reference, Official Reference) current with the v0.12.0 CLI surface, re-export each to PDF, and retire the leftover variant files that have no ongoing purpose.

**Architecture:** These are standalone styled HTML files (952/1186/1567 lines each) with inline CSS and no build pipeline — edits are direct HTML edits, PDFs are produced by hand via browser print-to-PDF. Each file carries its own in-file `MAINTENANCE` comment (visible via `grep -n MAINTENANCE docs/*.html`) specifying exactly what must be updated per release.

**Tech Stack:** Hand-authored HTML/CSS. PDF export via browser print dialog (Chrome/Safari "Save as PDF") — no CLI tool for this step.

---

This plan is one of 4 independent, parallel-dispatchable plans derived from `docs/superpowers/specs/2026-07-15-v0.12.0-docs-onboarding-refresh-design.md`. It touches only `docs/synlynk-*.html`, `docs/synlynk-*.pdf`, and the 4 retired variant files — disjoint from the other 3 plans' files (README.md / website/* / docs/blog/*.md).

**Verified before this plan was written:** no other tracked file (`README.md`, `website/src/docs.njk`, or any `.njk` under `website/src/`) links to the 4 files being retired in Task 4 — confirmed via `grep -rn "quickstart-apple|quickstart-compact|synlynk_quick_start" README.md website/src/*.njk`, zero hits. So Task 4's deletions need no link-fixup elsewhere.

### Task 1: Update `docs/synlynk-quickstart-guide.html`

**Files:**
- Modify: `docs/synlynk-quickstart-guide.html`

Per its own `MAINTENANCE` comment (line 11): "Quick Start Guide: update version tag only unless UX flow changed." The agent count changed (3→4, adding grok since v0.9.4), which is a UX-flow-relevant fact shown on the cover — so this pass touches the version tag AND the agent-count pill.

**Scope note:** the `local` (on-device oMLX) agent has shipped in code but is intentionally **excluded** from every doc surface in this pass — it's being trialed before a public announcement. Do not reference it anywhere in any of the 3 HTML files, and do not count it in any "N agents" figure below (roster shown throughout this task is claude/codex/agy/grok = 4, not 5).

- [ ] **Step 1: Read current state of every location the version string `v0.9.4` / `0.9.4` appears**

Run: `grep -n "0.9.4\|3 Agents" docs/synlynk-quickstart-guide.html`

Expected hits (verify against actual output, adapt line numbers if the file has drifted):
- Line 6: `<title>Synlynk Quick Start Guide — v0.9.4</title>`
- Line 12: `Last updated: v0.9.4 (2026-06-24)` (inside the MAINTENANCE comment block)
- Line 578: `<div class="cover-version">v0.9.4 · SQLite Canon · Agent Profiles · Relay</div>`
- Line 583: `<div>...synlynk 0.9.4 installed to ~/.synlynk/bin</div>`
- Line 591: `<div>🤖 3 Agents</div>` (cover-pill)
- Line 631: `<div>...synlynk 0.9.4 ready</div>`
- Line 945: footer `... v0.9.4 · synlynk.com`

- [ ] **Step 2: Apply these exact replacements** (use each surrounding line's existing HTML structure/classes — only change the text content, not the markup):

| Location | Old | New |
|---|---|---|
| `<title>` | `Synlynk Quick Start Guide — v0.9.4` | `Synlynk Quick Start Guide — v0.12.0` |
| MAINTENANCE comment | `Last updated: v0.9.4 (2026-06-24)` | `Last updated: v0.12.0 (2026-07-15)` |
| `.cover-version` | `v0.9.4 · SQLite Canon · Agent Profiles · Relay` | `v0.12.0 · Measurement & Reliability` |
| terminal mock (cover) | `synlynk 0.9.4 installed to ~/.synlynk/bin` | `synlynk 0.12.0 installed to ~/.synlynk/bin` |
| `.cover-pill` | `🤖 3 Agents` | `🤖 4 Agents` |
| terminal mock (body) | `synlynk 0.9.4 ready` | `synlynk 0.12.0 ready` |
| footer | `v0.9.4 · synlynk.com` | `v0.12.0 · synlynk.com` |

- [ ] **Step 3: Check for any body content referencing "3 agents" or listing agent names**

Run: `grep -n -i "codex\|claude\|agy\|grok\|local agent\|three agents\|agent.*profile" docs/synlynk-quickstart-guide.html`

If the flow text anywhere enumerates the agent roster (e.g., "Claude, Codex, and AGY"), extend it to mention Claude, Codex, Agy, and Grok — **do not include `local`** (out of scope for this release per the scope note above) — read the surrounding paragraph first with `sed -n 'N-3,N+3p' docs/synlynk-quickstart-guide.html` to match its exact tone/structure before editing. If no such enumeration exists beyond the cover pill already fixed in Step 2, no further change needed — this file's mandate is version-tag-only per its own MAINTENANCE comment, don't add new sections.

- [ ] **Step 4: Commit the HTML change**

```bash
git add docs/synlynk-quickstart-guide.html
git commit -m "docs: update Quick Start Guide to v0.12.0 (5-agent roster)"
```

- [ ] **Step 5: Re-export to PDF**

Open `docs/synlynk-quickstart-guide.html` in a browser (`open docs/synlynk-quickstart-guide.html` on macOS), use File → Print → Save as PDF, and overwrite `docs/synlynk-quickstart-guide.pdf` in place. Confirm the new PDF's file size differs from its prior committed size (proof of a real re-export, not a stale copy):

```bash
git show HEAD~1:docs/synlynk-quickstart-guide.pdf | wc -c
wc -c docs/synlynk-quickstart-guide.pdf
```
The two byte counts should differ (even a small diff from the changed version-tag text is enough — an exact match means the export didn't actually happen).

- [ ] **Step 6: Commit the PDF**

```bash
git add docs/synlynk-quickstart-guide.pdf
git commit -m "docs: re-export Quick Start Guide PDF for v0.12.0"
```

### Task 2: Update `docs/synlynk-command-reference.html`

**Files:**
- Modify: `docs/synlynk-command-reference.html`

Per its own `MAINTENANCE` comment: "Command Reference: update commands section for any new/changed commands." This is a full command sync against the spine in `docs/superpowers/specs/2026-07-15-v0.12.0-docs-onboarding-refresh-design.md`.

- [ ] **Step 1: Read the full current commands section**

Run: `grep -n 'class="sec-label"\|class="sec"\|ctbl' docs/synlynk-command-reference.html` to find every table section, then read each with `sed -n 'START,ENDp' docs/synlynk-command-reference.html` to see its full row set before editing.

- [ ] **Step 2: Cross-check every command against `synlynk/cli.py`**

Run: `grep -n 'add_parser(' synlynk/cli.py` and read each `help="..."` string (some span multiple lines — use `sed -n 'N,N+5p' synlynk/cli.py`). This is the source of truth for exact command names, flags, and descriptions.

- [ ] **Step 3: Update the version tag and cover** (same locations/pattern as Task 1 Step 1-2, applied to this file):

Run: `grep -n "0.9.4" docs/synlynk-command-reference.html` and update `<title>`, MAINTENANCE comment date, `.cover-version` (`v0.9.4 · Complete CLI Reference` → `v0.12.0 · Complete CLI Reference`), and footer (`v0.9.4 · synlynk.com` → `v0.12.0 · synlynk.com`).

- [ ] **Step 4: Add missing commands to their matching existing table sections, or a new section if no existing section fits**

Based on the current sections seen in Step 1 (Core, Dispatch/Jobs/Daemon, Relay/Team/Stories/Identity, and others further in the file — read the full file to find all sections via the `sec-label`/`sec` grep from Step 1), add rows for every v0.11.0/v0.12.0-era command missing from the file. At minimum, based on the spine, these are very likely absent and need adding (verify each against Step 1's actual current content before assuming — the file may already have some):

- `synlynk schedule [--execute] [--max-stories N]` — under Team/Stories section, tag `v0.12.0`
- `synlynk cost log` — under a Cost/Ledger section or alongside `status`, tag `v0.12.0`
- `synlynk goal create|list|link|status` — under Team/Stories section
- `synlynk pr check` — under a PR/CI section
- `synlynk instructions status|diff|update|ack`
- `synlynk roles [--fix]`
- `synlynk viz [--serve|--generate|--open|--stop|--port]` — tag `v0.11.0` or `v0.12.0` per actual first-shipped version (check `CHANGELOG.md` for when Vizor first shipped: `grep -n "viz\b" CHANGELOG.md | head -5`)
- `synlynk release [--dry-run] [--version] [--minor]`
- `synlynk doctor`, `synlynk probe`
- `synlynk repair`, `synlynk sync`, `synlynk exit`
- `synlynk jobs handoff <job-id> <agent>`

Use the file's existing `<table class="ctbl"><thead>...</thead><tbody><tr><td>...</td><td>...</td></tr></tbody></table>` structure and the `<span class="tag tg-new" style="vertical-align:middle;">vX.Y.Z</span>` version-tag convention already used throughout the file (see the existing `daemon start|stop|status` row for the exact pattern to copy). Determine each command's actual first-shipped version via `grep -n "<command-name>" CHANGELOG.md` rather than guessing.

- [ ] **Step 5: Cross-check `--agents claude,agy,codex` mentions for the grok agent**

Run: `grep -n "claude,agy,codex\|3 agents\|three agents" docs/synlynk-command-reference.html`. If found, update the flag example to include the full current roster where accurate (init's `--agents` flag per `README.md`'s existing documentation only supports `claude,agy,codex` for instruction-file generation — verify current accepted values via `grep -n "agents.*claude\|choices=" synlynk/cli.py | grep -i agent` before changing; do not add agents to this flag's example unless they're actually accepted). **Do not add `local` to this flag's example** — out of scope for this release per the scope note above.

- [ ] **Step 6: Self-verify — grep every command name in the updated file against `cli.py`**

Run:
```bash
grep -oE '>[a-z][a-z-]* ' docs/synlynk-command-reference.html | tr -d '>' | sort -u
```
This is a rough extraction (HTML table cells aren't as clean to grep as markdown) — manually cross-reference the command names visible in each `<td>` against `grep -n '"<name>"' synlynk/cli.py` for each one. Fix any orphan before committing.

- [ ] **Step 7: Commit the HTML change**

```bash
git add docs/synlynk-command-reference.html
git commit -m "docs: sync Command Reference with v0.12.0 CLI surface"
```

- [ ] **Step 8: Re-export to PDF and verify size changed**

```bash
open docs/synlynk-command-reference.html
# File → Print → Save as PDF, overwrite docs/synlynk-command-reference.pdf
git show HEAD~1:docs/synlynk-command-reference.pdf | wc -c
wc -c docs/synlynk-command-reference.pdf
```

- [ ] **Step 9: Commit the PDF**

```bash
git add docs/synlynk-command-reference.pdf
git commit -m "docs: re-export Command Reference PDF for v0.12.0"
```

### Task 3: Update `docs/synlynk-official-reference.html`

**Files:**
- Modify: `docs/synlynk-official-reference.html`

Per its own `MAINTENANCE` comment: "Official Reference: update version tag, add features page, update changelog + commands + comparison matrix." This is the most involved of the 3 files — it has a dedicated "What's New" features chapter, a changelog chapter, a commands appendix table, and a comparison matrix, all of which need updates.

- [ ] **Step 1: Update version tag and cover** (same pattern as Tasks 1-2)

Run: `grep -n "0.9.4" docs/synlynk-official-reference.html` and update every occurrence: `<title>`, MAINTENANCE comment date, `.cover-version` (`v0.9.4 · SQLite Canon · Agent Profiles · Relay` → `v0.12.0 · Measurement & Reliability`), terminal mocks (`synlynk 0.9.4 installed` / `synlynk 0.9.4 ready` → `0.12.0`).

- [ ] **Step 2: Add a new "What's New" chapter page for v0.12.0**

Run: `sed -n '1260,1300p' docs/synlynk-official-reference.html` to see the existing v0.9.4 features chapter structure (starts around line 1263 with `<!-- PAGE 10 — v0.9.4 FEATURES (NEW) -->`, a `.ph-title` "Chapter 09 — What's New in v0.9.4", a `.sec-label`, and body paragraphs).

Insert a new chapter page immediately before that v0.9.4 chapter (i.e., before the `<!-- PAGE 10 — v0.9.4 FEATURES (NEW) -->` comment), following the exact same `<div class="page">` / `.page-header` / `.ph-title` / `.sec-label` / body-paragraph structure, but content for v0.12.0. Renumber the `.ph-num` and subsequent chapter numbers by +1 if the file uses sequential page numbers (check by reading a few chapters forward to see if `.ph-num` values need shifting — if they're per-page literal numbers rather than auto-generated, this requires manually incrementing every subsequent page's `.ph-num` by 1, which is tedious but necessary for internal consistency; grep first: `grep -n 'class="ph-num"' docs/synlynk-official-reference.html` to see the full sequence before deciding whether renumbering is needed).

Content for the new chapter (adapt exact HTML tag structure from the v0.9.4 chapter you read in this step — do not invent new CSS classes):

```
Chapter title: "What's New in v0.12.0"
Section label: "v0.12.0 · Measurement & Reliability"
Body: "v0.12.0 makes the agent fleet trustworthy: dispatched jobs finish their own git steps instead of leaving commits unfinished, story routing becomes a real 3-stage scoring engine (capability, quota headroom, cost tie-break) with a fleet batch scheduler to clear backlogs unattended, and every cost figure synlynk reports is now either structurally measured or visibly flagged as an estimate."
```

- [ ] **Step 3: Update the Changelog chapter**

Run: `sed -n '1345,1365p' docs/synlynk-official-reference.html` to see the exact `.cl-row` / `.cl-ver` / `.cl-body` structure used for each changelog entry (see the existing rows for v0.9.4 down to v0.4.x).

Prepend new `.cl-row` entries above the existing `v0.9.4` row, one per named release since v0.9.4, using `CHANGELOG.md` as the source (`grep -n "^## \[" CHANGELOG.md` to list every version header, then read each section's `### Added` bullets to write a one-sentence summary in this file's existing tone). At minimum add rows for: v0.10.0, v0.11.0, v0.12.0. Use the existing color convention (`var(--green)` for the 3 most recent, `var(--blue)` older, `var(--purple)` oldest — read enough of the existing rows to infer the color-recency pattern before applying it to new rows).

Example row to prepend (adapt wording from actual `CHANGELOG.md [0.12.0]` content — do not use this verbatim if it doesn't match):

```html
<div class="cl-row"><div class="cl-ver" style="color:var(--green);">v0.12.0</div><div class="cl-body"><strong>Dispatched jobs now finish their own git steps</strong> — commit, push, and PR happen automatically once work is verified complete. Story routing gets real capability + quota + cost scoring, plus a fleet batch scheduler. Every cost number is now measured or flagged as an estimate.</div></div>
```

- [ ] **Step 4: Update the Commands appendix table**

Run: `sed -n '1390,1470p' docs/synlynk-official-reference.html` to see the full current appendix table structure (multiple `<table class="ctbl">` sections by category, same pattern as Task 2's Command Reference file but condensed).

Add the same set of missing commands identified in Task 2 Step 4 (schedule, cost log, goal, pr check, instructions, roles, viz, release, doctor, probe, repair, sync, exit, jobs handoff — excluding `local doctor`, out of scope for this release) to their matching category tables here, using this file's existing `<tr><td>command</td><td>description <span class="tag tg-new" ...>vX.Y.Z</span></td></tr>` pattern. Keep descriptions terser than the Command Reference file's — this appendix is already condensed (compare row lengths in the existing content to match tone).

- [ ] **Step 5: Update the comparison matrix**

Run: `sed -n '1455,1470p' docs/synlynk-official-reference.html` to see the existing comparison matrix rows (feature name / version introduced / before / after columns).

Add 1-2 new rows for the most marketable v0.12.0 capabilities, matching the existing `<tr><td>...</td><td>vX.Y.Z</td><td><span class="fx">✗</span> ...</td><td><span class="fc">✓</span> ...</td></tr>` structure:

```html
<tr><td>Dispatch git-finalization</td><td>v0.12.0</td><td><span class="fx">✗</span> Agent must remember to commit/push/PR</td><td><span class="fc">✓</span> synlynk finishes it automatically</td></tr>
<tr><td>Cost provenance</td><td>v0.12.0</td><td><span class="fx">✗</span> Hardcoded per-token estimates</td><td><span class="fc">✓</span> Structurally sourced or visibly flagged</td></tr>
```

- [ ] **Step 6: Self-verify — grep every command name added in this task against `cli.py`**

Same method as Task 2 Step 6 — cross-reference every new `<td>` command cell against `synlynk/cli.py`'s `add_parser` calls. Fix any orphan before committing.

- [ ] **Step 7: Commit the HTML change**

```bash
git add docs/synlynk-official-reference.html
git commit -m "docs: update Official Reference (features, changelog, commands, matrix) for v0.12.0"
```

- [ ] **Step 8: Re-export to PDF and verify size changed**

```bash
open docs/synlynk-official-reference.html
# File → Print → Save as PDF, overwrite docs/synlynk-official-reference.pdf
git show HEAD~1:docs/synlynk-official-reference.pdf | wc -c
wc -c docs/synlynk-official-reference.pdf
```

- [ ] **Step 9: Commit the PDF**

```bash
git add docs/synlynk-official-reference.pdf
git commit -m "docs: re-export Official Reference PDF for v0.12.0"
```

### Task 4: Retire leftover variant files

**Files:**
- Delete: `docs/synlynk-quickstart-apple.html`
- Delete: `docs/synlynk-quickstart-apple.pdf`
- Delete: `docs/synlynk-quickstart-compact.pdf`
- Delete: `synlynk_quick_start.pdf` (repo root)

Already verified (see plan header) that no tracked file links to any of these 4 — no link-fixup needed.

- [ ] **Step 1: Confirm no other references exist right before deleting** (defense-in-depth re-check, since other tasks in this plan may have added new content in parallel)

```bash
grep -rln "quickstart-apple\|quickstart-compact\|synlynk_quick_start" --include="*.md" --include="*.html" --include="*.njk" . 2>/dev/null | grep -v node_modules
```
Expected: no output (or only the 4 files themselves, which is fine since they reference their own filenames in no meaningful way). If any other file has a real reference, stop and fix that reference before deleting — do not delete a file something else still points to.

- [ ] **Step 2: Delete and commit**

```bash
git rm docs/synlynk-quickstart-apple.html docs/synlynk-quickstart-apple.pdf docs/synlynk-quickstart-compact.pdf synlynk_quick_start.pdf
git commit -m "docs: retire quickstart HTML/PDF variants, keep 3 canonical doc bundles"
```

### Task 5: Final cross-file verification

- [ ] **Step 1: Confirm exactly 3 canonical HTML files and 3 canonical PDFs remain in `docs/`**

```bash
ls docs/*.html docs/*.pdf
```
Expected output: exactly `docs/synlynk-command-reference.html`, `docs/synlynk-command-reference.pdf`, `docs/synlynk-official-reference.html`, `docs/synlynk-official-reference.pdf`, `docs/synlynk-quickstart-guide.html`, `docs/synlynk-quickstart-guide.pdf` — 6 files, no variants.

- [ ] **Step 2: Confirm all 3 PDFs' byte sizes differ from their pre-plan committed versions**

```bash
for f in synlynk-quickstart-guide synlynk-command-reference synlynk-official-reference; do
  echo "$f: $(git log --oneline -- docs/$f.pdf | wc -l) commits touching this PDF in this branch"
done
```
Each should show at least 1 commit from this plan's work (Tasks 1/2/3's PDF-commit steps).

- [ ] **Step 3: Confirm version string `v0.9.4` no longer appears anywhere in the 3 HTML files** (except inside historical changelog rows, which correctly retain old version numbers as history)

```bash
grep -n "v0.9.4\|0\.9\.4" docs/synlynk-quickstart-guide.html docs/synlynk-command-reference.html docs/synlynk-official-reference.html
```
Every remaining hit should be inside a `.cl-row` changelog entry (historical record, correct to keep) — not in a title, cover, MAINTENANCE comment, or footer. If any non-changelog hit remains, fix it.
