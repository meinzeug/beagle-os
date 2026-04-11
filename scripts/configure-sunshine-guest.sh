#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOCAL_PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$SCRIPT_DIR/lib/beagle_provider.py}"
REMOTE_INSTALL_DIR="${BEAGLE_REMOTE_INSTALL_DIR:-/opt/beagle}"
REMOTE_PROVIDER_MODULE_PATH="${BEAGLE_REMOTE_PROVIDER_MODULE_PATH:-${REMOTE_INSTALL_DIR%/}/scripts/lib/beagle_provider.py}"

PROXMOX_HOST="${PROXMOX_HOST:-proxmox.local}"
VMID="${VMID:-}"
GUEST_USER="${GUEST_USER:-beagle}"
GUEST_PASSWORD="${GUEST_PASSWORD:-}"
IDENTITY_LOCALE="${IDENTITY_LOCALE:-de_DE.UTF-8}"
IDENTITY_LANGUAGE="${IDENTITY_LANGUAGE:-de_DE:de}"
IDENTITY_KEYMAP="${IDENTITY_KEYMAP:-de}"
DESKTOP_ID="${DESKTOP_ID:-xfce}"
DESKTOP_LABEL="${DESKTOP_LABEL:-XFCE}"
DESKTOP_SESSION="${DESKTOP_SESSION:-xfce}"
PROXMOX_USER="${PROXMOX_USER:-}"
PROXMOX_PASSWORD="${PROXMOX_PASSWORD:-}"
PROXMOX_TOKEN="${PROXMOX_TOKEN:-}"
SUNSHINE_USER="${SUNSHINE_USER:-sunshine}"
SUNSHINE_PASSWORD="${SUNSHINE_PASSWORD:-}"
SUNSHINE_PIN="${SUNSHINE_PIN:-}"
SUNSHINE_PORT="${SUNSHINE_PORT:-}"
SUNSHINE_URL="${SUNSHINE_URL:-https://github.com/LizardByte/Sunshine/releases/download/v2025.924.154138/sunshine-ubuntu-24.04-amd64.deb}"
SUNSHINE_ORIGIN_WEB_UI_ALLOWED="${SUNSHINE_ORIGIN_WEB_UI_ALLOWED:-wan}"
PUBLIC_STREAM_HOST_RAW="${PUBLIC_STREAM_HOST:-}"
UPDATE_METADATA="${UPDATE_METADATA:-1}"
VM_REBOOT="${VM_REBOOT:-1}"
DESKTOP_PACKAGES=()
SOFTWARE_PACKAGES=()
PACKAGE_PRESETS=()
EXTRA_PACKAGES=()

resolve_public_stream_host() {
  python3 - "$1" <<'PY'
import ipaddress
import socket
import sys

host = str(sys.argv[1] or "").strip()
if not host:
    print("")
    raise SystemExit(0)
try:
    ipaddress.ip_address(host)
except ValueError:
    pass
else:
    print(host)
    raise SystemExit(0)

try:
    infos = socket.getaddrinfo(host, None, family=socket.AF_INET, type=socket.SOCK_STREAM)
except socket.gaierror:
    print(host)
    raise SystemExit(0)

for item in infos:
    ip = str(item[4][0]).strip()
    if ip:
        print(ip)
        raise SystemExit(0)
print(host)
PY
}

PUBLIC_STREAM_HOST="$(resolve_public_stream_host "$PUBLIC_STREAM_HOST_RAW")"

usage() {
  cat <<EOF
Usage: $0 --vmid VMID [--proxmox-host HOST] [--guest-user USER] [--guest-password PASS] [--identity-locale LOCALE] [--identity-keymap KEYMAP] [--desktop-id ID] [--desktop-label LABEL] [--desktop-session SESSION] [--desktop-package PKG]... [--software-package PKG]... [--package-preset ID]... [--extra-package PKG]... [--proxmox-user USER@REALM] [--proxmox-password PASS|--proxmox-token TOKEN] [--sunshine-user USER] --sunshine-password PASS [--sunshine-pin PIN] [--sunshine-port PORT] [--public-stream-host HOST]
EOF
}

