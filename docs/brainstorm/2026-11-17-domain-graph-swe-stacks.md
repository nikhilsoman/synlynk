# Brainstorm — Domain Graph for Common SWE Stacks

- **Date:** 2026-11-17
- **Issue:** gh:#5339 — "Domain Graph for common SWE stacks @pm @tpm"
- **Story:** story-17e556b7
- **Goal:** goal-bccda8b7 (host arc; this brainstorm is research-only, no implementation)
- **Status:** Research + agenda. No spec yet. Per the Brainstorm-First Policy, a
  `docs/superpowers/specs/` design doc and a `synlynk decide --record` panel are required before any code.

---

## 1. Intent

Brownfield discovery today has no stack-specific prior. When synlynk dispatches a job into an
unfamiliar repo, the dispatched harness can only lean on three things:

1. **The code itself** — via the Graphify AST code graph (`.synlynk/graphify-out/graph.json`,
   warmed by `synlynk/graph_cache.py`) and the doc sidecar graph (`synlynk/docgraph.py`).
2. **Whatever the called model happens to know** — undeclared, unversioned, unmeasurable training
   depth for that stack.
3. **The workspace owner's interactive hand-holding** — an expensive, non-reusable transfer of intent.

(3) is the failure mode the product exists to eliminate; (2) is the one we cannot audit. #5339 proposes
a third graph — a **domain graph** — that sits alongside code graph and doc graph and supplies the
stack prior explicitly: for an Android Kotlin app, that Gradle/AGP is the build surface, that
`build.gradle.kts` version catalogs are where dependency edits land, that Compose state hoisting is
the idiomatic pattern, that Robolectric vs. instrumented tests have different CI costs.

The intent is therefore: **make the stack prior a versioned, inspectable, swappable artifact rather
than an implicit property of the model or the operator.** It is a direct instance of the product
thesis — closing an intent-transmission gap, here between *the ecosystem's accumulated convention*
and *the dispatched agent*.

Secondary intent from the issue: the corpus must be **independent of the synlynk source tree**, so it
can refresh on the ecosystem's cadence (AGP ships ~quarterly; Swift annually) rather than on
synlynk's release cadence, and can be **sideloaded instantly** at onboarding — a `synlynk intuition`
/ `synlynk corpus` service maintained on synlynk.com.

## 2. Context

### 2.1 What already exists in-repo (and what it is *not*)

There is a naming hazard here that must be resolved before any spec is written.

`synlynk/domain_packs.py` + `synlynk/domain_packs/*.json` **already exist** (`software.json`,
`hitchcock.json`, `rxcc.json`). But they are *industry-vertical lifecycle* packs, not stack packs.
`software.json` carries: `domain_id`, `industry`, `naics: 541511`, `apqc`, `max_autonomy_level: L3_AUTONOMOUS`,
six `lifecycle_stages` (brainstorm → … ) with `owner_archetype`/`output`, and four `suggested_tools`
keyed by `(archetype, sfia_code)`. Every suggested tool is returned with
`requires_confirmation=True, confirmed=False` per Binding Amendment 2 (dec-4a53a2ee): *no taxonomy
lookup or domain pack may grant write authority unconfirmed.*

So the existing axis answers **"what lifecycle and which archetype owns this stage, in this
industry."** #5339 asks for an orthogonal axis: **"what are the syntax, frameworks, patterns, build
and test surfaces of this technical stack."** Android-vs-iOS is not a different *industry* from
`software` — it is a different *stack within* it. Collapsing the two axes into one `domain_packs`
namespace would make `software.json` and `android-kotlin.json` siblings while they are in fact
parent and child on different dimensions.

Adjacent existing surfaces the design must reuse rather than duplicate:

| Surface | File | Relevance |
|---|---|---|
| Code graph (Graphify AST) | `graph_cache.py`, `pack.py` | The structural half; the domain graph is the semantic prior over it |
| Doc graph | `docgraph.py` | Precedent for a sidecar JSON graph with reverse indexes; `reverse_code_index` is the join pattern to copy |
| Context packager | `pack.py` (`_cut_to_token_budget`, 1500-token default) | Hard budget ceiling the corpus must fit inside; "sub-3k context packager" is a declared core capability in `editions.py` |
| Stack fingerprinting | `scan.py` `_STACK_FINGERPRINTS` / `_STACK_EXT_MAP` | **The binding gap** (see 2.2) |
| Repo classification | `repo_classifier.py` | Greenfield/brownfield + language histogram by extension |
| SFIA skills taxonomy | `sfia.py`, `sfia_taxonomy.json` | Existing precedent for vendoring an external taxonomy as JSON |
| Org/role packs | `packs/*.yaml` (studio, software-product, agency) | A *third* existing "pack" namespace — naming is already crowded |
| Hosted-capability tiering | `editions.py` (`category: "hosted"`, `hosted_key`) | Where a synlynk.com-hosted corpus service would register |
| Onboarding state machine | `onboarding_state.py` (`advance_stage`, `propose_topology`, `record_probe`) | The sideload insertion point |

### 2.2 The concrete gap that makes this urgent

`_STACK_FINGERPRINTS` in `scan.py` is 12 entries: Python, Rust, Go, Next.js, Pulumi, Docker.
`_STACK_EXT_MAP` is two entries (`.go`, `.rs`). `repo_classifier.py`'s `_KNOWN_MANIFESTS` includes
`build.gradle` and `pom.xml`, and `_CODE_EXTENSIONS` includes `.kt` and `.swift` — but there is **no
`build.gradle.kts`, no `settings.gradle.kts`, no `*.xcodeproj`, no `Package.swift`, no `Podfile`, no
`*.xcworkspace`**. synlynk literally cannot today distinguish an Android app from a Java backend, or
an iOS app from a Swift CLI. Whatever the domain graph turns out to be, **stack detection is its
prerequisite and the cheapest first deliverable** — it is useful on its own (better `synlynk scan`
output) and it is the key every corpus lookup will be keyed on.

### 2.3 External research — is there a taxonomy we can adopt?

No single authoritative taxonomy of technology stacks exists. The candidates split cleanly by layer:

- **Knowledge-area layer — SWEBOK v4.0 (IEEE CS, 2024).** 15 knowledge areas; conceptual, stable,
  citable. Covers *requirements / design / construction / testing / maintenance*. Good for naming the
  **facets** of a pack (what kinds of knowledge a pack must carry), useless for naming stacks.
- **Occupation/skill layer — ESCO (EU), O*NET (US), SFIA.** Occupation classifications, not stack
  catalogs; O*NET's software coverage is famously thin (essentially one undifferentiated
  "programming" skill). SFIA is **already vendored** (`sfia_taxonomy.json`) and already keys
  `suggested_tools` — so the skill axis is solved and should not be re-litigated.
- **Technology layer — posting-derived and community-derived sets.** Lightcast Open Skills is
  posting-derived (contains the actual tool/framework names employers write). Stack Overflow's 2017
  tag-correlation network is public on Kaggle. Feng et al. (arXiv:2504.03581, CC BY 4.0) derive a
  fine-grained software-skill taxonomy by stochastic-block-model clustering of SO tag co-occurrence
  over 2008–Jun 2023 — the most current rigorous option, though its data-availability terms need
  checking before vendoring. Software.zhishi.schema (CEUR Vol-1486) is an earlier SO-derived
  programming taxonomy; likely bit-rotted (2015).
- **Content layer — `llms.txt` / `llms-full.txt` (llmstxt.org).** A community convention: a Markdown
  index (`llms.txt`) plus a flattened full-text companion (`llms-full.txt`), auto-generated by
  Mintlify, Docusaurus, ReadMe; published by Stripe among others. **This is the single most
  important external finding** — for any stack whose vendor publishes `llms.txt`, corpus
  *acquisition* is a fetch, not an authoring project. It does not solve curation, compression to a
  1500-token budget, or pattern/anti-pattern encoding, but it removes the bulk-text problem.

**Conclusion:** adopt a **layered hybrid** — SWEBOK for pack facets, SFIA (already in tree) for the
skill axis, a posting/tag-derived set for the *stack name space*, and `llms.txt` for raw content
acquisition. Do **not** attempt a hand-authored global taxonomy of SWE domains; that is the trap the
issue's "construct a comprehensive list of domains in SWE" phrasing invites.

