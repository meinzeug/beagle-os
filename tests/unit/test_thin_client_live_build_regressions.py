from __future__ import annotations

import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_LIST = ROOT / "thin-client-assistant" / "live-build" / "config" / "package-lists" / "pve-thin-client.list.chroot"
VERIFY_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "011-verify-runtime-deps.hook.chroot"
PREPARE_RUNTIME = ROOT / "thin-client-assistant" / "runtime" / "prepare-runtime.sh"
RUNTIME_DEBUG_REPORT = ROOT / "thin-client-assistant" / "runtime" / "runtime_debug_report.sh"
SYSTEMD_BOOTSTRAP = ROOT / "thin-client-assistant" / "runtime" / "runtime_systemd_bootstrap.sh"
WIREGUARD_ENROLLMENT = ROOT / "thin-client-assistant" / "runtime" / "enrollment_wireguard.sh"
WIREGUARD_RUNTIME_GUARD = ROOT / "thin-client-assistant" / "runtime" / "wireguard_runtime_guard.sh"
RUNTIME_ENDPOINT_ENROLLMENT = ROOT / "thin-client-assistant" / "runtime" / "runtime_endpoint_enrollment.sh"
BEAGLE_STREAM_CLIENT_CONNECT_HOST = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_connect_host.sh"
BEAGLE_STREAM_CLIENT_RUNTIME_EXEC = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_runtime_exec.sh"
LAUNCH_BEAGLE_STREAM_CLIENT = ROOT / "thin-client-assistant" / "runtime" / "launch-beagle-stream-client.sh"
LAUNCH_SESSION = ROOT / "thin-client-assistant" / "runtime" / "launch-session.sh"
BUILD_THIN_CLIENT = ROOT / "scripts" / "build-thin-client-installer.sh"
BUILD_BEAGLE_OS = ROOT / "scripts" / "build-beagle-os.sh"
PREPARE_HOST_DOWNLOADS = ROOT / "scripts" / "prepare-host-downloads.sh"
INSTALL_THINCLIENT = ROOT / "thin-client-assistant" / "installer" / "install.sh"
LIVE_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "008-install-beagle-stream-client.hook.chroot"
ENABLE_SERVICES_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "010-enable-services.hook.chroot"
CREATE_THINCLIENT_USER_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "005-create-thinclient-user.hook.chroot"
BEAGLE_STREAM_CLIENT_TARGETING = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_targeting.sh"
BEAGLE_STREAM_CLIENT_HOST_SYNC = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_host_sync.sh"
BEAGLE_STREAM_CLIENT_API_URL = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_api_url.sh"
RUNTIME_USER_SETUP = ROOT / "thin-client-assistant" / "runtime" / "runtime_user_setup.sh"
RUNTIME_NETWORK_BACKEND = ROOT / "thin-client-assistant" / "runtime" / "runtime_network_backend.sh"
RUNTIME_SSH_SERVICE_CONFIG = ROOT / "thin-client-assistant" / "runtime" / "runtime_ssh_service_config.sh"
COMMON_SH = ROOT / "thin-client-assistant" / "runtime" / "common.sh"
DEVICE_LOCK_SCREEN = ROOT / "thin-client-assistant" / "runtime" / "device_lock_screen.sh"
DEVICE_STATE_ENFORCEMENT = ROOT / "thin-client-assistant" / "runtime" / "device_state_enforcement.sh"
DEVICE_SYNC = ROOT / "thin-client-assistant" / "runtime" / "device_sync.sh"
USB_HOTPLUG = ROOT / "thin-client-assistant" / "runtime" / "beagle-usb-hotplug"
USB_RUNTIME_ACTIONS = ROOT / "thin-client-assistant" / "runtime" / "beagle_usb_runtime_actions.sh"
USB_RUNTIME_USBIPD = ROOT / "thin-client-assistant" / "runtime" / "beagle_usb_runtime_usbipd.sh"
AUDIO_INPUT_BRIDGE = ROOT / "thin-client-assistant" / "runtime" / "beagle_audio_input_bridge.py"
APPLY_ENROLLMENT_CONFIG = ROOT / "thin-client-assistant" / "runtime" / "apply_enrollment_config.py"
ENSURE_XDG_RUNTIME_DIR = ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "sbin" / "beagle-ensure-xdg-runtime-dir"


