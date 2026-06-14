from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "scripts" / "configure-beagle-stream-server-guest.sh"


def test_configure_beagle_stream_server_guest_disables_display_idle_and_lockers() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "/etc/X11/xorg.conf.d/20-beagle-software-cursor.conf" in content
    assert 'Identifier "Beagle Virtio GPU Software Cursor"' in content
    assert 'Driver "modesetting"' in content
    assert 'Option "SWCursor" "true"' in content
    assert "/etc/X11/Xsession.d/19-beagle-lightdm-session-compat" in content
    assert 'if ! type has_option >/dev/null 2>&1; then' in content
    assert ': "${OPTIONFILE:=/etc/X11/Xsession.options}"' in content or ': "\\${OPTIONFILE:=/etc/X11/Xsession.options}"' in content
    assert "/etc/X11/Xsession.d/90-beagle-disable-display-idle" in content
    assert 'xset -dpms >/dev/null 2>&1 || true' in content
    assert 'xset s off >/dev/null 2>&1 || true' in content
    assert 'xset s noblank >/dev/null 2>&1 || true' in content
    assert '/home/\\$GUEST_USER/.local' in content
    assert '/home/\\$GUEST_USER/.local/state' in content
    assert '/home/\\$GUEST_USER/.local/state/wireplumber' in content
    assert 'chown -R "\\$GUEST_USER:\\$GUEST_USER" "/home/\\$GUEST_USER/.config" "/home/\\$GUEST_USER/.local"' in content
    assert (
        '/home/$GUEST_USER/.config/autostart/light-locker.desktop' in content
        or '/home/\\$GUEST_USER/.config/autostart/light-locker.desktop' in content
    )
    assert (
        '/home/$GUEST_USER/.config/autostart/xfce4-power-manager.desktop' in content
        or '/home/\\$GUEST_USER/.config/autostart/xfce4-power-manager.desktop' in content
    )
    assert (
        '/home/$GUEST_USER/.config/autostart/xfce4-screensaver.desktop' in content
        or '/home/\\$GUEST_USER/.config/autostart/xfce4-screensaver.desktop' in content
    )


def test_configure_beagle_stream_server_guest_prefers_beaglestream_server_package() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'STREAM_RUNTIME_STATUS_FILE="/etc/beagle/stream-runtime.env"' in content
    assert 'write_stream_runtime_status() {' in content
    assert "BEAGLE_STREAM_SERVER_DEFAULT_URL" in content
    assert "beagle-stream-server-latest-ubuntu-24.04-amd64.deb" in content
    assert "BEAGLE_STREAM_SERVER_SHA256SUMS_URL" in content
    assert "Checksum entry for" in content
    assert "BeagleStream server package unavailable" not in content
    assert 'stream_runtime_variant="beagle-stream-server"' in content
    assert 'stream_runtime_variant="beagle-stream-server-fallback"' not in content
    assert 'cat > /etc/beagle/stream-runtime.env <<RUNTIMEENV' in content
    assert 'BEAGLE_STREAM_RUNTIME_VARIANT=\\${stream_runtime_variant}' in content
    assert 'BEAGLE_STREAM_RUNTIME_PACKAGE_URL=\\${stream_runtime_package_url}' in content
    assert '-o "\\$tmpdir/beagle-stream-server.deb" \\' in content
    assert '"\\$BEAGLE_STREAM_SERVER_URL"' in content
    assert "Checksum mismatch for beagle-stream-server package" in content
    assert "--beagle-manager-url" in content
    assert 'BEAGLE_MANAGER_URL="https://${PUBLIC_STREAM_HOST}/beagle-api"' in content
    assert "--beagle-manager-url or --public-stream-host is required" in content


def test_configure_beagle_stream_server_guest_bootstraps_vscode_repository() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "install_visual_studio_code_repo()" in content
    assert "https://packages.microsoft.com/repos/code stable main" in content
    assert "packages.microsoft.gpg" in content
    assert "install_visual_studio_code_repo" in content


def test_configure_beagle_stream_server_guest_detects_beagle_stream_server_exec_path_dynamically() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    # Package installs must win over stale local fallback binaries.
    # The script generates a guest script via heredoc, so $ is escaped as \$.
    assert 'if [[ "\\$stream_runtime_variant" == "beagle-stream-server" && -x /usr/bin/beagle-stream-server ]]; then' in content
    assert 'BEAGLE_STREAM_SERVER_EXEC=/usr/bin/beagle-stream-server' in content
    assert 'BEAGLE_STREAM_SERVER_EXEC="\\$(command -v beagle-stream-server 2>/dev/null || true)"' in content
    assert "beagle-stream-server binary was not installed by stream runtime package" in content
    assert "cat > /usr/local/bin/beagle-stream-server <<'BEAGLEWRAP'" not in content
    assert 'exec /usr/local/bin/sunshine "\\$@"' not in content
    assert 'ExecStart=\\$BEAGLE_STREAM_SERVER_EXEC' in content
    assert 'ExecStart=/usr/local/bin/beagle-stream-server\n' not in content


