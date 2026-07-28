#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

GUEST_USER="__GUEST_USER__"
VMID="__VMID__"
NODE="__NODE__"
BEAGLE_MANAGER_URL="__BEAGLE_MANAGER_URL__"
BEAGLE_ENDPOINT_TOKEN="__BEAGLE_ENDPOINT_TOKEN__"
BEAGLE_VERSION="__BEAGLE_VERSION__"
BEAGLE_GUEST_UPDATER_B64="__BEAGLE_GUEST_UPDATER_B64__"
BEAGLE_DESKTOP_PROFILE_REFRESH_B64="__BEAGLE_DESKTOP_PROFILE_REFRESH_B64__"
BEAGLE_THINCLIENT_ADMIN_B64="__BEAGLE_THINCLIENT_ADMIN_B64__"
BEAGLE_THINCLIENT_ADMIN_DESKTOP_B64="__BEAGLE_THINCLIENT_ADMIN_DESKTOP_B64__"
BEAGLE_NETBRIDGE_TRAY_B64="__BEAGLE_NETBRIDGE_TRAY_B64__"
IDENTITY_LOCALE="__IDENTITY_LOCALE__"
IDENTITY_LANGUAGE="__IDENTITY_LANGUAGE__"
IDENTITY_KEYMAP="__IDENTITY_KEYMAP__"
DESKTOP_ID="__DESKTOP_ID__"
DESKTOP_THEME_VARIANT="__DESKTOP_THEME_VARIANT__"
DESKTOP_SESSION="__DESKTOP_SESSION__"
DESKTOP_SESSION_EFFECTIVE="${DESKTOP_SESSION}"
DESKTOP_PACKAGES="__DESKTOP_PACKAGES__"
DESKTOP_WALLPAPER_FILENAME="__DESKTOP_WALLPAPER_FILENAME__"
SOFTWARE_PACKAGES="__SOFTWARE_PACKAGES__"
PACKAGE_PRESETS="__PACKAGE_PRESETS__"
NETWORK_MAC="__NETWORK_MAC__"
BEAGLE_STREAM_SERVER_USER="__BEAGLE_STREAM_SERVER_USER__"
BEAGLE_STREAM_SERVER_PASSWORD="__BEAGLE_STREAM_SERVER_PASSWORD__"
BEAGLE_STREAM_SERVER_TOKEN="__BEAGLE_STREAM_SERVER_TOKEN__"
BEAGLE_STREAM_SERVER_PORT="__BEAGLE_STREAM_SERVER_PORT__"
BEAGLE_STREAM_SERVER_URL="__BEAGLE_STREAM_SERVER_URL__"
BEAGLE_STREAM_SERVER_SHA256="__BEAGLE_STREAM_SERVER_SHA256__"
BEAGLE_USB_MICROPHONE_VOLUME="${BEAGLE_USB_MICROPHONE_VOLUME:-250%}"
BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED="__BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED__"
CALLBACK_URL="__CALLBACK_URL__"
CALLBACK_PINNED_PUBKEY="__CALLBACK_PINNED_PUBKEY__"
FAILED_CALLBACK_URL="${CALLBACK_URL%/complete}/failed"
DONE_FILE="/var/lib/beagle/ubuntu-firstboot.done"
CALLBACK_DONE_FILE="/var/lib/beagle/ubuntu-firstboot-callback.done"
TMPDIR_WORK=""
BEAGLE_WALLPAPER_DIR="/usr/local/share/beagle/wallpapers"
BEAGLE_WALLPAPER_PATH=""
STREAM_RUNTIME_STATUS_FILE="/etc/beagle/stream-runtime.env"

cleanup_tmpdir() {
  if [[ -n "$TMPDIR_WORK" && -d "$TMPDIR_WORK" ]]; then
    rm -rf "$TMPDIR_WORK"
  fi
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

install_beagle_guest_updater() {
  install -d -m 0755 /etc/beagle /var/lib/beagle/guest-updater
  printf '%s' "$BEAGLE_GUEST_UPDATER_B64" | base64 -d > /usr/local/sbin/beagle-guest-updater
  chmod 0755 /usr/local/sbin/beagle-guest-updater
  printf '%s' "$BEAGLE_DESKTOP_PROFILE_REFRESH_B64" | base64 -d > /usr/local/sbin/beagle-desktop-profile-refresh
  chmod 0755 /usr/local/sbin/beagle-desktop-profile-refresh
  cat > /etc/beagle/guest-updater.env <<EOF
BEAGLE_MANAGER_URL=${BEAGLE_MANAGER_URL}
BEAGLE_ENDPOINT_TOKEN=${BEAGLE_ENDPOINT_TOKEN}
BEAGLE_ENDPOINT_ID=desktop-vm-${VMID}
BEAGLE_PROFILE_NAME=vm-${VMID}
BEAGLE_NODE=${NODE}
BEAGLE_VMID=${VMID}
BEAGLE_GUEST_VERSION=${BEAGLE_VERSION}
BEAGLE_UPDATE_CHANNEL=stable
BEAGLE_UPDATE_BEHAVIOR=prompt
BEAGLE_UPDATE_FEED_URL=${BEAGLE_MANAGER_URL%/}/api/v1/endpoints/update-feed
BEAGLE_MANAGER_PINNED_PUBKEY=${CALLBACK_PINNED_PUBKEY}
BEAGLE_MANAGER_ALLOW_INSECURE_TLS=1
BEAGLE_GUEST_UPDATER_INTERACTIVE_REBOOT=1
EOF
  chmod 0600 /etc/beagle/guest-updater.env
  cat > /etc/sudoers.d/beagle-guest-updater <<EOF
${GUEST_USER} ALL=(root) NOPASSWD: /usr/local/sbin/beagle-guest-updater status, /usr/local/sbin/beagle-guest-updater scan --force, /usr/local/sbin/beagle-guest-updater apply --reboot, /usr/local/sbin/beagle-guest-updater desktop-profile-refresh --force, /usr/local/sbin/beagle-guest-updater reboot, /usr/local/sbin/beagle-guest-updater shutdown
EOF
  chmod 0440 /etc/sudoers.d/beagle-guest-updater
  cat > /etc/systemd/system/beagle-guest-updater-scan.service <<'EOF'
[Unit]
Description=Beagle Desktop Guest Update Scan
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/beagle-guest-updater scan --auto-apply-if-idle
EOF
  cat > /etc/systemd/system/beagle-guest-updater-scan.timer <<'EOF'
[Unit]
Description=Run Beagle Desktop Guest Update Scan

[Timer]
OnBootSec=3min
OnUnitActiveSec=30min
RandomizedDelaySec=3min
Persistent=true

[Install]
WantedBy=timers.target
EOF
  cat > /etc/systemd/system/beagle-guest-updater-actions.service <<'EOF'
[Unit]
Description=Beagle Desktop Guest Action Poller
After=network-online.target
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/sbin/beagle-guest-updater poll-actions
EOF
  cat > /etc/systemd/system/beagle-guest-updater-actions.timer <<'EOF'
[Unit]
Description=Poll Beagle Desktop Guest Actions

[Timer]
OnBootSec=90s
OnUnitActiveSec=30s
RandomizedDelaySec=5s
Persistent=true

[Install]
WantedBy=timers.target
EOF
  systemctl daemon-reload
  systemctl enable --now beagle-guest-updater-actions.timer >/dev/null 2>&1 || true
  systemctl enable --now beagle-guest-updater-scan.timer >/dev/null 2>&1 || true
  /usr/local/sbin/beagle-guest-updater check-in >/dev/null 2>&1 || true
}

disable_cdrom_apt_sources() {
  python3 - <<'PY'
from pathlib import Path

for path in Path("/etc/apt").rglob("*"):
    if not path.is_file():
        continue
    try:
        original = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        continue
    updated = original
    if path.suffix == ".sources":
        kept_blocks = []
        for block in original.split("\n\n"):
            if "cdrom" in block:
                continue
            if block.strip():
                kept_blocks.append(block.strip())
        updated = "\n\n".join(kept_blocks)
        if updated:
            updated += "\n"
    else:
        kept_lines = []
        for line in original.splitlines():
            stripped = line.strip()
            if "cdrom" in stripped:
                continue
            kept_lines.append(line)
        updated = "\n".join(kept_lines)
        if updated:
            updated += "\n"
    if updated != original:
        path.write_text(updated, encoding="utf-8")
PY
}

callback_tls_args() {
  if [[ -n "$CALLBACK_PINNED_PUBKEY" ]]; then
    # tls-bypass-allowlist: Callback to Beagle host with pubkey pinning; host may use self-signed cert
    printf '%s\n' --insecure --pinnedpubkey "$CALLBACK_PINNED_PUBKEY"
  else
    # tls-bypass-allowlist: Callback to Beagle host without pinning; system CA used if valid, else insecure
    printf '%s\n' --insecure
  fi
}

report_failure() {
  local exit_code="${1:-1}"
  local line_no="${2:-unknown}"
  local command_text="${3:-unknown}"
  local payload_file=""
  local -a curl_args

  [[ -n "$FAILED_CALLBACK_URL" ]] || return 0

  payload_file="$(mktemp)"
  python3 - "$payload_file" "$exit_code" "$line_no" "$command_text" <<'PY'
import json
import sys
from pathlib import Path

payload = {
    "phase": "firstboot",
    "message": "Ubuntu firstboot provisioning failed.",
    "error": f"exit={sys.argv[2]} line={sys.argv[3]} command={sys.argv[4]}",
}
Path(sys.argv[1]).write_text(json.dumps(payload), encoding="utf-8")
PY
  curl_args=(curl -fsS)
  mapfile -t tls_args < <(callback_tls_args)
  curl_args+=("${tls_args[@]}")
  "${curl_args[@]}" \
    --connect-timeout 5 \
    --max-time 15 \
    --retry 3 \
    --retry-delay 2 \
    -H 'Content-Type: application/json' \
    --data-binary "@${payload_file}" \
    "$FAILED_CALLBACK_URL" >/dev/null 2>&1 || true
  rm -f "$payload_file"
}
trap cleanup_tmpdir EXIT
trap 'report_failure $? "$LINENO" "$BASH_COMMAND"' ERR

if [[ -f "$DONE_FILE" && -f "$CALLBACK_DONE_FILE" ]]; then
  exit 0
fi

install -d -m 0755 /var/lib/beagle

ensure_network_connectivity() {
  local iface=""
  local static_ip=""
  local static_cidr=""
  local static_gateway="192.168.123.1"

  iface="$(ip -o link show | awk -F': ' '$2 != "lo" {print $2; exit}')"
  if [[ -z "$iface" ]]; then
    return 1
  fi

  install -d -m 0755 /etc/netplan
  python3 - "$iface" "$NETWORK_MAC" >/etc/netplan/01-beagle-dhcp.yaml <<'PY'
import json
import sys

iface = sys.argv[1]
mac = sys.argv[2].strip().lower()
lines = [
    "network:",
    "  version: 2",
    "  renderer: networkd",
    "  ethernets:",
    f"    {iface}:",
]
if mac:
    lines.extend([
        "      match:",
        f"        macaddress: \"{mac}\"",
        f"      set-name: {iface}",
    ])
lines.extend([
    "      dhcp4: true",
    "      dhcp6: false",
])
print("\n".join(lines) + "\n")
PY
  chmod 0600 /etc/netplan/01-beagle-dhcp.yaml

  ip link set "$iface" up >/dev/null 2>&1 || true
  # Starting wait-online here can deadlock firstboot on some guests without a configured uplink yet.
  systemctl enable systemd-networkd.service >/dev/null 2>&1 || true
  systemctl start systemd-networkd.service >/dev/null 2>&1 || true
  netplan generate >/dev/null 2>&1 || true
  netplan apply >/dev/null 2>&1 || true
  networkctl reconfigure "$iface" >/dev/null 2>&1 || true

  for _attempt in $(seq 1 25); do
    if ip -4 -o addr show dev "$iface" scope global | grep -q 'inet '; then
      return 0
    fi
    sleep 2
  done

  # DHCP can fail in some host bridge setups during first boot.
  # Fall back to a deterministic static address derived from the VM MAC.
  static_ip="$(python3 - "$NETWORK_MAC" <<'PY'
import sys

mac = str(sys.argv[1] or "").strip().lower()
parts = [p for p in mac.split(":") if p]
octet = 0
if len(parts) >= 6:
    try:
        octet = int(parts[-1], 16)
    except ValueError:
        octet = 0
if octet < 2:
    octet = 200
print(f"192.168.123.{octet}")
PY
)"
  static_cidr="${static_ip}/24"

  python3 - "$iface" "$NETWORK_MAC" "$static_cidr" "$static_gateway" >/etc/netplan/01-beagle-static.yaml <<'PY'
import sys

iface = sys.argv[1]
mac = sys.argv[2].strip().lower()
cidr = sys.argv[3].strip()
gateway = sys.argv[4].strip()
lines = [
    "network:",
    "  version: 2",
    "  renderer: networkd",
    "  ethernets:",
    f"    {iface}:",
]
if mac:
    lines.extend([
        "      match:",
        f"        macaddress: \"{mac}\"",
        f"      set-name: {iface}",
    ])
lines.extend([
    f"      addresses: [{cidr}]",
    "      routes:",
    "        - to: default",
    f"          via: {gateway}",
    "      nameservers:",
    "        addresses: [1.1.1.1,8.8.8.8]",
    "      dhcp4: false",
    "      dhcp6: false",
])
print("\n".join(lines) + "\n")
PY
  chmod 0600 /etc/netplan/01-beagle-static.yaml

  netplan generate >/dev/null 2>&1 || true
  netplan apply >/dev/null 2>&1 || true
  networkctl reconfigure "$iface" >/dev/null 2>&1 || true

  for _attempt in $(seq 1 20); do
    if ip -4 -o addr show dev "$iface" scope global | grep -q 'inet '; then
      return 0
    fi
    sleep 2
  done

  return 1
}

ensure_dns_resolution() {
  local default_iface=""

  install -d -m 0755 /etc/systemd/resolved.conf.d
  cat > /etc/systemd/resolved.conf.d/60-beagle.conf <<'EOF'
[Resolve]
DNS=1.1.1.1 8.8.8.8
FallbackDNS=9.9.9.9 1.0.0.1
EOF

  systemctl enable --now systemd-resolved.service >/dev/null 2>&1 || true
  systemctl restart systemd-resolved.service >/dev/null 2>&1 || true

  if [[ ! -s /etc/resolv.conf ]] || ! grep -Eq '^\s*nameserver\s+' /etc/resolv.conf 2>/dev/null; then
    rm -f /etc/resolv.conf
    if [[ -s /run/systemd/resolve/resolv.conf ]]; then
      ln -s /run/systemd/resolve/resolv.conf /etc/resolv.conf
    elif [[ -s /run/systemd/resolve/stub-resolv.conf ]]; then
      ln -s /run/systemd/resolve/stub-resolv.conf /etc/resolv.conf
    else
      cat > /etc/resolv.conf <<'EOF'
nameserver 1.1.1.1
nameserver 8.8.8.8
EOF
    fi
  fi

  default_iface="$(ip route show default 2>/dev/null | awk '/default/ {print $5; exit}')"
  if [[ -n "$default_iface" ]]; then
    resolvectl dns "$default_iface" 1.1.1.1 8.8.8.8 >/dev/null 2>&1 || true
    resolvectl domain "$default_iface" "~." >/dev/null 2>&1 || true
  fi

  for _attempt in $(seq 1 20); do
    if resolvectl query archive.ubuntu.com >/dev/null 2>&1 || getent ahostsv4 archive.ubuntu.com >/dev/null 2>&1; then
      return 0
    fi
    sleep 2
  done

  return 1
}

resolve_desktop_session() {
  local session="${DESKTOP_SESSION:-}"

  if [[ "${DESKTOP_ID}" == "xfce" ]]; then
    if [[ -f /usr/share/xsessions/xfce.desktop ]]; then
      session="xfce"
    elif [[ -f /usr/share/xsessions/xfce4.desktop ]]; then
      session="xfce4"
    fi
  elif [[ "${DESKTOP_ID}" == plasma* || "${DESKTOP_SESSION:-}" == "plasma" ]]; then
    if [[ -f /usr/share/xsessions/plasma.desktop ]]; then
      session="plasma"
    elif [[ -f /usr/share/xsessions/plasmawayland.desktop ]]; then
      session="plasma"
    fi
  fi

  if [[ -z "$session" ]]; then
    session="default"
  fi

  DESKTOP_SESSION_EFFECTIVE="$session"
}

apt_retry() {
  local attempt
  for attempt in $(seq 1 4); do
    repair_interrupted_dpkg || true
    if "$@"; then
      if repair_interrupted_dpkg; then
        return 0
      fi
    fi
    sleep $((attempt * 5))
    ensure_dns_resolution || true
  done
  repair_interrupted_dpkg
}

repair_interrupted_dpkg() {
  local attempt
  local audit_output=""

  for attempt in $(seq 1 5); do
    audit_output="$(dpkg --audit 2>&1 || true)"
    if [[ -z "${audit_output//[[:space:]]/}" ]]; then
      return 0
    fi
    printf '%s\n' "$audit_output" >&2
    dpkg --configure -a || true
    apt-get install -f -y || true
    sleep $((attempt * 2))
  done

  audit_output="$(dpkg --audit 2>&1 || true)"
  [[ -z "${audit_output//[[:space:]]/}" ]]
}

configure_system_locale() {
  local locale="${IDENTITY_LOCALE:-de_DE.UTF-8}"
  local language="${IDENTITY_LANGUAGE:-de_DE:de}"
  local language_code="${locale%%_*}"
  local escaped_locale=""

  apt_retry apt-get install -y --no-install-recommends locales
  case "$language_code" in
    de)
      apt_retry apt-get install -y --no-install-recommends language-pack-de language-pack-gnome-de
      ;;
  esac

  escaped_locale="$(printf '%s\n' "$locale" | sed 's/[.[\*^$()+?{}|]/\\&/g')"
  if grep -q "^# ${escaped_locale} UTF-8" /etc/locale.gen 2>/dev/null; then
    sed -i "s/^# ${escaped_locale} UTF-8/${locale} UTF-8/" /etc/locale.gen
  elif ! grep -q "^${escaped_locale} UTF-8" /etc/locale.gen 2>/dev/null; then
    printf '%s UTF-8\n' "$locale" >> /etc/locale.gen
  fi

  locale-gen "$locale" >/dev/null 2>&1 || true
  update-locale LANG="$locale" LANGUAGE="$language" >/dev/null 2>&1 || true
  cat > /etc/default/locale <<EOF
LANG=${locale}
LANGUAGE=${language}
EOF

  install -d -m 0755 /var/lib/AccountsService/users
  cat > "/var/lib/AccountsService/users/$GUEST_USER" <<EOF
[User]
Language=${locale}
XSession=${DESKTOP_SESSION_EFFECTIVE}
EOF

  cat > "/home/$GUEST_USER/.dmrc" <<EOF
