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
DCV_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "007-install-dcv-viewer.hook.chroot"
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
    assert "dbus-user-session" in package_text
    assert "libpam-systemd" in package_text


def test_thin_client_live_image_verifies_wireguard_commands() -> None:
    hook_text = VERIFY_HOOK.read_text(encoding="utf-8")

    assert "wireguard-tools" in hook_text
    assert "dbus-user-session" in hook_text
    assert "libpam-systemd" in hook_text
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


def test_live_build_starts_runtime_session_bootstrap_by_default() -> None:
    hook_text = ENABLE_SERVICES_HOOK.read_text(encoding="utf-8")
    build_thin_client_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")
    prepare_downloads_text = PREPARE_HOST_DOWNLOADS.read_text(encoding="utf-8")

    assert "beagle-thin-client-prepare.service" in hook_text
    assert "getty@tty1.service" in hook_text
    assert "ensure_wantedby_symlink /etc/systemd/system/beagle-thin-client-prepare.service multi-user.target" in hook_text
    assert "ensure_wantedby_symlink /etc/systemd/system/pve-thin-client-runtime.service multi-user.target" in hook_text
    assert '    pve-thin-client-runtime.service \\' in build_thin_client_text
    assert "ensure_rootfs_wants_link pve-thin-client-runtime.service multi-user.target" in build_thin_client_text
    assert 'multi-user.target.wants/pve-thin-client-runtime.service"' not in prepare_downloads_text


def test_live_build_chroot_uses_apt_retry_configuration() -> None:
    apt_conf = (ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "etc" / "apt" / "apt.conf.d" / "99beagle-retries").read_text(encoding="utf-8")

    assert 'Acquire::Retries "5";' in apt_conf
    assert 'Acquire::https::Timeout "60";' in apt_conf


def test_thin_client_live_hooks_retry_transient_apt_failures() -> None:
    dcv_hook = DCV_HOOK.read_text(encoding="utf-8")
    stream_hook = LIVE_HOOK.read_text(encoding="utf-8")

    assert 'APT_RETRY_ATTEMPTS="${BEAGLE_APT_RETRY_ATTEMPTS:-5}"' in dcv_hook
    assert 'apt_retry apt-get update -qq -o Acquire::Retries=5 -o Acquire::https::Timeout=60' in dcv_hook
    assert 'apt_retry apt-get install -y --fix-missing --no-install-recommends' in dcv_hook

    assert 'APT_RETRY_ATTEMPTS="${BEAGLE_APT_RETRY_ATTEMPTS:-5}"' in stream_hook
    assert 'apt_retry apt-get update -qq -o Acquire::Retries=5 -o Acquire::https::Timeout=60' in stream_hook
    assert 'apt_retry apt-get install -y --fix-missing --no-install-recommends' in stream_hook


