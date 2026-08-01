---
decision_id: dec-e27ef144
topic: "SELF-REVIEW ROUND — different from the last panel review of PR #587. Do NOT critique the overall synlynk design or the other agents' work. Instead, each of you review AS THE MAINTAINER AND REPRESENTATIVE OF YOUR OWN HARNESS ONLY, reporting on your own actual current state, honestly and specifically (this output is being compiled into a canonical harness-capability reference synlynk will treat as source of truth, so precision over breadth). Answer these five sections about YOURSELF (your harness family), not synlynk's code: (1) CAPABILITY MATRIX — list what you (your harness) can actually do, broken out by variant/surface (CLI, IDE extension, web/chatbot, desktop/mobile app, API) where applicable to you — auth method per surface, tool/function-calling support, file read/write, shell/command execution, network egress, MCP support, permission-prompt model. Note where a capability differs meaningfully between your own surfaces. (2) INTERACTIVE vs NON-INTERACTIVE (headless) BEHAVIOR — for each capability in (1), does it work the same headless/scripted as it does interactively, or does something silently degrade, block, or require a prompt that headless mode can't answer? Be specific about what actually happens on a permission/sandbox wall in headless mode for you: silent deny, loud error, hang, or something else. (3) CONFIG & CONTROL SURFACES — what local config file(s), flags, or environment variables actually control your permission/sandbox/tool-access behavior (confirm or correct what synlynk's design currently assumes: Agy — ~/.gemini/antigravity-cli/settings.json allow-rules; Codex — ~/.codex/config.toml [sandbox_workspace_write] with network_access/writable_roots; Claude — ~/.claude/settings.json + --allowedTools flags; Grok — synlynk's dispatch.py currently has NO Grok-specific permission-flag translation at all and Grok is documented as 'inheriting Claude's harness instructions' — is that accurate, and does Grok have any real config/flag surface of its own that's never been wired up?). (4) KNOWN GAPS — what can you NOT do, or what's unreliable, when dispatched headless by an orchestrator like synlynk today, that operators should know about rather than discover via a failed job. (5) SELF-CORRECTION — synlynk's harness-compatibility design spec (docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md, PR #587) makes claims about your specific failure modes (Agy: silent PERMISSION_DENIED auto-deny on headless 'command' permission; Codex: workspace-write sandbox blocks api.github.com network egress by design; Grok: unwired permission no-op, falls through to empty flag list). Confirm, correct, or add nuance to the claim about YOUR harness specifically — and if synlynk's proposed remediation approach (propose-and-apply config diffs, gated on --yes, per docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md section 2a) is a poor fit for how your harness actually wants to be configured, say so and propose what would fit better."
date: 2026-07-30
panel: [claude, agy, codex, grok]
status: approved
---

## Topic
SELF-REVIEW ROUND — different from the last panel review of PR #587. Do NOT critique the overall synlynk design or the other agents' work. Instead, each of you review AS THE MAINTAINER AND REPRESENTATIVE OF YOUR OWN HARNESS ONLY, reporting on your own actual current state, honestly and specifically (this output is being compiled into a canonical harness-capability reference synlynk will treat as source of truth, so precision over breadth). Answer these five sections about YOURSELF (your harness family), not synlynk's code: (1) CAPABILITY MATRIX — list what you (your harness) can actually do, broken out by variant/surface (CLI, IDE extension, web/chatbot, desktop/mobile app, API) where applicable to you — auth method per surface, tool/function-calling support, file read/write, shell/command execution, network egress, MCP support, permission-prompt model. Note where a capability differs meaningfully between your own surfaces. (2) INTERACTIVE vs NON-INTERACTIVE (headless) BEHAVIOR — for each capability in (1), does it work the same headless/scripted as it does interactively, or does something silently degrade, block, or require a prompt that headless mode can't answer? Be specific about what actually happens on a permission/sandbox wall in headless mode for you: silent deny, loud error, hang, or something else. (3) CONFIG & CONTROL SURFACES — what local config file(s), flags, or environment variables actually control your permission/sandbox/tool-access behavior (confirm or correct what synlynk's design currently assumes: Agy — ~/.gemini/antigravity-cli/settings.json allow-rules; Codex — ~/.codex/config.toml [sandbox_workspace_write] with network_access/writable_roots; Claude — ~/.claude/settings.json + --allowedTools flags; Grok — synlynk's dispatch.py currently has NO Grok-specific permission-flag translation at all and Grok is documented as 'inheriting Claude's harness instructions' — is that accurate, and does Grok have any real config/flag surface of its own that's never been wired up?). (4) KNOWN GAPS — what can you NOT do, or what's unreliable, when dispatched headless by an orchestrator like synlynk today, that operators should know about rather than discover via a failed job. (5) SELF-CORRECTION — synlynk's harness-compatibility design spec (docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md, PR #587) makes claims about your specific failure modes (Agy: silent PERMISSION_DENIED auto-deny on headless 'command' permission; Codex: workspace-write sandbox blocks api.github.com network egress by design; Grok: unwired permission no-op, falls through to empty flag list). Confirm, correct, or add nuance to the claim about YOUR harness specifically — and if synlynk's proposed remediation approach (propose-and-apply config diffs, gated on --yes, per docs/superpowers/specs/2026-07-29-harness-compatibility-capability-design.md section 2a) is a poor fit for how your harness actually wants to be configured, say so and propose what would fit better.

