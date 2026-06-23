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

    assert "usbcore.autosuspend=-1 rootdelay=15 rootwait usb-storage.delay_use=5 idle=nomwait processor.max_cstate=1" in writer
    assert "copy to RAM compatibility mode" in writer
    assert "live-media-timeout=5" in writer
    assert 'live_boot_runtime_args="live-media=removable live-media-path=live live-media-timeout=5 ignore_uuid' in writer
    assert 'installer_boot_media_args="live-media=removable live-media-path=pve-thin-client/live live-media-timeout=5 ignore_uuid' in writer
    assert "rootdelay=15 rootwait usb-storage.delay_use=5" in writer
    assert "module_blacklist=sdhci,sdhci_pci,sdhci_acpi rd.driver.blacklist=sdhci,sdhci_pci,sdhci_acpi" in writer
    assert writer.count(" toram ") == 4
    assert "usbcore.autosuspend=-1 idle=nomwait processor.max_cstate=1" in local_installer
    assert "copy to RAM compatibility mode" in local_installer
    assert 'compatibility_live_args="live-media-timeout=30 ignore_uuid toram' in local_installer
    assert "usbcore.autosuspend=-1 rootdelay=15 rootwait usb-storage.delay_use=5 idle=nomwait processor.max_cstate=1" in windows_installer
    assert "copy to RAM compatibility mode" in windows_installer
    assert '$runtimeBootMediaArgs = "live-media=removable live-media-path=live live-media-timeout=5 ignore_uuid' in windows_installer
    assert '$installerBootMediaArgs = "live-media=removable live-media-path=pve-thin-client/live live-media-timeout=5 ignore_uuid' in windows_installer
    assert "rootdelay=15 rootwait usb-storage.delay_use=5" in windows_installer
    assert "module_blacklist=sdhci,sdhci_pci,sdhci_acpi rd.driver.blacklist=sdhci,sdhci_pci,sdhci_acpi" in windows_installer
    assert windows_installer.count(" toram ") == 4
    assert "live-media-timeout=10 ignore_uuid ip=dhcp usbcore.autosuspend=-1 rootdelay=15 rootwait usb-storage.delay_use=5" in BUILD_SCRIPT.read_text(encoding="utf-8")
    assert "Beagle OS Installer (copy to RAM compatibility mode)" in BUILD_SCRIPT.read_text(encoding="utf-8")


def test_default_usb_and_installed_boot_entries_show_real_boot_progress() -> None:
    writer = WRITE_STAGE.read_text(encoding="utf-8")
    local_installer = LOCAL_INSTALLER.read_text(encoding="utf-8")
    windows_installer = WINDOWS_USB_INSTALLER.read_text(encoding="utf-8")
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")

    visible_args = "loglevel=5 systemd.show_status=1 systemd.gpt_auto=0 vt.global_cursor_default=1 consoleblank=0"
    assert visible_args in writer
    assert visible_args in local_installer
    assert visible_args in windows_installer
    assert visible_args in build_script

    live_entry = writer.split("menuentry 'Beagle OS Live' {", 1)[1].split("initrd /live/initrd.img", 1)[0]
    installed_desktop_entry = local_installer.split("menuentry 'Beagle OS Desktop' {", 1)[1].split("initrd /live/current/initrd.img", 1)[0]
    installed_gaming_entry = local_installer.split("menuentry 'Beagle OS Gaming' {", 1)[1].split("initrd /live/current/initrd.img", 1)[0]
    windows_live_entry = windows_installer.split("menuentry 'Beagle OS Live' {", 1)[1].split("initrd /live/initrd.img", 1)[0]
    installer_entry = build_script.split("menuentry 'Beagle OS Installer' {", 1)[1].split("initrd /live/initrd.img", 1)[0]

    for boot_entry in [live_entry, installed_desktop_entry, installed_gaming_entry, windows_live_entry, installer_entry]:
        assert "quiet" not in boot_entry
        assert "splash" not in boot_entry
        assert "systemd.show_status=0" not in boot_entry
        assert "vt.global_cursor_default=0" not in boot_entry
        assert "plymouth.ignore-serial-consoles" not in boot_entry

    assert "${live_boot_visible_args}" in live_entry
    assert "$visible_boot_args" in installed_desktop_entry
    assert "$visible_boot_args" in installed_gaming_entry
    assert "$runtimeVisibleArgs" in windows_live_entry
    assert "$beagle_visible_args" in installer_entry

    assert "set gfxpayload=text" in writer
    assert "set gfxpayload=text" in local_installer
    assert "set gfxpayload=text" in windows_installer
    assert "set gfxpayload=text" in build_script


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