[Desktop]
Language=${locale}
Session=${DESKTOP_SESSION_EFFECTIVE}
EOF
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.dmrc"
}

find_seed_wallpaper() {
  local candidate=""
  local discovered=""

  [[ -n "$DESKTOP_WALLPAPER_FILENAME" ]] || return 1
  for candidate in \
    "/var/lib/beagle/seed/${DESKTOP_WALLPAPER_FILENAME}" \
    "/var/lib/cloud/seed/nocloud/${DESKTOP_WALLPAPER_FILENAME}" \
    "/var/lib/cloud/seed/nocloud-net/${DESKTOP_WALLPAPER_FILENAME}" \
    "/var/lib/cloud/instance/${DESKTOP_WALLPAPER_FILENAME}"
  do
    if [[ -f "$candidate" ]]; then
      printf '%s\n' "$candidate"
      return 0
    fi
  done

  discovered="$(find /var/lib/cloud -maxdepth 5 -type f -name "$DESKTOP_WALLPAPER_FILENAME" 2>/dev/null | head -n 1 || true)"
  if [[ -n "$discovered" && -f "$discovered" ]]; then
    printf '%s\n' "$discovered"
    return 0
  fi

  return 1
}

install_desktop_wallpaper() {
  local source_path=""

  [[ -n "$DESKTOP_WALLPAPER_FILENAME" ]] || return 0
  source_path="$(find_seed_wallpaper)" || {
    echo "Required wallpaper asset '${DESKTOP_WALLPAPER_FILENAME}' is missing from the provisioning seed." >&2
    return 1
  }
  install -d -m 0755 "$BEAGLE_WALLPAPER_DIR"
  install -m 0644 "$source_path" "$BEAGLE_WALLPAPER_DIR/$DESKTOP_WALLPAPER_FILENAME"
  BEAGLE_WALLPAPER_PATH="$BEAGLE_WALLPAPER_DIR/$DESKTOP_WALLPAPER_FILENAME"
}

configure_keyboard_layout() {
  local keymap="${IDENTITY_KEYMAP:-de}"

  cat > /etc/default/keyboard <<EOF
XKBMODEL="pc105"
XKBLAYOUT="${keymap}"
XKBVARIANT=""
XKBOPTIONS=""
BACKSPACE="guess"
EOF

  install -d -m 0755 /etc/X11/xorg.conf.d
  cat > /etc/X11/xorg.conf.d/00-keyboard.conf <<EOF
Section "InputClass"
    Identifier "system-keyboard"
    MatchIsKeyboard "on"
    Option "XkbLayout" "${keymap}"
    Option "XkbModel" "pc105"
EndSection
EOF
}

install_google_chrome() {
  install -d -m 0755 /etc/apt/keyrings
  apt_retry apt-get install -y --no-install-recommends gnupg xdg-utils
  curl -fsSL https://dl.google.com/linux/linux_signing_key.pub \
    | gpg --dearmor -o /etc/apt/keyrings/google-chrome.gpg.tmp
  install -m 0644 /etc/apt/keyrings/google-chrome.gpg.tmp /etc/apt/keyrings/google-chrome.gpg
  rm -f /etc/apt/keyrings/google-chrome.gpg.tmp
  cat > /etc/apt/sources.list.d/google-chrome.list <<'EOF'
deb [arch=amd64 signed-by=/etc/apt/keyrings/google-chrome.gpg] https://dl.google.com/linux/chrome/deb/ stable main
EOF
  apt_retry apt-get update -o Acquire::Retries=5
  apt_retry apt-get install -y --no-install-recommends google-chrome-stable
}

install_visual_studio_code_repo() {
  install -d -m 0755 /etc/apt/keyrings
  apt_retry apt-get install -y --no-install-recommends gnupg
  curl -fsSL https://packages.microsoft.com/keys/microsoft.asc \
    | gpg --dearmor -o /etc/apt/keyrings/packages.microsoft.gpg.tmp
  install -m 0644 /etc/apt/keyrings/packages.microsoft.gpg.tmp /etc/apt/keyrings/packages.microsoft.gpg
  rm -f /etc/apt/keyrings/packages.microsoft.gpg.tmp
  cat > /etc/apt/sources.list.d/vscode.list <<'EOF'
deb [arch=amd64 signed-by=/etc/apt/keyrings/packages.microsoft.gpg] https://packages.microsoft.com/repos/code stable main
EOF
  apt_retry apt-get update -o Acquire::Retries=5
}

configure_flatpak_flathub() {
  if command -v flatpak >/dev/null 2>&1; then
    flatpak remote-add --if-not-exists flathub https://flathub.org/repo/flathub.flatpakrepo >/dev/null 2>&1 || true
  fi
}

configure_virtual_display_vkms() {
  if ! modinfo vkms >/dev/null 2>&1; then
    echo "WARN: vkms module is not available; continuing without virtual display module" >&2
    return 0
  fi

  if ! lsmod | grep -q '^vkms\b'; then
    modprobe vkms >/dev/null 2>&1 || true
  fi

  install -d -m 0755 /etc/modules-load.d
  cat > /etc/modules-load.d/vkms.conf <<'EOF'
vkms
EOF

  cat > /etc/systemd/system/vkms-virtual-display.service <<'EOF'
[Unit]
Description=Beagle Virtual Display (vkms)
Before=display-manager.service

[Service]
Type=oneshot
ExecStart=/bin/bash -lc 'lsmod | grep -q "^vkms\\b" || modprobe vkms'
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

  cat > /usr/local/bin/beagle-vkms-xrandr-setup <<'EOF'
#!/usr/bin/env bash
# Beagle Virtual Display — registers all common resolutions on the virtual output.
# After this script runs, KDE System Settings → Display shows them as selectable options.
# No hardware dependency: all modes are added to the VKMS virtual connector.
set -euo pipefail

for _ in {1..30}; do
  if xrandr --query >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

output="$(xrandr --query | awk '/ connected/{print $1; exit}')"
[[ -n "$output" ]] || exit 0

# --- Register all common display resolutions ---
# Format: xrandr --newmode <name> <pclk> <h_active> <h_sync_start> <h_sync_end> <h_total>
#                            <v_active> <v_sync_start> <v_sync_end> <v_total> <flags>
declare -A MODES
MODES["1280x720_60.00"]="74.48 1280 1336 1472 1664 720 723 728 748 -hsync +vsync"
MODES["1366x768_60.00"]="85.50 1366 1436 1578 1790 768 771 774 798 -hsync +vsync"
MODES["1440x900_60.00"]="106.50 1440 1528 1672 1904 900 903 909 934 -hsync +vsync"
MODES["1600x900_60.00"]="108.00 1600 1624 1704 1800 900 901 904 1000 +hsync +vsync"
MODES["1920x1080_60.00"]="148.50 1920 2008 2052 2200 1080 1084 1089 1125 +hsync +vsync"
MODES["1920x1200_60.00"]="193.25 1920 2056 2256 2592 1200 1203 1209 1245 -hsync +vsync"
MODES["2560x1440_60.00"]="312.25 2560 2752 3024 3488 1440 1443 1448 1493 -hsync +vsync"
MODES["3840x2160_30.00"]="338.75 3840 4128 4544 5248 2160 2163 2168 2200 -hsync +vsync"
MODES["3840x2160_60.00"]="712.75 3840 4160 4576 5312 2160 2163 2168 2237 -hsync +vsync"

for mode_name in "${!MODES[@]}"; do
  # shellcheck disable=SC2086
  xrandr --newmode "$mode_name" ${MODES[$mode_name]} 2>/dev/null || true
  xrandr --addmode "$output" "$mode_name" 2>/dev/null || true
done

# Also register the canonical mode names VKMS may already know
for builtin in 1920x1080 1280x720 1024x768; do
  xrandr --addmode "$output" "$builtin" 2>/dev/null || true
done

# Set active mode to 1920x1080 as the universal default (works on any client display).
# Users can change via KDE System Settings → Display Configuration.
if xrandr --output "$output" --primary --mode "1920x1080_60.00" 2>/dev/null; then
  exit 0
fi
if xrandr --output "$output" --primary --mode "1920x1080" 2>/dev/null; then
  exit 0
fi
xrandr --output "$output" --primary --auto 2>/dev/null || true
EOF
  chmod 0755 /usr/local/bin/beagle-vkms-xrandr-setup

  cat > /etc/xdg/autostart/beagle-vkms-xrandr.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Beagle vkms xrandr setup
Exec=/usr/local/bin/beagle-vkms-xrandr-setup
NoDisplay=false
X-GNOME-Autostart-enabled=true
X-KDE-autostart-phase=2
X-KDE-autostart-after=panel
EOF

  systemctl daemon-reload
  systemctl enable vkms-virtual-display.service >/dev/null 2>&1 || true
}

configure_default_browser() {
  install -d -m 0700 -o "$GUEST_USER" -g "$GUEST_USER" \
    "/home/$GUEST_USER/.config"
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --set x-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  update-alternatives --set gnome-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  if [[ "$DESKTOP_ID" == "xfce" ]]; then
    install -d -m 0700 -o "$GUEST_USER" -g "$GUEST_USER" "/home/$GUEST_USER/.config/xfce4"
    cat > "/home/$GUEST_USER/.config/xfce4/helpers.rc" <<'EOF'
WebBrowser=google-chrome
MailReader=thunderbird
TerminalEmulator=xfce4-terminal
FileManager=thunar
EOF
    chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config/xfce4/helpers.rc"
  fi
  cat > "/home/$GUEST_USER/.config/mimeapps.list" <<'EOF'
[Default Applications]
x-scheme-handler/http=google-chrome.desktop
x-scheme-handler/https=google-chrome.desktop
text/html=google-chrome.desktop
application/xhtml+xml=google-chrome.desktop
x-scheme-handler/about=google-chrome.desktop
x-scheme-handler/unknown=google-chrome.desktop
EOF
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config/mimeapps.list"
}

