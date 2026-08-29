# "The Supervised Machine" — Part 0 + Part I Multi-Author Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **This plan's tasks are content-authorship dispatches, not code tasks — each "implementer" step is a `synlynk dispatch` call to a specific harness, not inline code by whoever executes this plan.**

**Goal:** Insert the new Part 0 (The Reckoning) and Part I (What This Actually Is — three chapters) into `docs/book/the-supervised-machine-v0.2-DRAFT.html`, plus the "How to Read This Book" front-matter segment map, each chapter drafted by the specific co-author assigned lead in the approved design doc, with the manuscript's existing dialogue-box/marginalia CSS pattern extended per the design's hard rule (real disagreement or cited incident only).

**Architecture:** New content is dispatched — one `synlynk dispatch` call per chapter to that chapter's lead harness (Grok, Claude, or Agy per the ownership map), each producing a self-contained HTML fragment inserted at a named anchor in the existing manuscript. A final Claude-direct (undispatched) consistency-review pass reconciles voice/terminology across the four new chapters and the front-matter, followed by a PDF rebuild and README version bump to v0.3-DRAFT. Parts II–IV and the renumbering of the existing Part One–Four content into the new Part III "Field Notebook" framing are explicitly **out of scope** — this plan only adds new front content; it does not touch or renumber any existing chapter, per the design doc's own statement that the full table of contents is follow-on planning work.

**Tech Stack:** Single-file self-contained HTML manuscript (inline CSS, no build step), Google Chrome headless for PDF rendering, `synlynk dispatch` for content authorship, `git`/`gh` for branch and PR flow.

---

## Current Manuscript State (grounded 2026-08-29, HEAD `6321063`)

`docs/book/the-supervised-machine-v0.2-DRAFT.html` is 679 lines. Confirmed structure via
`grep -n '<h1\|<h2\|<h3'`:

- Line 114: `<h1>The Supervised Machine</h1>` (cover)
- Line 121: `<h2>Preface to Draft v0.2</h2>` (front-matter, ends before line 126)
- Line 126: `<h2 class="glossary">Glossary</h2>` (front-matter, `<dl>` of terms, closes before line 154)
- Line 154: `<h2 style="font-size:18pt;">Contents</h2>` (TOC, `.toc-part`/`.toc-entry` divs, closes before line 184)
- Line 184: Prologue chapter, `<h2 class="chap-title">The Gap Between Neurons</h2>`, closes at `</chapter>` before line 208
- Line 208: `<h1>The Eras of Software</h1>` — existing "Part One" divider (`.part-divider`), followed by 3 chapters (lines 214, 230, 244)
- Line 256: `<h1>synlynk, In Parallel</h1>` — existing "Part Two", 7 chapters (lines 262–383)
- Line 410: `<h1>Fleet Notebook</h1>` — existing "Part Three", 3 chapters (lines 416–508)
- Line 534: `<h1>Layers, Dynamics, and What Comes Next</h1>` — existing "Part Four", 5 chapters + Notes (lines 540–669)

None of this existing content is touched by this plan.

**Relevant existing CSS classes (all already defined in the `<style>` block, do not redefine):**

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

Existing dialogue-box markup pattern (from line 282, reuse exactly):

```html
<div class="line"><span class="who human">Nikhil:</span> ...</div>
<div class="line"><span class="who grok">Grok</span> (dispatched to review): ...</div>
```

`.callout` is defined in CSS but has zero usages in the current body — this plan is the first to use it, for the "How to Read This Book" segment map and for marginalia blocks.

**Marginalia hard rule (from design doc Section 3), encoded as a concrete HTML pattern this plan uses everywhere:**

```html
<div class="callout">
<div class="callout-label">Marginalia — Grok</div>
<p>[Must either contradict the lead author's adjacent paragraph, or cite a specific
issue/LIVE-N/PR number. No purely reactive/color-commentary text.]</p>
</div>
```

---

## Task 1: Front-matter — "How to Read This Book" segment map

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.2-DRAFT.html:121-125` (insert a new front-matter section immediately after the existing Preface `</div>` and before the Glossary `<h2 class="glossary">` at line 126)

- [ ] **Step 1: Read the exact current boundary**

Run: `sed -n '118,127p' docs/book/the-supervised-machine-v0.2-DRAFT.html`

Expected output (confirm before editing — if it drifts from this, stop and re-read the file, do not blind-insert):

```
</div>

