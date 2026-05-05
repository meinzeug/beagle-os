#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

GUEST_USER="__GUEST_USER__"
VMID="__VMID__"
BEAGLE_MANAGER_URL="__BEAGLE_MANAGER_URL__"
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
BEAGLE_STREAM_SERVER_URL="__BEAGLE_STREAM_SERVER_URL__"
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
After=multi-user.target

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
BackgroundAlternate=18,22,38
BackgroundNormal=14,18,30
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
BackgroundAlternate=0,130,145
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

[Colors:Window]
BackgroundAlternate=12,16,28
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

[Containments][2][Applets][4]
immutability=1
plugin=org.kde.plasma.icontasks

[Containments][2][Applets][4][Configuration][General]
launchers=applications:google-chrome.desktop,applications:org.kde.dolphin.desktop,applications:org.kde.konsole.desktop,applications:beagle-ai.desktop,applications:systemsettings.desktop
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
    xdg-utils
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
    nftables \
    x11vnc \
    fonts-ibm-plex \
    fonts-hack-ttf
  repair_interrupted_dpkg
  if [[ -n "$DESKTOP_PACKAGES" ]]; then
    apt_retry apt-get install -y --fix-missing --no-install-recommends ${DESKTOP_PACKAGES}
    repair_interrupted_dpkg
  fi
  if [[ -n "$SOFTWARE_PACKAGES" ]]; then
    apt_retry apt-get install -y --fix-missing --no-install-recommends ${SOFTWARE_PACKAGES}
    repair_interrupted_dpkg
  fi
  resolve_desktop_session
  install_visual_studio_code_repo

  TMPDIR_WORK="$(mktemp -d)"
  stream_runtime_variant="beagle-stream-server"
  stream_runtime_package_url="$BEAGLE_STREAM_SERVER_URL"
  curl -fsSLo "$TMPDIR_WORK/beagle-stream-server.deb" "$BEAGLE_STREAM_SERVER_URL"
  apt_retry apt-get install -y --no-install-recommends "$TMPDIR_WORK/beagle-stream-server.deb"
  repair_interrupted_dpkg
  write_stream_runtime_status "$stream_runtime_variant" "$stream_runtime_package_url"
  # Detect the beagle-stream-server binary path across package layout changes.
  BEAGLE_STREAM_SERVER_EXEC="$(command -v beagle-stream-server 2>/dev/null || echo /usr/bin/beagle-stream-server)"
  if [[ ! -x /usr/local/bin/beagle-stream-server && -n "$(command -v sunshine 2>/dev/null || true)" ]]; then
    cat > /usr/local/bin/beagle-stream-server <<'EOF'
#!/usr/bin/env bash
exec "$(command -v sunshine)" "$@"
EOF
    chmod 0755 /usr/local/bin/beagle-stream-server
    BEAGLE_STREAM_SERVER_EXEC="/usr/local/bin/beagle-stream-server"
  fi
  configure_system_locale
  configure_keyboard_layout
  install_desktop_wallpaper
  configure_virtual_display_vkms
  install_google_chrome
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
sw_preset = superfast
sw_tune = zerolatency
capture = x11
hevc_mode = 0
av1_mode = 0
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
Hidden=true
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
Environment=HOME=/home/${GUEST_USER}
Environment=XDG_CONFIG_HOME=/home/${GUEST_USER}/.config
Environment=DISPLAY=:0
Environment=XAUTHORITY=/home/${GUEST_USER}/.Xauthority
Environment=XDG_RUNTIME_DIR=/run/user/${GUEST_UID}
Environment=DBUS_SESSION_BUS_ADDRESS=unix:path=/run/user/${GUEST_UID}/bus
Environment=PULSE_SERVER=unix:/run/user/${GUEST_UID}/pulse/native
EnvironmentFile=-/etc/beagle/stream-server.env
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
GUEST_USER="${GUEST_USER:-beagle}"
GUEST_UID="${GUEST_UID:-$(id -u "$GUEST_USER" 2>/dev/null || echo 1000)}"

repair="${1:-}"
api_port=47990
if [[ -n "$BEAGLE_STREAM_SERVER_PORT" ]]; then
  api_port="$((BEAGLE_STREAM_SERVER_PORT + 1))"
fi

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

ensure_timer() {
  systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
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

ensure_timer

if [[ "$repair" == "--repair-only" ]]; then
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
  configure_stream_port_guard
  systemctl enable --now beagle-stream-server.service >/dev/null 2>&1 || true
  systemctl enable --now beagle-stream-server-healthcheck.timer >/dev/null 2>&1 || true
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