### 2.4 Proposed taxonomy shape (for debate, not decided)

A stack identity is a coordinate, not a leaf in one tree. Four independent dimensions:

```
platform   : android | ios | web-frontend | backend-service | cli | embedded | data-pipeline | infra
language   : kotlin | java | swift | objc | typescript | python | go | rust | ...
framework  : compose | views-xml | swiftui | uikit | next | fastapi | spring | ...
toolchain  : gradle-agp | spm | cocoapods | xcodebuild | pnpm | uv | cargo | ...
```

`android/kotlin/compose/gradle-agp` and `ios/swift/swiftui/spm` are then addresses, and a pack can
attach at any prefix — a `platform:android` pack carries Play Console/signing/ABI facts true for both
Kotlin and Java, while `framework:compose` carries recomposition and state-hoisting patterns. This
keeps the pack count sub-linear in the combinatorial space and lets a repo resolve to a *set* of
packs (as `fingerprint_stack` already returns a *list* of labels, not one label).

Per-pack facets, SWEBOK-aligned:

| Facet | Example (android/kotlin) | Why an agent needs it |
|---|---|---|
| `layout` | `app/src/main/`, `app/src/test/` vs `androidTest/` | Where to put a new file |
| `build` | `./gradlew :app:assembleDebug`, version catalogs in `gradle/libs.versions.toml` | How to verify without guessing |
| `test` | JUnit + Robolectric (JVM, fast) vs instrumented (emulator, slow/costly) | Verification cost routing |
| `patterns` | MVVM + `StateFlow`, Hilt DI, Room DAO | Idiomatic-change shape |
| `anti_patterns` | `GlobalScope`, blocking main thread, leaking `Context` | Review checklist seed |
| `release` | AAB, signing config, Play tracks | Deploy-task priors |
| `pitfalls` | AGP↔Kotlin↔JDK version coupling | The #1 brownfield time sink |

`anti_patterns` deserves emphasis: it converts the corpus from a *discovery* aid into a **review**
aid, which is the lane with the most measured dispatch traffic (`capability_ratings`).

## 3. Trade-offs

**T1 — Namespace: extend `domain_packs` vs. a new `stack_packs`/corpus namespace.**
Extending reuses `load_domain_pack` and Binding Amendment 2's confirmation discipline for free, but
conflates industry-vertical with technical-stack and will silently corrupt the `software.json`
lifecycle semantics. A new namespace is honest about the orthogonality but adds a *fourth* "pack"
concept (`domain_packs/`, `packs/*.yaml`, `capability export-pack`, addon bundles). **Lean: new
namespace, explicitly cross-referenced, with a glossary entry — the `docs/glossary-agent-vs-harness.md`
precedent shows this project pays for clear naming.**

**T2 — Shipped in-tree vs. fetched from synlynk.com.** The issue requires source-independence so
packs refresh on ecosystem cadence. But a network fetch at discovery time breaks the local-first
posture, adds a failure mode to every `scan`/`dispatch`, and makes dispatch non-deterministic
(two jobs, same commit, different corpus = uncomparable `capability_ratings`). **Lean: content-addressed,
pinned, cached. Packs live outside the source tree (`~/.synlynk/corpus/<pack>@<version>/`), are
resolved at *onboarding/explicit-sync* time only, never lazily mid-dispatch, and the resolved
`pack_id@version+digest` is recorded in the job's provenance so cost/quality comparisons stay honest.
Offline and air-gapped work from cache; a stale cache warns in `synlynk doctor` rather than blocking.**

**T3 — Breadth vs. trust.** A 40-stack corpus auto-generated from `llms-full.txt` would be broad and
largely unvetted; hallucinated or stale "idiomatic patterns" are worse than no prior at all, because
the agent will cite them confidently. **Lean: two-tier provenance in the schema —
`curated` (human-reviewed, eligible to be injected as assertion) vs `derived` (auto-ingested,
injected only as citation with a source URL). Start curated-only, two stacks deep (android/kotlin,
ios/swift) rather than twenty stacks shallow.**