<div class="front-matter">
<h2>Preface to Draft v0.2</h2>
<p>This draft adds a full field notebook...</p>
...
</div>

<h2 class="glossary">Glossary</h2>
```

- [ ] **Step 2: Insert the segment map as a new `.front-matter` block**

Insert immediately after the Preface's closing `</div>` (the one that closes the `<div class="front-matter">` opened at line 120) and before `<h2 class="glossary">Glossary</h2>`:

```html
<div class="front-matter">
<h2>How to Read This Book</h2>
<p>This book is written to be read start to finish, but it does not require that. If one of the descriptions below sounds like you, skip to where it says — you will lose nothing you need for the parts you do read.</p>
<div class="callout">
<div class="callout-label">Find your entry point</div>
<p><b>Skeptical this is real, or worth your time:</b> start at Part 0. It is written for you first, not last.</p>
<p><b>Never used an AI tool for anything serious, or lost work/hours to one going wrong:</b> Part 0, then Part II directly — the recipes assume no prior comfort.</p>
<p><b>Already use AI tools daily and want the "why," not another tutorial:</b> Part I, then skim Part II for anything you haven't tried.</p>
<p><b>Build software professionally:</b> Part I for the framing, then Part III's field notebook is written for you specifically — dated incidents, not abstractions.</p>
<p><b>Manage people or budgets who will be affected by this:</b> Part I, then Part IV — the operational detail in Part III is optional context, not required reading.</p>
<p><b>Already sold, want the philosophical case:</b> Part IV can be read first; the rest will still make sense read out of order.</p>
</div>
</div>

```

- [ ] **Step 3: Verify the HTML is well-formed**

Run: `python3 -c "import html.parser; p = html.parser.HTMLParser(); p.feed(open('docs/book/the-supervised-machine-v0.2-DRAFT.html').read()); print('parsed OK')"`

Expected: `parsed OK` (this is a lenient parser — it will not catch every issue, but will catch unclosed tags/basic malformation). Also run: `grep -c '<div' docs/book/the-supervised-machine-v0.2-DRAFT.html` and `grep -c '</div>' docs/book/the-supervised-machine-v0.2-DRAFT.html` — the two counts must match (they matched before this edit; confirm they still match after).

- [ ] **Step 4: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
git add docs/book/the-supervised-machine-v0.2-DRAFT.html
git commit -m "docs(book): add How to Read This Book segment map to front matter"
```

This task is small enough to do directly (Claude, or whoever is executing this plan) — it is a mechanical front-matter insertion using content already fully specified above, not original chapter authorship, so it does not need a content dispatch.

---

