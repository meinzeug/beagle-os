#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PVE_DIR="/usr/share/pve-manager"
CONFIG_TARGET="$PVE_DIR/js/beagle-ui-config.js"
COMMON_TARGET="$PVE_DIR/js/beagle-ui-common.js"
PROVIDER_REGISTRY_TARGET="$PVE_DIR/js/beagle-provider-registry.js"
VIRTUALIZATION_SERVICE_TARGET="$PVE_DIR/js/beagle-virtualization-service.js"
PLATFORM_SERVICE_TARGET="$PVE_DIR/js/beagle-platform-service.js"
PROXMOX_PROVIDER_TARGET="$PVE_DIR/js/beagle-proxmox-provider.js"
API_CLIENT_TARGET="$PVE_DIR/js/beagle-ui-api-client.js"
STATE_TARGET="$PVE_DIR/js/beagle-ui-installer-state.js"
FLEET_STATE_TARGET="$PVE_DIR/js/beagle-ui-fleet-state.js"
VM_PROFILE_STATE_TARGET="$PVE_DIR/js/beagle-ui-vm-profile-state.js"
PROVISIONING_API_TARGET="$PVE_DIR/js/beagle-ui-provisioning-api.js"
PROVISIONING_FLOW_TARGET="$PVE_DIR/js/beagle-ui-provisioning-flow.js"
USB_API_TARGET="$PVE_DIR/js/beagle-ui-usb-api.js"
USB_UI_TARGET="$PVE_DIR/js/beagle-ui-usb-ui.js"
SHARED_VM_PROFILE_MAPPER_TARGET="$PVE_DIR/js/beagle-browser-vm-profile-mapper.js"
SHARED_VM_PROFILE_HELPERS_TARGET="$PVE_DIR/js/beagle-browser-vm-profile-helpers.js"
COMPONENTS_UI_HELPERS_TARGET="$PVE_DIR/js/beagle-ui-render-helpers.js"
COMPONENTS_MODAL_SHELL_TARGET="$PVE_DIR/js/beagle-ui-modal-shell.js"
COMPONENTS_DESKTOP_OVERLAY_TARGET="$PVE_DIR/js/beagle-ui-desktop-overlay.js"
COMPONENTS_PROFILE_MODAL_TARGET="$PVE_DIR/js/beagle-ui-profile-modal.js"
COMPONENTS_FLEET_MODAL_TARGET="$PVE_DIR/js/beagle-ui-fleet-modal.js"
COMPONENTS_EXTJS_INTEGRATION_TARGET="$PVE_DIR/js/beagle-ui-extjs-integration.js"
COMPONENTS_PROVISIONING_RESULT_MODAL_TARGET="$PVE_DIR/js/beagle-ui-provisioning-result-modal.js"
COMPONENTS_PROVISIONING_CREATE_MODAL_TARGET="$PVE_DIR/js/beagle-ui-provisioning-create-modal.js"
UTILS_BROWSER_ACTIONS_TARGET="$PVE_DIR/js/beagle-ui-browser-actions.js"
JS_TARGET="$PVE_DIR/js/beagle-ui.js"
TPL_TARGET="$PVE_DIR/index.html.tpl"
TPL_BACKUP="$PVE_DIR/index.html.tpl.beagle.bak"
BEAGLE_MANAGER_ENV_FILE="${PVE_DCV_CONFIG_DIR:-/etc/beagle}/beagle-manager.env"
PROJECT_VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION" 2>/dev/null || echo dev)"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/beagle-downloads}"
DEFAULT_USB_INSTALLER_URL="https://{host}:${LISTEN_PORT}/beagle-api/api/v1/vms/{vmid}/installer.sh"
USB_INSTALLER_URL="${PVE_DCV_USB_INSTALLER_URL:-$DEFAULT_USB_INSTALLER_URL}"
DEFAULT_INSTALLER_ISO_URL="https://{host}:${LISTEN_PORT}${DOWNLOADS_PATH}/beagle-os-installer-amd64.iso"
INSTALLER_ISO_URL="${PVE_DCV_INSTALLER_ISO_URL:-$DEFAULT_INSTALLER_ISO_URL}"
DEFAULT_CONTROL_PLANE_HEALTH_URL="https://{host}:${LISTEN_PORT}/beagle-api/api/v1/health"
CONTROL_PLANE_HEALTH_URL="${BEAGLE_CONTROL_PLANE_HEALTH_URL:-$DEFAULT_CONTROL_PLANE_HEALTH_URL}"
DEFAULT_WEB_UI_URL="https://{host}"
WEB_UI_URL="${BEAGLE_WEB_UI_URL:-$DEFAULT_WEB_UI_URL}"
BEAGLE_API_TOKEN="${BEAGLE_MANAGER_API_TOKEN:-}"
BEAGLE_PVE_UI_EMBED_API_TOKEN="${BEAGLE_PVE_UI_EMBED_API_TOKEN:-1}"
CONFIG_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-config.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMMON_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-common.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
PROVIDER_REGISTRY_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-provider-registry.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
VIRTUALIZATION_SERVICE_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-virtualization-service.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
PLATFORM_SERVICE_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-platform-service.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
PROXMOX_PROVIDER_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-proxmox-provider.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
API_CLIENT_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-api-client.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
STATE_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-installer-state.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
FLEET_STATE_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-fleet-state.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
VM_PROFILE_STATE_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-vm-profile-state.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
PROVISIONING_API_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-provisioning-api.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
PROVISIONING_FLOW_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-provisioning-flow.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
USB_API_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-usb-api.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
USB_UI_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-usb-ui.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
SHARED_VM_PROFILE_MAPPER_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-browser-vm-profile-mapper.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
SHARED_VM_PROFILE_HELPERS_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-browser-vm-profile-helpers.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_UI_HELPERS_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-render-helpers.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_MODAL_SHELL_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-modal-shell.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_DESKTOP_OVERLAY_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-desktop-overlay.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_PROFILE_MODAL_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-profile-modal.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_FLEET_MODAL_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-fleet-modal.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_EXTJS_INTEGRATION_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-extjs-integration.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_PROVISIONING_RESULT_MODAL_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-provisioning-result-modal.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
COMPONENTS_PROVISIONING_CREATE_MODAL_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-provisioning-create-modal.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
UTILS_BROWSER_ACTIONS_INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui-browser-actions.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"
INCLUDE_LINE="    <script type=\"text/javascript\" src=\"/pve2/js/beagle-ui.js?ver=[% version %]-beagle-${PROJECT_VERSION}\"></script>"

