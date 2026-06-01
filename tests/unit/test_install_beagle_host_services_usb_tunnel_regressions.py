from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def test_usb_tunnel_uses_authorized_keys_command() -> None:
    content = (ROOT / "scripts" / "install-beagle-host-services.sh").read_text(encoding="utf-8")

    assert 'USB_TUNNEL_AUTH_COMMAND="/usr/local/libexec/beagle-usb-authorized-keys"' in content
    assert 'install -d -m 0755 "$(dirname "$USB_TUNNEL_AUTH_COMMAND")"' in content
    assert 'cat >"$USB_TUNNEL_AUTH_COMMAND" <<EOF' in content
    assert 'AuthorizedKeysFile none' in content
    assert 'AuthorizedKeysCommand $USB_TUNNEL_AUTH_COMMAND' in content
    assert 'AuthorizedKeysCommandUser root' in content


def test_usb_tunnel_install_does_not_remove_auth_command_script() -> None:
    content = (ROOT / "scripts" / "install-beagle-host-services.sh").read_text(encoding="utf-8")

    assert 'rm -f "$USB_TUNNEL_TEST_DROPIN" "$USB_TUNNEL_AUTH_COMMAND"' not in content
    assert 'rm -f "$USB_TUNNEL_TEST_DROPIN"' in content