**T4 — Token budget.** `pack.py` cuts to 1500 tokens by default and "sub-3k context packager" is a
declared core capability. A naive corpus injection blows this and directly inflates cost — the repo
already has a standing cost-inflation record. **Lean: the corpus is *retrieved*, not *appended* —
keyed by the task's detected stack ∩ the task's keywords (reuse `_extract_keywords`), with a hard
per-pack token ceiling (~400) and a declared displacement rule so corpus never evicts code-graph
context. Measure: median `total_cost_usd` and `pr_review_cycles` with corpus on vs. off.**

**T5 — Authority.** Packs name tools and commands. Binding Amendment 2 already forbids a pack
granting write authority unconfirmed. A `build`/`test` facet is a *suggested command*, i.e. exactly
the hazard that amendment anticipates. **Lean: inherit the amendment verbatim — every pack-sourced
command surfaces as `requires_confirmation=True, confirmed=False`, and a corpus pack can never be a
source of truth for merge/deploy authority.**

**T6 — Maintenance economics.** Hand-curating Android/iOS packs is real recurring labour against a
quarterly-moving target. Unmaintained packs become actively harmful (asserting pre-AGP-8 facts).
**Lean: every pack carries `verified_against` (AGP/Swift/SDK versions) and `verified_at`; staleness
is surfaced passively in `synlynk doctor` and expires a pack from `curated` to `derived` tier
automatically after a declared horizon, rather than silently serving stale assertions.**

**T7 — Licensing.** Vendoring Lightcast/ESCO/SO-derived taxonomies or vendor docs has terms. SFIA is
already vendored, so there is precedent and presumably a cleared path; `llms.txt` content is the
vendor's own publication but not automatically redistributable. **Lean: ship *references* (URL +
digest + fetch recipe) for anything not confirmed redistributable; ship text only for CC-BY/permissive
sources with attribution. Resolve before the first hosted pack, not after.**