apply_desktop_defaults() {
  case "${DESKTOP_ID:-xfce}" in
    xfce)
      DESKTOP_LABEL="${DESKTOP_LABEL:-XFCE}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-xfce}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(xfce4 xfce4-goodies)
      fi
      ;;
    gnome)
      DESKTOP_LABEL="${DESKTOP_LABEL:-GNOME}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-ubuntu-xorg}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(ubuntu-desktop-minimal)
      fi
      ;;
    plasma)
      DESKTOP_LABEL="${DESKTOP_LABEL:-KDE Plasma}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-plasma}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(plasma-desktop konsole dolphin)
      fi
      ;;
    mate)
      DESKTOP_LABEL="${DESKTOP_LABEL:-MATE}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-mate}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(mate-desktop-environment-core mate-terminal caja)
      fi
      ;;
    lxqt)
      DESKTOP_LABEL="${DESKTOP_LABEL:-LXQt}"
      DESKTOP_SESSION="${DESKTOP_SESSION:-lxqt}"
      if [[ ${#DESKTOP_PACKAGES[@]} -eq 0 ]]; then
        DESKTOP_PACKAGES=(lxqt qterminal pcmanfm-qt)
      fi
      ;;
    *)
      echo "Unsupported desktop-id: ${DESKTOP_ID}" >&2
      exit 1
      ;;
  esac
}

join_words() {
  local IFS=' '
  printf '%s' "$*"
}

join_csv() {
  local IFS=','
  printf '%s' "$*"
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
      --guest-password) GUEST_PASSWORD="$2"; shift 2 ;;
      --identity-locale) IDENTITY_LOCALE="$2"; shift 2 ;;
      --identity-keymap) IDENTITY_KEYMAP="$2"; shift 2 ;;
      --desktop-id) DESKTOP_ID="$2"; shift 2 ;;
      --desktop-label) DESKTOP_LABEL="$2"; shift 2 ;;
      --desktop-session) DESKTOP_SESSION="$2"; shift 2 ;;
      --desktop-package) DESKTOP_PACKAGES+=("$2"); shift 2 ;;
      --software-package) SOFTWARE_PACKAGES+=("$2"); shift 2 ;;
      --package-preset) PACKAGE_PRESETS+=("$2"); shift 2 ;;
      --extra-package) EXTRA_PACKAGES+=("$2"); shift 2 ;;
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
  IDENTITY_LANGUAGE="${IDENTITY_LOCALE%%_*}:${IDENTITY_LOCALE%%_*}"
  apply_desktop_defaults
}

ssh_host() {
  local target="${PROXMOX_HOST:-}"
  if is_local_host_target; then
    bash -lc "$*"
    return 0
  fi
  ssh "$target" "$@"
}

is_local_host_target() {
  local target="${PROXMOX_HOST:-}"
  case "$target" in
    localhost|127.0.0.1|::1|"$(hostname)"|"$(hostname -f 2>/dev/null || hostname)")
      return 0
      ;;
    *)
      return 1
      ;;
  esac
}

provider_module_path_for_target() {
  if is_local_host_target; then
    printf '%s\n' "$LOCAL_PROVIDER_MODULE_PATH"
    return 0
  fi
  printf '%s\n' "$REMOTE_PROVIDER_MODULE_PATH"
}

provider_helper_available() {
  local module_path
  module_path="$(provider_module_path_for_target)"
  ssh_host "test -f '$module_path'"
}

provider_helper_exec() {
  local module_path
  module_path="$(provider_module_path_for_target)"
  ssh_host "python3 '$module_path' $*"
}

qm_guest_exec_sync() {
  local command="$1"
  local raw_output payload_json pid status_raw status_json exitcode
  raw_output="$(ssh_host "sudo /usr/sbin/qm guest exec '$VMID' -- bash -lc $(printf '%q' "$command")")"
  payload_json="$(python3 - "$raw_output" <<'PY'
import json
import sys

raw = sys.argv[1]
payload = {}
for line in reversed([line.strip() for line in raw.splitlines() if line.strip()]):
    try:
        payload = json.loads(line)
        break
    except json.JSONDecodeError:
        continue
print(json.dumps(payload))
PY
)"

  pid="$(python3 - "$payload_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
pid = payload.get("pid")
print("" if pid is None else str(pid))
PY
)"

  if [[ -z "$pid" ]]; then
    status_json="$payload_json"
  else
    while true; do
      sleep 2
      status_raw="$(ssh_host "sudo /usr/sbin/qm guest exec-status '$VMID' '$pid'")"
      status_json="$(python3 - "$status_raw" <<'PY'
import json
import sys

raw = sys.argv[1]
payload = {}
for line in reversed([line.strip() for line in raw.splitlines() if line.strip()]):
    try:
        payload = json.loads(line)
        break
    except json.JSONDecodeError:
        continue
