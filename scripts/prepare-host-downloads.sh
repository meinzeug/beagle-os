#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIST_DIR="$ROOT_DIR/dist"
VERSION="$(tr -d ' \n\r' < "$ROOT_DIR/VERSION")"
SERVER_NAME="${PVE_DCV_PROXY_SERVER_NAME:-$(hostname -f 2>/dev/null || hostname)}"
LISTEN_PORT="${PVE_DCV_PROXY_LISTEN_PORT:-8443}"
DOWNLOADS_PATH="${PVE_DCV_DOWNLOADS_PATH:-/pve-dcv-downloads}"
BASE_URL="${PVE_DCV_DOWNLOADS_BASE_URL:-https://${SERVER_NAME}:${LISTEN_PORT}${DOWNLOADS_PATH}}"
HOST_INSTALLER_VERSIONED="$DIST_DIR/pve-thin-client-usb-installer-host-v${VERSION}.sh"
HOST_INSTALLER_LATEST="$DIST_DIR/pve-thin-client-usb-installer-host-latest.sh"
GENERIC_INSTALLER="$DIST_DIR/pve-thin-client-usb-installer-v${VERSION}.sh"
PAYLOAD_URL="${BASE_URL%/}/pve-thin-client-usb-payload-latest.tar.gz"
INSTALLER_URL="${BASE_URL%/}/pve-thin-client-usb-installer-host-latest.sh"
VM_INSTALLER_URL_TEMPLATE="${BASE_URL%/}/pve-thin-client-usb-installer-vm-{vmid}.sh"
STATUS_URL="${BASE_URL%/}/pve-dcv-downloads-status.json"
SHA256SUMS_URL="${BASE_URL%/}/SHA256SUMS"
STATUS_JSON_PATH="$DIST_DIR/pve-dcv-downloads-status.json"
VM_INSTALLERS_METADATA_PATH="$DIST_DIR/pve-dcv-vm-installers.json"
INSTALLER_SHA256=""
PAYLOAD_SHA256=""

[[ -f "$GENERIC_INSTALLER" ]] || {
  echo "Missing packaged USB installer: $GENERIC_INSTALLER" >&2
  exit 1
}

[[ -f "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" ]] || {
  echo "Missing packaged USB payload: $DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" >&2
  exit 1
}

rm -f "$DIST_DIR"/pve-thin-client-usb-installer-vm-*.sh "$VM_INSTALLERS_METADATA_PATH"
install -m 0755 "$GENERIC_INSTALLER" "$HOST_INSTALLER_VERSIONED"

python3 - "$HOST_INSTALLER_VERSIONED" "$PAYLOAD_URL" <<'PY'
import re
import sys
from pathlib import Path

path = Path(sys.argv[1])
payload_url = sys.argv[2]
text = path.read_text()
pattern = r'^RELEASE_PAYLOAD_URL="\$\{RELEASE_PAYLOAD_URL:-[^"]*}"$'
replacement = f'RELEASE_PAYLOAD_URL="${{RELEASE_PAYLOAD_URL:-{payload_url}}}"'
updated, count = re.subn(pattern, replacement, text, count=1, flags=re.MULTILINE)
if count != 1:
    raise SystemExit("failed to patch RELEASE_PAYLOAD_URL in hosted installer")
path.write_text(updated)
PY

install -m 0755 "$HOST_INSTALLER_VERSIONED" "$HOST_INSTALLER_LATEST"

python3 - "$HOST_INSTALLER_VERSIONED" "$DIST_DIR" "$VM_INSTALLERS_METADATA_PATH" "$SERVER_NAME" "$LISTEN_PORT" "$DOWNLOADS_PATH" "$VM_INSTALLER_URL_TEMPLATE" <<'PY'
import base64
import json
import re
import shlex
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

template_path = Path(sys.argv[1])
dist_dir = Path(sys.argv[2])
metadata_path = Path(sys.argv[3])
server_name = sys.argv[4]
listen_port = int(sys.argv[5])
downloads_path = sys.argv[6]
installer_url_template = sys.argv[7]
template = template_path.read_text()

