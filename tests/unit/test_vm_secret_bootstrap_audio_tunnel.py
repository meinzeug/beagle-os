from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[2]
MODULE_PATH = ROOT / "beagle-host" / "services" / "vm_secret_bootstrap.py"
spec = importlib.util.spec_from_file_location("vm_secret_bootstrap", MODULE_PATH)
assert spec is not None and spec.loader is not None
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
VmSecretBootstrapService = module.VmSecretBootstrapService


def _service() -> VmSecretBootstrapService:
    return VmSecretBootstrapService(
        data_dir=lambda: Path("/tmp/beagle-manager"),
        load_vm_secret=lambda node, vmid: None,
        public_server_name="srv1.beagle-os.com",
        public_stream_host="",
        random_pin=lambda: "123456",
        random_secret=lambda size: "x" * size,
        resolve_beagle_stream_server_pinned_pubkey=lambda vm: "",
        safe_slug=lambda value, fallback="node": str(value or fallback),
        save_vm_secret=lambda node, vmid, secret: secret,
        session_script_path=Path("/opt/beagle/beagle-host/bin/beagle-usb-tunnel-session"),
        store_endpoint_token=lambda token, payload: payload,
        token_urlsafe=lambda size: "t" * size,
        usb_tunnel_attach_host="192.168.123.1",
        usb_tunnel_auth_dir=None,
        usb_tunnel_auth_root=None,
        usb_tunnel_base_port=43000,
        usb_tunnel_home=None,
        usb_tunnel_hostkey_file=Path("/nonexistent"),
        usb_tunnel_user="beagle-tunnel",
    )


def test_usb_tunnel_authorized_key_permits_audio_input_bridge_port() -> None:
    service = _service()
    vm = SimpleNamespace(node="beagle-0", vmid=100)
    secret = {
        "usb_tunnel_public_key": "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIFakeKey beagle-vm100-usb",
        "usb_tunnel_port": 43100,
        "usb_tunnel_audio_input_port": 43200,
        "usb_tunnel_camera_port": 53100,
    }

    line = service.usb_tunnel_authorized_key_line(vm, secret)

    assert 'permitlisten="192.168.123.1:43100"' in line
    assert 'permitlisten="192.168.123.1:43200"' in line
    assert 'permitlisten="192.168.123.1:53100"' in line


def test_default_usb_audio_input_port_tracks_vm_tunnel_port() -> None:
    service = _service()

    assert service.default_usb_audio_input_port(100, 43100) == 43200
    assert service.default_usb_audio_input_port(201, 43201) == 43301
