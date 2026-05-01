#!/usr/bin/env bash
set -euo pipefail

require_var() {
  local value="${1:-}"
  local name="$2"
  if [[ -z "$value" ]]; then
    echo "[copilot-autofix] ERROR: missing ${name}" >&2
    exit 1
  fi
}

REPO="${GITHUB_REPOSITORY:-}"
RUN_ID="${WORKFLOW_RUN_ID:-}"
WORKFLOW_NAME="${WORKFLOW_NAME:-}"
WORKFLOW_URL="${WORKFLOW_URL:-}"
WORKFLOW_BRANCH="${WORKFLOW_BRANCH:-}"
WORKFLOW_SHA="${WORKFLOW_SHA:-}"
WORKFLOW_CONCLUSION="${WORKFLOW_CONCLUSION:-failure}"
GH_TOKEN="${COPILOT_ASSIGNMENT_TOKEN:-${GH_TOKEN:-}}"

require_var "$REPO" "GITHUB_REPOSITORY"
require_var "$RUN_ID" "WORKFLOW_RUN_ID"
require_var "$WORKFLOW_NAME" "WORKFLOW_NAME"
require_var "$GH_TOKEN" "COPILOT_ASSIGNMENT_TOKEN"

export GH_TOKEN

owner="${REPO%%/*}"
repo_name="${REPO#*/}"
base_branch="${WORKFLOW_BRANCH:-main}"
short_sha="${WORKFLOW_SHA:0:8}"
issue_title="[autofix] ${WORKFLOW_NAME} failed on ${base_branch} ${short_sha}"
dedupe_title="[autofix] ${WORKFLOW_NAME} failed on ${base_branch}"
run_url="${WORKFLOW_URL:-https://github.com/${REPO}/actions/runs/${RUN_ID}}"

run_log="$(gh run view "$RUN_ID" --repo "$REPO" --log-failed 2>/dev/null || true)"
if [[ -n "$run_log" ]]; then
  run_log="$(printf '%s\n' "$run_log" | tail -n 180)"
else
  run_log="No log tail could be retrieved automatically."
fi

issue_body="$(cat <<EOF
Automated CI failure detected.

Workflow: ${WORKFLOW_NAME}
Conclusion: ${WORKFLOW_CONCLUSION}
Repository: ${REPO}
Branch: ${base_branch}
Commit: ${WORKFLOW_SHA:-unknown}
Run: ${run_url}

Please fix the failing workflow in this repository and keep the intended behavior intact.

Failure log tail:
\`\`\`
${run_log}
\`\`\`
EOF
)"

query_repo='query($owner:String!, $name:String!) { repository(owner: $owner, name: $name) { id suggestedActors(capabilities: [CAN_BE_ASSIGNED], first: 100) { nodes { login __typename ... on Bot { id } } } } }'
repo_json="$(gh api graphql \
  -H 'GraphQL-Features: issues_copilot_assignment_api_support,coding_agent_model_selection' \
  -f query="$query_repo" \
  -F owner="$owner" \
  -F name="$repo_name")"

repo_id="$(python3 - "$repo_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
repo = ((data.get("data") or {}).get("repository") or {})
print(repo.get("id") or "")
PY
)"

copilot_id="$(python3 - "$repo_json" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
nodes = (((data.get("data") or {}).get("repository") or {}).get("suggestedActors") or {}).get("nodes") or []
for node in nodes:
    if str(node.get("login") or "") == "copilot-swe-agent":
        print(node.get("id") or "")
        raise SystemExit(0)
print("")
PY
)"

if [[ -z "$repo_id" || -z "$copilot_id" ]]; then
  echo "[copilot-autofix] ERROR: Copilot coding agent is not available for ${REPO}" >&2
  exit 1
fi

existing_issue="$(gh issue list \
  --repo "$REPO" \
  --state open \
  --search "${dedupe_title} in:title" \
  --json number,title,url \
  --limit 20)"

existing_number="$(python3 - "$existing_issue" "$dedupe_title" <<'PY'
import json
import sys

issues = json.loads(sys.argv[1])
prefix = sys.argv[2]
for issue in issues:
    title = str(issue.get("title") or "")
    if title.startswith(prefix):
        print(issue.get("number") or "")
        raise SystemExit(0)
print("")
PY
)"

if [[ -n "$existing_number" ]]; then
  gh issue comment "$existing_number" \
    --repo "$REPO" \
    --body "Another failure for this workflow/branch was detected at ${WORKFLOW_SHA:-unknown}: ${run_url}"
  echo "[copilot-autofix] reused existing issue #${existing_number} for ${dedupe_title}"
  exit 0
fi

create_issue_query='mutation($repositoryId: ID!, $botId: ID!, $title: String!, $body: String!, $baseBranch: String!, $targetRepositoryId: ID!, $instructions: String!) { createIssue(input: { repositoryId: $repositoryId, title: $title, body: $body, assigneeIds: [$botId], agentAssignment: { targetRepositoryId: $targetRepositoryId, baseRef: $baseBranch, customInstructions: $instructions, customAgent: "", model: "" } }) { issue { id url number title } } }'
create_result="$(gh api graphql \
  -H 'GraphQL-Features: issues_copilot_assignment_api_support,coding_agent_model_selection' \
  -f query="$create_issue_query" \
  -F repositoryId="$repo_id" \
  -F botId="$copilot_id" \
  -F title="$issue_title" \
  -F body="$issue_body" \
  -F baseBranch="$base_branch" \
  -F targetRepositoryId="$repo_id" \
  -F instructions='Fix the failing workflow in this repository, keep the current behavior intact, and update tests or docs only when needed.' \
)"

python3 - "$create_result" <<'PY'
import json, sys
data = json.loads(sys.argv[1])
issue = (((data.get("data") or {}).get("createIssue") or {}).get("issue") or {})
print(f"[copilot-autofix] created issue #{issue.get('number')} {issue.get('url')}")
PY
