from __future__ import annotations

import importlib.util
import json
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
HELPER = ROOT / "scripts" / "lib" / "prepare_host_downloads.py"
SPEC = importlib.util.spec_from_file_location("beagle_prepare_host_downloads", HELPER)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC is not None and SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


def test_write_download_status_omits_server_release_artifacts_when_not_hosted_locally() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        vm_installers = base / "beagle-vm-installers.json"
        status_path = base / "beagle-downloads-status.json"

        installer = base / "pve-thin-client-usb-installer-host-latest.sh"
        live_usb = base / "pve-thin-client-live-usb-host-latest.sh"
        installer_windows = base / "pve-thin-client-usb-installer-host-latest.ps1"
        live_usb_windows = base / "pve-thin-client-live-usb-host-latest.ps1"
        payload = base / "pve-thin-client-usb-payload-latest.tar.gz"

        for path in (
            installer,
            live_usb,
            installer_windows,
            live_usb_windows,
            payload,
        ):
            path.write_bytes(b"artifact")

        vm_installers.write_text("[]\n", encoding="utf-8")

        MODULE.write_download_status(
            status_path=status_path,
            version="8.0",
            server_name="srv1.beagle-os.com",
            listen_port=443,
            downloads_path="/beagle-downloads",
            installer_url="https://srv1/beagle-downloads/pve-thin-client-usb-installer-host-latest.sh",
            live_usb_url="https://srv1/beagle-downloads/pve-thin-client-live-usb-host-latest.sh",
            installer_windows_url="https://srv1/beagle-downloads/pve-thin-client-usb-installer-host-latest.ps1",
            live_usb_windows_url="https://srv1/beagle-downloads/pve-thin-client-live-usb-host-latest.ps1",
            bootstrap_url="https://srv1/beagle-downloads/pve-thin-client-usb-bootstrap-v8.0.tar.gz",
            payload_url="https://srv1/beagle-downloads/pve-thin-client-usb-payload-v8.0.tar.gz",
            installer_iso_url="https://beagle-os.com/beagle-updates/beagle-os-installer-amd64.iso",
            status_url="https://srv1/beagle-downloads/beagle-downloads-status.json",
            sha256sums_url="https://srv1/beagle-downloads/SHA256SUMS",
            installer_path=installer,
            live_usb_path=live_usb,
            installer_windows_path=installer_windows,
            live_usb_windows_path=live_usb_windows,
            payload_path=payload,
            installer_sha256="sha-installer",
            bootstrap_sha256="sha-bootstrap",
            payload_sha256="sha-payload",
            vm_installer_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/installer.sh",
            vm_windows_installer_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/installer.ps1",
            vm_windows_live_usb_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/live-usb.ps1",
            vm_live_usb_url_template="https://srv1/beagle-api/api/v1/vms/{vmid}/live-usb.sh",
            vm_installers_path=vm_installers,
        )

        payload_json = json.loads(status_path.read_text(encoding="utf-8"))
        assert "server_installer_iso_url" not in payload_json
        assert "server_installimage_url" not in payload_json
        assert payload_json["installer_iso_url"].endswith("beagle-os-installer-amd64.iso")
        assert "installer_iso_size" not in payload_json
        assert payload_json["bootstrap_url"].endswith("pve-thin-client-usb-bootstrap-v8.0.tar.gz")
        assert payload_json["payload_url"].endswith("pve-thin-client-usb-payload-v8.0.tar.gz")
        assert payload_json["bootstrap_filename"] == payload_json["payload_filename"] == "pve-thin-client-usb-payload-latest.tar.gz"
        assert payload_json["endpoint_compatibility"]["foundation_generation"] == "2"
        assert payload_json["endpoint_compatibility"]["minimum_self_update_version"] == "8.0"
        assert payload_json["endpoint_compatibility"]["reinstall_required"] is False


