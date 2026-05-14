from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MENU = ROOT / "thin-client-assistant" / "runtime" / "runtime-network-menu.sh"
RUNTIME_CONFIG = ROOT / "thin-client-assistant" / "runtime" / "runtime_network_config_files.sh"
RUNTIME_BACKEND = ROOT / "thin-client-assistant" / "runtime" / "runtime_network_backend.sh"
RUNTIME_PERSISTENCE = ROOT / "thin-client-assistant" / "runtime" / "runtime_config_persistence.sh"
APPLY_NETWORK = ROOT / "thin-client-assistant" / "runtime" / "apply-network-config.sh"
LIVE_MENU = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-live-menu.sh"
WRITE_STAGE = ROOT / "thin-client-assistant" / "usb" / "usb_writer_write_stage.sh"
LOCAL_INSTALLER = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-local-installer.sh"
WINDOWS_USB_INSTALLER = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-usb-installer.ps1"
NETWORK_MENU_UNIT = ROOT / "thin-client-assistant" / "systemd" / "pve-thin-client-network-menu.service"
PREPARE_UNIT = ROOT / "thin-client-assistant" / "systemd" / "pve-thin-client-prepare.service"
BUILD_SCRIPT = ROOT / "scripts" / "build-thin-client-installer.sh"
LIVE_PACKAGES = ROOT / "thin-client-assistant" / "live-build" / "config" / "package-lists" / "pve-thin-client.list.chroot"
RUNTIME_SYSTEMD_BOOTSTRAP = ROOT / "thin-client-assistant" / "runtime" / "runtime_systemd_bootstrap.sh"
SSH_HOSTKEY_PREPARE = ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "sbin" / "beagle-ssh-hostkeys-prepare"


def test_live_usb_runtime_network_menu_is_gated_to_live_usb_boots() -> None:
    unit = NETWORK_MENU_UNIT.read_text(encoding="utf-8")
    writer = WRITE_STAGE.read_text(encoding="utf-8")

    assert "ConditionKernelCommandLine=pve_thin_client.mode=runtime" in unit
    assert "ConditionKernelCommandLine=pve_thin_client.network_tui=1" in unit
    assert "Before=beagle-thin-client-prepare.service pve-thin-client-runtime.service" in unit
    assert "pve_thin_client.mode=installer pve_thin_client.installer_ui=text" in writer
    assert writer.count("pve_thin_client.mode=runtime pve_thin_client.network_tui=1") == 4
    assert writer.count("pve_thin_client.debug=1") == 4
    assert writer.count("pve_thin_client.mode=installer pve_thin_client.network_tui=1") == 0


def test_live_usb_boot_entries_include_ryzen_usb_compatibility_guards() -> None:
    writer = WRITE_STAGE.read_text(encoding="utf-8")
    local_installer = LOCAL_INSTALLER.read_text(encoding="utf-8")
    windows_installer = WINDOWS_USB_INSTALLER.read_text(encoding="utf-8")

    assert "usbcore.autosuspend=-1" in writer
    assert "idle=nomwait" in writer
    assert "processor.max_cstate=1" in writer
    assert "copy to RAM compatibility mode" in writer
    assert "live-media-timeout=180" in writer
    assert 'local live_boot_runtime_args="live-media-path=/live live-media-timeout=180 ignore_uuid ${runtime_ip_args}' in writer
    assert "${live_boot_runtime_args} ${live_boot_safe_args} toram" in writer
    assert "usbcore.autosuspend=-1 idle=nomwait processor.max_cstate=1" in local_installer
    assert "copy to RAM compatibility mode" in local_installer
    assert 'compatibility_live_args="live-media-timeout=30 ignore_uuid toram' in local_installer
    assert "usbcore.autosuspend=-1 idle=nomwait processor.max_cstate=1" in windows_installer
    assert "copy to RAM compatibility mode" in windows_installer
    assert '$runtimeBootMediaArgs = "live-media-path=/live live-media-timeout=30 ignore_uuid toram' in windows_installer


def test_live_usb_network_choice_is_persistent_and_can_be_overridden() -> None:
    script = RUNTIME_MENU.read_text(encoding="utf-8")

    assert "BANNER_TIMEOUT_SECONDS" in script
    assert "dialog_notice()" in script
    assert 'read -r -s -n 1 -t "$BANNER_TIMEOUT_SECONDS"' in script
    assert "PVE_THIN_CLIENT_NETWORK_CHOICE_CONFIRMED=1" in script
    assert "persist_runtime_config_to_live_state" in script
    assert "NETWORK_MODE=dhcp" in script
    assert "INTERFACE=%s" in script
    assert "DHCP IPv4:" in script
    assert 'configured_ipv4="$(current_ipv4_address "$configured_iface"' in script


def test_live_usb_network_menu_auto_selects_single_wired_interface() -> None:
    script = RUNTIME_MENU.read_text(encoding="utf-8")

    assert "maybe_auto_configure_network_choice()" in script
    assert "NETWORK_INTERFACE_WAIT_RETRIES" in script
    assert "NETWORK_INTERFACE_WAIT_SECONDS" in script
    assert 'sleep "$timeout_seconds"' in script
    assert 'sleep "$NETWORK_INTERFACE_WAIT_SECONDS"' in script
    assert "${#wired_ifaces[@]} == 1 && ${#wifi_ifaces[@]} == 0" in script
    assert 'write_network_choice "ethernet" "${wired_ifaces[0]}"' in script
    assert 'Netzwerk wurde automatisch konfiguriert.' in script


