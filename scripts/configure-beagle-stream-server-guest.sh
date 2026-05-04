#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
source "$SCRIPT_DIR/lib/trace-guard.sh"
beagle_trace_guard_disable_xtrace_if_sensitive
source "$SCRIPT_DIR/lib/provider_shell.sh"
LOCAL_PROVIDER_MODULE_PATH="${BEAGLE_PROVIDER_MODULE_PATH:-$SCRIPT_DIR/lib/beagle_provider.py}"
REMOTE_INSTALL_DIR="${BEAGLE_REMOTE_INSTALL_DIR:-/opt/beagle}"
REMOTE_PROVIDER_MODULE_PATH="${BEAGLE_REMOTE_PROVIDER_MODULE_PATH:-${REMOTE_INSTALL_DIR%/}/scripts/lib/beagle_provider.py}"
PROVIDER_HELPER_AVAILABLE_CACHE="${PROVIDER_HELPER_AVAILABLE_CACHE:-}"

# Ensure provider imports can resolve top-level repo modules (e.g. core/*) on live hosts.
export PYTHONPATH="$REPO_ROOT${PYTHONPATH:+:$PYTHONPATH}"

BEAGLE_HOST="${BEAGLE_HOST:-beagle.local}"
VMID="${VMID:-}"
GUEST_USER="${GUEST_USER:-beagle}"
BEAGLE_MANAGER_URL="${BEAGLE_MANAGER_URL:-}"
VMID="${VMID:-}"
GUEST_PASSWORD="${GUEST_PASSWORD:-}"
IDENTITY_LOCALE="${IDENTITY_LOCALE:-de_DE.UTF-8}"
IDENTITY_LANGUAGE="${IDENTITY_LANGUAGE:-de_DE:de}"
IDENTITY_KEYMAP="${IDENTITY_KEYMAP:-de}"
DESKTOP_ID="${DESKTOP_ID:-xfce}"
DESKTOP_LABEL="${DESKTOP_LABEL:-XFCE}"
DESKTOP_SESSION="${DESKTOP_SESSION:-xfce}"
BEAGLE_USER="${BEAGLE_USER:-}"
BEAGLE_PASSWORD="${BEAGLE_PASSWORD:-}"
BEAGLE_TOKEN="${BEAGLE_TOKEN:-}"
GUEST_IP_OVERRIDE="${GUEST_IP_OVERRIDE:-}"
BEAGLE_STREAM_SERVER_USER="${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_TOKEN="${BEAGLE_STREAM_SERVER_TOKEN:-}"
BEAGLE_STREAM_SERVER_PORT="${BEAGLE_STREAM_SERVER_PORT:-}"
BEAGLE_STREAM_SERVER_DEFAULT_URL="https://github.com/meinzeug/beagle-stream-server/releases/download/beagle-phase-a/beagle-stream-server-latest-ubuntu-24.04-amd64.deb"
BEAGLE_STREAM_SERVER_URL="${BEAGLE_STREAM_SERVER_URL:-$BEAGLE_STREAM_SERVER_DEFAULT_URL}"
BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED="${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED:-wan}"
BEAGLE_STREAM_SERVER_ALLOWED_CIDRS="${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS:-10.88.0.0/16}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC:-45}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC:-90}"
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
STREAM_RUNTIME_STATUS_FILE="/etc/beagle/stream-runtime.env"

usage() {
  cat <<EOF
Usage: $0 --vmid VMID [--beagle-host HOST] [--guest-user USER] [--guest-password PASS] [--identity-locale LOCALE] [--identity-keymap KEYMAP] [--desktop-id ID] [--desktop-label LABEL] [--desktop-session SESSION] [--desktop-package PKG]... [--software-package PKG]... [--package-preset ID]... [--extra-package PKG]... [--beagle-user USER@REALM] [--beagle-password PASS|--beagle-token TOKEN] [--beagle-stream-server-user USER] --beagle-stream-server-password PASS --beagle-stream-server-token TOKEN [--beagle-stream-server-port PORT] [--public-stream-host HOST]
EOF
}

write_stream_runtime_status() {
  local variant="$1"
  local package_url="$2"

  install -d -m 0755 /etc/beagle
  cat > "$STREAM_RUNTIME_STATUS_FILE" <<EOF
BEAGLE_STREAM_RUNTIME_VARIANT=${variant}
BEAGLE_STREAM_RUNTIME_PACKAGE_URL=${package_url}
BEAGLE_STREAM_RUNTIME_UPDATED_AT=$(date -Iseconds)
EOF
  chmod 0644 "$STREAM_RUNTIME_STATUS_FILE"
}

