#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUN_PACKAGE="${RUN_PACKAGE:-0}"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"

check_tool() {
  local tool="$1"
  if ! command -v "$tool" >/dev/null 2>&1; then
    echo "Missing required tool: $tool" >&2
    exit 1
  fi
}

check_tool bash
check_tool node
check_tool rg
check_tool python3

required_docs=(
  "$ROOT_DIR/AGENTS.md"
  "$ROOT_DIR/docs/refactor/00-system-overview.md"
  "$ROOT_DIR/docs/refactor/01-problem-analysis.md"
  "$ROOT_DIR/docs/refactor/02-target-architecture.md"
  "$ROOT_DIR/docs/refactor/03-refactor-plan.md"
  "$ROOT_DIR/docs/refactor/04-risk-register.md"
  "$ROOT_DIR/docs/refactor/05-progress.md"
  "$ROOT_DIR/docs/refactor/06-next-steps.md"
  "$ROOT_DIR/docs/refactor/07-decisions.md"
  "$ROOT_DIR/docs/refactor/08-todo-global.md"
  "$ROOT_DIR/docs/refactor/09-provider-abstraction.md"
)

for file in "${required_docs[@]}"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing required documentation file: $file" >&2
    exit 1
  fi
done

mapfile -t shell_files < <(
  find \
    "$ROOT_DIR/scripts" \
    "$ROOT_DIR/thin-client-assistant" \
    "$ROOT_DIR/beagle-kiosk" \
    "$ROOT_DIR/server-installer" \
    -type f \
    \( -name '*.sh' -o -name '*.hook.chroot' \) \
    | sort
)
for file in "${shell_files[@]}"; do
  bash -n "$file"
done
bash -n "$ROOT_DIR/server-installer/live-build/auto/config"

mapfile -t python_files < <(
  find \
    "$ROOT_DIR/proxmox-host" \
    "$ROOT_DIR/thin-client-assistant" \
    "$ROOT_DIR/beagle-kiosk" \
    -type f \
    -name '*.py' \
    | sort
)
if (( ${#python_files[@]} > 0 )); then
  python3 -m py_compile "${python_files[@]}"
fi

node --check "$ROOT_DIR/proxmox-ui/beagle-ui.js"
node --check "$ROOT_DIR/proxmox-ui/beagle-ui-common.js"
node --check "$ROOT_DIR/core/provider/registry.js"
node --check "$ROOT_DIR/core/virtualization/service.js"
node --check "$ROOT_DIR/core/platform/service.js"
node --check "$ROOT_DIR/providers/proxmox/virtualization-provider.js"
node --check "$ROOT_DIR/proxmox-ui/api-client/beagle-api.js"
node --check "$ROOT_DIR/proxmox-ui/beagle-autologin.js"
node --check "$ROOT_DIR/proxmox-ui/provisioning/api.js"
node --check "$ROOT_DIR/proxmox-ui/state/installer-eligibility.js"
node --check "$ROOT_DIR/proxmox-ui/state/vm-profile.js"
node --check "$ROOT_DIR/proxmox-ui/usb/api.js"
node --check "$ROOT_DIR/proxmox-ui/usb/ui.js"
node --check "$ROOT_DIR/proxmox-ui/components/ui-helpers.js"
node --check "$ROOT_DIR/proxmox-ui/components/desktop-overlay.js"
node --check "$ROOT_DIR/proxmox-ui/components/profile-modal.js"
node --check "$ROOT_DIR/proxmox-ui/components/fleet-modal.js"
node --check "$ROOT_DIR/proxmox-ui/components/provisioning-result-modal.js"
node --check "$ROOT_DIR/proxmox-ui/components/provisioning-create-modal.js"
node --check "$ROOT_DIR/proxmox-ui/utils/browser-actions.js"
node --check "$ROOT_DIR/extension/common.js"
node --check "$ROOT_DIR/extension/provider-registry.js"
node --check "$ROOT_DIR/extension/providers/proxmox.js"
node --check "$ROOT_DIR/extension/services/virtualization.js"
node --check "$ROOT_DIR/extension/services/platform.js"
node --check "$ROOT_DIR/extension/services/profile.js"
node --check "$ROOT_DIR/extension/content.js"
node --check "$ROOT_DIR/extension/options.js"
node --check "$ROOT_DIR/website/app.js"
node --check "$ROOT_DIR/beagle-kiosk/main.js"
node --check "$ROOT_DIR/beagle-kiosk/preload.js"
node --check "$ROOT_DIR/beagle-kiosk/renderer/kiosk.js"
node --check "$ROOT_DIR/beagle-kiosk/scripts/write-release-manifest.js"

python3 - "$ROOT_DIR/extension/manifest.json" "$VERSION" <<'PY'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = sys.argv[2]
manifest = json.loads(path.read_text())
if manifest.get("version") != version:
    raise SystemExit(f"extension manifest version mismatch: {manifest.get('version')} != {version}")
PY

rg -q "^## v${VERSION} -" "$ROOT_DIR/CHANGELOG.md"

if [[ "$RUN_PACKAGE" == "1" ]]; then
  "$ROOT_DIR/scripts/package.sh"
fi

if [[ -f "$ROOT_DIR/dist/beagle-extension-v${VERSION}.zip" ]]; then
  echo "OK  artifact dist/beagle-extension-v${VERSION}.zip"
fi

echo "Project validation completed successfully."