def test_runtime_service_bootstraps_getty_session_without_owning_x11_tty() -> None:
    owner_script = ROOT / "thin-client-assistant" / "runtime" / "runtime_getty_session_owner.sh"
    login_shell = ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "bin" / "pve-thin-client-login-shell"
    unit = (ROOT / "thin-client-assistant" / "live-build" / "config" / "includes.chroot" / "etc" / "systemd" / "system" / "pve-thin-client-runtime.service").read_text(encoding="utf-8")
    login_shell_text = login_shell.read_text(encoding="utf-8")

    assert "Description=Thinclient Runtime Session Bootstrap" in unit
    assert "Type=oneshot" in unit
    assert "RemainAfterExit=yes" in unit
    assert "ExecStart=/usr/local/lib/pve-thin-client/runtime/runtime_getty_session_owner.sh" in unit
    assert "Wants=plymouth-quit-wait.service network.target pve-thin-client-network-menu.service beagle-thin-client-prepare.service getty@tty1.service" in unit
    assert "Conflicts=getty@tty1.service" not in unit
    assert "User=thinclient" not in unit
    assert "ExecStart=/usr/local/bin/pve-thin-client-start-x11" not in unit
    assert owner_script.exists()
    assert owner_script.stat().st_mode & 0o111
    assert '"$SYSTEMCTL_BIN" cat "$GETTY_UNIT"' in owner_script.read_text(encoding="utf-8")
    assert 'list-unit-files "$GETTY_UNIT"' not in owner_script.read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_X11_RESTART_ON_EXIT:-1' in login_shell_text
    assert 'PVE_THIN_CLIENT_X11_RESTART_DELAY:-3' in login_shell_text
    assert login_shell_text.index('/usr/local/bin/pve-thin-client-start-x11') < login_shell_text.index('exec /bin/bash --login')


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
    assert "pgrep -x beagle-stream-client" in heartbeat
    assert "pgrep -f '(^|/)beagle-stream stream( |$)'" in heartbeat


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
    assert 'ip route delete default dev "$WG_IFACE"' in guard_text
    assert 'ip route replace 0.0.0.0/1 dev "$WG_IFACE"' in guard_text
    assert 'ip route delete "$endpoint_host" dev "$WG_IFACE"' in guard_text
    assert 'ip route replace "$endpoint_host" via "$default_gw" dev "$default_dev"' in guard_text
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
    assert 'pin-compat' in manager_registration_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_COMPAT_PIN' in manager_registration_text
    assert 'manager-pin-compat' not in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_MANAGER_REGISTER_TIMEOUT:-6' in manager_registration_text
    assert 'Failed to load application' in launcher_text
    assert 'prepare-stream.ok" "mode=hostless' in launcher_text
    assert 'beagle_log_event "beagle-stream-client.beagle-stream-hostless"' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST="$local_host"' in host_sync_text
    assert 'value("beagle_stream_client_local_host", "stream_local_host", "guest_ip")' in host_sync_text
    assert 'beagle-stream-client.connection-terminated' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_MAX_RESTARTS:-3' in launcher_text
    assert 'wait_for_stream_server_ready "${connect_host:-$host}" "$port" 15' in launcher_text
    assert 'BEAGLE_STREAM_CLIENT_LAUNCHER_ACTIVE:-0' in launcher_text
    assert 'beagle-stream-client.reentry-suppressed' in launcher_text
    assert '{ exec 9>&- || true; "${args[@]}"; } >>"$BEAGLE_STREAM_CLIENT_STREAM_LOG" 2>&1 &' in launcher_text
    runtime_exec_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_runtime_exec.sh").read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUDIO_ON_HOST:-0' in runtime_exec_text
    assert 'out_ref+=(--audio-on-host)' in runtime_exec_text
    assert 'beagle_stream_startup_status_pace()' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_STARTUP_STATUS_ENABLED:-0' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_STARTUP_STATUS_PACE_SEC:-0.5' in launcher_text
    assert "if (p+0 < 0.5) print 0.5; else print p+0" in launcher_text
    assert "window.location.replace(current.toString())" in launcher_text
    assert "initial_state = json.dumps(state, ensure_ascii=True)" in launcher_text
    assert "initial_state = html.escape(json.dumps(state, ensure_ascii=True))" not in launcher_text
    assert 'if [[ "$method" == "broker" && -r /etc/beagle/enrollment.conf ]]; then' in launch_session_text
    assert 'beagle_stream_connection_method()' in targeting_text
    assert 'if beagle_stream_broker_connection; then' in targeting_text


def test_beaglestream_launcher_waits_for_manager_registration_before_stream_exec() -> None:
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")
    manager_registration_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_manager_registration.sh").read_text(encoding="utf-8")

    assert 'wait_for_beagle_stream_client_manager_registration()' in launcher_text
    assert 'beagle_stream_client_manager_url 2>/dev/null || true' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_MANAGER_TOKEN:-' in launcher_text
    assert 'extract_beagle_stream_client_certificate_pem >/dev/null 2>&1' in launcher_text
    assert 'bootstrap_beagle_stream_client >/dev/null 2>&1 || true' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_REGISTER_WAIT_ATTEMPTS:-30' in launcher_text
    assert 'beagle-stream-client.register-wait' in launcher_text
    assert 'beagle-stream-client.register-wait-fail-open' in launcher_text
    assert 'beagle-stream-client.register-wait-timeout' in launcher_text
    assert 'pkill -TERM -f -- "--user-data-dir=${BEAGLE_STREAM_CLIENT_STARTUP_BROWSER_PROFILE}"' in launcher_text
    assert 'ensure_iface_route "0.0.0.0/1"' in launcher_text
    assert 'ip route delete default dev "$iface"' in launcher_text
    assert 'ensure_iface_route "$route"' in launcher_text
    assert 'ip route replace "$endpoint_host" via "$default_gw" dev "$default_dev"' in launcher_text
    assert 'route_uses_dev "$route_spec" "$iface" && return 0' in launcher_text
    assert launcher_text.index('wait_for_beagle_stream_client_manager_registration || {') < launcher_text.index('beagle-stream-client.exec')
    assert 'beagle_stream_client_manager_url()' in manager_registration_text
    assert 'beagle_stream_enrollment_value control_plane' in manager_registration_text
    assert 'awk -F= \'$1 == "control_plane"' in manager_registration_text