def test_thin_client_live_image_bundles_wireguard_runtime_dependencies() -> None:
    package_text = PACKAGE_LIST.read_text(encoding="utf-8")

    assert "jq" in package_text
    assert "libcap2-bin" in package_text
    assert "wireguard-tools" in package_text


def test_thin_client_live_image_verifies_wireguard_commands() -> None:
    hook_text = VERIFY_HOOK.read_text(encoding="utf-8")

    assert "wireguard-tools" in hook_text
    assert 'for command_name in jq wg ip; do' in hook_text
    assert 'setcap cap_net_admin+ep "$(command -v wg)"' in hook_text


def test_prepare_runtime_does_not_block_enrollment_on_getty_bootstrap_failure() -> None:
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")

    assert 'ensure_getty_overrides || beagle_log_event "prepare-runtime.getty-overrides-error"' in prepare_text
    assert 'ip route delete 0.0.0.0/1 dev "$stale_wg_iface" 2>/dev/null || true' in prepare_text
    assert prepare_text.index("ip route delete 0.0.0.0/1") < prepare_text.index('bash "$SCRIPT_DIR/apply-network-config.sh"')
    assert prepare_text.index("ensure_getty_overrides ||") < prepare_text.index("enroll_endpoint_if_needed ||")
    assert prepare_text.index("enroll_endpoint_if_needed ||") < prepare_text.index("enroll_wireguard_if_needed ||")
    assert "prepare_runtime_already_ready()" in prepare_text
    assert 'prepare_runtime_reentry=1' in prepare_text
    assert 'prepare-runtime.reentry' in prepare_text
    assert 'if [[ "$prepare_runtime_reentry" -eq 0 ]]; then' in prepare_text


def test_prepare_runtime_grants_stream_audio_priority_capability() -> None:
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")
    runtime_environment_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_runtime_environment.sh").read_text(encoding="utf-8")
    build_thin_client_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")
    build_beagle_os_text = BUILD_BEAGLE_OS.read_text(encoding="utf-8")

    assert "ensure_beagle_stream_client_audio_capabilities()" in prepare_text
    assert "/opt/beagle-stream-client/usr/bin/beagle-stream-client" in prepare_text
    assert "/opt/beagle-stream-client/usr/bin/beagle-stream" in prepare_text
    assert "setcap cap_sys_nice+ep \"$binary\"" in prepare_text
    assert "ensure_wireguard_runtime_capabilities\nensure_beagle_stream_client_audio_capabilities" in prepare_text
    assert "patchelf" in build_thin_client_text
    assert "patchelf --set-rpath" in build_thin_client_text
    assert "patchelf" in build_beagle_os_text
    assert "patchelf --set-rpath" in build_beagle_os_text
    assert "/etc/ld.so.conf.d/beagle-stream-client.conf" not in prepare_text
    assert "ldconfig" not in prepare_text
    assert "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PULSE_LATENCY_MSEC" in runtime_environment_text
    assert "PULSE_LATENCY_MSEC:-90" in runtime_environment_text
    assert "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PIPEWIRE_LATENCY" in runtime_environment_text
    assert "PIPEWIRE_LATENCY:-2048/48000" in runtime_environment_text


def test_live_audio_runtime_dir_helper_is_executable() -> None:
    mode = ENSURE_XDG_RUNTIME_DIR.stat().st_mode

    assert mode & stat.S_IXUSR
    assert "install -d -o \"$uid\" -g \"$uid\" -m 0700 \"$dir\"" in ENSURE_XDG_RUNTIME_DIR.read_text(encoding="utf-8")


