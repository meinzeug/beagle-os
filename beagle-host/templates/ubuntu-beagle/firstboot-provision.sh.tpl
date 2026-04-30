#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

GUEST_USER="__GUEST_USER__"
IDENTITY_LOCALE="__IDENTITY_LOCALE__"
IDENTITY_LANGUAGE="__IDENTITY_LANGUAGE__"
IDENTITY_KEYMAP="__IDENTITY_KEYMAP__"
DESKTOP_ID="__DESKTOP_ID__"
DESKTOP_SESSION="__DESKTOP_SESSION__"
DESKTOP_SESSION_EFFECTIVE="${DESKTOP_SESSION}"
DESKTOP_PACKAGES="__DESKTOP_PACKAGES__"
SOFTWARE_PACKAGES="__SOFTWARE_PACKAGES__"
PACKAGE_PRESETS="__PACKAGE_PRESETS__"
NETWORK_MAC="__NETWORK_MAC__"
SUNSHINE_USER="__SUNSHINE_USER__"
SUNSHINE_PASSWORD="__SUNSHINE_PASSWORD__"
SUNSHINE_PORT="__SUNSHINE_PORT__"
SUNSHINE_URL="__SUNSHINE_URL__"
SUNSHINE_ORIGIN_WEB_UI_ALLOWED="__SUNSHINE_ORIGIN_WEB_UI_ALLOWED__"
CALLBACK_URL="__CALLBACK_URL__"
CALLBACK_PINNED_PUBKEY="__CALLBACK_PINNED_PUBKEY__"
FAILED_CALLBACK_URL="${CALLBACK_URL%/complete}/failed"
DONE_FILE="/var/lib/beagle/ubuntu-firstboot.done"
CALLBACK_DONE_FILE="/var/lib/beagle/ubuntu-firstboot-callback.done"
TMPDIR_WORK=""

cleanup_tmpdir() {
  if [[ -n "$TMPDIR_WORK" && -d "$TMPDIR_WORK" ]]; then
    rm -rf "$TMPDIR_WORK"
  fi
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
set -euo pipefail

for _ in {1..30}; do
  if xrandr --query >/dev/null 2>&1; then
    break
  fi
  sleep 1
done

output="$(xrandr --query | awk '/ connected/{print $1; exit}')"
[[ -n "$output" ]] || exit 0

xrandr --newmode "3840x2160_60.00" 712.75 3840 4160 4576 5312 2160 2163 2168 2237 -hsync +vsync >/dev/null 2>&1 || true
xrandr --addmode "$output" "3840x2160_60.00" >/dev/null 2>&1 || true
if xrandr --output "$output" --primary --mode "3840x2160_60.00" >/dev/null 2>&1; then
  exit 0
fi

xrandr --output "$output" --primary --mode "1920x1080" >/dev/null 2>&1 || true
EOF
  chmod 0755 /usr/local/bin/beagle-vkms-xrandr-setup

  cat > /etc/xdg/autostart/beagle-vkms-xrandr.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=Beagle vkms xrandr setup
Exec=/usr/local/bin/beagle-vkms-xrandr-setup
OnlyShowIn=XFCE;
NoDisplay=false
X-GNOME-Autostart-enabled=true
EOF

  systemctl daemon-reload
  systemctl enable vkms-virtual-display.service >/dev/null 2>&1 || true
}