def test_prepare_host_downloads_rebuilds_payload_after_public_mirror_fallback() -> None:
    prepare_text = PREPARE_HOST_DOWNLOADS.read_text(encoding="utf-8")

    assert "local_live_assets_complete()" in prepare_text
    assert "rebuild_packaged_payload_from_live_assets()" in prepare_text
    assert 'rebuild_packaged_payload_from_live_assets "local package build fallback after mirror hydration" || true' in prepare_text
    assert prepare_text.index("hydrate_packaged_artifacts_from_public_release") < prepare_text.index('rebuild_packaged_payload_from_live_assets "local package build fallback after mirror hydration" || true')
    assert 'ln -f "$payload_versioned" "$bootstrap_versioned"' in prepare_text
    assert 'ln -f "$payload_latest" "$bootstrap_latest"' in prepare_text
    assert "ensure_versioned_payload_aliases()" in prepare_text
    assert 'PAYLOAD_VERSIONED_URL="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-payload-v${VERSION}.tar.gz")"' in prepare_text
    assert 'BOOTSTRAP_VERSIONED_URL="$(beagle_hosted_download_url "$DOWNLOADS_BASE_URL" "pve-thin-client-usb-bootstrap-v${VERSION}.tar.gz")"' in prepare_text
    assert '--payload-url "$PAYLOAD_VERSIONED_URL"' in prepare_text
    assert '--bootstrap-url "$BOOTSTRAP_VERSIONED_URL"' in prepare_text
    assert 'local live assets before ISO fallback' in prepare_text
    assert 'if [[ ! -f "$packaged_payload" ]]; then' in prepare_text


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
    assert 'ensure_iface_route "$route"' in launcher_text


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
    assert '01) audio_input_bridge_enabled && continue ;;' in usbipd_text
    assert '0e) return 1 ;;  # Webcams stay local so beagle-camera-stream can expose them to the VM reliably.' in usbipd_text
    assert '_usb_device_has_block_child "$busid" && return 1' in usbipd_text
    assert '_usb_device_has_storage_interface "$busid" && return 1' in usbipd_text
    assert '[[ "$iface_class" == "08" ]] && return 0' in usbipd_text
    assert '01|06|07|0a|0b|ff) has_useful=1 ;;' in usbipd_text
    assert '01|06|07|0a|0b|0e|ff) has_useful=1 ;;' not in usbipd_text
    assert 'has_interface=1' in usbipd_text
    assert '_usb_device_identity_has_camera_hint()' in usbipd_text
    assert 'grep -Eq \'(camera|webcam|video|uvc|cam)\'' in usbipd_text
    assert '[[ "$class" == "ef" ]] && _usb_device_identity_has_camera_hint "$busid" && return 1' in usbipd_text
    assert 'bound_add "$busid" >/dev/null 2>&1 || true' in usbipd_text
    assert 'printf \'%s\\n\' "/usr/sbin/usbip"' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_usb_runtime_env.sh").read_text(encoding="utf-8")
    assert 'printf \'%s\\n\' "/usr/sbin/usbipd"' in actions_text
    assert 'beagle_audio_input_bridge.py' in actions_text
    assert '$(usb_attach_host):$(audio_input_remote_port):127.0.0.1:$(audio_input_local_port)' in actions_text
    assert 'PVE_THIN_CLIENT_BEAGLE_USB_EXTRA_REVERSE_FORWARDS' in actions_text
    assert 'append_extra_reverse_forwards "$tunnel_attach_host" reverse_forwards' in actions_text
    assert "ignoring invalid extra reverse forward" in actions_text
    assert "enabled extra reverse forward" in actions_text
    assert 'stale_tunnel_pids' in actions_text
    assert 'remote reverse port occupied' in actions_text
    assert 'waiting for host stale-session reaper' in actions_text
    assert 'kill -9 "$pid"' in actions_text
    assert '"$ssh_cmd" -N \\' in actions_text
    assert 'exec "$ssh_cmd" -N \\' not in actions_text
    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT:-43200' in actions_text
    assert '"PVE_THIN_CLIENT_BEAGLE_USB_EXTRA_REVERSE_FORWARDS", config.get("usb_extra_reverse_forwards", "")' in apply_enrollment_text
    assert '"PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT", config.get("usb_audio_input_port", "")' in apply_enrollment_text
    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_PORT="$BEAGLE_AUDIO_INPUT_PORT"' in write_config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_USB_EXTRA_REVERSE_FORWARDS="$BEAGLE_USB_EXTRA_REVERSE_FORWARDS"' in write_config_text
    assert '"BEAGLE_AUDIO_INPUT_PORT": ""' in defaults_text
    assert '"BEAGLE_USB_EXTRA_REVERSE_FORWARDS": ""' in defaults_text
    assert 'parec' in bridge_text
    assert '--format=s16le' in bridge_text
    assert '--rate={rate}' in bridge_text
    assert '--channels={channels}' in bridge_text
    assert '--frame-msec", type=int' in bridge_text
    assert 'PVE_THIN_CLIENT_BEAGLE_AUDIO_INPUT_FRAME_MSEC", "20"' in bridge_text