def test_live_runtime_executes_tmpfs_staged_shell_scripts_with_bash() -> None:
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")
    lifecycle_text = (ROOT / "thin-client-assistant" / "runtime" / "runtime_endpoint_enrollment.sh").read_text(encoding="utf-8")
    session_launcher_text = (ROOT / "thin-client-assistant" / "runtime" / "session_launcher.sh").read_text(encoding="utf-8")
    launch_session_text = LAUNCH_SESSION.read_text(encoding="utf-8")
    launch_gfn_text = (ROOT / "thin-client-assistant" / "runtime" / "launch-geforcenow.sh").read_text(encoding="utf-8")

    assert 'bash "$SCRIPT_DIR/apply-network-config.sh"' in prepare_text
    assert 'bash "$script_path"' in lifecycle_text
    assert 'bash "$SCRIPT_DIR/launch-beagle-stream-client.sh"' in session_launcher_text
    assert 'exec bash "$SCRIPT_DIR/launch-geforcenow.sh"' in launch_session_text
    assert 'bash "$SCRIPT_DIR/install-geforcenow.sh" --ensure-only' in launch_gfn_text


def test_live_build_does_not_start_legacy_runtime_x_service_by_default() -> None:
    hook_text = ENABLE_SERVICES_HOOK.read_text(encoding="utf-8")
    build_thin_client_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")
    prepare_downloads_text = PREPARE_HOST_DOWNLOADS.read_text(encoding="utf-8")

    assert "beagle-thin-client-prepare.service" in hook_text
    assert "getty@tty1.service" in hook_text
    assert "ensure_wantedby_symlink /etc/systemd/system/beagle-thin-client-prepare.service multi-user.target" in hook_text
    assert "pve-thin-client-runtime.service multi-user.target" not in hook_text
    assert '    pve-thin-client-runtime.service \\' not in build_thin_client_text
    assert "ensure_rootfs_wants_link pve-thin-client-runtime.service multi-user.target" not in build_thin_client_text
    assert 'rm -f \\' in prepare_downloads_text
    assert 'multi-user.target.wants/pve-thin-client-runtime.service"' in prepare_downloads_text


def test_runtime_scripts_normalize_live_boot_var_local_overlay_paths() -> None:
    runtime_scripts = [
        COMMON_SH,
        DEVICE_LOCK_SCREEN,
        DEVICE_STATE_ENFORCEMENT,
        DEVICE_SYNC,
        LAUNCH_BEAGLE_STREAM_CLIENT,
    ]

    for runtime_script in runtime_scripts:
        runtime_text = runtime_script.read_text(encoding="utf-8")
        assert '== /var/local/*' in runtime_text
        assert '"/usr/local/${' in runtime_text

    common_text = COMMON_SH.read_text(encoding="utf-8")
    assert 'export RUNTIME_SCRIPT_DIR' in common_text
    assert 'runtime_resolve_source_dir()' in common_text
    assert 'runtime_first_readable_file()' in common_text
    assert 'runtime_resolve_helper_path()' in common_text
    assert 'runtime_stage_dir_to_tmpfs()' in common_text
    assert 'RUNTIME_TMPFS_DIR_DEFAULT="/run/pve-thin-client/runtime"' in common_text
    assert 'if [[ -r "$target_dir/common.sh" && -r "$target_dir/runtime_value_helpers.sh" ]]; then' in common_text
    assert 'if ! source "$RUNTIME_VALUE_HELPERS_SH"; then' in common_text
    assert 'beagle_curl_tls_args()' in common_text
    assert '$(dirname -- "${BASH_SOURCE[0]}")' not in common_text


def test_runtime_heartbeat_uses_tmpfs_runtime_copy_before_sourcing_common() -> None:
    heartbeat = (ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "sbin" / "beagle-runtime-heartbeat").read_text(encoding="utf-8")

    assert '_rt_run="/run/pve-thin-client/runtime"' in heartbeat
    assert 'cp -a "${_rt_orig}/." "$_rt_run/"' in heartbeat
    assert 'COMMON_SH="$_rt_orig/common.sh"' in heartbeat
    assert 'DEVICE_SYNC_SH="$_rt_orig/device_sync.sh"' in heartbeat