write_beagle_stream_server_broker_env() {
  install -d -m 0755 /etc/beagle
  cat > /etc/beagle/stream-server.env <<EOF
BEAGLE_CONTROL_PLANE=${BEAGLE_MANAGER_URL}
BEAGLE_STREAM_TOKEN=${BEAGLE_STREAM_SERVER_TOKEN}
BEAGLE_VM_ID=${VMID}
EOF
  chmod 0600 /etc/beagle/stream-server.env
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
      --beagle-host|--beagle-host) BEAGLE_HOST="$2"; shift 2 ;; # --beagle-host kept for backwards compat
      --vmid) VMID="$2"; shift 2 ;;
      --guest-user) GUEST_USER="$2"; shift 2 ;;
      --guest-password) GUEST_PASSWORD="$2"; shift 2 ;;
      --guest-ip) GUEST_IP_OVERRIDE="$2"; shift 2 ;;
      --identity-locale) IDENTITY_LOCALE="$2"; shift 2 ;;
      --identity-keymap) IDENTITY_KEYMAP="$2"; shift 2 ;;
      --desktop-id) DESKTOP_ID="$2"; shift 2 ;;
      --desktop-label) DESKTOP_LABEL="$2"; shift 2 ;;
      --desktop-session) DESKTOP_SESSION="$2"; shift 2 ;;
      --desktop-package) DESKTOP_PACKAGES+=("$2"); shift 2 ;;
      --software-package) SOFTWARE_PACKAGES+=("$2"); shift 2 ;;
      --package-preset) PACKAGE_PRESETS+=("$2"); shift 2 ;;
      --extra-package) EXTRA_PACKAGES+=("$2"); shift 2 ;;
      --beagle-user) BEAGLE_USER="$2"; shift 2 ;;
      --beagle-password) BEAGLE_PASSWORD="$2"; shift 2 ;;
      --beagle-token) BEAGLE_TOKEN="$2"; shift 2 ;;
      --beagle-stream-server-user) BEAGLE_STREAM_SERVER_USER="$2"; shift 2 ;;
      --beagle-stream-server-password) BEAGLE_STREAM_SERVER_PASSWORD="$2"; shift 2 ;;
      --beagle-stream-server-token) BEAGLE_STREAM_SERVER_TOKEN="$2"; shift 2 ;;
      --beagle-stream-server-port) BEAGLE_STREAM_SERVER_PORT="$2"; shift 2 ;;
      --beagle-stream-server-url) BEAGLE_STREAM_SERVER_URL="$2"; shift 2 ;;
      --beagle-stream-server-origin-web-ui-allowed) BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED="$2"; shift 2 ;;
      --beagle-stream-server-allowed-cidrs) BEAGLE_STREAM_SERVER_ALLOWED_CIDRS="$2"; shift 2 ;;
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

qm_guest_exec_sync() {
  local command="$1"
  beagle_provider_guest_exec_sync_bash "$VMID" "$command"
}

guest_exec_script() {
  local script="$1"
  local guest_ip=""
  local script_b64
  local chunk=""
  local chunk_size=3000

  guest_ip="$GUEST_IP_OVERRIDE"
  if [[ -z "$guest_ip" ]]; then
    guest_ip="$(detect_guest_ip | tail -n1 | tr -d '\r' || true)"
  fi
  if [[ -n "$GUEST_PASSWORD" && -n "$guest_ip" ]] && command -v sshpass >/dev/null 2>&1; then
    local ssh_target="${GUEST_USER}@${guest_ip}"
    local tmp_script
    local remote_script_path="/home/${GUEST_USER}/pve-beagle-stream-server-setup.sh"
    tmp_script="$(mktemp)"
    printf '%s' "$script" >"$tmp_script"
    SSHPASS="$GUEST_PASSWORD" sshpass -e scp \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$tmp_script" "${ssh_target}:${remote_script_path}" >/dev/null
    printf '%s\n' "$GUEST_PASSWORD" | SSHPASS="$GUEST_PASSWORD" sshpass -e ssh \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o PreferredAuthentications=password \
      -o PubkeyAuthentication=no \
      -o ConnectTimeout=10 \
      "$ssh_target" "sudo -S -p '' bash ${remote_script_path} && rm -f ${remote_script_path}" >/dev/null
    rm -f "$tmp_script"
    return 0
  fi

  script_b64="$(printf '%s' "$script" | base64 -w0)"

  qm_guest_exec_sync "rm -f /tmp/pve-beagle-stream-server-setup.sh /tmp/pve-beagle-stream-server-setup.sh.b64 && touch /tmp/pve-beagle-stream-server-setup.sh.b64 && chmod 600 /tmp/pve-beagle-stream-server-setup.sh.b64" >/dev/null
  while [[ -n "$script_b64" ]]; do
    chunk="${script_b64:0:$chunk_size}"
    script_b64="${script_b64:$chunk_size}"
    qm_guest_exec_sync "printf '%s' '$chunk' >> /tmp/pve-beagle-stream-server-setup.sh.b64" >/dev/null
  done
  qm_guest_exec_sync "base64 -d /tmp/pve-beagle-stream-server-setup.sh.b64 >/tmp/pve-beagle-stream-server-setup.sh && chmod +x /tmp/pve-beagle-stream-server-setup.sh && /tmp/pve-beagle-stream-server-setup.sh" >/dev/null
}

