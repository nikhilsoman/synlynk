#!/usr/bin/env bash
# Live status tracker for the five-track code-adjacency plan (gh:#1985-1989).
# Re-run (press Enter) to refresh. Reads issue/PR state directly from GitHub —
# never trusts synlynk jobs labels alone, per project policy.
set -euo pipefail
export PATH="/Users/nikhilsoman/.synlynk/gh-shim:$PATH"
cd /Users/nikhilsoman/dev/synlynk

declare -A TRACK1=( [1925]="Safe-by-default execution" [1976]="Dispatch smart defaults" [1984]="Hermes-class local roster" [2015]="Job-status false-negative recurrence" [1963]="Codex scope violation" [1990]="GOVERNS hard-fail gate" [1991]="cross_harness_review_required enforcement" [1992]="Audit-log GH_WRITE_ALLOW_HOST_AUTH" [1993]="Capability report routing" [1960]="LIVE-22 gh identity zone-boundary" [2008]="Job-status verified remote delivery" [2012]="Release-docs CI gate scope" )
declare -A TRACK2=( [1973]="Baseline metrics capture" [1974]="Tiered --help" [1975]="Quickstart + guided first-run" [1977]="Docs restructure" [1927]="CLI core/packs split" [1941]="Flaky cold-start test" [1943]="Move cold-start/EPUB out of CI" [1918]="decide --record slug collision" )
declare -A TRACK3=( [1923]="Split viz.py" [1926]="state.db consolidation" [1995]="Cost-log regen drops rows" [1999]="_rotate_project_doc duplication" [1917]="memory.md write-through drift" [1915]="costs.md regen drops rows" [1969]="Cost inflation escalation" [1937]="Cost-inflation record" [1951]="Cost audit redesign" )
declare -A TRACK4=( [1978]="Positioning sentence everywhere" [1979]="Verify job outcomes (narrowed)" )
declare -A TRACK5=( [1980]="route --report + benchmark kit" [1981]="90-day design-partner program" [1982]="Competitive matrix" [1983]="Partnership moves (narrowed)" )

print_track() {
  local name="$1"; shift
  local -n map=$1
  echo ""
  echo "=== $name ==="
  printf "%-6s %-9s %-s\n" "#" "STATE" "TITLE"
  for num in $(echo "${!map[@]}" | tr ' ' '\n' | sort -n); do
    state=$(synlynk gh --role pm -- issue view "$num" --json state -q '.state' 2>/dev/null || echo "?")
    printf "%-6s %-9s %-s\n" "$num" "$state" "${map[$num]}"
  done
}

while true; do
  clear
  echo "Five-Track Status — refreshed $(date '+%Y-%m-%d %H:%M:%S')"
  echo "Plan: docs/superpowers/plans/2026-10-04-five-track-code-adjacency-plan.md"
  print_track "Track 1: Dispatch/Harness Layer (gh:#1985)" TRACK1
  print_track "Track 2: CLI Surface & Taxonomy (gh:#1986)" TRACK2
  print_track "Track 3: Data/Display Layer (gh:#1987)" TRACK3
  print_track "Track 4: Trust & Positioning Copy (gh:#1988)" TRACK4
  print_track "Track 5: Go-to-Market (gh:#1989)" TRACK5
  echo ""
  echo "Press Enter to refresh, Ctrl-C to stop."
  read -r -t 300 _ || true
done
