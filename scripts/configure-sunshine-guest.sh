#!/usr/bin/env bash
set -euo pipefail

PROXMOX_HOST="${PROXMOX_HOST:-thinovernet}"
VMID="${VMID:-}"
GUEST_USER="${GUEST_USER:-dennis}"
PROXMOX_USER="${PROXMOX_USER:-}"
PROXMOX_PASSWORD="${PROXMOX_PASSWORD:-}"
PROXMOX_TOKEN="${PROXMOX_TOKEN:-}"
SUNSHINE_USER="${SUNSHINE_USER:-sunshine}"
SUNSHINE_PASSWORD="${SUNSHINE_PASSWORD:-}"
SUNSHINE_PIN="${SUNSHINE_PIN:-}"
SUNSHINE_PORT="${SUNSHINE_PORT:-}"
SUNSHINE_URL="${SUNSHINE_URL:-https://github.com/LizardByte/Sunshine/releases/download/v2025.924.154138/sunshine-ubuntu-24.04-amd64.deb}"
SUNSHINE_ORIGIN_WEB_UI_ALLOWED="${SUNSHINE_ORIGIN_WEB_UI_ALLOWED:-wan}"
PUBLIC_STREAM_HOST="${PUBLIC_STREAM_HOST:-}"
UPDATE_METADATA="${UPDATE_METADATA:-1}"
VM_REBOOT="${VM_REBOOT:-1}"

usage() {
  cat <<EOF
Usage: $0 --vmid VMID [--proxmox-host HOST] [--guest-user USER] [--proxmox-user USER@REALM] [--proxmox-password PASS|--proxmox-token TOKEN] [--sunshine-user USER] --sunshine-password PASS [--sunshine-pin PIN] [--sunshine-port PORT] [--public-stream-host HOST]
EOF
}

require_tool() {
  local tool="$1"
  command -v "$tool" >/dev/null 2>&1 || {
    echo "Missing required tool: $tool" >&2
    exit 1
  }
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --proxmox-host) PROXMOX_HOST="$2"; shift 2 ;;
      --vmid) VMID="$2"; shift 2 ;;
      --guest-user) GUEST_USER="$2"; shift 2 ;;
      --proxmox-user) PROXMOX_USER="$2"; shift 2 ;;
      --proxmox-password) PROXMOX_PASSWORD="$2"; shift 2 ;;
      --proxmox-token) PROXMOX_TOKEN="$2"; shift 2 ;;
      --sunshine-user) SUNSHINE_USER="$2"; shift 2 ;;
      --sunshine-password) SUNSHINE_PASSWORD="$2"; shift 2 ;;
      --sunshine-pin) SUNSHINE_PIN="$2"; shift 2 ;;
      --sunshine-port) SUNSHINE_PORT="$2"; shift 2 ;;
      --sunshine-url) SUNSHINE_URL="$2"; shift 2 ;;
      --sunshine-origin-web-ui-allowed) SUNSHINE_ORIGIN_WEB_UI_ALLOWED="$2"; shift 2 ;;
      --public-stream-host) PUBLIC_STREAM_HOST="$2"; shift 2 ;;
      --no-metadata) UPDATE_METADATA="0"; shift ;;
      --no-reboot) VM_REBOOT="0"; shift ;;
      -h|--help) usage; exit 0 ;;
      *)
        echo "Unknown argument: $1" >&2
        usage
        exit 1
        ;;
    esac
  done
}

ssh_host() {
  local target="${PROXMOX_HOST:-}"
  case "$target" in
    localhost|127.0.0.1|::1|"$(hostname)"|"$(hostname -f 2>/dev/null || hostname)")
      bash -lc "$*"
      ;;
    *)
      ssh "$target" "$@"
      ;;
  esac
}

guest_exec_script() {
  local script="$1"
  local script_b64
  script_b64="$(printf '%s' "$script" | base64 -w0)"

  ssh_host "sudo /usr/sbin/qm guest exec '$VMID' -- bash -lc 'echo $script_b64 | base64 -d >/tmp/pve-sunshine-setup.sh && chmod +x /tmp/pve-sunshine-setup.sh && /tmp/pve-sunshine-setup.sh'"
}

detect_guest_ip() {
  local raw_output
  raw_output="$(ssh_host "sudo /usr/sbin/qm guest exec '$VMID' -- bash -lc 'hostname -I | tr \" \" \"\\n\" | sed \"/^$/d\" | head -n1'")"
  python3 - "$raw_output" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
if not raw:
    raise SystemExit(1)

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    print(raw.splitlines()[-1].strip())
    raise SystemExit(0)

out = str(payload.get("out-data", "")).strip()
if out:
    print(out.splitlines()[-1].strip())
PY
}