detect_guest_ip() {
  beagle_provider_guest_ipv4 "$VMID"
}

current_vm_description() {
  beagle_provider_vm_description "$VMID"
}

set_current_vm_description_b64() {
  local description_b64="$1"
  beagle_provider_set_vm_description_b64 "$VMID" "$description_b64"
}

reboot_current_vm() {
  beagle_provider_reboot_vm "$VMID"
}

update_vm_metadata() {
  local guest_ip="$1"
  local stream_host="${PUBLIC_STREAM_HOST:-$guest_ip}"
  local stream_port="${BEAGLE_STREAM_SERVER_PORT:-}"
  local stream_api_url=""
  local encoded_desc new_desc_b64
  if [[ -n "$stream_port" ]]; then
    stream_api_url="https://${stream_host}:$((stream_port + 1))"
  else
    stream_api_url="https://${stream_host}:47990"
  fi
  encoded_desc="$(current_vm_description)"

  new_desc_b64="$(
    python3 - "$encoded_desc" "$guest_ip" "$stream_host" "$stream_port" "$stream_api_url" "$BEAGLE_STREAM_SERVER_USER" "$BEAGLE_STREAM_SERVER_PASSWORD" "$BEAGLE_USER" "$BEAGLE_PASSWORD" "$BEAGLE_TOKEN" "$GUEST_USER" "$IDENTITY_LOCALE" "$IDENTITY_KEYMAP" "$DESKTOP_ID" "$DESKTOP_LABEL" "$DESKTOP_SESSION" "$(join_csv "${PACKAGE_PRESETS[@]}")" "$(join_csv "${EXTRA_PACKAGES[@]}")" <<'PY'
import base64
import sys
from urllib.parse import unquote

(
    encoded,
    guest_ip,
    stream_host,
    stream_port,
    stream_api_url,
    beagle_stream_server_user,
    beagle_stream_server_password,
    beagle_user,
    beagle_password,
    beagle_token,
    guest_user,
    identity_locale,
    identity_keymap,
    desktop_id,
    desktop_label,
    desktop_session,
    package_presets,
    extra_packages,
) = sys.argv[1:19]
skip = {
    "beagle-stream-server-guest-user",
    "beagle-stream-server-host",
    "beagle-stream-server-ip",
    "beagle-stream-server-api-url",
    "beagle-stream-server-user",
    "beagle-stream-server-password",
    "beagle-user",
    "beagle-password",
    "beagle-token",
    "beagle-public-stream-host",
    "beagle-public-beagle-stream-client-port",
    "beagle-public-beagle-stream-server-api-url",
    "beagle-stream-server-app",
    "beagle-stream-client-host",
    "beagle-stream-client-port",
    "beagle-stream-client-app",
    "beagle-stream-client-resolution",
    "beagle-stream-client-fps",
    "beagle-stream-client-bitrate",
    "beagle-stream-client-video-codec",
    "beagle-stream-client-video-decoder",
    "beagle-stream-client-audio-config",
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
        f"beagle-stream-server-guest-user: {guest_user}",
        f"beagle-stream-server-host: {stream_host}",
        f"beagle-stream-server-ip: {guest_ip}",
        f"beagle-stream-server-api-url: {stream_api_url}",
        "beagle-stream-server-app: Desktop",
        f"beagle-stream-client-host: {stream_host}",
        f"beagle-stream-client-port: {stream_port}",
        "beagle-stream-client-app: Desktop",
        "beagle-stream-client-resolution: auto",
        "beagle-stream-client-fps: 60",
        "beagle-stream-client-bitrate: 20000",
        "beagle-stream-client-video-codec: H.264",
        "beagle-stream-client-video-decoder: auto",
        "beagle-stream-client-audio-config: stereo",
        "thinclient-default-mode: BEAGLE_STREAM_CLIENT",
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
            f"beagle-public-beagle-stream-client-port: {stream_port}",
            f"beagle-public-beagle-stream-server-api-url: {stream_api_url}",
        ]
    )

