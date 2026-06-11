from __future__ import annotations

import json
import tempfile
from importlib.machinery import SourceFileLoader
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[2]
NETBRIDGE_DIR = ROOT / "beagle-host" / "netbridge"
AGENT = NETBRIDGE_DIR / "beagle-netbridge-agent"
CLIENT = NETBRIDGE_DIR / "beagle-netbridge-client"
TRAY = NETBRIDGE_DIR / "beagle-netbridge-tray"
TRAY_DESKTOP = NETBRIDGE_DIR / "beagle-netbridge-tray.desktop"
AGENT_UNIT = NETBRIDGE_DIR / "beagle-netbridge-agent.service"
CLIENT_UNIT = NETBRIDGE_DIR / "beagle-netbridge-client.service"
FIRSTBOOT_TEMPLATE = ROOT / "beagle-host" / "templates" / "ubuntu-beagle" / "firstboot-provision.sh.tpl"
TC_AGENT = (
    ROOT
    / "thin-client-assistant"
    / "live-build"
    / "config"
    / "includes.chroot"
    / "usr"
    / "local"
    / "bin"
    / "beagle-netbridge-agent"
)
TC_AGENT_UNIT = (
    ROOT
    / "thin-client-assistant"
    / "live-build"
    / "config"
    / "includes.chroot"
    / "etc"
    / "systemd"
    / "system"
    / "beagle-netbridge-agent.service"
)
TC_ENABLE_HOOK = (
    ROOT
    / "thin-client-assistant"
    / "live-build"
    / "config"
    / "hooks"
    / "live"
    / "010-enable-services.hook.chroot"
)


def test_netbridge_assets_exist() -> None:
    for path in (AGENT, CLIENT, AGENT_UNIT, CLIENT_UNIT):
        assert path.is_file(), f"missing {path}"


def test_agent_discovers_printer_services_and_serves_catalog() -> None:
    script = AGENT.read_text(encoding="utf-8")

    # Printer service types we bridge.
    for service in ("_ipp._tcp.local.", "_ipps._tcp.local.",
                    "_pdl-datastream._tcp.local.", "_printer._tcp.local."):
        assert service in script

    # DNS record parsing must carry absolute offsets so compressed PTR/SRV
    # target names resolve correctly.
    assert "for name, rtype, rdata, rdata_offset in _parse_records(data):" in script
    assert "_read_name(data, rdata_offset)" in script
    assert "_read_name(data, rdata_offset + 6)" in script

    # Catalog control port and proxy behaviour.
    assert "CONTROL_PORT = int(os.environ.get(\"BEAGLE_NETBRIDGE_CONTROL_PORT\", \"47100\"))" in script
    assert "def serve_catalog(self)" in script
    assert "def detect_bind_host()" in script
    assert "10.88." in script  # binds to the WireGuard mesh address


def test_client_wires_printers_into_cups_over_tunnel() -> None:
    script = CLIENT.read_text(encoding="utf-8")

    assert 'DEFAULT_AGENTS = "10.88.1.1:47100"' in script
    assert 'MANAGED_PREFIX = "beagle-net-"' in script
    # Prefer driverless IPP Everywhere, fall back to a raw JetDirect socket.
    assert '"-m", "everywhere"' in script
    assert 'f"socket://{agent_host}:{raw[\'proxy_port\']}"' in script
    assert "def reconcile_printers(" in script
    assert "def remove_stale_queues(" in script


def test_firstboot_installs_netbridge_client_by_default() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")

    assert "install_beagle_netbridge_client() {" in script
    # Called in the main provisioning flow alongside the other bridges.
    assert "install_thinclient_microphone_bridge\n  install_beagle_netbridge_client" in script
    # CUPS tooling is pulled in so lpadmin/lpstat exist.
    assert "cups cups-client cups-ipp-utils" in script
    # Default agent endpoint config is written.
    assert "BEAGLE_NETBRIDGE_AGENTS=10.88.1.1:47100" in script
    assert "/usr/local/bin/beagle-netbridge-client" in script
    assert "systemctl enable --now beagle-netbridge-client.service" in script


