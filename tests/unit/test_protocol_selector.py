from __future__ import annotations

import os
import socket
import subprocess
import tempfile
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "protocol_selector.sh"


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _make_stub_bin(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    _write_stub(
        bindir / "ip",
        """#!/usr/bin/env bash
if [[ "${1:-}" == "link" && "${2:-}" == "show" ]]; then
  if [[ "${PROTO_TEST_WG_IF_PRESENT:-0}" == "1" ]]; then
    exit 0
  fi
fi
exit 1
""",
    )
    _write_stub(
        bindir / "wg",
        """#!/usr/bin/env bash
if [[ "${1:-}" == "show" && "${3:-}" == "latest-handshakes" ]]; then
  if [[ "${PROTO_TEST_WG_HANDSHAKE:-}" != "" ]]; then
    printf 'peer %s\\n' "${PROTO_TEST_WG_HANDSHAKE}"
  fi
  exit 0
fi
exit 1
""",
    )
    _write_stub(
        bindir / "date",
        """#!/usr/bin/env bash
if [[ "${1:-}" == "+%s" ]]; then
  printf '%s\\n' "${PROTO_TEST_NOW:-1000}"
  exit 0
fi
exec /bin/date "$@"
""",
    )
    _write_stub(
        bindir / "nc",
        """#!/usr/bin/env bash
if [[ "${PROTO_TEST_UDP_SUCCESS:-0}" == "1" ]]; then
  exit 0
fi
exit 1
""",
    )
    _write_stub(
        bindir / "timeout",
        """#!/usr/bin/env bash
shift
exec "$@"
""",
    )
    return bindir


def _run_selector(tmp_path: Path, extra_env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    bindir = _make_stub_bin(tmp_path)
    env = os.environ.copy()
    env.update(
        {
            "PATH": str(bindir) + os.pathsep + env.get("PATH", ""),
            "BEAGLE_HOST": "127.0.0.1",
            "PROTO_TEST_NOW": "1000",
        }
    )
    env.update(extra_env)
    return subprocess.run(
        ["/usr/bin/env", "bash", str(SCRIPT)],
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_vpn_required_fails_without_wireguard(tmp_path: Path) -> None:
    result = _run_selector(
        tmp_path,
        {
            "NETWORK_MODE": "vpn_required",
            "PROTO_TEST_WG_IF_PRESENT": "0",
        },
    )

    assert result.returncode == 10
    assert "network_mode=vpn_required" in result.stderr


def test_wireguard_beaglestream_is_preferred_when_udp_is_reachable(tmp_path: Path) -> None:
    result = _run_selector(
        tmp_path,
        {
            "NETWORK_MODE": "vpn_preferred",
            "PROTO_TEST_WG_IF_PRESENT": "1",
            "PROTO_TEST_WG_HANDSHAKE": "999",
            "PROTO_TEST_UDP_SUCCESS": "1",
        },
    )

    assert result.returncode == 0
    assert "PROTOCOL=beaglestream" in result.stdout
    assert "VPN=wireguard" in result.stdout


def test_direct_allowed_uses_direct_beaglestream_without_wireguard(tmp_path: Path) -> None:
    result = _run_selector(
        tmp_path,
        {
            "NETWORK_MODE": "direct_allowed",
            "PROTO_TEST_WG_IF_PRESENT": "0",
            "PROTO_TEST_UDP_SUCCESS": "1",
        },
    )

    assert result.returncode == 0
    assert "PROTOCOL=beaglestream" in result.stdout
    assert "VPN=none" in result.stdout


def test_xrdp_fallback_is_used_when_udp_is_blocked(tmp_path: Path) -> None:
    with tempfile.TemporaryDirectory() as tcp_dir:
        listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        listener.bind(("127.0.0.1", 0))
        listener.listen(1)
        port = listener.getsockname()[1]
        try:
            result = _run_selector(
                tmp_path,
                {
                    "NETWORK_MODE": "vpn_preferred",
                    "PROTO_TEST_WG_IF_PRESENT": "1",
                    "PROTO_TEST_WG_HANDSHAKE": "999",
                    "PROTO_TEST_UDP_SUCCESS": "0",
                    "RDP_PORT": str(port),
                },
            )
        finally:
            listener.close()

    assert result.returncode == 0
    assert "PROTOCOL=xrdp" in result.stdout
    assert "VPN=wireguard" in result.stdout
