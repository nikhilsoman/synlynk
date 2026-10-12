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

**Verdict: Codex remains `unconfirmed`** — the R2 decision's "default to Agy-style
worst-case treatment for unconfirmed harnesses" stands for Codex as-is. A real probe
(deliberately editing `AGENTS.md` mid-session in a dispatch explicitly scoped to allow
that edit) is still open work, consistent with R2's stated empirical-probe plan.

Note: this job's cost ($4.01, 1.3M input tokens for a report-only audit task) is high
relative to its output and worth flagging against the project's existing cost-inflation
pattern tracking (gh:#1937/#2219 lineage) — not investigated further here, out of scope
for this addendum.

## Updated harness reload-confidence table (supersedes R1/R2's provisional one)

| Harness | Reload confidence | Evidence |
|---|---|---|
| Claude | `confirmed_per_session` | R1: CLAUDE.md/MEMORY.md loaded once at session start, not resent (direct transcript observation) |
| Agy | `confirmed_per_turn` | R1: full system-instruction block re-inlined every `generateContent` call (payload inspection) |
| Grok | `confirmed_per_turn` | **This addendum**: `prompt_tokens` growth across tool-loop rounds in `~/.grok/logs/unified.jsonl`, confirmed by direct session-log evidence |
| Codex | `unconfirmed` | **This addendum**: persistent session identity confirmed, but the one probe that disambiguates reload timing (mid-session AGENTS.md mutation) was not run; no log/transcript evidence either way |

This changes R2's framing from "Codex and Grok are both open gaps" to "Grok is now
confirmed (treat as per-turn, same as Agy); Codex remains the sole open gap, with a
specific next probe identified above."
