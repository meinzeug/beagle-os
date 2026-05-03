from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_MENU = ROOT / "thin-client-assistant" / "runtime" / "runtime-network-menu.sh"
RUNTIME_CONFIG = ROOT / "thin-client-assistant" / "runtime" / "runtime_network_config_files.sh"
RUNTIME_PERSISTENCE = ROOT / "thin-client-assistant" / "runtime" / "runtime_config_persistence.sh"
APPLY_NETWORK = ROOT / "thin-client-assistant" / "runtime" / "apply-network-config.sh"
LIVE_MENU = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-live-menu.sh"
WRITE_STAGE = ROOT / "thin-client-assistant" / "usb" / "usb_writer_write_stage.sh"
NETWORK_MENU_UNIT = ROOT / "thin-client-assistant" / "systemd" / "pve-thin-client-network-menu.service"
PREPARE_UNIT = ROOT / "thin-client-assistant" / "systemd" / "pve-thin-client-prepare.service"
BUILD_SCRIPT = ROOT / "scripts" / "build-thin-client-installer.sh"


def test_live_usb_runtime_network_menu_is_gated_to_live_usb_boots() -> None:
    unit = NETWORK_MENU_UNIT.read_text(encoding="utf-8")
    writer = WRITE_STAGE.read_text(encoding="utf-8")

    assert "ConditionKernelCommandLine=pve_thin_client.mode=runtime" in unit
    assert "ConditionKernelCommandLine=pve_thin_client.network_tui=1" in unit
    assert "Before=beagle-thin-client-prepare.service pve-thin-client-runtime.service" in unit
    assert "pve_thin_client.mode=installer pve_thin_client.installer_ui=text" in writer
    assert writer.count("pve_thin_client.mode=runtime pve_thin_client.network_tui=1") == 3
    assert writer.count("pve_thin_client.debug=1") == 3
    assert writer.count("pve_thin_client.mode=installer pve_thin_client.network_tui=1") == 0


def test_live_usb_network_choice_is_persistent_and_can_be_overridden() -> None:
    script = RUNTIME_MENU.read_text(encoding="utf-8")

    assert "BANNER_TIMEOUT_SECONDS" in script
    assert 'read -r -s -n 1 -t "$BANNER_TIMEOUT_SECONDS"' in script
    assert "PVE_THIN_CLIENT_NETWORK_CHOICE_CONFIRMED=1" in script
    assert "persist_runtime_config_to_live_state" in script
    assert "NETWORK_MODE=dhcp" in script
    assert "INTERFACE=%s" in script
    assert "DHCP IPv4:" in script
    assert 'configured_ipv4="$(current_ipv4_address "$configured_iface"' in script


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

    assert "write_networkmanager_no_random_mac_config()" in config
    assert "wifi.scan-rand-mac-address=no" in config
    assert "wifi.cloned-mac-address=permanent" in config
    assert "ethernet.cloned-mac-address=permanent" in config
    assert "cloned-mac-address=permanent" in config
    assert "write_networkmanager_no_random_mac_config || true" in apply_script
    assert 'dhcp_ipv4="$(wait_for_ipv4_address "$iface"' in apply_script
    assert 'refresh_networkd_link "$iface"' in apply_script
    assert 'wait_for_default_route "$iface" || return 1' in apply_script
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
