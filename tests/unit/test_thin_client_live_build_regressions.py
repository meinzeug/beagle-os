from __future__ import annotations

import stat
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
PACKAGE_LIST = ROOT / "thin-client-assistant" / "live-build" / "config" / "package-lists" / "pve-thin-client.list.chroot"
VERIFY_HOOK = ROOT / "thin-client-assistant" / "live-build" / "config" / "hooks" / "live" / "011-verify-runtime-deps.hook.chroot"
PREPARE_RUNTIME = ROOT / "thin-client-assistant" / "runtime" / "prepare-runtime.sh"
SYSTEMD_BOOTSTRAP = ROOT / "thin-client-assistant" / "runtime" / "runtime_systemd_bootstrap.sh"
WIREGUARD_ENROLLMENT = ROOT / "thin-client-assistant" / "runtime" / "enrollment_wireguard.sh"


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


def test_getty_override_bootstrap_tolerates_existing_readonly_dropin_permissions() -> None:
    bootstrap_text = SYSTEMD_BOOTSTRAP.read_text(encoding="utf-8")

    assert 'mkdir -p "$tty1_dir" "$default_dir"' in bootstrap_text
    assert 'chmod 0755 "$tty1_dir" "$default_dir" >/dev/null 2>&1 || true' in bootstrap_text
    assert 'install -d -m 0755 "$tty1_dir" "$default_dir"' not in bootstrap_text


def test_wireguard_enrollment_script_is_executable_for_prepare_runtime() -> None:
    mode = WIREGUARD_ENROLLMENT.stat().st_mode

    assert mode & stat.S_IXUSR