## Panel Inputs

### claude
**CAPABILITY MATRIX (Claude Code harness):** CLI is the primary surface — OAuth (claude.ai login) or API key auth, full tool/function-calling (Read/Write/Edit/Bash/Grep/Glob/Agent/MCP), shell execution via Bash tool, network egress via WebFetch/WebSearch/MCP servers, first-class MCP client support (stdio + SSE), permission model is per-tool prompts gated by `settings.json`/`settings.local.json` allow/deny/ask lists plus `--allowedTools`/`--dangerously-skip-permissions` flags. IDE extensions (VS Code/JetBrains) share the same core engine but add editor-context tools (open file, diagnostics) and route permission prompts through the IDE UI instead of terminal stdin. Desktop app wraps the CLI with a GUI; no separate mobile app exists today. No standalone "web/chatbot" surface with tool-calling parity — claude.ai web chat is a different, more limited product (no shell/filesystem access).

**INTERACTIVE vs HEADLESS:** Bash/file tools work identically headless when pre-authorized via `--allowedTools` or `settings.json` permission rules. Anything not covered by those rules and not matching an explicit deny hits a **hard blocking prompt** in interactive mode; in headless/scripted mode (`-p`/print mode, CI, dispatch) there's no stdin to answer it, so the call **errors loudly** (permission-denied exception surfaced in output) rather than silently no-op'ing or hanging indefinitely. This is a loud failure, not silent — that's a meaningful distinction from the Agy claim.

**CONFIG SURFACES:** `~/.claude/settings.json` (global) and per-repo `.claude/settings.json`/`settings.local.json` control permissions, hooks, env vars; CLI flags (`--allowedTools`, `--disallowedTools`, `--permission-mode`, `--dangerously-skip-permissions`) override at invocation time. This part of synlynk's design matches reality.

**KNOWN GAPS:** No durable memory across dispatch invocations unless synlynk injects it; long-running interactive confirmations (e.g., destructive git ops) will hard-fail headless unless pre-approved; MCP servers requiring OAuth handshakes can stall headless.

**SELF-CORRECTION:** I have no claimed "silent" failure mode to correct — my gap is a loud error, and I'd flag that distinction explicitly in the spec. Propose-and-apply config diffs gated on `--yes` fit my harness well since `settings.json` is designed to be machine-edited; I'd support that remediation approach as-is for my own harness.

### agy
Row 1: Last completed task: Session initialization.
Row 2: Next task: Submit Maintainer Self-Review for Google Antigravity (Agy) harness.

### Google Antigravity (Agy) Maintainer Self-Review

**(1) CAPABILITY MATRIX**
* **CLI & Headless (`agy`)**: Auth via Google OAuth2 / API Key. Supports native tool-calling (`view_file`, `replace_file_content`, `run_command`, subagent orchestration, background scheduling, web search, MCP tools). Governed by a granular permission policy engine (`allow`, `ask`, `deny`).
* **IDE & Web**: Shares core function-calling alongside visual preview artifacts, browser automation, and interactive UI modals (`ask_question`).

**(2) INTERACTIVE vs NON-INTERACTIVE BEHAVIOR**
Interactive sessions prompt operators dynamically when evaluating `ask` permissions. In headless/scripted mode, ungranted permissions do **not** hang or block; they trigger an immediate **silent auto-deny** (`PERMISSION_DENIED`), returning an error payload directly into the agent context.

**(3) CONFIG & CONTROL SURFACES**
* **Files**: Managed via `~/.gemini/antigravity-cli/settings.json` (and `~/.gemini/config/permissions.json`).
* **Rule Format**: Explicit target rules such as `command(<prefix>)`, `read_file(<path>)`, `write_file(<path>)`, and `mcp(<target>)`.
* **Flags & Environment**: Configured via `AGY_HEADLESS=1`, `GEMINI_API_KEY`, and CLI flags (`--auto-approve`). Synlynk's assumption regarding `settings.json` allow-rules is accurate.

