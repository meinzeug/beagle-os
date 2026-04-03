#!/usr/bin/env bash
set -euo pipefail

INSTALL_ROOT="${BEAGLE_KIOSK_ROOT:-/opt/beagle-kiosk}"
RELEASE_REPO="${BEAGLE_KIOSK_RELEASE_REPO:-meinzeug/beagle-os}"
HASH_URL="${BEAGLE_KIOSK_HASH_URL:-https://beagle-os.com/kiosk-release-hash.txt}"
VERSION="${BEAGLE_KIOSK_VERSION:-latest}"
ASSET_PREFIX="${BEAGLE_KIOSK_ASSET_PREFIX:-beagle-kiosk-v}"
APPIMAGE_NAME=""
ENSURE_ONLY="0"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --version)
      VERSION="${2:-$VERSION}"
      shift 2
      ;;
    --ensure)
      ENSURE_ONLY="1"
      shift
      ;;
    *)
      shift
      ;;
  esac
done

require_root() {
  if [[ "${EUID}" -ne 0 ]]; then
    exec sudo "$0" "$@"
  fi
}

latest_version() {
  curl -fsSL -H 'Accept: application/vnd.github+json' -H 'User-Agent: BeagleKioskInstaller' \
    "https://api.github.com/repos/${RELEASE_REPO}/releases/latest" | python3 - <<'PY'
import json, sys
payload = json.load(sys.stdin)
tag = str(payload.get("tag_name") or "").strip()
print(tag[1:] if tag.startswith("v") else tag)
PY
}

download_url() {
  local version="$1"
  APPIMAGE_NAME="${ASSET_PREFIX}${version}-linux-x64.AppImage"
  printf 'https://github.com/%s/releases/download/v%s/%s\n' "$RELEASE_REPO" "$version" "$APPIMAGE_NAME"
}

expected_hash() {
  local asset_name="$1"
  curl -fsSL "$HASH_URL" | python3 - "$asset_name" <<'PY'
import sys
asset = sys.argv[1]
lines = sys.stdin.read().splitlines()
for line in lines:
    parts = line.strip().split()
    if len(parts) >= 2 and parts[-1] == asset:
        print(parts[0])
        raise SystemExit(0)
if lines:
    print(lines[0].split()[0])
PY
}

install_payload() {
  local version="$1"
  local url tmp_dir asset_path actual expected

  url="$(download_url "$version")"
  tmp_dir="$(mktemp -d)"
  asset_path="$tmp_dir/$APPIMAGE_NAME"

  curl -fL --retry 3 --retry-delay 2 -o "$asset_path" "$url"
  expected="$(expected_hash "$APPIMAGE_NAME")"
  actual="$(sha256sum "$asset_path" | awk '{print $1}')"

  if [[ -z "$expected" || "$actual" != "$expected" ]]; then
    echo "Checksum mismatch for $APPIMAGE_NAME" >&2
    rm -rf "$tmp_dir"
    exit 1
  fi

  install -d -m 0755 "$INSTALL_ROOT" "$INSTALL_ROOT/assets/covers"
  install -m 0755 "$asset_path" "$INSTALL_ROOT/beagle-kiosk"

  cat >"$INSTALL_ROOT/launch.sh" <<'EOF'
#!/usr/bin/env bash
set -euo pipefail
INSTALL_ROOT="${BEAGLE_KIOSK_ROOT:-/opt/beagle-kiosk}"
LOG_DIR="${INSTALL_ROOT}/logs"
LOG_FILE="${LOG_DIR}/kiosk.log"
mkdir -p "$LOG_DIR"
export ELECTRON_DISABLE_SECURITY_WARNINGS=1
export BEAGLE_KIOSK_ROOT="$INSTALL_ROOT"
exec "${INSTALL_ROOT}/beagle-kiosk" >>"$LOG_FILE" 2>&1
EOF
  chmod 0755 "$INSTALL_ROOT/launch.sh"

  if [[ ! -f "$INSTALL_ROOT/kiosk.conf" ]]; then
    cat >"$INSTALL_ROOT/kiosk.conf" <<'EOF'
GFN_BINARY=/usr/bin/GeForceNOW
GFN_BINARY_FALLBACK=/opt/nvidia/GeForceNOW.AppImage
AFFILIATE_CONFIG_URL=https://beagle-os.com/api/kiosk/affiliate-config
AFFILIATE_REQUEST_TIMEOUT_MS=8000
STORE_ALLOWED_DOMAINS=greenmangaming.com fanatical.com humblebundle.com store.epicgames.com
KIOSK_FULLSCREEN=1
STORE_WINDOW_FULLSCREEN=1
DEFAULT_FILTER_GFN_ONLY=1
GFN_GAME_ID_FIELD=gfn_id
EOF
    chmod 0644 "$INSTALL_ROOT/kiosk.conf"
  fi

  if [[ ! -f "$INSTALL_ROOT/games.json" ]]; then
    printf '[]\n' >"$INSTALL_ROOT/games.json"
  fi

  if [[ ! -f "$INSTALL_ROOT/user_library.json" ]]; then
    cat >"$INSTALL_ROOT/user_library.json" <<'EOF'
{
  "logged_in": false,
  "updated_at": null,
  "games": []
}
EOF
  fi

  cat >"$INSTALL_ROOT/update_catalog.py" <<'EOF'
#!/usr/bin/env python3
from __future__ import annotations
import json
import os
import sys
from pathlib import Path
from urllib.error import URLError
from urllib.request import Request, urlopen

INSTALL_ROOT = Path(os.environ.get("BEAGLE_KIOSK_ROOT", "/opt/beagle-kiosk"))
GAMES_PATH = INSTALL_ROOT / "games.json"
MASTER_LIST_URL = os.environ.get("GFN_MASTER_CATALOG_URL", "").strip()

def write_json(path: Path, payload):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

def fetch_json(url: str):
    request = Request(url, headers={"User-Agent": "BeagleOSGamingKiosk/Installer"})
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))

