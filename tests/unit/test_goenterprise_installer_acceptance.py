from __future__ import annotations

import builtins
import importlib.util
from importlib.machinery import SourceFileLoader
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
GUI_PATH = (
    ROOT_DIR
    / "server-installer"
    / "live-build"
    / "config"
    / "includes.chroot"
    / "usr"
    / "local"
    / "bin"
    / "beagle-server-installer-gui"
)
INSTALLER_SCRIPT_PATH = (
    ROOT_DIR
    / "server-installer"
    / "live-build"
    / "config"
    / "includes.chroot"
    / "usr"
    / "local"
    / "bin"
    / "beagle-server-installer"
)
PXE_SCRIPT_PATH = ROOT_DIR / "scripts" / "setup-pxe-server.sh"


def _load_gui_module():
    loader = SourceFileLoader("beagle_server_installer_gui_acceptance", str(GUI_PATH))
    spec = importlib.util.spec_from_loader("beagle_server_installer_gui_acceptance", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_plain_installer_flow_covers_all_steps_with_validation(monkeypatch):
    gui = _load_gui_module()

    # Input sequence with deliberate invalid entries to exercise validation loops:
    # 1) Hostname: invalid -> valid
    # 2) Username: invalid -> valid
    # 3) Password: mismatch -> valid
    # 4) Disk selection: invalid index -> valid index
    # 5) Cluster-join: yes, then invalid target -> valid target
    answers = iter(
        [
            "Beagle Host", "beagle-host-01",  # hostname
            "Admin!", "beagle",               # username
            "secret-1", "secret-2", "secret-1", "secret-1",  # password + confirm
            "9", "1",                         # disk select
            "YES",                              # wipe confirmation
            "yes",                              # cluster join
            "   ", "10.10.0.15",              # cluster join target
        ]
    )

    monkeypatch.setattr(gui, "list_disks", lambda: [("/dev/sda", "512G", "NVMe SSD")])

    def _fake_input(_prompt: str = "") -> str:
        return next(answers)

    monkeypatch.setattr(builtins, "input", _fake_input)

    state = gui.plain_main()

    assert state["BEAGLE_SERVER_INSTALL_MODE"] == "standalone"
    assert state["BEAGLE_GUI_HOSTNAME"] == "beagle-host-01"
    assert state["BEAGLE_GUI_USERNAME"] == "beagle"
    assert state["BEAGLE_GUI_PASSWORD"] == "secret-1"
    assert state["BEAGLE_GUI_TARGET_DISK"] == "/dev/sda"
    assert state["BEAGLE_GUI_CLUSTER_JOIN"] == "yes"
    assert state["BEAGLE_GUI_CLUSTER_JOIN_TARGET"] == "10.10.0.15"


def test_seed_config_path_is_explicitly_non_interactive_in_installer_script():
    content = INSTALLER_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "seed_file=\"$(discover_seed_config || true)\"" in content
    assert "apply_seed_config \"$seed_file\"" in content
    assert "seed config active; skipping interactive installer UI" in content
    assert "elif [[ -x \"$gui_bin\"" in content


def test_pxe_script_renders_seed_url_into_dhcp_and_boot_entries():
    content = PXE_SCRIPT_PATH.read_text(encoding="utf-8")

    assert "PXE_SEED_URL" in content
    assert "beagle.seed_url=${PXE_SEED_URL}" in content
    assert "dhcp-range=$PXE_DHCP_RANGE" in content
    assert "seed_url=$PXE_SEED_URL" in content