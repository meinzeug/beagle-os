from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SESSION_SCRIPT = ROOT / "beagle-host" / "bin" / "beagle-usb-tunnel-session"
HOST_INSTALL_SCRIPT = ROOT / "scripts" / "install-beagle-host-services.sh"


def test_usb_tunnel_session_reaps_stale_reverse_listener_sessions() -> None:
    text = SESSION_SCRIPT.read_text(encoding="utf-8")

    assert "beagle-usb tunnel does not allow remote commands" in text
    assert "USB_TUNNEL_STALE_SECONDS" in text
    assert "USB_TUNNEL_PORTS" in text
    assert "SELF_SESSION_PID" in text
    assert "reap_stale_reverse_listener_sessions()" in text
    assert 'ss -ltnp "sport = :${port}"' in text
    assert "ps -o etimes= -p" in text
    assert "if (( etimes < USB_TUNNEL_STALE_SECONDS )); then" in text
    assert 'kill "$pid" >/dev/null 2>&1 || true' in text
    assert "sleep 30" in text


def test_install_script_enforces_ssh_keepalive_for_usb_tunnel_user() -> None:
    text = HOST_INSTALL_SCRIPT.read_text(encoding="utf-8")

    assert "Match User $USB_TUNNEL_USER" in text
    assert "AllowTcpForwarding remote" in text
    assert "GatewayPorts clientspecified" in text
    assert "TCPKeepAlive yes" in text
    assert "ClientAliveInterval 20" in text
    assert "ClientAliveCountMax 2" in text

    # TCPKeepAlive is a global directive and is rejected inside a Match block
    # (sshd refuses to start). It must be emitted before the Match block.
    keepalive_index = text.index("TCPKeepAlive yes")
    match_index = text.index("Match User $USB_TUNNEL_USER")
    assert keepalive_index < match_index


def test_install_script_validates_generated_sshd_dropin_before_use() -> None:
    text = HOST_INSTALL_SCRIPT.read_text(encoding="utf-8")

    # A malformed sshd drop-in makes sshd refuse to start and locks the operator
    # out of the server. The installer must validate the generated drop-in with
    # `sshd -t` and remove it (failing the install) rather than persist a config
    # that bricks SSH on the next boot.
    assert 'SSHD_BIN="$(command -v sshd 2>/dev/null || echo /usr/sbin/sshd)"' in text
    dropin_index = text.index('chmod 0644 "$USB_TUNNEL_SSHD_DROPIN"')
    validation_index = text.index('"$SSHD_BIN" -t', dropin_index)
    remove_index = text.index('rm -f "$USB_TUNNEL_SSHD_DROPIN"', dropin_index)
    assert dropin_index < validation_index < remove_index


def test_install_script_never_restarts_sshd_with_invalid_config() -> None:
    text = HOST_INSTALL_SCRIPT.read_text(encoding="utf-8")

    # The sshd restart must be guarded by a config validation so a bad config can
    # never take the daemon down and lock the operator out of the server.
    restart_index = text.index("systemctl restart ssh.service")
    guard_index = text.rindex('"$SSHD_BIN" -t', 0, restart_index)
    assert guard_index < restart_index
    assert "refusing to restart sshd because configuration validation failed" in text
