# 101. PR #853 — Watching Synlynk @Work, the 4th docs.njk document

## Goal at the end of the previous PR

PR #852 closed out the #846/#847 bugfix cycle: the TUI's approve/kill keybindings existed but weren't wired up, and the Slack notifier's event filter matched nothing due to three divergent naming schemes plus a wrong hardcoded port. Both were fixed, independently verified, and merged. Issue #848 — the "Watching synlynk" onboarding guide that surfaced those two bugs in the first place — was unblocked but explicitly not started, per its own dependency framing ("do not write the final guide until both are resolved").

## What moved the goalpost this PR

The user asked to kick off #848 as a real, publishable document rather than internal reference material: a 4th card on the `synlynk.com/docs` page, sitting alongside the Quick Start Guide, Command Reference, and The Manual. Two things had to be established before any writing could start:

1. **What "rich visuals/screenshots" means for this project.** A grep across all three existing docs turned up zero `<img>` tags — every "visual" in the existing series is a hand-coded CSS/HTML mockup: fake terminal windows with syntax-colored spans, fake browser chrome, fake UI panels. Rather than assume, this was raised as an explicit clarifying question; the user confirmed CSS mockups only, matching the existing style exactly.
2. **How to get from HTML to a published PDF.** All three existing docs are self-contained, print-styled A4 HTML files with a matching `.pdf` committed alongside them — but there's no PDF-generation tooling anywhere in the repo (no wkhtmltopdf, no weasyprint, no puppeteer script). The three existing PDFs are static, produced out-of-band. This meant PDF rendering had to be a manual "deploy" step done directly, not something delegated to the content-writing dispatch.

## What this PR shipped, technically

Content-writing was dispatched to Agy (`job-94bd0c6b`, $1.40, 126s) with a fully detailed, code-grounded task spec — not "write a guide," but the exact keybindings from `synlynk/tui.py`, the exact port (`8721`, from `synlynk/viz.py`'s `DEFAULT_PORT`) and CLI flags for Vizor, and the corrected Slack event names (`dispatch`/`approve_pr`/`kill_job`) and one-way/read-only nature from `synlynk/notifiers/slack.py`. The task spec also mapped specific content to specific callout classes (`.c-new` for the TUI approve/kill keybindings as a recently-shipped capability, `.c-tip` for the uxcore-shared-backend observation, `.c-info` for "bring your own Slack webhook," `.c-warn` for the Slack notifier's read-only limitation) so the finished doc would use the existing design language correctly rather than reinvent it.

Agy delivered `docs/synlynk-watching-at-work-guide.html` (1224 lines, 9 pages) and the 4th `.doc-card` in `website/src/docs.njk` (🛰️ thumb, matching copy tone). Review found one real bug — three `<td>` elements used inside a bare `<ul>` with no table, in the Slack event-types list — fixed directly (`<li>`, matching the surrounding list markup) rather than re-dispatched, since it was a single 3-line HTML correction. Everything else held up: zero `<img>` tags, all five callout classes used correctly, port `8721` correct throughout with no stray `8420`, keybindings and Slack event names verified against the current source.

With content and markup verified, the remaining two deliverables were handled directly as "deploy" actions per the PM/implementer role split (dispatch agents write content and code; Claude packages and ships):

- **Version placeholder**: the doc shipped with a `vNEXT` placeholder by design (per the dispatch task's own instruction), to be filled in before merge. `synlynk/_constants.py` gives the current shipped version as `v0.13.0`; all four occurrences (title, maintenance-comment header, cover page, footer) were updated via `sed`.
- **PDF rendering**: with no in-repo tooling, rendered via headless Chrome (`google-chrome --headless --print-to-pdf`) against a local `python3 -m http.server` serving the docs directory — Chrome's `file://` handling inside the browser-automation tool was blocked, so a local HTTP server was the reliable path. Output: 9 pages (matching the target page count from the other docs), 1.14MB (in line with the 0.8–1.8MB range of the three existing PDFs). Verified visually by rendering the cover page and the TUI keybindings page to PNG and inspecting them directly — both matched the design system and had accurate content, including a terminal mockup showing the exact `[1]Fleet [2]Jobs [3]Costs [4]Review  [q]uit  [a]pprove [k]ill` hint string from the shipped `tui.py`.

The PR itself (#853) was originally auto-opened by the dispatch finalizer with a generic title; its title and body were rewritten to describe the actual shipped work and include `Closes #848` for GitHub auto-close.

## Brainstorm visuals

None used — this was a content and packaging task against an already-established design system (the three existing docs), not new visual design surface.

## What this achieved toward the long-arc goal

The `synlynk.com/docs` page now documents all three of UX 1.0's observability surfaces — TUI, Vizor, Slack — in the same polished, publishable form as the rest of the manual. More importantly, the process that produced it (tracing real keybindings and event names against shipped code, rather than describing intended behavior) is the same process that caught #846 and #847 in the first place. This PR is the payoff of that earlier bug-hunting: the guide it produces is accurate on day one because the two things it would otherwise have had to caveat are already fixed.

## New goalpost

With #848 shipped, the original "Watching synlynk" documentation thread is closed. No specific next step was assigned by this PR — the next priorities under discussion are the already-spec'd-and-planned GOVERNS-lifecycle + workspace-agent pilot (`2026-08-08-governs-lifecycle-workspace-agent-pilot.md`), the still-open UX-1.0 field-trial-readiness thread, and a recurring cluster of job-status/cost-capture truthfulness bugs (#701, #579, #752, #740, #787) worth batching into one investigation rather than fixing piecemeal.