install_beagle_web_apps() {
  local app_dir="/usr/local/share/applications"
  local launchpad="/usr/local/share/beagle/beagle-launchpad.html"
  install -d -m 0755 "$app_dir"
  install -d -m 0755 /usr/local/share/beagle

  create_web_app() {
    local file="$1"
    local name="$2"
    local url="$3"
    local icon="$4"
    cat > "$app_dir/$file" <<EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=${name}
Exec=google-chrome --app=${url} --new-window --disable-session-crashed-bubble --no-first-run
Icon=${icon}
Categories=Network;Office;Utility;
StartupNotify=true
NoDisplay=false
EOF
  }

  create_web_app beagle-chatgpt.desktop "ChatGPT" "https://chatgpt.com" google-chrome
  create_web_app beagle-microsoft-365.desktop "Microsoft 365" "https://www.office.com" libreoffice-startcenter
  create_web_app beagle-google-workspace.desktop "Google Workspace" "https://workspace.google.com/dashboard" google-chrome
  create_web_app beagle-gmail.desktop "Gmail" "https://mail.google.com" internet-mail
  create_web_app beagle-whatsapp.desktop "WhatsApp Web" "https://web.whatsapp.com" internet-chat
  create_web_app beagle-discord.desktop "Discord" "https://discord.com/app" internet-chat
  create_web_app beagle-youtube.desktop "YouTube" "https://www.youtube.com" applications-multimedia

  cat > "$launchpad" <<'EOF'
<!doctype html>
<html lang="de">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Beagle Launchpad</title>
  <style>
    :root {
      color-scheme: dark;
      --bg: #070b14;
      --panel: rgba(14, 20, 36, .82);
      --line: rgba(0, 245, 255, .28);
      --text: #e8f4f8;
      --muted: #8da3b3;
      --cyan: #00f5ff;
      --pink: #ff006e;
      --violet: #7c3cff;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      font-family: "IBM Plex Sans", "Segoe UI", system-ui, sans-serif;
      background:
        radial-gradient(circle at 18% 12%, rgba(124, 60, 255, .28), transparent 34%),
        radial-gradient(circle at 86% 18%, rgba(0, 245, 255, .18), transparent 30%),
        linear-gradient(135deg, #070b14 0%, #10172a 48%, #090d18 100%);
      color: var(--text);
      padding: 40px;
    }
    header { max-width: 1040px; margin: 0 auto 28px; }
    h1 { margin: 0 0 8px; font-size: clamp(34px, 5vw, 64px); line-height: .95; letter-spacing: 0; }
    p { margin: 0; color: var(--muted); font-size: 18px; }
    main { max-width: 1040px; margin: 0 auto; display: grid; grid-template-columns: repeat(auto-fit, minmax(210px, 1fr)); gap: 14px; }
    a {
      min-height: 112px;
      border: 1px solid var(--line);
      background: var(--panel);
      color: var(--text);
      text-decoration: none;
      border-radius: 8px;
      padding: 18px;
      display: flex;
      flex-direction: column;
      justify-content: space-between;
      box-shadow: 0 20px 60px rgba(0,0,0,.22);
    }
    a:hover { border-color: var(--cyan); transform: translateY(-1px); }
    strong { font-size: 19px; }
    span { color: var(--muted); }
    .hot strong { color: var(--cyan); }
    .work strong { color: #fff; }
    .ai strong { color: var(--pink); }
  </style>
</head>
<body>
  <header>
    <h1>Beagle Cyberpunk</h1>
    <p>Apps, AI, Cloud und Tools direkt startklar.</p>
  </header>
  <main>
    <a class="hot" href="https://chatgpt.com"><strong>ChatGPT</strong><span>AI Assistant</span></a>
    <a class="work" href="https://www.office.com"><strong>Microsoft 365</strong><span>Word, Excel, PowerPoint Web</span></a>
    <a class="work" href="https://workspace.google.com/dashboard"><strong>Google Workspace</strong><span>Docs, Drive, Meet</span></a>
    <a class="work" href="https://mail.google.com"><strong>Gmail</strong><span>Mail im Browser</span></a>
    <a class="ai" href="https://discord.com/app"><strong>Discord</strong><span>Community & Voice</span></a>
    <a class="ai" href="https://web.whatsapp.com"><strong>WhatsApp</strong><span>Messaging</span></a>
    <a class="hot" href="https://www.youtube.com"><strong>YouTube</strong><span>Video & Lernen</span></a>
    <a class="work" href="http://localhost:47990"><strong>Beagle Stream</strong><span>Local Stream Server</span></a>
  </main>
</body>
</html>
EOF

  cat > "$app_dir/beagle-launchpad.desktop" <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Beagle Launchpad
Exec=google-chrome --app=file:///usr/local/share/beagle/beagle-launchpad.html --new-window --disable-session-crashed-bubble --no-first-run
Icon=preferences-desktop-launch-feedback
Categories=Utility;Network;Office;
StartupNotify=true
NoDisplay=false
EOF
}

configure_lightdm_greeter() {
  local theme_name="Adwaita"
  local icon_theme="breeze-dark"
  local font_name="IBM Plex Sans 12"

  install -d -m 0755 /etc/lightdm/lightdm-gtk-greeter.conf.d
  if [[ "$DESKTOP_THEME_VARIANT" == "cyberpunk" ]]; then
    theme_name="Adwaita-dark"
    icon_theme="breeze-dark"
  elif [[ "$DESKTOP_THEME_VARIANT" == "windows" ]]; then
    theme_name="Adwaita-dark"
    icon_theme="breeze"
    font_name="Segoe UI 11"
  fi
  cat > /etc/lightdm/lightdm-gtk-greeter.conf.d/60-beagle-branding.conf <<EOF
[greeter]
theme-name=${theme_name}
icon-theme-name=${icon_theme}
font-name=${font_name}
cursor-theme-name=breeze_snow
cursor-theme-size=24
clock-format=%H:%M
panel-position=top
indicators=~host;~spacer;~clock;~spacer;~session;~power
EOF
  if [[ -n "$BEAGLE_WALLPAPER_PATH" && -f "$BEAGLE_WALLPAPER_PATH" ]]; then
    printf 'background=%s\n' "$BEAGLE_WALLPAPER_PATH" >> /etc/lightdm/lightdm-gtk-greeter.conf.d/60-beagle-branding.conf
  fi
}

configure_plasma_profile() {
  local autostart_file=""
  local apply_script=""
  local look_and_feel="org.kde.breeze.desktop"

  [[ "$DESKTOP_ID" == plasma* ]] || return 0
  if [[ "$DESKTOP_THEME_VARIANT" == "cyberpunk" ]]; then
    look_and_feel="org.kde.breezedark.desktop"
  fi

  install -d -m 0755 /etc/xdg/autostart "$BEAGLE_WALLPAPER_DIR" /usr/local/lib/beagle
  install -d -m 0700 -o "$GUEST_USER" -g "$GUEST_USER" \
    "/home/$GUEST_USER/.config" \
    "/home/$GUEST_USER/.config/autostart" \
    "/home/$GUEST_USER/.local/bin" \
    "/home/$GUEST_USER/.local/state/beagle" \
    "/home/$GUEST_USER/.local/share/color-schemes"

  # --- Beagle Cyberpunk Color Scheme ---
  # Full KDE .colors file: Dark Navy base + Electric Cyan accent + Neon Magenta secondary.
  # Applied when DESKTOP_THEME_VARIANT==cyberpunk; replaces generic BreezeDark.
  cat > "/home/$GUEST_USER/.local/share/color-schemes/BeagleCyberpunk.colors" <<'EOF'
[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0

[Colors:Button]
BackgroundAlternate=24,30,52
BackgroundNormal=18,24,42
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=110,140,160
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=232,244,248
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[Colors:Complementary]
BackgroundAlternate=10,14,26
BackgroundNormal=8,12,22
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=100,130,150
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=232,244,248
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[Colors:Header]
BackgroundAlternate=12,16,28
BackgroundNormal=8,12,22
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=100,130,150
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=232,244,248
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[Colors:Selection]
BackgroundAlternate=75,0,145
BackgroundNormal=0,210,225
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=110,140,160
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=8,12,22
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[Colors:Tooltip]
BackgroundAlternate=12,16,28
BackgroundNormal=8,12,22
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=100,130,150
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=232,244,248
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[Colors:View]
BackgroundAlternate=16,20,36
BackgroundNormal=10,14,26
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=100,130,150
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=232,244,248
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[Colors:Window]
BackgroundAlternate=18,22,38
BackgroundNormal=10,14,26
DecorationFocus=0,245,255
DecorationHover=255,0,110
ForegroundActive=255,255,255
ForegroundInactive=100,130,150
ForegroundLink=0,245,255
ForegroundNegative=255,80,80
ForegroundNeutral=255,200,0
ForegroundNormal=232,244,248
ForegroundPositive=80,255,140
ForegroundVisited=180,0,220

[General]
ColorScheme=BeagleCyberpunk
Name=Beagle Cyberpunk
shadeSortColumn=true

[KDE]
contrast=7
EOF
  chown "$GUEST_USER:$GUEST_USER" \
    "/home/$GUEST_USER/.local/share/color-schemes/BeagleCyberpunk.colors"

  # --- BeagleWindows color scheme (Win10/11 dark hybrid with blue accent) ---
  cat > "/home/$GUEST_USER/.local/share/color-schemes/BeagleWindows.colors" <<'EOF'
[ColorEffects:Disabled]
Color=56,56,56
ColorAmount=0
ColorEffect=0
ContrastAmount=0.65
ContrastEffect=1
IntensityAmount=0.1
IntensityEffect=2

[ColorEffects:Inactive]
ChangeSelectionColor=true
Color=112,111,110
ColorAmount=0.025
ColorEffect=2
ContrastAmount=0.1
ContrastEffect=2
Enable=false
IntensityAmount=0
IntensityEffect=0

[Colors:Button]
BackgroundAlternate=60,60,60
BackgroundNormal=48,48,48
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=160,160,160
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[Colors:Complementary]
BackgroundAlternate=32,32,32
BackgroundNormal=28,28,28
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=140,140,140
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[Colors:Header]
BackgroundAlternate=32,32,32
BackgroundNormal=28,28,28
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=140,140,140
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[Colors:Selection]
BackgroundAlternate=0,90,160
BackgroundNormal=0,120,212
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=200,220,255
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[Colors:Tooltip]
BackgroundAlternate=36,36,36
BackgroundNormal=32,32,32
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=140,140,140
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[Colors:View]
BackgroundAlternate=30,30,30
BackgroundNormal=28,28,28
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=140,140,140
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[Colors:Window]
BackgroundAlternate=30,30,30
BackgroundNormal=28,28,28
DecorationFocus=0,120,212
DecorationHover=0,120,212
ForegroundActive=255,255,255
ForegroundInactive=140,140,140
ForegroundLink=66,183,244
ForegroundNegative=255,100,80
ForegroundNeutral=255,200,0
ForegroundNormal=255,255,255
ForegroundPositive=80,220,100
ForegroundVisited=180,120,255

[General]
ColorScheme=BeagleWindows
Name=Beagle Windows
shadeSortColumn=true

[KDE]
contrast=7
EOF
  chown "$GUEST_USER:$GUEST_USER" \
    "/home/$GUEST_USER/.local/share/color-schemes/BeagleCyberpunk.colors" \
    "/home/$GUEST_USER/.local/share/color-schemes/BeagleWindows.colors"

  cat > "/home/$GUEST_USER/.config/kscreenlockerrc" <<'EOF'
[Daemon]
Autolock=false
LockOnResume=false
Timeout=0
EOF

  # Disable KDE splash screen for faster login (no animated splash in stream)
  cat > "/home/$GUEST_USER/.config/ksplashrc" <<'EOF'
[KSplash]
Engine=none
Theme=none
EOF

  cat > "/home/$GUEST_USER/.config/powermanagementprofilesrc" <<'EOF'
[AC][DPMSControl]
idleTime=0

[AC][SuspendSession]
idleTime=0
suspendThenHibernate=false
suspendType=0

[Battery][DPMSControl]
idleTime=0

[Battery][SuspendSession]
idleTime=0
suspendThenHibernate=false
suspendType=0

[LowBattery][DPMSControl]
idleTime=0

[LowBattery][SuspendSession]
idleTime=0
suspendThenHibernate=false
suspendType=0
EOF

  if [[ "$DESKTOP_THEME_VARIANT" == "cyberpunk" ]]; then
    cat > "/home/$GUEST_USER/.config/kdeglobals" <<'EOF'
[General]
ColorScheme=BeagleCyberpunk
font=IBM Plex Sans,10,-1,5,50,0,0,0,0,0
fixed=Hack,10,-1,5,50,0,0,0,0,0
smallestReadableFont=IBM Plex Sans,8,-1,5,50,0,0,0,0,0
toolBarFont=IBM Plex Sans,9,-1,5,50,0,0,0,0,0
menuFont=IBM Plex Sans,10,-1,5,50,0,0,0,0,0
XftHintStyle=hintfull
XftSubPixel=rgb
XftAntialias=1

[Icons]
Theme=breeze-dark

[KDE]
LookAndFeelPackage=org.kde.breezedark.desktop
widgetStyle=Breeze
SingleClick=true
EOF
  elif [[ "$DESKTOP_THEME_VARIANT" == "windows" ]]; then
    cat > "/home/$GUEST_USER/.config/kdeglobals" <<'EOF'
[General]
ColorScheme=BeagleWindows
font=IBM Plex Sans,10,-1,5,50,0,0,0,0,0
fixed=Hack,10,-1,5,50,0,0,0,0,0
smallestReadableFont=IBM Plex Sans,8,-1,5,50,0,0,0,0,0
toolBarFont=IBM Plex Sans,9,-1,5,50,0,0,0,0,0
menuFont=IBM Plex Sans,10,-1,5,50,0,0,0,0,0
XftHintStyle=hintfull
XftSubPixel=rgb
XftAntialias=1

[KDE]
LookAndFeelPackage=org.kde.breezedark.desktop
widgetStyle=Breeze
SingleClick=false

[KScreen]
ScaleFactor=1
EOF
  else
    cat > "/home/$GUEST_USER/.config/kdeglobals" <<'EOF'
[General]
ColorScheme=BreezeLight
font=IBM Plex Sans,10,-1,5,50,0,0,0,0,0
fixed=Hack,10,-1,5,50,0,0,0,0,0
smallestReadableFont=IBM Plex Sans,8,-1,5,50,0,0,0,0,0
toolBarFont=IBM Plex Sans,9,-1,5,50,0,0,0,0,0
menuFont=IBM Plex Sans,10,-1,5,50,0,0,0,0,0
XftHintStyle=hintfull
XftSubPixel=rgb
XftAntialias=1

[KDE]
LookAndFeelPackage=org.kde.breeze.desktop
widgetStyle=Breeze
SingleClick=true
EOF
  fi

  # kwinrc — windows variant uses Win11-style rounding + snappier animations
  if [[ "$DESKTOP_THEME_VARIANT" == "windows" ]]; then
    cat > "/home/$GUEST_USER/.config/kwinrc" <<'EOF'
[$Version]
update_info=kwin.upd:auto-bordersize,kwin.upd:animation-speed

[Compositing]
Enabled=true
OpenGLIsUnsafe=false
AnimationDurationFactor=0.3
Backend=OpenGL
VSync=true
TearingPrevention=2
LatencyPolicy=Low

[Effect-Blur]
NoiseStrength=0

[MouseBindings]
CommandAllKey=Meta

[Plugins]
blurEnabled=true
contrastEnabled=true
kwin4_effect_fadeEnabled=true
kwin4_effect_loginEnabled=true
kwin4_effect_maximizeEnabled=true
kwin4_effect_scaleEnabled=true
slidingpopupsEnabled=true
snapEnabled=true

[Windows]
BorderlessMaximizedWindows=false
FocusPolicy=ClickToFocus
Placement=Smart
AutoRaise=false
DelayFocusInterval=0
DragToMaximize=false
ElectricBorderDelay=150
ElectricBorderCooldown=350

[Desktops]
Number=1
Rows=1

[Animations]
speed=5

[NightColor]
Active=false

[org.kde.kdecoration2]
BorderSize=Normal
ButtonsOnLeft=
ButtonsOnRight=NMX
CloseOnDoubleClickOnMenu=false
library=org.kde.breeze
plugin=org.kde.breeze
EOF
  else
    cat > "/home/$GUEST_USER/.config/kwinrc" <<'EOF'
[$Version]
update_info=kwin.upd:auto-bordersize,kwin.upd:animation-speed

[Compositing]
Enabled=true
OpenGLIsUnsafe=false
AnimationDurationFactor=0.5

[Effect-Blur]
NoiseStrength=0

[MouseBindings]
CommandAllKey=Meta

[Plugins]
blurEnabled=true
contrastEnabled=true
kwin4_effect_fadeEnabled=true
kwin4_effect_loginEnabled=true
kwin4_effect_maximizeEnabled=true
kwin4_effect_scaleEnabled=true
slidingpopupsEnabled=true

[Windows]
BorderlessMaximizedWindows=false
FocusPolicy=ClickToFocus
Placement=Smart
AutoRaise=false
DelayFocusInterval=0
DragToMaximize=false
ElectricBorderDelay=150
ElectricBorderCooldown=350

[Desktops]
Number=1
Rows=1

[Animations]
speed=3

[NightColor]
Active=false

[org.kde.kdecoration2]
BorderSize=Normal
ButtonsOnLeft=
ButtonsOnRight=NMX
CloseOnDoubleClickOnMenu=false
library=org.kde.breeze
plugin=org.kde.breeze
EOF
  fi

  cat > "/home/$GUEST_USER/.config/plasmashellrc" <<'EOF'
[PlasmaViews][Panel 2][Defaults]
thickness=48

[PlasmaViews][Panel 2][Horizontal1920]
thickness=48

[Updates]
beagleUsabilityProfile=1
EOF

  cat > "/home/$GUEST_USER/.config/plasma-org.kde.plasma.desktop-appletsrc" <<EOF
[ActionPlugins][0]
RightButton;NoModifier=org.kde.contextmenu
wheel:Vertical;NoModifier=org.kde.switchdesktop

[ActionPlugins][1]
RightButton;NoModifier=org.kde.contextmenu

[Containments][1]
ItemGeometries-1920x1080=
ItemGeometriesHorizontal=
activityId=
formfactor=0
immutability=1
lastScreen=0
location=0
plugin=org.kde.plasma.desktop
wallpaperplugin=org.kde.image

[Containments][1][Wallpaper][org.kde.image][General]
Image=file://${BEAGLE_WALLPAPER_PATH}

[Containments][2]
activityId=
formfactor=2
immutability=1
lastScreen=0
location=4
plugin=org.kde.panel
wallpaperplugin=org.kde.image

[Containments][2][Applets][3]
immutability=1
plugin=org.kde.plasma.kickoff

[Containments][2][Applets][3][Configuration][General]
favoritesPortedToKAstats=true
favorites=applications:beagle-launchpad.desktop,applications:google-chrome.desktop,applications:beagle-chatgpt.desktop,applications:org.kde.dolphin.desktop,applications:thunderbird.desktop,applications:libreoffice-writer.desktop,applications:org.kde.okular.desktop,applications:code.desktop,applications:beagle-ai.desktop,applications:systemsettings.desktop,applications:org.kde.discover.desktop

[Containments][2][Applets][4]
immutability=1
plugin=org.kde.plasma.icontasks

[Containments][2][Applets][4][Configuration][General]
launchers=applications:beagle-launchpad.desktop,applications:google-chrome.desktop,applications:beagle-chatgpt.desktop,applications:org.kde.dolphin.desktop,applications:thunderbird.desktop,applications:libreoffice-writer.desktop,applications:org.kde.okular.desktop,applications:org.kde.spectacle.desktop,applications:code.desktop,applications:beagle-ai.desktop,applications:systemsettings.desktop,applications:org.kde.discover.desktop
groupingStrategy=0
middleClickAction=NewInstance
wheelEnabled=true
showOnlyCurrentScreen=false
showOnlyCurrentDesktop=false
showOnlyCurrentActivity=false
highlightWindows=true

[Containments][2][Applets][5]
immutability=1
plugin=org.kde.plasma.marginsseparator

[Containments][2][Applets][6]
immutability=1
plugin=org.kde.plasma.systemtray

[Containments][2][Applets][6][Configuration][General]
extraItems=org.kde.plasma.networkmanagement,org.kde.plasma.volume,org.kde.plasma.battery,org.kde.plasma.bluetooth,org.kde.plasma.notifications
knownItems=org.kde.plasma.networkmanagement,org.kde.plasma.volume,org.kde.plasma.battery,org.kde.plasma.bluetooth,org.kde.plasma.notifications

[Containments][2][Applets][7]
immutability=1
plugin=org.kde.plasma.digitalclock

[Containments][2][Applets][7][Configuration][Appearance]
showDate=true
showSeconds=false
use24hFormat=2

[Containments][2][Applets][7][Configuration][Calendar]
firstDayOfWeek=1

[Containments][2][Applets][8]
immutability=1
plugin=org.kde.plasma.showdesktop

[Containments][2][General]
AppletOrder=3;4;5;6;7;8

[ScreenMapping]
itemsOnDisabledScreens=
screenMapping=
EOF

  cat > /usr/local/bin/beagle-plasma-desktop-repair <<'EOF'
#!/usr/bin/env bash
set -u

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
export DBUS_SESSION_BUS_ADDRESS="${DBUS_SESSION_BUS_ADDRESS:-unix:path=${XDG_RUNTIME_DIR}/bus}"

if ! pgrep -u "$(id -u)" -x kwin_x11 >/dev/null 2>&1; then
  nohup kwin_x11 --replace >/tmp/beagle-kwin-repair.log 2>&1 &
fi

sleep 1

if ! pgrep -u "$(id -u)" -x plasmashell >/dev/null 2>&1; then
  nohup plasmashell --no-respawn >/tmp/beagle-plasmashell-repair.log 2>&1 &
fi
EOF
  chmod 0755 /usr/local/bin/beagle-plasma-desktop-repair

  cat > "/home/$GUEST_USER/.config/autostart/beagle-plasma-desktop-repair.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Beagle Plasma Desktop Repair
Exec=/usr/local/bin/beagle-plasma-desktop-repair
OnlyShowIn=KDE;
X-KDE-autostart-phase=1
NoDisplay=true
EOF

  # --- Beagle AI launcher ---
  # Opens a curated AI assistant (ChatGPT / local Ollama) in an app-mode Chrome window.
  # Pin is added to the taskbar via the icontasks launchers= line above.
  # Keyboard shortcut Meta+A is configured in kglobalshortcutsrc below.
  cat > /usr/local/bin/beagle-ai <<'EOF'
#!/usr/bin/env bash
# Beagle AI launcher — opens AI assistant in a clean standalone window.
# Priority: local Ollama → ChatGPT (web fallback)
OLLAMA_URL="http://localhost:11434"
AI_WEB_URL="https://chatgpt.com"

export DISPLAY="${DISPLAY:-:0}"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"

if curl -fsS --connect-timeout 2 "${OLLAMA_URL}/api/tags" >/dev/null 2>&1; then
  TARGET_URL="http://localhost:3000"  # Open WebUI on port 3000 if available
  if ! curl -fsS --connect-timeout 1 "${TARGET_URL}" >/dev/null 2>&1; then
    TARGET_URL="${OLLAMA_URL}"
  fi
else
  TARGET_URL="${AI_WEB_URL}"
fi

if command -v google-chrome >/dev/null 2>&1; then
  exec google-chrome --app="${TARGET_URL}" --new-window \
    --window-size=900,700 --window-position=200,100 \
    --disable-session-crashed-bubble --no-first-run 2>/dev/null
elif command -v chromium-browser >/dev/null 2>&1; then
  exec chromium-browser --app="${TARGET_URL}" --new-window \
    --window-size=900,700 2>/dev/null
else
  exec xdg-open "${TARGET_URL}" 2>/dev/null
fi
EOF
  chmod 0755 /usr/local/bin/beagle-ai

  cat > /usr/share/applications/beagle-ai.desktop <<'EOF'
[Desktop Entry]
Version=1.0
Type=Application
Name=Beagle AI
Comment=Open AI assistant — local Ollama or ChatGPT
Exec=/usr/local/bin/beagle-ai
Icon=google-chrome
Categories=Network;AI;Utility;
StartupNotify=true
NoDisplay=false
EOF

  # Windows-style keyboard shortcuts + Beagle AI shortcut
  cat >> "/home/$GUEST_USER/.config/kglobalshortcutsrc" <<'EOF'

[beagle-ai.desktop]
_launch=Meta+A,none,Beagle AI

[org.kde.dolphin.desktop]
_launch=Meta+E,none,File Manager

[plasmashell]
show-desktop=Meta+D,none,Show Desktop

[krunner]
_launch=Alt+F2\tMeta+R,none,KRunner

[systemsettings.desktop]
_launch=Meta+I,none,System Settings
EOF

  # Cursor theme: breeze_snow (white, highly visible in streaming)
  cat > "/home/$GUEST_USER/.config/kcminputrc" <<'EOF'
[Mouse]
cursorTheme=breeze_snow
cursorSize=24
EOF
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config/kcminputrc"

  chown "$GUEST_USER:$GUEST_USER" \
    "/home/$GUEST_USER/.config/kscreenlockerrc" \
    "/home/$GUEST_USER/.config/ksplashrc" \
    "/home/$GUEST_USER/.config/powermanagementprofilesrc" \
    "/home/$GUEST_USER/.config/kdeglobals" \
    "/home/$GUEST_USER/.config/kwinrc" \
    "/home/$GUEST_USER/.config/plasmashellrc" \
    "/home/$GUEST_USER/.config/plasma-org.kde.plasma.desktop-appletsrc" \
    "/home/$GUEST_USER/.config/autostart/beagle-plasma-desktop-repair.desktop" \
    "/home/$GUEST_USER/.config/kglobalshortcutsrc"

  # Konsole cyberpunk terminal profile
  mkdir -p "/home/$GUEST_USER/.local/share/konsole"
  cat > "/home/$GUEST_USER/.local/share/konsole/Beagle.profile" <<'EOF'
[Appearance]
ColorScheme=BeagleCyberpunk
Font=Hack,12,-1,5,50,0,0,0,0,0
LineSpacing=2

[General]
Command=/bin/bash
Name=Beagle
Parent=FALLBACK/
StartInCurrentSessionDir=false

[Interaction Options]
AutoCopySelectedText=true
TrimLeadingWhitespacesInSelectedText=true

[Scrolling]
ScrollBarPosition=2
ScrollFullPage=false
HistorySize=5000

[Terminal Features]
BlinkingCursorEnabled=true
CursorShape=1
EOF

  cat > "/home/$GUEST_USER/.local/share/konsole/BeagleCyberpunk.colorscheme" <<'EOF'
[Background]
Color=10,14,26

[BackgroundFaint]
Color=10,14,26

[BackgroundIntense]
Color=20,28,52

[Color0]
Color=10,14,26

[Color0Faint]
Color=18,22,35

[Color0Intense]
Color=80,90,120

[Color1]
Color=255,0,110

[Color1Intense]
Color=255,50,150

[Color2]
Color=0,200,130

[Color2Intense]
Color=0,245,180

[Color3]
Color=255,185,0

[Color3Intense]
Color=255,215,50

[Color4]
Color=0,120,255

[Color4Intense]
Color=0,160,255

[Color5]
Color=200,0,255

[Color5Intense]
Color=220,80,255

[Color6]
Color=0,245,255

[Color6Intense]
Color=80,255,255

[Color7]
Color=200,220,230

[Color7Intense]
Color=232,244,248

[Foreground]
Color=232,244,248

[ForegroundFaint]
Color=150,175,190

[ForegroundIntense]
Color=255,255,255

[General]
Anchor=0.5,0.5
Blur=false
ColorRandomization=false
Description=Beagle Cyberpunk
FillStyle=Tile
Opacity=0.92
Wallpaper=

[Cursor]
CustomCursorColor=0,245,255
UseCustomCursorColor=true
EOF

  cat > "/home/$GUEST_USER/.config/konsolerc" <<'EOF'
[Desktop Entry]
DefaultProfile=Beagle.profile

[MainWindow]
MenuBar=Disabled
StatusBar=Disabled
ToolBarsMovable=Disabled
EOF

  chown -R "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.local/share/konsole"
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config/konsolerc"

  apply_script="/usr/local/lib/beagle/beagle-plasma-profile-apply"
  cat > "$apply_script" <<EOF
#!/usr/bin/env bash
set -euo pipefail

MARKER="\$HOME/.local/state/beagle/plasma-profile-applied"
WALLPAPER_PATH="${BEAGLE_WALLPAPER_PATH}"
LOOK_AND_FEEL="${look_and_feel}"
THEME_VARIANT="${DESKTOP_THEME_VARIANT}"
KWRITECONFIG_BIN=""

if [[ -f "\$MARKER" ]]; then
  exit 0
fi

KWRITECONFIG_BIN="\$(command -v kwriteconfig6 || command -v kwriteconfig5 || true)"

if command -v plasma-apply-lookandfeel >/dev/null 2>&1; then
  plasma-apply-lookandfeel -a "\$LOOK_AND_FEEL" >/dev/null 2>&1 || true
fi

if command -v plasma-apply-wallpaperimage >/dev/null 2>&1 && [[ -n "\$WALLPAPER_PATH" && -f "\$WALLPAPER_PATH" ]]; then
  plasma-apply-wallpaperimage "\$WALLPAPER_PATH" >/dev/null 2>&1 || true
fi

if [[ -n "\$KWRITECONFIG_BIN" ]]; then
  if [[ "\$THEME_VARIANT" == "cyberpunk" ]]; then
    "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key ColorScheme BeagleCyberpunk >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KDE --key LookAndFeelPackage org.kde.breezedark.desktop >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group Animations --key speed 3 >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group Compositing --key AnimationDurationFactor 0.5 >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KDE --key SingleClick true >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnLeft "" >/dev/null 2>&1 || true
  elif [[ "\$THEME_VARIANT" == "windows" ]]; then
    # Windows 10/11 hybrid — blue accent, double-click to open, close button on right
    "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key ColorScheme BeagleWindows >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KDE --key LookAndFeelPackage org.kde.breezedark.desktop >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group Animations --key speed 5 >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group Compositing --key AnimationDurationFactor 0.3 >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KDE --key SingleClick false >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnLeft "" >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KScreen --key ScaleFactor 1 >/dev/null 2>&1 || true
  else
    "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key ColorScheme BreezeLight >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KDE --key LookAndFeelPackage org.kde.breeze.desktop >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group Animations --key speed 3 >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group Compositing --key AnimationDurationFactor 0.5 >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kdeglobals --group KDE --key SingleClick true >/dev/null 2>&1 || true
    "\$KWRITECONFIG_BIN" --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnLeft "" >/dev/null 2>&1 || true
  fi
  "\$KWRITECONFIG_BIN" --file kscreenlockerrc --group Daemon --key Autolock false >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kscreenlockerrc --group Daemon --key LockOnResume false >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kscreenlockerrc --group Daemon --key Timeout 0 >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kwinrc --group Windows --key BorderlessMaximizedWindows false >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kwinrc --group org.kde.kdecoration2 --key ButtonsOnRight NMX >/dev/null 2>&1 || true
  # Single virtual desktop — no workspace-switching confusion while streaming
  "\$KWRITECONFIG_BIN" --file kwinrc --group Desktops --key Number 1 >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kwinrc --group Desktops --key Rows 1 >/dev/null 2>&1 || true
  # Font rendering: full hinting + sub-pixel for sharp text in H.264 streams
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key XftHintStyle hintfull >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key XftSubPixel rgb >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key XftAntialias 1 >/dev/null 2>&1 || true
  # IBM Plex Sans — Beagle brand font; improves stream text clarity vs default Noto Sans
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key font "IBM Plex Sans,10,-1,5,50,0,0,0,0,0" >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key fixed "Hack,10,-1,5,50,0,0,0,0,0" >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key toolBarFont "IBM Plex Sans,9,-1,5,50,0,0,0,0,0" >/dev/null 2>&1 || true
  "\$KWRITECONFIG_BIN" --file kdeglobals --group General --key menuFont "IBM Plex Sans,10,-1,5,50,0,0,0,0,0" >/dev/null 2>&1 || true
fi

if command -v beagle-plasma-desktop-repair >/dev/null 2>&1; then
  beagle-plasma-desktop-repair >/dev/null 2>&1 || true
fi

mkdir -p "\$(dirname "\$MARKER")"
touch "\$MARKER"
EOF
  chmod 0755 "$apply_script"

  autostart_file="/etc/xdg/autostart/beagle-plasma-profile.desktop"
  cat > "$autostart_file" <<EOF
[Desktop Entry]
Type=Application
Name=Beagle Plasma Profile
Exec=${apply_script}
OnlyShowIn=KDE;
X-GNOME-Autostart-enabled=true
X-KDE-autostart-phase=2
X-KDE-autostart-after=panel
NoDisplay=false
EOF
}

post_completion_callback() {
  local callback_endpoint="${CALLBACK_URL}?restart=0"
  local attempt
  local -a curl_args

  for attempt in $(seq 1 20); do
    curl_args=(curl -fsS)
    mapfile -t tls_args < <(callback_tls_args)
    curl_args+=("${tls_args[@]}")
    if "${curl_args[@]}" \
      --connect-timeout 5 \
      --max-time 20 \
      --retry 2 \
      --retry-delay 2 \
      -X POST \
      "$callback_endpoint" >/dev/null
    then
      return 0
    fi
    sleep 5
  done

  return 1
}

wait_for_beagle_stream_server_ready() {
  local -a expected_ports=()

  if [[ -n "$BEAGLE_STREAM_SERVER_PORT" ]]; then
    expected_ports=("$BEAGLE_STREAM_SERVER_PORT" "$((BEAGLE_STREAM_SERVER_PORT + 1))")
  else
    expected_ports=("47984" "47990")
  fi

  for _ in {1..180}; do
    if systemctl is-active --quiet beagle-stream-server.service; then
      for port in "${expected_ports[@]}"; do
        if ss -H -ltn "( sport = :${port} )" 2>/dev/null | grep -q LISTEN; then
          return 0
        fi
      done
    fi
    if (( _ % 30 == 0 )); then
      /usr/local/bin/beagle-stream-server-healthcheck --repair-only >/dev/null 2>&1 || true
    fi
    sleep 2
  done

  return 1
}

if [[ ! -f "$DONE_FILE" ]]; then
  ensure_network_connectivity || true
  ensure_dns_resolution || true
  disable_cdrom_apt_sources
  repair_interrupted_dpkg

  echo 'lightdm shared/default-x-display-manager select lightdm' | debconf-set-selections
  apt_retry apt-get update -o Acquire::Retries=5
  apt_retry apt-get install -y --fix-missing --no-install-recommends \
    qemu-guest-agent \
    openssh-server \
    curl \
    ca-certificates \
    usbutils \
    xdg-utils \
    zenity
  repair_interrupted_dpkg
  systemctl enable --now qemu-guest-agent.service >/dev/null 2>&1 || true

  apt_retry apt-get install -y --fix-missing --no-install-recommends \
    openssh-server \
    xserver-xorg \
    x11-xserver-utils \
    lightdm \
    lightdm-gtk-greeter \
    accountsservice \
    pipewire \
    pipewire-pulse \
    wireplumber \
    pulseaudio-utils \
    logrotate \
    nftables \
    x11vnc \
    fonts-ibm-plex \
    fonts-hack-ttf
  repair_interrupted_dpkg
  if [[ -n "$DESKTOP_PACKAGES" ]]; then
    apt_retry apt-get install -y --fix-missing --no-install-recommends ${DESKTOP_PACKAGES}
    repair_interrupted_dpkg
  fi
  install_visual_studio_code_repo
  if [[ -n "$SOFTWARE_PACKAGES" ]]; then
    apt_retry apt-get install -y --fix-missing --no-install-recommends ${SOFTWARE_PACKAGES}
    repair_interrupted_dpkg
  fi
  configure_flatpak_flathub
  resolve_desktop_session

  TMPDIR_WORK="$(mktemp -d)"
  stream_runtime_variant="beagle-stream-server"
  stream_runtime_package_url="$BEAGLE_STREAM_SERVER_URL"
  BEAGLE_STREAM_SERVER_SHA256="${BEAGLE_STREAM_SERVER_SHA256:-}"
  BEAGLE_STREAM_SERVER_SHA256SUMS_URL="${BEAGLE_STREAM_SERVER_SHA256SUMS_URL:-${BEAGLE_STREAM_SERVER_URL%/*}/SHA256SUMS}"
  curl -fL \
    --retry 8 \
    --retry-delay 3 \
    --retry-connrefused \
    --retry-all-errors \
    --continue-at - \
    --speed-limit 5000 \
    --speed-time 30 \
    -o "$TMPDIR_WORK/beagle-stream-server.deb" \
    "$BEAGLE_STREAM_SERVER_URL"
  if [[ -z "$BEAGLE_STREAM_SERVER_SHA256" ]]; then
    curl -fL \
      --retry 8 \
      --retry-delay 3 \
      --retry-connrefused \
      --retry-all-errors \
      -o "$TMPDIR_WORK/SHA256SUMS" \
      "$BEAGLE_STREAM_SERVER_SHA256SUMS_URL"
    asset_name="${BEAGLE_STREAM_SERVER_URL##*/}"
    BEAGLE_STREAM_SERVER_SHA256="$(awk -v asset="$asset_name" '$2 == asset || $2 == "dist/" asset { print $1; exit }' "$TMPDIR_WORK/SHA256SUMS")"
    if [[ -z "$BEAGLE_STREAM_SERVER_SHA256" ]]; then
      echo "Checksum entry for ${asset_name} missing in ${BEAGLE_STREAM_SERVER_SHA256SUMS_URL}" >&2
      exit 1
    fi
  fi
  if [[ -n "$BEAGLE_STREAM_SERVER_SHA256" ]]; then
    actual_sha="$(sha256sum "$TMPDIR_WORK/beagle-stream-server.deb" | awk '{print $1}')"
    if [[ "$actual_sha" != "$BEAGLE_STREAM_SERVER_SHA256" ]]; then
      echo "Checksum mismatch for beagle-stream-server package: expected $BEAGLE_STREAM_SERVER_SHA256, got $actual_sha" >&2
      exit 1
    fi
  fi
  apt_retry apt-get install -y --no-install-recommends "$TMPDIR_WORK/beagle-stream-server.deb"
  repair_interrupted_dpkg
  write_stream_runtime_status "$stream_runtime_variant" "$stream_runtime_package_url"
  if [[ -x /usr/bin/beagle-stream-server ]]; then
    BEAGLE_STREAM_SERVER_EXEC=/usr/bin/beagle-stream-server
  else
    BEAGLE_STREAM_SERVER_EXEC="$(command -v beagle-stream-server 2>/dev/null || true)"
  fi
  if [[ -z "$BEAGLE_STREAM_SERVER_EXEC" || ! -x "$BEAGLE_STREAM_SERVER_EXEC" ]]; then
    echo "beagle-stream-server binary was not installed by stream runtime package" >&2
    exit 1
  fi
  configure_system_locale
  configure_keyboard_layout
  install_desktop_wallpaper
  configure_virtual_display_vkms
  install_google_chrome
  install_beagle_web_apps
  configure_lightdm_greeter

  install -d -m 0755 /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/60-beagle.conf <<EOF
[Seat:*]
autologin-user=${GUEST_USER}
autologin-session=${DESKTOP_SESSION_EFFECTIVE}
user-session=${DESKTOP_SESSION_EFFECTIVE}
greeter-session=lightdm-gtk-greeter
EOF

  install -d -m 0700 -o "$GUEST_USER" -g "$GUEST_USER" \
    "/home/$GUEST_USER/.config" \
    "/home/$GUEST_USER/.config/autostart" \
    "/home/$GUEST_USER/.config/beagle-stream-server" \
    "/home/$GUEST_USER/.local" \
    "/home/$GUEST_USER/.local/state" \
    "/home/$GUEST_USER/.local/state/wireplumber" \
    "/home/$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml"
  if [[ -d "/home/$GUEST_USER/.config/sunshine" && ! -e "/home/$GUEST_USER/.config/beagle-stream-server" ]]; then
    mv "/home/$GUEST_USER/.config/sunshine" "/home/$GUEST_USER/.config/beagle-stream-server"
  fi
  if [[ -e "/home/$GUEST_USER/.config/sunshine" && ! -L "/home/$GUEST_USER/.config/sunshine" ]]; then
    cp -a "/home/$GUEST_USER/.config/sunshine/." "/home/$GUEST_USER/.config/beagle-stream-server/" 2>/dev/null || true
    rm -rf "/home/$GUEST_USER/.config/sunshine"
  fi
  ln -sfn "/home/$GUEST_USER/.config/beagle-stream-server" "/home/$GUEST_USER/.config/sunshine"
  install -d -m 0755 /etc/X11/xorg.conf.d
  GUEST_UID="$(id -u "$GUEST_USER")"

  cat > /etc/X11/xorg.conf.d/20-beagle-software-cursor.conf <<'EOF'
Section "Device"
    Identifier "Beagle Virtio GPU Software Cursor"
    Driver "modesetting"
    Option "SWCursor" "true"
EndSection
EOF

  cat > /etc/X11/xorg.conf.d/90-beagle-ignore-virtual-input.conf <<'EOF'
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
EOF
  cat > /etc/X11/Xsession.d/19-beagle-lightdm-session-compat <<'EOF'
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
EOF
  chmod 0755 /etc/X11/Xsession.d/19-beagle-lightdm-session-compat

  cat > /etc/X11/Xsession.d/90-beagle-disable-display-idle <<'EOF'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
EOF
  chmod 0755 /etc/X11/Xsession.d/90-beagle-disable-display-idle

  cat > "/home/$GUEST_USER/.xprofile" <<'EOF'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
EOF
  chmod 0755 "/home/$GUEST_USER/.xprofile"

  cat > "/home/$GUEST_USER/.config/beagle-stream-server/beagle-stream-server.conf" <<EOF
sunshine_name = ${GUEST_USER}-beagle-stream-server
min_log_level = info
origin_web_ui_allowed = ${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}
origin_pin_allowed = ${BEAGLE_STREAM_SERVER_ORIGIN_WEB_UI_ALLOWED}
encoder = software
sw_preset = ultrafast
sw_tune = zerolatency
capture = x11
hevc_mode = 0
av1_mode = 0
minimum_fps_target = 30
max_bitrate = 35000
ping_timeout = 120000
$( if [[ -n "$BEAGLE_STREAM_SERVER_PORT" ]]; then printf 'port = %s\n' "$BEAGLE_STREAM_SERVER_PORT"; fi )
$( if [[ -n "$BEAGLE_STREAM_SERVER_PORT" ]]; then printf 'file_state = /home/%s/.config/beagle-stream-server/sunshine_state.json\n' "$GUEST_USER"; fi )
EOF
  cp "/home/$GUEST_USER/.config/beagle-stream-server/beagle-stream-server.conf" "/home/$GUEST_USER/.config/beagle-stream-server/sunshine.conf"

  cat > "/home/$GUEST_USER/.config/beagle-stream-server/apps.json" <<'EOF'
{
  "env": {
    "PATH": "$(PATH):$(HOME)/.local/bin"
  },
  "apps": [
    {
      "name": "Desktop",
      "image-path": "desktop.png"
    }
  ]
}
EOF

  python3 - "/home/$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" <<'EOF'
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
EOF
  ln -sfn "/home/$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" "/home/$GUEST_USER/.config/beagle-stream-server/beagle_stream_server_state.json"
  chown -h "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config/beagle-stream-server/beagle_stream_server_state.json" >/dev/null 2>&1 || true
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" >/dev/null 2>&1 || true
  chmod 0600 "/home/$GUEST_USER/.config/beagle-stream-server/sunshine_state.json" >/dev/null 2>&1 || true

  if [[ "$DESKTOP_ID" == "xfce" ]]; then
  cat > "/home/$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="use_compositing" type="bool" value="false"/>
    <property name="vblank_mode" type="string" value="off"/>
  </property>
</channel>
EOF

  cat > "/home/$GUEST_USER/.config/autostart/light-locker.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Light Locker
Exec=light-locker
Hidden=true
X-GNOME-Autostart-enabled=false
EOF

  cat > "/home/$GUEST_USER/.config/autostart/xfce4-power-manager.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=XFCE Power Manager
Hidden=true
EOF

  cat > "/home/$GUEST_USER/.config/autostart/xfce4-screensaver.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=XFCE Screensaver
Hidden=true
EOF
  fi

  chown -R "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config" "/home/$GUEST_USER/.local"
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.xprofile"
  configure_default_browser
  configure_plasma_profile

  cat > /etc/systemd/system/beagle-stream-server.service <<EOF
[Unit]
Description=Beagle Beagle Stream Server
After=network-online.target display-manager.service graphical.target sound.target
Wants=network-online.target
StartLimitIntervalSec=0

[Service]
Type=simple
User=${GUEST_USER}
Group=${GUEST_USER}
SupplementaryGroups=video render input
CapabilityBoundingSet=CAP_SYS_ADMIN CAP_SYS_NICE CAP_SETPCAP CAP_DAC_OVERRIDE CAP_CHOWN CAP_FOWNER CAP_KILL CAP_SETGID CAP_SETUID
AmbientCapabilities=CAP_SYS_ADMIN CAP_SYS_NICE
LimitNICE=-15
Nice=-10
CPUWeight=10000
Environment=HOME=/home/${GUEST_USER}
Environment=XDG_CONFIG_HOME=/home/${GUEST_USER}/.config
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${GUEST_USER}/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/${GUEST_UID}
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${GUEST_UID}/bus
Environment=PULSE_SERVER=unix:/run/user/${GUEST_UID}/pulse/native
EnvironmentFile=-/etc/beagle/stream-server.env
ExecStartPre=/usr/local/bin/beagle-stream-server-preflight
ExecStartPre=/bin/bash -lc 'pulse_socket="/run/user/${GUEST_UID}/pulse/native"; for _ in {1..180}; do if [[ -S /tmp/.X11-unix/X0 && -s /home/${GUEST_USER}/.Xauthority && -d /run/user/${GUEST_UID} && -S /run/user/${GUEST_UID}/bus && -S "\$pulse_socket" ]] && DISPLAY=:0 XAUTHORITY=/home/${GUEST_USER}/.Xauthority xrandr --query >/dev/null 2>&1; then sleep 5; exit 0; fi; sleep 1; done; echo "Timed out waiting for an active graphical/audio session on :0" >&2; exit 1'
ExecStart=${BEAGLE_STREAM_SERVER_EXEC}
Restart=always
RestartSec=2
TimeoutStartSec=210

[Install]
WantedBy=graphical.target
EOF

  install -d -m 0755 /etc/beagle
  write_beagle_stream_server_broker_env
  cat > /etc/beagle/beagle-stream-server-healthcheck.env <<EOF
BEAGLE_STREAM_SERVER_USER=${BEAGLE_STREAM_SERVER_USER}
BEAGLE_STREAM_SERVER_PASSWORD=${BEAGLE_STREAM_SERVER_PASSWORD}
BEAGLE_STREAM_SERVER_PORT=${BEAGLE_STREAM_SERVER_PORT}
GUEST_USER=${GUEST_USER}
GUEST_UID=${GUEST_UID}
EOF
  chmod 0600 /etc/beagle/beagle-stream-server-healthcheck.env

  cat > /usr/local/bin/beagle-stream-server-preflight <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

stream_port="${BEAGLE_STREAM_SERVER_PORT:-50000}"
if ! [[ "$stream_port" =~ ^[0-9]+$ ]]; then
  stream_port="50000"
fi
rtsp_port="$((stream_port + 21))"

# Legacy Sunshine or BeagleStream helper instances can keep RTSP bound.
pkill -x sunshine >/dev/null 2>&1 || true
pkill -x beagle-stream-server >/dev/null 2>&1 || true
sleep 1

# Best-effort cleanup for any remaining listener before start.
if command -v fuser >/dev/null 2>&1; then
  fuser -k "${rtsp_port}/tcp" >/dev/null 2>&1 || true
fi

if ss -H -ltn "( sport = :${rtsp_port} )" 2>/dev/null | grep -q .; then
  echo "beagle-stream-server-preflight: RTSP port ${rtsp_port} still busy" >&2
  exit 1
fi
EOF
  chmod 0755 /usr/local/bin/beagle-stream-server-preflight

  cat > /usr/local/bin/beagle-stream-server-healthcheck <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/etc/beagle/beagle-stream-server-healthcheck.env"
[[ -r "$ENV_FILE" ]] || exit 1
# shellcheck disable=SC1090
source "$ENV_FILE"

BEAGLE_STREAM_SERVER_USER="${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_PORT="${BEAGLE_STREAM_SERVER_PORT:-}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC:-45}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD="${BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD:-4}"
GUEST_USER="${GUEST_USER:-beagle}"
GUEST_UID="${GUEST_UID:-$(id -u "$GUEST_USER" 2>/dev/null || echo 1000)}"

repair="${1:-}"
if ! [[ "$BEAGLE_STREAM_SERVER_PORT" =~ ^[0-9]+$ ]]; then
  BEAGLE_STREAM_SERVER_PORT="50000"
fi
api_port="$((BEAGLE_STREAM_SERVER_PORT + 1))"
rtsp_port="$((BEAGLE_STREAM_SERVER_PORT + 21))"
readiness_failure_file="/run/beagle-stream-server-healthcheck/readiness-failures"

ensure_runtime() {
  local runtime_dir="/run/user/${GUEST_UID}"
  if [[ ! -d "$runtime_dir" ]]; then
    loginctl enable-linger "$GUEST_USER" >/dev/null 2>&1 || true
  fi
}

restart_stack() {
  ensure_runtime
  systemctl daemon-reload >/dev/null 2>&1 || true
  systemctl enable beagle-stream-server.service >/dev/null 2>&1 || true
  systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true
}

reset_readiness_failures() {
  rm -f "$readiness_failure_file" >/dev/null 2>&1 || true
}

record_readiness_failure() {
  local count state_dir
  state_dir="$(dirname "$readiness_failure_file")"
  install -d -m 0755 "$state_dir" >/dev/null 2>&1 || true
  count="$(cat "$readiness_failure_file" 2>/dev/null || echo 0)"
  [[ "$count" =~ ^[0-9]+$ ]] || count=0
  count="$((count + 1))"
  printf '%s\n' "$count" > "$readiness_failure_file"
  [[ "$count" -ge "$BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD" ]]
}

beagle_stream_server_is_running() {
  local main_pid
  main_pid="$(systemctl show -p MainPID --value beagle-stream-server.service 2>/dev/null || echo 0)"
  [[ "$main_pid" =~ ^[0-9]+$ && "$main_pid" -gt 0 ]] || return 1
  kill -0 "$main_pid" 2>/dev/null
}

service_state() {
  systemctl is-active beagle-stream-server.service 2>/dev/null || true
}

service_is_transitioning() {
  case "$(service_state)" in
    activating|reloading|deactivating) return 0 ;;
    *) return 1 ;;
  esac
}