ensure_root() {
  if [[ "${EUID}" -eq 0 ]]; then
    return 0
  fi

  if command -v sudo >/dev/null 2>&1; then
    exec sudo "$0" "$@"
  fi

  echo "This installer must run as root or use sudo." >&2
  exit 1
}

ensure_root "$@"

if [[ -z "$BEAGLE_API_TOKEN" && -f "$BEAGLE_MANAGER_ENV_FILE" ]]; then
  # shellcheck disable=SC1090
  source "$BEAGLE_MANAGER_ENV_FILE"
  BEAGLE_API_TOKEN="${BEAGLE_MANAGER_API_TOKEN:-}"
fi

if [[ "$BEAGLE_PVE_UI_EMBED_API_TOKEN" != "1" ]]; then
  BEAGLE_API_TOKEN=""
fi

if [[ ! -d "$PVE_DIR/js" || ! -f "$TPL_TARGET" ]]; then
  echo "Proxmox UI files not found under $PVE_DIR" >&2
  exit 1
fi

install -D -m 0644 "$ROOT_DIR/proxmox-ui/beagle-ui.js" "$JS_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/beagle-ui-common.js" "$COMMON_TARGET"
install -D -m 0644 "$ROOT_DIR/core/provider/registry.js" "$PROVIDER_REGISTRY_TARGET"
install -D -m 0644 "$ROOT_DIR/core/virtualization/service.js" "$VIRTUALIZATION_SERVICE_TARGET"
install -D -m 0644 "$ROOT_DIR/core/platform/service.js" "$PLATFORM_SERVICE_TARGET"
install -D -m 0644 "$ROOT_DIR/providers/proxmox/virtualization-provider.js" "$PROXMOX_PROVIDER_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/api-client/beagle-api.js" "$API_CLIENT_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/state/installer-eligibility.js" "$STATE_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/state/fleet.js" "$FLEET_STATE_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/state/vm-profile.js" "$VM_PROFILE_STATE_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/provisioning/api.js" "$PROVISIONING_API_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/provisioning/flow.js" "$PROVISIONING_FLOW_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/usb/api.js" "$USB_API_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/usb/ui.js" "$USB_UI_TARGET"
install -D -m 0644 "$ROOT_DIR/extension/shared/vm-profile-mapper.js" "$SHARED_VM_PROFILE_MAPPER_TARGET"
install -D -m 0644 "$ROOT_DIR/extension/shared/vm-profile-helpers.js" "$SHARED_VM_PROFILE_HELPERS_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/ui-helpers.js" "$COMPONENTS_UI_HELPERS_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/modal-shell.js" "$COMPONENTS_MODAL_SHELL_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/desktop-overlay.js" "$COMPONENTS_DESKTOP_OVERLAY_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/profile-modal.js" "$COMPONENTS_PROFILE_MODAL_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/fleet-modal.js" "$COMPONENTS_FLEET_MODAL_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/extjs-integration.js" "$COMPONENTS_EXTJS_INTEGRATION_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/provisioning-result-modal.js" "$COMPONENTS_PROVISIONING_RESULT_MODAL_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/components/provisioning-create-modal.js" "$COMPONENTS_PROVISIONING_CREATE_MODAL_TARGET"
install -D -m 0644 "$ROOT_DIR/proxmox-ui/utils/browser-actions.js" "$UTILS_BROWSER_ACTIONS_TARGET"
cat > "$CONFIG_TARGET" <<EOF
window.BeagleIntegrationConfig = Object.assign({}, window.BeagleIntegrationConfig || {}, {
  usbInstallerUrl: ${USB_INSTALLER_URL@Q},
  installerIsoUrl: ${INSTALLER_ISO_URL@Q},
  controlPlaneHealthUrl: ${CONTROL_PLANE_HEALTH_URL@Q},
  webUiUrl: ${WEB_UI_URL@Q},
  apiToken: ${BEAGLE_API_TOKEN@Q}
});
EOF