resources_cmd = ["pvesh", "get", "/cluster/resources", "--type", "vm", "--output-format", "json"]


def run_json(command):
    try:
        result = subprocess.run(command, check=True, capture_output=True, text=True)
    except (FileNotFoundError, subprocess.CalledProcessError):
        return None
    try:
        return json.loads(result.stdout or "null")
    except json.JSONDecodeError:
        return None


def parse_description_meta(description):
    meta = {}
    text = str(description or "").replace("\\r\\n", "\n").replace("\\n", "\n")
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip().lower()
        value = value.strip()
        if key and key not in meta:
            meta[key] = value
    return meta


def safe_hostname(name, vmid):
    cleaned = re.sub(r"[^a-z0-9-]+", "-", str(name or "").strip().lower()).strip("-")
    if not cleaned:
        cleaned = f"pve-tc-{vmid}"
    return cleaned[:63].strip("-") or f"pve-tc-{vmid}"


def with_auth_token_and_session(url, auth_token, session_id):
    if not url:
        return ""
    parsed = urlparse(url if "://" in url else f"https://{url}")
    query = dict(parse_qsl(parsed.query, keep_blank_values=True))
    fragment = parsed.fragment
    if auth_token and not query.get("authToken"):
        query["authToken"] = auth_token
    if session_id and not fragment:
        fragment = session_id
    return urlunparse(parsed._replace(query=urlencode(query), fragment=fragment))


def patch_installer(text, preset_name, preset_b64):
    replacements = {
        'PVE_THIN_CLIENT_PRESET_NAME="${PVE_THIN_CLIENT_PRESET_NAME:-}"': f'PVE_THIN_CLIENT_PRESET_NAME="${{PVE_THIN_CLIENT_PRESET_NAME:-{preset_name}}}"',
        'PVE_THIN_CLIENT_PRESET_B64="${PVE_THIN_CLIENT_PRESET_B64:-}"': f'PVE_THIN_CLIENT_PRESET_B64="${{PVE_THIN_CLIENT_PRESET_B64:-{preset_b64}}}"',
    }
    patched = text
    for old, new in replacements.items():
        if old not in patched:
            raise SystemExit(f"unable to locate preset placeholder: {old}")
        patched = patched.replace(old, new, 1)
    return patched


def shell_line(key, value):
    return f"{key}={shlex.quote(str(value))}\n"