## Task 2: Dispatch Grok — Part 0 chapter ("The Reckoning")

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.2-DRAFT.html` — insert a new `.part-divider` + `<chapter>` block immediately before the existing Prologue chapter (before line 184's `<chapter>` opening tag, i.e. immediately after the TOC's closing `</div>` which closes the `.toc-page` div opened at line 153/154 — re-locate this exact line number after Task 1's edit shifts line numbers by +18)

- [ ] **Step 1: Locate the exact current insertion anchor after Task 1's edit**

Run: `grep -n 'toc-page\|<chapter>' docs/book/the-supervised-machine-v0.2-DRAFT.html | head -5`

The new chapter goes immediately after the line containing the `.toc-page` div's closing `</div>` and immediately before the first `<chapter>` line (the Prologue). Confirm both line numbers before editing.

- [ ] **Step 2: Also update the TOC to add the new Part 0 entry**

In the same edit pass, insert into the `<div class="toc-page">` block (added in Task 1's neighborhood, now shifted — re-`grep -n 'toc-part\|Prologue'` to confirm), immediately before the existing `<div class="toc-entry"><span class="t">Prologue — The Gap Between Neurons</span></div>` line:

```html
<div class="toc-part">Part 0 — The Reckoning</div>
<div class="toc-entry"><span class="t">Panic as a User-Interface Bug</span></div>
```

- [ ] **Step 3: Dispatch the chapter draft to Grok**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch grok \
  --force-agent \
  --context-mode full \
  --task "$(cat <<'PROMPT'
Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is Part 0 of a
repositioned nonfiction book ("The Supervised Machine") about human-AI
collaboration for a general audience. You are the bylined author of this
chapter — write in your own voice, as established in this manuscript's
existing .who.grok dialogue lines (dry, blunt, grounded in real operational
incidents, no hedging).

CONTEXT: You already pitched this chapter in an editorial consultation:
"a Reckoning chapter on panic as a user-interface bug. Denial and fear are
not moral failings; they are what a brain does when a new tool is sold as a
person. I want the chapter that laughs *with* the denier, then shows the
tell: if it were a god, it would not need a sandbox, a worktree, a receipt,
and a human with merge authority. Humor here is diagnostic, not a roast."
Write the actual chapter delivering on that pitch.

REQUIREMENTS:
- Output ONLY the HTML fragment for this one chapter, ready to paste
  directly into the manuscript. Do not include <html>/<head>/<body> tags,
  do not include the surrounding part-divider (that is handled separately).
- Wrap the chapter in exactly this structure (matching the manuscript's
  existing chapter markup, e.g. the Prologue chapter at line ~184 of the
  current file — read that file first to match voice, length, and format
  before writing):
  <chapter>
  <div class="chap-label">Part 0</div>
  <h2 class="chap-title">Panic as a User-Interface Bug</h2>
  <div class="chap-dek">[one-line dek, your own words]</div>
  [your prose, using <p> tags, roughly 900-1400 words — match the existing
  chapters' length and density, do not pad]
  </chapter>
- This chapter must disarm denial/fear with humor while being genuinely
  funny, not mean — it addresses deniers and the fearful directly, it is
  the very first thing a reader encounters after the front matter.
- Do not fabricate incidents. If you reference a specific synlynk failure
  or LIVE issue as evidence, it must be a real one you can name (grep the
  repo's issues/LIVE-N docs first) — do not invent plausible-sounding ones.
- Save your output to a new file at docs/book/fragments/part0-reckoning.html
  in this worktree (create the docs/book/fragments/ directory if it does
  not exist) rather than editing the manuscript file directly — a
  consistency-review pass will merge it in.
- Commit the new fragment file to the current branch
  (docs/book-multiauthor-repositioning-design) with message
  "docs(book): draft Part 0 chapter (Grok)" and push.
PROMPT
)"
```

- [ ] **Step 4: Confirm the dispatch produced the fragment**

Run: `ls -la docs/book/fragments/part0-reckoning.html && wc -w docs/book/fragments/part0-reckoning.html`

Expected: file exists, word count roughly 900-1600 (chapter prose + markup). Do not trust the dispatch job's own printed "success" summary alone — per this project's standing verification discipline, open the file and read it.

- [ ] **Step 5: If the job reports BLOCKED, NEEDS_CONTEXT, or produces no file**

Re-dispatch once with the same command, adding to the end of the `--task` string: `"Your previous attempt did not produce docs/book/fragments/part0-reckoning.html. Produce it now, following the exact requirements above."` If a second attempt also fails, stop and escalate — do not fall back to writing this chapter inline (that would violate the design doc's dispatch-based authorship model), report to Nikhil instead.

---

## Task 3: Dispatch Claude — Part I chapter 1 ("Why This Is a Cognitive Tool, Not Magic")

**Files:**
- Create (via dispatch): `docs/book/fragments/part1-ch1-cognitive-tool.html`

- [ ] **Step 1: Dispatch the chapter draft to Claude**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch claude \
  --force-agent \
  --context-mode full \
  --task "$(cat <<'PROMPT'
Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is the first chapter
of Part I ("What This Actually Is") of a repositioned nonfiction book
("The Supervised Machine") about human-AI collaboration for a general
audience. You are the bylined author of this chapter, writing in your own
voice as established in this manuscript's existing .who.claude dialogue
lines and the manuscript's existing prose register (precise, willing to
correct an overclaim mid-sentence, argues from inside the reviewer's own
seat rather than from outside).

CONTEXT: You already pitched this chapter in an editorial consultation:
"Part I's cognitive-tool framing (I can argue for it without hype, because
my day job in this project is literally saying no to my own code)."
Write the actual chapter delivering on that pitch: make the case that AI
assistance is a cognitive tool, not magic and not a person, argued from the
position of someone whose actual job is reviewing and often rejecting AI
output, not evangelizing it.

