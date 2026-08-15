# Workspace Agent Artifact Storage — Design Spec

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:writing-plans to turn this spec into an implementation plan before any code is written. Per Brainstorm-First Policy, no implementation may begin until this spec is committed and Nikhil signs off.

**Origin:** `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` §4/§5, action items 9 and 10 — the highest-leverage remaining slice of that spec, because it directly unblocks `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` §10 Phase 1 (Agent manifest + CLI config), which is next in the roadmap queue.

**Goal:** stand up canonical, workspace-scoped storage for durable agents' charter, memory, and Statements of Record, plus a stable `agent_id` identity registry — so Phase 1 of the agent-roles roadmap builds on real storage instead of a stub, and so agent identity doesn't inherit the same fork risk that hit human devlog identity before the `member_id` registry fix (PRs #949/#953/#956/#958).

**Method:** single-session brainstorm with Nikhil, working from the two source specs above plus direct inspection of the current codebase (`synlynk/__init__.py` DB centralization, the shipped `member_id`/`member_aliases` pattern in `synlynk/db.py`) to resolve two conflicts the source specs left open.

---

## 1. Two conflicts this spec resolves

**Conflict A — storage authority.** The original agent-roles-charters spec (2026-08-09, §10 Phase 1) names a **per-repo** `.synlynk/agents/<id>.yaml` as the canonical artifact. The later workspace-context-governance spec (2026-08-14, Round 7) says canonical agent artifacts must live in a **workspace-level** store, because agent identity is cross-repo (GitHub App identities per #859, gh:#914's cross-repo App scope) — a repo's `.synlynk/` may only hold pointers/projections, never canonical state.

**Resolution:** the workspace-level store wins. `.synlynk/agents/<id>.yaml` is redefined as a generated, gitignored projection (agent_id + repo-scoped overrides only) — the same source/projection treatment R5 already applied to `workspace-canon.md`. This keeps Phase 1 consistent with the more carefully reasoned, later spec instead of shipping against storage that would need migrating almost immediately.

**Conflict B — `workspace_id` doesn't exist yet.** Round 7's language (`~/.synlynk/workspaces/<workspace_id>/`) assumes the `workspace_id` concept from the 2026-06-07 multi-repo workspace design spec. That spec was approved but never implemented — the actual running code (`synlynk/__init__.py:817-828`) centralizes `state.db` at `~/.synlynk/projects/<md5(repo_root)>/state.db`, a per-repo key with no cross-repo grouping, no `repos` table, no `workspace join` CLI.

**Resolution:** this slice mints a real `workspace_id` (uuid4, generated once, written to the existing `.synlynk/config.json`) and uses it to key the new agent artifact store — but does **not** implement cross-repo workspace grouping, `state.db` relocation, the `repos` table, `sync_log`, or `synlynk workspace join`. Each repo gets its own `workspace_id` for now, which is an honest reflection of current reality rather than a fake cross-repo story. True multi-repo sharing is a separate, later follow-up gated on the 2026-06-07 spec actually being built.

## 2. Storage layout

```
.synlynk/config.json                                  ← gains "workspace_id": "<uuid4>"
                                                          (generated once, alongside existing repo_id/etc.)

~/.synlynk/workspaces/<workspace_id>/
  agents/
    registry.json                                      ← canonical agent_id registry
    <agent_id>/
      charter.md            + charter.revisions.jsonl
      memory/                                           ← memory namespace; one file per entry,
                                                            one shared revisions.jsonl
      statements-of-record/                              ← curated SoR docs, same file+revisions.jsonl pairing

<repo>/.synlynk/agents/<agent_id>.yaml                  ← GENERATED projection only. Never canonical.
                                                            Regenerated on demand. Gitignored.
```

Each canonical artifact (`charter.md`, each memory entry, each SoR doc) is paired with an append-only `<name>.revisions.jsonl`:

```json
{"revision": 3, "parent_hash": "<sha256 of revision 2's content>", "content_hash": "<sha256 of this revision's content>", "actor": "agent:dev-primary" | "human:nikhilsoman", "timestamp": "2026-08-15T20:14:00Z"}
```

Writes detect stale revisions (the writer's assumed `parent_hash` must match the current head) and refuse silently overwriting — same "revision-aware writes, emit conflict artifacts" principle Round 6 decided for the (not-yet-built) doc-lifecycle manifest, applied here independently since that manifest schema isn't shipped yet and this slice shouldn't depend on it.

This gives provenance and conflict detection without depending on any unshipped infrastructure.

## 3. `agent_id` registry

Mirrors the already-shipped `member_id`/`member_aliases` pattern (`synlynk/db.py`, devlog identity registry) but lives in the workspace-level store (`registry.json`), not local `state.db`, since agent identity is workspace-scoped by design (Conflict A's resolution).

```json
{
  "agents": [
    {
      "agent_id": "dev-primary",
      "canonical_role": "dev",
      "created_at": "2026-08-15T20:14:00Z",
      "aliases": [
        {"kind": "role_slug", "value": "dev"},
        {"kind": "github_app_slug", "value": "synlynk-dev[bot]"}
      ],
      "history": [
        {"event": "created", "at": "2026-08-15T20:14:00Z"}
      ]
    }
  ]
}
```

Resolving an alias that isn't registered fails loudly — never silently forks a new agent record. Same rule Round 6 set for `member_id`, carried forward here before the fork risk becomes live (Round 7's stated rationale for building this ahead of Phase 1).

## 4. API surface this slice ships

Consumed by task #97 (Agent-roles-charters Phase 1) — this slice builds the storage layer, not Phase 1's own CLI (`agent init/list/show/edit/disable`):

- `get_workspace_id() -> str` — reads (or mints, on first call) `workspace_id` in `.synlynk/config.json`.
- `agent_store_path(agent_id: str) -> str` — resolves `~/.synlynk/workspaces/<workspace_id>/agents/<agent_id>/`.
- `resolve_agent_id(alias: str) -> str | None` — looks up an alias in `registry.json`; returns `None` (never a guess) if unregistered.
- `register_agent(agent_id: str, aliases: list[dict]) -> None` — creates a new registry entry; refuses if `agent_id` or any alias already exists.
- `read_charter(agent_id: str) -> tuple[str, int]` — returns `(content, current_revision)`.
- `propose_charter_revision(agent_id: str, content: str, actor: str, parent_revision: int) -> int` — writes a new revision if `parent_revision` matches the current head; raises a conflict error otherwise. No auto-approval logic — the `gated` (agent-proposed/human-approved) mutability tier stays fully deferred (item 11), but this write shape is structured so gating can be layered on top later without a rewrite.
- `regenerate_agent_projection(agent_id: str, repo_overrides: dict | None) -> None` — writes `<repo>/.synlynk/agents/<agent_id>.yaml` from the canonical registry + charter metadata (not full charter content). Idempotent, safe to call from `synlynk upgrade` or `pr check` the way other projections already regenerate.

`memory/` and `statements-of-record/` get the same `read_*`/`propose_*_revision` shape as charter, parameterized by entry name — no separate design needed per category.

## 5. Explicitly out of scope for this slice

- `gated` mutability enforcement/approval workflow (item 11 of the source spec) — the write API leaves room for it, but no approval queue or gate is built here.
- GOVERNS-derived per-agent action-log/cost projections (also item 11).
- Phase 1's own CLI (`agent init/list/show/edit/disable`) and its consumption of the projection file — that's task #97.
- Cross-repo `workspace_id` sharing, `state.db` relocation, the `repos` table, `sync_log`, `synlynk workspace join` — the full 2026-06-07 multi-repo spec stays a separate, later follow-up.
- Server-side storage (Round 7 named `~/.synlynk/workspaces/<workspace_id>/` *or* server-side as options) — this slice is local-first only, consistent with synlynk's stated local-first-then-sync trajectory.

## 6. Testing approach

- `get_workspace_id()`: first call mints and persists a uuid4 into `.synlynk/config.json`; second call returns the same value; a pre-existing `workspace_id` in config is never overwritten.
- `register_agent()` / `resolve_agent_id()`: registering, resolving each alias kind, rejecting a duplicate `agent_id`, rejecting a duplicate alias across two different agents, and confirming an unregistered alias resolves to `None` rather than raising or guessing.
- `propose_charter_revision()`: first write with `parent_revision=0` succeeds; a second write with a stale `parent_revision` raises a conflict rather than overwriting; `read_charter()` after a successful write reflects the new content and incremented revision; `charter.revisions.jsonl` gains exactly one line per successful write with the correct `parent_hash`/`content_hash` chain.
- `regenerate_agent_projection()`: writes a `.yaml` file containing only `agent_id`/`role`/overrides (never charter content), is idempotent (second call with unchanged inputs produces byte-identical output), and the file path is confirmed present in `.gitignore`.
- Integration-style test: full flow — mint workspace_id, register an agent, propose two sequential charter revisions, regenerate the projection, assert the projection file has no canonical content and the workspace-level store does.

---

**Related specs:**
- `docs/superpowers/specs/2026-08-14-workspace-context-governance-design.md` (source spec, action items 9/10)
- `docs/superpowers/specs/2026-08-09-synlynk-agent-roles-charters-design.md` (§10 Phase 1, the consumer of this slice)
- `docs/superpowers/specs/2026-06-07-synlynk-workspace-multi-repo-design.md` (deferred full workspace_id/multi-repo design — not implemented by this slice)
