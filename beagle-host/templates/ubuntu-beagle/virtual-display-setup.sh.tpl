#!/bin/bash
# Virtual Display Setup for Beagle Desktop VMs
# Sets up vkms (Virtual Kernel Mode Setting) as a virtual display driver
# Enables Beagle Stream Server/Apollo streaming without physical monitors
# 
# Ref: docs/gofuture/11-streaming-v2.md, D-031

set -e

GUEST_USER="${GUEST_USER:-beagle}"
GUEST_XFCE_CONFIG_DIR="${GUEST_XFCE_CONFIG_DIR:-/home/${GUEST_USER}/.config/xfce4/xfconf/xfce-perchannel-xml}"

# Logging
log() {
  echo "[VirtualDisplay] $(date '+%Y-%m-%d %H:%M:%S') $*"
}

log "Starting Virtual Display setup (vkms DRM module)..."

# 1. Verify kernel module availability
if ! modinfo vkms >/dev/null 2>&1; then
  log "ERROR: vkms module not available in kernel. Fallback required."
  exit 1
fi

# 2. Load vkms kernel module
if ! lsmod | grep -q vkms; then
  log "Loading vkms kernel module..."
  modprobe vkms
  sleep 1
fi

if lsmod | grep -q vkms; then
  log "✓ vkms module loaded successfully"
else
  log "ERROR: Failed to load vkms module"
  exit 1
fi

# 3. Create DRM device symlink if needed
if [[ ! -e /dev/dri/card0 ]]; then
  log "Waiting for DRM devices to appear..."
  sleep 2
fi

if ! ls /dev/dri/card* >/dev/null 2>&1; then
  log "ERROR: No DRM card devices found after vkms load"
  exit 1
fi

log "✓ DRM devices available: $(ls /dev/dri/card* 2>/dev/null | tr '\n' ' ')"

# 4. Configure xrandr outputs for vkms (runs as desktop user during firstboot)
# This will be executed later during XFCE startup via auto-profile
# For now, just ensure permissions
if [[ -e /dev/dri/card0 ]]; then
  chmod 666 /dev/dri/card0
  log "✓ DRM device permissions updated"
fi

# 5. Create a systemd service to ensure vkms persists across reboots
cat > /etc/systemd/system/vkms-virtual-display.service <<'EOF'
[Unit]
Description=Virtual Display (vkms) Driver
Before=display-manager.service
After=multi-user.target

[Service]
Type=oneshot
ExecStart=/bin/bash -c 'if ! lsmod | grep -q vkms; then modprobe vkms; fi'
RemainAfterExit=yes
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable vkms-virtual-display.service
log "✓ vkms systemd service enabled (auto-load on boot)"

# 6. Add xrandr auto-configuration via XFCE profile
# This runs after Xorg/XFCE starts and configures 4K resolution on vkms output
if [[ ! -d "$GUEST_XFCE_CONFIG_DIR" ]]; then
  mkdir -p "$GUEST_XFCE_CONFIG_DIR"
  chown "$GUEST_USER:$GUEST_USER" "$GUEST_XFCE_CONFIG_DIR"
fi

# Create a profile that runs xrandr-setup script at XFCE startup
cat > /etc/xdg/autostart/vkms-xrandr-setup.desktop <<'EOF'
[Desktop Entry]
Type=Application
Name=vkms Virtual Display xrandr Setup
Exec=/usr/local/bin/vkms-xrandr-setup.sh
OnlyShowIn=XFCE
NoDisplay=false
AutoRestart=false
X-XFCE-Autostart-Override=true
EOF

# 7. Create xrandr setup script (runs during XFCE session)
cat > /usr/local/bin/vkms-xrandr-setup.sh <<'XRANDR_SCRIPT'
#!/bin/bash
# Auto-configure xrandr for vkms virtual display
# Runs during XFCE session startup

{
  sleep 3  # Wait for X11 to fully initialize
  
  # Detect vkms output (usually named "Virtual-1", "Virtual-2", etc.)
  VKMS_OUTPUT=$(xrandr | grep -i virtual | awk '{print $1}' | head -1)
  
  if [[ -z "$VKMS_OUTPUT" ]]; then
    echo "[vkms-setup] No virtual output detected by xrandr"
    exit 0
  fi
  
  echo "[vkms-setup] Configuring $VKMS_OUTPUT to 3840x2160@60Hz"
  
  # Add 4K mode if not present
  xrandr --newmode "3840x2160_60.00" 712.75 3840 4160 4576 5312 2160 2163 2168 2237 -hsync +vsync 2>/dev/null || true
  xrandr --addmode "$VKMS_OUTPUT" "3840x2160_60.00" 2>/dev/null || true
  
  # Try 4K first, then fall back to a stable full-hd mode on constrained virtual pipelines.
  if xrandr --output "$VKMS_OUTPUT" --primary --mode 3840x2160_60.00 --pos 0x0 2>/dev/null; then
    echo "[vkms-setup] Virtual display configured: $VKMS_OUTPUT at 3840x2160@60Hz"
    exit 0
  fi

  echo "[vkms-setup] 4K mode apply failed, falling back to 1920x1080"
  if xrandr --output "$VKMS_OUTPUT" --primary --mode 1920x1080 --pos 0x0 2>/dev/null; then
    echo "[vkms-setup] Virtual display configured: $VKMS_OUTPUT at 1920x1080"
    exit 0
  fi

  echo "[vkms-setup] Fallback apply failed, keeping existing mode"
} >> /tmp/vkms-setup.log 2>&1
XRANDR_SCRIPT

chmod +x /usr/local/bin/vkms-xrandr-setup.sh
log "✓ xrandr auto-setup script installed"

# 8. Test and report
log "Virtual Display setup complete!"
log "Summary:"
log "  - vkms kernel module: loaded"
log "  - DRM devices: $(ls /dev/dri/card* 2>/dev/null | wc -l) available"
log "  - Auto-startup: enabled via systemd"
log "  - xrandr auto-config: ready (runs after XFCE starts)"
log ""
log "After VM boots, xrandr will detect vkms Virtual-X output"
log "and configure it to 3840x2160@60Hz automatically."
log "Beagle Stream Server will then see the virtual display and stream correctly."
log ""
log "Expected Beagle Stream Client behavior:"
log "  - Client connects to Beagle Stream Server"
log "  - Beagle Stream Server detects Virtual-X@3840x2160 and streams at that resolution"
log "  - No physical monitor required on host"