REQUIREMENTS:
- Output ONLY the HTML fragment for this one chapter, ready to paste
  directly into the manuscript. Do not include <html>/<head>/<body> tags.
- Wrap the chapter in exactly this structure (read the manuscript's
  existing chapters first, e.g. the three chapters under the current
  "Part One — The Eras of Software" heading, to match voice, length, and
  format before writing):
  <chapter>
  <div class="chap-label">Part I, Chapter One</div>
  <h2 class="chap-title">Why This Is a Cognitive Tool, Not Magic</h2>
  <div class="chap-dek">[one-line dek, your own words]</div>
  [your prose, using <p> tags, roughly 900-1400 words]
  </chapter>
- Do not fabricate incidents or metrics. Any specific claim about synlynk's
  own behavior must be verifiable against this repo's real history (grep
  code, issues, project-docs/decisions/ first).
- Save your output to docs/book/fragments/part1-ch1-cognitive-tool.html
  in this worktree (create docs/book/fragments/ if it does not exist).
- Commit to branch docs/book-multiauthor-repositioning-design with message
  "docs(book): draft Part I ch.1 cognitive-tool chapter (Claude)" and push.
PROMPT
)"
```

- [ ] **Step 2: Confirm the fragment exists**

Run: `ls -la docs/book/fragments/part1-ch1-cognitive-tool.html && wc -w docs/book/fragments/part1-ch1-cognitive-tool.html`

Same BLOCKED/retry handling as Task 2 Step 5, substituted for this file/chapter.

---

## Task 4: Dispatch Grok — Part I chapter 2 ("Power Tools Have Kickback")

**Files:**
- Create (via dispatch): `docs/book/fragments/part1-ch2-kickback.html`

- [ ] **Step 1: Dispatch the chapter draft to Grok**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch grok \
  --force-agent \
  --context-mode full \
  --task "$(cat <<'PROMPT'
Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is the second
chapter of Part I ("What This Actually Is") of a repositioned nonfiction
book ("The Supervised Machine"). You are the bylined author, in your own
established voice (see Task 2's chapter for tone reference, and this
manuscript's .who.grok dialogue lines).

CONTEXT: You already pitched this chapter: "the mechanical framing: agent
vs harness, dispatch vs chat, provenance, capability routing, ground-truth
vs self-report. This is the chapter that kills the chatbot metaphor. A
circular saw does not 'understand wood.' It *cuts*. The skill is jigs,
fences, and not putting your hand in the blade. That is supervision."
Write the actual chapter delivering on that pitch — explain the
agent/harness distinction and the "don't trust self-report" discipline
using real, concrete synlynk mechanisms (policy.json, capability routing,
telemetry) as illustrations, translated for a general reader who has never
heard the word "harness" used this way.

REQUIREMENTS:
- Output ONLY the HTML fragment for this one chapter, ready to paste
  directly into the manuscript. Do not include <html>/<head>/<body> tags.
- Wrap in:
  <chapter>
  <div class="chap-label">Part I, Chapter Two</div>
  <h2 class="chap-title">Power Tools Have Kickback</h2>
  <div class="chap-dek">[one-line dek, your own words]</div>
  [your prose, using <p> tags, roughly 900-1400 words]
  </chapter>
- This chapter follows Claude's "Why This Is a Cognitive Tool, Not Magic"
  chapter (Task 3) in reading order — do not repeat its argument, extend
  it into the mechanical/practical layer.
- Do not fabricate incidents or metrics; verify against the real repo.
- Save output to docs/book/fragments/part1-ch2-kickback.html in this
  worktree.
- Commit to branch docs/book-multiauthor-repositioning-design with message
  "docs(book): draft Part I ch.2 kickback chapter (Grok)" and push.
PROMPT
)"
```

- [ ] **Step 2: Confirm the fragment exists**

Run: `ls -la docs/book/fragments/part1-ch2-kickback.html && wc -w docs/book/fragments/part1-ch2-kickback.html`

Same BLOCKED/retry handling as Task 2 Step 5.

---

## Task 5: Dispatch Agy — Part I chapter 3 ("Context & Working Memory")

**Files:**
- Create (via dispatch): `docs/book/fragments/part1-ch3-context-memory.html`

- [ ] **Step 1: Dispatch the chapter draft to Agy**

