from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
LIVE_MENU_SCRIPT = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-live-menu.sh"
LOCAL_INSTALLER_SCRIPT = ROOT / "thin-client-assistant" / "usb" / "pve-thin-client-local-installer.sh"


def test_bundled_preset_install_requires_explicit_target_disk_selection() -> None:
    script = LIVE_MENU_SCRIPT.read_text(encoding="utf-8")

    assert "starting preset-based install with explicit target-disk selection" in script
    assert 'run_installer_as_root --target-disk "$target_disk" --auto-install' in script
    assert '--target-disk "$target_disk" --yes --auto-install' not in script


def test_list_targets_json_excludes_read_only_and_mmc_boot_pseudo_devices() -> None:
    script = LOCAL_INSTALLER_SCRIPT.read_text(encoding="utf-8")

    assert '"NAME,SIZE,MODEL,TYPE,RM,RO,TRAN"' in script
    assert 're.match(r"^/dev/mmcblk\\d+(boot\\d+|rpmb)$", device)' in script
    assert 'if str(entry.get("RO", "0")) == "1":' in script
    assert '"read_only": entry.get("RO", "0")' in script
