# Harness Capability Matrix (Canon)

**Status:** Canonical reference. Source: two `synlynk decide` panel rounds where each agent self-reported as maintainer of its own harness — not synlynk's assumptions about them.

**Provenance:**
- Round 2a (Claude, Agy, Grok self-reported via `synlynk decide`; Codex timed out at 120s, twice) — decision `dec-e27ef144`, `project-docs/decisions/2026-07-30-self-review-round-different-from-the-las.md`
- Round 2b (Codex, queried directly via `codex exec` with no artificial timeout, bypassing `synlynk decide`'s hardcoded 120s in `synlynk/team.py:329`) — not recorded as a `synlynk decide` decision; raw output preserved at the time of writing, folded into this doc directly by the reviewing session.

**How to use this doc:** This is what `docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md` (PR #587) and any future implementation of it should treat as ground truth for per-harness behavior, in preference to inferring it from code/docs alone. Update this file (not tribal knowledge) whenever a harness's own maintainer corrects or extends it — re-run a `synlynk decide` self-review round rather than hand-editing assumptions back in.

**Caveat:** Self-reports are a harness's own maintainer describing itself, gathered via the *same* headless dispatch mechanism this whole goal is scrutinizing. Treat this as high-confidence primary-source data, not infallible — re-verify against `probe.py`/`doctor.py` TC1-5 results where they exist, and re-run the self-review periodically (see the design spec's §2b re-probe policy) as harness versions drift.

## Maintenance & calibration (standing task)

This doc is a **living reference, not a one-time snapshot** — treat updating it as a recurring Sustain/Maintain task (GOVERNS model), not a one-off artifact of this design spec. Recalibrate when:
- Any tracked CLI's version bumps by a minor version or more (`brew upgrade`/`npm update`/vendor release notes), since flag surfaces and config schemas are exactly what drifts between versions (see Codex's `--approval-policy` → `--ask-for-approval` rename below — that class of drift is silent unless re-checked).
- A dispatched job hits an unexpected permission/capability wall that contradicts what's recorded here.
- At minimum, once per quarter, independent of any triggering incident.

**How to recalibrate:** capture local CLI version via `<binary> --version` (cheap, no dispatch needed) for the Version Snapshot table below, then re-run a `synlynk decide --panel claude,agy,codex,grok --record` self-review round using the same five-section prompt structure as `dec-e27ef144` (`project-docs/decisions/2026-07-30-self-review-round-different-from-the-las.md`) to refresh the narrative sections. For Codex specifically, query it directly via `codex exec` rather than through `synlynk decide` until the 120s timeout in `synlynk/team.py:329` is made configurable (see Known Gaps below) — the panel tool has failed to get a Codex response twice against this doc's own compilation.

### Version snapshot

Captured directly via each vendor's own `--version` output, not self-reported narrative (higher confidence than the panel round for this specific field). CLI is the only surface independently verified this pass — IDE extension, web/chatbot, desktop/app, and API surface versions are **not tracked here yet** and should be added at the next calibration pass (each vendor typically versions these independently of the CLI).

| Harness | CLI surface | CLI version (captured 2026-07-30) | IDE ext. version | Web/chatbot version | Desktop/app version | API version |
|---|---|---|---|---|---|---|
| Claude | `claude` | 2.1.220 (Claude Code) | not captured — next pass | not captured — next pass | not captured — next pass | n/a (Messages API is versioned by request header, not a CLI concern) |
| Agy | `agy` | 1.1.8 | not captured — next pass | not captured — next pass | n/a (no separate desktop app known) | not captured — next pass |
| Codex | `codex` | 0.144.1 (`codex-cli`) | not captured — next pass | n/a per self-report | `codex app`/`app-server` share CLI's version, not separately tracked | not captured — next pass |
| Grok | `grok` | 0.2.106 (`bde89716f679`) | not captured — next pass (ACP/stdio "agent mode" shares core, per self-report) | n/a per self-report (grok.com/X chat is a different product) | n/a per self-report | not captured — next pass |

---

## Claude (Claude Code, CLI v2.1.220 — see Version Snapshot above)

