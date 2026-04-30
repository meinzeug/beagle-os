#!/usr/bin/env bash
set -euo pipefail

IMG="${1:-/var/lib/libvirt/images/beagle-thinclient.qcow2}"
TMP_DIR="$(mktemp -d)"
cleanup() {
  rm -rf "$TMP_DIR"
}
trap cleanup EXIT

cat > "$TMP_DIR/90-beagle-disable-display-idle" <<'EOF'
#!/bin/sh
if command -v xset >/dev/null 2>&1; then
  xset -dpms >/dev/null 2>&1 || true
  xset s off >/dev/null 2>&1 || true
  xset s noblank >/dev/null 2>&1 || true
fi
EOF

cat > "$TMP_DIR/light-locker.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=Light Locker
Hidden=true
EOF

cat > "$TMP_DIR/xfce4-power-manager.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=XFCE Power Manager
Hidden=true
EOF

cat > "$TMP_DIR/xfce4-screensaver.desktop" <<'EOF'
[Desktop Entry]
Type=Application
Name=XFCE Screensaver
Hidden=true
EOF

sudo -n guestfish -a "$IMG" <<EOF
run
mount /dev/sda3 /
mkdir-p /etc/X11/Xsession.d
mkdir-p /etc/xdg/autostart
upload $TMP_DIR/90-beagle-disable-display-idle /etc/X11/Xsession.d/90-beagle-disable-display-idle
chmod 0755 /etc/X11/Xsession.d/90-beagle-disable-display-idle
upload $TMP_DIR/light-locker.desktop /etc/xdg/autostart/light-locker.desktop
upload $TMP_DIR/xfce4-power-manager.desktop /etc/xdg/autostart/xfce4-power-manager.desktop
upload $TMP_DIR/xfce4-screensaver.desktop /etc/xdg/autostart/xfce4-screensaver.desktop
EOF

echo "patched $IMG"
