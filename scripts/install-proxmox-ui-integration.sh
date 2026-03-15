#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PVE_DIR="/usr/share/pve-manager"
JS_TARGET="$PVE_DIR/js/pve-dcv-integration.js"
TPL_TARGET="$PVE_DIR/index.html.tpl"
TPL_BACKUP="$PVE_DIR/index.html.tpl.pve-dcv-integration.bak"
INCLUDE_LINE='    <script type="text/javascript" src="/pve2/js/pve-dcv-integration.js?ver=[% version %]"></script>'

if [[ "${EUID}" -ne 0 ]]; then
  echo "This installer must run as root." >&2
  exit 1
fi

if [[ ! -d "$PVE_DIR/js" || ! -f "$TPL_TARGET" ]]; then
  echo "Proxmox UI files not found under $PVE_DIR" >&2
  exit 1
fi

install -D -m 0644 "$ROOT_DIR/proxmox-ui/pve-dcv-integration.js" "$JS_TARGET"

if [[ ! -f "$TPL_BACKUP" ]]; then
  cp "$TPL_TARGET" "$TPL_BACKUP"
fi

if ! grep -Fq '/pve2/js/pve-dcv-integration.js' "$TPL_TARGET"; then
  python3 - "$TPL_TARGET" "$INCLUDE_LINE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
include = sys.argv[2]
text = path.read_text()
needle = '    <script type="text/javascript" src="/pve2/js/pvemanagerlib.js?ver=[% version %]"></script>\n'
if needle not in text:
    raise SystemExit("needle not found in index.html.tpl")
text = text.replace(needle, needle + include + "\n", 1)
path.write_text(text)
PY
fi

systemctl restart pveproxy
echo "Installed Proxmox UI integration to $JS_TARGET"
