from __future__ import annotations

import sys
from pathlib import Path

SERVICES_DIR = Path(__file__).resolve().parents[2] / "beagle-host" / "services"
if str(SERVICES_DIR) not in sys.path:
    sys.path.insert(0, str(SERVICES_DIR))

from vm_profile import VmProfileService


class _Vm:
    vmid = 100
    node = "beagle-0"
    name = "vm-100"
    status = "running"
    tags = "beagle"


def _service(config: dict) -> VmProfileService:
    return VmProfileService(
        allocate_public_stream_base_port=lambda node, vmid: None,
        current_public_stream_host=lambda: "",
        expand_software_packages=lambda presets, extras: list(presets) + list(extras),
        find_vm=lambda vmid: _Vm() if int(vmid) == 100 else None,
        first_guest_ipv4=lambda vmid: "",
        get_vm_config=lambda node, vmid: dict(config),
        list_policies=lambda: [],
        listify=lambda value: [item.strip() for item in str(value or "").replace(",", " ").split() if item.strip()],
        load_vm_secret=lambda node, vmid: {},
        manager_pinned_pubkey="",
        normalize_endpoint_profile_contract=lambda profile, **payload: {**profile, **payload},
        parse_description_meta=lambda text: {},
        public_installer_iso_url=lambda: "https://srv1/beagle-os-installer.iso",
        public_manager_url="https://srv1/beagle-api",
        resolve_public_stream_host=lambda host: host,
        resolve_ubuntu_beagle_desktop=lambda desktop: {"id": desktop or "default"},
        safe_hostname=lambda name, vmid: f"vm-{vmid}",
        stream_ports=lambda base: {},
        truthy=lambda value, default=False: str(value or "").strip().lower() in {"1", "true", "yes", "on"} if str(value or "").strip() else default,
        ubuntu_beagle_default_desktop="plasma",
        ubuntu_beagle_default_guest_user="beagle",
        ubuntu_beagle_default_keymap="de",
        ubuntu_beagle_default_locale="de_DE.UTF-8",
        ubuntu_beagle_software_presets={},
    )


def test_build_profile_reads_top_level_update_policy_overrides() -> None:
    profile = _service({
        "name": "vm-100",
        "beagle-update-enabled-override": "1",
        "beagle-update-channel-override": "rolling",
        "beagle-update-behavior-override": "auto",
    }).build_profile(_Vm())

    assert profile["update_enabled"] is True
    assert profile["update_channel"] == "rolling"
    assert profile["update_behavior"] == "auto"


def test_build_profile_reads_legacy_underscored_update_policy_overrides() -> None:
    profile = _service({
        "name": "vm-100",
        "beagle_update_enabled_override": "0",
        "beagle_update_channel_override": "rolling",
        "beagle_update_behavior_override": "off",
    }).build_profile(_Vm())

    assert profile["update_enabled"] is False
    assert profile["update_channel"] == "rolling"
    assert profile["update_behavior"] == "off"