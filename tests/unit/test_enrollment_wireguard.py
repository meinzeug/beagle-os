from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest


ROOT_DIR = Path(__file__).resolve().parents[2]
ENROLL_SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "enrollment_wireguard.sh"
PROTOCOL_SELECTOR_SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "protocol_selector.sh"
DEVICE_SYNC_SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "device_sync.sh"


def _write_stub(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")
    path.chmod(0o755)


def _build_wireguard_stubs(tmp_path: Path) -> Path:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)

    _write_stub(
        bindir / "wg",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"genkey\" ]]; then\n"
        "  printf 'private-key-abc\\n'\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"pubkey\" ]]; then\n"
        "  cat >/dev/null\n"
        "  printf 'public-key-xyz\\n'\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"show\" ]]; then\n"
        "  if [[ \"${3:-}\" == \"latest-handshakes\" ]]; then\n"
        "    printf 'peer1 %s\\n' \"$(date +%s)\"\n"
        "    exit 0\n"
        "  fi\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"setconf\" && -n \"${WG_SETCONF_LOG:-}\" ]]; then\n"
        "  printf '%s\\n' \"$*\" >>\"${WG_SETCONF_LOG}\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )

    _write_stub(
        bindir / "ip",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ -n \"${IP_LOG:-}\" ]]; then\n"
        "  printf '%s\\n' \"$*\" >>\"${IP_LOG}\"\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"link\" && \"${2:-}\" == \"show\" ]]; then\n"
        "  exit \"${IP_LINK_SHOW_EXIT:-1}\"\n"
        "fi\n"
        "exit 0\n",
    )

    _write_stub(
        bindir / "curl",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "out=''\n"
        "data=''\n"
        "while [[ $# -gt 0 ]]; do\n"
        "  case \"$1\" in\n"
        "    --output)\n"
        "      out=\"$2\"\n"
        "      shift 2\n"
        "      ;;\n"
        "    --data)\n"
        "      data=\"$2\"\n"
        "      shift 2\n"
        "      ;;\n"
        "    *)\n"
        "      shift\n"
        "      ;;\n"
        "  esac\n"
        "done\n"
        "if [[ -n \"${CURL_DATA_LOG:-}\" ]]; then\n"
        "  printf '%s\\n' \"${data}\" >\"${CURL_DATA_LOG}\"\n"
        "fi\n"
        "python3 - <<'PY' >\"${out:-/tmp/wg-register-response.json}\"\n"
        "import json\n"
        "import os\n"
        "payload = {\n"
        "  'server_public_key': os.environ.get('CURL_SERVER_PUBLIC_KEY', ''),\n"
        "  'server_endpoint': os.environ.get('CURL_SERVER_ENDPOINT', ''),\n"
        "  'allowed_ips': os.environ.get('CURL_ALLOWED_IPS', '10.88.0.0/16'),\n"
        "  'client_ip': os.environ.get('CURL_CLIENT_IP', ''),\n"
        "  'dns': os.environ.get('CURL_DNS', '10.88.0.1'),\n"
        "}\n"
        "print(json.dumps(payload))\n"
        "PY\n"
        "printf '%s' \"${CURL_HTTP_CODE:-200}\"\n",
    )

    _write_stub(
        bindir / "nc",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "exit 0\n",
    )

    return bindir


def _require_jq() -> None:
    if shutil.which("jq") is None:
        pytest.skip("jq is required for enrollment_wireguard.sh")


def test_enrollment_wireguard_writes_config_and_brings_interface_up(tmp_path: Path) -> None:
    _require_jq()
    bindir = _build_wireguard_stubs(tmp_path)
    wg_conf = tmp_path / "wireguard" / "wg-beagle.conf"
    wg_keys = tmp_path / "keys"
    curl_data_log = tmp_path / "curl-data.json"
    ip_log = tmp_path / "ip.log"
    wg_setconf_log = tmp_path / "wg-setconf.log"
    resolv_conf = tmp_path / "resolv.conf"

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["WG_CONF"] = str(wg_conf)
    env["WG_KEYS_DIR"] = str(wg_keys)
    env["CURL_DATA_LOG"] = str(curl_data_log)
    env["IP_LOG"] = str(ip_log)
    env["WG_SETCONF_LOG"] = str(wg_setconf_log)
    env["WG_RESOLV_CONF"] = str(resolv_conf)
    env["BEAGLE_CONTROL_PLANE"] = "https://control.example"
    env["BEAGLE_DEVICE_ID"] = "endpoint-001"
    env["BEAGLE_ENROLLMENT_TOKEN"] = "enroll-token"
    env["CURL_HTTP_CODE"] = "200"
    env["CURL_SERVER_PUBLIC_KEY"] = "server-pub-key"
    env["CURL_SERVER_ENDPOINT"] = "vpn.beagle-os.com:51820"
    env["CURL_ALLOWED_IPS"] = "10.88.0.0/16"
    env["CURL_CLIENT_IP"] = "10.88.10.5/32"
    env["CURL_DNS"] = "10.88.0.1"

    subprocess.run(["bash", str(ENROLL_SCRIPT)], cwd=str(ROOT_DIR), env=env, check=True)

    conf_text = wg_conf.read_text(encoding="utf-8")
    assert "Address = 10.88.10.5/32" in conf_text
    assert "PrivateKey = private-key-abc" in conf_text
    assert "PublicKey = server-pub-key" in conf_text
    assert "Endpoint = vpn.beagle-os.com:51820" in conf_text
    assert "AllowedIPs = 10.88.0.0/16" in conf_text
    assert "PersistentKeepalive = 25" in conf_text

    payload = json.loads(curl_data_log.read_text(encoding="utf-8"))
    assert payload["device_id"] == "endpoint-001"
    assert payload["public_key"] == "public-key-xyz"
    assert payload["token"] == "enroll-token"

    wg_setconf_text = wg_setconf_log.read_text(encoding="utf-8")
    assert "setconf wg-beagle " in wg_setconf_text

    ip_text = ip_log.read_text(encoding="utf-8")
    assert "link add wg-beagle type wireguard" in ip_text
    assert "address add 10.88.10.5/32 dev wg-beagle" in ip_text
    assert "route replace 10.88.0.0/16 dev wg-beagle" in ip_text
    assert resolv_conf.read_text(encoding="utf-8") == "nameserver 10.88.0.1\n"


def test_enrollment_wireguard_fails_on_incomplete_control_plane_response(tmp_path: Path) -> None:
    _require_jq()
    bindir = _build_wireguard_stubs(tmp_path)
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["WG_CONF"] = str(tmp_path / "wireguard" / "wg-beagle.conf")
    env["WG_KEYS_DIR"] = str(tmp_path / "keys")
    env["BEAGLE_CONTROL_PLANE"] = "https://control.example"
    env["BEAGLE_DEVICE_ID"] = "endpoint-001"
    env["CURL_HTTP_CODE"] = "200"
    env["CURL_SERVER_PUBLIC_KEY"] = "server-pub-key"
    env["CURL_SERVER_ENDPOINT"] = "vpn.beagle-os.com:51820"

    result = subprocess.run(["bash", str(ENROLL_SCRIPT)], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True)

    assert result.returncode == 3
    assert "Incomplete peer config" in result.stderr


def test_enrollment_wireguard_supports_manager_bearer_registration(tmp_path: Path) -> None:
    _require_jq()
    bindir = _build_wireguard_stubs(tmp_path)
    curl_path = bindir / "curl"
    curl_path.write_text(
        curl_path.read_text(encoding="utf-8").replace(
            "done\\n"
            "if [[ -n \"${CURL_DATA_LOG:-}\" ]]; then\\n",
            "done\\n"
            "printf '%s\\n' \"$*\" >\"${CURL_ARGS_LOG:?}\"\\n"
            "if [[ -n \"${CURL_DATA_LOG:-}\" ]]; then\\n",
        ),
        encoding="utf-8",
    )
    curl_path.chmod(0o755)
    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["WG_CONF"] = str(tmp_path / "wireguard" / "wg-beagle.conf")
    env["WG_KEYS_DIR"] = str(tmp_path / "keys")
    env["CURL_ARGS_LOG"] = str(tmp_path / "curl-args.log")
    env["CURL_DATA_LOG"] = str(tmp_path / "curl-data.json")
    env["WG_SETCONF_LOG"] = str(tmp_path / "wg-setconf.log")
    env["IP_LOG"] = str(tmp_path / "ip.log")
    env["WG_RESOLV_CONF"] = str(tmp_path / "resolv.conf")
    env["BEAGLE_CONTROL_PLANE"] = "https://control.example"
    env["BEAGLE_DEVICE_ID"] = "endpoint-001"
    env["BEAGLE_MANAGER_TOKEN"] = "endpoint-bearer"
    env["CURL_HTTP_CODE"] = "200"
    env["CURL_SERVER_PUBLIC_KEY"] = "server-pub-key"
    env["CURL_SERVER_ENDPOINT"] = "vpn.beagle-os.com:51820"
    env["CURL_ALLOWED_IPS"] = "0.0.0.0/0"
    env["CURL_CLIENT_IP"] = "10.88.10.5/32"
    env["CURL_DNS"] = "1.1.1.1"

    subprocess.run(["bash", str(ENROLL_SCRIPT)], cwd=str(ROOT_DIR), env=env, check=True)

    curl_args = (tmp_path / "curl-args.log").read_text(encoding="utf-8")
    assert "Authorization: Bearer endpoint-bearer" in curl_args


def test_post_enrollment_runtime_prefers_wireguard_for_heartbeat_and_streaming(tmp_path: Path) -> None:
    bindir = _build_wireguard_stubs(tmp_path)

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["BEAGLE_HOST"] = "10.88.10.20"
    env["NETWORK_MODE"] = "vpn_required"
    env["IP_LINK_SHOW_EXIT"] = "0"

    sync_cmd = (
        f"source {DEVICE_SYNC_SCRIPT}\n"
        "runtime_device_sync_payload endpoint-001 thin-01 wg-beagle 1 10.88.10.5/32\n"
    )
    sync_result = subprocess.run(
        ["bash", "-lc", sync_cmd],
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    payload = json.loads(sync_result.stdout)
    assert payload["vpn"]["active"] is True
    assert payload["vpn"]["interface"] == "wg-beagle"
    assert payload["vpn"]["assigned_ip"] == "10.88.10.5/32"

    stream_result = subprocess.run(
        ["bash", str(PROTOCOL_SELECTOR_SCRIPT)],
        cwd=str(ROOT_DIR),
        env=env,
        text=True,
        capture_output=True,
        check=True,
    )
    assert "PROTOCOL=beaglestream" in stream_result.stdout
    assert "VPN=wireguard" in stream_result.stdout
