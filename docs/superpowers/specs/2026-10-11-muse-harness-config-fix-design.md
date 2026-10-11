# Muse Harness Config Fix — Design

## Problem

synlynk already has substantial Muse (Meta) harness plumbing: `synlynk/harness_adapters/muse.py`
(a registered `MuseAdapter`), a full capability-baseline entry in `synlynk/_constants.py`
(`HARNESS_CAPABILITY_BASELINES["muse"]`), and dispatch-time special-casing in `synlynk/dispatch.py`
(prompt construction, output-format flag injection, worktree cwd flag). Muse sits in
`NEXT_GEN_FLEET`/`EXTENDED_FLEET` — dispatchable via the experimental path, not yet promoted to
`CORE_FLEET` (claude/agy/codex/grok).

That config was written against a CLI contract that does not match the installed `muse` binary
(v1.4.4 / 1.4.4-R5419.1, confirmed installed at `~/.local/bin/muse` and already authenticated via
`muse auth set` → `~/.muse/auth.json`, populated 2026-10-05). Concretely:

| Config assumes | Real CLI has |
|---|---|
| `muse run --prompt "<task>" --non-interactive --output-format json` | `muse exec [PROMPT] --json --provider meta --model <id> ...` — no `run` subcommand, no `--non-interactive` flag, no `--output-format` flag |
| Prompt passed via `--prompt` flag (`prompt_flag: "--prompt"`) | Prompt is a positional argument to `exec` |
| `-C <worktree_path>` to scope the working directory (dispatch.py ~line 3982, same pattern as codex/grok) | No `-C` flag exists; the real equivalent is `--workspace <path>` |
| Credentials passed via `MUSE_API_KEY`/`META_API_KEY` env vars (`env_passthrough`) | Muse stores its own credentials via `muse auth set`, read from `~/.muse/auth.json` — no env var needed |
| `resolve_tier_model(tier, "muse")` resolves a real model id | No `"muse"` entry exists anywhere in the model catalog (`synlynk/models.py`'s `tiers` dict or `.synlynk/models.json`), so resolution silently falls through to the fake placeholder `"muse-default"` |

Net effect: **any dispatch to Muse today fails before doing real work**, on flag/contract
mismatches that have nothing to do with Muse's actual task capability. This blocks not just
"onboard Muse as a full harness" but even running the calibration dispatches needed to measure it
under the Empirical Capability Assessment Policy (CLAUDE.md, 2026-10-04) — Muse currently has zero
samples in `cost_entries`/`capability_ratings`.

## Scope

**In scope:** fix the adapter/config layer so a dispatch to Muse actually executes correctly
end-to-end. This is a correctness fix to existing (non-functional) plumbing, not new capability
work.

**Out of scope (explicitly deferred to later, separate efforts):**
- Running the calibration batch (N dispatches per task type to accrue the ≥5-merged-job sample
  threshold the Empirical Capability Assessment Policy requires before Muse can influence routing).
- Promoting Muse from `EXTENDED_FLEET`/`NEXT_GEN_FLEET` to `CORE_FLEET`.
- Any change to the `HarnessAdapter` protocol itself, or to the `roles` list already declared for
  muse (`builder`, `verifier`, `architect` — unchanged).
- Auditing other harnesses (agy/grok/codex) for similar drift. This spec only confirms Muse is
  broken; it does not claim or investigate whether the others are.

## Changes

### 1. `synlynk/_constants.py` — rewrite the `"muse"` entry in `HARNESS_CAPABILITY_BASELINES`

- `non_interactive_flags`: becomes `["exec"]` (the real headless entrypoint is the `exec`
  subcommand itself, not a separate flag).
- `prompt_flag`: removed. `prompt_via_arg: True` stays — the prompt is the positional argument to
  `exec`.
- `dispatch_flags.valid_flags`: becomes `["--json", "--provider", "--model", "--approval-mode",
  "--workspace"]`.
- `dispatch_flags.invalid_flags`: unchanged (`--dangerously-skip-permissions`, `--always-approve`
  — these belong to other harnesses and were already correctly excluded).
- `dispatch_flags.required_flags`: becomes `["--json", "--approval-mode"]` (headless dispatch
  must not block on an interactive approval prompt — `--approval-mode never`).
- `headless_contract.non_interactive_flag`: becomes `"exec"`.
- `env_passthrough`: becomes `[]` — remove `MUSE_API_KEY`/`META_API_KEY`. Muse's credential store
  is CLI-managed, not env-var-based.
- `auth_check.probe`: unchanged (`["muse", "--version"]` — confirmed this already runs and exits 0
  against the installed binary).
- `roles`, `strengths`, `network_deps`, `can_gh_write`: unchanged.

### 2. `synlynk/dispatch.py` — fix the two muse special-case blocks

- The block that currently injects `--output-format json` for muse (~line 3941) becomes `--json`.
- The block that currently injects `-C <worktree_path>` for muse (~line 3982) becomes `--workspace
  <worktree_path>`, matching the pattern already used for codex's `-C`/grok's `--cwd` immediately
  above it, just with muse's actual flag name.
- The prompt-construction block for muse (~line 2139) stays structurally the same — it already
  builds a plain task-text string and does not itself hardcode a wrong flag; the flag mismatch was
  injected later at the `_dispatch_flags_for_agent`/append-flags stage covered above.

### 3. Model catalog — add a real `muse` entry

- Add a `"muse"` key to at least one tier (minimally the tier synlynk's default dispatch path
  resolves first, e.g. `"pro"` or `"fast"` depending on existing tier semantics) in the builtin
  fallback catalog in `synlynk/models.py::load_model_catalog()`, mapped to `"muse-spark-1.3"`
  (confirmed real catalog id via `muse model-profile show muse-spark-1.3`).
- If the project also maintains a live `.synlynk/models.json`, add the same entry there so the
  file-backed catalog doesn't silently override the builtin fallback with the old gap.

## Testing

1. **Unit tests** on `_dispatch_flags_for_agent("muse")` and `_permissions_to_flags("muse", ...)`
   asserting the new flag shape: `--json` present, `--approval-mode never` present, no `--prompt`,
   no `--non-interactive`, no `--output-format`, no `-C`. Add a test asserting
   `resolve_tier_model(<tier>, "muse")` returns `"muse-spark-1.3"` (or whichever tier is chosen),
   not the fallback `"muse-default"` string.
2. **One live smoke-test dispatch**: `synlynk dispatch --harness muse` with a cheap, read-only,
   no-op task (e.g. "read this file and summarize it in one sentence, do not modify anything").
   This is real cost/tokens, logged via the normal `synlynk cost log` path — the point is proving
   the `exec`/`--json`/`--workspace`/model-catalog wiring produces a real completed job end-to-end,
   which unit tests alone can't confirm (they don't invoke the real binary).

## Acceptance

- Unit tests pass.
- The live smoke-test dispatch completes with a real, verified effect (not just an exit code —
  per this project's job-status false-negative history, verify the actual file/output change
  directly rather than trusting the job's reported status string).
- Muse remains in `EXTENDED_FLEET`/`NEXT_GEN_FLEET` after this fix — promotion to `CORE_FLEET` is
  explicitly not a goal of this spec, since zero capability samples exist yet.
