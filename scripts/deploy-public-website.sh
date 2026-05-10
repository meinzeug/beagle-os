#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SITE_SRC_DIR="${BEAGLE_PUBLIC_SITE_DIR:-$ROOT_DIR/public-site}"
SITE_TARGET="${BEAGLE_PUBLIC_SITE_TARGET:-}"
SITE_APP_TARGET="${BEAGLE_PUBLIC_SITE_APP_TARGET:-}"
PUBLIC_UPDATE_BASE_URL="${BEAGLE_PUBLIC_UPDATE_BASE_URL:-https://beagle-os.com/beagle-updates}"
SSH_KEY_FILE="${BEAGLE_SSH_KEY_FILE:-$HOME/.ssh/id_ed25519}"
SSH_KNOWN_HOSTS_FILE="${BEAGLE_SSH_KNOWN_HOSTS_FILE:-$HOME/.ssh/known_hosts}"
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
[[ -r "$SSH_KEY_FILE" ]] || {
  echo "SSH key not readable: $SSH_KEY_FILE" >&2
  exit 1
}
[[ -r "$SSH_KNOWN_HOSTS_FILE" ]] || {
  echo "SSH known_hosts not readable: $SSH_KNOWN_HOSTS_FILE" >&2
  exit 1
}

if [[ -z "$SITE_APP_TARGET" ]] && [[ "$SITE_TARGET" =~ ^([^:]+):(.+)$ ]]; then
  SITE_APP_TARGET="${BASH_REMATCH[1]}:/opt/beagle-os-saas/src/public/"
fi

export RSYNC_RSH="ssh -i $SSH_KEY_FILE -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o UserKnownHostsFile=$SSH_KNOWN_HOSTS_FILE -o BatchMode=yes"

render_dir="$(mktemp -d)"
cleanup() {
  rm -rf "$render_dir"
}
trap cleanup EXIT

rsync -a --delete --exclude '.git/' "$SITE_SRC_DIR/" "$render_dir/"

SERVER_INSTALLIMAGE_FILENAME="${BEAGLE_SERVER_INSTALLIMAGE_TARBALL_FILENAME:-Debian-1301-trixie-amd64-beagle-server.tar.gz}"

python3 "$ROOT_DIR/scripts/render-site-templates.py" \
  "$render_dir" "$RELEASE_TAG" "$GITHUB_RELEASE_URL" "${PUBLIC_UPDATE_BASE_URL%/}" "$SERVER_INSTALLIMAGE_FILENAME"

rsync -av --delete --exclude 'beagle-updates/' --exclude '.git/' "$render_dir/" "$SITE_TARGET"

if [[ -n "$SITE_APP_TARGET" && "$SITE_APP_TARGET" != "$SITE_TARGET" ]]; then
  rsync -av --delete --exclude 'beagle-updates/' --exclude '.git/' "$render_dir/" "$SITE_APP_TARGET"
fi

echo "Published public website to $SITE_TARGET"
if [[ -n "$SITE_APP_TARGET" && "$SITE_APP_TARGET" != "$SITE_TARGET" ]]; then
  echo "Published public website app mirror to $SITE_APP_TARGET"
fi
