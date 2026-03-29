#!/usr/bin/env bash
set -euo pipefail

export DEBIAN_FRONTEND=noninteractive

GUEST_USER="__GUEST_USER__"
SUNSHINE_USER="__SUNSHINE_USER__"
SUNSHINE_PASSWORD="__SUNSHINE_PASSWORD__"
SUNSHINE_PORT="__SUNSHINE_PORT__"
SUNSHINE_URL="__SUNSHINE_URL__"
SUNSHINE_ORIGIN_WEB_UI_ALLOWED="__SUNSHINE_ORIGIN_WEB_UI_ALLOWED__"
DONE_FILE="/var/lib/beagle/ubuntu-firstboot.done"

if [[ -f "$DONE_FILE" ]]; then
  exit 0
fi

install -d -m 0755 /var/lib/beagle

echo 'lightdm shared/default-x-display-manager select lightdm' | debconf-set-selections
apt-get update
apt-get install -y --no-install-recommends \
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

tmpdir="$(mktemp -d)"
trap 'rm -rf "$tmpdir"' EXIT
curl -fsSLo "$tmpdir/sunshine.deb" "$SUNSHINE_URL"
apt-get install -y "$tmpdir/sunshine.deb"

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
