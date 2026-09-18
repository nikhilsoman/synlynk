# Workspace identity Wave 5 — Vizor Board plan

## Scope

Implement the local Vizor Board described by the approved W3 product-board
spec. The board reads the product-scoped `state.db`, exposes repo/type/goal
filters, deep-links tracker pointers and GitHub PRs, and writes card status
changes back to the same database. GitHub Projects, hosted Vizor, OAuth, and
tracker SDKs are out of scope.

## Steps

1. Add a product-scoped board query/read model that joins stories, goals,
   repos, types, tracker pointers, and PR metadata without falling back to a
   checkout-local database when a product database is available.
2. Add a fail-closed status update operation that validates the requested
   story and status, writes `state.db`, and returns the updated card.
3. Add authenticated Vizor HTTP routes for board data and status updates,
   plus a local Board tab/card UI with repo, type, and goal filters.
4. Render safe deep links for GitHub Issues/PRs and generic tracker pointers;
   unknown or malformed pointers remain non-clickable.
5. Add unit/integration coverage for product scoping, filters, deep links,
   status writes, auth, and the absence of GitHub Projects calls.
6. Run focused tests and the smallest full verification, then update the Wave
   5 blog note and issue comment after merge.

## Acceptance criteria

- One product `state.db` can render stories from multiple `repo_id` values.
- Repo, type, and goal filters are deterministic and composable.
- Board status writes update product `state.db` and do not call any tracker.
- Cards expose safe GitHub/Linear-style deep links from stored pointers.
- Unknown export/tracker surfaces fail closed; no hosted or Projects behavior
  is added.
