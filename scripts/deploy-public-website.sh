#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_SRC_DIR="${BEAGLE_PUBLIC_SITE_DIR:-$ROOT_DIR/public-site}"
SITE_TARGET="${BEAGLE_PUBLIC_SITE_TARGET:-}"
SITE_APP_TARGET="${BEAGLE_PUBLIC_SITE_APP_TARGET:-}"
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

if [[ -z "$SITE_APP_TARGET" ]] && [[ "$SITE_TARGET" =~ ^([^:]+):(.+)$ ]]; then
  SITE_APP_TARGET="${BASH_REMATCH[1]}:/opt/beagle-os-saas/src/public/"
fi

render_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$render_dir"
}
trap cleanup EXIT

rsync -a --delete "$SITE_SRC_DIR/" "$render_dir/"

python3 - "$render_dir" "$RELEASE_TAG" "$GITHUB_RELEASE_URL" "${PUBLIC_UPDATE_BASE_URL%/}" <<'PY'
from pathlib import Path
import sys

root = Path(sys.argv[1])
release_tag = sys.argv[2]
github_release_url = sys.argv[3]
public_update_base_url = sys.argv[4]

replacements = {
    "__BEAGLE_RELEASE_TAG__": release_tag,
    "__BEAGLE_GITHUB_RELEASE_URL__": github_release_url,
    "__BEAGLE_PUBLIC_UPDATE_BASE_URL__": public_update_base_url,
}

for path in root.rglob("*"):
    if not path.is_file():
        continue
    if path.suffix.lower() not in {".html", ".css", ".js", ".json", ".txt"}:
        continue
    content = path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        content = content.replace(old, new)
    path.write_text(content, encoding="utf-8")
PY

rsync -av --delete --exclude 'beagle-updates/' "$render_dir/" "$SITE_TARGET"

if [[ -n "$SITE_APP_TARGET" && "$SITE_APP_TARGET" != "$SITE_TARGET" ]]; then
  rsync -av --delete --exclude 'beagle-updates/' "$render_dir/" "$SITE_APP_TARGET"
fi

echo "Published public website to $SITE_TARGET"
if [[ -n "$SITE_APP_TARGET" && "$SITE_APP_TARGET" != "$SITE_TARGET" ]]; then
  echo "Published public website app mirror to $SITE_APP_TARGET"
fi
