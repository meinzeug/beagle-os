from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "install-beagle-host-services.sh"


def test_legacy_host_runtime_dir_uses_underscore_alias() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'HOST_RUNTIME_DIR="$INSTALL_DIR/beagle-host"' in script
    assert 'LEGACY_HOST_RUNTIME_DIR="$INSTALL_DIR/beagle_host"' in script


def test_host_runtime_repair_handles_self_symlink_and_uses_relative_alias() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert "repair_host_runtime_links()" in script
    assert 'if [[ -L "$HOST_RUNTIME_DIR" ]]; then' in script
    assert 'rm -f "$HOST_RUNTIME_DIR"' in script
    assert 'install -d -m 0755 "$HOST_RUNTIME_DIR"' in script
    assert 'ln -sfn "beagle-host" "$LEGACY_HOST_RUNTIME_DIR"' in script


def test_wireguard_reconcile_units_are_installed_and_enabled() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'BEAGLE_WIREGUARD_RECONCILE_SERVICE="beagle-wireguard-reconcile.service"' in script
    assert 'BEAGLE_WIREGUARD_RECONCILE_PATH="beagle-wireguard-reconcile.path"' in script
    assert 'install_unit "$ROOT_DIR/beagle-host/systemd/$BEAGLE_WIREGUARD_RECONCILE_SERVICE"' in script
    assert 'install -m 0644 "$ROOT_DIR/beagle-host/systemd/$BEAGLE_WIREGUARD_RECONCILE_PATH"' in script
    assert 'systemctl enable "$BEAGLE_WIREGUARD_RECONCILE_PATH" 2>/dev/null || true' in script
    assert '"$BEAGLE_WIREGUARD_RECONCILE_PATH")' in script


def test_secret_store_dir_is_bootstrapped_for_control_plane_user() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'install -d -m 0700 -o "$BEAGLE_CONTROL_USER" -g "$BEAGLE_CONTROL_USER" /var/lib/beagle/secrets' in script


def test_auth_reset_and_bootstrap_disable_state_are_install_time_aware() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'BEAGLE_AUTH_RESET_ON_INSTALL="${BEAGLE_AUTH_RESET_ON_INSTALL:-0}"' in script
    assert 'existing_bootstrap_disable="$(strip_env_quotes "$(read_env_value "$BEAGLE_CONTROL_ENV_FILE" "BEAGLE_AUTH_BOOTSTRAP_DISABLE" 2>/dev/null || true)")"' in script
    assert 'if [[ "$(normalize_bool_flag "$BEAGLE_AUTH_RESET_ON_INSTALL")" == "1" ]]; then' in script
    assert 'rm -rf /var/lib/beagle/beagle-manager/auth' in script


def test_kvm_device_permissions_are_persisted_via_udev_rule() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'KVM_UDEV_RULE_FILE="/etc/udev/rules.d/65-beagle-kvm.rules"' in script
    assert "ensure_kvm_device_permissions()" in script
    assert 'KERNEL=="kvm", GROUP="kvm", MODE="0660"' in script
    assert 'udevadm trigger --name-match=/dev/kvm >/dev/null 2>&1 || true' in script
    assert 'chgrp kvm /dev/kvm >/dev/null 2>&1 || true' in script
    assert 'chmod 0660 /dev/kvm >/dev/null 2>&1 || true' in script
    assert "ensure_kvm_device_permissions" in script


def test_install_beagle_host_services_writes_installed_commit_stamp_when_git_checkout_exists() -> None:
    script = SCRIPT.read_text(encoding="utf-8")

    assert 'INSTALLED_COMMIT_FILE="$INSTALL_DIR/.beagle-installed-commit"' in script
    assert "write_installed_commit_stamp()" in script
    assert 'git -C "$ROOT_DIR" rev-parse HEAD' in script
    assert 'printf \'%s\\n\' "$commit" > "$INSTALLED_COMMIT_FILE"' in script
    assert 'write_installed_commit_stamp' in script
