#!/usr/bin/env bash
# Verify a restored state database on a remote node without applying another restore.
set -euo pipefail

if [ "$#" -ne 5 ]; then
  echo "usage: $0 REMOTE SNAPSHOT CANONICAL_STATE PRODUCT_SLUG PRODUCT_ID" >&2
  exit 64
fi

REMOTE=$1
SNAPSHOT=$2
CANONICAL_STATE=$3
PRODUCT_SLUG=$4
PRODUCT_ID=$5

ssh "$REMOTE" bash -s -- "$SNAPSHOT" "$CANONICAL_STATE" "$PRODUCT_SLUG" "$PRODUCT_ID" <<'REMOTE_CHECK'
set -euo pipefail

SNAPSHOT=$1
CANONICAL_STATE=$2
PRODUCT_SLUG=$3
PRODUCT_ID=$4

echo "== DR restore dry-run =="
synlynk state restore "$SNAPSHOT" "$CANONICAL_STATE" \
  --slug "$PRODUCT_SLUG" \
  --product-id "$PRODUCT_ID"

echo "== State inventory =="
synlynk state inventory --all

echo "== Synlynk status =="
synlynk status

echo "== Checkpoint =="
synlynk checkpoint
REMOTE_CHECK