def test_prepare_runtime_persists_redacted_live_usb_debug_reports() -> None:
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")
    debug_text = RUNTIME_DEBUG_REPORT.read_text(encoding="utf-8")

    assert "runtime_debug_live_dir()" in debug_text
    assert "runtime_debug_redact_env_file()" in debug_text
    assert "write_runtime_debug_report()" in debug_text
    assert "PASSWORD|PASS|TOKEN|PRIVATE_KEY|PRESHARED|PIN|PSK|CERT_B64|SECRET" in debug_text
    assert 'source "$RUNTIME_DEBUG_REPORT_SH"' in prepare_text
    assert 'write_runtime_debug_report "prepare-start"' in prepare_text
    assert 'write_runtime_debug_report "after-network"' in prepare_text
    assert 'write_runtime_debug_report "prepare-ready"' in prepare_text


def test_getty_override_bootstrap_tolerates_existing_readonly_dropin_permissions() -> None:
    bootstrap_text = SYSTEMD_BOOTSTRAP.read_text(encoding="utf-8")

    assert 'mkdir -p "$tty1_dir" "$default_dir"' in bootstrap_text
    assert 'chmod 0755 "$tty1_dir" "$default_dir" >/dev/null 2>&1 || true' in bootstrap_text
    assert 'install -d -m 0755 "$tty1_dir" "$default_dir"' not in bootstrap_text


def test_wireguard_enrollment_script_is_executable_for_prepare_runtime() -> None:
    mode = WIREGUARD_ENROLLMENT.stat().st_mode

    assert mode & stat.S_IXUSR


def test_prepare_runtime_starts_wireguard_runtime_guard() -> None:
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")
    guard_text = WIREGUARD_RUNTIME_GUARD.read_text(encoding="utf-8")
    build_thin_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")
    build_os_text = BUILD_BEAGLE_OS.read_text(encoding="utf-8")
    installer_text = INSTALL_THINCLIENT.read_text(encoding="utf-8")

    assert 'ensure_wireguard_runtime_guard()' in prepare_text
    assert 'ensure_wireguard_runtime_guard || beagle_log_event "prepare-runtime.wg-guard-error"' in prepare_text
    assert 'beagle-wg-runtime-guard.service' in prepare_text
    assert 'phase=wg-runtime-guard' in guard_text
    assert 'ip route replace 0.0.0.0/1 dev "$WG_IFACE"' in guard_text
    assert 'beagle-wg-runtime-guard.service' in build_thin_text
    assert 'beagle-wg-runtime-guard.service' in build_os_text
    assert 'beagle-wg-runtime-guard.service' in installer_text


def test_wireguard_enrollment_works_with_enrollment_token_without_manager_bearer() -> None:
    enrollment_text = RUNTIME_ENDPOINT_ENROLLMENT.read_text(encoding="utf-8")

    assert 'enrollment_token="${PVE_THIN_CLIENT_BEAGLE_ENROLLMENT_TOKEN:-}"' in enrollment_text
    assert "runtime_enrollment_value enrollment_token" in enrollment_text
    assert '[[ -n "$manager_token" || -n "$enrollment_token" ]] || return 1' in enrollment_text
    assert 'BEAGLE_ENROLLMENT_TOKEN="$enrollment_token"' in enrollment_text


def test_wireguard_streaming_never_falls_back_to_public_connect_host() -> None:
    connect_text = BEAGLE_STREAM_CLIENT_CONNECT_HOST.read_text(encoding="utf-8")
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")

    assert "beagle_stream_client_wireguard_required()" in connect_text
    assert "if beagle_stream_client_wireguard_required; then" in connect_text
    assert "resolve_preferred_beagle_stream_client_host \"$local_host\"" in connect_text
    assert connect_text.index("if beagle_stream_client_wireguard_required; then") < connect_text.index('if [[ -n "$public_host" ]]')

    assert "ensure_beagle_stream_wireguard_ready()" in launcher_text
    assert 'enroll_wireguard_if_needed || beagle_log_event "beagle-stream-client.wireguard-enroll-error"' in launcher_text
    assert 'beagle-stream-client.wireguard-required-missing' in launcher_text
    assert 'ensure_beagle_stream_wireguard_ready || exit 1' in launcher_text
    main_text = launcher_text[launcher_text.index("main() {") :]
    assert main_text.index('ensure_beagle_stream_wireguard_ready || exit 1') < main_text.index('connect_host="$(beagle_stream_client_connect_host)"')