if [[ ! -f "$TPL_BACKUP" ]]; then
  cp "$TPL_TARGET" "$TPL_BACKUP"
fi

python3 - "$TPL_TARGET" "$CONFIG_INCLUDE_LINE" "$COMMON_INCLUDE_LINE" "$PROVIDER_REGISTRY_INCLUDE_LINE" "$API_CLIENT_INCLUDE_LINE" "$PROVISIONING_API_INCLUDE_LINE" "$PROVISIONING_FLOW_INCLUDE_LINE" "$USB_API_INCLUDE_LINE" "$PROXMOX_PROVIDER_INCLUDE_LINE" "$VIRTUALIZATION_SERVICE_INCLUDE_LINE" "$PLATFORM_SERVICE_INCLUDE_LINE" "$STATE_INCLUDE_LINE" "$FLEET_STATE_INCLUDE_LINE" "$VM_PROFILE_STATE_INCLUDE_LINE" "$USB_UI_INCLUDE_LINE" "$SHARED_VM_PROFILE_MAPPER_INCLUDE_LINE" "$SHARED_VM_PROFILE_HELPERS_INCLUDE_LINE" "$COMPONENTS_UI_HELPERS_INCLUDE_LINE" "$COMPONENTS_MODAL_SHELL_INCLUDE_LINE" "$COMPONENTS_DESKTOP_OVERLAY_INCLUDE_LINE" "$COMPONENTS_PROFILE_MODAL_INCLUDE_LINE" "$COMPONENTS_FLEET_MODAL_INCLUDE_LINE" "$COMPONENTS_EXTJS_INTEGRATION_INCLUDE_LINE" "$COMPONENTS_PROVISIONING_RESULT_MODAL_INCLUDE_LINE" "$COMPONENTS_PROVISIONING_CREATE_MODAL_INCLUDE_LINE" "$UTILS_BROWSER_ACTIONS_INCLUDE_LINE" "$INCLUDE_LINE" <<'PY'
import sys
from pathlib import Path