update_vm_metadata() {
  local guest_ip="$1"
  local stream_host="${PUBLIC_STREAM_HOST:-$guest_ip}"
  local stream_port="${SUNSHINE_PORT:-}"
  local stream_api_url=""
  local encoded_desc new_desc_b64
  if [[ -n "$stream_port" ]]; then
    stream_api_url="https://${stream_host}:$((stream_port + 1))"
  else
    stream_api_url="https://${stream_host}:47990"
  fi
  encoded_desc="$(
    ssh_host "sudo /usr/sbin/qm config '$VMID'" | sed -n 's/^description: //p'
  )"

  new_desc_b64="$(
    python3 - "$encoded_desc" "$guest_ip" "$stream_host" "$stream_port" "$stream_api_url" "$SUNSHINE_USER" "$SUNSHINE_PASSWORD" "$SUNSHINE_PIN" "$PROXMOX_USER" "$PROXMOX_PASSWORD" "$PROXMOX_TOKEN" <<'PY'
import base64
import sys
from urllib.parse import unquote

encoded, guest_ip, stream_host, stream_port, stream_api_url, sunshine_user, sunshine_password, sunshine_pin, proxmox_user, proxmox_password, proxmox_token = sys.argv[1:12]
skip = {
    "sunshine-host",
    "sunshine-ip",
    "sunshine-api-url",
    "beagle-public-stream-host",
    "beagle-public-moonlight-port",
    "beagle-public-sunshine-api-url",
    "sunshine-user",
    "sunshine-password",
    "sunshine-pin",
    "sunshine-app",
    "moonlight-host",
    "moonlight-port",
    "moonlight-app",
    "moonlight-resolution",
    "moonlight-fps",
    "moonlight-bitrate",
    "moonlight-video-codec",
    "moonlight-video-decoder",
    "moonlight-audio-config",
    "thinclient-default-mode",
    "proxmox-user",
    "proxmox-password",
    "proxmox-token",
}

text = unquote(encoded) if encoded else ""
lines = []
for raw_line in text.splitlines():
    line = raw_line.strip()
    if ":" in line:
        key = line.split(":", 1)[0].strip().lower()
        if key in skip:
            continue
    if line:
        lines.append(raw_line)

lines.extend(
    [
        f"proxmox-user: {proxmox_user}",
        f"proxmox-password: {proxmox_password}",
        f"proxmox-token: {proxmox_token}",
        f"sunshine-host: {stream_host}",
        f"sunshine-ip: {guest_ip}",
        f"sunshine-api-url: {stream_api_url}",
        f"sunshine-user: {sunshine_user}",
        f"sunshine-password: {sunshine_password}",
        f"sunshine-pin: {sunshine_pin}",
        "sunshine-app: Desktop",
        f"moonlight-host: {stream_host}",
        f"moonlight-port: {stream_port}",
        "moonlight-app: Desktop",
        "moonlight-resolution: auto",
        "moonlight-fps: 60",
        "moonlight-bitrate: 20000",
        "moonlight-video-codec: H.264",
        "moonlight-video-decoder: auto",
        "moonlight-audio-config: stereo",
        "thinclient-default-mode: MOONLIGHT",
    ]
)
if stream_port:
    lines.extend(
        [
            f"beagle-public-stream-host: {stream_host}",
            f"beagle-public-moonlight-port: {stream_port}",
            f"beagle-public-sunshine-api-url: {stream_api_url}",
        ]
    )

payload = "\n".join(lines).strip() + "\n"
print(base64.b64encode(payload.encode("utf-8")).decode("ascii"))
PY
  )"

  ssh_host "python3 - '$VMID' '$new_desc_b64' <<'PY'
import base64
import subprocess
import sys

vmid = sys.argv[1]
desc = base64.b64decode(sys.argv[2]).decode('utf-8')
subprocess.run(['sudo', '/usr/sbin/qm', 'set', vmid, '--description', desc], check=True)
PY"
}