def test_live_usb_network_menu_supports_wifi_before_runtime_networking() -> None:
    config = RUNTIME_CONFIG.read_text(encoding="utf-8")
    apply_script = APPLY_NETWORK.read_text(encoding="utf-8")

    assert "write_wifi_wpa_supplicant_config()" in config
    assert "start_wifi_wpa_supplicant()" in config
    assert 'wpa_passphrase "$ssid" "$psk"' in config
    assert "type=wifi" in config
    assert 'write_wifi_wpa_supplicant_config' in apply_script
    assert 'start_wifi_wpa_supplicant "$iface"' in apply_script


def test_live_usb_network_runtime_disables_mac_randomization_and_writes_debug_report() -> None:
    config = RUNTIME_CONFIG.read_text(encoding="utf-8")
    apply_script = APPLY_NETWORK.read_text(encoding="utf-8")
    writer = WRITE_STAGE.read_text(encoding="utf-8")
    backend = RUNTIME_BACKEND.read_text(encoding="utf-8")
    packages = LIVE_PACKAGES.read_text(encoding="utf-8")

    assert "write_networkmanager_no_random_mac_config()" in config
    assert "wifi.scan-rand-mac-address=no" in config
    assert "wifi.cloned-mac-address=permanent" in config
    assert "ethernet.cloned-mac-address=permanent" in config
    assert "cloned-mac-address=permanent" in config
    assert "write_networkmanager_no_random_mac_config || true" in apply_script
    assert 'dhcp_ipv4="$(wait_for_ipv4_address "$iface"' in apply_script
    assert 'refresh_networkd_link "$iface"' in apply_script
    assert 'acquire_dhcp_ipv4_fallback "$iface"' in apply_script
    assert 'write_runtime_debug_report "network-ipv4-failed" "$iface"' in apply_script
    assert 'wait_for_default_route "$iface" || {' in apply_script
    assert "acquire_dhcp_ipv4_fallback()" in backend
    assert '"$dhclient_bin" -4 -1 -v "$iface"' in backend
    assert "isc-dhcp-client" in packages
    assert "xserver-xorg-legacy" in packages
    assert 'write_runtime_debug_report "network-applied" "$iface"' in apply_script
    assert "$live_state_dir/debug/README.txt" in writer


def test_live_usb_write_stage_passes_stream_fallback_values_into_runtime_state() -> None:
    writer = WRITE_STAGE.read_text(encoding="utf-8")

    assert 'BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST:-}"' in writer
    assert 'BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL="${PVE_THIN_CLIENT_PRESET_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL:-}"' in writer


def test_network_menu_is_included_before_runtime_services() -> None:
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")
    prepare_unit = PREPARE_UNIT.read_text(encoding="utf-8")

    assert "pve-thin-client-network-menu.service" in build_script
    assert "pve-thin-client-network-menu.service" in prepare_unit


def test_preset_installer_prompts_for_network_before_disk_selection() -> None:
    script = LIVE_MENU.read_text(encoding="utf-8")

    preset_start = script.index("install_from_bundled_preset()")
    network_prompt = script.index("configure_network_access || {", preset_start)
    disk_resolution = script.index('target_disk="$(resolve_auto_target_disk || true)"', preset_start)
    assert network_prompt < disk_resolution


def test_persisted_wifi_psk_keeps_network_env_private() -> None:
    script = RUNTIME_PERSISTENCE.read_text(encoding="utf-8")

    assert "PVE_THIN_CLIENT_WIFI_PSK" in script
    assert "chmod 0600" in script


def test_runtime_getty_override_uses_systemd_safe_user_escape() -> None:
    script = RUNTIME_SYSTEMD_BOOTSTRAP.read_text(encoding="utf-8")

    assert 'rm -f "$default_dir/zz-beagle-default.conf"' in script
    assert 'ExecStart=-/usr/local/bin/pve-thin-client-tty-login %I $TERM' in script
    assert '"$systemctl_bin" stop pve-thin-client-runtime.service' in script
    assert '"$systemctl_bin" reset-failed pve-thin-client-runtime.service' in script
    assert '"$systemctl_bin" disable pve-thin-client-runtime.service' in script
    assert '"$systemctl_bin" unmask getty@tty1.service' in script
    assert '"$systemctl_bin" enable getty@tty1.service' in script
    assert '"$systemctl_bin" restart --no-block getty@tty1.service' in script
    assert '"$systemctl_bin" start --no-block getty@tty1.service' in script


def test_live_ssh_hostkey_prepare_degrades_when_state_dir_is_read_only() -> None:
    script = SSH_HOSTKEY_PREPARE.read_text(encoding="utf-8")

    assert 'if ! install -d -m 0700 "$KEY_DIR" >/dev/null 2>&1; then' in script
    assert 'KEY_DIR=""' in script


def test_start_x11_prefers_xorg_wrapper_when_available() -> None:
    script = RUNTIME_MENU.parent.parent / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "bin" / "pve-thin-client-start-x11"
    start_x11 = script.read_text(encoding="utf-8")

    assert "resolve_x_server_command()" in start_x11
    assert "/usr/lib/xorg/Xorg.wrap" in start_x11
    assert 'x_server_cmd="$(resolve_x_server_command)"' in start_x11
    assert 'trace_event "x11.start" "launcher=pve-thin-client-start-x11 attempt=${1:-1} x_server=${x_server_cmd}"' in start_x11