payload = "\n".join(lines).strip() + "\n"
print(base64.b64encode(payload.encode("utf-8")).decode("ascii"))
PY
  )"

  set_current_vm_description_b64 "$new_desc_b64"
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
  [[ -n "$BEAGLE_STREAM_SERVER_PASSWORD" ]] || {
    echo "--beagle-stream-server-password is required" >&2
    exit 1
  }
  [[ -n "$BEAGLE_STREAM_SERVER_TOKEN" ]] || {
    echo "--beagle-stream-server-token is required" >&2
    exit 1
  }

  guest_script="$(cat <<EOF
#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive
GUEST_USER='${GUEST_USER}'
VMID='${VMID}'
BEAGLE_MANAGER_URL='${BEAGLE_MANAGER_URL}'
IDENTITY_LOCALE='${IDENTITY_LOCALE:-de_DE.UTF-8}'
IDENTITY_LANGUAGE='${IDENTITY_LANGUAGE:-de:de}'
IDENTITY_KEYMAP='${IDENTITY_KEYMAP:-de}'
DESKTOP_ID='${DESKTOP_ID}'
DESKTOP_SESSION='${DESKTOP_SESSION}'
DESKTOP_PACKAGES='$(join_words "${DESKTOP_PACKAGES[@]}")'
SOFTWARE_PACKAGES='$(join_words "${SOFTWARE_PACKAGES[@]}")'
BEAGLE_STREAM_SERVER_USER='${BEAGLE_STREAM_SERVER_USER}'
BEAGLE_STREAM_SERVER_PASSWORD='${BEAGLE_STREAM_SERVER_PASSWORD}'
BEAGLE_STREAM_SERVER_TOKEN='${BEAGLE_STREAM_SERVER_TOKEN}'
BEAGLE_STREAM_SERVER_PORT='${BEAGLE_STREAM_SERVER_PORT}'
BEAGLE_STREAM_SERVER_URL='${BEAGLE_STREAM_SERVER_URL}'
BEAGLE_STREAM_SERVER_URL='${BEAGLE_STREAM_SERVER_URL}'
BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED='${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}'
BEAGLE_STREAM_SERVER_ALLOWED_CIDRS='${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS}'
BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC='${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC}'
BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC='${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC}'

configure_system_locale() {
  local locale="\${IDENTITY_LOCALE:-de_DE.UTF-8}"
  local language="\${IDENTITY_LANGUAGE:-de_DE:de}"
  local language_code="\${locale%%_*}"
  local escaped_locale=""

  apt-get install -y --no-install-recommends locales
  case "\$language_code" in
    de)
      # Ubuntu language-pack packages are optional and not present on Debian hosts.
      if apt-cache show language-pack-de >/dev/null 2>&1 && apt-cache show language-pack-gnome-de >/dev/null 2>&1; then
        apt-get install -y --no-install-recommends language-pack-de language-pack-gnome-de || true
      fi
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