**Capability matrix**
- **CLI** (primary surface): OAuth (claude.ai login) or API key. Full tool/function-calling (Read/Write/Edit/Bash/Grep/Glob/Agent/MCP). Shell execution via Bash tool. Network egress via WebFetch/WebSearch/MCP servers. First-class MCP client (stdio + SSE). Permission model: per-tool prompts gated by `settings.json`/`settings.local.json` allow/deny/ask lists, plus `--allowedTools`/`--dangerously-skip-permissions` flags.
- **IDE extensions** (VS Code/JetBrains): same core engine, adds editor-context tools (open file, diagnostics); permission prompts route through the IDE UI instead of terminal stdin.
- **Desktop app**: GUI wrapper around the CLI. No separate mobile app.
- **Web/chatbot** (claude.ai): a different, more limited product — no shell/filesystem access, no tool-calling parity with the CLI.

**Interactive vs. headless**
Bash/file tools behave identically headless when pre-authorized via `--allowedTools` or `settings.json` rules. Anything not covered by a rule and not explicitly denied hits a hard blocking prompt interactively; headless (`-p`/print mode, CI, dispatch) has no stdin to answer it, so the call **errors loudly** — a permission-denied exception surfaces in output. **Not silent, not a hang.**

**Config & control surfaces**
`~/.claude/settings.json` (global) + per-repo `.claude/settings.json`/`settings.local.json` control permissions, hooks, env vars. CLI flags (`--allowedTools`, `--disallowedTools`, `--permission-mode`, `--dangerously-skip-permissions`) override at invocation time. Confirmed accurate against synlynk's existing assumption.

**Known gaps (headless via orchestrator)**
- No durable memory across dispatch invocations unless synlynk injects it.
- Long-running interactive confirmations (e.g., destructive git ops) hard-fail headless unless pre-approved.
- MCP servers requiring OAuth handshakes can stall headless.

**Self-correction vs. PR #587**
No silent failure mode to correct — the gap is a loud error. Propose-and-apply config diffs gated on `--yes` (design spec §2a) are a good fit as-is: `settings.json` is designed to be machine-edited.

---

## Agy (Google Antigravity, CLI v1.1.8 — see Version Snapshot above)

**Capability matrix**
- **CLI & headless** (`agy`): auth via Google OAuth2 or API key. Native tool-calling (`view_file`, `replace_file_content`, `run_command`, subagent orchestration, background scheduling, web search, MCP tools). Governed by a granular permission policy engine (`allow`/`ask`/`deny`).
- **IDE & web**: shares core function-calling, plus visual preview artifacts, browser automation, interactive UI modals (`ask_question`).

**Interactive vs. headless**
Interactive sessions prompt operators dynamically for `ask`-tier permissions. In headless/scripted mode, ungranted permissions do **not** hang or block — they trigger an immediate **silent auto-deny** (`PERMISSION_DENIED`), an error payload returned directly into the agent's own context (not surfaced to the operator as a distinct signal).

**Config & control surfaces**
- Files: `~/.gemini/antigravity-cli/settings.json` and `~/.gemini/config/permissions.json`.
- Rule format: `command(<prefix>)`, `read_file(<path>)`, `write_file(<path>)`, `mcp(<target>)`.
- Flags/env: `AGY_HEADLESS=1`, `GEMINI_API_KEY`, `--auto-approve`.
- Confirmed accurate against synlynk's existing `settings.json` allow-rule assumption.

**Known gaps (headless via orchestrator)**
- Interactive prompts (`ask_question`, `escalate_admin`) cannot be answered headless — immediate fallback/denial.
- Any shell command missing an explicit matching prefix rule in `settings.json` fails silently, with no runtime authorization path.

**Self-correction vs. PR #587**
Confirms PR #587's diagnosis exactly: ungranted permissions → fast silent auto-deny, not a deadlock. But the proposed runtime `--yes` diff prompt is a poor fit for headless orchestration (headless can't answer a runtime prompt any better than it can answer `ask_question`). Recommends **pre-flight manifest seeding** — pre-populate required permission rules into `settings.json` *before* the harness is invoked, not during the run.

---

## Grok (Grok Build CLI, v0.2.106 `bde89716f679` — see Version Snapshot above)

**Capability matrix**
- **Primary surface: local CLI** (`~/.grok/bin/grok`) — interactive TUI + headless (`-p`/`--single`). Auth: browser OAuth, device-code, or `XAI_API_KEY`. Full agent loop: file R/W, shell, web search/fetch, subagents, MCP (`search_tool`/`use_tool`), image/video gen in this environment. Shell and network work unless sandbox/profile restricts them.
- **ACP/stdio "agent mode"**: same core, different transport, for IDE embedding.
- **Not covered by this harness**: grok.com/X chat, mobile apps, raw model API without the agent runtime.

