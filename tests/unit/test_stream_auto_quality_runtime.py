from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
PROFILE_SCRIPT = ROOT_DIR / "thin-client-assistant" / "runtime" / "beagle_stream_client_stream_profile.sh"


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def test_auto_quality_detects_good_link_and_writes_state(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)
    state_file = tmp_path / "stream-auto-profile.env"

    _write_executable(
        bindir / "ping",
        "#!/usr/bin/env bash\n"
        "cat <<'OUT'\n"
        "PING 192.168.123.114 (192.168.123.114) 56(84) bytes of data.\n"
        "64 bytes from 192.168.123.114: icmp_seq=1 ttl=64 time=2.4 ms\n"
        "64 bytes from 192.168.123.114: icmp_seq=2 ttl=64 time=4.0 ms\n"
        "64 bytes from 192.168.123.114: icmp_seq=3 ttl=64 time=5.1 ms\n"
        "64 bytes from 192.168.123.114: icmp_seq=4 ttl=64 time=3.7 ms\n"
        "64 bytes from 192.168.123.114: icmp_seq=5 ttl=64 time=6.2 ms\n"
        "\n"
        "--- 192.168.123.114 ping statistics ---\n"
        "5 packets transmitted, 5 received, 0% packet loss, time 4005ms\n"
        "rtt min/avg/max/mdev = 2.400/4.280/6.200/1.270 ms\n"
        "OUT\n",
    )
    _write_executable(
        bindir / "ip",
        "#!/usr/bin/env bash\n"
        "if [[ \"$*\" == \"route get 192.168.123.114\" ]]; then\n"
        "  printf '192.168.123.114 dev wg-beagle src 10.88.1.1 uid 0\\n'\n"
        "  exit 0\n"
        "fi\n"
        "exit 1\n",
    )

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["BEAGLE_STREAM_AUTO_PROFILE_ENV"] = str(state_file)

    cmd = (
        f"source {PROFILE_SCRIPT}\n"
        "beagle_stream_client_connect_host() { printf '%s\\n' 192.168.123.114; }\n"
        "beagle_stream_client_host() { printf '%s\\n' 192.168.123.114; }\n"
        "beagle_log_event() { return 0; }\n"
        "local_display_resolution() { printf '%s\\n' 1920x1080; }\n"
        "export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION=auto\n"
        "export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS=auto\n"
        "export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE=auto\n"
        "export PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE=auto\n"
        "beagle_stream_apply_auto_profile\n"
        "printf '%s %s %s %s %s\\n' \"$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_BUCKET\" \"$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_RESOLUTION\" \"$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_FPS\" \"$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_BITRATE\" \"$PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_PACKET_SIZE\"\n"
    )
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), env=env, text=True, capture_output=True, check=True)

    assert result.stdout.strip() == "ultra 1920x1080 60 45000 1392"
    state = state_file.read_text(encoding="utf-8")
    assert "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_BUCKET=ultra" in state
    assert "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_PACKET_LOSS=0" in state
    assert "PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_AUTO_QUALITY_RTT_AVG_MS=4" in state


def test_auto_quality_bucket_degrades_on_loss_and_latency() -> None:
    cmd = (
        f"source {PROFILE_SCRIPT}\n"
        "beagle_stream_auto_quality_bucket 8 85 150 100\n"
    )
    result = subprocess.run(["bash", "-lc", cmd], cwd=str(ROOT_DIR), text=True, capture_output=True, check=True)

    assert result.stdout.strip() == "low"