def test_hostless_beagle_stream_runtime_uses_enrollment_without_static_host() -> None:
    runtime_text = BEAGLE_STREAM_CLIENT_RUNTIME_EXEC.read_text(encoding="utf-8")
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")
    host_sync_text = BEAGLE_STREAM_CLIENT_HOST_SYNC.read_text(encoding="utf-8")
    launch_session_text = LAUNCH_SESSION.read_text(encoding="utf-8")
    targeting_text = BEAGLE_STREAM_CLIENT_TARGETING.read_text(encoding="utf-8")

    assert "beagle_stream_hostless_enabled()" in runtime_text
    assert 'printf \'%s\\n\' "beagle-stream"' in runtime_text
    assert 'out_ref=("$(beagle_stream_client_bin)" stream "$target" "$app")' in runtime_text
    assert 'out_ref=("$(beagle_stream_client_bin)" stream "$app")' in runtime_text
    assert 'pool_id="$(beagle_stream_enrollment_value pool_id' not in runtime_text
    assert '[[ -n "$control_plane" && -n "$token" && -n "$device_id" ]] || return 1' in runtime_text
    assert 'if beagle_stream_broker_connection; then' in runtime_text
    assert 'if beagle_stream_broker_connection; then' in targeting_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BROKER_HOST' in targeting_text
    assert 'hostless_beagle_stream=1' in launcher_text
    assert "fetch_beagle_stream_client_current_session_via_manager" in launcher_text
    assert 'mode=hostless-fallback host=${host}' in launcher_text
    assert 'mode=hostless host=${host}' in launcher_text
    assert 'ensure_paired || {' in launcher_text
    assert 'beagle_stream_client_stream_ready' in launcher_text
    assert 'beagle-stream-client.register-refresh' in launcher_text
    assert 'sync_beagle_stream_client_host_from_serverinfo_probe' in launcher_text
    assert 'beagle-stream-client.serverinfo-refresh' in launcher_text
    assert 'http://${connect_host}:${port}/serverinfo' in host_sync_text
    assert 'openssl s_client -connect "${connect_host}:${cert_port}"' in host_sync_text
    assert 'beagle-stream-client.port-fallback' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh").read_text(encoding="utf-8")
    assert 'while [[ "$attempt" -lt "$(beagle_stream_client_pairing_timeout)" ]]; do' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh").read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN:-' not in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh").read_text(encoding="utf-8")
    assert '/api/pair-token' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_remote_api.sh").read_text(encoding="utf-8")
    assert 'https://${candidate}:${api_port}' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_remote_api.sh").read_text(encoding="utf-8")
    assert '/api/pin' not in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_remote_api.sh").read_text(encoding="utf-8")
    manager_registration_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_manager_registration.sh").read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_MANAGER_REGISTER_TIMEOUT:-45' in manager_registration_text
    assert 'Failed to load application' in launcher_text
    assert 'prepare-stream.ok" "mode=hostless' in launcher_text
    assert 'beagle_log_event "beagle-stream-client.beagle-stream-hostless"' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST="$local_host"' in host_sync_text
    assert 'value("beagle_stream_client_local_host", "stream_local_host", "guest_ip")' in host_sync_text
    assert 'beagle-stream-client.connection-terminated' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_MAX_RESTARTS:-3' in launcher_text
    assert 'wait_for_stream_server_ready "${connect_host:-$host}" "$port" 15' in launcher_text
    assert 'if [[ "$method" == "broker" && -r /etc/beagle/enrollment.conf ]]; then' in launch_session_text
    assert 'beagle_stream_connection_method()' in targeting_text
    assert 'if beagle_stream_broker_connection; then' in targeting_text


def test_beaglestream_launcher_restores_wireguard_peer_without_truncating_base64_padding() -> None:
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")

    assert 'index($0, "=")' in launcher_text
    assert 'value=substr($0, index($0, "=") + 1)' in launcher_text
    assert 'pubkey="$(wireguard_peer_state_value WG_PEER_PUBLIC_KEY "$peer_state")"' in launcher_text
    assert 'wg set "${wg_args[@]}" 2>/dev/null || sudo wg set "${wg_args[@]}"' in launcher_text
    assert 'write_wireguard_peer_restore_state' in prepare_text
    assert 'WG_PEER_PUBLIC_KEY=%s' in prepare_text
    assert 'WG_PEER_ALLOWED_IPS=%s' in prepare_text
    assert "print $3; exit" not in launcher_text
    assert 'beagle-stream-client.wg-routes-fallback' in launcher_text
    assert 'sudo ip route replace "$route" dev "$iface"' in launcher_text


