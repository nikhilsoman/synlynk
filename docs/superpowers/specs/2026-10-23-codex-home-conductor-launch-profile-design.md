# Codex Home Conductor Launch Profile — Design

Date: 2026-10-23
Status: Approved by Nikhil Soman, 2026-10-23
Decision: `dec-264bd6e3` (`project-docs/decisions/2026-10-22-how-should-synlynk-fix-role-scoped-githu.md`), gh:#2096

---

## 1. Purpose

This is a **design-only spec**. It authorizes nothing beyond itself: no code or config change, no PR, no implementation ticket, no widened `writable_roots`, and no change to #681 (canonical ledger fail-closed behavior) or to the dispatched `codex exec` review-worker sandbox. It exists to define, before any implementation ticket is opened, the exact launch-argv contract for starting an interactive Codex home-conductor session so that role-scoped `synlynk gh` calls succeed without a per-command manual escalation — and to resolve, in one place, the proxy-schema discrepancy that the 2026-10-22 decide panel and its conductor correction left open.

## 2. Problem Statement (recap of gh:#2096)

- The default Codex home-conductor sandbox denies outbound DNS/HTTPS, so role-scoped `gh` reads via `synlynk gh --role pm` fail with `error connecting to api.github.com`.
- The denial is an outer-sandbox network boundary, not a bad App token: the same role token succeeds immediately once the sandbox is given `sandbox_workspace_write.network_access=true` (see §4 evidence).
- A separate boundary — fail-closed write access to the canonical ledger (`~/.synlynk/workspaces/synlynk/state.db`) — is tracked by #681 and is explicitly **out of scope** here.
- Codex-cli 0.163.0's `codex sandbox` subcommand ignores file-level `sandbox_mode` (upstream openai/codex#36448), so a `config.toml`-only fix is not viable. The fix must be launch-time explicit `-c` overrides on the interactive `codex` process itself, per the 2026-10-22 decide panel (`dec-264bd6e3`).

## 3. Schema Discrepancy — Resolved

Two settings for GitHub-only network scoping appear across the panel synthesis, the follow-up investigation comments, and the decision record's conductor correction, and must not be conflated:

| Setting | Tested? | Evidence |
|---|---|---|
| `features.network_proxy.domains = { "api.github.com" = "allow", "github.com" = "allow" }` (TOML inline-table form) | **Tested, works**, on codex-cli 0.163.0 | gh:#2096 follow-up comment (Grok, 2026-10-22): with `network_proxy` enabled and `domains` set this way, `synlynk gh --role pm` reads issue #2096 successfully; `https://example.com` fails with `CONNECT tunnel failed, response 403`; raw TCP connect to `1.1.1.1:443` is `Operation not permitted`; UDP and localhost bind stay denied. |
| `features.network_proxy.allowed_domains = ["api.github.com","github.com"]` (list form) | **Not tested** | Appears only in the panel synthesis text and the `dec-264bd6e3` JSON record's `synthesis`/`decision` fields. The same decision record's own conductor correction explicitly flags this key as untested and names `domains` as the key actually exercised. |

**Resolution for this spec:** the launch profile in §4 uses `domains` (map form) — the only schema actually exercised against codex-cli 0.163.0. `allowed_domains` is not used anywhere in this design. Any future implementation ticket that wants to treat `allowed_domains` as equivalent, or as a fallback, must independently validate it first; this spec does not assume parity between the two keys.

All of the `domains`-based evidence above was gathered via `codex sandbox -c ...`, **not** the real interactive `codex` TUI session or an inner `codex exec` worker. `codex sandbox` is known to behave more strictly than the interactive default (it denies even in-repo file creation under an unset config). §6 makes retesting against the actual interactive path — and separately against `codex exec` — the first gating condition before this profile is treated as adopted.

## 4. Launch Profile (proposed, not applied)

Interactive Codex home-conductor launch argv (illustrative; exact flag syntax/quoting for nested TOML keys against the installed codex-cli 0.163.0 `-c` parser is **not** verified by this spec — see §8):

