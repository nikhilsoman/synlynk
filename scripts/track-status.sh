#!/usr/bin/env bash
# Live status tracker for the five-track code-adjacency plan (gh:#1985-1989).
# Re-run (press Enter) to refresh. Reads issue/PR state directly from GitHub —
# never trusts synlynk jobs labels alone, per project policy.
# Written for bash 3.2 (macOS default) — no associative arrays.
set -euo pipefail
export PATH="/Users/nikhilsoman/.synlynk/gh-shim:$PATH"
cd /Users/nikhilsoman/dev/synlynk

# Colors
C_RESET=$'\033[0m'
C_GREEN=$'\033[32m'
C_YELLOW=$'\033[33m'
C_RED=$'\033[31m'
C_CYAN=$'\033[36m'
C_DIM=$'\033[2m'

TRACK1="1925:Safe-by-default execution
1976:Dispatch smart defaults
1984:Hermes-class local roster
2015:Job-status false-negative recurrence
1963:Codex scope violation
1990:GOVERNS hard-fail gate
1991:cross_harness_review_required enforcement
1992:Audit-log GH_WRITE_ALLOW_HOST_AUTH
1993:Capability report routing
1960:LIVE-22 gh identity zone-boundary
2008:Job-status verified remote delivery
2012:Release-docs CI gate scope"

TRACK2="1973:Baseline metrics capture
1974:Tiered --help
1975:Quickstart + guided first-run
1977:Docs restructure
1927:CLI core/packs split
1941:Flaky cold-start test
1943:Move cold-start/EPUB out of CI
1918:decide --record slug collision"

TRACK3="1923:Split viz.py
1926:state.db consolidation
1995:Cost-log regen drops rows
1999:_rotate_project_doc duplication
1917:memory.md write-through drift
1915:costs.md regen drops rows
1969:Cost inflation escalation
1937:Cost-inflation record
1951:Cost audit redesign
2023:Regen write-through root-cause (investigation)"

TRACK4="1978:Positioning sentence everywhere
1979:Verify job outcomes (narrowed)"

TRACK5="1980:route --report + benchmark kit
1981:90-day design-partner program
1982:Competitive matrix
1983:Partnership moves (narrowed)"