print(json.dumps(payload))
PY
)"
      if python3 - "$status_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
raise SystemExit(0 if payload.get("exited") else 1)
PY
      then
        break
      fi
    done
  fi

  exitcode="$(python3 - "$status_json" <<'PY'
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
print(int(payload.get("exitcode", 0) or 0))
PY
)"
  if [[ "$exitcode" != "0" ]]; then
    python3 - "$status_json" <<'PY' >&2
import json
import sys

payload = json.loads(sys.argv[1] or "{}")
stdout = str(payload.get("out-data", "") or "").strip()
stderr = str(payload.get("err-data", "") or "").strip()
if stdout:
    print(stdout)
if stderr:
    print(stderr, file=sys.stderr)
PY
    return 1
  fi

  printf '%s\n' "$status_json"
  return 0
}

guest_exec_script() {
  local script="$1"
  local guest_ip=""
  local script_b64
  local chunk=""
  local chunk_size=3000

  guest_ip="$(detect_guest_ip | tail -n1 | tr -d '\r' || true)"
  if [[ -n "$GUEST_PASSWORD" && -n "$guest_ip" ]] && command -v sshpass >/dev/null 2>&1; then
    local ssh_target="${GUEST_USER}@${guest_ip}"
    local tmp_script
    tmp_script="$(mktemp)"
    printf '%s' "$script" >"$tmp_script"
    SSHPASS="$GUEST_PASSWORD" sshpass -e scp \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$tmp_script" "${ssh_target}:/tmp/pve-sunshine-setup.sh" >/dev/null
    printf '%s\n' "$GUEST_PASSWORD" | SSHPASS="$GUEST_PASSWORD" sshpass -e ssh \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$ssh_target" "sudo -S -p '' bash /tmp/pve-sunshine-setup.sh && rm -f /tmp/pve-sunshine-setup.sh" >/dev/null
    rm -f "$tmp_script"
    return 0
  fi

  script_b64="$(printf '%s' "$script" | base64 -w0)"

  qm_guest_exec_sync "rm -f /tmp/pve-sunshine-setup.sh /tmp/pve-sunshine-setup.sh.b64 && touch /tmp/pve-sunshine-setup.sh.b64 && chmod 600 /tmp/pve-sunshine-setup.sh.b64" >/dev/null
  while [[ -n "$script_b64" ]]; do
    chunk="${script_b64:0:$chunk_size}"
    script_b64="${script_b64:$chunk_size}"
    qm_guest_exec_sync "printf '%s' '$chunk' >> /tmp/pve-sunshine-setup.sh.b64" >/dev/null
  done
  qm_guest_exec_sync "base64 -d /tmp/pve-sunshine-setup.sh.b64 >/tmp/pve-sunshine-setup.sh && chmod +x /tmp/pve-sunshine-setup.sh && /tmp/pve-sunshine-setup.sh" >/dev/null
}

detect_guest_ip() {
  if provider_helper_available; then
    provider_helper_exec "guest-ipv4 '$VMID'" 2>/dev/null && return 0
  fi

  local raw_output
  raw_output="$(ssh_host "sudo /usr/sbin/qm guest cmd '$VMID' network-get-interfaces" 2>/dev/null || true)"
  python3 - "$raw_output" <<'PY'
import json
import sys

raw = sys.argv[1].strip()
if not raw:
    raise SystemExit(1)

try:
    payload = json.loads(raw)
except json.JSONDecodeError:
    raise SystemExit(1)

for iface in payload if isinstance(payload, list) else []:
    for address in iface.get("ip-addresses", []):
        ip = str(address.get("ip-address", "")).strip()
        if address.get("ip-address-type") != "ipv4":
            continue
        if not ip or ip.startswith("127.") or ip.startswith("169.254."):
            continue
        print(ip)
        raise SystemExit(0)

raise SystemExit(1)
PY
}

