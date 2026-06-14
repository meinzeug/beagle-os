from __future__ import annotations

import importlib.machinery
import importlib.util
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SERVICES = ROOT / "beagle-host" / "services"
if str(SERVICES) not in sys.path:
    sys.path.insert(0, str(SERVICES))

from update_feed import UpdateFeedService
from vm_http_surface import VmHttpSurfaceService


UPDATE_CLIENT = ROOT / "beagle-os" / "overlay" / "usr" / "local" / "sbin" / "beagle-update-client"
GUEST_UPDATER = ROOT / "beagle-host" / "bin" / "beagle-guest-updater"
UBUNTU_FIRSTBOOT = ROOT / "beagle-host" / "templates" / "ubuntu-beagle" / "firstboot-provision.sh.tpl"
HEALTHCHECK = ROOT / "beagle-os" / "overlay" / "usr" / "local" / "sbin" / "beagle-healthcheck"
ENDPOINT_DISPATCH = ROOT / "beagle-os" / "overlay" / "usr" / "local" / "sbin" / "beagle-endpoint-dispatch"
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


def test_update_client_prevents_parallel_update_commands_and_stalled_downloads() -> None:
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert "LOCK_FILE = Path(\"/run/beagle-os/update-client.lock\")" in script
    assert "def acquire_command_lock(command: str)" in script
    assert "another update command is running" in script
    assert "PAYLOAD_DOWNLOAD_MAX_TIME_SECONDS" in script
    assert "--speed-limit" in script
    assert "--speed-time" in script
    assert "payload download timed out or stalled" in script


def test_update_client_preserves_live_usb_kernel_flags_when_rewriting_grub() -> None:
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert "preserved_runtime_kernel_args()" in script
    assert "pve_thin_client.network_tui=1" in script
    assert "pve_thin_client.live_usb=" in script
    assert "pve_thin_client.update_persistence=" in script
    assert "pve_thin_client.mode=runtime{extra_args}" in script


