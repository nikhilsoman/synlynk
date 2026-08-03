# Local Agent (aider + Ornith + oMLX) — Parity Configuration Design

**Status:** Draft
**Author:** Claude (PM), research informed by Aider official docs
**Related:** `docs/superpowers/specs/2026-07-12-local-agent-mlx-driver-design.md` (Addenda 1-4), PR #672, #678, #690

## Goal

`local` currently sits in `EXPERIMENTAL_FLEET`, not `CORE_FLEET = {claude, agy, codex, grok}`
(`synlynk/_constants.py`). Its long-run purpose is not to become a fifth interchangeable
core harness — it's to **offload as much routine, token-burning work as it can safely
handle from the four core harnesses**, so their (metered, costlier) capacity is spent on
work that actually needs frontier reasoning. Full parity with the core fleet's
capability schema (`AGENT_CAPABILITY_BASELINES`) is the eventual target; it's a multi-stage
graduation, not a single config change.

This spec defines two configuration tiers to get there:

- **Starter** — where `local` should sit today, immediately after PR #690. Safety-first;
  narrow scope; offloads only what's provably safe to offload.
- **Full** — the parity target. Self-verifying (architect + editor + lint + test loop),
  broader scope, closes the gap the core harnesses already clear via real tool use.

Graduation from Starter to Full, and eventually from `EXPERIMENTAL_FLEET` toward
`CORE_FLEET`-adjacent trust, is gated on a track record defined below — not on this spec
alone.

## Background: what we learned building it

Three real bugs surfaced in `local`'s first end-to-end dispatches, none caught by
`synlynk local doctor`:

1. **litellm provider-prefix** (PR #672) — Aider's `--model` string needs an explicit
   `openai/` prefix for litellm to route to a local oMLX endpoint; without it, litellm
   errors *before* sending anything and Aider still exits 0.
2. **Missing auth header** (PR #672/678 lineage) — `doctor` didn't send oMLX's required
   `Authorization: Bearer` header, so a green doctor run didn't mean a real dispatch would
   reach the model.
3. **`edit_format: "whole"` on the pinned model** (PR #690) — with the `whole` edit
   format, a plain question ("scan this repo and summarize it") drove the model into a
   44-minute runaway of destructive whole-file rewrites of unrelated files, because
   `whole` forces every response through a file-edit code path. `--no-auto-commits`
   happened to prevent real damage; that was luck, not design.

Every one of these was a case of `exit 0` lying about whether the real work happened —
the recurring theme across this project's dispatch tooling this session
(`docs/blog/95-*`, `docs/blog/96-*`). The tiers below are built to make that class of
failure structurally harder, not just patched one instance at a time.

## Research: Aider's own guidance

Summarized from `aider.chat/docs` (edit-formats, options reference, advanced model
settings, chat modes, LLM connection docs):

- **Edit formats**: `whole` (full-file rewrite — slow, costly, and per PR #690 dangerous
  on non-edit prompts), `diff` (search/replace blocks — efficient, what we now pin),
  `diff-fenced` (Gemini-specific), `udiff` (GPT-4-Turbo-specific), `editor-diff` /
  `editor-whole` (simplified formats used only inside architect mode). Aider has no
  default for unrecognized custom model names — `Ornith-1.0-9B-4bit` gets nothing unless
  we declare it, which is exactly how the `whole` bug happened.
- **Chat modes**: `code` (direct edits, current behavior), `ask` (zero file-write risk,
  pure Q&A), `architect` (a planner model proposes changes, a separate faster/cheaper
  *editor model* turns them into actual diffs — introduced because frontier-reasoning
  models sometimes mangle structured diff output while narrower models are precise at
  diffs but weak at planning).
- **Local-model guidance**: a 7B–14B local model is "genuinely good at focused edits,
  refactors, and boilerplate," and "noticeably weaker... on sprawling multi-file
  architecture." The architect/editor split exists specifically to close that gap.
- **`.aider.model.settings.yml`**: the mechanism for declaring `edit_format`,
  `use_repo_map`, `extra_params.api_base`, `editor_model_name`, `weak_model_name`, etc.
  for a custom OpenAI-compatible model name Aider doesn't recognize. This is the correct
  long-term home for `Ornith-1.0-9B-4bit`'s declaration instead of ad hoc CLI flags.
- **Guardrail flags**: `--auto-commits`/`--dirty-commits` (we already disable, harness
  commits instead), `--yes-always` (required — no PTY per
  `headless_contract.requires_pty: false`), `--auto-lint`/`--lint-cmd`,
  `--auto-test`/`--test-cmd`, `--map-tokens` (repo-map context cost, relevant on a small
  local context window).

## Tier 1: Starter (safety-first, ship next)

**Objective:** offload only what's provably safe — single-file, narrowly-scoped edit
tasks — with no path for the model's own output to trigger further autonomous action.

| Setting | Value | Why |
|---|---|---|
| `edit_format` | `diff`, pinned per model in `.agents/local.json` | Already fixed in PR #690. `whole` stays available for roster models that need it, but never for a task-facing dispatch without explicit review. |
| Chat mode | `code` only | No `--architect`. One inference call per dispatch — nothing to desynchronize between a planner and an editor. |
| `--no-auto-commits --yes-always` | unchanged | Harness owns commits (matches how the rest of the fleet works); `--yes-always` is required for headless dispatch, not a relaxation. |
| `auto-lint` | `false` | No autonomous command execution triggered by a weak model's output. This is the single highest-leverage guardrail given the `whole`-format incident — a hallucinating model with lint/test execution wired up can do more than rewrite files. |
| `auto-test` | `false` | Same reasoning. |
| `map-tokens` | conservative cap (or `0`) via `.aider.model.settings.yml` | Reduces large repo-map context on a small local context window — plausible secondary contributor to the runaway (more ambiguous context, more room to drift). |
| Task scope | single-file / narrowly-scoped only | Dispatch prompts stay task-level ("add a docstring to X", "extract Y into a helper"), never repo-wide asks. Repo-wide/exploratory asks route to a core harness. |
| Fleet placement | `EXPERIMENTAL_FLEET`, `roles: ["builder"]` | Unchanged. `can_gh_write: False` unchanged — no GH-write parity question here, that's an identity/token issue orthogonal to model tier. |

**What this offloads today:** small, well-bounded builder tasks that a core harness would
otherwise burn tokens on — boilerplate, single-file refactors, docstrings, mechanical
renames — anything where a wrong or incomplete edit is cheap to catch in review and cheap
to redo.

**What this explicitly does NOT do:** multi-file changes, anything requiring repo-wide
context, anything where a bad edit could land unreviewed (harness commit + PR review is
still the safety net, not autonomous verification).

## Tier 2: Full (parity target, later)

**Objective:** a self-verifying loop — architect + editor + lint + test — that closes
the gap Aider's own docs identify (strong on focused edits, weak on architecture) instead
of just working around it, and offloads proportionally more from the core fleet as trust
is earned.

| Setting | Value | Why |
|---|---|---|
| Chat mode | `--architect` with `editor_model_name` set | A stronger local model (or a cloud model, cost permitting) plans; Ornith or a coder-tuned model executes via `editor-diff`. Directly addresses "weak on architecture, strong on focused edits" instead of avoiding architecture-shaped tasks altogether. |
| `auto-lint` | `true`, `lint-cmd` wired to the repo's real linter | Closes the loop the core harnesses already get for free via real tool use — a bad edit gets caught and fed back before the dispatch reports done. |
| `auto-test` | `true`, `test-cmd` scoped to the touched module (not the full suite — cost control) | Same reasoning; scoped to avoid full-suite cost on every dispatch. |
| `map-tokens` | tuned up once context-window headroom is confirmed per model via `.aider.model.settings.yml` | Broader repo awareness once the smaller-context risk from Tier 1 is retired. |
| Task scope | multi-file changes permitted | Now that lint+test feedback closes the loop, scope can widen. |
| Fleet placement | still `EXPERIMENTAL_FLEET` until graduation criteria (below) are met | Full config is a capability increase, not an automatic trust increase — those are evaluated separately. |

**What this offloads once shipped:** proportionally more — multi-file refactors, small
features with their own tests, anything where the lint/test loop can catch a bad edit
before a human ever sees it. The ceiling is still below the core fleet (no GH-write, no
reviewer role) but the floor of "safe to hand to `local`" rises substantially.

### Graduation criteria (Starter → Full, and Full → trust expansion)

Not a code change — a track-record gate, evaluated by Claude as PM before either
transition ships:

1. **Starter → Full**: N (proposed: 10) consecutive clean Starter-tier dispatches — no
   runaway, no reverted/lost commits, `doctor` and live dispatch both green each time.
2. **Full → any `roles`/`can_gh_write` expansion**: a further clean track record on Full
   config itself, evaluated the same way, before any change to
   `AGENT_CAPABILITY_BASELINES["local"]`'s `roles` or `can_gh_write` fields. GH-write
   parity in particular is blocked independently on the role-scoped GitHub App token gap
   already tracked under #423/#569 — that's an identity problem, not a config-tier
   problem, and Full-tier config alone does not resolve it.

`N` and the exact clean-dispatch definition are open for your input — proposed here as a
starting point, not a final number.

## Non-goals

- This does not make `local` a general Q&A agent (carried over from Addendum 4 of the
  original spec) — `ask` mode is available but out of scope for automated dispatch; a
  human can still use it interactively.
- This does not resolve the dispatch-harness wrap-up-commit bug found during PR #690
  (where a sandboxed agent's `git update-index --cacheinfo` workaround could be silently
  reverted by the harness's own post-job commit) — that's tooling-side and tracked as a
  separate follow-up, not a `local`-agent config concern.
- This does not change `can_gh_write` or add GH-write capability to `local` at either
  tier — orthogonal to this spec, gated on #423/#569 regardless of config tier.

## Open questions for you

1. Is `N = 10` clean dispatches a reasonable graduation bar, or do you want it
   time-boxed instead (e.g., "two weeks of production use") or higher/lower?
2. For Full tier's architect mode, is there hardware/model budget for a second local
   model as the planner, or should the planner also be Ornith (self-architect, same
   model in both roles — weaker signal but zero additional resource cost)?
3. Should Starter ship as a follow-up PR now (config-only: chat mode restriction,
   `auto-lint`/`auto-test` explicitly `false`, `map-tokens` cap), or is PR #690's
   `edit_format` fix sufficient for Starter as-is and this spec is purely forward-looking
   until Full is scoped?