Run:

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
python3 /Users/nikhilsoman/dev/synlynk/bin/synlynk.py dispatch agy \
  --force-agent \
  --context-mode full \
  --grant "run:shell" \
  --task "$(cat <<'PROMPT'
Write one new book chapter, as an HTML fragment, for the manuscript at
docs/book/the-supervised-machine-v0.2-DRAFT.html. This is the third
chapter of Part I ("What This Actually Is") of a repositioned nonfiction
book ("The Supervised Machine"). You are the bylined author, in your own
voice (see this manuscript's .who.agy dialogue lines for tone reference).

CONTEXT: You already pitched this chapter: "the high-volume context trench
where human intent actually gets hammered into reliable reality across
massive context windows... the unsparing, pragmatic field manual that
drags readers out of the 500-token prompt-box mindset and hands them the
blueprint for building a persistent, multi-file cognitive assembly line
that doesn't hallucinate or collapse on Tuesday." Write the actual chapter
delivering on that pitch — explain what "context" means for an AI system
in terms a general reader can use immediately (why a fresh chat forgets
everything, what a persistent working-memory file actually buys you), using
concrete examples from your own strengths (large context, multimodal,
search-augmented) as illustration.

REQUIREMENTS:
- Output ONLY the HTML fragment for this one chapter, ready to paste
  directly into the manuscript. Do not include <html>/<head>/<body> tags.
- Wrap in:
  <chapter>
  <div class="chap-label">Part I, Chapter Three</div>
  <h2 class="chap-title">Context & Working Memory</h2>
  <div class="chap-dek">[one-line dek, your own words]</div>
  [your prose, using <p> tags, roughly 900-1400 words]
  </chapter>
- This is the closing chapter of Part I, following Claude's and Grok's
  chapters (Tasks 3-4) — it should feel like a capstone, not a third
  parallel argument; briefly acknowledge the prior two chapters'
  arguments before extending into the context/memory dimension.
- Do not fabricate incidents or metrics; verify against the real repo.
- Save output to docs/book/fragments/part1-ch3-context-memory.html in
  this worktree.
- Commit to branch docs/book-multiauthor-repositioning-design with message
  "docs(book): draft Part I ch.3 context/memory chapter (Agy)" and push.
PROMPT
)"
```

Note: `--grant "run:shell"` is included because Agy's default org-role permission set for
a "content" task does not include `run:shell` by default (see
`synlynk/_constants.py` `_ROLE_PERMISSION_DEFAULTS["content"]`, which grants
`read:*`/`write:src/`/`write:docs/` but not `run:shell`), and this task needs Agy to run
`git commit`/`git push` itself per the requirements above. If the dispatch fails on a
permission-denial for the commit/push step specifically, this is the fix — the flag is
already included above, so no separate corrective task should be needed, but note it here
in case the underlying role defaults have changed since this plan was written.

- [ ] **Step 2: Confirm the fragment exists**

Run: `ls -la docs/book/fragments/part1-ch3-context-memory.html && wc -w docs/book/fragments/part1-ch3-context-memory.html`

Same BLOCKED/retry handling as Task 2 Step 5. If Agy fails twice (matching this session's
prior experience with Agy headless/permission errors — see
`memory/feedback_prefer_codex_grok_over_agy.md` and the earlier same-session Agy retry that
needed `--dangerously-skip-permissions`), do not silently substitute another harness for
Agy's chapter — Agy is the design doc's named lead for this chapter specifically because of
her established voice; escalate to Nikhil instead of reassigning.

---

## Task 6: Claude-direct — merge fragments, add marginalia, final consistency review

**This step is explicitly NOT dispatched — Claude does this directly, per the design doc
and the writing-plans dispatch note above; this is PM/review work, not primary content
authorship.**

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.2-DRAFT.html`
- Read: `docs/book/fragments/part0-reckoning.html`, `docs/book/fragments/part1-ch1-cognitive-tool.html`, `docs/book/fragments/part1-ch2-kickback.html`, `docs/book/fragments/part1-ch3-context-memory.html`

