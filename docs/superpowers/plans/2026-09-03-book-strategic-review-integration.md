# Strategic Review Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **This is book-manuscript content work, not code** — there are no automated tests. Every "Verify" step is editorial: a `grep -n` for exact anchor text confirming the edit landed where intended, plus a prose read-through for tone/continuity. Every "Write content" step's actual prose is authored live by Claude at execution time (per this project's book-authorship carve-out — Claude writes book prose directly, unlike code, which is dispatched) — but the step below specifies every fact, quote, figure, and structural beat the prose MUST include, so nothing is invented and nothing is left to guesswork.

**Goal:** Integrate the approved Strategic Review content into `docs/book/the-supervised-machine-v0.5-DRAFT.html`: a new Part Two "Neutral Layer" chapter, deep-dive expansions of the rxcc and cc-videoreframing chapters (including the LIVE-5/#99 correction), expansions of Ch.16 and Ch.18, a new Part Four "Three Positions in the Sun" chapter, three embedded Stitch mockups in the rxcc chapter, and all resulting TOC/renumbering updates — per `docs/superpowers/specs/2026-09-03-book-strategic-review-integration-design.md` (Approved).

**Architecture:** All work lands in one file, `docs/book/the-supervised-machine-v0.5-DRAFT.html`, edited task-by-task via anchored `Edit` calls against exact existing text (quoted verbatim below from the current file so no insertion point is ambiguous). New standalone chapter content is also saved to `docs/book/fragments/*.html`, matching the repo's existing fragment convention. Four Stitch screenshots are downloaded to `docs/book/assets/` and referenced by relative path. The PDF is regenerated once, at the end, from the final HTML.

**Tech Stack:** Static HTML/CSS (single file, inline styles, existing class vocabulary — `.chap-label`, `.chap-title`, `.chap-dek`, `.part-divider`, `.callout`, `.banter`, `.autonomy-box`, `.market-op`, `.primitive-contrast`, `.mapping-box`, `.pattern-box`). Chrome headless for PDF regeneration (see `docs/book/README.md`).

---

## Ordering rationale

Tasks are ordered top-to-bottom through the file so each edit's anchor text is still valid when the task runs (no task depends on a later task's insertion having already happened). Renumbering tasks (Ch.10→11, TOC) are placed immediately after the content insertion that necessitates them, not batched at the end, so the file is never left in a self-contradictory state between commits.

---

### Task 1: Correct LIVE-5/#99 framing in the Codex fact-check fragment file

**Files:**
- Modify: `docs/book/fragments/part3-codex-factcheck-notes.html`

The fragment file's cc-videoreframing callout (lines 7–11) still asserts the old "fabricated PTS, copied/shifted from source" framing as something Codex could only partially verify. Per spec Section 3b, the real root cause (confirmed against `docs/superpowers/specs/2026-08-03-live-5-timestamp-aware-verification-design.md`) is a variable-frame-rate source video where declared fps (24.917) disagreed with true per-frame timing by 7.6% against a 31.26s actual duration — the verifier trusted the wrong ground-truth clock, not a fabrication.

- [ ] **Step 1: Replace the cc-videoreframing fact-check callout**

Old text (verbatim, lines 7–11):
```html
<!-- targets: cc-videoreframing chapter -->
<div class="callout" style="background:#eef4ee;">
<div class="callout-label">Fact-Check — Codex</div>
<p>The exact claim is that issue #99 found the verifier fabricating output timestamps by copying the source timestamps and shifting them to zero, so a real encode could drift while verification reported confidence. I verified the issue’s existence and description in <code>project-docs/memory.md</code>, which calls #99 the “fabricated PTS correctness bug” and records it as an open gate for the cc-videoreframing/Vdowrx rollout. That repository-level record supports the defect characterization, but this checkout does not contain the sibling project’s source, issue body, or the cited <code>memory/live5-cc-videoreframing-verification-gap.md</code> file. I therefore cannot independently confirm the chapter’s finer implementation wording (“copied,” “shifted,” and the concat-demuxer assumption) beyond the project memory’s summary. The broad claim is supported; the detailed mechanism remains partially unverifiable here.</p>
</div>
```

New text:
```html
<!-- targets: cc-videoreframing chapter -->
<div class="callout" style="background:#eef4ee;">
<div class="callout-label">Fact-Check — Codex</div>
<p>The claim as it now stands in the chapter is that issue #99's root cause was a timing-comparison bug, not a fabrication bug: a variable-frame-rate source video whose declared frame rate (24.917 fps) disagreed with its true per-frame timing by 7.6% against a measured 31.26-second actual duration, so the verifier's confidence check was comparing rendered output against the wrong ground-truth clock. This supersedes an earlier draft of this chapter, which described the defect as the verifier fabricating output timestamps by copying and shifting the source's own timestamps — that framing is incorrect and has been removed. I verified the corrected framing against <code>docs/superpowers/specs/2026-08-03-live-5-timestamp-aware-verification-design.md</code>, which documents the VFR/declared-fps discrepancy and the 7.6% figure directly, and against <code>memory/live5-cc-videoreframing-verification-gap.md</code>, which records #99 as one of two root-caused gates (alongside #98, duration tolerance) opened after the design doc's investigation. The corrected mechanism is well-supported by this checkout's own design-doc evidence; the earlier "fabricated PTS" wording was carried over from an older project-memory summary that had not yet incorporated that investigation's findings.</p>
</div>
```

- [ ] **Step 2: Verify**

Run: `grep -n "timing-comparison bug" docs/book/fragments/part3-codex-factcheck-notes.html`
Expected: one match, inside the cc-videoreframing callout `<p>`.

Run: `grep -n "fabricating output timestamps by copying" docs/book/fragments/part3-codex-factcheck-notes.html`
Expected: no matches (old framing fully removed).

- [ ] **Step 3: Commit**

```bash
git add docs/book/fragments/part3-codex-factcheck-notes.html
git commit -m "docs: correct LIVE-5/#99 framing in Codex fact-check fragment

The verifier didn't fabricate timestamps — it compared against the
wrong ground-truth clock on a VFR source (declared 24.917fps vs
7.6% real-timing drift against 31.26s actual duration). Corrects
the fragment ahead of propagating the same fix into the manuscript."
```

---

### Task 2: Correct LIVE-5/#99 framing in the manuscript body and its inline Codex callout

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (lines ~742–791, Part III Chapter Two)