def test_usbip_autobind_keeps_local_hid_devices_off_usbip_host() -> None:
    usbipd_text = USB_RUNTIME_USBIPD.read_text(encoding="utf-8")
    hotplug_text = USB_HOTPLUG.read_text(encoding="utf-8")
    actions_text = USB_RUNTIME_ACTIONS.read_text(encoding="utf-8")

    assert '03) return 1 ;;  # Any HID interface can be keyboard/mouse: keep local.' in usbipd_text
    assert '_usb_device_has_mounted_block_child "$busid" && return 1' in usbipd_text
    assert 'findmnt -rn -S "/dev/$part"' in usbipd_text
    assert 'is_bound_to_usbip_host()' in usbipd_text
    assert 'if is_bound_to_usbip_host "$item"; then' in usbipd_text
    assert 'if ! _is_eligible_for_autobind "$item"; then' in usbipd_text
    assert 'bound_remove "$item"' in usbipd_text
    assert 'autobind_hotplug_device "$BUSID" && is_bound_to_usbip_host "$BUSID"' in hotplug_text
    assert '_is_eligible_for_autobind "$busid" || {' in actions_text
    assert 'refusing to bind local input/reserved USB device' in actions_text


def test_usbip_autobind_keeps_usb_audio_local_for_mic_bridge() -> None:
    usbipd_text = USB_RUNTIME_USBIPD.read_text(encoding="utf-8")
    actions_text = USB_RUNTIME_ACTIONS.read_text(encoding="utf-8")
    bridge_text = AUDIO_INPUT_BRIDGE.read_text(encoding="utf-8")
    apply_enrollment_text = APPLY_ENROLLMENT_CONFIG.read_text(encoding="utf-8")
    write_config_text = (ROOT / "thin-client-assistant" / "installer" / "write-config.sh").read_text(encoding="utf-8")
    defaults_text = (ROOT / "thin-client-assistant" / "installer" / "env-defaults.json").read_text(encoding="utf-8")

    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_BRIDGE_ENABLED:-1' in usbipd_text
    assert '01) audio_input_bridge_enabled && return 1 ;;' in usbipd_text
    assert 'beagle_audio_input_bridge.py' in actions_text
    assert '$(usb_attach_host):$(audio_input_remote_port):127.0.0.1:$(audio_input_local_port)' in actions_text
    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT:-43200' in actions_text
    assert '"PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT", config.get("usb_audio_input_port", "")' in apply_enrollment_text
    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT="$BEAGLE_AUDIO_INPUT_PORT"' in write_config_text
    assert '"BEAGLE_AUDIO_INPUT_PORT": ""' in defaults_text
    assert 'parec' in bridge_text
    assert '--format=s16le' in bridge_text
    assert '--rate={rate}' in bridge_text
    assert '--channels={channels}' in bridge_text