def test_thin_client_image_ships_and_enables_agent() -> None:
    assert TC_AGENT.is_file()
    assert TC_AGENT_UNIT.is_file()
    hook = TC_ENABLE_HOOK.read_text(encoding="utf-8")
    assert "enable_if_present beagle-netbridge-agent.service" in hook


def _load(path: Path, name: str) -> ModuleType:
    # The scripts have no .py suffix; load them explicitly for functional tests.
    return SourceFileLoader(name, str(path)).load_module()


def test_agent_control_protocol_supports_manage_ops() -> None:
    script = AGENT.read_text(encoding="utf-8")

    # The control port understands the manager verbs in addition to "catalog".
    for op in ("rescan", "add_static", "remove_static", "list_static"):
        assert f'op == "{op}"' in script
    assert "def _dispatch(self, request: dict)" in script
    # Manual devices are persisted so they survive an agent restart.
    assert "static-devices.json" in script
    assert "def _load_static_devices(self)" in script
    assert "def _save_static_devices(self)" in script
    # The manual flag must survive reconcile so the manager can offer removal.
    assert '"manual": bool(device.get("manual", False))' in script
    # On-demand rescans wake the discovery loop instead of waiting the interval.
    assert "self._rescan = threading.Event()" in script
    assert "self._rescan.wait(DISCOVERY_INTERVAL)" in script


def test_agent_validates_manual_device_input() -> None:
    agent = _load(AGENT, "beagle_netbridge_agent")

    good = agent.Agent._make_static_device(
        {"address": "192.168.50.20", "port": 9100, "name": "Test"})
    assert good is not None
    assert good["manual"] is True
    assert good["id"] == "static-192-168-50-20-9100"
    assert good["services"] == {"raw": {"device_port": 9100}}

    ipp = agent.Agent._make_static_device(
        {"address": "printer.local", "port": 631, "rp": "/ipp/print"})
    assert ipp is not None
    assert ipp["services"]["ipp"]["rp"] == "ipp/print"

    # Reject hostile / malformed input (command-injection style addresses, bad ports).
    assert agent.Agent._make_static_device({"address": "bad addr; rm -rf /"}) is None
    assert agent.Agent._make_static_device({"address": ""}) is None
    assert agent.Agent._make_static_device({"address": "1.2.3.4", "port": 0}) is None
    assert agent.Agent._make_static_device({"address": "1.2.3.4", "port": 70000}) is None


def test_agent_persists_static_devices_round_trip() -> None:
    agent = _load(AGENT, "beagle_netbridge_agent_persist")
    with tempfile.TemporaryDirectory() as tmp:
        agent.STATE_DIR = tmp
        agent.STATIC_FILE = str(Path(tmp) / "static-devices.json")
        inst = agent.Agent.__new__(agent.Agent)
        import threading
        inst.lock = threading.Lock()
        inst.static_devices = [agent.Agent._make_static_device(
            {"address": "10.0.0.9", "port": 9100, "name": "Saved"})]
        inst._save_static_devices()
        restored = inst._load_static_devices()
    assert len(restored) == 1
    assert restored[0]["address"] == "10.0.0.9"
    assert restored[0]["manual"] is True


def test_tray_assets_exist_and_compile() -> None:
    assert TRAY.is_file()
    assert TRAY_DESKTOP.is_file()
    import py_compile
    py_compile.compile(str(TRAY), doraise=True)


