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
BUILD_THIN_CLIENT = ROOT / "scripts" / "build-thin-client-installer.sh"
BUILD_BEAGLE_OS = ROOT / "scripts" / "build-beagle-os.sh"
LIVE_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "008-install-beagle-stream-client.hook.chroot"


def test_thin_client_live_image_bundles_wireguard_runtime_dependencies() -> None:
    package_text = PACKAGE_LIST.read_text(encoding="utf-8")

    assert "jq" in package_text
    assert "wireguard-tools" in package_text


def test_thin_client_live_image_verifies_wireguard_commands() -> None:
    hook_text = VERIFY_HOOK.read_text(encoding="utf-8")

    assert "wireguard-tools" in hook_text
    assert 'for command_name in jq wg ip; do' in hook_text


def test_prepare_runtime_does_not_block_enrollment_on_getty_bootstrap_failure() -> None:
    prepare_text = PREPARE_RUNTIME.read_text(encoding="utf-8")

    assert 'ensure_getty_overrides || beagle_log_event "prepare-runtime.getty-overrides-error"' in prepare_text
    assert 'ip route delete 0.0.0.0/1 dev "$stale_wg_iface" 2>/dev/null || true' in prepare_text
    assert prepare_text.index("ip route delete 0.0.0.0/1") < prepare_text.index('"$SCRIPT_DIR/apply-network-config.sh"')
    assert prepare_text.index("ensure_getty_overrides ||") < prepare_text.index("enroll_endpoint_if_needed ||")
    assert prepare_text.index("enroll_endpoint_if_needed ||") < prepare_text.index("enroll_wireguard_if_needed ||")


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

    assert "beagle_stream_hostless_enabled()" in runtime_text
    assert 'printf \'%s\\n\' "beagle-stream"' in runtime_text
    assert 'out_ref=("$(beagle_stream_client_bin)" stream "$app")' in runtime_text
    assert 'hostless_beagle_stream=1' in launcher_text
    assert "fetch_beagle_stream_client_current_session_via_manager" in launcher_text
    assert 'beagle_log_event "beagle-stream-client.beagle-stream-hostless"' in launcher_text


def test_thin_client_build_can_stage_beagle_stream_client_wrapper() -> None:
    build_text = BUILD_THIN_CLIENT.read_text(encoding="utf-8")

    assert "BEAGLE_STREAM_CLIENT_DEFAULT_URL" in build_text
    assert "BeagleStream-latest-x86_64.AppImage" in build_text
    assert "BEAGLE_STREAM_CLIENT_URL" in build_text
    assert "BeagleStream.AppImage" in build_text
    assert 'beagle_wrapper_path="$BUILD_DIR/config/includes.chroot/usr/local/bin/beagle-stream"' in build_text
    assert 'if [[ -x "$target_dir/usr/bin/beagle-stream" ]]; then' in build_text


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