configure_default_browser() {
  install -d -m 0700 -o "$GUEST_USER" -g "$GUEST_USER" \
    "/home/$GUEST_USER/.config" \
    "/home/$GUEST_USER/.config/xfce4"
  update-alternatives --install /usr/bin/x-www-browser x-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --install /usr/bin/gnome-www-browser gnome-www-browser /usr/bin/google-chrome-stable 200 >/dev/null 2>&1 || true
  update-alternatives --set x-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  update-alternatives --set gnome-www-browser /usr/bin/google-chrome-stable >/dev/null 2>&1 || true
  cat > "/home/$GUEST_USER/.config/xfce4/helpers.rc" <<'EOF'
WebBrowser=google-chrome
MailReader=thunderbird
TerminalEmulator=xfce4-terminal
FileManager=thunar
EOF
  cat > "/home/$GUEST_USER/.config/mimeapps.list" <<'EOF'
[Default Applications]
x-scheme-handler/http=google-chrome.desktop
x-scheme-handler/https=google-chrome.desktop
text/html=google-chrome.desktop
application/xhtml+xml=google-chrome.desktop
x-scheme-handler/about=google-chrome.desktop
x-scheme-handler/unknown=google-chrome.desktop
EOF
  chown "$GUEST_USER:$GUEST_USER" \
    "/home/$GUEST_USER/.config/xfce4/helpers.rc" \
    "/home/$GUEST_USER/.config/mimeapps.list"
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

wait_for_sunshine_ready() {
  local -a expected_ports=()

  if [[ -n "$SUNSHINE_PORT" ]]; then
    expected_ports=("$SUNSHINE_PORT" "$((SUNSHINE_PORT + 1))")
  else
    expected_ports=("47984" "47990")
  fi

  for _ in {1..180}; do
    if systemctl is-active --quiet beagle-sunshine.service; then
      for port in "${expected_ports[@]}"; do
        if ss -H -ltn "( sport = :${port} )" 2>/dev/null | grep -q LISTEN; then
          return 0
        fi
      done
    fi
    if (( _ % 30 == 0 )); then
      /usr/local/bin/beagle-sunshine-healthcheck --repair-only >/dev/null 2>&1 || true
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
  apt_retry apt-get install -y --fix-missing \
    qemu-guest-agent \
    openssh-server \
    xserver-xorg \
    x11-xserver-utils \
    lightdm \
    lightdm-gtk-greeter \
    accountsservice \
    curl \
    ca-certificates \
    pipewire \
    pipewire-pulse \
    wireplumber \
    pulseaudio-utils \
    usbutils \
    xdg-utils \
    x11vnc
  repair_interrupted_dpkg
  if [[ -n "$DESKTOP_PACKAGES" ]]; then
    apt_retry apt-get install -y --fix-missing ${DESKTOP_PACKAGES}
    repair_interrupted_dpkg
  fi
  if [[ -n "$SOFTWARE_PACKAGES" ]]; then
    apt_retry apt-get install -y --fix-missing ${SOFTWARE_PACKAGES}
    repair_interrupted_dpkg
  fi
  resolve_desktop_session

  TMPDIR_WORK="$(mktemp -d)"
  curl -fsSLo "$TMPDIR_WORK/sunshine.deb" "$SUNSHINE_URL"
  apt_retry apt-get install -y "$TMPDIR_WORK/sunshine.deb"
  repair_interrupted_dpkg
  configure_system_locale
  configure_keyboard_layout
  configure_virtual_display_vkms
  install_google_chrome

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
    "/home/$GUEST_USER/.config/sunshine" \
    "/home/$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml"
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

  cat > "/home/$GUEST_USER/.config/sunshine/sunshine.conf" <<EOF
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
$( if [[ -n "$SUNSHINE_PORT" ]]; then printf 'port = %s\n' "$SUNSHINE_PORT"; fi )
EOF

  cat > "/home/$GUEST_USER/.config/sunshine/apps.json" <<'EOF'
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

  chown -R "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config"
  chown "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.xprofile"
  configure_default_browser

  cat > /etc/systemd/system/beagle-sunshine.service <<EOF
[Unit]
Description=Beagle Sunshine
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
ExecStartPre=/bin/bash -lc 'pulse_socket="/run/user/${GUEST_UID}/pulse/native"; for _ in {1..180}; do if [[ -S /tmp/.X11-unix/X0 && -s /home/${GUEST_USER}/.Xauthority && -d /run/user/${GUEST_UID} && -S /run/user/${GUEST_UID}/bus && -S "\$pulse_socket" ]] && DISPLAY=:0 XAUTHORITY=/home/${GUEST_USER}/.Xauthority xrandr --query >/dev/null 2>&1; then sleep 5; exit 0; fi; sleep 1; done; echo "Timed out waiting for an active graphical/audio session on :0" >&2; exit 1'
ExecStart=/usr/bin/sunshine
Restart=always
RestartSec=2
TimeoutStartSec=210

[Install]
WantedBy=graphical.target
EOF

  install -d -m 0755 /etc/beagle
  cat > /etc/beagle/sunshine-healthcheck.env <<EOF
SUNSHINE_USER=${SUNSHINE_USER}
SUNSHINE_PASSWORD=${SUNSHINE_PASSWORD}
SUNSHINE_PORT=${SUNSHINE_PORT}
GUEST_USER=${GUEST_USER}
GUEST_UID=${GUEST_UID}
EOF
  chmod 0600 /etc/beagle/sunshine-healthcheck.env

  cat > /usr/local/bin/beagle-sunshine-healthcheck <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="/etc/beagle/sunshine-healthcheck.env"
[[ -r "$ENV_FILE" ]] || exit 1
# shellcheck disable=SC1090
source "$ENV_FILE"

SUNSHINE_USER="${SUNSHINE_USER:-sunshine}"
SUNSHINE_PASSWORD="${SUNSHINE_PASSWORD:-}"
SUNSHINE_PORT="${SUNSHINE_PORT:-}"
GUEST_USER="${GUEST_USER:-beagle}"
GUEST_UID="${GUEST_UID:-$(id -u "$GUEST_USER" 2>/dev/null || echo 1000)}"

repair="${1:-}"
api_port=47990
if [[ -n "$SUNSHINE_PORT" ]]; then
  api_port="$((SUNSHINE_PORT + 1))"
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
  systemctl enable beagle-sunshine.service >/dev/null 2>&1 || true
  systemctl restart beagle-sunshine.service >/dev/null 2>&1 || true
}

ensure_timer() {
  systemctl enable --now beagle-sunshine-healthcheck.timer >/dev/null 2>&1 || true
}

is_api_ready() {
  [[ -n "$SUNSHINE_PASSWORD" ]] || return 1
  # Sunshine uses a self-signed cert on 127.0.0.1; --insecure disables CN check
  # while --pinnedpubkey (when set) ensures cryptographic pinning.
  # tls-bypass-allowlist: loopback Sunshine API, self-signed cert, pubkey-pinned
  local _tls_args=(--insecure)  # tls-bypass-allowlist: Sunshine loopback
  [[ -n "${SUNSHINE_PINNED_PUBKEY:-}" ]] && _tls_args+=(--pinnedpubkey "$SUNSHINE_PINNED_PUBKEY")
  curl -fsS --connect-timeout 3 --max-time 5 \
    "${_tls_args[@]}" \
    --user "${SUNSHINE_USER}:${SUNSHINE_PASSWORD}" \
    "https://127.0.0.1:${api_port}/api/apps" >/dev/null
}

ensure_timer

if [[ "$repair" == "--repair-only" ]]; then
  restart_stack
  exit 0
fi

if ! systemctl is-active --quiet beagle-sunshine.service; then
  restart_stack
  exit 0
fi

if ! pgrep -x sunshine >/dev/null 2>&1; then
  restart_stack
  exit 0
fi

if ! is_api_ready; then
  restart_stack
fi
EOF
  chmod 0755 /usr/local/bin/beagle-sunshine-healthcheck

  cat > /etc/systemd/system/beagle-sunshine-healthcheck.service <<'EOF'
[Unit]
Description=Beagle Sunshine Healthcheck and Repair
After=network-online.target beagle-sunshine.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/local/bin/beagle-sunshine-healthcheck
EOF

  cat > /etc/systemd/system/beagle-sunshine-healthcheck.timer <<EOF
[Unit]
Description=Run Beagle Sunshine healthcheck periodically

[Timer]
OnBootSec=30s
OnUnitActiveSec=30s
Persistent=true
RandomizedDelaySec=5s
Unit=beagle-sunshine-healthcheck.service

[Install]
WantedBy=timers.target
EOF

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
ExecStart=/usr/bin/x11vnc -display :0 -rfbport 5901 -forever -nopw -auth /home/${GUEST_USER}/.Xauthority -shared -noxdamage -xkb
Restart=always
RestartSec=5
TimeoutStartSec=210

[Install]
WantedBy=graphical.target
EOF

  systemctl disable sunshine >/dev/null 2>&1 || true
  systemctl stop sunshine >/dev/null 2>&1 || true
  su - "$GUEST_USER" -c "systemctl --user disable --now sunshine.service >/dev/null 2>&1 || true" || true
  rm -f "/home/$GUEST_USER/.config/autostart/sunshine.desktop"
  pkill -u "$GUEST_USER" -x sunshine >/dev/null 2>&1 || true
  systemctl disable gdm3 >/dev/null 2>&1 || true
  printf '/usr/sbin/lightdm\n' > /etc/X11/default-display-manager
  ln -sf /usr/lib/systemd/system/lightdm.service /etc/systemd/system/display-manager.service
  systemctl daemon-reload
  systemctl enable qemu-guest-agent.service >/dev/null 2>&1 || true
  systemctl set-default graphical.target >/dev/null

  su - "$GUEST_USER" -c "HOME=/home/$GUEST_USER XDG_CONFIG_HOME=/home/$GUEST_USER/.config sunshine --creds '$SUNSHINE_USER' '$SUNSHINE_PASSWORD'"
  systemctl restart display-manager.service >/dev/null 2>&1 || true
  loginctl enable-linger "$GUEST_USER" >/dev/null 2>&1 || true
  for _ in {1..60}; do
    if systemctl --user -M "$GUEST_USER@" show basic.target >/dev/null 2>&1; then
      systemctl --user -M "$GUEST_USER@" enable --now pipewire.service pipewire-pulse.service wireplumber.service >/dev/null 2>&1 || true
      break
    fi
    sleep 1
  done
  systemctl enable --now beagle-sunshine.service >/dev/null 2>&1 || true
  systemctl enable --now beagle-sunshine-healthcheck.timer >/dev/null 2>&1 || true
  systemctl enable beagle-x11vnc.service >/dev/null 2>&1 || true
  if ! wait_for_sunshine_ready; then
    echo "WARN: Sunshine did not become ready during firstboot; continuing and leaving repair timer active" >&2
    /usr/local/bin/beagle-sunshine-healthcheck --repair-only >/dev/null 2>&1 || true
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