install_visual_studio_code_repo() {
  install -d -m 0755 /etc/apt/keyrings
  apt-get install -y --no-install-recommends gnupg
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /etc/apt/keyrings/packages.microsoft.gpg.tmp
  install -m 0644 /etc/apt/keyrings/packages.microsoft.gpg.tmp /etc/apt/keyrings/packages.microsoft.gpg
  rm -f /etc/apt/keyrings/packages.microsoft.gpg.tmp
  cat > /etc/apt/sources.list.d/vscode.list <<'VSCODEREPO'
deb [arch=amd64 signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main
VSCODEREPO
  apt-get update
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
install_visual_studio_code_repo
apt-get install -y \
  x11-xserver-utils \
  lightdm \
  lightdm-gtk-greeter \
  curl \
  ca-certificates \
  nftables \
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
stream_runtime_package_url="\$BEAGLE_STREAM_SERVER_URL"
stream_runtime_variant="beagle-stream-server"
curl -fsSLo "\$tmpdir/beagle-stream-server.deb" "\$BEAGLE_STREAM_SERVER_URL"
apt-get install -y "\$tmpdir/beagle-stream-server.deb"
write_stream_runtime_status "\$stream_runtime_variant" "\$stream_runtime_package_url"
BEAGLE_STREAM_SERVER_EXEC="\$(command -v beagle-stream-server 2>/dev/null || command -v sunshine 2>/dev/null || echo /usr/bin/beagle-stream-server)"
if [[ ! -x /usr/local/bin/beagle-stream-server && -n "\$(command -v sunshine 2>/dev/null || true)" ]]; then
cat > /usr/local/bin/beagle-stream-server <<'BEAGLEWRAP'
#!/usr/bin/env bash
exec "\$(command -v sunshine)" "\$@"
BEAGLEWRAP
chmod 0755 /usr/local/bin/beagle-stream-server
BEAGLE_STREAM_SERVER_EXEC="/usr/local/bin/beagle-stream-server"
fi
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
  "/home/\$GUEST_USER/.config/autostart" \
  "/home/\$GUEST_USER/.config/beagle-stream-server" \
  "/home/\$GUEST_USER/.local" \
  "/home/\$GUEST_USER/.local/state" \
  "/home/\$GUEST_USER/.local/state/wireplumber" \
  "/home/\$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml"
if [[ -d "/home/\$GUEST_USER/.config/sunshine" && ! -e "/home/\$GUEST_USER/.config/beagle-stream-server" ]]; then
  mv "/home/\$GUEST_USER/.config/sunshine" "/home/\$GUEST_USER/.config/beagle-stream-server"
fi
if [[ -e "/home/\$GUEST_USER/.config/sunshine" && ! -L "/home/\$GUEST_USER/.config/sunshine" ]]; then
  cp -a "/home/\$GUEST_USER/.config/sunshine/." "/home/\$GUEST_USER/.config/beagle-stream-server/" 2>/dev/null || true
  rm -rf "/home/\$GUEST_USER/.config/sunshine"
fi
ln -sfn "/home/\$GUEST_USER/.config/beagle-stream-server" "/home/\$GUEST_USER/.config/sunshine"
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

cat > /etc/X11/Xsession.d/19-beagle-lightdm-session-compat <<'XSESSIONCOMPAT'
#!/bin/sh
# LightDM may source Xsession.d snippets directly without the helpers from
# /etc/X11/Xsession. Provide safe fallbacks so downstream snippets stay valid.

: "${OPTIONFILE:=/etc/X11/Xsession.options}"
: "${SYSRESOURCES:=/etc/X11/Xresources}"
: "${USRRESOURCES:=$HOME/.Xresources}"
: "${USERXSESSION:=$HOME/.xsession}"
: "${USERXSESSIONRC:=$HOME/.xsessionrc}"
: "${ALTUSERXSESSION:=$HOME/.Xsession}"

if ! type has_option >/dev/null 2>&1; then
  OPTIONS="$({
    [ -r "$OPTIONFILE" ] && cat "$OPTIONFILE"
    if [ -d /etc/X11/Xsession.options.d ]; then
      run-parts --list --regex '\\.conf$' /etc/X11/Xsession.options.d | xargs -d '\n' cat
    fi
  } 2>/dev/null)"

  has_option() {
    if [ "$(echo "$OPTIONS" | grep -Eo "^(no-)?$1\\>" | tail -n 1)" = "$1" ]; then
      return 0
    fi
    return 1
  }
fi

if ! type message >/dev/null 2>&1; then
  message() {
    echo "Xsession: $*" >&2
  }
fi

if ! type errormsg >/dev/null 2>&1; then
  errormsg() {
    message "$*"
    return 1
  }
fi
XSESSIONCOMPAT
chmod 0755 /etc/X11/Xsession.d/19-beagle-lightdm-session-compat

cat > /etc/X11/Xsession.d/90-beagle-disable-display-idle <<'XSESSIONIDLE'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
XSESSIONIDLE
chmod 0755 /etc/X11/Xsession.d/90-beagle-disable-display-idle

cat > "/home/\$GUEST_USER/.xprofile" <<'XPROFILE'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
XPROFILE
chmod 0755 "/home/\$GUEST_USER/.xprofile"