**T8 — Alternative considered and rejected as sufficient: "links to public documentation"** (the
issue's own stated alternative). Cheap and always current, but it pushes a fetch + read + compress
cost onto every dispatch, is unavailable to sandboxed/no-network harnesses (Codex gets network only
on explicit `--requires-gh-write`), and transmits no *convention* — a link to the Gradle manual does
not tell an agent that this repo's ecosystem prefers version catalogs. Keep links as the `derived`
tier's backing, not as the product.

## 4. Key Decisions

Proposed for the DECIDE panel; none are final until recorded.

- **KD1 — Two orthogonal axes, two namespaces.** Industry-vertical lifecycle stays in
  `domain_packs/`. Technical-stack intuition goes in a new, separately-versioned corpus namespace.
  A repo resolves to one vertical pack + N stack packs. (T1)
- **KD2 — Stack identity is a 4-tuple coordinate** (`platform/language/framework/toolchain`), packs
  attach at any prefix, and resolution yields a *set*. No single global tree of "SWE domains". (2.4)
- **KD3 — Do not author a taxonomy; compose one.** SWEBOK v4.0 → pack facets; SFIA (in-tree) → skill
  axis; posting/tag-derived set (Feng et al. arXiv:2504.03581, or SO tag network) → stack name space;
  `llms.txt`/`llms-full.txt` → content acquisition. (2.3)
- **KD4 — Stack fingerprinting is deliverable #1 and ships standalone.** Extend `scan.py`
  `_STACK_FINGERPRINTS`/`_STACK_EXT_MAP` and `repo_classifier.py` `_KNOWN_MANIFESTS` with
  `build.gradle.kts`, `settings.gradle.kts`, `gradle/libs.versions.toml`, `Package.swift`, `Podfile`,
  `*.xcodeproj`, `*.xcworkspace`, `pubspec.yaml`, `*.csproj`. Valuable with zero corpus; prerequisite
  for all of it. (2.2)
- **KD5 — Pinned, content-addressed, cached; resolved at onboarding/sync, never lazily mid-dispatch.**
  Resolved `pack_id@version+digest` recorded in job provenance. Offline works from cache. (T2)
- **KD6 — Two provenance tiers.** `curated` may be injected as assertion; `derived` only as cited
  reference. Ship curated-only, depth-first on `android/kotlin` + `ios/swift`. (T3)
- **KD7 — Retrieval under a hard budget, with measured ROI.** Stack ∩ keyword retrieval, ~400 tokens
  per pack, corpus never evicts code-graph context; accept into default dispatch only on measured
  improvement in median `pr_review_cycles` / `total_cost_usd` per the Empirical Capability
  Assessment Policy. (T4)
- **KD8 — Binding Amendment 2 inherited verbatim.** Pack-sourced commands are suggestions requiring
  confirmation; a pack is never an authority source. (T5)
- **KD9 — Staleness is a first-class field.** `verified_against` + `verified_at`; auto-demotion from
  `curated` past a horizon; surfaced in `synlynk doctor`. (T6)
- **KD10 — Hosted corpus registers as a `hosted` capability in `editions.py`** with its own
  `hosted_key`, so tiering is explicit rather than ad hoc; the local cache path remains fully
  functional without it. (T2, T7)
- **KD11 — Licensing cleared before the first hosted pack**, with references-not-text as the default
  for anything unconfirmed. (T7)
- **KD12 — `anti_patterns` is mandatory in the pack schema**, not optional — it is what connects the
  corpus to the review lane. (2.4)

### Open questions for the panel

1. Does the corpus belong behind the Graphify/doc-graph interface (a third graph with reverse
   indexes, per `docgraph.py`) or as a flat retrieval index? A true *graph* only pays for itself if
   edges are traversed (pattern → anti-pattern → test surface); otherwise it is a dictionary wearing
   a graph's name.
2. Who maintains curated packs — a dispatched `architect` sweep on a cadence, or human review? KD9's
   auto-demotion presumes nobody is guaranteed to show up.
3. Is `synlynk intuition` or `synlynk corpus` the command surface? Neither is in `COMMAND_TAXONOMY`
   today; whichever wins must be added there or README validation (`synlynk release --check-docs`)
   will reject it.
4. Does the non-SWE generalization (the issue's "other similar domain specific lit") reuse this same
   4-tuple shape, or is stack-coordinate a software-only abstraction? `hitchcock.json` suggests the
   vertical axis generalizes; the stack axis may not.

### Research agenda (next steps, in order)

1. **Verify data availability + license** for Feng et al. (arXiv:2504.03581) and the SO tag-network
   Kaggle dataset; confirm SFIA's existing vendoring terms as the precedent. (blocks KD3, KD11)
2. **Inventory `llms.txt` coverage** for the target stacks — Android developer docs, Swift/Apple
   docs, Gradle, Jetpack Compose. Determines whether `derived` tier is cheap or hand-fed. (blocks KD6)
3. **Land KD4 (fingerprinting) as its own small PR** — independently valuable, unblocks everything.
4. **Draft one hand-authored `android/kotlin` pack** against the facet schema as an existence proof,
   and measure it: one dispatch with, one without, same task, compare cost and review cycles. (KD7)
5. **Write the design spec** to `docs/superpowers/specs/2026-11-17-domain-graph-swe-stacks-design.md`
   and run `synlynk decide --record` on it before any further implementation.

---

## Sources

- [SWEBOK — IEEE Computer Society](https://www.computer.org/education/bodies-of-knowledge/software-engineering)
- [Feng et al., "Using digital traces to analyze software work" (arXiv:2504.03581, CC BY 4.0)](https://arxiv.org/html/2504.03581v2)
- [Stack Overflow — Mapping ecosystems of software development (tag correlation network)](https://stackoverflow.blog/2017/10/03/mapping-ecosystems-software-development/)
- [Software.zhishi.schema — a software programming taxonomy from Stack Overflow (CEUR Vol-1486)](https://ceur-ws.org/Vol-1486/paper_61.pdf)
- [Skills Taxonomy Frameworks: O*NET, ESCO, and the skills-based hiring stack](https://aieh-com.pages.dev/skills-taxonomy-frameworks/)
- [Review of skills taxonomies (SPB, May 2022) — SFIA, Singapore, Nesta](https://dera.ioe.ac.uk/id/eprint/39278/1/Review_of_skills_taxonomies_report_prepared_for_the_SPB_May_2022.pdf)
- [llms.txt explained — LLM-ready content standard](https://www.analyticsvidhya.com/blog/2025/03/llms-txt/)