def test_configure_beagle_stream_server_guest_keeps_beagle_plasma_default() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'DESKTOP_ID="${DESKTOP_ID:-plasma-cyberpunk}"' in content
    assert 'DESKTOP_SESSION="${DESKTOP_SESSION:-}"' in content
    assert 'case "${DESKTOP_ID:-plasma-cyberpunk}" in' in content
    assert 'plasma|plasma-*|kde|kde-plasma)' in content
    assert 'DESKTOP_LABEL="${DESKTOP_LABEL:-Beagle Desktop}"' in content
    assert 'DESKTOP_SESSION="${DESKTOP_SESSION:-plasma}"' in content
    assert 'rm -f /etc/lightdm/lightdm.conf.d/60-pve-thin-client.conf' in content
    assert 'cat > /etc/lightdm/lightdm.conf.d/60-beagle.conf <<GUESTCFG' in content
    assert 'cat > /etc/lightdm/lightdm.conf.d/60-pve-thin-client.conf <<GUESTCFG' not in content


def test_configure_beagle_stream_server_guest_normalizes_usb_microphones() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'BEAGLE_USB_MICROPHONE_VOLUME="${BEAGLE_USB_MICROPHONE_VOLUME:-250%}"' in content
    assert 'cat > /usr/local/bin/beagle-normalize-usb-microphones <<\'MICNORM\'' in content
    assert 'bridge_source="\\$(pactl list short sources' in content
    assert '$2 == "beagle_tc_microphone"' in content
    assert 'pactl set-default-source "\\$bridge_source"' in content
    assert "^alsa_input\\.usb-" in content
    assert 'pactl set-default-source "\\$source_name"' in content
    assert 'pactl set-source-mute "\\$source_name" 0' in content
    assert 'pactl set-source-volume "\\$source_name" "\\$volume"' in content
    assert 'beagle-usb-microphone-normalize.service' in content
    assert 'beagle-usb-microphone-normalize.timer' in content
    assert 'OnUnitActiveSec=30s' in content
    assert 'install_usb_microphone_normalizer' in content


def test_configure_beagle_stream_server_guest_installs_thinclient_microphone_bridge() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'beagle-tc-mic-bridge' in content
    assert 'BEAGLE_TC_MIC_BRIDGE_SCRIPT_B64' in content
    assert 'BEAGLE_TC_MIC_BRIDGE_SERVICE_B64' in content
    assert 'BEAGLE_TC_MIC_BRIDGE_PORT="\\${BEAGLE_TC_MIC_BRIDGE_PORT:-\\$((43000 + VMID + 100))}"' in content
    assert '/usr/local/bin/beagle-tc-mic-bridge' in content
    assert '/etc/systemd/system/beagle-tc-mic-bridge.service' in content
    assert 'Environment=XDG_RUNTIME_DIR=/run/user/\\$GUEST_UID' in content
    assert 'Environment=BEAGLE_TC_MIC_BRIDGE_PORT=\\$BEAGLE_TC_MIC_BRIDGE_PORT' in content
    assert 'systemctl enable --now beagle-tc-mic-bridge.service' in content
    service_template = (ROOT_DIR / "scripts" / "lib" / "beagle-tc-mic-bridge.service").read_text(encoding="utf-8")
    assert 'Environment=XDG_RUNTIME_DIR=/run/user/%U' in service_template
    assert 'ExecStartPre=/usr/bin/systemctl --user start pipewire.service pipewire-pulse.service wireplumber.service' in service_template
    assert 'WantedBy=graphical.target' in service_template
    assert 'WantedBy=multi-user.target' not in service_template


def test_virtual_display_units_do_not_order_after_multi_user() -> None:
    firstboot = (ROOT_DIR / "beagle-host" / "templates" / "ubuntu-beagle" / "firstboot-provision.sh.tpl").read_text(encoding="utf-8")
    setup = (ROOT_DIR / "beagle-host" / "templates" / "ubuntu-beagle" / "virtual-display-setup.sh.tpl").read_text(encoding="utf-8")

    for content in (firstboot, setup):
        unit_start = content.index("vkms-virtual-display.service")
        unit_block = content[unit_start:content.index("[Service]", unit_start)]
        assert "Before=display-manager.service" in unit_block
        assert "After=multi-user.target" not in unit_block


def test_configure_beagle_stream_server_guest_freezes_stable_stream_server_baseline() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert "encoder = software" in content
    assert "sw_preset = ultrafast" in content
    assert "sw_tune = zerolatency" in content
    assert "capture = kms" in content
    assert "hevc_mode = 0" in content
    assert "av1_mode = 0" in content
    assert "minimum_fps_target = 60" in content
    assert "max_bitrate = 35000" in content
    # sunshine.conf 'port' == HTTP port; Moonlight/beagle-stream connects here directly
    assert "BEAGLE_STREAM_SERVER_PORT:-50000}" in content
    assert "BEAGLE_STREAM_SERVER_PORT=\"${BEAGLE_STREAM_SERVER_PORT:-50000}\"" in content
    assert "BEAGLE_STREAM_SERVER_ALLOWED_CIDRS=\"${BEAGLE_STREAM_SERVER_ALLOWED_CIDRS:-10.88.0.0/16}\"" in content
    assert "beagle-stream-client-video-decoder: auto" in content
    assert "pgrep -x sunshine" in content
    assert "beagle_stream_server_is_running()" in content
    assert "kill -0 \"\\$main_pid\"" in content
    assert "pgrep -x beagle-stream-server" not in content