def test_beaglestream_client_production_baseline_matches_live_smooth_profile() -> None:
    runtime_text = BEAGLE_STREAM_CLIENT_RUNTIME_EXEC.read_text(encoding="utf-8")
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")
    profile_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_stream_profile.sh").read_text(encoding="utf-8")
    defaults_text = (ROOT / "thin-client-assistant" / "installer" / "env-defaults.json").read_text(encoding="utf-8")
    write_config_text = (ROOT / "thin-client-assistant" / "installer" / "write-config.sh").read_text(encoding="utf-8")

    assert 'configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER:-software}"' in profile_text
    assert 'beagle_stream_detect_auto_profile()' in profile_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY:-1' in profile_text
    assert 'beagle-stream-client.auto-quality' in profile_text
    assert 'source "$BEAGLE_STREAM_CLIENT_STREAM_PROFILE_SH"' in launcher_text
    assert 'stream profile afterwards so live tuning and auto-quality overrides win' in launcher_text
    assert 'out_ref+=(--display-mode "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISPLAY_MODE:-windowed}")' in runtime_text
    assert 'out_ref+=(--no-frame-pacing)' in runtime_text
    assert 'out_ref+=(--no-vsync)' in runtime_text
    assert '${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}' in launcher_text
    assert 'export VK_ICD_FILENAMES="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VK_ICD_FILENAMES:-/dev/null}"' in launcher_text
    assert '"BEAGLE_STREAM_CLIENT_VIDEO_DECODER": "software"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_DISPLAY_MODE": "windowed"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_BITRATE": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_AUTO_QUALITY": "1"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_FRAME_PACING": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_VSYNC": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_DISABLE_VULKAN": "1"' in defaults_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISPLAY_MODE="$BEAGLE_STREAM_CLIENT_DISPLAY_MODE"' in write_config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY="$BEAGLE_STREAM_CLIENT_AUTO_QUALITY"' in write_config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN="$BEAGLE_STREAM_CLIENT_DISABLE_VULKAN"' in write_config_text


def test_thin_client_build_can_stage_beagle_stream_client_wrapper() -> None:
    build_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")

    assert "BEAGLE_STREAM_CLIENT_DEFAULT_URL" in build_text
    assert "BeagleStream-latest-x86_64.AppImage" in build_text
    assert "validate_beagle_stream_client_bundle" in build_text
    assert "LD_LIBRARY_PATH=\"$appdir/usr/lib" in build_text
    assert "BeagleStream AppImage has unresolved runtime library dependencies" in build_text
    assert "version `[^" in build_text
    assert "BEAGLE_STREAM_CLIENT_URL" in build_text
    assert "BeagleStream.AppImage" in build_text
    assert 'beagle_wrapper_path="$BUILD_DIR/config/includes.chroot/usr/local/bin/beagle-stream"' in build_text
    assert 'if [[ -x "$target_dir/usr/bin/beagle-stream" ]]; then' in build_text
    assert '"$ROOT_DIR/scripts/lib/trace-guard.sh"' in build_text
    assert 'install -d -m 0755 \\' in build_text
    assert '"$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/runtime"' in build_text
    assert '"$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/installer"' in build_text
    assert '"$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/usb"' in build_text
    assert '"$ROOTFS_STAGE_DIR/usr/local/lib/pve-thin-client/templates"' in build_text
    assert 'find "$target_dir" -type d -exec chmod 0755 {} +' in build_text


def test_live_and_raw_image_builds_default_to_beaglestream_client() -> None:
    raw_build_text = BUILD_BEAGLE_OS.read_text(encoding="utf-8")
    live_hook_text = LIVE_HOOK.read_text(encoding="utf-8")

    assert "BEAGLE_STREAM_CLIENT_DEFAULT_URL" in raw_build_text
    assert "BeagleStream-latest-x86_64.AppImage" in raw_build_text
    assert "BEAGLE_STREAM_CLIENT_FALLBACK_URL" not in raw_build_text
    assert "BeagleStream.AppImage" in raw_build_text
    assert "BEAGLE_STREAM_CLIENT_DEFAULT_URL" in live_hook_text
    assert "BeagleStream-latest-x86_64.AppImage" in live_hook_text
    assert "BEAGLE_STREAM_CLIENT_FALLBACK_URL" not in live_hook_text
    assert "BeagleStream.AppImage" in live_hook_text
    assert 'find "${TARGET_DIR}" -type d -exec chmod 0755 {} +' in live_hook_text


def test_stream_runtime_uses_preset_fallback_host_and_api_url_when_primary_values_are_empty() -> None:
    targeting_text = BEAGLE_STREAM_CLIENT_TARGETING.read_text(encoding="utf-8")
    api_url_text = BEAGLE_STREAM_CLIENT_API_URL.read_text(encoding="utf-8")

    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST' in targeting_text
    assert 'fallback_host="$(render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_CLIENT_HOST:-}"' in targeting_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL' in api_url_text
    assert 'fallback_configured="$(render_template "${PVE_THIN_CLIENT_BEAGLE_STREAM_FALLBACK_BEAGLE_STREAM_SERVER_API_URL:-}"' in api_url_text


