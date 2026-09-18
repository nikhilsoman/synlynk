# Wave 6 workspace identity slice

## Scope

Implement the bounded W4/W9 slice from the approved specs:

- make `join` an explicit membership operation distinct from `init`, with no
  identity/App/PEM provisioning;
- keep dispatch non-connector by default and fail closed for connector work
  without an explicit grant;
- expose graph reads through an API-shaped seam that fails closed when no
  graph minter/relay is configured;
- add a hosted Vizor placeholder URL/response with no OAuth or hosting.

## Verification

- unit tests cover join side effects, connector dispatch gating, graph
  fail-closed behavior, and hosted placeholder output;
- run the focused Wave 6 tests plus the existing W2/W3 identity and Vizor
  suites;
- run `git diff --check` and the repository's PR checks before merge.

## Non-goals

No live OAuth, relay service, production hosting, PEM copy, or GitHub Projects
source-of-truth behavior is included in this slice.
