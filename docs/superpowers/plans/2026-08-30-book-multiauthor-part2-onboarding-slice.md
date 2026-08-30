# "The Supervised Machine" — Part II "The Onboarding" Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **This plan's tasks are content-authorship dispatches, not code tasks — each "implementer" step is a `synlynk dispatch` call to a specific harness, not inline code by whoever executes this plan.**

**Goal:** Insert the new Part II ("The Onboarding") into `docs/book/the-supervised-machine-v0.3-DRAFT.html` — Agy's lead chapter plus a named Codex-credited practical-workflow section within it — reusing the four recipe pitches already on file in the design doc's Section 5, then rebuild the PDF and bump the manuscript to v0.4-DRAFT.

**Architecture:** One `synlynk dispatch` call to Agy for the chapter's narrative spine, one follow-up `synlynk dispatch` call to Codex for a named subsection inserted inside that same chapter (per the design doc's lead/contributor split — not a separate chapter), each producing a self-contained HTML fragment. A Claude-direct (undispatched) merge pass inserts both fragments in the correct position, adds cross-author marginalia per the design's hard rule, verifies HTML validity, then rebuilds the PDF and bumps the version. Part III's restructuring of the existing "Part One" through "Part Four" content into the new Field Notebook framing, and Part IV (blocked on Nikhil's still-unprovided long-form voice sample per the design doc's Open Items), are explicitly **out of scope** — this plan only inserts Part II.

**Tech Stack:** Single-file self-contained HTML manuscript (inline CSS, no build step), Google Chrome headless for PDF rendering, `synlynk dispatch` for content authorship, `git`/`gh` for branch and PR flow.

---

## Current Manuscript State (grounded 2026-08-30, HEAD `a48820a`, v0.3-DRAFT merged via PR #1239)

`docs/book/the-supervised-machine-v0.3-DRAFT.html` is 820 lines. Confirmed structure via
`grep -n '<h1\|<h2\|part-label\|toc-part'`:

- Line 114: `<h1>The Supervised Machine</h1>` (cover)
- Line 121: `<h2>Preface to Draft v0.3</h2>` — its second `<p>` (line 123) currently reads: *"Parts II through IV of the repositioned structure (The Onboarding, Field Notebook, What This Means) are not yet drafted under the new model — this draft's existing Parts One through Four remain in their prior engineering-memoir framing until that work lands in a future version."* This sentence must be rewritten by this plan (Task 4) — it will be false once Part II lands.
- Line 153: `<h2>How to Read This Book</h2>` front-matter segment map (already references Part II by name — no change needed there)
- Line 167: `<div class="toc-page">` — Contents, `.toc-part` / `.toc-entry` divs
- Line 202: `<div class="part-divider">` Part 0
- Line 209: Part 0 chapter (`<chapter>` ... `</chapter>`, closes line ~239)
- Line 241: `<div class="part-divider">` Part I
- Lines 247–318: three Part I chapters (Claude, Grok, Agy), each `<chapter>...</chapter>`, last one closes at line 318
- Line 320: `<chapter>` Prologue ("The Gap Between Neurons"), closes line ~347
- Line 349: `<div class="part-divider">` "Part One — The Eras of Software" (existing engineering-memoir content, **not renamed by this plan** — that renumbering is Part III's job, out of scope here)

None of the existing Part 0 / Part I / Prologue / old-Part-One-through-Four content is touched by this plan except the two edits named explicitly in Task 1 (preface sentence) and Task 4 (TOC entry).

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

Chapter wrapper pattern (reuse exactly — from the Part I chapters at lines 247–318):

```html
<chapter>
<div class="chap-label">[Part / chapter position]</div>
<h2 class="chap-title">[Title]</h2>
<div class="chap-dek">[one-line dek]</div>
<p>...</p>
</chapter>
```

**Marginalia hard rule (design doc Section 3), same pattern used in the merged v0.3 chapters:**

```html
<div class="callout">
<div class="callout-label">Marginalia — [Author]</div>
<p>[Must either contradict the lead author's adjacent paragraph, or cite a specific
issue/LIVE-N/PR number. No purely reactive/color-commentary text.]</p>
</div>
```

**Named-contributor subsection pattern (new to this plan — Part II is the first chapter with a lead/contributor split rather than a single byline).** Use a `<div class="callout">` variant with a distinct label so it reads as a credited subsection, not a marginalia aside:

```html
<div class="callout" style="background:#eef2f4;">
<div class="callout-label">A Contributed Recipe — Codex</div>
<h3 style="margin-top:0;">[Recipe title]</h3>
<p>[Codex's own prose, first person, 300-500 words — a self-contained practical
recipe, not a reaction to Agy's surrounding text]</p>
</div>
```

`h3` has no existing style rule in this manuscript's `<style>` block — check
`grep -n '^h3' docs/book/the-supervised-machine-v0.3-DRAFT.html` before writing Task 3;
if still absent, leave it unstyled (inherits body font at a slightly larger implicit
browser default) rather than inventing new CSS not requested by this plan.

---

## Task 1: Dispatch Agy — Part II chapter ("The Onboarding")

**Files:**
- Create (via dispatch): `docs/book/fragments/part2-onboarding.html`

- [ ] **Step 1: Dispatch the chapter draft to Agy**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch agy \
  --force-agent \
  --context-mode full \
  --grant "run:shell" \
  --task "$(cat <<'PROMPT'
Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.3-DRAFT.html. This is Part II ("The
Onboarding") of a repositioned nonfiction book ("The Supervised Machine")
about human-AI collaboration for a general audience. You are the bylined
lead author of this chapter, writing in your own voice as established in
this manuscript's existing .who.agy dialogue lines and your own Part I
chapter ("Context & Working Memory", read it first at the location found
via `grep -n 'Context & Working Memory' docs/book/the-supervised-machine-v0.3-DRAFT.html`
for tone/length/density reference).

CONTEXT: You already pitched this chapter in an editorial consultation
recorded in docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md
(Section 4): "Part II lead — the broader onboarding narrative." Your job is
practical recipes that get a reader from chatbot-toy-phase confusion to
real productivity, defusing real fears (job loss, math-terror, "AI is
evil," environmental cost) without dismissing them.

You also already contributed one specific recipe to this chapter's raw
material (design doc Section 5): "The Inverse Delegation Protocol (Never
Outsource the Spec)" — the Operator's Contract: forbidden prompting, a
zero-code spec with invariants/failure conditions, diff-only review, and
culpability-and-taste as the human's scarce contribution. Use this as your
chapter's structural spine — it is your own established position, not
something to summarize secondhand.

You may also draw on (attributed to their real authors, not claimed as
your own, if you use them) these other panelists' Part II recipes already
on file in the same design doc Section 5:
- Claude's environmental-cost fear recipe: reframe training vs. inference
  cost, a unit-converter comparison table (one chat response vs. one search
  vs. one minute of video streaming vs. one dishwasher cycle), explicit
  that it addresses per-query guilt, not the separate infrastructure/grid/
  water policy question.
- Grok's "Receipts before vibes" six-step supervised loop: name a visible
  side effect, cage it, run and ignore the victory speech, check the world
  not the transcript, write a one-line receipt with cost, decide what it
  means for the job.

Do NOT draft Codex's "20-minute supervised task, 3-pass rule" recipe
yourself — that is being dispatched to Codex separately as a named,
separately-credited subsection that will be inserted into your chapter
afterward. Leave a natural gap in your narrative flow where a third,
Codex-credited recipe would fit (e.g. after your own Operator's Contract
material and before or after Grok's receipts loop) — reference it in
passing ("a third discipline, contributed separately, covers...") rather
than describing its content, since you have not seen Codex's actual draft.

REQUIREMENTS:
- Output ONLY the HTML fragment for this one chapter, ready to paste
  directly into the manuscript. Do not include <html>/<head>/<body> tags,
  do not include the surrounding part-divider (handled separately by the
  merge pass).
- Wrap the chapter in exactly this structure:
  <chapter>
  <div class="chap-label">Part II</div>
  <h2 class="chap-title">The Onboarding</h2>
  <div class="chap-dek">[one-line dek, your own words]</div>
  [your prose, using <p> tags, roughly 1400-2000 words — longer than a
  single Part I chapter since this is the whole of Part II, not one of
  three; do not pad past what the content needs]
  </chapter>
- Address the four listed fear categories (job loss, math-terror, "AI is
  evil," environmental cost) directly and by name somewhere in the
  chapter — do not let them go unaddressed even where a recipe doesn't
  map onto one specifically.
- Do not fabricate incidents, PR numbers, or issue numbers. Any specific
  claim about synlynk's own behavior must be verifiable against this
  repo's real history (grep code, issues, project-docs/decisions/ first).
- Save your output to docs/book/fragments/part2-onboarding.html in this
  worktree (create the docs/book/fragments/ directory if it does not
  exist — it already exists from the prior Part 0/Part I dispatch and
  contains four unrelated fragment files from that slice; do not touch or
  delete them).
- Commit the new fragment file to the current branch
  (docs/book-part2-onboarding) with message
  "docs(book): draft Part II Onboarding chapter (Agy)" and push.
PROMPT
)"
```

Note: `--grant "run:shell"` is required — Agy's default "content" role permission set does
not include `run:shell` by default, and this task needs Agy to run `git commit`/`git push`
itself. This matched the same requirement in the prior Part 0/Part I plan's Task 5.

- [ ] **Step 2: Confirm the fragment exists**

Run: `ls -la docs/book/fragments/part2-onboarding.html && wc -w docs/book/fragments/part2-onboarding.html`

Expected: file exists, word count roughly 1600-2600 (chapter prose + markup, scaled up from
the ~900-1600 single-chapter range used in the Part I slice since this is a whole Part on
its own). Do not trust the dispatch job's own printed "success" summary alone — open the
file and read it.

- [ ] **Step 3: If the job reports BLOCKED, NEEDS_CONTEXT, or produces no file**

Re-dispatch once with the same command, adding to the end of the `--task` string: `"Your
previous attempt did not produce docs/book/fragments/part2-onboarding.html. Produce it now,
following the exact requirements above."` If a second attempt also fails, per
`memory/feedback_prefer_codex_grok_over_agy.md` do not silently substitute another harness
for Agy's chapter — Agy is the design doc's named lead for Part II specifically because of
her established voice; escalate to Nikhil instead of reassigning.

---

## Task 2: Dispatch Codex — named contributed recipe ("The 3-Pass Supervised Task Rule")

**Files:**
- Create (via dispatch): `docs/book/fragments/part2-codex-3pass-recipe.html`

- [ ] **Step 1: Dispatch the recipe draft to Codex**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch codex \
  --force-agent \
  --context-mode full \
  --task "$(cat <<'PROMPT'
Write one short, self-contained, credited subsection (NOT a full chapter)
as an HTML fragment, for insertion inside Part II ("The Onboarding") of the
manuscript at docs/book/the-supervised-machine-v0.3-DRAFT.html. Agy leads
Part II as bylined chapter author; you are contributing one named,
separately-credited practical recipe within her chapter, per the design
doc's lead/contributor split at
docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md
(Section 4: "Codex contributes named practical-workflow sections within it
— credited, not co-branded as chapter lead").

CONTEXT: You already pitched this specific recipe in the editorial
consultation recorded in that design doc's Section 5: "the 20-minute
supervised task, 3-pass rule" — draft-with-assumptions pass, self-attack
pass, human-approves-smallest-step pass. Write the actual recipe delivering
on that pitch, in your own established voice (see this manuscript's
existing .who.codex dialogue lines — precise, review-minded, allergic to
unverified claims).

REQUIREMENTS:
- Output ONLY the HTML fragment for this one subsection, ready to be
  inserted inside Agy's chapter by a later merge pass. Do not include
  <html>/<head>/<body>, <chapter>, or any part-divider markup — those
  belong to the surrounding chapter, not this subsection.
- Wrap in exactly this structure:
  <div class="callout" style="background:#eef2f4;">
  <div class="callout-label">A Contributed Recipe — Codex</div>
  <h3 style="margin-top:0;">The 3-Pass Supervised Task Rule</h3>
  [your prose, using <p> tags, 300-500 words, first person, a
  self-contained practical recipe a reader can act on directly]
  </div>
- Explain the three passes concretely: (1) a draft pass that states its own
  working assumptions explicitly rather than silently guessing, (2) a
  self-attack pass where the same task is asked to find the flaw in its own
  first draft before a human sees either, (3) a human-approves-smallest-step
  pass, where the human is shown the smallest reviewable increment rather
  than the whole task's output at once.
- Ground this in a real synlynk mechanism or incident if one applies — do
  not fabricate a PR/issue number; if you don't have a specific verified
  one on hand, write the recipe generically without inventing a citation
  rather than making one up.
- Save your output to docs/book/fragments/part2-codex-3pass-recipe.html in
  this worktree (docs/book/fragments/ already exists; do not touch other
  files in it).
- Commit to branch docs/book-part2-onboarding with message
  "docs(book): draft Part II Codex-contributed 3-pass recipe" and push.
PROMPT
)"
```

- [ ] **Step 2: Confirm the fragment exists**

Run: `ls -la docs/book/fragments/part2-codex-3pass-recipe.html && wc -w docs/book/fragments/part2-codex-3pass-recipe.html`

Expected: file exists, word count roughly 350-650 (this is a subsection, not a full
chapter — much shorter than Task 1's output).

- [ ] **Step 3: If the job reports BLOCKED, NEEDS_CONTEXT, or produces no file**

Re-dispatch once with the same addendum pattern as Task 1 Step 3, substituted for this
file. If Codex fails twice, escalate to Nikhil — do not reassign Codex's named-credit
recipe to another harness, since the credit line is specifically his.

---

## Task 3: Claude-direct — merge fragments, add marginalia, insert Part II divider

**This step is explicitly NOT dispatched — Claude does this directly, per the design doc
and this project's PM/review role; it is editorial merge work, not primary content
authorship.**

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.3-DRAFT.html`
- Read: `docs/book/fragments/part2-onboarding.html`, `docs/book/fragments/part2-codex-3pass-recipe.html`

- [ ] **Step 1: Read both fragments in full**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
cat docs/book/fragments/part2-onboarding.html
cat docs/book/fragments/part2-codex-3pass-recipe.html
```

- [ ] **Step 2: Check each fragment against the marginalia hard rule and voice consistency**

For each fragment, confirm:
- No fabricated incident/issue/PR references — spot-check any cited number against
  `gh issue view <N>` or `git log --oneline | grep <N>` before trusting it.
- Agy's chapter word count in the 1400-2200 range; Codex's subsection in the 300-600 range.
  Padded or suspiciously short output should be flagged, not silently accepted.
- Agy's chapter uses `<chapter>`/`.chap-label`/`.chap-title`/`.chap-dek` markup exactly as
  specified. Codex's subsection uses the `.callout` + `h3` wrapper exactly as specified —
  it must NOT be wrapped in its own `<chapter>` tag (it is a subsection of Agy's chapter,
  not a sibling chapter).
- Agy's chapter addresses all four fear categories named in Task 1 (job loss, math-terror,
  "AI is evil," environmental cost) — if one is missing, this is a spec-compliance gap to
  fix by editing the fragment directly (a missing paragraph on one fear category is a small
  enough gap to patch inline rather than re-dispatching the whole chapter).

- [ ] **Step 3: Insert Codex's subsection into Agy's chapter fragment**

Open `docs/book/fragments/part2-onboarding.html`. Find the "natural gap" Agy was asked to
leave (the passage referencing a third, separately-contributed recipe in passing). Insert
the full contents of `docs/book/fragments/part2-codex-3pass-recipe.html` at that point,
replacing Agy's forward-reference sentence with the actual subsection. If Agy's draft did
not leave an obvious gap, insert Codex's subsection after Agy's own Operator's Contract
material and before her chapter's closing paragraph — do not append it after the chapter's
final `<p>` where it would read as an afterthought rather than an integrated recipe.

- [ ] **Step 4: Insert Part II with its part-divider, after the Prologue and before the existing "Part One" divider**

Re-locate the exact current insertion point with:
`grep -n '<div class="part-divider">\|</chapter>' docs/book/the-supervised-machine-v0.3-DRAFT.html`

The correct anchor is immediately after the Prologue chapter's closing `</chapter>` tag
and immediately before the `<div class="part-divider">` that opens "Part One — The Eras of
Software" (confirmed at line 349 in the Current Manuscript State section above; re-confirm
the line number since it may have shifted if earlier tasks in this plan already edited the
file). Insert:

```html
<div class="part-divider">
  <div class="part-label">Part II</div>
  <h1>The Onboarding</h1>
  <div class="part-sub">Practical recipes to skip the chatbot-toy phase and reach real productivity, without dismissing the fears that keep most people stuck there</div>
</div>

[merged contents of docs/book/fragments/part2-onboarding.html from Step 3, including
Codex's inserted subsection]

```

- [ ] **Step 5: Add cross-chapter marginalia per the hard rule**

Add exactly one marginalia callout to Part II's chapter, from a co-author who did not lead
it (Claude, Grok, or Codex is already credited via his named subsection so should not also
get a marginalia note in the same chapter — use Claude or Grok). Following the reusable
pattern defined at the top of this plan:

```html
<div class="callout">
<div class="callout-label">Marginalia — Grok</div>
<p>Agy's Operator's Contract is the right discipline, and it is also exactly what was
missing the two times this fleet's own dispatch model failed loudest: a role dispatched
with <code>--requires-gh-write</code> and no provisioned GitHub App token silently no-op'd
with exit 0 (the daemon-persistence and per-worktree GitHub App gaps this project's own
memory tracks, e.g. gh:#1228), and a job status reporting "cancelled" turned out to hide a
real completed PR needing independent verification, not a trusted status label. The
contract in this chapter is not a nicety — it is the difference between those two silent
failures and a caught one.</p>
</div>
```

**Before finalizing this marginalia note**, verify the cited issue number is real: run
`gh issue view 1228 --json title,state` in the main repo (not this worktree, to reach full
issue history) and confirm it matches the daemon-persistence/worktree-GitHub-App-gap
description. If it does not match, substitute the correct real issue number found via
`gh issue list --search "github app token worktree"` rather than publishing an unverified
citation.

- [ ] **Step 6: Verify HTML validity and TOC/anchor consistency**

Run: `python3 -c "import html.parser; p = html.parser.HTMLParser(); p.feed(open('docs/book/the-supervised-machine-v0.3-DRAFT.html').read()); print('parsed OK')"`

Run: `grep -c '<div' docs/book/the-supervised-machine-v0.3-DRAFT.html` and
`grep -c '</div>' docs/book/the-supervised-machine-v0.3-DRAFT.html` — must match.

Run: `grep -n '<h1>\|<h2 class="chap-title">' docs/book/the-supervised-machine-v0.3-DRAFT.html`
and confirm reading order is: Part 0 → Part I (3 chapters) → Prologue → Part II (1 chapter,
with Codex's subsection embedded inside it) → (existing, unchanged) Part One "The Eras of
Software" → Part Two → Part Three → Part Four.

- [ ] **Step 7: Add the Part II entry to the Contents (TOC)**

In the `<div class="toc-page">` block, immediately after the existing
`<div class="toc-entry"><span class="t">Prologue — The Gap Between Neurons</span></div>`
line and before `<div class="toc-part">Part One — The Eras of Software</div>`, insert:

```html
<div class="toc-part">Part II — The Onboarding</div>
<div class="toc-entry"><span class="t">The Onboarding</span></div>
```

- [ ] **Step 8: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
git add docs/book/the-supervised-machine-v0.3-DRAFT.html
git commit -m "docs(book): merge Part II Onboarding chapter into manuscript with cross-author marginalia"
```

---

## Task 4: PDF rebuild + README version bump to v0.4-DRAFT

**Files:**
- Rename: `docs/book/the-supervised-machine-v0.3-DRAFT.html` → `docs/book/the-supervised-machine-v0.4-DRAFT.html`
- Rename: `docs/book/the-supervised-machine-v0.3-DRAFT.pdf` → `docs/book/the-supervised-machine-v0.4-DRAFT.pdf` (regenerated, not just renamed)
- Modify: `docs/book/README.md`
- Modify: cover/preface version strings inside the renamed HTML file

- [ ] **Step 1: Rename the HTML file**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
git mv docs/book/the-supervised-machine-v0.3-DRAFT.html docs/book/the-supervised-machine-v0.4-DRAFT.html
```

- [ ] **Step 2: Update the version strings inside the HTML**

Run: `grep -n 'v0.3\|Draft v0.3' docs/book/the-supervised-machine-v0.4-DRAFT.html`

Replace each occurrence of `v0.3`/`Draft v0.3` with `v0.4`/`Draft v0.4`. Specifically:
- Cover `.ed` div: `DRAFT v0.3 — Not Publish-Ready — August 2026` → `DRAFT v0.4 — Not Publish-Ready — August 2026`
- Preface `<h2>Preface to Draft v0.3</h2>` → `<h2>Preface to Draft v0.4</h2>`. Replace the
  existing two preface `<p>` paragraphs (the second of which currently says Parts II-IV
  aren't drafted yet — now false for Part II) with:

```html
<p>This draft adds Part 0 ("The Reckoning") and Part I ("What This Actually Is"), the first chapters written under this manuscript's new multi-author model: Claude, Codex, Grok, and Agy each lead the chapters that fit their own established voice, credited by name, with cross-chapter marginalia carrying real disagreement rather than color commentary. The full editorial rationale — including a live four-model consultation on chapter ownership and title — is recorded at <code>docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md</code>.</p>
<p>This draft adds Part II ("The Onboarding"): Agy leads as bylined chapter author, with Codex contributing one named, separately-credited practical recipe within it, per the same design doc's lead/contributor split.</p>
<p>Part III (Field Notebook) and Part IV (What This Means) are not yet drafted under the new model — this draft's existing Parts One through Four remain in their prior engineering-memoir framing until that restructuring work lands in a future version; Part IV is additionally blocked on a long-form writing-voice sample from Nikhil, per the design doc's Open Items.</p>
```

- [ ] **Step 3: Rebuild the PDF**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/book/the-supervised-machine-v0.4-DRAFT.pdf \
  "file://$(pwd)/docs/book/the-supervised-machine-v0.4-DRAFT.html"
git rm docs/book/the-supervised-machine-v0.3-DRAFT.pdf
```

Expected: `docs/book/the-supervised-machine-v0.4-DRAFT.pdf` exists and is non-empty
(`ls -la docs/book/the-supervised-machine-v0.4-DRAFT.pdf`).

- [ ] **Step 4: Update README.md**

Modify `docs/book/README.md`:
- Replace both `v0.3-DRAFT` filename references with `v0.4-DRAFT` (Files section).
- Replace the `--print-to-pdf` command block's filenames with `v0.4-DRAFT`.
- Add a new bullet under "## Editorial history" (after the existing Part 0/Part I bullet):

```markdown
This draft also adds Part II ("The Onboarding"): see
`docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md` Section 4 for
the lead/contributor split (Agy leads, Codex contributes a named practical recipe within
the same chapter rather than a separate byline).
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
git add docs/book/the-supervised-machine-v0.4-DRAFT.html docs/book/the-supervised-machine-v0.4-DRAFT.pdf docs/book/README.md
git status --short
git commit -m "docs(book): bump to v0.4-DRAFT, rebuild PDF, update README for Part II"
git push -u origin docs/book-part2-onboarding
```

- [ ] **Step 6: Open the PR**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-part2-onboarding
gh pr create --title "docs(book): Part II Onboarding chapter, v0.4-DRAFT" --body "$(cat <<'EOF'
## Summary
- Adds Part II ("The Onboarding") to the manuscript, per the approved design at docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md
- Agy leads as bylined chapter author (dispatched via `synlynk dispatch agy`); Codex contributes one named, separately-credited practical recipe ("The 3-Pass Supervised Task Rule") within the same chapter, per the design's lead/contributor split
- One cross-chapter marginalia note (Grok), citing a real, verified issue number
- Bumps manuscript to v0.4-DRAFT, rebuilds PDF, updates README

## Test plan
- [ ] HTML parses cleanly (`html.parser` smoke test) and div/closing-div counts match
- [ ] PDF renders without error and opens correctly
- [ ] Marginalia citation verified against a real issue (no placeholder citations)
- [ ] All four fear categories (job loss, math-terror, "AI is evil," environmental cost) are addressed somewhere in Part II
- [ ] Existing Part 0 / Part I / Prologue / old Parts One–Four (untouched except the preface sentence and TOC entry) still render identically — diff shows only additive changes plus those two named edits
EOF
)"
```

Per this project's PR Review Discipline, do not merge this PR — a non-authoring agent
must review and merge. Stop after opening the PR and report back to Nikhil for
review-assignment.

---

## Self-Review

**1. Spec coverage:** Design doc Section 4 (Part II ownership: Agy lead, Codex named
contributor, not co-branded) → Tasks 1-2 dispatch to exactly those two harnesses with
exactly that credit structure; Section 5's Part II recipe raw material (all four
panelists' contributions) → passed to Agy in Task 1's prompt so drafting doesn't have to
re-derive it, with Codex's own recipe explicitly excluded from Agy's scope and dispatched
separately in Task 2; Section 3 marginalia hard rule → Task 3 Step 5 applies it with a
required real-citation verification step, same discipline as the merged Part 0/Part I PR.
Part III and Part IV are explicitly out of scope per this plan's own Architecture section,
matching the design doc's Open Items (Part IV blocked on a voice sample that still has not
been provided as of this plan's writing).

**2. Placeholder scan:** No TBD/TODO markers. The one "verify before publishing" item (Task
3 Step 5's marginalia citation) is a required verification instruction with a fallback
search command specified, not an unresolved gap — same pattern used and completed
successfully in the prior Part 0/Part I plan's Task 6.

**3. Type/format consistency:** Agy's chapter uses the identical `<chapter>` /
`.chap-label` / `.chap-title` / `.chap-dek` wrapper used by every other chapter in the
manuscript. Codex's subsection introduces one new pattern (`.callout` with an `h3` and a
distinct "A Contributed Recipe" label, styled `background:#eef2f4` to read as visually
distinct from a marginalia `.callout`) — this is intentional, since Part II is the first
chapter with a lead/contributor split rather than a single byline, and Task 3 Step 2
explicitly checks that Codex's fragment is NOT wrapped in its own `<chapter>` tag to avoid
it being misread as a sibling chapter. Both dispatch commands specify
`--force-agent --context-mode full` consistently with the prior slice's convention; Agy's
command additionally carries `--grant "run:shell"` per the same requirement documented in
the prior plan.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-30-book-multiauthor-part2-onboarding-slice.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch each content task in sequence via `synlynk dispatch` as written above, reviewing the fragment file after each before proceeding, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints for review.

Which approach?