service_uptime_sec() {
  local main_pid uptime
  main_pid="$(systemctl show -p MainPID --value beagle-stream-server.service 2>/dev/null || echo 0)"
  [[ "$main_pid" =~ ^[0-9]+$ && "$main_pid" -gt 0 ]] || { echo 0; return 0; }
  uptime="$(ps -o etimes= -p "$main_pid" 2>/dev/null | tr -d ' ' || true)"
  [[ "$uptime" =~ ^[0-9]+$ ]] || uptime=0
  echo "$uptime"
}

service_is_warming_up() {
  [[ "$(service_uptime_sec)" -lt "$BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC" ]]
}

is_stream_ready() {
  curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${BEAGLE_STREAM_SERVER_PORT}/serverinfo" >/dev/null
}

is_api_ready() {
  [[ -n "$BEAGLE_STREAM_SERVER_PASSWORD" ]] || return 1
  # Beagle Stream Server uses a self-signed cert on 127.0.0.1; --insecure disables CN check
  # while --pinnedpubkey (when set) ensures cryptographic pinning.
  # tls-bypass-allowlist: loopback Beagle Stream Server API, self-signed cert, pubkey-pinned
  local _tls_args=(--insecure)  # tls-bypass-allowlist: Beagle Stream Server loopback
  [[ -n "${BEAGLE_STREAM_SERVER_PINNED_PUBKEY:-}" ]] && _tls_args+=(--pinnedpubkey "$BEAGLE_STREAM_SERVER_PINNED_PUBKEY")
  curl -fsS --connect-timeout 3 --max-time 5 \
    "${_tls_args[@]}" \
    --user "${BEAGLE_STREAM_SERVER_USER}:${BEAGLE_STREAM_SERVER_PASSWORD}" \
    "https://127.0.0.1:${api_port}/api/apps" >/dev/null
}

