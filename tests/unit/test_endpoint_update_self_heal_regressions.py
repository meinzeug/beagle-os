from __future__ import annotations

import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "beagle-host" / "services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from update_feed import UpdateFeedService
from vm_http_surface import VmHttpSurfaceService


UPDATE_CLIENT = ROOT / "beagle-os" / "overlay" / "usr" / "local" / "sbin" / "beagle-update-client"
HEALTHCHECK = ROOT / "beagle-os" / "overlay" / "usr" / "local" / "sbin" / "beagle-healthcheck"
PREPARE_RUNTIME = ROOT / "thin-client-assistant" / "runtime" / "prepare-runtime.sh"
SYSTEMD_UNITS = [
    ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-update-scan.service",
    ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-update-boot-scan.service",
    ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-endpoint-report.service",
    ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-endpoint-dispatch.service",
    ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-healthcheck.service",
]
MAIN_JS = ROOT / "website" / "main.js"


def test_update_client_persists_state_and_cache_on_live_medium() -> None:
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert "ensure_persistent_update_paths()" in script
    assert 'persistent_state = state_dir / "update"' in script
    assert 'persistent_cache = state_dir / "update-cache"' in script
    assert "replace_with_symlink(STATE_ROOT, persistent_state)" in script
    assert "replace_with_symlink(CACHE_ROOT, persistent_cache)" in script


def test_update_client_preserves_live_usb_kernel_flags_when_rewriting_grub() -> None:
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert "preserved_runtime_kernel_args()" in script
    assert "pve_thin_client.network_tui=1" in script
    assert "pve_thin_client.live_usb=" in script
    assert "pve_thin_client.update_persistence=" in script
    assert "pve_thin_client.client_mode=desktop{extra_args}" in script


def test_installed_thinclient_ab_update_path_keeps_two_slots_and_pending_manifest() -> None:
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert 'slot_a = live_dir / "a"' in script
    assert 'slot_b = live_dir / "b"' in script
    assert 'atomic_symlink(current_slot, current_link)' in script
    assert 'target_slot = inactive_slot(current_slot)' in script
    assert 'write_pending_install_manifest(medium, manifest)' in script
    assert 'atomic_symlink(target_slot, medium / "live" / "current")' in script
    assert 'clear_pending_install_manifest(medium)' in script


def test_management_timers_run_after_prepare_network_and_health() -> None:
    prepare = PREPARE_RUNTIME.read_text(encoding="utf-8")

    assert prepare.index('run_optional_runtime_hook "/usr/local/sbin/beagle-egress-apply"') < prepare.index("ensure_beagle_management_units")
    for unit in SYSTEMD_UNITS:
        text = unit.read_text(encoding="utf-8")
        assert "pve-thin-client-prepare.service" in text
        assert "network-online.target" in text


def test_healthcheck_marks_update_status_for_repair_reporting() -> None:
    script = HEALTHCHECK.read_text(encoding="utf-8")

    assert "health_failure_reasons" in script
    assert "beagle-update-client mark-health-failed" in script
    assert "rollback_recommended" not in script  # owned by update-client status payload
    assert "moonlight target unreachable" in script
    assert "secure egress not ready" in script


def test_update_feed_can_require_reinstall_for_old_foundation() -> None:
    status_file = ROOT / "does-not-exist.json"
    service = UpdateFeedService(
        downloads_status_file=status_file,
        load_json_file=lambda _path, _default: {
            "version": "8.0",
            "endpoint_compatibility": {
                "minimum_self_update_version": "8.0",
                "foundation_generation": "2",
            },
        },
        update_payload_metadata=lambda version: {
            "version": version,
            "filename": f"pve-thin-client-usb-payload-v{version}.tar.gz",
            "payload_url": "https://srv1/beagle-downloads/payload.tar.gz",
            "payload_sha256": "abc",
            "sha256sums_url": "https://srv1/beagle-downloads/SHA256SUMS",
            "payload_pinned_pubkey": "",
        },
        public_update_sha256sums_url=lambda: "https://srv1/beagle-downloads/SHA256SUMS",
    )

    feed = service.build_update_feed({}, installed_version="7.9")

    assert feed["reinstall_required"] is True
    assert feed["rebuild_recommended"] is True
    assert feed["available"] is False
    assert feed["update_path"] == "reinstall_required"


class _Vm:
    vmid = 100
    node = "beagle-0"
    name = "vm-100"


def test_vm_update_payload_exposes_rebuild_and_health_failure(tmp_path: Path) -> None:
    vm = _Vm()
    surface = VmHttpSurfaceService(
        build_profile=lambda item: {"vmid": item.vmid, "update_enabled": True, "update_behavior": "auto"},
        build_novnc_access=lambda item: {},
        build_vm_state=lambda item: {"endpoint": {"reported_at": "now"}, "last_action": {}},
        build_vm_usb_state=lambda item, report: {},
        downloads_status_file=tmp_path / "downloads.json",
        ensure_vm_secret=lambda item: {},
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        list_support_bundle_metadata=lambda **kwargs: [],
        load_action_queue=lambda node, vmid: [],
        load_endpoint_report=lambda node, vmid: {"update": {"current_version": "7.9", "health_failure": True, "rollback_recommended": True}},
        load_installer_prep_state=lambda node, vmid: {},
        load_json_file=lambda path, default: {"version": "8.0", "endpoint_compatibility": {"minimum_self_update_version": "8.0"}},
        public_manager_url="https://srv1/beagle-api",
        public_server_name="srv1",
        render_vm_installer_script=lambda item: (b"", "installer.sh"),
        render_vm_live_usb_script=lambda item: (b"", "live.sh"),
        render_vm_windows_installer_script=lambda item: (b"", "installer.ps1"),
        render_vm_windows_live_usb_script=lambda item: (b"", "live.ps1"),
        service_name="beagle",
        summarize_endpoint_report=lambda report: {
            "reported_at": "now",
            "update_current_version": report["update"]["current_version"],
            "update_health_failure": report["update"]["health_failure"],
            "update_rollback_recommended": report["update"]["rollback_recommended"],
        },
        summarize_installer_prep_state=lambda item, state: {},
        usb_tunnel_ssh_user="beagle-usb",
        utcnow=lambda: "now",
        version="8.0",
    )

    response = surface.route_get("/api/v1/vms/100/update")

    update = response["payload"]["update"]
    assert update["compatibility"]["reinstall_required"] is True
    assert update["compatibility"]["rebuild_recommended"] is True
    assert update["endpoint"]["health_failure"] is True
    assert update["endpoint"]["rollback_recommended"] is True


def test_webui_update_panel_warns_when_endpoint_rebuild_is_recommended() -> None:
    script = MAIN_JS.read_text(encoding="utf-8")

    assert "Thinclient/Live-USB neu bauen empfohlen" in script
    assert "compatibility.rebuild_recommended" in script
    assert "Runtime-Health fehlgeschlagen" in script