def test_configure_beagle_stream_server_guest_installs_uptime_guardian() -> None:
    content = SCRIPT.read_text(encoding="utf-8")

    assert 'BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_INTERVAL_SEC:-15}"' in content
    assert 'BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_BOOT_DELAY_SEC:-20}"' in content
    assert 'BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC="${BEAGLE_STREAM_SERVER_GUARD_INTERVAL_SEC:-10}"' in content
    assert 'BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD="${BEAGLE_STREAM_SERVER_GUARD_REBOOT_THRESHOLD:-18}"' in content
    assert "OnFailure=beagle-stream-server-healthcheck.service" in content
    # OnFailure must be in [Unit], not [Service] — systemd ignores it in [Service]
    unit_section_pos = content.index("[Unit]", content.index("beagle-stream-server.service"))
    service_section_pos = content.index("[Service]", unit_section_pos)
    on_failure_pos = content.index("OnFailure=beagle-stream-server-healthcheck.service", unit_section_pos)
    assert on_failure_pos < service_section_pos, "OnFailure must appear in [Unit], before [Service]"
    assert "cat > /usr/local/bin/beagle-stream-server-guardian <<'GUARDIAN'" in content
    assert 'service_is_transitioning() {' in content
    assert 'BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC="\\${BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC:-45}"' in content
    assert 'BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD="\\${BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD:-4}"' in content
    assert 'record_readiness_failure() {' in content
    assert 'service_is_warming_up() {' in content
    assert 'activating|reloading|deactivating) return 0 ;;' in content
    assert '"http://127.0.0.1:\\${BEAGLE_STREAM_SERVER_PORT}/serverinfo"' in content
    assert 'if is_stream_ready || is_api_ready; then' in content
    assert 'if beagle_stream_server_is_running; then' in content
    assert content.index('if beagle_stream_server_is_running; then', content.index('if has_rtsp_port_conflict; then')) < content.index('if record_readiness_failure; then')
    assert 'if record_readiness_failure; then' in content
    assert 'ensure_timer()' not in content
    assert 'BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD="\\${BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD:-4}"' in content
    assert 'elif [[ "\\$(service_state)" == "active" ]] && main_pid="\\$(systemctl show -p MainPID --value beagle-stream-server.service 2>/dev/null || echo 0)"' in content
    assert 'elif service_is_transitioning || service_is_warming_up; then' in content
    assert "stream offline for \\${consecutive_failures} checks; rebooting guest" in content
    assert "cat > /etc/systemd/system/beagle-stream-server-guardian.service <<'GUARDSVC'" in content
    assert "ExecStart=/usr/local/bin/beagle-stream-server-guardian" in content
    assert "systemctl enable --now beagle-stream-server-guardian.service" in content


def test_firstboot_stream_server_healthcheck_avoids_startup_restart_loop() -> None:
    content = (ROOT_DIR / "beagle-host" / "templates" / "ubuntu-beagle" / "firstboot-provision.sh.tpl").read_text(encoding="utf-8")

    assert 'service_is_transitioning() {' in content
    assert 'BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC="${BEAGLE_STREAM_SERVER_HEALTHCHECK_GRACE_SEC:-45}"' in content
    assert 'BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD="${BEAGLE_STREAM_SERVER_HEALTHCHECK_FAILURE_THRESHOLD:-4}"' in content
    assert 'record_readiness_failure() {' in content
    assert 'service_is_warming_up() {' in content
    assert 'activating|reloading|deactivating) return 0 ;;' in content
    assert '"http://127.0.0.1:${BEAGLE_STREAM_SERVER_PORT}/serverinfo"' in content
    assert 'if is_stream_ready || is_api_ready; then' in content
    assert 'if beagle_stream_server_is_running; then' in content
    assert content.index('if beagle_stream_server_is_running; then', content.index('if has_rtsp_port_conflict; then')) < content.index('if record_readiness_failure; then')
    assert 'if record_readiness_failure; then' in content
    assert "cat > /usr/local/bin/beagle-stream-server-guardian <<'EOF'" in content
    assert 'BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD="${BEAGLE_STREAM_SERVER_GUARD_RESTART_THRESHOLD:-4}"' in content
    assert 'elif [[ "$(service_state)" == "active" ]] && main_pid="$(systemctl show -p MainPID --value beagle-stream-server.service 2>/dev/null || echo 0)"' in content
    assert "cat > /etc/systemd/system/beagle-stream-server-guardian.service <<'EOF'" in content
    assert "systemctl enable --now beagle-stream-server-guardian.service" in content