cat > "/home/\$GUEST_USER/.config/beagle-stream-server/beagle-stream-server.conf" <<SUNCONF
beagle_stream_server_name = ${GUEST_USER}-beagle-stream-server
min_log_level = info
origin_web_ui_allowed = ${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}
origin_pin_allowed = ${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}
encoder = software
sw_preset = superfast
sw_tune = zerolatency
capture = x11
hevc_mode = 0
av1_mode = 0
$( if [[ -n "${BEAGLE_STREAM_SERVER_PORT}" ]]; then printf 'port = %s\n' "${BEAGLE_STREAM_SERVER_PORT}"; fi )
SUNCONF
cp "/home/\$GUEST_USER/.config/beagle-stream-server/beagle-stream-server.conf" "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine.conf"

cat > "/home/\$GUEST_USER/.config/beagle-stream-server/apps.json" <<'APPS'
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

python3 - "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" <<'PY'
import json
import sys
import uuid
from pathlib import Path

state_path = Path(sys.argv[1])
payload = {}
if state_path.exists():
    try:
        payload = json.loads(state_path.read_text(encoding="utf-8"))
    except Exception:
        payload = {}
root = payload.setdefault("root", {})
named = root.get("named_devices")
if not isinstance(named, list):
    root["named_devices"] = []
root["uniqueid"] = str(root.get("uniqueid") or "").strip() or str(uuid.uuid4()).upper()
state_path.parent.mkdir(parents=True, exist_ok=True)
state_path.write_text(json.dumps(payload, indent=4) + "\n", encoding="utf-8")
PY
ln -sfn "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" "/home/\$GUEST_USER/.config/beagle-stream-server/beagle_stream_server_state.json"
chown -h "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config/beagle-stream-server/beagle_stream_server_state.json" >/dev/null 2>&1 || true
chown "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" >/dev/null 2>&1 || true
chmod 0600 "/home/\$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" >/dev/null 2>&1 || true

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

cat > "/home/\$GUEST_USER/.config/autostart/light-locker.desktop" <<'AUTOSTARTLOCK'
[Desktop Entry]
Type=Application
Name=Light Locker
Hidden=true
AUTOSTARTLOCK

cat > "/home/\$GUEST_USER/.config/autostart/xfce4-power-manager.desktop" <<'AUTOSTARTPOWER'
[Desktop Entry]
Type=Application
Name=XFCE Power Manager
Hidden=true
AUTOSTARTPOWER

cat > "/home/\$GUEST_USER/.config/autostart/xfce4-screensaver.desktop" <<'AUTOSTARTSCREENSAVER'
[Desktop Entry]
Type=Application
Name=XFCE Screensaver
Hidden=true
AUTOSTARTSCREENSAVER
fi

chown -R "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.config" "/home/\$GUEST_USER/.local"
chown "\$GUEST_USER:\$GUEST_USER" "/home/\$GUEST_USER/.xprofile"
configure_default_browser

cat > /etc/systemd/system/beagle-stream-server.service <<BEAGLE_STREAM_SERVERSVC
[Unit]
Description=Beagle Beagle Stream Server
After=network-online.target display-manager.service graphical.target sound.target
Wants=network-online.target
StartLimitIntervalSec=0

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
EnvironmentFile=-/etc/beagle/stream-server.env
ExecStartPre=/bin/bash -lc 'pulse_socket="/run/user/\$GUEST_UID/pulse/native"; for _ in {1..180}; do if [[ -S /tmp/.X11-unix/X0 && -s /home/\$GUEST_USER/.Xauthority && -d /run/user/\$GUEST_UID && -S /run/user/\$GUEST_UID/bus && -S "\\\$pulse_socket" ]] && DISPLAY=:0 XAUTHORITY=/home/\$GUEST_USER/.Xauthority xrandr --query >/dev/null 2>&1 && DISPLAY=:0 XAUTHORITY=/home/\$GUEST_USER/.Xauthority xrandr --query | grep -q " connected"; then sleep 5; exit 0; fi; sleep 1; done; echo "Timed out waiting for an active graphical/audio session on :0" >&2; exit 1'
ExecStart=\$BEAGLE_STREAM_SERVER_EXEC
Restart=always
RestartSec=3
TimeoutStartSec=210

[Install]
WantedBy=graphical.target
BEAGLE_STREAM_SERVERSVC

