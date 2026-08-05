# HN Idea-Finder: Discovery Pipeline (Stage A) — Design

## Context

This is Stage A of a two-stage creative challenge: build the smallest artifact that meaningfully exercises synlynk's own orchestration capabilities (dispatch, story auto-provisioning, telemetry, cost logging, budget tracking) while producing something genuinely useful.

The full challenge, as it evolved through brainstorming:

1. **Stage A (this spec):** Find a real, still-unaddressed feature gap in a real open-source project, sourced from organic Hacker News discussion and validated against the target repo's own issue tracker.
2. **Stage B (future, separate spec):** Fork the identified repo, implement the feature, and prepare a pull request — stopping short of actually submitting it until the user explicitly approves. Stage B cannot be designed yet because its shape (language, codebase, complexity) is entirely determined by Stage A's output.

Stage A's deliverable is a small, disposable-but-real CLI tool. The actual point of building it is the **synlynk session that builds it** — a demonstration of dispatch/story/telemetry/budget machinery working end-to-end on a small but non-trivial multi-task build.

## What Stage A Does

A one-shot Python CLI, `examples/hn-idea-finder/`, that:

1. Fetches recent Hacker News posts and their comment trees via HN's official Firebase API (no auth required).
2. Scans comment text for organic demand-signal phrases (e.g. "someone should build", "I wish there was", "does this exist") **only when the same HN thread also contains a `github.com/<owner>/<repo>` link** — this is the mechanism for resolving "which tool are they talking about" without ambiguous name-guessing.
3. For each such candidate, cross-checks the linked repo's **open** GitHub issues (via the `gh` CLI, already authenticated in this environment) for a matching feature request using keywords drawn from the HN comment.
4. Only candidates backed by a real, currently-open matching issue make the final shortlist — this is the strongest available signal that the gap is real, still wanted, and not already fixed.
5. Prints the shortlist to stdout (HN thread URL, matched comment snippet, matched phrase, target repo, matching issue URL/title), with an optional `--output <file>` flag to persist it.

No code is written to, or PR opened against, any target repo in this phase. This is pure discovery.

## Non-Goals