def test_tray_control_client_and_queue_naming() -> None:
    tray = _load(TRAY, "beagle_netbridge_tray")
    client = _load(CLIENT, "beagle_netbridge_client")

    device = {"name": "HP DeskJet 2700 series [0FC280]", "id": "192-168-178-35"}
    # The tray must compute identical CUPS queue names to the client so it can
    # tell which discovered device maps onto which queue.
    assert tray.queue_name(device) == client._queue_name(device)
    assert tray.queue_name(device) == "beagle-net-hp-deskjet-2700-series-0fc280"

    # Endpoint parsing honours the env override and falls back to the mesh agent.
    assert tray.agent_endpoints({}) == [("10.88.1.1", 47100)]
    assert tray.agent_endpoints({"BEAGLE_NETBRIDGE_AGENTS": "host:5000"}) == [("host", 5000)]

    # NetBridgeControl issues the right verbs without touching the network.
    control = tray.NetBridgeControl([("127.0.0.1", 1)])
    captured: list[dict] = []
    control.request = lambda op="catalog", **kw: captured.append({"op": op, **kw}) or {"ok": True}
    control.rescan()
    control.add_static(address="1.2.3.4", port=9100, name="x")
    control.remove_static("static-1-2-3-4-9100")
    ops = [c["op"] for c in captured]
    assert ops == ["rescan", "add_static", "remove_static"]
    assert captured[1]["address"] == "1.2.3.4"
    assert captured[2]["id"] == "static-1-2-3-4-9100"


def test_tray_uses_system_tray_and_manager_actions() -> None:
    script = TRAY.read_text(encoding="utf-8")
    assert "QSystemTrayIcon" in script
    assert "def action_add(self)" in script
    assert "def action_remove(self" in script
    assert "def action_rescan(self)" in script
    assert "def action_test_print(self" in script
    # Headless verification entrypoint for provisioning checks.
    assert "def selftest()" in script
    assert "--selftest" in script
    # Keep a strong Python reference to the manager; otherwise PyQt action
    # slots can be garbage-collected while the visible DBus menu remains stale.
    assert "manager = TrayManager(app)" in script
    assert "app.setProperty(\"beagleNetBridgeTrayManager\", manager)" in script
    # Menu updates must not race user clicks; defer rebuild while menu is open.
    assert "self.menu.aboutToShow.connect(self._on_menu_show)" in script
    assert "self.menu.aboutToHide.connect(self._on_menu_hide)" in script
    assert "self._menu_open = True" in script
    assert "if self._menu_open:" in script
    assert "self._pending_data" in script


def test_agent_service_grants_state_directory() -> None:
    # The agent persists manual devices under /var/lib/beagle/netbridge, which
    # ProtectSystem=strict would otherwise make read-only.
    for unit in (AGENT_UNIT, TC_AGENT_UNIT):
        text = unit.read_text(encoding="utf-8")
        assert "StateDirectory=beagle/netbridge" in text


def test_firstboot_installs_tray_manager() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")
    # PyQt5 powers the tray; it is installed alongside the CUPS tooling.
    assert "python3-pyqt5" in script
    assert "/usr/local/bin/beagle-netbridge-tray" in script
    # Autostart entry so the manager appears in the user's Plasma session.
    assert "/etc/xdg/autostart/beagle-netbridge-tray.desktop" in script
    assert "Exec=/usr/local/bin/beagle-netbridge-tray" in script


def test_firstboot_embedded_tray_is_non_blocking() -> None:
    script = FIRSTBOOT_TEMPLATE.read_text(encoding="utf-8")
    # The embedded tray copy must match the non-blocking design: no blocking
    # refresh from menu.aboutToShow; network/CUPS I/O runs on worker threads.
    assert "import threading" in script
    assert "dataReady = QtCore.pyqtSignal(object, object)" in script
    assert "threading.Thread(target=self._refresh_worker, daemon=True).start()" in script
    assert "def _run_action(self, op) -> None:" in script
    assert "self.menu.aboutToShow.connect(self.refresh)" not in script
    assert "self.menu.aboutToShow.connect(self._on_menu_show)" in script
    assert "self.menu.aboutToHide.connect(self._on_menu_hide)" in script
    assert "if self._menu_open:" in script
    assert "manager = TrayManager(app)" in script
    assert "app.setProperty(\"beagleNetBridgeTrayManager\", manager)" in script

