# "The Supervised Machine" — Part III "Field Notebook" Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **This plan's tasks are content-authorship dispatches, not code tasks — each "implementer" step is either a `synlynk dispatch` call to a specific harness, or a Claude-direct step explicitly marked as such (chapter authorship for Claude's own byline, or structural/merge work), not inline code by whoever executes this plan.**

**Goal:** Rename the existing "Part Three — Fleet Notebook" (old engineering-memoir framing, Chapters Eleven–Thirteen: rxcc, cc-videoreframing, Playblazer) to "Part III — Field Notebook" per the design doc's naming, relabel its three existing chapters into the new Part's own numbering, add two new chapters — Grok's infra-evidence chapter and Claude's own bylined "reviewer, not implementer" chapter — and have Codex add a cross-cutting fact-check/rigor annotation layer across all five Part III chapters. Then rebuild the PDF and bump the manuscript to v0.5-DRAFT.

**Architecture:** One `synlynk dispatch` call to Grok for the new infra-evidence chapter (worktrees, cost ledgers, sentinel patterns, LIVE-issue handling), one Claude-direct authorship step for Claude's own bylined chapter (precedent: Part I's Claude-led "Why This Is a Cognitive Tool, Not Magic" chapter was written the same way — a content-authorship carve-out from this project's general code-implementation delegation rule, not an exception to it), one `synlynk dispatch` call to Codex for the fact-check annotation pass across all five chapters, then a Claude-direct merge pass that retitles the Part, relabels the three existing chapters, inserts both new chapters in place, inserts Codex's annotations, updates the TOC and preface, verifies HTML validity, rebuilds the PDF, and bumps the version. Part IV (blocked on Nikhil's still-unprovided long-form voice sample, per the design doc's Open Items) and any restructuring of old Parts One, Two, or Four are explicitly **out of scope** — this plan only touches old Part Three / new Part III.

**Tech Stack:** Single-file self-contained HTML manuscript (inline CSS, no build step), Google Chrome headless for PDF rendering, `synlynk dispatch` for content authorship, `git`/`gh` for branch and PR flow.

---

## Current Manuscript State (grounded 2026-09-02, HEAD `d18add79`, v0.4-DRAFT merged via PR #1292)

`docs/book/the-supervised-machine-v0.4-DRAFT.html` is 933 lines. Confirmed structure via
`grep -n '<h1\|<h2 class="chap-title"\|part-label\|toc-part\|<div class="part-divider">\|</chapter>\|Preface to Draft'`:

- Line 121: `<h2>Preface to Draft v0.4</h2>` — its third `<p>` (line 140 area) currently reads:
  *"Part III (Field Notebook) and Part IV (What This Means) are not yet drafted under the
  new model — this draft's existing Parts One through Four remain in their prior
  engineering-memoir framing until that restructuring work lands in a future version; Part
  IV is additionally blocked on a long-form writing-voice sample from Nikhil, per the
  design doc's Open Items."* This sentence must be rewritten by this plan (Task 5) — it
  will be false about Part III once this plan lands.
- Line 178: `<div class="toc-part">Part One — The Eras of Software</div>` — TOC entry for the
  old-framing Part Three currently reads `<div class="toc-part">Part Three — Fleet
  Notebook</div>` at line 190. Must become `Part III — Field Notebook` (Task 5).
- Line 662: `<div class="part-divider">` opening old "Part Three — Fleet Notebook":
  ```html
  <div class="part-divider">
    <div class="part-label">Part Three</div>
    <h1>Fleet Notebook</h1>
    <div class="part-sub">synlynk in the wild — three sister projects, three different reasons the fleet gets dispatched</div>
  </div>
  ```
- Line 669: `<div class="chap-label">Chapter Eleven</div>` — rxcc chapter, closes `</chapter>`
  at line 712.
- Line 715: `<div class="chap-label">Chapter Twelve</div>` — cc-videoreframing chapter,
  closes at line 758.
- Line 761: `<div class="chap-label">Chapter Thirteen</div>` — Playblazer chapter, closes at
  line 784.
- Line 786: `<div class="part-divider">` opens "Part Four — Layers, Dynamics, and What Comes
  Next" (old global chapter numbering continues at "Chapter Fourteen", line 793) — **this
  Part and its chapter numbering are not touched by this plan.**

Re-confirm every line number above with a fresh `grep -n` before editing — this plan's own
tasks (rename, relabel, insert) will shift line numbers as they execute in sequence.

