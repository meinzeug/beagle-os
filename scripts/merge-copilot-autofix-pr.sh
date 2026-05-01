#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local value="${1:-}"
  local name="$2"
  if [[ -z "$value" ]]; then
    echo "[copilot-automerge] ERROR: missing ${name}" >&2
    exit 1
  fi
}

REPO="${GITHUB_REPOSITORY:-}"
RUN_ID="${WORKFLOW_RUN_ID:-}"
WORKFLOW_NAME="${WORKFLOW_NAME:-}"
WORKFLOW_URL="${WORKFLOW_URL:-}"
WORKFLOW_BRANCH="${WORKFLOW_BRANCH:-}"
WORKFLOW_SHA="${WORKFLOW_SHA:-}"
GH_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"

require_var "$REPO" "GITHUB_REPOSITORY"
require_var "$RUN_ID" "WORKFLOW_RUN_ID"
require_var "$WORKFLOW_SHA" "WORKFLOW_SHA"
require_var "$GH_TOKEN" "GITHUB_TOKEN"

export GH_TOKEN

run_url="${WORKFLOW_URL:-https://github.com/${REPO}/actions/runs/${RUN_ID}}"

pr_json="$(gh api "repos/${REPO}/commits/${WORKFLOW_SHA}/pulls" -H 'Accept: application/vnd.github+json')"
pr_number="$(python3 - "$pr_json" <<'PY'
import json
import sys

data = json.loads(sys.argv[1])
for pr in data:
    user = ((pr.get("user") or {}).get("login") or "")
    if user == "copilot-swe-agent" and pr.get("state") == "open":
        print(pr.get("number") or "")
        raise SystemExit(0)
print("")
PY
)"

if [[ -z "$pr_number" ]]; then
  echo "[copilot-automerge] no open Copilot PR found for ${WORKFLOW_SHA} (${WORKFLOW_NAME})" >&2
  exit 0
fi

pr_view="$(gh pr view "$pr_number" --repo "$REPO" --json author,isDraft,headRefOid,mergeStateStatus,reviewDecision,url,title,number)"
pr_author="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print((((data.get("author") or {}).get("login")) or ""))
PY
)"
pr_draft="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print("true" if data.get("isDraft") else "false")
PY
)"
pr_head="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("headRefOid") or "")
PY
)"
merge_state="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("mergeStateStatus") or "")
PY
)"
review_decision="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("reviewDecision") or "")
PY
)"
pr_url="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("url") or "")
PY
)"

if [[ "$pr_author" != "copilot-swe-agent[bot]" && "$pr_author" != "copilot-swe-agent" ]]; then
  echo "[copilot-automerge] PR #${pr_number} is not owned by Copilot (${pr_author})" >&2
  exit 0
fi

if [[ "$pr_draft" == "true" ]]; then
  echo "[copilot-automerge] PR #${pr_number} is still draft: ${pr_url}" >&2
  exit 0
fi

if [[ -n "$pr_head" && "$pr_head" != "$WORKFLOW_SHA" ]]; then
  echo "[copilot-automerge] PR #${pr_number} head moved (${pr_head} != ${WORKFLOW_SHA}); wait for a fresh run" >&2
  exit 0
fi

if [[ "$review_decision" == "CHANGES_REQUESTED" ]]; then
  echo "[copilot-automerge] PR #${pr_number} has requested changes; not auto-merging ${pr_url}" >&2
  exit 0
fi

if [[ "$review_decision" != "APPROVED" ]]; then
  echo "[copilot-automerge] approving PR #${pr_number} before merge (review=${review_decision})" >&2
  gh pr review "$pr_number" \
    --repo "$REPO" \
    --approve \
    --body "Automated approval for Copilot autofix after passing checks."

  pr_view="$(gh pr view "$pr_number" --repo "$REPO" --json author,isDraft,headRefOid,mergeStateStatus,reviewDecision,url,title,number)"
  merge_state="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("mergeStateStatus") or "")
PY
)"
  review_decision="$(python3 - "$pr_view" <<'PY'
import json
import sys
data = json.loads(sys.argv[1])
print(data.get("reviewDecision") or "")
PY
)"
fi

if [[ "$merge_state" == "CLEAN" ]]; then
  echo "[copilot-automerge] merging PR #${pr_number} from ${run_url}" >&2
  gh pr merge "$pr_number" \
    --repo "$REPO" \
    --squash \
    --delete-branch \
    --match-head-commit "$WORKFLOW_SHA"
  exit 0
fi

echo "[copilot-automerge] PR #${pr_number} is not merge-clean yet (mergeState=${merge_state}, review=${review_decision}); enabling auto-merge as fallback" >&2
gh pr merge "$pr_number" \
  --repo "$REPO" \
  --auto \
  --squash \
  --delete-branch \
  --match-head-commit "$WORKFLOW_SHA" || true