current_vm_description() {
  if provider_helper_available; then
    provider_helper_exec "vm-description '$VMID'" 2>/dev/null && return 0
  fi
  ssh_host "sudo /usr/sbin/qm config '$VMID'" | sed -n 's/^description: //p'
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
  encoded_desc="$(current_vm_description)"

  new_desc_b64="$(
    python3 - "$encoded_desc" "$guest_ip" "$stream_host" "$stream_port" "$stream_api_url" "$SUNSHINE_USER" "$SUNSHINE_PASSWORD" "$SUNSHINE_PIN" "$PROXMOX_USER" "$PROXMOX_PASSWORD" "$PROXMOX_TOKEN" "$GUEST_USER" "$IDENTITY_LOCALE" "$IDENTITY_KEYMAP" "$DESKTOP_ID" "$DESKTOP_LABEL" "$DESKTOP_SESSION" "$(join_csv "${PACKAGE_PRESETS[@]}")" "$(join_csv "${EXTRA_PACKAGES[@]}")" <<'PY'
import base64
import sys
from urllib.parse import unquote

(
    encoded,
    guest_ip,
    stream_host,
    stream_port,
    stream_api_url,
    sunshine_user,
    sunshine_password,
    sunshine_pin,
    proxmox_user,
    proxmox_password,
    proxmox_token,
    guest_user,
    identity_locale,
    identity_keymap,
    desktop_id,
    desktop_label,
    desktop_session,
    package_presets,
    extra_packages,
) = sys.argv[1:20]
skip = {
    "sunshine-guest-user",
    "sunshine-host",
    "sunshine-ip",
    "sunshine-api-url",
    "sunshine-user",
    "sunshine-password",
    "sunshine-pin",
    "proxmox-user",
    "proxmox-password",
    "proxmox-token",
    "beagle-public-stream-host",
    "beagle-public-moonlight-port",
    "beagle-public-sunshine-api-url",
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
    "beagle-identity-locale",
    "beagle-identity-keymap",
    "beagle-desktop",
    "beagle-desktop-id",
    "beagle-desktop-session",
    "beagle-package-presets",
    "beagle-extra-packages",
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
        f"sunshine-guest-user: {guest_user}",
        f"sunshine-host: {stream_host}",
        f"sunshine-ip: {guest_ip}",
        f"sunshine-api-url: {stream_api_url}",
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
        f"beagle-identity-locale: {identity_locale}",
        f"beagle-identity-keymap: {identity_keymap}",
        f"beagle-desktop: {desktop_label}",
        f"beagle-desktop-id: {desktop_id}",
        f"beagle-desktop-session: {desktop_session}",
    ]
)
if package_presets:
    lines.append(f"beagle-package-presets: {package_presets}")
if extra_packages:
    lines.append(f"beagle-extra-packages: {extra_packages}")
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
IDENTITY_LOCALE='${IDENTITY_LOCALE:-de_DE.UTF-8}'
IDENTITY_LANGUAGE='${IDENTITY_LANGUAGE:-de:de}'
IDENTITY_KEYMAP='${IDENTITY_KEYMAP:-de}'
DESKTOP_ID='${DESKTOP_ID}'
DESKTOP_SESSION='${DESKTOP_SESSION}'
DESKTOP_PACKAGES='$(join_words "${DESKTOP_PACKAGES[@]}")'
SOFTWARE_PACKAGES='$(join_words "${SOFTWARE_PACKAGES[@]}")'
SUNSHINE_USER='${SUNSHINE_USER}'
SUNSHINE_PASSWORD='${SUNSHINE_PASSWORD}'
SUNSHINE_PORT='${SUNSHINE_PORT}'
SUNSHINE_URL='${SUNSHINE_URL}'
SUNSHINE_ORIGIN_WEB_UI_ALLOWED='${SUNSHINE_ORIGIN_WEB_UI_ALLOWED}'

configure_system_locale() {
  local locale="\${IDENTITY_LOCALE:-de_DE.UTF-8}"
  local language="\${IDENTITY_LANGUAGE:-de_DE:de}"
  local language_code="\${locale%%_*}"
  local escaped_locale=""

  apt-get install -y --no-install-recommends locales
  case "\$language_code" in
    de)
      apt-get install -y --no-install-recommends language-pack-de language-pack-gnome-de
      ;;
  esac

  escaped_locale="\$(printf '%s\n' "\$locale" | sed 's/[.[\\*^$()+?{}|]/\\\\&/g')"
  if grep -q "^# \$escaped_locale UTF-8" /etc/locale.gen 2>/dev/null; then
    sed -i "s/^# \$escaped_locale UTF-8/\$locale UTF-8/" /etc/locale.gen
  elif ! grep -q "^\$escaped_locale UTF-8" /etc/locale.gen 2>/dev/null; then
    printf '%s UTF-8\n' "\$locale" >> /etc/locale.gen
  fi

  locale-gen "\$locale" >/dev/null 2>&1 || true
  update-locale LANG="\$locale" LANGUAGE="\$language" >/dev/null 2>&1 || true
  cat > /etc/default/locale <<LOCALECONF
