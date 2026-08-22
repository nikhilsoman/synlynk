#!/usr/bin/env bash
set -euo pipefail

endpoint="repos/nikhilsoman/synlynk/branches/main/protection/required_status_checks"
error_file="$(mktemp)"
trap 'rm -f "$error_file"' EXIT

if current_contexts="$(gh api "$endpoint" --jq '.contexts' 2>"$error_file")"; then
    :
else
    if grep -q '404' "$error_file"; then
        current_contexts='[]'
    else
        cat "$error_file" >&2
        exit 1
    fi
fi

current_contexts="${current_contexts:-[]}"
if ! jq -e 'type == "array"' >/dev/null <<<"$current_contexts"; then
    echo "Expected required status-check contexts to be a JSON array" >&2
    exit 1
fi

if jq -e 'index("qa-gate") != null' >/dev/null <<<"$current_contexts"; then
    echo "qa-gate is already present in main's required status checks; no changes needed."
    exit 0
fi

merged_contexts="$(jq -c '
    reduce .[] as $context
      ([]; if index($context) == null then . + [$context] else . end)
    + ["qa-gate"]
  ' <<<"$current_contexts")"
echo "Merged required status checks: $merged_contexts"

read -r -p "Apply this to main's branch protection [y/N] " answer
if [[ "$answer" != "y" ]]; then
    echo "Aborted; no changes made."
    exit 1
fi

payload="$(jq -cn --argjson contexts "$merged_contexts" \
    '{strict: true, contexts: $contexts}')"
printf '%s\n' "$payload" |
    gh api "$endpoint" --method PATCH --input -
