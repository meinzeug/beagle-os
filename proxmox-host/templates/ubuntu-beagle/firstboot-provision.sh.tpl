#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

GUEST_USER="__GUEST_USER__"
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

callback_tls_args() {
  if [[ -n "$CALLBACK_PINNED_PUBKEY" ]]; then
    printf '%s\n' -k --pinnedpubkey "$CALLBACK_PINNED_PUBKEY"
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

apt_retry() {
  local attempt
  for attempt in $(seq 1 3); do
    if "$@"; then
      return 0
    fi
    sleep $((attempt * 5))
    ensure_dns_resolution
  done
  return 1
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

if [[ ! -f "$DONE_FILE" ]]; then
  ensure_dns_resolution

  echo 'lightdm shared/default-x-display-manager select lightdm' | debconf-set-selections
  apt_retry apt-get update -o Acquire::Retries=5
  apt_retry apt-get install -y --fix-missing --no-install-recommends \
    qemu-guest-agent \
    openssh-server \
    xfce4 \
    xfce4-goodies \
    xserver-xorg \
    lightdm \
    lightdm-gtk-greeter \
    accountsservice \
    curl \
    ca-certificates \
    pulseaudio-utils \
    usbutils

  TMPDIR_WORK="$(mktemp -d)"
  curl -fsSLo "$TMPDIR_WORK/sunshine.deb" "$SUNSHINE_URL"
  apt_retry apt-get install -y "$TMPDIR_WORK/sunshine.deb"

  install -d -m 0755 /etc/lightdm/lightdm.conf.d
  cat > /etc/lightdm/lightdm.conf.d/60-beagle.conf <<EOF
[Seat:*]
autologin-user=${GUEST_USER}
autologin-session=xfce
user-session=xfce
greeter-session=lightdm-gtk-greeter
EOF

  install -d -m 0700 -o "$GUEST_USER" -g "$GUEST_USER" \
    "/home/$GUEST_USER/.config" \
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

  cat > "/home/$GUEST_USER/.config/xfce4/xfconf/xfce-perchannel-xml/xfwm4.xml" <<'EOF'
<?xml version="1.0" encoding="UTF-8"?>
<channel name="xfwm4" version="1.0">
  <property name="general" type="empty">
    <property name="use_compositing" type="bool" value="false"/>
    <property name="vblank_mode" type="string" value="off"/>
  </property>
</channel>
EOF

  chown -R "$GUEST_USER:$GUEST_USER" "/home/$GUEST_USER/.config"

  cat > /etc/systemd/system/beagle-sunshine.service <<EOF
[Unit]
Description=Beagle Sunshine
After=network-online.target display-manager.service graphical.target sound.target
Wants=network-online.target

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
ExecStart=/usr/bin/sunshine
Restart=always
RestartSec=2

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
  systemctl enable --now beagle-sunshine.service >/dev/null 2>&1 || true

  touch "$DONE_FILE"
fi

if [[ ! -f "$CALLBACK_DONE_FILE" ]]; then
  post_completion_callback
  touch "$CALLBACK_DONE_FILE"
  systemctl reboot >/dev/null 2>&1 || reboot >/dev/null 2>&1 || true
fi