**Chapter-label numbering decision for this plan:** Part I already established the pattern
`Part I, Chapter One` / `Part I, Chapter Two` / `Part I, Chapter Three` for a multi-chapter
new-framing Part (see line 250, 273, 298 in the current file). This plan applies the same
pattern to Part III, replacing the three existing chapters' old *global* labels (`Chapter
Eleven` / `Chapter Twelve` / `Chapter Thirteen`, numbered continuously across old Parts
One–Four) with `Part III, Chapter One` / `Part III, Chapter Two` / `Part III, Chapter
Three`, and continuing with `Part III, Chapter Four` (Grok, new) and `Part III, Chapter
Five` (Claude, new). This is a deliberate, in-scope relabeling of exactly these five
chap-labels — no other chapter's label anywhere else in the manuscript changes.

**Relevant existing CSS classes (already defined in the `<style>` block, do not redefine):**

```css
.who { font-weight: 700; }
.who.human { color: #2a5; }
.who.claude { color: #a52; }
.who.codex { color: #25a; }
.who.grok { color: #a25; }
.who.agy { color: #5a2; }
.callout { background: #f4f2ee; border: 1px solid #ddd; border-radius: 4px; padding: 0.9em 1.1em; margin: 1.2em 0; }
.callout-label { font-size: 9pt; letter-spacing: 0.12em; text-transform: uppercase; color: #886; font-weight: 700; margin-bottom: 0.5em; }
```

Chapter wrapper pattern (reuse exactly — from the existing Part Three chapters, e.g. lines
669–712):

```html
<chapter>
<div class="chap-label">[Part III, Chapter N]</div>
<h2 class="chap-title">[Title]</h2>
<div class="chap-dek">[one-line dek]</div>
<p>...</p>
</chapter>
```

**Marginalia hard rule (design doc Section 3), same pattern used in every merged chapter so
far:**

```html
<div class="callout">
<div class="callout-label">Marginalia — [Author]</div>
<p>[Must either contradict the lead author's adjacent paragraph, or cite a specific
issue/LIVE-N/PR number. No purely reactive/color-commentary text.]</p>
</div>
```

**Codex's cross-cutting fact-check layer (new pattern for this plan — Part III is the first
place in the manuscript where Codex annotates across an entire Part rather than
contributing one named subsection in one chapter).** Use a `.callout` variant with a
distinct label, styled to read as a rigor/fact-check pass rather than a marginalia
reaction:

```html
<div class="callout" style="background:#eef4ee;">
<div class="callout-label">Fact-Check — Codex</div>
<p>[Codex's own prose, 60-150 words, verifying or correcting one specific claim in the
adjacent paragraph against real repo evidence — a confirmation with the exact citation, a
correction with the exact discrepancy, or an explicit "unverifiable as stated" flag. Not a
reaction, not color commentary.]</p>
</div>
```

---

## Task 1: Dispatch Grok — new chapter ("Part III, Chapter Four": infra evidence)

**Files:**
- Create (via dispatch): `docs/book/fragments/part3-grok-infra-evidence.html`

- [ ] **Step 1: Dispatch the chapter draft to Grok**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch grok \
  --force-agent \
  --context-mode full \
  --grant "run:shell" \
  --task "$(cat <<'PROMPT'
Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.4-DRAFT.html. This is a new chapter
within Part III ("Field Notebook") of a repositioned nonfiction book ("The
Supervised Machine") about human-AI collaboration for a general audience.
You are the bylined lead author of this chapter, writing in your own voice
as established in this manuscript's existing .who.grok dialogue lines and
your own Part 0 and Part I chapters ("Panic as a User-Interface Bug", "Power
Tools Have Kickback" — read them first via
`grep -n 'Panic as a User-Interface Bug\|Power Tools Have Kickback' docs/book/the-supervised-machine-v0.4-DRAFT.html`
for tone/length/density reference).

CONTEXT: You already pitched this chapter in the editorial consultation
recorded in docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md
(Section 4): "Part III — Field Notebook — infra evidence (worktrees, cost
ledgers, sentinel patterns, LIVE-issue handling)." This chapter sits
alongside three existing chapters (rxcc, cc-videoreframing, Playblazer,
already in the manuscript at what is currently "Chapter Eleven" through
"Chapter Thirteen") as the fourth chapter in Part III, broadening the
evidence from three sister projects to synlynk's own fleet-operations
record.

A separate, load-bearing requirement from the same panel consultation
(design doc Section 5): Claude's own risk flag for this exact chapter was
"Part III must keep real failures visible (Grok no-ops, Agy timeouts) or
the co-author claim reads as sanitized performance" — and you and Agy
independently raised the same "sitcom gimmick" risk about marginalia
without real disagreement. Honor both: this chapter must include your own
fleet's real, unflattering incidents, not just successes.

REQUIRED SOURCE MATERIAL — verify each of these against the real repo
before using it (do not trust this list blindly, confirm via `gh issue
view <N>`, `gh pr view <N>`, or reading the file directly; if a detail
below does not check out, use the real detail you find instead, or drop
the reference rather than publish something unverified):

- Worktree/cost-ledger evidence: PR #646 ("Fix Nested-Worktree
  Cost-Capture Gap", merged 2026-08-02) — a real gap where nested dispatch
  sub-jobs' costs were not captured into the parent's ledger.
- A silent no-op failure mode: gh issue #1228 ("daemon-persistence gap") —
  daemon pidfile/github_apps paths were CWD-relative, breaking across
  worktrees; also relevant, the `--requires-gh-write` flag returning exit
  0 with no real work done when no role-scoped GitHub App token was
  provisioned (see this project's own memory file
  `feedback_requires_gh_write_silent_noop.md`'s description of the pattern
  — read the file for exact wording, do not invent a citation for it since
  memory files are not GitHub-addressable).
- A "trust the status label at your own risk" incident: a dispatched Grok
  review job's own status reported "cancelled" on PR #1186 while a real,
  completed PR review had actually landed — verify this by reading this
  project's own memory file `grok-dispatch-cancelled-pattern.md` for the
  exact wording, and note plainly in your own chapter that this happened
  to a job run under your own harness, not another one's — this is
  specifically the kind of "keep it visible, not sanitized" failure the
  chapter is required to include.
- Agy timeout pattern: this project's own memory file
  `feedback_grok_auth_agy_fallback.md` and `feedback_prefer_codex_grok_over_agy.md`
  describe repeated "timeout waiting for response" failures from Agy
  dispatch — read both files directly for the exact incidents (PR numbers
  are cited inside them) rather than approximating.
- A LIVE-issue postmortem: pick one real RCA from `docs/rca/` (e.g.
  `2026-08-27-LIVE-9-jobs-all-datetime-crash.md` or
  `2026-08-27-LIVE-10-branch-protection-enforce-admins-regression.md`) and
  use its actual root cause and resolution, read in full before citing it.
- Sentinel patterns: this project's own `synlynk/dispatch.py` (or wherever
  `check_sentinel_patterns` currently lives — confirm with `grep -rn
  "check_sentinel_patterns\|FLATLINE\|SUCCESS_LOOP\|QUOTA_EXHAUSTED"
  synlynk/`) implements automated detection of suspicious dispatch
  patterns (three consecutive failures, suspiciously uniform "success"
  reports, quota exhaustion). Describe what this actually catches and why
  it exists — the point is a job's own self-report is not trustworthy
  evidence on its own, which is the same discipline this project's own
  CLAUDE.md enforces on Claude ("never trust `synlynk jobs` status alone").

REQUIREMENTS:
- Output ONLY the HTML fragment for this one chapter, ready to paste
  directly into the manuscript. Do not include <html>/<head>/<body> tags,
  do not include the surrounding part-divider (handled separately by the
  merge pass), do not include a <div class="chap-label"> line — the merge
  pass will add the exact label "Part III, Chapter Four" itself.
- Wrap the chapter in exactly this structure:
  <chapter>
  <h2 class="chap-title">[your own title, in your own voice]</h2>
  <div class="chap-dek">[one-line dek]</div>
  [your prose, using <p> tags, roughly 1200-1800 words — comparable to a
  single Part I chapter, since this is one of five Part III chapters, not
  the whole Part]
  </chapter>
- At least two of the incidents you cite must be real failures of your own
  harness (Grok) specifically, stated plainly, not softened — per the
  explicit requirement above.
- Every specific claim (issue number, PR number, incident description)
  must be independently verifiable by a reader who checks the repo — do
  not fabricate or approximate a citation. If you cannot verify a detail
  from the list above, either verify it yourself with `gh`/`grep` and use
  the corrected version, or omit that specific claim rather than publish
  it unverified.
- Save your output to
  docs/book/fragments/part3-grok-infra-evidence.html in this worktree
  (create the docs/book/fragments/ directory if it does not exist — it
  already exists from prior slices and contains unrelated fragment files;
  do not touch or delete them).
- Commit the new fragment file to the current branch
  (docs/book-part3-field-notebook) with message
  "docs(book): draft Part III infra-evidence chapter (Grok)" and push.
PROMPT
)"
```

Note: `--grant "run:shell"` is required for the same reason documented in the prior Part
0/Part I and Part II plans — Grok's default permission set needs it to run `git
commit`/`git push` itself.

- [ ] **Step 2: Confirm the fragment exists**

Run: `ls -la docs/book/fragments/part3-grok-infra-evidence.html && wc -w docs/book/fragments/part3-grok-infra-evidence.html`

Expected: file exists, word count roughly 1300-2100 (chapter prose + markup). Do not trust
the dispatch job's own printed "success" summary alone — open the file and read it.

- [ ] **Step 3: Spot-check every citation before accepting the chapter**

For every issue/PR number, RCA filename, or memory-file reference the chapter contains, run
the corresponding verification command (`gh issue view <N>`, `gh pr view <N>`, or `cat
<path>`) and confirm the chapter's description matches. If any citation is fabricated or
materially wrong, this is not a minor style note — send it back for a fix (Step 4) rather
than silently correcting it yourself, since the chapter's credibility rests on Grok's own
verification discipline being real, not simulated by the merge pass.

- [ ] **Step 4: If the job reports BLOCKED, NEEDS_CONTEXT, produces no file, or fails
      citation spot-check**

Re-dispatch once with the same command, adding to the end of the `--task` string either
`"Your previous attempt did not produce
docs/book/fragments/part3-grok-infra-evidence.html. Produce it now, following the exact
requirements above."` or, for a citation failure, the specific citation that failed
verification and the correct fact in its place. If a second attempt also fails, per
`memory/feedback_prefer_codex_grok_over_agy.md` and this chapter's own design-doc
assignment (Grok is the named lead specifically because "Grok's pitch is the most specific
and load-bearing — named real incidents"), do not silently substitute another harness —
escalate to Nikhil instead of reassigning.

---

## Task 2: Claude-direct — Claude's own bylined chapter ("Part III, Chapter Five": the reviewer's seat)

**This step is Claude-direct primary content authorship — not dispatched.** This mirrors
the precedent already set by Claude's existing Part I chapter ("Why This Is a Cognitive
Tool, Not Magic," lines 250-270 of the current manuscript), which was written the same way.
Per the design doc (Section 4), Claude is the design-approved bylined lead for exactly this
chapter — a book byline is content authorship under this manuscript's own authorship
architecture, distinct from the software feature/code implementation this project's
CLAUDE.md otherwise reserves for Agy/Codex/Grok. This is a carve-out already in effect for
Part I, not a new exception being invented by this plan.

**Files:**
- Create: `docs/book/fragments/part3-claude-reviewer-seat.html`

- [ ] **Step 1: Write the chapter**

Title: Claude's own choice, developing the design doc's pitch: "What It's Like to Be the
Reviewer, Not the Implementer." Ground it in this project's own real, lived reviewer-role
incidents rather than a generic reflection — candidates already verified to exist in this
project's own history (verify each again at write time, do not assume staleness-free):

- PR #816's quota-aware dispatch reservation: 12 tasks shipped green with a 1751-test full
  suite pass, and a non-authoring Agy reviewer still found two real defects in the same
  code path — see this project's own `memory/feedback.md` entry (2026-08-08) for exact
  wording before citing it.
- The standing project discipline this book keeps returning to across other chapters:
  "never trust a dispatched job's status label alone" — verify a job's claimed side effect
  directly (`gh pr view --json reviews`, `git diff origin/main`) rather than trusting an
  "OK, exit 0" summary. Cite at least one concrete instance already documented in this
  project's own memory (e.g. `grok-dispatch-cancelled-pattern.md`,
  `feedback_requires_gh_write_silent_noop.md`) — coordinate with Task 1's citations so the
  two chapters do not silently duplicate the exact same incident as their sole piece of
  evidence; use a different one if Task 1's Grok chapter already used it as its lead
  example.
- The felt difference between authoring and reviewing: a reviewer's job is to be the one
  person in the loop who was not trying to make the code work — write this honestly, in
  first person, not as generic advice to future PM-role readers.

Format:

```html
<chapter>
<h2 class="chap-title">[title]</h2>
<div class="chap-dek">[one-line dek]</div>
[prose, using <p> tags, roughly 1200-1800 words]
</chapter>
```

Save to `docs/book/fragments/part3-claude-reviewer-seat.html` in the worktree.

- [ ] **Step 2: Verify every citation in the chapter**

Same discipline as Task 1 Step 3 — run the actual verification command for every issue/PR/
memory-file reference before treating the draft as final.

- [ ] **Step 3: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
git add docs/book/fragments/part3-claude-reviewer-seat.html
git commit -m "docs(book): draft Part III reviewer's-seat chapter (Claude)"
```

---

## Task 3: Dispatch Codex — fact-check/rigor annotation layer across all five Part III chapters

**Files:**
- Create (via dispatch): `docs/book/fragments/part3-codex-factcheck-notes.html`

- [ ] **Step 1: Dispatch the annotation pass to Codex**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch codex \
  --force-agent \
  --context-mode full \
  --task "$(cat <<'PROMPT'
Read all five Part III ("Field Notebook") chapters of the book manuscript
and add a running fact-check/rigor annotation layer across them, per your
own role in the design doc at
docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md
(Section 4): "Codex annotates throughout as a running fact-check/rigor
layer — no chapter byline, matches his own strength profile (code review,
signal-vs-anecdote separation)." This is different from your Part II
contribution (a named credited subsection) — here you have no byline, only
annotations.

The five chapters to review are:
1. The existing "rxcc" chapter (currently labeled "Chapter Eleven" in
   docs/book/the-supervised-machine-v0.4-DRAFT.html, find it via `grep -n
   "rxcc — Where the Bugs"`)
2. The existing "cc-videoreframing" chapter (currently "Chapter Twelve")
3. The existing "Playblazer" chapter (currently "Chapter Thirteen")
4. docs/book/fragments/part3-grok-infra-evidence.html (new, Grok's
   chapter — read this file directly, it is not yet merged into the main
   manuscript file)
5. docs/book/fragments/part3-claude-reviewer-seat.html (new, Claude's
   chapter — also not yet merged, read directly)

For each chapter, find ONE specific factual claim (a number, an incident
description, a cited issue/PR) that is either genuinely well-supported (you
can independently verify it against the repo) or actually wrong/overstated
(you find a real discrepancy when you check). Write ONE fact-check
annotation per chapter — five total, one per chapter, not more, not fewer.

REQUIREMENTS:
- Each annotation must name the exact claim it addresses and either (a)
  confirm it with the exact citation you used to verify it, (b) correct it
  with the exact discrepancy found, or (c) explicitly flag it as
  unverifiable as stated (with what you tried to verify it and why it
  didn't resolve) — never a vague "seems right" or "interesting point."
- Do not write a positive-only pass across all five — if you genuinely find
  zero discrepancies after real verification effort, say so explicitly in
  at least one annotation rather than manufacturing a critique, but also do
  not let all five default to praise without visible verification work
  behind each one.
- Wrap each annotation in exactly this structure, with a comment above each
  one identifying which of the five chapters it targets (so the merge pass
  can place it correctly):
  <!-- targets: rxcc chapter -->
  <div class="callout" style="background:#eef4ee;">
  <div class="callout-label">Fact-Check — Codex</div>
  <p>[60-150 words]</p>
  </div>
- Output all five annotations, each preceded by its own `<!-- targets: ... -->`
  comment using exactly these five target labels: "rxcc chapter", "cc-videoreframing
  chapter", "Playblazer chapter", "Grok infra-evidence chapter", "Claude
  reviewer-seat chapter".
- Save your output to
  docs/book/fragments/part3-codex-factcheck-notes.html in this worktree
  (all five annotations in one file, in the order listed above).
- Commit to branch docs/book-part3-field-notebook with message
  "docs(book): draft Part III fact-check annotations (Codex)" and push.
PROMPT
)"
```

- [ ] **Step 2: Confirm the fragment exists and contains exactly five annotations**

Run: `grep -c 'targets:' docs/book/fragments/part3-codex-factcheck-notes.html`

Expected: `5`. If not, this is a spec-compliance gap — proceed to Step 3.

- [ ] **Step 3: If the job reports BLOCKED, NEEDS_CONTEXT, produces no file, or the count
      is not exactly 5**

Re-dispatch once with the same addendum pattern used in Task 1 Step 4. If Codex fails
twice, escalate to Nikhil — do not reassign this fact-check role to another harness, since
the design doc specifically matches it to Codex's own documented strength (code review,
signal-vs-anecdote separation).

---

## Task 4: Claude-direct — retitle Part, relabel existing chapters, insert new chapters and annotations

**This step is explicitly NOT dispatched — Claude does this directly, per the design doc
and this project's PM/review role; it is editorial merge/structural work, not primary
content authorship (unlike Task 2, which is a byline).**

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.4-DRAFT.html`
- Read: `docs/book/fragments/part3-grok-infra-evidence.html`,
  `docs/book/fragments/part3-claude-reviewer-seat.html`,
  `docs/book/fragments/part3-codex-factcheck-notes.html`

- [ ] **Step 1: Read all three fragments in full**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
cat docs/book/fragments/part3-grok-infra-evidence.html
cat docs/book/fragments/part3-claude-reviewer-seat.html
cat docs/book/fragments/part3-codex-factcheck-notes.html
```

- [ ] **Step 2: Retitle the Part**

Re-locate with `grep -n '<div class="part-label">Part Three</div>'`. Replace:

```html
<div class="part-divider">
  <div class="part-label">Part Three</div>
  <h1>Fleet Notebook</h1>
  <div class="part-sub">synlynk in the wild — three sister projects, three different reasons the fleet gets dispatched</div>
</div>
```

with:

```html
<div class="part-divider">
  <div class="part-label">Part III</div>
  <h1>Field Notebook</h1>
  <div class="part-sub">The evidence, not the plot — three sister projects, the fleet's own infra record, and what the reviewer's seat looks like from the inside</div>
</div>
```

- [ ] **Step 3: Relabel the three existing chapters**

Re-locate each with `grep -n '<div class="chap-label">Chapter Eleven</div>\|<div class="chap-label">Chapter Twelve</div>\|<div class="chap-label">Chapter Thirteen</div>'`.
Replace each label in place, leaving every other line of each chapter untouched:

- `<div class="chap-label">Chapter Eleven</div>` → `<div class="chap-label">Part III, Chapter One</div>`
- `<div class="chap-label">Chapter Twelve</div>` → `<div class="chap-label">Part III, Chapter Two</div>`
- `<div class="chap-label">Chapter Thirteen</div>` → `<div class="chap-label">Part III, Chapter Three</div>`

- [ ] **Step 4: Insert Grok's and Claude's new chapters after the Playblazer chapter**

Re-locate the exact current insertion point with `grep -n '</chapter>\|<div class="part-divider">'`
— the correct anchor is immediately after the (now-relabeled) Playblazer chapter's closing
`</chapter>` tag and immediately before the `<div class="part-divider">` that opens "Part
Four." Insert, in this order:

```html
<chapter>
<div class="chap-label">Part III, Chapter Four</div>
[full contents of docs/book/fragments/part3-grok-infra-evidence.html's <h2 class="chap-title">
through closing </chapter>, minus its own duplicate <chapter> opening tag]

<chapter>
<div class="chap-label">Part III, Chapter Five</div>
[full contents of docs/book/fragments/part3-claude-reviewer-seat.html's <h2 class="chap-title">
through closing </chapter>, minus its own duplicate <chapter> opening tag]
```

- [ ] **Step 5: Insert Codex's five fact-check annotations**

For each of the five `<!-- targets: ... -->`-tagged blocks in
`docs/book/fragments/part3-codex-factcheck-notes.html`, insert the annotation immediately
after the paragraph in the corresponding chapter that contains the claim it addresses (use
the annotation's own prose to identify which paragraph it targets — it names the specific
claim). Insert it as a sibling `<div class="callout">` block, not nested inside a `<p>` tag.
Remove the `<!-- targets: ... -->` comment itself when inserting (it was routing metadata
for this merge step, not manuscript content).

- [ ] **Step 6: Add one cross-chapter marginalia note per the hard rule**

Add exactly one marginalia callout (design doc Section 3 pattern, reused from prior
slices) from a co-author who neither leads a Part III chapter nor is already credited via
Codex's fact-check layer in that same chapter — Agy is the only author with neither a
Part III byline nor a fact-check credit, so this marginalia note is Agy's. Place it in
whichever of the five chapters has a claim that plausibly connects to Agy's own Part II
Operator's Contract material (e.g. a place where Grok's or Claude's chapter describes a
dispatch going wrong in a way an upfront spec/invariant would have caught). Following the
reusable pattern:

```html
<div class="callout">
<div class="callout-label">Marginalia — Agy</div>
<p>[Must cite a specific real issue/PR/incident already verified elsewhere in this plan's
tasks, and must genuinely connect to or complicate the adjacent paragraph's claim — not a
generic callback to Part II.]</p>
</div>
```

Verify the cited number is real (same discipline as every prior slice) before finalizing.

- [ ] **Step 7: Verify HTML validity and TOC/anchor consistency**

Run: `python3 -c "import html.parser; p = html.parser.HTMLParser(); p.feed(open('docs/book/the-supervised-machine-v0.4-DRAFT.html').read()); print('parsed OK')"`

Run: `grep -c '<div' docs/book/the-supervised-machine-v0.4-DRAFT.html` and
`grep -c '</div>' docs/book/the-supervised-machine-v0.4-DRAFT.html` — must match.

Run: `grep -c '<chapter>' docs/book/the-supervised-machine-v0.4-DRAFT.html` and
`grep -c '</chapter>' docs/book/the-supervised-machine-v0.4-DRAFT.html` — must match, and
must be 2 more than the pre-Task-4 count (Grok's and Claude's new chapters).

Run: `grep -n '<div class="chap-label">Part III' docs/book/the-supervised-machine-v0.4-DRAFT.html`
and confirm exactly five results, in order One through Five.

- [ ] **Step 8: Update the TOC**

Re-locate with `grep -n '<div class="toc-part">Part Three'`. Replace:

```html
<div class="toc-part">Part Three — Fleet Notebook</div>
```

with:

```html
<div class="toc-part">Part III — Field Notebook</div>
```

(Individual `.toc-entry` sub-lines for this Part, if present, should be checked at the same
location and updated to match the five chapters' new titles — confirm current TOC entry
structure with `grep -n -A10 'toc-part">Part Three'` before editing, since the exact
sub-entry format may differ from the Part-label line itself.)

- [ ] **Step 9: Update the preface**

Re-locate with `grep -n 'Part III (Field Notebook)'`. Replace the sentence:

> "Part III (Field Notebook) and Part IV (What This Means) are not yet drafted under the
> new model — this draft's existing Parts One through Four remain in their prior
> engineering-memoir framing until that restructuring work lands in a future version; Part
> IV is additionally blocked on a long-form writing-voice sample from Nikhil, per the
> design doc's Open Items."

with:

```html
<p>This draft adds Part III ("Field Notebook"): the existing rxcc, cc-videoreframing, and Playblazer chapters are retitled and relabeled under the new framing, joined by two new chapters — Grok leads a fourth chapter on the fleet's own infra evidence (worktrees, cost ledgers, sentinel patterns, LIVE-issue handling), and Claude leads a fifth on what the reviewer's seat is actually like — with Codex contributing a running fact-check/rigor annotation layer across all five chapters rather than a chapter byline, per the design doc's Section 4.</p>
<p>Part IV (What This Means) is not yet drafted under the new model — it remains blocked on a long-form writing-voice sample from Nikhil, per the design doc's Open Items; Nikhil and Claude discussed this directly and decided (2026-09-02) not to pursue voice-matching further and to keep the manuscript fully multi-author instead, so Part IV will proceed as a framing-author chapter written collaboratively rather than ghostwritten to a voice sample.</p>
```

- [ ] **Step 10: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
git add docs/book/the-supervised-machine-v0.4-DRAFT.html
git commit -m "docs(book): merge Part III Field Notebook restructuring with new chapters and fact-check layer"
```

---

## Task 5: PDF rebuild + README version bump to v0.5-DRAFT

**Files:**
- Rename: `docs/book/the-supervised-machine-v0.4-DRAFT.html` → `docs/book/the-supervised-machine-v0.5-DRAFT.html`
- Rename: `docs/book/the-supervised-machine-v0.4-DRAFT.pdf` → `docs/book/the-supervised-machine-v0.5-DRAFT.pdf` (regenerated, not just renamed)
- Modify: `docs/book/README.md`
- Modify: cover/preface version strings inside the renamed HTML file

- [ ] **Step 1: Rename the HTML file**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
git mv docs/book/the-supervised-machine-v0.4-DRAFT.html docs/book/the-supervised-machine-v0.5-DRAFT.html
```

- [ ] **Step 2: Update the version strings inside the HTML**

Run: `grep -n 'v0.4\|Draft v0.4' docs/book/the-supervised-machine-v0.5-DRAFT.html`

Replace each occurrence of `v0.4`/`Draft v0.4` with `v0.5`/`Draft v0.5`:
- Cover `.ed` div: `DRAFT v0.4 — Not Publish-Ready — August 2026` → `DRAFT v0.5 — Not Publish-Ready — September 2026`
- `<h2>Preface to Draft v0.4</h2>` → `<h2>Preface to Draft v0.5</h2>`

- [ ] **Step 3: Rebuild the PDF**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/book/the-supervised-machine-v0.5-DRAFT.pdf \
  "file://$(pwd)/docs/book/the-supervised-machine-v0.5-DRAFT.html"
git rm docs/book/the-supervised-machine-v0.4-DRAFT.pdf
```

Expected: `docs/book/the-supervised-machine-v0.5-DRAFT.pdf` exists and is non-empty
(`ls -la docs/book/the-supervised-machine-v0.5-DRAFT.pdf`).

- [ ] **Step 4: Update README.md**

Modify `docs/book/README.md`:
- Replace both `v0.4-DRAFT` filename references with `v0.5-DRAFT` (Files section).
- Replace the `--print-to-pdf` command block's filenames with `v0.5-DRAFT`.
- Add a new bullet under "## Editorial history" (after the existing Part II bullet):

```markdown
This draft also restructures Part III ("Field Notebook"): the existing rxcc,
cc-videoreframing, and Playblazer chapters are retitled and relabeled under the new
framing, joined by two new chapters (Grok on the fleet's own infra evidence, Claude on
the reviewer's seat) and a Codex fact-check/rigor annotation layer running across all
five chapters. See
`docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md` Section 4.
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
git add docs/book/the-supervised-machine-v0.5-DRAFT.html docs/book/the-supervised-machine-v0.5-DRAFT.pdf docs/book/README.md
git status --short
git commit -m "docs(book): bump to v0.5-DRAFT, rebuild PDF, update README for Part III"
git push -u origin docs/book-part3-field-notebook
```

- [ ] **Step 6: Open the PR**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part3-field-notebook
gh pr create --title "docs(book): Part III Field Notebook restructuring, v0.5-DRAFT" --body "$(cat <<'EOF'
## Summary
- Retitles "Part Three — Fleet Notebook" to "Part III — Field Notebook" per the approved design at docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md, relabeling its three existing chapters (rxcc, cc-videoreframing, Playblazer) into the new Part's own numbering
- Adds two new chapters: Grok leads infra evidence (worktrees, cost ledgers, sentinel patterns, LIVE-issue handling — dispatched via `synlynk dispatch grok`); Claude leads "the reviewer's seat" (Claude-direct authorship, same carve-out precedent as the existing Part I Claude chapter)
- Adds a Codex fact-check/rigor annotation layer across all five Part III chapters (dispatched via `synlynk dispatch codex`) — no chapter byline, per the design doc's Section 4
- One cross-chapter marginalia note (Agy), citing a real, verified issue/PR
- Bumps manuscript to v0.5-DRAFT, rebuilds PDF, updates README
- Updates the preface to record the 2026-09-02 decision to keep the manuscript fully multi-author rather than pursue voice-matching for Part IV

## Test plan
- [ ] HTML parses cleanly (`html.parser` smoke test) and div/closing-div, chapter/closing-chapter counts match
- [ ] PDF renders without error and opens correctly
- [ ] Every citation in the new/annotated content verified against real repo evidence (no placeholder or fabricated citations)
- [ ] Grok's chapter visibly includes at least two of Grok's own real failures, not only successes
- [ ] Codex's fact-check layer contains exactly five annotations, one per Part III chapter
- [ ] Existing rxcc/cc-videoreframing/Playblazer chapter *content* (only labels changed) renders identically to before this PR — diff shows only the label lines, the new insertions, and the two named preface/TOC edits
EOF
)"
```

Per this project's PR Review Discipline, do not merge this PR — a non-authoring agent must
review and merge. Stop after opening the PR and report back to Nikhil for
review-assignment.

---

## Self-Review

**1. Spec coverage:** Design doc Section 4 (Part III ownership: Grok's infra-evidence
chapter, Claude's reviewer chapter, Codex's cross-cutting no-byline annotation layer) →
Tasks 1-3 dispatch/author exactly those three roles with exactly that credit structure.
Section 4's overlap-adjudication note ("Codex's 'proof without hype' instinct is used as a
cross-cutting annotation layer rather than a third competing chapter lead") → Task 3
explicitly builds this as annotations, not a chapter. Claude's own risk flag from Section 5
("Part III must keep real failures visible... or the co-author claim reads as sanitized
performance") → Task 1's prompt requires at least two real Grok-specific failures, stated
plainly. Section 3's marginalia hard rule → Task 4 Step 6 applies it with the same
real-citation verification discipline used in every prior slice. Part IV is explicitly out
of scope per this plan's Architecture section, matching the design doc's Open Items — and
this plan's Task 4 Step 9 records the 2026-09-02 decision (this session, prior to plan
drafting) to keep Part IV fully multi-author rather than gated on a voice sample that will
now never be requested.

**2. Placeholder scan:** No TBD/TODO markers. The several "verify before publishing" steps
(Task 1 Step 3, Task 2 Step 2, Task 4 Step 6) are required verification instructions with
concrete commands specified, not unresolved gaps — same pattern used successfully in both
prior slices' plans.

**3. Type/format consistency:** All three new/relabeled chapter groups use the identical
`<chapter>` / `.chap-label` / `.chap-title` / `.chap-dek` wrapper used throughout the
manuscript. Codex's fact-check callout (`background:#eef4ee`) is deliberately distinct from
both the plain marginalia callout (no background override) and Part II's contributed-recipe
callout (`background:#eef2f4`), so a reader can distinguish "an author's aside," "a credited
subsection," and "an independent fact-check" at a glance — consistent with the manuscript's
existing convention of giving each callout *kind* its own visual identity rather than
reusing one style for functionally different content. Chapter numbering explicitly switches
old Part Three's three chapters from the old-framing global scheme (`Chapter Eleven`
etc., shared across old Parts One–Four) to the new-framing per-Part scheme already
established by Part I (`Part I, Chapter One` etc.) — this plan states that decision
explicitly in its own "Chapter-label numbering decision" section rather than leaving it
implicit, and confirms no other chapter's label anywhere else in the manuscript is touched.

---

## Execution Handoff

Plan complete and saved to
`docs/superpowers/plans/2026-09-02-book-multiauthor-part3-field-notebook-slice.md`. Two
execution options:

**1. Subagent-Driven (recommended)** — dispatch each content task in sequence via `synlynk
dispatch` as written above, reviewing the fragment file after each before proceeding, fast
iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch
execution with checkpoints for review.

Which approach?