has_rtsp_port_conflict() {
  local listeners server_count sunshine_count total_count

  listeners="$(ss -lntp 2>/dev/null | awk -v p=":${rtsp_port}" '$4 ~ p"$" {print $0}')"
  [[ -n "$listeners" ]] || return 1

  server_count=0
  beagle_stream_server_is_running && server_count=1
  sunshine_count="$(pgrep -x sunshine 2>/dev/null | wc -l | tr -d ' ')"
  total_count="$(( ${server_count:-0} + ${sunshine_count:-0} ))"
  if [[ "${total_count:-0}" -gt 1 ]]; then
    return 0
  fi

  if printf '%s\n' "$listeners" | grep -Eq "sunshine|beagle-stream-server"; then
    return 1
  fi
  return 0
}

if [[ "$repair" == "--repair-only" ]]; then
  restart_stack
  exit 0
fi

case "$(service_state)" in
  active) ;;
  activating|reloading|deactivating) exit 0 ;;
  *)
    restart_stack
    exit 0
    ;;
esac

if ! beagle_stream_server_is_running && ! pgrep -x sunshine >/dev/null 2>&1; then
  restart_stack
  exit 0
fi

if service_is_warming_up; then
  exit 0
fi

if is_stream_ready || is_api_ready; then
  reset_readiness_failures
  exit 0
fi

if has_rtsp_port_conflict; then
  reset_readiness_failures
  restart_stack
  exit 0
fi

if beagle_stream_server_is_running; then
  # Do not restart a live stream-server process solely because readiness probes
  # flap during an active media/control session. Restart=always still covers
  # genuine process exits.
  reset_readiness_failures
  exit 0
fi

if record_readiness_failure; then
  reset_readiness_failures
  restart_stack
fi
EOF
  chmod 0755 /usr/local/bin/beagle-stream-server-healthcheck

  cat > /etc/systemd/system/beagle-stream-server-healthcheck.service <<'EOF'
[Unit]
Description=Beagle Beagle Stream Server Healthcheck and Repair
After=network-online.target beagle-stream-server.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/beagle-stream-server-healthcheck
EOF

  cat > /etc/systemd/system/beagle-stream-server-healthcheck.timer <<EOF
[Unit]
Description=Run Beagle Beagle Stream Server healthcheck periodically

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
Persistent=true
RandomizedDelaySec=5s
Unit=beagle-stream-server-healthcheck.service

[Install]
WantedBy=timers.target
EOF

  cat > /usr/local/bin/beagle-stream-server-guardian <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/etc/beagle/beagle-stream-server-healthcheck.env"
[[ -r "$ENV_FILE" ]] || exit 1
# shellcheck disable=SC1090
source "$ENV_FILE"

BEAGLE_STREAM_SERVER_USER="${BEAGLE_STREAM_SERVER_USER:-beagle-stream-server}"
BEAGLE_STREAM_SERVER_PASSWORD="${BEAGLE_STREAM_SERVER_PASSWORD:-}"
BEAGLE_STREAM_SERVER_PORT="${BEAGLE_STREAM_SERVER_PORT:-50000}"
BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC:-45}"
BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC="${BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC:-10}"
BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD="${BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD:-4}"
BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD="${BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD:-18}"

if ! [[ "$BEAGLE_STREAM_SERVER_PORT" =~ ^[0-9]+$ ]]; then
  BEAGLE_STREAM_SERVER_PORT="50000"
fi

api_port="$((BEAGLE_STREAM_SERVER_PORT + 1))"
consecutive_failures=0

service_state() {
  systemctl is-active beagle-stream-server.service 2>/dev/null || true
}

service_is_transitioning() {
  case "$(service_state)" in
    activating|reloading|deactivating) return 0 ;;
    *) return 1 ;;
  esac
}

service_uptime_sec() {
  local main_pid uptime
  main_pid="$(systemctl show -p MainPID --value beagle-stream-server.service 2>/dev/null || echo 0)"
  [[ "$main_pid" =~ ^[0-9]+$ && "$main_pid" -gt 0 ]] || { echo 0; return 0; }
  uptime="$(ps -o etimes= -p "$main_pid" 2>/dev/null | tr -d ' ' || true)"
  [[ "$uptime" =~ ^[0-9]+$ ]] || uptime=0
  echo "$uptime"
}

service_is_warming_up() {
  [[ "$(service_uptime_sec)" -lt "$BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC" ]]
}

stream_ready() {
  curl -fsS --connect-timeout 3 --max-time 5 "http://127.0.0.1:${BEAGLE_STREAM_SERVER_PORT}/serverinfo" >/dev/null
}

api_ready() {
  [[ -n "$BEAGLE_STREAM_SERVER_PASSWORD" ]] || return 1
  curl -kfsS --connect-timeout 3 --max-time 5 --user "${BEAGLE_STREAM_SERVER_USER}:${BEAGLE_STREAM_SERVER_PASSWORD}" "https://127.0.0.1:${api_port}/api/apps" >/dev/null # tls-bypass-allowlist: loopback health check against local Beagle Stream Server self-signed API
}

while :; do
  /usr/local/bin/beagle-stream-server-healthcheck >/dev/null 2>&1 || true

  if [[ "$(service_state)" == "active" ]] && { stream_ready || api_ready; }; then
    consecutive_failures=0
  elif [[ "$(service_state)" == "active" ]] && main_pid="$(systemctl show -p MainPID --value beagle-stream-server.service 2>/dev/null || echo 0)" && [[ "$main_pid" =~ ^[0-9]+$ && "$main_pid" -gt 0 ]] && kill -0 "$main_pid" 2>/dev/null; then
    consecutive_failures=0
  elif service_is_transitioning || service_is_warming_up; then
    :
  else
    consecutive_failures=$((consecutive_failures + 1))
    if [[ "$consecutive_failures" -ge "$BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD" ]]; then
      systemctl restart beagle-stream-server.service >/dev/null 2>&1 || true
    fi

    if [[ "$consecutive_failures" -ge "$BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD" ]]; then
      logger -t beagle-stream-server-guardian "stream offline for ${consecutive_failures} checks; rebooting guest"
      systemctl reboot >/dev/null 2>&1 || /sbin/reboot >/dev/null 2>&1 || true
      sleep 120
    fi
  fi

  sleep "$BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC"
done
EOF
  chmod 0755 /usr/local/bin/beagle-stream-server-guardian

  cat > /etc/systemd/system/beagle-stream-server-guardian.service <<'EOF'
[Unit]
Description=Beagle Stream Server Uptime Guardian
After=network-online.target beagle-stream-server.service
Wants=network-online.target beagle-stream-server.service

[Service]
Type=simple
ExecStart=/usr/local/bin/beagle-stream-server-guardian
Restart=always
RestartSec=2