install -d -m 0755 /etc/beagle
write_beagle_stream_server_broker_env
cat > /etc/beagle/beagle-stream-server-healthcheck.env <<HEALTHENV
BEAGLE_STREAM_SERVER_USER=\$BEAGLE_STREAM_SERVER_USER
BEAGLE_STREAM_SERVER_PASSWORD=\$BEAGLE_STREAM_SERVER_PASSWORD
BEAGLE_STREAM_SERVER_PORT=\$BEAGLE_STREAM_SERVER_PORT
GUEST_USER=\$GUEST_USER
GUEST_UID=\$GUEST_UID
HEALTHENV
chmod 0600 /etc/beagle/beagle-stream-server-healthcheck.env

cat > /usr/local/bin/beagle-stream-server-healthcheck <<'HEALTHCHECK'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/etc/beagle/beagle-stream-server-healthcheck.env"
[[ -r "\$ENV_FILE" ]] || exit 1
# shellcheck disable=SC1090
source "\$ENV_FILE"

BEAGLE_STREAM_SERVER_USER="\${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="\${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_PORT="\${BEAGLE_STREAM_SERVER_PORT:-}"
GUEST_USER="\${GUEST_USER:-beagle}"
GUEST_UID="\${GUEST_UID:-\$(id -u "\$GUEST_USER" 2>/dev/null || echo 1000)}"

repair="\${1:-}"
api_port=47990
if [[ -n "\$BEAGLE_STREAM_SERVER_PORT" ]]; then
  api_port="\$((BEAGLE_STREAM_SERVER_PORT + 1))"
fi

ensure_runtime() {
  local runtime_dir="/run/user/\${GUEST_UID}"
  if [[ ! -d "\$runtime_dir" ]]; then
    loginctl enable-linger "\$GUEST_USER" >/dev/null 2>&1 || true
  fi
}

restart_stack() {
  ensure_runtime
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable beagle-stream-server.service >/dev/null 2>&1 || true
  systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true
}

ensure_timer() {
  systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
}

is_api_ready() {
  [[ -n "\$BEAGLE_STREAM_SERVER_PASSWORD" ]] || return 1
  curl -kfsS --connect-timeout 3 --max-time 5 --user "\${BEAGLE_STREAM_SERVER_USER}:\${BEAGLE_STREAM_SERVER_PASSWORD}" "https://127.0.0.1:\${api_port}/api/apps" >/dev/null # tls-bypass-allowlist: loopback health check against local Beagle Stream Server self-signed API
}

ensure_timer

if [[ "\$repair" == "--repair-only" ]]; then
  restart_stack
  exit 0
fi

if ! systemctl is-active --quiet beagle-stream-server.service; then
  restart_stack
  exit 0
fi

if ! pgrep -x beagle-stream-server >/dev/null 2>&1; then
  restart_stack
  exit 0
fi

if ! is_api_ready; then
  restart_stack
fi
HEALTHCHECK
chmod 0755 /usr/local/bin/beagle-stream-server-healthcheck

cat > /etc/systemd/system/beagle-stream-server-healthcheck.service <<'HEALTHSVC'
[Unit]
Description=Beagle Beagle Stream Server Healthcheck and Repair
After=network-online.target beagle-stream-server.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/beagle-stream-server-healthcheck
HEALTHSVC

cat > /etc/systemd/system/beagle-stream-server-healthcheck.timer <<HEALTHTIMER
[Unit]
Description=Run Beagle Beagle Stream Server healthcheck periodically

[Timer]
OnBootSec=\${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC}s
OnUnitActiveSec=\${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC}s
Persistent=true
RandomizedDelaySec=5s
Unit=beagle-stream-server-healthcheck.service

[Install]
WantedBy=timers.target
HEALTHTIMER

configure_stream_port_guard() {
  local stream_port="\${BEAGLE_STREAM_SERVER_PORT:-50000}"
  local api_port="50001"
  local rtsp_port="50021"
  local https_port="49995"
  local allowed_raw="\${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS:-10.88.0.0/16}"
  local default_gateway=""
  local default_gateway_cidr=""
  local cidr=""
  local cidr_csv=""

  if [[ "\$stream_port" =~ ^[0-9]+$ ]]; then
    api_port="\$((stream_port + 1))"
    rtsp_port="\$((stream_port + 21))"
    if [[ "\$stream_port" -gt 5 ]]; then
      https_port="\$((stream_port - 5))"
    fi
  else
    stream_port="50000"
  fi

  for cidr in \$(printf '%s' "\$allowed_raw" | tr ',;' '  '); do
    if [[ "\$cidr" =~ ^([0-9]{1,3}\\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]; then
      if [[ -n "\$cidr_csv" ]]; then
        cidr_csv+=", "
      fi
      cidr_csv+="\$cidr"
    fi
  done
  if [[ -z "\$cidr_csv" ]]; then
    cidr_csv="10.88.0.0/16"
  fi

  default_gateway="\$(ip route show default 2>/dev/null | awk '/default/ {print $3; exit}')"
  if [[ "\$default_gateway" =~ ^([0-9]{1,3}\\.){3}[0-9]{1,3}$ ]]; then
    default_gateway_cidr="\${default_gateway}/32"
    cidr_csv+=", \${default_gateway_cidr}"
  fi

  install -d -m 0755 /etc/beagle
  cat > /etc/beagle/beagle-stream-guest-guard.nft <<NFTGUARD
table inet beagle_stream_guest_guard {
  chain input {
    type filter hook input priority -5; policy accept;

    iifname "lo" accept
    ct state { established, related } accept

    iifname "wg-beagle" tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } accept
    ip saddr { \${cidr_csv} } tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } accept
    ip6 saddr ::1 tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } accept

    tcp dport { \${https_port}, \${stream_port}, \${api_port}, \${rtsp_port} } drop
  }
}
NFTGUARD

  systemctl enable nftables >/dev/null 2>&1 || true
  nft delete table inet beagle_stream_guest_guard >/dev/null 2>&1 || true
  nft -f /etc/beagle/beagle-stream-guest-guard.nft >/dev/null 2>&1 || true
}