LANG=\$locale
LANGUAGE=\$language
LOCALECONF

  install -d -m 0755 /var/lib/AccountsService/users
  cat > "/var/lib/AccountsService/users/\$GUEST_USER" <<ACCOUNTCONF
[User]
Language=\$locale
XSession=\${DESKTOP_SESSION}
ACCOUNTCONF

  cat > "/home/\$GUEST_USER/.dmrc" <<DMRCCONF
[Desktop]
Language=\$locale
Session=\${DESKTOP_SESSION}
DMRCCONF
  chown "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.dmrc"
}

configure_keyboard_layout() {
  local keymap="\${IDENTITY_KEYMAP:-de}"

  cat > /etc/default/keyboard <<KEYBOARDCONF
XKBMODEL="pc105"
XKBLAYOUT="\${keymap}"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
KEYBOARDCONF

  install -d -m 0755 /etc/X11/xorg.conf.d
  cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<KEYMAPCONF
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "\${keymap}"
    Option "XkbModel" "pc105"
EndSection
KEYMAPCONF
}

install_google_chrome() {
  install -d -m 0755 /etc/apt/keyrings
  apt-get install -y --no-install-recommends gnupg xdg-utils
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg.tmp
  install -m 0644 /etc/apt/keyrings/google-chrome.gpg.tmp /etc/apt/keyrings/google-chrome.gpg
  rm -f /etc/apt/keyrings/google-chrome.gpg.tmp
  cat > /etc/apt/sources.list.d/google-chrome.list <<'CHROMEREPO'
deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main
CHROMEREPO
  apt-get update
  apt-get install -y --no-install-recommends google-chrome-stable
}

configure_default_browser() {
  install -d -m 0700 -o "\$GUEST_USER" -g "\$GUEST_USER" \
    "/home/\$GUEST_USER/.config" \
    "/home/\$GUEST_USER/.config/xfce4"
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --set x-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  update-alternatives --set gnome-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  cat > "/home/\$GUEST_USER/.config/xfce4/helpers.rc" <<'HELPERS'
WebBrowser=google-chrome
MailReader=thunderbird
TerminalEmulator=xfce4-terminal
FileManager=thunar
HELPERS
  cat > "/home/\$GUEST_USER/.config/mimeapps.list" <<'MIMEAPPS'
[Default Applications]
x-scheme-handler/http=google-chrome.desktop
x-scheme-handler/https=google-chrome.desktop
text/html=google-chrome.desktop
application/xhtml+xml=google-chrome.desktop
x-scheme-handler/about=google-chrome.desktop
x-scheme-handler/unknown=google-chrome.desktop
MIMEAPPS
  chown "\$GUEST_USER:\$GUEST_USER" \
    "/home/\$GUEST_USER/.config/xfce4/helpers.rc" \
    "/home/\$GUEST_USER/.config/mimeapps.list"
}

echo 'lightdm shared/default-x-display-manager select lightdm' | debconf-set-selections
apt-get update
apt-get install -y \
  x11-xserver-utils \
  lightdm \
  lightdm-gtk-greeter \
  curl \
  ca-certificates \
  pipewire \
  pipewire-pulse \
  wireplumber \
  pulseaudio-utils \
  xdg-utils \
  usbutils
if [[ -n "\$DESKTOP_PACKAGES" ]]; then
  apt-get install -y \$DESKTOP_PACKAGES
fi
if [[ -n "\$SOFTWARE_PACKAGES" ]]; then
  apt-get install -y \$SOFTWARE_PACKAGES
fi

tmpdir=\$(mktemp -d)
trap 'rm -rf "\$tmpdir"' EXIT
curl -fsSLo "\$tmpdir/sunshine.deb" "\$SUNSHINE_URL"
apt-get install -y "\$tmpdir/sunshine.deb"
configure_system_locale
configure_keyboard_layout
install_google_chrome

install -d -m 0755 /etc/lightdm/lightdm.conf.d
cat > /etc/lightdm/lightdm.conf.d/60-pve-thin-client.conf <<GUESTCFG
[Seat:*]
autologin-user=${GUEST_USER}
autologin-session=${DESKTOP_SESSION}
user-session=${DESKTOP_SESSION}
greeter-session=lightdm-gtk-greeter
GUESTCFG