def test_broker_runtime_ignores_static_stream_host_values() -> None:
    targeting_text = BEAGLE_STREAM_CLIENT_TARGETING.read_text(encoding="utf-8")

    assert 'render_template "${PVE_THIN_CLIENT_CONNECTION_METHOD:-direct}"' in targeting_text
    assert 'if beagle_stream_broker_connection; then' in targeting_text
    assert 'return 0' in targeting_text


def test_live_image_unlocks_thinclient_account_for_ssh_before_runtime_password_rotation() -> None:
    create_user_text = CREATE_THINCLIENT_USER_HOOK.read_text(encoding="utf-8")
    runtime_user_text = RUNTIME_USER_SETUP.read_text(encoding="utf-8")
    build_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")

    assert 'printf \'%s:%s\\n\' "${THINCLIENT_USER}" "${THINCLIENT_PASSWORD}" | chpasswd' in create_user_text
    assert 'usermod -U "${THINCLIENT_USER}" >/dev/null 2>&1 || passwd -u "${THINCLIENT_USER}" >/dev/null 2>&1 || true' in create_user_text
    assert 'printf \'root:%s\\n\' "${ROOT_DEBUG_PASSWORD}" | chpasswd' in create_user_text
    assert 'PermitRootLogin yes' in (ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "etc" / "ssh" / "sshd_config.d" / "99-pve-thin-client.conf").read_text(encoding="utf-8")
    assert 'local passwd_bin="${BEAGLE_PASSWD_BIN:-passwd}"' in runtime_user_text
    assert '"$usermod_bin" -U "$runtime_user" >/dev/null 2>&1 || "$passwd_bin" -u "$runtime_user" >/dev/null 2>&1 || true' in runtime_user_text
    assert 'sync_root_debug_password' in runtime_user_text
    assert "printf 'root:%s\\n' 'THINCLIENT' | chpasswd" in build_text
    assert "usermod -U root >/dev/null 2>&1 || passwd -u root >/dev/null 2>&1 || true" in build_text
    assert '"/etc/beagle/enrollment.conf"' not in runtime_user_text


def test_runtime_user_setup_opens_enrollment_config_for_runtime_user_group() -> None:
    runtime_user_text = RUNTIME_USER_SETUP.read_text(encoding="utf-8")

    assert 'if [[ -d /etc/beagle ]]; then' in runtime_user_text
    assert '"$chown_bin" root:"$runtime_user" /etc/beagle' in runtime_user_text
    assert 'chmod 0750 /etc/beagle' in runtime_user_text
    assert 'if [[ -f /etc/beagle/enrollment.conf ]]; then' in runtime_user_text
    assert '"$chown_bin" root:"$runtime_user" /etc/beagle/enrollment.conf' in runtime_user_text
    assert 'chmod 0640 /etc/beagle/enrollment.conf' in runtime_user_text


def test_live_image_bundles_libopengl_for_beaglestream_client() -> None:
    package_text = PACKAGE_LIST.read_text(encoding="utf-8")

    assert "libopengl0" in package_text


def test_runtime_network_fallback_does_not_release_live_dhcp_lease() -> None:
    network_backend_text = RUNTIME_NETWORK_BACKEND.read_text(encoding="utf-8")
    apply_network_text = (ROOT / "thin-client-assistant" / "runtime" / "apply-network-config.sh").read_text(encoding="utf-8")

    assert '"$dhclient_bin" -4 -r "$iface"' not in network_backend_text
    assert "network_runtime_ready()" in apply_network_text
    assert 'beagle_log_event "network.reuse"' in apply_network_text


def test_runtime_ssh_config_only_restarts_sshd_when_config_changes() -> None:
    ssh_config_text = RUNTIME_SSH_SERVICE_CONFIG.read_text(encoding="utf-8")

    assert 'if "$systemctl_bin" is-active "$service_name" >/dev/null 2>&1; then' in ssh_config_text
    assert 'if ! cmp -s "${sshd_config}.tmp" "$sshd_config"; then' in ssh_config_text
    assert 'if [[ "$changed" -eq 1 ]]; then' in ssh_config_text