main() {
  local guest_script guest_ip

  require_tool ssh
  require_tool python3
  require_tool base64

  parse_args "$@"

  [[ -n "$VMID" ]] || {
    echo "--vmid is required" >&2
    exit 1
  }
  [[ -n "$SUNSHINE_PASSWORD" ]] || {
    echo "--sunshine-password is required" >&2
    exit 1
  }

  if [[ -z "$SUNSHINE_PIN" ]]; then
    SUNSHINE_PIN="$(printf '%04d' $(( VMID % 10000 )))"
  fi

  guest_script="$(cat <<EOF
#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
GUEST_USER='${GUEST_USER}'
SUNSHINE_USER='${SUNSHINE_USER}'
SUNSHINE_PASSWORD='${SUNSHINE_PASSWORD}'
SUNSHINE_PORT='${SUNSHINE_PORT}'
SUNSHINE_URL='${SUNSHINE_URL}'
SUNSHINE_ORIGIN_WEB_UI_ALLOWED='${SUNSHINE_ORIGIN_WEB_UI_ALLOWED}'

echo 'lightdm shared/default-x-display-manager select lightdm' | debconf-set-selections
apt-get update
apt-get install -y --no-install-recommends \
  xfce4 \
  xfce4-goodies \
  lightdm \
  lightdm-gtk-greeter \
  curl \
  ca-certificates

tmpdir=\$(mktemp -d)
trap 'rm -rf "\$tmpdir"' EXIT
curl -fsSLo "\$tmpdir/sunshine.deb" "\$SUNSHINE_URL"
apt-get install -y "\$tmpdir/sunshine.deb"

install -d -m 0755 /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/60-pve-thin-client.conf <<'GUESTCFG'
[Seat:*]
autologin-user=${GUEST_USER}
autologin-session=xfce
user-session=xfce
greeter-session=lightdm-gtk-greeter
GUESTCFG

install -d -m 0700 -o "\$GUEST_USER" -g "\$GUEST_USER" \
  "/home/\$GUEST_USER/.config" \
  "/home/\$GUEST_USER/.config/autostart" \
  "/home/\$GUEST_USER/.config/sunshine" \
  "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml"

cat > "/home/\$GUEST_USER/.config/autostart/sunshine.desktop" <<'AUTOSTART'
[Desktop Entry]
Type=Application
Name=Sunshine
Exec=sunshine
X-GNOME-Autostart-enabled=true
OnlyShowIn=XFCE;
AUTOSTART

cat > "/home/\$GUEST_USER/.config/sunshine/sunshine.conf" <<'SUNCONF'
sunshine_name = ${GUEST_USER}-sunshine
min_log_level = warning
origin_web_ui_allowed = ${SUNSHINE_ORIGIN_WEB_UI_ALLOWED}
origin_pin_allowed = ${SUNSHINE_ORIGIN_WEB_UI_ALLOWED}
encoder = software
sw_preset = superfast
sw_tune = zerolatency
capture = x11
hevc_mode = 0
av1_mode = 0
$( if [[ -n "${SUNSHINE_PORT}" ]]; then printf 'port = %s\n' "${SUNSHINE_PORT}"; fi )
SUNCONF

cat > "/home/\$GUEST_USER/.config/sunshine/apps.json" <<'APPS'
{
  "env": {
    "PATH": "\$(PATH):\$(HOME)/.local/bin"
  },
  "apps": [
    {
      "name": "Desktop",
      "image-path": "desktop.png"
    }
  ]
}
APPS

cat > "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml" <<'XFWM4'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="use_compositing" type="bool" value="false"/>
    <property name="vblank_mode" type="string" value="off"/>
  </property>
</channel>
XFWM4

chown -R "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config"

systemctl disable sunshine >/dev/null 2>&1 || true
systemctl stop sunshine >/dev/null 2>&1 || true
systemctl disable gdm3 >/dev/null 2>&1 || true
printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
ln -sf /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
systemctl daemon-reload
systemctl set-default graphical.target >/dev/null

su - "\$GUEST_USER" -c "HOME=/home/\$GUEST_USER XDG_CONFIG_HOME=/home/\$GUEST_USER/.config sunshine --creds '\$SUNSHINE_USER' '\$SUNSHINE_PASSWORD'"
systemctl enable sunshine >/dev/null 2>&1 || true
systemctl restart sunshine >/dev/null 2>&1 || true
if ! pgrep -u "\$GUEST_USER" -x sunshine >/dev/null 2>&1; then
  su - "\$GUEST_USER" -c "HOME=/home/\$GUEST_USER XDG_CONFIG_HOME=/home/\$GUEST_USER/.config nohup sunshine >/tmp/sunshine-user.log 2>&1 &" >/dev/null 2>&1 || true
fi
systemctl restart display-manager.service >/dev/null 2>&1 || true
EOF
)"

  guest_exec_script "$guest_script"
  guest_ip="$(detect_guest_ip | tail -n1 | tr -d '\r')"
  [[ -n "$guest_ip" ]] || {
    echo "Unable to determine guest IPv4 address for VM $VMID" >&2
    exit 1
  }

  if [[ "$UPDATE_METADATA" == "1" ]]; then
    update_vm_metadata "$guest_ip"
  fi

  if [[ "$VM_REBOOT" == "1" ]]; then
    ssh_host "sudo /usr/sbin/qm reboot '$VMID'" >/dev/null 2>&1 || true
  fi
  echo "Configured Sunshine guest VM $VMID on $PROXMOX_HOST (guest IP: $guest_ip)"
}

main "$@"
