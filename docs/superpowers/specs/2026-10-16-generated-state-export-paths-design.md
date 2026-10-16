# Generated State Export Paths

Decision: `dec-02b76895` on issue #2328 (approved by Nikhil, 2026-10-16).

## Decision

The `todo.md`, `roadmap.md`, and `costs.md` files are generated exports of
`state.db`. Write each only to
`product_root(identity_slug) / "project-docs" / filename`, beside the canonical
product state database. Refresh the exports when state changes and when a
status/export command renders them. Keep `memory.md` at its current path and
leave devlogs unchanged.

The three exports are not Git-tracked and must not be written inside a project
checkout or committed by feature jobs. Do not add a nightly export job.

## Consequences

- Readers use the same canonical product export directory.
- Autocommit excludes all three legacy checkout paths and the canonical home
  export paths.
- `synlynk pr check` fails when a PR diff touches any legacy checkout path.
- Remove the three checked-in markdown exports and their `merge=union`
  attributes; retain the devlogs merge attribute.
- No blog generator or per-PR blog behavior changes.
