from __future__ import annotations

import sys
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SERVICES_DIR = ROOT_DIR / "beagle-host" / "services"
for _p in [str(ROOT_DIR), str(SERVICES_DIR)]:
    if _p not in sys.path:
        sys.path.insert(0, _p)

from vm_console_access import VmConsoleAccessService


class _Vm:
    vmid = 100
    node = "srv1.beagle-os.com"
    name = "beagle-100"


def _service() -> VmConsoleAccessService:
    return VmConsoleAccessService(
        ensure_vm_secret=lambda _vm: {
            "guest_password": "LoL123LoL",
            "password": "LoL123LoL",
        },
        host_provider_kind="beagle",
        listify=lambda value: list(value) if isinstance(value, (list, tuple, set)) else [str(value)],
        novnc_path="/novnc",
        novnc_token_file="/tmp/beagle-test-novnc-token-file",
        public_server_name="srv1.beagle-os.com",
    )


def test_render_spice_vv_ignores_guest_password_when_spice_has_no_auth(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {"listen": "0.0.0.0", "port": 5902, "tls_port": 0, "password": ""},
    )
    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", lambda vmid, domain_name=None: "ticket-abc")

    body, filename = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert filename == "beagle-vm-100.vv"
    assert "port=5902" in text
    assert "host=srv1.beagle-os.com" in text
    assert "password=ticket-abc" in text
    assert "password=LoL123LoL" not in text


def test_render_spice_vv_uses_spice_password_when_configured(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {
            "listen": "0.0.0.0",
            "port": 5902,
            "tls_port": 0,
            "password": "legacy-static-password",
        },
    )
    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", lambda vmid, domain_name=None: "ticket-xyz")

    body, _ = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert "password=ticket-xyz" in text
    assert "password=legacy-static-password" not in text
    assert "password=LoL123LoL" not in text


def test_render_spice_vv_raises_when_ticket_cannot_be_created(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {"listen": "0.0.0.0", "port": 5902, "tls_port": 0, "password": ""},
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("monitor failed")

    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", _raise)

    try:
        service.render_spice_vv(_Vm())
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "SPICE-Ticket konnte nicht erstellt werden" in str(exc)