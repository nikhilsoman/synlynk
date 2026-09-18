# W8 packs, onboarding, and connector isolation implementation plan

## Scope

Implement the approved W8 local contract from
`docs/superpowers/specs/2026-09-17-workspace-identity-w8-packs-onboarding-organigram-design.md`.
Keep Vizor hosting, live OAuth, vendor SDKs, and production hosting out of scope.

## Steps

1. Inventory the existing type registry, identity-init, onboarding, and product-store seams; preserve W5 behavior and choose the smallest local integration points.
2. Add package-shipped `software-product`, `studio`, and `agency` pack definitions with stable kind/type-id/label metadata and catalog-only connector support.
3. Add deterministic pack selection/validation for headless onboarding and identity initialization; ensure studio/agency spine type IDs are minted without reminting on relabel.
4. Add product-store connector metadata/secret isolation primitives with fail-closed validation for empty allowlists and unknown protocols; do not expose connector credentials to QA dispatch.
5. Add focused unit/acceptance tests for pack loading, type-id vs kind, relabel persistence, connector validation/isolation, and `--pack ... --yes` behavior.
6. Run focused plus full verification, open PR against `main`, run CI and QA/policy checks, merge, clean up, and update #1689/#914 and local roadmap records.