path = Path(sys.argv[1])
config_include = sys.argv[2]
common_include = sys.argv[3]
provider_registry_include = sys.argv[4]
api_client_include = sys.argv[5]
provisioning_api_include = sys.argv[6]
provisioning_flow_include = sys.argv[7]
usb_api_include = sys.argv[8]
proxmox_provider_include = sys.argv[9]
virtualization_service_include = sys.argv[10]
platform_service_include = sys.argv[11]
state_include = sys.argv[12]
fleet_state_include = sys.argv[13]
vm_profile_state_include = sys.argv[14]
usb_ui_include = sys.argv[15]
shared_vm_profile_mapper_include = sys.argv[16]
shared_vm_profile_helpers_include = sys.argv[17]
components_ui_helpers_include = sys.argv[18]
components_modal_shell_include = sys.argv[19]
components_desktop_overlay_include = sys.argv[20]
components_profile_modal_include = sys.argv[21]
components_fleet_modal_include = sys.argv[22]
components_extjs_integration_include = sys.argv[23]
components_provisioning_result_modal_include = sys.argv[24]
components_provisioning_create_modal_include = sys.argv[25]
utils_browser_actions_include = sys.argv[26]
include = sys.argv[27]
text = path.read_text()
needle = '    <script type="text/javascript" src="/pve2/js/pvemanagerlib.js?ver=[% version %]"></script>\n'
if needle not in text:
    raise SystemExit("needle not found in index.html.tpl")
lines = []
for line in text.splitlines():
    if '/pve2/js/beagle-ui.js' in line or '/pve2/js/beagle-ui-common.js' in line or '/pve2/js/beagle-provider-registry.js' in line or '/pve2/js/beagle-virtualization-service.js' in line or '/pve2/js/beagle-platform-service.js' in line or '/pve2/js/beagle-proxmox-provider.js' in line or '/pve2/js/beagle-ui-api-client.js' in line or '/pve2/js/beagle-ui-installer-state.js' in line or '/pve2/js/beagle-ui-fleet-state.js' in line or '/pve2/js/beagle-ui-vm-profile-state.js' in line or '/pve2/js/beagle-ui-provisioning-api.js' in line or '/pve2/js/beagle-ui-provisioning-flow.js' in line or '/pve2/js/beagle-ui-usb-api.js' in line or '/pve2/js/beagle-ui-usb-ui.js' in line or '/pve2/js/beagle-browser-vm-profile-mapper.js' in line or '/pve2/js/beagle-browser-vm-profile-helpers.js' in line or '/pve2/js/beagle-ui-render-helpers.js' in line or '/pve2/js/beagle-ui-modal-shell.js' in line or '/pve2/js/beagle-ui-desktop-overlay.js' in line or '/pve2/js/beagle-ui-profile-modal.js' in line or '/pve2/js/beagle-ui-fleet-modal.js' in line or '/pve2/js/beagle-ui-extjs-integration.js' in line or '/pve2/js/beagle-ui-provisioning-result-modal.js' in line or '/pve2/js/beagle-ui-provisioning-create-modal.js' in line or '/pve2/js/beagle-ui-browser-actions.js' in line or '/pve2/js/beagle-ui-config.js' in line or '/pve2/js/pve-dcv-integration.js' in line or '/pve2/js/pve-dcv-integration-config.js' in line:
        continue
    lines.append(line)
text = "\n".join(lines) + "\n"
text = text.replace(needle, needle + config_include + "\n" + common_include + "\n" + provider_registry_include + "\n" + api_client_include + "\n" + provisioning_api_include + "\n" + usb_api_include + "\n" + proxmox_provider_include + "\n" + virtualization_service_include + "\n" + platform_service_include + "\n" + state_include + "\n" + fleet_state_include + "\n" + usb_ui_include + "\n" + shared_vm_profile_mapper_include + "\n" + shared_vm_profile_helpers_include + "\n" + components_ui_helpers_include + "\n" + components_modal_shell_include + "\n" + components_profile_modal_include + "\n" + vm_profile_state_include + "\n" + components_desktop_overlay_include + "\n" + components_fleet_modal_include + "\n" + components_extjs_integration_include + "\n" + components_provisioning_result_modal_include + "\n" + components_provisioning_create_modal_include + "\n" + provisioning_flow_include + "\n" + utils_browser_actions_include + "\n" + include + "\n", 1)
path.write_text(text)
PY

systemctl restart pveproxy
echo "Installed Proxmox UI integration to $JS_TARGET"