- [ ] **Step 1: Read all four fragments in full**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
cat docs/book/fragments/part0-reckoning.html
cat docs/book/fragments/part1-ch1-cognitive-tool.html
cat docs/book/fragments/part1-ch2-kickback.html
cat docs/book/fragments/part1-ch3-context-memory.html
```

- [ ] **Step 2: Check each fragment against the marginalia hard rule and voice consistency**

For each fragment, confirm:
- No fabricated incident/issue/PR references — spot-check any cited number against
  `gh issue view <N>` or `git log --oneline | grep <N>` before trusting it.
- Word count in the 900-1600 range (chapters padded well past this or suspiciously short
  should be flagged, not silently accepted).
- Uses `<chapter>`/`<div class="chap-label">`/`<h2 class="chap-title">`/`<div class="chap-dek">`
  markup exactly as specified in each dispatch prompt — fix formatting drift directly
  rather than re-dispatching for a markup-only issue.

- [ ] **Step 3: Insert Part 0 with its part-divider, before the Prologue**

Re-locate the exact current insertion point with `grep -n '<chapter>' docs/book/the-supervised-machine-v0.2-DRAFT.html | head -1` (should still be the Prologue's opening tag, since Task 1/2 only touched front-matter/TOC). Insert immediately before it:

```html
<div class="part-divider">
  <div class="part-label">Part 0</div>
  <h1>The Reckoning</h1>
  <div class="part-sub">A note to the reader who isn't sure this book is for them, or isn't sure any of this is real</div>
</div>

[contents of docs/book/fragments/part0-reckoning.html, minus its own outer <chapter> if the fragment happens to double-wrap — verify no duplicate <chapter> tags before inserting]

```

- [ ] **Step 4: Insert Part I with its part-divider and three chapters, immediately after Part 0's chapter and before the existing Prologue**

```html
<div class="part-divider">
  <div class="part-label">Part I</div>
  <h1>What This Actually Is</h1>
  <div class="part-sub">Three ways of naming the same thing precisely enough to stop being afraid of it or worshipping it</div>
</div>

[contents of docs/book/fragments/part1-ch1-cognitive-tool.html]

[contents of docs/book/fragments/part1-ch2-kickback.html]

[contents of docs/book/fragments/part1-ch3-context-memory.html]

```

- [ ] **Step 5: Add cross-chapter marginalia per the hard rule**

Add exactly one marginalia callout to each of the four new chapters, from a co-author who
did not lead that chapter, following the pattern defined at the top of this plan. Each
marginalia note must either contradict the lead author's own text or cite a real,
verifiable incident. Concretely, based on the panel consultation record already on file in
the design doc:

In `part0-reckoning.html`'s inserted content, near its closing `<p>`, insert:

```html
<div class="callout">
<div class="callout-label">Marginalia — Agy</div>
<p>Grok is right that panic is a UI bug, but watch the next three parts for the fix landing too fast: Part II is going to ask you to trust a process before you've seen it survive a bad day. If Part 0 talks you out of fear and Part III doesn't show you a real failure, you were sold reassurance, not evidence.</p>
</div>
```

In `part1-ch1-cognitive-tool.html`'s inserted content, near its closing `<p>`, insert:

```html
<div class="callout">
<div class="callout-label">Marginalia — Grok</div>
<p>Claude's "not magic" case is correct and still too gentle. A circular saw with no fence still cuts your hand off "as designed" — the entire reason synlynk has a policy.json and a capability baseline is that "cognitive tool, not magic" was never sufficient on its own; it took real incidents (a Grok job silently no-op'ing with exit 0, see the fleet's own #(cite the actual issue number for the Grok gh-write silent no-op incident, confirmed via gh issue search before publishing)) before the fences got built.</p>
</div>
```

**Before finalizing this specific marginalia note**, run `gh issue list --search "grok no-op silent"` or equivalent in the main repo (not this worktree, to search full issue history) and substitute the real issue number — do not publish a placeholder citation. If no exact matching issue is found, rewrite the note to cite whichever real incident (e.g. the `#426` GitHub write-identity hardening finding, already documented in this project's CLAUDE.md "GitHub write routing" section) is accurate, rather than leaving an approximate one in.

In `part1-ch2-kickback.html`'s inserted content, near its closing `<p>`, insert:

```html
<div class="callout">
<div class="callout-label">Marginalia — Codex</div>
<p>Worth being precise about "kickback" here: my own sandbox denies network egress to api.github.com by design, not by accident — that's not a bug the fleet tolerates, it's a fence Grok's chapter is describing correctly. The failure mode isn't the fence; it's routing a GitHub-write task to a harness whose fence blocks it and trusting the "OK" exit code anyway.</p>
</div>
```