def test_usb_writer_uses_legacy_bios_visible_mbr_layout() -> None:
    writer = WRITE_STAGE.read_text(encoding="utf-8")

    assert 'parted -s "$TARGET_DEVICE" mklabel msdos' in writer
    assert 'parted -s "$TARGET_DEVICE" mkpart primary fat32 4MiB 100%' in writer
    assert 'parted -s "$TARGET_DEVICE" set 1 boot on' in writer
    assert 'parted -s "$TARGET_DEVICE" set 1 lba on' in writer
    assert 'usb_partition="$(partition_suffix "$TARGET_DEVICE" 1)"' in writer
    assert 'grub-install --target=i386-pc --boot-directory="$mount_dir/boot" "$TARGET_DEVICE"' in writer
    assert 'grub-install \\\n    --target=x86_64-efi' in writer
    assert 'mklabel gpt' not in writer.split('write_usb() {', 1)[1].split('mkfs.vfat', 1)[0]
    assert 'bios_grub on' not in writer


def test_windows_usb_writer_uses_legacy_bios_visible_mbr_layout() -> None:
    windows_installer = WINDOWS_USB_INSTALLER.read_text(encoding="utf-8")

    assert '"convert mbr"' in windows_installer
    assert '"active"' in windows_installer
    assert '"convert gpt"' not in windows_installer
    assert "insmod biosdisk" in windows_installer
    assert "insmod part_msdos" in windows_installer
    assert 'boot_mode = "legacy-bios-and-uefi-mbr"' in windows_installer
    assert "aktives MBR/FAT32-Live-Medium fuer alte BIOS/CSM-Firmware und UEFI" in windows_installer


def test_manual_installer_iso_boot_menu_includes_legacy_usb_guards() -> None:
    build_script = BUILD_SCRIPT.read_text(encoding="utf-8")

    assert "insmod biosdisk" in build_script
    assert "insmod part_msdos" in build_script
    assert "insmod iso9660" in build_script
    assert "set beagle_usb_args='live-media=removable live-media-timeout=10 ignore_uuid ip=dhcp usbcore.autosuspend=-1 rootdelay=15 rootwait usb-storage.delay_use=5 idle=nomwait processor.max_cstate=1'" in build_script
    assert "set beagle_safe_args=" in build_script
    assert "set beagle_legacy_args=" in build_script
    assert "Beagle OS Installer (copy to RAM compatibility mode)" in build_script


def test_local_installer_keeps_manager_token_from_preset() -> None:
    local_installer = LOCAL_INSTALLER.read_text(encoding="utf-8")

    assert 'BEAGLE_MANAGER_TOKEN="${PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_TOKEN:-}"' in local_installer


def test_local_installer_uses_mbr_layout_for_old_laptop_bioses() -> None:
    local_installer = LOCAL_INSTALLER.read_text(encoding="utf-8")

    assert 'run_logged parted -s "$target_disk" mklabel msdos' in local_installer
    assert 'run_logged parted -s "$target_disk" mkpart primary fat32 4MiB 516MiB' in local_installer
    assert 'run_logged parted -s "$target_disk" set 1 boot on' in local_installer
    assert 'run_logged parted -s "$target_disk" set 1 lba on' in local_installer
    assert 'run_logged parted -s "$target_disk" mkpart primary ext4 516MiB 100%' in local_installer
    assert 'boot_part="$(partition_suffix "$target_disk" 1)"' in local_installer
    assert 'root_part="$(partition_suffix "$target_disk" 2)"' in local_installer
    assert "BIOSBOOT" not in local_installer
    assert "bios_grub on" not in local_installer


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
    assert '"$systemctl_bin" reset-failed pve-thin-client-runtime.service' in script
    assert '"$systemctl_bin" enable pve-thin-client-runtime.service' in script
    assert '"$systemctl_bin" start --no-block pve-thin-client-runtime.service' in script
    assert '"$systemctl_bin" unmask getty@tty1.service' in script
    assert '"$systemctl_bin" enable getty@tty1.service' in script
    runtime_case = script.split('runtime)', 1)[1].split(';;', 1)[0]
    assert '"$systemctl_bin" stop pve-thin-client-runtime.service' not in runtime_case
    assert '"$systemctl_bin" disable pve-thin-client-runtime.service' not in runtime_case
    assert '"$systemctl_bin" restart --no-block getty@tty1.service' not in runtime_case


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