**Interactive vs. headless**
Headless is first-class: `--output-format plain|json|streaming-json`, `--tools`/`--disallowed-tools`/`--max-turns` (headless-only). On a permission wall: **no hang** — the would-prompt call is cancelled and reported back to the model. `dontAsk` auto-denies anything not allowlisted or built-in read-only. Unattended runs need `--yolo`/`--always-approve`/`--permission-mode bypassPermissions` (or a durable `defaultMode`). Explicit `deny` rules and PreToolUse hooks still apply even under always-approve.

**Config & control surfaces**
Precedence: CLI → env → config.
- CLI: `--permission-mode`, `--allow`/`--deny`, `--yolo`/`--always-approve`, `--tools`/`--disallowed-tools`, `--sandbox`.
- Files: `~/.grok/config.toml` (`[permission]`, `[ui]`), project `.grok/config.toml`, `sandbox.toml`, Claude-compatible `.claude/settings.json` (`permissions.defaultMode`/allow/deny/ask), `requirements.toml` locks.
- Env: `XAI_API_KEY`, `GROK_HOME`, `GROK_SANDBOX`, etc.

**Corrects synlynk's prior assumption:** `_permissions_to_flags` genuinely does fall through to `[]` for Grok (confirmed real gap) — but it's **not accurate** that Grok "only inherits Claude's instructions with no config of its own." Claude-compatible `settings.json` reading is one compatibility layer Grok happens to also support, alongside its own native flags/config listed above. `dispatch.py` already does some Grok-specific wiring outside `_permissions_to_flags` (`always_approve_unsupported` → `--permission-mode bypassPermissions`, `--output-format json`, `_inject_grok_rules` for `GROK.md` context).

**Known gaps (headless via orchestrator)**
- No role-permission → `--allow`/`--deny`/`--tools` mapping exists yet; only coarse always-approve is wired.
- CWD/worktree still easy to get wrong if not passed explicitly.
- API cost fields incomplete on some OAuth paths.
- macOS sandbox child-network block is currently a no-op.
- MCP/tools need local config, not dispatch-time grants.

**Self-correction vs. PR #587**
Permission-class translation is effectively a no-op in `_permissions_to_flags` — correct. But not a total permission vacuum: `bypassPermissions` is already applied in some paths. The "research whether flags exist" framing in the original spec was wrong — they demonstrably exist; the work is wiring them, not discovering them. Remediation preference: **dispatch-time CLI flags** (`--allow`/`--deny`, mode, optional `--sandbox`) as the primary lever; config-file diffs to `~/.grok/config.toml` are fine for durable project policy (still `--yes` + audit log), not as the main per-job mechanism.

---

## Codex (OpenAI Codex CLI v0.144.1)

*Note on provenance: Codex timed out at the 120s hardcoded limit in `synlynk decide`/`_run_agent_sync` (`synlynk/team.py:329`) on two separate attempts within the panel tool. It responded successfully once queried directly (`codex exec - -s workspace-write`, no artificial timeout, ~44K tokens used, several minutes). This is itself a known-gap data point — see below.*

**Capability matrix**
- **CLI / `codex exec`**: auth via `codex login` (`--with-api-key`, `--with-access-token`, or `--device-auth`). Built-in tool use, file read/write, shell execution, `--search` web search, `mcp`/`mcp-server`, approval/sandbox controls.
- **IDE extension**: no separate Codex IDE-extension surface confirmed by the CLI's own maintainer from this binary.
- **Web/chatbot, API**: not a first-class surface of the local Codex CLI harness — no CLI parity claimed.
- **Desktop/app-server**: `codex app`, `app-server`, `remote-control` exist but share the same local Codex stack and permission model, not a separate one.

**Interactive vs. headless**
`codex exec` is designed to run non-interactively. When approval is disallowed, failures are "immediately returned to the model" — **a loud failure surfaced back into the run, not a silent deny and not a hang.** Same pattern as Claude, distinct from Agy's silent auto-deny.