# --- Inline findings discovered DURING implementation (not separately filed
# as their own GH issue, or filed but not yet triaged into the tracks above).
# Format: track:label:status:detail
# status: FIXED (resolved same-session, no follow-up needed)
#         OPEN  (confirmed real, not yet fixed — needs a dispatch/decision)
#         CRIT  (open + high-impact, e.g. cost/correctness risk spanning waves)
INLINE_FINDINGS="1:PR #2029 (#1990) breaks 3 pre-existing dispatch tests (no GOVERNS goal linked in fixtures):OPEN:test_dispatch_creates_job / test_dispatch_ready_jobs_launches_queued_job / test_dispatch_ready_jobs_commits_per_job now fail CI — needs test fixtures updated to link a goal, or gate needs a test-context opt-out
1:Job-status false-negative, 6th+ instance this session (#2015):OPEN:5 of 6 Wave-2 jobs labeled succeeded_gh_write_failed/unpushed_branch despite all 5 PRs genuinely open+pushed (#2024/#2026/#2027/#2028/#2029) — verified directly via gh pr list, not trusting labels
2:PR #2026 (#1975) stale generated docs after adding quickstart cmd:FIXED:commands.md/README commands section not regenerated + duplicate <!-- commands:end --> marker; fixed inline (commit fd7f00d), regenerated via scripts/generate_command_docs.py, pushed
2:PR #2028 (#1977) test fixture stub broke new commands-md release check:FIXED:test_add_synlynk_release_command_to_synlynk__ seeded docs/reference/commands.md with a hardcoded stub instead of render_reference_doc() output; the PR's own new release--check-docs extension correctly caught it as stale. Fixed inline, test updated to seed real content
3:Cost inflation NOT reduced by #1969/PR#2021 fix:CRIT:5 Wave-2 Codex implementation jobs cost \$5.58-\$15.93 each (avg ~\$9.4), essentially unchanged from Wave-1's \$1.96-\$12.52 range measured BEFORE #1969 merged — the merged fix does not appear to address the actual root cause. Needs fresh investigation, not yet dispatched."

# --- Job metrics (job_id, elapsed start->merge, cost) for completed/in-flight
# dispatches, keyed by issue number. Populated as waves land; static lookup
# refreshed by hand each wave (not a live query, to avoid extra gh/db calls
# on every tracker refresh tick).
# Format: issue:job_id:elapsed:cost
JOB_METRICS="1973:job-92c3cd46:1h19m:\$11.81
1941:job-3561f357:29m:\$1.96
1963:job-594ec949:1h13m:\$8.69
1974:job-69ba7fa6:1h04m:\$10.52
1969:job-45c98165:1h18m:\$12.52
1978:job-b1e83605:35m:\$6.66
2012:job-b86f460e:1h54m:\$2.35
1990:job-e5daa609:running:\$15.93
1991:job-ebb67741:running:\$6.93
1975:job-34f5240c:running:\$9.62
1977:job-1794154e:running:\$9.10
1979:job-2b9ba652:running:\$5.58
2023:job-7f4334af:7m:\$0.00 (comment-only, no code cost tracked)"

lookup_metrics() {
  local num="$1"
  echo "$JOB_METRICS" | awk -F: -v n="$num" '$1==n {printf "%-9s %s", $3, $4}'
}

print_track() {
  local name="$1"
  local items="$2"
  echo ""
  echo "=== $name ==="
  printf "%-6s %-9s %-9s %-8s %-s\n" "#" "STATE" "TIME" "COST" "TITLE"
  echo "$items" | while IFS=: read -r num title; do
    [ -z "$num" ] && continue
    state=$(synlynk gh --role pm -- issue view "$num" --json state -q '.state' 2>/dev/null || echo "?")
    metrics=$(lookup_metrics "$num")
    time_col="—"
    cost_col="—"
    if [ -n "$metrics" ]; then
      time_col=$(echo "$metrics" | awk '{print $1}')
      cost_col=$(echo "$metrics" | awk '{print $2}')
    fi
    color="$C_RESET"
    [ "$state" = "CLOSED" ] && color="$C_GREEN"
    printf "%s%-6s %-9s %-9s %-8s %-s%s\n" "$color" "$num" "$state" "$time_col" "$cost_col" "$title" "$C_RESET"
  done
}

print_inline_findings() {
  local track_num="$1"
  local found=0
  echo "$INLINE_FINDINGS" | while IFS=: read -r t label status detail; do
    [ -z "$t" ] && continue
    [ "$t" != "$track_num" ] && continue
    color="$C_YELLOW"
    tag="FIXED-INLINE"
    [ "$status" = "OPEN" ] && color="$C_YELLOW" && tag="NEW-NEEDS-FIX"
    [ "$status" = "CRIT" ] && color="$C_RED" && tag="NEW-CRITICAL"
    printf "%s  [%s] %s%s\n" "$color" "$tag" "$label" "$C_RESET"
    printf "%s      %s%s\n" "$C_DIM" "$detail" "$C_RESET"
  done
}

while true; do
  clear
  echo "Five-Track Status — refreshed $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Plan: docs/superpowers/plans/2026-10-04-five-track-code-adjacency-plan.md"
  echo "${C_GREEN}green${C_RESET}=closed  ${C_YELLOW}yellow${C_RESET}=inline finding (fixed or needs fix)  ${C_RED}red${C_RESET}=critical inline finding"
  print_track "Track 1: Dispatch/Harness Layer (gh:#1985)" "$TRACK1"
  print_inline_findings 1
  print_track "Track 2: CLI Surface & Taxonomy (gh:#1986)" "$TRACK2"
  print_inline_findings 2
  print_track "Track 3: Data/Display Layer (gh:#1987)" "$TRACK3"
  print_inline_findings 3
  print_track "Track 4: Trust & Positioning Copy (gh:#1988)" "$TRACK4"
  print_inline_findings 4
  print_track "Track 5: Go-to-Market (gh:#1989)" "$TRACK5"
  print_inline_findings 5
  echo ""
  echo "Press Enter to refresh, Ctrl-C to stop."
  read -r -t 300 _ || true
done