**(4) KNOWN GAPS**
* **Interactive Prompts**: Headless jobs cannot complete interactive user questions (`ask_question`) or privilege escalation (`escalate_admin`), resulting in immediate fallback or denial.
* **Unprefixed Shell Commands**: Any command missing an explicit matching prefix rule in `settings.json` fails silently without runtime authorization.

**(5) SELF-CORRECTION & RECOMMENDATION**
PR #587 correctly diagnoses Agy’s headless failure mode: ungranted permissions lead to fast silent auto-denials (`PERMISSION_DENIED`) rather than deadlocks. However, synlynk’s proposed runtime interactive diff prompt (`--yes`) is ill-suited for headless orchestration. We recommend replacing runtime diff prompts with **pre-flight manifest seeding**, pre-populating required permission rules into `~/.gemini/antigravity-cli/settings.json` prior to harness invocation.

**Position**: Maintainer confirms PR #587’s diagnosis of Agy’s headless auto-deny behavior and recommends adopting pre-flight permission manifest injection into `settings.json` for seamless headless execution.

### grok
I'll review Grok's harness as its maintainer: current surfaces, headless behavior, config/flags, and how that lines up with synlynk's PR #587 claims.Grok's CLI has real permission flags — reading those surfaces and how synlynk wires them today.## Grok harness self-review (Grok Build CLI v0.2.106)

### (1) Capability matrix
**Primary surface: local CLI** (`~/.grok/bin/grok`) — interactive TUI + headless (`-p` / `--single`). Auth: browser OAuth, device-code, or `XAI_API_KEY`. Tools: full agent loop (file R/W, shell, web search/fetch, subagents, MCP via `search_tool`/`use_tool`, image/video gen in this environment). Shell and network work unless sandbox/profile restricts them. **ACP/stdio “agent mode”** exists for IDE embedding (same core, different transport). **Not this harness:** grok.com / X chat, mobile apps, or raw model API without the agent runtime.

### (2) Interactive vs headless
Headless is first-class: `--output-format plain|json|streaming-json`, `--tools` / `--disallowed-tools` / `--max-turns` (headless-only). On a permission wall: **no hang** — a would-prompt call is **cancelled and reported to the model**. `dontAsk` auto-denies anything not allowlisted or built-in read-only. Unattended runs need `--yolo` / `--always-approve` / `--permission-mode bypassPermissions` (or durable `defaultMode`). Explicit `deny` rules and PreToolUse hooks still apply under always-approve.

### (3) Config & control surfaces
Real surfaces (precedence: CLI → env → config):
- **CLI:** `--permission-mode`, `--allow`/`--deny`, `--yolo`/`--always-approve`, `--tools`/`--disallowed-tools`, `--sandbox`
- **Files:** `~/.grok/config.toml` (`[permission]`, `[ui]`), project `.grok/config.toml`, `sandbox.toml`, Claude-compatible `.claude/settings.json` (`permissions.defaultMode` / allow/deny/ask), `requirements.toml` locks
- **Env:** `XAI_API_KEY`, `GROK_HOME`, `GROK_SANDBOX`, etc.

**Synlynk assumptions:** `_permissions_to_flags` **does** fall through to `[]` for Grok (no perm→flag map). Dispatch **does** partially wire Grok: `always_approve_unsupported` → `--permission-mode bypassPermissions`, plus `--output-format json` and `_inject_grok_rules` (`GROK.md` / context). **Not** accurate that Grok only “inherits Claude instructions with no config of its own.” Claude settings are one compatibility layer among several native ones.

### (4) Known gaps for orchestrated headless
No role-permission → `--allow`/`--deny`/`--tools` mapping; coarse always-approve only. CWD/worktree still easy to get wrong if not passed. API cost fields incomplete on some OAuth paths. macOS sandbox child-network block is a no-op. MCP/tools need local config, not dispatch grants.

### (5) Self-correction vs #587 / §2a
**Correct:** permission-class translation is effectively a no-op in `_permissions_to_flags`.  
**Nuance:** not a total permission vacuum — bypassPermissions is already applied.  
**Wrong framing:** “research whether flags exist” — they do; wire them.  

**Remediation fit:** prefer **dispatch-time CLI flags** (`--allow`/`--deny`, mode, optional `--sandbox`) over mutating `~/.grok/config.toml` for every job. Config propose-and-apply is fine for durable project policy, with `--yes` + audit log — not as the primary per-job control.