**Config & control surfaces — corrects synlynk's prior assumption**
- `~/.codex/config.toml` is real; `-c/--config`, `--profile`, `--ignore-user-config`, `--strict-config`, `--enable`/`--disable` are real controls.
- **Correction: the approval flag is `--ask-for-approval` (`untrusted|on-request|never`), not `--approval-policy`** as `AGENT_CAPABILITY_BASELINES` currently assumes.
- `--sandbox` is real, with `read-only|workspace-write|danger-full-access`. `--dangerously-bypass-approvals-and-sandbox` exists and is explicitly unsafe (confirms the existing code-comment warning against ever defaulting to it).
- **Cannot confirm the `[sandbox_workspace_write]` TOML table with `network_access`/`writable_roots` keys from the current binary's own help output** — this is the exact write-back target §2a's Codex remediation path assumes exists. The `codex sandbox` subcommand instead exposes `--sandbox-state-disable-network`, `--sandbox-state-readable-root`, `--allow-unix-socket`, `--permission-profile`. **This needs independent verification (e.g. against actual `config.toml` schema docs, not just `--help`) before §2a's Codex write-back mechanism is implemented — treat as unconfirmed, not as a known-good target.**

**Known gaps (headless via orchestrator)**
- Headless runs cannot answer live prompts — anything still needing human approval fails fast, not silently.
- No fine-grained per-tool allowlist surface like some other harnesses expose — control is coarser-grained, via sandbox/approval/profile only.
- Network/file boundaries are sandbox-driven; orchestrators should not assume a narrower policy than the CLI actually exposes.
- **The 120s timeout in `synlynk decide` is too short for Codex under some prompts** — this query alone used ~44K tokens and took several minutes when unconstrained. Any synlynk tooling that queries Codex headless (panel reviews, self-review rounds, dispatch) should treat a >120s silence as "still working," not "failed," for anything beyond a trivial prompt.

**Self-correction vs. PR #587**
- The `api.github.com` network-egress-blocked-by-design claim **cannot be confirmed from the Codex CLI itself** — treat as unproven pending separate testing, not as an established fact.
- Propose-and-apply config diffs gated on `--yes` are a **poor primary fit** — the CLI's own design center is direct flags and config overrides at invocation time, not runtime config-edit prompts. Same preference pattern as Grok.

---

## Cross-harness summary

| Harness | Headless permission-wall behavior | Primary remediation lever | Config confirmed accurate? |
|---|---|---|---|
| Claude | Loud error (exception surfaced) | Runtime propose-and-apply diff to `settings.json`, `--yes`-gated | Yes |
| Agy | Silent auto-deny (`PERMISSION_DENIED`) | Pre-flight manifest seeding into `settings.json` before invocation | Yes |
| Grok | Cancelled-and-reported-to-model, no hang | Dispatch-time CLI flags (`--allow`/`--deny`/`--permission-mode`); config diffs for durable policy only | Corrected — Grok has real native config, not just Claude-inheritance |
| Codex | Loud failure surfaced back into the run, not silent | Direct flags/config overrides at invocation (`--ask-for-approval`, `--sandbox`), not runtime diff prompts | **No** — flag name was wrong (`--ask-for-approval`, not `--approval-policy`), and the assumed `[sandbox_workspace_write]` write-back target is unconfirmed by the CLI's own `--help` output |

**Pattern across all four:** none confirmed a silent-deny-only or hang failure mode except Agy. Three of four (Claude, Codex, Grok) push back on a uniform "runtime `--yes` diff prompt" remediation mechanism, each for a different reason (loud-error-already-informative, flags-are-the-real-interface, or headless-can't-answer-a-prompt-anyway). Only Agy's failure mode and only Claude's remediation fit match the design spec's original uniform assumption.

**Surface-capability asymmetry (counting the 7 capability-matrix dimensions — auth, tool-calling, file R/W, shell exec, network egress, MCP support, permission model — present per surface):** Claude and Agy are the only two harnesses whose non-CLI surfaces add *genuinely new* capability (Claude's IDE extension adds editor-context tools; Agy's IDE/web surface adds visual preview, browser automation, and an interactive `ask_question` modal) rather than just rehosting the CLI. Grok's non-CLI surface (ACP/stdio "agent mode") is a transport variant with no capability delta. Codex is the most CLI-concentrated of the four: every other surface either shares the identical stack (`codex app`/`app-server`) or has no confirmed presence at all (no separate IDE extension, no first-class web/chatbot/API surface). Implication for synlynk: dispatch-time capability assumptions ported from one harness's IDE/desktop behavior do not generalize — Codex in particular should be treated as CLI-only for capability-detection purposes until a non-CLI surface is independently confirmed.
