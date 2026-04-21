#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ALLOWLIST_FILE="${BEAGLE_SECRETS_ALLOWLIST_FILE:-$ROOT_DIR/.security-secrets-allowlist}"
REPORT_FILE="${BEAGLE_SECRETS_REPORT_FILE:-$ROOT_DIR/dist/security-audit/secrets-check.txt}"

mkdir -p "$(dirname "$REPORT_FILE")"
: > "$REPORT_FILE"

log() {
  echo "$*" | tee -a "$REPORT_FILE"
}

fail() {
  log "[FAIL] $*"
  exit 1
}

require_cmd() {
  command -v "$1" >/dev/null 2>&1 || fail "Missing required command: $1"
}

require_cmd git

search_tool() {
  if command -v rg >/dev/null 2>&1; then
    printf 'rg\n'
    return 0
  fi
  if command -v grep >/dev/null 2>&1; then
    printf 'grep\n'
    return 0
  fi
  fail "Missing required command: rg or grep"
}

SEARCH_TOOL="$(search_tool)"

repo_is_git=1
if ! git -C "$ROOT_DIR" rev-parse --is-inside-work-tree >/dev/null 2>&1; then
  repo_is_git=0
fi

list_files() {
  if [[ "$repo_is_git" -eq 1 ]]; then
    git -C "$ROOT_DIR" ls-files
    return 0
  fi
  find "$ROOT_DIR" -type f \
    ! -path '*/.git/*' \
    ! -path '*/dist/*' \
    ! -path '*/.build/*' \
    ! -path '*/node_modules/*' \
    | sed "s#^$ROOT_DIR/##"
}

log "[INFO] Running secrets hygiene checks"

if [[ "$repo_is_git" -eq 1 ]]; then
  if git -C "$ROOT_DIR" ls-files --error-unmatch .env >/dev/null 2>&1; then
    fail "Tracked .env file detected in repository"
  fi

  if git -C "$ROOT_DIR" ls-files --error-unmatch '.env.*' >/dev/null 2>&1; then
    fail "Tracked .env.* file detected in repository"
  fi
else
  if [[ -f "$ROOT_DIR/.env" ]] || find "$ROOT_DIR" -maxdepth 2 -type f -name '.env.*' | grep -q .; then
    fail "Environment files (.env/.env.*) found in deployment tree"
  fi
fi

if [[ "$SEARCH_TOOL" == "rg" ]]; then
  rg -n '^\.env$|^\.env\.\*$' "$ROOT_DIR/.gitignore" >/dev/null 2>&1 || fail ".gitignore must include .env and .env.* rules"
else
  grep -nE '^\.env$|^\.env\.\*$' "$ROOT_DIR/.gitignore" >/dev/null 2>&1 || fail ".gitignore must include .env and .env.* rules"
fi

if [[ "$repo_is_git" -eq 1 ]] && git -C "$ROOT_DIR" ls-files --error-unmatch AGENTS.md >/dev/null 2>&1; then
  fail "AGENTS.md must stay untracked"
fi

pattern='(AKIA[0-9A-Z]{16}|-----BEGIN (RSA|EC|OPENSSH|PGP) PRIVATE KEY-----|([Aa][Pp][Ii][_ -]?[Kk][Ee][Yy]|[Ss][Ee][Cc][Rr][Ee][Tt]|[Tt][Oo][Kk][Ee][Nn]|[Pp][Aa][Ss][Ss][Ww][Oo][Rr][Dd])\s*[:=]\s*["'"'"'][^"'"'"' ]{8,}["'"'"'])'

if [[ "$SEARCH_TOOL" == "rg" ]]; then
  matches="$(list_files | rg -n -H -g '!*.ppm' -g '!docs/**' -g '!*.md' -e "$pattern" || true)"
else
  matches="$(list_files | grep -nE "$pattern" || true)"
fi

if [[ -n "$matches" && -f "$ALLOWLIST_FILE" ]]; then
  while IFS= read -r allowed; do
    [[ -z "$allowed" || "$allowed" =~ ^# ]] && continue
    if [[ "$SEARCH_TOOL" == "rg" ]]; then
      matches="$(printf '%s\n' "$matches" | rg -v "$allowed" || true)"
    else
      matches="$(printf '%s\n' "$matches" | grep -vE "$allowed" || true)"
    fi
  done < "$ALLOWLIST_FILE"
fi

if [[ -n "$matches" ]]; then
  log "[FAIL] Potential hard-coded secrets detected:"
  printf '%s\n' "$matches" | tee -a "$REPORT_FILE"
  exit 1
fi

log "[PASS] Secrets hygiene checks passed"
