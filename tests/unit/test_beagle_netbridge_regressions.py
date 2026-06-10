from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NETBRIDGE_DIR = ROOT / "beagle-host" / "netbridge"
AGENT = NETBRIDGE_DIR / "beagle-netbridge-agent"
CLIENT = NETBRIDGE_DIR / "beagle-netbridge-client"
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
