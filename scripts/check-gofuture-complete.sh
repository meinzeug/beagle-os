#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d docs/gofuture ]]; then
  echo "docs/gofuture not found" >&2
  exit 1
fi

# Match markdown checklist items that are still open.
# Examples: "- [ ] task" or "* [ ] task" (with optional leading spaces).
mapfile -t OPEN_ITEMS < <(rg --no-heading --line-number '^\s*[-*]\s+\[\s\]' docs/gofuture/*.md || true)

if [[ ${#OPEN_ITEMS[@]} -gt 0 ]]; then
  echo "GoFuture gate failed: open checklist items remain in docs/gofuture:" >&2
  printf '%s\n' "${OPEN_ITEMS[@]}" >&2
  echo "\nClose all [ ] items before merge/push." >&2
  exit 2
fi

echo "GoFuture gate passed: all checklist items are closed ([x])."