[Install]
WantedBy=multi-user.target
EOF

  configure_stream_port_guard() {
    local stream_port="${BEAGLE_STREAM_SERVER_PORT:-50000}"
    local api_port="50001"
    local rtsp_port="50021"
    local https_port="49995"
    local allowed_raw="${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS:-10.88.0.0/16}"
    local default_gateway=""
    local default_gateway_cidr=""
    local cidr=""
    local cidr_csv=""

    if [[ "$stream_port" =~ ^[0-9]+$ ]]; then
      api_port="$((stream_port + 1))"
      rtsp_port="$((stream_port + 21))"
      if [[ "$stream_port" -gt 5 ]]; then
        https_port="$((stream_port - 5))"
      fi
    else
      stream_port="50000"
    fi

    for cidr in $(printf '%s' "$allowed_raw" | tr ',;' '  '); do
      if [[ "$cidr" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}(/[0-9]{1,2})?$ ]]; then
        if [[ -n "$cidr_csv" ]]; then
          cidr_csv+=", "
        fi
        cidr_csv+="$cidr"
      fi
    done
    if [[ -z "$cidr_csv" ]]; then
      cidr_csv="10.88.0.0/16"
    fi

    default_gateway="$(ip route show default 2>/dev/null | awk '/default/ {print $3; exit}')"
    if [[ "$default_gateway" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
      default_gateway_cidr="${default_gateway}/32"
      cidr_csv+=", ${default_gateway_cidr}"
    fi

    install -d -m 0755 /etc/beagle
    cat > /etc/beagle/beagle-stream-guest-guard.nft <<EOF
table inet beagle_stream_guest_guard {
  chain input {
    type filter hook input priority -5; policy accept;

    iifname "lo" accept
    ct state { established, related } accept

    iifname "wg-beagle" tcp dport { ${https_port}, ${stream_port}, ${api_port}, ${rtsp_port} } accept
    ip saddr { ${cidr_csv} } tcp dport { ${https_port}, ${stream_port}, ${api_port}, ${rtsp_port} } accept
    ip6 saddr ::1 tcp dport { ${https_port}, ${stream_port}, ${api_port}, ${rtsp_port} } accept

    tcp dport { ${https_port}, ${stream_port}, ${api_port}, ${rtsp_port} } drop
  }
}
EOF

    systemctl enable nftables >/dev/null 2>&1 || true
    nft delete table inet beagle_stream_guest_guard >/dev/null 2>&1 || true
    nft -f /etc/beagle/beagle-stream-guest-guard.nft >/dev/null 2>&1 || true
  }

  install_usb_microphone_normalizer() {
    cat > /usr/local/bin/beagle-normalize-usb-microphones <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

volume="${BEAGLE_USB_MICROPHONE_VOLUME:-250%}"
if ! command -v pactl >/dev/null 2>&1; then
  exit 0
fi

bridge_source="$(pactl list short sources 2>/dev/null | awk '$2 == "beagle_tc_microphone" {print $2; exit}')"
if [[ -n "$bridge_source" ]]; then
  pactl set-default-source "$bridge_source" >/dev/null 2>&1 || true
  pactl set-source-mute "$bridge_source" 0 >/dev/null 2>&1 || true
  pactl set-source-volume "$bridge_source" 100% >/dev/null 2>&1 || true
  exit 0
fi

source_name="$(pactl list short sources 2>/dev/null | awk '$2 ~ /^alsa_input\.usb-/ && $2 !~ /\.monitor$/ {print $2; exit}')"
if [[ -z "$source_name" ]]; then
  exit 0
fi

pactl set-default-source "$source_name" >/dev/null 2>&1 || true
pactl set-source-mute "$source_name" 0 >/dev/null 2>&1 || true
pactl set-source-volume "$source_name" "$volume" >/dev/null 2>&1 || true
EOF
    chmod 0755 /usr/local/bin/beagle-normalize-usb-microphones

    cat > /etc/systemd/system/beagle-usb-microphone-normalize.service <<EOF
[Unit]
Description=Normalize Beagle USB microphone defaults
After=display-manager.service
Wants=display-manager.service

[Service]
Type=oneshot
User=${GUEST_USER}
Environment=HOME=/home/${GUEST_USER}
Environment=XDG_RUNTIME_DIR=/run/user/${GUEST_UID}
Environment=BEAGLE_USB_MICROPHONE_VOLUME=${BEAGLE_USB_MICROPHONE_VOLUME}
ExecStart=/usr/local/bin/beagle-normalize-usb-microphones
EOF

    cat > /etc/systemd/system/beagle-usb-microphone-normalize.timer <<'EOF'
[Unit]
Description=Periodically normalize Beagle USB microphone defaults

[Timer]
OnBootSec=20s
OnUnitActiveSec=30s
AccuracySec=5s
Unit=beagle-usb-microphone-normalize.service

[Install]
WantedBy=timers.target
EOF

    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable --now beagle-usb-microphone-normalize.timer >/dev/null 2>&1 || true
    systemctl start beagle-usb-microphone-normalize.service >/dev/null 2>&1 || true
  }

  install_pipewire_resource_limits() {
    local dropin_dir="/home/$GUEST_USER/.config/systemd/user/pipewire-pulse.service.d"

    install -d -m 0755 -o "$GUEST_USER" -g "$GUEST_USER" "$dropin_dir"
    cat > "$dropin_dir/10-beagle-resource-limits.conf" <<'EOF'
[Service]
# Streaming and browser sessions can retain PipeWire event/memory descriptors
# for long periods. Keep ample headroom so Pulse-compatible audio remains able
# to create new streams during long-lived, linger-enabled desktop sessions.
LimitNOFILE=65536
EOF
    chown "$GUEST_USER:$GUEST_USER" "$dropin_dir/10-beagle-resource-limits.conf"

    if systemctl --user -M "$GUEST_USER@" daemon-reload >/dev/null 2>&1; then
      systemctl --user -M "$GUEST_USER@" restart pipewire-pulse.service >/dev/null 2>&1 || true
    fi
  }

  install_log_retention_policy() {
    install -d -m 0755 /etc/systemd/journald.conf.d /etc/logrotate.d
    cat > /etc/systemd/journald.conf.d/10-beagle-retention.conf <<'EOF'
[Journal]
Storage=persistent
Compress=yes
SystemMaxUse=256M
SystemKeepFree=1G
RuntimeMaxUse=64M
RuntimeKeepFree=128M
MaxRetentionSec=14day
MaxFileSec=1day
EOF

    cat > /etc/logrotate.d/beagle <<'EOF'
/var/log/beagle*.log /var/log/beagle/*.log /var/log/beagle-os/*.log /var/lib/beagle/guest-updater/*.log {
    daily
    rotate 14
    maxsize 25M
    missingok
    notifempty
    compress
    delaycompress
    copytruncate
    su root root
}
EOF

    systemctl try-reload-or-restart systemd-journald.service >/dev/null 2>&1 || true
  }

  install_thinclient_microphone_bridge() {
    local mic_bridge_port="$((43000 + VMID + 100))"
    cat > /usr/local/bin/beagle-tc-mic-bridge <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

BRIDGE_HOST="${BEAGLE_TC_MIC_BRIDGE_HOST:-192.168.123.1}"
BRIDGE_PORT="${BEAGLE_TC_MIC_BRIDGE_PORT:-43200}"
SOURCE_NAME="${BEAGLE_TC_MIC_SOURCE_NAME:-beagle_tc_microphone}"
SOURCE_DESCRIPTION="${BEAGLE_TC_MIC_SOURCE_DESCRIPTION:-Beagle Thin Client Microphone}"
FIFO_PATH="${BEAGLE_TC_MIC_FIFO:-/run/beagle/tc-mic.raw}"
RATE="${BEAGLE_TC_MIC_RATE:-48000}"
CHANNELS="${BEAGLE_TC_MIC_CHANNELS:-1}"
FRAME_MSEC="${BEAGLE_TC_MIC_FRAME_MSEC:-20}"
PREBUFFER_MSEC="${BEAGLE_TC_MIC_PREBUFFER_MSEC:-60}"
MAX_BUFFER_MSEC="${BEAGLE_TC_MIC_MAX_BUFFER_MSEC:-200}"
STATS_INTERVAL_SEC="${BEAGLE_TC_MIC_STATS_INTERVAL_SEC:-5}"
RECONNECT_DELAY="${BEAGLE_TC_MIC_RECONNECT_DELAY:-1}"

log() {
  printf '%s beagle-tc-mic-bridge: %s\n' "$(date -Is)" "$*" >&2
}

ensure_fifo() {
  install -d -m 0755 "$(dirname "$FIFO_PATH")"
  if [[ -e "$FIFO_PATH" && ! -p "$FIFO_PATH" ]]; then
    rm -f "$FIFO_PATH"
  fi
  [[ -p "$FIFO_PATH" ]] || mkfifo "$FIFO_PATH"
  chmod 0660 "$FIFO_PATH" 2>/dev/null || true
}

source_exists() {
  pactl list short sources 2>/dev/null | awk '{print $2}' | grep -Fxq "$SOURCE_NAME"
}

unload_pipe_source() {
  local module_id
  while read -r module_id; do
    [[ -n "$module_id" ]] || continue
    pactl unload-module "$module_id" >/dev/null 2>&1 || true
  done < <(
    pactl list short modules 2>/dev/null \
      | awk -v src="source_name=$SOURCE_NAME" '$2 == "module-pipe-source" && index($0, src) {print $1}'
  )
}

load_pipe_source() {
  local filler_pid=""

  # module-pipe-source opens the FIFO while loading. Keep a short-lived writer
  # present so module load cannot block when the network stream is not connected yet.
  (while true; do printf '\0\0' >"$FIFO_PATH" 2>/dev/null || true; sleep 0.05; done) &
  filler_pid="$!"
  pactl load-module module-pipe-source \
    source_name="$SOURCE_NAME" \
    file="$FIFO_PATH" \
    format=s16le \
    rate="$RATE" \
    channels="$CHANNELS" \
    source_properties="device.description=$SOURCE_DESCRIPTION" >/dev/null
  kill "$filler_pid" >/dev/null 2>&1 || true
  wait "$filler_pid" 2>/dev/null || true
}

normalize_source() {
  pactl set-default-source "$SOURCE_NAME" >/dev/null 2>&1 || true
  pactl set-source-mute "$SOURCE_NAME" 0 >/dev/null 2>&1 || true
  pactl set-source-volume "$SOURCE_NAME" 100% >/dev/null 2>&1 || true
}

stream_once() {
  python3 - "$BRIDGE_HOST" "$BRIDGE_PORT" "$FIFO_PATH" "$RATE" "$CHANNELS" "$FRAME_MSEC" "$PREBUFFER_MSEC" "$MAX_BUFFER_MSEC" "$STATS_INTERVAL_SEC" <<'PY'
import math
import socket
import sys
import time
from collections import deque

host = sys.argv[1]
port = int(sys.argv[2])
fifo = sys.argv[3]
rate = int(sys.argv[4])
channels = int(sys.argv[5])
frame_msec = max(5, int(sys.argv[6]))
prebuffer_msec = max(0, int(sys.argv[7]))
max_buffer_msec = max(frame_msec * 2, int(sys.argv[8]))
stats_interval_sec = max(1, int(sys.argv[9]))

sample_width = 2
frame_bytes = max(2, (rate * channels * sample_width * frame_msec) // 1000)
frame_sec = frame_msec / 1000.0
prebuffer_frames = max(2, math.ceil(prebuffer_msec / frame_msec))
max_buffer_frames = max(prebuffer_frames + 2, math.ceil(max_buffer_msec / frame_msec))
silence = b"\0" * frame_bytes


def log(message: str) -> None:
  stamp = time.strftime("%Y-%m-%dT%H:%M:%S%z")
  print(f"{stamp} beagle-tc-mic-bridge: {message}", file=sys.stderr, flush=True)


stats: dict[str, int] = {
  "frames_rx": 0,
  "frames_tx": 0,
  "underruns": 0,
  "silence_inserted": 0,
  "frames_dropped": 0,
  "reconnects": 0,
  "max_fill": 0,
}


def emit_stats(prefix: str, fill_frames: int) -> None:
  log(
    f"{prefix} fill={fill_frames} max_fill={stats['max_fill']} "
    f"rx={stats['frames_rx']} tx={stats['frames_tx']} underruns={stats['underruns']} "
    f"silence={stats['silence_inserted']} dropped={stats['frames_dropped']} reconnects={stats['reconnects']}"
  )

with socket.create_connection((host, port), timeout=10) as sock:
  try:
    sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
  except OSError:
    pass
  sock.settimeout(0.05)
  net_buffer = bytearray()
  frame_buffer: deque[bytes] = deque()
  started = False
  remote_closed = False
  next_write_deadline = time.monotonic()
  next_stats = time.monotonic() + stats_interval_sec
  with open(fifo, "wb", buffering=0) as handle:
    while True:
      now = time.monotonic()

      if not remote_closed:
        try:
          data = sock.recv(65536)
        except socket.timeout:
          data = None
        if data:
          net_buffer.extend(data)
          while len(net_buffer) >= frame_bytes:
            frame = bytes(net_buffer[:frame_bytes])
            del net_buffer[:frame_bytes]
            if len(frame_buffer) >= max_buffer_frames:
              frame_buffer.popleft()
              stats["frames_dropped"] += 1
            frame_buffer.append(frame)
            stats["frames_rx"] += 1
        elif data == b"":
          remote_closed = True
          stats["reconnects"] += 1

      while now >= next_write_deadline:
        fill = len(frame_buffer)
        if fill > stats["max_fill"]:
          stats["max_fill"] = fill

        if not started and fill >= prebuffer_frames:
          started = True

        if started and frame_buffer:
          frame = frame_buffer.popleft()
        else:
          frame = silence
          stats["underruns"] += 1
          stats["silence_inserted"] += 1

        handle.write(frame)
        stats["frames_tx"] += 1
        next_write_deadline += frame_sec
        now = time.monotonic()

        if now - next_write_deadline > frame_sec * 3:
          next_write_deadline = now + frame_sec

      if now >= next_stats:
        emit_stats("stats", len(frame_buffer))
        next_stats = now + stats_interval_sec

      if remote_closed and not frame_buffer:
        break
      time.sleep(0.002)

emit_stats("stream_end", 0)
PY
}

ensure_fifo
unload_pipe_source
load_pipe_source
normalize_source
log "ready host=$BRIDGE_HOST port=$BRIDGE_PORT source=$SOURCE_NAME fifo=$FIFO_PATH rate=$RATE channels=$CHANNELS frame_msec=$FRAME_MSEC prebuffer_msec=$PREBUFFER_MSEC"

while true; do
  if stream_once; then
    log "stream ended; reconnecting"
  else
    log "stream unavailable; retrying"
  fi
  sleep "$RECONNECT_DELAY"
done
EOF
    chmod 0755 /usr/local/bin/beagle-tc-mic-bridge

    cat > /etc/systemd/system/beagle-tc-mic-bridge.service <<EOF
[Unit]
Description=Beagle thin-client microphone audio bridge
After=display-manager.service
Wants=display-manager.service

[Service]
Type=simple
User=${GUEST_USER}
Environment=HOME=/home/${GUEST_USER}
Environment=XDG_RUNTIME_DIR=/run/user/${GUEST_UID}
Environment=BEAGLE_TC_MIC_BRIDGE_HOST=192.168.123.1
Environment=BEAGLE_TC_MIC_BRIDGE_PORT=${mic_bridge_port}
Environment=BEAGLE_TC_MIC_RATE=48000
Environment=BEAGLE_TC_MIC_CHANNELS=1
Environment=BEAGLE_TC_MIC_FRAME_MSEC=20
Environment=BEAGLE_TC_MIC_PREBUFFER_MSEC=60
Environment=BEAGLE_TC_MIC_MAX_BUFFER_MSEC=200
RuntimeDirectory=beagle
RuntimeDirectoryMode=0755
ExecStart=/usr/local/bin/beagle-tc-mic-bridge
Nice=5
CPUQuota=25%
Restart=always
RestartSec=2s

[Install]
WantedBy=graphical.target
EOF

    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable beagle-tc-mic-bridge.service >/dev/null 2>&1 || true
    systemctl restart beagle-tc-mic-bridge.service >/dev/null 2>&1 || true
  }

  install_beagle_netbridge_client() {
    # Bridge local-network devices (e.g. the user's Wi-Fi printer) that live on
    # the thin client's LAN into this VM. The thin-client NetBridge agent proxies
    # those devices onto the WireGuard mesh; this client wires the printers it
    # advertises into CUPS so the streamed desktop can print on them.
    # the streamed desktop can print on them. The PyQt5 dependency powers the
    # in-VM tray manager (beagle-netbridge-tray).
    apt_retry apt-get install -y --no-install-recommends cups cups-client cups-ipp-utils python3-cups python3-pyqt5 || true

    install -d -m 0755 /etc/beagle
    if [[ ! -f /etc/beagle/netbridge.env ]]; then
      cat > /etc/beagle/netbridge.env <<'EOF'
# Beagle NetBridge client configuration.
# Comma-separated list of thin-client NetBridge agents (host[:port]).
BEAGLE_NETBRIDGE_AGENTS=10.88.1.1:47100
EOF
    fi

    cat > /usr/local/bin/beagle-netbridge-client <<'NETBRIDGECLIENTEOF'
#!/usr/bin/env python3
"""Beagle NetBridge client (in-VM side).

Talks to the thin-client NetBridge agent across the Beagle WireGuard tunnel,
reads the catalog of bridged local-network devices and reconciles them into the
VM. Today it wires Wi-Fi/network printers into CUPS so the streamed desktop can
print on the printer that sits next to the user's thin client.

Runs as a periodic systemd service; depends only on the Python 3 standard
library plus the CUPS command-line tools (``lpadmin``/``lpstat``) that the VM
provisioning installs.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import time

DEFAULT_AGENTS = "10.88.1.1:47100"
ENV_FILE = "/etc/beagle/netbridge.env"
STATE_DIR = "/var/lib/beagle/netbridge"
MANAGED_PREFIX = "beagle-net-"


def log(message: str) -> None:
    sys.stderr.write(f"{time.strftime('%Y-%m-%dT%H:%M:%S')} beagle-netbridge-client: {message}\n")
    sys.stderr.flush()


def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"')
    except OSError:
        pass
    return env


def agent_endpoints(env: dict[str, str]) -> list[tuple[str, int]]:
    raw = os.environ.get("BEAGLE_NETBRIDGE_AGENTS") or env.get("BEAGLE_NETBRIDGE_AGENTS") or DEFAULT_AGENTS
    endpoints: list[tuple[str, int]] = []
    for item in filter(None, (chunk.strip() for chunk in raw.split(","))):
        host, _, port = item.partition(":")
        endpoints.append((host, int(port) if port else 47100))
    return endpoints


def fetch_catalog(host: str, port: int) -> dict | None:
    try:
        with socket.create_connection((host, port), timeout=6) as sock:
            sock.sendall(b'{"op":"catalog"}\n')
            sock.settimeout(6)
            buffer = bytearray()
            while b"\n" not in buffer:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                buffer.extend(chunk)
                if len(buffer) > 1_000_000:
                    break
    except OSError as exc:
        log(f"agent {host}:{port} unreachable: {exc}")
        return None
    try:
        payload = json.loads(buffer.decode("utf-8").splitlines()[0])
    except (ValueError, IndexError) as exc:
        log(f"agent {host}:{port} sent invalid catalog: {exc}")
        return None
    payload.setdefault("agent_host", host)
    return payload


# --------------------------------------------------------------------------- #
# CUPS reconciliation
# --------------------------------------------------------------------------- #
def _run(args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=60, check=False)


def cups_available() -> bool:
    return bool(_which("lpadmin")) and bool(_which("lpstat"))


def _which(binary: str) -> str:
    for directory in os.environ.get("PATH", "/usr/sbin:/usr/bin:/sbin:/bin").split(":"):
        candidate = os.path.join(directory, binary)
        if os.access(candidate, os.X_OK):
            return candidate
    return ""


def ensure_cups_running() -> None:
    state = _run(["systemctl", "is-active", "cups"])
    if state.stdout.strip() != "active":
        _run(["systemctl", "enable", "--now", "cups"])


def existing_managed_queues() -> set[str]:
    result = _run(["lpstat", "-p"])
    queues: set[str] = set()
    for line in result.stdout.splitlines():
        match = re.match(r"printer (\S+)", line)
        if match and match.group(1).startswith(MANAGED_PREFIX):
            queues.add(match.group(1))
    return queues


def _queue_name(device: dict) -> str:
    base = device.get("name") or device.get("id") or "printer"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower() or device.get("id", "printer")
    return f"{MANAGED_PREFIX}{slug}"


def _device_uri(agent_host: str, device: dict) -> tuple[str, str] | None:
    services = device.get("services", {})
    if "ipp" in services:
        service = services["ipp"]
        rp = service.get("rp", "ipp/print").lstrip("/")
        return f"ipp://{agent_host}:{service['proxy_port']}/{rp}", "everywhere"
    if "raw" in services:
        service = services["raw"]
        return f"socket://{agent_host}:{service['proxy_port']}", "raw"
    if "lpd" in services:
        service = services["lpd"]
        return f"lpd://{agent_host}:{service['proxy_port']}/queue", "raw"
    return None


def reconcile_printers(agent_host: str, devices: list[dict]) -> set[str]:
    desired: set[str] = set()
    first_queue = ""
    for device in devices:
        if device.get("kind") != "printer":
            continue
        target = _device_uri(agent_host, device)
        if not target:
            continue
        uri, model = target
        queue = _queue_name(device)
        desired.add(queue)
        description = device.get("make_model") or device.get("name") or "Local network printer"
        args = ["lpadmin", "-p", queue, "-E", "-v", uri,
                "-D", f"{device.get('name', queue)} (Thin Client)",
                "-L", "Beagle Thin Client LAN",
                "-o", "printer-is-shared=false"]
        if model == "everywhere":
            args += ["-m", "everywhere"]
        result = _run(args)
        if result.returncode != 0 and model == "everywhere":
            # IPP Everywhere needs the printer reachable at setup time; fall back
            # to a raw socket queue if the device also exposes JetDirect.
            raw = device.get("services", {}).get("raw")
            if raw:
                uri = f"socket://{agent_host}:{raw['proxy_port']}"
                result = _run(["lpadmin", "-p", queue, "-E", "-v", uri,
                               "-D", f"{device.get('name', queue)} (Thin Client)",
                               "-L", "Beagle Thin Client LAN",
                               "-o", "printer-is-shared=false"])
        if result.returncode != 0:
            log(f"lpadmin failed for {queue}: {result.stderr.strip()}")
            desired.discard(queue)
            continue
        _run(["cupsenable", queue])
        _run(["cupsaccept", queue])
        log(f"printer ready: {queue} -> {uri} ({description})")
        if not first_queue:
            first_queue = queue

    if first_queue:
        current_default = _run(["lpstat", "-d"]).stdout
        if "no system default" in current_default or MANAGED_PREFIX not in current_default:
            _run(["lpadmin", "-d", first_queue])
    return desired


def remove_stale_queues(desired: set[str]) -> None:
    for queue in existing_managed_queues() - desired:
        _run(["lpadmin", "-x", queue])
        log(f"removed stale printer queue: {queue}")


def sync_once() -> bool:
    env = load_env()
    if not cups_available():
        log("CUPS tools (lpadmin/lpstat) not found; nothing to reconcile")
        return False
    ensure_cups_running()
    catalog: dict | None = None
    for host, port in agent_endpoints(env):
        catalog = fetch_catalog(host, port)
        if catalog is not None:
            break
    if catalog is None:
        log("no NetBridge agent reachable; leaving existing queues untouched")
        return False
    agent_host = catalog.get("agent_host") or agent_endpoints(env)[0][0]
    devices = catalog.get("devices", [])
    desired = reconcile_printers(agent_host, devices)
    remove_stale_queues(desired)
    os.makedirs(STATE_DIR, exist_ok=True)
    with open(os.path.join(STATE_DIR, "last-catalog.json"), "w", encoding="utf-8") as handle:
        json.dump(catalog, handle, indent=2)
    log(f"sync complete: {len(desired)} bridged printer(s)")
    return True


def main() -> int:
    once = "--once" in sys.argv
    interval = int(os.environ.get("BEAGLE_NETBRIDGE_CLIENT_INTERVAL", "60"))
    while True:
        try:
            sync_once()
        except Exception as exc:  # noqa: BLE001 - keep the daemon alive
            log(f"sync error: {exc}")
        if once:
            return 0
        time.sleep(interval)


if __name__ == "__main__":
    raise SystemExit(main())
NETBRIDGECLIENTEOF
    chmod 0755 /usr/local/bin/beagle-netbridge-client

    cat > /etc/systemd/system/beagle-netbridge-client.service <<'EOF'
[Unit]
Description=Beagle NetBridge client (attach thin-client LAN printers to this VM)
After=network-online.target cups.service
Wants=network-online.target

[Service]
Type=simple
ExecStart=/usr/local/bin/beagle-netbridge-client
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload >/dev/null 2>&1 || true
    systemctl enable cups.service >/dev/null 2>&1 || true
    systemctl enable --now beagle-netbridge-client.service >/dev/null 2>&1 || true

    # In-VM tray manager: lets the user view the shared LAN devices, trigger a
    # re-scan, and add/remove devices manually from the KDE Plasma system tray.
    cat > /usr/local/bin/beagle-netbridge-tray <<'NETBRIDGETRAYEOF'
#!/usr/bin/env python3
"""Beagle NetBridge tray manager (in-VM side).

A small desktop tray application for the streamed VM that lets the user manage
the LAN devices shared from their thin client through Beagle NetBridge:

  * see the network devices the thin-client agent has discovered/bridged,
  * trigger an on-demand re-scan of the local network,
  * add a device manually (e.g. a printer that does not advertise itself), and
  * remove devices that were added manually.

It talks to the thin-client ``beagle-netbridge-agent`` over the WireGuard tunnel
using the agent's JSON control protocol (catalog / rescan / add_static /
remove_static / list_static / status / set_stream_profile / service_action) and
shows how each device maps onto the local CUPS queues that
``beagle-netbridge-client`` maintains.

The networking core (:class:`NetBridgeControl`) depends only on the Python 3
standard library so it can be unit-tested without a display; the tray UI uses
PyQt5 (``QSystemTrayIcon``), which integrates natively with the VM's KDE Plasma
desktop.
"""
from __future__ import annotations

import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import threading
import time

DEFAULT_AGENTS = "10.88.1.1:47100"
ENV_FILE = "/etc/beagle/netbridge.env"
MANAGED_PREFIX = "beagle-net-"
CONTROL_TIMEOUT = 6
TRAY_WAIT_TIMEOUT_SECONDS = float(os.environ.get("BEAGLE_NETBRIDGE_TRAY_WAIT_TIMEOUT", "90"))
TRAY_WAIT_INTERVAL_SECONDS = float(os.environ.get("BEAGLE_NETBRIDGE_TRAY_WAIT_INTERVAL", "1"))
APP_ID = "com.beagle-os.netbridge.tray"
APP_NAME = "Beagle NetBridge"
ADMIN_APP_PATHS = (
    "/usr/local/bin/beagle-thinclient-admin",
)
ICON_PATHS = (
    "/usr/local/share/beagle/beagle-netbridge-tray.png",
    "/usr/local/share/icons/hicolor/256x256/apps/beagle-netbridge-tray.png",
    "/usr/share/pixmaps/beagle-netbridge-tray.png",
)
WALLPAPER_ICON_SOURCES = (
    "/usr/local/share/beagle/wallpapers/beagle-cyberpunk-wallpaper.png",
    "/usr/local/share/beagle-os/beagleos.png",
)


# --------------------------------------------------------------------------- #
# Configuration helpers (shared semantics with beagle-netbridge-client)
# --------------------------------------------------------------------------- #
def load_env() -> dict[str, str]:
    env: dict[str, str] = {}
    try:
        with open(ENV_FILE, "r", encoding="utf-8") as handle:
            for line in handle:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, _, value = line.partition("=")
                env[key.strip()] = value.strip().strip('"')
    except OSError:
        pass
    return env


def agent_endpoints(env: dict[str, str] | None = None) -> list[tuple[str, int]]:
    env = env if env is not None else load_env()
    raw = os.environ.get("BEAGLE_NETBRIDGE_AGENTS") or env.get("BEAGLE_NETBRIDGE_AGENTS") or DEFAULT_AGENTS
    endpoints: list[tuple[str, int]] = []
    for item in filter(None, (chunk.strip() for chunk in raw.split(","))):
        host, _, port = item.partition(":")
        endpoints.append((host, int(port) if port else 47100))
    return endpoints


def queue_name(device: dict) -> str:
    """Mirror beagle-netbridge-client._queue_name so we can match queues."""
    base = device.get("name") or device.get("id") or "printer"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", base).strip("-").lower() or device.get("id", "printer")
    return f"{MANAGED_PREFIX}{slug}"


# --------------------------------------------------------------------------- #
# Agent control client (stdlib only -> unit-testable without a display)
# --------------------------------------------------------------------------- #
class NetBridgeControl:
    """Talk to the thin-client NetBridge agent's JSON control port."""

    def __init__(self, endpoints: list[tuple[str, int]] | None = None) -> None:
        self.endpoints = endpoints if endpoints is not None else agent_endpoints()

    def request(self, op: str = "catalog", **fields) -> dict | None:
        payload = {"op": op}
        payload.update(fields)
        line = (json.dumps(payload) + "\n").encode("utf-8")
        for host, port in self.endpoints:
            try:
                with socket.create_connection((host, port), timeout=CONTROL_TIMEOUT) as sock:
                    sock.sendall(line)
                    sock.settimeout(CONTROL_TIMEOUT)
                    buffer = bytearray()
                    while b"\n" not in buffer:
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        buffer.extend(chunk)
                        if len(buffer) > 2_000_000:
                            break
                response = json.loads(buffer.decode("utf-8").splitlines()[0])
            except (OSError, ValueError, IndexError):
                continue
            if isinstance(response, dict):
                response.setdefault("agent_host", host)
                return response
        return None

    def catalog(self) -> dict | None:
        return self.request("catalog")

    def rescan(self) -> dict | None:
        return self.request("rescan")

    def add_static(self, address: str, port: int = 9100, name: str = "",
                   rp: str = "ipp/print") -> dict | None:
        return self.request("add_static", address=address, port=int(port),
                            name=name, rp=rp)

    def remove_static(self, device_id: str) -> dict | None:
        return self.request("remove_static", id=device_id)

    def list_static(self) -> dict | None:
        return self.request("list_static")

    def restart_agent(self) -> dict | None:
        return self.request("restart")

    def status(self) -> dict | None:
        return self.request("status")

    def set_stream_profile(self, profile: str) -> dict | None:
        return self.request("set_stream_profile", profile=profile)

    def service_action(self, service: str, action: str = "restart") -> dict | None:
        return self.request("service_action", service=service, action=action)

    def thinclient_update(self, action: str = "status") -> dict | None:
        return self.request("thinclient_update", action=action)

    def thinclient_power(self, action: str) -> dict | None:
        return self.request("thinclient_power", action=action)

    def usb_bind(self, busid: str) -> dict | None:
        return self.request("usb_bind", busid=busid)

    def usb_unbind(self, busid: str) -> dict | None:
        return self.request("usb_unbind", busid=busid)


# --------------------------------------------------------------------------- #
# Local CUPS state (so the tray can show what is actually wired up)
# --------------------------------------------------------------------------- #
def _run(args: list[str], timeout: int = 20) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True, timeout=timeout, check=False)


def cups_managed_queues() -> dict[str, str]:
    """Return {queue_name: device-uri} for Beagle-managed CUPS queues."""
    queues: dict[str, str] = {}
    try:
        result = _run(["lpstat", "-v"])
    except (OSError, subprocess.SubprocessError):
        return queues
    for line in result.stdout.splitlines():
        match = re.search(r"(?:for|für)\s+(\S+?):\s*(\S+)", line)
        if match and match.group(1).startswith(MANAGED_PREFIX):
            queues[match.group(1)] = match.group(2)
    return queues


def print_test_page(queue: str) -> tuple[bool, str]:
    body = (
        "=== Beagle NetBridge Testseite / test page ===\n"
        f"Queue:     {queue}\n"
        f"Zeitpunkt: {time.strftime('%Y-%m-%d %H:%M:%S %Z')}\n"
        "Pfad: VM -> WireGuard -> Thin Client -> Drucker\n"
    )
    try:
        with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False,
                                         encoding="utf-8") as handle:
            handle.write(body)
            path = handle.name
    except OSError as exc:
        return False, str(exc)
    try:
        result = _run(["lp", "-d", queue, path])
    except (OSError, subprocess.SubprocessError) as exc:
        return False, str(exc)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass
    if result.returncode != 0:
        return False, result.stderr.strip() or "lp failed"
    return True, result.stdout.strip()


# --------------------------------------------------------------------------- #
# Headless self-test (verify the control path without a display)
# --------------------------------------------------------------------------- #
def selftest() -> int:
    control = NetBridgeControl()
    print(f"agent endpoints: {control.endpoints}")
    catalog = control.catalog()
    if catalog is None:
        print("RESULT: agent unreachable")
        return 1
    devices = catalog.get("devices", [])
    print(f"agent_host: {catalog.get('agent_host')}  devices: {len(devices)}")
    status = control.status() or {}
    thinclient = status.get("thinclient", {}) if isinstance(status, dict) else {}
    services = thinclient.get("services", {}) if isinstance(thinclient, dict) else {}
    stream = thinclient.get("stream", {}) if isinstance(thinclient, dict) else {}
    print(f"thinclient_services: {len(services)}  stream_profile: {stream.get('profile', 'unknown')}")
    wired = cups_managed_queues()
    for device in devices:
        queue = queue_name(device)
        services = ",".join(device.get("services", {}))
        flag = "wired" if queue in wired else "not-wired"
        manual = " (manual)" if device.get("manual") else ""
        print(f"  - {device.get('name')} [{services}] -> {queue} ({flag}){manual}")
    print("RESULT: ok")
    return 0


# --------------------------------------------------------------------------- #
# Tray UI (PyQt5)
# --------------------------------------------------------------------------- #
def wait_for_system_tray(app, tray_class) -> bool:
    deadline = time.monotonic() + max(0.0, TRAY_WAIT_TIMEOUT_SECONDS)
    logged = False
    while not tray_class.isSystemTrayAvailable():
        if not logged:
            sys.stderr.write("beagle-netbridge-tray: waiting for system tray\n")
            logged = True
        if time.monotonic() >= deadline:
            return False
        app.processEvents()
        time.sleep(max(0.1, TRAY_WAIT_INTERVAL_SECONDS))
    return True


def run_tray() -> int:
    from PyQt5 import QtCore, QtGui, QtWidgets

    class AddDeviceDialog(QtWidgets.QDialog):
        def __init__(self, parent=None) -> None:
            super().__init__(parent)
            self.setWindowTitle("Gerät hinzufügen")
            self.setModal(True)
            form = QtWidgets.QFormLayout(self)

            self.name_edit = QtWidgets.QLineEdit()
            self.name_edit.setPlaceholderText("z. B. Wohnzimmer-Drucker")
            self.addr_edit = QtWidgets.QLineEdit()
            self.addr_edit.setPlaceholderText("IP-Adresse oder Hostname")
            self.port_spin = QtWidgets.QSpinBox()
            self.port_spin.setRange(1, 65535)
            self.port_spin.setValue(9100)
            self.kind_combo = QtWidgets.QComboBox()
            self.kind_combo.addItem("Raw / JetDirect (Port 9100)", "raw")
            self.kind_combo.addItem("IPP (Port 631)", "ipp")
            self.rp_edit = QtWidgets.QLineEdit("ipp/print")

            form.addRow("Name:", self.name_edit)
            form.addRow("Adresse:", self.addr_edit)
            form.addRow("Typ:", self.kind_combo)
            form.addRow("Port:", self.port_spin)
            form.addRow("IPP-Pfad:", self.rp_edit)

            self.kind_combo.currentIndexChanged.connect(self._sync_kind)
            self._sync_kind()

            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel)
            buttons.accepted.connect(self.accept)
            buttons.rejected.connect(self.reject)
            form.addRow(buttons)

        def _sync_kind(self) -> None:
            kind = self.kind_combo.currentData()
            if kind == "raw":
                self.port_spin.setValue(9100)
                self.rp_edit.setEnabled(False)
            else:
                if self.port_spin.value() == 9100:
                    self.port_spin.setValue(631)
                self.rp_edit.setEnabled(True)

        def values(self) -> dict:
            return {
                "name": self.name_edit.text().strip(),
                "address": self.addr_edit.text().strip(),
                "port": self.port_spin.value(),
                "rp": self.rp_edit.text().strip() or "ipp/print",
            }

    class TrayManager(QtCore.QObject):
        # Emitted from worker threads; delivered on the GUI thread via Qt's
        # queued connections so all UI work stays on the main thread and the
        # Plasma DBus menu requests are never blocked by network/CUPS I/O.
        dataReady = QtCore.pyqtSignal(object, object)
        uiMessage = QtCore.pyqtSignal(str, str)

        def __init__(self, app: QtWidgets.QApplication) -> None:
            super().__init__()
            self.app = app
            self.control = NetBridgeControl()
            self.catalog: dict | None = None
            self.wired: dict[str, str] = {}
            self._busy = False
            self._menu_open = False
            self._pending_data: tuple[dict | None, dict[str, str]] | None = None

            self.tray = QtWidgets.QSystemTrayIcon(self._icon(), self.app)
            self.tray.setToolTip(APP_NAME)
            self.menu = QtWidgets.QMenu()
            self.tray.setContextMenu(self.menu)
            self.menu.aboutToShow.connect(self._on_menu_show)
            self.menu.aboutToHide.connect(self._on_menu_hide)
            self.tray.activated.connect(self._on_activated)
            self.tray.show()

            self.dataReady.connect(self._on_data)
            self.uiMessage.connect(self._notify)

            # Build a usable menu immediately (no I/O) so the very first DBus
            # menu request from plasmashell returns instantly.
            self._rebuild_menu()

            self.timer = QtCore.QTimer(self)
            self.timer.setInterval(20000)
            self.timer.timeout.connect(self.refresh)
            self.timer.start()

            self.refresh()

        # -- helpers ---------------------------------------------------- #
        def _icon(self) -> "QtGui.QIcon":
            for path in ICON_PATHS:
                if os.path.exists(path):
                    icon = QtGui.QIcon(path)
                    if not icon.isNull():
                        return icon
            for path in WALLPAPER_ICON_SOURCES:
                if not os.path.exists(path):
                    continue
                pixmap = QtGui.QPixmap(path)
                if pixmap.isNull():
                    continue
                # Crop the Beagle head/visor from the Cyberpunk wallpaper so
                # the tray icon is the product dog, not a generic device icon.
                size = min(int(pixmap.width() * 0.367), int(pixmap.height() * 0.653))
                x = max(0, min(int(pixmap.width() * 0.351), pixmap.width() - size))
                y = max(0, min(int(pixmap.height() * 0.090), pixmap.height() - size))
                cropped = pixmap.copy(x, y, size, size)
                return QtGui.QIcon(cropped.scaled(
                    256, 256, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation))
            icon = QtGui.QIcon.fromTheme("printer")
            if icon.isNull():
                icon = QtGui.QIcon.fromTheme("network-workgroup")
            if icon.isNull():
                pixmap = QtGui.QPixmap(64, 64)
                pixmap.fill(QtGui.QColor("#2d6cdf"))
                icon = QtGui.QIcon(pixmap)
            return icon

        def _on_activated(self, reason) -> None:
            if reason in (QtWidgets.QSystemTrayIcon.Trigger,
                          QtWidgets.QSystemTrayIcon.Context):
                # Keep menu interaction responsive: do not rebuild the menu
                # while the user is clicking entries.
                self.menu.popup(QtGui.QCursor.pos())

        def _on_menu_show(self) -> None:
            self._menu_open = True

        def _on_menu_hide(self) -> None:
            self._menu_open = False
            if self._pending_data is not None:
                catalog, wired = self._pending_data
                self._pending_data = None
                self.catalog = catalog
                self.wired = wired or {}
                self._rebuild_menu()

        def _notify(self, title: str, message: str) -> None:
            self.tray.showMessage(title, message, self._icon(), 5000)

        # -- data (all blocking work happens off the GUI thread) -------- #
        def refresh(self) -> None:
            if self._busy:
                return
            self._busy = True
            threading.Thread(target=self._refresh_worker, daemon=True).start()

        def _refresh_worker(self) -> None:
            try:
                catalog = self.control.status()
                if catalog is None:
                    catalog = self.control.catalog()
                wired = cups_managed_queues()
            except Exception:  # never let a worker thread die silently
                catalog, wired = None, {}
            self.dataReady.emit(catalog, wired)

        def _on_data(self, catalog, wired) -> None:
            self._busy = False
            if self._menu_open:
                self._pending_data = (catalog, wired or {})
                return
            self.catalog = catalog
            self.wired = wired or {}
            self._rebuild_menu()

        def _run_action(self, op) -> None:
            """Run a blocking control/CUPS operation off the GUI thread.

            ``op`` returns an optional ``(title, message)`` tuple to notify.
            """
            def work() -> None:
                try:
                    message = op()
                except Exception as exc:  # noqa: BLE001 - surface to the user
                    message = (APP_NAME, f"Fehler: {exc}")
                if message:
                    self.uiMessage.emit(message[0], message[1])
                try:
                    catalog = self.control.status()
                    if catalog is None:
                        catalog = self.control.catalog()
                    wired = cups_managed_queues()
                except Exception:
                    catalog, wired = None, {}
                self.dataReady.emit(catalog, wired)

            threading.Thread(target=work, daemon=True).start()

        def _rebuild_menu(self) -> None:
            self.menu.clear()
            header = self.menu.addAction(APP_NAME)
            header.setEnabled(False)

            if self.catalog is None:
                status = self.menu.addAction("● Agent nicht erreichbar")
                status.setEnabled(False)
            else:
                host = self.catalog.get("agent_host", "?")
                devices = self.catalog.get("devices", [])
                status = self.menu.addAction(f"● Verbunden mit {host}")
                status.setEnabled(False)
                self.menu.addSeparator()
                if not devices:
                    empty = self.menu.addAction("Keine Geräte gefunden")
                    empty.setEnabled(False)
                self._add_control_center_menu(self.catalog.get("thinclient", {}))
                self.menu.addSeparator()
                for device in devices:
                    self._add_device_menu(device)

            self.menu.addSeparator()
            self.menu.addAction("Thinclient Verwaltung öffnen", self.action_open_admin)
            self.menu.addAction("Geräte suchen…", self.action_rescan)
            self.menu.addAction("Gerät hinzufügen…", self.action_add)
            self.menu.addAction("Druckerverwaltung öffnen", self.action_open_cups)
            self.menu.addAction("Agent neu starten", self.action_restart_agent)
            self.menu.addAction("Aktualisieren", self.refresh)
            self.menu.addSeparator()
            self.menu.addAction("Beenden", self.app.quit)

        def _add_control_center_menu(self, thinclient: dict) -> None:
            control = self.menu.addMenu("Thinclient verwalten")
            self._add_stream_menu(control, thinclient.get("stream", {}))
            self._add_services_menu(control, thinclient.get("services", {}))
            self._add_usb_menu(control, thinclient.get("usb", {}))
            self._add_av_menu(control, thinclient)
            self._add_network_menu(control, thinclient.get("network", {}))

        def _add_stream_menu(self, parent, stream: dict) -> None:
            menu = parent.addMenu("Streamqualität")
            current = stream.get("profile", "unbekannt")
            info = menu.addAction(f"Aktiv: {current}")
            info.setEnabled(False)
            auto = stream.get("auto_quality", {})
            bucket = auto.get("bucket")
            if bucket:
                line = menu.addAction(
                    f"Auto: {bucket}, RTT {auto.get('rtt_avg_ms', '?')} ms, Loss {auto.get('loss', '?')}%")
                line.setEnabled(False)
            menu.addSeparator()
            presets = stream.get("presets", {})
            for profile in ("auto", "lan-ultra", "smooth", "balanced", "economy", "survival"):
                label = presets.get(profile, {}).get("label", profile)
                menu.addAction(label, lambda _=False, p=profile: self.action_set_stream_profile(p))
            menu.addSeparator()
            menu.addAction("Stream neu starten",
                           lambda _=False: self.action_service("stream", "restart"))

        def _add_services_menu(self, parent, services: dict) -> None:
            menu = parent.addMenu("Dienste")
            labels = {
                "usb_tunnel": "USB/Mic Tunnel",
                "camera_stream": "Webcam Stream",
                "audio_input_bridge": "Mic Bridge Quelle",
                "stream": "Stream Launcher",
                "netbridge_agent": "NetBridge Agent",
            }
            for key in ("usb_tunnel", "camera_stream", "audio_input_bridge", "stream", "netbridge_agent"):
                state = services.get(key, {})
                active = state.get("active", "unknown")
                submenu = menu.addMenu(f"{labels.get(key, key)}: {active}")
                unit = submenu.addAction(state.get("unit", key))
                unit.setEnabled(False)
                if key != "audio_input_bridge":
                    submenu.addAction("Starten", lambda _=False, s=key: self.action_service(s, "start"))
                    submenu.addAction("Neu starten", lambda _=False, s=key: self.action_service(s, "restart"))

        def _add_usb_menu(self, parent, usb: dict) -> None:
            menu = parent.addMenu("USB Geräte")
            state = menu.addAction(f"Tunnel: {usb.get('tunnel_state', 'unknown')}")
            state.setEnabled(False)
            devices = usb.get("devices", [])
            if not devices:
                empty = menu.addAction("Keine USB-Geräte erkannt")
                empty.setEnabled(False)
                return
            for device in devices:
                busid = str(device.get("busid") or device.get("id") or "")
                name = device.get("product") or device.get("name") or busid or "USB-Gerät"
                bound = bool(device.get("bound") or device.get("exported"))
                submenu = menu.addMenu(("✓ " if bound else "  ") + name)
                if busid:
                    line = submenu.addAction(f"Bus-ID: {busid}")
                    line.setEnabled(False)
                    if bound:
                        submenu.addAction("Vom VM-Tunnel lösen",
                                          lambda _=False, b=busid: self.action_usb("unbind", b))
                    else:
                        submenu.addAction("Für VM freigeben",
                                          lambda _=False, b=busid: self.action_usb("bind", b))

        def _add_av_menu(self, parent, thinclient: dict) -> None:
            menu = parent.addMenu("Mikrofon & Webcam")
            audio = thinclient.get("audio", {})
            video = thinclient.get("video", {})
            capture = audio.get("capture_devices", [])
            cameras = video.get("devices", [])
            mic_header = menu.addAction(f"Mikrofone: {len(capture)}")
            mic_header.setEnabled(False)
            for device in capture[:6]:
                label = device.get("name") or device.get("summary") or device.get("id") or "Audio Capture"
                item = menu.addAction(str(label)[:80])
                item.setEnabled(False)
            menu.addSeparator()
            cam_header = menu.addAction(f"Webcams: {len(cameras)}")
            cam_header.setEnabled(False)
            for device in cameras[:6]:
                label = f"{device.get('node', '')} {device.get('name', '')}".strip()
                item = menu.addAction(label[:80] or "Video Device")
                item.setEnabled(False)
            menu.addSeparator()
            menu.addAction("USB/Mic Tunnel neu starten",
                           lambda _=False: self.action_service("usb_tunnel", "restart"))
            menu.addAction("Webcam Stream neu starten",
                           lambda _=False: self.action_service("camera_stream", "restart"))

        def _add_network_menu(self, parent, network: dict) -> None:
            menu = parent.addMenu("Netzwerk")
            interfaces = network.get("interfaces", [])
            if not interfaces:
                empty = menu.addAction("Keine Netzwerkdaten")
                empty.setEnabled(False)
                return
            for iface in interfaces:
                name = iface.get("name", "?")
                state = iface.get("state", "unknown")
                ip = iface.get("ipv4", "")
                speed = iface.get("speed_mbps", "")
                wifi = " WLAN" if iface.get("wireless") else ""
                item = menu.addAction(f"{name}{wifi}: {state} {ip} {speed}M".strip())
                item.setEnabled(False)

        def _add_device_menu(self, device: dict) -> None:
            name = device.get("name") or device.get("id") or "Gerät"
            queue = queue_name(device)
            wired = queue in self.wired
            label = ("✓ " if wired else "  ") + name
            submenu = self.menu.addMenu(label)
            info = submenu.addAction(f"Adresse: {device.get('address', '?')}")
            info.setEnabled(False)
            for kind, service in device.get("services", {}).items():
                line = submenu.addAction(
                    f"{kind.upper()} · Geräteport {service.get('device_port')} "
                    f"→ Proxy {service.get('proxy_port', '?')}")
                line.setEnabled(False)
            state = submenu.addAction(
                "In CUPS eingerichtet" if wired else "Noch nicht in CUPS")
            state.setEnabled(False)
            submenu.addSeparator()
            if wired:
                submenu.addAction("Testseite drucken",
                                  lambda _=False, q=queue: self.action_test_print(q))
            if device.get("manual"):
                submenu.addAction("Gerät entfernen",
                                  lambda _=False, d=device.get("id", ""): self.action_remove(d))

        # -- actions (network/CUPS work is dispatched to worker threads) - #
        def action_rescan(self) -> None:
            def op():
                result = self.control.rescan()
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                count = len(result.get("devices", []))
                return (APP_NAME, f"Suche abgeschlossen: {count} Gerät(e).")
            self._run_action(op)

        def action_add(self) -> None:
            dialog = AddDeviceDialog()
            if dialog.exec_() != QtWidgets.QDialog.Accepted:
                return
            values = dialog.values()
            if not values["address"]:
                self._notify(APP_NAME, "Bitte eine Adresse angeben.")
                return

            def op():
                result = self.control.add_static(
                    address=values["address"], port=values["port"],
                    name=values["name"], rp=values["rp"])
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                if not result.get("ok"):
                    return (APP_NAME, f"Fehler: {result.get('error', 'unbekannt')}")
                return (APP_NAME, "Gerät hinzugefügt.")
            self._run_action(op)

        def action_remove(self, device_id: str) -> None:
            if not device_id:
                return

            def op():
                result = self.control.remove_static(device_id)
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                if not result.get("ok"):
                    return (APP_NAME, f"Fehler: {result.get('error', 'unbekannt')}")
                return (APP_NAME, "Gerät entfernt.")
            self._run_action(op)

        def action_test_print(self, queue: str) -> None:
            def op():
                ok, message = print_test_page(queue)
                return (APP_NAME,
                        f"Testseite gesendet: {queue}" if ok else f"Druckfehler: {message}")
            self._run_action(op)

        def action_open_cups(self) -> None:
            QtGui.QDesktopServices.openUrl(QtCore.QUrl("http://localhost:631/printers/"))

        def action_open_admin(self) -> None:
            for candidate in ADMIN_APP_PATHS:
                if os.access(candidate, os.X_OK):
                    try:
                        subprocess.Popen([candidate], close_fds=True)
                    except OSError as exc:
                        self._notify(APP_NAME, f"Thinclient Verwaltung konnte nicht gestartet werden: {exc}")
                    return
            self._notify(APP_NAME, "Thinclient Verwaltung ist nicht installiert.")

        def action_set_stream_profile(self, profile: str) -> None:
            def op():
                result = self.control.set_stream_profile(profile)
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                if not result.get("ok"):
                    return (APP_NAME, f"Fehler: {result.get('error', 'unbekannt')}")
                return (APP_NAME, f"Streamprofil gesetzt: {profile}.")
            self._run_action(op)

        def action_service(self, service: str, action: str = "restart") -> None:
            def op():
                result = self.control.service_action(service, action)
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                if not result.get("ok"):
                    return (APP_NAME, f"Fehler: {result.get('error', 'unbekannt')}")
                return (APP_NAME, f"Dienstaktion ausgeführt: {service}.")
            self._run_action(op)

        def action_usb(self, action: str, busid: str) -> None:
            def op():
                if action == "bind":
                    result = self.control.usb_bind(busid)
                else:
                    result = self.control.usb_unbind(busid)
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                if not result.get("ok"):
                    return (APP_NAME, f"Fehler: {result.get('error', 'unbekannt')}")
                return (APP_NAME, f"USB aktualisiert: {busid}.")
            self._run_action(op)

        def action_restart_agent(self) -> None:
            def op():
                result = self.control.restart_agent()
                if result is None:
                    return (APP_NAME, "Agent nicht erreichbar.")
                if not result.get("ok"):
                    return (APP_NAME, f"Fehler: {result.get('error', 'unbekannt')}")
                time.sleep(1.0)
                return (APP_NAME, "Agent-Neustart ausgelöst.")
            self._run_action(op)

    app = QtWidgets.QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setDesktopFileName(APP_ID)
    app.setQuitOnLastWindowClosed(False)

    if not wait_for_system_tray(app, QtWidgets.QSystemTrayIcon):
        sys.stderr.write("beagle-netbridge-tray: no system tray available after wait\n")
        return 1

    manager = TrayManager(app)
    app.setProperty("beagleNetBridgeTrayManager", manager)
    return app.exec_()


def main(argv: list[str] | None = None) -> int:
    argv = argv if argv is not None else sys.argv[1:]
    if "--selftest" in argv:
        return selftest()
    return run_tray()


if __name__ == "__main__":
    raise SystemExit(main())
NETBRIDGETRAYEOF
    if [[ -n "$BEAGLE_NETBRIDGE_TRAY_B64" ]]; then
      printf '%s' "$BEAGLE_NETBRIDGE_TRAY_B64" | base64 -d > /usr/local/bin/beagle-netbridge-tray
    fi
    chmod 0755 /usr/local/bin/beagle-netbridge-tray

    cat > /usr/local/bin/beagle-thinclient-admin <<'THINCLIENTADMINEOF'
#!/usr/bin/env python3
from importlib.machinery import SourceFileLoader
from pathlib import Path
import subprocess
import sys

tray = Path("/usr/local/bin/beagle-netbridge-tray")
if not tray.is_file():
    raise SystemExit("beagle-netbridge-tray backend not installed")
backend = SourceFileLoader("beagle_netbridge_tray_admin_fallback", str(tray)).load_module()
if "--selftest" in sys.argv[1:]:
    print(f"backend: {backend.__file__}")
    print("RESULT: ok")
    raise SystemExit(0)
if Path("/usr/bin/systemsettings").exists():
    subprocess.Popen(["/usr/bin/systemsettings"], close_fds=True)
    raise SystemExit(0)
raise SystemExit("full beagle-thinclient-admin payload was not embedded")
THINCLIENTADMINEOF
    if [[ -n "$BEAGLE_THINCLIENT_ADMIN_B64" ]]; then
      printf '%s' "$BEAGLE_THINCLIENT_ADMIN_B64" | base64 -d > /usr/local/bin/beagle-thinclient-admin
    fi
    chmod 0755 /usr/local/bin/beagle-thinclient-admin

    install -d -m 0755 /usr/local/share/applications
    cat > /usr/local/share/applications/beagle-thinclient-admin.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Beagle Thinclient Verwaltung
GenericName=Thinclient system manager
Comment=Manage thin-client updates, services, USB devices and shared LAN devices
Exec=/usr/local/bin/beagle-thinclient-admin
Icon=beagle-netbridge-tray
Terminal=false
Categories=Utility;System;HardwareSettings;
StartupNotify=true
EOF
    if [[ -n "$BEAGLE_THINCLIENT_ADMIN_DESKTOP_B64" ]]; then
      printf '%s' "$BEAGLE_THINCLIENT_ADMIN_DESKTOP_B64" | base64 -d > /usr/local/share/applications/beagle-thinclient-admin.desktop
    fi
    python3 - "${BEAGLE_WALLPAPER_PATH:-}" <<'PY' || true
import os
import sys
from PyQt5 import QtCore, QtGui

sources = [
    sys.argv[1] if len(sys.argv) > 1 else "",
    "/usr/local/share/beagle/wallpapers/beagle-cyberpunk-wallpaper.png",
    "/usr/local/share/beagle-os/beagleos.png",
]
image = QtGui.QImage()
for source in sources:
    if source and os.path.exists(source) and image.load(source):
        break
if image.isNull():
    raise SystemExit(0)
size = min(int(image.width() * 0.367), int(image.height() * 0.653))
x = max(0, min(int(image.width() * 0.351), image.width() - size))
y = max(0, min(int(image.height() * 0.090), image.height() - size))
cropped = image.copy(x, y, size, size).scaled(
    256, 256, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
for path in (
    "/usr/local/share/beagle/beagle-netbridge-tray.png",
    "/usr/local/share/icons/hicolor/256x256/apps/beagle-netbridge-tray.png",
    "/usr/share/pixmaps/beagle-netbridge-tray.png",
):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    cropped.save(path, "PNG")
PY
    gtk-update-icon-cache -q -t -f /usr/local/share/icons/hicolor >/dev/null 2>&1 || true

    install -d -m 0755 /etc/xdg/autostart
    cat > /etc/xdg/autostart/beagle-netbridge-tray.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Beagle NetBridge
GenericName=Network device manager
Comment=Manage the thin-client LAN devices (printers) shared with this VM
Exec=/usr/local/bin/beagle-netbridge-tray
Icon=beagle-netbridge-tray
Terminal=false
Categories=Utility;System;HardwareSettings;
X-GNOME-Autostart-enabled=true
X-KDE-autostart-after=panel
StartupNotify=false
EOF
  }

  # x11vnc: capture X11 display :0 so noVNC shows actual desktop (not QEMU VGA/TTY1)
  cat > /etc/systemd/system/beagle-x11vnc.service <<EOF
[Unit]
Description=Beagle x11vnc Display Server
After=display-manager.service graphical.target
Wants=display-manager.service

[Service]
Type=simple
User=${GUEST_USER}
Group=${GUEST_USER}
Environment=HOME=/home/${GUEST_USER}
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${GUEST_USER}/.Xauthority
ExecStartPre=/bin/bash -lc 'for _ in {1..180}; do if [[ -S /tmp/.X11-unix/X0 && -s /home/${GUEST_USER}/.Xauthority ]] && DISPLAY=:0 XAUTHORITY=/home/${GUEST_USER}/.Xauthority xrandr --query >/dev/null 2>&1; then exit 0; fi; sleep 1; done; echo "Timed out waiting for X11 session" >&2; exit 1'
ExecStart=/usr/bin/x11vnc -display :0 -rfbport 5901 -forever -nopw -auth /home/${GUEST_USER}/.Xauthority -shared -noxdamage -xkb -noxfixes -noxrecord -nosel -cursor arrow
Restart=always
RestartSec=5
TimeoutStartSec=210

[Install]
WantedBy=graphical.target
EOF

  systemctl disable beagle-stream-server >/dev/null 2>&1 || true
  systemctl stop beagle-stream-server >/dev/null 2>&1 || true
  systemctl disable --now beagle-sunshine.service >/dev/null 2>&1 || true
  systemctl disable --now beagle-sunshine-healthcheck.timer >/dev/null 2>&1 || true
  systemctl stop beagle-sunshine-healthcheck.service >/dev/null 2>&1 || true
  pkill -x sunshine >/dev/null 2>&1 || true
  su - "$GUEST_USER" -c "systemctl --user disable --now beagle-stream-server.service >/dev/null 2>&1 || true" || true
  rm -f "/home/$GUEST_USER/.config/autostart/beagle-stream-server.desktop"
  pkill -u "$GUEST_USER" -x beagle-stream-server >/dev/null 2>&1 || true
  systemctl disable gdm3 >/dev/null 2>&1 || true
  printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
  ln -sf /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
  systemctl daemon-reload
  systemctl enable qemu-guest-agent.service >/dev/null 2>&1 || true
  systemctl set-default graphical.target >/dev/null

  su - "$GUEST_USER" -c "HOME=/home/$GUEST_USER XDG_CONFIG_HOME=/home/$GUEST_USER/.config beagle-stream-server --creds '$BEAGLE_STREAM_SERVER_USER' '$BEAGLE_STREAM_SERVER_PASSWORD'"
  systemctl restart display-manager.service >/dev/null 2>&1 || true
  loginctl enable-linger "$GUEST_USER" >/dev/null 2>&1 || true
  for _ in {1..60}; do
    if systemctl --user -M "$GUEST_USER@" show basic.target >/dev/null 2>&1; then
      systemctl --user -M "$GUEST_USER@" enable --now pipewire.service pipewire-pulse.service wireplumber.service >/dev/null 2>&1 || true
      break
    fi
    sleep 1
  done
  install_pipewire_resource_limits
  install_log_retention_policy
  configure_stream_port_guard
  install_beagle_guest_updater
  install_usb_microphone_normalizer
  install_thinclient_microphone_bridge
  install_beagle_netbridge_client
  systemctl enable --now beagle-stream-server.service >/dev/null 2>&1 || true
  systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
  systemctl enable --now beagle-stream-server-guardian.service >/dev/null 2>&1 || true
  systemctl enable beagle-x11vnc.service >/dev/null 2>&1 || true
  if ! wait_for_beagle_stream_server_ready; then
    echo "WARN: Beagle Stream Server did not become ready during firstboot; continuing and leaving repair timer active" >&2
    /usr/local/bin/beagle-stream-server-healthcheck --repair-only >/dev/null 2>&1 || true
  fi

  touch "$DONE_FILE"
fi

if [[ ! -f "$CALLBACK_DONE_FILE" ]]; then
  if ! post_completion_callback; then
    echo "WARN: firstboot completion callback failed; continuing with local finalize/reboot" >&2
  fi
  touch "$CALLBACK_DONE_FILE"
  systemctl reboot >/dev/null 2>&1 || reboot >/dev/null 2>&1 || true
fi