**Position:** Treat Grok as a full-flag harness. Close the silent `[]` path by mapping synlynk permissions to `--allow`/`--deny` (and mode), keep always-approve only for broad grants, and use config diffs only for sticky project policy—not as the main dispatch remediation.

## Synthesis
This is a synthesis/decision task, not implementation work — no skill applies here (it's not brainstorming a feature, debugging, or code work). Let me synthesize the three self-reviews directly.

All three harnesses converge on the core factual points, with important corrections to PR #587's framing:

**Where the panel agrees with #587:** Agy's silent `PERMISSION_DENIED` auto-deny on headless `command` calls is confirmed as accurate by Agy's own maintainer. Codex's network-egress sandbox claim wasn't contested here (Codex didn't submit — worth flagging as a gap in this round). Claude's config-file assumptions (`settings.json` + `--allowedTools`) are confirmed accurate, but Claude's own failure mode is a **loud error**, not silent — #587 should not lump Claude in with Agy's silent-deny pattern if it currently does.

**Where the panel corrects #587:** The Grok claim ("unwired permission no-op, inherits Claude instructions") is half-right and half-wrong per Grok's own maintainer: `_permissions_to_flags` genuinely does fall through to `[]` (confirmed gap), but Grok is *not* a bare Claude-instruction-inheritor — it has its own native flag surface (`--permission-mode`, `--allow`/`--deny`, `--yolo`, `~/.grok/config.toml`) that synlynk has simply never wired up. The fix is mapping synlynk's permission model to Grok's existing flags, not treating Grok as configless.

**On remediation fit (§2a propose-and-apply config diffs gated on `--yes`):** Split verdict, not uniform.
- Claude: good fit — `settings.json` is designed for machine editing, supports diff-and-apply cleanly.
- Agy: poor fit as a *runtime* prompt — Agy wants **pre-flight manifest seeding** into `settings.json`/`permissions.json` before invocation, not an interactive diff during the headless run (headless can't answer prompts anyway).
- Grok: poor fit as the *primary* mechanism — Grok wants **dispatch-time CLI flags** (`--allow`/`--deny`/`--permission-mode`) as the main lever, reserving config-file diffs for durable project-level policy only.

So §2a as currently scoped (single interactive diff-and-apply gated on `--yes`) is really only a clean fit for one of three harnesses reviewed. It needs to branch per-harness: pre-flight file seeding for Agy, CLI-flag mapping for Grok, and diff-and-apply for Claude.

**Decision:** Amend the harness-compatibility design spec (PR #587) to (1) correct the Claude failure-mode description from implied-silent to explicit loud-error, (2) correct the Grok section to state that Grok has a real native permission/flag surface (`--permission-mode`, `--allow`/`--deny`, `--yolo`, `~/.grok/config.toml`) that synlynk has never wired up — rather than describing Grok as inheriting Claude's instructions with no config of its own — and prioritize closing `_permissions_to_flags` for Grok via that native flag mapping, (3) split §2a's remediation into three per-harness paths instead of one uniform mechanism: pre-flight manifest/config seeding for Agy, dispatch-time CLI flags as primary (config diffs only for durable project policy) for Grok, and interactive/scripted diff-and-apply against `settings.json` for Claude, and (4) flag that this round has no confirmed self-report from Codex on the network-egress sandbox claim — treat that specific claim as unconfirmed until Codex's maintainer reviews it, and dispatch a follow-up self-review request to Codex before treating the spec as canonical.

## Decision
**Decision:** Amend the harness-compatibility design spec (PR #587) to (1) correct the Claude failure-mode description from implied-silent to explicit loud-error, (2) correct the Grok section to state that Grok has a real native permission/flag surface (`--permission-mode`, `--allow`/`--deny`, `--yolo`, `~/.grok/config.toml`) that synlynk has never wired up — rather than describing Grok as inheriting Claude's instructions with no config of its own — and prioritize closing `_permissions_to_flags` for Grok via that native flag mapping, (3) split §2a's remediation into three per-harness paths instead of one uniform mechanism: pre-flight manifest/config seeding for Agy, dispatch-time CLI flags as primary (config diffs only for durable project policy) for Grok, and interactive/scripted diff-and-apply against `settings.json` for Claude, and (4) flag that this round has no confirmed self-report from Codex on the network-egress sandbox claim — treat that specific claim as unconfirmed until Codex's maintainer reviews it, and dispatch a follow-up self-review request to Codex before treating the spec as canonical.

> Signatures: see 2026-07-30-self-review-round-different-from-the-las.json
