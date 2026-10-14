# Charter Superpowers-Skill Binding — Implementation Plan

Date: 2026-10-14
Spec: `docs/superpowers/specs/2026-10-14-charter-superpowers-binding-design.md`
Tracking: gh:#2305

## Task 1 — `ROLE_SUPERPOWERS_SKILLS` mapping + merge into `adapt_charters_for_installed_tools`

Files: `synlynk/charters.py`, `tests/test_charters.py`

1. Add `ROLE_SUPERPOWERS_SKILLS: dict[str, list[str]]` constant per design §3.2, placed next to the existing
   `TOOL_ROLE_SKILLS` constant (`charters.py:151`).
2. In `adapt_charters_for_installed_tools()` (`charters.py:181`), in both the registered-agent branch
   (around line 215) and the seed-charter fallback branch (around line 256), extend the `desired_skills` merge
   loop to also iterate `ROLE_SUPERPOWERS_SKILLS.get(role, [])`, same `if s not in desired_skills: append` pattern
   already used for `active_role_skills.get(role, [])`. Do not change the removal logic (lines 220-225, 261-265) —
   superpowers skills are never removed based on tool availability, only tool-derived ones are.
3. Unit tests (new or extended in `tests/test_charters.py`):
   - `test_adapt_charters_merges_superpowers_skills_for_dev_role` — registered-agent branch, assert
     `"test-driven-development"` and `"systematic-debugging"` appear in `updated["dev"]["skills"]`.
   - `test_adapt_charters_seed_fallback_merges_superpowers_skills` — no registered agent, assert the seed-charter
     fallback branch also includes the role's superpowers skills.
   - `test_adapt_charters_unlisted_role_unaffected` — a role absent from `ROLE_SUPERPOWERS_SKILLS` (e.g.
     `designer`) produces the same `skills` output as before this change (empty, or tool-derived only).
   - `test_adapt_charters_no_duplicate_skills` — a role already carrying a superpowers skill in its existing
     charter frontmatter doesn't get a duplicate entry.

## Task 2 — Bound-skills rendering in `render_charter_section`

Files: `synlynk/charter_injection.py`, `tests/test_charter_injection.py`

1. In `render_charter_section()` (`charter_injection.py:44`), after resolving `content` via
   `resolve_role_charter`, parse its frontmatter with `charter_schema.split_frontmatter` +
   `charter_schema.parse_frontmatter` (both already exist — no new parsing code).
2. If the parsed `skills` key is a non-empty list, build the `## Bound Skills (required)` section per design §3.3
   (exact template text) and append it after the main charter content, before the closing `---` separator.
3. If `skills` is absent/empty, or frontmatter parsing yields nothing (no frontmatter present at all — some
   charters may still be pre-migration per the 2026-08-27 design's rollout), render exactly as today — no
   behavior change, no error.
4. If frontmatter is present but fails to parse (malformed YAML), let the existing `charter_schema` parse error
   propagate rather than catching and silently omitting the section (design §4).
5. Unit tests (new or extended in `tests/test_charter_injection.py`):
   - `test_render_charter_section_includes_bound_skills_when_present` — synthetic charter fixture with
     `skills:\n  - test-driven-development\n  - systematic-debugging` in frontmatter; assert the rendered output
     contains `## Bound Skills (required)` and both skill names as list items.
   - `test_render_charter_section_omits_bound_skills_when_absent` — charter with no `skills:` key at all; assert
     `## Bound Skills` does NOT appear in output.
   - `test_render_charter_section_omits_bound_skills_when_empty_list` — `skills: []`; same assertion as above.
   - `test_render_charter_section_unchanged_for_pre_migration_charter` — charter with no frontmatter at all
     (`split_frontmatter` returns `(None, content)`); assert output is identical to pre-this-change behavior.

## Task 3 — Regression check against the real dispatch injection path

Files: `tests/test_dispatch.py`

1. Add one test exercising the actual `dispatch.py:2417-2423` call site (not just `charter_injection.py` in
   isolation): mock/fixture a `dev`-role charter with `skills:` populated via `adapt_charters_for_installed_tools`,
   run the context-assembly path that calls `render_charter_section`, and assert the dispatched context text
   passed to the subprocess includes the `## Bound Skills (required)` section for `dev`.
2. This is the acceptance test proving the full chain (role mapping → adapt → render → dispatched context) is
   wired end-to-end, not just unit-correct in isolation — directly motivated by this session's earlier experience
   on gh:#2294 where unit tests passed but the real dispatched-job behavior diverged (gh:#2304).

## Verification

Scoped: `pytest tests/test_charters.py tests/test_charter_injection.py tests/test_dispatch.py -q`

Full regression set before merge (same set used for PR #2303): all four of
`tests/test_gh_shim.py tests/test_synlynk.py tests/test_dispatch_container.py tests/test_worktree_timestamp.py`
plus the three files above, `-q`.

## Non-Goals (restated from spec §6)

Do not attempt to reconcile the dead `AgentCharter`/`load_charter` JSON path, build skill-usage verification, or
expand `ROLE_SUPERPOWERS_SKILLS` beyond the seven roles in design §3.2 as part of this plan.
