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
BEAGLE_STREAM_CLIENT_RUNTIME_EXEC = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_runtime_exec.sh"
LAUNCH_BEAGLE_STREAM_CLIENT = ROOT / "thin-client-assistant" / "runtime" / "launch-beagle-stream-client.sh"
LAUNCH_SESSION = ROOT / "thin-client-assistant" / "runtime" / "launch-session.sh"
BUILD_THIN_CLIENT = ROOT / "scripts" / "build-thin-client-installer.sh"
BUILD_BEAGLE_OS = ROOT / "scripts" / "build-beagle-os.sh"
LIVE_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "008-install-beagle-stream-client.hook.chroot"
CREATE_THINCLIENT_USER_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "005-create-thinclient-user.hook.chroot"
BEAGLE_STREAM_CLIENT_TARGETING = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_targeting.sh"
BEAGLE_STREAM_CLIENT_HOST_SYNC = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_host_sync.sh"
BEAGLE_STREAM_CLIENT_API_URL = ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_api_url.sh"
RUNTIME_USER_SETUP = ROOT / "thin-client-assistant" / "runtime" / "runtime_user_setup.sh"
RUNTIME_NETWORK_BACKEND = ROOT / "thin-client-assistant" / "runtime" / "runtime_network_backend.sh"
RUNTIME_SSH_SERVICE_CONFIG = ROOT / "thin-client-assistant" / "runtime" / "runtime_ssh_service_config.sh"


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
    assert prepare_text.index("ip route delete 0.0.0.0/1") < prepare_text.index('"$SCRIPT_DIR/apply-network-config.sh"')
    assert prepare_text.index("ensure_getty_overrides ||") < prepare_text.index("enroll_endpoint_if_needed ||")
    assert prepare_text.index("enroll_endpoint_if_needed ||") < prepare_text.index("enroll_wireguard_if_needed ||")
    assert "prepare_runtime_already_ready()" in prepare_text
    assert 'prepare_runtime_reentry=1' in prepare_text
    assert 'prepare-runtime.reentry' in prepare_text
    assert 'if [[ "$prepare_runtime_reentry" -eq 0 ]]; then' in prepare_text


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
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PAIRING_TOKEN' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh").read_text(encoding="utf-8")
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_SERVER_PIN:-' not in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_pairing.sh").read_text(encoding="utf-8")
    assert '/api/pair-token' in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_remote_api.sh").read_text(encoding="utf-8")
    assert '/api/pin' not in (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_remote_api.sh").read_text(encoding="utf-8")
    assert 'prepare-stream.ok" "mode=hostless' in launcher_text
    assert 'beagle_log_event "beagle-stream-client.beagle-stream-hostless"' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_LOCAL_HOST="$local_host"' in host_sync_text
    assert 'value("beagle_stream_client_local_host", "stream_local_host", "guest_ip")' in host_sync_text
    assert 'beagle-stream-client.connection-terminated' in launcher_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_MAX_RESTARTS:-3' in launcher_text
    assert 'if [[ "$method" == "broker" && -r /etc/beagle/enrollment.conf ]]; then' in launch_session_text
    assert 'beagle_stream_connection_method()' in targeting_text
    assert 'if beagle_stream_broker_connection; then' in targeting_text


def test_beaglestream_client_production_baseline_matches_live_smooth_profile() -> None:
    runtime_text = BEAGLE_STREAM_CLIENT_RUNTIME_EXEC.read_text(encoding="utf-8")
    launcher_text = LAUNCH_BEAGLE_STREAM_CLIENT.read_text(encoding="utf-8")
    profile_text = (ROOT / "thin-client-assistant" / "runtime" / "beagle_stream_client_stream_profile.sh").read_text(encoding="utf-8")
    defaults_text = (ROOT / "thin-client-assistant" / "installer" / "env-defaults.json").read_text(encoding="utf-8")
    write_config_text = (ROOT / "thin-client-assistant" / "installer" / "write-config.sh").read_text(encoding="utf-8")

    assert 'configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VIDEO_DECODER:-software}"' in profile_text
    assert 'configured="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE:-32000}"' in profile_text
    assert 'out_ref+=(--display-mode "${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISPLAY_MODE:-windowed}")' in runtime_text
    assert 'out_ref+=(--no-frame-pacing)' in runtime_text
    assert 'out_ref+=(--no-vsync)' in runtime_text
    assert '${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISABLE_VULKAN:-1}' in launcher_text
    assert 'export VK_ICD_FILENAMES="${PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_VK_ICD_FILENAMES:-/dev/null}"' in launcher_text
    assert '"BEAGLE_STREAM_CLIENT_VIDEO_DECODER": "software"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_DISPLAY_MODE": "windowed"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_FRAME_PACING": "0"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_VSYNC": "0"' in defaults_text
    assert '"BEAGLE_STREAM_CLIENT_DISABLE_VULKAN": "1"' in defaults_text
    assert 'PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_DISPLAY_MODE="$BEAGLE_STREAM_CLIENT_DISPLAY_MODE"' in write_config_text
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