def build_preset(vm, config):
    meta = parse_description_meta(config.get("description", ""))
    vmid = int(vm["vmid"])
    vm_name = config.get("name") or vm.get("name") or f"vm-{vmid}"
    proxmox_scheme = meta.get("proxmox-scheme", "https")
    proxmox_host = meta.get("proxmox-host", server_name)
    proxmox_port = meta.get("proxmox-port", "8006")
    proxmox_realm = meta.get("proxmox-realm", "pam")
    proxmox_verify_tls = meta.get("proxmox-verify-tls", "0")
    proxmox_username = meta.get("proxmox-user", "")
    proxmox_password = meta.get("proxmox-password", "")
    proxmox_token = meta.get("proxmox-token", "")

    dcv_host = meta.get("dcv-host") or meta.get("dcv-ip") or ""
    dcv_url = meta.get("dcv-url") or (f"https://{dcv_host}:{listen_port}/" if dcv_host else "")
    dcv_url = with_auth_token_and_session(dcv_url, meta.get("dcv-auth-token", ""), meta.get("dcv-session", ""))
    moonlight_host = meta.get("moonlight-host") or meta.get("sunshine-host") or meta.get("sunshine-ip") or dcv_host
    sunshine_api_url = meta.get("sunshine-api-url") or (f"https://{moonlight_host}:47990" if moonlight_host else "")
    moonlight_default_mode = meta.get("thinclient-default-mode", "MOONLIGHT" if moonlight_host else "")

    spice_url = meta.get("spice-url", "")
    novnc_url = meta.get("novnc-url", "")
    spice_method = meta.get("spice-method", "direct" if spice_url else "proxmox-ticket")

    preset = {
        "PVE_THIN_CLIENT_PRESET_PROFILE_NAME": f"vm-{vmid}",
        "PVE_THIN_CLIENT_PRESET_VM_NAME": vm_name,
        "PVE_THIN_CLIENT_PRESET_HOSTNAME_VALUE": safe_hostname(vm_name, vmid),
        "PVE_THIN_CLIENT_PRESET_AUTOSTART": meta.get("thinclient-autostart", "1"),
        "PVE_THIN_CLIENT_PRESET_DEFAULT_MODE": moonlight_default_mode,
        "PVE_THIN_CLIENT_PRESET_NETWORK_MODE": meta.get("thinclient-network-mode", "dhcp"),
        "PVE_THIN_CLIENT_PRESET_NETWORK_INTERFACE": meta.get("thinclient-network-interface", "eth0"),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_SCHEME": proxmox_scheme,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_HOST": proxmox_host,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PORT": proxmox_port,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_NODE": vm.get("node", ""),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VMID": str(vmid),
        "PVE_THIN_CLIENT_PRESET_PROXMOX_REALM": proxmox_realm,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_VERIFY_TLS": proxmox_verify_tls,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_USERNAME": proxmox_username,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_PASSWORD": proxmox_password,
        "PVE_THIN_CLIENT_PRESET_PROXMOX_TOKEN": proxmox_token,
        "PVE_THIN_CLIENT_PRESET_SPICE_METHOD": spice_method,
        "PVE_THIN_CLIENT_PRESET_SPICE_URL": spice_url,
        "PVE_THIN_CLIENT_PRESET_SPICE_USERNAME": meta.get("spice-user", proxmox_username),
        "PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD": meta.get("spice-password", proxmox_password),
        "PVE_THIN_CLIENT_PRESET_SPICE_TOKEN": meta.get("spice-token", proxmox_token),
        "PVE_THIN_CLIENT_PRESET_NOVNC_URL": novnc_url,
        "PVE_THIN_CLIENT_PRESET_NOVNC_USERNAME": meta.get("novnc-user", proxmox_username),
        "PVE_THIN_CLIENT_PRESET_NOVNC_PASSWORD": meta.get("novnc-password", proxmox_password),
        "PVE_THIN_CLIENT_PRESET_NOVNC_TOKEN": meta.get("novnc-token", proxmox_token),
        "PVE_THIN_CLIENT_PRESET_DCV_URL": dcv_url,
        "PVE_THIN_CLIENT_PRESET_DCV_USERNAME": meta.get("dcv-user", ""),
        "PVE_THIN_CLIENT_PRESET_DCV_PASSWORD": meta.get("dcv-password", ""),
        "PVE_THIN_CLIENT_PRESET_DCV_TOKEN": meta.get("dcv-auth-token", ""),
        "PVE_THIN_CLIENT_PRESET_DCV_SESSION": meta.get("dcv-session", ""),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST": moonlight_host,
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_APP": meta.get("moonlight-app", meta.get("sunshine-app", "Desktop")),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BIN": meta.get("moonlight-bin", "moonlight"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_RESOLUTION": meta.get("moonlight-resolution", "1080"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_FPS": meta.get("moonlight-fps", "60"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_BITRATE": meta.get("moonlight-bitrate", "20000"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_CODEC": meta.get("moonlight-video-codec", "H.264"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_VIDEO_DECODER": meta.get("moonlight-video-decoder", "auto"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_AUDIO_CONFIG": meta.get("moonlight-audio-config", "stereo"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_ABSOLUTE_MOUSE": meta.get("moonlight-absolute-mouse", "1"),
        "PVE_THIN_CLIENT_PRESET_MOONLIGHT_QUIT_AFTER": meta.get("moonlight-quit-after", "0"),
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_API_URL": sunshine_api_url,
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_USERNAME": meta.get("sunshine-user", ""),
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PASSWORD": meta.get("sunshine-password", ""),
        "PVE_THIN_CLIENT_PRESET_SUNSHINE_PIN": meta.get("sunshine-pin", f"{vmid % 10000:04d}"),
    }

    available_modes = []
    if preset["PVE_THIN_CLIENT_PRESET_MOONLIGHT_HOST"]:
        available_modes.append("MOONLIGHT")
    if preset["PVE_THIN_CLIENT_PRESET_SPICE_URL"] or (
        preset["PVE_THIN_CLIENT_PRESET_PROXMOX_HOST"]
        and preset["PVE_THIN_CLIENT_PRESET_PROXMOX_NODE"]
        and preset["PVE_THIN_CLIENT_PRESET_PROXMOX_VMID"]
        and preset["PVE_THIN_CLIENT_PRESET_SPICE_USERNAME"]
        and preset["PVE_THIN_CLIENT_PRESET_SPICE_PASSWORD"]
    ):
        available_modes.append("SPICE")
    if preset["PVE_THIN_CLIENT_PRESET_NOVNC_URL"]:
        available_modes.append("NOVNC")
    if preset["PVE_THIN_CLIENT_PRESET_DCV_URL"]:
        available_modes.append("DCV")

    return preset, available_modes


resources = run_json(resources_cmd)
vm_installers = []

if not resources:
    metadata_path.write_text("[]\n")
    raise SystemExit(0)

for vm in resources:
    if vm.get("type") != "qemu" or vm.get("vmid") is None or not vm.get("node"):
        continue

    config = run_json(
        [
            "pvesh",
            "get",
            f"/nodes/{vm['node']}/qemu/{vm['vmid']}/config",
            "--output-format",
            "json",
        ]
    ) or {}
    preset, available_modes = build_preset(vm, config)
    preset_name = f"vm-{vm['vmid']}"
    preset_text = "".join(shell_line(key, value) for key, value in preset.items())
    preset_b64 = base64.b64encode(preset_text.encode("utf-8")).decode("ascii")
    installer_name = f"pve-thin-client-usb-installer-vm-{vm['vmid']}.sh"
    installer_path = dist_dir / installer_name
    installer_path.write_text(patch_installer(template, preset_name, preset_b64))
    installer_path.chmod(0o755)
    vm_installers.append(
        {
            "vmid": int(vm["vmid"]),
            "node": vm["node"],
            "name": preset["PVE_THIN_CLIENT_PRESET_VM_NAME"],
            "installer_filename": installer_name,
            "installer_url": installer_url_template.replace("{vmid}", str(vm["vmid"])),
            "available_modes": available_modes,
        }
    )

metadata_path.write_text(json.dumps(sorted(vm_installers, key=lambda item: item["vmid"]), indent=2) + "\n")
PY

INSTALLER_SHA256="$(sha256sum "$HOST_INSTALLER_LATEST" | awk '{print $1}')"
PAYLOAD_SHA256="$(sha256sum "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" | awk '{print $1}')"

cat > "$DIST_DIR/pve-dcv-downloads-index.html" <<EOF
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>PVE DCV Integration Downloads</title>
  <style>
    body { font-family: sans-serif; margin: 2rem auto; max-width: 60rem; line-height: 1.5; padding: 0 1rem; }
    code { background: #f4f4f4; padding: 0.15rem 0.3rem; border-radius: 0.25rem; }
    table { border-collapse: collapse; width: 100%; margin-top: 1rem; }
    th, td { border-bottom: 1px solid #ddd; padding: 0.55rem; text-align: left; vertical-align: top; }
    th { width: 18rem; }
  </style>
</head>
<body>
  <h1>PVE DCV Integration Downloads</h1>
  <p>Host-local thin-client media downloads for this Proxmox server.</p>
  <ul>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-usb-installer-host-latest.sh">Generic USB installer launcher</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/pve-thin-client-usb-payload-latest.tar.gz">USB payload bundle</a></li>
    <li>VM-specific USB installers are generated as <code>pve-thin-client-usb-installer-vm-&lt;vmid&gt;.sh</code> and linked from the Proxmox VM toolbar.</li>
    <li><a href="${DOWNLOADS_PATH%/}/pve-dcv-downloads-status.json">Status JSON</a></li>
    <li><a href="${DOWNLOADS_PATH%/}/SHA256SUMS">SHA256SUMS</a></li>
  </ul>
  <p>The hosted USB installers are preconfigured to download their large payload from this same Proxmox host instead of GitHub. VM-specific variants also embed the chosen VM connection profile directly into the USB stick, including Moonlight plus Sunshine pairing defaults where configured.</p>
  <table>
    <tr><th>Release version</th><td><code>${VERSION}</code></td></tr>
    <tr><th>Server</th><td><code>${SERVER_NAME}:${LISTEN_PORT}</code></td></tr>
    <tr><th>VM installer template</th><td><code>${VM_INSTALLER_URL_TEMPLATE}</code></td></tr>
    <tr><th>Status JSON</th><td><a href="${DOWNLOADS_PATH%/}/pve-dcv-downloads-status.json">${STATUS_URL}</a></td></tr>
    <tr><th>SHA256SUMS</th><td><a href="${DOWNLOADS_PATH%/}/SHA256SUMS">${SHA256SUMS_URL}</a></td></tr>
    <tr><th>Hosted installer SHA256</th><td><code>${INSTALLER_SHA256}</code></td></tr>
    <tr><th>Payload SHA256</th><td><code>${PAYLOAD_SHA256}</code></td></tr>
  </table>
</body>
</html>
EOF

python3 - "$STATUS_JSON_PATH" "$VERSION" "$SERVER_NAME" "$LISTEN_PORT" "$DOWNLOADS_PATH" "$INSTALLER_URL" "$PAYLOAD_URL" "$STATUS_URL" "$SHA256SUMS_URL" "$HOST_INSTALLER_LATEST" "$DIST_DIR/pve-thin-client-usb-payload-latest.tar.gz" "$INSTALLER_SHA256" "$PAYLOAD_SHA256" "$VM_INSTALLER_URL_TEMPLATE" "$VM_INSTALLERS_METADATA_PATH" <<'PY'
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

status_path = Path(sys.argv[1])
version = sys.argv[2]
server_name = sys.argv[3]
listen_port = int(sys.argv[4])
downloads_path = sys.argv[5]
installer_url = sys.argv[6]
payload_url = sys.argv[7]
status_url = sys.argv[8]
sha256sums_url = sys.argv[9]
installer_path = Path(sys.argv[10])
payload_path = Path(sys.argv[11])
installer_sha256 = sys.argv[12]
payload_sha256 = sys.argv[13]
vm_installer_url_template = sys.argv[14]
vm_installers_path = Path(sys.argv[15])
vm_installers = json.loads(vm_installers_path.read_text()) if vm_installers_path.exists() else []

payload = {
    "version": version,
    "generated_at": datetime.now(timezone.utc).isoformat(),
    "server_name": server_name,
    "listen_port": listen_port,
    "downloads_path": downloads_path,
    "installer_url": installer_url,
    "payload_url": payload_url,
    "status_url": status_url,
    "sha256sums_url": sha256sums_url,
    "installer_size": installer_path.stat().st_size,
    "payload_size": payload_path.stat().st_size,
    "installer_sha256": installer_sha256,
    "payload_sha256": payload_sha256,
    "installer_filename": installer_path.name,
    "payload_filename": payload_path.name,
    "vm_installer_url_template": vm_installer_url_template,
    "vm_installer_count": len(vm_installers),
    "vm_installers": vm_installers,
}
status_path.write_text(json.dumps(payload, indent=2) + "\n")
PY

echo "Prepared host-local download artifacts under $DIST_DIR"
echo "Hosted USB installer URL: $INSTALLER_URL"
