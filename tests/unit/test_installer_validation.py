from __future__ import annotations

import importlib.util
from pathlib import Path
from importlib.machinery import SourceFileLoader


ROOT_DIR = Path(__file__).resolve().parents[2]
GUI_PATH = ROOT_DIR / "server-installer" / "live-build" / "config" / "includes.chroot" / "usr" / "local" / "bin" / "beagle-server-installer-gui"


def _load_gui_module():
    loader = SourceFileLoader("beagle_server_installer_gui", str(GUI_PATH))
    spec = importlib.util.spec_from_loader("beagle_server_installer_gui", loader)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_validate_hostname_accepts_valid_host():
    gui = _load_gui_module()
    ok, message = gui.validate_hostname("beagle-rack-01")
    assert ok is True
    assert message == ""


def test_validate_hostname_rejects_invalid_host():
    gui = _load_gui_module()
    ok, message = gui.validate_hostname("Beagle Rack 01")
    assert ok is False
    assert "lowercase" in message


def test_validate_username_rejects_invalid_chars():
    gui = _load_gui_module()
    ok, message = gui.validate_username("Admin!")
    assert ok is False
    assert "lowercase" in message


def test_validate_cluster_join_target_requires_value():
    gui = _load_gui_module()
    ok, message = gui.validate_cluster_join_target("   ")
    assert ok is False
    assert "darf nicht leer" in message
