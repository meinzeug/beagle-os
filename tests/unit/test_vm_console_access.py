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
    monkeypatch.setattr(service, "_create_spice_proxy", lambda target_host, target_port: {"host": "srv1.beagle-os.com", "port": 46002})

    body, filename = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert filename == "beagle-vm-100.vv"
    assert "port=46002" in text
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
    monkeypatch.setattr(service, "_create_spice_proxy", lambda target_host, target_port: {"host": "srv1.beagle-os.com", "port": 46003})

    body, _ = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert "port=46003" in text
    assert "password=legacy-static-password" in text
    assert "password=ticket-xyz" not in text
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
    monkeypatch.setattr(service, "_runtime_spice_auth_mode", lambda vmid, domain_name=None: "ticket")
    monkeypatch.setattr(service, "_create_spice_proxy", lambda target_host, target_port: {"host": "srv1.beagle-os.com", "port": 46004})

    try:
        service.render_spice_vv(_Vm())
        assert False, "expected ValueError"
    except ValueError as exc:
        assert "SPICE-Ticket konnte nicht erstellt werden" in str(exc)


def test_render_spice_vv_falls_back_to_no_password_when_runtime_auth_is_none(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {"listen": "0.0.0.0", "port": 5902, "tls_port": 0, "password": ""},
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("monitor failed")

    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", _raise)
    monkeypatch.setattr(service, "_runtime_spice_auth_mode", lambda vmid, domain_name=None: "none")
    monkeypatch.setattr(service, "_create_spice_proxy", lambda target_host, target_port: {"host": "srv1.beagle-os.com", "port": 46005})

    body, _ = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert "port=46005" in text
    assert "password=" not in text


def test_render_spice_vv_falls_back_to_static_graphics_password_when_ticket_fails(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {
            "listen": "0.0.0.0",
            "port": 5902,
            "tls_port": 0,
            "password": "static-spice-pass",
        },
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("monitor failed")

    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", _raise)
    monkeypatch.setattr(service, "_runtime_spice_auth_mode", lambda vmid, domain_name=None: "none")
    monkeypatch.setattr(service, "_create_spice_proxy", lambda target_host, target_port: {"host": "srv1.beagle-os.com", "port": 46007})

    body, _ = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert "port=46007" in text
    assert "password=static-spice-pass" in text


def test_render_spice_vv_emits_http_connect_proxy_when_enabled(monkeypatch) -> None:
    monkeypatch.setenv("BEAGLE_SPICE_HTTP_CONNECT_PROXY", "1")
    monkeypatch.setenv("BEAGLE_SPICE_HTTP_PROXY_HOST", "srv1.beagle-os.com")
    monkeypatch.setenv("BEAGLE_SPICE_HTTP_PROXY_PORT", "443")
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {"listen": "0.0.0.0", "port": 5902, "tls_port": 0, "password": ""},
    )
    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", lambda vmid, domain_name=None: "ticket-xyz")
    monkeypatch.setattr(
        service,
        "_create_spice_proxy",
        lambda target_host, target_port: {
            "host": "srv1.beagle-os.com",
            "port": 46006,
            "proxy_token": "token-abc",
        },
    )

    body, _ = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert "host=127.0.0.1" in text
    assert "port=46006" in text
    assert "proxy=http://beagle:token-abc@srv1.beagle-os.com:443" in text


def test_authorize_spice_proxy_connect_validates_token_and_target(monkeypatch) -> None:
    service = _service()
    monkeypatch.setattr(service, "_spice_proxy_bind_host", "127.0.0.1")
    proxy = service._create_spice_proxy(target_host="127.0.0.1", target_port=5902)
    port = int(proxy["port"])
    token = str(proxy["proxy_token"])

    assert service.authorize_spice_proxy_connect(
        target_host="127.0.0.1",
        target_port=port,
        proxy_token=token,
    )
    assert not service.authorize_spice_proxy_connect(
        target_host="srv1.beagle-os.com",
        target_port=port,
        proxy_token=token,
    )
    assert not service.authorize_spice_proxy_connect(
        target_host="127.0.0.1",
        target_port=port,
        proxy_token="wrong-token",
    )


def test_render_spice_vv_emits_keymap_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("BEAGLE_SPICE_KEYMAP", "de")
    service = _service()
    monkeypatch.setattr(
        service,
        "_libvirt_spice_graphics",
        lambda vmid, domain_name=None: {"listen": "0.0.0.0", "port": 5902, "tls_port": 0, "password": ""},
    )
    monkeypatch.setattr(service, "_issue_ephemeral_spice_ticket", lambda vmid, domain_name=None: "ticket-xyz")
    monkeypatch.setattr(
        service,
        "_create_spice_proxy",
        lambda target_host, target_port: {"host": "srv1.beagle-os.com", "port": 46008},
    )

    body, _ = service.render_spice_vv(_Vm())
    text = body.decode("utf-8")

    assert "keymap=de-de" in text