def _load_update_client_module():
    loader = importlib.machinery.SourceFileLoader("beagle_update_client_test", str(UPDATE_CLIENT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def _load_guest_updater_module():
    loader = importlib.machinery.SourceFileLoader("beagle_guest_updater_test", str(GUEST_UPDATER))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


def test_update_client_resolves_live_media_uuid_from_cmdline_when_root_is_tmpfs(monkeypatch) -> None:
    module = _load_update_client_module()

    def fake_check_output(args, **_kwargs):
        if args[:3] == ["findmnt", "-nro", "SOURCE"]:
            return "tmpfs\n"
        raise AssertionError(f"unexpected command: {args}")

    original_read_text = module.Path.read_text

    def fake_read_text(path, *args, **kwargs):
        if str(path) == "/proc/cmdline":
            return "boot=live live-media=/dev/disk/by-uuid/8051f327-e67d-4ee2-9339-9ab140f0348d live-media-path=/live/current toram"
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(module.subprocess, "check_output", fake_check_output)
    monkeypatch.setattr(module.Path, "read_text", fake_read_text)

    assert module.root_uuid_for_medium(Path("/run/live/medium")) == "8051f327-e67d-4ee2-9339-9ab140f0348d"


def test_update_client_ignores_unknown_manifest_version_for_build_info_fallback(monkeypatch) -> None:
    module = _load_update_client_module()

    monkeypatch.setattr(module, "read_install_manifest", lambda _medium: {"project_version": "unknown"})
    monkeypatch.setattr(module, "read_env_file", lambda _path: {"PROJECT_VERSION": "8.3.1"})

    assert module.current_version({}, Path("/run/live/medium")) == "8.3.1"


def test_update_client_load_config_applies_runtime_update_env_overrides(tmp_path: Path, monkeypatch) -> None:
    module = _load_update_client_module()

    config_dir = tmp_path / "config"
    config_dir.mkdir(parents=True, exist_ok=True)
    (config_dir / "thinclient.conf").write_text(
        "\n".join(
            [
                "PVE_THIN_CLIENT_BEAGLE_UPDATE_ENABLED='1'",
                "PVE_THIN_CLIENT_BEAGLE_UPDATE_CHANNEL='stable'",
                "PVE_THIN_CLIENT_BEAGLE_UPDATE_BEHAVIOR='prompt'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    runtime_env = tmp_path / "state" / "device-updates.env"
    runtime_env.parent.mkdir(parents=True, exist_ok=True)
    runtime_env.write_text(
        "\n".join(
            [
                "export PVE_THIN_CLIENT_BEAGLE_UPDATE_ENABLED='0'",
                "export PVE_THIN_CLIENT_BEAGLE_UPDATE_CHANNEL='rolling'",
                "export PVE_THIN_CLIENT_BEAGLE_UPDATE_BEHAVIOR='auto'",
                "export PVE_THIN_CLIENT_BEAGLE_UPDATE_VERSION_PIN='8.4.0'",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(module, "CONFIG_DIR_CANDIDATES", [config_dir])
    monkeypatch.setattr(module, "DEVICE_UPDATE_ENV_CANDIDATES", [runtime_env])

    _, config = module.load_config()

    assert config["PVE_THIN_CLIENT_BEAGLE_UPDATE_ENABLED"] == "0"
    assert config["PVE_THIN_CLIENT_BEAGLE_UPDATE_CHANNEL"] == "rolling"
    assert config["PVE_THIN_CLIENT_BEAGLE_UPDATE_BEHAVIOR"] == "auto"
    assert config["PVE_THIN_CLIENT_BEAGLE_UPDATE_VERSION_PIN"] == "8.4.0"


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
        assert "beagle-thin-client-prepare.service" in text
        assert "network-online.target" in text
        for line in text.splitlines():
            if line.startswith("Wants="):
                assert "beagle-thin-client-prepare.service" not in line

    scan_service = (ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-update-scan.service").read_text(encoding="utf-8")
    boot_scan_service = (ROOT / "beagle-os" / "overlay" / "etc" / "systemd" / "system" / "beagle-update-boot-scan.service").read_text(encoding="utf-8")
    assert "TimeoutStartSec=20min" in scan_service
    assert "TimeoutStartSec=20min" in boot_scan_service


def test_healthcheck_marks_update_status_for_repair_reporting() -> None:
    script = HEALTHCHECK.read_text(encoding="utf-8")

    assert "health_failure_reasons" in script
    assert "beagle-update-client mark-health-failed" in script
    assert "beagle-update-client clear-health-failed" in script
    assert "rollback_recommended" not in script  # owned by update-client status payload
    assert "beagle-stream-client target unreachable" in script
    assert "secure egress not ready" in script


def test_healthcheck_probes_broker_allocation_without_logging_tokens() -> None:
    script = HEALTHCHECK.read_text(encoding="utf-8")

    assert "broker_allocation_reachable" in script
    assert "/api/v1/streams/allocate" in script
    assert '"pool_id": conf.get("pool_id", "")' in script
    assert '"device_id": conf.get("device_id", "")' in script
    assert '-H "X-Beagle-Token: ${enrollment_token}"' in script
    assert "socket.create_connection((host, port), timeout=3)" in script
    assert "beagle_stream_client_target_reachable=\"1\"" in script
    assert '"$broker_allocation_reachable" != "1"' in script
    assert "echo ${enrollment_token}" not in script
    assert "logger ${enrollment_token}" not in script


def test_update_client_can_clear_health_failure_state() -> None:
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert "def clear_health_failure() -> dict:" in script
    assert 'subparsers.add_parser("clear-health-failed")' in script
    assert 'elif args.command == "clear-health-failed":' in script
    assert "health_failure=False" in script
    assert "rollback_recommended=False" in script
    assert 'state="current"' in script


def test_desktop_guest_updater_prompts_before_required_reboot() -> None:
    script = GUEST_UPDATER.read_text(encoding="utf-8")
    firstboot = UBUNTU_FIRSTBOOT.read_text(encoding="utf-8")

    assert "Beagle OS Update abgeschlossen" in script
    assert "Jetzt neu starten" in script
    assert "Spaeter manuell neu starten" in script
    assert "prompt_reboot_on_desktop(config)" in script
    assert "Authorization: Bearer" in script
    assert "url.split('?', 1)[0]" in script
    assert '["apt-get", "upgrade", "-y", "--with-new-pkgs"]' in script
    assert "dist-upgrade" not in script
    assert "zenity" in firstboot
    assert "beagle-guest-updater-actions.timer" in firstboot
    assert "beagle-guest-updater scan --auto-apply-if-idle" in firstboot
    assert "desktop_profile_available" in script
    assert "desktop-profile-refresh" in script
    assert "beagle-desktop-profile-refresh" in firstboot


def test_desktop_guest_updater_reports_desktop_profile_drift_as_available(tmp_path: Path, monkeypatch) -> None:
    module = _load_guest_updater_module()

    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    monkeypatch.setattr(module, "STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(module, "VERSION_FILE", tmp_path / "version")
    monkeypatch.setattr(
        module,
        "update_feed",
        lambda _config: {
            "available": False,
            "latest_version": "",
            "behavior": "prompt",
            "channel": "stable",
            "self_update_supported": False,
        },
    )
    monkeypatch.setattr(
        module,
        "desktop_profile_status",
        lambda: {
            "current": False,
            "available": True,
            "profile_version": "2026-06-14-cyberpunk-standard-apps-v2",
        },
    )
    monkeypatch.setattr(module, "check_in", lambda _config: {})

    status = module.scan({})

    assert status["available"] is True
    assert status["desktop_profile_available"] is True
    assert status["self_update_supported"] is True
    assert status["update_path"] == "desktop_profile_refresh"


def test_desktop_guest_updater_apply_refreshes_profile_without_os_version_change(tmp_path: Path, monkeypatch) -> None:
    module = _load_guest_updater_module()

    monkeypatch.setattr(module, "STATE_DIR", tmp_path)
    monkeypatch.setattr(module, "STATUS_FILE", tmp_path / "status.json")
    monkeypatch.setattr(module, "VERSION_FILE", tmp_path / "version")
    monkeypatch.setattr(module, "check_in", lambda _config: {})
    monkeypatch.setattr(module, "run_apt_upgrade", lambda: (_ for _ in ()).throw(AssertionError("apt upgrade should not run")))
    statuses = [
        {"current": False, "available": True, "profile_version": "2026-06-14-cyberpunk-standard-apps-v2"},
        {"current": True, "available": False, "profile_version": "2026-06-14-cyberpunk-standard-apps-v2"},
    ]
    monkeypatch.setattr(module, "desktop_profile_status", lambda: statuses.pop(0) if statuses else statuses[-1])
    refresh_calls: list[bool] = []
    monkeypatch.setattr(module, "apply_desktop_profile_refresh", lambda *, force=False: refresh_calls.append(bool(force)) or {"changed": True})

    status = module.apply_update({}, feed={"available": False, "latest_version": "", "self_update_supported": False})

    assert refresh_calls == [True]
    assert status["state"] == "current"
    assert status["desktop_profile_available"] is False


def test_desktop_guest_updater_supports_manual_desktop_profile_refresh_action(monkeypatch) -> None:
    module = _load_guest_updater_module()

    calls: list[tuple[bool, str]] = []
    monkeypatch.setattr(module, "apply_desktop_profile_refresh", lambda *, force=False: {"changed": force})
    monkeypatch.setattr(module, "desktop_profile_status", lambda: {"current": True, "available": False})
    monkeypatch.setattr(module, "status_payload", lambda _config, **updates: updates)
    monkeypatch.setattr(module, "check_in", lambda _config: {})
    monkeypatch.setattr(
        module,
        "post_action_result",
        lambda _config, _action, ok, message, _status=None: calls.append((bool(ok), str(message))),
    )

    module.handle_action({}, {"action": "desktop-profile-refresh", "action_id": "refresh-1", "params": {"force": True}})

    assert calls == [(True, "desktop profile refreshed")]


def test_desktop_guest_updater_supports_launcher_reboot_shutdown_actions(monkeypatch) -> None:
    module = _load_guest_updater_module()

    calls: list[tuple[str, bool, str]] = []
    reboot_scheduled: list[bool] = []
    shutdown_scheduled: list[bool] = []

    monkeypatch.setattr(module, "post_action_result", lambda _config, action, ok, message, _status=None: calls.append((str(action.get("action", "")), bool(ok), str(message))))
    monkeypatch.setattr(module, "restart_desktop_launcher", lambda: True)
    monkeypatch.setattr(module, "schedule_reboot", lambda: reboot_scheduled.append(True))
    monkeypatch.setattr(module, "schedule_shutdown", lambda: shutdown_scheduled.append(True))

    config: dict[str, str] = {}
    module.handle_action(config, {"action": "restart-session", "action_id": "a-1"})
    module.handle_action(config, {"action": "reboot", "action_id": "a-2"})
    module.handle_action(config, {"action": "shutdown", "action_id": "a-3"})

    assert [item[0] for item in calls] == ["restart-session", "reboot", "shutdown"]
    assert all(item[1] is True for item in calls)
    assert reboot_scheduled == [True]
    assert shutdown_scheduled == [True]


def test_desktop_guest_updater_exposes_direct_vm_power_cli() -> None:
    script = GUEST_UPDATER.read_text(encoding="utf-8")
    firstboot = UBUNTU_FIRSTBOOT.read_text(encoding="utf-8")

    assert 'subparsers.add_parser("reboot")' in script
    assert 'subparsers.add_parser("shutdown")' in script
    assert 'reboot_target="vm"' in script
    assert "beagle-guest-updater reboot" in firstboot
    assert "beagle-guest-updater shutdown" in firstboot


def test_endpoint_dispatch_supports_launcher_reboot_shutdown_with_fallback_services() -> None:
    script = ENDPOINT_DISPATCH.read_text(encoding="utf-8")

    assert "restart_launcher_session()" in script
    assert "beagle-kiosk.service" in script
    assert "beagle-autologin.service" in script
    assert "pve-thin-client-autologin.service" in script
    assert "display-manager.service" in script
    assert "restart-session|restart-launcher" in script
    assert "restart-runtime|restart-thin-client" in script
    assert "reboot|reboot-thin-client" in script
    assert "shutdown|shutdown-thin-client" in script


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


def test_update_feed_prefers_server_profile_channel_over_endpoint_query() -> None:
    service = UpdateFeedService(
        downloads_status_file=ROOT / "does-not-exist.json",
        load_json_file=lambda _path, _default: {"version": "8.3.3"},
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

    feed = service.build_update_feed(
        {"update_channel": "rolling", "update_behavior": "auto", "update_enabled": True},
        installed_version="8.3.1",
        channel="stable",
    )

    assert feed["channel"] == "rolling"
    assert feed["behavior"] == "auto"
    assert feed["latest_version"] == "8.3.3"
    assert feed["available"] is True


def test_update_feed_marks_ubuntu_desktops_as_migration_required() -> None:
    service = UpdateFeedService(
        downloads_status_file=ROOT / "does-not-exist.json",
        load_json_file=lambda _path, _default: {"version": "8.3.3"},
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

    feed = service.build_update_feed(
        {"beagle_role": "desktop", "os_family": "ubuntu", "update_channel": "rolling"},
        installed_version="8.3.1",
    )

    assert feed["channel"] == "rolling"
    assert feed["update_path"] == "migration_required"
    assert feed["self_update_supported"] is False
    assert feed["available"] is False
    assert "ubuntu desktop" in feed["migration_reasons"][0]


def test_update_feed_allows_ubuntu_desktop_guest_updater_client() -> None:
    service = UpdateFeedService(
        downloads_status_file=ROOT / "does-not-exist.json",
        load_json_file=lambda _path, _default: {"version": "8.3.3"},
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

    feed = service.build_update_feed(
        {"beagle_role": "desktop", "os_family": "ubuntu", "update_channel": "rolling"},
        installed_version="8.3.1",
        client_type="desktop-guest-updater",
    )

    assert feed["channel"] == "rolling"
    assert feed["update_path"] == "self_update"
    assert feed["self_update_supported"] is True
    assert feed["available"] is True
    assert feed["client_type"] == "desktop-guest-updater"


class _Vm:
    vmid = 100
    node = "beagle-0"
    name = "vm-100"


def test_vm_update_payload_allows_reported_desktop_guest_updater(tmp_path: Path) -> None:
    vm = _Vm()
    surface = VmHttpSurfaceService(
        build_profile=lambda item: {
            "vmid": item.vmid,
            "beagle_role": "desktop",
            "os_family": "ubuntu",
            "update_enabled": True,
            "update_channel": "rolling",
            "update_behavior": "auto",
        },
        build_novnc_access=lambda item: {},
        build_vm_state=lambda item: {"endpoint": {"reported_at": "now"}, "last_action": {}},
        build_vm_usb_state=lambda item, report: {},
        downloads_status_file=tmp_path / "downloads.json",
        ensure_vm_secret=lambda item: {},
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        list_support_bundle_metadata=lambda **kwargs: [],
        load_action_queue=lambda node, vmid: [],
        load_endpoint_report=lambda node, vmid: {
            "update": {
                "client": "desktop-guest-updater",
                "client_version": "1",
                "current_version": "8.3.1",
                "latest_version": "8.3.3",
                "available": True,
                "state": "available",
            }
        },
        load_installer_prep_state=lambda node, vmid: {},
        load_json_file=lambda path, default: {"version": "8.3.3", "endpoint_compatibility": {"minimum_self_update_version": "8.0"}},
        public_manager_url="https://srv1/beagle-api",
        public_server_name="srv1",
        render_vm_installer_script=lambda item: (b"", "installer.sh"),
        render_vm_live_usb_script=lambda item: (b"", "live.sh"),
        render_vm_windows_installer_script=lambda item: (b"", "installer.ps1"),
        render_vm_windows_live_usb_script=lambda item: (b"", "live.ps1"),
        service_name="beagle",
        summarize_endpoint_report=lambda report: {
            "reported_at": "now",
            "update_client": report["update"]["client"],
            "update_client_version": report["update"]["client_version"],
            "update_current_version": report["update"]["current_version"],
            "update_latest_version": report["update"]["latest_version"],
            "update_available": report["update"]["available"],
            "update_state": report["update"]["state"],
        },
        summarize_installer_prep_state=lambda item, state: {},
        usb_tunnel_ssh_user="beagle-usb",
        utcnow=lambda: "now",
        version="8.3.3",
    )

    update = surface.route_get("/api/v1/vms/100/update")["payload"]["update"]

    assert update["endpoint"]["client"] == "desktop-guest-updater"
    assert update["compatibility"]["update_path"] == "self_update"
    assert update["compatibility"]["self_update_supported"] is True
    assert update["compatibility"]["migration_required"] is False


def test_vm_update_payload_exposes_rebuild_and_health_failure(tmp_path: Path, monkeypatch) -> None:
    vm = _Vm()
    downloads_file = tmp_path / "downloads.json"
    repo_status_file = tmp_path / "repo-auto-update-status.json"

    def load_update_json(path: Path, default):
        if Path(path) == repo_status_file:
            return {
                "repo_url": "https://github.com/meinzeug/beagle-os.git",
                "branch": "main",
                "state": "healthy",
                "current_commit": "1111111111111111111111111111111111111111",
                "target_commit": "1111111111111111111111111111111111111111",
                "channel_position": "behind_target",
                "stable_ref": "v8.0.0",
                "stable_version": "8.0.0",
                "stable_commit": "3333333333333333333333333333333333333333",
                "rolling_commit": "4444444444444444444444444444444444444444",
                "rolling_version": "8.0.1",
            }
        return {
            "version": "8.0",
            "generated_at": "2026-05-27T12:00:00Z",
            "payload_filename": "pve-thin-client-usb-payload-v8.0.tar.gz",
            "payload_url": "https://srv1/beagle-downloads/payload.tar.gz",
            "payload_sha256": "abc123",
            "payload_size": 1024,
            "sha256sums_url": "https://srv1/beagle-downloads/SHA256SUMS",
            "status_url": "https://srv1/beagle-downloads/beagle-downloads-status.json",
            "endpoint_compatibility": {"minimum_self_update_version": "8.0"},
        }

    import vm_http_surface

    monkeypatch.setattr(vm_http_surface, "REPO_AUTO_UPDATE_STATUS_FILE", repo_status_file)
    surface = VmHttpSurfaceService(
        build_profile=lambda item: {"vmid": item.vmid, "update_enabled": True, "update_behavior": "auto"},
        build_novnc_access=lambda item: {},
        build_vm_state=lambda item: {"endpoint": {"reported_at": "now"}, "last_action": {}},
        build_vm_usb_state=lambda item, report: {},
        downloads_status_file=downloads_file,
        ensure_vm_secret=lambda item: {},
        find_vm=lambda vmid: vm if int(vmid) == vm.vmid else None,
        list_support_bundle_metadata=lambda **kwargs: [],
        load_action_queue=lambda node, vmid: [],
        load_endpoint_report=lambda node, vmid: {"update": {"current_version": "7.9", "health_failure": True, "rollback_recommended": True}},
        load_installer_prep_state=lambda node, vmid: {},
        load_json_file=load_update_json,
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
    assert update["source"]["repo_url"] == "https://github.com/meinzeug/beagle-os.git"
    assert update["source"]["payload_filename"] == "pve-thin-client-usb-payload-v8.0.tar.gz"
    assert update["source"]["stable_ref"] == "v8.0.0"
    assert update["source"]["channel_position"] == "at_target"


def test_webui_update_panel_warns_when_endpoint_rebuild_is_recommended() -> None:
    script = MAIN_JS.read_text(encoding="utf-8")

    assert "Thinclient/Live-USB neu bauen empfohlen" in script
    assert "compatibility.rebuild_recommended" in script
    assert "Runtime-Health fehlgeschlagen" in script
    assert "GitHub / Release Quelle" in script
    assert "Stable Release" in script
    assert "Rolling Head" in script


def test_update_client_refuses_payload_download_into_ram_backed_cache() -> None:
    """The Live thin client froze when a USB-full fallback wrote the update
    payload into the tmpfs overlay (RAM). The client must defer instead."""
    script = UPDATE_CLIENT.read_text(encoding="utf-8")

    assert "def guard_volatile_download(" in script
    assert "def path_is_ram_backed(" in script
    assert "def mem_available_bytes(" in script
    assert "max_filesize = guard_volatile_download(payload_size)" in script
    assert "--max-filesize" in script
    # extraction must also avoid the RAM-backed /tmp tmpfs
    assert "extract_root = archive_path.parent" in script


def test_guard_volatile_download_defers_on_ram_backed_cache() -> None:
    module = _load_update_client_module()
    module.CACHE_ROOT = Path("/run/live/overlay/rw/var/cache/beagle-os/update")

    # RAM-backed + not explicitly allowed -> defer regardless of (unknown) size
    module.path_is_ram_backed = lambda path, _depth=0: True
    import os as _os
    _os.environ.pop("BEAGLE_UPDATE_ALLOW_VOLATILE_CACHE", None)
    raised = False
    try:
        module.guard_volatile_download(0)
    except RuntimeError as exc:
        raised = "volatile" in str(exc).lower()
    assert raised, "must defer when cache is RAM-backed"

    # explicitly allowed + ample RAM -> returns a positive --max-filesize budget
    _os.environ["BEAGLE_UPDATE_ALLOW_VOLATILE_CACHE"] = "1"
    module.mem_available_bytes = lambda: 3 * 1024 ** 3
    budget = module.guard_volatile_download(0)
    assert isinstance(budget, int) and budget > 0

    # allowed but payload larger than the safe RAM budget -> defer
    try:
        module.guard_volatile_download(3 * 1024 ** 3)
        assert False, "oversized payload must defer"
    except RuntimeError:
        pass

    # allowed but too little RAM -> defer
    module.mem_available_bytes = lambda: 400 * 1024 ** 2
    try:
        module.guard_volatile_download(0)
        assert False, "low RAM must defer"
    except RuntimeError:
        pass

    _os.environ.pop("BEAGLE_UPDATE_ALLOW_VOLATILE_CACHE", None)


def test_guard_volatile_download_allows_non_volatile_cache() -> None:
    module = _load_update_client_module()
    module.path_is_ram_backed = lambda path, _depth=0: False
    # persistent USB medium / real disk -> no RAM cap, download proceeds
    assert module.guard_volatile_download(0) == 0
    assert module.guard_volatile_download(900 * 1024 ** 2) == 0
