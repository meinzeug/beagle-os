#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WRITE_FILE=""
GITHUB_OUTPUT_FILE=""

usage() {
  cat >&2 <<'EOF'
Usage: resolve-release-version.sh [--write VERSION_FILE] [--github-output GITHUB_OUTPUT]

Resolves the Beagle OS release version.

Precedence:
  1. BEAGLE_RELEASE_VERSION, with optional leading "v"
  2. Git tag refs named vX.Y.Z
  3. max(VERSION file, latest vX.Y.Z git tag) with patch bumped by one
EOF
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    --write)
      WRITE_FILE="$2"
      shift 2
      ;;
    --github-output)
      GITHUB_OUTPUT_FILE="$2"
      shift 2
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      usage
      exit 2
      ;;
  esac
done

normalize_version() {
  local value="$1"
  value="${value#v}"
  value="$(printf '%s' "$value" | tr -d ' \n\r\t')"
  if [[ ! "$value" =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
    echo "Invalid SemVer core version: $value" >&2
    exit 1
  fi
  printf '%s\n' "$value"
}

semver_key() {
  local version="$1" major minor patch
  IFS=. read -r major minor patch <<<"$version"
  printf '%09d.%09d.%09d\n' "$major" "$minor" "$patch"
}

semver_max() {
  local left="$1" right="$2"
  if [[ "$(semver_key "$left")" > "$(semver_key "$right")" ]]; then
    printf '%s\n' "$left"
  else
    printf '%s\n' "$right"
  fi
}

bump_patch() {
  local version="$1" major minor patch
  IFS=. read -r major minor patch <<<"$version"
  printf '%s.%s.%s\n' "$major" "$minor" "$((patch + 1))"
}

if [[ -n "${BEAGLE_RELEASE_VERSION:-}" ]]; then
  VERSION="$(normalize_version "$BEAGLE_RELEASE_VERSION")"
elif [[ "${GITHUB_REF_TYPE:-}" == "tag" && "${GITHUB_REF_NAME:-}" =~ ^v[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
  VERSION="$(normalize_version "$GITHUB_REF_NAME")"
else
  BASE_VERSION="$(normalize_version "$(cat "$ROOT_DIR/VERSION")")"
  if git -C "$ROOT_DIR" rev-parse --git-dir >/dev/null 2>&1; then
    git -C "$ROOT_DIR" fetch --tags --force --quiet origin '+refs/tags/v*:refs/tags/v*' 2>/dev/null || true
    HEAD_TAG="$(git -C "$ROOT_DIR" tag --points-at HEAD -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n 1 || true)"
    if [[ -n "$HEAD_TAG" ]]; then
      VERSION="$(normalize_version "$HEAD_TAG")"
      if [[ -n "$WRITE_FILE" ]]; then
        printf '%s\n' "$VERSION" > "$WRITE_FILE"
      fi
      if [[ -n "$GITHUB_OUTPUT_FILE" ]]; then
        {
          printf 'version=%s\n' "$VERSION"
          printf 'tag=v%s\n' "$VERSION"
        } >> "$GITHUB_OUTPUT_FILE"
      fi
      printf '%s\n' "$VERSION"
      exit 0
    fi
    LATEST_TAG="$(git -C "$ROOT_DIR" tag -l 'v[0-9]*.[0-9]*.[0-9]*' --sort=-v:refname | head -n 1 || true)"
    if [[ -n "$LATEST_TAG" ]]; then
      BASE_VERSION="$(semver_max "$BASE_VERSION" "$(normalize_version "$LATEST_TAG")")"
    fi
  fi
  VERSION="$(bump_patch "$BASE_VERSION")"
fi

if [[ -n "$WRITE_FILE" ]]; then
  printf '%s\n' "$VERSION" > "$WRITE_FILE"
fi

if [[ -n "$GITHUB_OUTPUT_FILE" ]]; then
  {
    printf 'version=%s\n' "$VERSION"
    printf 'tag=v%s\n' "$VERSION"
  } >> "$GITHUB_OUTPUT_FILE"
fi

printf '%s\n' "$VERSION"
