from __future__ import annotations

import os
import subprocess
from pathlib import Path


ROOT_DIR = Path(__file__).resolve().parents[2]
LAUNCHER = ROOT_DIR / "thin-client-assistant" / "runtime" / "launch-beagle-stream-client.sh"


def _write_executable(path: Path, text: str) -> None:
    path.write_text(text, encoding="utf-8")
    path.chmod(0o755)


def test_launcher_restores_wireguard_peer_with_base64_padding_from_state_file(tmp_path: Path) -> None:
    bindir = tmp_path / "bin"
    bindir.mkdir(parents=True, exist_ok=True)

    wg_set_log = tmp_path / "wg-set.log"
    peer_state = tmp_path / "wg-peer.env"
    peer_state.write_text(
        "\n".join(
            [
                "WG_PEER_PUBLIC_KEY=abcdeFGHijklmnoPQRSTuvwxyz0123456789+/==",
                "WG_PEER_ENDPOINT=10.0.0.1:51820",
                "WG_PEER_ALLOWED_IPS=10.88.0.0/16,192.168.123.0/24",
                "WG_PEER_KEEPALIVE=25",
            ]
        )
        + "\n",
        encoding="utf-8",
    )

    _write_executable(
        bindir / "sudo",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ $# -eq 0 ]]; then exit 0; fi\n"
        "exec \"$@\"\n",
    )
    _write_executable(
        bindir / "ip",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"link\" && \"${2:-}\" == \"show\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(
        bindir / "wg",
        "#!/usr/bin/env bash\n"
        "set -euo pipefail\n"
        "if [[ \"${1:-}\" == \"show\" && \"${3:-}\" == \"peers\" ]]; then\n"
        "  exit 0\n"
        "fi\n"
        "if [[ \"${1:-}\" == \"set\" ]]; then\n"
        "  printf '%s\n' \"$*\" >>\"${WG_SET_LOG:?}\"\n"
        "  exit 0\n"
        "fi\n"
        "exit 0\n",
    )
    _write_executable(bindir / "systemctl", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bindir / "wg-quick", "#!/usr/bin/env bash\nexit 0\n")
    _write_executable(bindir / "beagle-stream", "#!/usr/bin/env bash\nexit 0\n")

    stubs = tmp_path / "stubs"
    stubs.mkdir(parents=True, exist_ok=True)

    common_sh = stubs / "common.sh"
    common_sh.write_text(
        "#!/usr/bin/env bash\n"
        "load_runtime_config() { return 0; }\n"
        "beagle_log_event() { return 0; }\n"
        "configure_audio_runtime() { return 0; }\n"
        "configure_graphics_runtime() { return 0; }\n"
        "record_decoder_choice() { return 0; }\n"
        "beagle_stream_client_audio_driver() { printf '%s' auto; }\n"
        "beagle_stream_client_video_decoder() { printf '%s' software; }\n"
        "beagle_stream_enrollment_config() { printf '%s' /etc/beagle/enrollment.conf; }\n"
        "beagle_stream_client_resolution() { printf '%s' 1920x1080; }\n"
        "beagle_stream_client_fps() { printf '%s' 60; }\n",
        encoding="utf-8",
    )

    targeting_sh = stubs / "targeting.sh"
    targeting_sh.write_text(
        "#!/usr/bin/env bash\n"
        "beagle_stream_client_host() { printf '%s' ''; }\n"
        "beagle_stream_client_connect_host() { printf '%s' ''; }\n"
        "beagle_stream_client_port() { printf '%s' ''; }\n"
        "beagle_stream_client_app() { printf '%s' Desktop; }\n"
        "beagle_stream_hostless_enabled() { return 0; }\n"
        "beagle_stream_broker_connection() { return 1; }\n"
        "beagle_stream_client_local_host() { printf '%s' 127.0.0.1; }\n"
        "beagle_stream_connection_method() { printf '%s' broker; }\n",
        encoding="utf-8",
    )

    cli_sh = stubs / "cli.sh"
    cli_sh.write_text(
        "#!/usr/bin/env bash\n"
        "beagle_stream_client_bin() { printf '%s' beagle-stream; }\n",
        encoding="utf-8",
    )

    host_sync_sh = stubs / "host_sync.sh"
    host_sync_sh.write_text(
        "#!/usr/bin/env bash\n"
        "wait_for_stream_target() { return 0; }\n"
        "ensure_beagle_stream_client_local_host_route() { return 1; }\n"
        "bootstrap_beagle_stream_client() { return 0; }\n"
        "beagle_stream_client_host_configured() { return 1; }\n"
        "seed_beagle_stream_client_host_from_runtime_config() { return 1; }\n"
        "retarget_beagle_stream_client_host_from_runtime_config() { return 1; }\n"
        "beagle_stream_client_stream_ready() { return 0; }\n",
        encoding="utf-8",
    )

    remote_api_sh = stubs / "remote_api.sh"
    remote_api_sh.write_text("#!/usr/bin/env bash\n", encoding="utf-8")

    manager_sh = stubs / "manager.sh"
    manager_sh.write_text(
        "#!/usr/bin/env bash\n"
        "fetch_beagle_stream_client_current_session_via_manager() { return 1; }\n"
        "retarget_beagle_stream_client_host_from_session_broker_response() { return 1; }\n"
        "prepare_beagle_stream_client_stream_via_manager() { return 1; }\n",
        encoding="utf-8",
    )

    pairing_sh = stubs / "pairing.sh"
    pairing_sh.write_text(
        "#!/usr/bin/env bash\n"
        "ensure_paired() { return 0; }\n"
        "resolve_stream_app_name() { printf '%s' \"$1\"; }\n",
        encoding="utf-8",
    )

    runtime_exec_sh = stubs / "runtime_exec.sh"
    runtime_exec_sh.write_text(
        "#!/usr/bin/env bash\n"
        "build_stream_args() {\n"
        "  local -n out_ref=$1\n"
        "  out_ref=(\"$(beagle_stream_client_bin)\" stream \"$(beagle_stream_client_app)\")\n"
        "}\n",
        encoding="utf-8",
    )

    xdg_runtime_dir = tmp_path / "run"
    xdg_runtime_dir.mkdir(parents=True, exist_ok=True)

    env = os.environ.copy()
    env["PATH"] = str(bindir) + os.pathsep + env.get("PATH", "")
    env["XDG_RUNTIME_DIR"] = str(xdg_runtime_dir)
    env["WG_SET_LOG"] = str(wg_set_log)
    env["BEAGLE_WG_PEER_RESTORE_STATE_FILE"] = str(peer_state)
    env["PVE_THIN_CLIENT_BEAGLE_STREAM_CLIENT_MAX_RESTARTS"] = "1"
    env["BEAGLE_STREAM_CLIENT_TARGETING_SH"] = str(targeting_sh)
    env["BEAGLE_STREAM_CLIENT_PAIRING_SH"] = str(pairing_sh)
    env["BEAGLE_STREAM_CLIENT_RUNTIME_EXEC_SH"] = str(runtime_exec_sh)
    env["BEAGLE_STREAM_CLIENT_CLI_SH"] = str(cli_sh)
    env["BEAGLE_STREAM_CLIENT_HOST_SYNC_SH"] = str(host_sync_sh)
    env["BEAGLE_STREAM_CLIENT_REMOTE_API_SH"] = str(remote_api_sh)
    env["BEAGLE_STREAM_CLIENT_MANAGER_REGISTRATION_SH"] = str(manager_sh)

    # Put common.sh next to the launcher's expected location via temporary copy tree.
    runtime_dir = tmp_path / "runtime"
    runtime_dir.mkdir(parents=True, exist_ok=True)
    launcher_copy = runtime_dir / "launch-beagle-stream-client.sh"
    launcher_copy.write_text(LAUNCHER.read_text(encoding="utf-8"), encoding="utf-8")
    launcher_copy.chmod(0o755)
    (runtime_dir / "common.sh").write_text(common_sh.read_text(encoding="utf-8"), encoding="utf-8")

    subprocess.run(["bash", str(launcher_copy)], cwd=str(ROOT_DIR), env=env, check=True)

    wg_set_calls = wg_set_log.read_text(encoding="utf-8")
    assert "set wg-beagle peer abcdeFGHijklmnoPQRSTuvwxyz0123456789+/==" in wg_set_calls
    assert "allowed-ips 10.88.0.0/16,192.168.123.0/24" in wg_set_calls
    assert "persistent-keepalive 25" in wg_set_calls