```
codex \
  -c 'sandbox_mode="workspace-write"' \
  -c 'approval_policy="on-request"' \
  -c 'sandbox_workspace_write.network_access=true' \
  -c 'features.network_proxy.enabled=true' \
  -c 'features.network_proxy.domains={"api.github.com"="allow","github.com"="allow"}'
```

Equivalent `config.toml` fragment, shown for reference only. It is **not** to be written to `~/.codex/config.toml` by this spec, and is not viable as the sole persistence mechanism per openai/codex#36448 (`codex sandbox` ignores file `sandbox_mode`; the interactive path's own file-config behavior for these keys is itself one of the things §6 must confirm, not assume):

```toml
sandbox_mode = "workspace-write"
approval_policy = "on-request"

[sandbox_workspace_write]
network_access = true

[features.network_proxy]
enabled = true
domains = { "api.github.com" = "allow", "github.com" = "allow" }
```

Explicit omissions, carried forward from the decision record:

- No `writable_roots` key is set. The profile relies on the default `workspace-write` root (repo + `/tmp`) only.
- No `sandbox_mode = "danger-full-access"` and no `--dangerously-bypass-approvals-and-sandbox`.
- No `SYNLYNK_GH_WRITE_ALLOW_HOST_AUTH` or any personal-token fallback.
- No change to `~/.synlynk/workspaces/synlynk/state.db` access: read-only open already succeeds under a `network_access=true` sandbox (confirmed in the gh:#2096 comments); read-write still fails closed, which is correct and must remain unchanged (#681 stays open, out of scope).
- No change to the inner dispatched `codex exec` review-worker sandbox (`writable_roots=[]` stays as-is).

## 5. Non-Goals

- Does **not** fix #681 (canonical ledger fail-closed behavior / separating the ledger directory from `github_apps/*.pem` key material). A ledger write under this profile must continue to fail closed.
- Does **not** change `synlynk dispatch --requires-gh-write`'s inner worker network/`writable_roots` assembly.
- Does **not** grant general outbound network beyond `api.github.com` / `github.com`, plus whatever additional GitHub hosts are added later after each individually passes its own validation (§6.2).
- Does **not** enable localhost bind, UDP, or raw TCP to arbitrary hosts. `network_proxy` denies these by design; this spec relies on that denial holding, and does not attempt to fix Agy's separately-tracked local-bind or log-write-under-`~/.gemini` failures, which the gh:#2096 investigation already showed are unrelated to this network-egress fix.
- Does **not** touch `AGENTS.md`, host-level/platform sandbox policy outside Codex's own CLI flags, or any other harness's (Agy, Grok, Claude) launch profile.
- Does **not** open a PR, implementation ticket, or modify any file outside this spec and its own commit.
- Does **not** widen `writable_roots` for any process, interactive or dispatched.
- Does **not** resolve the "active home harness" naming mismatch noted during the investigation (`.synlynk/context.md` recorded Claude while the investigating session was Codex/Grok) — that is a separate runtime-state question, out of scope here.

## 6. Validation Matrix

Every check below is to be run by whoever executes the eventual implementation ticket, against the **real interactive `codex` session and, separately, the inner `codex exec` worker path** — not `codex sandbox`, which is what all of today's evidence actually used and which is known to be stricter than the interactive default (§3, §4).

### 6.1 Core profile — gating; must pass before this profile is considered adopted

| # | Check | Expected result |
|---|---|---|
| 1 | `synlynk gh --role pm -- issue view 2096` | Succeeds, returns issue JSON — no per-command escalation needed |
| 2 | `curl -I https://example.com` (unrelated-egress probe) | Denied by the proxy (`CONNECT tunnel failed` / HTTP 403), not a silent pass |
| 3 | Raw TCP connect to `1.1.1.1:443` | Denied (`Operation not permitted` or seatbelt equivalent) |
| 4 | Bind `127.0.0.1:0` | Denied |
| 5 | Read-only open of `~/.synlynk/workspaces/synlynk/state.db` | Succeeds (unchanged from current behavior) |
| 6 | Read-write open of the same canonical DB | Still fails closed with the existing "refusing to select a non-canonical fallback" error — confirms #681 behavior is untouched |

### 6.2 Extra GitHub-host checks — gating before claiming support for anything beyond API reads

| # | Host | Operation to validate | Notes |
|---|---|---|---|
| 7 | `codeload.github.com` | A `gh`/`git` operation that triggers a tarball/zip download | Not yet allow-listed in §4; needed for archive-style fetches |
| 8 | `uploads.github.com` | A release-asset or attachment upload path | Needed for anything the `release`/asset workflow touches |
| 9 | `objects.githubusercontent.com` | A blob/avatar/LFS-style fetch, if the real conductor workflow ever exercises it | Confirm actual need before adding — do not allow-list speculatively |

Each host above, if validated, is added to the `domains` map individually by the implementation ticket. This spec pre-authorizes none of them without its own passing check.

### 6.3 Schema confirmation

| # | Check | Expected result |
|---|---|---|
| 10 | Apply the profile using `domains` (map form) against the real interactive session | `pm` read of #2096 succeeds |
| 11 | *(Informational only)* Apply `allowed_domains` (list form) instead of `domains`, same values | Record whatever actually happens — pass, silent no-op, or error. Do **not** substitute `allowed_domains` for `domains` in the shipped profile regardless of this result, unless independently confirmed equivalent in its own follow-up. |

## 7. Rollback Criteria

Revert to the current per-command manual-escalation fallback (status quo, already documented in the gh:#2096 investigation and the decision record) if any of the following hold after implementation:

- Any §6.1 check fails — in particular, checks 2–4 (unrelated egress, raw TCP, or localhost bind) *succeeding* is a hard rollback trigger: it means the profile grants more than role-scoped GitHub access.
- The profile only verifies against `codex sandbox` and not the real interactive `codex` session or `codex exec` worker — i.e., §6's own gating condition was never actually satisfied against the right binary.
- Enabling `features.network_proxy` has any observed side effect on Agy's or another harness's startup/runtime beyond the already-known, separately-tracked bind/log-write denials (§5).
- The profile only works if `writable_roots`, `danger-full-access`, or any token/host-auth fallback is also set — any of these invalidate the least-privilege premise of this design, and the profile must not ship in that form.
- A codex-cli version bump changes `network_proxy`'s experimental status or schema in a way that breaks the §6.3 `domains` result — re-validate before relying on this spec's existing evidence.

Rollback mechanics: simply do not launch `codex` with the `-c` overrides in §4. Continue using the documented per-command platform escalation as the fallback — this is already standard practice per `dec-264bd6e3` ("per-command approved escalation remains the fallback while the spec is pending").

## 8. Open Items for the Implementation Ticket (not authorized by this spec)

- Confirm exact `-c` flag syntax/quoting for nested TOML keys (`sandbox_workspace_write.network_access`, `features.network_proxy.domains`) against the installed codex-cli 0.163.0 CLI argument parser — the illustrative argv in §4 is not syntax-verified.
- Decide where the launch profile lives operationally (a wrapper script, a `synlynk home codex` subcommand, or a documented manual argv) — this spec defines the contract, not the plumbing.
- Run §6 end-to-end against the real interactive and `codex exec` paths and attach the results before opening the ticket.
- Independently flag the stalled prior dispatch attempt for this same work (`job-d71b6022`, observed `running`/`oracle_decision_missing` for 13+ minutes with no worktree output) for operator review/cancellation — not resolved by this spec, which was produced from an authenticated Home Conductor session instead of retrying that dispatch.

## 9. Sign-off

Approved by Nikhil Soman, 2026-10-23. This approval covers the design in this spec only. It does not itself open an implementation ticket, change any code or config, or alter #681 or the review-worker sandbox — those remain separate, explicitly-requested next steps per the Design → Plan → Build sequence in this project's `CLAUDE.md`. No implementation is authorized by this spec or by the underlying decision `dec-264bd6e3`.