def test_beaglestream_client_production_baseline_matches_live_smooth_profile() -> None:
    runtime_text = BEAGLE_STREAM_CLIENT_RUNTIME_EXEC.read_text(encoding="utf-8")
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")
    profile_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_stream_profile.sh").read_text(encoding="utf-8")
    defaults_text = (ROOT / "thin-client-assistant" / "installer" / "env-defaults.json").read_text(encoding="utf-8")
    write_config_text = (ROOT / "thin-client-assistant" / "installer" / "write-config.sh").read_text(encoding="utf-8")

    assert 'configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER:-auto}"' in profile_text
    assert 'if beagle_stream_hostless_enabled; then\n      printf \'software\\n\'' not in profile_text
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
    assert '"BEAGLE_STREAM_CLIENT_VIDEO_DECODER": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_DISPLAY_MODE": "windowed"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_BITRATE": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_AUTO_QUALITY": "1"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_FRAME_PACING": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_VSYNC": "auto"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_DISABLE_VULKAN": "1"' in defaults_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISPLAY_MODE="$BEAGLE_STREAM_CLIENT_DISPLAY_MODE"' in write_config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY="$BEAGLE_STREAM_CLIENT_AUTO_QUALITY"' in write_config_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN="$BEAGLE_STREAM_CLIENT_DISABLE_VULKAN"' in write_config_text


def test_stream_launcher_does_not_rewrite_healthy_wireguard_routes_during_stream() -> None:
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")

    assert "route_uses_dev()" in launcher_text
    assert "endpoint_route_ok()" in launcher_text
    assert "ensure_iface_route()" in launcher_text
    assert 'routes_changed=0' in launcher_text
    assert 'if [[ "$routes_changed" == "1" ]]; then' in launcher_text
    assert 'route_uses_dev "0.0.0.0/1" "$iface"' in launcher_text
    assert 'sudo ip route delete default dev "$iface"' in launcher_text
    assert 'sudo ip route delete default dev "$iface" >/dev/null 2>&1 || true\n  IFS=' not in launcher_text
    assert 'sudo ip route replace "$route" dev "$iface" >/dev/null 2>&1 || true' not in launcher_text


def test_thin_client_build_can_stage_beagle_stream_client_wrapper() -> None:
    build_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")

    assert "BEAGLE_STREAM_CLIENT_DEFAULT_URL" in build_text
    assert "BeagleStream-latest-x86_64.AppImage" in build_text
    assert "BEAGLE_STREAM_CLIENT_SHA256SUMS_URL" in build_text
    assert "resolve_release_sha256" in build_text
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
    assert "BEAGLE_STREAM_CLIENT_SHA256SUMS_URL" in raw_build_text
    assert "BEAGLE_STREAM_CLIENT_FALLBACK_URL" not in raw_build_text
    assert "BeagleStream.AppImage" in raw_build_text
    assert "BEAGLE_STREAM_CLIENT_DEFAULT_URL" in live_hook_text
    assert "BeagleStream-latest-x86_64.AppImage" in live_hook_text
    assert "BEAGLE_STREAM_CLIENT_SHA256SUMS_URL" in live_hook_text
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


def test_live_image_bundles_legacy_laptop_firmware_and_video_drivers() -> None:
    package_text = PACKAGE_LIST.read_text(encoding="utf-8")
    verify_text = VERIFY_HOOK.read_text(encoding="utf-8")
    initramfs_text = (ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "013-configure-amd-initramfs.hook.chroot").read_text(encoding="utf-8")
    initramfs_verify_text = (ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "014-verify-amd-initramfs.hook.chroot").read_text(encoding="utf-8")

    for package in (
        "firmware-linux",
        "firmware-atheros",
        "firmware-brcm80211",
        "firmware-libertas",
        "firmware-zd1211",
        "firmware-ti-connectivity",
        "firmware-mediatek",
        "intel-microcode",
        "amd64-microcode",
        "libgl1-mesa-dri",
        "xserver-xorg-video-ati",
        "xserver-xorg-video-radeon",
        "xserver-xorg-video-nouveau",
        "xserver-xorg-video-fbdev",
    ):
        assert package in package_text

    for package in (
        "firmware-linux",
        "firmware-atheros",
        "firmware-brcm80211",
        "intel-microcode",
        "amd64-microcode",
        "xserver-xorg-video-radeon",
        "xserver-xorg-video-fbdev",
    ):
        assert package in verify_text

    for module in ("amdgpu", "radeon", "i915", "nouveau"):
        assert module in initramfs_text
    assert "for module_name in radeon i915" in initramfs_verify_text


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