The manuscript's own cc-videoreframing chapter carries the same outdated framing inline, both in chapter prose (~line 773) and its embedded fact-check callout (~lines 775–778). This task corrects both, using the same corrected mechanism as Task 1, and does NOT touch anything else in this chapter (the CV pipeline deep-dive is Task 7, done separately after this correction so the two edits don't collide on the same region).

- [ ] **Step 1: Read the current exact text around line 773 to confirm it hasn't shifted**

Run: `grep -n "fabricated, copied from the source" docs/book/the-supervised-machine-v0.5-DRAFT.html`

Use the Read tool on the returned line number ± 5 lines to capture the exact surrounding sentence verbatim before editing (the summary's transcript excerpt is the best-available copy, but confirm against the live file since Task 1's fragment edit does not touch the manuscript).

- [ ] **Step 2: Replace the chapter-body sentence describing the bug**

Old text (verbatim, from prior conversation's confirmed read, ~line 773):
```
It was fabricated, copied from the source's own timestamps and shifted to start at zero, on the assumption that a crop/zoom re-encode followed by a concat-demuxer join would preserve exact timing
```

New text:
```
The verifier was checking against the wrong clock. The source video was variable-frame-rate, and its declared frame rate — 24.917 fps — disagreed with the file's true per-frame timing by 7.6%, measured against a real duration of 31.26 seconds. A crop/zoom re-encode followed by a concat-demuxer join preserves frame count faithfully; it does not preserve a declared-but-wrong frame rate's arithmetic. The verifier trusted the declared number, did the multiplication, and reported high confidence in a timeline that never matched the actual footage
```

Use Edit with enough surrounding context (the full sentence/paragraph) to make the `old_string` uniquely matched.

- [ ] **Step 3: Replace the inline Codex fact-check callout for this chapter**

Locate the callout immediately following the corrected sentence (originally ~lines 775–778) — it is the manuscript's own inline copy of the same block corrected in Task 1's fragment file, so use the same "New text" block from Task 1 Step 1 as the replacement content here (identical wording — the fragment and the manuscript inline copy must stay byte-identical per the repo's dual-write convention).

- [ ] **Step 4: Verify**

Run: `grep -n "wrong clock" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: at least one match in the cc-videoreframing chapter.

Run: `grep -n "fabricated, copied from the source" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: no matches.

Run: `diff <(sed -n '/targets: cc-videoreframing/,/<\/div>/p' docs/book/fragments/part3-codex-factcheck-notes.html) <(grep -A4 "Fact-Check — Codex" docs/book/the-supervised-machine-v0.5-DRAFT.html | sed -n '/timing-comparison bug/,/<\/p>/p')`
This is a soft check, not a hard gate — its purpose is a human diff-scan to confirm the two copies read the same; exact whitespace mismatches are fine, wording drift is not.

- [ ] **Step 5: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: correct LIVE-5/#99 framing in manuscript body + inline callout

Propagates the Task 1 fragment correction into the manuscript's own
cc-videoreframing chapter text and its embedded fact-check callout."
```

---

### Task 3: Download the four Stitch mockup images into `docs/book/assets/`

**Files:**
- Create: `docs/book/assets/rxcc-mockup-1.png` (or actual extension returned)
- Create: `docs/book/assets/rxcc-mockup-2.png`
- Create: `docs/book/assets/rxcc-mockup-3.png`
- Create: `docs/book/assets/rxcc-mockup-4.png`

Per spec Section 4, the rxcc chapter deep-dive (Task 6) embeds three of these four Stitch-generated screenshots (project ID `2056778402899642068`); the fourth is available as a spare/alternate in case one doesn't read well inline. The URLs are ephemeral Google-hosted download links already captured during the brainstorm phase — retrieve the current live URLs via the Stitch MCP tools rather than assuming the old ones are still valid.

- [ ] **Step 1: Re-list the project's screens to get current download URLs**

Load the Stitch tools if deferred: `ToolSearch({"query": "select:mcp__stitch__list_screens,mcp__stitch__get_screen", "max_results": 5})`

Call `mcp__stitch__list_screens` with `project_id: "2056778402899642068"`. Record each screen's id and current image URL.

- [ ] **Step 2: Download each screen image to the assets directory**

```bash
mkdir -p docs/book/assets
```

For each of the 4 screen URLs returned in Step 1, download with `curl -sL "<url>" -o docs/book/assets/rxcc-mockup-N.png` (N = 1..4, in the same order `list_screens` returned them). Confirm the file type with `file docs/book/assets/rxcc-mockup-N.png` — if Stitch returns a different format (e.g. `.webp`), rename the target file to match and use that extension consistently in Task 6's `<img>` tags.

- [ ] **Step 3: Verify**

Run: `ls -la docs/book/assets/`
Expected: 4 image files, each with nonzero size.

- [ ] **Step 4: Commit**

```bash
git add docs/book/assets/
git commit -m "docs: land Stitch rxcc mockup screenshots as static assets

Downloads the four Stitch-generated screenshots (project
2056778402899642068) from their ephemeral hosted URLs into a
version-controlled assets directory, ahead of embedding three of
them in the rxcc chapter deep-dive."
```

---

### Task 4: Insert the new Part Two "The Neutral Layer" chapter after Chapter Nine

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (insert after line 656, before line 658)
- Create: `docs/book/fragments/neutral-layer-chapter.html`

Per spec Section 2, this chapter has 5 structural parts: origin-story anecdote, economic reframe, BYOH thesis, four moats (with explicit cross-references), and a closing "Lightest Possible Touch" section. It becomes the new Chapter Ten; the existing Chapter Ten "The Long Arc" becomes Chapter Eleven (renumbered in Task 5).

- [ ] **Step 1: Write the chapter to the fragment file**

Write `docs/book/fragments/neutral-layer-chapter.html` containing exactly this structure (author full prose for each `<p>` at execution time — the bullets below are the required content, not the final wording):

```html
<chapter>
<div class="chap-label">Chapter Ten</div>
<h2 class="chap-title">The Neutral Layer</h2>
<div class="chap-dek">[write a one-sentence dek matching the existing dek register — see Ch.4–9 for tone/length precedent]</div>

<!-- Part 1: Origin-story anecdote -->
<p>[Open with the origin story: why synlynk exists as a wrapper/orchestration layer rather than a fork of any one AI CLI. Ground this in the project's actual founding motivation — the multi-harness (Claude/Agy/Grok/Codex) reality already established across Parts Two and Three, and the explicit bet against single-harness convergence already referenced in Ch.18's existing text ("its founding thesis, in Chapter Four, is explicitly a rejection of exactly this kind of single-winner framing"). Do not contradict that existing Ch.4/Ch.18 framing — this chapter's origin story must be consistent with it, elaborating rather than replacing it.]</p>

<!-- Part 2: Economic reframe -->
<p>[Reframe the harness-fleet economics already dramatized in Ch.15 "The War of the Harnesses" — four differently-priced, differently-reliable labor sources — as a market-structure argument: a neutral orchestration layer is valuable precisely because it lets a builder arbitrage across harnesses on cost/reliability/capability rather than being locked into one vendor's roadmap and pricing.]</p>

<!-- Part 3: BYOH thesis -->
<p>[State the BYOH — Bring Your Own Harness — thesis explicitly: synlynk does not compete with Claude, Codex, Grok, or Agy: it sits below all of them, agnostic to which one does the work, and its value is orthogonal to any single harness's capability curve. Distinguish this from a "we picked the best model" pitch.]</p>

<!-- Part 4: Four moats -->
<div class="pattern-box">
<div class="label">Four Moats of a Neutral Layer</div>
<p>[Moat 1 — cross-reference Part I Ch.3's working-memory argument (context injection as the mechanism that makes any harness usable across long-running work, tying back to the book's own "cognitive tool, not magic" framing from Ch.1)]</p>
<p>[Moat 2 — cross-reference Ch.9 "Capability Is Not Static" (the capability-baseline reassessment discipline itself is a moat: knowing which harness is currently good at what is proprietary, earned knowledge, not a static fact anyone can look up)]</p>
<p>[Moat 3 — cross-reference Part I Ch.2's agent/harness distinction, established by Grok's chapter (the Agent-vs-Harness terminology split itself is the moat: a role/charter model that survives any single harness being swapped out)]</p>
<p>[Moat 4 — local-first, Git-native governance (policy.json, telemetry.json, the whole governance-as-code apparatus from Ch.7, living in the user's own repo rather than a vendor's cloud — the moat is data gravity plus auditability, not lock-in)]</p>
</div>

<!-- Part 5: Closing — Lightest Possible Touch -->
<h3>The Lightest Possible Touch</h3>
<p>[State the featherlight-touch philosophy: the neutral layer's job is to inject context, track cost, enforce policy, and verify outcomes — and otherwise get out of the way. Forward-reference Part One Ch.1–3's eras-of-software argument (each era's winning layer did less than the era before assumed a winning layer had to do). Explicitly contrast this with the "Autonomous CTO/CAIO" positioning option that Part Four's new "Three Positions in the Sun" chapter (Task 8) will describe as one of three possible market positions — name it as the position this chapter's philosophy deliberately does NOT take, without fully re-litigating Task 8's argument here (a forward pointer, not a duplicate).]</p>

</chapter>
```

- [ ] **Step 2: Insert the fragment content into the manuscript**

Old text (verbatim, end of Chapter Nine, line 656):
```html
<p>None of these protocols exist in a static "done" state. Each is a recurring verb — sweep, verify, reassess, reconcile — not a one-time noun. An AI-native product is not built and then operated. It is built by being continuously operated, with the operating discipline itself as much a part of the product's real architecture as its code.</p>
</chapter>
```

New text: same old text, followed immediately by the full `<chapter>...</chapter>` block written in Step 1 (paste the finished fragment content in directly beneath the closing `</chapter>` of Chapter Nine).

- [ ] **Step 3: Verify**

Run: `grep -n "The Neutral Layer" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: at least one match (the new `<h2 class="chap-title">`).

Run: `grep -n "chap-label" docs/book/the-supervised-machine-v0.5-DRAFT.html | sed -n '1,20p'`
Read through manually to confirm "Chapter Ten" (new) appears once, directly before the OLD "Chapter Ten" label (still unrenumbered until Task 5) — i.e. there are momentarily two "Chapter Ten" labels in the file. This is expected and gets resolved in Task 5. Do not treat this as an error.

- [ ] **Step 4: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html docs/book/fragments/neutral-layer-chapter.html
git commit -m "docs: add Part Two Chapter Ten, The Neutral Layer

New chapter covering the origin story, economic reframe, BYOH
thesis, four moats (cross-referencing Ch.3/Ch.9/Grok's Ch.2/Ch.7),
and the featherlight-touch closing philosophy. Inserted after the
existing Chapter Nine, immediately before the existing Chapter Ten
(The Long Arc), which Task 5 renumbers to Chapter Eleven."
```

---

### Task 5: Renumber the existing Chapter Ten to Chapter Eleven

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html`

- [ ] **Step 1: Relabel the chapter**

Old text (verbatim):
```html
<div class="chap-label">Chapter Ten</div>
<h2 class="chap-title">The Long Arc — 1,000+ Pull Requests</h2>
```

New text:
```html
<div class="chap-label">Chapter Eleven</div>
<h2 class="chap-title">The Long Arc — 1,000+ Pull Requests</h2>
```

This is now unambiguous since Task 4's new chapter is the only OTHER "Chapter Ten" label, and it has a different `<h2 class="chap-title">` ("The Neutral Layer") — include both lines in the `old_string` so the Edit call matches only this occurrence.

- [ ] **Step 2: Verify**

Run: `grep -c "Chapter Ten" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: `1` (only the new Neutral Layer chapter remains labeled Chapter Ten).

Run: `grep -c "Chapter Eleven" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: renumber The Long Arc from Chapter Ten to Chapter Eleven

Displaced by the new Neutral Layer chapter inserted immediately
before it."
```

---

### Task 6: Update the Part Two TOC block for the new chapter and renumbering

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (TOC block, ~lines 185–192)

- [ ] **Step 1: Edit the TOC**

Old text (verbatim):
```html
<div class="toc-part">Part Two — synlynk, In Parallel</div>
<div class="toc-entry"><span class="t">4. The Polyglot Harness</span><span class="d">May–Jun 2026</span></div>
<div class="toc-entry"><span class="t">5. From Tool to Organization</span><span class="d">Jun–Aug 2026</span></div>
<div class="toc-entry"><span class="t">6. The Verification Tax</span><span class="d">Jul–Aug 2026</span></div>
<div class="toc-entry"><span class="t">7. Governance as Code</span><span class="d">Aug 2026</span></div>
<div class="toc-entry"><span class="t">8. The Autonomous Loop</span><span class="d">Aug 2026</span></div>
<div class="toc-entry"><span class="t">9. Capability Is Not Static</span><span class="d">Aug 25, 2026</span></div>
<div class="toc-entry"><span class="t">10. The Long Arc — 1,000+ Pull Requests</span><span class="d">May–Aug 2026</span></div>
```

New text:
```html
<div class="toc-part">Part Two — synlynk, In Parallel</div>
<div class="toc-entry"><span class="t">4. The Polyglot Harness</span><span class="d">May–Jun 2026</span></div>
<div class="toc-entry"><span class="t">5. From Tool to Organization</span><span class="d">Jun–Aug 2026</span></div>
<div class="toc-entry"><span class="t">6. The Verification Tax</span><span class="d">Jul–Aug 2026</span></div>
<div class="toc-entry"><span class="t">7. Governance as Code</span><span class="d">Aug 2026</span></div>
<div class="toc-entry"><span class="t">8. The Autonomous Loop</span><span class="d">Aug 2026</span></div>
<div class="toc-entry"><span class="t">9. Capability Is Not Static</span><span class="d">Aug 25, 2026</span></div>
<div class="toc-entry"><span class="t">10. The Neutral Layer</span></div>
<div class="toc-entry"><span class="t">11. The Long Arc — 1,000+ Pull Requests</span><span class="d">May–Aug 2026</span></div>
```

(No date range given for the Neutral Layer TOC entry — it's a synthesis/positioning chapter, not tied to a specific dated period, matching the style of TOC entries elsewhere in the file that omit `<span class="d">` when no date range applies, e.g. Part III's entries.)

- [ ] **Step 2: Verify**

Run: `grep -n "10\. The Neutral Layer" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: one match.

Run: `grep -n "11\. The Long Arc" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: update Part Two TOC for Neutral Layer insertion + renumbering"
```

---

### Task 7: Expand the rxcc chapter (Part III Chapter One) with the deep-dive content and three embedded mockups

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (Part III Chapter One, currently ~lines 691–740)

Per spec Section 3a, add five things to the existing rxcc chapter, inserted as new `<p>`/box elements after the existing `.market-op` box and before the closing `.autonomy-box`/`</chapter>` (i.e., appended as new material near the end of the chapter, not interleaved into the existing banter/RCA narrative, which stays as-is).

- [ ] **Step 1: Locate the exact insertion point**

Run: `grep -n "Market Opportunity — The Honest Version" docs/book/the-supervised-machine-v0.5-DRAFT.html`

Read 20 lines starting at that match to capture the exact closing `</div>` of the `.market-op` box and the exact opening tag of the following `.autonomy-box`, so the new content can be inserted precisely between the two, using both as anchor context in the Edit call's `old_string`.

- [ ] **Step 2: Write and insert the deep-dive content**

Insert a new subsection (use `<h3>` headers matching any existing in-chapter subheading convention — check the chapter for precedent; if none exists, introduce `<h3>` here as the first use, consistent with Task 4's Neutral Layer chapter which also introduces `<h3>` for "The Lightest Possible Touch") covering, in order:

1. **Domain/document-type detail** — what kinds of documents rxcc actually ingests and processes (clinical notes, lab reports, prescriptions, referral letters — the categories already established in the existing rxcc chapter's ingestion narrative; do not invent categories not grounded in the existing chapter or spec).
2. **Standards detail** — FHIR, LOINC, SNOMED, RxNorm: what each standard is for in this pipeline (FHIR = interoperable clinical data exchange format, LOINC = lab/observation coding, SNOMED = clinical terminology, RxNorm = medication naming) and where rxcc's own data model maps onto them.
3. **Two-regime regulatory centerpiece** — a `<div class="mapping-box">` (existing class, used elsewhere for structured comparisons — confirm its exact markup pattern by grepping for `mapping-box` elsewhere in the file and matching it) contrasting: India's ABDM (Ayushman Bharat Digital Mission) + DPDP Act 2023 regime vs. the EU/Netherlands regime under GDPR Article 9 (special-category health data) + NEN 7510 (Dutch health-information-security standard) + a 30-day soft-delete right-to-be-forgotten window. State plainly what differs operationally between the two regimes for rxcc's own architecture (e.g., data residency, consent model, deletion semantics).
4. **Tamper-evident audit-trail design philosophy** — a blockquote (matching the existing `<blockquote><cite>` pattern used elsewhere in this chapter for the Antigravity CLI error string) presenting the design philosophy behind rxcc's synchronous AccessLog: every access is logged in the same transaction as the access itself, not asynchronously, so there is no window in which an access could occur without a corresponding log entry.
5. **Ingestion-pipeline architecture** — the pipeline: Cloudflare Worker (edge intake) → AWS Textract (OCR/document extraction) → Google Document AI (fallback when Textract's confidence is low) → Amazon Nova Pro (structured extraction/classification) → six accuracy tracks (per-document-type or per-field accuracy measurement, matching the "100%... property of the reviewed subset" thesis below). Close this subsection with a pull-quote-style callout (use `.primitive-contrast` or a blockquote, matching existing chapter precedent) stating the thesis: "100% accuracy is not a property of the pipeline. It's a property of the reviewed subset" — i.e., accuracy claims are only meaningful conditioned on what fraction of output has actually been human-reviewed, and the pipeline's honest self-report must always carry that denominator.

- [ ] **Step 3: Embed the three Stitch mockups**

Within or immediately after the ingestion-pipeline subsection (Step 2, item 5), insert three `<img>` tags referencing the assets downloaded in Task 3:

```html
<div style="text-align:center; margin: 2em 0;">
<img src="assets/rxcc-mockup-1.png" alt="rxcc document review UI mockup" style="max-width:100%; border:1px solid #ccc; margin-bottom: 0.5em;">
<p style="font-size:0.9em; color:#666; font-style:italic;">[caption describing what this specific mockup shows — write after viewing the downloaded image, do not caption blind]</p>
</div>
```

Repeat for `rxcc-mockup-2.png` and a third of the four downloaded in Task 3 (choose the three that best illustrate the ingestion/review/accuracy-tracking narrative just written; the fourth stays unused in `assets/` as a spare, per Task 3's note — do not delete it). Adjust the `src` path's extension if Task 3 found Stitch returned a non-`.png` format.

- [ ] **Step 4: Verify**

Run: `grep -n "AccessLog\|ABDM\|DPDP\|NEN 7510\|property of the reviewed subset" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: all five terms present, inside the rxcc chapter (line numbers between the chapter's start ~691 and its new extended end).

Run: `grep -n "assets/rxcc-mockup" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: 3 matches.

Read through the full expanded chapter once for tone consistency with the existing banter/RCA narrative before it (same register: dry, evidence-first, willing to state limitations plainly).

- [ ] **Step 5: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: expand rxcc chapter with domain/standards/regulatory deep-dive

Adds document-type and FHIR/LOINC/SNOMED/RxNorm standards detail,
the ABDM+DPDP vs GDPR/NEN-7510 two-regime regulatory comparison,
the synchronous AccessLog audit-trail design philosophy, the
Cloudflare Worker -> Textract -> Document AI -> Nova Pro ingestion
pipeline, and three embedded Stitch UI mockups."
```

---

### Task 8: Expand the cc-videoreframing chapter (Part III Chapter Two) with the CV pipeline walkthrough

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (Part III Chapter Two, currently ~lines 742–791, already corrected by Task 2)

Per spec Section 3b, add the nine-module CV pipeline walkthrough. This is a separate insertion from Task 2's correction — Task 2 fixed an existing sentence in place; this task adds new material, appended near the end of the chapter (same pattern as Task 7: after the existing `.market-op`/closing narrative content, before the chapter's closing `.autonomy-box`/`</chapter>`).

- [ ] **Step 1: Locate the insertion point**

Run: `grep -n "Market Opportunity" docs/book/the-supervised-machine-v0.5-DRAFT.html`

This chapter's own `.market-op` box (distinct from rxcc's, further down the file) — read 20 lines from that match to capture the same closing-box → next-box anchor pattern used in Task 7 Step 1.

- [ ] **Step 2: Write and insert the nine-module pipeline walkthrough**

Insert a new `<h3>The Nine Modules</h3>` subsection listing, in pipeline order, each module and its one-sentence job:

1. `ingestion` — accepts the raw source video and its declared metadata (including the frame rate the Task 2 correction just showed cannot always be trusted at face value).
2. `attention` — determines which regions of each frame are the visual subject (faces, motion, points of interest) that reframing must keep in view.
3. `scene_detection` — segments the source into distinct shots so reframing decisions don't blend continuity across a cut.
4. `effect_classifier` — identifies existing camera effects in the source (pans, zooms, cuts) so the reframe doesn't fight or duplicate them.
5. `motion_solver` — computes the actual crop/pan/zoom path per frame needed to keep the attention target in frame.
6. `edl_generator` — turns the motion solver's per-frame path into an edit-decision-list the renderer can consume.
7. `renderer` — executes the EDL, producing the actual output video.
8. `verifier` — the module at the center of #99 (and #98): checks the rendered output against expected timing/duration/content, using whatever ground-truth clock it's given.
9. `narrative_validator` — a higher-level check that the reframed output still tells a coherent visual story (subject continuity across cuts, no jarring reframe jumps) beyond just technical correctness.

Close the subsection tying #98 (duration tolerance) and #99 (the corrected verifier ground-truth bug) back explicitly to module 8 (`verifier`) — both LIVE-5 issues live in the same module, which is why they were root-caused together in the same investigation (per `memory/live5-cc-videoreframing-verification-gap.md`).

- [ ] **Step 3: Verify**

Run: `grep -n "narrative_validator\|edl_generator\|motion_solver" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: all three present, inside the cc-videoreframing chapter.

Run: `grep -c "chapter" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Sanity check only — confirm the insertion didn't accidentally break an existing `<chapter>`/`</chapter>` pair (should be an even, unchanged-from-before-this-task count of open+close tags around this region; spot-check by reading the full chapter through once).

- [ ] **Step 4: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: add nine-module CV pipeline walkthrough to cc-videoreframing chapter

Walks ingestion -> attention -> scene_detection -> effect_classifier
-> motion_solver -> edl_generator -> renderer -> verifier ->
narrative_validator, and ties #98/#99 explicitly back to the
verifier module they share."
```

---

### Task 9: Expand Chapter Sixteen with the competitive product-stack scorecard

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (Chapter Sixteen, currently ~lines 955–967)

- [ ] **Step 1: Insert a competitive scorecard table**

Old text (verbatim, closing of Chapter Sixteen, line 966–967):
```html
<p><strong>5. Portable memory and identity layer.</strong> The most speculative, and the one this book treats most skeptically: agent-owned, cross-session, cross-platform memory and identity, so what an agent learns working inside one product is not trapped inside that product's own database. synlynk's adjacent design document for a project called Tokq — agent-first memory storage, zero-knowledge encrypted, multi-cloud, with a marketplace and a cryptocurrency-based incentive model — is a serious, well-considered proposal for exactly this layer. It is also, as of this writing, unbuilt: a product requirements document, not a shipping product, and its reach for crypto-native economic primitives to solve a coordination problem should be read with the same clear eyes this book applied to crypto's original decade. A coherent design on paper is not evidence of product-market fit.</p>
</chapter>
```

New text: same old text, immediately followed (before `</chapter>`) by:
```html

<h3>Where synlynk Sits Against the Field</h3>
<p>[Introduce the comparison: this five-layer model isn't abstract — five real products are already building pieces of it, each with a different bet about which layer matters most. Write 1-2 sentences framing the table below.]</p>

<table>
<tr><th>Product</th><th>Primary bet</th><th>How it differs from synlynk's layer 2/3 focus</th></tr>
<tr><td>Factory</td><td>[state Factory's actual positioning as understood from the Strategic Review's competitive research — autonomous software engineering / "Droid" agents targeting the full SDLC]</td><td>[contrast: full-stack autonomous engineering platform vs. synlynk's neutral dispatch/governance layer sitting below any single vendor's agents]</td></tr>
<tr><td>OpenHands</td><td>[open-source autonomous coding agent framework]</td><td>[contrast: single-agent-framework focus vs. multi-harness orchestration]</td></tr>
<tr><td>Codex (OpenAI product, distinct from the Codex harness this book's own fleet uses)</td><td>[OpenAI's own agentic coding product]</td><td>[contrast: vendor-native, single-model-family vs. synlynk's explicit harness-agnosticism]</td></tr>
<tr><td>GitHub Copilot (Workspace/Agent mode)</td><td>[Microsoft/GitHub-native agentic coding, deeply integrated into the GitHub product surface]</td><td>[contrast: platform-embedded vs. synlynk's Git-native-but-platform-independent governance layer]</td></tr>
<tr><td>Goose (Block)</td><td>[open-source, extensible local agent framework]</td><td>[contrast: closest in spirit to BYOH, but framework-first rather than governance/verification-first]</td></tr>
</table>
<p>[Close with a one-paragraph honest self-assessment: synlynk is not ahead of any of these on maturity, funding, or adoption — its differentiated bet is specifically layers 2 and 3 (harness/dispatch, governance), built empirically from one project's own incident history rather than designed top-down. State this without overclaiming, matching this chapter's existing skeptical tone (see its treatment of Tokq/layer 5 immediately above as the register to match).]</p>
```

- [ ] **Step 2: Verify**

Run: `grep -n "Where synlynk Sits Against the Field" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: one match.

Run: `grep -n "Factory\|OpenHands\|GitHub Copilot\|Goose" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: all four present in the new table.

- [ ] **Step 3: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: add competitive product-stack scorecard to Chapter Sixteen

Positions synlynk against Factory, OpenHands, Codex, GitHub
Copilot, and Goose — differentiated bet is layers 2/3
(harness/dispatch, governance), not full-stack or single-vendor."
```

---

### Task 10: Insert the new Part Four "Three Positions in the Sun" chapter before existing Chapter Eighteen

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (insert after Chapter Seventeen's `</chapter>`, before Chapter Eighteen's `<chapter>`, i.e. after line 991, before line 993)
- Create: `docs/book/fragments/three-positions-in-the-sun-chapter.html`

Per spec Section 1/6, this chapter covers the three-position debate, the KNOW→DECIDE→DO→LEARN→KNOW loop, `synlynk decide`/GOD mode, and HAPSO folded in as a paragraph (not a standalone chapter). It becomes the new Chapter Eighteen; the existing Chapter Eighteen becomes Chapter Nineteen (renumbered in Task 11).

- [ ] **Step 1: Write the chapter to the fragment file**

Write `docs/book/fragments/three-positions-in-the-sun-chapter.html`:

```html
<chapter>
<div class="chap-label">Chapter Eighteen</div>
<h2 class="chap-title">Three Positions in the Sun</h2>
<div class="chap-dek">[one-sentence dek in the existing register]</div>

<p>[Open by naming the positioning debate directly: any AI-native orchestration project eventually has to answer "what are you, at the top of your ambition" — and there are three genuinely different, defensible answers, not one. Introduce them as three levels of abstraction over the same underlying category: a neutral orchestration layer.]</p>

<table>
<tr><th>Position</th><th>What it claims</th><th>What it optimizes for</th></tr>
<tr><td>Full-Stack Builder</td><td>[the product that writes and ships your software end-to-end]</td><td>[speed/completeness of a single build]</td></tr>
<tr><td>Product OS</td><td>[the substrate a whole product's ongoing operation runs on — build, ship, monitor, iterate as one continuous loop]</td><td>[operational continuity over the product's whole lifecycle]</td></tr>
<tr><td>Autonomous Technology Org</td><td>[the thing that replaces not just engineering labor but an entire technology organization's decision-making — the "Autonomous CTO/CAIO" positioning Chapter Ten already named and explicitly declined]</td><td>[maximal scope, maximal autonomy, minimal human-in-loop]</td></tr>
</table>

<p>[State explicitly: this book, and synlynk's own stated philosophy (Chapter Ten's "lightest possible touch"), picks the middle position — Product OS — not by default but by argument. Explain why: Full-Stack Builder is a race synlynk is not positioned to win against vendor-native, fully-funded competitors (Chapter Sixteen's scorecard already made this concrete); Autonomous Technology Org overclaims what the evidence in this book (Part Three, Part Four Ch.14-17) actually supports about current AI reliability.]</p>

<h3>The KNOW → DECIDE → DO → LEARN → KNOW Loop</h3>
<p>[Describe this as the operational loop underlying the Product OS position: KNOW (context/state — what Chapter 3's working-memory argument and the whole context-injection apparatus provide), DECIDE (governance-gated choice — Chapter 7's policy-as-code), DO (dispatched execution — the whole Part Two/Three harness-fleet narrative), LEARN (verification and capability reassessment — Chapter 9, Chapter 6's verification tax), closing the loop back to an updated KNOW. Tie explicitly to `synlynk decide` and GOD mode (describe GOD mode accurately per the project's actual `decide --record` / autonomous-decision tooling — a mode where the loop runs with minimal human gating, used deliberately and narrowly, not as the default operating posture) as the concrete implementation of this loop's DECIDE step.]</p>

<p>[Fold in HAPSO — Human Attention Per Shipped Outcome — as a single paragraph, not a subsection: define it as a metric for the Product OS position specifically (how much human attention a given shipped outcome actually consumed, end to end, as the real cost/quality metric that matters more than raw agent throughput), and note briefly why the other two positions don't need this metric the same way (Full-Stack Builder measures build speed; Autonomous Technology Org's whole premise is minimizing this number toward zero, which this book's own evidence — Ch.14-17 — argues is premature to claim.]</p>

<div class="pattern-box">
<div class="label">Why the Middle Position</div>
<p>[Closing paragraph: the honest case for Product OS as the position synlynk actually occupies today, stated without hedging but also without overclaiming — matching the register of Ch.18's existing closing "Closing Thought" box.]</p>
</div>

</chapter>
```

- [ ] **Step 2: Insert the fragment content into the manuscript**

Run: `grep -n "This chapter exists to let a few of the best of them just be what they were first" docs/book/the-supervised-machine-v0.5-DRAFT.html`

Confirm the exact closing paragraph and `</chapter>` tag of Chapter Seventeen ("The Funny Chapter") — old text (verbatim, from the earlier read, line 990-991):
```html
<p>None of the above is included to make the fleet look incompetent. Every single one of these incidents was caught, not because anything failed loudly, but because someone — a human, in every case, at least so far — refused to accept a clean-looking status line at face value and went and checked. That refusal, applied consistently enough to produce a chapter's worth of funny stories rather than a chapter's worth of quiet production incidents, is itself the entire thesis of this book, and this chapter is simply the version of that thesis you're allowed to laugh at.</p>
</chapter>
```

New text: same old text, immediately followed by the full fragment content from Step 1.

- [ ] **Step 3: Verify**

Run: `grep -n "Three Positions in the Sun" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: one match (the new `<h2>`).

Run: `grep -c "Chapter Eighteen" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: `2` (new chapter + old, unrenumbered Ch.18 — resolved in Task 11).

- [ ] **Step 4: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html docs/book/fragments/three-positions-in-the-sun-chapter.html
git commit -m "docs: add Part Four Chapter Eighteen, Three Positions in the Sun

Covers the Full-Stack Builder / Product OS / Autonomous Technology
Org positioning debate, argues for the Product OS middle position,
introduces the KNOW-DECIDE-DO-LEARN-KNOW loop with synlynk
decide/GOD mode as its DECIDE implementation, and folds in HAPSO
as a single paragraph. Inserted before the existing Chapter
Eighteen, which Task 11 renumbers to Chapter Nineteen."
```

---

### Task 11: Renumber the existing Chapter Eighteen to Chapter Nineteen

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html`

- [ ] **Step 1: Relabel the chapter**

Old text (verbatim):
```html
<div class="chap-label">Chapter Eighteen</div>
<h2 class="chap-title">Is synlynk Part of This Future — Or the Future Itself?</h2>
```

New text:
```html
<div class="chap-label">Chapter Nineteen</div>
<h2 class="chap-title">Is synlynk Part of This Future — Or the Future Itself?</h2>
```

- [ ] **Step 2: Verify**

Run: `grep -c "Chapter Eighteen" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: `1` (only the new Three Positions chapter).

Run: `grep -c "Chapter Nineteen" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: `1`.

- [ ] **Step 3: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: renumber final chapter from Chapter Eighteen to Chapter Nineteen"
```

---

### Task 12: Expand Chapter Nineteen (formerly Eighteen) with market-sizing data

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (Chapter Nineteen, currently ~lines 993–1009 pre-renumber)

- [ ] **Step 1: Insert market-sizing content**

Old text (verbatim, the paragraph beginning "What is more plausible..."):
```html
<p>What is more plausible, and more useful as a projection: synlynk, or a project descended from its lineage, becomes one of the durable, widely-adopted governance and dispatch layers — the way Terraform became a durable layer for infrastructure provisioning without becoming "the future of cloud computing" in totality, and without needing to. Its own strategy document sets a public preview target of 2026-10-01 for a genuinely autonomous development loop and is refreshingly candid that the loop is roughly a third complete as of this writing. That candor — measuring the gap honestly rather than marketing past it, and, this draft would add, being willing to publish its own funniest failures rather than only its cleanest wins — is itself evidence for the thesis, not against it: an organization, human or hybrid, that can accurately state how much of its own autonomy is real, and laugh honestly at the parts that aren't yet, is demonstrating, in miniature, exactly the verification discipline this book has argued the whole era depends on.</p>
```

New text: same old text, immediately followed by a new market-sizing subsection:
```html

<h3>Sizing the Category</h3>
<p>[State the current market figure: Gartner's estimate of the current AI-native software-development-tooling category at roughly $9.8-11B. Attribute clearly as a third-party estimate, not synlynk's own figure, matching this book's sourcing discipline (see "A Note on Sources").]</p>
<p>[Present a three-horizon model for how this category could grow, each horizon representing a different one of the "Three Positions in the Sun" (Chapter Eighteen) becoming the dominant framing industry-wide:]</p>
<table>
<tr><th>Horizon</th><th>Size</th><th>Dominant framing if this horizon wins</th></tr>
<tr><td>Near-term (current tooling category matures)</td><td>$1-3B</td><td>Full-Stack Builder tools remain point solutions; no consolidated orchestration layer emerges</td></tr>
<tr><td>Mid-term (a governance/dispatch layer becomes standard infrastructure)</td><td>$5-15B</td><td>Product OS position wins broadly — the category this book has argued synlynk is actually building toward</td></tr>
<tr><td>Long-term (autonomous operation becomes the default posture for a meaningful share of software orgs)</td><td>$20-50B+</td><td>Autonomous Technology Org position wins broadly — the outcome this book has repeatedly declined to predict as likely on current evidence</td></tr>
</table>
<p>[Close by tying the horizon model back to this chapter's own honest "no, and here's why" answer to whether synlynk is THE future: state plainly that the mid-term horizon, not the long-term one, is the bet this book finds most defensible given everything Part Three and Part Four actually documented about current AI reliability — and that betting on the long-term horizon today would be marketing past the gap the book has spent its whole length arguing you should not market past.]</p>
```

- [ ] **Step 2: Verify**

Run: `grep -n "Sizing the Category\|Gartner\|\\$9.8" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: matches present in the final chapter.

- [ ] **Step 3: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: add market-sizing section to Chapter Nineteen

Gartner ~\$9.8-11B current category estimate plus a three-horizon
(\$1-3B / \$5-15B / \$20-50B+) model, each horizon tied to one of
Chapter Eighteen's three positions winning industry-wide."
```

---

### Task 13: Update the Part Four TOC block for the new chapter and renumbering

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (TOC block, ~lines 199–204)

- [ ] **Step 1: Edit the TOC**

Old text (verbatim):
```html
<div class="toc-part">Part Four — Layers, Dynamics, and What Comes Next</div>
<div class="toc-entry"><span class="t">14. Trust, Renegotiated — Layers, Builder, User, One Continuous Verb</span></div>
<div class="toc-entry"><span class="t">15. The War of the Harnesses</span></div>
<div class="toc-entry"><span class="t">16. The Product Stack of the AI-Native Era</span></div>
<div class="toc-entry"><span class="t">17. The Funny Chapter</span></div>
<div class="toc-entry"><span class="t">18. Is synlynk Part of This Future — Or the Future Itself?</span></div>
```

New text:
```html
<div class="toc-part">Part Four — Layers, Dynamics, and What Comes Next</div>
<div class="toc-entry"><span class="t">14. Trust, Renegotiated — Layers, Builder, User, One Continuous Verb</span></div>
<div class="toc-entry"><span class="t">15. The War of the Harnesses</span></div>
<div class="toc-entry"><span class="t">16. The Product Stack of the AI-Native Era</span></div>
<div class="toc-entry"><span class="t">17. The Funny Chapter</span></div>
<div class="toc-entry"><span class="t">18. Three Positions in the Sun</span></div>
<div class="toc-entry"><span class="t">19. Is synlynk Part of This Future — Or the Future Itself?</span></div>
```

- [ ] **Step 2: Verify**

Run: `grep -n "18\. Three Positions in the Sun" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: one match.

Run: `grep -n "19\. Is synlynk Part of This Future" docs/book/the-supervised-machine-v0.5-DRAFT.html`
Expected: one match.

- [ ] **Step 3: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.html
git commit -m "docs: update Part Four TOC for Three Positions insertion + renumbering"
```

---

### Task 14: Full-document consistency pass and PDF regeneration

**Files:**
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.html` (no content changes expected — verification only)
- Modify: `docs/book/the-supervised-machine-v0.5-DRAFT.pdf` (regenerated)
- Modify: `docs/book/README.md` (editorial-history note)

- [ ] **Step 1: Full chapter-numbering sanity sweep**

Run: `grep -n "chap-label" docs/book/the-supervised-machine-v0.5-DRAFT.html`

Read the full ordered list of chapter labels top to bottom. Expected sequence from Part One onward: Chapter One, Two, Three (Part One) → Prologue → Part Two: Four, Five, Six, Seven, Eight, Nine, **Ten (Neutral Layer, new)**, **Eleven (Long Arc, renumbered)** → Part III: One through Five (unchanged, own local numbering) → Part Four: Fourteen, Fifteen, Sixteen, Seventeen, **Eighteen (Three Positions, new)**, **Nineteen (renumbered)** → Closing, Reference. Confirm no duplicate or skipped number anywhere in this sequence.

- [ ] **Step 2: Full TOC-to-body cross-check**

Run: `grep -n "toc-entry" docs/book/the-supervised-machine-v0.5-DRAFT.html`

Manually confirm every TOC entry's chapter number/title matches the corresponding body `chap-label`/`chap-title` pair exactly, for every chapter touched by this plan (Ch.10 Neutral Layer, Ch.11 Long Arc, Ch.18 Three Positions, Ch.19 closing chapter).

- [ ] **Step 3: Confirm both LIVE-5 copies still agree**

Run: `grep -A6 "Fact-Check — Codex" docs/book/fragments/part3-codex-factcheck-notes.html | sed -n '/timing-comparison bug/,/<\/p>/p'`

Run: `grep -A6 "Fact-Check — Codex" docs/book/the-supervised-machine-v0.5-DRAFT.html | sed -n '/timing-comparison bug/,/<\/p>/p'`

Compare the two outputs by eye — wording should match (this re-confirms Task 2 Step 4's soft check now that all later tasks have finished touching the file).

- [ ] **Step 4: Regenerate the PDF**

```bash
"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" \
  --headless --disable-gpu --no-pdf-header-footer \
  --print-to-pdf=docs/book/the-supervised-machine-v0.5-DRAFT.pdf \
  "file://$(pwd)/docs/book/the-supervised-machine-v0.5-DRAFT.html"
```

Confirm the command exits 0 and the PDF file's mtime updates: `ls -la docs/book/the-supervised-machine-v0.5-DRAFT.pdf`

- [ ] **Step 5: Update `docs/book/README.md`'s editorial history**

Add one new paragraph to the "Editorial history" section (after the existing Part III restructuring paragraph) noting: this draft incorporates the Strategic Review integration — see `docs/superpowers/specs/2026-09-03-book-strategic-review-integration-design.md` — adding the Part Two Neutral Layer chapter (new Ch.10), the Part Four Three Positions in the Sun chapter (new Ch.18), deep-dive expansions of the rxcc and cc-videoreframing Part III chapters (including a LIVE-5/#99 framing correction), expansions of Ch.16 and the closing chapter, and embedded Stitch UI mockups (`docs/book/assets/`). Also note the pre-Part-0 cold-open addition per the same spec's Section 4a.

- [ ] **Step 6: Commit**

```bash
git add docs/book/the-supervised-machine-v0.5-DRAFT.pdf docs/book/README.md
git commit -m "docs: regenerate PDF and update editorial history for strategic review integration

Closes out the Strategic Review integration plan: full
chapter-numbering and TOC-to-body consistency verified, both
LIVE-5 fact-check copies confirmed in agreement, PDF rebuilt from
final HTML, README editorial-history section updated."
```

---

## Self-Review

**Spec coverage** (against `docs/superpowers/specs/2026-09-03-book-strategic-review-integration-design.md`):
- Section 1 (Ch.16 scorecard, Ch.18 market sizing, Three Positions chapter) → Tasks 9, 10, 11, 12, 13
- Section 2 (Neutral Layer chapter) → Tasks 4, 5, 6
- Section 3a (rxcc deep-dive) → Task 7
- Section 3b (cc-videoreframing deep-dive + LIVE-5 correction) → Tasks 1, 2, 8
- Section 4 (Stitch mockups) → Tasks 3, 7 (Step 3)
- Section 4a (cold-open) → already implemented and committed prior to this plan (per spec addendum); Task 14 Step 5 documents it in the README alongside this plan's other changes, no further action needed
- Section 6 (non-goals: Playblazer/Grok-infra/Claude-reviewer-seat chapters untouched except the one required LIVE-5 correction) → respected; no task in this plan touches Part III Chapters Three, Four, or Five

**Placeholder scan:** Every content-writing step (Tasks 4, 7, 8, 9, 10, 12) specifies exact facts/figures/cross-references/structural beats rather than "TBD" or "similar to Task N" — the actual sentence-level prose is deliberately left to be authored live at execution time per this project's book-authorship model (Claude writes book prose directly), but every fact that prose must contain is enumerated. This is the agreed adaptation for content work, stated up front in the plan header.

**Naming/numbering consistency:** Chapter numbering verified self-consistent task-by-task (Task 4 introduces Ch.10 before Task 5 vacates the old Ch.10 label; same pattern for Ch.18/19 in Tasks 10-11) and given one final cross-check in Task 14. Fragment filenames (`neutral-layer-chapter.html`, `three-positions-in-the-sun-chapter.html`) match the existing `docs/book/fragments/` naming convention (kebab-case, descriptive, `-chapter` suffix for full new chapters per `cold-open-the-gap-lights-up.html`'s precedent).