In `part1-ch3-context-memory.html`'s inserted content, near its closing `<p>`, insert:

```html
<div class="callout">
<div class="callout-label">Marginalia — Claude</div>
<p>Agy's context-trench framing is right, and it's also the reason this manuscript itself almost drifted: three sessions in, a summarized-context restart nearly lost the "run generational per-harness" requirement from an earlier instruction entirely — caught only because the requirement had already been written into a memory file, not because context "just worked." The blueprint Agy describes needs an external record, not just a bigger window.</p>
</div>
```

- [ ] **Step 6: Verify HTML validity and TOC/anchor consistency**

Run: `python3 -c "import html.parser; p = html.parser.HTMLParser(); p.feed(open('docs/book/the-supervised-machine-v0.2-DRAFT.html').read()); print('parsed OK')"`

Run: `grep -c '<div' docs/book/the-supervised-machine-v0.2-DRAFT.html` and `grep -c '</div>' docs/book/the-supervised-machine-v0.2-DRAFT.html` — must match.

Run: `grep -n '<h1>\|<h2 class="chap-title">' docs/book/the-supervised-machine-v0.2-DRAFT.html` and confirm reading order is: Part 0 divider → Part 0 chapter → Part I divider → 3 Part I chapters → (existing) Prologue → (existing) Part One "The Eras of Software" → ... unchanged.

- [ ] **Step 7: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
git add docs/book/the-supervised-machine-v0.2-DRAFT.html
git commit -m "docs(book): merge Part 0 + Part I chapters into manuscript with cross-author marginalia"
```

---

## Task 7: PDF rebuild + README version bump to v0.3-DRAFT

**Files:**
- Rename: `docs/book/the-supervised-machine-v0.2-DRAFT.html` → `docs/book/the-supervised-machine-v0.3-DRAFT.html`
- Rename: `docs/book/the-supervised-machine-v0.2-DRAFT.pdf` → `docs/book/the-supervised-machine-v0.3-DRAFT.pdf` (regenerated, not just renamed)
- Modify: `docs/book/README.md`
- Modify: cover/preface version strings inside the renamed HTML file

- [ ] **Step 1: Rename the HTML file**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
git mv docs/book/the-supervised-machine-v0.2-DRAFT.html docs/book/the-supervised-machine-v0.3-DRAFT.html
```

- [ ] **Step 2: Update the version strings inside the HTML**

Run: `grep -n 'v0.2\|Draft v0.2' docs/book/the-supervised-machine-v0.3-DRAFT.html`

Replace each occurrence of `v0.2`/`Draft v0.2` with `v0.3`/`Draft v0.3`. Specifically:
- Cover `.ed` div: `DRAFT v0.2 — Not Publish-Ready — August 2026` → `DRAFT v0.3 — Not Publish-Ready — August 2026`
- Preface `<h2>Preface to Draft v0.2</h2>` → `<h2>Preface to Draft v0.3</h2>`, and update the preface's own prose to describe this draft's actual change (the Part 0/Part I addition and the multi-author byline model), not v0.2's field-notebook addition. Replace the existing `<p>` paragraphs under this heading with:

```html
<p>This draft adds Part 0 ("The Reckoning") and Part I ("What This Actually Is"), the first chapters written under this manuscript's new multi-author model: Claude, Codex, Grok, and Agy each lead the chapters that fit their own established voice, credited by name, with cross-chapter marginalia carrying real disagreement rather than color commentary. The full editorial rationale — including a live four-model consultation on chapter ownership and title — is recorded at <code>docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md</code>.</p>
<p>Parts II through IV of the repositioned structure (The Onboarding, Field Notebook, What This Means) are not yet drafted under the new model — this draft's existing Parts One through Four remain in their prior engineering-memoir framing until that work lands in a future version.</p>
```

- [ ] **Step 3: Rebuild the PDF**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/book/the-supervised-machine-v0.3-DRAFT.pdf \
  "file://$(pwd)/docs/book/the-supervised-machine-v0.3-DRAFT.html"