install -d -m 0700 -o "\$GUEST_USER" -g "\$GUEST_USER" \
  "/home/\$GUEST_USER/.config" \
  "/home/\$GUEST_USER/.config/sunshine" \
  "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml"
install -d -m 0755 /etc/X11/xorg.conf.d
GUEST_UID="\$(id -u "\$GUEST_USER")"

cat > /etc/X11/xorg.conf.d/90-beagle-ignore-virtual-input.conf <<'XORGCONF'
Section "InputClass"
    Identifier "beagle-ignore-touch-passthrough"
    MatchProduct "Touch passthrough"
    Option "Ignore" "on"
EndSection

Section "InputClass"
    Identifier "beagle-ignore-pen-passthrough"
    MatchProduct "Pen passthrough"
    Option "Ignore" "on"
EndSection
XORGCONF

cat > "/home/\$GUEST_USER/.config/sunshine/sunshine.conf" <<SUNCONF
sunshine_name = ${GUEST_USER}-sunshine
min_log_level = info
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

if [[ "\$DESKTOP_ID" == "xfce" ]]; then
cat > "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml" <<'XFWM4'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="use_compositing" type="bool" value="false"/>
    <property name="vblank_mode" type="string" value="off"/>
  </property>
</channel>
XFWM4
fi

chown -R "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config"
configure_default_browser

cat > /etc/systemd/system/beagle-sunshine.service <<SUNSHINESVC
[Unit]
Description=Beagle Sunshine
After=network-online.target display-manager.service graphical.target sound.target
Wants=network-online.target

[Service]
Type=simple
User=\$GUEST_USER
Group=\$GUEST_USER
Environment=HOME=/home/\$GUEST_USER
Environment=XDG_CONFIG_HOME=/home/\$GUEST_USER/.config
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/\$GUEST_USER/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/\$GUEST_UID
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/\$GUEST_UID/bus
Environment=PULSE_SERVER=unix:/run/user/\$GUEST_UID/pulse/native
ExecStartPre=/bin/bash -lc 'pulse_socket="/run/user/\$GUEST_UID/pulse/native"; for _ in {1..180}; do if [[ -S /tmp/.X11-unix/X0 && -s /home/\$GUEST_USER/.Xauthority && -d /run/user/\$GUEST_UID && -S /run/user/\$GUEST_UID/bus && -S "\\\$pulse_socket" ]] && DISPLAY=:0 XAUTHORITY=/home/\$GUEST_USER/.Xauthority xrandr --query >/dev/null 2>&1 && DISPLAY=:0 XAUTHORITY=/home/\$GUEST_USER/.Xauthority xrandr --query | grep -q " connected"; then sleep 5; exit 0; fi; sleep 1; done; echo "Timed out waiting for an active graphical/audio session on :0" >&2; exit 1'
ExecStart=/usr/bin/sunshine
Restart=always
RestartSec=2

[Install]
WantedBy=graphical.target
SUNSHINESVC

systemctl disable sunshine >/dev/null 2>&1 || true
systemctl stop sunshine >/dev/null 2>&1 || true
su - "\$GUEST_USER" -c "systemctl --user disable --now sunshine.service >/dev/null 2>&1 || true" || true
rm -f "/home/\$GUEST_USER/.config/autostart/sunshine.desktop"
pkill -u "\$GUEST_USER" -x sunshine >/dev/null 2>&1 || true
systemctl disable gdm3 >/dev/null 2>&1 || true
printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
ln -sf /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
systemctl daemon-reload
systemctl set-default graphical.target >/dev/null

su - "\$GUEST_USER" -c "HOME=/home/\$GUEST_USER XDG_CONFIG_HOME=/home/\$GUEST_USER/.config sunshine --creds '\$SUNSHINE_USER' '\$SUNSHINE_PASSWORD'"
systemctl restart display-manager.service >/dev/null 2>&1 || true
loginctl enable-linger "\$GUEST_USER" >/dev/null 2>&1 || true
for _ in {1..60}; do
  if systemctl --user -M "\$GUEST_USER@" show basic.target >/dev/null 2>&1; then
    systemctl --user -M "\$GUEST_USER@" enable --now pipewire.service pipewire-pulse.service wireplumber.service >/dev/null 2>&1 || true
    break
  fi
  sleep 1
done
systemctl enable --now beagle-sunshine.service >/dev/null 2>&1 || true
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
