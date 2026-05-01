#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_SRC_DIR="${BEAGLE_PUBLIC_SITE_DIR:-$ROOT_DIR/public-site}"
SITE_TARGET="${BEAGLE_PUBLIC_SITE_TARGET:-}"
PUBLIC_UPDATE_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
RELEASE_TAG="v${VERSION}"
GITHUB_RELEASE_URL="https://github.com/meinzeug/beagle-os/releases/tag/${RELEASE_TAG}"

[[ -n "$SITE_TARGET" ]] || {
  echo "Set BEAGLE_PUBLIC_SITE_TARGET to an SSH rsync target." >&2
  exit 1
}
[[ -d "$SITE_SRC_DIR" ]] || {
  echo "Public site source directory not found: $SITE_SRC_DIR" >&2
  exit 1
}

render_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$render_dir"
}
trap cleanup EXIT

rsync -a --delete "$SITE_SRC_DIR/" "$render_dir/"

python3 "$(dirname "${BASH_SOURCE[0]}")/render-site-templates.py" \
  "$render_dir" "$RELEASE_TAG" "$GITHUB_RELEASE_URL" "${PUBLIC_UPDATE_BASE_URL%/}"

rsync -av --delete --exclude 'beagle-updates/' "$render_dir/" "$SITE_TARGET"

echo "Published public website to $SITE_TARGET"
