# Cost anomaly investigation: job-2a16259d / PR #2232

Date: 2026-10-15  
PR: https://github.com/nikhilsoman/synlynk/pull/2232

## Finding

The alert was caused by cumulative Codex turn accounting being priced as
fresh input. It was not caused by OpenRouter or `GenericAPIAdapter`.

The job's single `turn.completed` usage record contained:

| Metric | Value |
| --- | ---: |
| Cumulative `input_tokens` | 6,169,874 |
| `cached_input_tokens` | 6,013,184 (97.5%) |
| Fresh input after cache split | 156,690 |
| Output plus reasoning output | 25,478 |
| Flat uncached estimate | $18.89 |
| Cache-aware estimate | $0.854 |

Codex resends the growing tool-loop transcript on each round. The stable
prefix is cache-read input, but the old reconciler priced the cumulative
`input_tokens` total at the fresh-input rate. Fifty-three command executions
and two 126 KB `pytest -v` captures enlarged the transcript and therefore the
cumulative total, without representing 6.17M unique file-read tokens.

## Disposition

The cache-aware split is already present in this branch through
`split_billed_tokens()` and is used by both cost reconciliation and the
circuit breaker. The exact incident values now have regression coverage in
`tests/test_costs.py`. No adapter or OpenRouter change is required.

The remaining follow-up is dispatch transcript hygiene: broad `pytest -v`
output should be written to a log and summarized before it is returned to the
harness transcript.
