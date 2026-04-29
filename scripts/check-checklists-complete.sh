#!/usr/bin/env bash
# Gate: scan docs/checklists/*.md for open `[ ]` items.
# Used in CI to enforce that release-blocking lists are closed before tagging.
# Pass CHECKLIST_GATE_LIST="01-platform.md 03-security.md" to scope.
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

if [[ ! -d docs/checklists ]]; then
  echo "docs/checklists not found" >&2
  exit 1
fi

if [[ -n "${CHECKLIST_GATE_LIST:-}" ]]; then
  FILES=()
  for f in $CHECKLIST_GATE_LIST; do
    FILES+=("docs/checklists/$f")
  done
else
  mapfile -t FILES < <(ls docs/checklists/*.md)
fi

mapfile -t OPEN_ITEMS < <(rg --no-heading --line-number '^\s*[-*]\s+\[\s\]' "${FILES[@]}" || true)

if [[ ${#OPEN_ITEMS[@]} -gt 0 ]]; then
  echo "Checklist gate failed: open items remain:" >&2
  printf '%s\n' "${OPEN_ITEMS[@]}" >&2
  printf '\nClose all [ ] items in the listed checklists before merge/release.\n' >&2
  exit 2
fi

echo "Checklist gate passed: all items are closed ([x])."