def main() -> int:
    if not MASTER_LIST_URL:
        return 0
    try:
        payload = fetch_json(MASTER_LIST_URL)
    except (URLError, TimeoutError, ValueError) as error:
        print(f"warning: unable to update master catalog: {error}", file=sys.stderr)
        return 0
    games = payload.get("games", payload) if isinstance(payload, dict) else payload
    if isinstance(games, list):
        write_json(GAMES_PATH, games)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
EOF
  chmod 0755 "$INSTALL_ROOT/update_catalog.py"

  cat > /etc/systemd/system/beagle-kiosk-update-catalog.service <<'EOF'
[Unit]
Description=Refresh Beagle OS Gaming catalog
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/python3 /opt/beagle-kiosk/update_catalog.py
EOF

  cat > /etc/systemd/system/beagle-kiosk-update-catalog.timer <<'EOF'
[Unit]
Description=Daily Beagle OS Gaming catalog refresh

[Timer]
OnBootSec=5min
OnUnitActiveSec=24h
Persistent=true
RandomizedDelaySec=20min
Unit=beagle-kiosk-update-catalog.service

[Install]
WantedBy=timers.target
EOF

  printf '{\n  "version": "%s",\n  "asset": "%s"\n}\n' "$version" "$APPIMAGE_NAME" >"$INSTALL_ROOT/release.json"
  chmod 0644 "$INSTALL_ROOT/release.json" "$INSTALL_ROOT/games.json" "$INSTALL_ROOT/user_library.json"
  rm -rf "$tmp_dir"
}

installed_version() {
  python3 - "$INSTALL_ROOT/release.json" <<'PY' 2>/dev/null || true
import json, sys
from pathlib import Path
path = Path(sys.argv[1])
if not path.is_file():
    raise SystemExit(1)
payload = json.loads(path.read_text(encoding="utf-8"))
print(str(payload.get("version") or "").strip())
PY
}

require_root
if [[ "$VERSION" == "latest" ]]; then
  if VERSION="$(latest_version)"; then
    :
  elif [[ -x "$INSTALL_ROOT/beagle-kiosk" ]]; then
    exit 0
  else
    echo "Unable to resolve latest beagle-kiosk release." >&2
    exit 1
  fi
fi

if [[ -x "$INSTALL_ROOT/beagle-kiosk" && "$(installed_version)" == "$VERSION" ]]; then
  systemctl daemon-reload
  systemctl enable --now beagle-kiosk-update-catalog.timer >/dev/null 2>&1 || true
  exit 0
fi

install_payload "$VERSION"
systemctl daemon-reload
systemctl enable --now beagle-kiosk-update-catalog.timer >/dev/null 2>&1 || true
