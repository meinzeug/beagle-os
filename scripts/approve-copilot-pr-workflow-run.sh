#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local value="${1:-}"
  local name="$2"
  if [[ -z "$value" ]]; then
    echo "[copilot-approve] ERROR: missing ${name}" >&2
    exit 1
  fi
}

REPO="${GITHUB_REPOSITORY:-}"
RUN_ID="${WORKFLOW_RUN_ID:-}"
WORKFLOW_BRANCH="${WORKFLOW_BRANCH:-}"
WORKFLOW_SHA="${WORKFLOW_SHA:-}"
GH_TOKEN="${COPILOT_ASSIGNMENT_TOKEN:-${GITHUB_TOKEN:-${GH_TOKEN:-}}}"

require_var "$REPO" "GITHUB_REPOSITORY"
require_var "$RUN_ID" "WORKFLOW_RUN_ID"
require_var "$WORKFLOW_BRANCH" "WORKFLOW_BRANCH"
require_var "$GH_TOKEN" "COPILOT_ASSIGNMENT_TOKEN or GITHUB_TOKEN"

export GH_TOKEN

if [[ "$WORKFLOW_BRANCH" != copilot/* ]]; then
  echo "[copilot-approve] branch ${WORKFLOW_BRANCH} is not a Copilot branch; skipping" >&2
  exit 0
fi

pr_json="$(gh pr list \
  --repo "$REPO" \
  --head "$WORKFLOW_BRANCH" \
  --state open \
  --json number,author,isDraft,headRefOid \
  --limit 10)"

pr_number="$(python3 - "$pr_json" "$WORKFLOW_SHA" <<'PY'
import json
import sys

prs = json.loads(sys.argv[1])
workflow_sha = sys.argv[2]
for pr in prs:
    author = ((pr.get("author") or {}).get("login") or "")
    if author not in {"copilot-swe-agent", "copilot-swe-agent[bot]", "app/copilot-swe-agent"}:
        continue
    if workflow_sha and pr.get("headRefOid") and pr.get("headRefOid") != workflow_sha:
        continue
    print(pr.get("number") or "")
    raise SystemExit(0)
print("")
PY
)"

if [[ -z "$pr_number" ]]; then
  echo "[copilot-approve] no open Copilot PR found for ${WORKFLOW_BRANCH}/${WORKFLOW_SHA}" >&2
  exit 0
fi

is_draft="$(python3 - "$pr_json" "$pr_number" <<'PY'
import json
import sys

prs = json.loads(sys.argv[1])
number = int(sys.argv[2])
for pr in prs:
    if pr.get("number") == number:
        print("true" if pr.get("isDraft") else "false")
        raise SystemExit(0)
print("false")
PY
)"

if [[ "$is_draft" == "true" ]]; then
  echo "[copilot-approve] marking PR #${pr_number} ready for review" >&2
  gh pr ready "$pr_number" --repo "$REPO" || true
fi

echo "[copilot-approve] approving workflow run ${RUN_ID} for PR #${pr_number}" >&2
gh api -X POST "repos/${REPO}/actions/runs/${RUN_ID}/approve" >/dev/null || {
  echo "[copilot-approve] workflow run ${RUN_ID} could not be approved; it may not require approval anymore" >&2
}