- Does **not** attempt to resolve a tool name to a repo via search/guessing — a candidate without an explicit GitHub link in-thread is simply not actionable and is skipped.
- Does **not** verify whether a gap is real beyond "a matching open issue exists" — no live web search, no LLM plausibility judgment. This is a deliberate scope cut to keep the tool small; false positives (an open issue that's actually stale or already fixed via an unlinked PR) are acceptable and left to human review of the shortlist.
- Does **not** implement any feature or interact with any target repo beyond read-only issue search.
- Does **not** run on a schedule (no cron wiring) — one-shot execution only, matching the "smallest artifact" goal.
- Does **not** persist run state or dedupe against previous runs — each invocation is independent.

## Components

All new files live under `examples/hn-idea-finder/`:

| File | Responsibility |
|---|---|
| `hn_fetcher.py` | Calls HN's Firebase API (`https://hacker-news.firebaseio.com/v0/`) to fetch recent top/new story IDs and their comment trees. |
| `matcher.py` | Scans comment text for demand-signal phrases; when matched, extracts the first `github.com/<owner>/<repo>` link present anywhere in the same thread (post text or any comment). |
| `gh_crosscheck.py` | Given `owner/repo` and keywords drawn from the matched comment, shells out to `gh search issues --repo <owner>/<repo> --state open <keywords>` and returns the best-matching open issue, if any. |
| `cli.py` | Orchestrates fetch → match → cross-check → output. Entry point (`python3 -m examples.hn-idea-finder.cli` or a thin `__main__.py`), handles `--output` flag. |
| `README.md` | Usage instructions: how to run it, what the phrase list is, how the GitHub cross-check works, and its limitations (per Non-Goals). |
| `tests/` | Unit and integration tests — see Testing section. |

## Data Flow

```
cli.py
  → hn_fetcher.fetch_recent_stories(limit=N)      # Firebase API, default N=100 recent top+new stories
      → for each story: fetch story + comment tree (bounded depth, e.g. 2 levels)
  → matcher.find_candidates(stories)               # pure function, no I/O
      → for each comment: phrase-match AND thread-level github.com link present
      → yields Candidate(hn_thread_url, comment_snippet, matched_phrase, repo_owner, repo_name)
  → for each Candidate:
      → gh_crosscheck.find_matching_open_issue(candidate.repo_owner, candidate.repo_name, candidate.comment_snippet)
      → if a matching open issue is found: attach issue_url + issue_title, keep candidate
      → else: drop candidate
  → cli.py formats and prints/writes the final shortlist
```

### Phrase list (initial, configurable as a module-level constant in `matcher.py`)

```
"someone should build"
"i wish there was"
"i wish someone would"
"does this exist"
"why doesn't this exist"
"would pay for"
"no one has built"
```

Matching is case-insensitive substring matching on comment text (HTML-stripped, since HN comment text is HTML-escaped/wrapped).

## Error Handling

- Any single story/comment fetch failure (network error, missing/deleted item) → skip that story, print a warning to stderr, continue processing the rest.
- Any `gh` invocation failure (rate limit, repo not found/private, malformed repo reference) → skip that candidate, print a warning to stderr, continue.
- The tool never crashes on partial failures — it always prints whatever shortlist it accumulated by the time it finishes, even if some stories/candidates were skipped.
- Exit code 0 on a normal run regardless of skipped items; non-zero only on a fatal error before any processing could occur (e.g. `gh` not installed/authenticated at all).

## Testing

TDD per component, matching project convention:

- `matcher.py`: pure unit tests — given synthetic story/comment fixtures (as plain Python dicts, no network), assert correct candidate extraction, including edge cases (phrase present but no GitHub link → no candidate; GitHub link present but no phrase match → no candidate; link in the post body vs. in a nested comment).
- `hn_fetcher.py`: tests use mocked HTTP responses (no real network calls in the test suite) — assert correct parsing of the Firebase API's story/comment JSON shape, and that a single failed fetch doesn't abort the batch.
- `gh_crosscheck.py`: tests mock the `gh` subprocess call (e.g. via `unittest.mock.patch` on `subprocess.run`) — assert correct command construction and correct parsing of `gh`'s JSON output into a matched-issue result or `None`.
- `cli.py`: an integration test with `hn_fetcher`, `matcher`, and `gh_crosscheck` all mocked/stubbed, asserting the final shortlist output (stdout and `--output` file) has the expected shape given known inputs.

## synlynk Orchestration Plan

Three Codex dispatches (Python/CLI/tests is Codex's lane per the project's capability allocation table):

1. **Task 1 — Core logic:** `hn_fetcher.py` + `matcher.py`, TDD, with their unit tests.
2. **Task 2 — GitHub integration + CLI:** `gh_crosscheck.py` + `cli.py`, TDD, with their tests.
3. **Task 3 — Test suite completion + docs:** fill any remaining test gaps (particularly the CLI integration test) + `README.md`.

Each dispatch auto-provisions its own story via the existing `resolve_or_create_story_id()` path, and `dispatch_agent()`'s existing telemetry/cost-capture machinery runs unmodified — no changes to synlynk's own code are needed for this build. An explicit budget cap is set for this work in the dispatching session (via existing `synlynk` budget config) so `check_budgets()` has something real to track; no failure is artificially engineered — sentinel pattern detection runs naturally and is expected to stay quiet for a build this small.

## Open Questions / Risks

- **HN Firebase API pagination:** the "recent top/new stories" endpoint returns a flat list of IDs; fetching comment trees for N=100 stories means up to a few hundred HTTP calls per run. No official rate limit is documented, but `hn_fetcher.py` should fetch with modest concurrency (e.g. a small thread pool or sequential with a short delay) to be a good API citizen. Exact concurrency approach is an implementation detail left to Task 1's implementer, not specified further here.
- **`gh search issues` query quality:** keyword extraction from free-form comment text is a heuristic (e.g. stripping the matched demand-signal phrase and stopwords, keeping the remaining nouns/phrases as the search query). This is not expected to be perfect — false negatives (a real matching issue that the keyword search misses) are acceptable; the human reviewing the shortlist is the final filter, not this tool.