def test_vm_catalog_preset_carries_default_manager_token() -> None:
    captured: dict[str, str] = {}
    original_encode = MODULE._encode_preset

    def capture_preset(preset):
        captured.update(dict(preset))
        return original_encode(preset)

    MODULE._encode_preset = capture_preset
    try:
        MODULE._build_vm_catalog_entry(
            vm={"vmid": 100, "node": "srv1"},
            config={
                "name": "ubuntu-beagle-100",
                "description": "beagle-stream-client-host=46.4.96.80",
            },
            load_vm_config=lambda _node, _vmid: {},
            metadata_support=MODULE.MetadataSupportService(),
            server_name="srv1.beagle-os.com",
            installer_iso_url="https://downloads.example/installer.iso",
            default_beagle_username="",
            default_beagle_password="",
            default_beagle_token="manager-token-xyz",
            beagle_manager_url="https://srv1.beagle-os.com/beagle-api",
        )
    finally:
        MODULE._encode_preset = original_encode

    assert captured["PVE_THIN_CLIENT_PRESET_BEAGLE_MANAGER_TOKEN"] == "manager-token-xyz"


def test_check_beagle_host_expects_versioned_host_payload_urls_in_status_json() -> None:
    script = (ROOT / "scripts" / "check-beagle-host.sh").read_text(encoding="utf-8")

    assert 'version="$(tr -d \' \\n\\r\' < "$INSTALL_DIR/VERSION")"' in script
    assert 'pve-thin-client-usb-bootstrap-v${version}.tar.gz' in script
    assert 'pve-thin-client-usb-payload-v${version}.tar.gz' in script
    assert 'printf \'%s\\n\' "${PVE_DCV_PROXY_CERT_FILE:-$BEAGLE_PROXY_TLS_DIR/beagle-proxy.crt}"' in script
    assert 'curl_args+=(--insecure) # tls-bypass-allowlist: first-install host validation must accept bootstrap self-signed proxy certs' in script


def test_prepare_host_downloads_rebuilds_usb_payload_when_thinclient_runtime_changes() -> None:
    script = (ROOT / "scripts" / "prepare-host-downloads.sh").read_text(encoding="utf-8")

    assert "any_source_newer_than()" in script
    assert '"$ROOT_DIR/thin-client-assistant/runtime"' in script
    assert '"$ROOT_DIR/thin-client-assistant/live-build"' in script
    assert 'any_source_newer_than "$packaged_payload" "${thin_client_package_sources[@]}"' in script


def test_prepare_host_downloads_refreshes_live_squashfs_from_repo_sources() -> None:
    script = (ROOT / "scripts" / "prepare-host-downloads.sh").read_text(encoding="utf-8")

    assert "refresh_live_rootfs_from_repo()" in script
    assert "refresh_live_rootfs_from_repo_overlay()" in script
    assert 'run_maybe_sudo mksquashfs "$rootfs_mount" "${squashfs_path}.new" -comp xz -noappend -ef "$exclude_file" -pf "$pseudo_file"' in script
    assert 'unsquashfs -d "$rootfs_stage" "$squashfs_path"' in script
    assert 'mksquashfs "$rootfs_stage" "${squashfs_path}.new" -comp xz -noappend' in script
    assert '"$ROOT_DIR/thin-client-assistant/runtime/"' in script
    assert '"$ROOT_DIR/beagle-os/overlay/usr/local/sbin/beagle-update-client"' in script
    assert '"$ROOT_DIR/thin-client-assistant/live-build/config/includes.chroot/usr/local/sbin/beagle-runtime-heartbeat"' in script
    assert '"$ROOT_DIR/thin-client-assistant/systemd/pve-thin-client-network-menu.service"' in script


def test_iso_bootstrap_fast_path_does_not_mask_thinclient_source_rebuild() -> None:
    script = (ROOT / "scripts" / "prepare-host-downloads.sh").read_text(encoding="utf-8")
    fast_path = script.split("ensure_bootstrap_from_deployed_iso()", 1)[1].split("recover_packaged_artifacts_from_existing_builds()", 1)[0]

    assert '[[ "$packaged_payload" -nt "$iso" ]]' in fast_path
    assert "any_source_newer_than" not in fast_path


def test_prepare_host_downloads_treats_busy_artifact_lock_as_duplicate_success() -> None:
    script = (ROOT / "scripts" / "prepare-host-downloads.sh").read_text(encoding="utf-8")

    assert 'beagle_artifact_lock_acquire "prepare-host-downloads" || lock_rc=$?' in script
    assert 'if [[ "$lock_rc" -eq 75 ]]; then' in script
    assert 'if ! beagle_artifact_lock_acquire "prepare-host-downloads"; then' not in script
    assert "Skipping duplicate prepare-host-downloads run" in script