git rm docs/book/the-supervised-machine-v0.2-DRAFT.pdf
```

Expected: `docs/book/the-supervised-machine-v0.3-DRAFT.pdf` exists and is non-empty
(`ls -la docs/book/the-supervised-machine-v0.3-DRAFT.pdf`).

- [ ] **Step 4: Update README.md**

Modify `docs/book/README.md`:
- Replace both `v0.2-DRAFT` filename references with `v0.3-DRAFT` (Files section).
- Replace the `--print-to-pdf` command block's filenames with `v0.3-DRAFT`.
- Add a new bullet under "## Editorial history" (after the existing 2026-08-29 editorial-panel-review bullet):

```markdown
This draft also incorporates the first chapters written under the multi-author
repositioning: see `docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md`
for the chapter-ownership map and the live claude/codex/grok/agy consultation this design
was based on.
```

- [ ] **Step 5: Commit**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
git add docs/book/the-supervised-machine-v0.3-DRAFT.html docs/book/the-supervised-machine-v0.3-DRAFT.pdf docs/book/README.md
git status --short
git commit -m "docs(book): bump to v0.3-DRAFT, rebuild PDF, update README for multi-author chapters"
git push
```

- [ ] **Step 6: Open the PR**

```bash
cd /Users/nikhilsoman/dev/synlynk/worktrees/docs+book-multiauthor-repositioning-design
gh pr create --title "docs(book): Part 0 + Part I multi-author chapters, v0.3-DRAFT" --body "$(cat <<'EOF'
## Summary
- Adds Part 0 ("The Reckoning") and Part I ("What This Actually Is", 3 chapters) to the manuscript, per the approved design at docs/superpowers/specs/2026-08-29-book-multiauthor-repositioning-design.md
- Each chapter drafted by its assigned lead co-author via `synlynk dispatch` (Grok: Part 0 + Part I ch.2; Claude: Part I ch.1; Agy: Part I ch.3), with cross-chapter marginalia carrying real disagreement or cited incidents per the design's hard rule
- Adds "How to Read This Book" front-matter segment map
- Bumps manuscript to v0.3-DRAFT, rebuilds PDF, updates README

## Test plan
- [ ] HTML parses cleanly (`html.parser` smoke test) and div/closing-div counts match
- [ ] PDF renders without error and opens correctly
- [ ] All marginalia citations verified against real issues/PRs (no placeholder citations)
- [ ] Existing Parts One–Four (untouched) still render identically — diff shows only additive changes to front-matter/TOC + new Part 0/Part I content
EOF
)"
```

---

## Self-Review

**1. Spec coverage:** Design doc Section 2 (scope pivot) → Task 6/7 preface text documents it; Section 3 (marginalia hard rule) → encoded as the reusable pattern at the top of this plan and applied concretely in Task 6 Step 5; Section 4 (chapter ownership for Part 0/Part I only) → Tasks 2-5 dispatch each chapter to its exact assigned lead; Section 6 (title) → not touched by this slice, correctly out of scope (cover title/subtitle change is a separate, larger decision affecting the whole book, not bundled into a partial-chapter PR); Section 7 open items (front-matter segment map) → Task 1; (voice sample gap) → flagged again in Task 6 Step 2 as an ongoing constraint, not resolved by this plan. Parts II-IV and full ToC renumbering are explicitly out of scope per the design doc's own "Open Items" — correctly excluded here.

**2. Placeholder scan:** The one item that looks placeholder-like — the marginalia note in Task 6 Step 5 referencing "(cite the actual issue number...)" — is intentional and flagged as a required verification step immediately below it, not a plan gap; the task explicitly requires resolving it against real `gh issue` data before publishing, with a named fallback citation (`#426`) if no exact match is found. This is a verification instruction, not an unresolved TODO left for later.

**3. Type/format consistency:** All four dispatched chapters use the identical `<chapter>` / `.chap-label` / `.chap-title` / `.chap-dek` wrapper (matches existing manuscript markup, confirmed against the real file's Prologue and Part One chapters). All four dispatch commands specify `--force-agent --context-mode full` consistently. Marginalia blocks all use the same `.callout` / `.callout-label` pattern defined once at the top and reused verbatim in Task 6.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-29-book-multiauthor-part0-part1-slice.md`. Two execution options:

**1. Subagent-Driven (recommended)** — dispatch each content task in sequence via `synlynk dispatch` as written above, reviewing the fragment file after each before proceeding, fast iteration.

**2. Inline Execution** — execute tasks in this session using executing-plans, batch execution with checkpoints for review.

Which approach?
