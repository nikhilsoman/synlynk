# R1 Addendum: Individual dispatch audits — Grok and Codex

**Date:** 2026-10-12
**GOVERNS:** story-c04f64b1 / goal-e79062e8
**Context:** The original R1 `synlynk decide` panel excluded Grok after two consecutive
headless timeouts (`decide`'s all-or-nothing panel-response requirement refuses to
synthesize if any named member fails to respond — see
[2026-10-12-context-window-management-r1-audit-your.md](2026-10-12-context-window-management-r1-audit-your.md)).
Codex *did* respond in that panel round, but only via a quick synchronous query with no
tool access, so its answer was explicitly a "can't confirm from inside a decide query" punt.

To fill both gaps, this addendum dispatches the R1 audit question to Grok and Codex
**individually**, as real `synlynk dispatch` jobs (full tool/log access, no all-or-nothing
coupling to other panel members' availability). This is also the direct motivation for
[gh:#2242](https://github.com/nikhilsoman/synlynk/issues/2242) (filed this session,
story-2ed5303f) — a single flaky harness should not have veto power over an entire decide
round when the rest of the panel answered fine.

## Grok — job-21045384 (`$0.75`, 113,999 in / 27,128 out, 391s)

**Confirmed, directly evidenced from this session's own logs** (`~/.grok/logs/unified.jsonl`):
instructions are **resent on every model call**, not loaded once and dropped. Within this
job's single user turn, the tool loop rebuilt the request 10+ times, and `prompt_tokens`
grew monotonically every round (37,316 → 40,782 → 59,941 → ... → 104,781), while
`cached_prompt_tokens` tracked the prior loop's full prompt almost exactly — i.e. the
provider prompt-cache makes repeat calls *cheap*, but the full prefix (including loaded
instruction files) still occupies the context window every call. It is not removed from
the budget; it's just discounted on cost.

One correction to the original R1 synthesis: **`GROK.md` itself is not currently loaded
into Grok sessions at all** — Grok Build 1.0.50's recognized project-rule filenames are
`Agents.md`/`Claude.md`/`CLAUDE.md`/`AGENT.md`/`AGENTS.md`, which excludes `GROK.md`. What
*is* resent every call in this repo's case is `AGENTS.md` (7,620 bytes) and the project's
`Claude.md` (32,561 bytes) plus `~/.claude/Claude.md` (22,031 bytes) — so today, Grok's
instruction-reload cost is being driven by files not even named for it, not by `GROK.md`'s
own content. This is a correctness finding for the instruction-writer task: writing a
leaner `GROK.md` has **zero effect** on Grok's resend cost until the init() template writer
also accounts for which filenames Grok's harness actually discovers.

Budget signal: a model-facing runtime preamble (not in `system_prompt.txt`) carries
`Context: 524288`, `Compaction at: 204800`, `Compactions remaining: 1` on every call —
confirms R1's original finding that any budget signal is wrapper/serving-layer injected,
not something the model introspects natively.

Scoping primitives confirmed: `spawn_subagent` (fresh context window, optional worktree
isolation), skills (name/path listed, ~19KB, bodies lazy-loaded on activation), MCP tool
schemas (lazy, fetched via `search_tool`), memory v2 (index resident, topic files on
demand).

**Verdict: Grok = `confirmed_per_turn`, same tier as Agy** — not `unconfirmed` any longer.
The instruction-writer's `reload_confidence` enum from R2 should be updated accordingly.

## Codex — job-8544e49e (`$4.01`, 1,297,381 in / 7,822 out, 250s)

**Still unverified**, honestly reported as such. Codex confirmed persistent session/thread
identity (`CODEX_SESSION_ID`/`CODEX_THREAD_ID` stable) and found synlynk's own Codex
capacity config (128K context baseline, 110K read / 16K write budget — a configured
estimate, not a live measurement) and cost-ledger parsing of `turn.completed` usage
records. But the one probe that would have settled per-turn-reload-vs-per-session (mutate
`AGENTS.md` mid-session, see if it's picked up without restart) was explicitly **not run**,
because this dispatch's own task text prohibited file edits. No transcript/log evidence
exposed instruction-payload reload events directly either way.

**Verdict at the time: Codex remains `unconfirmed`** — the R2 decision's "default to Agy-style
worst-case treatment for unconfirmed harnesses" stands for Codex as-is. A real probe
(deliberately editing `AGENTS.md` mid-session in a dispatch explicitly scoped to allow
that edit) is still open work, consistent with R2's stated empirical-probe plan.

Note: this job's cost ($4.01, 1.3M input tokens for a report-only audit task) is high
relative to its output and worth flagging against the project's existing cost-inflation
pattern tracking (gh:#1937/#2219 lineage) — not investigated further here, out of scope
for this addendum.

## Codex — job-3cad6bd5, mid-session AGENTS.md mutation probe (`$3.28`, 1,059,968 in / 6,920 out, 149s)

The follow-up probe this addendum called for. Dispatched with explicit permission to edit
`AGENTS.md` as the diagnostic mechanism: append a one-line sentinel mid-session, continue
with 4+ substantive tool actions without deliberately re-reading the file, then check
whether the sentinel surfaced in active instruction/system context on a later turn.
Restored `AGENTS.md` afterward; worktree confirmed clean.

**Result: the sentinel never appeared in active instruction/system context on any later
turn.** This is evidence *against* a verbatim full-file per-turn resend of `AGENTS.md` —
if Codex re-inlined the file's current on-disk content every turn the way Agy does, the
appended sentinel should have shown up in a subsequent turn's context. It did not.

This is weaker than Grok's confirmation, though, for two reasons the job itself flagged:
(1) the only instruction payload exposed in `~/.codex/sessions/.../rollout-*.jsonl` is the
turn-1 `session_meta.base_instructions` — later turns' usage records (entries 121, 125)
prove continued activity but not their prompt *contents*, so a reload that uses a cached/
reconstructed copy rather than a literal re-read of the file wouldn't necessarily show up
as a fresh sentinel-bearing payload either; (2) `history.jsonl`, `session_index.jsonl`,
and `transcription-history.jsonl` were also searched with no direct reload-event evidence
either way.

**Verdict: Codex moves from `unconfirmed` to `probed_no_evidence_of_per_turn_reload`** —
distinct from Claude's `confirmed_per_session` (which has direct transcript proof of a
one-time load) because this is an absence-of-evidence result, not a positive confirmation
of session-level caching. Practically: the R2 instruction-writer's worst-case default no
longer needs to treat Codex identically to Agy's *confirmed* per-turn case, but Codex
still isn't promoted to Claude's confirmed tier either. Treat as session-level for cost-model
purposes (no evidence of per-turn resend cost), while keeping the `reload_confidence` enum
value distinct so a future stronger probe (full later-turn prompt payload capture) can
still close the gap cleanly.

## Updated harness reload-confidence table (supersedes R1/R2's provisional one and this addendum's own earlier revision)

| Harness | Reload confidence | Evidence |
|---|---|---|
| Claude | `confirmed_per_session` | R1: CLAUDE.md/MEMORY.md loaded once at session start, not resent (direct transcript observation) |
| Agy | `confirmed_per_turn` | R1: full system-instruction block re-inlined every `generateContent` call (payload inspection) |
| Grok | `confirmed_per_turn` | This addendum: `prompt_tokens` growth across tool-loop rounds in `~/.grok/logs/unified.jsonl`, confirmed by direct session-log evidence |
| Codex | `probed_no_evidence_of_per_turn_reload` | **This addendum, job-3cad6bd5**: mid-session `AGENTS.md` sentinel mutation never resurfaced in later-turn context across 4+ tool actions — absence-of-evidence against per-turn resend, not a positive session-level confirmation; later-turn prompt payloads remain unexposed in available logs |

This changes R2's framing from "Codex and Grok are both open gaps" to: Grok confirmed
per-turn (treat as Agy-tier for cost-model purposes); Codex probed with a negative result
for per-turn resend (treat as session-tier for cost-model purposes, pending a stronger
confirmation), closing the sole remaining fully-open gap from the original R1 synthesis.