systemctl disable beagle-stream-server >/dev/null 2>&1 || true
systemctl stop beagle-stream-server >/dev/null 2>&1 || true
systemctl disable --now beagle-sunshine.service >/dev/null 2>&1 || true
systemctl disable --now beagle-sunshine-healthcheck.timer >/dev/null 2>&1 || true
systemctl stop beagle-sunshine-healthcheck.service >/dev/null 2>&1 || true
pkill -x sunshine >/dev/null 2>&1 || true
su - "\$GUEST_USER" -c "systemctl --user disable --now beagle-stream-server.service >/dev/null 2>&1 || true" || true
rm -f "/home/\$GUEST_USER/.config/autostart/beagle-stream-server.desktop"
pkill -u "\$GUEST_USER" -x beagle-stream-server >/dev/null 2>&1 || true
systemctl disable gdm3 >/dev/null 2>&1 || true
printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
ln -sf /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
systemctl daemon-reload
systemctl set-default graphical.target >/dev/null

su - "\$GUEST_USER" -c "HOME=/home/\$GUEST_USER XDG_CONFIG_HOME=/home/\$GUEST_USER/.config beagle-stream-server --creds '\$BEAGLE_STREAM_SERVER_USER' '\$BEAGLE_STREAM_SERVER_PASSWORD'"
systemctl restart display-manager.service >/dev/null 2>&1 || true
loginctl enable-linger "\$GUEST_USER" >/dev/null 2>&1 || true
for _ in {1..60}; do
  if systemctl --user -M "\$GUEST_USER@" show basic.target >/dev/null 2>&1; then
    systemctl --user -M "\$GUEST_USER@" enable --now pipewire.service pipewire-pulse.service wireplumber.service >/dev/null 2>&1 || true
    break
  fi
  sleep 1
done
configure_stream_port_guard
systemctl enable --now beagle-stream-server.service >/dev/null 2>&1 || true
systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
/usr/local/bin/beagle-stream-server-healthcheck >/dev/null 2>&1 || true
EOF
)"

  guest_exec_script "$guest_script"
  guest_ip="$GUEST_IP_OVERRIDE"
  if [[ -z "$guest_ip" ]]; then
    guest_ip="$(detect_guest_ip 2>/dev/null | tail -n1 | tr -d '\r' || true)"
  fi
  if [[ "$UPDATE_METADATA" == "1" && -z "$guest_ip" ]]; then
    echo "Unable to determine guest IPv4 address for VM $VMID" >&2
    exit 1
  fi

  if [[ "$UPDATE_METADATA" == "1" ]]; then
    update_vm_metadata "$guest_ip"
  fi

  if [[ "$VM_REBOOT" == "1" ]]; then
    reboot_current_vm
  fi
  echo "Configured Beagle Stream Server guest VM $VMID on $BEAGLE_HOST (guest IP: ${guest_ip:-unknown})"
}

main "$@"
