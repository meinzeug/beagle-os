#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local value="${1:-}"
  local name="$2"
  if [[ -z "$value" ]]; then
    echo "[copilot-close-issues] ERROR: missing ${name}" >&2
    exit 1
  fi
}

REPO="${GITHUB_REPOSITORY:-}"
WORKFLOW_NAME="${WORKFLOW_NAME:-}"
WORKFLOW_BRANCH="${WORKFLOW_BRANCH:-}"
WORKFLOW_SHA="${WORKFLOW_SHA:-}"
WORKFLOW_URL="${WORKFLOW_URL:-}"
GH_TOKEN="${COPILOT_ASSIGNMENT_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}"

require_var "$REPO" "GITHUB_REPOSITORY"
require_var "$WORKFLOW_NAME" "WORKFLOW_NAME"
require_var "$WORKFLOW_BRANCH" "WORKFLOW_BRANCH"
require_var "$GH_TOKEN" "COPILOT_ASSIGNMENT_TOKEN or GITHUB_TOKEN"

export GH_TOKEN

case "$WORKFLOW_BRANCH" in
  main | v[0-9]*)
    ;;
  *)
    echo "[copilot-close-issues] ${WORKFLOW_BRANCH} is not a release/main branch; skipping" >&2
    exit 0
    ;;
esac

title_prefix="[autofix] ${WORKFLOW_NAME} failed on ${WORKFLOW_BRANCH}"
issues_json="$(gh issue list \
  --repo "$REPO" \
  --state open \
  --search "${title_prefix} in:title" \
  --json number,title,url \
  --limit 100)"

issue_numbers="$(python3 - "$issues_json" "$title_prefix" <<'PY'
import json
import sys

issues = json.loads(sys.argv[1])
prefix = sys.argv[2]
for issue in issues:
    title = str(issue.get("title") or "")
    if title.startswith(prefix):
        print(issue.get("number") or "")
PY
)"

if [[ -z "$issue_numbers" ]]; then
  echo "[copilot-close-issues] no matching open autofix issues for ${title_prefix}" >&2
  exit 0
fi

for issue_number in $issue_numbers; do
  gh issue comment "$issue_number" \
    --repo "$REPO" \
    --body "Resolved automatically: workflow ${WORKFLOW_NAME} passed on ${WORKFLOW_BRANCH} at ${WORKFLOW_SHA:-unknown}. Run: ${WORKFLOW_URL:-unknown}"
  gh issue close "$issue_number" --repo "$REPO"
  echo "[copilot-close-issues] closed issue #${issue_number}" >&2
done
